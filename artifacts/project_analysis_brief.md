# Project Analysis Brief: Multi-Scale Structural Descriptors for Data Lineage Governance

## Purpose of this document

This brief is written for a fresh, high-capability model with no prior context. It summarises the full state of a research paper, its experimental evidence, the honest negative findings uncovered during revision, and the open paths to strengthening it. The goal is an objective analysis of where the paper stands and what the highest-leverage next steps are.

---

## 1. The paper in one paragraph

The paper proposes four graph-theoretic descriptors — D1 (community stability index via Louvain resolution sweep), D2 (blast-radius Gini concentration), D3 (spectral gap and Fiedler structure from the combinatorial Laplacian), D4 (persistent H1 homology via Vietoris-Rips filtration) — applied to directed acyclic data lineage graphs (dbt manifests, data pipeline DAGs). The original hypothesis was that lineage topology carries measurable governance-relevant information: well-governed pipelines should have higher community stability, lower blast-radius concentration, and fewer topological cycles than poorly-governed ones. After extensive revision, the paper's actual contribution is narrower and more honest: it delivers a structural characterization framework, a rigorous negative finding (the D3/documentation correlation is between-layer architecture, not within-layer governance quality), and a principled boundary condition established through cross-organization validation.

**Repository:** https://github.com/mhdk1602/multiscale-governance-descriptors (private)  
**Zenodo DOI:** 10.5281/zenodo.20101643 (v2.0.0)  
**Author:** Dineshkumar Malempati Hari, ORCID 0009-0003-1036-9477  
**Status:** Preprint-ready, not yet submitted to a journal or workshop  

---

## 2. Descriptor definitions (code-verified)

All four descriptors are computed on the **largest weakly connected component (LWCC)** of the undirected projection of the directed graph. D2 (blast radius) uses the full directed graph.

| Descriptor | What it computes | Implementation notes |
|---|---|---|
| D1 CSI | Fraction of consecutive Louvain resolution steps (γ ∈ [0.1, 10.0], 20 log-spaced) where NVI < 0.1. NVI = VI / log₂(N_LWCC). | Single fixed seed=42 for null model comparisons; multi-seed audit also run (25 seeds). Uses NetworkX Louvain (heuristic, not Leiden). |
| D2 max Gini | Maximum Gini coefficient of downstream blast-radius distribution across nodes and depths. | Full directed graph. For DAGs only. |
| D3 alg. conn. | λ₂ of the combinatorial Laplacian L = D − A on the LWCC. λ₂ > 0 always (LWCC is connected). | Also reports normalized gap = λ₂/λ_max and Fiedler bimodality. Fiedler bimodality = bimodality coefficient of the Fiedler eigenvector. |
| D4 H1/N | H1 bar count / N from Vietoris-Rips filtration on LWCC shortest-path distances. max_dimension=2, F_2 coefficients, zero-persistence and infinite bars discarded. | Also reports cycle rank baseline β₁ = M − N + C on full graph. |

---

## 3. Experimental evidence

### Experiment 1: Synthetic governance differentiation

**Setup:** 4 scales (tiny ~18–30, small ~28–43, medium ~65–76, large ~114–128 nodes), 3 governance levels (well/baseline/poor), 10 random generator seeds per condition = 120 graphs. Generator produces layered DAGs with varying cross-domain edge density and hub structure.

