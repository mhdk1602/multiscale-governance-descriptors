# Submission Strategy

Rewritten 2026-08-05. The previous version filed ACM JDIQ under "no longer
viable" on the grounds that it now charges an APC. The APC is real. The
conclusion was wrong, because the APC does not apply to this author.

## The APC question, settled

ACM became a fully open-access publisher on 1 January 2026. The JDIQ author
guidelines state it directly, "As of January 1, 2026, ACM is a fully Open
Access Publisher. All ACM publications, including ACM journals, are 100% Open
Access." The 2026 APC is $1,450, reduced by a temporary ACM-funded subsidy.

Two other documents in this repository still assert that JDIQ charges no APC.
They are stale and should be read as superseded by this file.

**University of the Cumberlands is an ACM Open participating institution.** It
appears by name on the ACM Open participant list at
libraries.acm.org/acmopen/open-participants, in the United States block between
"University of Wyoming" and "University of the Pacific". ACM Open is a read-and-
publish agreement that gives participating institutions unlimited open-access
publishing in the ACM Digital Library, so a paper submitted under that
affiliation carries no APC.

Two conditions attach and both need checking on the day of submission. ACM
verifies eligibility against the *corresponding author's* affiliation, so the UC
affiliation must be the one on the submission record, not a secondary listing.
And institutional participation is renewed periodically, so re-verify against
the live participant list rather than against this file.

The manuscript byline has been changed from "Independent Researcher" to
"University of the Cumberlands, Williamsburg, KY, USA" accordingly. That is also
the more accurate description of the author's academic affiliation.

## Paper type, settled

JDIQ publishes six contribution types. The three that could plausibly fit and
their published limits, from the JDIQ call for papers, are these.

| Type | Length | Character |
|---|---|---|
| Research paper | 20–25 single-spaced pages (final version) | Significant and novel contribution. Explicitly admits "empirical research to experiential evaluations". Reviewed on relevance, originality of the problem, grounding in theory and literature, appropriateness of research methods, readability. |
| Experience paper | **10 pages** plus optional online supplement. Mandatory `Experience:` prefix in the title. | A practitioner or industrial researcher with a compelling application or interesting dataset. Reviewed on whether the data-quality problem is clearly specified and whether a convincing solution is offered. |
| Challenge paper | **3 pages**, 4 by exception. No abstract needed. | Vision piece describing an *unsolved* open challenge on page one and possible solutions on page two. |

**A challenge paper is out.** Three pages of vision cannot carry a 28-page
empirical study, and the paper's whole point is that it ran the test and got an
answer, which is the opposite of "not yet solved".

**Recommended type: research paper.** The manuscript is an empirical study with
a methods contribution, currently 28 pages in `article`/11pt/a4 with 1in margins.
JDIQ requires the `acmsmall` template, which sets denser than the current class,
so the reformatted length should land inside or near the 20–25 page band. The
research-paper review criteria are also the right fit, since they weigh method
appropriateness and originality of the *problem*, which is where a well-executed
null earns its keep.

**Experience paper is the fallback and it costs real work.** Ten pages plus a
supplement means cutting roughly 60% of the body, and the reviewer criteria
("do the authors provide a solution? is it convincing?") suit a null result
poorly. Choose it only if an editor signals that the research-paper track will
not take a negative result.

Submission is double-anonymous, so author names, affiliations and funding must
be stripped from the submitted PDF and added back on acceptance. An existing
arXiv or SSRN preprint does not need to be withdrawn.

## Venue ranking

| Venue | APC for this author | Fit | Estimate |
|---|---|---|---|
| **ACM JDIQ** (research paper) | **$0** under ACM Open via UC | Strong. "Provenance, lineage and trust" is named in scope; corporate data governance is a listed topic. | 45–60% |
| DOLAP at EDBT/ICDT 2027 (CEUR) | $0 | Good. Data quality and graph data in scope. Workshop register suits the structural-characterization material. | 60–70% |
| DEEM at SIGMOD 2027 | $0 | Moderate. Better for method-plus-ML framing than for a pure negative result. | 55–65% |
| Data & Knowledge Engineering (Elsevier) | $0 (subscription; optional Gold OA $2,850) | Strong topical fit. Longer decision cycle. | 30–45% |
| Knowledge and Information Systems (Springer) | $0 (subscription) | Moderate. | 25–40% |
| VLDB / SIGMOD / ICDE / EDBT main track | n/a | Not a candidate. | < 5% |

Dead as before. PLOS ONE ($1,805–$3,000), PeerJ CS ($1,695), IEEE Access
($2,045), Frontiers in Big Data ($1,650+), Applied Network Science (€1,790),
MDPI. ACM TODS is now open access on the same terms as JDIQ, so it is free under
ACM Open too, but the topical fit is worse.

## Recommended action

1. **Primary: JDIQ, research paper, corresponding author affiliation University
   of the Cumberlands.** Reformat to `acmsmall`, prepare the double-anonymous
   PDF, write a JDIQ cover letter. The three existing cover letters
   (`paper/cover_letter_dke.md`, `_kais.md`, `_plos_one.md`) target the wrong
   venues and none should be submitted with a JDIQ package.
2. **Verify ACM Open eligibility on the day of submission** against the live
   participant list, and confirm with the UC library that the agreement covers
   doctoral students as corresponding authors.
3. **Fallback: DOLAP 2027** if JDIQ rejects. The deadline is likely late 2026,
   so it can run behind a JDIQ submission rather than instead of one.
4. Post the reframed preprint to arXiv regardless of JDIQ timing, so it is
   citable before the defense. ACM policy permits arXiv deposit.

## What submission still requires

- Reformatted manuscript in the ACM template, anonymous version (`acmsmall`)
- JDIQ cover letter (not yet written)
- Suggested reviewers, 3–5 names (`paper/suggested_reviewers.md` is a start)
- ORCID 0009-0003-1036-9477 (linked)
- Data-availability statement, Zenodo DOI 10.5281/zenodo.20209148
- Research ethics declaration (no human subjects) and conflict-of-interest
  declaration (none)
- Generative-AI declaration consistent with the work actually performed

## Sources

- JDIQ author guidelines  https://dl.acm.org/journal/jdiq/author-guidelines
- JDIQ call for papers, article types and page limits
  https://jdiq.acm.org/call-for-papers.cfm
- ACM Open participant list  https://libraries.acm.org/acmopen/open-participants
