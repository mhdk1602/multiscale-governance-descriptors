"""Assemble the extracted per-project results into a releasable corpus.

Layout produced under --dest:

  MANIFEST.json          dataset-level provenance, one entry per project
  schema.json            machine-readable column dictionary and types
  README.md              how to consume the corpus without reading any code
  corpus_index.csv       one row per included project, the yield table
  snapshots.csv          every snapshot of every included project, long format
  drift_events.csv       step-change drift events over the whole corpus
  excluded.csv           every screened repository that did not make the corpus
  projects/<id>/snapshots.csv
  projects/<id>/extraction.json
"""
import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))

SNAPSHOT_COLUMNS = [
    'project_id', 'date', 'sha', 'commit_msg', 'N', 'M', 'too_small',
    'D1_csi', 'D1_n_comm', 'D2_max_gini', 'D3_alg_conn', 'D3_norm_gap',
    'D3_fiedler_bim', 'D4_cycle_rank_norm',
    'n_components', 'giant_component_frac', 'isolated_frac',
    'n_staging', 'n_intermediate', 'n_mart', 'n_unclassified',
    'n_sql_files', 'n_dbt_projects',
]

DRIFT_COLUMNS = ['project_id', 'date', 'sha', 'descriptor', 'prev', 'curr',
                 'pct_change', 'commit_msg']

INDEX_COLUMNS = [
    'project_id', 'repo_url', 'status', 'snapshots', 'date_start', 'date_end',
    'span_days', 'span_years', 'nodes_first', 'nodes_last', 'nodes_min',
    'nodes_max', 'edges_first', 'edges_last', 'edges_min', 'edges_max',
    'node_growth_multiple', 'edge_growth_multiple',
    'nodes_first_viable', 'date_first_viable', 'node_growth_from_first_viable',
    'tier', 'net_contraction_from_peak_pct', 'median_giant_component_frac',
    'median_edges_per_node', 'median_snapshot_gap_days',
    'max_snapshot_gap_days', 'drift_events', 'n_dbt_projects_at_head',
    'model_paths', 'head_sha', 'stars', 'license', 'strata', 'error',
]

DRIFT_DESCRIPTORS = ['D1_csi', 'D3_alg_conn', 'D4_cycle_rank_norm']
DRIFT_THRESHOLD_PCT = 20.0


FIELD_DOC = {
    'project_id': ('string', 'Stable corpus identifier, GitHub owner and repository '
                             'joined by a double underscore.'),
    'date': ('ISO-8601 datetime', 'Author timestamp of the sampled commit.'),
    'sha': ('string (40 hex)', 'Full git commit SHA the snapshot was extracted at.'),
    'commit_msg': ('string', 'Commit subject line, truncated to 120 characters.'),
    'N': ('integer', 'Nodes in the lineage DAG, one per resolved dbt model.'),
    'M': ('integer', 'Directed edges, one per ref() call between two resolved models.'),
    'too_small': ('boolean', 'True when N < 5 and the D1-D4 descriptors were skipped.'),
    'D1_csi': ('float [0,1]', 'Community stability index. Fraction of consecutive steps '
                              'in a 15-point Louvain resolution sweep whose partitions '
                              'differ by NVI < 0.1.'),
    'D1_n_comm': ('integer', 'Communities found at Louvain resolution gamma = 1.'),
    'D2_max_gini': ('float [0,1]', 'Maximum over depth of the Gini coefficient of the '
                                   'blast-radius distribution.'),
    'D3_alg_conn': ('float >= 0', 'Algebraic connectivity, the second-smallest Laplacian '
                                  'eigenvalue of the undirected connected skeleton.'),
    'D3_norm_gap': ('float [0,1]', 'Algebraic connectivity divided by the largest '
                                   'Laplacian eigenvalue.'),
    'D3_fiedler_bim': ('float [0,1]', 'Bimodality coefficient of the Fiedler vector.'),
    'D4_cycle_rank_norm': ('float >= 0', 'Cycle rank (M - N + C) of the undirected '
                                         'skeleton, divided by N.'),
    'n_staging': ('integer', 'Models classified as staging by name prefix or directory.'),
    'n_intermediate': ('integer', 'Models classified as intermediate.'),
    'n_mart': ('integer', 'Models classified as mart, fact, dimension or reporting.'),
    'n_unclassified': ('integer', 'Models matching no layer rule.'),
    'n_sql_files': ('integer', 'Model SQL files read at this commit, before stem '
                               'collision collapsing. Equals N unless two files in '
                               'different directories share a filename.'),
    'n_dbt_projects': ('integer', 'dbt_project.yml files visible at this commit, '
                                  'vendored packages excluded.'),
    'n_components': ('integer', 'Connected components of the undirected skeleton.'),
    'giant_component_frac': ('float (0,1]', 'Largest connected component divided by N. '
                                            'D1 and D3 are computed on the giant '
                                            'component alone, so this says how much of '
                                            'the reported N they describe.'),
    'isolated_frac': ('float [0,1]', 'Models with no ref() in either direction, '
                                     'divided by N.'),
    'descriptor': ('string', 'Which descriptor drifted.'),
    'prev': ('float', 'Descriptor value at the preceding snapshot.'),
    'curr': ('float', 'Descriptor value at this snapshot.'),
    'pct_change': ('float > 20', '100 * |curr - prev| / |prev|. Emitted only above 20.'),
}


