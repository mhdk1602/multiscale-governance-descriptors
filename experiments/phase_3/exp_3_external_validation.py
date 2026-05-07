"""Experiment 3: Cross-dataset structural validation.

Computes D1-D4 descriptors on external open datasets to test whether
descriptor values for real-world pipeline/workflow graphs differ from
synthetic generators and from each other.

Datasets:
  - WfCommons: 11 scientific workflow DAGs (101-4846 nodes)
  - DW-Bench: 2 data warehouse schemas (OMOP 37 tables, TPC-DI 31 tables)
  - dbt manifest: production lineage (223 nodes) [already computed]

This is a structural characterization, not a governance correlation
(external datasets lack governance metadata). The question is whether
real pipeline topologies occupy a different region of descriptor space
than our synthetic generators.
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


def load_wfcommons_graph(json_path):
    with open(json_path) as f:
        data = json.load(f)
    spec = data.get("workflow", {}).get("specification", {})
    tasks = spec.get("tasks", [])

    g = nx.DiGraph()
    for task in tasks:
        tid = task["id"]
        g.add_node(tid, name=task.get("name", tid))
    for task in tasks:
        tid = task["id"]
        for parent in task.get("parents", []):
            if parent in g:
                g.add_edge(parent, tid)
    return g


def load_dlg_graph(node_path, edge_path, table_level=True):
    """Load a DLG-DG-23 lineage graph.

    If table_level=True, returns only Data Table + Data Job nodes with
    DATA_FLOW edges (comparable to dbt lineage). Otherwise returns the
    full graph including Data Field nodes and PARENT_CHILD edges.
    """
    with open(node_path) as f:
        nodes = json.load(f)["nodes"]
    with open(edge_path) as f:
        edges = json.load(f)["edges"]

    g = nx.DiGraph()
    node_types = {}
    for n in nodes:
        nid = n["asset_id"]
        ntype = n.get("asset_type", "unknown")
        node_types[nid] = ntype
        if table_level and ntype == "Data Field":
            continue
        g.add_node(nid, asset_type=ntype)

    for e in edges:
        src, tgt = e["source"], e["target"]
        rtype = e.get("relation_type", "unknown")
        if table_level and rtype == "PARENT_CHILD":
            continue
        if src in g and tgt in g:
            g.add_edge(src, tgt, relation_type=rtype)

    return g


def load_dwbench_graph(nodes_path, edges_path):
    nodes_df = pd.read_csv(nodes_path)
    edges_df = pd.read_csv(edges_path)
    g = nx.DiGraph()
    for _, row in nodes_df.iterrows():
        g.add_node(row.iloc[0], **{k: row[k] for k in nodes_df.columns[1:]})
    for _, row in edges_df.iterrows():
        src, tgt = row["source"], row["target"]
        if src in g and tgt in g:
            g.add_edge(src, tgt, type=row.get("type", "unknown"))
    return g


def compute_descriptors_safe(g, label="") -> dict:
    n = g.number_of_nodes()
    m = g.number_of_edges()
    result = {"label": label, "N": n, "M": m, "is_dag": nx.is_directed_acyclic_graph(g)}

    if n < 5:
        result["too_small"] = True
        return result
    result["too_small"] = False

    try:
        d1 = community_descriptor_summary(g)
        result["D1_csi"] = d1["csi"]
        result["D1_frag_onset"] = d1["fragmentation_onset"]
        result["D1_n_comm"] = d1["n_communities_at_gamma_1"]
    except Exception as e:
        result["D1_error"] = str(e)

    try:
        d2 = concentration_profile(g)
        result["D2_max_gini"] = d2["max_gini"]
        result["D2_transition"] = d2["concentration_transition_depth"]
    except Exception as e:
        result["D2_error"] = str(e)

    try:
        d3 = spectral_descriptors(g)
        result["D3_alg_conn"] = d3["algebraic_connectivity"]
        result["D3_norm_gap"] = d3["normalized_spectral_gap"]
        result["D3_fiedler_bim"] = d3["fiedler_bimodality"]
        result["D3_entropy"] = d3["spectral_entropy"]
    except Exception as e:
        result["D3_error"] = str(e)

    if n <= 500:
        try:
            d4 = topological_descriptors(g)
            result["D4_h1_bars"] = d4["h1_n_bars"]
            result["D4_h1_bars_norm"] = d4["h1_n_bars"] / n if n > 0 else 0
            result["D4_h1_entropy"] = d4["h1_persistence_entropy"]
        except Exception as e:
            result["D4_error"] = str(e)
    else:
        result["D4_skipped"] = f"N={n} too large for Rips complex"

    try:
        cr = cycle_rank_descriptors(g)
        result["D4_cycle_rank"] = cr["cycle_rank"]
        result["D4_cycle_rank_norm"] = cr["cycle_rank_norm"]
    except Exception as e:
        result["CR_error"] = str(e)

    return result


def fmt(val, spec=".4f"):
    if isinstance(val, (int, float, np.integer, np.floating)):
        return f"{val:{spec}}"
    return str(val)


def main():
    data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
    ext_dir = os.path.join(data_dir, "external")

    print("=" * 70)
    print("EXPERIMENT 3: CROSS-DATASET STRUCTURAL VALIDATION")
    print("=" * 70)

    rows = []

    # --- WfCommons ---
    wf_dir = os.path.join(ext_dir, "wfcommons")
    if os.path.isdir(wf_dir):
        print("\n--- WfCommons Scientific Workflows ---")
        for fname in sorted(os.listdir(wf_dir)):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(wf_dir, fname)
            g = load_wfcommons_graph(fpath)
            label = fname.replace(".json", "")
            app = label.split("-")[0]
            print(f"  {label} (N={g.number_of_nodes()}, M={g.number_of_edges()})...", flush=True)
            desc = compute_descriptors_safe(g, label=label)
            desc["source"] = "wfcommons"
            desc["application"] = app
            rows.append(desc)

            if not desc.get("too_small"):
                for prefix in ["D1", "D2", "D3", "D4"]:
                    if f"{prefix}_error" in desc:
                        print(f"    {prefix}: ERROR {desc[f'{prefix}_error']}")
                    elif f"{prefix}_skipped" in desc:
                        print(f"    {prefix}: {desc[f'{prefix}_skipped']}")
    else:
        print(f"\n  WfCommons dir not found: {wf_dir}")

    # --- DLG-DG-23 (Huawei Cloud lineage graphs) ---
    dlg_dir = os.path.join(ext_dir, "dlg-dg-23")
    if os.path.isdir(dlg_dir):
        print("\n--- DLG-DG-23 Data Lineage Graphs (table-level) ---")
        for i in range(1, 19):
            npath = os.path.join(dlg_dir, "Node", f"DLG{i}-node.json")
            epath = os.path.join(dlg_dir, "Edge", f"DLG{i}-edge.json")
            if not (os.path.exists(npath) and os.path.exists(epath)):
                continue
            g = load_dlg_graph(npath, epath, table_level=True)
            label = f"DLG{i}"
            print(f"  {label} (N={g.number_of_nodes()}, M={g.number_of_edges()})...", flush=True)
            desc = compute_descriptors_safe(g, label=label)
            desc["source"] = "dlg-dg-23"
            desc["application"] = "huawei_lineage"
            rows.append(desc)

            if not desc.get("too_small"):
                for prefix in ["D1", "D2", "D3", "D4"]:
                    if f"{prefix}_error" in desc:
                        print(f"    {prefix}: ERROR {desc[f'{prefix}_error']}")
                    elif f"{prefix}_skipped" in desc:
                        print(f"    {prefix}: {desc[f'{prefix}_skipped']}")
    else:
        print(f"\n  DLG-DG-23 dir not found: {dlg_dir}")

    # --- DW-Bench ---
    dwb_dir = os.path.join(ext_dir, "dw-bench")
    if os.path.isdir(dwb_dir):
        print("\n--- DW-Bench Data Warehouse Schemas ---")
        for schema in ["omop", "tpcdi"]:
            npath = os.path.join(dwb_dir, f"{schema}_nodes.csv")
            epath = os.path.join(dwb_dir, f"{schema}_edges.csv")
            if os.path.exists(npath) and os.path.exists(epath):
                g = load_dwbench_graph(npath, epath)
                print(f"  {schema} (N={g.number_of_nodes()}, M={g.number_of_edges()})...", flush=True)
                desc = compute_descriptors_safe(g, label=schema)
                desc["source"] = "dw-bench"
                desc["application"] = schema
                rows.append(desc)

    # --- Reference: dbt manifest (already computed, re-run for comparison) ---
    dbt_nodes = os.path.join(data_dir, "dbt_nodes.csv")
    dbt_edges = os.path.join(data_dir, "dbt_edges.csv")
    if os.path.exists(dbt_nodes):
        print("\n--- dbt Manifest (reference) ---")
        nodes_df = pd.read_csv(dbt_nodes)
        edges_df = pd.read_csv(dbt_edges)
        g = nx.DiGraph()
        for _, row in nodes_df.iterrows():
            g.add_node(row["node_id"])
        for _, row in edges_df.iterrows():
            if row["source_node_id"] in g and row["target_node_id"] in g:
                g.add_edge(row["source_node_id"], row["target_node_id"])
        print(f"  dbt_manifest (N={g.number_of_nodes()}, M={g.number_of_edges()})...", flush=True)
        desc = compute_descriptors_safe(g, label="dbt_manifest")
        desc["source"] = "dbt"
        desc["application"] = "data_pipeline"
        rows.append(desc)

    df = pd.DataFrame(rows)

    # --- Summary Table ---
    print("\n" + "=" * 70)
    print("STRUCTURAL PROFILE COMPARISON")
    print("=" * 70)

    cols = ["label", "source", "N", "M", "is_dag",
            "D1_csi", "D2_max_gini", "D3_norm_gap", "D3_fiedler_bim",
            "D3_entropy", "D4_h1_bars_norm", "D4_cycle_rank_norm"]

    print(f"\n  {'Label':40s} {'Src':10s} {'N':>6s} {'M':>6s} {'DAG':>4s} "
          f"{'CSI':>6s} {'Gini':>6s} {'gap':>7s} {'FBim':>6s} {'Ent':>6s} "
          f"{'H1/N':>6s} {'CR/N':>6s}")
    print("  " + "-" * 120)

    for _, r in df.iterrows():
        if r.get("too_small"):
            continue
        print(f"  {str(r.get('label','')):40s} {str(r.get('source','')):10s} "
              f"{r['N']:6d} {r['M']:6d} {'Y' if r.get('is_dag') else 'N':>4s} "
              f"{fmt(r.get('D1_csi', ''), '.3f'):>6s} "
              f"{fmt(r.get('D2_max_gini', ''), '.3f'):>6s} "
              f"{fmt(r.get('D3_norm_gap', ''), '.4f'):>7s} "
              f"{fmt(r.get('D3_fiedler_bim', ''), '.3f'):>6s} "
              f"{fmt(r.get('D3_entropy', ''), '.2f'):>6s} "
              f"{fmt(r.get('D4_h1_bars_norm', ''), '.3f'):>6s} "
              f"{fmt(r.get('D4_cycle_rank_norm', ''), '.3f'):>6s}")

    # --- Statistical comparison: WfCommons vs synthetic ranges ---
    print("\n" + "=" * 70)
    print("WfCommons vs SYNTHETIC GENERATORS (from Exp 1)")
    print("=" * 70)

    for src_name, src_key in [("WfCommons", "wfcommons"), ("DLG-DG-23", "dlg-dg-23")]:
        src_rows = df[df["source"] == src_key]
        if len(src_rows) == 0:
            continue
        print(f"\n  {src_name} ({len(src_rows)} graphs):")
        for col in ["D1_csi", "D2_max_gini", "D3_norm_gap", "D3_fiedler_bim",
                     "D4_cycle_rank_norm"]:
            vals = src_rows[col].dropna()
            if len(vals) > 0:
                print(f"    {col:25s}: mean={vals.mean():.4f}, "
                      f"std={vals.std():.4f}, "
                      f"range=[{vals.min():.4f}, {vals.max():.4f}]")

    # --- Save ---
    out_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'artifacts', 'phase_3')
    os.makedirs(out_dir, exist_ok=True)
    df.to_csv(os.path.join(out_dir, "exp_3_external_descriptors.csv"), index=False)

    summary = {
        "experiment": "3_external_validation",
        "n_graphs": len(df),
        "sources": {src: int(cnt) for src, cnt in df["source"].value_counts().items()},
        "descriptor_ranges": {},
    }
    for col in ["D1_csi", "D2_max_gini", "D3_norm_gap", "D4_cycle_rank_norm"]:
        vals = df[col].dropna()
        if len(vals) > 0:
            summary["descriptor_ranges"][col] = {
                "min": float(vals.min()), "max": float(vals.max()),
                "mean": float(vals.mean()), "std": float(vals.std()),
            }
    with open(os.path.join(out_dir, "exp_3_external_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\nResults saved to {out_dir}/")
    print("\n" + "=" * 70)
    print("EXPERIMENT 3 COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
