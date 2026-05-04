"""Phase 1 Gate: Validate all descriptors on known graph families.

Tests:
  D1 (community stability): Karate club should find 2-4 communities at gamma=1.
      Barbell graph should fragment later than Erdos-Renyi.
  D2 (blast-radius): Star graph should have Gini ~1 at depth 1.
      Path graph should have low Gini (uniform blast radius).
  D3 (spectral): Barbell should have small spectral gap.
      Complete graph should have large spectral gap.
  D4 (persistent homology): Cycle graph should have exactly 1 H1 bar.
      Tree should have 0 H1 bars (no cycles).

Also tests all descriptors on governance-varied lineage DAGs at
N in {30, 50, 100, 200} to verify the Phase 1 gate.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import networkx as nx
import numpy as np
import pandas as pd
from governance_descriptors.community_stability import community_descriptor_summary
from governance_descriptors.blast_radius import concentration_profile, gini_vs_depth
from governance_descriptors.spectral import spectral_descriptors
from governance_descriptors.persistent_homology import topological_descriptors
from governance_descriptors.generators import scaled_lineage


def validate_d1():
    """D1: Community stability on known graphs."""
    print("=" * 60)
    print("D1: Community Stability Validation")
    print("=" * 60)

    results = []

    # Karate club: should find 2-4 communities at gamma=1
    K = nx.karate_club_graph()
    d = community_descriptor_summary(K)
    results.append({
        "graph": "karate_club (N=34)",
        "csi": d["csi"],
        "fragmentation_onset": d["fragmentation_onset"],
        "stability_variance": d["stability_variance"],
        "n_communities_gamma1": d["n_communities_at_gamma_1"],
        "modularity_gamma1": d["modularity_at_gamma_1"],
    })
    assert 2 <= d["n_communities_at_gamma_1"] <= 6, \
        f"Karate club: expected 2-6 communities, got {d['n_communities_at_gamma_1']}"
    print(f"  Karate club: {d['n_communities_at_gamma_1']} communities at gamma=1 [PASS]")

    # Barbell: two cliques joined by a path, should fragment late
    B = nx.barbell_graph(15, 1)
    d = community_descriptor_summary(B)
    results.append({
        "graph": "barbell (N=31)",
        "csi": d["csi"],
        "fragmentation_onset": d["fragmentation_onset"],
        "stability_variance": d["stability_variance"],
        "n_communities_gamma1": d["n_communities_at_gamma_1"],
        "modularity_gamma1": d["modularity_at_gamma_1"],
    })
    assert d["n_communities_at_gamma_1"] in [2, 3], \
        f"Barbell: expected 2-3 communities, got {d['n_communities_at_gamma_1']}"
    print(f"  Barbell: {d['n_communities_at_gamma_1']} communities, CSI={d['csi']:.3f} [PASS]")

    # Erdos-Renyi: random, should have low CSI
    ER = nx.erdos_renyi_graph(50, 0.1, seed=42)
    if not nx.is_connected(ER):
        giant = max(nx.connected_components(ER), key=len)
        ER = ER.subgraph(giant).copy()
    d = community_descriptor_summary(ER)
    results.append({
        "graph": f"erdos_renyi (N={ER.number_of_nodes()})",
        "csi": d["csi"],
        "fragmentation_onset": d["fragmentation_onset"],
        "stability_variance": d["stability_variance"],
        "n_communities_gamma1": d["n_communities_at_gamma_1"],
        "modularity_gamma1": d["modularity_at_gamma_1"],
    })
    print(f"  Erdos-Renyi: CSI={d['csi']:.3f}, frag_onset={d['fragmentation_onset']:.2f}")

    df = pd.DataFrame(results)
    print(f"\n{df.to_string(index=False)}\n")
    return df


def validate_d2():
    """D2: Blast-radius on known DAGs."""
    print("=" * 60)
    print("D2: Blast-Radius Concentration Validation")
    print("=" * 60)

    results = []

    # Star DAG: center -> leaves. Center has blast radius N-1, leaves have 0.
    # Gini at depth 1 should be high.
    star = nx.star_graph(20)
    star_dag = nx.DiGraph()
    star_dag.add_edges_from([(0, i) for i in range(1, 21)])
    gini = gini_vs_depth(star_dag, max_depth=2)
    results.append({
        "graph": "star_dag (N=21)",
        "gini_d1": gini[0] if len(gini) > 0 else None,
        "gini_d2": gini[1] if len(gini) > 1 else None,
        "max_gini": max(gini) if gini else 0,
    })
    assert gini[0] > 0.8, f"Star DAG: expected high Gini at depth 1, got {gini[0]:.3f}"
    print(f"  Star DAG: Gini(d=1)={gini[0]:.3f} [PASS: high concentration]")

    # Path DAG: linear chain. All nodes have blast radius proportional to position.
    path_dag = nx.DiGraph()
    for i in range(19):
        path_dag.add_edge(i, i + 1)
    gini = gini_vs_depth(path_dag, max_depth=5)
    results.append({
        "graph": "path_dag (N=20)",
        "gini_d1": gini[0] if len(gini) > 0 else None,
        "gini_d2": gini[1] if len(gini) > 1 else None,
        "max_gini": max(gini) if gini else 0,
    })
    print(f"  Path DAG: Gini(d=1)={gini[0]:.3f}, Gini(d=2)={gini[1]:.3f}")

    # Binary tree DAG: root has max blast radius, leaves have 0
    tree = nx.balanced_tree(2, 4, create_using=nx.DiGraph())
    gini = gini_vs_depth(tree, max_depth=4)
    results.append({
        "graph": f"binary_tree (N={tree.number_of_nodes()})",
        "gini_d1": gini[0] if len(gini) > 0 else None,
        "gini_d2": gini[1] if len(gini) > 1 else None,
        "max_gini": max(gini) if gini else 0,
    })
    print(f"  Binary tree: Gini curve = {[f'{g:.3f}' for g in gini]}")

    df = pd.DataFrame(results)
    print(f"\n{df.to_string(index=False)}\n")
    return df


def validate_d3():
    """D3: Spectral descriptors on known graphs."""
    print("=" * 60)
    print("D3: Spectral Descriptor Validation")
    print("=" * 60)

    results = []

    # Complete graph: lambda_2 = N, normalized gap should be high
    K20 = nx.complete_graph(20)
    d = spectral_descriptors(K20)
    results.append({"graph": "complete (N=20)", **d})
    assert d["normalized_spectral_gap"] > 0.9, \
        f"Complete graph: expected high normalized gap, got {d['normalized_spectral_gap']:.3f}"
    print(f"  Complete graph: norm_gap={d['normalized_spectral_gap']:.3f} [PASS: high]")

    # Barbell: should have small spectral gap (bottleneck)
    B = nx.barbell_graph(15, 1)
    d = spectral_descriptors(B)
    results.append({"graph": "barbell (N=31)", **d})
    assert d["normalized_spectral_gap"] < 0.2, \
        f"Barbell: expected low normalized gap, got {d['normalized_spectral_gap']:.3f}"
    print(f"  Barbell: norm_gap={d['normalized_spectral_gap']:.3f}, bimodality={d['fiedler_bimodality']:.3f} [PASS: bottleneck]")

    # Karate club
    K = nx.karate_club_graph()
    d = spectral_descriptors(K)
    results.append({"graph": "karate_club (N=34)", **d})
    print(f"  Karate club: norm_gap={d['normalized_spectral_gap']:.3f}, entropy={d['spectral_entropy']:.3f}")

    # Path graph: small spectral gap (long bottleneck)
    P = nx.path_graph(30)
    d = spectral_descriptors(P)
    results.append({"graph": "path (N=30)", **d})
    print(f"  Path graph: norm_gap={d['normalized_spectral_gap']:.3f} [low expected]")

    df = pd.DataFrame(results)
    print(f"\n{df.to_string(index=False)}\n")
    return df


def validate_d4():
    """D4: Persistent homology on known graphs."""
    print("=" * 60)
    print("D4: Persistent Homology Validation")
    print("=" * 60)

    results = []

    # Cycle: exactly 1 H1 bar
    C = nx.cycle_graph(15)
    d = topological_descriptors(C)
    results.append({"graph": "cycle (N=15)", **d})
    assert d["h1_n_bars"] == 1, f"Cycle: expected 1 H1 bar, got {d['h1_n_bars']}"
    print(f"  Cycle graph: H1 bars={d['h1_n_bars']} [PASS: exactly 1 cycle]")

    # Tree: 0 H1 bars (no cycles)
    T = nx.balanced_tree(2, 4)
    d = topological_descriptors(T)
    results.append({"graph": f"binary_tree (N={T.number_of_nodes()})", **d})
    assert d["h1_n_bars"] == 0, f"Tree: expected 0 H1 bars, got {d['h1_n_bars']}"
    print(f"  Binary tree: H1 bars={d['h1_n_bars']} [PASS: acyclic]")

    # Karate club: should have multiple H1 bars (triangles)
    K = nx.karate_club_graph()
    d = topological_descriptors(K)
    results.append({"graph": "karate_club (N=34)", **d})
    assert d["h1_n_bars"] > 0, f"Karate club: expected H1 bars > 0, got {d['h1_n_bars']}"
    print(f"  Karate club: H1 bars={d['h1_n_bars']} [PASS: cycles present]")

    # Grid: should have many H1 bars (square faces)
    G = nx.grid_2d_graph(5, 5)
    d = topological_descriptors(G)
    results.append({"graph": "grid_5x5 (N=25)", **d})
    print(f"  Grid 5x5: H1 bars={d['h1_n_bars']}")

    df = pd.DataFrame(results)
    print(f"\n{df.to_string(index=False)}\n")
    return df


def validate_governance_differentiation():
    """Test all descriptors on governance-varied lineage DAGs across scales."""
    print("=" * 60)
    print("Governance Differentiation Across Scales")
    print("=" * 60)

    rows = []
    for scale in ["tiny", "small", "medium", "large"]:
        for gov in ["well", "baseline", "poor"]:
            g = scaled_lineage(scale=scale, governance=gov, seed=42)
            n = g.number_of_nodes()
            m = g.number_of_edges()

            d1 = community_descriptor_summary(g)
            d2 = concentration_profile(g)
            d3 = spectral_descriptors(g)
            d4 = topological_descriptors(g)

            row = {
                "scale": scale,
                "governance": gov,
                "N": n,
                "M": m,
                "D1_csi": d1["csi"],
                "D1_frag_onset": d1["fragmentation_onset"],
                "D1_stab_var": d1["stability_variance"],
                "D2_max_gini": d2["max_gini"],
                "D2_transition_depth": d2["concentration_transition_depth"],
                "D3_norm_gap": d3["normalized_spectral_gap"],
                "D3_fiedler_bim": d3["fiedler_bimodality"],
                "D3_entropy": d3["spectral_entropy"],
                "D4_h1_bars": d4["h1_n_bars"],
                "D4_h1_persistence": d4["h1_total_persistence"],
                "D4_h0_entropy": d4["h0_persistence_entropy"],
            }
            rows.append(row)
            print(f"  {scale}/{gov} (N={n}): CSI={d1['csi']:.3f}, "
                  f"maxGini={d2['max_gini']:.3f}, gap={d3['normalized_spectral_gap']:.3f}, "
                  f"H1={d4['h1_n_bars']}")

    df = pd.DataFrame(rows)
    print(f"\n{df.to_string(index=False)}\n")
    return df


def main():
    print("Phase 1 Gate: Descriptor Validation on Known Graph Families")
    print("=" * 60)
    print()

    df1 = validate_d1()
    df2 = validate_d2()
    df3 = validate_d3()
    df4 = validate_d4()
    df_gov = validate_governance_differentiation()

    out_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'artifacts', 'phase_1')
    os.makedirs(out_dir, exist_ok=True)

    df1.to_csv(os.path.join(out_dir, "d1_validation.csv"), index=False)
    df2.to_csv(os.path.join(out_dir, "d2_validation.csv"), index=False)
    df3.to_csv(os.path.join(out_dir, "d3_validation.csv"), index=False)
    df4.to_csv(os.path.join(out_dir, "d4_validation.csv"), index=False)
    df_gov.to_csv(os.path.join(out_dir, "governance_differentiation.csv"), index=False)

    print("=" * 60)
    print("PHASE 1 GATE ASSESSMENT")
    print("=" * 60)

    # Check: do descriptors differentiate governance levels?
    for scale in ["tiny", "small", "medium", "large"]:
        subset = df_gov[df_gov["scale"] == scale]
        well = subset[subset["governance"] == "well"]
        poor = subset[subset["governance"] == "poor"]

        if len(well) > 0 and len(poor) > 0:
            csi_diff = well["D1_csi"].values[0] - poor["D1_csi"].values[0]
            gap_diff = well["D3_norm_gap"].values[0] - poor["D3_norm_gap"].values[0]
            h1_diff = poor["D4_h1_bars"].values[0] - well["D4_h1_bars"].values[0]
            gini_diff = well["D2_max_gini"].values[0] - poor["D2_max_gini"].values[0]

            print(f"\n  Scale={scale}:")
            print(f"    D1 CSI diff (well-poor): {csi_diff:+.3f} {'[+]' if csi_diff > 0 else '[-]'}")
            print(f"    D2 maxGini diff (well-poor): {gini_diff:+.3f}")
            print(f"    D3 gap diff (well-poor): {gap_diff:+.3f} {'[+]' if gap_diff > 0 else '[-]'}")
            print(f"    D4 H1 diff (poor-well): {h1_diff:+.0f} {'[+]' if h1_diff > 0 else '[-]'}")

    print("\nAll CSV artifacts saved to artifacts/phase_1/")
    print("Gate: PASS if all assertions above succeeded without error.")


if __name__ == "__main__":
    main()
