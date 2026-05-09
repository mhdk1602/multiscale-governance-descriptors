"""Experiment: D1 community stability seed robustness audit.

Louvain is a stochastic heuristic. A single-seed CSI value may conflate
true multiresolution stability with optimizer randomness. This experiment
runs the D1 resolution sweep with 25 random seeds and reports:

  - CSI mean, std, min, max per graph
  - Seed-NVI at gamma≈1: mean NVI between all pairs of seed partitions at
    a fixed resolution, isolating optimizer variance from resolution variance

Graphs tested:
  - Production dbt manifest (N=185 in LWCC)
  - Synthetic well-governed and poorly-governed graphs (large scale, N~130)
  - Selected DLG-DG-23 lineage graphs (N < 500)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import json
import numpy as np
import pandas as pd
import networkx as nx
from governance_descriptors.community_stability import community_stability_index_multiseed

N_SEEDS = 25


def dbt_graph():
    data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
    nodes_df = pd.read_csv(os.path.join(data_dir, 'dbt_nodes.csv'))
    edges_df = pd.read_csv(os.path.join(data_dir, 'dbt_edges.csv'))
    g = nx.DiGraph()
    for _, row in nodes_df.iterrows():
        g.add_node(row['node_id'])
    for _, row in edges_df.iterrows():
        if row['source_node_id'] in g and row['target_node_id'] in g:
            g.add_edge(row['source_node_id'], row['target_node_id'])
    return g


def synthetic_graph(n_nodes: int, governance: str, seed: int = 0):
    """Generate a synthetic lineage DAG.

    governance='well': clear layered DAGs, low cross-domain edges
    governance='poor': many cross-domain edges, star hubs, cycles
    """
    rng = np.random.default_rng(seed)
    g = nx.DiGraph()
    nodes = list(range(n_nodes))
    g.add_nodes_from(nodes)

    n_layers = 3
    layer_size = n_nodes // n_layers
    layers = [list(range(i * layer_size, min((i + 1) * layer_size, n_nodes)))
              for i in range(n_layers)]

    if governance == 'well':
        # Chain within layer, clean inter-layer connections
        for layer in layers:
            for i in range(len(layer) - 1):
                g.add_edge(layer[i], layer[i + 1])
        for i in range(len(layers) - 1):
            n_cross = max(1, len(layers[i]) // 5)
            srcs = rng.choice(layers[i], n_cross, replace=False)
            tgts = rng.choice(layers[i + 1], n_cross, replace=False)
            for s, t in zip(srcs, tgts):
                g.add_edge(s, t)
    else:
        # Poor: random edges, hub nodes, many cross-layer connections
        for _ in range(int(n_nodes * 1.5)):
            u, v = rng.integers(0, n_nodes, size=2)
            if u != v and u < v:
                g.add_edge(u, v)
        # Hub: connect 10% of nodes to a single central node
        hub = n_nodes // 2
        for node in rng.choice(nodes, n_nodes // 10, replace=False):
            if node < hub:
                g.add_edge(node, hub)
            elif node > hub:
                g.add_edge(hub, node)

    return g


def dlg_graphs(max_n: int = 400):
    """Load table-level DLG-DG-23 graphs below max_n nodes."""
    from experiments.phase_3.exp_3_external_validation import load_dlg_graph
    ext_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'external', 'dlg-dg-23')
    graphs = []
    for i in range(1, 19):
        npath = os.path.join(ext_dir, 'Node', f'DLG{i}-node.json')
        epath = os.path.join(ext_dir, 'Edge', f'DLG{i}-edge.json')
        if not (os.path.exists(npath) and os.path.exists(epath)):
            continue
        g = load_dlg_graph(npath, epath, table_level=True)
        if 5 <= g.number_of_nodes() <= max_n:
            graphs.append((f'DLG{i}', g))
    return graphs


def run_seed_audit(label, g):
    n = g.number_of_nodes()
    print(f"  {label} (N={n})...", flush=True)
    result = community_stability_index_multiseed(g, n_seeds=N_SEEDS)
    print(f"    CSI: {result['csi_mean']:.4f} ± {result['csi_std']:.4f} "
          f"[{result['csi_min']:.4f}, {result['csi_max']:.4f}]  "
          f"seed-NVI: {result['seed_nvi_mean']:.4f} ± {result['seed_nvi_std']:.4f}")
    return {"label": label, "N": n, **result}


def main():
    print("=" * 70)
    print(f"D1 SEED ROBUSTNESS AUDIT ({N_SEEDS} seeds per graph)")
    print("=" * 70)

    rows = []

    # --- dbt manifest ---
    print("\n--- Production dbt Manifest ---")
    g_dbt = dbt_graph()
    rows.append(run_seed_audit("dbt_manifest_full", g_dbt))

    # --- Synthetic graphs at two governance levels ---
    print("\n--- Synthetic Graphs (N=130, well vs. poor) ---")
    for gov in ['well', 'poor']:
        g_syn = synthetic_graph(n_nodes=130, governance=gov, seed=99)
        rows.append(run_seed_audit(f"synthetic_{gov}_N130", g_syn))

    # --- DLG-DG-23 (N <= 400) ---
    print("\n--- DLG-DG-23 Lineage Graphs (N ≤ 400) ---")
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    for label, g in dlg_graphs(max_n=400):
        rows.append(run_seed_audit(label, g))

    # --- Summary ---
    df = pd.DataFrame(rows)

    print("\n" + "=" * 70)
    print("SUMMARY: CSI SEED ROBUSTNESS")
    print("=" * 70)
    print(f"\n  {'Label':35s} {'N':>5s} {'CSI_mean':>9s} {'CSI_std':>8s} "
          f"{'[min,max]':>14s} {'seedNVI':>8s}")
    print("  " + "-" * 90)
    for _, r in df.iterrows():
        rng_str = f"[{r['csi_min']:.3f},{r['csi_max']:.3f}]"
        print(f"  {r['label']:35s} {r['N']:5d} {r['csi_mean']:9.4f} {r['csi_std']:8.4f} "
              f"{rng_str:>14s} {r['seed_nvi_mean']:8.4f}")

    print("\nInterpretation:")
    print("  CSI_std < 0.05 and seed-NVI < 0.05 → CSI is stable (not Louvain noise)")
    print("  CSI_std > 0.10 or seed-NVI > 0.10 → D1 result is optimizer-sensitive")

    # Save
    out_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'artifacts', 'phase_3')
    os.makedirs(out_dir, exist_ok=True)
    df.to_csv(os.path.join(out_dir, 'exp_d1_seed_robustness.csv'), index=False)

    summary = {
        "experiment": "d1_seed_robustness",
        "n_seeds": N_SEEDS,
        "graphs_tested": len(df),
        "max_csi_std": float(df['csi_std'].max()),
        "max_seed_nvi": float(df['seed_nvi_mean'].max()),
        "conclusion": (
            "stable" if df['csi_std'].max() < 0.05 and df['seed_nvi_mean'].max() < 0.05
            else "seed-sensitive"
        ),
    }
    with open(os.path.join(out_dir, 'exp_d1_seed_robustness_summary.json'), 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nSaved to {out_dir}/")
    print("=" * 70)
    print("D1 SEED ROBUSTNESS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
