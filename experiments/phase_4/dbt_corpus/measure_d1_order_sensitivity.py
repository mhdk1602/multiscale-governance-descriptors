"""Quantify how much D1 moves when only the node insertion order changes.

The two-project pipeline built each lineage graph by inserting nodes from a
Python set. Set iteration order for strings depends on `PYTHONHASHSEED`, which
CPython randomises per process, and Louvain's greedy pass is order sensitive, so
`D1_csi` and `D1_n_comm` in the published artifacts are not reproducible between
runs. The corpus extractor inserts nodes in sorted order, which removes the
dependence, but the published numbers were produced under the old behaviour and
the paper needs the size of the effect rather than the fact of it.

This rebuilds real corpus graphs from their recorded commits, permutes the node
insertion order, and reports the spread of each descriptor across permutations.
D2, D3 and D4 are included as controls; they should not move at all.

    python experiments/phase_4/dbt_corpus/measure_d1_order_sensitivity.py \\
        --release artifacts/phase_4_corpus --clones SCRATCH/clones \\
        --n-permutations 12 --n-snapshots 40 --out artifacts/phase_4_corpus/d1_order_sensitivity.json
"""
import argparse
import csv
import json
import os
import random
import statistics
import sys

import networkx as nx

sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'src')))

from governance_descriptors.dbt_lineage import (  # noqa: E402
    compute_descriptors_safe, extract_lineage_at_commit,
)

# Every descriptor the corpus reports, so the table is complete rather than
# silently partial. D3_fiedler_bim is the one that is not exactly order-stable,
# because the Fiedler vector is not unique under near-degenerate eigenvalues.
CONTROLS = ['D2_max_gini', 'D3_alg_conn', 'D3_norm_gap', 'D3_fiedler_bim',
            'D4_cycle_rank_norm']
SUBJECTS = ['D1_csi', 'D1_n_comm']


def permuted(g, order):
    h = nx.DiGraph()
    h.add_nodes_from(order)
    h.add_edges_from(g.edges())
    return h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--release', required=True)
    ap.add_argument('--clones', required=True)
    ap.add_argument('--n-permutations', type=int, default=12)
    ap.add_argument('--n-snapshots', type=int, default=40)
    ap.add_argument('--min-nodes', type=int, default=20)
    ap.add_argument('--seed', type=int, default=20260804)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    manifest = json.load(open(os.path.join(a.release, 'MANIFEST.json')))
    paths = {p['project_id']: p['model_paths'] for p in manifest['projects']}

    pool = []
    with open(os.path.join(a.release, 'snapshots.csv')) as f:
        for row in csv.DictReader(f):
            try:
                if int(row['N']) >= a.min_nodes:
                    pool.append((row['project_id'], row['sha'], int(row['N'])))
            except (TypeError, ValueError):
                continue
    rng = random.Random(a.seed)
    rng.shuffle(pool)

    records = []
    for pid, sha, _n in pool:
        if len(records) >= a.n_snapshots:
            break
        repo = os.path.join(a.clones, pid)
        if not os.path.isdir(os.path.join(repo, '.git')):
            continue
        g, _meta = extract_lineage_at_commit(repo, sha, paths.get(pid, ['models']))
        if g is None or g.number_of_nodes() < a.min_nodes:
            continue
        nodes = list(g.nodes())
        runs = []
        for k in range(a.n_permutations):
            order = sorted(nodes) if k == 0 else rng.sample(nodes, len(nodes))
            runs.append(compute_descriptors_safe(permuted(g, order)))
        rec = {'project_id': pid, 'sha': sha,
               'N': g.number_of_nodes(), 'M': g.number_of_edges()}
        for key in SUBJECTS + CONTROLS:
            vals = [r.get(key) for r in runs if isinstance(r.get(key), (int, float))]
            if not vals:
                continue
            rec[key] = {
                'min': min(vals), 'max': max(vals),
                'range': max(vals) - min(vals),
                'mean': statistics.fmean(vals),
                'sd': statistics.pstdev(vals),
                'distinct_values': len(set(round(v, 12) for v in vals)),
            }
        records.append(rec)
        print(f'  {pid[:44]:44s} N={rec["N"]:4d} '
              f'D1_csi range {rec.get("D1_csi", {}).get("range", float("nan")):.4f}',
              flush=True)

    def agg(key, field):
        vals = [r[key][field] for r in records if key in r]
        return {'n': len(vals),
                'median': statistics.median(vals) if vals else None,
                'max': max(vals) if vals else None,
                'mean': statistics.fmean(vals) if vals else None}

    summary = {
        'n_snapshots_tested': len(records),
        'n_permutations_each': a.n_permutations,
        'min_nodes': a.min_nodes,
        'seed': a.seed,
        'note': ('Permutation zero is the sorted order the corpus extractor uses. '
                 'The remaining permutations stand in for the arbitrary orders the '
                 'predecessor produced under a randomised process hash seed.'),
        'range_across_permutations': {k: agg(k, 'range')
                                      for k in SUBJECTS + CONTROLS},
        'distinct_values_across_permutations': {k: agg(k, 'distinct_values')
                                                for k in SUBJECTS + CONTROLS},
        'per_snapshot': records,
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'w') as f:
        json.dump(summary, f, indent=1)

    print('\nrange across permutations, median over snapshots')
    for k in SUBJECTS + CONTROLS:
        s = summary['range_across_permutations'][k]
        print(f'  {k:22s} median {s["median"]!s:>22s}  max {s["max"]!s:>22s}')
    print(f'\nwrote {a.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
