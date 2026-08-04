# CHANGELOG

## Unreleased: Governance-Mediated Change Risk

### New study

- Added a preregistered PR-level successor study with post-merge adverse events
  as the primary outcome.
- Added exact dbt manifest extraction with canonical IDs, typed dependencies,
  tests, contracts, ownership, descriptions, and source freshness controls.
- Added ordinary graph-diff, governance, and multiscale feature families with
  fixed analysis prefixes.
- Added leave-project-out and terminal-time evaluation. Imputation and scaling
  occur inside each training fold.
- Added a descriptor-blind annotation codebook and a manifest-pair data contract.
- Added a hermetic git-ref collector that records resolved refs, commands, dbt
  versions, and SHA-256 artifact hashes.
- Ran exact before/after extraction on five public dbt projects. Four pairs had
  a manifest-visible exposure; one successful no-op pair established an explicit
  confirmatory exclusion rule.
- Added registry hash enforcement and zero-filled absent resource-type deltas.
- Declared runtime and test dependencies in package metadata. CI now installs the
  package without masking failures, runs both matrix jobs independently, and uses
  the Node 24 GitHub action releases.

### Corrections

- Constant-input permutation tests now return `rho=NaN, p=1.0` instead of the
  minimum attainable p-value.
- Corrected the README statement about phase five. It reproduces centrality-based
  core-asset prediction but does not evaluate D1-D4 incremental value.

### Null model B had never run (2026-08-04)

The layer-stratified permutation result is the paper's headline negative
finding, and until now no artifact contained it. `exp_null_models_extended.py`
carried three defects that made null model B skip silently and write a summary
with only null model A in it.

- The domain join compared unpadded keys from `data/dbt_domain_summary.csv`
  (`domain_1`) against zero-padded keys from
  `artifacts/phase_3/exp_2b_dbt_domain_descriptors.csv` (`domain_001`). The
  inner join returned zero rows every time. The descriptor CSV already carries
  both the descriptor and the target on the canonical key, so the join is gone.
- `permutation_spearman` was called with `n_permutations=`, which is not its
  keyword. The correct name is `n_perms=`. The zero-row join masked this.
- The permutation target was `documentation_coverage`, which is a different
  column from the `doc_rate` the headline `rho = -0.708` is computed against.
- The guard `if 'null_b_result' in dir()` swallowed the skip. A missing null
  model B now raises instead of writing a partial summary.

Rerunning reproduces the published claim exactly. `rho = -0.708` on n = 18
domains, layer-stratified permutation `p = 1.000`, null rho std `0.0`. The
artifact now also records the per-stratum descriptor spread, which shows D3 is
constant inside all three strata and explains why every permutation returns the
observed correlation. Null model A is unchanged to ten significant figures.

### Pointer and citation hygiene (2026-08-04)

- README now points each headline number at the artifact that contains it.
- Added `CITATION.cff` with the concept DOI, the three version DOIs, and ORCID.
- Recorded the Zenodo concept DOI `10.5281/zenodo.20099999` alongside the
  version DOI. It always resolves to the latest version.
- Corrected the preprint and analysis-brief footnotes that labelled the
  v2.1.0 archive DOI as v2.0.0.
- Updated the stale `AUC 0.897` in the README hero graphic to the current
  `0.898`, which is the value after the within-fold StandardScaler fix.
- `hari2026fractal` pointed at `github.com/mhdk1602/fractal-enterprise-graphs`,
  which returns 404 and has never existed. It is now an `@unpublished` entry
  with no URL, and the preprint states the phase 0 finding in full so the
  citation carries no load.

## Revision 2 (2026-05-09) — Mathematical and Statistical Hardening

### Security

> **OPEN as of 2026-08-04. Rotate the Zenodo API token.**
> Rotation requires an interactive login at zenodo.org/account/settings/applications
> and has not been performed. This warning stays here until it has.

- Confirmed the Zenodo API token is not committed to any repo file.
- Re-verified on 2026-08-04 across every object in the repository history,
  573 objects including unreachable and dangling blobs. No credential-shaped
  string is present in any of them. The only long alphanumeric strings in
  tracked files are the documented SHA-256 manifest hashes under
  `research/governance_change_risk/`.
- The exposure was to a conversation session, not to the repository. Git
  history therefore needs no rewrite, and the token still needs rotating.

### Code corrections

