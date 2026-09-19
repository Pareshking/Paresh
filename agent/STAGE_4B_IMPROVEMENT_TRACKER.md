# Stage-4B Improvement Loop Tracker

**Status:** ACTIVE — fail-closed improvement loop  
**Scope:** Stage-4B adaptive research / provenance / adversarial publication gate  
**Source:** Report 1 + Report 1b + Report 2 supplied on 2026-09-19  
**Current execution branch:** `agent/stage4b-second-archetype-clean`  
**Current PR:** #15

## Operating rule

Each improvement follows:

1. Inspect current implementation.
2. Write/confirm the change boundary.
3. Implement the smallest canonical change.
4. Add a regression test that exercises the executable path.
5. Run focused tests.
6. Run full regression + compile.
7. Run real SANSERA and ANANDRATHI acceptance executions.
8. Run adversarial council.
9. Repair findings.
10. Re-run all affected gates.
11. Record VERIFIED / FAILED / NOT VERIFIED.
12. Do not close Stage-4B while any required gate remains open.

## Priority queue

| ID | Improvement | Source | Status |
|---|---|---|---|
| 1 | Require `published_on` for primary/secondary evidence | A1 | **VERIFIED — run #346 (35437730258), all 16 steps green** |
| 2 | Enforce minimum primary-source share in judge | A2 | TODO |
| 3 | Reject malformed string evidence refs explicitly | existing | **DONE — code + regression test** |
| 4 | Validate source URLs / separate gaps from evidence | B3/B6 | TODO |
| 5 | Quality-aware domain coverage | A3 | TODO |
| 6 | Soften judge summary to actual guarantees | A4 | TODO |
| 7 | Contradictions require genuinely disagreeing evidence | B2 | TODO |
| 8 | Detect cross-tier numeric disagreement | B1 | TODO |
| 9 | Entity-relative source tiering | B4 | TODO |
| 10 | Evidence age distribution + rounded score | C1/C2/R5c | TODO |
| 11 | Claim-type evidence half-life classification | R4 | TODO |
| 12 | Stale evidence cannot sole-cover/carry mechanism/primary share | R5a | TODO |
| 13 | Joint tier + recency ranking, never recency-first | R3/R5b | TODO |
| 14 | Explicit last-disclosed/stale finding | R5c/R1 | TODO |
| 15 | Fix ANANDRATHI refs[16] only through provenance-safe repair | E1/E2 | **DONE — absorbed into 16** |
| 16 | Claim-keyed evidence refs; prohibit positional refs | E3 | **DONE — ANANDRATHI converted** |
| 17 | Executable test per archetype: packet + execute_research | E4 | **DONE — ANANDRATHI test added** |
| 18 | Detect evidence cited by no causal/contradiction finding | E5 | **DONE — ANANDRATHI execution test enforces zero orphans** |
| 19 | Reject/downgrade unstable sources | F1/F2/B3 | TODO |
| 20 | Evidence-window freshness: max(published_on) vs snapshot.as_of | F4 | TODO |
| 21 | Mark absence-based support explicitly | F6 | TODO |
| 22 | Apply genuine-contradiction standard retroactively to SANSERA | G1/B2 | TODO |
| 23 | Require and test explicit domain exclusions for every archetype | G2 | **PARTIAL — ANANDRATHI plan + test already present; framework enforcement TODO** |
| 24 | Make `information_cutoff` required (no `date.today()` default) | Report 0 S3 | **VERIFIED — run #346 (35437730258)** |

## Immediate execution result

### Loop 0 — known ANANDRATHI breakage

**Observed:** `refs[16]` on a 16-element evidence tuple.

**Root-cause decision:** do not patch 16 → 15. Positional provenance is the defect class.

**Repair:** `anandrathi_research_packet.py` now uses:

```python
refs = {e.claim: evidence_ref(e) for e in evidence}
```

and a claim lookup helper that fails explicitly when a claim is absent.

All causal/contradiction provenance is now bound to explicit claim text rather than tuple position.

### Regression hardening

Added:

- `tests/test_agent_anandrathi_execution.py::test_anandrathi_packet_is_executable`
- `tests/test_agent_anandrathi_execution.py::test_anandrathi_packet_uses_every_evidence_record`
- `tests/test_agent_anandrathi_execution.py::test_anandrathi_plan_exclusions_are_explicit_and_material`
- malformed `str` evidence-ref regression in `tests/test_agent_research_execution.py`

This specifically addresses the failure mode where the declarative plan tests pass while the executable research packet is broken.

### Loop 0b — INDUSTRY declared material with zero evidence (found after Loop 0)

