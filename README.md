# NSE Quantitative Momentum Terminal

Institutional-style quantitative momentum ranking, portfolio construction and
walk-forward backtesting for Indian equities (NSE), with an append-only monthly
track record against Nifty 500.

## V1 quantitative status

The current V1 research model has been hardened against the main mathematical and architectural issues identified in the 2026 quantitative audit. The canonical System-1 signal is now calendar-period based and does **not** use R-squared.

### System-1 — Sharpe Momentum

Five calendar horizons:

- 1 month
- 3 months
- 6 months
- 9 months
- 12 months

For each as-of date, the engine:

1. subtracts the calendar horizon from the as-of date;
2. selects the first available market observation on or after that target date;
3. uses the actual valid daily observations through the as-of date;
4. calculates the approved period risk-adjusted momentum statistic;
5. standardizes the cross-section using the approved outlier-control sequence; and
6. combines the five standardized signals using the configured 10/30/30/20/10 weights.

The approved System-1 Sharpe methodology is intentionally retained. It is a **period risk-adjusted momentum statistic**, not conventional annualized Sharpe, and should not be compared numerically with institutional annualized Sharpe figures.

**R-squared is not part of System-1 and is not used to scale its score.**

### Removed ranking systems

System-1 is the **only** ranking system. Four alternatives — Vectorized
Exp-Regression, Residual / Idiosyncratic Alpha, Industry-Relative Momentum and
Momentum Acceleration — together with the Multi-Strategy Overlay tab, have been
removed.

None of them ever fed the composite Rank. Each produced extra columns and
carried its own failure modes: residual alpha reached out to Yahoo mid-
calculation, making a compute method's cost depend on a third party. Mean-
Variance Optimization was removed from the portfolio engine for the same class
of reason — it silently degraded to Equal Weight on any exception while still
reporting itself as MVO (audit F1). Delivery Accumulation was removed with them.

`tests/test_removed_systems_stay_removed.py` asserts their absence, so a
re-import or a stray column reference cannot quietly resurrect a half-wired
feature.

## Canonical V1 conventions

### Benchmark

The common V1 market benchmark is:

`^CRSLDX` — Nifty 500.

Where a market benchmark is required by a V1 quantitative module, this benchmark should be used consistently unless a module has an explicitly documented reason not to.

### Periods

System-1 uses **calendar months**, not fixed trading-row windows. The legacy 21/63/126/189/252 momentum-window definition has been removed from the root configuration.

Session-based windows may still exist in portfolio/risk components where they are intentionally part of the approved methodology. They must not be reused as System-1 economic horizons.

### Monthly backtest convention

For monthly V1 rebalancing:

- last available trading day of the month = signal/rebalance date at T close;
- first available trading day of the following month = execution at T+1.

The backtester must use the same canonical System-1 calendar-period engine as the live screener.

### Reported backtest window

The backtest reports the last **six completed calendar months**. The month in
progress is excluded: a part-month return shown beside whole ones invites
comparing three weeks against six full months, and it moves every session until
the month closes. Rebalances are filtered on the **execution** date (T+1), so
the rebalance signalled on the last session of the previous month — which fills
on the first session of the current one — falls outside the reported window by
construction.

### Current book and this month's changes

That exclusion leaves the person holding the portfolio with no answer to their
two questions, so the Backtest tab answers them separately, above the
performance tables:

- **Current Holdings** — the book as it stands *after* this month's fill,
  marked at the latest close, with entry date, entry price, unrealised return,
  holding period, weight, and rank drift since entry. Names bought at this
  month's fill carry that fill date and price; retained names keep their
  original entry date, because buffer retention is not a re-entry.
- **This Month's Changes** — SOLD / BOUGHT / HELD with the reason for each. A
  SOLD row reports the realised round trip struck at the fill; BOUGHT and HELD
  rows are unrealised at the latest close.

These marks use the latest close — a date the reported window does not cover —
and feed neither the equity curve, the monthly table, nor the headline stats.

### Missing stock observations

Exchange-wide closures may be removed as holidays. A stock-specific missing observation must **not** be forward-filled for quantitative return/volatility calculations. This prevents synthetic zero returns and artificial smoothing.

### Cross-sectional normalization

The documented pipeline is:

`raw factor -> approved winsorization/outlier control -> Z-score -> final numerical clipping`

The implementation must not describe simple Z-score clipping as raw-score winsorization.

## Portfolio and risk methodology

Portfolio/risk mathematics is intentionally separate from System-1 signal mathematics. Approved session-based risk calculations are not converted to calendar horizons merely because System-1 uses calendar periods.

Examples include realized-volatility targeting, inverse-volatility weighting, covariance estimation and constrained ERC. These retain their approved session counts and annualization conventions.

## Track record

`data/track_record.json` is an **append-only** monthly record of what the
strategy posted, from January 2026, against Nifty 500.

