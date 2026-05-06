"""D4: Persistent homology of the distance filtration.

Builds a Vietoris-Rips filtration from shortest-path distances and
computes persistent homology (H0: components, H1: cycles).

For DAGs: H1 features in the undirected version indicate redundant
paths (multiple routes from source to consumer). Persistent H1
features suggest structurally robust redundancy vs transient noise.

References:
    Otter et al. (2017), EPJ Data Science 6:17.
    Chowdhury & Memoli (2018), SODA, 1152-1169.
"""
from __future__ import annotations

import numpy as np
import networkx as nx
import gudhi


def _distance_matrix(g) -> np.ndarray:
    """Shortest-path distance matrix, treating the graph as undirected."""
    if isinstance(g, nx.DiGraph):
        g = g.to_undirected()
    if not nx.is_connected(g):
        giant = max(nx.connected_components(g), key=len)
        g = g.subgraph(giant).copy()

    nodes = list(g.nodes())
    n = len(nodes)
    node_idx = {v: i for i, v in enumerate(nodes)}
    dist = np.full((n, n), np.inf)
    np.fill_diagonal(dist, 0.0)

    lengths = dict(nx.all_pairs_shortest_path_length(g))
    for u, targets in lengths.items():
        i = node_idx[u]
        for v, d in targets.items():
            j = node_idx[v]
            dist[i, j] = d

    return dist


def persistence_diagrams(g, max_dimension: int = 1, max_edge_length: float = None) -> list[list[tuple[float, float]]]:
    """Compute persistence diagrams from shortest-path distance filtration.

    Returns list of diagrams, one per homology dimension (0..max_dimension).
    Each diagram is a list of (birth, death) tuples.
    """
    dist = _distance_matrix(g)

    if max_edge_length is None:
        finite_dists = dist[dist < np.inf]
        max_edge_length = float(finite_dists.max()) + 1.0 if len(finite_dists) > 0 else 10.0

    rips = gudhi.RipsComplex(distance_matrix=dist, max_edge_length=max_edge_length)
    st = rips.create_simplex_tree(max_dimension=max_dimension + 1)
    st.compute_persistence()

    diagrams = []
    for dim in range(max_dimension + 1):
        pairs = st.persistence_intervals_in_dimension(dim)
        diagram = [(float(b), float(d)) for b, d in pairs]
        diagrams.append(diagram)

    return diagrams


def persistence_entropy(diagram: list[tuple[float, float]]) -> float:
    """Shannon entropy of persistence bar lengths (normalized)."""
    lifetimes = np.array([d - b for b, d in diagram if d < np.inf and d > b])
    if len(lifetimes) == 0:
        return 0.0

    total = lifetimes.sum()
    if total == 0:
        return 0.0

    probs = lifetimes / total
    return float(-np.sum(probs * np.log2(probs + 1e-15)))


def total_persistence(diagram: list[tuple[float, float]], p: int = 1) -> float:
    """Sum of p-th power of bar lengths. Default p=1 (total lifetime)."""
    lifetimes = np.array([d - b for b, d in diagram if d < np.inf and d > b])
    if len(lifetimes) == 0:
        return 0.0
    return float(np.sum(lifetimes ** p))


def n_persistent_features(diagram: list[tuple[float, float]], threshold: str = "median") -> int:
    """Count of bars with persistence above threshold.

    threshold='median': bars longer than median lifetime.
    """
    lifetimes = np.array([d - b for b, d in diagram if d < np.inf and d > b])
    if len(lifetimes) == 0:
        return 0

    if threshold == "median":
        thresh_val = np.median(lifetimes)
    else:
        thresh_val = float(threshold)

    return int(np.sum(lifetimes > thresh_val))


def cycle_rank_descriptors(g) -> dict:
    """Simple cycle-rank baseline: M - N + C on the undirected skeleton."""
    u = g.to_undirected() if isinstance(g, nx.DiGraph) else g.copy()
    n = u.number_of_nodes()
    m = u.number_of_edges()
    c = nx.number_connected_components(u)
    cr = m - n + c
    return {
        "cycle_rank": cr,
        "cycle_rank_norm": cr / n if n > 0 else 0.0,
    }


def topological_descriptors(g, max_dimension: int = 1) -> dict:
    """Compute all D4 descriptors in one call."""
    diagrams = persistence_diagrams(g, max_dimension=max_dimension)

    h0 = diagrams[0] if len(diagrams) > 0 else []
    h1 = diagrams[1] if len(diagrams) > 1 else []

    return {
        "h0_persistence_entropy": persistence_entropy(h0),
        "h0_total_persistence": total_persistence(h0),
        "h0_n_persistent": n_persistent_features(h0),
        "h1_persistence_entropy": persistence_entropy(h1),
        "h1_total_persistence": total_persistence(h1),
        "h1_n_persistent": n_persistent_features(h1),
        "h0_n_bars": len(h0),
        "h1_n_bars": len(h1),
    }
