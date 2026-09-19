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
| 1 | Require `published_on` for primary/secondary evidence | A1 | TODO |
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

- SANSERA Stage-4B execution: **VERIFIED previously**
- ANANDRATHI execution before repair: **FAILED**
- ANANDRATHI provenance repair: **IMPLEMENTED — awaiting CI**
- Executable-path regression coverage: **IMPLEMENTED — awaiting CI**
- Full improvement suite: **NOT VERIFIED**
- SANSERA retroactive contradiction audit: **NOT VERIFIED**
- WELCORP adaptive rerun: **NOT VERIFIED**
- Full adversarial council: **NOT VERIFIED**
- Stage-4B closure: **NOT READY**

## Rule against false closure

A green unit-test suite alone does not close Stage-4B. The real acceptance runners must execute successfully, retained dossiers must exist, and the adversarial/research-quality improvements must be re-run after repair.
