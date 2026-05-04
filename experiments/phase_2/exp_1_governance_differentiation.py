"""Experiment 1: Synthetic lineage DAGs at varying governance quality.

Design:
  - Scales: tiny (~18-30), small (~28-43), medium (~65-76), large (~114-128)
  - Governance levels: well, baseline, poor
  - 10 random seeds per condition
  - Descriptors: D1 (community stability), D2 (blast-radius), D3 (spectral), D4 (TDA)
  - Baselines: degree stats, betweenness, PageRank, diameter, density
  - Outcome: MTTD with stewardship-based monitor placement

Hypothesis:
  Well-governed variants have higher CSI, later fragmentation onset,
  fewer H1 cycles per node, and lower MTTD.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import numpy as np
import pandas as pd
import networkx as nx
from governance_descriptors.community_stability import community_descriptor_summary
from governance_descriptors.blast_radius import concentration_profile
from governance_descriptors.spectral import spectral_descriptors
from governance_descriptors.persistent_homology import topological_descriptors
from governance_descriptors.generators import scaled_lineage
from governance_descriptors.mttd import (
    place_monitors_stewardship,
    place_monitors_betweenness,
    place_monitors_random,
    mttd_distribution,
)


def single_scale_baselines(g) -> dict:
    """Compute single-scale baseline features for comparison."""
    ug = g.to_undirected() if isinstance(g, nx.DiGraph) else g

    degrees = [d for _, d in g.degree()]
    in_degrees = [d for _, d in g.in_degree()] if isinstance(g, nx.DiGraph) else degrees
    out_degrees = [d for _, d in g.out_degree()] if isinstance(g, nx.DiGraph) else degrees

    bc = nx.betweenness_centrality(g)
    pr = nx.pagerank(g) if isinstance(g, nx.DiGraph) else nx.pagerank(ug)

    if not nx.is_connected(ug):
        giant = max(nx.connected_components(ug), key=len)
        ug_conn = ug.subgraph(giant).copy()
    else:
        ug_conn = ug
    diam = nx.diameter(ug_conn)

    return {
        "mean_degree": np.mean(degrees),
        "std_degree": np.std(degrees),
        "max_in_degree": max(in_degrees),
        "max_out_degree": max(out_degrees),
        "mean_betweenness": np.mean(list(bc.values())),
        "max_betweenness": max(bc.values()),
        "max_pagerank": max(pr.values()),
        "diameter": diam,
        "density": nx.density(g),
    }


def run_experiment(scales=None, seeds=None):
    """Run full Experiment 1."""
    if scales is None:
        scales = ["tiny", "small", "medium", "large"]
    if seeds is None:
        seeds = list(range(42, 52))

    gov_levels = ["well", "baseline", "poor"]
    rows = []

    total = len(scales) * len(gov_levels) * len(seeds)
    count = 0

    for scale in scales:
        for gov in gov_levels:
            for seed in seeds:
                count += 1
                g = scaled_lineage(scale=scale, governance=gov, seed=seed)
                n = g.number_of_nodes()
                m = g.number_of_edges()

                print(f"  [{count}/{total}] {scale}/{gov}/seed={seed} (N={n}, M={m})",
                      flush=True)

                # D1
                d1 = community_descriptor_summary(g)

                # D2
                d2 = concentration_profile(g)

                # D3
                d3 = spectral_descriptors(g)

                # D4
                d4 = topological_descriptors(g)

                # Baselines
                bl = single_scale_baselines(g)

                # MTTD with stewardship-based monitors
                n_monitors = max(2, n // 10)
                monitors_stew = place_monitors_stewardship(g, fraction=0.3, seed=seed)
                monitors_bc = place_monitors_betweenness(g, k=n_monitors)
                monitors_rand = place_monitors_random(g, k=n_monitors, seed=seed)

                mttd_stew = mttd_distribution(g, monitors_stew)
                mttd_bc = mttd_distribution(g, monitors_bc)
                mttd_rand = mttd_distribution(g, monitors_rand)

                row = {
                    "scale": scale,
                    "governance": gov,
                    "seed": seed,
                    "N": n,
                    "M": m,
                    # D1
                    "D1_csi": d1["csi"],
                    "D1_frag_onset": d1["fragmentation_onset"],
                    "D1_stab_var": d1["stability_variance"],
                    "D1_n_comm_g1": d1["n_communities_at_gamma_1"],
                    "D1_mod_g1": d1["modularity_at_gamma_1"],
                    # D2
                    "D2_max_gini": d2["max_gini"],
                    "D2_transition": d2["concentration_transition_depth"],
                    # D3
                    "D3_alg_conn": d3["algebraic_connectivity"],
                    "D3_norm_gap": d3["normalized_spectral_gap"],
                    "D3_fiedler_bim": d3["fiedler_bimodality"],
                    "D3_entropy": d3["spectral_entropy"],
                    # D4
                    "D4_h1_bars": d4["h1_n_bars"],
                    "D4_h1_persist": d4["h1_total_persistence"],
                    "D4_h1_entropy": d4["h1_persistence_entropy"],
                    "D4_h1_bars_norm": d4["h1_n_bars"] / n if n > 0 else 0,
                    # Baselines
                    **{f"BL_{k}": v for k, v in bl.items()},
                    # MTTD
                    "MTTD_stew_mean": mttd_stew["mean_mttd"],
                    "MTTD_stew_max": mttd_stew["max_mttd"],
                    "MTTD_bc_mean": mttd_bc["mean_mttd"],
                    "MTTD_rand_mean": mttd_rand["mean_mttd"],
                    "MTTD_stew_undetected": mttd_stew["n_undetected"],
                }
                rows.append(row)

    return pd.DataFrame(rows)


def summarize(df):
    """Print summary statistics grouped by scale and governance."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 1 SUMMARY")
    print("=" * 70)

    key_cols = [
        "D1_csi", "D1_frag_onset", "D2_max_gini", "D3_norm_gap",
        "D3_fiedler_bim", "D4_h1_bars_norm", "MTTD_stew_mean",
        "BL_mean_degree", "BL_max_betweenness", "BL_diameter",
    ]

    for scale in df["scale"].unique():
        print(f"\n--- Scale: {scale} ---")
        sub = df[df["scale"] == scale]
        summary = sub.groupby("governance")[key_cols].agg(["mean", "std"])
        print(summary.to_string())

    # Effect sizes (Cohen's d) for well vs poor at each scale
    print("\n" + "=" * 70)
    print("EFFECT SIZES (Cohen's d): well vs poor")
    print("=" * 70)

    for scale in df["scale"].unique():
        sub = df[df["scale"] == scale]
        well = sub[sub["governance"] == "well"]
        poor = sub[sub["governance"] == "poor"]

        print(f"\n  Scale: {scale}")
        for col in key_cols:
            w_mean, w_std = well[col].mean(), well[col].std()
            p_mean, p_std = poor[col].mean(), poor[col].std()
            pooled_std = np.sqrt((w_std**2 + p_std**2) / 2)
            if pooled_std > 0:
                d = (w_mean - p_mean) / pooled_std
            else:
                d = 0.0
            sig = "***" if abs(d) > 0.8 else "**" if abs(d) > 0.5 else "*" if abs(d) > 0.2 else ""
            print(f"    {col:25s}: d={d:+.3f} {sig}")


def main():
    print("Experiment 1: Governance Differentiation via Multi-Scale Descriptors")
    print("=" * 70)

    df = run_experiment()

    out_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'artifacts', 'phase_2')
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "exp_1_governance_differentiation.csv")
    df.to_csv(csv_path, index=False)
    print(f"\nResults saved to {csv_path}")

    summarize(df)


if __name__ == "__main__":
    main()