def build_schema(dest):
    return {
        'schema_version': '1.0.0',
        'files': {
            'snapshots.csv': {
                'description': ('Every snapshot of every included project, one row per '
                                'project per sampled commit. Identical columns to the '
                                'per-project projects/<id>/snapshots.csv files.'),
                'primary_key': ['project_id', 'sha'],
                'fields': [{'name': c, 'type': FIELD_DOC.get(c, ('', ''))[0],
                            'description': FIELD_DOC.get(c, ('', ''))[1]}
                           for c in SNAPSHOT_COLUMNS],
            },
            'drift_events.csv': {
                'description': ('Consecutive-snapshot relative changes above 20 percent '
                                'in D1_csi, D3_alg_conn or D4_cycle_rank_norm.'),
                'primary_key': ['project_id', 'sha', 'descriptor'],
                'fields': [{'name': c, 'type': FIELD_DOC.get(c, ('', ''))[0],
                            'description': FIELD_DOC.get(c, ('', ''))[1]}
                           for c in DRIFT_COLUMNS],
            },
            'corpus_index.csv': {
                'description': 'One row per included project, the yield table.',
                'primary_key': ['project_id'],
                'fields': [{'name': c} for c in INDEX_COLUMNS],
            },
            'excluded.csv': {
                'description': ('Every repository that was cloned and extracted but did '
                                'not meet the inclusion criteria, with the reason.'),
                'primary_key': ['project_id'],
            },
            'longitudinal/longitudinal_<id>.csv': {
                'description': ('The per-project snapshot rows again, under the flat '
                                'name the phase_4 scripts glob for. Byte-identical '
                                'content to projects/<id>/snapshots.csv.'),
                'primary_key': ['sha'],
            },
            'sampling_frame.csv': {
                'description': ('The full candidate population and the screening outcome '
                                'for each entry, including repositories never cloned.'),
                'primary_key': ['full_name'],
            },
            'MANIFEST.json': {
                'description': ('Dataset provenance. Repository URL, default branch, HEAD '
                                'SHA, resolved model paths, first and last snapshot SHA '
                                'and date, extraction timestamps, and a SHA-256 for every '
                                'other file in the release.'),
            },
        },
        'conventions': {
            'missing': 'Empty string in CSV, null in JSON.',
            'timestamps': 'Snapshot dates are git author timestamps, local to the commit. '
                          'Extraction timestamps are UTC with a Z suffix.',
            'encoding': 'UTF-8, RFC 4180 quoting, LF line endings.',
        },
    }


