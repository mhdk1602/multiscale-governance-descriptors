# CHANGELOG

## Unreleased: Governance-Mediated Change Risk

### Longitudinal dbt lineage corpus, two projects to 154 (2026-08-04)

The longitudinal study in `artifacts/phase_4/` rested on Cal-ITP and Mattermost,
106 snapshots between them. `artifacts/phase_4_corpus/` adds a census of the
public dbt population beside it. **154 projects, 3,586 monthly snapshots, 566
cumulative project-years, 2016-07-27 to 2026-08-04.** Nothing in
`artifacts/phase_4/` was changed.

Sampling frame of 3,718 repositories, recorded per entry in
`sampling_frame.csv`, from three strata.

- The 20 entries in `InfuseAI/awesome-public-dbt-projects`.
- GitHub repository search over five dbt topics, each split into ten star bands.
  The search API serves at most 1,000 results per query and `topic:dbt` alone
  reports 3,944. 1,951 repositories.
- GitHub code search for `filename:dbt_project.yml`, split into twelve
  repository-size bands for the same reason. GitHub reports 5,340 hits, of which
  the partitioning recovers 2,207.

Only conditions under which no monthly series can exist were allowed to exclude,
so 631 repositories were screened in and cloned rather than filtered on how they
look at HEAD.

| stage | n |
|---|---|
| candidate population | 3,718 |
| excluded, under 40 commits on the default branch | 2,275 |
| excluded, under 12 months between creation and last push | 811 |
| excluded, metadata unavailable | 1 |
| screened in and cloned | 631, plus 13 curated entries the screen could not reach |
| extracted successfully | 419 |
| extracted with gaps | 39 |
| extraction failed | 186 |
| in corpus | **154**, of which 33 `core` and 121 `extended` |

Failures are a finding, not attrition to hide. 81 repositories carry no
`dbt_project.yml` anywhere in their history, which means the code-search index
saw one that has since been deleted. 78 declare a `dbt_project.yml` whose model
directory was never committed, almost all adapters, macro libraries and dbt
tooling. 25 resolve model paths that hold no SQL at any sampled commit. 2 could
not be cloned. Every one is in `excluded.csv` with its reason.

#### The curated list does not contain twenty usable projects

Run end to end, `gitlab-data/analytics` returns 401 and
`FlipsideCrypto/sql_models` returns 404, both dead since the list was written.
`dagster-io/dagster-open-platform` publishes `dbt_project.yml` in a mirror whose
`models/` directory was deleted, so it extracts to zero snapshots. Eight more are
demonstration repositories yielding one or two monthly snapshots. On a
12-snapshot floor the curated list contributes five projects.

#### D1 was never reproducible

`extract_lineage_at_commit` in `exp_longitudinal_dbt.py` built each graph with
`g.add_nodes_from(model_names)` where `model_names` is a Python set. String set
iteration order depends on `PYTHONHASHSEED`, which CPython randomises per
process, and NetworkX's Louvain is an order-sensitive greedy pass. `D1_csi` and
`D1_n_comm` therefore differ between runs of identical code on an identical
repository.

Re-running the shipped script on a fresh Cal-ITP clone reproduces N, M,
`D2_max_gini` and `D4_cycle_rank_norm` exactly on all 50 shared commits, and
`D3_alg_conn` to 9e-15. `D1_csi` differs by up to 0.286 and `D1_n_comm` by four
communities. Holding one commit's graph fixed at N=360 and M=421, three hash
seeds give CSI of 0.6429, 0.7857 and 0.5000.

Measured across the corpus in
`artifacts/phase_4_corpus/d1_order_sensitivity.json`, 40 real snapshots under 12
node-order permutations each:

| descriptor | median range | max range |
|---|---|---|
| `D1_csi` | 0.0714 | 0.5714 |
| `D1_n_comm` | 0 | 5 |
| `D2_max_gini` | 0 | 0 |
| `D4_cycle_rank_norm` | 0 | 0 |
| `D3_alg_conn` | 2.2e-15 | 1.6e-14 |

**This changes a claim.** `table3_summary_statistics.csv` reports `D1_csi` with
sd 0.123 over n=106. The order-induced range reaches 0.571 on a single graph.
`D1_csi` is also one of three descriptors monitored in
`drift_events_refined.csv`, so an unknown share of the 44 reported drift events
are hash-seed artifacts rather than lineage changes. The corpus inserts nodes in
sorted order under `PYTHONHASHSEED=0`, which removes the dependence, but D1 in
the corpus is not comparable to D1 in the two-project artifacts.

#### The growth claim does not survive

The two-project release reports node growth of 8.53x and 14.69x, which reads as
"dbt lineage graphs grow steeply". Over 154 projects the median is 4.09x, and
Cal-ITP and Mattermost sit at the 71st and 78th percentiles. Measured instead
from the first snapshot at or above the N>=10 inclusion floor, which removes the
multiple a project earns merely for starting from an empty repository, the
median is **2.41x** and 12 percent of projects end smaller than they started.
`corpus_index.csv` carries both as `node_growth_multiple` and
`node_growth_from_first_viable`.

Contraction behaves the same way. 74 percent of projects never fall below their
peak at all, so Mattermost's 21.9 percent net contraction is the tail rather
than the pattern. The drift rate drops from 0.415 to 0.279 events per snapshot,
and 36 of 154 projects show no drift event at any threshold.

#### Three further defects, each of which moved a measurement