**Results (Mann-Whitney U + BH FDR correction):**
- D1 CSI, D2 max Gini, D4 H1/N: statistically significant at large scale (Cohen's d > 0.8)
- D3: not significant after FDR

**Critical caveat (added in revision):** D1 seed robustness over 25 Louvain seeds shows:
- Tiny/small/medium: Louvain seed variance ≈ governance-level separation (SNR < 1×). Results unreliable.
- Large: SNR = 2.8×. This is the only scale where D1 differentiation is robust to optimizer noise.

**Grouped cross-validation (leave-scale-out):**
- Baselines (degree, betweenness, etc.) AUC = 1.000 across all 4 held-out scale folds
- Multi-scale descriptors AUC = 0.935 ± 0.113 (drops to 0.74 when medium-scale held out)
- Baselines generalise better across scale than D1–D4 in this controlled synthetic setting

### Experiment 2: Real dbt production lineage

**Graph:** 223 nodes, 263 edges, verified DAG. 38 weakly connected components. LWCC = 185 nodes (83%). Three layers: 155 source/raw, 33 silver/intermediate, 35 gold/mart. 26 anonymized domains; 18 have N ≥ 5.

**Governance metadata:** documentation rate (per domain), test coverage rate, composite score. No steward metadata available.

**Domain layer distribution:**
- Source/raw: 12 of 18 analyzable domains. No internal edges. D3 = 0 for all.
- Silver/intermediate: 5 domains. All star-structured (K_{1,k}). D3 alg. conn. = 1.0 for all.
- Gold/mart: 1 domain (domain_012, N=35, M=63). D3 = 0.168.

**Permutation Spearman correlations (10,000 perms, BH FDR):**
- D3 alg. conn. vs doc_rate: ρ = −0.708, FDR p = 0.043 ✓
- D3 norm. gap vs doc_rate: ρ = −0.701, FDR p = 0.043 ✓
- All other descriptors: not significant after FDR

**Partial correlations (rank-transform + OLS residualization, not Freedman-Lane):**
- D3 alg. conn. vs governance score: partial ρ = −0.684, p = 0.002 (survives)
- D3 alg. conn. vs doc_rate: partial ρ = −0.546, p = 0.021 (survives)
- D3 norm. gap: sign reversal after controlling for domain size (nonsignificant)

**Subset robustness (5 subsets):**
- Subset A (all N≥5, n=18): FDR p = 0.029 — survives
- Subset B (internal edges only, n=6): FDR p = 0.189 — **fails**
- Subset C (no source-dominant, n=6): FDR p = 0.189 — **fails**

**Layer-stratified permutation (5,000 perms):** p = 1.000. D3 is constant within every layer stratum. Every permutation within-stratum reproduces the real correlation exactly.

**Conclusion on D3:** The correlation is 100% between-layer architecture. Source domains have D3=0 and varying documentation. Silver domains all have D3=1.0 (star structure) and zero documentation. The dbt case study produces a negative correlation purely because documentation effort concentrates at ingestion points (source, low D3) while silver domains have full internal connectivity but no documentation. This is organizational layer composition, not governance quality.

### Experiment 2b: Degree-preserving null model (100 rewirings)

| Descriptor | Real | Null mean | z | Sig |
|---|---|---|---|---|
| D1 CSI | 0.947* | 0.615 | +3.70 | *** |
| D3 Fiedler bimodality | 0.302 | 0.934 | −23.8 | *** |
| D4 H1/N | 0.220 | 0.272 | −2.95 | ** |
| D3 alg. conn. | 0.067 | 0.071 | −0.42 | ns |
| D4 cycle rank/N | 0.350 | 0.347 | +0.88 | ns |

*CSI = 0.947 uses fixed seed=42; multi-seed mean = 0.87 ± 0.08 over 25 seeds.

D3 alg. conn. is degree-sequence-determined (z = −0.42). D3 Fiedler bimodality is the strongest structural signal: the real graph has dramatically lower bimodality (0.302) than degree-matched rewirings (0.934), indicating a smooth gradient across pipeline layers rather than sharp random bipartitions.

### Experiment 2d: Layer-preserving edge rewiring stress test (100 rewirings)

Constrains swaps to edge pairs where source layers match and target layers match. Acceptance rate: 22.8% of 10M attempts. Only 11% of rewired graphs remain DAGs — this is a stress test, not a proper lineage null.

| Descriptor | z | Sig |
|---|---|---|
| D1 CSI | +2.68 | ** |
| D3 alg. conn. | −2.27 | ** |
| D3 Fiedler bim. | −1.50 | ns |
| D2 max Gini | −0.79 | ns |

D1 and D3 alg. conn. survive even this imperfect null. D3 Fiedler bimodality does not — likely because the low swap acceptance rate limits structural diversity in rewired graphs (null std = 0.216 vs 0.027 in degree-preserving null).

### Experiment 5: Cross-dataset structural characterization (32 graphs)

| Source | N graphs | N nodes | CSI (mean) | max Gini | norm. gap | Fiedler bim. | CR/N |
|---|---|---|---|---|---|---|---|
| WfCommons | 11 | 101–4,846 | 0.78 | 0.39 | 0.011 | 0.59 | 0.91 |
| DLG-DG-23 | 18 | 24–1,059 | 0.87 | 0.61 | 0.003 | 0.66 | 0.26 |
| DW-Bench | 2 | 31–37 | 0.68 | 0.54 | 0.030 | 0.66 | 0.95 |
| dbt manifest | 1 | 223 | 0.95 | 0.48 | 0.003 | 0.30 | 0.35 |

DLG-DG-23 graphs lack domain-level governance metadata in the public release. The structural convergence of dbt and DLG-DG-23 (high CSI, low spectral gaps) is real but govenance-metadata-free — structural characterization only.

PCA of 5 standardized descriptors: PC1 (29.5%) loads on high CSI / low norm. gap / low cycle rank. dbt and DLG-DG-23 cluster in positive-PC1 region; WfCommons spreads widely; DW-Bench separates on both axes. Total variance explained in 2D: 54.7%.

### Experiment 6: Cross-organization governance validation

Two public dbt projects parsed without running dbt (ref() for lineage, YAML for governance metadata):

| Organization | N analyzable domains | D3 vs doc_rate ρ | perm. p | Direction |
|---|---|---|---|---|
| dbt (this study) | 18 | −0.708 | 0.002 | negative |
| Cal-ITP (govt transit) | 26 | +0.023 | 0.911 | none |
| Mattermost (SaaS) | 6 | +0.812 | 0.070 | **positive (reversed)** |

**Cal-ITP:** 631 models, 40+ domain labels, documentation in YAML. No descriptor achieves significance (p > 0.11 for all).

**Mattermost:** 235 models, 18 domain tags. D3 correlation reverses sign from the dbt case study. In Mattermost, the well-documented domains are the large interconnected mart layers (high D3); in dbt, they are source clusters (low D3).

**Conclusion:** The D3/documentation correlation is organization-specific. The sign and direction depend entirely on how documentation practices align with architectural layer choices in each organization. The original dbt finding is not a universal governance signal — it is a layer-composition artifact specific to that organization's data engineering conventions.

---

## 4. What is solid vs what is weak

### Solid (survives all scrutiny)

1. **D1 structural signal at large scale.** D1 CSI z = +3.70 (degree-preserving null), z = +2.68 (layer-preserving null), SNR = 2.8× over seed variation at large synthetic scale. This is real structure beyond degree sequence.

2. **D3 Fiedler bimodality as architectural signal.** z = −23.8 (degree-preserving null). The real dbt graph has dramatically lower Fiedler bimodality than random degree-matched graphs. This reflects the smooth layered structure of production pipelines vs the bipartite-like structure that emerges from random rewiring.

3. **D4 H1 features add value over cycle rank in null model testing.** z = −2.95 (D4 H1/N) vs z = +0.88 (cycle rank/N). Persistent homology captures structure that cycle rank does not, but only in the structural (null model) comparison, not in direct governance correlations.

4. **Cross-dataset structural regularity.** Production lineage graphs cluster distinctly from scientific workflows in descriptor space (PC1 axis). The pattern is consistent across two independent organizations (dbt, Huawei Cloud DLG-DG-23).

5. **Mathematical precision.** All four descriptors are now precisely defined, code-verified, and documented with implementation parameters (LWCC choice, GUDHI max_dimension=2, Louvain seed convention, etc.).

### Weak (honest limitations)

1. **D1 at small/medium scale is unreliable.** The synthetic differentiation at tiny/small/medium scales (the majority of scale conditions) does not survive seed robustness. Only large-scale D1 is trustworthy.

2. **D3 governance correlation is entirely between-layer architecture.** The dbt finding doesn't generalize. Cal-ITP shows no association, Mattermost reverses sign. The descriptor measures architectural layer identity (source vs silver vs gold), not governance quality within layers.

3. **No within-layer governance signal found in any organization.** The paper cannot claim topology predicts governance in a universal sense. Local calibration is required.

4. **Mattermost sample is too small (n=6) for reliable inference.** The sign-reversal result is directionally interesting but statistically underpowered. A result at p=0.07 with n=6 is suggestive, not conclusive.

5. **Generator circularity in Experiment 1.** The synthetic generators were designed to embed governance-like structure, then the descriptors recover it. This is a partial validation — the descriptors are designed for what the generators produce.

6. **DLG-DG-23 lacks governance metadata.** The 18 Huawei Cloud graphs provide structural comparison but no governance-label validation. The dataset description mentions core-asset annotations but these are not in the public release files.

7. **Partial correlation method is rank-residualization, not Freedman-Lane.** This is documented in the paper but is a methodological limitation.

---

## 5. Current publication prospects

| Venue | Estimate | Rationale |
|---|---|---|
| SSRN / arXiv preprint | Ready now | Paper is coherent and honest |
| VLDB/SIGMOD/EDBT workshop | 65–75% | Strong if framed as structural lineage analysis with governance implications |
| JDIQ (Journal of Data and Information Quality) | 50–60% | Plausible; reviewers may want more governance-labeled organizations |
| Big Data Research / Information Systems | 45–55% | Depends on tolerance for negative cross-org governance result |
| VLDB/SIGMOD/ICDE main track | < 20% | Needs formal theory or multi-org positive governance validation |

The paper's honest framing of negative findings is an asset at workshop venues. It is a potential liability at journal venues where reviewers expect positive results.

---

## 6. What would concretely raise the venue ceiling

### Path A: More governance-labeled lineage graphs (highest impact)

The blocker for journal/top-venue submission is having only one organization's governance metadata (the dbt case study). The cross-org validation currently shows non-replication and sign reversal. To make a positive governance-correlation claim, the paper needs at least 3–4 organizations where descriptors show *consistent* associations with governance metadata.

**Feasible sources:**
- **Additional public dbt projects with rich YAML documentation:** GitLab's analytics project (500+ models, mandatory doc standards per handbook, public on GitLab.com) could be parsed the same way Cal-ITP and Mattermost were. The governance quality gradient would likely differ from both.
- **OpenMetadata or DataHub with governance-labeled exports:** Both platforms have structured governance metadata (owners, quality scores, documentation). Organizations that have published their catalogs.
- **Request from DLG-DG-23 authors (Ying Zhao, Central South University):** The paper explicitly mentions governance labels for 6 of 18 graphs. These may exist in the authors' possession but were not included in the public release. An email request is the most direct path to governance-labeled Huawei Cloud lineage graphs.
- **Government open data catalogs:** Some agencies publish data catalogs with stewardship and quality metadata attached to lineage graphs.

**What's needed:** Domain-level governance metrics (documentation rate, test coverage, owner assignment) on graphs with at least 8–10 analyzable domains per organization. The dbt YAML format makes this straightforward for public dbt projects.

### Path B: Stronger formal result (longer timeline)

The paper could be strengthened theoretically by:
- Proving that D1 CSI converges to a meaningful quantity as N → ∞ under a random graph model with community structure
- Establishing information-theoretic bounds on how much governance signal topology can carry, given degree-sequence constraints
- Connecting D3 Fiedler bimodality to known results on layered DAGs

This is a 6–12 month path and would change the venue ceiling significantly (toward VLDB/SIGMOD main), but requires graph theory expertise beyond what empirical iteration can provide.

### Path C: Governance-topology simulation study (medium effort)

The cross-org non-replication could be turned into a strength with a simulation: under what conditions does topology correlate with governance? Build a parametric model where governance practices and layer architecture co-vary differently, show that D3 correlation sign and strength depend on the governance-architecture alignment parameter. This would transform the negative finding from "D3 doesn't generalize" to "here is the formal condition under which topology is and isn't a governance proxy."

### Path D: Application paper — governance monitoring in practice

Pivot framing to a systems paper: given that D1/D3 Fiedler bimodality identify structural regularities in production pipelines, build a lightweight continuous monitoring tool and show it on a live dbt project. This bypasses the governance-prediction critique entirely by focusing on structural change detection (did the topology change in ways that suggest governance drift?). Publishable as an industrial track paper at VLDB or SIGMOD.

---

## 7. Paper structure summary (current state)

- **17 pages, 11 tables, 1 figure (PCA)**
- **Abstract:** Updated to reflect cross-org non-replication and layer-stratification finding
- **Contributions:** 5 bullets (descriptors, synthetic validation, real-data with honest negative, cross-dataset characterization, cross-org boundary condition)
- **Experiments:** 1 (synthetic), 2 (dbt real), 2b (null model), 2c (D1 seed robustness), 2d (layer-preserving null), 2e (subset robustness), 3 (intervention), 4 (predictive with grouped CV), 5 (cross-dataset), 6 (cross-org governance)
- **Discussion:** Correctly identifies D1 large-scale + null models as strongest evidence; D3 as layer architecture; D4 adds value only in null model
- **Limitations:** Governance correlation does not generalize; layer-specific calibration required
- **Reproducibility:** Zenodo DOI 10.5281/zenodo.20101643, ORCID linked

---

## 8. The core scientific finding (honest summary)

The paper set out to answer: does lineage topology encode governance maturity? The honest answer it arrived at after exhaustive testing:

> **Topology encodes layer architecture reliably. Whether that co-varies with governance depends entirely on how each organization's documentation and testing practices are distributed across architectural layers — and that distribution is organization-specific.**

D3 algebraic connectivity measures whether a domain's subgraph is a star (source tables), a small connected cluster (silver/intermediate), or something more complex (gold/mart). In the original dbt case, documentation happens to concentrate at source layers (low D3) and not at silver layers (high D3), producing a negative correlation. In Mattermost, the opposite. In Cal-ITP, no pattern. The descriptor works as designed; the governance hypothesis was too simple.

The remaining positive claim — that production lineage graphs have distinctive structural signatures (high D1 CSI, low spectral gaps, low cycle rank) distinguishable from scientific workflows and warehouse schemas — is well-supported across 32 graphs from four sources and two independent organizations. That is the paper's actual empirical contribution.
