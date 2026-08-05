# Submission Integrity Checklist

This file records what must be true before any journal upload. It is not a claim
that the current development manuscript is submission-ready.

## Evidence and claims

- [x] Phase 5 logistic-regression scaling is fitted inside each training fold.
- [x] Phase 5 random forest receives unscaled features.
- [x] Phase 5 artifacts and figure were regenerated from the corrected code.
- [x] Manuscript values match `artifacts/phase_5/exp7_hardening.json`.
- [x] Every statement that D1--D4 add no node-level lift has been removed. Phase
  5 does not contain those features.
- [x] The DLG result is labelled a centrality reproduction, not a governance
  prediction result.
- [x] The repair-linked Cal-ITP feasibility case is excluded from the successor
  study's confirmation set.
- [ ] Rerun the complete manuscript table-and-figure audit immediately before
  submission and record the commit SHA here.

## Manuscript package

- [ ] Convert the accepted draft to the current venue template. ACM journals
  require the ACM authoring template; the present `article` source is a working
  manuscript.
- [ ] Submit as a JDIQ **research paper**, not a challenge paper (3 pages,
  vision, unsolved problems) and not an experience paper (10 pages, mandatory
  `Experience:` title prefix). Rationale and sources in
  `artifacts/submission_strategy.md`.
- [ ] JDIQ review is double-anonymous. Create a separate anonymous source with
  author names, affiliation, and funding removed, and check that file metadata
  and self-citations do not leak identity. Do not anonymize the archival
  repository by rewriting history.
- [ ] Verify on the day of submission that University of the Cumberlands is
  still on the ACM Open participant list, and that the corresponding-author
  affiliation on the submission record is UC. Otherwise the 2026 APC of $1,450
  applies.
- [ ] Add accessible descriptions for every figure in the venue template.
- [ ] Resolve every LaTeX warning that affects references, floats, or text.
- [ ] Confirm the title, abstract, and contribution language match across the
  manuscript, submission form, cover letter, README, and archive metadata.
- [ ] Select one cover letter for the actual venue; do not submit letters for
  alternate journals in the same package.

## Reproducibility and archive

- [ ] Rebuild from a clean environment using the declared dependency set.
- [ ] Run the full test suite and archive its output with the submission record.
- [ ] Rebuild `paper/preprint.pdf` from the committed source.
- [ ] Verify that the Zenodo deposit contains the corrected Phase 5 code,
  artifacts, figure, and manuscript. Mint a new version if the current DOI
  resolves to an older package.
- [ ] Verify that no private dbt manifest, raw SQL, credential, or path-bound
  restricted artifact is included.
- [ ] Record repository commit, archive version, dataset hashes, and software
  versions in the reproducibility appendix.

## Declarations

- [ ] Recheck the selected journal's current authorship, generative-AI,
  competing-interest, funding, human-participant, and data-availability rules on
  the day of submission.
- [ ] Make the generative-AI declaration factually consistent with the work
  performed. The author remains solely accountable; an AI system is not an
  author.
- [ ] Confirm ORCID, email, affiliation, and sole-author metadata.
- [ ] Confirm that the manuscript is not under review elsewhere.
