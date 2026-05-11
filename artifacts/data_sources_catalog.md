# Public Data Lineage / Governance Dataset Catalog

Compiled May 2026. Used to inform Pivot C and future partnership outreach.
Datasets are tiered by governance-metadata quality and usability for
topology-governance correlation studies.

---

## Tier 1: Datasets with explicit governance metadata

### 1. RAIRAB (Nov 2025) — **highest priority for follow-up**
- **Citation**: "Prudential Reliability of Large Language Models in Reinsurance: Governance, Assurance, and Capital Efficiency" — arXiv:2511.08082
- **URL**: https://arxiv.org/html/2511.08082v1
- Regulatory-grade governance metadata: encrypted lineage registers, Solvency II Article 41 / EIOPA / IAIS compliance. First lineage benchmark with regulatory framework embedded by design.
- Authentication: open (arXiv).
- **Action**: read full paper; check if dataset is downloadable; this could be the cleanest governance-labeled lineage dataset in existence.

### 2. OpenMetadata sandbox
- **URL**: http://sandbox.open-metadata.org (live demo, no auth)
- **GitHub**: https://github.com/open-metadata/openmetadata
- Explicit governance metadata: owners, tags, domains, glossary terms, quality scores, data products.
- **Action**: try extracting via the OpenMetadata API at the sandbox URL; check what governance fields are populated on demo data.

### 3. LinkedIn DataHub (open source)
- **GitHub**: https://github.com/datahub-project/datahub
- Docker quickstart at http://localhost:9002 (after `datahub docker quickstart`).
- Demo includes Kafka → Hive → derived tables with owner annotations (we already inspected the bootstrap_mce.json, 7 datasets).
- **Action**: stand up the Docker quickstart locally and pull demo data via REST API.

### 4. dbt Jaffle Shop with metadata extensions
- **URL**: https://github.com/dbt-labs/jaffle-shop-metadata
- Documented dbt-labs example; includes `meta.owner: "@drew"`, `meta.contains_pii: true`, `meta.SLA: "1 hour"`. PII classification on raw_customers.
- Small (~10 models) — insufficient for correlation analysis but useful as a reference for governance-metadata schema.

---

## Tier 2: Structural lineage without governance labels (already in paper)

### 5. DLG-DG-23 (Chen et al., Visual Informatics 2024)
- 18 Huawei Cloud DLGs, 278–17,085 nodes per graph; structural only in public release.
- **Action**: email Ying Zhao (Central South University) to request the core-asset annotations referenced in the paper.

### 6. WfCommons
- Scientific workflow DAGs (astronomy, bioinformatics, geophysics, seismology), 100s of workflows, no governance metadata.

### 7. DW-Bench
- 2 warehouse schemas (OMOP, TPC-DI), no governance metadata.

---

## Tier 3: Newly published 2025 datasets — worth tracking

### 8. Schema Lineage Extraction Benchmark (Aug 2025)
- **URL**: https://arxiv.org/html/2508.07179v1
- Multilingual real-world data processing scripts (SQL, Python). Implicit governance metadata in script structure.
- **Action**: check supplementary materials for dataset URLs.

### 9. LineageX: Column Lineage Extraction System (May 2025)
- **URL**: https://arxiv.org/html/2505.23133v1
- Column-level lineage from SQL warehouses. Directly applicable to governance research.
- **Action**: check if column-level lineage examples are downloadable.

---

## Tier 4: Workflow provenance with execution metadata (FAIR / RO-Crate)

### 10. Workflow Run RO-Crate examples (Leo et al., PLOS ONE 2024)
- Multiple Zenodo DOIs:
  - runcrate: 10.5281/zenodo.7774351
  - Galaxy: 10.5281/zenodo.7785861
  - StreamFlow: 10.5281/zenodo.7911906
  - Sapporo: 10.5281/zenodo.10134581
  - Autosubmit: 10.5281/zenodo.8144612
- Provenance metadata (author, contributor, version, test data, documentation) but not domain-level governance.
- **Action**: useful as comparison datasets for the cross-dataset characterization, less so for governance correlation.

### 11. WorkflowHub registry
- https://about.workflowhub.eu/
- 100s of registered workflows with RO-Crate metadata.

### 12. PegasusHub workflow repository
- Curated instances at https://github.com/wfcommons/pegasus-instances
- Scientific workflows with execution provenance.

---

## Tier 5: Government open data — metadata but no lineage

### 13. data.europa.eu (DCAT-AP)
- Publisher, creator, contact, license, update frequency. No lineage graph.

### 14. data.gov (DCAT-US)
- 100,000+ datasets but no inter-dataset lineage.

---

## Why finding governance-labeled lineage is hard

After this round of search, the constraint is clear:
- Organisations that publish dbt projects (Cal-ITP, Mattermost, GitLab) rarely populate `meta.domain` consistently — most rely on folder structure.
- Organisations that publish curated metadata (OpenMetadata/DataHub demos, dbt-labs Jaffle Shop) keep the example data small.
- Organisations with rich curated governance metadata at scale (enterprise data teams) do not publish it because the metadata itself reveals organisational structure.
- The 2024–2025 academic datasets (DLG-DG-23, Schema Lineage, LineageX) lead with structural lineage; governance metadata is either implicit, sparse, or absent from public releases.

**The structural gap is real, not just an artifact of insufficient searching.** This is a research-data infrastructure problem in the lineage-governance field: governance metadata at the necessary granularity is enterprise-internal almost by definition.

---

## Recommended follow-up actions

| Priority | Action | Effort |
|---|---|---|
| 1 | Read RAIRAB paper end-to-end; identify if its lineage corpus is downloadable | 1 day |
| 2 | Stand up OpenMetadata sandbox locally; extract via API; assess scale | 2 days |
| 3 | Email DLG-DG-23 authors for core-asset annotations | 1 hour + waiting |
| 4 | Email RAIRAB authors for any non-encrypted lineage corpus | 1 hour + waiting |
| 5 | Stand up DataHub Docker; pull sample data; extract via REST | 1 day |
| 6 | Check LineageX and Schema Lineage Extraction papers for dataset releases | 1 day |
| 7 | Pivot C — git-history of Cal-ITP + Mattermost (no new external data needed) | 2–4 weeks |

The current paper does not need to wait for any of these.
