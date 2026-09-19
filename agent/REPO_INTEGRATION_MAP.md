# AI Agent Repository Integration Map

Date: 2026-09-19
Branch: agent/foundation-v1

## Purpose

This document is the agent's repository map. It exists to prevent the agent project
from rebuilding functionality that Paresh already implements.

**Rule: reuse before rebuild.**

The agent is an orchestration/research layer around Paresh. It is not a second
quantitative engine, data loader, backtester, portfolio optimizer, market-breadth
engine, or UI pipeline.

## 1. Canonical ownership

| Capability | Existing owner | Agent behaviour |
|---|---|---|
| System-1 formulas | `src/engine/calendar_momentum.py`, `src/engine/momentum.py` | Consume results; never duplicate formulas |
| Ranking orchestration | `src/engine/pipeline.py` | Treat as sole ranking pipeline |
| Current ranking artifact | `rankings.parquet` release asset via `src/loaders/ranking_store.py` | Preferred Stage-2 input |
| Price snapshot | `prices.parquet` release asset via `src/loaders/price_store.py` | Use only when a task genuinely needs price history |
| Price-source selection | `src/loaders/price_source.py` | Do not invent a new source-selection rule |
| Corporate actions | `src/engine/corporate_actions.py` | Consume applied-action provenance |
| Universe constituents | `src/loaders/indices_loader.py` + `data/indices/` | Reuse current universe |
| Point-in-time membership | `src/engine/membership.py` + `data/membership_history.json` | Reuse for historical questions |
| Market caps | `src/loaders/mcap_loader.py` + repository snapshot | Reuse |
| ATH | `src/loaders/ath_loader.py` + `data/nse_all_time_highs.csv` | Reuse |
| Sector/industry taxonomy | `src/loaders/tv_loader.py` + `data/nse_tv_classification.csv` | Reuse |
| Backtest | `src/engine/backtester.py` | Consume results / invoke existing engine only for explicit audit |
| Portfolio construction | `src/engine/portfolio.py` | Do not reproduce allocation mathematics |
| Track record | `src/engine/track_record.py` + `data/track_record.json` | Consume frozen record |
| QA/tests | `tests/`, `.github/workflows/` | Extend existing tests; do not create parallel test architecture |
| UI | `app.py`, `src/ui/` | Agent UI is separate and must not alter production UI contracts without an explicit task |

## 2. Current production ranking path

The normal production path is already optimized:

1. GitHub Actions runs `scripts/sync_data.py`.
2. The sync prepares the price snapshot.
3. The sync runs the canonical `src.engine.pipeline.build_engine()`.
4. It runs `pipeline.rank_with_weights()`.
5. It writes `rankings.parquet` with an embedded contract.
6. `.github/workflows/daily_sync.yml` publishes the ranking as the rolling `data-latest` release asset.
7. The Streamlit app fetches that artifact through `ranking_store.fetch_snapshot()`.
8. `app.py::_precomputed_ranking()` accepts it only when its contract matches the live state.
9. Only a contract miss falls back to live ranking computation.

Therefore Stage 2 should **consume the accepted ranking artifact first**.

## 3. What the ranking artifact already proves

The embedded ranking contract contains:

- pipeline version;
- price fingerprint;
- symbols fingerprint;
- price source;
- weights;
- universe;
- price as-of date;
- applied corporate-action digest.

This is stronger provenance than the Stage-1 agent originally assumed.

The agent should not independently calculate these fields. It should read and preserve
them.

## 4. Price data is not the first input

Do not begin Stage 2 by downloading Yahoo/Screener data.

The normal order is:

`ranking artifact -> validate contract -> expose quantitative rows -> research`

Price history is a secondary input for tasks that explicitly require it, such as a
chart, a historical event check, or an independent audit.

## 5. Existing data that can answer planned Stage-2 questions

### Market
Use existing breadth/regime calculations and their underlying engine outputs.
Do not create another breadth calculation.

### Sector
Use TradingView sector fields already attached to `rank_df` and the existing
sector view/engine.

### Industry
Use `TV_Industry` and existing industry ranking methods.

### Peer group
Derive peer membership from the existing industry/taxonomy fields. Do not build
a second industry taxonomy.

