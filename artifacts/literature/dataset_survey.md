# Open-Source Data Lineage Graph Datasets for Governance Descriptor Validation

Survey date: 2026-05-06

Descriptor targets:
- D1: Community detection (modularity, Louvain/Leiden)
- D2: Blast radius (failure propagation, reachability)
- D3: Spectral descriptors (Laplacian eigenvalues, Fiedler value)
- D4: Persistent homology (Betti numbers, persistence diagrams)

---

## Tier 1: Directly Usable (Data Lineage Graphs with Metadata)

### 1. DLG-DG-23 (Huawei Cloud Data Lineage Graphs)

**What it is:** The first open dataset of real-world data lineage graphs for data governance research. Sourced from Huawei Cloud production environments.

- **URL (paper):** https://www.sciencedirect.com/science/article/pii/S2468502X24000020
- **Download:** The paper (open access, CC license) contains the repository link. Check the Data Availability section. Related Huawei datasets at https://github.com/sir-lab/data-release (though DLG-DG-23 may be hosted separately, possibly on Figshare).
- **Format:** JSON (Node.json + Edge.json per graph)
- **Size:** 18 DLGs, 24 MB uncompressed
  - 10 small-scale: ~hundreds of nodes (smallest: 278 nodes)
  - 6 medium-scale: ~thousands of nodes
  - 2 large-scale: >10,000 nodes (largest: 17,085 nodes)
- **Node types:** data table, data job, data field (heterogeneous)
- **Edge types:** DATA_FLOW, PARENT_CHILD (directed)
- **Governance metadata:** One label type (core data asset). Three application scenarios: cloud infrastructure, customer service, operation analysis.
- **License:** Creative Commons (CC BY-NC-ND per ScienceDirect)

**Descriptor suitability:**
- D1 (community detection): Excellent. Heterogeneous node types across 3 business domains. Scale-free structure should yield meaningful community partitions.
- D2 (blast radius): Excellent. DATA_FLOW edges directly model ETL propagation paths. Directed graph structure is exactly what blast radius needs.
- D3 (spectral): Good. Graphs range from 278 to 17,085 nodes, giving a decent spread for spectral analysis. Sparse and directed, so the Laplacian construction needs care (use directed Laplacian or symmetrize).
- D4 (persistent homology): Good. The heterogeneous, scale-free structure should produce interesting filtrations, though the sparsity of DAGs may yield thin persistence diagrams.

**Verdict: PRIMARY DATASET. The closest thing to ground-truth data lineage with governance labels.**

---

### 2. DW-Bench (Data Warehouse Graph Topology Benchmark)

**What it is:** A benchmark of 5 data warehouse schemas with both foreign-key and lineage edges, stored as PyTorch Geometric HeteroData.

- **Paper:** https://arxiv.org/abs/2604.18964
- **GitHub:** https://github.com/AJamal27891/dw-bench
- **License:** MIT (Syn-Logistics), mixed for source schemas (TPC EULA, Apache 2.0, Microsoft Public License)

**Schema statistics:**

| Dataset | Tables | FK Edges | Lineage Edges | Total Edges |
|---|---|---|---|---|
| AdventureWorks | 102 | 136 | 39 | 175 |
| TPC-DS | 24 | 70 | 0 | 70 |
| TPC-DI | 35 | 29 | 21 | 50 |
| OMOP CDM | 37 | 74 | 21 | 95 |
| Syn-Logistics | 64 | 96 | 35 | 131 |

- **Node features:** in-degree, out-degree, normalized degree, lineage degree, betweenness centrality, PageRank
- **Edge types:** fk_to (structural, undirected for connectivity), derived_from (lineage, directed DAG)
- **Format:** PyG HeteroData (.pt files), convertible to NetworkX

**Descriptor suitability:**
- D1: Moderate. Graphs are small (24-102 nodes). Community structure may be trivial at this scale, but the dual-edge-type heterogeneity is interesting for testing whether FK vs lineage edges yield different partitions.
- D2: Good. Lineage edges form DAGs ideal for blast radius computation. The AdventureWorks schema (102 tables, 39 lineage edges) is the most realistic.
- D3: Moderate. Small graphs mean few interesting eigenvalues, but useful for validating spectral methods on known structures (star schema vs normalized schema).
- D4: Limited. Very small graphs will produce sparse persistence diagrams.

**Verdict: USEFUL FOR VALIDATION. Small but well-structured schemas with ground-truth edge types. Good for unit-testing descriptor implementations.**

---

### 3. Isomera (Synthetic Data Mesh Lineage Graphs)

**What it is:** Synthetic data mesh lineage graphs in GML format, designed for data lineage research, redundancy detection, and graph benchmarking in Data Mesh architectures.

