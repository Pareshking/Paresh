# Memory audit, 8 Oct 2026

Streamlit Community Cloud emailed at 06:49 IST on 8 Oct: "Your app has gone over
its resource limits ... It's using too much memory", and restricted the app.
"Connecting..." in the browser is what a reader sees while the container is
killed and restarted.

Everything below was **measured** on this repository at `d99a5ac` with the
pinned requirements (Streamlit 1.65.0, pandas 3.0.6), against the live release
files, in a cloud container. Nothing was measured on Streamlit Cloud itself: it
exposes no memory figures, and its limit (about 2.7 GB) is from its docs.

## How it was measured

- `node conc.mjs N page,...`: N headless Chromium sessions open a page at the
  same moment; the server's RSS is sampled every 200 ms (peak) and read again
  when every session has finished (after). Cache sizes are Streamlit's own,
  from `/_stcore/metrics` (`cache_memory_bytes`).
- memray, on one warm rerun of the Screener page under `AppTest`, for what is
  allocated at the peak, line by line.
- `AppTest` with `cfg_w1` moved through six values, for cache growth.

## What the data is

| File | On disk | In memory |
|---|---|---|
| Screener store (`screener_prices.parquet`, 1,794 x 2,414, float64) | 8.5 MB | 35 MB |
| Long NSE closes (`nse_long_close.parquet`, 4,647 x 1,419, float32) | 17.9 MB | 26 MB |
| Long NSE traded value | 23.8 MB | 26 MB |

The inputs are small. The memory went into copies of them.

## Findings

| # | Where | What | Measured |
|---|---|---|---|
| M1 | `app.py` price path | `@st.cache_data` pickles its value and unpickles a **fresh copy on every hit**. The Screener store and its shaped frames came back as two 35 MB copies on every rerun of every session, and the NSE fill and weekly splice (`keep_and_fill`) ran uncached on every rerun. | memray: 136 MB allocated at the peak of one warm Screener rerun, all of it in `_resolve_price_source`; 2.3 s CPU per rerun |
| M2 | `run_momentum_pipeline`, `_run_engine_base` | Keyed on the weight vector with **no `max_entries`**, and the value is the whole engine with the ranking: 56 MB per entry, kept for an hour. | cache 117 MB -> 449 MB after five slider positions; ~1.7 GB after thirty |
| M3 | `run_backtest` | No `max_entries`; a parameter sweep stores one entry per combination (up to 1,920, x3 with the holdout). | 2 MB per Live entry; not the cause today, unbounded all the same |
| M4 | `load_all_data` thread pool | The ranking download imported `src.storage.reader` lazily on a pool thread while the script thread imported it via `r2_streamlit`: Python raised `_DeadlockError` on **every cold start**, and the R2 ranking was skipped for the release file. Not memory; found on the way. | 3 of 3 cold starts |
| M5 | glibc | Each session's script runs on its own thread and gets its own malloc arena, which keeps what it frees. | `MALLOC_ARENA_MAX=2`: peak 1,440 -> 1,286 MB, resting 946 -> 766 MB |

Not found: session state holds a few strings and small lists, no frames.
`runner.postScriptGC` (on by default) already runs `gc.collect(2)` after every
script run, so adding `gc.collect()` calls changes nothing.

## What changed

1. The Screener store, the resolved price frames and the corporate-action pass
   are `st.cache_resource` (one object for every session, `ttl=3600`,
   `max_entries` 2-4). Each rerun gets `frame.copy(deep=False)`: free, and under
   pandas 3 copy-on-write a write to it copies the touched block and never
   reaches the shared frame; a raw numpy write raises. Pinned by
   `tests/test_shared_price_cache.py`.
   The resolved frames are keyed on the Screener revision, the universe, and a
   stat of `data/nse_prices` and `data/reference`, so a nightly pull of NSE
   data still invalidates them.
