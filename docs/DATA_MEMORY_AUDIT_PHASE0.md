# Phase 0 — Data Footprint Audit

**Status:** audit tooling/documentation only; no application runtime change.

## Current release evidence

The 2026-10-07 `data-latest` release contains:

| Artifact | Compressed release size |
|---|---:|
| `nse_long_close.parquet` | 17,901,024 bytes (~17.9 MB) |
| `nse_long_value.parquet` | 23,778,870 bytes (~23.8 MB) |
| **close + value** | **41,679,894 bytes (~41.7 MB)** |
| `nse_raw_pack.parquet` | 169,940,135 bytes (~169.9 MB) |
| `nse_actions_pack.parquet` | 3,817,631 bytes (~3.8 MB) |
| `history_backtests.zip` | 3,311,385 bytes (~3.3 MB) |
| `rankings.parquet` | 232,406 bytes (~0.23 MB) |

These are **compressed release-object sizes**, not pandas RAM usage.

The long loader reads `nse_long_close.parquet` into pandas and converts it to `float32`. It can also read traded value separately; value is only required when a historical liquidity floor is enabled.

## Data-role boundary

Raw historical prices must be included in this audit, but they have a different role from adjusted historical prices.

| Dataset | Normal website startup | Normal ranking/current pages | Historical backtest | Reconstruction / data audit |
|---|---:|---:|---:|---:|
| Current Screener prices | Yes, if required | Yes | Sometimes | Yes |
| Current NSE prices | Fallback/validation | Fallback/validation | If required | Yes |
| Adjusted historical close | **No** | **No** | **Yes** | Yes |
| Raw historical price pack | **No** | **No** | Usually **No** | **Yes** |
| Corporate-action pack | **No** | **No** | Only if rebuilding adjustments | **Yes** |
| Historical traded value | **No** | **No** | Only when liquidity floor requires it | Yes |
| Precomputed historical runs | No | No | Potentially | Yes |

**Rule:** raw historical data is an underlying reconstruction/validation dependency, not a normal Streamlit page dependency. We must not load it into application RAM merely because the website opened.

## What is already established

### Historical close

`src/loaders/nse_long.py` uses the long close file for the 2010+ historical Backtest path. The published close data is adjusted and includes the historical rename/corporate-action processing performed by the build.

### Historical value

`nse_long_value.parquet` contains traded value in Rs crore. It is not needed when the historical liquidity floor is off.

### Raw source pack

`nse_raw_pack.parquet` is substantially larger than the published close matrix. It is an intermediate/reproducibility artifact used by the weekly long-price build, not something the Streamlit Backtest should load.

### Current NSE loader

`data/nse_prices/closes.parquet` is already a wide sessions × symbols representation. Therefore we must not assume that "long format" alone explains the memory problem.

## Phase-0 questions

1. What are the exact rows/symbol columns/dates in each published price matrix?
2. What is pandas deep memory after Parquet materialisation?
3. Does Parquet read create float64 intermediates before the final float32 object?
4. How much memory is the DatetimeIndex?
5. How many symbols are actually present versus needed by each historical index?
6. How many cells are missing?
7. How much memory is consumed by the traded-value matrix?
8. What happens when only the selected historical membership/date range is read?
9. Where are duplicate copies created after loading?
10. What is peak process RSS for the complete Backtest path?
11. **Does the website load adjusted historical, raw historical, or both on pages that do not need history?**
12. **Does a cold/stale container download raw source artifacts at all, or only published application artifacts?**
13. **Which loader call causes each historical artifact to be materialised?**

## Required measurements

Run:

```bash
python scripts/audit_data_footprint.py data_cache/nse_long/nse_long_close.parquet
python scripts/audit_data_footprint.py data_cache/nse_long/nse_long_value.parquet
python scripts/audit_data_footprint.py --dir data_cache/nse_long
```

For the application path, record RSS checkpoints for:

```
cold startup
→ ranking
→ Screener store
→ current NSE
→ adjusted historical close
→ raw historical price (if reached)
→ corporate actions (if reached)
→ historical value (if reached)
→ selected historical slice
→ backtest preparation
→ backtest execution
→ result rendering
```

Also record whether each step caused a network download and whether the artifact came from local cache/R2/release.

The application itself is **not changed by this audit script**.

## Required audit table

Phase 0 must produce one row per material dataset:

| Dataset | Source | Compressed bytes | Rows | Columns/symbols | Date range | Missing cells | Pandas deep MB | Numeric buffer MB | Instant RSS delta MB | Peak RSS MB | Downloaded? | Loaded by | Purpose |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|

This separates four things that must not be conflated:

