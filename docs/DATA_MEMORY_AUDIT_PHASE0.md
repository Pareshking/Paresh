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

The long loader explicitly reads `nse_long_close.parquet` into pandas and converts it
to `float32`; it reads traded value separately and also converts it to `float32`.
The traded-value file is only needed when a liquidity floor is enabled.

## What is already established

### Historical close

`src/loaders/nse_long.py` says the long close file contains adjusted closes for
the 2010+ historical Backtest path, with renames joined and corporate-action
adjustments already applied by the build.

### Historical value

`nse_long_value.parquet` contains traded value in Rs crore. It is not needed
when the historical liquidity floor is off.

### Raw source pack

`nse_raw_pack.parquet` is substantially larger than the published close matrix.
It is an intermediate/reproducibility artifact used by the weekly long-price build,
not something the Streamlit Backtest should load.

### Current NSE loader

`data/nse_prices/closes.parquet` is already a wide sessions × symbols representation.
Therefore we must not assume that "long format" alone explains the memory problem.

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

## Required measurements

Run:

```bash
python scripts/audit_data_footprint.py data_cache/nse_long/nse_long_close.parquet
python scripts/audit_data_footprint.py data_cache/nse_long/nse_long_value.parquet
python scripts/audit_data_footprint.py --dir data_cache/nse_long
```

For the application path, additionally record RSS checkpoints for:

```
cold startup
→ ranking
→ Screener store
→ current NSE
→ long close
→ long value
→ selected historical slice
→ backtest preparation
→ backtest execution
→ result rendering
```

The application itself is **not changed by this audit script**.

## Important interpretation rule

The previous local observation of a ~110 MB long-file memory increase must not be
compared directly with the current 17.9 MB Parquet object size.

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
peak process RSS
```

Only the last measurement explains the Streamlit memory limit.

## Current hypothesis ranking

1. **Multiple materialised copies / derived frames** — high priority.
2. **Universal loading before page-specific need** — high priority.
3. **Long history + backtest intermediates** — high priority.
4. **Historical value matrix loaded unnecessarily** — high priority when floor is off.
5. **NSE/Screener duplicate history** — high priority to verify.
6. **Raw Parquet size itself being the root cause** — currently unproven.
7. **Long-format representation itself being the root cause** — currently unproven.
8. **Streamlit cache/reload behavior** — secondary until data footprint is measured.

## No-go conditions

Do not replace/delete/repartition the historical close artifact until:

- schema and shape are measured;
- historical coverage is verified;
- corporate-action correctness is verified;
- point-in-time membership coverage is verified;
- current Backtest output is captured as a regression baseline;
- peak RSS is captured.

## Rollback anchor

If subsequent Phase-0/Phase-1 work causes a live regression, the known-safe rollback
anchor is PR #414's merge commit:

`79e99f0f64f389f8fed9e0b27efc22b0501a98afb`

The previous problematic PRs are **#410, #411 and #412**. They must not be restored
as a group.

## Next gate

Phase 0 is complete only when the audit table exists and every major memory
consumer has an identified owner and purpose.

Only then should Phase 1 data-model changes begin.