README = """# Longitudinal dbt lineage corpus

Monthly reconstructions of the model dependency graph of {n_projects} public dbt
projects, {n_snapshots} snapshots in all, spanning {date_start} to {date_end}.
Each snapshot is a lineage DAG recovered from a single git commit together with
the D1-D4 governance descriptors computed on it.

Nothing here requires dbt to be installed or run. The graph at a commit is
recovered by reading the model SQL out of the git object database and parsing
`{{{{ ref('...') }}}}` declarations, so a project's history can be reconstructed
without credentials, a warehouse, or a working build.

## Files

| file | what it holds |
|---|---|
| `snapshots.csv` | every snapshot of every project, one row per project per commit |
| `corpus_index.csv` | one row per project, the yield table |
| `drift_events.csv` | consecutive-snapshot changes above 20 percent in D1_csi, D3_alg_conn or D4_cycle_rank_norm |
| `excluded.csv` | repositories that were cloned and extracted but did not meet the inclusion criteria, with the reason |
| `sampling_frame.csv` | the full candidate population of {n_population} repositories and what happened to each |
| `schema.json` | column dictionary, types and primary keys for every table |
| `MANIFEST.json` | provenance, commit SHAs, and a SHA-256 for every other file |
| `projects/<id>/snapshots.csv` | the same rows as `snapshots.csv`, split per project |
| `longitudinal/longitudinal_<id>.csv` | the per-project rows again under the flat name the phase_4 scripts glob for |
| `projects/<id>/extraction.json` | per-project provenance including every snapshot SHA and every snapshot that failed |

Start with `corpus_index.csv` for the shape of the corpus and `snapshots.csv`
for the measurements. `schema.json` documents every column.

## How a snapshot is chosen

Commits touching a declared model path are listed oldest first. The history is
cut into rolling 30-day windows anchored on the first such commit, and the last
commit in each window is sampled. One snapshot per project per month of activity,
so a quiet month yields nothing and a busy month yields one.

## How the lineage graph is built

At the sampled commit, every `.sql` file under the tracked dbt project's
`model-paths` is read. Files under `macros`, `tests`, `snapshots`, and vendored
package directories are skipped. A node is the filename stem. An edge runs from
`ref('a')` to the model whose file contains it, and only when `a` resolves to
another model in the same snapshot, so references to sources, seeds, and models
from other packages do not appear.

Two consequences worth knowing before you use the data. Models in different dbt
projects inside one repository cannot reference each other, so only one dbt
project per repository is tracked, named in `MANIFEST.json` under
`model_paths`. And two model files in different directories that share a
filename collapse to one node, which is what dbt itself does, since dbt model
names are globally unique within a project.

## Inclusion criteria

A repository is in the corpus when all of the following hold.

- At least {min_snapshots} monthly snapshots were extracted.
- Peak lineage size of at least {min_nodes} nodes.
- At least one `dbt_project.yml` with resolvable `model-paths` somewhere in its
  history.

### Tiers

`corpus_index.csv` carries a `tier` column. A dbt *package* repository can clear
the criteria above with fifty model files and three edges between them, and on a
graph that sparse the D1 and D3 routines describe the giant component, which may
be a handful of nodes while `N` says fifty. `core` marks the {n_core} projects
where the descriptors describe most of the reported N and the series is long
enough to carry a trend, meaning at least {core_min_snapshots} snapshots, peak
size at least {core_min_nodes} nodes, and a median giant component of at least
{core_min_giant_frac} of N. Everything else is `extended`.

Both tiers are real measurements and neither is filtered out. Which one an
analysis should use depends on whether it reasons about dependency structure,
where `core` is the safer population, or about lifecycle and size, where the
full corpus is.

The candidate population and the screen that preceded these criteria are in
`sampling_frame.csv`. The screen only removed repositories that could not
produce a monthly series in principle: fewer than 40 commits on the default
branch, under 12 months between creation and last push, forks, and empty
repositories. Everything else was cloned and extracted, and membership was
decided from the extraction rather than from the screen.

## Reconstructing any snapshot

`MANIFEST.json` pins `head_sha`, the commit each repository was cloned at, and
`projects/<id>/extraction.json` lists the SHA of every sampled commit. Neither
depends on the repository still looking the way it did, so a row stays
reconstructible after the project moves on.

    git clone <repository>
    git -C <repo> checkout <head_sha>          # the state the corpus saw
    git -C <repo> ls-tree -r <snapshot_sha> -- <model_paths>

Rerunning the pipeline against a live repository will not reproduce the corpus,
because repositories gain commits, get renamed, go private and get deleted.
Cal-ITP had 1,019 model-touching commits when the two-project study ran and
1,049 when this corpus was built. Reproduce from the pinned SHAs, not from HEAD.

## Reproducibility

`D1_csi` and `D1_n_comm` come from a Louvain resolution sweep. Louvain is
sensitive to the order in which nodes enter the graph, so nodes are inserted in
sorted order and the runs are made with `PYTHONHASHSEED=0` and Louvain
`seed=42`. Earlier work on this pipeline inserted nodes from a Python set, whose
string iteration order varies with the process hash seed, and D1 values from
that code are not reproducible between runs. N, M, D2 and D4 are unaffected by
node ordering and reproduce exactly.

`MANIFEST.json` records the tool version, the extraction timestamps, the
repository URL, the default branch, the HEAD SHA at extraction time, and the SHA
of every sampled commit, so any row can be traced back to the exact tree it was
computed from.

## Known limitations

- `ref()` calls constructed dynamically, for example inside a macro or from a
  loop variable, are not resolved. The regex matches literal string arguments
  only.
- A repository that fans a single dbt project out into several subprojects
  leaves the tracked project empty from that point on. Those snapshots are
  recorded as gaps in `projects/<id>/extraction.json` and the project's status
  becomes `partial`.
- Public mirrors of internal dbt projects sometimes publish `dbt_project.yml`
  without the model SQL. Those repositories extract to zero snapshots and appear
  in `excluded.csv`.
- Layer labels in `n_staging`, `n_intermediate` and `n_mart` come from naming
  conventions, not from dbt metadata. Projects that do not follow a convention
  land in `n_unclassified`.
"""