1. network/download cost;
2. compressed storage cost;
3. materialised DataFrame cost;
4. process-level peak RSS.

## Important interpretation rule

The previous local observation of a ~110 MB long-file memory increase must not be compared directly with the current 17.9 MB Parquet object size.

The correct comparison is:

```
compressed Parquet
vs
Arrow/Parquet materialisation
vs
pandas deep memory
vs
NumPy numeric buffers
vs
instantaneous RSS
vs
peak process RSS
```

Only process RSS explains the Streamlit memory limit. The other measurements explain **why** RSS rises.

## Current hypothesis ranking

1. **Multiple materialised copies / derived frames** — high priority.
2. **Universal loading before page-specific need** — high priority.
3. **Long history + backtest intermediates** — high priority.
4. **Historical value matrix loaded unnecessarily** — high priority when floor is off.
5. **NSE/Screener duplicate history** — high priority to verify.
6. **Raw historical data being loaded by normal pages** — high priority to verify; not yet proven.
7. **Raw Parquet size itself being the root cause** — currently unproven.
8. **Long-format representation itself being the root cause** — currently unproven.
9. **Streamlit cache/reload behavior** — secondary until data footprint is measured.

## Engineering phases

### Phase 0 — Measurement foundation
No runtime optimization. Establish artifact footprint, dependency ownership, cold/warm loading behavior, RSS checkpoints, and correctness baseline.

**Gate:** every major memory consumer has a measured footprint and an identified purpose.

### Phase 1 — Data-loading dependency audit
Trace `load_all_data()`, price-source resolution, Screener/NSE fallback, historical loaders, raw packs, corporate actions, and page entry points.

**Goal:** prove exactly which pages cause which datasets to be downloaded/materialised.

**Gate:** dependency graph is measured; no code optimization is accepted without a before/after measurement.

### Phase 2 — Minimal lazy-loading refactor
Make historical/raw/value data page- and feature-specific. Do not redesign the data format yet.

**Gate:** same outputs, lower peak RSS, and no increase in normal page latency/loading regressions.

### Phase 3 — Data representation optimization
Only after Phase 2 measurements: evaluate `float32`, wide matrices, partitioned/lazy Parquet, selective historical slices, and metadata separation.

**Gate:** correctness and point-in-time membership/corporate-action checks pass, with measured memory/network benefit.

### Phase 4 — Canonical historical runs
Evaluate precomputed `history_backtests.zip` only if measured. Do not restore the old module-reload/cache approach from PRs #410/#411/#412.

**Gate:** canonical runs are reproducible and do not cause the page-freezing/loading regression that led to PR #414.

### Phase 5 — Cache/session/UI optimization
Only after the data path is controlled: targeted cache keys, bounded caches, fragments/forms where useful, and reload behavior.

**Gate:** repeated navigation does not trigger unnecessary heavy work and memory remains bounded.

### Phase 6 — Production validation
Cold container, warm container, each page, canonical/custom Backtest, multiple sessions, downloads, cache hit/miss, peak RSS, latency, and health-check stability.

**Gate:** production-like memory headroom is demonstrated, not inferred.

## No-go conditions

Do not replace/delete/repartition the historical close artifact until:

- schema and shape are measured;
- historical coverage is verified;
- corporate-action correctness is verified;
- point-in-time membership coverage is verified;
- current Backtest output is captured as a regression baseline;
- peak RSS is captured;
- raw-vs-adjusted data roles are verified.

Do not optimize Streamlit cache/reload behavior merely because the app reports a memory error.

## Rollback protocol

**Normal rule:** if an individual phase PR causes a regression, revert **that phase PR only**. Do not revert unrelated history.

For a GitHub PR that was merged, use GitHub's revert mechanism against the merge commit rather than rewriting history.

**Known-good application anchor:** PR #414 merge commit:

`79e99f0f64f389f8fed9e0b27efc22b0501a98afb`

The previous problematic PRs are **#410, #411 and #412**. They must **not** be restored as a group.

For data artifacts, keep the previous immutable R2/release artifact and pin the reader to the previous artifact revision/SHA if a new artifact proves faulty. Roll back the code/artifact pair together.

If a phase produces an ambiguous regression that cannot be isolated quickly, restore the application to the known-good #414 anchor first, then investigate the phase branch independently.

## Next gate

Phase 0 is complete only when:

- the audit table exists;
- raw, adjusted, value, corporate-action, current-price, and precomputed-run roles are explicit;
- cold/warm download behavior is measured;
- major memory consumers have an identified owner and purpose;
- the live Backtest correctness baseline is captured.

Only then should Phase 1 loading changes begin.
