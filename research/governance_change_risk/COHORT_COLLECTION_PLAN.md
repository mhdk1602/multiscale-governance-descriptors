# Consecutive Cohort Collection Plan

This plan begins only after protocol 0.3 and feature spec v2 are committed. Its
purpose is to estimate event prevalence, extraction yield, annotation cost, and
control variance without choosing changes because their outcomes are known.

## Stage 0: project screen without outcome inspection

Select 8--12 mature public dbt projects using repository-level criteria fixed in
advance:

- at least 25 merged dbt-touching changes with a fully elapsed 30-day window;
- exact merge and parent SHAs available;
- repeatable manifest generation at sampled historical refs;
- active CI or an observable project check history;
- sufficient variation in at least one declared control across recent manifests;
- no requirement to read incident, repair, or revert evidence during screening.

Project screening may inspect repository structure, dependency files, dbt
versions, merge timestamps, changed paths, and manifest-build success. It must
not inspect later repairs or assign event labels. Projects with zero contract
coverage are not automatically excluded: tests, descriptions, ownership, or
freshness may still vary. The screen reports every criterion and rejection.

Two projects are reserved before annotation as untouched confirmation projects.
Their records and terminal time periods remain closed until the model and all
analysis code are frozen.

## Stage 1: 300-change prevalence cohort

Export a complete ordered ledger of merged dbt-touching changes from each
selected project. Use only fields needed for eligibility and exact extraction.
Do not export PR bodies, issue comments, repair links, or outcome fields into the
selection ledger.

Take consecutive records within each project's fixed calendar window until the
combined eligible target reaches 300. Keep pre-outcome exclusions in the ledger
with a reason. The `sequence_index` must be contiguous within each project, so a
record cannot disappear after outcome inspection.

Freeze the ledger before generating labels:

```bash
governance-change-risk freeze-cohort \
  --candidates /restricted/prevalence_candidates.jsonl \
  --protocol-version 0.3 \
  --output /restricted/prevalence_cohort_frozen.json
```

The command rejects outcome fields, non-immutable refs, duplicate changes,
sequence gaps, and unexplained exclusions. It writes a deterministic cohort ID
over the ordered records and protocol versions.

## Stage 2: exact manifests and extraction audit

For every included change:

1. generate before and after manifests in detached worktrees;
2. store artifact hashes, dbt versions, commands, and extraction logs;
3. build feature spec v2 without opening outcome evidence;
4. classify failures by stage and reason;
5. retain manifest no-ops in the audit but exclude them from confirmation under
   protocol 0.3.

The extraction report answers four questions before annotation starts:

- What fraction of consecutive candidates produces two valid manifests?
- What fraction has a manifest-visible exposure?
- Do governance controls vary within and across projects?
- Are local geometry features estimable without pathological saturation or
  scale degeneracy?

If a control is constant, it is marked non-estimable. It is not replaced with a
new moderator after labels are opened.

## Stage 3: descriptor-blind annotation

Two reviewers independently inspect each focal change and its fixed 30-day
window under `ANNOTATION_CODEBOOK.md`. They cannot see descriptor values, feature
tables, predictions, or the other reviewer's decision. Automated searches may
nominate candidate repairs; they cannot assign labels. A third reviewer resolves
disagreements after independent forms are locked.

Report agreement before adjudication, time per record, evidence type, ambiguous
and censored counts, and event prevalence with a project-cluster interval.

## Stage 4: set the final sample once

The prevalence cohort determines the final collection size by simulation. A
target of 200 adverse events implies the following approximate eligible counts
before inflation for manifest failures, ambiguity, and project clustering:

| Observed event rate | Eligible changes for 200 events |
|---:|---:|
| 2% | 10,000 |
| 5% | 4,000 |
| 10% | 2,000 |
| 15% | 1,334 |

If 200 events is operationally infeasible, revise the target once using the
prevalence and variance estimates, record the decision as a protocol deviation,
and narrow the estimand. Do not repeatedly collect until a preferred interval
appears.

## Stage 5: confirmation firewall

Before the first model fit:

- freeze the adjudicated table hash;
- freeze every feature column and model specification;
- freeze the minimally useful review-allocation margin;
- confirm that Cal-ITP PR 5392 and every other selected feasibility case are
  absent from the confirmation corpus;
- run tests on synthetic labels only;
- then open the training projects, followed by the two untouched projects once.

Paper 2 advances only if the project-held-out result changes review allocation,
not merely because an isolated coefficient or ROC AUC is nonzero.
