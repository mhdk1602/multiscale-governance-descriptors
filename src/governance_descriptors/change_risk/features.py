"""Change-level features for governance-moderated lineage risk.

Feature names encode their inferential role:

``baseline__``
    Cheap size, churn, degree, component, and blast-radius change statistics.
``governance__``
    Controls observed in the post-change manifest and their change from before.
``multiscale__``
    D1-D3 snapshot deltas. D4 is reported as cycle rank because the existing
    real-data experiment showed that persistent H1 collapsed to that quantity.
``change_geometry__``
    Pre-outcome, change-centred multiscale summaries of directed ball growth,
    affected-subgraph geometry, and community-boundary crossing.

That naming makes the primary incremental-value test mechanical rather than a
researcher-selected feature comparison after looking at outcomes.
"""
from __future__ import annotations

from collections import Counter
import math
from typing import Iterable

import networkx as nx
import numpy as np

from governance_descriptors.blast_radius import blast_radius_at_depth, gini_vs_depth
from governance_descriptors.community_stability import (
    community_stability_index,
    resolution_sweep,
)
from governance_descriptors.persistent_homology import cycle_rank_descriptors
from governance_descriptors.spectral import spectral_descriptors

from .manifest import ManifestSnapshot


FEATURE_GROUP_PREFIXES = {
    "baseline": "baseline__",
    "governance": "governance__",
    "multiscale": "multiscale__",
    "change_geometry": "change_geometry__",
}


def select_feature_columns(columns: Iterable[str], groups: Iterable[str]) -> list[str]:
    """Select columns belonging to preregistered feature groups."""

    prefixes = tuple(FEATURE_GROUP_PREFIXES[group] for group in groups)
    return sorted(column for column in columns if column.startswith(prefixes))


def _ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _degree_distribution(graph: nx.DiGraph) -> np.ndarray:
    degrees = [degree for _, degree in graph.degree()]
    if not degrees:
        return np.array([1.0])
    counts = np.bincount(degrees).astype(float)
    return counts / counts.sum()


def _jensen_shannon(left: np.ndarray, right: np.ndarray) -> float:
    width = max(len(left), len(right))
    p = np.pad(left, (0, width - len(left)))
    q = np.pad(right, (0, width - len(right)))
    midpoint = 0.5 * (p + q)

    def kl(first, second):
        mask = first > 0
        return float(np.sum(first[mask] * np.log2(first[mask] / second[mask])))

    return math.sqrt(max(0.0, 0.5 * kl(p, midpoint) + 0.5 * kl(q, midpoint)))


def _largest_weak_component(graph: nx.DiGraph) -> nx.DiGraph:
    if graph.number_of_nodes() == 0:
        return graph.copy()
    components = list(nx.weakly_connected_components(graph))
    return graph.subgraph(max(components, key=len)).copy()


def _longest_path(graph: nx.DiGraph) -> int:
    if graph.number_of_nodes() == 0:
        return 0
    if nx.is_directed_acyclic_graph(graph):
        return int(nx.dag_longest_path_length(graph))
    return -1


def _changed_descendants(graph: nx.DiGraph, nodes: set[str]) -> tuple[int, int, float]:
    per_node = []
    union: set[str] = set()
    for node in nodes:
        if node not in graph:
            continue
        descendants = nx.descendants(graph, node)
        per_node.append(len(descendants))
        union.update(descendants)
    return (
        len(union),
        max(per_node, default=0),
        float(np.mean(per_node)) if per_node else 0.0,
    )


def _resource_counts(graph: nx.DiGraph) -> Counter:
    return Counter(str(data.get("resource_type") or "unknown") for _, data in graph.nodes(data=True))