**Observed:** the `refs[16]` crash (Loop 0) fired during packet *construction*,
before `execute_research` could reach `validate_research_coverage`. Once Loop 0
was fixed, the packet still failed:

    ValueError: research coverage missing domains: industry

`anandrathi_plan()` had declared `ResearchDomain.INDUSTRY` material since the
packet was first ported (`bf4951d`), and the 16-item evidence packet has never
carried a single industry-tagged record. Two independent defects, serialized by
CI's fail-fast step ordering (see Report 0, S6) — one CI cycle each.

**Root-cause decision:** do not source industry evidence to satisfy the flag.
None of the four hypotheses asks an industry-level question (AUM durability,
RM productivity vs employee cost, regulatory/AMC economics, diversification),
and all seven economic drivers are company-level. The domain was declared
reflexively — the checklist behaviour the adaptive architecture (Section 6 of
the handover) exists to prevent. Two rejected alternatives: a `research-window:`
absence record (satisfies coverage while being the exact presence-only
anti-pattern flagged in A3/F5), and fabricating an unverifiable industry
citation.

**Repair:** removed `ResearchDomain.INDUSTRY` from `anandrathi_plan()`
`material_domains`. Plan domains now equal evidence domains exactly (6/6,
zero gap). Fixed in `7379fe5`.

**Local verification (commit 7379fe5):**
- focused tests: 14 passed
- `compileall`: OK
- full regression: 1150 passed in 92.19s
- SANSERA live: `STAGE4B_SANSERA_EXECUTION=PASS` (unchanged — no regression)
- ANANDRATHI live: `STAGE4B_ANANDRATHI_EXECUTION=PASS`
  (rank 7, score 2.192162, evidence 16, primary 7, domains 6, causal 4,
  contradictions 4)
- both dossier artifacts written:
  `stage4b_anandrathi_dossier.md` (14810 bytes),
  `stage4b_sansera_dossier.md` (21784 bytes)

