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
