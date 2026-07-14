# Public Extraction Feasibility Pass

- **Run date:** 2026-07-13
- **Protocol:** `governance-change-risk-v1` under preregistration version 0.2
- **Purpose:** test exact-ref extraction and identify measurement failures before
  outcome sampling

## Result

Eight public repositories were screened. Six exact pairs were attempted across
six projects; five built successfully. Those five pairs cover 9–908 lineage
nodes and 6–1,235 directed edges. Four contain a manifest-visible exposure. The
fifth, Mattermost PR 1686, generated valid manifests at both refs but changed no
enabled resource fingerprint or lineage edge. It is an extraction success and a
confirmatory no-op.

No predictive model was fitted. The pass was selected to exercise collection
paths, not to estimate adverse-event prevalence. Cal-ITP PR 5392 was deliberately
included as a repair-linked positive control, so these rows must not be treated
as an outcome-random sample.

| Project and change | Exact extraction | Nodes | Edges | Manifest-visible delta | Decision |
|---|---:|---:|---:|---|---|
| [CalData PR 590](https://github.com/cagov/data-infrastructure/pull/590) | yes | 41 → 47 | 35 → 39 | 6 nodes and 4 edges added | eligible |
| [Cal-ITP PR 5392](https://github.com/cal-itp/data-infra/pull/5392) | yes | 885 → 885 | 1,235 → 1,235 | 3 modified nodes; 16.7% downstream reach | eligible, positive control |
| [MDSFest PR 2](https://github.com/dagster-io/mdsfest-opensource-mds/pull/2) | yes | 9 → 9 | 6 → 6 | 1 modified node | eligible |
| [NBA Monte Carlo PR 193](https://github.com/matsonj/nba-monte-carlo/pull/193) | yes | 78 → 79 | 164 → 169 | 1 added and 4 modified nodes; 5 edges added | eligible |
| [Mattermost PR 1686](https://github.com/mattermost/mattermost-data-warehouse/pull/1686) | yes | 908 → 908 | 615 → 615 | none | extraction audit only |

The Cal-ITP case is a useful measurement check. Its topology is unchanged, yet
three fingerprints change and their downstream closure covers 148 of 885 nodes.
[PR 5427](https://github.com/cal-itp/data-infra/pull/5427), merged two days later,
states that PR 5392 broke `dbt_all` because fields did not propagate through an
intermediate model. This is candidate evidence, not an adjudicated study label.
Independent descriptor-blind review is still required.

## Screened-out projects

| Repository | Result | Reason |
|---|---|---|
| [Danish Democracy Data PR 20](https://github.com/bgarcevic/danish-democracy-data/pull/20) | attempted, excluded | The PR moves the dbt project from repository root into `dbt/`; one common project path cannot represent both refs. This is an inseparable repository migration. |
| [Filecoin Data Portal](https://github.com/davidgasquez/filecoin-data-portal) | screened out | The screened head no longer contains a dbt project. |
| [Fake Star Detector](https://github.com/dagster-io/fake-star-detector) | screened out | No eligible merged dbt change was found in the screened history. |

## Measurement observations

The generated feature table contains five rows across five projects. Raw
manifests and the path-bound derived table remain outside Git.

Control coverage is sparse and asymmetric in this small screen:

- model contract coverage is zero in all five post-change manifests;
- owner coverage ranges from zero to 0.56%;
- model test coverage ranges from zero to 68.97%;
- description coverage ranges from zero to 95.74%;
- source freshness coverage is 100% in all five pairs.

These values do not support a moderation estimate. The confirmatory project
screen must establish cross-project and within-project control variance before
labels are opened. A control with no estimable variation will be reported as
such, not replaced after outcome inspection.

Only the NBA pair changes the multiscale summaries in this pass. CalData adds
peripheral resources without changing the largest-component summaries, while
Cal-ITP and MDSFest change fingerprints under fixed topology. This is a direct
test of the research premise: ordinary code and graph-diff features may carry
most of the usable signal. The preregistered ablation retains that possibility
as a valid negative result.

## Protocol 0.3 feature rerun

The same five immutable manifest pairs were rebuilt under
`governance-change-risk-v2` after the pre-outcome protocol amendment. No label
was assigned and no model was fitted. The derived CSV remains outside Git; its
SHA-256 is
`6fabda018e5e1fdad85abea45865469a75780357375f90fd4cbd5c32d0b1c7bd`.

The added `change_geometry__` family contains 24 fixed before, after, and delta
features. All four manifest-visible pairs have a nonzero post-change local
geometry, two have a nonzero before/after geometry delta, and the Mattermost
no-op remains zero. Cal-ITP and MDSFest illustrate why both post-change position
and delta are retained: their fingerprints change at fixed topology, so the
changed models occupy an affected region even though the region's topology does
not change.

This is a measurement result, not evidence of predictive value. The Cal-ITP
positive control remains outside confirmation. Exact selected values and the
derived-table hash are recorded in
`pilot_feature_rerun_2026-07-13.json`.

## Reproduction boundary

The first four projects were parsed with dbt Core 1.9.10. Cal-ITP was parsed with
dbt Core 1.10.8 and dbt-bigquery 1.10.2 to match its dependency family. Each
manifest was generated in a detached temporary worktree at the recorded SHA.
The machine-readable provenance file records refs, artifact hashes, dbt versions,
and aggregate graph differences. Generated manifests can contain compiled SQL
and environment metadata, so they are intentionally omitted from the repository.
