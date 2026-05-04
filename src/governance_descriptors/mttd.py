"""Mean-Time-to-Detect (MTTD) simulation on lineage DAGs.

Simulates incident propagation: a defect injected at a source node
propagates downstream. Monitoring nodes detect the defect when it
reaches them. MTTD = propagation depth at first detection.

Monitor placement strategies:
- stewardship: monitors on nodes with assigned stewards (governance metadata)
- betweenness_topk: monitors on the k nodes with highest betweenness centrality
- random: monitors placed uniformly at random
- blast_radius_topk: monitors on k nodes with highest downstream reachability
"""
from __future__ import annotations

import numpy as np
import networkx as nx


def _downstream_at_depth(g: nx.DiGraph, source, max_depth: int) -> list[set]:
    """Return list of sets: nodes reachable at exactly depth d (d=0 is {source})."""
    layers = [{source}]
    visited = {source}
    for d in range(max_depth):
        frontier = set()
        for n in layers[-1]:
            for succ in g.successors(n):
                if succ not in visited:
                    frontier.add(succ)
                    visited.add(succ)
        layers.append(frontier)
        if not frontier:
            break
    return layers


def place_monitors_stewardship(g: nx.DiGraph, fraction: float = 0.2, seed: int = 42) -> set:
    """Place monitors on nodes marked as stewarded. If no stewardship metadata,
    place on a fraction of mart/exposure layer nodes."""
    stewarded = {n for n, d in g.nodes(data=True) if d.get("stewarded", False)}
    if stewarded:
        return stewarded

    rng = np.random.default_rng(seed)
    candidates = [n for n, d in g.nodes(data=True) if d.get("layer") in ("mart", "exposure")]
    if not candidates:
        candidates = list(g.nodes())
    k = max(1, int(len(candidates) * fraction))
    return set(rng.choice(candidates, size=min(k, len(candidates)), replace=False))


def place_monitors_betweenness(g: nx.DiGraph, k: int = 5) -> set:
    """Place monitors on the k nodes with highest betweenness centrality."""
    bc = nx.betweenness_centrality(g)
    sorted_nodes = sorted(bc, key=bc.get, reverse=True)
    return set(sorted_nodes[:k])


def place_monitors_blast_radius(g: nx.DiGraph, k: int = 5) -> set:
    """Place monitors on k nodes with highest downstream reachability."""
    reach = {n: len(nx.descendants(g, n)) for n in g.nodes()}
    sorted_nodes = sorted(reach, key=reach.get, reverse=True)
    return set(sorted_nodes[:k])


def place_monitors_random(g: nx.DiGraph, k: int = 5, seed: int = 42) -> set:
    """Place monitors uniformly at random."""
    rng = np.random.default_rng(seed)
    nodes = list(g.nodes())
    return set(rng.choice(nodes, size=min(k, len(nodes)), replace=False))


def simulate_mttd(
    g: nx.DiGraph,
    source_node,
    monitors: set,
    max_depth: int = None,
) -> int:
    """Simulate defect propagation from source_node. Return depth at first detection.

    Returns max_depth + 1 if defect is never detected (no monitor reachable).
    """
    if max_depth is None:
        if nx.is_directed_acyclic_graph(g):
            max_depth = nx.dag_longest_path_length(g)
        else:
            max_depth = 10

    layers = _downstream_at_depth(g, source_node, max_depth)

    for depth, layer in enumerate(layers):
        if layer & monitors:
            return depth

    return max_depth + 1


def mttd_distribution(
    g: nx.DiGraph,
    monitors: set,
    source_nodes: list = None,
    max_depth: int = None,
) -> dict:
    """Compute MTTD for each source node. Return summary statistics."""
    if source_nodes is None:
        source_nodes = [n for n, d in g.nodes(data=True) if d.get("layer") == "source"]
        if not source_nodes:
            source_nodes = [n for n in g.nodes() if g.in_degree(n) == 0]

    mttds = []
    for src in source_nodes:
        mttd = simulate_mttd(g, src, monitors, max_depth)
        mttds.append(mttd)

    mttds = np.array(mttds, dtype=float)
    return {
        "mean_mttd": float(np.mean(mttds)),
        "median_mttd": float(np.median(mttds)),
        "max_mttd": float(np.max(mttds)),
        "std_mttd": float(np.std(mttds)),
        "n_undetected": int(np.sum(mttds > (max_depth or 10))),
        "n_sources": len(source_nodes),
        "mttds": mttds.tolist(),
    }
