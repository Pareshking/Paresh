# Phase 2 — Lazy long-history materialization

## Objective

Remove one confirmed unnecessary allocation from the universal application startup path:

- ranking/current pages need the ranking lookback frame;
- Backtest and Actions need the longer continuous history;
- the old _resolve_price_source() copied the requested long history before the page was known to need it.

The change keeps the same source, symbols, values, corporate-action behavior, and page calculations. It changes when the long-history copy is materialized.

## Before

load_all_data() → _resolve_price_source() → copy selected long history → return it → render any page.

The copy was created even for Screener, Portfolio, Sectors, RRG, Configuration, and Guide.

## After

load_all_data() → resolve ranking frame → return a callable for deep history.

Only Backtest or Actions calls the callable, at which point the requested symbol columns are copied.

The lazy frame is deliberately not put in st.cache_data; caching a large DataFrame would retain another serialized/copying path. Streamlit documents that st.cache_data returns copies to callers, while st.cache_resource shares one mutable instance, so neither is appropriate as an unmeasured fix here.

## Correctness invariant

No ranking input changes.

No price source changes.

No universe changes.

No corporate-action changes.

No backtest period rules change.

The only intended difference is that ordinary pages no longer allocate the separate deep-history copy.

## Measurement

Production acceptance must compare Phase 1 checkpoints against this branch:

- resolve_price_source:after_deep_defer
- resolve_price_source:deep_materialized (Backtest/Actions only)
- total startup RSS/VmHWM
- page render RSS/VmHWM
- cold vs warm container
- Backtest correctness outputs
- Actions correctness outputs
- latency

Expected result:

- ordinary pages: no deep_materialized checkpoint and lower peak RSS;
- Backtest/Actions: deep materialization still occurs and the result remains identical.

A memory improvement without correctness equality is a failed phase.

## Rollback

If this phase causes a regression, revert this PR only.

Do not restore PR #410/#411/#412 as a group.

If the regression cannot be isolated, restore the known-good PR #414 merge anchor:
79e99f0f64f389f8fed9e0b27efc22b0501a98afb.

Phase 3 must not start until this phase is measured and accepted.
