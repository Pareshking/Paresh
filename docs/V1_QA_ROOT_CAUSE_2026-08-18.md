# Umiya V1 — Production QA Root Cause & Hardening Loop — 2026-08-18

Branch: `claude/umiya-v1-qa-hardening-itgv19`
Baseline main SHA at start: `73e9187`

## Headline

The production application at https://paresh.streamlit.app/ **works**.

The repeated "Screener not visible within N seconds" failure was never an
application defect and was never a timeout. It was a QA-harness defect: the
harness inspected the top-level browser frame, but Streamlit Community Cloud
serves a wrapper SPA and mounts the app in a **nested iframe**. The selector
could not match in the frame being queried, so no value of N could ever have
passed. That is why 300s -> 600s changed nothing.

### Measured production evidence

Run `32089881539`, job `95569823302`, commit `c800ba5`, 2026-08-18 01:56-01:58 UTC:

| Signal | Value |
|---|---|
| readiness state | `ready` |
| time to ready | **22.0 s** (warm container) |
| websocket established | `True` |
| page errors | 0 |
| 5xx responses | 0 |
| console errors | 5, all `403/404 Failed to load resource` (blocked analytics/fonts) |
| tabs verified | 12 |
| viewports verified | 8 (5 desktop, 3 mobile) |
| tab visits | 96, **0 failures** |
| mobile horizontal overflow | none |
| rendered header | `Paresh Patel | ● BULLISH | ...` |

Frame layout proving the root cause:

```
https://paresh.streamlit.app/                     <- Cloud wrapper, body always empty
https://qjmnz4vd2y07.statuspage.io/embed/frame    <- status embed
https://paresh.streamlit.app/~/+/                 <- THE APP (nested iframe)
about:srcdoc x 12                                 <- the 12 tab panels
```

Contrast with run `32089145206` (frame-unaware): for the full 422 s budget
`body_len 0, stApp 0, stTabs 0, stSpinner 0, stException 0` while the
websocket was up with zero page errors — an empty frame, not a slow app.

## Ledger

| ID | Category | Severity | Location | Evidence | Root cause | Fix | Regression | Status |
|---|---|---|---|---|---|---|---|---|
| QA-01 | QA defect | CRITICAL | `scripts/production_website_qa*.py` | 422 s of `body_len 0` with live websocket; frame list shows app at `/~/+/` | Harness queried only the top-level frame; Cloud mounts the app in a nested iframe | Locate the frame hosting `[data-testid="stApp"]`; run readiness and all tab interaction there | Frame list recorded in every timeline sample and in the verdict | CLOSED |
| QA-02 | QA defect | HIGH | retired harness | `/_stcore/health` returned the same 9272-byte SPA shell as `/` | Edge serves the SPA for every path; a 200 there proves nothing about the Python app | Record the response and only treat a literal `ok` body as a health signal | Probe reports `is_streamlit_health_ok` / `looks_like_spa_shell` | CLOSED |
| QA-03 | QA defect | MEDIUM | retired harness | cookie-less client loops until max redirects | Cloud mints an anonymous viewer session over a redirect handshake; discarding the cookie loops forever | Use `requests.Session()` | Probe records redirect count | CLOSED |
| QA-04 | QA defect | MEDIUM | retired harness | one `get_by_text("Screener")` wait for every failure mode | Reachability, bootstrap and readiness collapsed into one signal | Readiness state machine over the real DOM, stopping at the first terminal state; every failure attributed APPLICATION / QA / INFRASTRUCTURE | 4 states verified against a live Streamlit DOM | CLOSED |
| Q-01 | New defect | HIGH | `src/engine/backtester.py` Industry-Relative branch | z 1.60 vs 1.45 peer scored 1.44 vs 1.45 and lost the top slot | Missing window filled with a zero z-score (the cross-sectional mean) and never renormalised; 10% shrink per 0.10 of missing weight, 30% for 9M+12M | Both branches call one shared `_composite_z_score()` with available-weight renormalisation | `tests/test_backtester_canonical_scoring.py` | CLOSED |
| Q-02 | New defect | LOW | `src/engine/backtester.py::_calendar_period_sharpe` | divergence 0.39% / 0.41% / 0.57% across stocks in one window | Sample SD (ddof=1) vs the screener's population SD; not uniform because in-window observation counts differ | `std(ddof=0)` | Screener equality asserted to rtol 1e-9 across all 5 horizons | CLOSED |
| Q-03 | New defect | LOW | `src/engine/backtester.py` Industry-Relative branch | `max(std, 1e-8)` yields an all-zero composite for a constant/empty cross-section | Missing degenerate-dispersion guard | Shared helper skips a window with non-finite or zero dispersion | Degenerate cross-section yields NaN | CLOSED |
| T-01 | New defect | MEDIUM | `src/ui/charts.py::render_sector_treemap` | unknown market cap drawn as a 1000 Cr tile | `fillna(1000)` on the tile-size column; tile AREA is the datum | Exclude unknown caps and disclose the exclusion; refuse to draw if none are known | `tests/test_sector_treemap_robustness.py` | CLOSED |
| T-02 | New defect | MEDIUM | `src/ui/charts.py::render_sector_treemap` | 6 of 16 degraded inputs raised `KeyError`/`ValueError` | Direct column dereference of optional columns | Guard required columns; filter `hover_data` to present columns | 16/16 degraded inputs now degrade with a message | CLOSED |
| R-01 | New defect | MEDIUM | `src/ui/views/rrg_view.py` | RS-Momentum 105.85 paired vs 109.69 flat-filled for a recent 40-session outage | `fillna(0)` on sector and benchmark returns asserts a flat session; lands in the denominator of every sector's RS | Pair observations with inner join + dropna | `tests/test_rrg_missing_data_integrity.py` | CLOSED |
| R-02 | New defect | HIGH (latent) | `src/ui/views/rrg_view.py` | `np.nan` used without `import numpy` | Module never imported numpy | Import added | Module import exercised in tests | CLOSED |
| INF-01 | Infrastructure | INFORMATIONAL | this QA sandbox | Chromium `ERR_CONNECTION_RESET` even for example.com | Sandbox egress proxy does not carry Chromium's TLS | Browser QA runs in GitHub Actions, which has clean egress | n/a | ACCEPTED |
| INF-02 | Infrastructure | INFORMATIONAL | this QA sandbox | yfinance `curl_cffi` reset by the proxy | TLS-impersonation transport cannot traverse a terminating proxy | Live-data runs happen in CI, not the sandbox | n/a | ACCEPTED |

