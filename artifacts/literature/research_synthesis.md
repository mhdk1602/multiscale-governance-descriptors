# Literature Synthesis: Multi-Scale Descriptors for Governance Graphs

**Compiled:** 2026-05-04

---

## Core research gap

No published work measures data governance quality through structural/graph-theoretic properties of data artifacts. Existing governance measurement relies on surveys, maturity assessments (DAMA-DMBOK, DCAM), and document analysis.

The theoretical foundations exist on both sides:
- Institutional theory (DiMaggio & Powell 1983; Scott 2013) predicts structural convergence among organizations under similar governance pressures
- Graph descriptors (spectral, community, topological) measure structural properties at multiple scales

Nobody has connected them. This synthesis is the contribution.

---

## D1: Community stability under resolution sweep

### Method foundation
- **Reichardt & Bornholdt (2006)**, Phys. Rev. E 74, 016110. Modified modularity: B_ij = A_ij - gamma * k_i * k_j / (2m). Higher gamma = finer partitions.
- **Lambiotte, Delvenne & Barahona (2014)**, IEEE TNSE 1(2), 76-90. Resolution parameter as Markov diffusion time. Physical interpretation: short diffusion = small communities, long diffusion = large.
- **Delvenne, Yaliraki & Barahona (2010)**, PNAS 107, 12755-12760. Stability as plateau detection via NVI across resolution sweep. Stable partitions = intrinsic scales.

### Resolution limit
- **Fortunato & Barthelemy (2007)**, PNAS 104(1), 36-41. Communities smaller than sqrt(L/2) edges are invisible to modularity. For N=150, avg degree 6: resolution floor ~15 nodes.
- **Constant Potts Model (CPM)** avoids the resolution limit entirely; resolution parameter is absolute, not relative to network size.

### DAG handling
- **Speidel, Takaguchi & Masuda (2015)**, Eur. Phys. J. B 88, 203. DAG-specific modularity exists but converting to undirected is "nearly as good." Defensible shortcut.
- **Vasiliauskaite & Evans (2020)**, Applied Network Science. "Siblinarity" groups nodes by shared parents/children, respecting DAG order.

### Leiden vs Louvain
- **Traag, Waltman & van Eck (2019)**, Scientific Reports 9, 5233. Leiden guarantees connected communities (Louvain can produce disconnected ones in up to 16% of cases). For N < 200, speed is irrelevant; connectivity guarantee is the value.

### Small-graph viability
LFR benchmark (Lancichinetti et al. 2008) established N=128 as unrealistically small. For N=50-200, community detection is viable but near the resolution limit. CPM recommended for this regime.

---

## D2: Blast-radius concentration profile

### Gini on networks
- **Hu & Wang (2005)**, Advances in Complex Systems. Foundational: Gini of degree distribution equivalent to degree exponent for scale-free networks.
- **Zabka et al. (2022)**, Financial Cryptography. Gini on betweenness in Lightning Network: 90% of nodes = 10% of cumulative betweenness.

### Cascade analysis
- **Burkholz & Quackenbush (2021)**, AAAI. Subtree Distribution Propagation: computes full cascade size distribution in O(N) on trees. But not depth-stratified.
- **Goel et al. (2021)**, PNAS. Cascade depth, breadth, reach are correlated with size but not measured as Gini-vs-depth.

### Fault propagation in data pipelines
- **Li et al. (2025)**, Scientific Reports 16:4430 (EEFL framework). TCN+GCN on lineage DAGs (1,240 nodes, 5,870 edges). Fault classification, not propagation modeling. 95.8% accuracy.
- **Drori et al. (2019)**, arXiv:1903.00405. Error contribution metric decomposing end-to-end pipeline error into per-stage contributions. ML pipelines, not general data quality.

### Monitor placement
- **Krause, Singh & Guestrin (2008)**, JMLR 9:235-284. Sensor placement via submodular mutual information maximization. Greedy algorithm with (1-1/e) approximation guarantee. Directly transferable to monitor placement on lineage DAGs.

### NOVELTY: Gini-vs-depth curve is unpublished. Individual ingredients exist; the composition is new.

---

## D3: Spectral gap and Fiedler structure

### Algebraic connectivity
- **Fiedler (1973)**, Czechoslovak Math. J. 23(98), 298-305. Lambda_2 = algebraic connectivity. Zero iff disconnected. Increases with edge addition. No minimum N.

