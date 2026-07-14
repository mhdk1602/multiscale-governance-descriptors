# Governance-Mediated Lineage Change Risk

This is the confirmatory successor to the domain-level governance study. The
earlier paper found that lineage topology does not identify governance maturity.
This study asks a different question:

> Do exact lineage changes improve prediction of post-merge adverse events, and
> is the association between changed blast radius and harm weaker when tests,
> contracts, ownership, and freshness controls are present?

The unit is a merged pull request or commit. Each row comes from exact dbt
manifests generated at its before and after refs. Monthly snapshots, SQL regular
expressions, and commit-message labels are prohibited.

## Study assets

| File | Purpose |
|---|---|
| `PREREGISTRATION.md` | Locked hypotheses, outcomes, feature families, exclusions, and validation |
| `LITERATURE_POSITIONING.md` | Primary-source evidence map and resulting design choices |
| `COHORT_COLLECTION_PLAN.md` | Outcome-blind prevalence cohort, annotation, and final-size workflow |
| `ANNOTATION_CODEBOOK.md` | Descriptor-blind adverse-event adjudication |
| `DATA_CONTRACT.md` | Manifest-pair registry and provenance requirements |
| `PILOT_FEASIBILITY_2026-07-13.md` | Five-project public extraction pass and boundary conditions |
| `pilot_provenance_2026-07-13.json` | Immutable refs, artifact hashes, and aggregate pair statistics |
| `pilot_feature_rerun_2026-07-13.json` | Version 2 feature audit over the same immutable pairs; no labels or model |
| `pilot_registry.example.jsonl` | Executable registry example using test fixtures |
| `cohort_candidates.example.jsonl` | Minimal consecutive pre-outcome selection ledger |

The implementation lives in `governance_descriptors.change_risk`. Its feature
names carry their analysis group: `baseline__`, `governance__`,
`multiscale__`, or `change_geometry__`. Global multiscale descriptors remain
the primary graph comparison. Change-centred geometry is a separately named,
pre-outcome secondary family. The evaluator selects groups by those prefixes
and fits every imputer and scaler inside the training fold.

## Commands

Collect an exact pair from two git refs:

```bash
governance-change-risk collect \
  --repo /path/to/public-dbt-project \
  --project project-slug \
  --change-id 1234 \
  --merged-at 2026-01-15T14:30:00Z \
  --before-ref '<merge-sha>^1' \
  --after-ref '<merge-sha>' \
  --command 'dbt deps' \
  --command 'dbt parse --no-partial-parse' \
  --output-dir /path/to/restricted-study-data
```

Build and evaluate the adjudicated dataset:

```bash
governance-change-risk build \
  --registry /path/to/pairs.jsonl \
  --output /path/to/change-risk.csv

governance-change-risk evaluate \
  --dataset /path/to/change-risk.csv \
  --output /path/to/evaluation.json
```

Freeze a consecutive candidate ledger before outcome annotation:

```bash
governance-change-risk freeze-cohort \
  --candidates /path/to/prevalence_candidates.jsonl \
  --protocol-version 0.3 \
  --output /path/to/prevalence_cohort_frozen.json
```

Raw manifests are not tracked here. They can contain compiled SQL, descriptions,
column names, and environment-specific metadata. The registry records hashes so
an authorized researcher can verify the exact artifacts used.
