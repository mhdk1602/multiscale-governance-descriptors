"""Experiment 2b: Real dbt manifest lineage — structural governance analysis.

Loads an anonymized lineage topology exported from a production dbt
manifest.json + catalog.json (223 nodes, 263 edges, 26 domains).
Computes D1-D4 descriptors plus cycle-rank baseline on the full graph,
the largest connected component, and per-domain subgraphs.

Statistical methods: permutation-based Spearman (10k perms),
Benjamini-Hochberg FDR correction, partial correlations controlling
for domain size and layer composition.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import json
import numpy as np
import pandas as pd
import networkx as nx
from collections import Counter
from scipy import stats
from governance_descriptors.community_stability import community_descriptor_summary
from governance_descriptors.blast_radius import concentration_profile
from governance_descriptors.spectral import spectral_descriptors
from governance_descriptors.persistent_homology import topological_descriptors, cycle_rank_descriptors
from governance_descriptors.stats_utils import permutation_spearman, benjamini_hochberg, partial_spearman


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
    source_frac = sum(1 for _, d in nodes if "source" in d.get("layer", "")) / n
    return {
        "steward_rate": steward,
        "test_rate": tested,
        "doc_rate": documented,
        "mean_test_count": mean_tc,
        "governance_score": (steward + tested + documented) / 3,
        "source_fraction": source_frac,
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

    try:
        cr = cycle_rank_descriptors(g)
        result.update({
            "D4_cycle_rank": cr["cycle_rank"],
            "D4_cycle_rank_norm": cr["cycle_rank_norm"],
        })
    except Exception as e:
        result["CR_error"] = str(e)

    return result


def fmt(val, spec=".4f"):
    if isinstance(val, (int, float, np.integer, np.floating)):
        return f"{val:{spec}}"
    return str(val)


def print_desc(desc, gov, indent=2):
    pad = " " * indent
    if desc.get("too_small"):
        print(f"{pad}Too small (N={desc['N']})")
        return
    for prefix, keys in [
        ("D1", [("CSI", "D1_csi"), ("comm", "D1_n_comm"), ("mod", "D1_modularity")]),
        ("D2", [("maxGini", "D2_max_gini"), ("trans", "D2_transition")]),
        ("D3", [("algConn", "D3_alg_conn"), ("gap", "D3_norm_gap"), ("ent", "D3_entropy")]),
        ("D4", [("H1/N", "D4_h1_bars_norm"), ("H1ent", "D4_h1_entropy"), ("cycRk/N", "D4_cycle_rank_norm")]),
    ]:
        if f"{prefix}_error" in desc:
            print(f"{pad}{prefix}: {desc[f'{prefix}_error']}")
        else:
            parts = [f"{k}={fmt(desc.get(v, 'ERR'))}" for k, v in keys if v in desc]
            print(f"{pad}{prefix}: {', '.join(parts)}")
    print(f"{pad}Gov: steward={gov.get('steward_rate',0):.2f}, "
          f"tested={gov.get('test_rate',0):.2f}, "
          f"documented={gov.get('doc_rate',0):.2f}, "
          f"score={gov.get('governance_score',0):.3f}")


def main():
    data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
    nodes_path = os.path.join(data_dir, "dbt_nodes.csv")
    edges_path = os.path.join(data_dir, "dbt_edges.csv")

    if not os.path.exists(nodes_path):
        print(f"dbt_nodes.csv not found at {nodes_path}")
        sys.exit(1)

    print("=" * 70)
    print("EXPERIMENT 2b: REAL dbt MANIFEST LINEAGE VALIDATION (REVISED)")
    print("=" * 70)

    g = load_graph(nodes_path, edges_path)
    print(f"\nFull graph: N={g.number_of_nodes()}, M={g.number_of_edges()}")
    print(f"DAG: {nx.is_directed_acyclic_graph(g)}")
    print(f"Weakly connected components: {nx.number_weakly_connected_components(g)}")

    print("\n--- Full Graph ---")
    full_desc = compute_descriptors(g, "full")
    full_gov = governance_metrics(g)
    print_desc(full_desc, full_gov)

    lcc = largest_weakly_connected(g)
    print(f"\n--- Largest Component (N={lcc.number_of_nodes()}, M={lcc.number_of_edges()}) ---")
    lcc_desc = compute_descriptors(lcc, "lcc")
    lcc_gov = governance_metrics(lcc)
    print_desc(lcc_desc, lcc_gov)

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
            print_desc(desc, gov, indent=4)

    df = pd.DataFrame(rows)

    # === CORRELATION WITH PERMUTATION TESTS ===
    print("\n" + "=" * 70)
    print("CORRELATION: Permutation Spearman + BH FDR")
    print("=" * 70)

    valid = df[~df.get("too_small", pd.Series([False]*len(df)))].copy()
    n_valid = len(valid)
    print(f"Domains with N>=5: {n_valid}")

    desc_cols = [c for c in valid.columns
                 if c.startswith("D") and c[1].isdigit()
                 and "error" not in c and valid[c].notna().sum() >= 4]

    all_tests = []

    if n_valid >= 4:
        for target in ["governance_score", "test_rate", "doc_rate"]:
            for col in desc_cols:
                vals = valid[[col, target]].dropna()
                if len(vals) >= 4:
                    rho, perm_p, param_p = permutation_spearman(
                        vals[col].values, vals[target].values)
                    all_tests.append({
                        "descriptor": col, "target": target,
                        "rho": rho, "perm_p": perm_p, "param_p": param_p,
                    })

    if all_tests:
        perm_ps = np.array([t["perm_p"] for t in all_tests])
        fdr_ps = benjamini_hochberg(perm_ps)
        for i, t in enumerate(all_tests):
            t["fdr_p"] = float(fdr_ps[i])

        for target in ["governance_score", "test_rate", "doc_rate"]:
            subset = [t for t in all_tests if t["target"] == target]
            subset.sort(key=lambda t: t["perm_p"])
            print(f"\n  vs {target}:")
            print(f"    {'Descriptor':25s} {'rho':>7s} {'perm_p':>8s} {'FDR_p':>8s} {'param_p':>8s}")
            print(f"    {'-'*52}")
            for t in subset[:10]:
                sig = "***" if t["fdr_p"] < 0.01 else "**" if t["fdr_p"] < 0.05 else "*" if t["fdr_p"] < 0.10 else "ns"
                print(f"    {t['descriptor']:25s} {t['rho']:+7.3f} "
                      f"{t['perm_p']:8.4f} {t['fdr_p']:8.4f} {t['param_p']:8.4f} {sig}")

    # === D4 vs CYCLE RANK ABLATION ===
    print("\n" + "=" * 70)
    print("D4 ABLATION: H1/N vs cycle_rank/N")
    print("=" * 70)

    for target in ["governance_score", "test_rate", "doc_rate"]:
        for col_pair in [("D4_h1_bars_norm", "D4_cycle_rank_norm")]:
            vals = valid[[col_pair[0], col_pair[1], target]].dropna()
            if len(vals) >= 4:
                rho_h1, pp_h1, _ = permutation_spearman(vals[col_pair[0]].values, vals[target].values)
                rho_cr, pp_cr, _ = permutation_spearman(vals[col_pair[1]].values, vals[target].values)
                print(f"  vs {target}: H1/N rho={rho_h1:+.3f} (p={pp_h1:.4f}), "
                      f"cycRk/N rho={rho_cr:+.3f} (p={pp_cr:.4f})")

    # === PARTIAL CORRELATIONS (D3 controlling for confounds) ===
    print("\n" + "=" * 70)
    print("PARTIAL CORRELATIONS: D3 controlling for domain_size, edge_count, source_fraction")
    print("=" * 70)

    d3_cols = [c for c in desc_cols if c.startswith("D3")]
    covariates_data = valid[["N", "M", "source_fraction"]].values

    for target in ["governance_score", "doc_rate"]:
        print(f"\n  vs {target}:")
        for col in d3_cols:
            vals_mask = valid[col].notna() & valid[target].notna()
            if vals_mask.sum() >= 4:
                x = valid.loc[vals_mask, col].values
                y = valid.loc[vals_mask, target].values
                cov = covariates_data[vals_mask.values]
                rho_partial, pp = partial_spearman(x, y, cov)
                rho_raw, _, _ = permutation_spearman(x, y)
                print(f"    {col:25s}: raw rho={rho_raw:+.3f}, partial rho={rho_partial:+.3f}, partial_perm_p={pp:.4f}")

    # === D4/TEST RATE QUALITATIVE NOTE ===
    print("\n" + "=" * 70)
    print("D4/TEST RATE: QUALITATIVE OBSERVATION")
    print("=" * 70)
    n_h1_nonzero = (valid["D4_h1_bars_norm"] > 0).sum() if "D4_h1_bars_norm" in valid.columns else 0
    n_test_nonzero = (valid["test_rate"] > 0).sum() if "test_rate" in valid.columns else 0
    print(f"  Domains with H1 features > 0: {n_h1_nonzero} / {n_valid}")
    print(f"  Domains with test_rate > 0: {n_test_nonzero} / {n_valid}")
    print(f"  The rho=1.0 correlation is driven by a binary split:")
    print(f"  one domain has both H1 features and tests. Under permutation,")
    print(f"  the probability of this alignment by chance is ~{1/max(n_valid,1):.3f} (1/{n_valid}).")
    print(f"  This is a case-study observation, not evidence of a continuous relationship.")

    # === GOVERNANCE GRADIENT ===
    print("\n" + "=" * 70)
    print("GOVERNANCE GRADIENT ANALYSIS")
    print("=" * 70)

    if n_valid >= 6:
        valid_sorted = valid.sort_values("governance_score")
        n_tercile = len(valid_sorted) // 3
        low = valid_sorted.head(n_tercile)
        high = valid_sorted.tail(n_tercile)
        print(f"\nLow tercile (n={len(low)}, mean score={low['governance_score'].mean():.3f}):")
        print(f"High tercile (n={len(high)}, mean score={high['governance_score'].mean():.3f}):")

        key_descs = ["D1_csi", "D2_max_gini", "D3_norm_gap", "D3_entropy",
                     "D4_h1_bars_norm", "D4_cycle_rank_norm"]
        print(f"\n  {'Descriptor':25s} {'Low':>8s} {'High':>8s} {'Diff':>8s} {'U':>6s} {'p':>8s}")
        print("  " + "-" * 67)
        for col in key_descs:
            if col in low.columns and col in high.columns:
                lv, hv = low[col].dropna(), high[col].dropna()
                if len(lv) >= 2 and len(hv) >= 2:
                    u_stat, p_val = stats.mannwhitneyu(lv, hv, alternative='two-sided')
                    print(f"  {col:25s} {lv.mean():8.4f} {hv.mean():8.4f} "
                          f"{hv.mean()-lv.mean():+8.4f} {u_stat:6.0f} {p_val:8.4f}")

    # === CROSS-TOPOLOGY COMPARISON ===
    print("\n" + "=" * 70)
    print("CROSS-TOPOLOGY STRUCTURAL PROFILES")
    print("=" * 70)

    real_nodes_path = os.path.join(data_dir, "real_nodes.csv")
    real_edges_path = os.path.join(data_dir, "real_edges.csv")
    synth_nodes_path = os.path.join(data_dir, "nodes.csv")
    synth_edges_path = os.path.join(data_dir, "edges.csv")

    profiles = {"dbt_manifest": (full_desc, full_gov)}
    if os.path.exists(real_nodes_path):
        g_s = load_graph(real_nodes_path, real_edges_path)
        profiles["static_code"] = (compute_descriptors(g_s), governance_metrics(g_s))
    if os.path.exists(synth_nodes_path):
        g_y = load_graph(synth_nodes_path, synth_edges_path)
        profiles["synthetic_6dom"] = (compute_descriptors(g_y), governance_metrics(g_y))

    print(f"\n  {'Topology':20s} {'N':>5s} {'CSI':>7s} {'maxGini':>8s} "
          f"{'gap':>7s} {'H1/N':>7s} {'cycRk/N':>8s} {'govScore':>9s}")
    print("  " + "-" * 80)
    for name, (d, gv) in profiles.items():
        if d.get("too_small"):
            continue
        print(f"  {name:20s} {d['N']:5d} {d.get('D1_csi',0):7.3f} "
              f"{d.get('D2_max_gini',0):8.3f} {d.get('D3_norm_gap',0):7.4f} "
              f"{d.get('D4_h1_bars_norm',0):7.3f} {d.get('D4_cycle_rank_norm',0):8.3f} "
              f"{gv.get('governance_score',0):9.3f}")

    # === LAYER-STRATIFIED GOVERNANCE ===
    print("\n" + "=" * 70)
    print("LAYER-STRATIFIED GOVERNANCE")
    print("=" * 70)
    for layer in ["source/raw", "silver/intermediate", "gold/mart"]:
        lnodes = [n for n, d in g.nodes(data=True) if d.get("layer") == layer]
        if lnodes:
            gov = governance_metrics(g.subgraph(lnodes).copy())
            print(f"  {layer} (N={len(lnodes)}): steward={gov['steward_rate']:.2f}, "
                  f"tested={gov['test_rate']:.2f}, documented={gov['doc_rate']:.2f}")

    # === SAVE ===
    out_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'artifacts', 'phase_3')
    os.makedirs(out_dir, exist_ok=True)
    df.to_csv(os.path.join(out_dir, "exp_2b_dbt_domain_descriptors.csv"), index=False)

    sig_results = [t for t in all_tests if t["fdr_p"] < 0.10]
    summary = {
        "experiment": "2b_dbt_real_data_revised",
        "statistical_method": "permutation Spearman (10k perms) + BH FDR",
        "n_domains_analyzed": n_valid,
        "n_significant_fdr_010": len(sig_results),
        "significant_correlations": sig_results,
        "full_graph": {k: (float(v) if isinstance(v, (np.floating, np.integer)) else v)
                       for k, v in {**full_desc, **full_gov}.items()},
    }
    with open(os.path.join(out_dir, "exp_2b_dbt_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\nResults saved to {out_dir}/")
    print("\n" + "=" * 70)
    print("EXPERIMENT 2b COMPLETE (REVISED)")
    print("=" * 70)


if __name__ == "__main__":
    main()
