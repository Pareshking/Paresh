# Stage 4 — Company Research PDCA

Date: 2026-09-19
Branch: agent/foundation-v1
Status: IMPLEMENTATION IN PROGRESS — GATE OPEN

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
