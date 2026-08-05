# Longitudinal dbt lineage corpus

Monthly reconstructions of the model dependency graph of 154 public dbt
projects, 3586 snapshots in all, spanning 2016-07-27 to 2026-08-04.
Each snapshot is a lineage DAG recovered from a single git commit together with
the D1-D4 governance descriptors computed on it.

Nothing here requires dbt to be installed or run. The graph at a commit is
recovered by reading the model SQL out of the git object database and parsing
`{{ ref('...') }}` declarations, so a project's history can be reconstructed
without credentials, a warehouse, or a working build.

## Files

| file | what it holds |
|---|---|
| `snapshots.csv` | every snapshot of every project, one row per project per commit |
| `corpus_index.csv` | one row per project, the yield table |
| `drift_events.csv` | consecutive-snapshot changes above 20 percent in D1_csi, D3_alg_conn or D4_cycle_rank_norm |
| `excluded.csv` | repositories that were cloned and extracted but did not meet the inclusion criteria, with the reason |
| `sampling_frame.csv` | the full candidate population of 3718 repositories and what happened to each |
| `schema.json` | column dictionary, types and primary keys for every table |
| `MANIFEST.json` | provenance, commit SHAs, and a SHA-256 for every other file |
| `projects/<id>/snapshots.csv` | the same rows as `snapshots.csv`, split per project |
| `longitudinal/longitudinal_<id>.csv` | the per-project rows again under the flat name the phase_4 scripts glob for |
| `projects/<id>/extraction.json` | per-project provenance including every snapshot SHA and every snapshot that failed |

Start with `corpus_index.csv` for the shape of the corpus and `snapshots.csv`
for the measurements. `schema.json` documents every column.

## How a snapshot is chosen

Commits touching a declared model path are listed oldest first. The history is
cut into rolling 30-day windows anchored on the first such commit, and the last
commit in each window is sampled. One snapshot per project per month of activity,
so a quiet month yields nothing and a busy month yields one.

## How the lineage graph is built

At the sampled commit, every `.sql` file under the tracked dbt project's
`model-paths` is read. Files under `macros`, `tests`, `snapshots`, and vendored
package directories are skipped. A node is the filename stem. An edge runs from
`ref('a')` to the model whose file contains it, and only when `a` resolves to
another model in the same snapshot, so references to sources, seeds, and models
from other packages do not appear.

Two consequences worth knowing before you use the data. Models in different dbt
projects inside one repository cannot reference each other, so only one dbt
project per repository is tracked, named in `MANIFEST.json` under
`model_paths`. And two model files in different directories that share a
filename collapse to one node, which is what dbt itself does, since dbt model
names are globally unique within a project.

## Inclusion criteria

A repository is in the corpus when all of the following hold.

- At least 12 monthly snapshots were extracted.
- Peak lineage size of at least 10 nodes.
- At least one `dbt_project.yml` with resolvable `model-paths` somewhere in its
  history.

### Tiers

`corpus_index.csv` carries a `tier` column. A dbt *package* repository can clear
the criteria above with fifty model files and three edges between them, and on a
graph that sparse the D1 and D3 routines describe the giant component, which may
be a handful of nodes while `N` says fifty. `core` marks the 33 projects
where the descriptors describe most of the reported N and the series is long
enough to carry a trend, meaning at least 24 snapshots, peak
size at least 25 nodes, and a median giant component of at least
0.5 of N. Everything else is `extended`.

Both tiers are real measurements and neither is filtered out. Which one an
analysis should use depends on whether it reasons about dependency structure,
where `core` is the safer population, or about lifecycle and size, where the
full corpus is.

The candidate population and the screen that preceded these criteria are in
`sampling_frame.csv`. The screen only removed repositories that could not
produce a monthly series in principle: fewer than 40 commits on the default
branch, under 12 months between creation and last push, forks, and empty
repositories. Everything else was cloned and extracted, and membership was
decided from the extraction rather than from the screen.

## Reproducibility

`D1_csi` and `D1_n_comm` come from a Louvain resolution sweep. Louvain is
sensitive to the order in which nodes enter the graph, so nodes are inserted in
sorted order and the runs are made with `PYTHONHASHSEED=0` and Louvain
`seed=42`. Earlier work on this pipeline inserted nodes from a Python set, whose
string iteration order varies with the process hash seed, and D1 values from
that code are not reproducible between runs. N, M, D2 and D4 are unaffected by
node ordering and reproduce exactly.

`MANIFEST.json` records the tool version, the extraction timestamps, the
repository URL, the default branch, the HEAD SHA at extraction time, and the SHA
of every sampled commit, so any row can be traced back to the exact tree it was
computed from.

## Known limitations

- `ref()` calls constructed dynamically, for example inside a macro or from a
  loop variable, are not resolved. The regex matches literal string arguments
  only.
- A repository that fans a single dbt project out into several subprojects
  leaves the tracked project empty from that point on. Those snapshots are
  recorded as gaps in `projects/<id>/extraction.json` and the project's status
  becomes `partial`.
- Public mirrors of internal dbt projects sometimes publish `dbt_project.yml`
  without the model SQL. Those repositories extract to zero snapshots and appear
  in `excluded.csv`.
- Layer labels in `n_staging`, `n_intermediate` and `n_mart` come from naming
  conventions, not from dbt metadata. Projects that do not follow a convention
  land in `n_unclassified`.
