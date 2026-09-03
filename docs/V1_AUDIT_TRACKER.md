# V1 Quantitative Audit Tracker

**Repository:** `Pareshking/Umiya`  
**Scope:** V1 only. V2 is intentionally out of scope.  
**Source:** Full quantitative/code audit supplied on 17-Aug-2026, followed by implementation loops and verification.

## Purpose

This document is the living checklist for the original V1 audit. It records what was identified, what has since been changed, what is intentionally unchanged, and what remains to be researched.

The audit is a roadmap, not a requirement to reproduce MSCI/NSE/BSE methodology. Umiya remains a custom research model; institutional methodologies are reference/benchmark models.

---

## 1. Audit scorecard — current status

| Audit area | Original finding | Current status | Action |
|---|---|---|---|
| Mathematical precision / System-1 Sharpe | Period signal-to-noise statistic; not conventional annualized Sharpe | 🟢 Closed by decision | Approved Sharpe mathematics retained; documentation explicitly calls it period risk-adjusted momentum |
| R² in System-1 | Missing-data vulnerability and `Sharpe × R²` dependency | 🟢 Removed | R² removed from the V1 scoring path and stale System-1 documentation |
| Calendar-period definition | Correct principle but legacy trading-row constants remained | 🟢 Closed | 1/3/6/9/12M are canonical calendar horizons; legacy System-1 row-window config removed |
| Benchmark consistency | Benchmark needed to be common | 🟢 Closed | `^CRSLDX` (Nifty 500) is the common V1 benchmark |
| Live/backtest calendar consistency | Live and backtest could use different period definitions | 🟢 Closed | Backtest aligned to the canonical calendar-period engine |
| Monthly rebalance timing | 21 sessions did not equal calendar month | 🟢 Closed | Last trading day T close → first trading day next month T+1 |
| Industry-relative self-inclusion | Peer mean included the stock itself | 🟢 Closed | Leave-one-out industry-relative calculation implemented and regression-tested |
| Winsorization / normalization description | Audit questioned clipping vs winsorization | 🟢 Closed | Current sequence is documented as raw-score outlier control → Z-score → final clipping; no mathematical change required |
| Stock-specific forward-fill | Could manufacture zero returns and smooth signals | 🟢 Closed | Security-specific missing observations remain missing in quantitative calculations |
| Volatility mathematics | Audit noted differing methodologies | 🟢 Closed by decision | User-approved volatility mathematics retained; regression tests lock the convention |
| Portfolio ERC naming | Lower bound means constrained ERC | 🟡 Documentation/research | Ensure UI/docs consistently call it constrained ERC where applicable |
| Volatility targeting | 63-session realized volatility | 🟢 Accepted | Retained as an intentional portfolio-risk convention; not a System-1 period |
| Survivorship bias | Current universe can bias historical results | ⚪ Deferred by decision, now partly measurable | Still deferred. Constituent snapshots have been committed daily since 2026-08-19, so point-in-time membership accumulates from here even though it cannot be reconstructed for earlier months |
| Data history / institutional 3Y replication | Main loader historically around 2Y | 🟠 Open research limitation | Do not claim MSCI replication; consider longer history later if needed |
| Liquidity / implementability | No strong liquidity penalty | 🟠 Open | Audit and decide whether liquidity/tradability controls are required |
| Intermediate momentum | 12–7M vs 6–2M not isolated | 🟠 Research opportunity | Test as a separate Umiya research hypothesis; no production change yet |
| Frog-in-the-Pan | R² was not equivalent to FIP | 🟠 Research opportunity | If desired, test a dedicated continuous-momentum measure; not part of current System-1 |
| Classic month-skip comparison | Current model includes latest month | 🟠 Research opportunity | Compare current no-skip model with 12–1 / 12–2 style alternatives out of sample |
| Institutional benchmark replication | Umiya differs from MSCI/NSE/BSE/AQR | 🟠 Open research | Build benchmark models for comparison, not as a forced replacement of Umiya |
| Portfolio construction vs signal | Signal and portfolio implementation are separate | 🟢 Accepted architecture | Keep alpha signal and portfolio implementation explicitly separated |
| Residual-alpha market proxy | Historical implementation used universe mean if no benchmark | 🟢 Closed by removal | Residual alpha was removed from the engine entirely (see 2.10). There is no call path left to verify |
| Numerical robustness | Alignment/missing-data edge cases | 🟠 Ongoing | Continue targeted synthetic tests as new audit items are closed |

