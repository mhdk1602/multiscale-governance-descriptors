# Draft email — DLG-DG-23 core-asset annotations (Ying Zhao group, CSU)

**To:** Ying Zhao (and co-authors), Central South University — corresponding author of the DLG-DG-23 dataset paper (Chen, Zhao, Li, Zhang, Long, Zhou, *Visual Informatics* 8(1), 2024).
**From:** Dineshkumar Malempati Hari (ORCID 0009-0003-1036-9477).
**Purpose:** ask whether more than the 36 published core-asset labels exist, and open a possible collaboration. Non-blocking for the JDIQ submission; send early because reply time is out of our control.

---

**Subject:** DLG-DG-23 core-asset labels — availability beyond Table 5?

Dear Dr. Zhao,

I am an independent researcher working on structural descriptors for data-lineage graphs, building directly on your DLG-DG-23 dataset and the *Visual Informatics* (2024) paper. The dataset has been genuinely useful, so thank you for releasing it.

I am writing with a specific question. In my reproduction, node-centrality features identify the expert-marked core assets well (mean AUC ≈ 0.90 under leave-one-graph-out cross-validation), which is consistent with your finding that centrality carries core-asset signal. I would like to test whether richer multi-scale descriptors add anything beyond centrality, but the analysis is constrained by the number of labeled core assets available in the public release (I count roughly 36 across the graphs in Table 5).

Two questions:

1. Do you hold core-asset annotations beyond those in the public release, even partial ones? Additional labels would let the comparison reach a sample size where a descriptor-versus-centrality difference is statistically meaningful, rather than at the current detection floor.

2. If such labels exist, would you be open to a short collaboration or a data-sharing arrangement (under whatever terms suit your group)? I am happy to share my descriptor code and the reproduction in return, and to credit your group appropriately.

If the 36 labels are the complete set, that is also useful to know: it tells me the ceiling on this analysis, and I will frame my results accordingly.

Thank you for your time, and for the dataset.

Best regards,
Dineshkumar Malempati Hari
ORCID 0009-0003-1036-9477
github.com/mhdk1602/multiscale-governance-descriptors

---

**Notes for the author (not part of the email):**
- This does not gate the JDIQ submission. If they decline or do not reply, ship the single-org negative result and cite the label ceiling as the reason the descriptor-vs-centrality test is underpowered.
- A positive reply could turn Experiment 7 from "reproduces Chen 2023" into a genuine descriptor-adds-no-lift (or, if it reverses, a descriptor-adds-lift) result at adequate n.
- Keep the centrality-reproduction framing honest in any follow-up; do not imply the descriptors beat centrality before the labels exist to show it.
