# Research Agent — Paresh Integration

**Start here: [`REPO_INTEGRATION_MAP.md`](REPO_INTEGRATION_MAP.md).** It is the
agent-facing map of existing Paresh capabilities and the non-duplication rules.

This directory adds an agent/orchestration layer around the existing Paresh quantitative engine.

## Non-negotiable architecture

The agent is **not** a second ranking engine. It consumes the canonical outputs already produced by Paresh and treats those outputs as facts. The normal Stage-2 quantitative input is the existing `rankings.parquet` release asset, not a fresh price download or a duplicate ranking calculation.

The agent may:
- explain quantitative results;
- investigate market, sector, industry and company context;
- collect positive evidence, negative evidence and unknowns;
- challenge its own conclusions;
- produce a weekly research report;
- record provenance and uncertainty.

The agent must not:
- change System-1 formulas;
- silently change benchmark, horizons, weights, universe or portfolio rules;
- manufacture missing data;
- turn qualitative evidence into a hidden numerical score;
- replace backtest results with narrative judgement.

## Staged implementation

1. **Foundation** — contracts, provenance, evidence model and report schema.
2. **Quant hand-off** — consume and validate the existing precomputed ranking artifact and expose its rows/provenance through read-only agent tools. Recalculation is reserved for an explicit audit, never the normal path.
3. **Market hierarchy** — market → sector → industry → peer context.
4. **Company research** — events, filings, announcements, corporate actions and material news.
5. **Adversarial review** — researcher → challenger → reviewer.
6. **Weekly report** — Top-25 quantitative candidates plus evidence, risks and unknowns.
7. **Historical audit** — measure whether the research process adds useful information without contaminating the ranking.
8. **Automation** — GitHub Actions only after the manual workflow is reproducible and tests are green.

## Provenance rule

Every external claim in an agent report should carry:
- source;
- publication/event date when available;
- retrieval date;
- entity/ticker;
- claim type;
- confidence;
- whether the source is primary or secondary.

The quantitative snapshot should also carry the exact as-of date and model/config fingerprint.

## Stage 1 completion gate

Stage 1 is complete only when all of these are true:

1. **Plan** — the pipeline stages and non-negotiable boundaries are explicit.
2. **Do** — immutable contracts exist for quantitative snapshots, evidence, research items, adversarial reviews and weekly reports.
3. **Check** — provenance fields are validated, confidence is bounded, evidence cannot be placed in the wrong bucket, report symbols are unique, and reviews cannot reference absent symbols.
4. **Act** — the runner uses the live canonical V1 configuration fingerprint rather than an `UNWIRED` placeholder, and the foundation tests are part of normal pytest discovery.

Stage 1 deliberately does **not** fetch prices, call external research providers, rank securities, or change portfolio behaviour. The post-Stage-1 repository audit also confirmed that Stage 2 must reuse the existing ranking snapshot, price snapshot, universe, membership, taxonomy, backtest and track-record infrastructure rather than duplicate them.

## PDCA record

The detailed Stage 1 PDCA record is in `agent/STAGE_1_PDCA.md`. Each later stage must repeat the same loop: define the gate, implement the smallest change, test adversarially, record failures/limitations, then act only on evidence.

## Current status

**Stage 1 — Foundation: re-reviewed and hardened.** The repository audit exposed additional provenance requirements and one precomputed-ranking contract gap; those are being addressed on this branch before Stage 2 begins. No production ranking methodology or portfolio behaviour is intentionally changed by the agent layer.


## Stage-2 implementation

`agent/quant_hand_off.py` is the single Stage-2 quantitative hand-off owner. It reads the existing published `rankings.parquet` through `ranking_store.fetch_snapshot()`, validates the embedded contract and row integrity, and produces a `QuantSnapshot`. It does not download prices, invoke the ranking engine, or silently fall back to recalculation.

Current Stage-2 verification remains **NOT VERIFIED** for local pytest, GitHub Actions, and live published-artifact E2E until those checks are actually observed.


## Stage-2 status — 2026-09-19

Stage 2 quantitative hand-off is **COMPLETE / GATE PASSED**. The real published `rankings.parquet` was consumed through `ranking_store.fetch_snapshot()` and accepted as a 750-row QuantSnapshot with as-of 2026-09-18, pipeline `v4_calendar_periods_cbab8da9`, and actual price source `screener`. The full regression suite recorded 1099 passing tests. A separate existing full-universe validation check remains red under thin current-session data and is not modified by the agent layer. Stage 3 has not yet been implemented; its repository inspection and written plan are the next gate.