---

## 2. Completed implementation loops

### 2.1 Calendar System-1

**Closed.** System-1 economic horizons are calendar months with actual market observations. Fixed 21/63/126/189/252 row windows are no longer the System-1 period definition.

### 2.2 R² removal

**Closed.** R² is no longer part of the System-1 score. The old `Sharpe × R²` formulation is not the current V1 methodology.

### 2.3 Forward-fill integrity

**Closed.** Security-specific gaps are not converted into synthetic flat-price observations for quantitative returns/volatility. Exchange-wide closure handling remains separate.

### 2.4 Industry-relative leave-one-out

**Closed.** For a multi-stock industry, stock `i` is compared against the mean of valid peer scores excluding `i`. Singleton industries have no peer-relative comparison. Existing ranking semantics for missing values are preserved.

### 2.5 Monthly backtest/live consistency

**Closed.** The backtest uses the same canonical calendar momentum definition as the live System-1 path.

### 2.6 Month-end execution convention

**Closed.** Signal/rebalance occurs at the last available trading-day close of the month. Execution occurs on the first available trading day of the next month.

### 2.7 Common benchmark

**Closed.** `^CRSLDX` is the common V1 benchmark and must remain consistent across modules that require a market benchmark.

### 2.8 Approved volatility methodology

**Closed by explicit decision.** The existing session-based portfolio/risk mathematics is retained. The audit work added regression coverage rather than changing the approved mathematics.

### 2.9 Root momentum-window cleanup

**Closed.** The old root `MOMENTUM_WINDOWS = [21, 63, 126, 189, 252]` definition was removed. `MOMENTUM_MONTHS = [1, 3, 6, 9, 12]` is the canonical System-1 configuration.

### 2.10 Removal of the four alternative systems, MVO and Delivery

Vectorized Exp-Regression, Residual / Idiosyncratic Alpha, Industry-Relative
Momentum and Momentum Acceleration were removed, together with the
Multi-Strategy Overlay tab, Mean-Variance Optimization and Delivery
Accumulation. None of the ranking systems ever fed the composite Rank; each
carried its own failure modes (MVO silently degraded to Equal Weight while
still reporting itself as MVO — audit F1; residual alpha reached out to Yahoo
mid-calculation). `tests/test_removed_systems_stay_removed.py` asserts their
absence so a stray reference cannot resurrect a half-wired feature.

This closes the residual-alpha benchmark-consistency item by removal rather
than by verification.

### 2.11 Completed-month reporting window

The backtest reports the last six COMPLETED calendar months; the month in
progress is excluded, and rebalances are filtered on the execution date (T+1).
A part-month return beside whole ones invites a false comparison and moves
every session. Open positions are marked at the window's last session, not at
the latest close, so the blotter cannot show a return over a period the equity
curve never covered.

### 2.12 Current book and this month's changes

The window exclusion left the holder of the portfolio with no view of what they
hold or what changed. The Backtest tab now shows the book as it stands AFTER
this month's fill, plus a SOLD / BOUGHT / HELD list with the reason for each.

Two corrections were made here worth recording:

- The month's rebalance was initially treated as **pending**. It is not: it is
  signalled on the last session of the previous month and fills on the first of
  the current one, so it has always executed by the time the page is read. The
  "current" book was therefore showing the previous month's portfolio.
- Ranks displayed beside holdings are struck at the rebalance signal date, not
  live, and are labelled "Rank at Rebalance" accordingly.

### 2.13 Append-only track record

`data/track_record.json` records what the strategy posted, month by month, from
January 2026 against Nifty 500. A closed month is frozen once and never
recomputed; months are marked `recorded` or `backfill` by origin. See
`docs/TRACK_RECORD.md`.

### 2.14 Test isolation — shipped data

The sync tests redirected the meta file to a temp path but left `INDICES_LOCAL`
pointing at the real `data/indices/*.csv`. A faked-successful sync therefore
overwrote the tracked constituent lists with fixture rows
(`Co 0,Financial Services,SYM0,...`), and a routine `git add -A` shipped them —
NIFTY NEXT 50 reached `main` holding 40 symbols that do not exist, so every
screen and backtest on NIFTY TOTAL MARKET silently lost 50 real constituents.

Fixed by sandboxing `INDICES_LOCAL` into `tmp_path`, plus
`tests/test_shipped_index_data_is_real.py` to fail loudly if placeholder
symbols or ISINs appear in a shipped list again. This also cleared five
sweep-holdout failures that had looked unrelated: they ran after the sync tests
in the same session and were scoring against the corrupted universe.

