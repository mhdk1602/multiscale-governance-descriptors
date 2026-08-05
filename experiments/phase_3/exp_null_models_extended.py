"""Experiment: Extended null models for the dbt manifest.

Goes beyond the degree-preserving rewiring null (exp_2b_null_models.py) with
two additional null models that better respect the layered DAG structure:

NULL MODEL A: Layer-preserving DAG rewiring
  Rewires edges while preserving:
  - In/out-degree of each node
  - Directionality constraint: edges only permitted source→silver, silver→gold,
    or within-layer (same layer to same layer)
  - DAG structure (acyclicity not strictly enforced, reported if broken)

NULL MODEL B: Governance-label permutation within layer stratum
  Holds topology fixed. Permutes domain-level governance labels (doc_rate,
  test_rate) independently within each layer-dominant stratum:
  - source-dominant domains (>50% source/raw nodes)
  - silver-dominant domains (>50% silver/intermediate)
  - gold-dominant domains (>50% gold/mart)
  Mixed-layer domains are permuted within their dominant stratum.

  This directly tests: does D3 algebraic connectivity correlate with
  documentation after removing the layer-composition confound?

Results are reported as z-scores (for A) and permutation p-values (for B).
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import json
import numpy as np
import pandas as pd
import networkx as nx
from scipy import stats
from governance_descriptors.spectral import spectral_descriptors
from governance_descriptors.community_stability import community_descriptor_summary
from governance_descriptors.blast_radius import concentration_profile
from governance_descriptors.persistent_homology import cycle_rank_descriptors
from governance_descriptors.stats_utils import permutation_spearman

N_REWIRE = 100
N_PERM = 5000


def load_dbt():
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
    return g, nodes_df


def _layer_rank(layer):
    """Numeric rank for layer ordering: source=0, silver=1, gold=2."""
    if 'source' in layer:
        return 0
    if 'silver' in layer or 'intermediate' in layer:
        return 1
    return 2


def layer_preserving_rewire(g, n_swaps=None, seed=0):
    """Attempt edge swaps that preserve layer directionality.

    Swaps a pair of edges (u→v, p→q) to (u→q, p→v) only if:
      - u, p are in the same layer (or at least same rank)
      - v, q are in the same layer (or at least same rank)
      - No self-loops, no multi-edges
    Returns the rewired graph and number of accepted swaps.
    """
    rng = np.random.default_rng(seed)
    h = g.copy()
    if n_swaps is None:
        n_swaps = 10 * h.number_of_edges()

    edges = list(h.edges())
    accepted = 0

    for _ in range(n_swaps):
        if len(edges) < 2:
            break
        i, j = rng.integers(0, len(edges), size=2)
        if i == j:
            continue
        u, v = edges[i]
        p, q = edges[j]
        if len({u, v, p, q}) < 4:
            continue

        ul = h.nodes[u].get('layer', '')
        pl = h.nodes[p].get('layer', '')
        vl = h.nodes[v].get('layer', '')
        ql = h.nodes[q].get('layer', '')

        # Accept only if src layers match and tgt layers match
        if _layer_rank(ul) != _layer_rank(pl):
            continue
        if _layer_rank(vl) != _layer_rank(ql):
            continue

        # No self-loop, no existing edge
        if u == q or p == v:
            continue
        if h.has_edge(u, q) or h.has_edge(p, v):
            continue

        h.remove_edge(u, v)
        h.remove_edge(p, q)
        h.add_edge(u, q)
        h.add_edge(p, v)

        # Update edge list
        edges[i] = (u, q)
        edges[j] = (p, v)
        accepted += 1

    return h, accepted


def compute_graph_descriptors(g):
    result = {}
    try:
        d1 = community_descriptor_summary(g)
        result['D1_csi'] = d1['csi']
    except Exception:
        pass
    try:
        d2 = concentration_profile(g)
        result['D2_max_gini'] = d2['max_gini']
    except Exception:
        pass
    try:
        d3 = spectral_descriptors(g)
        result['D3_alg_conn'] = d3['algebraic_connectivity']
        result['D3_fiedler_bim'] = d3['fiedler_bimodality']
        result['D3_norm_gap'] = d3['normalized_spectral_gap']
    except Exception:
        pass
    try:
        cr = cycle_rank_descriptors(g)
        result['D4_cycle_rank_norm'] = cr['cycle_rank_norm']
    except Exception:
        pass
    return result


def main():
    print("=" * 70)
    print("EXTENDED NULL MODELS")
    print("=" * 70)

    g, nodes_df = load_dbt()
    print(f"\nFull graph: N={g.number_of_nodes()}, M={g.number_of_edges()}")

    # ---------------------------------------------------------------
    # NULL MODEL A: Layer-preserving rewiring
    # ---------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"NULL MODEL A: LAYER-PRESERVING REWIRING ({N_REWIRE} rewirings)")
    print("=" * 70)

    real_desc = compute_graph_descriptors(g)
    print("\nReal graph descriptors:")
    for k, v in real_desc.items():
        print(f"  {k:25s}: {v:.4f}")

    null_records = []
    print(f"\nRunning {N_REWIRE} layer-preserving rewirings...", flush=True)
    for i in range(N_REWIRE):
        h, n_accepted = layer_preserving_rewire(g, seed=i)
        desc = compute_graph_descriptors(h)
        desc['accepted_swaps'] = n_accepted
        desc['is_dag'] = nx.is_directed_acyclic_graph(h)
        null_records.append(desc)
        if (i + 1) % 25 == 0:
            print(f"  [{i+1}/{N_REWIRE}]", flush=True)

    null_df = pd.DataFrame(null_records)

    avg_accepted = null_df['accepted_swaps'].mean()
    pct_dag = null_df['is_dag'].mean() * 100
    print(f"\n  Average accepted swaps: {avg_accepted:.1f} / {10*g.number_of_edges()}")
    print(f"  Rewired graphs still DAG: {pct_dag:.1f}%")

    print(f"\n  {'Descriptor':25s} {'Real':>8s} {'NullMean':>9s} {'NullStd':>8s} {'z':>8s} {'Sig':>5s}")
    print("  " + "-" * 65)
    z_results = {}
    for col in ['D1_csi', 'D2_max_gini', 'D3_alg_conn', 'D3_fiedler_bim',
                'D3_norm_gap', 'D4_cycle_rank_norm']:
        if col not in real_desc or col not in null_df.columns:
            continue
        real_val = real_desc[col]
        null_vals = null_df[col].dropna()
        if len(null_vals) < 5:
            continue
        z = (real_val - null_vals.mean()) / (null_vals.std() + 1e-12)
        sig = "***" if abs(z) > 3 else "**" if abs(z) > 2 else "*" if abs(z) > 1.65 else "ns"
        print(f"  {col:25s} {real_val:8.4f} {null_vals.mean():9.4f} {null_vals.std():8.4f} "
              f"{z:+8.3f} {sig:>5s}")
        z_results[col] = {'real': real_val, 'null_mean': float(null_vals.mean()),
                          'null_std': float(null_vals.std()), 'z': float(z)}

    # ---------------------------------------------------------------
    # NULL MODEL B: Governance-label permutation within layer stratum
    # ---------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"NULL MODEL B: GOVERNANCE-LABEL PERMUTATION WITHIN LAYER ({N_PERM} permutations)")
    print("=" * 70)
    print("Tests: does D3 correlate with doc_rate after removing layer confound?")

    # Build domain-level dataset with layer-dominant stratum.
    # exp_2b_dbt_domain_descriptors.csv already carries both the descriptor
    # (D3_alg_conn) and the governance target (doc_rate) on the canonical
    # zero-padded domain key used by dbt_nodes.csv, so it is read directly.
    # An earlier version joined it against dbt_domain_summary.csv, whose
    # unpadded keys (domain_1 vs domain_001) never matched and silently
    # emptied this null model. Do not reinstate that join. The two files use
    # unrelated anonymization labelings, so padding the keys aligns the wrong
    # rows rather than fixing it. See data/README.md.
    domain_desc_path = os.path.join(
        os.path.dirname(__file__), '..', '..', 'artifacts', 'phase_3', 'exp_2b_dbt_domain_descriptors.csv'
    )
    null_b_result = None
    if not os.path.exists(domain_desc_path):
        print("  Domain descriptor CSV not found — run exp_2b_dbt_real_data.py first.")
    else:
        merged = pd.read_csv(domain_desc_path)
        merged = merged.rename(columns={'domain': 'domain_or_team_owner'})
        merged = merged[~merged.get('too_small', pd.Series([False]*len(merged)))].copy()

        # Assign dominant layer per domain
        def dominant_layer(domain):
            dnodes = nodes_df[nodes_df['domain_or_team_owner'] == domain]
            if len(dnodes) == 0:
                return 'unknown'
            counts = dnodes['layer'].value_counts()
            dominant = counts.idxmax()
            if 'source' in dominant:
                return 'source'
            if 'silver' in dominant or 'intermediate' in dominant:
                return 'silver'
            return 'gold'

        merged['dominant_layer'] = merged['domain_or_team_owner'].apply(dominant_layer)
        print(f"\n  Domains available: {len(merged)}")
        print(f"  Layer distribution: {merged['dominant_layer'].value_counts().to_dict()}")

        rng = np.random.default_rng(42)
        # doc_rate is the documentation target the headline D3 correlation
        # (rho = -0.708, n = 18) is computed against elsewhere in phase 3.
        target = 'doc_rate'
        descriptor = 'D3_alg_conn'

        if descriptor not in merged.columns:
            print(f"  {descriptor} not found in domain descriptors — skipping.")
        elif merged[descriptor].notna().sum() < 4:
            print(f"  Too few valid {descriptor} values — skipping.")
        else:
            valid = merged[[descriptor, target, 'dominant_layer']].dropna()
            real_rho, _, _ = permutation_spearman(
                valid[descriptor].values, valid[target].values, n_perms=10000
            )

            # Permutation: shuffle target within each layer stratum
            perm_rhos = []
            for _ in range(N_PERM):
                shuffled = valid[target].copy().values
                for stratum in valid['dominant_layer'].unique():
                    mask = valid['dominant_layer'].values == stratum
                    idx = np.where(mask)[0]
                    if len(idx) > 1:
                        shuffled[idx] = rng.permutation(shuffled[idx])
                rho_perm = stats.spearmanr(valid[descriptor].values, shuffled).statistic
                perm_rhos.append(rho_perm)

            perm_rhos = np.array(perm_rhos)
            perm_p = np.mean(np.abs(perm_rhos) >= np.abs(real_rho))

            print(f"\n  {descriptor} vs {target}:")
            print(f"    Real Spearman rho: {real_rho:.4f}")
            print(f"    Layer-stratified permutation p: {perm_p:.4f} "
                  f"({'significant' if perm_p < 0.05 else 'not significant'} at α=0.05)")
            print(f"    Null rho: mean={perm_rhos.mean():.4f}, std={perm_rhos.std():.4f}")

            if perm_p >= 0.05:
                print("    → D3 correlation does NOT survive layer-stratified permutation.")
                print("      This suggests layer composition is a substantial confound.")
            else:
                print("    → D3 correlation SURVIVES layer-stratified permutation.")
                print("      The association holds within layer strata, not only across them.")

            # Record the per-stratum descriptor spread. When the descriptor is
            # constant inside every stratum the null distribution collapses to
            # a point mass at the observed rho, which is why p reaches 1.000.
            stratum_detail = {
                str(stratum): {
                    'n': int(len(gp)),
                    'n_distinct_descriptor_values': int(gp[descriptor].round(9).nunique()),
                }
                for stratum, gp in valid.groupby('dominant_layer')
            }

            null_b_result = {
                'descriptor': descriptor,
                'target': target,
                'n_domains': int(len(valid)),
                'real_rho': float(real_rho),
                'layer_perm_p': float(perm_p),
                'null_rho_mean': float(perm_rhos.mean()),
                'null_rho_std': float(perm_rhos.std()),
                'n_permutations': N_PERM,
                'strata': stratum_detail,
                'descriptor_constant_within_every_stratum': bool(
                    all(s['n_distinct_descriptor_values'] <= 1 for s in stratum_detail.values())
                ),
            }

    # Save
    out_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'artifacts', 'phase_3')
    os.makedirs(out_dir, exist_ok=True)
    null_df.to_csv(os.path.join(out_dir, 'exp_null_layer_rewire.csv'), index=False)
    summary = {
        'experiment': 'null_models_extended',
        'null_A': {'type': 'layer_preserving_rewiring', 'n': N_REWIRE,
                   'avg_accepted_swaps': float(avg_accepted),
                   'pct_dag': float(pct_dag),
                   'z_scores': z_results},
    }
    if null_b_result is None:
        raise RuntimeError(
            "Null model B produced no result. The summary would be written "
            "without null_B and the layer-stratified permutation claim would "
            "have no artifact behind it. Fix the input data before rerunning."
        )
    summary['null_B'] = null_b_result
    with open(os.path.join(out_dir, 'exp_null_models_extended_summary.json'), 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nResults saved to {out_dir}/")
    print("=" * 70)
    print("EXTENDED NULL MODELS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
