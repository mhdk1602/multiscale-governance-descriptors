"""Experiment: Statistical subset robustness for real-data correlations.

Tests whether the D3 algebraic connectivity—documentation rate correlation
survives five progressively restrictive subset definitions. Also reports
the full hypothesis matrix for all descriptor-target pairs.

Subsets:
  A: All domains with N >= 5 (current baseline)
  B: Domains with at least one internal edge (M_internal > 0)
  C: Excluding source-dominant domains (>50% source/raw nodes)
  D: Excluding the largest domain (potential high leverage)
  E: Internal-edge domains only, excluding the largest domain

Full hypothesis table: all descriptor × 3 target pairs, rho + perm_p + FDR_p.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import json
import numpy as np
import pandas as pd
import networkx as nx
from governance_descriptors.stats_utils import permutation_spearman, benjamini_hochberg

N_PERMS = 10000


def load_data():
    data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
    nodes_df = pd.read_csv(os.path.join(data_dir, 'dbt_nodes.csv'))
    edges_df = pd.read_csv(os.path.join(data_dir, 'dbt_edges.csv'))

    g = nx.DiGraph()
    for _, row in nodes_df.iterrows():
        g.add_node(row['node_id'],
                   layer=row.get('layer', 'unknown'),
                   domain=row.get('domain_or_team_owner', 'unknown'))
    for _, row in edges_df.iterrows():
        src, tgt = row['source_node_id'], row['target_node_id']
        if src in g and tgt in g:
            g.add_edge(src, tgt)

    desc_path = os.path.join(
        os.path.dirname(__file__), '..', '..', 'artifacts', 'phase_3',
        'exp_2b_dbt_domain_descriptors.csv'
    )
    df = pd.read_csv(desc_path)
    df = df[~df['too_small'].fillna(False)].copy()

    # Compute internal edges and dominant layer per domain
    for domain in df['domain'].unique():
        dnodes = [n for n, d in g.nodes(data=True) if d.get('domain') == domain]
        sub = g.subgraph(dnodes).copy()
        m_int = sub.number_of_edges()

        layer_counts = pd.Series([g.nodes[n].get('layer', '') for n in dnodes]).value_counts()
        dominant = layer_counts.idxmax() if len(layer_counts) > 0 else ''
        source_dominant = 'source' in dominant

        mask = df['domain'] == domain
        df.loc[mask, 'M_internal'] = m_int
        df.loc[mask, 'source_dominant'] = source_dominant
        df.loc[mask, 'dominant_layer'] = dominant

    return df, g


def run_subset(df, subset_name, mask, desc_cols, targets):
    sub = df[mask].copy()
    n = len(sub)
    if n < 4:
        print(f"  {subset_name}: n={n} — too small for testing.")
        return []

    tests = []
    for target in targets:
        for col in desc_cols:
            vals = sub[[col, target]].dropna()
            if len(vals) < 4:
                continue
            rho, perm_p, param_p = permutation_spearman(
                vals[col].values, vals[target].values, n_perms=N_PERMS
            )
            tests.append({
                'subset': subset_name, 'n': n,
                'descriptor': col, 'target': target,
                'rho': rho, 'perm_p': perm_p, 'param_p': param_p,
            })

    if tests:
        perm_ps = np.array([t['perm_p'] for t in tests])
        fdr_ps = benjamini_hochberg(perm_ps)
        for i, t in enumerate(tests):
            t['fdr_p'] = float(fdr_ps[i])

    return tests


def main():
    print("=" * 70)
    print("STATISTICAL SUBSET ROBUSTNESS")
    print("=" * 70)

    df, g = load_data()
    print(f"\nDomains loaded (N≥5): {len(df)}")
    print(f"  With internal edges: {(df['M_internal'] > 0).sum()}")
    print(f"  Source-dominant: {df['source_dominant'].astype(bool).sum()}")
    largest_domain = df.nlargest(1, 'N')['domain'].values[0]
    print(f"  Largest domain: {largest_domain} (N={df['N'].max()})")

    desc_cols = [c for c in df.columns
                 if c.startswith('D') and c[1].isdigit()
                 and 'error' not in c and df[c].notna().sum() >= 4]
    targets = ['doc_rate', 'test_rate']

    subsets = {
        'A: all N≥5': df.index,
        'B: internal edges only': df[df['M_internal'] > 0].index,
        'C: no source-dominant': df[~df['source_dominant'].astype(bool)].index,
        'D: no largest domain': df[df['domain'] != largest_domain].index,
        'E: internal + no largest': df[(df['M_internal'] > 0) &
                                       (df['domain'] != largest_domain)].index,
    }

    print("\n" + "=" * 70)
    print("D3 ALGEBRAIC CONNECTIVITY: SUBSET ROBUSTNESS")
    print("=" * 70)

    all_tests = []
    for subset_name, idx in subsets.items():
        mask = df.index.isin(idx)
        tests = run_subset(df, subset_name, mask, desc_cols, targets)
        n = mask.sum()
        print(f"\n  {subset_name} (n={n}):")
        for t in tests:
            if t['descriptor'] == 'D3_alg_conn':
                sig = ("***" if t['fdr_p'] < 0.01 else "**" if t['fdr_p'] < 0.05
                       else "*" if t['fdr_p'] < 0.10 else "ns")
                print(f"    vs {t['target']:12s}: rho={t['rho']:+.3f}  "
                      f"perm_p={t['perm_p']:.4f}  FDR_p={t['fdr_p']:.4f}  {sig}")
        all_tests.extend(tests)

    # Full hypothesis table for Subset A
    print("\n" + "=" * 70)
    print("FULL HYPOTHESIS TABLE (Subset A — all N≥5 domains)")
    print("=" * 70)
    subset_a = [t for t in all_tests if t['subset'] == 'A: all N≥5']
    subset_a.sort(key=lambda t: (t['target'], t['perm_p']))
    for target in targets:
        print(f"\n  vs {target}:")
        print(f"    {'Descriptor':28s} {'rho':>7s} {'perm_p':>8s} {'FDR_p':>8s} {'Sig':>4s}")
        print(f"    {'-'*55}")
        for t in [x for x in subset_a if x['target'] == target]:
            sig = ("***" if t['fdr_p'] < 0.01 else "**" if t['fdr_p'] < 0.05
                   else "*" if t['fdr_p'] < 0.10 else "ns")
            print(f"    {t['descriptor']:28s} {t['rho']:+7.3f} {t['perm_p']:8.4f} "
                  f"{t['fdr_p']:8.4f} {sig:>4s}")

    # Robustness verdict
    print("\n" + "=" * 70)
    print("ROBUSTNESS VERDICT: D3_alg_conn vs doc_rate")
    print("=" * 70)
    focus = {t['subset']: t for t in all_tests
             if t['descriptor'] == 'D3_alg_conn' and t['target'] == 'doc_rate'}
    for subset_name in subsets:
        if subset_name in focus:
            t = focus[subset_name]
            status = "SURVIVES (FDR<0.10)" if t['fdr_p'] < 0.10 else "FAILS (FDR≥0.10)"
            print(f"  {subset_name:35s}: rho={t['rho']:+.3f}  FDR_p={t['fdr_p']:.4f}  {status}")

    # Save
    out_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'artifacts', 'phase_3')
    os.makedirs(out_dir, exist_ok=True)
    pd.DataFrame(all_tests).to_csv(
        os.path.join(out_dir, 'exp_statistical_robustness.csv'), index=False)

    summary = {
        'experiment': 'statistical_robustness',
        'n_permutations': N_PERMS,
        'd3_doc_robustness': {
            t['subset']: {'n': t['n'], 'rho': t['rho'], 'fdr_p': t['fdr_p']}
            for t in all_tests
            if t['descriptor'] == 'D3_alg_conn' and t['target'] == 'doc_rate'
        },
    }
    with open(os.path.join(out_dir, 'exp_statistical_robustness_summary.json'), 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nSaved to {out_dir}/")
    print("=" * 70)
    print("STATISTICAL ROBUSTNESS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
