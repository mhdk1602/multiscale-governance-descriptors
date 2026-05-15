<p align="center">
  <img src="assets/readme/descriptor-system.svg" alt="Multiscale Governance Descriptors hero graphic" width="100%">
</p>

<h1 align="center">Multiscale Governance Descriptors</h1>

<p align="center">
  <strong>Graph descriptors for reading governance-relevant structure in data lineage systems.</strong>
</p>

<p align="center">
  <a href="https://github.com/mhdk1602/multiscale-governance-descriptors/releases/tag/v2.1.0"><img alt="Release v2.1.0" src="https://img.shields.io/badge/release-v2.1.0-55d6be?style=for-the-badge"></a>
  <a href="https://doi.org/10.5281/zenodo.20209148"><img alt="Zenodo DOI 10.5281/zenodo.20209148" src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.20209148-2f6f8f?style=for-the-badge&logo=zenodo&logoColor=white"></a>
  <img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-3776ab?style=for-the-badge&logo=python&logoColor=white">
  <img alt="NetworkX" src="https://img.shields.io/badge/graphs-NetworkX-f5b84b?style=for-the-badge">
</p>

<p align="center">
  <a href="#signal">Signal</a> /
  <a href="#descriptor-stack">Descriptor Stack</a> /
  <a href="#quick-start">Quick Start</a> /
  <a href="#reproducibility">Reproducibility</a> /
  <a href="#citation">Citation</a>
</p>

This repository asks a narrow research question:

> When governance metadata is missing, sparse, or too sensitive to publish, how much governance signal is already present in the topology of the lineage graph?

The answer is conditional. Domain-level aggregate correlations are unstable when layer composition dominates the graph. Node-level prediction, against curated expert labels, is much stronger: in DLG-DG-23 Huawei Cloud lineage graphs, topological features distinguish expert-marked core assets at mean logistic-regression AUC `0.897 +/- 0.099`.

## Signal

| Finding | Evidence | Where |
|---|---:|---|
| Core asset prediction on DLG-DG-23 | LR AUC `0.897 +/- 0.099`, random baseline `0.546`, `p = 0.0003` | `artifacts/phase_5/` |
| Shared-ID leakage check | AUC remains `0.890` after removing 3 repeated core IDs | `artifacts/phase_5/exp7_hardening.json` |
| Production dbt descriptor profile | `223` nodes, `263` edges, `26` anonymized domains | `artifacts/phase_3/` |
| Longitudinal dbt drift | `106` snapshots across `9.0` project-years, `44` large drift events | `artifacts/phase_4/summary_refined.json` |
| Cross-organisation caution | Cal-ITP and Mattermost do not reproduce the single-organisation D3 correlation | `artifacts/phase_3/exp6_summary.json` |
| Synthetic scale check | Multiscale descriptors reach AUC `0.935 +/- 0.113`; simpler baselines reach `1.000` | `artifacts/phase_3/exp4_grouped_cv.json` |

The core boundary condition:

> Topology-based governance inference works best at node granularity with curated expert labels. It is weaker at domain granularity when the target is aggregated governance metadata.

## Descriptor Stack

```mermaid
flowchart LR
    G["Lineage graph<br/>directed assets + dependencies"] --> D1["D1<br/>community stability<br/>resolution sweep"]
    G --> D2["D2<br/>blast-radius concentration<br/>Gini by depth"]
    G --> D3["D3<br/>spectral structure<br/>Fiedler geometry"]
    G --> D4["D4<br/>persistent topology<br/>H1 path redundancy"]

    D1 --> V["Descriptor vector"]
    D2 --> V
    D3 --> V
    D4 --> V

    V --> C["Comparative profile<br/>dbt / WfCommons / DLG-DG-23"]
    V --> P["Prediction task<br/>core asset classification"]
    V --> T["Time series<br/>topological drift events"]
```

| Family | Question | Representative outputs |
|---|---|---|
| `D1` community stability | Are domain boundaries stable across Louvain resolution? | CSI, fragmentation onset, modularity variance |
| `D2` blast radius | Is downstream impact concentrated in a small set of assets? | Gini curve, top-k downstream stability |
| `D3` spectral structure | How tightly coupled is the lineage skeleton? | algebraic connectivity, spectral gap, Fiedler bimodality, entropy |
| `D4` persistent topology | Are there persistent alternate paths through the graph? | H1 bars, total persistence, persistence entropy |

## Quick Start

```bash
git clone https://github.com/mhdk1602/multiscale-governance-descriptors.git
cd multiscale-governance-descriptors
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Compute the descriptor stack for a small lineage DAG:

```python
import networkx as nx
from governance_descriptors import (
    resolution_sweep,
    community_stability_index,
    concentration_profile,
    spectral_descriptors,
    topological_descriptors,
)

g = nx.DiGraph()
g.add_edges_from([
    ("raw_orders", "stg_orders"),
    ("raw_customers", "stg_customers"),
    ("stg_orders", "int_customer_orders"),
    ("stg_customers", "int_customer_orders"),
    ("int_customer_orders", "mart_customer_health"),
])

sweep = resolution_sweep(g, n_steps=12, seed=42)

profile = {
    "D1_csi": community_stability_index(sweep),
    "D2_blast_radius": concentration_profile(g, max_depth=3),
    "D3_spectral": spectral_descriptors(g),
    "D4_topology": topological_descriptors(g),
}

print(profile)
```

## Reproducibility

The repo is organized around executable experiments and saved result artifacts.

| Path | Contents |
|---|---|
| `src/governance_descriptors/` | Python implementation of D1-D4 descriptors and statistical helpers |
| `experiments/phase_3/` | real-data validation, null models, seed checks, cross-organisation comparison |
| `experiments/phase_4/` | longitudinal dbt topology drift over public project histories |
| `experiments/phase_5/` | DLG-DG-23 node-level core-asset prediction |
| `data/` | anonymized dbt metadata plus public external graph datasets |
| `paper/` | preprint source, references, submission materials |
| `artifacts/` | JSON, CSV, and Markdown outputs used by the paper |

Run the strongest current result:

```bash
python experiments/phase_5/exp_dlg_core_asset_prediction.py
```

Run the longitudinal dbt drift analysis:

```bash
python experiments/phase_4/exp_longitudinal_dbt.py
```

The production dbt graph is anonymized with HMAC-SHA256. The repository does not expose SQL, column names, business identifiers, or private lineage semantics.

## Empirical Scope

This is research code, not a governance scoring product. The project separates three claims:

1. Production data lineage graphs have measurable structural signatures.
2. Some graph descriptors correlate with governance metadata in a single anonymized dbt case, but those domain-level correlations are sensitive to layer structure.
3. Node-level topological features predict curated expert core-asset labels across six DLG-DG-23 graphs with materially better-than-random AUC.

That distinction matters. The methods are useful when the unit of analysis and label quality match the graph signal.

## Citation

```bibtex
@misc{hari2026multiscale,
  title  = {Multiscale Structural Descriptors for Data Governance Graph Assessment},
  author = {Dineshkumar Malempati Hari},
  year   = {2026},
  doi    = {10.5281/zenodo.20209148},
  url    = {https://github.com/mhdk1602/multiscale-governance-descriptors}
}
```

## Repository Status

- Latest release: `v2.1.0`
- Archive DOI: `10.5281/zenodo.20209148`
- Primary language: Python
- Main dependencies: NetworkX, NumPy, SciPy, pandas, GUDHI, scikit-learn
