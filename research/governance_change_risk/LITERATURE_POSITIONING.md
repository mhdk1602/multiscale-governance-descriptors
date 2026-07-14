# Evidence Map for Lineage Change Risk

**Search date:** 2026-07-13
**Scope:** primary papers and official dbt documentation relevant to per-change
risk, dependency propagation, dynamic graphs, local multiscale geometry, and
executable governance controls.

## The research gap

The proposed study sits between three mature research programs that have rarely
been joined at the same unit of analysis.

Just-in-time defect prediction assigns risk to a commit when it is submitted.
Dependency and change-impact work traces how a changed component can affect
other components. Dynamic-graph research detects unusual graph snapshots.
None of these, in the sources reviewed here, tests whether an exact before/after
data-lineage change predicts a later, manually adjudicated production repair,
or whether executable data controls attenuate that association.

That distinction is the paper's plausible contribution. It is narrower and more
testable than a claim that graph topology reveals governance maturity.

## 1. Change-level risk requires temporal and effort-aware evaluation

[Kamei et al. (2013)](https://doi.org/10.1109/TSE.2012.70) moved defect
prediction from modules to individual changes and evaluated inspection effort,
not classification alone. That establishes the appropriate unit and the need to
report how many adverse changes can be found under a fixed review budget.

Outcome construction is the weak point. The original SZZ procedure infers
bug-introducing changes by tracing lines changed in a later fix.
[SZZ Unleashed](https://arxiv.org/abs/1903.01742) documents the heuristic and its
reproducibility problems. Our primary outcome therefore cannot be assigned by a
keyword, temporal proximity, or same-file overlap. Those signals may nominate a
candidate repair, but two descriptor-blind reviewers must establish the link.

[JITLine](https://arxiv.org/abs/2103.07068) is especially pertinent to the
protocol. Its replication found that CC2Vec performance fell sharply when the
test set was removed from representation learning. The lesson is procedural:
every transformation, including imputation, scaling, vocabulary construction,
and any learned graph representation, must be fitted inside the training fold.
The present study uses fixed engineered features and fold-local preprocessing.

JITLine also reports effort-aware measures such as recall at a fixed percentage
of inspected lines. For lineage changes, review effort is better represented by
the number of changes or changed models inspected. The preregistered 10% review
budget is therefore a practical co-primary decision aid beside incremental
average precision.

## 2. Graph structure can help, but the result is conditional

[Zimmermann and Nagappan (2008)](https://www.microsoft.com/en-us/research/publication/predicting-defects-using-network-analysis-on-dependency-graphs/)
found that dependency-network measures improved defect recall for Windows Server
2003 binaries relative to code-complexity measures. A later multi-project study,
[Gong et al. (2022)](https://arxiv.org/abs/2202.06145), found improvements in
only five of nine prediction settings and recommended separating ego from global
network measures. This mixed record supports an ablation study, not an assumed
graph advantage.

[Bryan and Moriano (2023)](https://doi.org/10.1371/journal.pone.0284077) frame
just-in-time prediction as edge classification on developer--file contribution
graphs. Their result proves that graph-derived change context can be predictive,
but their graph represents collaboration rather than execution dependency. The
lineage study asks whether a changed model's position in a dataflow graph adds
information beyond churn, author history, and prior workflow failures.

[Change Impact Graphs](https://doi.org/10.1016/j.infsof.2009.04.018) propagate
historical changes through a dependence graph to help diagnose failures in
unchanged components. That mechanism is close to downstream lineage blast
radius. The proposed study differs by estimating prospective post-merge risk and
by comparing ordinary reachability with change-centred geometry at several
scales.

## 3. Whole-graph change is a baseline, not the final representation

[DeltaCon](https://arxiv.org/abs/1304.4657) measures change between graphs with
known node correspondence through differences in node-affinity structure.
[Laplacian Anomaly Detection](https://arxiv.org/abs/2007.01229) embeds each
snapshot with its Laplacian spectrum and compares short- and long-term windows.
[MultiLAD](https://arxiv.org/abs/2302.01204) extends that idea to several graph
views. These are appropriate baselines for longitudinal anomaly detection.

They do not solve the present measurement problem. A dbt change can modify SQL,
tests, contracts, or column metadata while leaving the node and edge sets fixed.
The Cal-ITP feasibility control demonstrates exactly that case: three model
fingerprints changed under fixed topology, with a large downstream closure.
Global snapshot descriptors are consequently retained as the primary test, but
they cannot be the only graph representation.

## 4. Local multiscale geometry supplies a principled amendment

[Song, Havlin, and Makse (2005)](https://doi.org/10.1038/nature03248) define
network self-similarity through box covering and a scale relation between box
count and box size. That is a global property and should not be inferred from a
five-hop downstream profile.

[Silva and Costa (2012)](https://arxiv.org/abs/1209.2476) instead estimate
node-level dimensional patterns across scales and use them to identify regions
and boundaries. [Peach et al. (2022)](https://www.nature.com/articles/s41467-022-30705-w)
define relative, local, and global dimension from diffusion, showing that local
dimension changes with scale and boundary effects. These papers support a
change-centred, scale-indexed geometric representation while warning against
calling every growth slope a fractal dimension.

Community structure also changes with resolution.
[Markov Stability](https://doi.org/10.1073/pnas.0903215107) treats diffusion time
as an intrinsic resolution parameter, and
[PyGenStability](https://arxiv.org/abs/2303.05385) operationalizes multiscale
partition analysis for directed and undirected graphs. The present extractor
uses a smaller fixed resolution grid because the study needs deterministic,
auditable features rather than an outcome-guided search for a preferred scale.

The resulting `change_geometry__` family contains:

- directed cumulative ball growth through depth five;
- a finite-scale growth exponent and fit diagnostic;
- normalized ball-growth area and saturation depth;
- conductance and cycle rank of the affected subgraph; and
- community-boundary crossing at resolutions 0.5, 1.0, and 2.0.

Every measure is computed before, after, and as a delta. The family is secondary
and separately named. A null primary result for global D1--D4 cannot be replaced
by a positive local result without that distinction.

## 5. Governance variables must correspond to executable controls

The official dbt documentation gives the operational interpretation of each
moderator. [Model contracts](https://docs.getdbt.com/docs/mesh/govern/model-contracts)
verify column names and types before a model builds; enforcement depends on the
materialization and data platform. [Data tests](https://docs.getdbt.com/docs/build/data-tests)
query built resources for failing records. [Source freshness](https://docs.getdbt.com/docs/deploy/source-freshness)
checks whether upstream data arrived within declared thresholds. The
[manifest artifact](https://docs.getdbt.com/reference/artifacts/manifest-json)
records resources and dependency maps at an exact project state.

Coverage is not equivalent to effectiveness. A declared contract may cover the
wrong columns, a test can assert a weak condition, and ownership metadata may be
stale. The study can estimate predictive moderation by declared controls, not a
causal effect of adopting governance.

An empirical study of data-pipeline quality by
[Foidl et al. (2024)](https://doi.org/10.1016/j.jss.2023.111855) examined 600
issues from 11 GitHub projects and 400 Stack Overflow posts. It found that data
cleaning contained the largest share of observed data-related issues and that
data-type problems were a frequent root cause. This supports retaining logic,
data-quality, schema/contract, and operational outcomes rather than reducing the
label to CI failure alone.

## Consequences for the study design

| Evidence | Design consequence |
|---|---|
| JIT prediction is change-level and effort-aware | Keep PR/commit as the unit; report recall at a fixed review budget |
| SZZ labels are heuristic | Require independent descriptor-blind adjudication; automation only nominates evidence |
| Test-distribution access can inflate results | Fit every learned transformation inside project-held-out folds |
| Dependency metrics help in some settings, not all | Preserve baseline-only models and publish null ablations |
| Global graph deltas miss semantic changes under fixed topology | Retain fingerprint changes and add separately named local geometry |
| Network dimension is scale-dependent | Freeze radii and resolutions; call the slope a finite-scale growth exponent |
| dbt controls have different execution semantics | Measure contracts, tests, ownership, descriptions, and freshness separately |
| Public-project controls can be nearly constant | Screen control variance before labels are opened; report non-estimable moderators |

## Claim boundary

The strongest defensible future claim is conditional: exact lineage-change
geometry may improve out-of-project allocation of review effort beyond churn and
ordinary graph differences. The data do not yet support that claim. Protocol
version 0.3 fixes the candidate feature family before a consecutive cohort is
sampled, and the deliberately selected Cal-ITP positive control is barred from
confirmation.
