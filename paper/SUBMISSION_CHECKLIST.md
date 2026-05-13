# Submission Artifact Checklists

## Data & Knowledge Engineering (Elsevier) — primary target

Submitted via Elsevier Editorial Manager: https://www.editorialmanager.com/dke/

### Required files

| File | Source | Notes |
|---|---|---|
| Manuscript PDF | `paper/preprint.pdf` | 20 pages, includes all tables and Figure 1 |
| LaTeX source archive (.zip) | `paper/preprint.tex` + `paper/references.bib` + `paper/figures/crossdataset_pca.pdf` | Required for production after acceptance; can upload at first submission |
| Cover letter | `paper/cover_letter_dke.md` | Convert to PDF or paste into "Cover Letter" field |
| Highlights (3–5 bullets, ≤85 chars each) | See below | Elsevier-specific |
| Graphical abstract (optional) | Skip for first submission | Can add after acceptance |
| Conflict of Interest declaration | None to declare | Standard checkbox + signed form |
| Author Agreement form | Elsevier provides template | Sign electronically |
| Suggested reviewers (≥3) | `paper/suggested_reviewers.md` | Enter into form fields |
| Data availability statement | See below | Mandatory field |
| Funding statement | "No external funding" | Standard field |

### Highlights (paste into Elsevier form, ≤85 chars each)

1. Four graph-theoretic descriptors computed on 32 lineage graphs from four sources.
2. Production lineage graphs cluster distinctly from scientific workflow topologies.
3. Single-org pilot of governance correlation; rigorous statistical methodology.
4. Cross-org replication fails due to construct mismatch in domain partitioning.
5. Feasibility study with explicit boundary condition for topology-based inference.

### Data availability statement

> Code, anonymised data, and experiment scripts are archived on Zenodo at DOI 10.5281/zenodo.20101643. The development repository is at https://github.com/mhdk1602/multiscale-governance-descriptors. The Zenodo archive reproduces every table and figure in the paper. The production dbt lineage data is anonymised via HMAC-SHA256 hashing; the WfCommons, DLG-DG-23, and DW-Bench external datasets are referenced via their original publications and URLs in the manuscript.

### Suggested reviewers form data

Enter from `paper/suggested_reviewers.md`. Elsevier requires:
- Name
- Affiliation
- Email
- Brief justification (1–2 sentences)

Need to verify the email addresses for Zhao (CSU), Porter (UCLA), Lambiotte (Oxford), Barahona (Imperial), De Domenico (Padua) before submission. Use institutional websites.

### Author keywords (paste into form)

`data lineage; data governance; community detection; spectral graph theory; persistent homology; structural descriptors; network analysis`

---

## Knowledge and Information Systems (Springer KAIS) — backup target

Submitted via Springer Editorial Manager: https://www.editorialmanager.com/kais/

### Required files

| File | Source | Notes |
|---|---|---|
| Manuscript PDF | `paper/preprint.pdf` | Same file as D&KE |
| LaTeX source (optional at submission) | `paper/preprint.tex` + bib + figures | Required after acceptance |
| Cover letter | `paper/cover_letter_kais.md` | Paste or upload |
| Title page (separate file) | Springer prefers separate title page with author info | See below |
| Conflict of Interest declaration | None | Standard form |
| Suggested reviewers (≥4, max 6) | `paper/suggested_reviewers.md` | Enter into form |
| Funding declaration | "No external funding" | Standard |
| Research data policy statement | See below | KAIS requires explicit |
| Ethics declaration | "No human subjects" | Mandatory checkbox |

### Title page content (separate document for Springer)

```
Title: Multi-Scale Structural Descriptors for Governance-Relevant
       Patterns in Data Lineage Graphs

Author: Dineshkumar Malempati Hari, Ph.D.
Affiliation: Independent Researcher
Email: mhdk.dinesh@gmail.com
ORCID: 0009-0003-1036-9477

Acknowledgements: None.
Funding: None.
Conflicts of interest: The author declares no conflicts of interest.
```

### Research data policy statement (Springer)

> The author has chosen Springer's data availability statement type 5: "All data and materials generated or analysed during this study are included in the published article and the Zenodo archive at DOI 10.5281/zenodo.20101643. No restrictions apply."

### Author keywords (KAIS form)

Same as D&KE.

---

## Both venues: pre-submission verification

Before pressing Submit, verify:

- [ ] Manuscript PDF compiles cleanly from source (no broken LaTeX, no missing figures)
- [ ] All citations in `references.bib` resolve in the bibliography
- [ ] All cross-references (Table 1, Figure 1, Experiment 2e, etc.) resolve correctly
- [ ] ORCID linked in author block matches form submission
- [ ] Zenodo DOI is correct (10.5281/zenodo.20101643) and the archive is accessible
- [ ] GitHub repository is public (currently is)
- [ ] No PII or organisational identifiers in anonymised data
- [ ] Cover letter mentions the no-APC subscription publication preference explicitly

## Estimated time per submission

- D&KE: 45–60 min (more forms than KAIS)
- KAIS: 30–45 min

## Where the LaTeX source archive goes

For both venues, you can submit the PDF only at first submission and only upload the LaTeX source after acceptance. Most authors do this. If you want to upload everything upfront, create:

```
preprint_source.zip:
  preprint.tex
  references.bib
  figures/crossdataset_pca.pdf
  README.md (one-paragraph build instructions)
```

Build with `tectonic preprint.tex` to verify.
