"""Corpus-scale longitudinal dbt lineage extraction.

Reconstructs the model dependency graph of a dbt project at monthly intervals
across its git history, without installing or running dbt. The graph at a commit
comes from reading the model SQL out of the object database and parsing literal
`{{ ref('...') }}` declarations.

This is the corpus-scale successor to `experiments/phase_4/exp_longitudinal_dbt.py`,
which handled two repositories with hand-supplied model paths. Five changes were
needed to run it over hundreds. Each is here because it changed a measurement,
not for tidiness.

1. Snapshots are read with `git ls-tree` and `git cat-file --batch` rather than
   `git checkout`. Nothing is written to the worktree, so a repository can be
   read concurrently and a crashed run leaves no detached HEAD behind. Cal-ITP's
   53 snapshots take seconds instead of minutes.
2. Model paths are resolved from each commit's own `dbt_project.yml` instead of
   being supplied by hand, so a project that relocates its models stays
   measurable and no repository needs manual configuration.
3. Nodes enter the graph in sorted order. The original inserted them from a
   Python set, whose string iteration order varies with `PYTHONHASHSEED`, and
   Louvain is order sensitive, so `D1_csi` and `D1_n_comm` were not reproducible
   between runs. On one Cal-ITP commit the same graph gave CSI of 0.50, 0.64 and
   0.79 under three hash seeds. N, M, D2 and D4 never depended on the ordering.
4. Vendored dbt packages are excluded. `dbt_modules/dbt_utils/models` belongs to
   dbt_utils, not to the project under study, and counting it inflates N and
   fuses unrelated lineage.
5. One dbt project is tracked per repository. Models in separate dbt projects
   cannot reference each other, so their union is disconnected, and both the
   community and spectral routines silently reduce a disconnected graph to its
   giant component. The union would have been counted in N and M and dropped
   from D1 and D3.

The `ref()` regex, the file exclusion rules, the model-name resolution rule and
the descriptor calls are unchanged from the original. Mattermost reproduces the
recorded 55-snapshot artifact exactly under automatic path resolution, and
Cal-ITP reproduces every commit it shares with the recorded 51.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import subprocess
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import PurePosixPath

import networkx as nx
import yaml

from governance_descriptors.community_stability import community_descriptor_summary
from governance_descriptors.spectral import spectral_descriptors
from governance_descriptors.blast_radius import concentration_profile
from governance_descriptors.persistent_homology import cycle_rank_descriptors

TOOL_VERSION = '2.0.0'

# The strict pattern from exp_longitudinal_dbt.py. It requires `{{` immediately
# before `ref(`, so it only sees a ref that is the entire Jinja expression.
REF_STRICT = re.compile(r"\{\{\s*ref\(\s*['\"](\w+)['\"]\s*\)\s*\}\}",
                        re.IGNORECASE)

# The permissive pattern drops the anchor and accepts the two-argument form.
# A ref passed as an argument to a macro is invisible to the strict pattern, and
# that is not an edge case: on Cal-ITP it hides 113 of 869 model-to-model edges,
# 13.0 percent, touching 29.2 percent of nodes. Every missed site is a plain
# literal, none is dynamically constructed, and 93 percent span multiple lines.
# The wrapping callables are `dbt_utils.union_relations`, `unpivot` and
# project-local macros. The lookbehind keeps `something.ref(` and `my_ref(` out.
REF_PERMISSIVE = re.compile(
    r"(?<![\w.])ref\s*\(\s*(?:['\"][\w.\-]+['\"]\s*,\s*)?['\"](\w+)['\"]\s*\)",
    re.IGNORECASE)

# Comments are stripped before either pattern runs. Without this a commented-out
# model reference becomes an edge, which is how the published Mattermost graphs
# acquired 7 edges that exist in no compiled manifest.
SQL_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
SQL_LINE_COMMENT = re.compile(r"--[^\n]*")
JINJA_COMMENT = re.compile(r"\{#.*?#\}", re.DOTALL)

DEFAULT_MODEL_PATHS = ['models']


def strip_sql_comments(text):
    """Remove block, line and Jinja comments, preserving line structure."""
    text = SQL_BLOCK_COMMENT.sub(lambda m: '\n' * m.group(0).count('\n'), text)
    text = JINJA_COMMENT.sub(lambda m: '\n' * m.group(0).count('\n'), text)
    return SQL_LINE_COMMENT.sub('', text)


# --------------------------------------------------------------------------
# git plumbing
# --------------------------------------------------------------------------

def git(repo, *args, check=False):
    p = subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {p.stderr.strip()[:300]}")
    return p.stdout


def ls_tree(repo, sha, paths=None):
    """[(mode, type, blob_sha, path)] for every blob under paths at sha."""
    args = ['ls-tree', '-r', '-z', sha]
    if paths:
        args.append('--')
        args.extend(paths)
    out = git(repo, *args)
    rows = []
    for rec in out.split('\0'):
        if not rec:
            continue
        meta, _, path = rec.partition('\t')
        parts = meta.split()
        if len(parts) != 3:
            continue
        mode, otype, osha = parts
        if otype == 'blob':
            rows.append((mode, otype, osha, path))
    return rows


def cat_blobs(repo, blob_shas):
    """Batch-read blobs. Returns {blob_sha: bytes}."""
    if not blob_shas:
        return {}
    p = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=repo,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    stdout, _ = p.communicate(('\n'.join(blob_shas) + '\n').encode())
    out = {}
    pos = 0
    n = len(stdout)
    while pos < n:
        nl = stdout.find(b'\n', pos)
        if nl == -1:
            break
        header = stdout[pos:nl].decode('utf-8', 'replace').split()
        pos = nl + 1
        if len(header) != 3:
            continue
        osha, _otype, size = header[0], header[1], int(header[2])
        out[osha] = stdout[pos:pos + size]
        pos += size + 1
    return out


# --------------------------------------------------------------------------
# dbt project discovery
# --------------------------------------------------------------------------

def parse_dbt_project(raw: bytes):
    """Return (project_name, [model-paths]) from a dbt_project.yml blob."""
    try:
        doc = yaml.safe_load(raw.decode('utf-8', 'replace'))
    except Exception:
        return None, list(DEFAULT_MODEL_PATHS)
    if not isinstance(doc, dict):
        return None, list(DEFAULT_MODEL_PATHS)
    name = doc.get('name') if isinstance(doc.get('name'), str) else None
    mp = doc.get('model-paths') or doc.get('source-paths') or DEFAULT_MODEL_PATHS
    if isinstance(mp, str):
        mp = [mp]
    if not isinstance(mp, list):
        mp = list(DEFAULT_MODEL_PATHS)
    mp = [str(x).strip('/') for x in mp if isinstance(x, (str, int))]
    return name, (mp or list(DEFAULT_MODEL_PATHS))


# Directories that hold third-party dbt packages vendored into the repository,
# or dbt build output. Their models belong to dbt_utils and friends, not to the
# project under study, so counting them inflates N and fuses unrelated lineage.
VENDOR_MARKERS = ('dbt_modules/', 'dbt_packages/', 'target/', 'integration_tests/',
                  'dbt_internal_packages/')


def is_vendored(path):
    p = path if path.endswith('/') else path + '/'
    return any(m in p for m in VENDOR_MARKERS)


def discover_model_paths(repo, sha):
    """Model directories, repo-relative, declared by every dbt_project.yml at sha.

    Returns ([paths], [{'config': path, 'name': str, 'model_paths': [...]}, ...]).
    """
    blobs = ls_tree(repo, sha)
    cfgs = [(osha, path) for _m, _t, osha, path in blobs
            if PurePosixPath(path).name == 'dbt_project.yml'
            and not is_vendored(path)]
    if not cfgs:
        return [], []
    contents = cat_blobs(repo, [c[0] for c in cfgs])
    paths, projects = [], []
    for osha, path in cfgs:
        raw = contents.get(osha, b'')
        name, mps = parse_dbt_project(raw)
        base = str(PurePosixPath(path).parent)
        resolved = []
        for mp in mps:
            full = mp if base in ('.', '') else f'{base}/{mp}'
            full = str(PurePosixPath(full))
            resolved.append(full)
            if full not in paths:
                paths.append(full)
        projects.append({'config': path, 'name': name, 'model_paths': resolved})
    return paths, projects


def read_configs_at(repo, sha, config_paths):
    """Resolve model-paths for named dbt_project.yml files at one commit.

    Same output shape as `discover_model_paths`, restricted to configs already
    known, and without listing the whole tree.
    """
    if not config_paths:
        return []
    blobs = ls_tree(repo, sha, list(config_paths))
    cfgs = [(osha, path) for _m, _t, osha, path in blobs
            if PurePosixPath(path).name == 'dbt_project.yml']
    if not cfgs:
        return []
    contents = cat_blobs(repo, [c[0] for c in cfgs])
    projects = []
    for osha, path in cfgs:
        name, mps = parse_dbt_project(contents.get(osha, b''))
        base = str(PurePosixPath(path).parent)
        resolved = [str(PurePosixPath(mp if base in ('.', '') else f'{base}/{mp}'))
                    for mp in mps]
        projects.append({'config': path, 'name': name, 'model_paths': resolved})
    return projects


def count_commits_on_paths(repo, rev, paths):
    if not paths:
        return 0
    out = git(repo, 'rev-list', '--count', rev, '--', *paths).strip()
    try:
        return int(out)
    except ValueError:
        return 0


def path_activity(repo, rev, paths):
    """(n_commits, first_date, last_date) for commits touching paths."""
    if not paths:
        return 0, None, None
    out = git(repo, 'log', '--pretty=format:%ai', rev, '--', *paths)
    dates = []
    for line in out.splitlines():
        try:
            dates.append(datetime.strptime(line[:19], '%Y-%m-%d %H:%M:%S'))
        except ValueError:
            continue
    if not dates:
        return 0, None, None
    return len(dates), min(dates), max(dates)


def path_activity_bulk(repo, rev, groups):
    """Activity for several path groups from a single history walk.

    `path_activity` costs one full history walk per group, and a repository can
    carry a dozen `dbt_project.yml` files, so ranking them that way dominates
    the runtime. One `git log --name-only` pass attributes every changed file to
    whichever groups contain it.

    `groups` is [[path, ...], ...]. Returns a list of (n_commits, first, last)
    in the same order. Counts come from a walk without pathspec history
    simplification, so they can differ slightly from `path_activity`. They are
    only used to rank groups and to date them, never to select commits.
    """
    if not groups:
        return []
    out = git(repo, 'log', '--pretty=format:%x00%ai', '--name-only', rev)
    prefixes = [tuple(p.rstrip('/') + '/' for p in grp) for grp in groups]
    exact = [set(p.rstrip('/') for p in grp) for grp in groups]
    counts = [0] * len(groups)
    first = [None] * len(groups)
    last = [None] * len(groups)

    def close(dt, hits):
        for i in hits:
            counts[i] += 1
            if first[i] is None or dt < first[i]:
                first[i] = dt
            if last[i] is None or dt > last[i]:
                last[i] = dt

    dt, hits = None, set()
    for line in out.split('\n'):
        if line.startswith('\0'):
            if dt is not None and hits:
                close(dt, hits)
            hits = set()
            try:
                dt = datetime.strptime(line[1:20], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                dt = None
            continue
        if not line or dt is None:
            continue
        for i, pres in enumerate(prefixes):
            if i in hits:
                continue
            if line.startswith(pres) or line in exact[i]:
                hits.add(i)
    if dt is not None and hits:
        close(dt, hits)
    return list(zip(counts, first, last))


def _interval_overlap_ratio(a, b):
    """Overlap of two (start, end) intervals as a fraction of the shorter one."""
    (a0, a1), (b0, b1) = a, b
    lo, hi = max(a0, b0), min(a1, b1)
    overlap = max(0.0, (hi - lo).total_seconds())
    shorter = min((a1 - a0).total_seconds(), (b1 - b0).total_seconds())
    if shorter <= 0:
        return 1.0 if overlap > 0 else 0.0
    return overlap / shorter


RELOCATION_OVERLAP = 0.2


def path_universe(repo, head, n_probes=6):
    """Choose the dbt project to follow and return its model paths.

    A repository can hold several independent dbt projects. Their models never
    ref() each other, so measuring their union produces a disconnected graph, and
    every D1 and D3 routine silently reduces a disconnected graph to its giant
    component. That would count the smaller project in N and M while dropping it
    from the community and spectral descriptors.

    The unit of observation is therefore one dbt project, the one whose model
    paths carry the most commits. That is the project with the longest usable
    series, which is not always the largest one at HEAD. Mattermost is the case
    in point: `transform/mattermost-analytics` has more models today but only
    236 commits since 2023, while `transform/snowflake-dbt` has 1,335 commits
    back to 2019.

    Two configs are not always two projects. A project that relocates leaves a
    second `dbt_project.yml` behind, and treating the two as rivals throws away
    half the history. Datadex moved from `models/` to `dbt/models/` on
    2023-04-11 and the two intervals do not overlap at all, whereas Mattermost's
    two projects overlap for two years. Configs whose model-path commit
    intervals overlap by less than RELOCATION_OVERLAP of the shorter interval
    are therefore chained into one series rather than competing.

    Returns ([paths for the chosen project], {'probes': ..., 'projects': ...}).
    """
    shas = [s for s in git(repo, 'rev-list', '--first-parent', head).split() if s]
    if not shas:
        return [], {}
    picks = [shas[0]]
    if len(shas) > 1:
        step = max(1, len(shas) // max(1, n_probes - 1))
        picks.extend(shas[i] for i in range(step, len(shas), step))
        picks.append(shas[-1])

    seen, per_probe = set(), {}
    # config path -> {'name', 'model_paths'} unioned across probes
    by_config = {}
    for s in picks:
        if s in seen:
            continue
        seen.add(s)
        _paths, projects = discover_model_paths(repo, s)
        per_probe[s] = projects
        for pr in projects:
            slot = by_config.setdefault(
                pr['config'], {'config': pr['config'], 'name': pr['name'],
                               'model_paths': []})
            if pr['name'] and not slot['name']:
                slot['name'] = pr['name']
            for mp in pr['model_paths']:
                if mp not in slot['model_paths']:
                    slot['model_paths'].append(mp)
    if not by_config:
        return [], {'probes': per_probe, 'projects': []}

    ranked = list(by_config.values())
    # One config needs no bulk walk, and the pathspec-filtered log is cheaper.
    if len(ranked) == 1:
        activity = [path_activity(repo, head, ranked[0]['model_paths'])]
    else:
        activity = path_activity_bulk(repo, head,
                                      [s['model_paths'] for s in ranked])
    for slot, (n, first, last) in zip(ranked, activity):
        slot['commits_on_model_paths'] = n
        slot['first_commit'] = first.isoformat() if first else None
        slot['last_commit'] = last.isoformat() if last else None
        slot['_interval'] = (first, last) if first and last else None
    ranked.sort(key=lambda s: (-s['commits_on_model_paths'], s['config']))

    chosen = ranked[0]
    chain = [chosen]
    span = chosen['_interval']
    for other in ranked[1:]:
        if not other['_interval'] or not span:
            continue
        if _interval_overlap_ratio(span, other['_interval']) < RELOCATION_OVERLAP:
            chain.append(other)
            span = (min(span[0], other['_interval'][0]),
                    max(span[1], other['_interval'][1]))

    paths, configs = [], []
    for slot in chain:
        configs.append(slot['config'])
        for mp in slot['model_paths']:
            if mp not in paths:
                paths.append(mp)
    for slot in ranked:
        slot.pop('_interval', None)

    # If every probe that carried the chosen config resolved the same model
    # paths, the layout never moved and there is nothing to re-resolve at each
    # snapshot. That removes two process spawns per snapshot.
    chain_cfgs = set(configs)
    seen_resolutions = set()
    for _s, projects in per_probe.items():
        for pr in projects:
            if pr['config'] in chain_cfgs:
                seen_resolutions.add(tuple(pr['model_paths']))
    stable = len(seen_resolutions) <= 1

    return paths, {
        'probes': per_probe,
        'model_paths_stable': stable,
        'projects': ranked,
        'chosen_config': chosen['config'],
        'chosen_name': chosen['name'],
        'chained_configs': configs,
        'n_dbt_projects_seen': len(ranked),
        'n_configs_chained': len(chain),
    }


# --------------------------------------------------------------------------
# commit sampling (verbatim from exp_longitudinal_dbt.py)
# --------------------------------------------------------------------------

def list_commits_in_paths(repo, paths, rev='HEAD'):
    """[(datetime, sha, subject)] oldest first, for commits touching paths.

    The subject comes back with the listing rather than from a `git log -1` per
    sampled commit. Process spawns dominate the runtime on repositories with
    many snapshots, so one call here removes one per snapshot.
    """
    args = ['log', '--reverse', '--pretty=format:%ai|%H|%s', rev]
    if paths:
        args.append('--')
        args.extend(paths)
    out = git(repo, *args)
    rows = []
    for line in out.splitlines():
        parts = line.split('|', 2)
        if len(parts) < 2:
            continue
        date_str, sha = parts[0], parts[1]
        subject = parts[2] if len(parts) > 2 else ''
        try:
            dt = datetime.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
        rows.append((dt, sha, subject))
    return rows


def sample_one_per_window(commits, window_days=30):
    """Keep the last commit in each rolling window_days bucket."""
    if not commits:
        return []
    sampled = []
    bucket_end = commits[0][0] + timedelta(days=window_days)
    last_in_bucket = commits[0]
    for entry in commits[1:]:
        dt = entry[0]
        if dt < bucket_end:
            last_in_bucket = entry
        else:
            sampled.append(last_in_bucket)
            while dt >= bucket_end:
                bucket_end += timedelta(days=window_days)
            last_in_bucket = entry
    sampled.append(last_in_bucket)
    return sampled


# --------------------------------------------------------------------------
# lineage extraction
# --------------------------------------------------------------------------

LAYER_RULES = [
    ('staging', ('stg_', 'staging_', 'base_', 'src_')),
    ('intermediate', ('int_', 'intermediate_')),
    ('mart', ('fct_', 'dim_', 'mart_', 'rpt_', 'agg_', 'bridge_')),
]


def classify_layer(name, path):
    lowered = name.lower()
    for layer, prefixes in LAYER_RULES:
        if lowered.startswith(prefixes):
            return layer
    parts = [p.lower() for p in PurePosixPath(path).parts]
    for layer, tokens in [('staging', ('staging', 'stg', 'base')),
                          ('intermediate', ('intermediate', 'int')),
                          ('mart', ('marts', 'mart', 'core', 'facts', 'dims',
                                    'dimensions', 'reporting', 'presentation'))]:
        if any(t in parts for t in tokens):
            return layer
    return 'unclassified'


def coverage_at_commit(repo, sha, model_paths, model_names, blobs=None,
                       contents=None):
    """Documentation and test coverage from the schema YAML beside the models.

    The extractor never opened these files, so the two governance-adjacent
    variables the corpus could most usefully carry were invisible. dbt records a
    model's description and its tests in a `.yml` next to it, not in the SQL.

    A model counts as documented when its `description` is a non-empty string,
    and as tested when it carries a `tests` or `data_tests` key at model level or
    on any of its columns. Both are measured against the models actually present
    in the graph, so a YAML entry for a model that no longer exists is ignored.
    """
    # The caller has already listed this tree and read most of it. Listing it
    # again costs two process spawns per snapshot, and process spawns dominate
    # the runtime on a project with fifty snapshots.
    if blobs is None:
        blobs = ls_tree(repo, sha, list(model_paths))
    ymls = [(osha, path) for _m, _t, osha, path in blobs
            if path.endswith(('.yml', '.yaml')) and not is_vendored(path)]
    out = {'n_documented': 0, 'n_tested': 0, 'n_yaml_files': len(ymls),
            'doc_rate': None, 'test_rate': None, 'yaml_parse_errors': 0}
    if not model_names:
        return out
    if not ymls:
        out['doc_rate'] = 0.0
        out['test_rate'] = 0.0
        return out

    if contents is None:
        contents = cat_blobs(repo, [y[0] for y in ymls])
    documented, tested, errors = set(), set(), 0
    for osha, _path in ymls:
        raw = contents.get(osha)
        if raw is None:
            continue
        try:
            doc = yaml.safe_load(raw.decode('utf-8', 'replace'))
        except Exception:
            errors += 1
            continue
        if not isinstance(doc, dict):
            continue
        for entry in (doc.get('models') or []):
            if not isinstance(entry, dict):
                continue
            name = entry.get('name')
            if name not in model_names:
                continue
            desc = entry.get('description')
            if isinstance(desc, str) and desc.strip():
                documented.add(name)
            has_tests = bool(entry.get('tests') or entry.get('data_tests'))
            for col in (entry.get('columns') or []):
                if isinstance(col, dict) and (col.get('tests')
                                              or col.get('data_tests')):
                    has_tests = True
                    break
            if has_tests:
                tested.add(name)
    n = len(model_names)
    out.update({'n_documented': len(documented), 'n_tested': len(tested),
                'doc_rate': round(len(documented) / n, 6),
                'test_rate': round(len(tested) / n, 6),
                'yaml_parse_errors': errors})
    return out


def extract_lineage_at_commit(repo, sha, model_paths, fixed_paths=False,
                              chosen_config=None):
    """Parse ref() out of the model SQL at a commit. Returns (DiGraph, meta).

    `model_paths` is the fallback path list. When `chosen_config` names the
    dbt_project.yml of the project under study, its model-paths are re-resolved
    from that commit's own copy of the file, so a project that moves or renames
    its model directory stays measurable.
    """
    projects = []
    paths = list(model_paths)
    if not fixed_paths and chosen_config:
        wanted = list(chosen_config if isinstance(chosen_config, (list, tuple))
                      else [chosen_config])
        # Ask git for those exact config paths rather than listing the whole
        # tree. A full recursive ls-tree per snapshot dominates the runtime on
        # a repository with tens of thousands of files.
        projects = read_configs_at(repo, sha, wanted)
        live = []
        for pr in projects:
            for mp in pr['model_paths']:
                if mp not in live:
                    live.append(mp)
        if live:
            paths = live

    blobs = ls_tree(repo, sha, paths)
    # Same exclusions as the original, applied to the repo-relative path,
    # plus vendored dbt packages which are not the project's own models.
    sql = [(osha, path) for _m, _t, osha, path in blobs
           if path.endswith('.sql')
           and 'macros' not in path
           and '/tests/' not in path
           and '/snapshots/' not in path
           and not is_vendored(path)]
    if not sql:
        return None, {'model_paths': paths, 'projects': projects, 'n_sql_files': 0}

    yml_shas = [osha for _m, _t, osha, path in blobs
                if path.endswith(('.yml', '.yaml')) and not is_vendored(path)]
    contents = cat_blobs(repo, [s[0] for s in sql] + yml_shas)
    stems = {}
    for osha, path in sql:
        stems.setdefault(PurePosixPath(path).stem, path)
    model_names = set(stems)

    g = nx.DiGraph()
    # Sorted, not set order. See module docstring.
    g.add_nodes_from(sorted(model_names))
    # capture_mode per edge, so the strict parse stays reconstructable from the
    # released data and the difference between the two is auditable rather than
    # merely disclosed.
    edge_mode = {}
    n_raw_comment_hits = 0
    for osha, path in sorted(sql, key=lambda x: x[1]):
        raw = contents.get(osha)
        if raw is None:
            continue
        text = raw.decode('utf-8', 'replace')
        clean = strip_sql_comments(text)
        stem = PurePosixPath(path).stem
        strict = {r for r in REF_STRICT.findall(clean) if r in model_names}
        permissive = {r for r in REF_PERMISSIVE.findall(clean) if r in model_names}
        # What the uncleaned text would have produced, to size the comment bug.
        # Only worth a second regex pass when stripping actually removed
        # something, which is the minority of files.
        if len(clean) != len(text):
            n_raw_comment_hits += len(
                {r for r in REF_PERMISSIVE.findall(text) if r in model_names}
                - permissive)
        for r in sorted(permissive):
            g.add_edge(r, stem)
            edge_mode[(r, stem)] = ('strict' if r in strict else 'permissive_only')

    layers = {}
    for name, path in stems.items():
        layers[classify_layer(name, path)] = layers.get(classify_layer(name, path), 0) + 1

    # Nodes come from the file listing, never from the regex. Changing how refs
    # are matched must move M and leave N alone, so an inflated node count means
    # an edge was added for a target that is not a model in this snapshot. The
    # `r in model_names` filter is what prevents it, and this is the guard that
    # notices if the filter is ever dropped.
    if g.number_of_nodes() != len(model_names):
        raise AssertionError(
            f'ref matching changed the node set at {sha[:12]}: '
            f'{len(model_names)} model files produced {g.number_of_nodes()} '
            f'nodes. Edges must never introduce a node.')

    n_strict = sum(1 for m in edge_mode.values() if m == 'strict')
    n_recovered = len(edge_mode) - n_strict
    touched = {n for (a, b), m in edge_mode.items()
               if m == 'permissive_only' for n in (a, b)}
    meta = {'model_paths': paths, 'projects': projects, 'n_sql_files': len(sql),
            'layers': layers, 'n_stem_collisions': len(sql) - len(stems),
            'edge_mode': edge_mode,
            'M_strict': n_strict,
            'M_recovered_by_permissive': n_recovered,
            'nodes_touched_by_recovered': len(touched),
            'edges_dropped_as_commented_out': n_raw_comment_hits,
            'model_files': dict(stems)}
    meta.update(coverage_at_commit(repo, sha, paths, model_names,
                                   blobs=blobs, contents=contents))
    return g, meta


def connectivity_context(g):
    """How much of the graph the D1 and D3 routines actually see.

    `_to_undirected_connected` in both `spectral` and `community_stability`
    reduces a disconnected graph to its giant component. A lineage graph with
    many isolated models therefore reports a large N while D1 and D3 describe a
    fraction of it. Recording that fraction is the only way a reader can tell
    the difference between a well-connected 50-node DAG and 50 loose files.
    """
    n = g.number_of_nodes()
    if n == 0:
        return {'n_components': 0, 'giant_component_frac': 0.0,
                'isolated_frac': 0.0}
    u = g.to_undirected()
    comps = list(nx.connected_components(u))
    giant = max((len(c) for c in comps), default=0)
    isolated = sum(1 for _node, deg in u.degree() if deg == 0)
    return {'n_components': len(comps),
            'giant_component_frac': round(giant / n, 6),
            'isolated_frac': round(isolated / n, 6)}


def graph_shape_only(g):
    """Size and connectivity without the D1-D4 descriptors.

    D1 runs Louvain fifteen times per snapshot, so on a large graph the
    descriptors cost more than recovering the graph does. On Cal-ITP's 53
    snapshots the full run takes about half again as long as this one. Useful
    for sizing a candidate set before paying for the descriptors on
    repositories that will not clear the inclusion floor anyway.
    """
    n, m = g.number_of_nodes(), g.number_of_edges()
    return {'N': n, 'M': m, 'too_small': n < 5, **connectivity_context(g)}


def compute_descriptors_safe(g):
    """Verbatim descriptor block from exp_longitudinal_dbt.py."""
    n = g.number_of_nodes()
    m = g.number_of_edges()
    if n < 5:
        return {'N': n, 'M': m, 'too_small': True, **connectivity_context(g)}
    out = {'N': n, 'M': m, 'too_small': False, **connectivity_context(g)}
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


# --------------------------------------------------------------------------
# per-project driver
# --------------------------------------------------------------------------

def run_project(repo, project_id, repo_url, out_dir, window_days=30,
                fixed_model_paths=None, max_snapshots=None, verbose=True,
                descriptors=True, emit_edges=True):
    started = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
    result = {
        'project_id': project_id,
        'repo_url': repo_url,
        'tool_version': TOOL_VERSION,
        'extraction_started_utc': started,
        'window_days': window_days,
        'descriptors_computed': descriptors,
        'status': 'failed',
        'error': None,
        'snapshots': [],
    }

    def finish():
        """Persist and return. Every exit from this function goes through here,
        so a project that fails for a legitimate reason still leaves a result
        file explaining why rather than nothing at all."""
        result['extraction_finished_utc'] = (
            datetime.utcnow().isoformat(timespec='seconds') + 'Z')
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, f'{project_id}.json'), 'w') as f:
                json.dump(result, f, indent=1)
        return result

    try:
        # Resolve the remote's default branch rather than trusting HEAD, which
        # may be detached from an earlier tool run.
        ref = 'HEAD'
        symref = git(repo, 'symbolic-ref', '-q', 'refs/remotes/origin/HEAD').strip()
        if symref:
            ref = symref
        head = git(repo, 'rev-parse', ref, check=True).strip()
        result['head_sha'] = head
        result['default_branch'] = (
            symref.rsplit('/', 1)[-1] if symref
            else (git(repo, 'rev-parse', '--abbrev-ref', 'HEAD').strip() or None))

        if fixed_model_paths:
            universe, info = list(fixed_model_paths), {}
        else:
            universe, info = path_universe(repo, head)
        chosen_config = info.get('chained_configs') or (
            [info['chosen_config']] if info.get('chosen_config') else None)
        result['model_path_universe'] = universe
        result['dbt_project_chosen'] = {
            'primary_config': info.get('chosen_config'),
            'name': info.get('chosen_name'),
            'chained_configs': info.get('chained_configs'),
            'n_configs_chained': info.get('n_configs_chained'),
            'model_paths': universe}
        result['dbt_projects_seen'] = info.get('projects', [])
        result['n_dbt_projects_seen'] = info.get('n_dbt_projects_seen', 0)
        if not universe:
            result['status'] = 'failed'
            result['error'] = ('no dbt_project.yml found anywhere on the '
                               'first-parent history')
            return finish()

        commits = list_commits_in_paths(repo, universe, rev=head)
        result['n_commits_touching_models'] = len(commits)
        if not commits:
            result['status'] = 'failed'
            result['error'] = 'no commits touch any declared model path'
            return finish()
        result['history_start'] = commits[0][0].isoformat()
        result['history_end'] = commits[-1][0].isoformat()

        sampled = sample_one_per_window(commits, window_days=window_days)
        if max_snapshots:
            sampled = sampled[:max_snapshots]
        result['n_snapshots_planned'] = len(sampled)

        resolve_per_commit = (chosen_config if not info.get('model_paths_stable')
                              else None)
        result['model_paths_stable'] = bool(info.get('model_paths_stable'))

        rows, errors = [], []
        edges_out = [] if emit_edges else None
        for i, entry in enumerate(sampled):
            dt, sha = entry[0], entry[1]
            subject = entry[2] if len(entry) > 2 else ''
            try:
                g, meta = extract_lineage_at_commit(
                    repo, sha, universe, fixed_paths=bool(fixed_model_paths),
                    chosen_config=resolve_per_commit)
                if g is None:
                    errors.append({'sha': sha, 'date': dt.isoformat(),
                                   'reason': 'no model SQL at this commit'})
                    continue
                desc = (compute_descriptors_safe(g) if descriptors
                        else graph_shape_only(g))
                row = {'date': dt.isoformat(), 'sha': sha,
                       'commit_msg': subject[:120], **desc}
                layers = meta.get('layers', {})
                for layer in ('staging', 'intermediate', 'mart', 'unclassified'):
                    row[f'n_{layer}'] = layers.get(layer, 0)
                row['n_sql_files'] = meta['n_sql_files']
                row['n_dbt_projects'] = (len(meta.get('projects') or [])
                                         or info.get('n_dbt_projects_seen', 0))
                for k in ('M_strict', 'M_recovered_by_permissive',
                          'nodes_touched_by_recovered',
                          'edges_dropped_as_commented_out',
                          'n_documented', 'n_tested', 'n_yaml_files',
                          'doc_rate', 'test_rate'):
                    row[k] = meta.get(k)
                if edges_out is not None:
                    for (a, b), mode in sorted(meta['edge_mode'].items()):
                        edges_out.append({'sha': sha, 'date': dt.isoformat(),
                                          'source': a, 'target': b,
                                          'capture_mode': mode})
                rows.append(row)
                if verbose and (i % 10 == 0 or i == len(sampled) - 1):
                    print(f'  {project_id} [{i+1}/{len(sampled)}] {dt.date()} '
                          f"N={desc.get('N')} M={desc.get('M')}", flush=True)
            except Exception as e:
                errors.append({'sha': sha, 'date': dt.isoformat(),
                               'reason': f'{type(e).__name__}: {str(e)[:200]}'})

        result['snapshots'] = rows
        # Edges go to their own gzipped file rather than into the result JSON.
        # Cal-ITP alone carries 31,345 of them across its 53 snapshots, and a
        # reader who only wants the descriptor series should not have to parse
        # them.
        if edges_out is not None and out_dir:
            edir = os.path.join(out_dir, 'edges')
            os.makedirs(edir, exist_ok=True)
            epath = os.path.join(edir, f'{project_id}.csv.gz')
            with gzip.open(epath, 'wt', newline='') as f:
                w = csv.DictWriter(
                    f, fieldnames=['sha', 'date', 'source', 'target',
                                   'capture_mode'])
                w.writeheader()
                w.writerows(edges_out)
            result['edges_file'] = f'edges/{project_id}.csv.gz'
            result['n_edge_rows'] = len(edges_out)
        result['snapshot_errors'] = errors
        result['n_snapshots'] = len(rows)
        result['snapshot_coverage'] = (round(len(rows) / len(sampled), 4)
                                       if sampled else 0.0)
        if not rows:
            result['status'] = 'failed'
            result['error'] = 'every sampled commit yielded zero models'
        elif errors:
            result['status'] = 'partial'
            result['error'] = f'{len(errors)} of {len(sampled)} snapshots failed'
        else:
            result['status'] = 'success'
    except Exception as e:
        result['status'] = 'failed'
        result['error'] = f'{type(e).__name__}: {str(e)[:300]}'
        result['traceback'] = traceback.format_exc()[-1500:]

    return finish()
