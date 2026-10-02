# UI / data overhaul: findings and plan

_Raised by the owner 1 Oct 2026. Status: **AWAITING APPROVAL.** No code has been changed._

Findings were checked against the code at `d5bbacf`. "Evidence" gives the file
so each item can be verified. Items are grouped into work packages (WP) that can
ship as separate PRs; the order at the bottom is the proposal.

## 0. Root causes (why so many small defects)

1. **Two parallel renderers for the same thing.** Portfolio "Current book"
   (`portfolio_view.py`, variant `portfolio`) and Backtest "Current book"
   (`backtest_view.py:306`) build the same table separately, so fonts, columns
   and behaviour differ. Same for Portfolio vs Track Record (calendar grid, equity).
2. **Mixed chart stacks.** Altair (Portfolio equity, Breadth), a second chart stack (RRG,
   correlation), ECharts (heatmap), Lightweight Charts (stock page only).
   Altair has hover tooltips but no crosshair or all-series readout.
3. **No shared type scale.** `theme.py` is 2,991 lines of per-view CSS; fonts
   differ per view. Needs one token set (family, sizes, numerics) used everywhere.
4. **Headings invented per page** instead of a finance vocabulary.

## WP1. Design foundation (do first; everything depends on it)

| # | Item | Evidence / fix |
|---|---|---|
| 1.1 | One typography + spacing token set (UI font, one mono for numerics, 4 sizes). Delete per-view font overrides | `theme.py`; audit every `font-family`/`font-size` outside tokens |
| 1.2 | One stock table component used by Screener, Portfolio, Backtest book, Watchlist, Qualified; views differ only by column set | `screener_table.py` (Executive look is the reference). Remove `render_saas_table` variant `portfolio` |
| 1.3 | Remove every "Table / Grid" toggle and the `st.dataframe` grids (Screener, Portfolio, stock page). Filter and sort sit inline with other controls | `ranking_view.py:341,482,549`, `portfolio_view.py:478-506`, `page_kit.stock_grid_config` |
| 1.4 | Mobile pass: no dead space between label and bar (exposure list), tables scroll, controls wrap | `kit.bar_list` |
| 1.5 | Heading and label glossary (below, §WP9) applied once | all views |

## WP2. One chart system

| # | Item |
|---|---|
| 2.1 | **Recommendation: TradingView Lightweight Charts everywhere** (already on the stock page, you rate it). Extend `lightweight_chart.py` to line, area, histogram, baseline and multi-series with crosshair and legend values. |
| 2.2 | Replace: Portfolio/Track Record equity and drawdown (merged into one chart, see WP4), Breadth participation and highs/lows, Sector/RRG trails where feasible. |
| 2.3 | Crosshair shows date + every series value on hover/touch. Same colours and pointer styling on every page |
| 2.4 | Keep a separate library only for RRG scatter and correlation heatmap unless Lightweight cannot do them (it cannot: scatter). Style those to the same tokens |
| 2.5 | Caveat (Opus review): the app uses the third-party `streamlit-lightweight-charts==0.7.20`, not its own component. "Multi-pane" there is stacked separate charts (`lightweight_chart.py:271-292`); the wrapper has no value legend or crosshair callback; and the fallback only catches Python exceptions, so a browser-side load failure still renders blank. **Prototype first** (multi-series, legend with values, drawdown pane); if the wrapper cannot do it, write a small own component (`components.html`/declared component) with the Lightweight Charts JS, which also removes the silent-failure risk |

**Decision needed (D1):** confirm Lightweight Charts as the standard. Alternative
considered: ECharts (richer, heavier, weaker finance feel). Recommend Lightweight.

## WP3. Portfolio page

