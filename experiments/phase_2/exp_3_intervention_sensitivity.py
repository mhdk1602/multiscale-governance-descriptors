"""Experiment 3: Sensitivity to governance interventions.

Design:
  Take a baseline lineage DAG (medium scale, N~65). Apply one governance
  intervention at a time and measure descriptor response. Compare against
  random perturbations of equal magnitude to compute signal-to-noise ratio.

Governance interventions:
  1. Add domain boundaries (partition nodes into domains, remove cross-domain edges)
  2. Remove orphan chains (prune disconnected linear chains)
  3. Remove shortcuts (prune source-to-exposure direct edges)
  4. Add monitoring nodes (attach test/check nodes to high-blast-radius nodes)

Random perturbations:
  - Remove k random edges (same k as intervention)
  - Add k random edges (same k)
  - Rewire k edges (remove + add)

Signal-to-noise: |descriptor_change_from_intervention| / std(descriptor_change_from_random)
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
from governance_descriptors.generators import synthetic_lineage


def compute_all_descriptors(g):
    """Compute all D1-D4 descriptors, return flat dict."""
    n = g.number_of_nodes()
    d1 = community_descriptor_summary(g)
    d2 = concentration_profile(g)
    d3 = spectral_descriptors(g)
    d4 = topological_descriptors(g)
    return {
        "N": n,
        "M": g.number_of_edges(),
        "D1_csi": d1["csi"],
        "D1_frag_onset": d1["fragmentation_onset"],
        "D2_max_gini": d2["max_gini"],
        "D3_norm_gap": d3["normalized_spectral_gap"],
        "D3_fiedler_bim": d3["fiedler_bimodality"],
        "D3_entropy": d3["spectral_entropy"],
        "D4_h1_bars_norm": d4["h1_n_bars"] / n if n > 0 else 0,
        "D4_h1_persist": d4["h1_total_persistence"],
    }


# --- Governance Interventions ---

def intervene_add_domains(g: nx.DiGraph, n_domains: int = 3, seed: int = 42) -> nx.DiGraph:
    """Partition staging nodes into domains, remove cross-domain edges."""
    rng = np.random.default_rng(seed)
    g = g.copy()

    staging = [n for n, d in g.nodes(data=True) if d.get("layer") == "staging"]
    rng.shuffle(staging)

    domain_size = len(staging) // n_domains
    domains = {}
    for i, s in enumerate(staging):
        domains[s] = i // domain_size if domain_size > 0 else 0
        g.nodes[s]["domain"] = domains[s]

    sources = [n for n, d in g.nodes(data=True) if d.get("layer") == "source"]
    for s in sources:
        succs = list(g.successors(s))
        stg_succs = [t for t in succs if t in domains]
        if len(stg_succs) > 1:
            target_domain = domains[stg_succs[0]]
            for t in stg_succs[1:]:
                if domains[t] != target_domain:
                    g.remove_edge(s, t)

    return g


def intervene_remove_orphans(g: nx.DiGraph) -> nx.DiGraph:
    """Remove orphan chains (nodes with layer='orphan' or degree-1 chains)."""
    g = g.copy()
    orphans = [n for n, d in g.nodes(data=True) if d.get("layer") == "orphan"]
    g.remove_nodes_from(orphans)

    changed = True
    while changed:
        changed = False
        for n in list(g.nodes()):
            if g.degree(n) == 0:
                g.remove_node(n)
                changed = True

    return g


def intervene_remove_shortcuts(g: nx.DiGraph) -> nx.DiGraph:
    """Remove direct source-to-exposure edges (bypassing staging/mart)."""
    g = g.copy()
    edges_to_remove = []
    for u, v in g.edges():
        u_layer = g.nodes[u].get("layer", "")
        v_layer = g.nodes[v].get("layer", "")
        if u_layer == "source" and v_layer == "exposure":
            edges_to_remove.append((u, v))
    g.remove_edges_from(edges_to_remove)
    return g


def intervene_add_monitors(g: nx.DiGraph, k: int = 5, seed: int = 42) -> nx.DiGraph:
    """Add k monitoring/test nodes connected to high-blast-radius nodes."""
    g = g.copy()
    reach = {n: len(nx.descendants(g, n)) for n in g.nodes()}
    top_k = sorted(reach, key=reach.get, reverse=True)[:k]

    for i, node in enumerate(top_k):
        monitor = f"monitor_{i}"
        g.add_node(monitor, layer="monitor", stewarded=True)
        g.add_edge(node, monitor)

    return g


# --- Random Perturbations ---

def perturb_remove_edges(g: nx.DiGraph, k: int, seed: int = 42) -> nx.DiGraph:
    """Remove k random edges."""
    rng = np.random.default_rng(seed)
    g = g.copy()
    edges = list(g.edges())
    if k >= len(edges):
        k = max(1, len(edges) // 2)
    to_remove = rng.choice(len(edges), size=k, replace=False)
    g.remove_edges_from([edges[i] for i in to_remove])

    isolates = list(nx.isolates(g))
    g.remove_nodes_from(isolates)
    return g


def perturb_add_edges(g: nx.DiGraph, k: int, seed: int = 42) -> nx.DiGraph:
    """Add k random forward edges (respecting DAG structure)."""
    rng = np.random.default_rng(seed)
    g = g.copy()

    if nx.is_directed_acyclic_graph(g):
        topo = list(nx.topological_sort(g))
        topo_idx = {n: i for i, n in enumerate(topo)}
    else:
        topo_idx = {n: i for i, n in enumerate(g.nodes())}

    nodes = list(g.nodes())
    added = 0
    attempts = 0
    while added < k and attempts < k * 20:
        u = rng.choice(nodes)
        v = rng.choice(nodes)
        if u != v and topo_idx.get(u, 0) < topo_idx.get(v, 0) and not g.has_edge(u, v):
            g.add_edge(u, v)
            added += 1
        attempts += 1
    return g


def perturb_rewire(g: nx.DiGraph, k: int, seed: int = 42) -> nx.DiGraph:
    """Rewire k edges: remove k, add k."""
    g = perturb_remove_edges(g, k, seed)
    g = perturb_add_edges(g, k, seed + 1000)
    return g


def run_experiment(n_random_trials: int = 20):
    """Run sensitivity experiment."""
    print("Experiment 3: Sensitivity to Governance Interventions")
    print("=" * 70)

    base_g = synthetic_lineage(n_sources=15, n_staging=30, n_marts=12, n_exposures=8, seed=42)
    print(f"Baseline: N={base_g.number_of_nodes()}, M={base_g.number_of_edges()}")

    from governance_descriptors.generators import poorly_governed_lineage
    poor_g = poorly_governed_lineage(n_sources=15, n_staging=30, n_marts=12, n_exposures=8, seed=42)
    print(f"Poorly governed variant: N={poor_g.number_of_nodes()}, M={poor_g.number_of_edges()}")

    base_desc = compute_all_descriptors(poor_g)
    print(f"\nBaseline descriptors (poorly governed):")
    for k, v in base_desc.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    interventions = {
        "add_domains": intervene_add_domains(poor_g),
        "remove_orphans": intervene_remove_orphans(poor_g),
        "remove_shortcuts": intervene_remove_shortcuts(poor_g),
        "add_monitors": intervene_add_monitors(poor_g),
    }

    desc_keys = [k for k in base_desc if k not in ("N", "M")]
    rows = []

    print(f"\nGovernance interventions:")
    for name, g_int in interventions.items():
        desc = compute_all_descriptors(g_int)
        print(f"\n  {name}: N={desc['N']}, M={desc['M']}")
        row = {"intervention": name, "type": "governance"}
        for k in desc_keys:
            delta = desc[k] - base_desc[k]
            row[f"{k}_delta"] = delta
            row[k] = desc[k]
            print(f"    {k}: {desc[k]:.4f} (delta={delta:+.4f})")
        rows.append(row)

    perturbation_k = 5
    print(f"\nRandom perturbations (k={perturbation_k}, {n_random_trials} trials each):")

    perturb_fns = {
        "random_remove": perturb_remove_edges,
        "random_add": perturb_add_edges,
        "random_rewire": perturb_rewire,
    }

    random_deltas = {k: [] for k in desc_keys}

    for p_name, p_fn in perturb_fns.items():
        for trial in range(n_random_trials):
            g_pert = p_fn(poor_g, k=perturbation_k, seed=trial)
            desc = compute_all_descriptors(g_pert)
            for k in desc_keys:
                random_deltas[k].append(desc[k] - base_desc[k])

    random_std = {k: np.std(v) for k, v in random_deltas.items()}
    random_mean = {k: np.mean(v) for k, v in random_deltas.items()}

    print("\n  Random perturbation noise (std of delta):")
    for k in desc_keys:
        print(f"    {k}: mean_delta={random_mean[k]:+.4f}, std={random_std[k]:.4f}")

    print("\n" + "=" * 70)
    print("SIGNAL-TO-NOISE RATIOS")
    print("=" * 70)

    snr_rows = []
    for row in rows:
        name = row["intervention"]
        print(f"\n  {name}:")
        snr_row = {"intervention": name}
        for k in desc_keys:
            signal = abs(row[f"{k}_delta"])
            noise = random_std[k] if random_std[k] > 1e-10 else 1e-10
            snr = signal / noise
            snr_row[f"{k}_snr"] = snr
            snr_row[f"{k}_delta"] = row[f"{k}_delta"]
            marker = "***" if snr > 3 else "**" if snr > 2 else "*" if snr > 1 else ""
            print(f"    {k:25s}: SNR={snr:6.2f} {marker}")
        snr_rows.append(snr_row)

    df_interventions = pd.DataFrame(rows)
    df_snr = pd.DataFrame(snr_rows)

    out_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'artifacts', 'phase_2')
    os.makedirs(out_dir, exist_ok=True)
    df_interventions.to_csv(os.path.join(out_dir, "exp_3_interventions.csv"), index=False)
    df_snr.to_csv(os.path.join(out_dir, "exp_3_snr.csv"), index=False)

    print("\n" + "=" * 70)
    print("SENSITIVITY RANKING")
    print("=" * 70)
    print("\nWhich descriptor responds most to governance interventions vs noise?")
    for k in desc_keys:
        snr_col = f"{k}_snr"
        mean_snr = df_snr[snr_col].mean()
        max_snr = df_snr[snr_col].max()
        best_int = df_snr.loc[df_snr[snr_col].idxmax(), "intervention"]
        print(f"  {k:25s}: mean_SNR={mean_snr:6.2f}, max_SNR={max_snr:6.2f} (best: {best_int})")

    print(f"\nCSV artifacts saved to {out_dir}")


if __name__ == "__main__":
    run_experiment()
