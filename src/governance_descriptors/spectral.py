"""D3: Spectral gap and Fiedler structure.

Computes algebraic connectivity (lambda_2), normalized spectral gap,
Fiedler vector bimodality, and von Neumann spectral entropy.

References:
    Fiedler (1973), Czechoslovak Math. J. 23(98), 298-305.
    De Domenico & Biamonte (2016), Phys. Rev. X 6, 041062.
"""
from __future__ import annotations

import numpy as np
import networkx as nx
from scipy.sparse.linalg import eigsh
from scipy.sparse import csr_matrix


def _to_undirected_connected(g):
    if isinstance(g, nx.DiGraph):
        g = g.to_undirected()
    if not nx.is_connected(g):
        giant = max(nx.connected_components(g), key=len)
        g = g.subgraph(giant).copy()
    return g


def _laplacian_eigenvalues(g, k=None):
    """Eigenvalues of the combinatorial (unnormalized) Laplacian L = D - A."""
    L = nx.laplacian_matrix(g).astype(float)
    n = g.number_of_nodes()

    if n <= 500 or k is None:
        eigenvalues = np.sort(np.linalg.eigvalsh(L.toarray()))
    else:
        eigenvalues = eigsh(csr_matrix(L), k=min(k, n - 1), which="SM", return_eigenvectors=False)
        eigenvalues = np.sort(eigenvalues)

    return eigenvalues


def algebraic_connectivity(g) -> float:
    """Second-smallest eigenvalue of the Laplacian (Fiedler value)."""
    g = _to_undirected_connected(g)
    return float(nx.algebraic_connectivity(g))


def fiedler_vector(g) -> np.ndarray:
    """Eigenvector corresponding to the Fiedler value."""
    g = _to_undirected_connected(g)
    return np.array(nx.fiedler_vector(g))


def bimodality_coefficient(values) -> float:
    """Bimodality coefficient: (skewness^2 + 1) / (kurtosis + 3 * (n-1)^2 / ((n-2)(n-3))).

    BC > 5/9 ~ 0.555 suggests bimodal distribution.
    """
    arr = np.array(values)
    n = len(arr)
    if n < 4:
        return 0.0

    m2 = np.mean((arr - arr.mean()) ** 2)
    m3 = np.mean((arr - arr.mean()) ** 3)
    m4 = np.mean((arr - arr.mean()) ** 4)

    if m2 == 0:
        return 0.0

    skew = m3 / (m2 ** 1.5)
    kurt = m4 / (m2 ** 2) - 3  # excess kurtosis

    numerator = skew ** 2 + 1
    denominator = kurt + 3 * (n - 1) ** 2 / ((n - 2) * (n - 3))

    if denominator == 0:
        return 0.0

    return float(numerator / denominator)


def von_neumann_entropy(g) -> float:
    """Von Neumann-style entropy of the combinatorial (unnormalized) Laplacian.

    Treats the positive Laplacian eigenvalues as an unnormalized density
    matrix (scaled so sum = 1) and computes Shannon entropy. Uses the
    combinatorial Laplacian L = D - A, not the normalized Laplacian.
    Higher entropy = more complex/heterogeneous structure.
    """
    g = _to_undirected_connected(g)
    n = g.number_of_nodes()
    if n < 2:
        return 0.0

    eigenvalues = _laplacian_eigenvalues(g)
    eigenvalues = eigenvalues[eigenvalues > 1e-10]

    if len(eigenvalues) == 0:
        return 0.0

    probs = eigenvalues / eigenvalues.sum()
    entropy = -np.sum(probs * np.log2(probs + 1e-15))
    return float(entropy)


def spectral_descriptors(g) -> dict:
    """Compute all D3 descriptors in one call."""
    g = _to_undirected_connected(g)
    n = g.number_of_nodes()

    eigenvalues = _laplacian_eigenvalues(g)
    lambda_2 = float(eigenvalues[1]) if len(eigenvalues) > 1 else 0.0
    lambda_max = float(eigenvalues[-1]) if len(eigenvalues) > 0 else 1.0
    normalized_gap = lambda_2 / lambda_max if lambda_max > 0 else 0.0

    fv = np.array(nx.fiedler_vector(g)) if n >= 3 else np.zeros(n)
    bc = bimodality_coefficient(fv)

    pos_eigenvalues = eigenvalues[eigenvalues > 1e-10]
    if len(pos_eigenvalues) > 0:
        probs = pos_eigenvalues / pos_eigenvalues.sum()
        entropy = -float(np.sum(probs * np.log2(probs + 1e-15)))
    else:
        entropy = 0.0

    return {
        "algebraic_connectivity": lambda_2,
        "lambda_max": lambda_max,
        "normalized_spectral_gap": normalized_gap,
        "fiedler_bimodality": bc,
        "spectral_entropy": entropy,
        "n_eigenvalues": len(eigenvalues),
    }
