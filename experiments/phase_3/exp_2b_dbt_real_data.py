"""Experiment 2b: Real dbt manifest lineage — structural governance analysis.

Loads an anonymized lineage topology exported from a production dbt
manifest.json + catalog.json (223 nodes, 263 edges, 26 domains).
Computes D1-D4 descriptors on the full graph, the largest connected
component (185 nodes), and per-domain subgraphs.  Tests whether
multi-scale structural descriptors correlate with observed governance
metadata (test coverage, documentation coverage).

This is the primary real-data validation for the preprint.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import json
import numpy as np
import pandas as pd
import networkx as nx
from scipy import stats
from governance_descriptors.community_stability import community_descriptor_summary
from governance_descriptors.blast_radius import concentration_profile
from governance_descriptors.spectral import spectral_descriptors
from governance_descriptors.persistent_homology import topological_descriptors


def load_graph(nodes_path, edges_path):
    nodes_df = pd.read_csv(nodes_path)
    edges_df = pd.read_csv(edges_path)

    g = nx.DiGraph()
    for _, row in nodes_df.iterrows():
        domain_col = "domain_or_team_owner" if "domain_or_team_owner" in nodes_df.columns else "domain"
        attrs = {
            "layer": row.get("layer", "unknown"),
            "domain": row.get(domain_col, "unknown"),
            "has_steward": str(row.get("has_steward", "False")).lower() == "true",
            "has_tests": str(row.get("has_tests", "False")).lower() == "true",
            "test_count": int(row.get("test_count", 0)),
            "has_documentation": str(row.get("has_documentation", "False")).lower() == "true",
        }
        g.add_node(row["node_id"], **attrs)

    for _, row in edges_df.iterrows():
        src, tgt = row["source_node_id"], row["target_node_id"]
        if src in g and tgt in g:
            g.add_edge(src, tgt)

    return g


def largest_weakly_connected(g):
    components = sorted(nx.weakly_connected_components(g), key=len, reverse=True)
    return g.subgraph(components[0]).copy()


def governance_metrics(g):
    nodes = list(g.nodes(data=True))
    n = len(nodes)
    if n == 0:
        return {}
    steward = sum(1 for _, d in nodes if d.get("has_steward")) / n
    tested = sum(1 for _, d in nodes if d.get("has_tests")) / n
    documented = sum(1 for _, d in nodes if d.get("has_documentation")) / n
    mean_tc = np.mean([d.get("test_count", 0) for _, d in nodes])
    return {
        "steward_rate": steward,
        "test_rate": tested,
        "doc_rate": documented,
        "mean_test_count": mean_tc,
        "governance_score": (steward + tested + documented) / 3,
    }


def compute_descriptors(g, label=""):
    n = g.number_of_nodes()
    m = g.number_of_edges()
    if n < 5:
        return {"N": n, "M": m, "too_small": True}

    result = {"N": n, "M": m, "too_small": False}

    try:
        d1 = community_descriptor_summary(g)
        result.update({
            "D1_csi": d1["csi"],
            "D1_frag_onset": d1["fragmentation_onset"],
            "D1_n_comm": d1["n_communities_at_gamma_1"],
            "D1_modularity": d1["modularity_at_gamma_1"],
        })
    except Exception as e:
        result["D1_error"] = str(e)

    try:
        d2 = concentration_profile(g)
        result.update({
            "D2_max_gini": d2["max_gini"],
            "D2_transition": d2["concentration_transition_depth"],
        })
    except Exception as e:
        result["D2_error"] = str(e)

    try:
        d3 = spectral_descriptors(g)
        result.update({
            "D3_alg_conn": d3["algebraic_connectivity"],
            "D3_norm_gap": d3["normalized_spectral_gap"],
            "D3_fiedler_bim": d3["fiedler_bimodality"],
            "D3_entropy": d3["spectral_entropy"],
        })
    except Exception as e:
        result["D3_error"] = str(e)

    try:
        d4 = topological_descriptors(g)
        result.update({
            "D4_h1_bars": d4["h1_n_bars"],
            "D4_h1_persist": d4["h1_total_persistence"],
            "D4_h1_entropy": d4["h1_persistence_entropy"],
            "D4_h1_bars_norm": d4["h1_n_bars"] / n if n > 0 else 0,
        })
    except Exception as e:
        result["D4_error"] = str(e)

    return result


def layer_distribution(g):
    layers = [d.get("layer", "unknown") for _, d in g.nodes(data=True)]
    from collections import Counter
    return dict(Counter(layers))


def fmt(val, spec=".4f"):
    if isinstance(val, (int, float, np.integer, np.floating)):
        return f"{val:{spec}}"
    return str(val)


def print_descriptors(desc, gov, indent=2):
    pad = " " * indent
    if desc.get("too_small"):
        print(f"{pad}Too small for descriptor computation (N={desc['N']})")
        return
    if "D1_error" not in desc:
        print(f"{pad}D1: CSI={fmt(desc.get('D1_csi', 'ERR'))}, "
              f"communities={desc.get('D1_n_comm', 'ERR')}, "
              f"modularity={fmt(desc.get('D1_modularity', 'ERR'))}")
    else:
        print(f"{pad}D1: {desc['D1_error']}")
    if "D2_error" not in desc:
        print(f"{pad}D2: max_gini={fmt(desc.get('D2_max_gini', 'ERR'))}, "
              f"transition_depth={desc.get('D2_transition', 'ERR')}")
    else:
        print(f"{pad}D2: {desc['D2_error']}")
    if "D3_error" not in desc:
        print(f"{pad}D3: alg_conn={fmt(desc.get('D3_alg_conn', 'ERR'), '.6f')}, "
              f"norm_gap={fmt(desc.get('D3_norm_gap', 'ERR'))}, "
              f"entropy={fmt(desc.get('D3_entropy', 'ERR'))}")
    else:
        print(f"{pad}D3: {desc['D3_error']}")
    if "D4_error" not in desc:
        print(f"{pad}D4: H1_bars={desc.get('D4_h1_bars', 'ERR')}, "
              f"H1/N={fmt(desc.get('D4_h1_bars_norm', 'ERR'))}, "
              f"H1_entropy={fmt(desc.get('D4_h1_entropy', 'ERR'))}")
    else:
        print(f"{pad}D4: {desc['D4_error']}")
    print(f"{pad}Gov: steward={gov.get('steward_rate', 0):.2f}, "
          f"tested={gov.get('test_rate', 0):.2f}, "
          f"documented={gov.get('doc_rate', 0):.2f}, "
          f"score={gov.get('governance_score', 0):.3f}")


def main():
    data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
    nodes_path = os.path.join(data_dir, "dbt_nodes.csv")
    edges_path = os.path.join(data_dir, "dbt_edges.csv")

    if not os.path.exists(nodes_path):
        print(f"dbt_nodes.csv not found at {nodes_path}")
        sys.exit(1)

    print("=" * 70)
    print("EXPERIMENT 2b: REAL dbt MANIFEST LINEAGE VALIDATION")
    print("=" * 70)

    g = load_graph(nodes_path, edges_path)
    print(f"\nFull graph: N={g.number_of_nodes()}, M={g.number_of_edges()}")
    print(f"DAG: {nx.is_directed_acyclic_graph(g)}")
    print(f"Layers: {layer_distribution(g)}")
    print(f"Weakly connected components: {nx.number_weakly_connected_components(g)}")

    # --- Full graph descriptors ---
    print("\n--- Full Graph (all 223 nodes) ---")
    full_desc = compute_descriptors(g, "full")
    full_gov = governance_metrics(g)
    print_descriptors(full_desc, full_gov)

    # --- Largest component ---
    lcc = largest_weakly_connected(g)
    print(f"\n--- Largest Component (N={lcc.number_of_nodes()}, M={lcc.number_of_edges()}) ---")
    lcc_desc = compute_descriptors(lcc, "lcc")
    lcc_gov = governance_metrics(lcc)
    print_descriptors(lcc_desc, lcc_gov)

    # --- Per-domain analysis ---
    print("\n" + "=" * 70)
    print("PER-DOMAIN STRUCTURAL ANALYSIS")
    print("=" * 70)

    domains = sorted(set(d.get("domain") for _, d in g.nodes(data=True)))
    rows = []

    for domain in domains:
        dnodes = [n for n, d in g.nodes(data=True) if d.get("domain") == domain]
        sub = g.subgraph(dnodes).copy()
        desc = compute_descriptors(sub)
        gov = governance_metrics(sub)

        row = {"domain": domain, **desc, **gov}
        rows.append(row)

        if desc["N"] >= 5:
            print(f"\n  {domain} (N={desc['N']}, M={desc['M']}):")
            print_descriptors(desc, gov, indent=4)

    df = pd.DataFrame(rows)

    # --- Correlation analysis ---
    print("\n" + "=" * 70)
    print("CORRELATION: Descriptors vs Governance Metadata")
    print("=" * 70)

    valid = df[~df.get("too_small", pd.Series([False]*len(df)))].copy()
    n_valid = len(valid)
    print(f"Domains with N>=5 for analysis: {n_valid}")

    if n_valid >= 4:
        desc_cols = [c for c in valid.columns
                     if c.startswith("D") and c[1].isdigit()
                     and "error" not in c and valid[c].notna().sum() >= 4]

        for target in ["governance_score", "test_rate", "doc_rate"]:
            print(f"\n  vs {target}:")
            for col in desc_cols:
                vals = valid[[col, target]].dropna()
                if len(vals) >= 4:
                    r, p = stats.spearmanr(vals[col], vals[target])
                    sig = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else "ns"
                    print(f"    {col:25s}: rho={r:+.3f}, p={p:.4f} {sig}")

    # --- Governance gradient analysis ---
    print("\n" + "=" * 70)
    print("GOVERNANCE GRADIENT ANALYSIS")
    print("=" * 70)

    if n_valid >= 6:
        valid_sorted = valid.sort_values("governance_score")
        n_tercile = len(valid_sorted) // 3
        low = valid_sorted.head(n_tercile)
        high = valid_sorted.tail(n_tercile)

        print(f"\nLow governance tercile (n={len(low)}, "
              f"mean score={low['governance_score'].mean():.3f}):")
        print(f"High governance tercile (n={len(high)}, "
              f"mean score={high['governance_score'].mean():.3f}):")

        key_descs = ["D1_csi", "D2_max_gini", "D3_norm_gap", "D3_entropy",
                     "D4_h1_bars_norm", "D4_h1_entropy"]

        print(f"\n  {'Descriptor':25s} {'Low mean':>10s} {'High mean':>10s} "
              f"{'Diff':>8s} {'U-stat':>8s} {'p-value':>8s}")
        print("  " + "-" * 73)

        for col in key_descs:
            if col in low.columns and col in high.columns:
                lv = low[col].dropna()
                hv = high[col].dropna()
                if len(lv) >= 2 and len(hv) >= 2:
                    u_stat, p_val = stats.mannwhitneyu(
                        lv, hv, alternative='two-sided')
                    diff = hv.mean() - lv.mean()
                    print(f"  {col:25s} {lv.mean():10.4f} {hv.mean():10.4f} "
                          f"{diff:+8.4f} {u_stat:8.1f} {p_val:8.4f}")

    # --- Cross-topology comparison ---
    print("\n" + "=" * 70)
    print("CROSS-TOPOLOGY STRUCTURAL PROFILE COMPARISON")
    print("=" * 70)

    real_nodes_path = os.path.join(data_dir, "real_nodes.csv")
    real_edges_path = os.path.join(data_dir, "real_edges.csv")
    synth_nodes_path = os.path.join(data_dir, "nodes.csv")
    synth_edges_path = os.path.join(data_dir, "edges.csv")

    profiles = {"dbt_manifest_full": (full_desc, full_gov)}

    if os.path.exists(real_nodes_path):
        g_static = load_graph(real_nodes_path, real_edges_path)
        profiles["static_code_pipeline"] = (
            compute_descriptors(g_static), governance_metrics(g_static))

    if os.path.exists(synth_nodes_path):
        g_synth = load_graph(synth_nodes_path, synth_edges_path)
        profiles["synthetic_6domain"] = (
            compute_descriptors(g_synth), governance_metrics(g_synth))

    print(f"\n  {'Topology':25s} {'N':>5s} {'M':>5s} {'CSI':>7s} "
          f"{'maxGini':>8s} {'gap':>7s} {'entropy':>8s} "
          f"{'H1/N':>7s} {'govScore':>9s}")
    print("  " + "-" * 90)

    for name, (desc, gov) in profiles.items():
        if desc.get("too_small"):
            continue
        print(f"  {name:25s} {desc['N']:5d} {desc['M']:5d} "
              f"{desc.get('D1_csi', 0):7.3f} "
              f"{desc.get('D2_max_gini', 0):8.3f} "
              f"{desc.get('D3_norm_gap', 0):7.4f} "
              f"{desc.get('D3_entropy', 0):8.3f} "
              f"{desc.get('D4_h1_bars_norm', 0):7.3f} "
              f"{gov.get('governance_score', 0):9.3f}")

    # --- Layer-stratified governance ---
    print("\n" + "=" * 70)
    print("LAYER-STRATIFIED GOVERNANCE (dbt manifest)")
    print("=" * 70)

    for layer_name in ["source/raw", "silver/intermediate", "gold/mart"]:
        layer_nodes = [n for n, d in g.nodes(data=True) if d.get("layer") == layer_name]
        if not layer_nodes:
            continue
        sub = g.subgraph(layer_nodes).copy()
        gov = governance_metrics(sub)
        print(f"\n  {layer_name} (N={len(layer_nodes)}):")
        print(f"    steward={gov['steward_rate']:.2f}, "
              f"tested={gov['test_rate']:.2f}, "
              f"documented={gov['doc_rate']:.2f}")

    # --- Save results ---
    out_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'artifacts', 'phase_3')
    os.makedirs(out_dir, exist_ok=True)

    df.to_csv(os.path.join(out_dir, "exp_2b_dbt_domain_descriptors.csv"), index=False)

    summary = {
        "experiment": "2b_dbt_real_data",
        "source": "dbt manifest.json + catalog.json (anonymized export)",
        "full_graph": {**full_desc, **full_gov},
        "largest_component": {**lcc_desc, **lcc_gov},
        "n_domains": len(domains),
        "n_domains_analyzable": n_valid,
        "cross_topology": {name: {**d, **g_} for name, (d, g_) in profiles.items()},
    }

    for k, v in summary.items():
        if isinstance(v, dict):
            for kk, vv in v.items():
                if isinstance(vv, (np.integer, np.int64)):
                    summary[k][kk] = int(vv)
                elif isinstance(vv, (np.floating, np.float64)):
                    summary[k][kk] = float(vv)
                elif isinstance(vv, dict):
                    for kkk, vvv in vv.items():
                        if isinstance(vvv, (np.integer, np.int64)):
                            summary[k][kk][kkk] = int(vvv)
                        elif isinstance(vvv, (np.floating, np.float64)):
                            summary[k][kk][kkk] = float(vvv)

    with open(os.path.join(out_dir, "exp_2b_dbt_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\nResults saved to {out_dir}/")

    print("\n" + "=" * 70)
    print("EXPERIMENT 2b COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
