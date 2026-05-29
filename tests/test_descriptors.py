"""Unit tests for the four structural descriptors (D1-D4).

These tests pin the descriptors to graphs whose values are known analytically,
so a refactor that silently changes a computation fails loudly. They also
encode, in code, the paper's central methodological finding: D4's persistent-H1
count collapses to the cycle rank beta_1 = M - N + C on lineage-like graphs,
so D4 carries no information beyond the far simpler cycle-rank baseline.

Run: python -m pytest tests/ -q
"""
import math

import networkx as nx
import pytest

from governance_descriptors.blast_radius import _gini, concentration_profile, gini_vs_depth
from governance_descriptors.persistent_homology import (
    cycle_rank_descriptors,
    topological_descriptors,
)
from governance_descriptors.spectral import spectral_descriptors, algebraic_connectivity
from governance_descriptors.community_stability import (
    community_stability_index,
    community_stability_index_multiseed,
    resolution_sweep,
)


# --------------------------------------------------------------------------- #
# Fixtures: graphs with known structure
# --------------------------------------------------------------------------- #
def path_digraph(n):
    """0 -> 1 -> ... -> (n-1). A tree: cycle rank 0."""
    return nx.DiGraph((i, i + 1) for i in range(n - 1))


def cycle_graph_undirected(n):
    """Undirected n-cycle. beta_1 = 1."""
    return nx.cycle_graph(n)


def out_star_digraph(k):
    """Root 0 -> each of k leaves. Concentrated blast radius at the root."""
    return nx.DiGraph((0, i) for i in range(1, k + 1))


def two_squares_sharing_a_node():
    """Two 4-cycles sharing node 0 (a connected 'figure-eight'). beta_1 = 2.

    7 nodes, 8 edges, 1 component => cycle rank = 8 - 7 + 1 = 2.
    """
    g = nx.Graph()
    g.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0)])      # square A
    g.add_edges_from([(0, 4), (4, 5), (5, 6), (6, 0)])      # square B
    return g


# --------------------------------------------------------------------------- #
# D2: blast-radius Gini concentration
# --------------------------------------------------------------------------- #
def test_gini_equality_is_zero():
    assert _gini([1, 1, 1, 1]) == pytest.approx(0.0)
    assert _gini([5, 5, 5]) == pytest.approx(0.0)


def test_gini_known_value():
    # sorted [0,0,0,4], n=4: (2*(4*4) - 5*4) / (4*4) = (32-20)/16 = 0.75
    assert _gini([0, 0, 0, 4]) == pytest.approx(0.75)


def test_gini_empty_and_zero_sum():
    assert _gini([]) == 0.0
    assert _gini([0, 0, 0]) == 0.0


def test_blast_radius_bounds_and_monotone_depth():
    g = out_star_digraph(6)            # root reaches 6 leaves at depth 1
    prof = concentration_profile(g)
    assert 0.0 <= prof["max_gini"] <= 1.0
    curve = gini_vs_depth(g)
    assert all(0.0 <= v <= 1.0 for v in curve)


def test_blast_radius_requires_digraph():
    with pytest.raises(TypeError):
        gini_vs_depth(nx.Graph([(0, 1)]))


# --------------------------------------------------------------------------- #
# D4: persistent homology and the cycle-rank collapse (the paper's key finding)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("n,expected_cr", [(3, 0), (5, 0), (10, 0)])
def test_cycle_rank_zero_on_trees(n, expected_cr):
    cr = cycle_rank_descriptors(path_digraph(n))
    assert cr["cycle_rank"] == expected_cr
    assert cr["cycle_rank_norm"] == pytest.approx(expected_cr / n)


@pytest.mark.parametrize("n", [4, 5, 6, 8])
def test_cycle_rank_single_cycle(n):
    cr = cycle_rank_descriptors(cycle_graph_undirected(n))
    assert cr["cycle_rank"] == 1                     # M - N + C = n - n + 1
    assert cr["cycle_rank_norm"] == pytest.approx(1 / n)


