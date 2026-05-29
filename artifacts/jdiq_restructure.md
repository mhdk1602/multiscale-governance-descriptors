# JDIQ restructure: from descriptor instrument to a negative result + protocol

Drop-in material for converting the manuscript from "a multi-scale descriptor battery"
(unpublishable: the branded D1-D4 do no work on real data, and the one strong result
replicates Chen 2023) into "lineage topology under-determines governance maturity: a
negative result and a reusable inference protocol." Target: **ACM JDIQ**, challenge/
experience-paper track (provenance/lineage in scope, double-anonymous, no APC).

All numbers below are verified against the saved JSONs (`bootstrap_cis.json`,
`exp6_summary.json`, `phase_5/...prediction_summary.json`) and the test suite
(`tests/`, 37 passing) and the new protocol module (`src/governance_descriptors/
inference_protocol.py`).

---

## 1. Title

> **Topology Under-Determines Governance Maturity in Data Lineage Graphs: A Negative Result and a Reusable Inference Protocol**

(Drop the "multi-scale structural descriptors" framing from the title entirely. The
descriptors are the *instrument under test*, not the contribution.)

## 2. Abstract (drop-in)

> A recurring assumption in data-governance tooling and in the lineage-graph literature
> is that governance maturity leaves a measurable structural signature: better-governed
> estates should produce topologically distinct lineage graphs. We test that assumption
> directly. On a curated-metadata production dbt estate (18 analyzable domains), a
> spectral-gap descriptor correlates strongly with documentation rate (Spearman
> rho = -0.71, bootstrap 95% CI [-0.92, -0.27]). The correlation does not mean what it
> appears to: the descriptor takes three distinct values across the eighteen domains,
> a layer-stratified permutation test returns p = 1.000, and the relationship is carried
> entirely by between-layer architecture (source, staging, mart), not within-layer
> governance. A rank-degeneracy power analysis shows the observed effect sits at the
> design's minimum detectable size. The relationship does not replicate across
> organizations, and the apparent non-replication is confounded with a domain-construct
> mismatch we make explicit. A persistent-homology descriptor reduces exactly to the
> cycle-rank baseline (rho = +1.000) on real graphs, and a node-importance prediction
> result (AUC 0.90) reproduces a published centrality finding rather than extending it.
> Our contribution is therefore twofold and deliberately deflationary: (1) a carefully
> bounded negative result, that lineage topology is a poor proxy for governance maturity
> once the architectural-layer confound is removed; and (2) a reusable inference protocol
> for small-n graph-descriptor correlation studies, covering permutation and FDR control,
> layer-stratified permutation, degree-preserving nulls, and a rank-degeneracy-aware power
> analysis, packaged as tested, runnable code. The protocol is the transferable artifact:
> it lets future structure-versus-attribute studies distinguish a real relationship from
> one manufactured by rank degeneracy or a confounding partition.

## 3. Section spine (the narrative arc)

1. **The assumption.** The field treats lineage structure as a governance signal
   (Gartner maturity tiers; the DLG-DG-23 dataset paper's cluster-structure framing;
   data-observability tooling). State it as a testable hypothesis.
2. **The cleanest test available.** One curated-metadata production dbt estate, 18
   domains with N >= 5. Descriptors precisely defined (LWCC, GUDHI params, Louvain seed).
3. **The naive result looks strong.** D3 spectral gap vs doc_rate, rho = -0.71, bootstrap
   CI excludes zero.
4. **It is an artifact.** D3 takes three distinct values across 18 domains
   (`effective_distinct_values` = 3); layer-stratified permutation p = 1.000; the effect
   is between-layer architecture. Show the three-tier structure explicitly.
5. **It does not generalize, and we say why honestly.** Cross-org non-replication
   (Cal-ITP +0.02, Mattermost +0.81 at n=6 with CI [0.00, 1.00]) is confounded with a
   domain-construct mismatch (curated metadata vs folder paths). Report it as a
   measurability finding, not a clean failed test.
6. **Power and the other descriptors.** Rank-degeneracy power analysis: minimum
   detectable |rho| ~ 0.7-0.8, exactly where the observed effect landed. D4 = cycle rank
   (rho +1.000). Experiment 7 (AUC 0.90) replicates Chen 2023.
7. **The protocol.** Lift the inference checklist into the named, citable contribution.
8. **Conclusion.** Measure governance through process and curated metadata, not graph
   structure. Provide the protocol so others avoid the same trap.

## 4. Related-work confrontations (drop-in paragraphs, must appear in the first 3 pages)

**Chen et al. (2023), *Big Data and Cognitive Computing* 7(4):161.** Chen et al. show
that node-centrality metrics identify core data assets on the DLG-DG-23 lineage graphs.
Our Experiment 7 (core-asset prediction, AUC 0.90) is, under leave-one-graph-out
cross-validation on the same corpus, a reproduction of that result: the top predictors
are PageRank and out-degree, and the D1-D4 descriptors add no measurable lift beyond
centrality. We report this as confirmation that lineage structure carries node-importance
signal that is already captured by simple centrality, not as a new finding, and not as
evidence that multi-scale descriptors detect governance.

**Chen et al. (2024), *Visual Informatics* 8(1).** The DLG-DG-23 dataset paper already
characterizes data-lineage graphs as sparse, scale-free, and cluster-rich. We therefore
scope our cross-source structural comparison (Experiment 5) narrowly, as a contrast
between production lineage, scientific workflows (WfCommons), and warehouse schemas
(DW-Bench), rather than as new structural discovery.

**Huang et al., LAD (KDD 2020) and MultiLAD (TKDD 2024, DOI 10.1145/3631609).** Spectral
change-point detection on dynamic graphs is a solved problem with a published,
benchmarked method. Our longitudinal descriptor-monitoring idea is an under-powered
re-derivation of it; we do not claim change detection as a contribution, and we defer
the git-history dbt time series to a separate dataset/resource paper where the
contribution is the data, not the detector.

## 5. README headline fix (before -> after)

**Before** (current README leads with the indefensible number):
> Multi-scale structural descriptors achieve **AUC 0.897** for core-asset prediction...

**After**:
> A negative result: lineage topology under-determines governance maturity (the strong
> D3 vs doc_rate correlation, rho = -0.71, collapses under layer-stratified permutation,
> p = 1.000), plus a reusable small-n graph-correlation inference protocol. The
> node-importance AUC reproduces Chen et al. (2023) centrality and is reported as such.

The README must not contradict the methods. Leading with AUC 0.897 invites the exact
"oversold" objection a reviewer will raise.

## 6. JDIQ submission checklist

| Item | State |
|---|---|
| Test suite over descriptor computations | **Done** — `tests/`, 37 passing, incl. D4 = cycle-rank assertion + CI workflow |
| Inference protocol as runnable module | **Done** — `src/governance_descriptors/inference_protocol.py` + tests |
| Related-work confrontations (Chen 23/24, LAD) | drafted above; fold into manuscript |
| Negative result as the spine | restructure per section spine above |
| Rank-degeneracy + power-analysis section | `min_detectable_rho` packaged; write the section |
| Housekeeping (stale DOI, token, empty stubs) | pending — `CHANGELOG` DOI, rotate token |
| Retitle + abstract + README | drafted above |
| Email Ying Zhao group for more core-asset labels | pending — one email, non-blocking |
| arXiv/SSRN preprint before the defense | post after restructure |

**Honest probability with the full reframe:** JDIQ challenge paper 45-60%; DOLAP/DEEM 2027
workshop fallback 60-70%. Do not submit the descriptor-instrument framing anywhere.
