"""Synthetic lineage DAG generators for governance experiments.

Generates lineage DAGs at varying governance quality levels:
- well_governed: clear domain boundaries, concentrated stewardship
- baseline: standard random layered DAG
- poorly_governed: cross-domain deps, orphan chains, ad-hoc shortcuts
"""
from __future__ import annotations

import numpy as np
import networkx as nx


def synthetic_lineage(
    n_sources: int = 8,
    n_staging: int = 14,
    n_marts: int = 6,
    n_exposures: int = 4,
    seed: int = 42,
) -> nx.DiGraph:
    """Baseline 4-layer lineage DAG."""
    rng = np.random.default_rng(seed)
    g = nx.DiGraph()
    sources = [f"src_{i}" for i in range(n_sources)]
    staging = [f"stg_{i}" for i in range(n_staging)]
    marts = [f"mart_{i}" for i in range(n_marts)]
    exposures = [f"exp_{i}" for i in range(n_exposures)]

    for layer, nodes in [
        ("source", sources), ("staging", staging),
        ("mart", marts), ("exposure", exposures),
    ]:
        for n in nodes:
            g.add_node(n, layer=layer)

    for s in staging:
        for src in rng.choice(sources, size=2, replace=False):
            g.add_edge(src, s)
    for m in marts:
        for stg in rng.choice(staging, size=3, replace=False):
            g.add_edge(stg, m)
    for e in exposures:
        for m_node in rng.choice(marts, size=2, replace=False):
            g.add_edge(m_node, e)

    return g


def well_governed_lineage(
    n_sources: int = 12,
    n_staging: int = 18,
    n_marts: int = 9,
    n_exposures: int = 6,
    n_domains: int = 3,
    seed: int = 42,
) -> nx.DiGraph:
    """Lineage with clear domain boundaries.

    Sources are partitioned into domains. Each staging node draws from
    at most one domain. Marts draw from staging within the same domain.
    Cross-domain edges exist only at the exposure layer.
    """
    rng = np.random.default_rng(seed)
    g = nx.DiGraph()

    src_per_domain = n_sources // n_domains
    stg_per_domain = n_staging // n_domains
    mart_per_domain = n_marts // n_domains

    for d in range(n_domains):
        sources = [f"src_d{d}_{i}" for i in range(src_per_domain)]
        staging = [f"stg_d{d}_{i}" for i in range(stg_per_domain)]
        marts = [f"mart_d{d}_{i}" for i in range(mart_per_domain)]

        for n in sources:
            g.add_node(n, layer="source", domain=d)
        for n in staging:
            g.add_node(n, layer="staging", domain=d)
        for n in marts:
            g.add_node(n, layer="mart", domain=d)

        for s in staging:
            for src in rng.choice(sources, size=min(2, len(sources)), replace=False):
                g.add_edge(src, s)
        for m in marts:
            for stg in rng.choice(staging, size=min(2, len(staging)), replace=False):
                g.add_edge(stg, m)

    all_marts = [n for n, a in g.nodes(data=True) if a["layer"] == "mart"]
    exposures = [f"exp_{i}" for i in range(n_exposures)]
    for e in exposures:
        g.add_node(e, layer="exposure", domain=-1)
        for m in rng.choice(all_marts, size=min(2, len(all_marts)), replace=False):
            g.add_edge(m, e)

    return g


def poorly_governed_lineage(
    n_sources: int = 12,
    n_staging: int = 18,
    n_marts: int = 9,
    n_exposures: int = 6,
    n_orphan_chains: int = 3,
    n_shortcuts: int = 4,
    seed: int = 42,
) -> nx.DiGraph:
    """Lineage with cross-domain deps, orphan chains, and ad-hoc shortcuts.

    Cross-domain: staging nodes pull from any source regardless of domain.
    Orphan chains: long transformation sequences with no governance metadata.
    Shortcuts: direct edges from sources to exposures bypassing staging/mart.
    """
    rng = np.random.default_rng(seed)
    g = synthetic_lineage(n_sources, n_staging, n_marts, n_exposures, seed)

    sources = [n for n, a in g.nodes(data=True) if a["layer"] == "source"]
    staging = [n for n, a in g.nodes(data=True) if a["layer"] == "staging"]
    exposures_list = [n for n, a in g.nodes(data=True) if a["layer"] == "exposure"]

    for stg in rng.choice(staging, size=min(6, len(staging)), replace=False):
        extra_src = rng.choice(sources)
        g.add_edge(extra_src, stg)

    next_id = g.number_of_nodes()
    for chain_i in range(n_orphan_chains):
        chain_len = rng.integers(3, 7)
        prev = rng.choice(sources)
        for j in range(chain_len):
            node = f"orphan_{chain_i}_{j}"
            g.add_node(node, layer="orphan", domain=-1)
            g.add_edge(prev, node)
            prev = node

    for _ in range(n_shortcuts):
        src = rng.choice(sources)
        exp = rng.choice(exposures_list)
        g.add_edge(src, exp)

    return g


def scaled_lineage(scale: str = "small", governance: str = "baseline", seed: int = 42) -> nx.DiGraph:
    """Convenience generator at preset scales.

    scale: 'tiny' (~30), 'small' (~50), 'medium' (~100), 'large' (~200)
    governance: 'well', 'baseline', 'poor'
    """
    configs = {
        "tiny": (4, 8, 4, 2),
        "small": (8, 14, 6, 4),
        "medium": (15, 30, 12, 8),
        "large": (25, 60, 20, 12),
    }
    n_src, n_stg, n_mart, n_exp = configs.get(scale, configs["small"])

    if governance == "well":
        return well_governed_lineage(n_src, n_stg, n_mart, n_exp, seed=seed)
    elif governance == "poor":
        return poorly_governed_lineage(n_src, n_stg, n_mart, n_exp, seed=seed)
    else:
        return synthetic_lineage(n_src, n_stg, n_mart, n_exp, seed=seed)
