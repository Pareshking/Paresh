# Stage 4 — Company Research Plan

Date: 2026-09-19
Branch: agent/foundation-v1
Status: PLAN RECORDED — IMPLEMENTATION NOT STARTED

## 1. Objective

Build the smallest evidence-first Company Research layer after the verified Market → Sector → Industry → Peer stage.

The output for each selected company must answer:
- what material information is known;
- what supports the quantitative candidate;
- what contradicts it;
- what remains unknown/unverified;
- what upcoming scheduled events matter;
- how fresh the evidence is;
- which claims come from primary vs secondary vs derived sources;
- what an adversarial reviewer should challenge.

The Company Research layer must not alter System-1 ranking, create a qualitative score, or substitute narrative judgment for the quantitative model.

## 2. Fresh repository inspection — completed before this plan

Inspected the current branch's:
- agent/AI_AGENT_MASTER_SPEC.md
- agent/AI_AGENT_DEVELOPMENT_TRACKER.md
- agent/REPO_INTEGRATION_MAP.md
- agent/contracts.py
- agent/quant_hand_off.py
- agent/market_hierarchy.py
- app.py
- .github/workflows/v1-full-validation.yml
- requirements.txt

The Stage-3 live verifier and current V1 workflow were also inspected.

## 3. Existing research/source-owner audit

### Existing canonical owners reused

| Research need | Existing owner | Stage-4 treatment |
|---|---|---|
| Quantitative candidate identity/rank/score | agent.quant_hand_off → canonical ranking_store artifact | Consume only |
| Sector/industry/taxonomy | src.loaders.tv_loader.py + classification data | Consume only |
| Corporate-action data already represented in Paresh | src.engine.corporate_actions.py / existing event data | Consume/provenance only |
| Market/peer context | Stage-3 adapter | Consume only |
| Evidence contract | agent/contracts.py | Extend only if a missing research field is demonstrated |
| External company/news research | No existing dedicated owner found in the inspected repository surface | New Stage-4 boundary |

### Explicit audit conclusion

No existing dedicated company-research/news/filings/orders/management-commentary source adapter was found in the inspected repository surface.

Therefore Stage 4 may introduce a dedicated research boundary, but it must remain separate from quantitative loaders and must not duplicate existing corporate-action, taxonomy, or ranking ownership.

## 4. Evidence policy

Every substantive research item must have:
- symbol/entity;
- claim;
- Positive / Negative / Unknown classification;
- source URL or source identifier;
- source tier;
- publication/event date when available;
- retrieval date;
- confidence;
- notes/context;
- materiality/why it matters;
- explicit distinction between event date and publication date.

Primary sources are preferred: company investor-relations disclosures, exchange filings/disclosures, SEBI/regulator/government disclosures, and official earnings/result presentations and transcripts.

Secondary sources may supplement Reuters and established financial journalism or financial-information providers.

Derived evidence must cite its underlying source(s). No unsupported inference is allowed.

## 5. Research scope per company

For each selected Top-25 company: corporate announcements; financial results and guidance; orders/contracts/business wins; acquisitions/divestments/fund raising/debt; management commentary; promoter/shareholding material information; corporate actions; litigation/regulatory developments; major customer/supplier developments; industry developments; scheduled results/events; positive evidence; negative evidence; unknown/unverified items.

Not every category needs a finding. Absence of a verified finding must remain explicit rather than becoming "none".

## 6. Temporal policy

For a current report, retrieval date must be recorded; publication/event date must be recorded where available; stale information must be labelled stale; future events must be clearly labelled scheduled/expected; later information must never be represented as if known earlier.

For eventual historical replay, the report must enforce an as-of cutoff.

## 7. Proposed smallest implementation

Create:
- agent/company_research.py — orchestration/data model boundary; no ranking calculations.
- tests/test_agent_company_research.py — validation and failure-mode tests.
- agent/STAGE_4_PDCA.md — implementation/check/act record.
- agent/STAGE_4_LIVE_OUTPUT_2026-09-19.md — actual report produced from the current Top-25.
- agent/RESEARCH_SOURCE_POLICY.md — durable source hierarchy and citation policy.

Do not add an external AI API dependency.

The initial implementation should support explicit evidence records supplied by a research collection process. It should not pretend that an unauthenticated automated scraper is authoritative.

## 8. Failure policy

Fail closed on missing symbol/company identity; duplicate company records; missing claim/source; malformed publication/retrieval dates; future publication date; invalid evidence classification; invalid source tier; evidence attached to a symbol outside the current Top-25 research set.

Unknown is valid evidence state. Unknown is never converted to Negative.

## 9. Adversarial loop

Researcher: collects potentially material evidence and records provenance.

Prosecution / Challenger: searches for contradictions, stale evidence, omitted negative information, weak sources, wrong entities, and unsupported claims.

Defence: tests whether positive evidence remains supported after the challenge without suppressing contradictions.

Reviewer: checks dates, URLs, source tier, duplicates, classification, entity identity, completeness and uncertainty.

Jury: summarizes unresolved factual disputes and evidence quality without recommending an investment choice.

Judge: enforces publication gates and refuses unsupported claims.

## 10. Acceptance tests

Unit: valid evidence accepted; duplicate symbols rejected; duplicate evidence IDs rejected; publication date after retrieval date rejected; future publication date rejected; invalid evidence kind rejected; invalid source tier rejected; unknown evidence preserved; unsupported symbol rejected.

Integration: current QuantSnapshot Top-25 can become a research candidate set; company research cannot modify rank/score; provenance from Stage 2/3 remains intact.

Live: actual current Top-25 research report generated; every substantive claim has a source; source tier is recorded; retrieval date is recorded; positive/negative/unknown buckets reconcile; no fabricated "no news" claims.

## 11. Gate

Stage 4 is complete only when fresh inspection and source-owner audit are documented; this plan exists before implementation; implementation passes focused tests; adversarial loop is documented; actual current Top-25 research output exists; source/date/provenance audit passes; contradictions and unknowns are explicit; no quantitative methodology is duplicated; exact output is retained for review.

If live research cannot be completed reliably, Stage 4 remains NOT VERIFIED rather than being marked complete.

## 12. Non-goals

No new ranking model; no qualitative score; no investment recommendation; no duplicate taxonomy; no duplicate corporate-action engine; no autonomous LLM API; no silent web scraping treated as primary evidence; no historical backtest; no automation scheduling yet.
