# Execution Plan: PLOS ONE Submission + Data Search + Pivot C

## Calibration

The reviewer's corrections to the prior recommendation are accepted:
- Do **not** split into a second methods paper. The current manuscript already is the methods/structural paper (Pivot A). Splitting would be salami slicing per COPE.
- PLOS ONE is plausible but not unambiguously best. PeerJ Computer Science and Applied Network Science are equally reasonable.
- IEEE Access acceptance is 27%, not 55–70%. Earlier estimate was optimistic.
- Pivot C (longitudinal git-history monitoring) is the next paper, not an extension of this one.
- Pivot E (combine with fractal work) is rejected — too broad, looks like portfolio stitching.

## Final strategy

- **One paper, one journal first.** Submit the current paper as the structural lineage-analysis + methodological-scaffolding feasibility study.
- **Primary target: PLOS ONE** (publishes negative results, evaluates on methodological rigor not perceived impact).
- **Backup targets**: PeerJ Computer Science (cleaner CS audience), Applied Network Science (graph-theoretic framing).
- **After submission**, build Pivot C as the next distinct paper.
- **Don't keep iterating** on governance prediction without partnership data.

---

## Phase 1: Pre-Submission Cleanup (PLOS ONE readiness)

Mandatory fixes before submission:

1. Replace remaining "confirming" / "confirms" with "consistent with" / "supports" around cross-org validation (reviewer correction #3).
2. Remove "two independent organizations" / "from two organizations" if independence cannot be defended; replace with "two source ecosystems" (reviewer correction).
3. Search for and fix any encoding artifacts (`2.8Œ`, mojibake, smart-quote corruption).
4. Verify GitHub repo accessibility — the paper says "on GitHub". The repo is currently private. Either: (a) make it public; or (b) rephrase to "development repository available on request" with the Zenodo archive as primary.
5. Verify Zenodo v2.0.0 archive contains everything needed to reproduce all tables.
6. Run a final overfull-hbox scan and fix anything substantive (>5pt).
7. Verify the abstract is within PLOS ONE's word limit (300 words is safe; the journal allows up to 300 in their template).
8. Add a cover letter draft for PLOS ONE editors.

Deliverables:
- `paper/preprint.pdf` final version
- `paper/cover_letter_plos_one.md`
- Commit, push, optionally update Zenodo to v2.1.0

---

## Phase 2: Expanded Data Search (the user's question)

The user asked: how do we find data that other researchers have used for governance/lineage research without being gated?

Approach:
1. **Citation chain analysis**: starting from DLG-DG-23 (Chen et al. 2024), trace forward citations to find related datasets. Also trace from OpenLineage, DataHub research papers, and any data quality / governance empirical study.
2. **Industry open-source data stacks**: Airbnb (Knowledge Repo), Spotify (Klio, Luigi), Netflix (Metaflow), Uber (Piper). Check if any have published lineage + governance metadata.
3. **DataHub / OpenMetadata sample data**: beyond the synthetic `bootstrap_mce.json` we already inspected, look for richer demo datasets.
4. **Apache Atlas demos**: governance-labeled metadata in a different ecosystem.
5. **MLOps / ML pipeline lineage**: tools like MLflow, Kubeflow, Metaflow track lineage; check for shared example data.
6. **Government data catalogs**: data.gov, ANDS, european open data portals.
7. **Academic empirical papers**: search for papers that did similar correlation analysis — what data did they use?

Output: `artifacts/data_sources_catalog.md` — a comprehensive list of every public lineage / governance dataset found, with assessment of usability for governance-correlation studies. Even if none are usable now, this is a reference for future work.

---

## Phase 3: Pivot C — Longitudinal Topological Drift in dbt Git Histories

Concept: extract dbt manifests at multiple commits over time from Cal-ITP and Mattermost (already cloned). Compute D1–D4 descriptors per commit. Identify "drift" events (large descriptor changes). Cross-reference with commit messages / PR descriptions to see what kinds of changes produce structural drift.

This is a separate paper, not an extension of the current one. Steps:

1. Validate data viability: do Cal-ITP and Mattermost have enough commits over a long enough period to make this analysis meaningful (target: 50+ commits over 12+ months affecting the dbt project)?
2. Build extraction pipeline: per-commit checkout → parse SQL files → extract lineage → compute descriptors. Handle dbt-version changes if any.
3. Compute descriptor time series.
4. Identify drift events using control-chart methods on the descriptor time series.
5. Annotate drift events with commit messages / PRs.
6. Write paper: "Detecting Topological Drift in dbt Lineage Graphs from Version-Control History."
7. Target: workshop (DBML, DEEM) or short-paper track. Could also target VLDB Industrial Track if it has compelling structural drift detection.

Deliverables:
- `experiments/phase_4/exp_longitudinal_dbt.py`
- `artifacts/phase_4/` results
- Draft paper for Pivot C
- Submit to selected venue

---

## Execution order

Phase 1 (immediate, this session).
Phase 2 (parallel with Phase 1 — research agent can search while we clean).
Phase 3 (after Phase 1 commit + Phase 2 catalog is built).

Status tracking inline below as each phase completes.

---

## Phase 1 status
- [x] Replace abstract "confirming" with "indicating" for layer-stratified result
- [x] Softened Experiment 5 "confirm" → "show"
- [x] Encoding artifact scan (no problems found beyond the 2.8× already fixed)
- [x] Verified no "two independent organizations" overclaims remain
- [x] GitHub visibility — made public for submission
- [x] Zenodo completeness — v2.0.0 archive intact; v2.1.0 update after Phase 1
- [x] Overfull hbox scan — all remaining ≤2pt typesetting noise
- [x] Cover letter for PLOS ONE drafted
- [ ] Final commit + push (next)

## Phase 2 status
- [x] Citation chain from DLG-DG-23 — yielded RAIRAB, Schema Lineage Extraction, LineageX (all 2025)
- [x] Industry stacks — DataHub, OpenMetadata, dbt Jaffle Shop with metadata
- [x] DataHub/OpenMetadata samples — sandbox URL identified
- [x] Apache Atlas / Egeria — no usable demo data with governance
- [x] MLOps lineage tools — MLflow/Kubeflow tracked, no extractable demo data
- [x] Government data catalogs — DCAT-AP / DCAT-US identified but no lineage graphs
- [x] Academic empirical papers — RO-Crate provenance examples on Zenodo
- [x] Compiled `artifacts/data_sources_catalog.md` with 16 entries

## Phase 3 status (Pivot C — separate paper)
- [x] Data viability check (Cal-ITP 1019 commits, Mattermost 1335 commits affecting models)
- [x] Extraction pipeline (`experiments/phase_4/exp_longitudinal_dbt.py`)
- [x] Per-commit descriptor computation (106 snapshots, 9 cumulative years)
- [x] Univariate drift detection (step-change >20%, 44 events)
- [x] Multivariate change-point detection (CUSUM, 16 events total)
- [x] Commit message annotation
- [x] Time-series figure (`paper/figures/longitudinal_dbt.pdf`)
- [x] Drift distribution figure (`paper/figures/drift_distribution.pdf`)
- [x] Paper outline (`artifacts/pivot_c_paper_outline.md`)
- [x] **Full paper draft (8 pages, `paper/pivot_c/preprint.pdf`)** — Week 1 complete
- [ ] Internal review pass (Week 2)
- [ ] Add GitLab Analytics as 3rd project (Week 2)
- [ ] Bayesian online change-point comparison (Week 2)
- [ ] Final commit-level annotation pass (Week 2)
- [ ] Venue selection (DEEM 2027 / DBML / VLDB Industrial Track 2027 / Empirical SE)
- [ ] Submission (deadlines early 2027)

## Phase 4: APC pivot (after PLOS ONE rejection)
- [x] Verified no-APC subscription-based venues
- [x] Cover letter for Data & Knowledge Engineering (primary target)
- [x] Cover letter for KAIS (Springer, backup)
- [x] Suggested reviewer list
- [x] Submission strategy document
- [ ] Submit to D&KE via Elsevier editorial system (user action required)
- [ ] If rejected, submit to KAIS
- [ ] Track decision timelines
