"""Experiment 2b-null: Degree-preserving directed rewiring null model.

Rewires edges of the real dbt lineage graph 100 times while preserving
in-degree and out-degree sequences. Computes D1-D4 + cycle-rank on
each rewired graph. Reports z-scores of observed (real) values relative
to the null distribution.

If descriptors capture governance-relevant structure beyond what degree
sequences alone determine, the real values should fall outside the null
distribution (|z| > 2).
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import json
import numpy as np
import pandas as pd
import networkx as nx
from governance_descriptors.community_stability import community_descriptor_summary
from governance_descriptors.blast_radius import concentration_profile
from governance_descriptors.spectral import spectral_descriptors
from governance_descriptors.persistent_homology import topological_descriptors, cycle_rank_descriptors


def load_graph(nodes_path, edges_path):
    nodes_df = pd.read_csv(nodes_path)
    edges_df = pd.read_csv(edges_path)
    g = nx.DiGraph()
    for _, row in nodes_df.iterrows():
        domain_col = "domain_or_team_owner" if "domain_or_team_owner" in nodes_df.columns else "domain"
        attrs = {
            "layer": row.get("layer", "unknown"),
            "domain": row.get(domain_col, "unknown"),
        }
        g.add_node(row["node_id"], **attrs)
    for _, row in edges_df.iterrows():
        src, tgt = row["source_node_id"], row["target_node_id"]
        if src in g and tgt in g:
            g.add_edge(src, tgt)
    return g


def degree_preserving_rewire(g, n_swaps=None, seed=42):
    """Degree-preserving directed edge rewiring.

    Uses networkx directed_edge_swap which preserves both in- and
    out-degree of every node. n_swaps defaults to 10 * edge count.
    """
    g_rw = g.copy()
    m = g_rw.number_of_edges()
    if n_swaps is None:
        n_swaps = 10 * m
    try:
        nx.directed_edge_swap(g_rw, nswap=n_swaps, max_tries=n_swaps * 10, seed=seed)
    except nx.NetworkXAlgorithmError:
        pass
    return g_rw


def compute_descriptors_safe(g) -> dict:
    n = g.number_of_nodes()
    m = g.number_of_edges()
    result = {"N": n, "M": m}

    try:
        d1 = community_descriptor_summary(g)
        result["D1_csi"] = d1["csi"]
        result["D1_frag_onset"] = d1["fragmentation_onset"]
        result["D1_n_comm"] = d1["n_communities_at_gamma_1"]
    except Exception:
        pass

    try:
        d2 = concentration_profile(g)
        result["D2_max_gini"] = d2["max_gini"]
        result["D2_transition"] = d2["concentration_transition_depth"]
    except Exception:
        pass

    try:
        d3 = spectral_descriptors(g)
        result["D3_alg_conn"] = d3["algebraic_connectivity"]
        result["D3_norm_gap"] = d3["normalized_spectral_gap"]
        result["D3_fiedler_bim"] = d3["fiedler_bimodality"]
        result["D3_entropy"] = d3["spectral_entropy"]
    except Exception:
        pass

    try:
        d4 = topological_descriptors(g)
        result["D4_h1_bars"] = d4["h1_n_bars"]
        result["D4_h1_persist"] = d4["h1_total_persistence"]
        result["D4_h1_entropy"] = d4["h1_persistence_entropy"]
        result["D4_h1_bars_norm"] = d4["h1_n_bars"] / n if n > 0 else 0
    except Exception:
        pass

    try:
        cr = cycle_rank_descriptors(g)
        result["D4_cycle_rank"] = cr["cycle_rank"]
        result["D4_cycle_rank_norm"] = cr["cycle_rank_norm"]
    except Exception:
        pass

    return result


def main():
    data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
    nodes_path = os.path.join(data_dir, "dbt_nodes.csv")
    edges_path = os.path.join(data_dir, "dbt_edges.csv")

    if not os.path.exists(nodes_path):
        print(f"dbt_nodes.csv not found at {nodes_path}")
        sys.exit(1)

    print("=" * 70)
    print("EXPERIMENT 2b-NULL: DEGREE-PRESERVING REWIRING NULL MODEL")
    print("=" * 70)

    g = load_graph(nodes_path, edges_path)
    print(f"Real graph: N={g.number_of_nodes()}, M={g.number_of_edges()}")

    print("\nComputing descriptors on real graph...")
    real_desc = compute_descriptors_safe(g)
    print(f"  Done. Keys: {sorted(real_desc.keys())}")

    n_rewires = 100
    print(f"\nRunning {n_rewires} degree-preserving rewirings...")
    null_rows = []
    for i in range(n_rewires):
        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{n_rewires}]", flush=True)
        g_rw = degree_preserving_rewire(g, seed=i)
        desc = compute_descriptors_safe(g_rw)
        desc["rewire_id"] = i
        null_rows.append(desc)

    null_df = pd.DataFrame(null_rows)

    desc_cols = [c for c in null_df.columns
                 if c.startswith("D") and c[1].isdigit()
                 and null_df[c].notna().sum() >= 10]

    print("\n" + "=" * 70)
    print("Z-SCORES: REAL vs NULL DISTRIBUTION")
    print("=" * 70)
    print(f"\n  {'Descriptor':25s} {'Real':>10s} {'Null mean':>10s} {'Null std':>10s} {'z-score':>10s} {'Sig':>5s}")
    print("  " + "-" * 75)

    z_results = {}
    for col in sorted(desc_cols):
        if col not in real_desc:
            continue
        null_vals = null_df[col].dropna().values
        null_mean = np.mean(null_vals)
        null_std = np.std(null_vals)
        real_val = real_desc[col]
        if null_std > 0:
            z = (real_val - null_mean) / null_std
        else:
            z = 0.0 if real_val == null_mean else np.inf * np.sign(real_val - null_mean)
        sig = "***" if abs(z) > 3 else "**" if abs(z) > 2 else "*" if abs(z) > 1.5 else "ns"
        print(f"  {col:25s} {real_val:10.4f} {null_mean:10.4f} {null_std:10.4f} {z:+10.3f} {sig:>5s}")
        z_results[col] = {
            "real": float(real_val),
            "null_mean": float(null_mean),
            "null_std": float(null_std),
            "z_score": float(z),
        }

    # Cycle rank is exactly preserved by degree-preserving rewiring (M - N + C stays same if connectivity preserved)
    print("\n  Note: cycle_rank = M - N + C. Under degree-preserving rewiring,")
    print("  M and N are fixed, so cycle_rank varies only through changes in C")
    print("  (number of connected components). This makes it a weak test for")
    print("  cycle_rank specifically; the value lies in comparing it to H1 features.")

    # DAG property
    n_still_dag = sum(1 for _, row in null_df.iterrows()
                      if nx.is_directed_acyclic_graph(
                          nx.DiGraph([(u, v) for u, v in g.edges()])))
    print(f"\n  Real graph is DAG: {nx.is_directed_acyclic_graph(g)}")
    print(f"  Rewired graphs still DAG: (rewiring does not preserve acyclicity)")

    out_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'artifacts', 'phase_3')
    os.makedirs(out_dir, exist_ok=True)
    null_df.to_csv(os.path.join(out_dir, "exp_2b_null_distributions.csv"), index=False)

    summary = {
        "experiment": "2b_null_models",
        "method": "degree-preserving directed edge rewiring",
        "n_rewires": n_rewires,
        "swaps_per_rewire": "10 * M",
        "z_scores": z_results,
    }
    with open(os.path.join(out_dir, "exp_2b_null_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nResults saved to {out_dir}/")
    print("\n" + "=" * 70)
    print("NULL MODEL EXPERIMENT COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