def _snapshot_multiscale(graph: nx.DiGraph, max_depth: int, d1_steps: int) -> dict[str, float]:
    """Compute stable scalar summaries with explicit small-graph fallbacks."""

    largest = _largest_weak_component(graph)
    n_nodes = largest.number_of_nodes()
    n_edges = largest.number_of_edges()
    out = {
        "d1_csi": 0.0,
        "d1_modularity_gamma1": 0.0,
        "d2_gini_auc": 0.0,
        "d2_gini_depth1": 0.0,
        "d2_gini_depth_max": 0.0,
        "d3_normalized_gap": 0.0,
        "d3_spectral_entropy": 0.0,
        "d3_fiedler_bimodality": 0.0,
        "d4_cycle_rank_norm": 0.0,
    }
    if n_nodes == 0:
        return out

    cycle = cycle_rank_descriptors(largest)
    out["d4_cycle_rank_norm"] = float(cycle["cycle_rank_norm"])

    if n_edges:
        depth = max(1, min(max_depth, n_nodes - 1))
        curve = gini_vs_depth(largest, max_depth=depth)
        if curve:
            out["d2_gini_auc"] = float(np.mean(curve))
            out["d2_gini_depth1"] = float(curve[0])
            out["d2_gini_depth_max"] = float(curve[-1])

    if n_nodes >= 3 and n_edges >= 2:
        sweep = resolution_sweep(
            largest,
            gamma_min=0.25,
            gamma_max=4.0,
            n_steps=d1_steps,
            seed=42,
        )
        out["d1_csi"] = float(community_stability_index(sweep))
        gamma_one = min(sweep, key=lambda row: abs(row["gamma"] - 1.0))
        out["d1_modularity_gamma1"] = float(gamma_one["modularity"])

        spectral = spectral_descriptors(largest)
        out["d3_normalized_gap"] = float(spectral["normalized_spectral_gap"])
        out["d3_spectral_entropy"] = float(spectral["spectral_entropy"])
        out["d3_fiedler_bimodality"] = float(spectral["fiedler_bimodality"])
    return out


def _max_depth_blast_radius(graph: nx.DiGraph, nodes: set[str], max_depth: int) -> int:
    values = []
    for node in nodes:
        if node in graph:
            radii = blast_radius_at_depth(graph, node, max_depth)
            values.append(radii[-1] if radii else 0)
    return max(values, default=0)


def _directed_ball_profile(
    graph: nx.DiGraph,
    seeds: set[str],
    max_depth: int,
) -> tuple[list[int], set[str]]:
    """Return cumulative downstream ball sizes from radius zero to max_depth."""

    reached = {node for node in seeds if node in graph}
    frontier = set(reached)
    profile = [len(reached)]
    for _ in range(max_depth):
        next_frontier = {
            successor
            for node in frontier
            for successor in graph.successors(node)
            if successor not in reached
        }
        reached.update(next_frontier)
        frontier = next_frontier
        profile.append(len(reached))
    return profile, reached


def _ball_growth_exponent(profile: list[int]) -> tuple[float, float]:
    """Estimate log-ball growth over the fixed positive-radius scale range."""

    if len(profile) < 3 or profile[0] == 0:
        return 0.0, 0.0
    radii = np.arange(1, len(profile), dtype=float)
    counts = np.asarray(profile[1:], dtype=float)
    design = np.column_stack([np.log(radii), np.ones(len(radii))])
    slope, intercept = np.linalg.lstsq(design, np.log(counts), rcond=None)[0]
    fitted = design @ np.array([slope, intercept])
    observed = np.log(counts)
    total = float(np.sum((observed - observed.mean()) ** 2))
    residual = float(np.sum((observed - fitted) ** 2))
    r_squared = 1.0 - residual / total if total > 0 else 0.0
    return float(max(0.0, slope)), float(max(0.0, min(1.0, r_squared)))


def _affected_conductance(graph: nx.DiGraph, affected: set[str]) -> float:
    undirected = graph.to_undirected()
    affected = set(affected) & set(undirected)
    complement = set(undirected) - affected
    if not affected or not complement:
        return 0.0
    cut_edges = sum(1 for left, right in undirected.edges() if (left in affected) != (right in affected))
    affected_volume = sum(dict(undirected.degree(affected)).values())
    complement_volume = sum(dict(undirected.degree(complement)).values())
    denominator = min(affected_volume, complement_volume)
    return _ratio(cut_edges, denominator)


