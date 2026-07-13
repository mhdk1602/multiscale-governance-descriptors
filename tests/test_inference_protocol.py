"""Tests for the reusable inference protocol.

The headline test reproduces, on synthetic data, the paper's central
diagnostic: a descriptor that is constant within architectural layers but
ordered across them produces a strong naive Spearman that COLLAPSES to a
p-value near 1.0 under layer-stratified permutation. That collapse is the
evidence that the dbt 'rho = -0.71' is between-layer architecture, not
within-layer governance.
"""
import numpy as np
import pytest

from governance_descriptors.inference_protocol import (
    degree_preserving_null,
    effective_distinct_values,
    layer_stratified_permutation,
    min_detectable_rho,
    permutation_spearman,
    run_family,
)
import networkx as nx


def _layered_design(per_tier=6, seed=0):
    """3 layers; descriptor is exactly constant within each layer and ordered
    across layers; target increases across layers. Mirrors the dbt rank
    degeneracy (3 effective descriptor values across n=18)."""
    rng = np.random.default_rng(seed)
    strata, descriptor, target = [], [], []
    for tier, dval in enumerate([0.0, 0.5, 1.0]):       # constant within tier
        for _ in range(per_tier):
            strata.append(tier)
            descriptor.append(dval)
            target.append(tier + 0.1 * rng.normal())     # ordered across tiers
    return (np.array(descriptor), np.array(target), np.array(strata))


def test_effective_distinct_values_flags_degeneracy():
    desc, _, _ = _layered_design()
    assert effective_distinct_values(desc) == 3          # 3 tiers across 18 obs


def test_naive_permutation_significant_but_stratified_collapses():
    desc, target, strata = _layered_design()
    rho_naive, p_naive, _ = permutation_spearman(desc, target, n_perms=2000, seed=1)
    rho_strat, p_strat, ndv = layer_stratified_permutation(
        desc, target, strata, n_perms=2000, seed=1
    )
    assert abs(rho_naive) > 0.7 and p_naive < 0.05        # naive looks strong
    assert ndv == 3
    assert p_strat > 0.9                                  # collapses: within-layer, nothing


def test_constant_input_is_non_evidence_not_minimum_p_value():
    rho, p_perm, p_param = permutation_spearman(
        np.ones(8), np.arange(8), n_perms=100, seed=1
    )
    assert np.isnan(rho)
    assert p_perm == 1.0
    assert p_param == 1.0

    rho_strat, p_strat, distinct = layer_stratified_permutation(
        np.ones(8), np.arange(8), np.repeat([0, 1], 4), n_perms=100, seed=1
    )
    assert np.isnan(rho_strat)
    assert p_strat == 1.0
    assert distinct == 1


def test_run_family_applies_fdr():
    desc, target, _ = _layered_design()
    rng = np.random.default_rng(3)
    noise = rng.normal(size=len(target))
    out = run_family(
        {"real": (desc, target), "noise": (noise, target)},
        n_perms=1000, seed=2,
    )
    assert set(out) == {"real", "noise"}
    assert all("bh_p" in v and "perm_p" in v for v in out.values())
    assert out["real"]["bh_p"] >= out["real"]["perm_p"]   # BH never shrinks p below raw


def test_degree_preserving_null_smoke():
    g = nx.barabasi_albert_graph(40, 2, seed=4)
    out = degree_preserving_null(g, lambda h: nx.transitivity(h), n_rewire=20, seed=4)
    assert out["n_null"] > 0
    assert np.isfinite(out["real"])


def test_min_detectable_rho_degeneracy_is_harder():
    """A 3-tier degenerate design needs a larger true rho to reach 80% power
    than a continuous design at the same n."""
    cont = min_detectable_rho(18, n_tiers=None, n_sim=600, seed=0)
    degen = min_detectable_rho(18, n_tiers=3, n_sim=600, seed=0)
    assert np.isfinite(cont)
    # degenerate threshold is at least as large (harder to detect), allowing
    # for simulation noise at the coarse 0.05 grid
    assert (not np.isfinite(degen)) or degen >= cont
