"""D2: Blast-radius concentration profile.

For DAGs: compute downstream reachability at each propagation depth,
then measure concentration via the Gini coefficient at each depth.

The Gini-vs-depth curve is novel (no published precedent per literature
review). Individual ingredients: Hu & Wang (2005) for Gini on networks,
Burkholz & Quackenbush (2021) for cascade size distributions.
"""
from __future__ import annotations

import numpy as np
import networkx as nx


def _gini(values) -> float:
    """Gini coefficient of a distribution. 0 = perfect equality, 1 = max inequality."""
    arr = np.array(values, dtype=float)
    if len(arr) == 0 or arr.sum() == 0:
        return 0.0
    arr = np.sort(arr)
    n = len(arr)
    index = np.arange(1, n + 1)
    return float((2 * np.sum(index * arr) - (n + 1) * np.sum(arr)) / (n * np.sum(arr)))


def blast_radius_at_depth(g: nx.DiGraph, node, max_depth: int) -> list[int]:
    """Count of reachable nodes at each depth d = 1, ..., max_depth.

    Returns list of length max_depth where entry i is the cumulative
    number of descendants reachable within i+1 hops.
    """
    cumulative = []
    reachable = set()
    frontier = {node}

    for d in range(max_depth):
        next_frontier = set()
        for n in frontier:
            for succ in g.successors(n):
                if succ not in reachable and succ != node:
                    next_frontier.add(succ)
        reachable |= next_frontier
        cumulative.append(len(reachable))
        frontier = next_frontier
        if not frontier:
            for _ in range(d + 1, max_depth):
                cumulative.append(len(reachable))
            break

    return cumulative


def gini_vs_depth(g: nx.DiGraph, max_depth: int = None) -> list[float]:
    """Gini coefficient of blast radius across all nodes, at each depth.

    Returns list of Gini values, one per depth level.
    """
    if not isinstance(g, nx.DiGraph):
        raise TypeError("gini_vs_depth requires a DiGraph")

    if max_depth is None:
        max_depth = nx.dag_longest_path_length(g) if nx.is_directed_acyclic_graph(g) else 10

    nodes = list(g.nodes())
    radius_matrix = np.zeros((len(nodes), max_depth))

    for i, node in enumerate(nodes):
        radii = blast_radius_at_depth(g, node, max_depth)
        radius_matrix[i, :len(radii)] = radii

    gini_curve = []
    for d in range(max_depth):
        gini_curve.append(_gini(radius_matrix[:, d]))

    return gini_curve


def concentration_transition_depth(gini_curve: list[float], threshold: float = 0.5) -> int:
    """Depth at which Gini first exceeds threshold.

    Returns 0-indexed depth, or -1 if never exceeded.
    """
    for d, g in enumerate(gini_curve):
        if g >= threshold:
            return d
    return -1


def topk_stability(g: nx.DiGraph, k: int = 5, max_depth: int = None) -> list[float]:
    """Jaccard similarity of top-k blast-radius nodes between consecutive depths.

    High stability = the riskiest nodes are consistent across scales.
    """
    if max_depth is None:
        max_depth = nx.dag_longest_path_length(g) if nx.is_directed_acyclic_graph(g) else 10

    nodes = list(g.nodes())
    radius_matrix = np.zeros((len(nodes), max_depth))
    for i, node in enumerate(nodes):
        radii = blast_radius_at_depth(g, node, max_depth)
        radius_matrix[i, :len(radii)] = radii

    stability = []
    prev_topk = None
    for d in range(max_depth):
        col = radius_matrix[:, d]
        topk_idx = set(np.argsort(col)[-k:])
        if prev_topk is not None:
            jaccard = len(topk_idx & prev_topk) / len(topk_idx | prev_topk) if (topk_idx | prev_topk) else 1.0
            stability.append(float(jaccard))
        prev_topk = topk_idx

    return stability


def concentration_profile(g: nx.DiGraph, max_depth: int = None, k: int = 5) -> dict:
    """Compute all D2 descriptors in one call."""
    gini_curve = gini_vs_depth(g, max_depth)
    return {
        "gini_curve": gini_curve,
        "concentration_transition_depth": concentration_transition_depth(gini_curve),
        "max_gini": max(gini_curve) if gini_curve else 0.0,
        "topk_stability": topk_stability(g, k=k, max_depth=max_depth),
    }