def test_cycle_rank_two_independent_cycles():
    g = two_squares_sharing_a_node()
    cr = cycle_rank_descriptors(g)
    assert cr["cycle_rank"] == 2                     # 8 - 7 + 1


def test_d4_h1_bars_equal_cycle_rank_on_single_cycle():
    """The collapse, in code: H1 bar count == beta_1 on a clean cycle.

    A k-cycle (k>=4) has one undirected independent cycle; its persistent-H1
    diagram has exactly one finite bar (born when edges appear, dies when the
    interior fills). This is identically the cycle rank.
    """
    for n in (4, 5, 6):
        g = cycle_graph_undirected(n)
        td = topological_descriptors(g)
        cr = cycle_rank_descriptors(g)
        assert td["h1_n_bars"] == cr["cycle_rank"] == 1


def test_d4_h1_bars_equal_cycle_rank_on_two_cycles():
    g = two_squares_sharing_a_node()
    td = topological_descriptors(g)
    cr = cycle_rank_descriptors(g)
    assert td["h1_n_bars"] == cr["cycle_rank"] == 2


def test_d4_no_h1_on_a_tree():
    g = nx.balanced_tree(2, 3)        # a tree: no cycles
    td = topological_descriptors(g)
    cr = cycle_rank_descriptors(g)
    assert td["h1_n_bars"] == 0
    assert cr["cycle_rank"] == 0


# --------------------------------------------------------------------------- #
# D3: spectral gap / algebraic connectivity (closed-form Laplacian spectra)
# --------------------------------------------------------------------------- #
def test_spectral_C4_closed_form():
    # C_4 combinatorial Laplacian eigenvalues {0, 2, 2, 4}
    sd = spectral_descriptors(nx.cycle_graph(4))
    assert sd["algebraic_connectivity"] == pytest.approx(2.0, abs=1e-6)
    assert sd["lambda_max"] == pytest.approx(4.0, abs=1e-6)
    assert sd["normalized_spectral_gap"] == pytest.approx(0.5, abs=1e-6)


def test_spectral_K3_closed_form():
    # K_3 Laplacian eigenvalues {0, 3, 3}
    sd = spectral_descriptors(nx.complete_graph(3))
    assert sd["algebraic_connectivity"] == pytest.approx(3.0, abs=1e-6)
    assert sd["normalized_spectral_gap"] == pytest.approx(1.0, abs=1e-6)


def test_spectral_P3_closed_form():
    # path a-b-c Laplacian eigenvalues {0, 1, 3}
    sd = spectral_descriptors(nx.path_graph(3))
    assert sd["algebraic_connectivity"] == pytest.approx(1.0, abs=1e-6)
    assert sd["normalized_spectral_gap"] == pytest.approx(1.0 / 3.0, abs=1e-6)


def test_algebraic_connectivity_helper_matches_summary():
    g = nx.cycle_graph(6)
    assert algebraic_connectivity(g) == pytest.approx(
        spectral_descriptors(g)["algebraic_connectivity"], abs=1e-6
    )


# --------------------------------------------------------------------------- #
# D1: community stability index (determinism, bounds, structure sanity)
# --------------------------------------------------------------------------- #
def clustered_graph():
    """Two 6-cliques joined by a single bridge edge: crisp two-community structure."""
    g = nx.disjoint_union(nx.complete_graph(6), nx.complete_graph(6))
    g.add_edge(0, 6)
    return g


def test_csi_in_unit_interval():
    sweep = resolution_sweep(clustered_graph(), seed=42)
    csi = community_stability_index(sweep)
    assert 0.0 <= csi <= 1.0


def test_csi_deterministic_given_seed():
    g = clustered_graph()
    a = community_stability_index(resolution_sweep(g, seed=7))
    b = community_stability_index(resolution_sweep(g, seed=7))
    assert a == b


def test_csi_multiseed_reports_variance_structure():
    out = community_stability_index_multiseed(clustered_graph(), n_seeds=5)
    assert 0.0 <= out["csi_mean"] <= 1.0
    assert out["csi_std"] >= 0.0
    assert out["csi_min"] <= out["csi_mean"] <= out["csi_max"]
    assert out["n_seeds"] == 5
