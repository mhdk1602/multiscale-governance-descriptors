# Data files

All dbt files here are anonymized with HMAC-SHA256. No SQL, column names,
business identifiers, or private lineage semantics are exposed.

## Which domain-level file is authoritative

`data/dbt_nodes.csv` is the ground truth. Every domain-level number used in the
paper is a rollup of it, and `artifacts/phase_3/exp_2b_dbt_domain_descriptors.csv`
is the authoritative rollup. Its `N`, `doc_rate`, and `test_rate` reproduce the
node-level aggregates exactly, and it uses the same zero-padded domain labels as
the node file.

**Do not join `data/dbt_domain_summary.csv` against anything.** It describes the
same 26 domains and the same 223 nodes, but under a second, unrelated
anonymization pass. Three things differ.

| | `dbt_domain_summary.csv` | `exp_2b_dbt_domain_descriptors.csv` |
|---|---|---|
| Domain label | `domain_1`, `domain_10` | `domain_001`, `domain_010` |
| Documentation column | `documentation_coverage` | `doc_rate` |
| Precision | rounded to 4 dp | full float |

The labels are not the same domains renumbered with padding. Of the six domains
whose `(node_count, doc, test)` triple is unique enough to match unambiguously,
not one maps to its own number. `domain_10` in the summary is `domain_020` in the
descriptors, `domain_16` is `domain_007`, and so on. Sorted against each other
the two files agree to 4.3e-05, which is rounding alone, so the underlying values
are the same. Only the row-to-label assignment differs.

This is a live trap and it has already cost one silent failure. An earlier
version of `experiments/phase_3/exp_null_models_extended.py` inner-joined the two
files on the domain label. Zero keys matched, the join returned an empty frame,
and null model B skipped without raising for as long as that code stood. Padding
the keys would not have saved it either, since padding aligns the wrong rows and
yields documentation values that disagree by up to 1.0.

No code reads `dbt_domain_summary.csv` today. It is kept because it is part of
the archived record, not because anything depends on it.

## Files

| Path | Contents |
|---|---|
| `dbt_nodes.csv` | 223 nodes, layer, domain, stewardship, tests, documentation. Ground truth |
| `dbt_nodes_extended.csv` | The same 223 nodes with additional attributes |
| `dbt_edges.csv` | Directed lineage edges over `dbt_nodes.csv` |
| `dbt_domain_summary.csv` | Legacy 26-domain rollup under a second labeling. Unused, see above |
| `dbt_component_summary.csv` | Per-component summary, 38 rows |
| `external/` | Public comparison corpora, `wfcommons`, `dlg-dg-23`, `dw-bench`, `isomera` |
| `change_risk/` | Manifest pairs for the PR-level successor study, see its own README |
