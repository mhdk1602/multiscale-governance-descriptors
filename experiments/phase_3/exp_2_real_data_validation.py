"""Experiment 2: Structural differentiation on lineage graph data.

Loads nodes.csv and edges.csv (anonymized lineage topology), partitions
by domain, computes all D1-D4 descriptors per domain subgraph and on
the full graph, and tests whether descriptors correlate with observable
governance quality indicators (stewardship rate, test coverage, doc coverage).

Works with both synthetic and real data in the same CSV format.
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
    """Load graph from CSV files."""
    nodes_df = pd.read_csv(nodes_path)
    edges_df = pd.read_csv(edges_path)

    g = nx.DiGraph()
    for _, row in nodes_df.iterrows():
        attrs = {
            "layer": row.get("layer", "unknown"),
            "domain": row.get("domain", row.get("domain_or_team_owner", "unknown")),
            "has_steward": str(row.get("has_steward", "False")).lower() == "true",
            "has_tests": str(row.get("has_tests", "False")).lower() == "true",
            "test_count": int(row.get("test_count", 0)),
            "has_documentation": str(row.get("has_documentation", "False")).lower() == "true",
        }
        g.add_node(row["node_id"], **attrs)

    for _, row in edges_df.iterrows():
        src = row["source_node_id"]
        tgt = row["target_node_id"]
        if src in g and tgt in g:
            g.add_edge(src, tgt)

    return g


def domain_subgraph(g, domain):
    """Extract the subgraph for a single domain, including cross-domain edges."""
    domain_nodes = [n for n, d in g.nodes(data=True) if d.get("domain") == domain]
    return g.subgraph(domain_nodes).copy()


def governance_quality_metrics(g):
    """Compute governance quality indicators from node metadata."""
    nodes = list(g.nodes(data=True))
    n = len(nodes)
    if n == 0:
        return {}

    steward_rate = sum(1 for _, d in nodes if d.get("has_steward")) / n
    test_rate = sum(1 for _, d in nodes if d.get("has_tests")) / n
    doc_rate = sum(1 for _, d in nodes if d.get("has_documentation")) / n
    mean_test_count = np.mean([d.get("test_count", 0) for _, d in nodes])

    return {
        "steward_rate": steward_rate,
        "test_rate": test_rate,
        "doc_rate": doc_rate,
        "mean_test_count": mean_test_count,
        "governance_score": (steward_rate + test_rate + doc_rate) / 3,
    }


def compute_descriptors(g):
    """Compute all D1-D4 descriptors for a graph."""
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
            "D1_stab_var": d1["stability_variance"],
            "D1_n_comm_g1": d1["n_communities_at_gamma_1"],
            "D1_mod_g1": d1["modularity_at_gamma_1"],
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


def run_experiment(nodes_path, edges_path, summary_path=None):
    """Run Experiment 2."""
    print("Experiment 2: Structural Differentiation on Lineage Data")
    print("=" * 70)

    g = load_graph(nodes_path, edges_path)
    print(f"Full graph: N={g.number_of_nodes()}, M={g.number_of_edges()}")
    print(f"DAG: {nx.is_directed_acyclic_graph(g)}")

    domains = sorted(set(d.get("domain", "unknown") for _, d in g.nodes(data=True)))
    print(f"Domains: {domains}")

    if summary_path and os.path.exists(summary_path):
        with open(summary_path) as f:
            summary = json.load(f)
        print(f"Ground truth maturity labels available: {bool(summary.get('domains'))}")
    else:
        summary = None

    # Full graph descriptors
    print(f"\n--- Full Graph ---")
    full_desc = compute_descriptors(g)
    full_gov = governance_quality_metrics(g)
    for k, v in {**full_desc, **full_gov}.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    # Per-domain analysis
    rows = []
    print(f"\n--- Per-Domain Analysis ---")
    for domain in domains:
        sub = domain_subgraph(g, domain)
        desc = compute_descriptors(sub)
        gov = governance_quality_metrics(sub)

        maturity = "unknown"
        if summary and "domains" in summary:
            dm = summary["domains"].get(domain, {})
            maturity = dm.get("maturity", "unknown")

        row = {
            "domain": domain,
            "maturity": maturity,
            **desc,
            **gov,
        }
        rows.append(row)

        print(f"\n  {domain} (maturity={maturity}, N={desc['N']}, M={desc['M']}):")
        print(f"    Governance: steward={gov.get('steward_rate', 0):.2f}, "
              f"tests={gov.get('test_rate', 0):.2f}, "
              f"docs={gov.get('doc_rate', 0):.2f}, "
              f"score={gov.get('governance_score', 0):.3f}")
        if not desc.get("too_small"):
            print(f"    D1 CSI={desc.get('D1_csi', 'N/A')}, "
                  f"D2 maxGini={desc.get('D2_max_gini', 'N/A')}")
            print(f"    D3 gap={desc.get('D3_norm_gap', 'N/A')}, "
                  f"entropy={desc.get('D3_entropy', 'N/A')}")
            print(f"    D4 H1/N={desc.get('D4_h1_bars_norm', 'N/A')}")

    df = pd.DataFrame(rows)

    # Correlation analysis
    print("\n" + "=" * 70)
    print("CORRELATION: Descriptors vs Governance Quality Score")
    print("=" * 70)

    valid = df[~df.get("too_small", False)].copy()
    if len(valid) >= 4:
        desc_cols = [c for c in valid.columns
                     if c.startswith("D") and c[1].isdigit() and "error" not in c]
        gov_col = "governance_score"

        for col in desc_cols:
            if col in valid.columns and valid[col].notna().sum() >= 4:
                r, p = stats.spearmanr(valid[col].values, valid[gov_col].values)
                sig = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else "ns"
                print(f"  {col:25s}: rho={r:+.3f}, p={p:.4f} {sig}")
    else:
        print("  Too few domains for correlation analysis (need >= 4)")

    # Maturity-stratified comparison
    if "maturity" in df.columns and df["maturity"].nunique() > 1:
        print("\n" + "=" * 70)
        print("MATURITY-STRATIFIED COMPARISON")
        print("=" * 70)

        for mat in ["high", "medium", "low"]:
            sub = valid[valid["maturity"] == mat]
            if len(sub) > 0:
                print(f"\n  {mat} (n={len(sub)}):")
                for col in ["governance_score", "D1_csi", "D2_max_gini",
                            "D3_norm_gap", "D3_entropy", "D4_h1_bars_norm"]:
                    if col in sub.columns and sub[col].notna().any():
                        vals = sub[col].dropna()
                        print(f"    {col:25s}: mean={vals.mean():.4f}")

    return df


def main():
    data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
    if not os.path.exists(data_dir):
        data_dir = "/Users/haridines/github/personal/non-git-files/files"

    nodes_path = os.path.join(data_dir, "nodes.csv")
    edges_path = os.path.join(data_dir, "edges.csv")
    summary_path = os.path.join(data_dir, "graph_summary.json")

    if not os.path.exists(nodes_path):
        print(f"nodes.csv not found at {nodes_path}")
        print("Provide path as argument or place files in data/ directory")
        sys.exit(1)

    df = run_experiment(nodes_path, edges_path, summary_path)

    out_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'artifacts', 'phase_3')
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "exp_2_domain_descriptors.csv")
    df.to_csv(csv_path, index=False)
    print(f"\nResults saved to {csv_path}")


if __name__ == "__main__":
    main()