- **URL:** https://ieee-dataport.org/documents/isomera-synthetic-data-mesh-lineage-graphs-tpc-ds-benchmarks-synthetic-scenarios-gml
- **DOI:** 10.21227/dmcm-zr93
- **Format:** GML (34 graph files in a ZIP)
- **Size:** 23.08 KB (34 GML graphs)
- **Content:** Two groups: (a) TPC-DS derived benchmark graphs modeling realistic data-warehouse architectures, (b) synthetic random-lineage graphs for robustness testing. Nodes encode data artifacts/tables/services; edges encode lineage/dependency relations.
- **Metadata:** Attribute metadata on nodes useful for node-matching and GNN experiments
- **License:** IEEE DataPort subscription required
- **Published:** March 2026

**Descriptor suitability:**
- D1: Moderate. Synthetic graphs, but the TPC-DS derived ones have realistic warehouse structure.
- D2: Good. Dependency/lineage edges directly model what blast radius measures.
- D3: Good. 34 graphs provide a reasonable corpus for spectral analysis comparison.
- D4: Moderate. Synthetic graphs may lack the topological complexity that produces interesting persistence.

**Verdict: SUPPLEMENTARY. The GML format is convenient, but small files (23 KB total) suggest very small graphs. The IEEE DataPort subscription is a barrier. Worth trying if accessible.**

---

## Tier 2: Convertible with Moderate Effort (Workflow/Pipeline DAGs)

### 4. WfCommons / WfInstances (Scientific Workflow Traces)

**What it is:** A curated collection of 180 real-world scientific workflow execution instances from production HPC systems, in a standardized JSON format.

- **Website:** https://wfcommons.org/
- **GitHub (instances):** https://github.com/wfcommons/WfInstances
- **GitHub (format spec):** https://github.com/wfcommons/WfFormat
- **Browser:** https://wfinstances.ics.hawaii.edu
- **Python package:** `pip install wfcommons`
- **License:** LGPL-3.0

**Instance breakdown:**
- Pegasus: 135 instances across 7 applications
- Makeflow: 30 instances across 2 applications
- Nextflow: 15 instances across 15 applications
- Applications include: Montage, Epigenomics, Seismology, BWA, others
- Task counts range from ~180 to ~9,807 per workflow

**Format (WfFormat JSON):**
- Tasks (nodes) with runtime, memory, I/O attributes
- Dependencies (edges) between tasks
- File transfer information
- Machine/platform metadata

**Conversion required:** Parse WfFormat JSON to extract task dependency DAG. Straightforward: tasks are nodes, dependencies are directed edges.

**Descriptor suitability:**
- D1: Good. Different scientific applications should have distinct community structures (e.g., Montage has a wide fan-out pattern, Epigenomics has deep chains). 180 instances give statistical power for comparing descriptor distributions.
- D2: Excellent. Workflow DAGs are the canonical use case for blast radius (what tasks fail if an upstream task fails?). Task runtime data enables weighted blast radius.
- D3: Excellent. Wide range of graph sizes (180 to 9,807 tasks) provides a good spectrum for spectral analysis. The different application types should have distinguishable spectral signatures.
- D4: Good. The variety of workflow topologies (fan-out, chains, diamonds) should produce interpretable persistence diagrams.

Additionally, WfCommons includes WfChef, a synthetic workflow generator that can produce arbitrarily large workflows matching real statistical profiles. This is valuable for scaling experiments.

**Verdict: STRONG CANDIDATE. Not data lineage per se, but workflow DAGs are structurally identical. Large corpus, varied topologies, good size range. The synthetic generator is a bonus.**

---

### 5. Alibaba Cluster Trace v2018 (Production DAG Workloads)

**What it is:** Production cluster traces from Alibaba Cloud containing ~4.2 million batch jobs with DAG task dependency information.

- **GitHub:** https://github.com/alibaba/clusterdata
- **Documentation:** https://github.com/alibaba/clusterdata/blob/master/cluster-trace-v2018/trace_2018.md
- **Also on IEEE DataPort:** https://ieee-dataport.org/documents/alibaba-production-cluster-data-v2018
- **Processed subset on Zenodo:** https://zenodo.org/records/14564935
- **Size:** ~48 GB compressed, ~280 GB extracted
- **License:** Free after survey completion

**Contents:**
- 4,201,013 batch workflows
- Task counts: 1 to 1,002 tasks per workflow (94.75% have <10 tasks)
- DAG structure encoded in `task_name` field of `batch_task.csv` (e.g., `M5_3_4` means task 5 depends on tasks 3 and 4)
- Machine info: 4,023 servers, 8 days of traces

