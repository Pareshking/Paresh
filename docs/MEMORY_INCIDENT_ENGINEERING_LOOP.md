# Memory Incident Engineering Loop

This is the governing plan for the memory/resource-limit incident.

## Rules

1. **Measure before changing behavior.**
2. Every behavior change gets its own PR and rollback point.
3. Never combine data-model, cache, reload, and UI changes in one optimization PR.
4. Preserve a correctness baseline before every optimization.
5. A lower memory number is not accepted if page latency, correctness, freshness, or reproducibility regresses.
6. A successful local run is not sufficient; production/cold-container behavior must be measured.
7. Do not revive #410/#411/#412 as a bundle. Their behavior already demonstrated that the loading/reload approach can regress the application.

## Baseline / rollback hierarchy

### Primary known-good application anchor

PR #414 merge:

\`79e99f0f64f389f8fed9e0b27efc22b0501a98afb\`

Use this when a regression cannot be isolated.

### Phase-specific rollback

- Phase 0 audit: revert PR #416.
- Phase 1 telemetry: revert PR #417.
- Phase 2 loading change: revert only the Phase-2 PR.
- Phase 3 representation/data change: revert only the Phase-3 PR and restore the previous immutable data artifact/revision.
- Phase 4 historical precompute: revert only the precompute PR; fall back to the canonical engine path.
- Phase 5 cache/UI/reload changes: revert only that phase PR.

Use GitHub PR/merge reverts rather than destructive history rewriting.

## Phase 0 — Footprint audit

**Question:** What are the actual sizes and shapes of the datasets?

Measure:

- compressed Parquet bytes;
- rows/columns;
- dtypes;
- date coverage;
- symbol coverage;
- missing cells;
- pandas deep memory;
- numeric buffer memory;
- current RSS;
- high-water RSS.

**Exit gate:** no major data consumer remains unidentified.

PR: #416.

## Phase 1 — Loading dependency audit

**Question:** What does each page actually cause the process to fetch/materialize?

Trace:

\`page → load_all_data → price source → dataset → pandas object → RSS\`

Measure cold and warm behavior for:

- Screener;
- Portfolio;
- Actions;
- Sectors/RRG;
- Backtest;
- Backtest with liquidity floor ON/OFF.

Explicitly prove:

- whether deep history is loaded on ordinary pages;
- whether NSE history is loaded despite usable Screener data;
- whether historical value is loaded when liquidity is OFF;
- whether raw packs are ever touched by Streamlit;
- whether duplicate DataFrames are retained.

PR: #417.

**Exit gate:** measured dependency graph and RSS attribution.

## Phase 2 — Minimal loading refactor

Only after Phase 1 evidence.

Likely candidates, subject to measurement:

- make deep history page-demand-driven;
- avoid loading NSE history when Screener fully satisfies the ranking request;
- load traded value only when liquidity filtering actually requires it;
- eliminate unnecessary copies;
- retain exactly the same ranking/backtest semantics.

Do NOT change:

- historical price definitions;
- corporate-action methodology;
- point-in-time membership;
- benchmark methodology;
- ranking formulas.

**Exit gate:**

- peak RSS lower;
- cold-start latency no worse beyond agreed threshold;
- warm navigation no worse;
- identical canonical outputs;
- no new download.

## Phase 3 — Representation optimization

Only if Phase 2 is insufficient.

Evaluate empirically:

- float32 vs float64;
- wide numeric matrix vs alternative representation;
- selective/partitioned Parquet;
- date/symbol slicing;
- metadata separation;
- removal of unnecessary materialized columns.

Do not remove historical/delisted symbols merely because they are not in today's 750. Historical membership is required to avoid survivorship bias.

**Exit gate:** lower memory/network/storage with validated historical correctness.

## Phase 4 — Historical execution/precomputation

Evaluate the \`history_backtests.zip\` approach independently.

Requirements:

- exact input fingerprint;
- canonical output contract;
- no giant startup load;
- custom periods still use lazy historical data;
- no module-reload dependency;
- no click-by-click reload regression.

PRs #410/#411/#412 are evidence to learn from, not a rollback bundle.

**Exit gate:** canonical historical runs become cheaper without the freezing/loading regression previously observed.

## Phase 5 — Cache/session/UI optimization

Only after data-loading and representation are correct.

Evaluate:

- bounded cache keys;
- cache lifetime;
- cache invalidation;
- \`st.fragment\` only around genuinely independent expensive UI;
- \`st.cache_resource\` only for immutable/thread-safe shared resources;
- session-state retention;
- avoidance of global \`st.cache_data.clear()\`.

Do not use cache changes to conceal excessive data loading.

**Exit gate:** repeated navigation remains responsive and memory stays bounded.

## Phase 6 — Production validation

Test:

1. cold container;
2. warm container;
3. first user;
4. second user/session;
5. all pages;
6. canonical Backtest;
7. custom Backtest;
8. liquidity ON/OFF;
9. deploy/restart;
10. repeated navigation.

Record:

- peak RSS;
- final RSS;
- stage timings;
- downloads;
- cache hits/misses;
- selected data source;
- correctness fingerprints;
- health-check stability.

## Acceptance rule

An optimization is accepted only when:

\`memory improvement + correctness preserved + latency acceptable + reproducibility preserved\`

All four are required.

If memory improves but navigation becomes slower/freezes, reject the change.

If memory improves but price/backtest outputs change unexpectedly, reject the change.

If correctness is preserved but peak RSS remains near the platform limit, continue to the next smallest measured bottleneck.

## Current status

Phase 0: audit framework established — PR #416.

Phase 1: memory boundary and allocation attribution instrumentation — PR #417.

Phase 2: **blocked deliberately until Phase 1 production measurements identify the dominant unnecessary allocation.**