### 2.15 DUMMY placeholder filter, now tested

NSE ships DUMMY rows in its constituent files for corporate actions in flight
(four in NIFTY TOTAL MARKET as of Sep 2026). `indices_loader` discards them, so
the real universe is 750 against a 754-row file — but that filter had **no test
at all**. The brittle `== 752` raw row-count assertion, which failed on any
index revision and counted rows the app never uses, was replaced with a
behavioural test of the filter and a plausible-range completeness check.

### 2.16 Modern Streamlit UX patterns

Four modern Streamlit primitives were adopted to reduce full-page reruns,
surface information without page-scroll jumps, and give structured progress
feedback:

- **`st.dialog()`** — the screener's single-stock drilldown now opens as a
  full-screen modal (`width="large"`). The function is defined at module level
  in `ranking_view.py` and called with all price data at click time. The
  underlying screener table stays visible; the modal is dismissible.

- **`st.fragment()`** — the entire Backtest tab body is wrapped in a fragment.
  Backtest controls (walk-forward sliders, holdout toggle) rerun only the
  backtest body, not the screener or any other tab. Config-weight changes
  still trigger a full rerun because the weights are read at `app.py` top level
  and passed as arguments to the fragment.

- **`st.popover()`** — a column-definition guide appears as a floating popover
  on the screener toolbar (5th column in the Tier-2 controls). The Config tab's
  Momentum Signal section has a second popover explaining each lookback window.

- **`st.status()`** — the app startup block (`app.py`) and the constituent-sync
  button (`config_view.py`) now use `st.status()` instead of `st.spinner()`.
  Both show a running state with a step message, then update to complete/error
  with the result label. The `.write()` step inside the startup block uses
  `st.write()` (no-runtime-safe); the `.update()` call is guarded with
  `is not None` so the test suite, which imports `app.py` without a Streamlit
  runtime, continues to pass.

Table rendering was reviewed at the same time. `st.column_config` was adopted
for the backtest parameter-sweep table (already using `st.dataframe`) but not
for other secondary tables: those all use `render_saas_table` (custom HTML),
which supports per-cell conditional coloring that `column_config` cannot
replicate. The main screener table was not changed.

The screener search bar was extended with a `[TV_INDUSTRY]` prefix option
(alongside the existing `[INDEX]`, `[INDUSTRY]`, `[SECTOR]` prefixes), and the
stock-chart overlay panel gained a Nifty 500 benchmark option.

---

## 3. Important distinctions to preserve

### Calendar horizon vs statistical sample vs annualization

These are three different concepts:

1. **Economic horizon:** e.g. 6 calendar months.
2. **Statistical sample:** all valid daily observations inside that interval.
3. **Annualization:** only where a portfolio/risk statistic intentionally requires annualization.

Do not collapse these into one generic variable called `window`.

### System-1 vs portfolio risk

System-1 uses calendar horizons. Portfolio risk calculations may intentionally use session counts such as a short realized-volatility window. The existence of a session-based risk window is not evidence that System-1 should return to trading-row momentum periods.

### Umiya vs institutional indices

MSCI/NSE/BSE/AQR methodologies are comparison/reference models. Umiya is not required to reproduce them. Deviations such as the five-window 10/30/30/20/10 weighting and latest-month inclusion are research choices that should be validated empirically rather than silently presented as institutional methodology.

---

## 4. Remaining work — ordered queue

### ~~NEXT 1 — Residual-alpha benchmark consistency~~ 🟢 Closed by removal

Residual alpha no longer exists in the engine (see 2.10), so there is no call
path to verify. Closed without action.

### NEXT 2 — Liquidity / implementability audit 🟠

Audit liquidity filters, stale prices, bid/ask/impact assumptions, circuit-limit exposure and whether smaller NSE securities can realistically be traded at the assumed transaction cost.

**Acceptance:** explicit methodology decision; no change unless evidence requires it.

### NEXT 3 — Data-history limitation 🟠

Determine whether V1 needs more than the current available history for institutional comparisons and covariance/regime research. Do not alter the current signal merely to imitate MSCI's 3-year weekly volatility.

### NEXT 4 — Intermediate momentum research 🟠

Test separate 12–7M and 6–2M components inspired by the Novy-Marx result. This is research, not a production fix.

### NEXT 5 — Latest-month / classic momentum comparison 🟠