| # | Item | Evidence |
|---|---|---|
| 3.1 | Current book = the shared stock table (WP1.2) with a trimmed column set: drop 3M/6M/12M returns (keep 1M), drop **Status** (always "Held": `build_portfolio_tracker`) | `portfolio_view.py:~620` `display_cols` |
| 3.2 | Current exposure: compact rows, bar next to the name, % at the right; sorted; works at 360 px | `kit.bar_list` |
| 3.3 | **Rebalance history stops at Aug 2026 (verified).** `months_to_cover` (`track_record.py:534-541`) asks for completed months only and the window ends there (`backtester.py:305`). The 1 Sep fill lives only in `change_rows` -> `month_changes` (`backtester.py:1364,1501`), never in `trade_records`/`tradebook`. Append `month_changes` to the tradebook, and each later month as it closes | `build_portfolio_history` -> `record["tradebook"]` |
| 3.4 | **Trades: "Still open" is empty (verified root cause).** The engine does add open positions to `closed_trades` (`backtester.py:1140-1158`) but the `stateful_history` filter at `backtester.py:1470-1474` drops them: open rows have `Exit Date = "Not exited (mark ...)"`, which parses to NaT, and NaT >= window_start is False. `record_run` keeps NaT on purpose (`track_record_view.py:99-101`), so the engine undoes it. **Fix in the engine (keep NaT rows) + regression test**; this also fixes Backtest's own "Still open". Open rows are marked at window end (end of Aug), so mark them from the live book. The 1 Sep closes exist only in `month_changes`; add them | `backtester.py:1140-1158,1470-1474` |
| 3.5 | Reuse the Backtest views (book, changes, trades, rebalance log) instead of Portfolio's copies. Same code for both pages | `backtest_view.py:284-` |
| 3.6 | Single page, no segmented tabs: Snapshot -> Equity + drawdown -> Calendar grid -> Current book -> Exposure -> Trades -> Rebalances (sections, with filters inline) |
| 3.7 | Equity and Drawdown in **one chart** (equity on top, drawdown pane below); removes a tab |
| 3.8 | Monthly view uses Track Record's calendar grid (one component) |
| 3.9 | Delete verbose lines: "Marked 30 Sep 2026 · 20 positions · 99.2% invested · ₹1,976,777 invested", "Inception · Jan 2026 · ₹2,000,000 starting capital · 8 completed months", "performance history · latest month marked...". Keep only facts not shown elsewhere; invested amount appears once | `portfolio_view.py:617,689-699,717` |

## WP4. Track Record vs Portfolio (merge)

Track Record has the best design; Portfolio shows the same ledger.
**Proposal:** one **Portfolio** page that owns the model portfolio's whole story
(live book + record). Track Record's calendar grid, month cards and the
"three systems side by side" panel move into it as sections; the Track Record
page is removed, with a redirect (`_MOVED` already exists in `app.py`).
Backtest stays separate: it is the *what-if* with adjustable parameters; Portfolio
is the *actual* recorded model. Shared components, no duplicated figures.

**Decision needed (D2):** merge (recommended) or keep Track Record as its own page?

## WP5. Screener

| # | Item | Evidence |
|---|---|---|
| 5.1 | Row sub-line (company · industry · index) is built (`screener_table.py:104-118`, class `sub`) but you never see it. Root cause to find first (missing `Company Name`/`Industry`/`Indices` columns in the frame, or CSS hiding `.sub`); then show it in every density | `screener_table.py:104-118`, `theme.py` |
| 5.2 | **One table, several column sets.** Full Quant = reference, Core and Executive are subsets of it (single column registry). Add any column Core/Exec show that Quant lacks (Filters, 52W high, etc.). Executive typography becomes the base for all | `_CORE`, `_EXEC_KEYS` |
| 5.3 | Sharpe columns only in Quant view. Core/Executive show **3M DD**, not 12M DD. Quant keeps all-period DD | `screener_table.py:41-42` |
| 5.4 | Add **Top 50 Not Qualified** preset next to Top 50 Qualified | `ranking_view.py preset_counts` |
| 5.5 | New columns **New highs 1M** and **New highs 3M**: count of sessions that closed at a new 52-week high within the last calendar month / 3 months (your example: 15 Jul, 15 Aug, 19 Aug -> 3). Computed from prices; definition below | engine: new function in `breadth.py` |
| 5.6 | Top-50 movers: three tabs in one card: **Biggest jumps** (top 10 by rank gain, e.g. "SUNTV +514, #724 -> #210"), **Entered Top 50**, **Left Top 50**. Titles drop the month name (it is "since last month-end", dynamic). Keep the single headline signal chip | `ranking_view.py:619`, `components.py:69` |
| 5.7 | Footer: delete "Returns exclude dividends" | `components.py:605` |
| 5.8 | Nav order: Screener, **Portfolio**, **Actions**, then the rest | `app.py:1187` |

