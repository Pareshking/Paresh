# Phase 1 — Data-Loading Dependency Audit

**Status:** observational instrumentation only. No loader behavior, cache policy, data format, or page semantics are changed.

## Objective

Prove which application stages load or materialize which datasets, and measure the resident-memory impact of each stage.

The Phase-0 question was not "is the Parquet file large?" but:

> **What does a user opening each page cause the process to download, materialize, copy, and retain?**

## Code-path finding from current main

The current `app.py` path is:

```
app startup
  → load_all_data()
      → _system_universe()
      → background market caps / regime / ranking snapshot
      → _resolve_price_source()
          → _fetch_screener_store()
          → _shape_screener_store()
          → build deep history from chosen Screener close
          → _nse.middle_close(symbols)
          → frames_from(...)
      → corporate actions
      → precomputed ranking validation
  → page render
```

A significant finding is already visible in code:

```python
deep = chosen.close[keep].copy() if keep else None
src = _ps.frames_from(chosen, symbols, _nse.middle_close(symbols))
```

Therefore two questions must be measured rather than assumed:

1. Does `_nse.middle_close(symbols)` materialize current NSE history even when Screener is already usable?
2. How large is the additional `deep` copy of the selected Screener history?

The current code comments say the deep history is for Backtest/Track Record, but `deep` is constructed inside `load_all_data()` before the page is selected. This is a dependency/ownership issue to verify in production measurements.

## Raw historical price boundary

The long historical raw source pack is a separate concern.

It is used to build/validate the published adjusted historical dataset. It should **not** be loaded by normal website startup.

Phase 1 must explicitly prove:

- raw historical pack is not touched by normal pages;
- adjusted historical close is only materialized when historical functionality needs it;
- historical traded value is only materialized when liquidity filtering needs it.

## Instrumentation added

`src/core/startup_metrics.py` now records instantaneous Linux `VmRSS` and `VmHWM` at every existing startup-stage boundary.

This is observational:

- no fetch order changed;
- no cache key changed;
- no data is dropped;
- no loader is made lazy;
- no price values change.

The telemetry distinguishes:

- **VmRSS** — memory resident now;
- **VmHWM** — process high-water RSS.

This is intentionally different from the earlier `ru_maxrss` measurement so the audit can see both current and high-water behavior.

## Required production run matrix

Run each case on a fresh/cold container and repeat once warm:

| Case | Page | Required observations |
|---|---|---|
| A | Screener | startup, current prices, NSE fallback/load, deep history |
| B | Portfolio | same + engine creation |
| C | Actions | same + benchmark |
| D | Rankings/Screener | ranking only |
| E | Backtest | deep history + historical slice + backtest |
| F | Backtest + liquidity floor ON | additionally historical value |
| G | Backtest + liquidity floor OFF | prove value is not loaded |

For every case capture:

- process identity/PID;
- deployed revision;
- cache state at startup;
- stage duration;
- RSS at stage start/end;
- high-water RSS;
- data-source facts;
- whether a network fetch occurred;
- rows/columns of loaded frames;
- final selected history shape.

## Acceptance measurements

The audit must answer these questions with evidence:

1. Does a normal Screener open load deep historical data?
2. Does a normal Screener open load current NSE history even when Screener is sufficient?
3. Does Portfolio inherit deep history before it actually requests it?
4. Does Backtest create duplicate historical DataFrames?
5. Does liquidity OFF avoid the traded-value file?
6. Is raw historical source data ever touched by Streamlit?
7. Which single stage produces the largest RSS increase?
8. Which objects remain resident after the page is rendered?
9. How much of peak RSS is data versus engine/backtest intermediates?
10. Does a second session reuse cached data or materialize another copy?

## Engineering gate

**Phase 1 cannot propose a data-format change yet.**

The output must first be a measured dependency graph:

```
PAGE
  ↓
FUNCTION
  ↓
DATASET
  ↓
DOWNLOAD / CACHE
  ↓
PANDAS MATERIALISATION
  ↓
RSS DELTA
  ↓
RETAINED AFTER PAGE
```

Only after this graph is complete can Phase 2 begin.

## Rollback

This branch changes telemetry only.

If telemetry itself causes an application regression:

1. revert this Phase-1 PR;
2. leave production data and ranking behavior untouched;
3. if the regression cannot be isolated, restore the known-good application anchor from PR #414:
   `79e99f0f64f389f8fed9e0b27efc22b0501a98afb`.

Do not restore PRs #410/#411/#412 as a group.

## Phase 2 entry condition

Phase 2 begins only if Phase 1 identifies at least one unnecessary materialisation with measured cost.

The first candidate to verify is the unconditional `_nse.middle_close(symbols)` call and the unconditional construction of the deep Screener history inside `_resolve_price_source()`.

No optimization is justified until the cold/warm measurements confirm their actual cost.
