"""A reusable inference protocol for small-n graph-descriptor correlation studies.

This module is the paper's portable methodological contribution, packaged so it
can be cited and reused independently of the lineage-governance application. It
collects the checks that distinguish a real structure-vs-attribute relationship
from one manufactured by rank degeneracy, a confounding partition (architectural
layer), or optimizer stochasticity, in the regime where the unit of analysis is
a handful of graph-level or domain-level observations (n ~ 10-30).

The motivating failure mode: a graph descriptor (e.g. the spectral gap) correlates
strongly with an attribute (e.g. documentation rate) at face value, but the
descriptor takes only a few distinct values across the sample (it is constant
within architectural layers), so the "correlation" is a between-layer ordering,
not a within-layer relationship. The protocol below makes that distinction
testable.

Checklist:
  1. permutation_spearman      -- exact-ish p without normality, robust to ties
  2. benjamini_hochberg        -- FDR control across an explicit hypothesis family
  3. partial_spearman          -- control a continuous confound (re-exported)
  4. layer_stratified_permutation -- permute WITHIN strata only; kills between-
                                  layer ordering effects (the central test)
  5. degree_preserving_null    -- is the descriptor value surprising vs a
                                  degree-matched random graph?
  6. min_detectable_rho        -- rank-degeneracy-aware power analysis: what
                                  effect size could this design even detect?

References
----------
Benjamini & Hochberg (1995), JRSS-B 57(1):289-300.
Good (2005), Permutation, Parametric, and Bootstrap Tests of Hypotheses, Springer.
Maslov & Sneppen (2002), Science 296:910-913 (degree-preserving rewiring).
Fortunato & Barthelemy (2007), PNAS 104(1):36-41 (Louvain resolution limit).
"""
from __future__ import annotations

import numpy as np
import networkx as nx
from scipy import stats

# Re-export the primitives so callers import one module.
from .stats_utils import permutation_spearman, benjamini_hochberg, partial_spearman

__all__ = [
    "permutation_spearman",
    "benjamini_hochberg",
    "partial_spearman",
    "layer_stratified_permutation",
    "degree_preserving_null",
    "min_detectable_rho",
    "effective_distinct_values",
    "run_family",
]


