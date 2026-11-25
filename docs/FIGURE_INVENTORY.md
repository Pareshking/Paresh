# Figure inventory: every page (S154 (a); Dashboard, Portfolio and Actions 21 Nov 2026, the other pages 24 Nov 2026)

Every figure that appears on more than one of the three pages, the one function that
makes it, the series it reads, and the test that keeps the pages from drifting apart.
Figures shown on one page only are listed in that page's requirements file
(`docs/DASHBOARD_REQUIREMENTS.md`, `docs/PORTFOLIO_REQUIREMENTS.md`,
`docs/ACTIONS_REQUIREMENTS.md`, which also carries Actions' own inventory).

Rule (S148, S154 (c)): an index figure ends on the page's session or reads "—"
(`dashboard_insights.as_of`); a page that is a session behind on any series says so.

| Label (as shown) | Pages | Made by | Reads | Test |
|---|---|---|---|---|
| Portfolio value, uninvested | Portfolio, Actions (basket and cash) | `ui.book_series.book_series` | the record's frozen months + the live month, prices clipped to the record's as-of | `tests/test_book_series.py` |
| Since inception, after costs; Nifty Total Market since inception | Dashboard, Portfolio | `build_portfolio_history` (book), `window_return` / `portfolio_report.ret` (market), on the same as-of | ledger + live month; `data/benchmark_indices.csv` | `tests/test_book_series.py` |
| Month so far, and the market's | Dashboard, Portfolio | `build_portfolio_history` (Dashboard its `strategy_mtd`, Portfolio its monthly grid's live row); the market by `window_return` / `month_returns` from the month-end on or before | ledger + live month; `data/benchmark_indices.csv` | one function for the book; 21 Nov screenshots agree (+5.8%, +9.8%) |
| Below its peak today | Dashboard, Portfolio | `metrics.drawdown` on `book_series.equity` | the daily book series | `tests/test_book_series.py`, `tests/test_drawdown_is_one_helper.py` |
| Volatility, a year; beta | Dashboard, Portfolio | `portfolio_report.risk(equity, market)` | book series against Nifty Total Market | `tests/test_same_label_same_value.py` |
| Weight now, by holding, industry and size | Dashboard, Portfolio, Actions ("Now") | Portfolio's holdings table `Weight %` (value over the book's value today) | `book_series.table` | `tests/test_same_label_same_value.py` (sources); 21 Nov: Healthcare 29.4% on all three |
| Rank: 3M · 1M · now | Dashboard, Portfolio, Actions | `dashboard_insights.rank_trails(..., now=qualified_ranks(rank_df))` | rank_history snapshots; today from the published ranking | `tests/test_same_label_same_value.py` |
| Distance from the 50D EMA and from the 52W high | Portfolio, Actions, Dashboard (rule text) | ranking columns `% 50 EMA`, `% High` (`exit_watch.assess`) | the published ranking | `tests/test_same_label_same_value.py` |
| Return since entry | Portfolio, Actions | entry price and today's price (`build_portfolio_tracker`; the record's `Return %`) | same daily prices | 21 Nov check: all 20 holdings agree |
| Sells, buys, holds, next in line, target weights | Dashboard, Actions | `ui.model_plan.model_plan` | the published ranking, the book with its fill date | `tests/test_model_plan_one_source.py` |
| Next rebalance, sessions away, fill day | Dashboard, Actions | `actions_view.next_rebalance`, `_sessions_between` | NSE's published holidays | `tests/test_exit_watch.py` and the Actions tests |
| Domestic institutions this month | Dashboard (tile, headline, chart) | `dashboard_home_view._dii_months` | `data/nse_dii.csv` | `tests/test_nse_dii.py` |
| Foreign investors this month | Dashboard | `flows_summary` | `data/nsdl_fpi_daily.csv` | existing flows tests |

## Shared with Market, Sectors, Screener and Indices (added 21 Nov 2026)

