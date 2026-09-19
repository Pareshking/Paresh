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


## CHECK — Adaptive research correction, 2026-09-19

### Human review finding
The expanded domain list must not become a universal checklist. Banks, pharma, CDMO, API, domestic pharma, specialty pharma, SaaS, hospitals, insurers, auto companies and industrial businesses have different economic drivers. Even two companies in the same sector can require different research lenses.

### Architectural correction
[✓] Research domains are now a capability library, not mandatory per-company fields
[✓] Added ResearchPlan contract with company archetype, economic drivers, selected material domains, hypotheses/questions and exclusions
[✓] Added validation for company-specific research plans
[✓] Added explicit information-cutoff controls to evidence validation

### Analytical correction
Evidence collection is now explicitly subordinate to analysis:

company profile → economic drivers → materiality map → hypotheses → targeted evidence → causal chain → timing → offsets/mitigants → peer/industry context where relevant → contradiction search → unresolved questions.

A chronological news report is a Stage-4 failure even when every headline is correctly sourced.

### Judge
**GATE OPEN — NOT COMPLETE.** The architecture now reflects adaptive, company-specific research and analytical connection of evidence, but the executable dossier generator and deep acceptance run still remain to be completed and verified.

## CHECK — Stage 4B execution loop, 2026-09-19

### PLAN
Stage 4B plan recorded in agent/STAGE_4B_PLAN.md. The architecture explicitly separates research collection from deterministic validation/compilation.

### DO
Added:
- agent/research_execution.py
- agent/sansera_research_packet.py
- scripts/stage4b_sansera_live_validation.py
- tests/test_agent_research_execution.py
- hypothesis binding on Evidence

### Research execution
A fresh SANSERA research cycle was performed against the 2026-09-18 information cutoff. It investigated the company-specific drivers of precision engineering, ADS, semiconductor equipment, aerospace, defence, automotive diversification, capacity, customer concentration, tariffs, FX, inputs, capital allocation, peers, industry and market reaction.

The research deliberately connected evidence rather than producing a chronology. Principal causal chains:
1. diversification → mix → margin;
2. backlog → qualification/machines/capacity → revenue timing;
3. ADS demand → industry demand → customer concentration → execution;
4. tariff → facility geography → customer sourcing → cost/incidence;
5. QIP/deleveraging → capex → asset turns → future ROCE.

### Prosecution / Challenger
Key challenges retained:
- backlog is not near-term revenue;
- semiconductor machine lead times constrain conversion;
- aerospace demand does not guarantee OEM production cadence;
- ADS backlog concentration is unresolved;
- tariff effects are asymmetric and product-specific incidence is unresolved;
- product concentration remains material despite end-market diversification;
- historical employee-misappropriation/fraud disclosure requires direct annual-report review;
- the later approximately INR57.5bn ADS backlog figure is secondary-source evidence and requires primary-transcript reconciliation.

### Defence
The positive thesis survives only in bounded form: diversification and ADS growth are already visible in reported revenue, but backlog conversion, customer concentration and capital productivity remain execution questions. No contradiction was suppressed.

### Reviewer
The provider packet has provenance, dates, selected-domain coverage, explicit unknowns, causal provenance and contradiction provenance. Future scheduled events are allowed only when the event is explicitly classified as SCHEDULED_EVENTS and the publication is available before the information cutoff.

### Judge
**GATE OPEN — NOT VERIFIED.** CI for the current Stage-4B head has not produced a workflow run through the available GitHub Actions interface, so machine execution cannot be claimed yet.

### Jury
The evidence set supports a factual finding that SANSERA's diversification is already operational rather than merely aspirational: ADS/non-auto growth is visible in Q1 revenue, the legacy ICE base still grows, and capacity is being expanded. The jury does not treat the large backlog as equivalent to near-term revenue. The principal unresolved issues are backlog/customer concentration, machine and qualification bottlenecks, current tariff incidence, current FX sensitivity, incremental asset returns and direct verification of the FY2025-26 fraud disclosure. The later approximately INR57.5bn backlog figure is retained as secondary evidence rather than silently replacing the June primary figure.

### Judge
The research loop has therefore completed the **Researcher → Prosecution → Defence → Reviewer → Jury** reasoning cycle for the manual SANSERA packet. Publication remains **OPEN / NOT VERIFIED** because the deterministic machine execution and current-head CI evidence are still unavailable through the current GitHub Actions interface, and some secondary claims require underlying-primary reconciliation.
