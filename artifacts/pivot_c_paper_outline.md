# Pivot C Paper Outline

**Working title:** Detecting Topological Drift in Data Lineage Graphs from Version-Control History: A Longitudinal Study of Two Production dbt Projects

**Target venue:** DBML (Database Engineering Meets ML), DEEM (Data management for ML), or VLDB Industrial Track

---

## 1. Motivation

Data lineage graphs evolve continuously as data engineering teams add models, refactor pipelines, and deprecate assets. Traditional governance assessment is periodic (annual reviews) and metadata-based (was a dataset documented at a point in time). This paper asks: can structural drift in the lineage topology itself be detected from version-control history alone, without any metadata?

If yes, the same descriptors that are difficult to use for governance prediction (because layer composition confounds them) become useful as change-detection signals.

## 2. Method

**Data extraction.** For each public dbt project, walk the git history, sample one commit per 30-day window, checkout each sample commit, parse SQL files for `{{ ref('...') }}` dependencies, build the lineage DAG, and compute D1–D4 + cycle rank.

**Drift detection.** A step change in descriptor value $> 20\%$ between consecutive snapshots is flagged as a drift event. Each event is annotated with the corresponding window's commit messages.

**Calibration.** This is intentionally simple. Compare against rolling-window control charts (X-bar at 2.5σ) and against absolute N-change (>10% node count change).

## 3. Data

| Project | Span | Commits affecting models | Snapshots (30-day window) | N range | M range |
|---|---|---|---|---|---|
| Cal-ITP | 2022-03 → 2026-05 | 1,019 | 51 | 74 → 631 (8.5×) | 69 → 756 (11×) |
| Mattermost | 2019-12 → 2025-01 | 1,335 | 55 | 16 → 301 (19×) | 14 → 517 (37×) |

Total: 106 snapshots over 9 cumulative years of production lineage history.

## 4. Findings

### 4.1 Major drift events

44 events detected at >20% step change. Selected with mechanistic interpretations:

**Cal-ITP:**
- **2022-07-26: D3 dropped 76%** during commit "payments-dbt-migration" — large-scale architectural migration adding 50+ payment models. D3 dropped because the LWCC integrated previously isolated subgraphs, reducing per-node algebraic connectivity.
- **2023-01-20: D3 dropped 58%** during "switch rt feed presence check to new daily rt url index" — refactor of RT feed monitoring infrastructure.
- **2025-06-02: D3 dropped 50%** during "NTD: mart table usability and testing" — mart-layer reorganization.

**Mattermost:**
- **2020-03-16: D3 dropped 95%** during "Fixed server_licensee_details date range" — early-stage major refactor; this is the period when N grew from 38 to 75.
- **2021-03-11: D3 jumped 232%** during "Adding daily_server_user_agent_events" — addition of high-fanout server events tables, creating new shortest-path bottlenecks.
- **2024-12-18: D1 CSI jumped 100%** during "remove deprecated models" — cleanup event consolidating community structure.

### 4.2 Stable evolutionary regimes

Between drift events, descriptors evolve smoothly. Cal-ITP's D3 stayed near 0.029 for ~18 months (2024-02 to 2025-05), corresponding to an incremental-improvement period without major architectural changes.

### 4.3 Cross-project regularity

The largest drift events in both projects correspond to dbt-labelled commits referencing "migration," "deprecation," or "refactor." Small commits (typo fixes, single-model additions) rarely produce >20% step changes. Drift detection therefore filters incremental edits and surfaces architectural events.

## 5. Implications

This is a positive use case for the descriptors that does NOT require governance metadata. The descriptors function as topology-change detectors. A practical deployment:
- Continuous CI/CD descriptor computation on dbt manifest changes
- Threshold-based alerting on drift events
- Cross-reference with PR descriptions to label drift events as "intended refactor" vs "unintended structural change"

## 6. Limitations

- Two projects only — generalization across more dbt projects (GitLab, Lyft, etc.) is required
- 30-day window is arbitrary; daily snapshots would be more precise but expensive
- Drift detection is univariate per descriptor; multivariate change-point detection (CUSUM, Bayesian online change-point) may outperform
- Causal interpretation requires correlating drift events with downstream governance incidents (data outages, schema break events) — partnership data needed

## 7. Future work

- Apply to MLOps pipeline lineage (MLflow, Kubeflow)
- Bayesian online change-point detection
- Cross-organisation drift signature benchmarking
- Connection to existing data observability tools (Monte Carlo, Acceldata)

---

## Status

- [x] Data extraction (106 snapshots, 9 years)
- [x] Time-series figure (paper/figures/longitudinal_dbt.pdf)
- [x] Drift detection (step-change, 44 events)
- [x] Commit-message annotation
- [ ] Multivariate change-point comparison
- [ ] Write full draft
- [ ] Internal review
- [ ] Submit to DEEM (June 2026 deadline) or VLDB Industrial Track