def refresh_manifest(dest):
    """Recompute the checksum table in place.

    Composition labelling and the D1 order-sensitivity measurement both need a
    built release to run against, so they necessarily write after the manifest
    exists. Without this the manifest would describe a release that no longer
    matches it, which is worse than having no manifest.
    """
    mpath = os.path.join(dest, 'MANIFEST.json')
    manifest = json.load(open(mpath))
    checksums = {}
    for root, _dirs, files in os.walk(dest):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, dest)
            if rel == 'MANIFEST.json':
                continue
            checksums[rel] = sha256_file(p)
    manifest['sha256'] = checksums
    manifest['manifest_refreshed_utc'] = datetime.now(timezone.utc).isoformat(
        timespec='seconds')
    with open(mpath, 'w') as f:
        json.dump(manifest, f, indent=1)
    print(f'refreshed {len(checksums)} checksums in {mpath}')
    return 0


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()


def step_change_drift(rows, threshold=DRIFT_THRESHOLD_PCT):
    """Consecutive-snapshot relative change above threshold, per descriptor."""
    events = []
    for desc in DRIFT_DESCRIPTORS:
        series = [(i, r) for i, r in enumerate(rows)
                  if isinstance(r.get(desc), (int, float)) and r.get(desc) is not None]
        for k in range(1, len(series)):
            _, prev_r = series[k - 1]
            _, curr_r = series[k]
            prev, curr = prev_r[desc], curr_r[desc]
            if prev is None or curr is None or prev == 0:
                continue
            pct = 100.0 * abs(curr - prev) / abs(prev)
            if pct > threshold:
                events.append({'date': curr_r['date'], 'sha': curr_r['sha'],
                               'descriptor': desc, 'prev': prev, 'curr': curr,
                               'pct_change': round(pct, 4),
                               'commit_msg': curr_r.get('commit_msg', '')})
    events.sort(key=lambda e: (e['date'], e['descriptor']))
    return events


VIABLE_N = 10


