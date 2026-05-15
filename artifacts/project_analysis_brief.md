# Project Analysis Brief: Multi-Scale Structural Descriptors for Data Lineage Governance

## Purpose of this document

This brief is written for a fresh, high-capability model with no prior context. It summarises the full state of a research paper, its experimental evidence, the methodological limitations uncovered during revision and calibration review, and the open paths to strengthening it. It deliberately understates positive findings and surfaces issues a careful methods reviewer would flag.

---

## 1. The paper in one paragraph

The paper proposes four graph-theoretic descriptors — D1 (community stability index via Louvain resolution sweep), D2 (blast-radius Gini concentration), D3 (spectral gap and Fiedler structure from the combinatorial Laplacian), D4 (persistent H1 homology via Vietoris-Rips filtration) — applied to directed acyclic data lineage graphs. The original hypothesis was that lineage topology carries measurable governance-relevant information. After extensive revision and external calibration review, the paper's defensible contribution is narrower: it delivers (a) a structural characterization framework validated across 32 graphs from four sources, (b) a pilot real-data feasibility study on one organization's dbt lineage with explicit acknowledgement of rank-degeneracy and small-sample limitations, and (c) a methodologically caveated cross-organization non-replication that is consistent with but does not prove a between-layer architecture interpretation.

**Repository:** https://github.com/mhdk1602/multiscale-governance-descriptors (private)  
**Zenodo DOI:** 10.5281/zenodo.20209148 (v2.0.0)  
**Author:** Dineshkumar Malempati Hari, ORCID 0009-0003-1036-9477  
**Status:** Feasibility study with negative real-data findings; preprint-ready for SSRN; **not journal-ready in current form** without further work

---

## 2. Descriptor definitions (code-verified)

All four descriptors are computed on the **largest weakly connected component (LWCC)** of the undirected projection of the directed graph. D2 (blast radius) uses the full directed graph.

| Descriptor | What it computes | Implementation notes |
|---|---|---|
| D1 CSI | Fraction of consecutive Louvain resolution steps (γ ∈ [0.1, 10.0], 20 log-spaced) where NVI < 0.1. NVI = VI / log₂(N_LWCC). | Single fixed seed=42 for null model comparisons; multi-seed audit also run (25 seeds). Uses NetworkX Louvain (heuristic, not Leiden). |
| D2 max Gini | Maximum Gini coefficient of downstream blast-radius distribution across nodes and depths. | Full directed graph. For DAGs only. |
| D3 alg. conn. | λ₂ of the combinatorial Laplacian L = D − A on the LWCC. λ₂ > 0 always (LWCC is connected). | Also reports normalized gap = λ₂/λ_max and Fiedler bimodality. |
| D4 H1/N | H1 bar count / N from Vietoris-Rips filtration on LWCC shortest-path distances. max_dimension=2, F_2 coefficients. | Also reports cycle rank β₁ = M − N + C on full graph. |

---

## 3. Experimental evidence (calibrated)

### Experiment 1: Synthetic governance differentiation

**Setup:** 4 scales (tiny ~18–30, small ~28–43, medium ~65–76, large ~114–128 nodes), 3 governance levels (well/baseline/poor), 10 generator seeds per condition = 120 graphs.