## Verified clean

- **R² is absent from the production runtime.** Zero references in `src/` and
  `app.py`. Remaining hits are `research/`, one-shot `scripts/`, tests and docs.
- **Universe is 752.** `data/indices/ind_niftytotalmarket_list.csv` holds 752
  rows and 752 unique symbols; `indices_sync_meta.json` records 752
  (50+50+150+250+252), synced 15 Aug 2026. No hard-coded 750.
- **Composite screener path renormalises correctly.**
  `calendar_momentum.apply_calendar_momentum()` pairs `fillna(0.0)` with
  `available_weight` and divides — the zero contributes to neither numerator
  nor denominator.
- **Security.** No secrets, tokens or credentials in source or workflows. No
  `subprocess`, `os.system`, `eval`, `exec` or `pickle.load` in `src/` or
  `app.py`. No workflow consumes a secret.
- **Suite.** 81 passed (54 pre-existing + 27 added).

## Top remaining risk — cold start (NOT yet measured in production)

The 22.0 s above is a **warm** container. A genuine cold start is unmeasured,
and the code path is structurally expensive:

- `DATA_DIR` is `/tmp/data_cache` on Streamlit Cloud (`src/core/config.py`),
  which is ephemeral, so every container restart starts with no parquet cache.
- `fetch_price_history()` then downloads 752 tickers in 8 batches with 1.2 s
  sleeps, and retries every still-missing ticker **individually and
  sequentially** with no cap — up to 752 serial downloads if Yahoo throttles.
- `fetch_market_caps()` falls back to `_fetch_mcaps_yfinance()`, which after
  its 8-worker pass retries every failure **sequentially and single-threaded**,
  each attempt costing up to three calls including the expensive `.info`.

Both unbounded retry loops sit inside `@st.cache_data`, so they block first
render. This was NOT changed: it is a structural performance risk, not an
observed production failure, and changing it is a design decision rather than
a defect fix. Recommended next step is to measure a true cold start (push to
`main` forces a redeploy, so the QA run that follows a deploy is the cold
case) and, if it is slow, bound the two retry loops.

---

# Cold-start measurement — 2026-08-18

## Outcome: no cold start observed, and the premise was wrong twice

The cold-start risk recorded above rested on the assumption that a deploy
produces a fresh container with an empty `/tmp/data_cache`, so every restart
re-downloads the full universe. **Measured: false, in two separate ways.**

### 1. `/tmp/data_cache` survives a deploy

Run `32092212949` (main `27d3266`), cache snapshot taken *before any fetch*:

