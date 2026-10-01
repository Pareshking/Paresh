# Changelog

## 2026-10-01 — UI overhaul (draft PR)

- Open trades and the current month's rebalances now reach Portfolio (engine fix).
- One table for the Screener: Full Quant is the master, Executive and Core hide columns; Table/Grid toggles removed.
- Time series use TradingView Lightweight Charts (hover legend; Breadth, Portfolio, Backtest, stock page with candles, volume, overlays and RS); Highcharts for the Relative Rotation Graph and the holdings correlation heatmap. The old fallback chart and its extra dependencies are gone.
- Portfolio sizes holdings at the latest rebalance (fixes negative cash / over 100% invested). Configuration has a data-freshness table.
- Portfolio absorbs the Track Record page; `/track-record` redirects.
- RRG benchmarks are Nifty 500 / Nifty 50; Configuration summary is a tidy list.
- New highs: 1M and 3M counts in Breadth and Full Quant.


## 2026-09-30 — Streamlit reload and track-record warning hardening

- Fixed a concurrency race in the custom Streamlit hot-reload path. The reload/import window is now serialized across script threads, preventing transient `KeyError` failures while `src.*` and `r2.*` modules are rebuilt.
- Added a concurrent reload regression test.
- Confirmed that `data/track_record_nano.json` and `data/track_record_combined.json` are intentionally absent before their October 2026 inception.
- Changed pre-inception missing-ledger logging from WARNING to INFO; missing ledgers at/after inception remain warnings, and corrupt ledgers still fail safely rather than being replaced with an empty record.
- PR #263 merged as `3529e834352156fafbd8f8f8b359ac8fb13219fc`.
- Validation: Lint #237, V1 Full Validation #1061, R2 Streamlit read-path gate #283 — all green.


## 2026-09-25 — Full code audit (merged up to #177)

- Owner decisions shipped:
  - 1B: ranking windows count back from the last price date.
  - 2B: up to five stragglers are ranked on their last print (⏸) instead of holding the ranking back.
  - 3B: the price fingerprint covers the whole history.
- UI read line by line:
  - escaping of every user- or vendor-supplied string;
  - exact index-tag matching;
  - cache keys that change when the history changes;
  - the navigation menu now closes when a page is chosen.
- Production QA:
  - a newer build that contains the triggering commit is no longer a mismatch;
  - the menu-reachability and nav-styling checks now measure what they claim;
  - a Reset that cannot be clicked is now a failure.
- Runtime dependencies pinned to the tested versions. The R2 read gate is skipped on Dependabot PRs and re-runs on main when `requirements.txt` changes.
- The Yahoo index-price fallback only accepts an exact index name.
- R2 storage size report added. Retention is awaiting the owner's decision.

## 2026-09-23 — Production ranking and Streamlit runtime hardening

- Enforced 100% current-universe coverage for canonical ranking sessions, eliminating the 749/750 acceptance path caused by the former 90% coverage floor.
- Added explicit symbol reconciliation diagnostics for precomputed-ranking rejection paths: missing, extra and duplicate symbols.
- Kept NSE DUMMY* placeholder filtering as the canonical tradability rule; no ticker aliases are introduced.
- Confirmed the canonical ranking source remains Screener/R2; Yahoo-origin data remains a separate deep-history/archive/healing feed.
- Reduced repeated Streamlit work by memoizing ranking-contract validation and Screener-frame shaping using correctness-preserving cache identities.
- Suppressed duplicate source-selection and precomputed-acceptance log messages when the logical decision is unchanged.
- Added production documentation covering the R2 path, 750-row completeness contract, Streamlit engine-skipped semantics and verification state.
- Verified the post-merge live deployment: main loaded successfully, the R2 Screener store was read, and a **750-row precomputed ranking was accepted**.

## 2026-09-22 — R2 production publication hardening

- R2 publication uses immutable content-addressed revisions, manifests and current pointers with read-back/hash verification.
- R2-focused CI is isolated from V1 Stage-4B research validation.
- Screener remains the canonical V1 ranking price source; Yahoo is separate archive/deep history.
