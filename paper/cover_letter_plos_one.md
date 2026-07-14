# Cover Letter — PLOS ONE Submission

Dear Editors,

I submit the manuscript "Topology Under-Determines Governance Maturity in Data Lineage Graphs: A Negative Result and a Reusable Inference Protocol" for consideration at PLOS ONE.

## What this paper does

The paper defines four graph-theoretic descriptors of directed acyclic data lineage graphs — community stability under Louvain resolution sweep, blast-radius Gini concentration, spectral gap and Fiedler structure from the combinatorial Laplacian, and persistent H1 homology over Vietoris–Rips filtrations — and computes them on 32 graphs from four heterogeneous sources: 11 scientific workflow DAGs (WfCommons), 18 production data lineage graphs from Huawei Cloud (DLG-DG-23), 2 data warehouse schemas (DW-Bench), and an anonymised production dbt manifest from a single organisation. The primary empirical finding is structural: production data lineage graphs occupy a distinct region of descriptor space characterised by high community stability and small normalised spectral gaps, distinguishable from scientific workflow topologies.

## Why PLOS ONE

The paper deliberately reports a feasibility-grade governance-correlation result with explicit negative findings and methodological scaffolding (bootstrap confidence intervals, two null models, layer-stratified permutation, subset robustness, seed robustness, power analysis, leave-scale-out cross-validation). The single-organisation pilot of governance--topology correlation yields rho = -0.71 between D3 algebraic connectivity and documentation rate, which we show is operationally a 3-tier rank ordering rather than a continuous relationship; layer-stratified permutation gives p = 1.0, indicating the correlation is captured by between-layer architecture rather than within-layer governance signal. A preliminary cross-organisation comparison on two public dbt projects (Cal-ITP, Mattermost) does not replicate the dbt finding, and we discuss why folder-derived domain partitioning is not the same construct as metadata-assigned domains.

PLOS ONE's editorial scope — evaluating work on methodological rigour and ethical soundness rather than perceived impact, and explicitly considering negative and null results — matches this manuscript's contribution profile.

## Significance for the field

Data lineage is increasingly central to data engineering, MLOps, and regulatory compliance (GDPR, EU AI Act, FAIR data principles). Topological characterisation of lineage graphs has been understudied. This paper contributes:

1. Reproducible structural characterisation across four heterogeneous DAG families;
2. A rigorous methodological framework for small-sample, rank-degenerate governance--topology studies;
3. An explicit boundary condition for topology-based governance inference, demonstrating where naïve correlations fail through layer confounding.

## Reproducibility

All code, anonymised data, and experiment scripts are archived on Zenodo (DOI: 10.5281/zenodo.20209148), with the development repository at https://github.com/mhdk1602/multiscale-governance-descriptors. The archive reproduces every table and figure in the paper.

## Author declarations

- The work is original and has not been published elsewhere.
- No conflicts of interest.
- I am an independent researcher; no institutional review was required as the dbt lineage data is anonymised via HMAC-SHA256 hashing and contains no personally identifying information.
- The author is the sole contributor.

Sincerely,

Dineshkumar Malempati Hari
Independent Researcher
mhdk.dinesh@gmail.com
ORCID: 0009-0003-1036-9477
