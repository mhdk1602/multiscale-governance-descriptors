# Cover Letter — Data & Knowledge Engineering (Elsevier)

Dear Editor-in-Chief,

I submit the manuscript "Multi-Scale Structural Descriptors for Governance-Relevant Patterns in Data Lineage Graphs" for consideration at Data & Knowledge Engineering, traditional subscription-based publication.

## What this paper does

The paper defines four graph-theoretic descriptors of directed acyclic data lineage graphs — community stability under Louvain resolution sweep, blast-radius Gini concentration, spectral gap and Fiedler structure from the combinatorial Laplacian, and persistent H1 homology over Vietoris–Rips filtrations — and computes them on 32 graphs from four heterogeneous sources: 11 scientific workflow DAGs (WfCommons), 18 production data lineage graphs from Huawei Cloud (DLG-DG-23), 2 data warehouse schemas (DW-Bench), and an anonymised production dbt manifest from a single organisation.

## Why Data & Knowledge Engineering

D&KE's scope explicitly covers data lineage, data quality, metadata management, and knowledge engineering applied to data systems. The manuscript contributes:

1. A reproducible structural characterisation framework showing that production data lineage graphs occupy a distinct region of descriptor space, characterised by high community stability and small normalised spectral gaps, distinct from scientific workflow topologies. This is the paper's primary empirical contribution and is independent of any governance metadata.

2. Methodological scaffolding for small-sample, rank-degenerate governance--topology studies: permutation-based inference (10,000 permutations), bootstrap confidence intervals, Benjamini--Hochberg FDR correction with explicit hypothesis families, rank-residualization partial correlations, two null models (degree-preserving and layer-preserving), subset robustness analysis, layer-stratified permutation, Louvain seed robustness, leave-scale-out cross-validation, and power analysis.

3. A single-organisation pilot of governance--topology correlation on a production dbt lineage. We find a 3-tier rank ordering between D3 algebraic connectivity and documentation rate (ρ = -0.71, bootstrap 95% CI [-0.92, -0.27]) and demonstrate through layer-stratified permutation (p = 1.0) that the correlation is captured by between-layer architecture rather than within-layer governance variation. A preliminary cross-organisation comparison on two public dbt projects does not replicate the dbt finding, and we discuss why folder-derived domain partitioning is not the same construct as metadata-assigned domains.

The work is intentionally framed as feasibility evidence with explicit boundary conditions, not as a validated governance prediction method. The negative cross-organisation result is a contribution: it establishes that naïve topology--governance correlations can be confounded by architectural layer composition, and outlines what curated multi-organisation metadata would be required for proper validation.

## Significance

Data lineage is increasingly central to data engineering and regulatory compliance (GDPR, EU AI Act, FAIR data principles). Topological characterisation of lineage graphs is understudied compared to descriptive metadata approaches. The methodological scaffolding generalises to any DAG-structured data pipeline analysis.

## Reproducibility

All code, anonymised data, and experiment scripts are archived on Zenodo (DOI: 10.5281/zenodo.20101643), with the development repository at https://github.com/mhdk1602/multiscale-governance-descriptors. The archive reproduces every table and figure in the paper.

## Author declarations

- The work is original and has not been submitted elsewhere.
- I have not used any LLM-generated content in the manuscript text except for routine editing assistance, which has been reviewed and verified by the author.
- No conflicts of interest. No funding to declare.
- I am an independent researcher.
- The author is the sole contributor.
- The dbt lineage data is anonymised via HMAC-SHA256 hashing and contains no personally identifying information.

## Preferred publication mode

I request **traditional subscription-based publication** without Article Processing Charges. I understand the published article will be accessible to subscribers and via the corresponding institutional access channels.

Sincerely,

Dineshkumar Malempati Hari
Independent Researcher
mhdk.dinesh@gmail.com
ORCID: 0009-0003-1036-9477
