# Stage 4 — Company Research PDCA

Date: 2026-09-19
Branch: agent/foundation-v1
Status: DEEP RESEARCH REFINEMENT IN PROGRESS — GATE OPEN

## PLAN

Fresh repository inspection was completed before implementation. The existing research/source-owner audit found no dedicated company-research/news/filings adapter in the inspected repository surface. The written plan was recorded in agent/STAGE_4_PLAN.md before implementation.

## DO

Implemented the smallest current boundary:
- agent/company_research.py
- tests/test_agent_company_research.py
- agent/RESEARCH_SOURCE_POLICY.md
- agent/STAGE_4_LIVE_OUTPUT_2026-09-19.md

The implementation only converts the accepted QuantSnapshot Top-25 into research candidates and validates evidence identity/date/classification. It does not calculate rank, score, momentum, price or any investment score.

## CHECK — INITIAL ADVERSARIAL LOOP

### Researcher
A real current Top-25 research pass was completed on 2026-09-19 using current public company/exchange/regulatory sources and established secondary sources for discovery/corroboration.

### Prosecution / Challenger
Found several areas where announcement titles are insufficient to infer financial impact. The live report therefore leaves such implications UNKNOWN. Exchange clarifications, regulatory/fine disclosures, preferential issues, promoter/shareholding transactions and media reports were explicitly prevented from being turned into unsupported directional claims.

### Defence
The report preserves the canonical rank/score unchanged, retains contradictory/adverse evidence where verified, and uses UNKNOWN rather than manufacturing a negative finding.

### Reviewer
Reviewed source hierarchy, dates, entity/ticker identity, evidence classification and quantitative non-duplication. The first implementation has focused validation tests. Full CI execution remains pending for the current head.

### Jury
The research boundary is structurally sound and a real report exists, but several companies require underlying filing/document review before the evidence can be considered deep enough for a final Stage-4 gate.

### Judge
**GATE OPEN — NOT COMPLETE.** The first live report is real and reviewable, but Stage 4 is not yet closed.

## Required next CHECK

1. Run focused Stage-4 tests in CI.
2. Run full V1 regression.
3. Verify live Top-25 candidate identity against the canonical artifact.
4. Audit every cited claim for source/date/entity consistency.
5. Review underlying primary documents for material items rather than relying only on index pages.
6. Add explicit adversarial tests for future dates, duplicate claims, unsupported symbols and rank/score immutability.
7. Re-run the report after any evidence correction.

## ACT

Do not mark Stage 4 complete yet. The current live report is retained for human review and is explicitly labelled provisional.


## CHECK — Human review refinement, 2026-09-19

The human review correctly rejected the initial report as too close to a news digest. A company announcement feed is already available from Screener/BSE and does not justify the intended Stage-4 investment in research infrastructure.

### New acceptance requirement

The WELCORP acceptance sample must demonstrate:
- peers and competitive footprint;
- industry-wide order flow;
- sector developments;
- government/regulatory/project pipeline;
- capacity and utilisation;
- customers/suppliers;
- input/energy/freight margin channels;
- FX exposure;
- tariffs/duties/trade-war asymmetry;
- macro/geopolitical transmission;
- technology/IP;
- funding/capital allocation/shareholding;
- management commentary across quarters;
- event lifecycle tracking;
- contradiction detection;
- explicit UNKNOWN-to-question-to-resolution tracking;
- market-reaction context.

The detailed specification is recorded in `agent/STAGE_4_DEEP_RESEARCH_SPEC.md` and the acceptance sample in `agent/STAGE_4_WELCORP_DEEP_SAMPLE_2026-09-19.md`.

### New adversarial finding

The WELCORP sample itself surfaced a reconciliation issue: the official July company disclosure reported an approximately ₹25,750 crore order book after a ₹960 crore order, while a third-party transcript summary currently reports ₹42,000 crore. The production implementation must resolve such definition/date discrepancies from the underlying primary transcript/presentation instead of selecting the more favourable figure.

### Judge

**GATE OPEN — NOT COMPLETE.** The research scope is now materially deeper, but the executable workflow and primary-document verification still need implementation and testing.
