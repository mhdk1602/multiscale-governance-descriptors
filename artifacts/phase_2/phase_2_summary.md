# Phase 2 Results Summary

**Date:** 2026-05-04

---

## Experiments completed

### Experiment 1: Governance differentiation (120 conditions)
- 4 scales x 3 governance levels x 10 seeds
- All D1-D4 descriptors + 9 single-scale baselines + 3 MTTD strategies

**Key findings:**
- D1 (CSI): well=0.653 vs poor=0.374 at large scale. Cohen's d=3.90. p<0.001.
- D4 (H1/N): well=0.589 vs poor=0.743 at large scale. Cohen's d=-15.99. p<0.001.
- D1 fragmentation onset: well=0.800 vs poor=0.154 at large scale. Cohen's d=4.74. p<0.001.
- D3 (Fiedler bimodality): significant but direction depends on intervention type.
- D2 (max Gini): significant at large scale (p=0.003) but weak effect size.
- Phase 2 gate: PASS. 4/4 descriptors significant at large scale, 3/4 at medium.

### Experiment 3: Intervention sensitivity (4 interventions, 60 random perturbation trials)
**Key findings:**
- Domain boundary addition: strongest structural signal. D4 SNR=8.67, D3 entropy SNR=6.85.
- Orphan removal: strong spectral response. D3 gap SNR=6.53, D1 frag_onset SNR=3.87.
- Monitor addition: moderate D1 CSI response (SNR=2.19), D2 Gini (SNR=2.79).
- Shortcut removal: weak signal across all descriptors (4 edges in 132 is below noise floor).
- Each descriptor responds most to a different intervention type, validating multi-descriptor approach.

### Experiment 4: Predictive comparison
**Key findings:**
- Classification (well vs poor): ceiling effect. Both baselines and multi-scale achieve AUC=1.0. Synthetic data creates too-clean separation. Not informative for feature set comparison.
- MTTD regression: multiscale RF R²=0.307 vs baselines RF R²=0.175. Multi-scale explains 75% more variance. Ridge regression shows similar pattern (multiscale R²=0.277 vs baselines R²=0.246).
- Combined features do not improve over multiscale-only (possible overfitting with 20 features on 120 samples).

---

## Gate assessment

| Gate | Criterion | Result |
|---|---|---|
| Phase 1 | All 4 descriptors produce interpretable output at N=30-200 | PASS |
| Phase 2 | >= 2 descriptors with p<0.05 for well vs poor | PASS (4/4 at large, 3/4 at medium) |
| Phase 3 (classification) | Delta-AUC > 0.05 | FAIL (ceiling effect) |
| Phase 3 (regression) | Delta-R² > 0.10 | PASS (delta-R² = 0.132) |

---

## Descriptor ranking (by publishable evidence strength)

1. **D1 (Community Stability Index):** Strongest governance interpretation. CSI and fragmentation onset both significant with large effect sizes. Clear theoretical grounding in institutional theory (domain boundaries as governance structure).

2. **D4 (Persistent Homology H1/N):** Strongest effect size. Normalized H1 bar count separates governance levels with Cohen's d > 15. Measures redundant path density, which governance practices should reduce. Most novel (no prior TDA on lineage graphs).

3. **D3 (Spectral Descriptors):** Mixed but informative. Spectral entropy and Fiedler bimodality show governance signal, but the normalized spectral gap is confounded by domain isolation reducing connectivity. Requires careful interpretation in the paper.

4. **D2 (Blast-Radius Gini):** Weakest differentiation. Max Gini differences are small. The Gini-vs-depth curve shape may be more informative than the max value, but current aggregation loses this signal. The concept is novel but needs refinement for governance measurement.

---

## What's needed for the paper

1. Real data validation (Experiment 2) would strengthen the contribution but is not required. The synthetic results are a self-contained methods contribution.

2. The classification ceiling effect needs framing: "synthetic experiments confirm structural detectability; real-world validation requires data where governance quality varies continuously rather than categorically."

3. The MTTD regression result (R²=0.307 vs 0.175) is the core predictive finding. This needs confidence intervals and potentially a paired permutation test.

4. The intervention sensitivity results (Experiment 3) are the strongest evidence for construct validity: the descriptors respond to governance-relevant perturbations more than to random noise.