2. `max_entries` on `_run_engine_base` (2), `run_momentum_pipeline` (4) and
   `run_backtest` (64). The engine caches stay `cache_data`:
   `rank_with_weights` writes `calc.weights` on the engine it is given, so it
   must not be shared.
3. `src.storage.reader`, `ranking_store` and `r2_streamlit` are imported on the
   script thread before the pool starts (M4).
4. `ENV MALLOC_ARENA_MAX=2` in the Dockerfile. It must be set before Python
   starts: `mallopt()` from `app.py` was tried and did nothing (peak 1,454 MB,
   resting 1,014 MB), because the server's own threads fix glibc's arena limit
   before the script runs. Streamlit Cloud cannot set it.
5. `server.maxUploadSize = 5` (the one uploader takes a holdings CSV).
6. Force Refresh, Sync and "Clear cached files" clear `st.cache_resource` as
   well as `st.cache_data`, so a refresh still drops the shared price frames.

Output unchanged: the app rendered on the old and new code, three reruns each,
gave the same page content and the same facts (price as-of, coverage 750/750,
weights), apart from `r2_rankings`, which no longer reports `_DeadlockError`.

## Before and after

Fresh server each time; 1 session on the Screener, then 4 at once on each page.

| | Before | After |
|---|---|---|
| 4 x Screener (warm), peak | 1,007 MB | 467 MB |
| 4 x Screener, time | 18 s | 4 s |
| 4 x Portfolio, peak | 1,876 MB | 1,440 MB |
| 4 x Backtest, peak | 1,764 MB | 1,075 MB |
| Resting after the run | 1,413 MB | 946 MB |
| Streamlit caches after the run | 252 MB | 137 MB |
| Errors in the server log | 1 (`_DeadlockError`) | 0 |

Before, five slider positions alone added 330 MB of cache (M2); that path is now
capped at 4 x 56 MB.

## Considered and not done

**DuckDB or Polars reading Parquet from R2 with column and row pushdown.** The
whole Screener store is 35 MB in memory; projecting the 750 ranked symbols out
of 1,207 would save about 14 MB, against ~250 MB of duplicated copies fixed
above. The R2 reader also checks every object's SHA-256 and size against its
manifest before use (`src/storage/reader.py`); range reads through `httpfs`
would skip that check, and the integrity contract is a decided rule. A second
engine also brings its own memory pool to a 2.7 GB container. Revisit if a
dataset grows past a few hundred MB.

**Moving backtests into a `ProcessPoolExecutor`.** Tornado was not starved: 410
health probes, every 200 ms, during 4 concurrent Portfolio and Backtest loads,
answered in median 11 ms, p99 123 ms, worst 1.5 s (the websocket tolerates far
longer). "Connecting..." was the container restarting after an OOM kill. A
worker process would start from a fork of a ~1 GB process and pickle the price
frames across, so it raises peak memory, which is the thing that failed.

## Correction to the parity check above

"The same page content" above hashed the markdown elements only: fonts, section
titles and the freshness ribbon. The ranking renders as raw HTML, which that
hash did not read, so it showed only that the facts (price as-of, coverage,
weights) were unchanged. The check was redone for S62 (below) over every HTML
element, which includes the top-50 movement panel built from the ranking.

## Follow-up, same day: S62 and S63

**S62, the engine shared.** `rank_with_weights` writes `weights`,
`momentum_scores` and `ranking_diagnostics` on the engine it is given, which is
why the engine stayed on `cache_data`. Now `pipeline.engine_view(calc)` gives a
caller its own engine object over the same arrays: frames are shallow
copy-on-write copies, dicts and lists are rebuilt three levels deep (the engine
holds `{months: frame}` and `{months: {field: value}}`). `_run_engine_base` and
`_ranked_shared` are `cache_resource`; ranking runs on a view of the base, and
each rerun gets a view of the ranked engine and a shallow copy of the table.
Tests: ranking on a view equals ranking on a deep copy (`assert_frame_equal`),
two weight vectors on one base do not see each other, and writes into a view's
frames and nested dicts reach neither the base nor another view.

