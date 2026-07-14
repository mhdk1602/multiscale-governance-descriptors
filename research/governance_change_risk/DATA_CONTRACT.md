# Manifest-Pair Data Contract

The registry is JSON Lines with one object per merged change. Paths are resolved
relative to the registry unless absolute.

```json
{
  "project": "owner-repository",
  "change_id": "1234",
  "change_url": "https://github.com/owner/repository/pull/1234",
  "merged_at": "2026-01-15T14:30:00Z",
  "before_ref": "immutable-sha",
  "after_ref": "immutable-sha",
  "before_manifest": "restricted/project/1234/before_manifest.json",
  "after_manifest": "restricted/project/1234/after_manifest.json",
  "baseline_covariates": {
    "lines_added": 42,
    "lines_deleted": 7,
    "files_changed": 5,
    "author_prior_merged_changes": 18,
    "prior_30d_failed_workflows": 2
  },
  "label_status": "adjudicated",
  "outcome_primary": 0,
  "outcome_window_days": 30,
  "adverse_event_type": null
}
```

Required fields are `project`, `change_id`, `merged_at`, `before_manifest`, and
`after_manifest`. Evaluation additionally requires `label_status=adjudicated`
and `outcome_primary` equal to `0` or `1`. If either expected manifest SHA-256
is present, the builder verifies it and stops on a mismatch.

All five `baseline_covariates` are required before a record can be marked
`adjudicated`. The names are fixed in code; unknown keys and negative values are
rejected. Feasibility records may omit them because they cannot enter evaluation.

The collector stores resolved refs, commands, manifest hashes, dbt versions, and
collection time. It also records whether node fingerprints or the lineage edge
set changed. Rebuilding the dataset stores another hash over the derived CSV. A
changed manifest therefore cannot pass unnoticed.

Derived tables built under protocol 0.3 must record
`feature_spec_version=governance-change-risk-v2`. Version 2 adds the
`change_geometry__` columns while preserving the baseline, governance, and
global multiscale definitions from version 1. Feature tables from the two
versions must not be concatenated.

Pairs with no changed node fingerprint and no changed edge remain in the
extraction audit as `manifest_visible_change=false`. They are not eligible for
confirmatory evaluation. A changed fingerprint with stable topology is eligible:
dbt code or governance metadata can change while canonical IDs and dependencies
stay fixed.

## Security boundary

dbt manifests may contain raw or compiled SQL, descriptions, database names,
column metadata, tags, and environment-specific identifiers. Do not commit raw
manifests from a private organization. Keep them in an access-controlled study
directory and publish only permitted graph projections, aggregate features, and
cryptographic hashes.

Public-project manifests still remain outside Git because they are generated
research inputs. The repository tracks their immutable refs and collection
procedure instead.