**CI:** pushed to `agent/stage4b-second-archetype-clean` (PR #15). Runs #343
and #344 (pre-fix commits `b21a698`, `0a2bf88`) both **FAILED** on this exact
`industry` coverage error, confirming the local reproduction. Run #345
(`35436832463`, commit `7379fe5`) dispatched — awaiting result. Do not mark
this loop VERIFIED until #345 is inspected.

**If industry context is wanted later:** it needs its own hypothesis and
sourced evidence (e.g. share of industry flows sharpening the AUM-durability
hypothesis), not a bare domain flag.

## Next loop order

1. Run focused ANANDRATHI packet/execution tests.
2. Run full regression and compile.
3. Run CI Stage-2/3/SANSERA/ANANDRATHI.
4. If green, begin evidence-integrity gate improvements:
   - #1 published date requirement
   - #19 unstable source classification
   - #20 evidence-window freshness
   - #4 gaps/source validation
5. Then strengthen adversarial semantics:
   - #7 genuine contradictions
   - #8 numeric disagreement
   - #22 retroactive SANSERA contradiction audit
6. Then stale-evidence model:
   - #11 → #12 → #13 → #14
7. Finish judge/coverage controls:
   - #2, #5, #6, #9, #10, #21, #23
8. Full adversarial council and WELCORP adaptive rerun.
9. Final Stage-4B gate decision.

## Gate status

- SANSERA Stage-4B execution: **VERIFIED previously** (unaffected by Loop 0/0b; re-confirmed locally at 7379fe5)
- ANANDRATHI execution before repair: **FAILED** (refs[16] crash, then industry-coverage error)
- ANANDRATHI provenance repair (Loop 0, claim-keyed refs): **DONE — code + regression test**
- ANANDRATHI domain-coverage repair (Loop 0b, drop unused INDUSTRY domain): **IMPLEMENTED locally — awaiting CI run #345**
- Executable-path regression coverage: **DONE — 14 focused tests pass, including both live runners**
- Items 1, 24: **VERIFIED** (run #346, 35437730258) -- see above
- Full improvement suite (items 2, 4-14, 19-23): **NOT STARTED**
- SANSERA retroactive contradiction audit (#22): **NOT VERIFIED**
- WELCORP adaptive rerun: **NOT VERIFIED**
- Full adversarial council (Section 33): **NOT VERIFIED**
- Stage-4B closure: **NOT READY**


## Loop 1 — item 1 (published_on requirement) + item 24 (required cutoff)

**CI precondition met:** run #345 (35436832463, commit 7379fe5) on PR #15
completed with all 16 steps green, including ANANDRATHI execution, both
dossiers retained, Streamlit smoke, and artifact upload. Per Section 20/37 of
the handover, item 1 work started only after this.

**Item 24 (Report 0 S3):** `validate_evidence_set`'s `information_cutoff`
parameter is now required (no `date.today()` default). All three production
call sites already passed it explicitly; one test call site did not and was
fixed to pass `information_cutoff` explicitly.

**Item 1 (A1):** `validate_evidence_set` now rejects any non-DERIVED evidence
item with `published_on is None`, unless `undated_primary_source=True` is set.

Enabling this against the real packets surfaced exactly 4 items (found via
direct execution before enabling the check network-wide, not by trial and
error against CI):

| Entity | Source | Verified via live fetch (2026-09-19) |
|---|---|---|
| SANSERA | bharatforge.com/AR2026/operational-highlights.html | states "Annual Report FY 2025-26", no publication/approval/filing date anywhere |
| SANSERA | acma.in/about-us.php | static page, no date anywhere |
| SANSERA | sansera.in .../Annual-Report-2024-25.pdf | only circumstantial signal (upload path + PDF XMP metadata ~2025-08); no disclosed filing date extracted |
| ANANDRATHI | anandrathiwealth.in (homepage) | shows "(As of 30 June 2026)" against the cited figures -- a data date, not a publication date |

**Decision: do not fabricate a date for any of the four.** Two are confirmed
dateless by direct fetch; the homepage's only date is a data-as-of date
already correctly captured in `event_date`; the PDF's metadata is
circumstantial, not an authoritative disclosure date.

**Repair:** added `Evidence.undated_primary_source: bool = False` -- an
explicit, narrow, fail-closed-by-default escape. `__post_init__` requires
`event_date` to be set whenever it is used, so an undated source still
carries a real temporal anchor. Set `True` on exactly the four items above,
each with an inline comment recording what was verified and when. No other
evidence item in either packet uses it.

**Rejected alternatives:**
- Guessing a plausible date -- fabrication.
- Weakening the validator (e.g. exempting PRIMARY tier, or making the check
  a warning) -- defeats the purpose of item 1; matches the "superficial test
  to make a gate green" anti-pattern the operating standard forbids.
- Silently dropping the four items -- one (the ANANDRATHI homepage claim) is
  cited by a real causal finding (confirmed by searching for `ref("...")`,
  not the old `refs["...")` pattern, after the claim-keyed refactor); removing
  it would have re-broken provenance for that finding. Caught before
  executing this by re-checking the citation with the correct pattern.

**Also closed in this loop:** no test in the suite called `sansera_packet()`
at all -- the exact class of gap item 17 exists to close, just not applied
symmetrically to SANSERA. Added `tests/test_agent_sansera_execution.py`
mirroring the ANANDRATHI executable test.

**New finding, not yet actioned (documented, not force-fixed):** applying the
ANANDRATHI executable test's `all_refs <= used_refs` rule to SANSERA shows 17
of 33 evidence items (52%) are not cited by any causal finding or
contradiction. This is NOT treated as 17 new bugs: SANSERA's plan declares 17
material domains (vs. ANANDRATHI's 6), and `validate_research_coverage` only
requires a domain to have evidence, not evidence tied to a specific finding.
Forcing every item into a finding's refs to satisfy a stricter test would be
exactly the "force evidence into a finding just to pass a test" anti-pattern
Section 11 of the handover warns against. Left as a measured, documented
data point for item 18 (E5), which already covers this and is still TODO --
the real fix needs the supporting-vs-background-evidence distinction Section
11 calls for, not a blanket assertion.

**Local verification (before push):**
- compileall: OK
- `tests/test_agent_sansera_execution.py`: 1 passed
- `tests/test_agent_anandrathi_execution.py` + `test_agent_anandrathi_adaptive.py`: 6 passed
- full regression: 1150 passed, 1 deselected (`test_build_info.py::test_revision_matches_git`,
  confirmed via `git stash` to fail identically with or without this change --
  a detached-HEAD artifact of this session's git worktree, not a regression)
- SANSERA live: `STAGE4B_SANSERA_EXECUTION=PASS` (unchanged facts: rank 8, evidence 33, causal 5, contradictions 4)
- ANANDRATHI live: `STAGE4B_ANANDRATHI_EXECUTION=PASS` (unchanged facts: rank 7, evidence 16, causal 4, contradictions 4)
- both dossier artifacts written

**CI: VERIFIED.** Run #346 (35437730258, job 105883144200, commit c9db923)
on PR #15 -- all 16 gate steps green: regression, compile, Stage-2, Stage-3,
SANSERA execution, ANANDRATHI execution, both dossiers retained, Streamlit
HTML cleanup + smoke, final artifact upload. Items 1 and 24 are CI-verified,
not only locally verified.

## Rule against false closure

A green unit-test suite alone does not close Stage-4B. The real acceptance runners must execute successfully, retained dossiers must exist, and the adversarial/research-quality improvements must be re-run after repair.