| file | state |
|---|---|
| `prices.parquet` | present, 16,210,238 B |
| `mcap_nse.parquet` | present, 70,851 B |
| `delivery.parquet` | present, 4,235,903 B |
| `market_caps.parquet` | absent |

`cold_container: false`. The probe refused to report a cold measurement.

### 2. The interpreter survives a deploy too

Run `32095465407` read `module_import_utc: None` and `process: null` — fields
that exist only in `2609b76` — while simultaneously reading
`memo_miss_prices: 1`, a counter that **also** exists only in `2609b76`.

The only state consistent with both: `app.py` was refreshed to the new commit
while `src/core/startup_metrics` remained the old build inside the same
interpreter, 3283 s (54.7 min) after its import. The entrypoint re-executes on
every run; an imported module sits in `sys.modules` and is not re-imported.

Streamlit Cloud therefore updated the script **without restarting the
process**. This is exactly the hazard the `module_import_utc` rename and
`process_identity()` were added to expose, and it is now demonstrated rather
than theorised.

## Measured baseline (warm, stable across runs)

| signal | run 32092212949 | run 32095465407 |
|---|---|---|
| navigation complete | 1.6 s | 2.6 s |
| Streamlit shell | 13.5 s | 14.9 s |
| Screener UI usable | 13.5 s | 14.9 s |
| fully interactive | 17.0 s | 18.2 s |
| `data_pipeline_total` | 0.3 s | 0.3 s |

The application's own work is 0.3 s. The ~14 s to first paint is Streamlit and
Cloud frontend bootstrap, not the V1 pipeline.

## Coverage — the retry loops are not being exercised

```
mcap_path              : pr_disk_cache
mcap_symbols_requested : 750
mcap_symbols_resolved  : 750
mcap_symbols_missing   : 0
price_path             : cache_incremental
universe_symbols       : 750
```

All 750 market caps resolved from the NSE PR bhavcopy cache, **zero missing**.
`mcap_yfinance_fallback_symbols` and `mcap_sequential_retries` are absent
entirely — the yfinance fallback was never entered. The sequential retry storm
that motivated the concern is not occurring in production.

## Correction: 752 and 750 are both right, and neither is stale

An earlier revision of this document claimed the repository CSV was stale
because it held 752 constituents while production reported 750. That was
wrong, twice over.

The index publishes **752** constituents. Two of them, `DUMMYINXGN` and
`DUMMYTRVN`, are corporate-action placeholders rather than tradable
securities, and `indices_loader._fetch_indices_impl()` filters them at the
`symbol.startswith("DUMMY")` guard. So:

```
752 published - 2 corporate-action placeholders = 750 tradable
```

Both figures are correct and describe different things. There is no
discrepancy and there never was one.

Confirmed against live data rather than argued: the daily sync ran on
18 Aug (run 32121112696) and committed a freshly downloaded constituent
file as `46c9acc`. That fresh file still contains 752 rows with the same
two dummies, so the repository snapshot was never behind the source.

Production derives the universe from niftyindices.com with the repo CSV as
fallback, which is the authoritative-source behaviour required. The
architecture was right; the reading of it was not.

## Decision

Cold start remains **unmeasured**, but the trigger for it is materially rarer
than assumed: neither the disk cache nor the interpreter is discarded on
deploy. Combined with zero missing symbols and no fallback usage, the evidence
supports leaving the retry architecture unchanged — the original decision, now
on firmer ground.

## Known instrument limitation

`stage()` retains only the first execution of each stage. That is correct for
capturing a cold start, but it means a later cache-invalidated re-run is not
timed. In run `32095465407` the changed `app.py` altered the `@st.cache_data`
source hash and forced a genuine re-fetch (`memo_miss_prices: 1`,
`price_path: cache_incremental`), and that re-fetch went unmeasured — the
reported `price_history` duration is still the 55-minute-old first run.

## Not reproducible from this session

A genuine cold start needs `/tmp` actually empty, which requires container
replacement rather than a deploy — app sleep/wake, resource eviction, or infra
migration. None can be forced without Streamlit Cloud dashboard access. The
reliable capture is a scheduled probe that records a baseline whenever it
observes `cold_container: true`.

## Infrastructure note

Run `32092756568` hung on its GitHub runner for 45 min at `duration_ms: 0` and
was cancelled. Production was healthy throughout, verified independently
(HTTP 200, ~2.1 s, three consecutive checks). Runner fault, not application.

---

# COLD START MEASURED — 2026-08-18, after dashboard reboot

Run `32100300353` paid the cold cost; run `32100801104` read the telemetry the
same process had recorded. A dashboard **Reboot** clears `/tmp`, where a
redeploy does not.

