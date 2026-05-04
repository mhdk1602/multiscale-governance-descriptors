# Real Data Validation Summary

## Data Source

Production dbt manifest.json + catalog.json (dbt 1.11.0, schema v12).
Anonymized via HMAC-SHA256 with private salt; no identifiers, SQL,
column names, or business logic exported.

- **Full graph**: 223 nodes, 263 edges, 26 anonymized domains
- **Largest component**: 185 nodes, 262 edges, 25 domains
- **Layers**: source/raw (155), silver/intermediate (33), gold/mart (35)
- **Governance**: 30 nodes with tests (81 total), 96 with documentation, 0 with steward

## Full-Graph Descriptor Profile

| Descriptor | Value |
|---|---|
| D1 CSI | 0.947 |
| D1 communities (gamma=1) | 10 |
| D1 modularity | 0.704 |
| D2 max Gini | 0.480 |
| D3 algebraic connectivity | 0.067 |
| D3 normalized gap | 0.003 |
| D3 spectral entropy | 6.674 |
| D4 H1 bars | 49 |
| D4 H1/N | 0.220 |
| D4 H1 entropy | 5.563 |

## Statistically Significant Correlations (Spearman)

### vs governance_score (composite: steward + test + doc / 3)

| Descriptor | rho | p-value | sig |
|---|---|---|---|
| D3 algebraic connectivity | -0.643 | 0.0040 | *** |
| D3 normalized gap | -0.635 | 0.0046 | *** |
| D2 max Gini | -0.447 | 0.063 | * |
| D3 spectral entropy | -0.447 | 0.063 | * |

### vs documentation rate

| Descriptor | rho | p-value | sig |
|---|---|---|---|
| D3 algebraic connectivity | -0.708 | 0.0010 | *** |
| D3 normalized gap | -0.701 | 0.0012 | *** |
| D2 max Gini | -0.563 | 0.015 | ** |
| D3 spectral entropy | -0.563 | 0.015 | ** |
| D3 Fiedler bimodality | -0.561 | 0.016 | ** |

### vs test rate

| Descriptor | rho | p-value | sig |
|---|---|---|---|
| D4 H1 bars / N | +1.000 | <0.001 | *** |
| D4 H1 total persistence | +1.000 | <0.001 | *** |
| D2 max Gini | +0.475 | 0.046 | ** |
| D3 Fiedler bimodality | +0.473 | 0.047 | ** |
| D3 spectral entropy | +0.475 | 0.046 | ** |

## Layer-Stratified Governance

| Layer | N | Steward | Tested | Documented |
|---|---|---|---|---|
| source/raw | 155 | 0% | 0% | 41% |
| silver/intermediate | 33 | 0% | 0% | 0% |
| gold/mart | 35 | 0% | 86% | 91% |

## Cross-Topology Comparison

| Topology | N | M | CSI | maxGini | gap | entropy | H1/N | govScore |
|---|---|---|---|---|---|---|---|---|
| dbt manifest (real) | 223 | 263 | 0.947 | 0.480 | 0.003 | 6.674 | 0.220 | 0.188 |
| Static code pipeline | 86 | 97 | 0.947 | 0.320 | 0.003 | 5.858 | 0.128 | 0.000 |
| Synthetic 6-domain | 108 | 161 | 0.684 | 0.506 | 0.002 | 6.197 | 0.556 | 0.565 |

## Interpretation

1. **D3 spectral descriptors are the strongest governance discriminators** in real data (p<0.005). Domains with higher internal connectivity (algebraic connectivity) tend to have lower documentation, reflecting the organizational pattern where intermediate transformation layers are structurally dense but less documented than source or mart layers.

2. **D4 topological descriptors perfectly discriminate tested from untested domains.** Only domain_012 (the gold/mart domain, 86% tested) has H1 topological features; all source-only domains have H1=0. This binary split is technically correct but driven by the single well-governed domain.

3. **D2 blast-radius concentration tracks test coverage.** Domains with higher max Gini (concentrated downstream impact) tend to have more tests, suggesting governance investment follows structural risk.

4. **Real vs synthetic structural profiles differ categorically.** The real dbt graph has CSI=0.947 (vs 0.684 synthetic), indicating far more stable community structure. H1/N=0.220 (vs 0.556) indicates fewer topological loops, consistent with a production DAG optimized for clarity.

## Limitations

- 0/223 nodes have steward metadata (steward_rate excluded from analysis)
- Only 6/18 analyzable domains have internal edges; remaining 12 are source-only clusters
- D4 perfect correlation with test_rate is driven by domain_012 being the sole domain with both topological features and tests
- Single production instance; cross-organization generalization requires additional datasets