**S63, the Track Record comparison.** It downloaded the Screener store again,
through a path that also ignored the configured R2 pin. The store reader moved
to `src/loaders/screener_cache.py`, shared by the app and the comparison. A
second, older fault went with it: the selected system's frame was returned from
inside an `st.cache_data` keyed on system names only, so after prices moved the
comparison served the old frame for up to an hour. That branch is no longer
cached.

**Parity.** #420's head (`3a67584`) and this code, three reruns each, with the
default weights (precomputed ranking) and with `cfg_w1 = 0.25`, which forces the
engine (`ranking_precompute = miss_weights_differ`): every HTML element and
every markdown element identical, no exceptions. Both sides read the same 8 Oct
market-cap file. Not compared: the full screener grid, which renders in an
element type the test harness does not expose as text.

**Memory**, same bench, two runs of the new code:

| 4 concurrent sessions, peak | Before #420 | #420 | + S62/S63 |
|---|---|---|---|
| Screener | 1,007 MB | 467 MB | 458 / 464 MB |
| Portfolio | 1,876 MB | 1,440 MB | 1,048 / 1,043 MB |
| Backtest | 1,764 MB | 1,075 MB | 958 / 910 MB |

Peaks repeat within ~50 MB; the resting figure after a run varied by ~100 MB
between identical runs, so it is not quoted. The target of 800 MB for Portfolio
was not reached.

**What the rest is.** memray over the whole server during 4 Portfolio loads
attributes ~1 GB of the 1.55 GB high-water mark to pyarrow's allocator
(mimalloc), charged to the first Arrow string allocation. That is mapped memory,
not necessarily resident, so it was tested against RSS: the same bench with
`ARROW_DEFAULT_MEMORY_POOL=system` gave Portfolio 922 MB, Backtest 918 MB (one
run). A lead, not a change: see TODO S64.

## Still open

See `docs/TODO.md` S61-S65.

- Portfolio peaks at ~1.05 GB with 4 sessions (S64: Arrow's allocator).
- The Backtest tab and the parameter sweep compute in the web process (S65).

## 8 Oct, afternoon: the production crash, S65 and telemetry

**What happened.** #420 deployed at 12:38 UTC (the config change made Streamlit
restart, so the new code ran from then). At 12:52 the health check got EOF with
no Python error before it: the signature of a memory kill, which Streamlit
Cloud does not log. The owner was running backtests.

**Cause, measured.** memray on one reader opening Backtest, then History from
2010: `backtester.py:_rolling_high_at` held 451 MB at the peak. A row of a
one-dtype frame is a view, so each 52-week-high row kept its whole 252-row
rolled frame alive, and `run_backtest` keeps one per signal date
(`_high_at_cache`): ~200 for the 2010 history. Synthetic check at the real
file's size (4,647 x 1,419): 581 MB retained, 2.8 MB with `.copy()`, values
identical. Single reader, same app: History peak 1,156 -> 751 MB.

**S65.** `compute_gate.serialised` under `run_backtest`'s cache: a miss waits
for any running backtest, a hit never does; the sweep takes it per
combination. Live check: reader B's cached History opened in 1.2 s during A's
sweep; B's new backtest showed the queued message within 0.5 s and rendered
after. Two large History backtests at once (Total Market + Microcap 250):
rise +410 / +391 MB on main, +286 / +322 MB gated (two runs each). Web sweep
ceiling 50 combinations (the engine's default 400 stays for scripts).

**Telemetry (from #417, bounded).** #417 appended a checkpoint to a list in
the page's facts at every stage boundary, every rerun, forever. Kept: the
first 64 (the cold start), the latest per label, the process peak, and one log
line each time VmHWM climbs 50 MB, with the label (`page:<name>` after each
page).

**Separate app for backtests.** Deferred by the owner (8 Oct) until production telemetry shows whether it is needed; TODO S68.
