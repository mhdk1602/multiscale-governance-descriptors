"""Pivot C: Longitudinal topological drift in dbt lineage graphs.

Extracts dbt manifests at quarterly commits from public dbt project git
histories, computes D1-D4 descriptors per timestamp, and detects drift
events using control-chart methods on descriptor time series.

Public dbt projects analyzed: Cal-ITP, Mattermost.

Method:
  1. Walk git history of each project, sample one commit per 30-day window
  2. At each commit, checkout the repo and extract lineage graph via ref() parsing
  3. Compute D1-D4 + cycle rank on each snapshot
  4. Build descriptor time series
  5. Apply control chart (X-bar with rolling std) to detect drift events
  6. Annotate drift events with commit-window messages

Outputs:
  - artifacts/phase_4/longitudinal_<project>.csv: per-snapshot descriptors
  - artifacts/phase_4/drift_events_<project>.csv: detected drift events
  - artifacts/phase_4/summary.json
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import json
import re
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

import numpy as np
import pandas as pd
import networkx as nx

from governance_descriptors.community_stability import community_descriptor_summary
from governance_descriptors.spectral import spectral_descriptors
from governance_descriptors.blast_radius import concentration_profile
from governance_descriptors.persistent_homology import cycle_rank_descriptors


def git_run(cwd, *args):
    result = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True)
    return result.stdout.strip()


def list_commits_in_path(repo, sub_path, since_days=None):
    """Return [(date, sha), ...] for commits touching sub_path, oldest-first."""
    args = ['log', '--reverse', '--pretty=format:%ai|%H', '--', sub_path]
    if since_days:
        args.insert(1, f'--since={since_days} days ago')
    out = git_run(repo, *args)
    rows = []
    for line in out.splitlines():
        if '|' not in line:
            continue
        date_str, sha = line.split('|', 1)
        try:
            dt = datetime.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S')
            rows.append((dt, sha))
        except ValueError:
            continue
    return rows


def sample_one_per_window(commits, window_days=30):
    """Keep the last commit in each rolling window_days bucket."""
    if not commits:
        return []
    sampled = []
    bucket_end = commits[0][0] + timedelta(days=window_days)
    last_in_bucket = commits[0]
    for dt, sha in commits[1:]:
        if dt < bucket_end:
            last_in_bucket = (dt, sha)
        else:
            sampled.append(last_in_bucket)
            while dt >= bucket_end:
                bucket_end += timedelta(days=window_days)
            last_in_bucket = (dt, sha)
    sampled.append(last_in_bucket)
    return sampled


def extract_lineage_at_commit(repo, sha, models_subpath):
    """Checkout commit, parse SQL files for ref() dependencies, return DiGraph."""
    git_run(repo, 'checkout', '-q', sha)
    models_dir = Path(repo) / models_subpath
    if not models_dir.exists():
        return None

    # Exclusions are tested against the path relative to the models directory.
    # Testing the absolute path, as this did originally, drops every model in
    # any checkout whose parent directory happens to contain "macros".
    sql_files = [f for f in models_dir.rglob("*.sql")
                 if 'macros' not in str(f.relative_to(models_dir))
                 and '/tests/' not in str(f.relative_to(models_dir))
                 and '/snapshots/' not in str(f.relative_to(models_dir))]
    ref_pat = re.compile(r"\{\{\s*ref\(\s*['\"](\w+)['\"]\s*\)\s*\}\}", re.IGNORECASE)
    model_names = {f.stem for f in sql_files}
    g = nx.DiGraph()
    # Sorted, not set order. Python randomises string set iteration per process
    # via PYTHONHASHSEED, NetworkX's Louvain is an order-sensitive greedy pass,
    # and D1_csi therefore differed between runs of this script on an unchanged
    # repository. The artifacts in artifacts/phase_4/ were produced before this
    # line was sorted, so their D1_csi and D1_n_comm columns will not reproduce.
    # N, M, D2 and D4 never depended on the ordering and reproduce exactly.
    g.add_nodes_from(sorted(model_names))
    for f in sorted(sql_files, key=lambda p: str(p)):
        try:
            for r in ref_pat.findall(f.read_text(errors='ignore')):
                if r in model_names:
                    g.add_edge(r, f.stem)
        except Exception:
            pass
    return g


def compute_descriptors_safe(g):
    n = g.number_of_nodes()
    m = g.number_of_edges()
    if n < 5:
        return {'N': n, 'M': m, 'too_small': True}
    out = {'N': n, 'M': m, 'too_small': False}
    try:
        d1 = community_descriptor_summary(g, n_steps=15)
        out['D1_csi'] = d1['csi']
        out['D1_n_comm'] = d1['n_communities_at_gamma_1']
    except Exception as e:
        out['D1_err'] = str(e)[:80]
    try:
        d2 = concentration_profile(g)
        out['D2_max_gini'] = d2['max_gini']
    except Exception as e:
        out['D2_err'] = str(e)[:80]
    try:
        d3 = spectral_descriptors(g)
        out['D3_alg_conn'] = d3['algebraic_connectivity']
        out['D3_norm_gap'] = d3['normalized_spectral_gap']
        out['D3_fiedler_bim'] = d3['fiedler_bimodality']
    except Exception as e:
        out['D3_err'] = str(e)[:80]
    try:
        cr = cycle_rank_descriptors(g)
        out['D4_cycle_rank_norm'] = cr['cycle_rank_norm']
    except Exception as e:
        out['D4_err'] = str(e)[:80]
    return out


def run_project(repo, models_subpath, project_name, window_days=30, out_dir=None):
    print(f"\n=== {project_name} ===")
    print("Listing commits affecting models...", flush=True)
    commits = list_commits_in_path(repo, models_subpath)
    print(f"  Total commits touching models: {len(commits)}")
    if not commits:
        print("  No commits found in models path; skipping.")
        return
    print(f"  Span: {commits[0][0].date()} → {commits[-1][0].date()}")

    sampled = sample_one_per_window(commits, window_days=window_days)
    print(f"  Sampling 1 per {window_days}-day window: {len(sampled)} snapshots")

    # Stash current state and remember branch
    branch = git_run(repo, 'symbolic-ref', '--short', 'HEAD') or 'main'
    git_run(repo, 'stash', '-u')

    rows = []
    for i, (dt, sha) in enumerate(sampled):
        print(f"  [{i+1}/{len(sampled)}] {dt.date()} {sha[:8]}", end=' ', flush=True)
        try:
            g = extract_lineage_at_commit(repo, sha, models_subpath)
            if g is None:
                print('(no models dir)')
                continue
            desc = compute_descriptors_safe(g)
            commit_msg = git_run(repo, 'log', '-1', '--pretty=%s', sha)
            row = {'date': dt.isoformat(), 'sha': sha, 'commit_msg': commit_msg[:120],
                   **desc}
            rows.append(row)
            print(f"N={desc.get('N',0)} M={desc.get('M',0)} "
                  f"CSI={desc.get('D1_csi','--')} D3={desc.get('D3_alg_conn','--'):.4f}"
                  if isinstance(desc.get('D3_alg_conn'), float) else
                  f"N={desc.get('N',0)} M={desc.get('M',0)}")
        except Exception as e:
            print(f"ERR {e}")

    # Restore branch
    git_run(repo, 'checkout', '-q', branch)
    try:
        git_run(repo, 'stash', 'pop')
    except Exception:
        pass

    df = pd.DataFrame(rows)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        df.to_csv(os.path.join(out_dir, f'longitudinal_{project_name}.csv'), index=False)
        print(f"  Saved {len(df)} snapshots")
    return df


def detect_drift_events(df, descriptor_col, threshold_sigma=2.5):
    """Control-chart drift detection: flag points > threshold_sigma from rolling mean."""
    if descriptor_col not in df.columns:
        return pd.DataFrame()
    s = pd.to_numeric(df[descriptor_col], errors='coerce').dropna()
    if len(s) < 5:
        return pd.DataFrame()
    rolling_mean = s.rolling(window=5, min_periods=2).mean()
    rolling_std = s.rolling(window=5, min_periods=2).std().fillna(0)
    z = (s - rolling_mean) / (rolling_std + 1e-9)
    drifts = df.loc[s.index][abs(z) > threshold_sigma].copy()
    drifts['descriptor'] = descriptor_col
    drifts['z'] = z[abs(z) > threshold_sigma].values
    return drifts


PROJECTS = [
    ('https://github.com/cal-itp/data-infra.git', 'warehouse/models', 'cal-itp'),
    ('https://github.com/mattermost/mattermost-data-warehouse.git',
     'transform/snowflake-dbt/models', 'mattermost'),
]


def clone_or_fail(url, dest):
    """Clone if absent. Raise rather than skip.

    This script used to `continue` past a missing clone, reach the bottom with
    an empty summary, and overwrite artifacts/phase_4/summary.json with
    {"drift_events_detected": 0} while exiting 0. Following the documented
    command in a fresh checkout destroyed a published artifact and reported
    success. A missing repository is now a hard failure.
    """
    if os.path.isdir(os.path.join(dest, '.git')):
        return dest
    print(f"Cloning {url} -> {dest}", flush=True)
    proc = subprocess.run(
        ['git', 'clone', '--quiet', '--single-branch', '--no-tags', url, dest],
        capture_output=True, text=True,
        env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))
    if proc.returncode != 0 or not os.path.isdir(os.path.join(dest, '.git')):
        raise SystemExit(
            f"clone failed for {url}: {proc.stderr.strip()[:300]}\n"
            "Refusing to continue. Running with no repositories would write an "
            "empty summary over the published artifact.")
    return dest


if __name__ == '__main__':
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--clones', default=os.environ.get('DBT_CLONE_DIR', '/tmp'),
                    help='directory to clone the two projects into')
    ap.add_argument('--out-dir', default=os.path.join(
        os.path.dirname(__file__), '..', '..', 'artifacts', 'phase_4'),
        help='where to write the artifacts. Point this somewhere else to '
             'avoid overwriting the published phase_4 outputs.')
    args = ap.parse_args()

    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)

    summary = {}
    all_drift = []

    for url, sub, name in PROJECTS:
        repo = clone_or_fail(url, os.path.join(args.clones, name))
        df = run_project(repo, sub, name, window_days=30, out_dir=out_dir)
        if df is None or len(df) < 4:
            continue
        summary[name] = {'n_snapshots': len(df),
                         'span_days': (pd.to_datetime(df['date']).max() -
                                       pd.to_datetime(df['date']).min()).days}
        for desc in ['D1_csi', 'D3_alg_conn', 'D3_norm_gap', 'D4_cycle_rank_norm']:
            drifts = detect_drift_events(df, desc)
            if len(drifts) > 0:
                drifts['project'] = name
                all_drift.append(drifts)

    projects_measured = [k for k in summary if k != 'drift_events_detected']
    if not projects_measured:
        raise SystemExit(
            "No project produced a usable series. Refusing to write "
            f"{out_dir}/summary.json, because an empty summary here overwrites "
            "the published artifact with a result that describes nothing.")

    if all_drift:
        all_drift_df = pd.concat(all_drift, ignore_index=True)
        all_drift_df.to_csv(os.path.join(out_dir, 'drift_events.csv'), index=False)
        summary['drift_events_detected'] = len(all_drift_df)
    else:
        summary['drift_events_detected'] = 0

    with open(os.path.join(out_dir, 'summary.json'), 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nSaved to {out_dir}/")
    print(json.dumps(summary, indent=2, default=str))