**spectral.py**
- Fixed docstring for `von_neumann_entropy()`: previously said "normalized Laplacian"; now correctly says "combinatorial (unnormalized) Laplacian L = D – A". The underlying computation was already using the combinatorial Laplacian; this was a documentation bug only.

**community_stability.py**
- Added `community_stability_index_multiseed()`: runs the D1 resolution sweep over N random seeds and returns CSI mean, std, min, max, and seed-NVI (mean pairwise NVI between seed partitions at a fixed resolution). This separates Louvain optimizer variance from true resolution instability.

**__init__.py**
- Exported `community_stability_index_multiseed`.

### Citation corrections

**references.bib**
- `dlgdg2024`: Corrected from "Wang et al., Big Data Research, 100429" to "Chen, Zhao, Li, Zhang, Long, Zhou — An open dataset of data lineage graphs for data governance research — Visual Informatics, vol. 8, no. 1, pp. 1–5, 2024, DOI 10.1016/j.visinf.2024.01.001".
- `dwbench2025`: Corrected from "Jamal et al. 2025, inproceedings" to "Ahmed & Sakar — DW-Bench: Benchmarking LLMs on Data Warehouse Graph Topology Reasoning — arXiv:2604.18964, 2026".

### Mathematical corrections in paper

**D1 section**
- Added explicit LWCC statement: D1, D3, D4 are computed on the largest weakly connected component of the undirected projection. D2 uses the full directed graph. For the production dbt graph: LWCC = 185/223 nodes (83%).
- Added Louvain stochasticity note and explanation of seed-NVI metric.
- Fixed: CSI = 0.947 (single seed) updated to CSI = 0.87 ± 0.08 over 25 seeds throughout narrative.

**D3 section**
- Fixed: "smallest nonzero eigenvalue" changed to "second-smallest eigenvalue of L on the LWCC (which is connected by construction, so λ₂ > 0 always)". This eliminates the technical inaccuracy for disconnected graphs.
- Spectral entropy description: "Von Neumann entropy of the normalized Laplacian" changed to "Von Neumann-style entropy of the combinatorial (unnormalized) Laplacian" in code docstring.

**D4 section**
- Added clarification that LWCC is used (as already implemented in code; now stated in paper).

### New experiments

**exp_d1_seed_robustness.py** (new)
- 25 seeds per graph on dbt manifest, 2 synthetic graphs, 15 DLG-DG-23 graphs.
- Key result: dbt CSI = 0.87 ± 0.08 (range 0.68–1.00), seed-NVI = 0.062.
- DLG-DG-23 mean CSI = 0.85 ± 0.06, generally seed-stable.

**exp_null_models_extended.py** (new)
- Null Model A: Layer-preserving DAG rewiring (100 rewirings, 22.8% swap acceptance).
  D1 z = +2.68**, D3 alg. conn. z = −2.27**, D3 Fiedler bim. z = −1.50 ns.
  Note: only 11% of rewired graphs remain DAGs — treat as stress test.
- Null Model B: Layer-stratified governance label permutation (5,000 permutations).
  D3 alg. conn. vs doc_rate: p = 1.000 — D3 is constant within each layer stratum.

**exp_statistical_robustness.py** (new)
- Five domain subsets for D3 algebraic connectivity vs documentation rate.
- Key result: Subset A (all N≥5, n=18) FDR_p=0.029; Subset B (internal edges, n=6) FDR_p=0.189.
- The D3 correlation does not survive restriction to domains with internal edges.

### Claims revised (all weakened where evidence demands)

- Abstract: D3 correlation now qualified with subset robustness finding.
- "The Negative D3–Governance Correlation" section (formerly): Retitled to "The D3 Correlation Is Between-Layer, Not Within-Layer". Conclusion changed from "genuine organizational dynamic" to "between-layer architectural pattern; within-layer governance signal not detected."
- Discussion D3 paragraph: Updated to reflect honest negative finding.
- D1 CSI point estimate changed to seed-robust mean ± std throughout.

### New tables added
- Table (D1 seed robustness): CSI mean ± std for dbt, synthetic, DLG-DG-23 graphs.
- Table (layer-preserving null): z-scores for D1–D4 under layer-preserving rewiring.
- Table (subset robustness): D3 alg. conn. vs doc_rate for 5 domain subsets.

### Publication readiness
- PDF now 16 pages, 9 tables.
- Zenodo version DOI 10.5281/zenodo.20209148. The API token must be rotated
  before the next API use, see the Security note above.
- SSRN-ready: keywords added, affiliation set to "Independent Researcher".