def _community_boundary_spectrum(
    graph: nx.DiGraph,
    affected: set[str],
    resolutions: tuple[float, ...] = (0.5, 1.0, 2.0),
) -> tuple[float, float]:
    """Summarize affected-edge boundary crossing over fixed resolutions."""

    undirected = graph.to_undirected()
    affected_graph = undirected.subgraph(set(affected) & set(undirected))
    if undirected.number_of_edges() == 0 or affected_graph.number_of_edges() == 0:
        return 0.0, 0.0
    fractions = []
    for resolution in resolutions:
        communities = nx.community.louvain_communities(
            undirected,
            resolution=resolution,
            seed=42,
        )
        membership = {
            node: community_index
            for community_index, community in enumerate(communities)
            for node in community
        }
        crossings = sum(
            membership[left] != membership[right]
            for left, right in affected_graph.edges()
        )
        fractions.append(_ratio(crossings, affected_graph.number_of_edges()))
    return float(np.mean(fractions)), float(max(fractions) - min(fractions))


def _change_centred_geometry(
    graph: nx.DiGraph,
    seeds: set[str],
    max_depth: int,
) -> dict[str, float]:
    """Compute local multiscale geometry around a fixed set of changed nodes."""

    profile, affected = _directed_ball_profile(graph, seeds, max_depth)
    exponent, fit_r_squared = _ball_growth_exponent(profile)
    n_nodes = graph.number_of_nodes()
    positive_radius = profile[1:]
    final_size = profile[-1] if profile else 0
    threshold = 0.95 * final_size
    saturation_radius = next(
        (radius for radius, size in enumerate(profile) if size >= threshold),
        max_depth,
    ) if final_size else 0
    affected_graph = graph.subgraph(affected).copy()
    cycle = cycle_rank_descriptors(affected_graph) if affected else {"cycle_rank_norm": 0.0}
    boundary_mean, boundary_range = _community_boundary_spectrum(graph, affected)
    return {
        "ball_growth_exponent": exponent,
        "ball_growth_fit_r2": fit_r_squared,
        "ball_growth_auc_norm": (
            float(np.mean(positive_radius)) / n_nodes
            if positive_radius and n_nodes else 0.0
        ),
        "saturation_depth_norm": _ratio(saturation_radius, max_depth),
        "affected_conductance": _affected_conductance(graph, affected),
        "affected_cycle_rank_norm": float(cycle["cycle_rank_norm"]),
        "community_boundary_crossing_mean": boundary_mean,
        "community_boundary_crossing_range": boundary_range,
    }


