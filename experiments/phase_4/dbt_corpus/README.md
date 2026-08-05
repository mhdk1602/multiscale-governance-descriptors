# Building the longitudinal dbt lineage corpus

Six stages, run in order. Each writes its output to disk and the next one reads
it, so a stage can be rerun without repeating the ones before it. The extractor
itself is not here, it is `src/governance_descriptors/dbt_lineage.py`, because it
is the tool the corpus is built with and it is unit tested.

Everything below assumes `PYTHONPATH=src` and a scratch directory outside the
repository for the clones. The clones are large. The corpus that ships in
`artifacts/phase_4_corpus/` came from roughly 50 GB of them.

## 1. Harvest the candidate population

    python experiments/phase_4/dbt_corpus/harvest_frame.py --out-dir SCRATCH/frame

Three strata, unioned and deduplicated.

- **S1** the 20 entries in `InfuseAI/awesome-public-dbt-projects`, hardcoded, because
  a curated list is what a reader will reach for first and the paper needs to say
  what it actually yields.
- **S2** GitHub repository search over `topic:dbt`, `dbt-core`, `dbt-project`,
  `analytics-engineering` and `dbt-models`. The search API serves at most 1,000
  results per query and `topic:dbt` alone reports 3,944, so each topic is split
  into ten star bands.
- **S3** GitHub code search for `filename:dbt_project.yml`, which reports 5,340
  hits and is subject to the same cap, so it is split into twelve repository-size
  bands.

Needs an authenticated `gh`. Takes about twenty minutes, most of it waiting out
the search rate limit.

## 2. Screen without cloning

    python experiments/phase_4/dbt_corpus/screen_metadata.py --frame SCRATCH/frame
    python experiments/phase_4/dbt_corpus/screen_trees.py    --frame SCRATCH/frame

The first pass batches 40 repositories per GraphQL request and collects stars,
disk usage, creation and push dates, fork and archive flags, the default branch
and its total commit count. The second pass takes one recursive tree listing per
repository that clears the first, locates every non-vendored `dbt_project.yml`
and counts the model SQL underneath.

The tree pass is deliberately one REST call per repository. An earlier version
fetched and parsed each `dbt_project.yml` and asked for per-path commit counts,
which cost up to thirteen calls per repository and would have taken two hours
against the rate limit. Nothing in the screen needs that precision, because the
screen does not decide membership.

## 3. Record the screening decision

    python experiments/phase_4/dbt_corpus/finalize_frame.py --frame SCRATCH/frame \
        --worklist SCRATCH/worklist.json

Writes `decisions.json`, one entry per candidate with the outcome and the reason,
and `worklist.json`, the repositories stage 4 will clone.
Only four conditions exclude, and each is a condition under which no monthly
series can exist.

| id | condition |
|---|---|
| P3 | at least 40 commits on the default branch |
| P4 | at least 12 months between repository creation and last push |
| P5 | not a fork |
| P6 | metadata resolvable, repository not empty, default branch present |

What HEAD looks like is recorded but does not exclude. An earlier version
required a `dbt_project.yml` and ten model files at HEAD, and that rejected
`davidgasquez/filecoin-data-portal`, which has neither at HEAD and still yields
27 monthly snapshots because it used dbt for two years and then stopped. A
HEAD-only test is blind to exactly the adoption-and-abandonment lifecycle a
longitudinal corpus should contain.

## 4. Clone and extract

    python experiments/phase_4/dbt_corpus/run_corpus.py \
        --worklist SCRATCH/worklist.json --out-dir SCRATCH/results \
        --log SCRATCH/run_log.jsonl --clones SCRATCH/clones --workers 12

One repository failing never stops the run. Every failure lands in the log with
its reason and in the per-project result JSON. Reruns skip anything the log
already records as `success` or `partial`, so an interrupted run resumes.

Cloning is network-bound and extraction is CPU-bound, so on a large worklist it
pays to clone ahead at high concurrency and then extract at roughly one worker
per core.

    python experiments/phase_4/dbt_corpus/prefetch_clones.py \
        --clones SCRATCH/clones --workers 24 SCRATCH/worklist.json

`--graph-only` on `run_corpus.py` records graph size and connectivity and skips
D1 to D4. Useful for sizing a candidate set before paying for the descriptors.

## 5. Assemble the release

    python experiments/phase_4/dbt_corpus/build_release.py \
        --results SCRATCH/results --dest artifacts/phase_4_corpus \
        --decisions SCRATCH/frame/decisions.json

Applies the inclusion criteria to what the extractor produced, writes the
per-project directories, the pooled tables, `schema.json`, `README.md`, and a
`MANIFEST.json` carrying a SHA-256 for every other file.

## 6. Compare against the two-project release

    python experiments/phase_4/dbt_corpus/compare_to_two_project.py \
        --release artifacts/phase_4_corpus

Recomputes every quantitative claim the two-project artifacts make and prints it
beside the corpus value.

There is a seventh script, `measure_d1_order_sensitivity.py`, which is not part
of building the corpus. It rebuilds real corpus graphs, permutes the node
insertion order, and reports how far each descriptor moves. It exists because
the two-project pipeline built its node set from a Python set, so `D1_csi` and
`D1_n_comm` in the committed artifacts depend on the process hash seed, and the
paper needs the size of that effect rather than the fact of it.

    python experiments/phase_4/dbt_corpus/measure_d1_order_sensitivity.py \
        --release artifacts/phase_4_corpus --clones SCRATCH/clones \
        --out artifacts/phase_4_corpus/d1_order_sensitivity.json

## What is deliberately not automated

The corpus is every member of the frame at one point in time, and the frame is
a documented subset of the population rather than an enumeration of it, because
GitHub code search caps pagination at 1,000 results per query and the size-band
partitioning recovers 2,207 of the 5,340 hits it reports. Rerunning it will not
reproduce it exactly, because repositories gain commits, get renamed, go private
and get deleted. Two of the twenty curated entries were already unreachable when
this corpus was built. `MANIFEST.json` pins every sampled commit SHA, so the
measurements are reproducible from a clone of the same repository at the same
SHA even when the repository has moved on.
