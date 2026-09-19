# AI Research Agent — Master Specification

Date: 2026-09-19
Status: Living specification

This is the master specification for the AI research-agent program. It prevents ad-hoc prompts, duplicated calculations, disconnected scripts, and untestable AI behaviour.

**Primary rule: reuse existing Paresh capability before creating anything new.**

## 1. Target outcome

Turn the existing quantitative System-1 output into a repeatable research workflow that answers: what do we know, what supports the thesis, what contradicts it, what is unknown, what could go wrong, and what should be monitored next.

The agent is an evidence and reasoning layer around the quantitative system, not a replacement for System-1.

## 2. Final weekly output

The intended weekly deliverable is a research report for the current Top-25 quantitative candidates.

### Market context
- quantitative snapshot/as-of date
- benchmark, universe, System-1 identity
- market/regime context
- existing market breadth
- sector rotation
- industry context
- material market-wide events
- data-quality limitations

### Candidate information
For every candidate: rank, company, existing System-1 metrics, sector, industry, peer group, changes versus prior report, positive evidence, negative evidence, unknowns, upcoming events, freshness, and adversarial status.

### Company research
Investigate relevant announcements, filings, regulatory events, orders/contracts, acquisitions/divestments, fund raising/debt, management commentary, results/guidance, shareholding/promoter material information, corporate actions, litigation/regulatory matters, industry developments, major customer/supplier developments and scheduled events.

### Evidence buckets
Every substantive point is Positive, Negative, or Unknown. Unknown is never automatically Negative.

### Adversarial section
Original thesis, strongest support, strongest contradiction, assumptions, weak links, missing information, invalidation conditions, evidence that could resolve uncertainty, and upcoming risks/catalysts.

### Event calendar
Expected results and other reliably scheduled material events, with sourced dates.

### Provenance appendix
Model, benchmark, universe, quantitative as-of, price as-of, pipeline version, configuration fingerprint, price source, source artifact, research retrieval window, limitations and fallback paths.

## 3. Hard prohibitions

Do not duplicate momentum, calendar momentum, Sharpe-like score, volatility, winsorisation, z-score, ranking, benchmark, universe, membership, 52-week high, ATH, corporate-action adjustment, price-source selection, breadth, sector/industry ranking, portfolio weighting/caps, volatility targeting, backtesting or track-record arithmetic.

If a quantitative defect is found, record it and fix the canonical owner or add an audit/regression test. Never create an agent workaround that becomes a second source of truth.

Do not manufacture facts/citations; turn unknown into negative; silently fill missing values; suppress contradictory evidence; infer motives; claim plausible events as facts; use stale evidence as current; or convert narrative judgement into a hidden numerical score.

## 4. Architecture

Existing Paresh quantitative system → validated quantitative artifact → read-only agent snapshot → market → sector → industry → peers → company evidence → adversarial challenge → review → weekly report → historical process audit.

Agent code remains separate from production ranking logic and UI.

## 5. Existing capability ownership

Ranking: src/engine/pipeline.py
Ranking artifact: src/loaders/ranking_store.py
Price snapshot: src/loaders/price_store.py
Price source: src/loaders/price_source.py
Corporate actions: src/engine/corporate_actions.py
Universe: src/loaders/indices_loader.py
Membership: src/engine/membership.py
Market caps: src/loaders/mcap_loader.py
ATH: src/loaders/ath_loader.py
Sector/industry: src/loaders/tv_loader.py
Breadth: src/engine/breadth.py
Backtest: src/engine/backtester.py
Portfolio: src/engine/portfolio.py
Track record: src/engine/track_record.py

Before adding code, search the existing owner and its callers/tests.

## 6. Artifact-first quantitative hand-off

Normal Stage-2 path: existing rankings.parquet → validate embedded contract → validate as-of/universe → preserve pipeline/config identity → expose rows read-only.

Do not start Stage 2 by downloading external price data. Price history is secondary input only for a genuine research question or explicit audit.

## 7. Quantitative snapshot

Preserve: as_of, benchmark, universe, model, config_fingerprint, pipeline_version, price_source, price_as_of, source_artifact, and quantitative rows.

This is provenance, not a new calculation engine.

## 8. Evidence model

Every evidence item should contain entity, claim, evidence kind, source, source tier, publication date when available, retrieval date, confidence where meaningful, and notes.

Primary: exchange/company/regulator/government disclosures.
Secondary: reputable journalism and established information providers.
Derived: calculations or transformations made from cited sources.

Derived information must never be disguised as an external fact.

## 9. Research hierarchy

Market → sector → industry → peer group → company → specific event/evidence.

This reduces company-level tunnel vision and uses existing taxonomy instead of rebuilding it.

## 10. Research loop

1. Discover potentially relevant information.
2. Verify dates/entities and prefer primary sources.
3. Classify positive/negative/unknown.
4. Synthesize a factual thesis without changing ranking.
5. Attack the thesis with contradictory evidence.
6. Review citations, dates, unsupported claims, omissions and uncertainty.
7. Publish only information that survives review.

