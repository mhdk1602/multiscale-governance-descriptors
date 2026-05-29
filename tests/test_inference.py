"""Unit tests for the small-n inference utilities.

These pin the inference protocol that is the paper's portable contribution:
permutation Spearman, Benjamini-Hochberg FDR, and partial Spearman. The
partial-correlation test encodes the layer-confound logic directly: a strong
raw correlation between two variables that are both driven by a third
(the architectural-layer analog) collapses once the confound is controlled.
"""
import numpy as np
import pytest

from governance_descriptors.stats_utils import (
    benjamini_hochberg,
    partial_spearman,
    permutation_spearman,
)


# --------------------------------------------------------------------------- #
# permutation_spearman
# --------------------------------------------------------------------------- #
def test_perm_spearman_monotonic_is_one():
    x = np.arange(20.0)
    y = 2.0 * x + 1.0                         # strictly monotone => rho = 1
    rho, perm_p, _ = permutation_spearman(x, y, n_perms=2000, seed=0)
    assert rho == pytest.approx(1.0)
    assert perm_p < 0.01


def test_perm_spearman_is_deterministic():
    rng = np.random.default_rng(123)
    x = rng.normal(size=30)
    y = rng.normal(size=30)
    a = permutation_spearman(x, y, n_perms=1000, seed=42)
    b = permutation_spearman(x, y, n_perms=1000, seed=42)
    assert a == b                              # same seed => byte-identical


def test_perm_spearman_independent_is_not_significant():
    rng = np.random.default_rng(7)
    x = rng.normal(size=40)
    y = rng.normal(size=40)
    rho, perm_p, _ = permutation_spearman(x, y, n_perms=2000, seed=1)
    assert perm_p > 0.05


def test_perm_spearman_too_few_points():
    rho, perm_p, p_param = permutation_spearman([1, 2], [1, 2], n_perms=100)
    assert np.isnan(rho) and perm_p == 1.0 and p_param == 1.0


# --------------------------------------------------------------------------- #
# benjamini_hochberg
# --------------------------------------------------------------------------- #
def test_bh_bounds_and_monotonicity():
    p = [0.001, 0.01, 0.02, 0.2, 0.5]
    adj = benjamini_hochberg(p)
    assert np.all(adj <= 1.0) and np.all(adj >= 0.0)
    # adjusted p-values are monotone non-decreasing in the original p-rank order
    order = np.argsort(p)
    assert np.all(np.diff(adj[order]) >= -1e-12)


def test_bh_known_small_case():
    # n=4, all raw p = 0.04 -> bh = 0.04 * 4 / rank; cummin from the top
    # ranks 1..4 give 0.16, 0.08, 0.0533, 0.04; cumulative min from right => 0.04 each
    adj = benjamini_hochberg([0.04, 0.04, 0.04, 0.04])
    assert np.allclose(adj, 0.04)


def test_bh_empty():
    assert len(benjamini_hochberg([])) == 0


# --------------------------------------------------------------------------- #
# partial_spearman: the layer-confound collapse, in code
# --------------------------------------------------------------------------- #
def test_partial_spearman_collapses_under_confound():
    """x and y are both generated from a shared 'layer' variable.

    Raw Spearman(x, y) is high; partialling out the layer drives it to ~0.
    This is the dbt result in miniature: D3 vs doc_rate looks strong until the
    architectural layer (the shared driver) is controlled.
    """
    rng = np.random.default_rng(2024)
    layer = rng.normal(size=60)
    x = layer + 0.05 * rng.normal(size=60)
    y = layer + 0.05 * rng.normal(size=60)

    raw_rho, raw_p, _ = permutation_spearman(x, y, n_perms=1000, seed=0)
    part_rho, part_p = partial_spearman(x, y, covariates=layer, n_perms=1000, seed=0)

    assert raw_rho > 0.8 and raw_p < 0.01            # strong raw association
    assert abs(part_rho) < 0.4                        # collapses once layer is controlled
    assert part_p > raw_p                             # and is far less significant


def test_partial_spearman_deterministic():
    rng = np.random.default_rng(9)
    x, y, c = rng.normal(size=40), rng.normal(size=40), rng.normal(size=40)
    a = partial_spearman(x, y, c, n_perms=500, seed=5)
    b = partial_spearman(x, y, c, n_perms=500, seed=5)
    assert a == b