The four pages redesigned after S154 (a) share these figures with the three above or with each other.
Read from the code on 21 Nov 2026. Market's own list of shared figures is in `docs/MARKET_REQUIREMENTS.md`.

| Label (as shown) | Pages | Made by | Reads | Test |
|---|---|---|---|---|
| Qualified # (place among the stocks that pass both filters) | Screener, Sectors ("Stocks in an industry"), Actions, and the "now" of the rank trail on Dashboard and Portfolio | `exit_watch.qualified_ranks` (`ranking_view.py:490`, `sector_view.py:352`, `actions_page.py:409`) | the published ranking | `tests/test_same_label_same_value.py`, `tests/test_exit_watch.py` |
| Industry names (FMCG, Auto, Durables) | Dashboard, Portfolio, Sectors, Screener (Actions not checked) | `ui.industry_names.INDUSTRY_SHORT` / `short_industry` | NSE's industry | `tests/test_screener_redesign_2026_11_21.py` (`test_one_industry_map_for_every_page`) |
| Share above the 200D EMA, on each date's members | Market, Dashboard | `pit_breadth.splice(mq._share_above_ema(...))` (`market_questions_view.py:201`, `dashboard_home_view.py:196`) | daily prices; the recorded members of each date | `tests/test_pit_breadth.py` |
| Size indices against the market | Market (By size), Sectors (By size), Dashboard §5 | `data/benchmark_indices.csv` through `loaders.benchmark_indices`, cut at the page's session; Sectors reads them against `market_questions_view.total_market()` | `data/benchmark_indices.csv`, `data/nse_total_market.csv` | none found that compares the pages; Market and Sectors both read `benchmark_indices.csv` since 21 Nov (BREADTH_REQUIREMENTS row 12, SECTORS_REQUIREMENTS row 12) |
| Nifty 500 P/E percentile since 31 Mar 2021; styles leading and trailing their parents over 12 months | Indices, Dashboard (At a glance, "Valuation and styles") | `engine.indices_page.valuation`, `styles`; the Dashboard through `indices_glance_rows`, on its own session (`Frames.until`) | `data/nse_indices_history.parquet` + `data/nse_indices_recent.csv` (`ui.indices_data.frames`) | `tests/test_indices_page.py` (`test_the_dashboard_card_reads_the_same_figures`) |
| Large caps = Nifty 100 | Dashboard §5, Indices | Dashboard `SIZE_LISTS`/`SIZE_LABELS` (`dashboard_home_view.py:45-56`); Indices `indices_page.SIZES` (`nifty_100`) | NSE's index lists and closes | none found |

## The other pages, one table each (S154 (a), 24 Nov 2026)

Read from the code on 24 Nov 2026 (main `d2c3540`). Every page cuts each series at its own session,
the one in its header (`formats.session_of`; S148, S193 E), so a series that runs past it shows the
page's session. Tests for the shared rows: `tests/test_same_label_every_page.py` (S154 (b)).

Last rows in the checkout on 24 Nov: `data/benchmark_indices.csv`, `data/nse_total_market.csv`, NSE's
index store (`data/nse_indices_history.parquet` + `nse_indices_recent.csv`), `data/benchmarks.csv`
(Nifty 500), `data/nse_market_caps.csv` and `data/nsdl_fpi_daily.csv` 23 Nov; `data/breadth_history.csv`
(members-of-the-day breadth) 20 Nov; `data/nse_dii.csv` 19 Nov. The ranking (`rank_df`) and the price
frames come from R2 and end on the published ranking's session (20 Nov on the live site, S193 A).

### Sectors