## 11. Multi-agent roles

**Researcher:** discovers and organizes evidence.

**Challenger / Prosecution:** actively attacks the thesis.

**Defence:** tests whether support survives the challenge without suppressing contradictions.

**Reviewer:** audits factuality, citations, dates, completeness and source quality.

**Jury:** summarizes unresolved factual disputes and evidence quality; does not recommend an investment choice.

**Judge:** enforces process/publication gates; does not alter System-1.

These are logical roles and do not require separate AI accounts.

## 12. Quality controls

Check every candidate for correct ticker/company, event date, source date, primary-source availability, stale information, duplicates, contradictions, materiality, classification, unsupported inference, citation completeness, unknowns and upcoming events.

## 13. Temporal controls

For historical reports, never use information published after the report as-of date as though it were known then. Distinguish event date, publication date and retrieval date. Current reports must label dates and avoid calling stale evidence recent.

## 14. Cost/efficiency

Use deterministic Python/repository data for whole-universe work. Use AI research selectively for Top-25. Do not ask an LLM to recompute 750-stock quantitative calculations that Python already performs. Cache evidence only with sufficient identity to prevent stale reuse.

## 15. API strategy

Manual development/research should not acquire an external AI API dependency merely for convenience. External credentials become relevant for autonomous GitHub Actions or another external runtime. Build and validate the manual workflow first.

## 16. Automation target

Scheduled workflow → obtain canonical ranking artifact → validate → select Top-25 → research market/sector/industry/company → adversarial review → report → archive report/provenance → process metrics → notification.

Automation must never silently modify System-1.

## 17. Failure policy

Fail closed for missing/unreadable ranking artifacts, contract mismatch, inconsistent dates/universe/source identity, or unverifiable evidence. Never silently substitute a different artifact. Unknown remains unknown.

## 18. Testing pyramid

Unit: contracts, evidence, provenance, dates.

Integration: artifact → snapshot → research.

Regression: existing Paresh outputs unchanged.

Adversarial: stale artifact, wrong universe/weights/version/as-of/actions, duplicate/contradictory evidence, future-information leakage.

End-to-end: actual published artifact → actual report.

Historical replay: eventually reproduce past reports using only information available at the time.

## 19. Quantitative parity rule

Canonical output wins. If an independent audit differs: stop, record both values, identify canonical owner, determine expectedness, fix the canonical system or audit, add regression coverage, and never silently choose the convenient value.

## 20. Documentation discipline

Every stage maintains plan, implementation record, tests, failures, decisions, changes from plan, limitations, completion gate and next-stage prerequisites. Documentation is updated during development, not reconstructed at the end.

## 21. Stage completion gate

A stage completes only when PLAN, DO, CHECK and ACT are recorded; documentation matches code; no duplicate ownership exists; provenance is sufficient; failure behaviour is known; regression risk is addressed; and next-stage entry conditions are explicit.

## 22. Roadmap

Stage 1 Foundation
Stage 2 Quant hand-off
Stage 3 Market hierarchy
Stage 4 Company research
Stage 5 Adversarial review
Stage 6 Weekly report
Stage 7 Historical audit
Stage 8 Automation

## 23. Definition of success

Success is one quantitative source of truth, reproducible research, traceable evidence, active contradiction search, explicit uncertainty, useful context around System-1, repeatable weekly output, measurable research quality, safe failure and minimal duplication. More code or more agents is not the goal.

## 24. Final engineering principle

The AI agent should make Paresh's existing system more understandable, auditable and researchable — not replace it with an AI approximation.

When uncertain: **inspect → search existing implementation → reuse → test → document → only then build.**

## Stage-2 implementation ownership

The read-only quantitative hand-off is implemented in `agent/quant_hand_off.py`. It consumes the canonical `ranking_store.fetch_snapshot()` result, validates the embedded contract against current canonical pipeline/source/weight identity, validates row/universe integrity, and converts the accepted rows to `QuantSnapshot`. It has no price acquisition, ranking calculation, portfolio logic, or qualitative research fallback.


### Canonical price-source fallback

Artifact provenance records the actual source used by the producer. When the canonical configuration prefers Screener, the producer may legitimately fall back to Yahoo if Screener is unavailable or insufficient. The agent must preserve and validate that documented fallback rather than treating the preference string as proof of the actual source. It must not independently download prices to determine which source should have won.


## Stage-3 implementation ownership

The Stage-3 market hierarchy adapter is agent/market_hierarchy.py. It is read-only and consumes canonical Paresh market outputs and taxonomy fields. Peer groups are deterministic groupings over the selected existing taxonomy; no peer model or second taxonomy is introduced. Historical membership delegates to src/engine/membership.py and preserves out-of-coverage unknowns. This does not change System-1.