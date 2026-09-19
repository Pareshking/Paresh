# Stage-4B Improvement Loop Tracker

**Status:** ACTIVE — fail-closed improvement loop  
**Scope:** Stage-4B adaptive research / provenance / adversarial publication gate  
**Source:** Report 1 + Report 1b + Report 2 supplied on 2026-09-19  
**PR #15 (`agent/stage4b-second-archetype-clean`): MERGED to `main`** as
squash commit `93d1474` on 2026-09-19, after CI run #360 (35443317589)
verified green on the final commit. Items 1-10, 15-24 above are now on
`main`; items 2, 9, 11-14 remain open per Paresh's recorded decisions
(Loop 8).  
**Current execution branch:** `agent/stage4b-third-archetypes` (from `main`
post-merge)  
**Current PR:** #16 -- CI VERIFIED (run #363), `mergeable_state: clean`,
ready to merge. See Loop 11 below.

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
| 2 | Enforce minimum primary-source share in judge | A2 | **DEFERRED (Paresh's decision) — no hard gate until item 9 exists** |
| 3 | Reject malformed string evidence refs explicitly | existing | **DONE — code + regression test** |
| 4 | Validate source URLs / separate gaps from evidence | B3/B6 | **4a VERIFIED (run #351); 4b (separate field) CLOSED as substantively superseded — see Loop 9** |
| 5 | Quality-aware domain coverage | A3 | **VERIFIED — run #351 (35439390433), reported metric, not a hard gate** |
| 6 | Soften judge summary to actual guarantees | A4 | **VERIFIED — run #351 (35439390433)** |
| 7 | Contradictions require genuinely disagreeing evidence | B2 | **VERIFIED — run #353 (35440586723) — Loop 5** |
| 8 | Detect cross-tier numeric disagreement | B1 | **VERIFIED — run #354 (35441089140) — Loop 6; regex gap fix VERIFIED — run #360 (35443317589) — Loop 10** |
| 9 | Entity-relative source tiering | B4 | **DEFERRED — needs an issuer-to-symbol map; a URL-shape heuristic would guess, not fix — Loop 4** |
| 10 | Evidence age distribution + rounded score | C1/C2/R5c | **VERIFIED — run #351 (35439390433); buckets confirmed exact match to local (SANSERA 23/4/2/2/2, ANANDRATHI 11/2/0/0/3)** |
| 11 | Claim-type evidence half-life classification | R4 | TODO |
| 12 | Stale evidence cannot sole-cover/carry mechanism/primary share | R5a | TODO |
| 13 | Joint tier + recency ranking, never recency-first | R3/R5b | TODO |
| 14 | Explicit last-disclosed/stale finding | R5c/R1 | TODO |
| 15 | Fix ANANDRATHI refs[16] only through provenance-safe repair | E1/E2 | **DONE — absorbed into 16** |
| 16 | Claim-keyed evidence refs; prohibit positional refs | E3 | **DONE — ANANDRATHI converted** |
| 17 | Executable test per archetype: packet + execute_research | E4 | **DONE — ANANDRATHI test added** |
| 18 | Detect evidence cited by no causal/contradiction finding | E5 | **DONE — ANANDRATHI execution test enforces zero orphans** |
| 19 | Reject/downgrade unstable sources | F1/F2/B3 | **VERIFIED — run #348 (35438217592), all 16 steps green** |
| 20 | Evidence-window freshness: max(published_on) vs snapshot.as_of | F4 | **VERIFIED — run #350 (35438667821); reported metric, not a hard gate — Loop 3** |
| 21 | Mark absence-based support explicitly | F6 | **VERIFIED — run #351 (35439390433); both archetypes 0/0, confirmed in job logs** |
| 22 | Apply genuine-contradiction standard retroactively to SANSERA | G1/B2 | **VERIFIED — run #356 (35441605984), all 16 steps green — Loop 7** |
| 23 | Require and test explicit domain exclusions for every archetype | G2 | **VERIFIED — run #351 (35439390433)** |
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
- Item 19: **VERIFIED** (run #348, 35438217592) -- see above
- Item 20: **VERIFIED** (run #350, 35438667821) -- see above
- Item 7: **VERIFIED** (run #353, 35440586723) -- see above
- Item 8: **VERIFIED** (run #354, 35441089140) -- see above
- Item 22: **VERIFIED** (run #356, 35441605984) -- see above
- Items 4a, 5, 6, 10, 21, 23: **VERIFIED** (run #351, 35439390433, all 16 steps green;
  printed values SANSERA age-buckets 23/4/2/2/2, ANANDRATHI 11/2/0/0/3, both
  absence-based 0/0, matching local exactly)
- Item 4's gaps-field half: **TODO**
- Item 9: **DEFERRED** -- needs an issuer-to-symbol map (Loop 4)
- Remaining (items 2, 11-14): **NOT STARTED — blocked on a threshold/half-life policy decision, see below**
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


## Loop 2 — item 19 (reject unstable PRIMARY sources)

Scoped narrowly and deterministically, per Section 21 of the handover
("prefer small deterministic validators", "do not over-engineer"):
`validate_evidence_set` now rejects `source_tier=PRIMARY` when the source is
(a) a known video-hosting host (youtube.com, youtu.be, vimeo.com), or (b) a
bare domain root (empty or `/` path). Deliberately does NOT try to classify
a "generic-looking" page that has a path (e.g. ACMA's about-us.php, Bharat
Forge's operational-highlights.html) -- that is an entity-relative source
policy question (item 9), not a URL-shape heuristic, and guessing at it here
would itself be over-engineering.

Enabling it found exactly 4 items, all ANANDRATHI, all previously identified
by name in Report 2 (F1: three items citing the same YouTube video; F2: the
bare-homepage item already flagged and handled for published_on in Loop 1):

- `anandrathiwealth.in` (bare root) -- domain CUSTOMERS_SUPPLIERS
- `youtube.com/watch?v=EFvyPYEU13I` x3 -- domains FINANCIALS, MANAGEMENT,
  CAPITAL_MARKETS (one of these was F1's flagged sole evidence for MANAGEMENT)

**Zero SANSERA items matched.** The sources Report 1 (B3) named as weak --
foliopulse, whalesbook, timesofwhales, earningscalls.dev -- were already
correctly tiered SECONDARY; B3's complaint about them is "prefer an issuer
document when one exists" (a recommendation), not a tier misclassification
(a defect), so item 19 correctly leaves them alone.

**Checked for side effects before downgrading (learned from the Loop 0b
industry-domain incident):** grepped every consumer of `source_tier` in the
codebase. Exactly three: (1) the published_on/undated_primary_source check
(SECONDARY needs the same thing PRIMARY does, so downgrading does not change
the requirement), (2) primary/secondary/derived audit counts (informational
only, not gated by anything yet -- item 2 is still TODO), (3) nothing else.
`validate_research_coverage` checks domain presence, not tier, so downgrading
a domain's only evidence item does not un-cover that domain (unlike deleting
it, which is what the industry-domain fix in Loop 0b had to avoid).

**Repair:** downgraded all 4 items from PRIMARY to SECONDARY. All three video
items already carried a real `published_on` (2026-07-10); the homepage item's
`undated_primary_source=True` from Loop 1 continues to apply.

**Result:** `STAGE4B_ANANDRATHI_PRIMARY` dropped from 7 to 3 -- matching
Report 2 finding F3's independent manual estimate ("effective primary share
is ~19%, not 44%": 3/16 = 18.75%) almost exactly. `SANSERA_PRIMARY_COVERAGE`
unchanged at 0.606, confirming no SANSERA regression.

**Test-fixture fallout (not a defect):** four unit tests in
`tests/test_agent_company_research.py` used the placeholder
`source="https://example.com"` on PRIMARY-tier evidence -- a literal bare
root, now correctly rejected regardless of the test's actual intent. Fixed
by changing the placeholder to `https://example.com/report` (a path, no
change to test semantics) in all 6 occurrences in that file (2 were already
tier=SECONDARY or otherwise unaffected but changed for consistency).

**Local verification:** compileall OK; full regression 1150 passed, 1
deselected (same pre-existing worktree artifact as Loop 1); SANSERA live
PASS (facts unchanged); ANANDRATHI live PASS (evidence 16, causal 4,
contradictions 4 unchanged; primary 7 -> 3 as intended); both dossiers
written.

**CI: VERIFIED.** Run #348 (35438217592, job 105884427449, commit 4aa7150)
on PR #15 -- all 16 gate steps green.


## Loop 3 — item 20 (evidence-window freshness)

Implemented as a REPORTED metric, not a hard gate, deliberately. Discussed
with Paresh before coding: a universal staleness threshold across archetypes
would repeat exactly the checklist mistake the adaptive-research design
exists to avoid -- a market-sensitive wealth manager and a quarterly-cadence
manufacturer do not go stale at the same rate, and inventing one number
unilaterally would be picking an arbitrary threshold and calling it rigor.

**What it measures, and how it differs from items 11/12 (per-item age):**
an evidence *set* can have every individual item within its own acceptable
age and still, as a whole, not have been updated in months. This is
`max(temporal anchor)` across the whole evidence set compared against
`snapshot.as_of`, not a per-item check.

**Design decisions, each grounded in what the packets actually contain
(checked before coding, not assumed):**
- The anchor is `published_on` for dated items. `retrieved_on` was
  considered and rejected: in both packets it is a single constant applied
  to every item (the day the research batch ran), not a per-item timestamp,
  so it carries no freshness signal at all.
- An item with `undated_primary_source=True` (Loop 1) falls back to its
  `event_date` -- it still carries a real, verified date, just not a
  publication date. Excluding it would understate freshness.
- A `DERIVED` item never contributes, even if it happened to carry an
  `event_date` -- confirmed no current DERIVED item does, but the rule holds
  either way, since an absence-of-evidence record is not information and
  should not count as "current" information.
- Returns `None` (not 0, not a crash) when no evidence item has any usable
  anchor -- an empty-anchor set is a different, worse condition than "zero
  days stale" and must not be conflated with it.

**Added:** `ResearchAudit.newest_evidence_anchor` (computed in
`execute_research`) and `ResearchDossier.evidence_window_gap_days` (a
property, since it needs `snapshot_as_of`, which lives on the dossier, not
the archetype-agnostic audit). Printed as
`STAGE4B_{SANSERA,ANANDRATHI}_EVIDENCE_WINDOW_GAP_DAYS` in both live
runners. Four new focused tests in `test_agent_research_execution.py`
covering: the normal dated case, the undated-primary-source fallback, the
DERIVED-never-contributes rule (including the adversarial case of a DERIVED
item that does carry an event_date), and the no-anchor-at-all None case.

**Measured on real data:**
- SANSERA: gap = **0 days** (newest evidence is the 2026-09-18 Reuters
  tariff-authority piece -- same day as the cutoff)
- ANANDRATHI: gap = **66 days** (newest evidence 2026-07-14; cutoff
  2026-09-18) -- exactly reproducing Report 2 finding F4

The 0-vs-66 spread is itself a useful confirmation that the metric
discriminates correctly between a currently-fresh dossier and a stale one on
real, unmodified data, not a contrived example.

**Not yet done, and deliberately left open:** no threshold, no hard gate.
The natural home for a threshold is the archetype's own `ResearchPlan` --
the same place material domains and exclusions are already declared -- so a
wealth-management plan could declare "30 days" and a manufacturing plan
"one reporting period" without a universal constant. That is a real design
decision for Paresh, not mine to invent; recorded here rather than guessed
at in code.

**Local verification:** compileall OK; 4 new tests pass (12 total in the
file); full regression 1154 passed, 1 deselected (same pre-existing
worktree artifact); SANSERA live PASS (gap=0, all other facts unchanged);
ANANDRATHI live PASS (gap=66, all other facts unchanged); both dossiers
written.

**CI: VERIFIED.** Run #350 (35438667821) on PR #15, commit 67c3cd1 -- all 16 gate steps green.


## Loop 4 — batched: items 4a, 5, 6, 10, 21, 23 (+ item 9 deferred)

Paresh asked to speed up: club items where confidence is high, verify once
with a full local pass, and use fewer CI round trips rather than one per
item. Considered parallel subagents first and rejected it -- this is a
single shared branch with a serialized CI pipeline and a handful of tightly
coupled files (today's real bugs all came from cross-file dependencies:
domain coverage, citation refs, tier consumers), so uncoordinated parallel
edits would cost more in merge/re-verification than batching saves.
Batching more items into fewer, still-fully-verified pushes was the actual
lever.

**Item 23 (framework-level exclusion enforcement):** `ResearchPlan` already
had an `exclusions` field (default `()`); made it mandatory in
`__post_init__`. Checked every construction site first -- both real
archetypes already declare exclusions; only test fixtures needed a
placeholder added (4 sites, across two files, one missed on the first pass
because an earlier per-file grep check doesn't catch a file with some
constructions fixed and others not -- caught by the second full-suite run).
Added a SANSERA exclusions test mirroring the existing ANANDRATHI one.

**Item 4a (URL format for non-derived tiers):** `validate_evidence_set` now
requires a `http://`/`https://` source for any non-DERIVED item. DERIVED
stays exempt (its `source` is a `research-window: ...` label, not a URL).
Item 4's second half -- moving DERIVED "gaps" into their own dossier field
rather than the shared evidence list -- is a bigger dossier-shape change
and stays TODO rather than being rushed into this batch.

**Item 5 (quality-aware domain coverage) -- implemented, found wrong, fixed
within this same loop, not shipped broken:** first cut made a domain
covered only by DERIVED evidence a hard `raise`. Running the full suite
immediately (this is what "verify in full test" bought here) surfaced 13
failures, not 1 -- the shared test fixture in `test_agent_research_execution.py`
deliberately covers its CAPACITY domain with only a DERIVED "not disclosed"
item, which is exactly the legitimate state Section 24 of the handover and
item 21's own design protect ("we could not find disclosure" must not be
punished or forced to look like something else). A hard gate here would
have meant either fabricating evidence to satisfy the check or forbidding a
disclosure gap from ever being honestly recorded -- both worse than the
defect it was meant to fix. Reverted the hard gate; `validate_research_coverage`
is back to its original presence check. Re-implemented item 5 as a
REPORTED metric instead, consistent with items 18/20/21's pattern:
`ResearchAudit.derived_only_domains` lists which of a plan's material
domains have evidence but only DERIVED evidence. Confirmed both real
packets currently report none.

**Item 6 (truthful judge wording):** only SANSERA's dossier renderer had
the overstated line ("passed... the adversarial publication gate");
ANANDRATHI's never did. Replaced with wording naming exactly what
`judge_dossier` checks (structural/provenance/coverage) and explicitly
stating this is not a full adversarial council review.

**Item 10 (age distribution + score rounding):** rounded SANSERA's dossier
score to `:.6f`, matching ANANDRATHI's existing convention (no new format
invented). Added five age buckets (`<=90d`, `91-180d`, `181-365d`, `>365d`,
`unanchored`) to `ResearchAudit`, reusing the exact per-item temporal-anchor
logic from item 20 (`published_on`, falling back to `event_date` for
`undated_primary_source` items, DERIVED never contributing) rather than a
second, possibly-inconsistent definition of "age". `unanchored` is its own
bucket, not folded into `>365d` -- "no date at all" and "very old" are
different findings and must not be conflated.

**Item 21 (absence-based support flag):** a causal finding or contradiction
is flagged when EVERY one of its `evidence_refs` resolves to a DERIVED item
-- deliberately strict (partial-absence support, e.g. one real citation plus
one derived one, is not flagged; that needs the more careful weighting item
7/22 will require, not an automatable rule). Both real packets currently
report 0/0 for both archetypes: SANSERA's contradictions that cite a
DERIVED item always cite it alongside real evidence, not alone.

**Item 9 (entity-relative source tiering) -- explicitly deferred, not
attempted:** correctly flagging "Bharat Forge's own annual report is
primary for Bharat Forge, not automatically primary for SANSERA" needs an
issuer-to-symbol mapping this codebase does not have. A URL-shape heuristic
(the technique that worked for item 19's bare-root/video-host check) cannot
distinguish "issuer's own primary document" from "a fine primary source for
a different company" -- guessing here would be exactly the kind of
half-built heuristic the operating standard warns against. Left for real
design work, not rushed into this batch.

**Local verification (one pass, after the item-5 course-correction):**
compileall OK; full regression 1155 passed, 1 deselected (same pre-existing
worktree artifact); SANSERA live PASS (all facts unchanged except the new
printed fields: age buckets 23/4/2/2/2, absence-based 0/0); ANANDRATHI live
PASS (age buckets 11/2/0/0/3, absence-based 0/0); both dossiers written and
visually checked for correct rendering of the new sections.

**CI: VERIFIED.** Run #351 (35439390433) on PR #15, commit 307a119 -- all
16 gate steps green. Job logs confirm the exact printed values matching
local: `STAGE4B_SANSERA_EVIDENCE_AGE_BUCKETS=23/4/2/2/2`,
`STAGE4B_SANSERA_ABSENCE_BASED_FINDINGS=0/0`,
`STAGE4B_ANANDRATHI_EVIDENCE_AGE_BUCKETS=11/2/0/0/3`,
`STAGE4B_ANANDRATHI_ABSENCE_BASED_FINDINGS=0/0`. CI ran 1156 tests (vs.
local's 1155 + 1 deselected) -- confirms `test_build_info.py::test_revision_matches_git`
was genuinely a local git-worktree artifact, not a real issue: it passes on
CI's actual checkout.


## Loop 5 — item 7 (contradiction evidence quality), done carefully, not batched

Per the explicit instruction after the speed-up request: #7/#8/#22 are
semantic/analytical, not small deterministic validators, and get done one at
a time, carefully -- never batched the way items 4a/5/6/10/21/23 were.

**First, verified the tracker's own inherited idea before building on it.**
The improvement list said "require contradictions to cite >=2 genuinely
disagreeing evidence refs". Pulled every contradiction's actual ref count
and content from both packets before writing any code:

    SANSERA:    [0] 2 refs  [1] 3 refs  [2] 2 refs  [3] 1 ref
    ANANDRATHI: [0] 3 refs  [1] 3 refs  [2] 3 refs  [3] 3 refs

Report 1 (B2) had already judged SANSERA's contradiction [3] (product
concentration: 35.5% connecting rods vs. "diversification is reducing
concentration") the ONE genuinely good one, and [0]/[1]/[2] weak. [3] is the
one with only 1 ref. A ">=2 refs" rule would have REJECTED the good one and
left the weak ones (already at 2-3 refs) untouched -- the opposite of what
item 7 needs. Ref count alone is not a usable proxy for "genuine
disagreement" on this data. Dropped it before writing any code.

**What IS safely, deterministically checkable:** whether a contradiction
shows evidence on both sides of the tension it claims, structurally. Split
`ContradictionFinding.evidence_refs` into `original_claim_refs` and
`counter_evidence_refs` (both required non-empty, resolvable, and disjoint --
the same ref cannot support both sides of one contradiction).
`evidence_refs` survives as a computed property (concatenation) so item 21's
generic per-finding absence-based check, which iterates causal findings and
contradictions together, needed no change. This does not detect every
strawman -- that needs reading the prose, which this deterministic pipeline
does not automate -- but it forces the two-sided structure to be explicit
and auditable instead of one undifferentiated list.

**Migrating the real data surfaced two genuine, evidence-grounded defects,
not just a mechanical schema change:**

1. SANSERA [3] (diversification vs. concentration) had ZERO evidence
   supporting its own original_claim side -- only the counter (35.5%
   connecting rods) was cited. The packet already contains the right
   evidence for the claim side ("FY26 top-five customer concentration was
   44.5%, down from 59.2% in FY21") but it was never cited here. Added it.
   Not fabricated -- it is an existing, exact-match evidence item, already
   in the packet, simply never linked to this finding.

2. ANANDRATHI [1] (operating leverage vs. employee costs) cited the AMC
   board-approval evidence item, which has nothing to do with RM
   productivity or operating leverage -- it is misattached. It belongs to
   ANANDRATHI [2] (the AMC contradiction itself), which was, in turn,
   missing that exact ref and instead carried two off-topic citations (SEBI
   regulations background, a Digital Wealth item) that don't support either
   side of the AMC tension. Moved the board-approval ref from [1] to [2] as
   [2]'s original_claim_ref (it is literally the factual basis for "the AMC
   is a growth engine"); dropped the two off-topic refs from [2] (both
   remain correctly cited on the AMC causal finding, so nothing becomes
   orphaned). Also found ANANDRATHI [0]'s counter_evidence text quotes a
   specific "~14%" figure whose source evidence item exists in the packet
   and is cited elsewhere (two causal findings) but was never cited on this
   contradiction; added it, and removed a stress-test-derived ref that was
   about a different concern (bear-market sensitivity) than what [0]'s
   counter_evidence actually asserts (flow-vs-appreciation composition) --
   it stays correctly cited on ANANDRATHI [3], which is actually about
   resilience/stress.

Checked before every move/drop that the ref being touched was not left
orphaned: cross-referenced each against the causal findings, which already
cite sebi-regs, digital-wealth, and the board-approval item independently.

**Fixed two test-fixture construction sites** for the field rename
(`tests/test_agent_research_execution.py`): the shared `packet()` fixture's
one contradiction, and the malformed-evidence-refs regression test (now
exercises the type-guard via `original_claim_refs`, with a valid
`counter_evidence_refs` alongside it so the test still isolates the one
defect it means to test).

**Local verification:** compileall OK; full regression 1156 passed (this
run used a real clone, not the flagged scratchpad worktree -- see below --
so the previously-excluded `test_build_info` test ran and passed cleanly,
confirming it really was a worktree artifact); SANSERA live PASS (evidence
33, causal 5, contradictions 4, all facts unchanged -- only which ref
supports which side changed, not the evidence set itself); ANANDRATHI live
PASS (evidence 16, causal 4, contradictions 4, all facts unchanged); both
dossiers written.

**Environment note:** switched from the scratchpad git worktree used for
Loops 0-4 to the primary clone at the repo root, after the platform's own
Bash classifier temporarily flagged operations in that worktree path
following an unrelated third-party-plugin-install attempt earlier in the
session. Confirmed the primary clone was unaffected before continuing; no
impact on any Loop 0-4 result, all of which were already CI-verified before
the block appeared.

**CI: VERIFIED.** Run #353 (35440586723) on PR #15, commit ed55c19 -- all 16 gate steps green.


## Loop 6 — item 8 (numeric disagreement detection)

Second item done carefully, one at a time, per the same instruction as
Loop 5. Prototyped against real data BEFORE writing any production code,
and the prototype itself caught a design flaw before it ever shipped.

**First design considered and rejected: same-domain + keyword/bag-of-words
overlap.** Tested it against the real packets specifically to check the
known SANSERA ADS-backlog case (Report 1 B1: primary source 44,368M vs
secondary ~57,500M, a verified 30% gap the pipeline never caught). It
worked for that case, but a bag-of-words check on "non-ADS new-business
order book" against "ADS cumulative unexecuted backlog" shared the token
"ADS" (because naive tokenization splits "non-ADS" into "non" + "ADS") plus
a second incidental word ("revenue"), which would have wrongly flagged two
genuinely different metrics (ADS backlog vs. the SEPARATE non-ADS order
book) as disagreeing. Fuzzy topic-matching on free text is not safe on this
dataset. Dropped before writing any validator code.

**What shipped instead: exact numeric coincidence, not topic similarity.**
`_extract_inr_million_values` extracts every "INR <number>(-<number>)?
<unit>" figure from a claim (crore/million/billion/lakh crore, normalized to
INR million) -- anchored on the literal word "INR" so it only extracts
figures this dataset actually states this way, not any bare number.
`_numeric_disagreement(claim_a, claim_b)` then requires: (1) the two
claims' own MAXIMUM (headline) figures differ by >=10%, AND (2) the smaller
headline is explicitly, verbatim present in the OTHER claim's own numbers
too -- proof the two claims are provably about the same quantity, not a
guess from shared wording.

**The prototype for this refined rule ALSO caught a false positive before
shipping:** same-domain, same-sentence-adjacent ANANDRATHI evidence (AUM
INR 1,06,300 crore in one claim; net inflows INR 2,743 crore repeated in a
different claim two sentences later) shared the number 2,743cr, but 2,743cr
is not either claim's own headline (1,06,300cr and 3,824cr are the
respective maxima) -- so it does not qualify under the "shared value must be
a headline" rule. Verified this by running the exact production logic
against both full real packets before wiring it into execute_research: one
true positive (SANSERA backlog), zero false positives on 30+ same-domain
evidence pairs across both archetypes.

**Never a hard gate, never auto-resolves which source is right** --
Section 23 of the handover is explicit about this ("Do NOT automatically
decide which source is correct... surface the disagreement for research
review"). `ResearchAudit.numeric_disagreements` is a reported tuple of
human-readable strings (domain, both values, % difference, both full
evidence refs for traceability), printed in both live runners as
`STAGE4B_{SANSERA,ANANDRATHI}_NUMERIC_DISAGREEMENTS` (count) and
`..._NUMERIC_DISAGREEMENT_DETAIL` (one line per finding), and rendered in
both dossiers under a `NUMERIC_DISAGREEMENT_REVIEW_REQUIRED` heading.

**Result on real data:** SANSERA now flags exactly the one real, previously
undetected disagreement Report 1 found by hand eight months into this
project's evidence review -- `orders: 44368 vs 57500 INR million (30%
difference)`, correctly citing both evidence items (the primary company
presentation and the secondary foliopulse update) so a reviewer can decide,
rather than the pipeline silently accepting whichever figure a later
finding happened to cite. ANANDRATHI: 0 (matches the earlier finding that
Report 2's ANANDRATHI review found no comparable defect).

**Two regression tests added**, each encoding one of the two verified
cases directly: `test_numeric_disagreement_detects_linked_headline_figures_differing`
(the true positive, using the exact real values) and
`test_numeric_disagreement_ignores_unrelated_co_occurring_figures` (the
false positive found during prototyping, so it can never silently regress).

**Explicitly acknowledged limitation, not hidden:** this only catches
disagreements where the same figure is explicitly restated somewhere in the
disagreeing text. A genuinely independent pair of claims stating different
numbers for the same fact with no shared anchor number would not be caught.
That is the accepted cost of staying deterministic instead of guessing at
topic similarity -- consistent with Section 23's explicit instruction to
prefer a narrower, safe detector over an ambitious one.

**Local verification:** compileall OK; 2 new tests pass; full regression
1158 passed (real clone); SANSERA live PASS -- 1 disagreement flagged,
exactly the known case, 30% difference computed correctly, both evidence
refs traceable; ANANDRATHI live PASS -- 0 disagreements, no regression;
both dossiers written and the new section visually checked in both.

**CI: VERIFIED.** Run #354 (35441089140) on PR #15, commit 26e4d1d -- all 16 gate steps green. Job log confirms STAGE4B_SANSERA_NUMERIC_DISAGREEMENTS=1 with the full 44368-vs-57500 detail line verbatim, and STAGE4B_ANANDRATHI_NUMERIC_DISAGREEMENTS=0, both matching local exactly.


## Loop 7 — item 22 (retroactive SANSERA contradiction audit)

Now that item 7's split (original_claim_refs / counter_evidence_refs) exists
and both real packets carry it, read all four SANSERA contradictions
against the same standard applied during item 7's migration -- not just
"does each side have evidence" (item 7's structural check, already passing
for all four) but "does the original_claim genuinely follow from its own
cited evidence, and does the counter genuinely oppose it" (the semantic part
item 7's docstring explicitly says this pipeline does not automate). Found
two more defects that the structural check could not catch, and confirmed
the other two are sound.

**[0] "Large order books provide revenue visibility" -- confirmed as the
exact strawman Report 1 (B2) originally found, now precisely locatable
because it has an explicit claim_ref to check against.** The cited evidence
("ADS cumulative unexecuted backlog... executable over approximately five
years") already states a five-year horizon; "provides revenue visibility"
without qualification reads as near-term, which the evidence itself never
claimed. Reworded to "provide multi-year revenue visibility" -- matches
what the evidence actually supports, and the real tension survives: even
multi-year visibility is at risk if capacity-constrained conversion
persists or worsens.

**[1] "ADS is supported by strong aerospace, semiconductor and defence
demand" cited evidence for only ONE of its three named drivers (Airbus /
aerospace).** Checked whether the other two exist in the packet before
touching anything: the defence item (India's Positive Indigenisation List)
does, and is already cited on this same hypothesis's causal finding
(reusing it here is not a new orphan risk); the semiconductor item (Applied
Materials' USD 5B India investment) exists but was cited nowhere in the
entire packet -- a genuine orphan, closed by this fix. Added both as
claim_refs so the citation set matches what the claim actually asserts.

**[2] and [3] read as sound on inspection -- no change.** [2] (tariffs):
claim_ref explicitly states the sourcing-shift the claim describes; the
"stop-gap" wording in the evidence itself appropriately tempers the
resolution's "not resolved" framing, no strawman. [3] (diversification):
already the one contradiction Report 1 called genuinely good, strengthened
structurally by item 7's fix (Loop 5) which added its missing claim-side
evidence; the customer-concentration-declining vs. product-concentration-
still-high tension is a real, evidence-grounded, non-strawman qualifier.

**Deliberately not touched:** ANANDRATHI's four contradictions were already
assessed as sound during item 7's migration (Loop 5) and again implicitly
during item 8's design (no numeric-disagreement false positives found in
them either). Re-auditing them here would be repeating work already done,
not new analysis.

**Local verification:** compileall OK; full regression 1158 passed;
SANSERA live PASS -- contradiction count unchanged at 4, all other facts
unchanged (including the numeric-disagreement detection, unaffected since
the claim text it scans was not touched); both fixes visually confirmed
correct in the rendered dossier. ANANDRATHI untouched, no re-run needed for
content, but included in the same CI push since both live scripts run in
one job.

**CI: VERIFIED.** Run #356 (35441605984) on PR #15, commit 23c7975 -- all 16 gate steps green. Both dossiers confirmed rendering the reworded contradiction and the added semiconductor/defence refs correctly.


## Loop 8 — Paresh's decisions on items 2/11-14's blocking policy question

Asked, rather than guessed, since these items all needed a policy input
this pipeline cannot derive from the data alone (same reasoning as item
20's deferred threshold).

**Q1: should staleness/half-life and primary-share thresholds be universal
constants or declared per-archetype?**
**A: per-archetype**, in each `ResearchPlan` -- the same place
`material_domains` and `exclusions` already live. This is the answer that
keeps the adaptive-research design consistent: a wealth manager and a
manufacturer do not go stale at the same rate, and a single universal
constant would repeat the checklist mistake found twice already today.

**Q2: minimum primary-source share (item 2)?** Told Paresh the real
consequence before asking: SANSERA is at 60.6%, ANANDRATHI is at ~19% after
item 19 correctly downgraded its video/homepage sources -- any threshold
above ~19% blocks ANANDRATHI's dossier today, on a defect (item 9,
entity-relative tiering) that is not yet fixed, not on new bad research.
**A: no hard gate yet.** Item 2 is DEFERRED, explicitly, until item 9
exists. This is now a recorded decision, not an assumption.

**Consequence for items 11-14:** the per-archetype answer means the
half-life table is an OPTIONAL, OVERRIDABLE field on ResearchPlan, not a
single constant applied everywhere -- a wrong default for one archetype
does not lock in for all. That materially lowers the risk of proposing a
reasonable starting table myself (see item 11 below), unlike item 2's
single hard universal gate, which stays deferred because getting it wrong
there means blocking a whole archetype outright.


## Loop 9 — item 4b reassessed and closed (not implemented as a schema split)

B6's original concern was "absence-of-evidence was counted as normal
evidence" -- i.e. a DERIVED record could silently masquerade as real
evidence, inflating counts unnoticed. Checked before building anything:
both dossier renderers already report primary/secondary/derived evidence
counts as separate, explicit fields (predates this session's work), so a
DERIVED item was never actually invisible in the total. What items 5, 18,
20 and 21 added today is tier-aware FILTERING in every metric computed
since: DERIVED never sets newest_evidence_anchor or an age bucket (item
20), a domain covered only by DERIVED evidence is separately reported
(item 5), and a finding resting solely on DERIVED support is flagged (item
21).

Given that, a literal "separate gaps field" -- pulling DERIVED items out of
`ResearchProviderPacket.evidence` into their own collection -- would mean
threading a new field through every construction site (both packets),
every consumer (`validate_evidence_set`, `validate_research_coverage`,
`execute_research`, `_evidence_map`, both dossier renderers, both live
scripts, the ResearchItem's positive/negative/unknowns split), and every
existing test that constructs a packet. That is a large, invasive refactor
whose only remaining benefit over the current source_tier-based filtering
is architectural tidiness, not a fixed defect -- B6's actual harm is
already closed. Doing it now would be exactly the over-engineering the
operating standard warns against: real effort for a benefit smaller than
what already exists.

**Closed, not implemented.** If a future need arises where DERIVED and
real evidence genuinely cannot share one collection (not yet identified),
revisit then with that concrete need driving the design, rather than
speculatively splitting the schema now.

## Loop 10 — item 8 regex gap: "+"-suffixed figures silently unextracted

**Observed** during a self-directed adversarial-council audit pass (not a
new report from Paresh): `_INR_VALUE_PATTERN` required whitespace or a
range dash immediately after the numeric group. Real ANANDRATHI evidence
states AUM as `"INR 1,06,300+ crore"` (website-sourced figure). Confirmed
by direct testing -- not inference -- that `_extract_inr_million_values`
returned an empty set for that claim: the literal `+` character sat
between the digits and the required `\s*` before the unit, so the whole
pattern failed to match.

**Root-cause decision:** narrow regex fix, not a rewrite. Tolerate an
optional `+` after each numeric group (both the single-value case and each
end of a range), consistent with item 8's original design constraint
(Section 23: deterministic, narrow, no NLP).

**Repair:** `_INR_VALUE_PATTERN` updated; docstring extended to document
the `+` case and cite the real evidence item it comes from.

**Local verification:** direct extraction test confirmed `"INR
1,06,300+ crore"` now yields `1063000.0` (INR million), matching the
non-`+` restatement of the same figure elsewhere in the packet -- so no
new disagreement is spuriously introduced. Full suite: 1159 passed (up
from before by one new regression test,
`test_numeric_disagreement_extracts_plus_suffixed_figures`). Both live
scripts re-run: SANSERA unchanged (1 disagreement, 44368 vs 57500 million);
ANANDRATHI unchanged (0 disagreements) -- confirms the fix closes a
detection gap without changing any real-data output, because the `+`
claim's own value already agrees with the other same-quarter AUM claim
once extraction actually works.

**CI: VERIFIED.** Run #360 (35443317589) on PR #15, commit f2663d3 --
completed/success.

**Scope decision:** stopping the self-directed audit here rather than
opening further rounds looking for more issues, per Paresh's explicit
"are we stuck in one loop" check -- this fix is shipped and closed, not a
new open-ended thread.

## Loop 11 — third/fourth/fifth archetypes: PAYTM, YATHARTH, LENSKART (in progress)

Per Paresh's explicit instruction after the PR #15 merge ("run 2-3
different companies analysis to get more ideas... move very fast"):
extending real-data coverage to three more Top-25 candidates, chosen
deliberately for archetype diversity against the two already built
(SANSERA = industrial exporter, ANANDRATHI = wealth management) so real
research surfaces new pipeline edge cases rather than repeating known
patterns:

- **PAYTM** (rank 22, One97 Communications) -- digital-payments/fintech
  platform archetype: network effects, RBI/PA-CB regulatory exposure, no
  physical order backlog.
- **YATHARTH** (rank 17, Yatharth Hospital and Trauma Care Services) --
  hospital-operator archetype: bed capacity/occupancy, ARPOB, payer mix,
  government-scheme exposure.
- **LENSKART** (rank 11) -- consumer D2C/omnichannel retail archetype:
  store-network expansion, same-store growth, private-label margin.

Dispatched as three parallel research agents, each given the exact current
schema (`contracts.py`, `research_execution.py`, `company_research.py`)
read directly from source rather than from memory, and every non-negotiable
rule this session already paid to learn: mandatory non-trivial exclusions,
`published_on` requirement with the narrow `undated_primary_source` escape,
real `http(s)://` URLs only, PRIMARY-tier rejection for video hosts/bare
domain roots, claim-keyed refs (never positional), two-sided
non-strawman contradictions with disjoint ref lists, full hypothesis
coverage, and an explicit no-fabrication requirement (every source must be
actually fetched and read, not inferred). Each agent works only on its own
three new files (`agent/<symbol>_research_packet.py`,
`scripts/stage4b_<symbol>_live_validation.py`,
`tests/test_agent_<symbol>_execution.py`) and does not touch any existing
file or commit -- integration, verification against real data, CI wiring,
and the commit/push are done centrally, one company at a time, with the
same discipline as every prior loop (full local suite, both/all live
scripts, actual CI run ID checked before any VERIFIED claim).

All three agents hit a shared, account-level session rate limit mid-run
(not a per-agent defect) and were resumed once via `SendMessage` after the
limit cleared; each then completed independently.

**Integration verification performed centrally** (not just trusted from
each agent's self-report): every packet file was read in full for schema
correctness (claim-keyed refs via `evidence_ref`, disjoint two-sided
contradiction ref lists, non-trivial exclusions, dates all `<=` the
2026-09-18 cutoff), then re-run independently through
`execute_research`/`judge_dossier`, then the single highest-stakes claim in
each packet was spot-checked against the real primary source directly (not
the agent's own quoted text):

- **YATHARTH**: the ₹3,150cr Advent International preferential-issue claim
  was checked against the actual board-outcome PDF
  (yatharth_20573744.pdf) -- every figure (1,30,26,516 shares,
  1,89,47,664 warrants, INR 985.17/unit, INR 31,50,00,02,910.60
  aggregate, 24.87% fully-diluted stake, 15 Oct 2026 EGM, CCI condition,
  55.80% pre-issue promoter holding, 3-year lock-in) matched exactly,
  down to the paisa.
- **PAYTM**: the RBI/PPBL licence-cancellation claim was checked against
  the actual RBI press release (prid=62621) -- date (24 April 2026),
  statutory grounds (Section 22, Banking Regulation Act 1949) and the
  depositor-liquidity statement all matched.
- **LENSKART**: the corrected IPO-listing-date claim (10 Nov 2025, which
  the agent corrected from this loop's own initial rank/sector hint) was
  independently confirmed via a fresh web search.

21/23/26 evidence items respectively (YATHARTH/PAYTM/LENSKART), all
PRIMARY/SECONDARY items real fetched sources with real dates, DERIVED
items honestly recording genuine disclosure gaps rather than fabricating
resolutions. Full local suite after adding all three: **1168 passed** (up
from 1159 -- 9 new tests, 3 per company, zero regressions).

**CI: VERIFIED.** Run #363 (35470906354) on PR #16, commit b5557b2 --
completed/success, all steps green including the three new live-execution
steps and dossier-artifact retention. `mergeable_state: clean`.

## Rule against false closure

A green unit-test suite alone does not close Stage-4B. The real acceptance runners must execute successfully, retained dossiers must exist, and the adversarial/research-quality improvements must be re-run after repair.