| Label (as shown) | Made by | Reads | Also on | Test |
|---|---|---|---|---|
| Each sector's lead over the 750, 6M and 1M (now, 1M and 3M ago); "ahead on both" | `sectors_page.leads` (`peer_index.relative_points`, equal-weighted) | daily ranking frame (`daily_history.frame`); `rank_df` Industry | Dashboard sector cards (S193 A: all 12 agreed) | `tests/test_sectors_page.py` |
| "Nifty Total Market rose 8.8%" (lede) | `ld.market_ret[1] - ld.gap["1"]` (`peer_index.size_gap`), printed `:.1f` | `market_questions_view.total_market()`: `nse_total_market.csv`, then `benchmark_indices.csv` after its last row | Indices, Dashboard, Portfolio, stock page | value: `test_total_market_window_returns_agree...`; rounding: strict xfail (difference 2 below) |
| The 750, equal-weighted, 1/3/6/12M | `sectors_page.ew_return` on `peer_index.equal_weight_level` | ranking frame | Dashboard "three ways" (`typical_stock`) | one function (`peer_index`) |
| Share above the 200D EMA, all ranked stocks and each sector, now / 1M / 3M ago | `sectors_page.ema_shares` (today's members throughout, said in the headline) | ranking frame | Market, Dashboard (members of each date for the past) | `test_share_above_the_200d_ema...`; `test_with_the_members_history...` (S193 A10, decided) |
| NSE sector indices: returns, from the 12M high, P/E | `sectors_page.sector_indices`, `broad_or_narrow`, `from_high` | NSE's index store | Indices | `test_from_the_52w_high_agrees...` |
| Month by month, each sector less the 750 | `market_questions.industry_months` | ranking frame | Market (leaders) | one function |
| Qualified # in "Stocks in a sector" | `exit_watch.qualified_ranks` | `rank_df` | Screener, stock page, Watchlist, Actions | `test_the_qualified_count_and_place...` |

### Market

| Label (as shown) | Made by | Reads | Also on | Test |
|---|---|---|---|---|
| Nifty 500 against its 200D EMA, now and a month ago | `market_questions.ema_gap` (`trend_answer`, size table) | `fetch_benchmark_history("5y")` (`benchmarks.csv`) | header strip (`price_loader.get_market_regime`, whole history), Dashboard signal row | `test_nifty500_against_its_200d_ema...` |
| Nifty 500 against its 10-month average; the month-end reading | `ten_month_today`; `ten_month_gap`, `last_month_end` | the same | Dashboard signal row | `test_nifty500_against_its_10_month_average...` |
| Nifty 500 and size indices from the 52W high | `market_questions.from_high` (a calendar year) | the same; sizes from `benchmark_indices.csv` | Indices "From 12M high"; Dashboard "Sharp rebound" | `test_from_the_52w_high_agrees...`; Dashboard: strict xfail (difference 1) |
| Share above the 200D and 50D EMA; net new highs | `pit_breadth.splice(market_questions._share_above_ema / _net_new_highs)` | ranking frame on `rank_df`'s symbols; `breadth_history.csv` | Dashboard, header (50D count), Sectors | `tests/test_pit_breadth.py`, `test_share_above_the_200d_ema...` |
| Share beating Nifty Total Market over 12M; median stock less it | `market_questions._beat_index_12m` (last close in the week to each date) | ranking frame, `total_market()` | Dashboard "three ways" (`typical_stock`, the exact session) | `test_the_12m_beat_share...`, `test_the_12m_figures_differ...` (S193 A11, open for the owner) |
| Which sectors lead | `market_questions.leaders_answer` | ranking frame, Nifty 500 | Sectors (`sectors_page.leads`, against the 750) | not compared: another benchmark, named on each page |

### Indices

| Label (as shown) | Made by | Reads | Also on | Test |
|---|---|---|---|---|
| Every index: 1/3/6/9/12M return, from the 12M high, P/E | `indices_page.every_index` (`ret`: last session on or before) | NSE's index store (`ui.indices_data.frames`) | Dashboard, Portfolio, Sectors, Market | `test_total_market_window_returns...`, `test_the_index_files_the_pages_read...` |
| Nifty 500 P/E percentile; styles' 12M lead | `indices_page.valuation`, `styles` | the same | Dashboard "Valuation and styles" | `tests/test_indices_page.py` |
| Size by calendar year | `indices_page.size_years` | the same | none | - |

### Stock page (`/screener?stock=`)

| Label (as shown) | Made by | Reads | Also on | Test |
|---|---|---|---|---|
| Close, 1M and 12M return, rank, rank 3M ago, market cap | `rank_df` (`CMP`, `{m}M Return`, `Rank`, `Rank (-3M)`, `Market Cap (Cr)`) | the published ranking | Screener, Watchlist | `test_a_stocks_12m_return...` |
| Place among the qualified, "of N" | `exit_watch.qualified_ranks`, its length | `rank_df` | Screener ("Pass both filters"), Sectors, Watchlist, Actions | `test_the_qualified_count_and_place...`, `tests/test_qualified_place_same_everywhere.py` |
| Qualified 3M and 1M ago | `ranking_view.with_book_columns` (`qualified_trail`) | deep closes | Screener, Watchlist, Dashboard, Portfolio, Actions | `tests/test_qualified_place_same_everywhere.py` |
| Nifty Total Market over the stock's window; "against +x% for Nifty Total Market" | `stock_lines.windows`, `market_return` (start on or after the date back) | `benchmark_indices.csv` | Indices, Dashboard, Portfolio (start on or before) | `test_the_stock_page_starts_its_market_window_on_or_after...` (STOCK row 29, S193 A9) |
| Typical stock (median of the ranked stocks' {m}M Return) | `stock_lines.windows` | `rank_df` | Dashboard's median stock (from prices, on or before) | differ by the window rule (S193 A9) |
| From the 52W high; distance from the 50D EMA | `rank_df` `% High`, `% 50 EMA` | the ranking | Portfolio, Actions | `test_a_stocks_12m_return...`, `tests/test_same_label_same_value.py` |
| In the model book: return since entry, weight | `stock_view._holding` (Portfolio's table) | deep closes, the record | Portfolio, Actions | `tests/test_book_series.py` |

### Screener and Watchlist

The Watchlist draws the Screener's table (`render_screener_table` on `with_book_columns`) for the
names saved, so every column is the Screener's; its plan lines are `ui.model_plan` (Dashboard, Actions).

| Label (as shown) | Made by | Reads | Also on | Test |
|---|---|---|---|---|
| Rank, rank 1M and 3M ago, returns, filters, Sharpe, falls | `rank_df` columns | the published ranking | stock page, Sectors, Watchlist | the same columns |
| Qualified #, qualified 3M and 1M ago, Held | `with_book_columns` (`qualified_ranks`, `qualified_trail`, the record's book) | ranking, deep closes | stock page, Watchlist, Sectors, Actions, Dashboard | `tests/test_qualified_place_same_everywhere.py`, `test_the_qualified_count_and_place...` |
| "Pass both filters" count | `to_bool_mask` on the two filter columns (`ranking_view.py:390`) | ranking | stock page "of N" | `test_the_qualified_count_and_place...` |
| "The book buys the top 20 qualified and keeps a holding while it is in the top 40"; "within 20% of the 52W high" | typed in `ranking_view.screener_lede`, `_KEY_HTML` | text | Watchlist, stock page (`watchlist_lines.lines()`), Guide, Backtest | `test_the_rule_numbers_are_the_track_records_on_every_page` |

### Guide, Configuration and Backtest

| Label (as shown) | Made by | Reads | Also on | Test |
|---|---|---|---|---|
| Guide: book size, keep rank, weights, caps, cost, EMA (the 20% is typed) | `guide_view._body` from `TRACK_RECORD_CONFIG` | code | Screener, Configuration, Backtest | `test_the_rule_numbers_are_the_track_records_on_every_page` |
| Guide: worked example "+20.0% against +5.0%" | typed, neutral (S193 A14) | text | no live figure | - |
| Configuration: data dates and ranked counts; weight and cap defaults | `config_view` (`DEFAULT_LOOKBACK_WEIGHTS`, `DEFAULT_SECTOR_CAP`, `DEFAULT_STOCK_CAP`) | sync log, `rank_df` | header and footers; Guide | `test_the_rule_numbers_are_the_track_records_on_every_page` |
| Backtest: a year, the Nifty 500's, lead in pts a year, falls, years table | `backtest_page.summary`, `falls`, `years_table` on its own run | NSE long file (R2), `benchmarks.csv`, membership history; to the run's last month-end | none: research on the Nifty 500, by decision (S165, owner 21 Nov 2026) | `tests/test_backtest_page.py` |
| Backtest defaults: 20 holdings, keep 40, 50D EMA, within 20%, 30 bps | `backtest_view` inputs | code | Guide, Screener | `test_the_rule_numbers_are_the_track_records_on_every_page` |

### Undocumented differences found 24 Nov 2026 (not fixed; for the owner to route)

**Status 25 Nov 2026: 1-5 closed.** 5: `nse_total_market.csv` now holds the seven weekend sessions (S163, fixed by rule 24 Nov; checked 25 Nov: 12 Nov 2023 9,757.10, 8 Nov 2026 13,251.55). **1-4 closed, each by a rule already settled, so no marker is left.** 1: the
Dashboard reads the calendar year too (`_from_high_series`, owner 24 Nov: "Use calendar date
everywhere"). 2: Sectors prints with `formats` (glossary 12). 3: "All ranked stocks" counts every
ranked stock (`test_a_ranked_stock_without_an_industry_counts_on_every_page`). 4: `exit_watch._flag`
and `theme.is_tick_true` read the same ticks, "✓" and "✅" (the test runs both). The text below is
the finding as written on 24 Nov.

1. **Nifty 500 from its 52W high, Dashboard against Market.** The Dashboard's "Sharp rebound" row
   (`dashboard_home_view.py:1563`) reads `market_questions._from_high_series`, a 252-session window
   (`market_questions.py:387-389`); Market (`market_questions.from_high`, `:365-372`), Indices and
   Sectors read a calendar year. NSE had 249 sessions in 2024 and in 2025, so the Dashboard reaches
   a few sessions further back. On `benchmarks.csv` the two differ at one decimal on 9 of the last
   750 sessions, most on 1 Oct 2025: Dashboard −6.4, Market −3.5. On 23 Nov 2026 both read −1.5.
   The signal tests read the 252-session series too (`signal_tests.py:95`).
2. **Sectors rounds the lede's Nifty Total Market with Python's format** (`sector_view.py:236`,
   `abs(tmr):.1f`), the other pages with `formats.signed` (half away from zero, glossary 12): 2.25
   reads "2.2" on Sectors and "+2.3" on the Dashboard. Only at an exact half.
3. **Sectors' "all ranked stocks" leaves out a stock without an industry** (`sectors_page.ema_shares`
   through `clean_groups`); Market and the Dashboard count every ranked stock. Not seen on 20 Nov
   (47% on all three).
4. **Tick marks** (not live: the engine writes booleans): `exit_watch._flag` reads "✓" and not "✅",
   `theme.is_tick_true` "✅" and not "✓", so on a ticked table the Screener's count and the
   qualified place would part.
5. **Data: `nse_total_market.csv` lacks NSE's seven weekend sessions** (Muhurat 12 Nov 2023 and
   8 Nov 2026; 20 Jan, 2 Mar and 18 May 2024; 1 Feb 2025; 1 Feb 2026), which `benchmark_indices.csv`
   and NSE's index store hold. `market_questions_view.total_market()` joins `benchmark_indices.csv`
   only after the file's last row, so Market and Sectors read the session before. On 8 Dec 2026 the
   1M window starts on 8 Nov: Dashboard, Indices and Portfolio from 13,251.55, Sectors from 6 Nov's
   13,226.40 (0.19% apart). Not tested (it is a data file the nightly sync writes).