def effective_distinct_values(x, tol: float = 1e-9) -> int:
    """Number of distinct values in x (within tol).

    A small count relative to n is the rank-degeneracy red flag: a "correlation"
    over k distinct descriptor values across n >> k observations is, at most, a
    k-tier ordering test, not a continuous association.
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return 0
    return int(len(np.unique(np.round(x / tol) * tol)))


def layer_stratified_permutation(
    descriptor, target, strata, n_perms: int = 10_000, seed: int = 42
):
    """Spearman with permutation restricted to WITHIN-stratum reshuffles.

    The plain permutation test shuffles `target` against `descriptor` freely,
    so any between-stratum ordering (e.g. source vs silver vs gold layers, each
    with a near-constant descriptor value) inflates significance. Restricting
    permutations to within-stratum reshuffles removes the between-layer signal
    and asks the sharper question: within layers of equal architecture, does the
    descriptor still track the target?

    When the descriptor is (near-)constant within each stratum, the observed
    statistic is essentially unbeatable under within-stratum permutation, so the
    p-value approaches 1.0 -- the diagnostic that the effect is purely
    between-layer architecture, not within-layer governance.

    Returns (rho_obs, perm_p, n_distinct_descriptor_values).
    """
    descriptor = np.asarray(descriptor, dtype=float)
    target = np.asarray(target, dtype=float)
    strata = np.asarray(strata)
    mask = np.isfinite(descriptor) & np.isfinite(target)
    descriptor, target, strata = descriptor[mask], target[mask], strata[mask]
    if len(descriptor) < 4:
        return (np.nan, 1.0, effective_distinct_values(descriptor))
    if len(np.unique(descriptor)) < 2 or len(np.unique(target)) < 2:
        return (np.nan, 1.0, effective_distinct_values(descriptor))

    rho_obs, _ = stats.spearmanr(descriptor, target)
    rng = np.random.default_rng(seed)

    # Precompute within-stratum index groups.
    groups = [np.where(strata == s)[0] for s in np.unique(strata)]

    count = 0
    for _ in range(n_perms):
        permuted = target.copy()
        for idx in groups:
            if len(idx) > 1:
                permuted[idx] = rng.permutation(target[idx])
        rho_perm, _ = stats.spearmanr(descriptor, permuted)
        if abs(rho_perm) >= abs(rho_obs) - 1e-12:
            count += 1
    perm_p = (count + 1) / (n_perms + 1)
    return (float(rho_obs), float(perm_p), effective_distinct_values(descriptor))


def degree_preserving_null(
    g, descriptor_fn, n_rewire: int = 100, n_swaps: int | None = None, seed: int = 42
) -> dict:
    """Z-score of a graph descriptor vs a degree-preserving random ensemble.

    Generates `n_rewire` graphs by double-edge swaps that preserve the degree
    sequence (Maslov-Sneppen), computes descriptor_fn on each, and reports where
    the real value sits in that null distribution.

    A large |z| is necessary but NOT sufficient for a structural claim: for a
    sparse layered DAG, gross topology (near-bipartite layering) differs so much
    from a degree-matched rewiring that some descriptors (e.g. Fiedler
    bimodality) are near-tautologically extreme. Report z alongside an honest
    note on whether the null is an appropriate comparison.

    Returns dict with real value, null mean/std, z, and the null sample.
    """
    g = g.to_undirected() if isinstance(g, nx.DiGraph) else g
    real = float(descriptor_fn(g))
    m = g.number_of_edges()
    if n_swaps is None:
        n_swaps = 10 * m
    rng = np.random.RandomState(seed)
    null_vals = []
    for i in range(n_rewire):
        h = g.copy()
        try:
            nx.double_edge_swap(h, nswap=n_swaps, max_tries=n_swaps * 20, seed=rng)
        except (nx.NetworkXError, nx.NetworkXAlgorithmError):
            pass
        try:
            null_vals.append(float(descriptor_fn(h)))
        except Exception:
            continue
    null_vals = np.array(null_vals, dtype=float)
    null_vals = null_vals[np.isfinite(null_vals)]
    mu = float(null_vals.mean()) if len(null_vals) else np.nan
    sd = float(null_vals.std(ddof=1)) if len(null_vals) > 1 else np.nan
    z = (real - mu) / sd if sd and sd > 0 else np.nan
    return {"real": real, "null_mean": mu, "null_std": sd, "z": float(z),
            "n_null": int(len(null_vals)), "null_values": null_vals.tolist()}


def min_detectable_rho(
    n: int, n_tiers: int | None = None, power: float = 0.8,
    alpha: float = 0.05, n_sim: int = 2000, seed: int = 42,
) -> float:
    """Smallest |rho| detectable at given power for this design, by simulation.

    Accounts for rank degeneracy: if the descriptor takes only `n_tiers`
    distinct values (tie structure), the achievable power at fixed n is lower
    than the continuous-data benchmark. Simulates data at a target rho, applies
    the tie structure, runs a permutation Spearman, and searches for the
    smallest rho whose empirical power reaches `power`.

    With n_tiers=None the descriptor is treated as continuous (the optimistic
    bound). Pass the observed `effective_distinct_values` to get the realistic
    bound for a degenerate design.

    Returns the minimum detectable |rho| (np.nan if even rho->1 cannot reach the
    target power, which itself is an informative answer).
    """
    rng = np.random.default_rng(seed)

    def _tie(x):
        if n_tiers is None or n_tiers >= n:
            return x
        # bin into n_tiers quantile tiers, replace with tier rank (induces ties)
        ranks = stats.rankdata(x)
        tiers = np.ceil(ranks / n * n_tiers)
        return tiers

    def _power_at(rho):
        hits = 0
        for _ in range(n_sim // 5):                      # lighter inner loop
            z1 = rng.normal(size=n)
            z2 = rho * z1 + np.sqrt(max(1 - rho ** 2, 0)) * rng.normal(size=n)
            xd = _tie(z1)
            r_obs, p = stats.spearmanr(xd, z2)
            if p < alpha:
                hits += 1
        return hits / (n_sim // 5)

    for rho in np.arange(0.30, 0.991, 0.05):
        if _power_at(rho) >= power:
            return float(round(rho, 2))
    return float("nan")


def run_family(pairs: dict, n_perms: int = 10_000, seed: int = 42) -> dict:
    """Run permutation Spearman over a family of (descriptor, target) hypotheses
    and apply Benjamini-Hochberg FDR across the family.

    `pairs` maps a hypothesis label to a (descriptor_array, target_array) tuple.
    Returns per-hypothesis rho, raw perm-p, BH-adjusted p, and the number of
    effective distinct descriptor values (the degeneracy flag).
    """
    labels, rhos, pvals, ndv = [], [], [], []
    for label, (x, y) in pairs.items():
        rho, p, _ = permutation_spearman(x, y, n_perms=n_perms, seed=seed)
        labels.append(label); rhos.append(rho); pvals.append(p)
        ndv.append(effective_distinct_values(x))
    adj = benjamini_hochberg(pvals)
    return {lab: {"rho": rhos[i], "perm_p": pvals[i], "bh_p": float(adj[i]),
                  "n_distinct_descriptor_values": ndv[i]}
            for i, lab in enumerate(labels)}