### Company
Only qualitative company research is genuinely new:
announcements, filings, orders, management commentary, regulatory events, material
news, corporate actions and other external evidence.

## 6. Backtest and track-record boundary

A live ranking is not the same thing as a historical track record.

- `src/engine/backtester.py` owns historical simulation.
- `src/engine/track_record.py` owns the frozen monthly record.
- `data/track_record.json` is the persisted record.

The agent may report these facts but must not recreate their arithmetic in its own
research code.

## 7. Agent-specific new work

The agent layer should add only:

- read-only quantitative snapshot construction;
- research orchestration;
- evidence/provenance handling;
- market/sector/industry/peer/company research coordination;
- adversarial challenge;
- reviewer/judge logic;
- report generation;
- research-process audit/history.

## 8. Forbidden duplication

Before adding a new function, search the repository for an existing owner.

Do not create agent versions of:

- momentum score;
- Sharpe calculation;
- winsorisation/z-score;
- rank calculation;
- universe construction;
- corporate-action adjustment;
- price-source selection;
- 52-week high;
- ATH;
- market breadth;
- sector ranking;
- industry ranking;
- portfolio caps;
- volatility targeting;
- backtest;
- track-record return;
- configuration constants.

If an existing implementation is imperfect, record the defect and fix the canonical
owner or add an audit test. Do not patch around it in the agent.

## 9. Stage-2 output contract

The agent's quantitative snapshot should identify at least:

- model;
- benchmark;
- universe;
- snapshot as-of;
- ranking price as-of;
- pipeline version;
- configuration fingerprint;
- price source;
- source artifact;
- rows/symbols actually consumed.

A research report must preserve these identities so a later reader can reproduce
which Paresh ranking was researched.

## 10. Review gate before Stage 2

After this repository audit, Stage 1 is considered **re-opened for review**, not
automatically accepted forever.

The Stage-2 gate is:

**No qualitative research begins until the agent can consume the canonical ranking
artifact without downloading/recalculating the quantitative system and can prove
the handoff is internally consistent.**

## 11. After Stage 2

Perform a complete Stage-1 + Stage-2 re-audit against:

- source code;
- tests;
- actual ranking artifact/output;
- provenance;
- failure paths;
- adversarial cases;
- documentation.

A stage can be reopened if later work exposes a weakness in its assumptions.


Stage 3 implementation ownership

The Stage-3 agent adapter is agent/market_hierarchy.py. It is an orchestration/read-only boundary only:
- market regime and breadth are supplied from existing Paresh owners;
- taxonomy remains src/loaders/tv_loader.py and data/nse_tv_classification.csv;
- industry aggregation remains MomentumEngine.get_industry_rankings;
- historical membership remains src/engine/membership.py;
- peer groups are deterministic groupings over an explicitly selected existing taxonomy.

No Stage-3 function downloads prices, recalculates ranking/breadth, creates a benchmark, or creates a second taxonomy.

## Stage-3 live verification integration — 2026-09-19

Added `scripts/stage3_live_validation.py` as the audit harness for the Market → Sector → Industry → Peer boundary. It consumes the Stage-2 QuantSnapshot, canonical TradingView classification, and canonical market-regime output; it does not introduce a ranking or taxonomy engine.

The V1 Full Validation workflow now runs this harness and retains its Markdown output as a dedicated `stage3-live-hierarchy` artifact before later QA gates.

The exact first live execution is preserved in `agent/STAGE_3_LIVE_VERIFICATION_2026-09-19.md`.


## Legacy Yahoo full-validation retirement — 2026-09-19

`scripts/full_validation.py` has been retired. It directly invoked `src.loaders.price_loader.fetch_price_history()` and independently rebuilt a ranking-validation path that no longer represents the production Screener-backed ranking pipeline.

The V1 production quantitative validation boundary is the published `data-latest/rankings.parquet` contract and the Stage-2 hand-off through `ranking_store.fetch_snapshot()` / `agent/quant_hand_off.py`.

Do not reintroduce the retired script as a production ranking gate. This does **not** remove Yahoo/yfinance from every repository use; it removes this obsolete validation path only.