Proof it was genuinely cold: `price_path: full_download` (the parquet was
absent, so neither the fresh nor the incremental cache path was taken), and
`mcap_yfinance_fallback_symbols: 750` (the NSE PR disk cache was absent too).

## Total: 110.9 s of pipeline, ~92.5 s to a usable UI

| stage | start | duration |
|---|---:|---:|
| universe | 1.8 s | **19.7 s** |
| price_history | 21.5 s | **37.9 s** |
| extract_ohlcv | 59.4 s | 0.6 s |
| market_caps | 60.0 s | **45.9 s** |
| market_regime | 105.9 s | 0.2 s |
| quant_engine | 106.0 s | 6.7 s |
| **data_pipeline_total** | 1.8 s | **110.9 s** |
| delivery | 118.6 s | 0.7 s |

Browser-observed on the session that paid for it (run `32100300353`):
fully interactive at **92.5 s**, against a warm baseline of 17.5 s.

## The retry loops were barely exercised

This is the finding that settles the open question.

```
price_path                     : full_download
price_symbols_requested        : 750
price_batches_attempted        : 8
price_missing_after_batches    : 0      <-- individual retry loop NOT entered
price_series_returned          : 3750   (750 symbols x 5 OHLCV fields)

mcap_pr_zip_attempts           : 5      <-- all failed
mcap_yfinance_fallback_symbols : 750
mcap_threaded_requested        : 750
mcap_threaded_failed           : 1
mcap_sequential_retries        : 1      <-- not 750
mcap_symbols_resolved          : 749
mcap_symbols_missing           : 1
```

- **Price**: all 750 symbols arrived in the 8 batched downloads. The unbounded
  per-ticker retry loop was never entered at all — its counter is absent.
- **Market caps**: the threaded pass failed for exactly one symbol, so the
  sequential retry ran once, not 750 times.

The loops are unbounded in code, but in practice they are bounded by the data
being available. Neither degenerated.

## The real trigger condition, stated precisely

On a genuinely cold container the **NSE PR bhavcopy path fails**: five zip
attempts, all unsuccessful, before falling through to yfinance for all 750
symbols. The warm runs reported `mcap_path: pr_disk_cache` only because an
earlier process had left the file behind.

So market caps on a cold start depend entirely on yfinance, and `market_caps`
is duly the slowest stage at 45.9 s. The unbounded sequential retry becomes
dangerous only if **both** NSE PR and yfinance degrade at once. That is the
condition to watch, not cold start in general.

## Decision: retry architecture unchanged

Per the stated rule — acceptable cold start means leave it alone and document
the baseline. 110.9 s of pipeline and ~92.5 s to a usable UI is acceptable for
a rare event, and the loops that motivated the concern did not fire. Bounding
them now would still be optimising a hypothetical, and would risk the data
completeness the measurement just confirmed (750/750 prices, 749/750 caps).

## Baseline for regression comparison

| | cold | warm |
|---|---:|---:|
| data pipeline | 110.9 s | 0.3 s |
| fully interactive | 92.5 s | 17.5 s |
| price source | full_download, 8 batches | cache |
| mcap source | yfinance (PR failed) | pr_disk_cache |
| symbols priced | 750/750 | 750/750 |
| caps resolved | 749/750 | 750/750 |

One stock had no market cap on the cold run. With the treemap fix committed
earlier it is now excluded from a market-cap-sized treemap and disclosed,
rather than drawn at a fabricated 1000 Cr tile.

## Cache lifetime, corrected and complete

| event | `/tmp` cache | interpreter |
|---|---|---|
| redeploy (git push) | **survives** | **survives** (script reloaded only) |
| dashboard reboot | **cleared** | restarted |

Both halves of the original assumption were wrong, and only a reboot produces
the cold path.


---

# Correction: the daily sync workflow history

An earlier commit message stated that `daily_sync.yml` "had never once run"
on the basis of 200 recorded runs, all failed. That was wrong.

The accurate history:

| when | state |
|---|---|
| 15 Aug | three `workflow_dispatch` runs succeeded; one produced a data commit |
| 17 Aug | `84c2357` introduced a step declaring both `uses:` and `run:`, making the file invalid |
| 17-18 Aug | every push produced a validation failure and the nightly cron could not fire |
| 18 Aug | `438f78b` restored validity; run 32121112696 succeeded and committed `46c9acc` |

Verified by replaying the file through a YAML/schema check at each commit
that touched it: `84c2357` is invalid, `438f78b` is valid.

The ~197 failures were real and the fix was necessary, but they date from
17 Aug rather than from the workflow's creation. The workflow worked before
that commit broke it.