**Results:**
- D1 CSI, D2 max Gini, D4 H1/N: significant at large scale (Cohen's d > 0.8)
- D3: not significant after FDR

**Methodological caveats** (critical):
- **Generator circularity.** The generator's `well/baseline/poor` knobs control structural features (cross-layer edge density, hub centrality) that overlap with what the descriptors measure. This is closer to a self-consistency / pipeline-correctness test than external validation.
- **D1 seed robustness.** Over 25 Louvain seeds: tiny/small/medium scales show seed variance ≈ governance-level separation (SNR < 1×). Only large scale has SNR = 2.8×.
- **Grouped CV (leave-scale-out).** Baselines achieve AUC = 1.000 across all 4 held-out scale folds. Multi-scale descriptors AUC = 0.935 ± 0.113 (drops to 0.74 on medium-out). **Baselines generalise better across scales than multi-scale features.** This contradicts the "D1 is solid" framing.

### Experiment 2: Real dbt production lineage

**Graph:** 223 nodes, 263 edges, verified DAG, 38 components. LWCC = 185 nodes (83%). Three layers: 155 source/raw, 33 silver/intermediate, 35 gold/mart. 26 anonymized domains; 18 have N ≥ 5.

**Critical data structure caveat (the central methodological issue):**

The "n=18 analyzable domains" understates the rank degeneracy of the data:

| Group | n domains | D3 alg. conn. | doc_rate |
|---|---|---|---|
| Source-only (M=0) | 12 | exactly 0 | 0.04–1.00 |
| Silver stars K_{1,k} | 5 | exactly 1.0 | 0.00 |
| Gold/mart (domain_012) | 1 | 0.168 | 0.914 |

**D3 takes three distinct values across 18 observations.** The "ρ=−0.708 permutation Spearman correlation" is mathematically valid but operationally a 3-tier rank ordering test, not a continuous correlation. A methods reviewer will identify this.

**Permutation Spearman (10,000 perms, BH FDR):**
- D3 alg. conn. vs doc_rate: ρ = −0.708, FDR p = 0.043
- D3 norm. gap vs doc_rate: ρ = −0.701, FDR p = 0.043

**Bootstrap 95% CIs (10,000 resamples; added in calibration revision):**
- D3 alg. conn. vs doc_rate: CI [−0.920, −0.266] — excludes zero
- D3 norm. gap vs doc_rate: CI [−0.879, −0.275] — excludes zero
- D4 H1/N vs doc_rate: ρ=+0.214, CI [+0.045, +0.492] — also excludes zero (previously understated)
- D4 cycle rank/N vs doc_rate: ρ=+0.214, CI [+0.025, +0.495]
- D3 Fiedler bim vs doc_rate: CI [−0.864, −0.066]

**Power analysis (added in calibration revision):**
- Continuous data, n=18: minimum detectable |ρ| ≈ 0.6 at 80% power
- Rank-degenerate data (3 tiers, dbt-like): minimum detectable |ρ| ≈ 0.7–0.8 at 80% power
- Observed |ρ|=0.71 is at the detection threshold

**Subset robustness:**
- Subset A (all N≥5, n=18): FDR p = 0.029 — survives
- Subset B (internal edges only, n=6): FDR p = 0.189 — fails
- Layer-stratified permutation: p = 1.000 (D3 constant within stratum)

**Component-level analysis** (alternative unit of analysis, attempted in calibration): only 1 component has N ≥ 5 (the LWCC). Component-level correlation is not viable.

**Conclusion on D3 (calibrated):** The bootstrap CI for the correlation excludes zero even with rank degeneracy, so the ordering effect is statistically real for this dataset. But D3 is constant within each layer stratum, so the correlation is captured entirely by between-layer architecture, not within-layer governance variation. The result is reproducible for *this* dataset's layer composition; it does not extend to within-layer governance prediction.

### Experiment 2b: Degree-preserving null model (100 rewirings)

| Descriptor | Real | Null mean | z | Interpretation |
|---|---|---|---|---|
| D1 CSI | 0.947* | 0.615 | +3.70 | Real graph more stable than rewirings |
| D3 Fiedler bimodality | 0.302 | 0.934 | −23.8 | **Likely tautological** — sparse layered DAGs vs random rewirings differ enormously in Fiedler structure |
| D4 H1/N | 0.220 | 0.272 | −2.95 | Real graph has slightly fewer H1 bars |
| D3 alg. conn. | 0.067 | 0.071 | −0.42 | Degree-sequence-determined |
| D4 cycle rank/N | 0.350 | 0.347 | +0.88 | Trivially preserved |

*CSI = 0.947 uses fixed seed=42; multi-seed mean = 0.87 ± 0.08 over 25 seeds.

**Calibration note on z = −23.8.** A z-score of 23 standard deviations is mathematically suspicious. Degree-preserving rewiring of a sparse layered DAG produces graphs with very different gross topology (more bipartite-like). The Fiedler bimodality difference reflects this gross structural difference, not subtle structural signal. Framing this as a "discovered governance-relevant property" overstates its importance.

### Experiment 2d: Layer-preserving edge rewiring stress test

22.8% swap acceptance, only 11% of rewired graphs remain DAGs. **This is a stress test, not a proper lineage null.** D1 z = +2.68, D3 alg. conn. z = −2.27 survive; D3 Fiedler bim. and D2 do not.

### Experiment 5: Cross-dataset structural characterization (32 graphs)

| Source | N graphs | N nodes | CSI | max Gini | norm. gap | Fiedler bim. | CR/N |
|---|---|---|---|---|---|---|---|
| WfCommons | 11 | 101–4,846 | 0.78 | 0.39 | 0.011 | 0.59 | 0.91 |
| DLG-DG-23 | 18 | 24–1,059 | 0.87 | 0.61 | 0.003 | 0.66 | 0.26 |
| DW-Bench | 2 | 31–37 | 0.68 | 0.54 | 0.030 | 0.66 | 0.95 |
| dbt | 1 | 223 | 0.95 | 0.48 | 0.003 | 0.30 | 0.35 |

DLG-DG-23 lacks governance metadata in public release. PCA: PC1 (29.5%) loads on high CSI / low norm. gap / low cycle rank. **2D variance explained: 54.7% — visualisation is suggestive, not definitive.**

This is the paper's strongest empirical evidence and is purely structural (no governance claim).

### Experiment 6: Cross-organization governance validation (with unit-of-analysis caveat)

| Organization | Domain definition | n | D3 vs doc_rate ρ | perm. p | Bootstrap 95% CI |
|---|---|---|---|---|---|
| dbt (this study) | **Metadata-assigned** `domain_or_team_owner` | 18 | −0.708 | 0.002 | [−0.920, −0.266] |
| Cal-ITP | **Folder-derived** (2-level path) | 26 | +0.023 | 0.911 | [−0.415, +0.436] |
| Mattermost | **Folder-derived** (2-level path) | 6 | +0.812 | 0.070 | [+0.000, +1.000] |

**Critical methodological caveat (added in calibration):** The three "domain" units are not the same construct. dbt domains are organisational/ownership assignments (curated metadata). Cal-ITP and Mattermost lack systematic `meta.domain` or `meta.owner` declarations on most models, so domains are inferred from folder structure. Folder structure in dbt projects often follows staging→intermediate→mart layer organisation rather than business-domain assignment. The "non-replication" therefore conflates:
1. Actual non-replication of the governance-topology relationship
2. Unit-of-analysis construct mismatch
3. n=6 sample noise in Mattermost (CI saturates at [+0.000, +1.000])

The honest reading: the original dbt finding does not extend straightforwardly to folder-derived domain partitions of other dbt projects. Whether it would replicate with curated domain metadata from another organisation remains untested.

---

## 4. What is solid vs what is weak (recalibrated)

### Defensible (survives rigorous review)

1. **Structural characterization across 32 graphs.** Production lineage graphs (dbt, DLG-DG-23) cluster distinctly from scientific workflows (WfCommons) on PC1 (high CSI, low gap, low cycle rank). This is empirically supported and purely descriptive.

2. **D3 has rank-degenerate but bootstrap-supported correlation in dbt.** ρ=−0.708, CI [−0.920, −0.266]. The correlation reflects a 3-tier between-layer ordering — source domains, silver stars, the gold domain — not a continuous within-layer relationship.

3. **D1 differentiates governance levels at large synthetic scale.** Cohen's d > 3.9 at the largest scale tested. Caveats: generator circularity, grouped-CV failure, seed sensitivity below large scale.

4. **Mathematical and implementation precision.** All descriptors are precisely defined, computed on a clearly stated graph subset, with documented parameters (LWCC, GUDHI max_dimension=2, Louvain seed convention).

### Limited / overstated in earlier framings

1. **D3 Fiedler bimodality z = −23.8 is near-tautological.** Sparse layered DAGs differ enormously from degree-matched rewirings in Fiedler structure. Framing this as a discovered governance signal overstates it.

2. **D4 H1/N has a small but real correlation with doc_rate (ρ=+0.214, CI excludes zero).** This was understated in earlier framings. However, D4 is operationally identical to cycle rank β₁ on real data (ρ=+1.000), so D4's added value over the simpler baseline is restricted to null-model testing.

3. **D1 large-scale synthetic result conflicts with grouped CV.** D1 differentiates within-scale but multi-scale features generalise worse than baselines across scales (AUC 0.935 vs 1.000).

4. **Cross-organization non-replication is methodologically caveated.** Folder-derived domains in Cal-ITP/Mattermost are not the same construct as metadata-assigned dbt domains. The non-replication is suggestive but not conclusive.

5. **Mattermost n=6 with CI saturating to [+0.000, +1.000].** The sign reversal is statistically inconclusive; bootstrap CI almost spans the full range.

### Genuinely weak

1. **Power analysis shows the dbt finding is at the detection threshold.** Minimum detectable |ρ| at 80% power with rank-degenerate data is 0.7–0.8; observed is 0.71. The result is borderline by design.

2. **Generator circularity in synthetic experiment** has not been fully addressed. The generators encode the structural patterns the descriptors detect.

3. **No truly independent governance-labeled replication exists.** All three organisations are dbt-based with inconsistent domain construct definitions.

---

## 5. Publication prospects (calibrated)

| Venue | Estimate | Rationale |
|---|---|---|
| SSRN / arXiv preprint | Ready | Coherent feasibility study; honest framing |
| Workshop (DBML, reproducibility tracks) | 50–65% | Short paper format with explicit pilot framing |
| VLDB/SIGMOD/EDBT workshop (general) | 40–55% | Methods reviewers will scrutinise n=18 with 3 effective D3 values |
| JDIQ (Journal of Data and Information Quality) | 25–40% **after revision below** | Single-org real-data finding + folder-derived cross-org + rank-degenerate D3 limit this |
| Big Data Research / Information Systems | 20–35% **after revision** | Similar concerns |
| VLDB/SIGMOD/ICDE main track | < 5% | Not a serious candidate |

The earlier brief overstated probabilities by 20–30 percentage points. Methods reviewers will identify the rank degeneracy in D3 and the unit-of-analysis mismatch in cross-org analysis. The recalibrated estimates reflect what actually happens under careful review.

---

## 6. Path forward (solo, then partnership-required)

### Solo path (executable now, raises JDIQ probability to 30–45%)

1. **Reframe the paper as a pilot/feasibility case study.** Lead with structural characterization (Experiment 5) as the validated empirical core. Treat the dbt case study as illustrative pilot. Move governance correlation to Section 5, not Section 2.

2. **Add bootstrap confidence intervals throughout.** Bootstrap CIs are added in calibration and consistently exclude zero for D3 vs doc_rate, supporting the headline result. CIs are more informative than p-values at small n.

3. **Explicit rank-degeneracy disclosure.** State plainly that D3 has 3 effective values across 18 dbt domains and that the analysis is operationally a 3-tier ordering test. Frame this as an honest methodological observation, not an apology.

4. **Power analysis section.** Include the simulation result showing minimum detectable effects. The observed effect being at the detection threshold is what the data could show.

5. **Unit-of-analysis caveat in cross-org section.** Explicitly state that folder-derived domains in Cal-ITP/Mattermost are not the same construct as metadata-assigned dbt domains. Frame Experiment 6 as "preliminary cross-organisation exploration" not "cross-organisation validation."

6. **D4 H1/N positive correlation result.** Surface the bootstrap CI result that the paper currently understates. D4 H1/N has ρ=+0.214, CI [+0.045, +0.492], with doc_rate. This is a small but defensible positive finding.

7. **Detailed future work section on partnership-required validation.** Specify what partnership-based research would look like:
   - 3–5 organizations sharing lineage + curated `meta.domain` / `meta.owner` assignments via NDA
   - Domain-level governance metrics (documentation, test coverage, ownership) on N ≥ 30 analyzable domains per organisation
   - Versioned manifests over 6–12 months to enable temporal change detection
   - Coordination via OpenMetadata or DataHub catalog exports

### Partnership path (future state)

The cross-organisation non-replication will only be resolved by curated-domain governance metadata from multiple organisations. Public dbt projects yield folder-derived domains which are not directly comparable to the dbt case study's metadata-assigned domains. Partnership routes:
- Email DLG-DG-23 authors (Ying Zhao, Central South University) for the core-asset annotations referenced in their paper but not in the public release
- OpenMetadata / DataHub user communities (some organisations publish anonymised catalogue exports)
- Direct enterprise partnerships under NDA

---

## 7. Core scientific finding (calibrated)

The paper set out to ask whether lineage topology encodes governance maturity. After exhaustive testing the answer is:

> **Lineage topology encodes architectural layer structure reliably across organisations. In our single pilot dbt case, layer composition co-varies with documentation rate, producing a 3-tier rank correlation that is statistically robust but operationally explained by between-layer architecture, not within-layer governance variation. Whether this co-variation generalises to other organisations remains untested due to construct mismatch in publicly available dbt projects.**

The paper's strongest empirical contribution is the cross-dataset structural characterization, which establishes that production data lineage graphs occupy a distinct region of descriptor space from scientific workflows. This is descriptive but well-supported.

The paper's contribution is **methodological + descriptive + pilot**, not predictive. Honest framing of this is the requirement for journal publication.
