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

## Reconstructing any snapshot

`MANIFEST.json` pins `head_sha`, the commit each repository was cloned at, and
`projects/<id>/extraction.json` lists the SHA of every sampled commit. Neither
depends on the repository still looking the way it did, so a row stays
reconstructible after the project moves on.

    git clone <repository>
    git -C <repo> checkout <head_sha>          # the state the corpus saw
    git -C <repo> ls-tree -r <snapshot_sha> -- <model_paths>

Rerunning the pipeline against a live repository will not reproduce the corpus,
because repositories gain commits, get renamed, go private and get deleted.
Cal-ITP had 1,019 model-touching commits when the two-project study ran and
1,049 when this corpus was built. Reproduce from the pinned SHAs, not from HEAD.

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

## How refs are matched, and the two parses

Comments are stripped first, `--`, `/* */` and `{# #}` alike. Without that a
commented-out reference becomes an edge, which is how the two-project release
acquired seven Mattermost edges that exist in no compiled manifest.

Two patterns then run. The **strict** one requires `{{` immediately before
`ref(`, so it only sees a ref that is the entire Jinja expression. The
**permissive** one drops that anchor and also accepts the two-argument
`ref('package', 'model')` form, so it sees a ref handed to a macro. That is not
a corner case. On Cal-ITP the anchor hides 114 of 854 edges, 13 percent,
touching 186 of 620 nodes, and every hidden site is a plain string literal
inside `dbt_utils.union_relations`, `unpivot` or a project-local macro.

The corpus reports the permissive parse, because those edges are real
dependencies that dbt itself resolves. `edges/<id>.csv.gz` labels every edge
`strict` or `permissive_only`, and `M_strict` is on every snapshot row, so
filtering to `strict` reconstructs the older parse exactly.

## Known limitations

- A `ref()` whose argument is genuinely computed, from a loop variable or string
  concatenation, is still not resolved. Both patterns match string literals only.
  On the two projects audited by hand there were no such sites.
- A repository that fans a single dbt project out into several subprojects
  leaves the tracked project empty from that point on. Those snapshots are
  recorded as gaps in `projects/<id>/extraction.json` and the project's status
  becomes `partial`.
- Public mirrors of internal dbt projects sometimes publish `dbt_project.yml`
  without the model SQL. Those repositories extract to zero snapshots and appear
  in `excluded.csv`.
- Layer labels in `n_staging`, `n_intermediate` and `n_mart` come from naming
  conventions, not from dbt metadata. Projects that do not follow a convention
  land in `n_unclassified`. The four columns sum to `N` on every snapshot.
- `median_giant_component_frac` in `corpus_index.csv` is a per-project median.
  Pooling snapshots across a tier gives a different number, 0.794 against 0.765
  for `core` and 0.370 against 0.383 for `extended`. Both are correct and they
  answer different questions, so state which one a figure is showing.
### `D3_fiedler_bim` is undefined on part of this corpus

Not unstable, undefined, and the distinction matters to anyone computing
spectral descriptors on small sparse graphs.

Algebraic connectivity is the second-smallest Laplacian eigenvalue, and an
eigenvalue is unique whatever the solver does, so `D3_alg_conn` reproduces to
the last bit under any node ordering. The Fiedler vector is an eigen*vector* of
that eigenvalue, and it is only unique when the eigenvalue is simple. When it is
not, any vector in the eigenspace qualifies and the bimodality coefficient of
whichever basis the solver happens to return is arbitrary.

The corpus contains such graphs. One snapshot of `DalgoT4D/dbt_shofco` has a
15-node giant component whose Laplacian carries lambda_2 through lambda_6 all
equal to 1.0, a five-fold degeneracy with a separation of 4.4e-16. Under twelve
node-order permutations of that one graph `D3_alg_conn` does not move at all
while `D3_fiedler_bim` moves by 0.174, which is 65 percent of the descriptor's
published standard deviation of 0.268. Across the 40 snapshots measured in
`d1_order_sensitivity.json` the other 39 move by at most 8.9e-06, so this is a
tail that a small sample will miss rather than a pervasive wobble.

Small, sparse and symmetric graphs are where degeneracy arises, and a corpus of
public dbt projects is full of them. Check the eigenvalue separation before
reporting anything that rests on a Fiedler vector.

## Other known limitations

- `D3_fiedler_bim`, as above.
- `tier` is defined partly by median giant component, and D1 and D3 are computed
  on that same component. Testing `tier` against a D3 descriptor is therefore
  partly circular. `composition` carries no such dependence, and D4 is computed
  on the whole graph.
- Documentation and test coverage come from the schema YAML beside the models.
  A project that documents elsewhere, or generates its YAML at build time, will
  read as uncovered when it is not.