### Spectral gap and robustness
- **DOE Technical Report** (OSTI 973665). Lambda_2 correlates inversely with mean path length in infrastructure networks.
- **Makse et al. (2024)**, Nature Reviews Physics. Spectral methods connect to percolation thresholds and cascading failures.

### Spectral entropy
- **De Domenico & Biamonte (2016)**, Phys. Rev. X 6, 041062. Von Neumann entropy of normalized Laplacian as complexity measure. Depends on network as a whole, not a single descriptor.
- **PLOS ONE (2021)**. Eigenvalue-based entropy extended to directed networks.

### Small-graph viability
Fiedler vector is defined for any connected graph with N >= 2. No lower bound. Quality depends on community structure presence, not size.

---

## D4: Persistent homology (exploratory)

### Standard references
- **Otter et al. (2017)**, EPJ Data Science 6:17. Computational roadmap. Standard filtrations: weight rank clique filtration, shortest-path distance, sublevel-set.
- **Petri et al. (2013)**, PLOS ONE 8(6):e66506. Weight-based filtrations revealing topological strata.

### Directed networks
- **Chowdhury & Memoli (2018)**, SODA, 1152-1169. Persistent Path Homology (PPH) for directed networks. For DAGs: H1 under PPH is trivial (no directed cycles by definition). Detection of H1 = structural anomaly (governance violation). Python: pypph.

### TDA on small graphs
No hard lower bound. Viable for any N, but informative only if enough topological structure exists. For governance DAGs: H0 (component merging) and H1 (cycles in undirected version = redundant paths) are meaningful.

### NOVELTY: No published TDA on data lineage or governance graphs.

---

## Governance measurement literature

### Core frameworks
- **Khatri & Brown (2010)**, CACM 53(1), 148-152. Five decision domains: data principles, quality, metadata, access, lifecycle.
- **Weber, Otto & Osterle (2009)**, JDIQ 1(1), 1-27. Contingency approach: governance design depends on organizational strategy.
- **Abraham, Schneider & vom Brocke (2019)**, IJIM 49, 424-438. Six dimensions. Structural/procedural/relational mechanisms.
- **DAMA-DMBOK**: 11 knowledge areas. Maturity via CMM/CMMI at 5 levels.

### Institutional theory
- **DiMaggio & Powell (1983)**, ASR 48(2), 147-160. Coercive, mimetic, normative isomorphism.
- **Scott (2013)**, Institutions and Organizations, 4th ed. Regulative, normative, cultural-cognitive pillars.
- **JBR (2025)**. Governance principles are "emergent institutional arrangements" not top-down mandates.
- **Electronic Markets (2025)**. Data ecosystems drift from decentralized to centralized governance as they mature.

### Graph-based governance (closest work)
- **KG.GOV (Tiddi et al. 2024)**, J. Web Semantics. KGs as backbone of data governance in AI.
- **Seo et al. (2022)**, Semantic Web Journal. Six structural quality metrics for KGs.
- **Zietsman (2026)**, arXiv:2604.21090. Structural completeness of AI governance prompt files (text, not graphs).

---

## Available datasets

| Dataset | Size | Format | License | Priority |
|---|---|---|---|---|
| DW-Bench (2024) | 5 schemas, 262 tables, 521 edges | PyTorch Geometric HeteroData | MIT | HIGH |
| Huawei DLG (2024) | 18 real lineage graphs | ScienceDirect (CC BY-NC-ND 4.0) | CC BY-NC-ND | HIGH |
| WfCommons Pegasus | 135 workflows, 25-1000 tasks | WfCommons JSON | BSD | MEDIUM |
| GitLab dbt | Thousands of models | manifest.json | MIT | MEDIUM |
| Dune Spellbook dbt | Thousands of models | dbt project | OSS | LOW |
| TPC-DI | 35 tables, 50 edges | Spec + generator | TPC EULA | LOW |

---

## Novelty summary

| Contribution | Status |
|---|---|
| Graph descriptors measuring governance quality | NOVEL: no published precedent |
| Gini-vs-depth blast-radius curve | NOVEL: composition of known ingredients |
| MTTD + sensor placement on lineage DAGs | NOVEL for data quality domain |
| Stewardship allocation by graph structure | NOVEL |
| TDA on data lineage graphs | NOVEL |
| Multi-resolution community detection on lineage | NOVEL application (method is established) |
| Spectral descriptors on governance graphs | NOVEL application |