def extract_change_features(
    before: ManifestSnapshot,
    after: ManifestSnapshot,
    *,
    max_depth: int = 5,
    d1_steps: int = 8,
) -> dict[str, float | int]:
    """Construct preregistered baseline, control, and multiscale features."""

    left = before.graph
    right = after.graph
    left_nodes = set(left)
    right_nodes = set(right)
    added_nodes = right_nodes - left_nodes
    removed_nodes = left_nodes - right_nodes
    shared_nodes = left_nodes & right_nodes
    modified_nodes = {
        node
        for node in shared_nodes
        if before.fingerprints.get(node) != after.fingerprints.get(node)
    }
    changed_nodes = added_nodes | removed_nodes | modified_nodes

    left_edges = set(left.edges())
    right_edges = set(right.edges())
    added_edges = right_edges - left_edges
    removed_edges = left_edges - right_edges
    union_edges = left_edges | right_edges

    descendants_after, max_desc_after, mean_desc_after = _changed_descendants(
        right, added_nodes | modified_nodes
    )
    descendants_before, max_desc_before, mean_desc_before = _changed_descendants(
        left, removed_nodes | modified_nodes
    )
    left_components = nx.number_weakly_connected_components(left) if left_nodes else 0
    right_components = nx.number_weakly_connected_components(right) if right_nodes else 0
    left_types = _resource_counts(left)
    right_types = _resource_counts(right)

    features: dict[str, float | int] = {
        "baseline__nodes_before": len(left_nodes),
        "baseline__nodes_after": len(right_nodes),
        "baseline__node_delta": len(right_nodes) - len(left_nodes),
        "baseline__nodes_added": len(added_nodes),
        "baseline__nodes_removed": len(removed_nodes),
        "baseline__nodes_modified": len(modified_nodes),
        "baseline__changed_node_fraction": _ratio(len(changed_nodes), len(left_nodes | right_nodes)),
        "baseline__edges_before": len(left_edges),
        "baseline__edges_after": len(right_edges),
        "baseline__edge_delta": len(right_edges) - len(left_edges),
        "baseline__edges_added": len(added_edges),
        "baseline__edges_removed": len(removed_edges),
        "baseline__edge_edit_fraction": _ratio(len(added_edges) + len(removed_edges), len(union_edges)),
        "baseline__degree_js_distance": _jensen_shannon(
            _degree_distribution(left), _degree_distribution(right)
        ),
        "baseline__component_delta": right_components - left_components,
        "baseline__longest_path_delta": _longest_path(right) - _longest_path(left),
        "baseline__changed_descendants_after": descendants_after,
        "baseline__changed_descendants_before": descendants_before,
        "baseline__changed_descendant_fraction_after": _ratio(descendants_after, len(right_nodes)),
        "baseline__changed_descendant_fraction_before": _ratio(descendants_before, len(left_nodes)),
        "baseline__max_changed_descendants_after": max_desc_after,
        "baseline__max_changed_descendants_before": max_desc_before,
        "baseline__mean_changed_descendants_after": mean_desc_after,
        "baseline__mean_changed_descendants_before": mean_desc_before,
        "baseline__max_changed_blast_radius_after": _max_depth_blast_radius(
            right, added_nodes | modified_nodes, max_depth
        ),
        "baseline__max_changed_blast_radius_before": _max_depth_blast_radius(
            left, removed_nodes | modified_nodes, max_depth
        ),
    }

    for resource_type in sorted(set(left_types) | set(right_types)):
        features[f"baseline__resource_delta__{resource_type}"] = (
            right_types[resource_type] - left_types[resource_type]
        )

    for control in sorted(set(before.governance) | set(after.governance)):
        before_value = float(before.governance.get(control, 0.0))
        after_value = float(after.governance.get(control, 0.0))
        features[f"governance__after__{control}"] = after_value
        features[f"governance__delta__{control}"] = after_value - before_value
        features[f"governance__interaction__blast_fraction_x_{control}"] = (
            features["baseline__changed_descendant_fraction_after"] * after_value
        )

    left_multiscale = _snapshot_multiscale(left, max_depth=max_depth, d1_steps=d1_steps)
    right_multiscale = _snapshot_multiscale(right, max_depth=max_depth, d1_steps=d1_steps)
    for descriptor in sorted(left_multiscale):
        features[f"multiscale__before__{descriptor}"] = left_multiscale[descriptor]
        features[f"multiscale__after__{descriptor}"] = right_multiscale[descriptor]
        features[f"multiscale__delta__{descriptor}"] = (
            right_multiscale[descriptor] - left_multiscale[descriptor]
        )

    left_geometry = _change_centred_geometry(
        left,
        removed_nodes | modified_nodes,
        max_depth=max_depth,
    )
    right_geometry = _change_centred_geometry(
        right,
        added_nodes | modified_nodes,
        max_depth=max_depth,
    )
    for descriptor in sorted(left_geometry):
        features[f"change_geometry__before__{descriptor}"] = left_geometry[descriptor]
        features[f"change_geometry__after__{descriptor}"] = right_geometry[descriptor]
        features[f"change_geometry__delta__{descriptor}"] = (
            right_geometry[descriptor] - left_geometry[descriptor]
        )

    return features
