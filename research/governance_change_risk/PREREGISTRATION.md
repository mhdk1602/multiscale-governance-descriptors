# Preregistration: Governance-Mediated Lineage Change Risk

- **Protocol version:** 0.2
- **Status:** amended after extraction feasibility; no outcome model has been fitted
- **Date:** 2026-07-13
- **Primary analysis code:** `src/governance_descriptors/change_risk/`

## Research question

Do multiscale changes in a typed data-lineage graph add out-of-repository
predictive information about post-merge adverse events beyond ordinary code and
graph-diff statistics?

The secondary question is whether post-change governance controls are associated
with weaker risk from a given changed downstream blast radius. This observational
interaction is not interpreted as a causal effect. A later prospective CI trial
would be required for that claim.

## Study unit and population

The unit is a merged pull request, or a single commit when the host does not
retain pull-request metadata, that changes a public dbt project. Every unit must
have:

1. an immutable before ref and after ref;
2. a dbt `manifest.json` generated at each ref;
3. a merge timestamp and stable change identifier;
4. a 30-day observable outcome window;
5. a nonzero manifest-visible node fingerprint or edge-set change; and
6. a descriptor-blind adjudicated outcome.

Fingerprint-only changes remain eligible because SQL, contracts, tests, and
metadata can change semantics without changing graph topology. Pairs with no
manifest-visible exposure remain in the extraction audit but do not enter the
confirmatory table.

The feasibility pass will use five to eight mature public projects. It estimates
event prevalence, manifest-generation success, project clustering, and annotation
cost. The confirmatory corpus will target 20–50 projects and at least 200
adjudicated adverse events. Its final size will be set by simulation using pilot
prevalence and between-project variance, not by repeated inspection of p-values.

The public engineering pass is not an event-prevalence sample. It contains a
deliberately selected repair-linked case to test whether the collection boundary
captures a known failure. Prevalence estimation starts with consecutive eligible
changes sampled without outcome inspection.

## Primary outcome

`outcome_primary = 1` when reviewers confirm that the focal change caused or
materially contributed to a revert, hotfix, rollback, or fix-inducing change
within 30 days of merge. Temporal proximity and a repair keyword are insufficient.
The causal link must be supported by the later diff, issue, pull-request
discussion, failing check, or maintainer statement.

`outcome_primary = 0` when the full window is observable and no qualifying event
is found. Ambiguous and censored changes are excluded from confirmation and
retained in a separate audit table.

Post-merge workflow failure, review duration, and tests added during review are
secondary outcomes. They will not replace the primary outcome after data are
opened.

## Exposures and feature families

The locked ordinary baseline contains:

- node and edge additions, removals, and net changes;
- changed-node fraction and edge-edit fraction;
- degree-distribution Jensen–Shannon distance;
- weak-component and longest-path change;
- changed downstream descendants and depth-five blast radius;
- resource-type count changes; and
- locked repository covariates added before outcome review: lines added, lines
  deleted, files changed, the author's prior merged-change count, and failed
  workflows in the preceding 30 days. Manifest node counts and changed models
  already encode repository size and model churn.

The governance family contains post-change coverage and before/after deltas for
tests, contracts, declared owners, descriptions, and source freshness. Explicit
blast-radius-by-control interactions test the secondary moderation question.

The multiscale family contains before, after, and delta values for:

- D1 community stability and modularity at fixed resolution range and seed;
- D2 blast-radius Gini curve summaries through depth five;
- D3 normalized spectral gap, spectral entropy, and Fiedler bimodality; and
- normalized cycle rank.

The study does not call cycle rank persistent homology. The earlier real-data
analysis showed that its H1 summary collapsed to this simpler statistic.

## Hypotheses

**H1, primary.** `baseline + multiscale` has greater leave-project-out average
precision than `baseline` alone.

**H2, secondary.** Adding multiscale features to `baseline + governance` improves
leave-project-out average precision.

**H3, directional and secondary.** Coefficients for prespecified
blast-radius-by-control interactions are negative in most held-out-project fits.
This is evidence of predictive moderation, not proof that adopting a control
causes the attenuation.

## Models and validation

All four model specifications are fixed:

1. baseline;
2. baseline plus governance;
3. baseline plus multiscale; and
4. baseline plus governance plus multiscale.

Each uses median imputation, standardization, and class-balanced logistic
regression with `C=1.0`. Imputation and scaling are fitted inside each training
fold. There is no outcome-guided feature selection.

The primary validation is leave-one-project-out. A secondary terminal-time test
holds out the latest 20% of changes in every project. Two untouched projects and
their terminal periods will be reserved after feasibility for final confirmation.

The primary metric is incremental average precision. Supporting metrics are
calibration through Brier score, ROC AUC, and recall at a fixed 10% review budget.
Uncertainty for incremental average precision uses a project-cluster bootstrap.

## Negative controls and sensitivity tests

- Documentation-only changes form a negative-control exposure set.
- Outcomes are permuted within repository and calendar block.
- Changed units are matched to same-churn units within repository.
- A typed DAG-rewiring null preserves node type, layer, and in/out degree where
  feasible.
- The primary result is repeated after excluding changes with low manifest
  extraction confidence or a dbt-version transition.
- D1 is repeated across seeds as a sensitivity test; it is not allowed to choose
  the seed with the strongest result.

## Exclusions

A change is excluded from confirmation when either manifest cannot be generated,
the refs are mutable or missing, the 30-day window is censored, the change mixes
an inseparable repository migration with ordinary model work, or adjudicators
cannot determine whether a candidate repair addresses the focal change. A pair
with no changed node fingerprint and no changed edge is also excluded because it
does not expose the hypothesized mechanism.

Exclusions and extraction failures are reported by project and calendar month.
They are never silently removed after inspecting feature values.

## Blinding and adjudication

Two reviewers independently inspect the focal change and its 30-day outcome
window without descriptor values or model scores. They record event status,
event type, evidence link, and confidence. Disagreements are resolved by a third
reviewer. Agreement is reported before adjudication.

Automated keyword and overlap searches only nominate evidence. They cannot assign
the primary label.

## Decision rule

The empirical claim advances only if the held-out incremental average-precision
interval and fixed-budget recall show an effect large enough to change review
allocation. The minimally useful margin will be chosen from pilot review capacity
before the confirmation projects are opened.

A null result is retained. The corpus, extraction-failure analysis, calibration,
and descriptor ablations remain reportable without substituting another outcome.

## Deviations

Every deviation receives a dated entry below before the affected analysis is
run. The entry must state the reason, affected records, and whether the deviation
was decided with outcome access.

| Date | Deviation | Outcome access? | Consequence |
|---|---|---|---|
| 2026-07-13 | Require a nonzero manifest-visible node fingerprint or edge-set delta; retain no-op pairs in the extraction audit | Yes, for one deliberately selected positive-control case; the rule was prompted by the Mattermost no-op pair before model fitting | No-op pairs cannot enter confirmation |