- **Vendored packages counted as project models.** Mattermost's
  `transform/snowflake-dbt/dbt_modules/dbt_utils/models` belongs to dbt_utils.
  `dbt_modules/`, `dbt_packages/`, `target/` and `integration_tests/` are now
  excluded.
- **Several dbt projects in one repository were unioned.** Models in separate
  dbt projects cannot `ref()` each other, so the union is disconnected, and
  `_to_undirected_connected` in both `spectral.py` and `community_stability.py`
  reduces a disconnected graph to its giant component. The smaller project was
  counted in N and M and dropped from D1 and D3. One dbt project is now tracked
  per repository, the one whose model paths carry the most commits.
- **A relocated project was split in two.** Datadex moved from `models/` to
  `dbt/models/` on 2023-04-11, and treating the two configs as rivals discarded
  40 percent of its history. Configs whose model-path commit intervals overlap
  by less than 20 percent of the shorter interval are chained into one series.
  Mattermost's two concurrent projects overlap for two years and stay separate.

#### The descriptors do not always describe the whole graph

Because D1 and D3 run on the giant component, a sparse lineage graph reports a
large N while the descriptors see a fraction of it. `Health-Union/dbt-xdb` has
51 nodes and 5 edges, `EqualExperts/dbt-unit-testing` 55 and 3. Both are dbt
packages rather than analytics projects. Every snapshot now carries
`n_components`, `giant_component_frac` and `isolated_frac`. The corpus median
giant component is 0.794 of N in the `core` tier and 0.370 in `extended`, so on
a typical extended project the descriptors describe barely a third of the models
they are reported against.

#### Reproduction gate

Both reference projects reproduce under fully automatic model-path detection,
with no hand-supplied paths. Mattermost gives 55 snapshots, all 55 commits shared
with the recorded artifact, and N, M and `D2_max_gini` identical to the last
digit. Cal-ITP gives 53 against the recorded 51, because the repository gained
three months of history, and every one of the 50 shared commits is identical.

#### Tool and tests

- `src/governance_descriptors/dbt_lineage.py` replaces the two-project script.
  Snapshots are read with `git ls-tree` and `git cat-file --batch` instead of
  `git checkout`, so nothing is written to the worktree and repositories can be
  read concurrently. Cal-ITP's 53 snapshots take under 30 seconds.
- `tests/test_dbt_lineage.py` adds 37 unit tests including a regression for each
  defect above. The suite goes from 48 to 85.
- `experiments/phase_4/dbt_corpus/` holds the pipeline and a README with the
  exact commands.
- `MANIFEST.json` pins every sampled commit SHA and carries a SHA-256 for every
  other file in the release.

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

### Subset robustness artifact regenerated (2026-08-04)

`artifacts/phase_3/exp_statistical_robustness_summary.json` predated the
constant-input permutation fix and still carried its output. Subset E read
`rho = NaN` beside `fdr_p = 9.999e-05`, which presented an undefined
correlation as the most significant row in the table.

Regenerated against the corrected `permutation_spearman`. Subsets A, B, and C
are unchanged. Two rows moved.

| Subset | n | rho | FDR p before | FDR p after |
|---|---|---|---|---|
| A, all N>=5 | 18 | -0.708 | 0.0288 | 0.0288 |
| B, internal edges only | 6 | -1.000 | 0.1890 | 0.1890 |
| C, no source-dominant | 6 | -1.000 | 0.1890 | 0.1890 |
| D, no largest domain | 17 | -0.806 | 0.0006 | 0.0038 |
| E, internal + no largest | 5 | undefined | 0.0001 | 1.0000 |

Subset D moved because Benjamini-Hochberg is applied across every test in a
subset. Eight or more constant-input tests in subset D previously returned the
minimum attainable p-value of 0.0001 with an undefined rho, which dragged the
adjustment down. With those tests correctly at p = 1.0, subset D's significance
now rests on five genuine doc_rate correlations between -0.79 and -0.81.

**This changes a claim.** Table `tab:subset` in the preprint labelled subset D
"Spurious" with the footnote "Significance driven by test\_rate constant-input
artifact". That was true of the buggy numbers and is false now. The row is
relabelled "Survives", with a footnote recording that dropping the largest
domain leaves the layer composition intact, so surviving it says nothing about
within-layer governance signal. Subset E is added to the table rather than
omitted. The paper's argument is untouched, since it rests on subset A, subset
B, and the layer-stratified permutation, all unchanged.

The summary also wrote a bare `NaN` token, which is not valid JSON under
RFC 8259 and is rejected by `JSON.parse` and most non-Python parsers. Undefined
rho is now `null` with an explicit `rho_defined` flag so it cannot be misread
as zero.

### Documented the two domain labelings (2026-08-04)

`data/dbt_domain_summary.csv` and
`artifacts/phase_3/exp_2b_dbt_domain_descriptors.csv` describe the same 26
domains and the same 223 nodes under two unrelated anonymization passes.
Added `data/README.md` recording which is authoritative and why.

`data/dbt_nodes.csv` is ground truth. The descriptors CSV is the authoritative
rollup, reproducing node-level `N`, `doc_rate`, and `test_rate` exactly on the
canonical zero-padded labels. The summary file is rounded to 4 dp, names its
columns `documentation_coverage` and `test_coverage`, and uses an unpadded
labeling that maps to nothing else in the repository. Of the six domains
matchable without ambiguity, none keeps its own number. Sorted against each
other the two files agree to 4.3e-05, so only the row-to-label assignment
differs. Padding the keys does not repair the join, it aligns the wrong rows
and produces documentation values off by up to 1.0.

Neither column is removed. No code reads the summary file today.

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
