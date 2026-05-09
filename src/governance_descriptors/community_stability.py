"""D1: Community stability under resolution sweep.

Uses NetworkX built-in Louvain with resolution parameter gamma.
Sweeps gamma logarithmically from gamma_min to gamma_max, records
partition at each step, and computes stability metrics.

References:
    Reichardt & Bornholdt (2006), Phys. Rev. E 74, 016110.
    Delvenne, Yaliraki & Barahona (2010), PNAS 107, 12755-12760.
    Fortunato & Barthelemy (2007), PNAS 104(1), 36-41.
"""
from __future__ import annotations

import numpy as np
import networkx as nx
from collections import Counter


def _to_undirected_connected(g):
    """Convert to undirected and extract giant component."""
    if isinstance(g, nx.DiGraph):
        g = g.to_undirected()
    if not nx.is_connected(g):
        giant = max(nx.connected_components(g), key=len)
        g = g.subgraph(giant).copy()
    return g


def resolution_sweep(
    g,
    gamma_min: float = 0.1,
    gamma_max: float = 10.0,
    n_steps: int = 20,
    seed: int = 42,
) -> list[dict]:
    """Run Louvain at logarithmically spaced resolution values.

    Returns list of dicts, one per gamma, with keys:
        gamma, n_communities, modularity, partition (frozenset of frozensets)
    """
    g = _to_undirected_connected(g)
    gammas = np.logspace(np.log10(gamma_min), np.log10(gamma_max), n_steps)
    results = []

    for gamma in gammas:
        communities = nx.community.louvain_communities(
            g, resolution=gamma, seed=seed
        )
        partition = frozenset(frozenset(c) for c in communities)
        mod = nx.community.modularity(g, communities, resolution=gamma)

        results.append({
            "gamma": float(gamma),
            "n_communities": len(communities),
            "modularity": float(mod),
            "partition": partition,
            "communities": communities,
        })

    return results


def _nvi(partition_a, partition_b, n_nodes: int) -> float:
    """Normalized Variation of Information between two partitions.

    Returns value in [0, 1]. 0 = identical partitions.
    """
    if partition_a == partition_b:
        return 0.0

    node_to_a = {}
    for i, comm in enumerate(partition_a):
        for node in comm:
            node_to_a[node] = i
    node_to_b = {}
    for i, comm in enumerate(partition_b):
        for node in comm:
            node_to_b[node] = i

    contingency = Counter()
    for node in node_to_a:
        if node in node_to_b:
            contingency[(node_to_a[node], node_to_b[node])] += 1

    n = n_nodes
    if n == 0:
        return 0.0

    h_a = 0.0
    sizes_a = Counter(node_to_a.values())
    for count in sizes_a.values():
        p = count / n
        if p > 0:
            h_a -= p * np.log2(p)

    h_b = 0.0
    sizes_b = Counter(node_to_b.values())
    for count in sizes_b.values():
        p = count / n
        if p > 0:
            h_b -= p * np.log2(p)

    mi = 0.0
    for (i, j), n_ij in contingency.items():
        p_ij = n_ij / n
        p_i = sizes_a[i] / n
        p_j = sizes_b[j] / n
        if p_ij > 0 and p_i > 0 and p_j > 0:
            mi += p_ij * np.log2(p_ij / (p_i * p_j))

    vi = h_a + h_b - 2 * mi
    log_n = np.log2(n) if n > 1 else 1.0
    return float(vi / log_n) if log_n > 0 else 0.0


def community_stability_index(sweep_results: list[dict]) -> float:
    """Fraction of consecutive resolution steps with NVI < 0.1.

    High CSI = partition is robust across resolutions = clear domain boundaries.
    """
    if len(sweep_results) < 2:
        return 1.0

    n_nodes = sum(len(c) for c in sweep_results[0]["partition"])
    stable_count = 0

    for i in range(len(sweep_results) - 1):
        nvi = _nvi(
            sweep_results[i]["partition"],
            sweep_results[i + 1]["partition"],
            n_nodes,
        )
        if nvi < 0.1:
            stable_count += 1

    return stable_count / (len(sweep_results) - 1)


def fragmentation_onset(sweep_results: list[dict]) -> float:
    """The gamma at which n_communities first exceeds 2x the minimum.

    Late fragmentation = strongly structured governance domains.
    Returns gamma value, or inf if fragmentation never occurs.
    """
    min_k = min(r["n_communities"] for r in sweep_results)
    threshold = 2 * min_k

    for r in sweep_results:
        if r["n_communities"] >= threshold:
            return r["gamma"]

    return float("inf")


def stability_variance(sweep_results: list[dict]) -> float:
    """Variance of modularity across resolutions.

    Low variance = structure is inherent. High variance = artifact of resolution choice.
    """
    mods = [r["modularity"] for r in sweep_results]
    return float(np.var(mods))


def community_stability_index_multiseed(
    g, n_seeds: int = 25, gamma_min: float = 0.1, gamma_max: float = 10.0, n_steps: int = 20
) -> dict:
    """Run CSI computation with multiple random seeds to quantify Louvain stochasticity.

    Returns mean, std, min, max of CSI across seeds, and per-seed values.
    Also returns mean seed-NVI at gamma=1.0 to measure within-resolution optimizer variance.
    """
    g = _to_undirected_connected(g)
    n_nodes = g.number_of_nodes()
    csi_values = []
    partitions_at_gamma1 = []

    for seed in range(n_seeds):
        sweep = resolution_sweep(g, gamma_min=gamma_min, gamma_max=gamma_max,
                                 n_steps=n_steps, seed=seed)
        csi_values.append(community_stability_index(sweep))
        # Record partition closest to gamma=1.0 for seed-NVI
        best = min(sweep, key=lambda r: abs(r["gamma"] - 1.0))
        partitions_at_gamma1.append(best["partition"])

    # Seed-NVI at gamma≈1: mean NVI between all pairs of seed partitions
    nvi_pairs = []
    for i in range(n_seeds):
        for j in range(i + 1, n_seeds):
            nvi_pairs.append(_nvi(partitions_at_gamma1[i], partitions_at_gamma1[j], n_nodes))

    return {
        "csi_mean": float(np.mean(csi_values)),
        "csi_std": float(np.std(csi_values)),
        "csi_min": float(np.min(csi_values)),
        "csi_max": float(np.max(csi_values)),
        "seed_nvi_mean": float(np.mean(nvi_pairs)) if nvi_pairs else 0.0,
        "seed_nvi_std": float(np.std(nvi_pairs)) if nvi_pairs else 0.0,
        "n_seeds": n_seeds,
        "csi_values": csi_values,
    }


def community_descriptor_summary(g, **sweep_kwargs) -> dict:
    """Compute all D1 descriptors in one call."""
    sweep = resolution_sweep(g, **sweep_kwargs)
    return {
        "csi": community_stability_index(sweep),
        "fragmentation_onset": fragmentation_onset(sweep),
        "stability_variance": stability_variance(sweep),
        "n_communities_at_gamma_1": next(
            (r["n_communities"] for r in sweep if r["gamma"] >= 1.0), None
        ),
        "modularity_at_gamma_1": next(
            (r["modularity"] for r in sweep if r["gamma"] >= 1.0), None
        ),
        "sweep": sweep,
    }