**Conversion required:** Parse `task_name` convention to reconstruct DAG adjacency. Non-trivial but documented. The DAG-Transformer paper (below) provides a processed version.

**Descriptor suitability:**
- D1: Moderate. Most workflows are very small (<10 tasks), limiting community detection. The few large workflows (up to 1,002 tasks) are more interesting but sparse.
- D2: Good. Real production failure propagation paths. The sheer volume enables statistical analysis of blast radius distributions.
- D3: Moderate. The DAGs are typically sparse trees with bounded depth per the literature. Spectral signatures may not be very diverse.
- D4: Limited. Tree-decomposable DAGs have trivial homology (no cycles).

**Verdict: USEFUL FOR SCALE TESTING. Millions of DAGs, but most are tiny. The processed DAG-Transformer subset is more practical.**

---

### 5a. DAG-Transformer Processed Dataset (Alibaba subset)

**What it is:** A processed subset of Alibaba cluster-trace-v2018, extracted for workflow performance prediction.

- **GitHub:** https://github.com/cloudworkflow/workflow-performance-prediction-jii
- **Paper:** https://www.sciencedirect.com/science/article/pii/S2452414X22000097
- **Size:** ~1 million workflows with DAG adjacency matrices
- **Format:** Sub-datasets with DAG information files (train/val/test splits) and performance data

**Verdict: MORE PRACTICAL than raw Alibaba traces. DAG matrices are pre-extracted.**

---

### 6. dbt Project Manifests (Public Open-Source Projects)

**What it is:** dbt projects generate `manifest.json` files containing the full DAG of models, sources, tests, and their dependencies. Several large open-source dbt projects exist.

**Key public dbt projects:**

| Project | URL | Approx Size |
|---|---|---|
| GitLab Data Team | https://gitlab.com/gitlab-data/analytics | ~50 MB manifest, thousands of models |
| Spellbook (Dune) | https://github.com/duneanalytics/spellbook | Large (crypto analytics) |
| Cal-ITP | https://github.com/cal-itp/data-infra | Medium |
| CalData | https://github.com/cagov/data-infrastructure | Medium |
| Dagster Open Platform | https://github.com/dagster-io/dagster-open-platform | Medium |
| Mattermost | https://github.com/mattermost/mattermost-data-warehouse | Medium |
| Jaffle Shop | https://github.com/dbt-labs/jaffle-shop | Small (demo) |

- **Curated list:** https://github.com/InfuseAI/awesome-public-dbt-projects
- **dbt Docs for GitLab:** https://dbt.gitlabdata.com/

**Format:** `manifest.json` with `.nodes` (models/tests/sources) and `.depends_on.nodes` (edges). Rich metadata: descriptions, test coverage, materialization type, schema, tags.

**Conversion required:** Parse manifest.json, extract node/edge graph. Tools exist: `dbt-artifacts-parser`, `canva-public/dbt-column-lineage-extractor`, custom `jq` or Python scripts.

**Governance metadata available:**
- Test counts per model (from `manifest.json`)
- Documentation presence/absence
- Materialization strategy (table/view/incremental)
- Schema assignments (approximate domain grouping)
- Model access level (public/protected/private in dbt Mesh)

**Descriptor suitability:**
- D1: Excellent. GitLab's project has thousands of models across multiple business domains. Schema/tag structure provides ground truth for community validation.
- D2: Excellent. The DAG structure directly represents data dependency chains. Test metadata enables governance-weighted blast radius.
- D3: Good. Large projects (GitLab) provide enough nodes for meaningful spectral analysis.
- D4: Moderate. Linear staging->intermediate->mart patterns may produce thin persistence. Cross-domain dependencies could create interesting cycles (though dbt DAGs are acyclic by construction).

**Verdict: HIGH VALUE. Real governance metadata (tests, docs, ownership). Requires building the project to generate manifest.json (needs a warehouse connection for some, but GitLab publishes docs). The GitLab project is the crown jewel.**

---

## Tier 3: General Graph Datasets (Structural Only, No Governance Metadata)

### 7. TPC-DI (Data Integration Benchmark)

**What it is:** The TPC benchmark for data integration/ETL pipelines.

- **URL:** https://www.tpc.org/tpcdi/default5.asp
- **Implementation:** https://github.com/shannon-barrow/databricks-tpc-di
- **Size:** 35 tables, 29 FK edges, 21 lineage edges (per DW-Bench encoding)
- **License:** TPC EULA (free for research)

**Verdict: ALREADY CAPTURED in DW-Bench. Use the DW-Bench encoding directly.**

---

### 8. Marquez / OpenLineage Sample Data

**What it is:** The Marquez metadata store ships with sample lineage data for a fictional "Food Delivery" application.

