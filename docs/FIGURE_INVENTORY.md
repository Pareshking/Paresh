# Figure inventory: Dashboard, Portfolio and Actions (S154 (a), 21 Nov 2026)

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
