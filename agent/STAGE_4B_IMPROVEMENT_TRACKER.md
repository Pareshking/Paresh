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
| 4 | Validate source URLs / separate gaps from evidence | B3/B6 | **PARTIAL — 4a (URL format for non-derived tiers) DONE; separate gaps field still TODO — Loop 4** |
| 5 | Quality-aware domain coverage | A3 | **DONE as a REPORTED metric, not a hard gate — Loop 4 course-correction** |
| 6 | Soften judge summary to actual guarantees | A4 | **DONE — Loop 4** |
| 7 | Contradictions require genuinely disagreeing evidence | B2 | TODO |
| 8 | Detect cross-tier numeric disagreement | B1 | TODO |
| 9 | Entity-relative source tiering | B4 | **DEFERRED — needs an issuer-to-symbol map; a URL-shape heuristic would guess, not fix — Loop 4** |
| 10 | Evidence age distribution + rounded score | C1/C2/R5c | **DONE — Loop 4** |
| 11 | Claim-type evidence half-life classification | R4 | TODO |
| 12 | Stale evidence cannot sole-cover/carry mechanism/primary share | R5a | TODO |
| 13 | Joint tier + recency ranking, never recency-first | R3/R5b | TODO |
| 14 | Explicit last-disclosed/stale finding | R5c/R1 | TODO |
| 15 | Fix ANANDRATHI refs[16] only through provenance-safe repair | E1/E2 | **DONE — absorbed into 16** |
| 16 | Claim-keyed evidence refs; prohibit positional refs | E3 | **DONE — ANANDRATHI converted** |
| 17 | Executable test per archetype: packet + execute_research | E4 | **DONE — ANANDRATHI test added** |
| 18 | Detect evidence cited by no causal/contradiction finding | E5 | **DONE — ANANDRATHI execution test enforces zero orphans** |
| 19 | Reject/downgrade unstable sources | F1/F2/B3 | **VERIFIED — run #348 (35438217592), all 16 steps green** |
| 20 | Evidence-window freshness: max(published_on) vs snapshot.as_of | F4 | **DONE (measured + reported, not yet a hard gate) — see Loop 3** |
| 21 | Mark absence-based support explicitly | F6 | **DONE — Loop 4** |
| 22 | Apply genuine-contradiction standard retroactively to SANSERA | G1/B2 | TODO |
| 23 | Require and test explicit domain exclusions for every archetype | G2 | **DONE — ResearchPlan.exclusions now mandatory framework-wide; SANSERA symmetry test added — Loop 4** |
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
- Items 6, 10, 21, 23: **DONE, CI pending** (Loop 4, batched)
- Item 5: **DONE as reported metric (not a hard gate), CI pending** (Loop 4)
- Item 4: **PARTIAL (4a done, gaps-field TODO), CI pending** (Loop 4)
- Item 9: **DEFERRED** -- needs an issuer-to-symbol map (Loop 4)
- Remaining (items 2, 7, 8, 11-14, 22): **NOT STARTED**
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

**CI: not yet verified for this loop.** Awaiting push and a fresh run.


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

**CI: not yet verified for this batch.** Awaiting push and a fresh run.

## Rule against false closure

A green unit-test suite alone does not close Stage-4B. The real acceptance runners must execute successfully, retained dossiers must exist, and the adversarial/research-quality improvements must be re-run after repair.
