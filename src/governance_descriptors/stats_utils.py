"""Statistical utilities for revised experiments.

Permutation-based inference, FDR correction, and partial correlations
for small-sample, tie-heavy settings (n~18 domain-level observations).
"""
from __future__ import annotations

import numpy as np
from scipy import stats


def permutation_spearman(x, y, n_perms: int = 10_000, seed: int = 42):
    """Spearman rho with permutation p-value.

    Returns (rho, perm_p, parametric_p).  perm_p is the fraction of
    permutations where |rho_perm| >= |rho_obs|.
    """
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if len(x) < 4:
        return (np.nan, 1.0, 1.0)

    rho_obs, p_param = stats.spearmanr(x, y)
    rng = np.random.default_rng(seed)
    count = 0
    for _ in range(n_perms):
        rho_perm, _ = stats.spearmanr(rng.permutation(x), y)
        if abs(rho_perm) >= abs(rho_obs):
            count += 1
    perm_p = (count + 1) / (n_perms + 1)
    return (float(rho_obs), float(perm_p), float(p_param))


def benjamini_hochberg(p_values):
    """Benjamini-Hochberg FDR correction. Returns adjusted p-values."""
    p = np.asarray(p_values, dtype=float)
    n = len(p)
    if n == 0:
        return np.array([])
    order = np.argsort(p)
    adjusted = np.empty(n)
    cummin = 1.0
    for i in range(n - 1, -1, -1):
        rank = i + 1
        bh = p[order[i]] * n / rank
        cummin = min(cummin, bh)
        adjusted[order[i]] = min(cummin, 1.0)
    return adjusted


def partial_spearman(x, y, covariates, n_perms: int = 10_000, seed: int = 42):
    """Partial Spearman correlation controlling for covariates.

    Residualizes rank-transformed x and y on rank-transformed covariates
    via OLS, then computes Spearman rho on residuals with permutation test.
    """
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    covariates = np.asarray(covariates, dtype=float)
    if covariates.ndim == 1:
        covariates = covariates.reshape(-1, 1)

    mask = np.isfinite(x) & np.isfinite(y) & np.all(np.isfinite(covariates), axis=1)
    x, y, covariates = x[mask], y[mask], covariates[mask]
    if len(x) < 4:
        return (np.nan, 1.0)

    rx = stats.rankdata(x)
    ry = stats.rankdata(y)
    rc = np.column_stack([stats.rankdata(covariates[:, j]) for j in range(covariates.shape[1])])

    rc_aug = np.column_stack([np.ones(len(rc)), rc])

    def residualize(v, Z):
        coef, _, _, _ = np.linalg.lstsq(Z, v, rcond=None)
        return v - Z @ coef

    res_x = residualize(rx, rc_aug)
    res_y = residualize(ry, rc_aug)

    rho_obs, _ = stats.spearmanr(res_x, res_y)

    rng = np.random.default_rng(seed)
    count = 0
    for _ in range(n_perms):
        rho_perm, _ = stats.spearmanr(rng.permutation(res_x), res_y)
        if abs(rho_perm) >= abs(rho_obs):
            count += 1
    perm_p = (count + 1) / (n_perms + 1)
    return (float(rho_obs), float(perm_p))
