# Adverse-Event Annotation Codebook

Annotators must not see descriptor values, feature tables, predictions, or the
other annotator's decision.

## Primary decision

Assign `1` only when all conditions hold:

- a revert, hotfix, rollback, or fix-inducing change occurs within 30 days;
- the repair touches the same model, a dependent model, or the same declared
  contract or source interface;
- the later evidence identifies an error introduced or exposed by the focal
  change; and
- the relationship is more specific than temporal proximity.

Assign `0` when the full window is observable, reasonable searches find no
qualifying repair, and no issue or review discussion reports an adverse event.

Assign `ambiguous` when a repair is plausible but causation cannot be determined.
Assign `censored` when repository history, issues, checks, or the full time window
are unavailable. Neither status enters the confirmatory table.

## Event types

Choose one primary type and any applicable secondary types:

- `schema_contract`: removed or renamed column, type mismatch, incompatible
  source or model contract;
- `data_quality`: null, duplicate, stale, incomplete, or semantically invalid
  output;
- `logic`: incorrect transformation, filter, join, aggregation, or metric;
- `operational`: failed build, resource exhaustion, scheduling, or deployment;
- `performance`: material regression in runtime or warehouse consumption;
- `policy_access`: unauthorized exposure, ownership breach, or policy violation;
- `other`: qualifying event outside the taxonomy, with written explanation.

## Evidence hierarchy

Prefer, in order:

1. maintainer statement or linked incident;
2. repair PR description and diff;
3. failing CI, dbt test, or contract result linked to the focal change;
4. issue discussion with a reproducible failure;
5. strong same-file and same-logic repair evidence.

A commit message containing “fix,” “revert,” or “hotfix” is a search aid, not
evidence by itself.

## Required fields

Each annotation records the focal change URL, window end, decision, primary event
type, candidate repair URL, evidence excerpt or summary, affected models,
confidence (`high`, `medium`, `low`), annotator identifier, and timestamp.

The adjudicator sees both completed forms only after independent submission.