The backtest recomputes from live prices on every run, which is correct for a
backtest and useless as a record: a vendor price revision, an index change or a
nudged slider silently rewrites what January returned. So a closed month is
written **once** and frozen — re-running the updater cannot move a stored
number. Each entry carries the configuration fingerprint that produced it, the
date it was frozen and the price date it was struck from.

Months are marked by origin. **Recorded** months were frozen as they closed,
from the data as it stood then. **Backfilled** months were reconstructed later
from today's universe and prices, so they carry the backtest's biases and are
weaker evidence. Month-to-date is never stored — it moves every session, so it
is computed live and shown beside the frozen months.

See [`docs/TRACK_RECORD.md`](docs/TRACK_RECORD.md) for the full contract,
conventions and operations.

## Research audit tracker

See [`docs/V1_AUDIT_TRACKER.md`](docs/V1_AUDIT_TRACKER.md) for the full audit roadmap, completed corrections, and remaining research tasks.

See [`docs/PARKED_IDEAS.md`](docs/PARKED_IDEAS.md) for features and integrations that were researched and deliberately set aside, with recorded reasoning.

## Core capabilities

Tabs, in the order the app renders them:

1. **Screener**: Full-universe screening with multi-prefix search — `[INDEX]`, `[INDUSTRY]`, `[SECTOR]`, and `[TV_INDUSTRY]` prefixes narrow the view without typing ticker names. Ranking, rank movers, single-stock deep-dive (opens in a full-screen modal dialog), and CSV export.
2. **Qualified**: High-conviction screening and concentration analysis.
3. **Sectors**: Industry rankings.
4. **RRG**: Relative Rotation Graph analysis.
5. **Portfolio**: Equal Weight and Inverse Volatility construction with capital sizing and broker-basket export. Note this is a *top-N snapshot* of the current ranking — it has no persistence buffer and no memory of existing holdings, so it is not the same book the backtest runs.
6. **Watchlist**: Custom portfolio tracking against quantitative rankings.
7. **Market Breadth**: Moving-average breadth and high/low statistics.
8. **Backtest**: Walk-forward backtesting over the last six completed months, rank at T close and execution at T+1, plus the current book and this month's changes. The entire tab runs as an independent Streamlit fragment — its controls rerun only the backtest, not the screener or any other tab.
9. **Track Record**: The frozen monthly record against Nifty 500 — see below.
10. **Configuration**: Index constituents, factor weights, risk parameters and cache diagnostics. Organised as a Windows 11-style left-nav with four sections: *Data & Sync*, *Momentum Signal*, *Portfolio Risk*, and *Data Health*. Each section is rendered on demand; only the active section appears on screen.
11. **Guide**: In-app methodology reference.

## UI patterns

The app uses four modern Streamlit primitives that reduce full-page reruns and noise:

| Pattern | Where used | Why |
|---|---|---|
| `st.dialog()` | Screener stock drilldown | Opens as a full-screen modal so the underlying screener ranking stays visible without a page scroll jump |
| `st.fragment()` | Entire Backtest tab | Backtest controls rerun only the backtest body; Config weight changes still trigger a full rerun via the top-level read in `app.py` |
| `st.popover()` | Screener column guide, Config window guide | Floating reference panel without leaving the current screen |
| `st.status()` | App startup, Config constituent sync | Structured progress with running/complete/error states and collapsible step log |

Table rendering deliberately splits into two tiers:
- **Main screener** and **all secondary tables** (live book, monthly returns, closed trades, sector breakdown, track record): custom HTML via `render_saas_table` in `src/ui/theme.py`, which supports per-cell conditional coloring that `st.column_config` cannot replicate.
- **Backtest parameter sweep**: `st.dataframe` with `column_config` for progress bars on numeric columns; no per-cell coloring needed there.

## Data integrity

- Exchange-wide closure rows are filtered using the existing holiday-detection rule.
- Security-specific missing observations remain missing for quantitative calculations.
- Short-history securities are masked where the required statistical sample is unavailable.
- Data-gap diagnostics remain available to identify problematic securities.
- NSE ships **DUMMY placeholder rows** in its constituent files for corporate actions in flight (four in NIFTY TOTAL MARKET as of Sep 2026, e.g. `DUMMYTRVN`). Any symbol beginning `DUMMY`, shorter than two characters, or literally `NAN` is discarded by the loader, so the real universe is smaller than the raw row count. These placeholders have no price history; ranking one could put an untradeable ticker in the portfolio.

## Project structure

```text
├── .github/workflows/   # daily data sync, monthly track-record freeze, QA probes
├── .streamlit/
├── data/
│   ├── indices/             # NSE constituent snapshots (committed by the daily sync)
│   └── track_record.json    # append-only monthly record
├── docs/
├── scripts/             # sync_data, update_track_record, QA probes
├── src/
│   ├── core/
│   ├── loaders/
│   ├── engine/          # momentum, backtester, portfolio, track_record
│   └── ui/views/
├── tests/
├── app.py
├── requirements.txt
└── README.md
```

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Disclaimer

Educational and research use only. Not financial or investment advice.