Compare the current no-month-skip formulation with a month-skip alternative out of sample.

### NEXT 6 — Dedicated Frog-in-the-Pan research 🟠

If useful, test a direct continuous-momentum measure against the current System-1 signal. Do not reintroduce R² merely to approximate FIP.

### NEXT 7 — Institutional benchmark models 🟠

Build clean comparison implementations for MSCI-style and NSE-style momentum so Umiya can be evaluated against them without replacing the Umiya signal.

### NEXT 8 — Numerical robustness sweep 🟠

Continue synthetic tests for missing observations, short histories, ties, singleton groups, constant prices, duplicate dates and index alignment.

---

## 5. Explicitly deferred / not in scope

### Survivorship bias ⚪

Historical point-in-time constituent reconstruction remains deferred by explicit
user decision.

Two facts recorded since that decision, neither of which reopens it:

1. The daily sync has committed constituent snapshots since **2026-08-19**, so
   git now accumulates real point-in-time membership going forward. Earlier
   months cannot be reconstructed — the data does not exist.
2. The track record's **backfilled** months (Jan–Jul 2026) are therefore scored
   against September 2026 membership. The bias direction is known — index
   additions skew toward recent strong performers, which a momentum screen
   preferentially buys — but its **magnitude is not measured and must not be
   asserted**. The `origin` field marks which months are affected.

### V2 ⚪

V2 is outside this audit. Do not modify or redesign V2 as part of this tracker.

### Sharpe mathematics ⚪

The approved System-1 Sharpe methodology is not to be changed unless the user explicitly reopens that decision.

### Volatility mathematics ⚪

The approved portfolio/risk volatility mathematics is not to be changed merely to match an institutional index methodology.

---

## 6. Final acceptance rule for each loop

A loop is only **closed/green** when:

1. the actual current code path has been inspected;
2. the intended change is implemented, or explicitly documented as intentionally unchanged;
3. targeted regression tests pass;
4. the relevant full test suite/CI is green;
5. documentation reflects the resulting mathematics and implementation; and
6. the tracker status is updated.

Never mark an audit item closed based only on a planned change or an unverified commit.

### NEXT 9 — Raw-price rebuild ⚪ (parked, not started)

Store unadjusted OHLCV prices and apply corporate-action adjustments at read
time instead of relying on Yahoo Finance's retroactively-mutable adjusted
series.

**Why:** Yahoo rewrites the entire price history backwards whenever a stock
splits or demerges. A price on 2024-01-15 stored today may differ from the
same cell stored next month if a new event triggers a retroactive revision.
The track record's frozen months were struck against whatever numbers were
current at freeze time; a re-run against revised prices would produce different
rankings for the same month. Demergers are never correctly adjusted by Yahoo —
they appear as large phantom losses that the current `adjust_prices()` workaround
can only neutralise after a human records the correct ratio.

**Foundation already built:**
- `src/engine/corporate_actions.py` — `adjust_prices(raw, events)` applies the
  log at read time, in memory, without touching stored files.
- `data/corporate_actions_log.json` — 12 events recorded (splits, demergers).
- `scripts/check_corporate_actions.py` — surfaces new events for human review.

**Implementation scope (when approved):**
1. `scripts/sync_data.py` — download with `auto_adjust=False`; save as
   `prices_raw.parquet`.
2. `src/loaders/price_loader.py` — load raw file; call `adjust_prices()`;
   fall back to existing adjusted snapshot if raw is absent.
3. `src/core/config.py` — add `USE_RAW_PRICES`, `PRICE_RAW_ASSET`, `PRICE_RAW_URL`.
4. `.github/workflows/daily_sync.yml` — publish `prices_raw.parquet` as a
   release asset alongside `prices.parquet` and `prices_full.parquet`.

**Why all stocks, not just the 12 flagged ones:** The price matrix is a single
DataFrame. You cannot mix raw and adjusted columns — a 4:1 split would make
that stock's prices 4x lower than its neighbours, corrupting every cross-
sectional rank. The download flag (`auto_adjust`) is per-batch, not per-ticker.
Stocks with no log entry receive no adjustment — same as today.

**Cost:** slightly larger parquet file; one extra function call in the loader
(already written); manual ratio curation for new events from NSE circulars;
one-time re-download migration (fallback means no outage).

**Full design:** `docs/RAW_PRICE_REBUILD.md`

**Decision gate:** Do not start until the user says proceed.