- **GitHub:** https://github.com/MarquezProject/marquez
- **Seed file:** `docker/metadata.template.json` in the repo
- **API spec:** https://marquezproject.ai/docs/api/get-lineage/
- **License:** Apache 2.0

**Contents:** OpenLineage events (datasets, jobs, runs) for a small food delivery ETL pipeline. Nodes include datasets like `public.customers`, `public.top_delivery_times`; jobs like `etl_delivery_7_days`.

**Descriptor suitability:** Very small graph. Useful only as a toy example for testing OpenLineage parsing, not for real descriptor validation.

**Verdict: TOY EXAMPLE. Good for testing OpenLineage ingestion code but too small for descriptor analysis.**

---

### 9. SNAP (Stanford Large Network Dataset Collection)

**What it is:** 50+ large network datasets covering social, web, citation, collaboration, and infrastructure graphs.

- **URL:** https://snap.stanford.edu/data/
- **License:** Various (mostly research-friendly)

**Relevant subset:** Citation networks are natural DAGs (papers cite only earlier papers). SNAP provides several:
- `cit-HepPh`: 34,546 nodes, 421,578 edges (high-energy physics citations)
- `cit-HepTh`: 27,770 nodes, 352,807 edges
- `cit-Patents`: 3,774,768 nodes, 16,518,948 edges

**Descriptor suitability:**
- D1-D4: These are large DAGs with rich structure. Good for stress-testing descriptor implementations at scale. But no governance metadata, and citation networks have different topology from data pipelines (very high in-degree for popular papers, vs. more balanced fan-out in ETL).

**Verdict: SUPPLEMENTARY for scalability testing. Not structurally representative of data pipelines.**

---

### 10. Open Graph Benchmark (OGB)

**What it is:** Standardized graph ML benchmark datasets with PyG/DGL loaders.

- **URL:** https://ogb.stanford.edu/
- **Format:** PyG / DGL compatible
- **License:** Various open

**Relevant datasets:** `ogbn-arxiv` (citation DAG), `ogbl-citation2` (directed citation links). Large scale, well-documented, easy to load.

**Verdict: SUPPLEMENTARY for scalability testing only. Same caveat as SNAP: citation topology differs from pipeline topology.**

---

## Summary: Recommended Dataset Strategy

### Primary validation corpus (use all of these):

1. **DLG-DG-23** - Real data lineage graphs, governance labels, varied sizes (278-17K nodes)
2. **dbt GitLab manifest** - Real data pipeline DAG with governance metadata (tests, docs, schemas)
3. **WfCommons** - 180 real workflow DAGs, varied applications, 180-9800 tasks

### Secondary / stress-testing:

4. **DW-Bench** - 5 small but well-characterized warehouse schemas for unit tests
5. **DAG-Transformer (Alibaba)** - Million-scale DAG corpus for statistical validation
6. **Isomera** - Synthetic data mesh graphs (if IEEE access available)

### Scale testing only:

7. **SNAP citation networks** - Large DAGs for performance benchmarking
8. **OGB** - Standard graph ML benchmarks

### Conversion priorities:

| Dataset | Parse effort | Graph extraction |
|---|---|---|
| DLG-DG-23 | Low (JSON) | Direct node/edge lists |
| DW-Bench | Low (PyG .pt) | `torch.load()` then convert |
| WfCommons | Low (JSON) | Parse WfFormat, extract task deps |
| dbt GitLab | Medium | Clone repo, run `dbt parse` or download published manifest |
| Alibaba/DAG-Transformer | Medium | Pre-processed DAG matrices |
| Isomera | Low (GML) | NetworkX reads GML natively |

---

## Sources

- DLG-DG-23: https://www.sciencedirect.com/science/article/pii/S2468502X24000020
- DW-Bench: https://arxiv.org/abs/2604.18964 / https://github.com/AJamal27891/dw-bench
- Isomera: https://ieee-dataport.org/documents/isomera-synthetic-data-mesh-lineage-graphs-tpc-ds-benchmarks-synthetic-scenarios-gml
- WfCommons: https://wfcommons.org/ / https://github.com/wfcommons/WfInstances
- Alibaba traces: https://github.com/alibaba/clusterdata
- DAG-Transformer: https://github.com/cloudworkflow/workflow-performance-prediction-jii
- dbt public projects: https://github.com/InfuseAI/awesome-public-dbt-projects
- GitLab dbt: https://gitlab.com/gitlab-data/analytics
- Marquez: https://github.com/MarquezProject/marquez
- SNAP: https://snap.stanford.edu/data/
- OGB: https://ogb.stanford.edu/
- TPC-DI: https://www.tpc.org/tpcdi/default5.asp