**Definition (5.5)** needs your OK: "new high" = close >= highest close of the
prior 252 sessions, counted per session in the window. Count, not distinct episodes.

## WP6. Market Breadth

| # | Item |
|---|---|
| 6.1 | Rebuild both charts on Lightweight Charts (WP2) with crosshair values |
| 6.2 | New highs vs new lows: two histograms mirrored around zero in one pane, plus the net line; or net new highs as a single baseline series. Today's Altair bars are unreadable at ~750 sessions |
| 6.3 | Participation chart: lines for 20/50/100/200 with 40% / 60% reference lines, readout on hover |
| 6.4 | Re-check all chart pointers and tooltips across pages after WP2 |

## WP7. RRG and Configuration wording

| # | Item | Evidence |
|---|---|---|
| 7.1 | "By quadrant / strongest first · RS-ratio · RS-momentum / Leading7 · ratio · momentum" -> section "Quadrants", columns **RS** and **Momentum**, count as a badge, not glued to the name | `rrg_view.py:210,387` |
| 7.2 | RRG benchmark: today options are three invented equal-weight baskets (loaded universe, top 50 by cap, cap ranks 101-250). Replace with standard index benchmarks: **Nifty 500** (default; same as `BENCHMARK_SYMBOL = "^CRSLDX"`, `config.py:166`, and the portfolio benchmark) and Nifty 50 / Nifty Total Market. Show the chosen benchmark in the page head | `rrg_view.py:23-26,80-88` |
| 7.3 | Configuration "Settings in effect" is a 6-cell strip that wraps into two rows with run-together text ("Data health38 fixedprice jumps neutralised"). One tidy key/value list; consistent units | `config_view.py:515-541` |
| 7.4 | "Data health: 38 fixed / price jumps neutralised": these are corporate actions (splits, bonuses, demergers) the app corrects, not data errors. Rename **Corporate actions adjusted: 38**; link to the list. Screener.in is split-adjusted already; the 38 come from Yahoo's unadjusted demergers and NSE actions (`corporate_actions_log.json`). Verify which source each one comes from, and whether any are still needed once Screener is the price | `corporate_actions.py`, `config_view.py:426` |
| 7.5 | Benchmarks and labels use standard terms (RS, Momentum, Alpha, Drawdown, CAGR, Sharpe, Sortino, Turnover, Benchmark: Nifty 500) |

## WP8. Cross-page text cleanup

Go through every page, keep only what is not visible elsewhere. Rule: **a figure
appears once per page; a caption exists only if it changes a decision.** The
audit list (all to be reduced to <= 1 short line, or removed):
`portfolio_view.py:617,689,692,699,717`; Backtest live-book captions
(`backtest_view.py:306-343`, four stacked captions); Config section
sub-headers; Track Record card sub-titles; Breadth explainer sentences.

## WP9. Heading and label glossary (applied everywhere)