def summarise(pid, res, rows, extra):
    dates = [r['date'][:10] for r in rows]
    ns = [r['N'] for r in rows if isinstance(r.get('N'), (int, float))]
    ms = [r['M'] for r in rows if isinstance(r.get('M'), (int, float))]
    d0 = datetime.fromisoformat(rows[0]['date'])
    d1 = datetime.fromisoformat(rows[-1]['date'])
    span = (d1 - d0).days
    gaps = []
    for a, b in zip(rows, rows[1:]):
        gaps.append((datetime.fromisoformat(b['date'])
                     - datetime.fromisoformat(a['date'])).days)
    gaps.sort()
    med = gaps[len(gaps) // 2] if gaps else None
    gcf = sorted(r['giant_component_frac'] for r in rows
                 if isinstance(r.get('giant_component_frac'), (int, float)))
    epn = sorted((r['M'] / r['N']) for r in rows
                 if isinstance(r.get('N'), (int, float)) and r['N'])
    # A project that starts from an empty repository shows a growth multiple
    # driven by its first commit rather than by anything about its lineage.
    # CDPVD's first snapshot has two models, which makes its growth 51.5x. The
    # viable baseline is the first snapshot at or above the inclusion floor.
    viable = next(((i, r) for i, r in enumerate(rows)
                   if isinstance(r.get('N'), (int, float)) and r['N'] >= VIABLE_N),
                  None)
    peak = max(ns) if ns else None
    last = ns[-1] if ns else None
    contraction = (round(100.0 * (peak - last) / peak, 2)
                   if peak and last is not None and peak > 0 else None)
    return {
        'project_id': pid,
        'repo_url': res.get('repo_url'),
        'status': res.get('status'),
        'snapshots': len(rows),
        'date_start': dates[0],
        'date_end': dates[-1],
        'span_days': span,
        'span_years': round(span / 365.25, 2),
        'nodes_first': ns[0] if ns else None,
        'nodes_last': ns[-1] if ns else None,
        'nodes_min': min(ns) if ns else None,
        'nodes_max': max(ns) if ns else None,
        'edges_first': ms[0] if ms else None,
        'edges_last': ms[-1] if ms else None,
        'edges_min': min(ms) if ms else None,
        'edges_max': max(ms) if ms else None,
        'node_growth_multiple': (round(ns[-1] / ns[0], 2)
                                 if ns and ns[0] else None),
        'edge_growth_multiple': (round(ms[-1] / ms[0], 2)
                                 if ms and ms[0] else None),
        'nodes_first_viable': viable[1]['N'] if viable else None,
        'date_first_viable': viable[1]['date'][:10] if viable else None,
        'node_growth_from_first_viable': (
            round(ns[-1] / viable[1]['N'], 2)
            if viable and ns and viable[1]['N'] else None),
        'net_contraction_from_peak_pct': contraction,
        'median_giant_component_frac': (round(gcf[len(gcf) // 2], 4) if gcf else None),
        'median_edges_per_node': (round(epn[len(epn) // 2], 4) if epn else None),
        'median_snapshot_gap_days': med,
        'max_snapshot_gap_days': gaps[-1] if gaps else None,
        'n_dbt_projects_at_head': len(res.get('dbt_projects_at_head') or []),
        'model_paths': ';'.join(res.get('model_path_universe') or []),
        'head_sha': res.get('head_sha'),
        'stars': extra.get('stars'),
        'license': extra.get('license'),
        'strata': ';'.join(extra.get('strata') or []),
        'error': res.get('error'),
    }


def write_csv(path, columns, rows):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', nargs='+', default=[])
    ap.add_argument('--dest', required=True)
    ap.add_argument('--decisions', default='',
                    help='frame/decisions.json from finalize_frame.py')
    ap.add_argument('--min-snapshots', type=int, default=12)
    ap.add_argument('--min-nodes', type=int, default=10)
    ap.add_argument('--core-min-nodes', type=int, default=25)
    ap.add_argument('--core-min-snapshots', type=int, default=24)
    ap.add_argument('--core-min-giant-frac', type=float, default=0.5)
    ap.add_argument('--refresh-manifest-only', action='store_true',
                    help='recompute the SHA-256 table over an existing release, '
                         'for steps that add or edit files after the build')
    ap.add_argument('--attach', nargs='*', default=[],
                    help='extra files to copy into the release and checksum, '
                         'for outputs produced from an earlier build')
    a = ap.parse_args()

    dest = a.dest
    if a.refresh_manifest_only:
        return refresh_manifest(dest)
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(os.path.join(dest, 'projects'), exist_ok=True)

    extra = {}
    if os.path.exists(a.decisions):
        for d in json.load(open(a.decisions)):
            extra[d['project_id']] = d

    results = {}
    for d in a.results:
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.json'):
                continue
            r = json.load(open(os.path.join(d, fn)))
            results[r['project_id']] = r

    index, all_snaps, all_drift, excluded = [], [], [], []
    manifest_projects = []

    for pid in sorted(results):
        res = results[pid]
        rows = res.get('snapshots') or []
        ex = extra.get(pid, {})
        reason = None
        if res.get('status') == 'failed' or not rows:
            reason = res.get('error') or 'extraction produced no snapshots'
        elif len(rows) < a.min_snapshots:
            reason = (f'only {len(rows)} monthly snapshots, '
                      f'below the {a.min_snapshots} minimum')
        elif max((r.get('N') or 0) for r in rows) < a.min_nodes:
            reason = (f'peak lineage size {max((r.get("N") or 0) for r in rows)} '
                      f'nodes, below the {a.min_nodes} minimum')
        if reason:
            excluded.append({'project_id': pid, 'repo_url': res.get('repo_url'),
                             'snapshots_obtained': len(rows),
                             'peak_nodes': max((r.get('N') or 0) for r in rows)
                             if rows else 0,
                             'extraction_status': res.get('status'),
                             'exclusion_reason': reason,
                             'strata': ';'.join(ex.get('strata') or [])})
            continue

        pdir = os.path.join(dest, 'projects', pid)
        os.makedirs(pdir, exist_ok=True)
        for r in rows:
            r['project_id'] = pid
        write_csv(os.path.join(pdir, 'snapshots.csv'), SNAPSHOT_COLUMNS, rows)
        # Same rows under the flat `longitudinal_<id>.csv` name the phase_4
        # figure and analysis scripts already glob for, so they can be pointed
        # at this corpus without being changed.
        os.makedirs(os.path.join(dest, 'longitudinal'), exist_ok=True)
        write_csv(os.path.join(dest, 'longitudinal', f'longitudinal_{pid}.csv'),
                  SNAPSHOT_COLUMNS, rows)
        prov = {k: v for k, v in res.items() if k != 'snapshots'}
        prov['snapshot_shas'] = [r['sha'] for r in rows]
        prov['stars'] = ex.get('stars')
        prov['license'] = ex.get('license')
        prov['strata'] = ex.get('strata')
        with open(os.path.join(pdir, 'extraction.json'), 'w') as f:
            json.dump(prov, f, indent=1)

        drifts = step_change_drift(rows)
        for e in drifts:
            e['project_id'] = pid
        all_drift.extend(drifts)
        all_snaps.extend(rows)
        summary = summarise(pid, res, rows, ex)
        summary['drift_events'] = len(drifts)
        # Two tiers, because breadth and interpretability pull apart. A dbt
        # package repository can clear the floor with fifty model files and
        # three edges between them, and on a graph like that D1 and D3 describe
        # the giant component, which is a handful of nodes. `core` marks the
        # projects where the descriptors describe most of the reported N.
        summary['tier'] = (
            'core' if (summary['snapshots'] >= a.core_min_snapshots
                       and (summary['nodes_max'] or 0) >= a.core_min_nodes
                       and (summary['median_giant_component_frac'] or 0)
                       >= a.core_min_giant_frac)
            else 'extended')
        index.append(summary)
        manifest_projects.append({
            'project_id': pid,
            'repository': res.get('repo_url'),
            'default_branch': res.get('default_branch'),
            'head_sha': res.get('head_sha'),
            'model_paths': res.get('model_path_universe'),
            'snapshots': len(rows),
            'first_snapshot': {'date': rows[0]['date'], 'sha': rows[0]['sha']},
            'last_snapshot': {'date': rows[-1]['date'], 'sha': rows[-1]['sha']},
            'extraction_started_utc': res.get('extraction_started_utc'),
            'extraction_finished_utc': res.get('extraction_finished_utc'),
            'extraction_status': res.get('status'),
            'snapshot_errors': len(res.get('snapshot_errors') or []),
            'files': {
                'snapshots': f'projects/{pid}/snapshots.csv',
                'extraction': f'projects/{pid}/extraction.json',
                'legacy_name': f'longitudinal/longitudinal_{pid}.csv',
            },
        })

    index.sort(key=lambda r: -r['snapshots'])
    write_csv(os.path.join(dest, 'corpus_index.csv'), INDEX_COLUMNS, index)
    write_csv(os.path.join(dest, 'snapshots.csv'), SNAPSHOT_COLUMNS, all_snaps)
    write_csv(os.path.join(dest, 'drift_events.csv'), DRIFT_COLUMNS, all_drift)
    write_csv(os.path.join(dest, 'excluded.csv'),
              ['project_id', 'repo_url', 'snapshots_obtained', 'peak_nodes',
               'extraction_status', 'exclusion_reason', 'strata'], excluded)

    # The full candidate population and what happened to each entry, including
    # the repositories that were never cloned. A reader can reconstruct the
    # frame without rerunning any GitHub search.
    frame_rows = []
    if os.path.exists(a.decisions):
        included = {r['project_id'] for r in index}
        extracted = set(results)
        for d in json.load(open(a.decisions)):
            pid = d['project_id']
            if d['screen'] != 'passed':
                outcome, why = 'not screened in', d['reason']
            elif pid not in extracted:
                outcome, why = 'screened in, not extracted', ''
            elif pid in included:
                outcome, why = 'in corpus', ''
            else:
                outcome = 'extracted, excluded'
                why = next((e['exclusion_reason'] for e in excluded
                            if e['project_id'] == pid), '')
            frame_rows.append({
                'full_name': d['full_name'], 'project_id': pid, 'url': d['url'],
                'strata': ';'.join(d.get('strata') or []),
                'stars': d.get('stars'), 'license': d.get('license'),
                'total_commits': d.get('total_commits'),
                'n_model_sql_at_head': d.get('n_model_sql'),
                'n_dbt_projects': d.get('n_dbt_projects'),
                'created_at': d.get('created_at'), 'pushed_at': d.get('pushed_at'),
                'screen': d['screen'], 'outcome': outcome, 'reason': why,
            })
    write_csv(os.path.join(dest, 'sampling_frame.csv'),
              ['full_name', 'project_id', 'url', 'strata', 'stars', 'license',
               'total_commits', 'n_model_sql_at_head', 'n_dbt_projects',
               'created_at', 'pushed_at', 'screen', 'outcome', 'reason'],
              frame_rows)

    with open(os.path.join(dest, 'schema.json'), 'w') as f:
        json.dump(build_schema(dest), f, indent=1)

    with open(os.path.join(dest, 'README.md'), 'w') as f:
        f.write(README.format(
            n_projects=len(index), n_snapshots=len(all_snaps),
            n_population=len(frame_rows),
            date_start=min((r['date_start'] for r in index), default='-'),
            date_end=max((r['date_end'] for r in index), default='-'),
            min_snapshots=a.min_snapshots, min_nodes=a.min_nodes,
            n_core=sum(1 for r in index if r['tier'] == 'core'),
            core_min_snapshots=a.core_min_snapshots,
            core_min_nodes=a.core_min_nodes,
            core_min_giant_frac=a.core_min_giant_frac))

    # Files produced from an earlier build of this release, notably the D1
    # order-sensitivity measurement, which needs the release to exist before it
    # can run. Copied in here so they land in the checksum table like everything
    # else rather than sitting beside it unverified.
    for extra in a.attach:
        if os.path.isfile(extra):
            shutil.copy2(extra, os.path.join(dest, os.path.basename(extra)))

    checksums = {}
    for root, _dirs, files in os.walk(dest):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, dest)
            if rel == 'MANIFEST.json':
                continue
            checksums[rel] = sha256_file(p)

    manifest = {
        'dataset': 'Longitudinal dbt lineage corpus',
        'tool': 'governance_descriptors.dbt_lineage',
        'tool_version': '1.0.0',
        'generated_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'snapshot_interval_days': 30,
        'snapshot_rule': ('last commit touching a declared model path within each '
                          'rolling 30-day window, anchored on the first such commit'),
        'inclusion_criteria': {
            'min_monthly_snapshots': a.min_snapshots,
            'min_peak_nodes': a.min_nodes,
            'requires': 'at least one dbt_project.yml with resolvable model-paths',
        },
        'tiers': {
            'core': {'min_snapshots': a.core_min_snapshots,
                     'min_peak_nodes': a.core_min_nodes,
                     'min_median_giant_component_frac': a.core_min_giant_frac,
                     'rationale': ('the descriptors describe most of the reported N, '
                                   'and the series is long enough for a trend')},
            'extended': {'rationale': 'meets the inclusion criteria but not the '
                                      'core thresholds'},
        },
        'n_core': sum(1 for r in index if r['tier'] == 'core'),
        'determinism': {
            'node_insertion_order': 'sorted',
            'pythonhashseed': 0,
            'louvain_seed': 42,
            'note': ('The original phase_4 script inserted nodes from a Python set, '
                     'making D1_csi and D1_n_comm dependent on PYTHONHASHSEED. '
                     'Sorted insertion removes that dependence.'),
        },
        'n_projects': len(index),
        'n_snapshots': len(all_snaps),
        'n_excluded': len(excluded),
        'n_candidate_population': len(frame_rows),
        'n_screened_in': sum(1 for r in frame_rows if r['screen'] == 'passed'),
        'projects': manifest_projects,
        'sha256': checksums,
    }
    with open(os.path.join(dest, 'MANIFEST.json'), 'w') as f:
        json.dump(manifest, f, indent=1)

    print(f'projects included : {len(index)}')
    print(f'snapshots         : {len(all_snaps)}')
    print(f'drift events      : {len(all_drift)}')
    print(f'excluded          : {len(excluded)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