Rank, Score, RS (relative strength), Momentum, Return (1M/3M/6M/12M), Drawdown
(Max DD), Alpha, Benchmark, CAGR, Sharpe, Sortino, Volatility, Turnover, Weight,
Exposure, Holdings, Rebalance, Trades, Equity curve, Calendar returns, Breadth,
New highs / New lows, Net new highs, Advance/Decline. No invented phrases ("Still
open" -> **Open**; "Current-book P&L" -> **Unrealised P&L**; "Price jumps
neutralised" -> **Corporate actions adjusted**).

## WP10. R2 / data management  (needs your approval before any change)

R2 currently holds: `prices/yahoo`, `snapshots/application`, `nse/prices_daily`,
`nse/corporate_actions`, `nse/market_caps`, `nse/source_checks`, screener
history, membership and classification, ranking archives, market-cap history.
Findings from the docs:

| # | Finding | Fix |
|---|---|---|
| 10.1 | No single map of what is stored where, by source/company/date. Layout is described across `MARKET_DATA_ARCHIVE_R2_SPEC.md` (1,568 lines), `R2_ENGINEERING_LOOP.md`, `NSE_DATA_LEDGER.md` | One `docs/DATA_CATALOGUE.md` table: dataset, source, key pattern, grain (per day / per company / per month), history held, writer workflow, reader, retention |
| 10.2 | Config "Data" section takes a large amount of space | Replace by a compact freshness table (dataset, as-of, rows, status) fed by the catalogue |
| 10.3 | Yahoo raw build and NSE vs Yahoo comparison not completed: TODO #3/#4 wait on the owner; `RAW_PRICE_REBUILD.md` is PARKED; ~50 stocks still differ NSE vs Screener | Finish the comparison per source pair (Screener/NSE/Yahoo), publish one report, then decide the price order (TODO #3). Needs D3 |
| 10.4 | Retention is manual or dry-run; growth ~35 MB/day | Apply approved policy on a schedule after a dry run you approve |
| 10.5 | Naming/labels for sources are inconsistent in UI ("Data from", "Prices pill") | Source names fixed: Screener.in, NSE, Yahoo Finance; shown by the catalogue |

**Decision needed (D3):** TODO #3: adopt Screener -> NSE -> Yahoo as the price order (Claude recommends yes).

## WP11. Documents to update on delivery

`docs/TODO.md` (all items here), `docs/UI_ARCHITECTURE.md` (components, chart
stack), `docs/TRACK_RECORD.md` (page merge), `CHANGELOG.md`, `README.md`,
`docs/DATA_CATALOGUE.md` (new), `docs/PARKED_IDEAS.md` (remove Table/Grid note).

## Proposed order

0. **Engine fixes first (small, independent):** keep NaT open-trade rows (3.4) and add the live-month changes to the tradebook (3.3), each with a regression test. Move `record_run` out of `track_record_view.py` into an engine/shared module (`canonical_book.py:41` and Actions import it; WP4 would otherwise break them).
1. WP1 foundation + WP2 chart prototype and component (unblocks everything).
2. WP3 + WP4 Portfolio rebuild with the merge (largest owner pain).
3. WP5 Screener (+ nav order).
4. WP6 Breadth, WP7 RRG/Config wording, WP8/9 text sweep.
5. WP10 data catalogue, then comparison and R2 policy.
6. WP11 documentation at the end of each PR, not only the end.

Each package: its own PR, existing tests plus new ones (rebalance history includes
the latest month; Open trades non-empty; table column registry), and V1 Production
QA on the live app before the next one starts.

## Decisions needed from you

- **D1** Lightweight Charts as the one chart library (recommended)?
- **D2** Merge Track Record into Portfolio (recommended)?
- **D3** Price order Screener -> NSE -> Yahoo (recommended)?
- **D4** "New high" definition in 5.5 (close at a new 252-session high, counted per session)?
- **D5** RRG default benchmark: Nifty 500 (recommended)?
- **D6** OK to start with WP1+WP2 once approved?

## Not covered / limits

- Earlier chat sessions were only partly readable (long logs); the repo's TODO,
  audits and parked-ideas were used as the record of promises. If you remember a
  specific past request not listed here, add it.
- Live-site screenshots were not taken in this pass; visual findings come from
  your description plus the code. WP1 starts with screenshots of every page.
