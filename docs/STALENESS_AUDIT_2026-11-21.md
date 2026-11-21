# Staleness audit, 21 Nov 2026 (S164)

Owner, 21 Nov 2026: "such misses are big disaster for portfolio as decisions will be wrong ... must be strict audit".
The standard used here: a rule may use completed months, but the page must show today's reading too and say
which reading the verdict uses. A figure that ends before the page's session without a stated rule is a fault;
one that states a rule but does not show today's reading is also a fault (the triggering case).

**How it was checked.** The app was run locally (`streamlit run app.py --server.port 8502`, data from R2 as on
the live site) on 21 Nov 2026, about 09:15 to 09:45 UTC. Every page in `app.py` `_PAGES` (`app.py:1275`) and
the stock page `/screener?stock=SGMART` was opened in Chromium at 1400 px with Playwright, scrolled to the end,
and the page text and every chart frame's HTML and spec were saved. Each chart's last date was read from its
spec (`dates`, `full`, `labels`, lightweight-charts `time`) and from its readout at rest ("Latest · …"). Each
figure was then traced to its function and data file, and the file's own last row was read. Where a live reading
is quoted below, it was computed with the site's own functions on the site's own files (a lead, not independent
evidence; see "What was not checked").

**The page's session is 20 Nov 2026** on every page: the header chip reads "Prices · closes of 20 Nov"
(`src/ui/components.py:297-308`), the footer "Data to 20 Nov 2026", the Screener status "Prices: 20 Nov ·
750/750 · latest session". `data/benchmarks.csv`, `data/benchmark_indices.csv` (all 11 indices),
`data/nse_total_market.csv` and `data/nsdl_fpi_daily.csv` all end 20 Nov 2026.

## Summary

90 elements were recorded across 12 pages. **63 CURRENT**, **6 STALE**, **10 RULE, NOT SHOWN**, **6 RULE,
SHOWN**, **5 CANNOT TELL** (counted from the class column of the tables below; a row that lists several
tiles counts once).

The faults are concentrated in two places, both feeding a market verdict:

1. **The 10-month-average rule** (`src/engine/market_questions.py:288` `ten_month_gap`) reads the 30 Oct
   month-end on a 20 Nov page. On 30 Oct every index was at or below its 10-month average; on 20 Nov every one is
   above it: Nifty 500 −3.1 vs **+6.6**, Nifty 50 −3.3 vs **+8.2**, Midcap 150 −4.2 vs **+3.6**, Smallcap 250
   −0.3 vs **+5.7**, Microcap 250 +1.7 vs **+6.6** (20 Nov close against the average of the ten completed
   month-ends Jan–Oct; against nine completed month-ends plus today: +6.1, +8.0, +3.0, +4.5, +4.9, same sign
   for all). Breadth's trend verdict counts four of these as "Down". Its weighted score is −0.1, "No clear
   trend". On the 20 Nov readings it is +0.9, **"Strong uptrend"** (7 of 8 measures up, none down). The page
   title says "no clear trend". The page never says that the verdict counts readings from 30 Oct.
2. **The Dashboard's signal count.** The opening sentence says "Of the 5 signals that pass our own test,
   3 points to a stronger month ... and 2 to a weaker one". Both "weaker" signals are 30 Oct month-end
   readings shown under the column "Now": the 10-month average (−3.1%; +6.6% on 20 Nov) and "Stocks that
   qualify" (17%, from `data/momentum_health_latest.json` dated 30 Oct; 42.4% on 16 Nov, the latest session the
   long NSE file has, against an "on" cut of 27% or fewer). On those readings both are off. By the page's own
   test values the count is **5 stronger, 0 weaker**.

The other faults have less effect on a decision: domestic institutions' flows end 18 Nov while 19 and
20 Nov provisional figures sit in `data/fii_dii_flows.csv`; the Dashboard's "12 months" momentum tile ends
in October and does not name the month; the Backtest's growth chart and rebalance table end 30 Oct. One data
file lags: `data/breadth_history.csv` ends 16 Nov because the long NSE price file it is built from is rebuilt
weekly. The pages fill 17–20 Nov from live prices, so no page figure stops at 16 Nov.

S164's entry "Not a fault, to keep and to say on the page: the 10-month-average rule counts completed months
only" is wrong by the owner's standard. The rule is acceptable, but the page shows no live reading and does not
say which reading the verdict uses.

## Ranked by decision impact

| # | Page | Element | Class | Effect |
|---|---|---|---|---|
| 1 | Breadth | Trend verdict "No clear trend", "3 of 8 measures say up, 4 say down", and the page title "Narrow participation; no clear trend." | STALE | On 20 Nov readings: "Strong uptrend", 7 up, 0 down. This is the page's market verdict |
| 2 | Dashboard | Opening sentence "3 points to a stronger month ... and 2 to a weaker one" and section 3's "Today 3 points to a stronger month, 2 to a weaker one" | RULE, NOT SHOWN | On 20 Nov (10-month) and 16 Nov (qualify) readings: 5 stronger, 0 weaker |
| 3 | Dashboard | Signal rows "Nifty 500 vs its 10-month average" (Now −3.1%, "Worse than usual") and "Stocks that qualify" (Now 17%, "Worse than usual") | RULE, NOT SHOWN | Column header "Now" shows 30 Oct |
| 4 | Breadth | Evidence rows "… against its 10-month average" ×5, "What has changed" lines for them, "What would change the answer" | STALE | Labelled "Now"; the row's rule text does not mention month-ends |
| 5 | Breadth | "Behind the answer": "The Nifty 500's last month-end close is 3.1% below its 10-month average" and its chart (ends 30 Oct) | RULE, NOT SHOWN | Today +6.6% above. This is the case that triggered the audit |
| 6 | Breadth | "By size" table, 10-month columns | RULE, NOT SHOWN | "Now" = 30 Oct, "A month ago" = 30 Sep |
| 7 | Dashboard | "Ahead over a year" headline and "12 months +12.2" tile | RULE, NOT SHOWN | Ends Oct 2026, month not named |
| 8 | Dashboard | "Domestic institutions, 2 to 18 Nov", its chart bar, and "Domestic institutions are selling into it." | RULE, NOT SHOWN | 19–20 Nov provisional DII are in `data/` and not shown |
| 9 | Backtest | Growth of ₹100 chart and "Rebalance periods" table end 30 Oct | RULE, NOT SHOWN | Informational |
| 10 | Breadth | Percentile under the 10-month rows ("12th percentile since Aug 2022") | STALE | Ranks the 30 Oct reading against a history whose last point is built from the 20 Nov close |

Nothing feeding Actions' sells, buys or holds, or Portfolio's book figures, was found to end before 20 Nov.

## Page by page

Columns: element (as labelled on the page) | last date shown | source file or function | that source's last
date | class | why | proposed fix (one line).

### Dashboard (`/`)

| Element | Last date shown | Source | Source's last date | Class | Why | Proposed fix |
|---|---|---|---|---|---|---|
| Header chip "Prices · closes of 20 Nov" | 20 Nov | `src/ui/components.py:297-308`; R2 `prices/screener` | 20 Nov | CURRENT | | |
| Opening sentence "Of the 5 signals that pass our own test, 3 points to a stronger month ... and 2 to a weaker one" | mixes 20 Nov and 30 Oct | `src/ui/views/dashboard_home_view.py:1176-1187` over `_signals` (`:1229`) | 30 Oct for two of the five inputs | RULE, NOT SHOWN | Two inputs are month-end readings; on live readings both flip to "stronger" (5 vs 0) | Say "at the 30 Oct month-end 3 vs 2; on today's close 5 vs 0", and which one the sentence uses |
| Section 1 tiles: book month so far +5.8%, Nifty Total Market +9.8%, since inception +46.3%, momentum indices 5 of 5, months ahead 8 of 11 | 20 Nov | `ui.book_series`, `data/benchmark_indices.csv` | 20 Nov | CURRENT | | |
| "The month" chart (November so far / October switch) | 20 Nov | `dash_charts` kind `month` | 20 Nov | CURRENT | October is a named switch | |
| Section 2: sells, buys, rank trail (3M ago 20 Aug, 1M ago 19 Oct, now), next in line | 20 Nov | `src/ui/model_plan.py`, `dashboard_insights.rank_trails` | 20 Nov | CURRENT | | |
| Leadership turnover "18 of today's top 40 were not there a month ago" | 20 Nov | ranking | 20 Nov | CURRENT | | |
| Section 3 headline "Ahead over a year, but 2 losing months in a row" | year to 30 Oct, plus Nov so far | `dashboard_home_view.py:445-452`, `dashboard_insights.momentum_lead` (`src/engine/dashboard_insights.py:139-162`) | `data/momentum_health.csv`: last return month Oct 2026 | RULE, NOT SHOWN | "a year" is Nov 2025–Oct 2026; the page does not say so | Name the year's end month, or add the year to 20 Nov |
| Tile "12 months +12.2, Top 100 of the ranking" | 30 Oct | `dashboard_insights.py:156` | Oct 2026 | RULE, NOT SHOWN | End month not named; the only live tile ("Month so far") is a different measure (Nifty500 Momentum 50 less Nifty Total Market, not top 100 less Nifty 500) | Label "12 months to October" and show the same measure to date |
| Tiles "Last 3 months +2.2, Aug to Oct" and "October −3.4" | 30 Oct | `dashboard_insights.py:157-158` | Oct 2026 | RULE, SHOWN | Months named; "Month so far −5.5" beside them | |
| "Momentum's lead, every month" chart | Nov 2026 so far | `dash_charts` `bars`, spec labels Jan '24 … Nov '26 | 20 Nov | CURRENT | The last bar is a different measure from the others (noted on the page) | |
| Signal "Nifty 500 vs its 200D EMA" 3M ago / 1M ago / Now | 20 Nov | `dashboard_home_view.py:1255-1260` | `data/benchmarks.csv` 20 Nov | CURRENT | | |
| Signal "Heavy foreign buying" | 20 Nov | `:1261-1268` | `data/nsdl_fpi_daily.csv` 20 Nov | CURRENT | | |
| Signal "Nifty 500 vs its 10-month average", Now −3.1%, "Worse than usual" | 30 Oct | `:1269-1274`, `market_questions.ten_month_gap` (`src/engine/market_questions.py:288-305`) | `data/benchmarks.csv` 20 Nov | RULE, NOT SHOWN | Sub-label says "Month-ends"; column says "Now"; 20 Nov reading +6.6% would be "on", +1.15, "Better than usual" | Add "Today +6.6% (counts at the 30 Nov close)" beside the month-end value |
| Signal "Stocks that qualify", Now 17%, "Worse than usual" | 30 Oct | `:1275-1289`; `data/momentum_health_latest.json` | `"date": "2026-10-30"` | RULE, NOT SHOWN | Labelled "Now"; 3M/1M cells are 31 Jul (44%) and 30 Sep (20%) month-ends; on 16 Nov the share is 42.4% (above the 27% cut, so "off", +1.20) | Compute today's share from the ranking and show it beside the month-end value |
| Signals "Breadth thin", "Participation jump" | 20 Nov | `nifty500_breadth` `:1203-1218`, `pit_breadth.splice` | `data/breadth_history.csv` 16 Nov, live after | CURRENT | 17–20 Nov counted on today's Nifty 500 members (seam) | Note the seam, or rebuild the file daily (see data files) |
| Signal "Sharp rebound" | 20 Nov | `:1302-1309` | 20 Nov | CURRENT | | |
| Money flows: FPI month so far +₹1.22 lakh Cr, last 20 sessions, 11 months before, FPI chart | 20 Nov | `flows_summary`, `data/nsdl_fpi_daily.csv` | 20 Nov | CURRENT | | |
| "What heavy foreign buying has meant · Jan 2016 to Oct 2026" | Oct 2026 | `data/signal_tests.json` (`through 2026-10`) | Oct 2026 | RULE, SHOWN | A dated study of completed months; the live month is above it | |
| Tile "Domestic institutions, 2 to 18 Nov, on NSE −₹50,000 Cr", chart bar "domestic, 2–18 Nov", headline "Domestic institutions are selling into it." | 18 Nov | `dashboard_home_view.py:555`, `_dii_months` `:1059`, `_all_exchange_months` `:1084-1100` | `data/nse_dii.csv` day rows 18 Nov; `data/fii_dii_flows.csv` DII to 20 Nov | RULE, NOT SHOWN | The footnote's rule (a month counts from all exchanges only when collected from its first session; `fii_dii_flows.csv` starts 6 Nov) drops 19 Nov and 20 Nov (−₹4,860 Cr provisional) | Show "19–20 Nov, provisional, all exchanges" beside the NSE figure |
| Size table: size against the market 1M/3M/6M, momentum against its size index | 20 Nov | `data/benchmark_indices.csv`, `dashboard_insights.as_of` | 20 Nov | CURRENT | S148 test holds | |
| "Is the rally shared?" chart (3M ago, 1M ago, now) | 20 Nov | ranked prices | 20 Nov | CURRENT | | |
| "The typical stock against the market" 1M/3M/6M/12M | 20 Nov | ranked prices, Total Market | 20 Nov | CURRENT | | |
| Section 6 industry cards and segment bar | 20 Nov | Sectors' functions, Portfolio weights | 20 Nov | CURRENT | | |
| Section 7 RRG frame and quadrant lists | week to 20 Nov | RRG weekly | 20 Nov | CURRENT | 20 Nov is a Friday; not checked on a mid-week session | |
| At a glance: "Indices, 20 Nov", breadth 47% / 49%, risk card | 20 Nov | `_glance`, `book_series`, `portfolio_report.risk` | 20 Nov | CURRENT | | |
| At a glance chart (Nifty 500 and share above 200D EMA) | 20 Nov | `_breadth_spec`, spec dates 2023-11-21 … 2026-11-20 | 20 Nov (file 16 Nov + splice) | CURRENT | | |

### Breadth (`/breadth`)

| Element | Last date shown | Source | Source's last date | Class | Why | Proposed fix |
|---|---|---|---|---|---|---|
| Title "Narrow participation; no clear trend." | trend half: 30 Oct | `src/ui/views/market_questions_view.py:631` | | STALE | No rule stated; the trend word rests on four 30 Oct readings and is "Strong uptrend" on 20 Nov readings | Compute the trend word on today's readings, or say "at the 30 Oct month-end" and give today's word |
| "Are most stocks taking part?" verdict "Narrow", sentence, evidence rows, What has changed | 20 Nov | `mq.breadth_answer` (`market_questions.py:228`) | prices 20 Nov; file 16 Nov + splice | CURRENT | | |
| "Is the market in an uptrend?" verdict "No clear trend", "3 of 8 measures say up, 4 say down", the scale | 30 Oct for 4 of 8 measures | `mq.trend_answer` (`market_questions.py:346-376`), cached in `_answers` (`market_questions_view.py:192-204`) | `data/benchmarks.csv`, `data/benchmark_indices.csv` 20 Nov | STALE | Rule not stated at the verdict; score −0.1; on 20 Nov readings +0.9, "Strong uptrend", 7 up, 0 down | Vote on today's close, or show both verdicts and say which one counts |
| Evidence rows "Nifty 500 / Nifty 50 / Midcap 150 / Smallcap 250 / Microcap 250 against its 10-month average", Now −3.1 / −3.3 / −4.2 / −0.3 / +1.7 | 30 Oct | `market_questions.py:354, 365`; `question_section_html` `market_questions_view.py:377-404` | 20 Nov | STALE | Column "Now"; the row's rule reads "Above is up, below is down" and does not mention month-ends | Show today's reading (+6.6, +8.2, +3.6, +5.7, +6.6) and name the month-end one as such |
| Percentile under those rows ("12th percentile since Aug 2022" etc.) | 30 Oct reading ranked against history to 30 Nov | `_ten_month_series` `market_questions.py:329-333` | includes a 30 Nov point from the 20 Nov close (+6.1) | STALE | The history includes the month in progress; the value ranked does not | Use one basis for the value and its history |
| "What has changed" for the 10-month measures (Microcap +12.3 → +1.7; Smallcap +5.8 → −0.3, "now down") | 30 Sep → 30 Oct | `changes` `market_questions.py:491` | | STALE | "A month ago" and "now" are month-ends, not 20 Oct and 20 Nov; not stated | Label as month-ends and add today's |
| "What would change the answer: To downtrend: Nifty 500 against its 200D EMA falling below 0.0" | derived from the 30 Oct mix | `what_would_change` `market_questions.py:512` | | STALE | Follows from the stale verdict | Follows the verdict fix |
| Evidence rows "Nifty 500 against its 200D EMA", "from its 52W high", "Stocks above their 200D EMA" | 20 Nov | `ema_gap`, `from_high`, splice | 20 Nov | CURRENT | | |
| "By size" table, "Against its 10-month average" columns (A month ago / Now) | 30 Sep / 30 Oct | `size_trend_html` `market_questions_view.py:411-439` | 20 Nov | RULE, NOT SHOWN | Note at `:437` states the rule; no live column | Add a "Today" column |
| "By size" table, 200D EMA and 52W-high columns | 20 Nov | same | 20 Nov | CURRENT | | |
| "Behind the answer": "The Nifty 500's last month-end close is 3.1% below its 10-month average" and chart ("Latest · 30 Oct 2026", 36 month-ends 2023-11-30 … 2026-10-30) | 30 Oct | `_trend_charts` `market_questions_view.py:551-573` | 20 Nov | RULE, NOT SHOWN | Today's close 24,088.8 is 6.6% above the same average (22,599.0); the chart drops the month in progress (`:556-558`) | Draw today's close as a marked point and state both readings in the heading |
| "Over the year, Microcap 250 did best against the Nifty 500 (+6.6 pts)…" and chart | 20 Nov | `_trend_charts` right column | 20 Nov | CURRENT | | |
| "Over the year the Nifty 500 rose 0.5%; the share … went from 46% to 47%" and chart | 20 Nov | `_breadth_charts` `market_questions_view.py:505-535`; spec 2023-11-21 … 2026-11-20 | file 16 Nov + splice | CURRENT | | |
| "Net new 52W highs this week: +4.6%" and weekly bars | week to 20 Nov | `market_questions_view.py:536-548` | 20 Nov | CURRENT | | |
| Today's charts: Above each EMA; new highs and lows; 52W events table | 20 Nov | specs 2026-05-22 … 2026-11-20 | 20 Nov | CURRENT | | |
| Header strip and footer "Data to 20 Nov 2026" | 20 Nov | | 20 Nov | CURRENT | | |

### Actions (`/actions`)

| Element | Last date shown | Source | Source's last date | Class | Why | Proposed fix |
|---|---|---|---|---|---|---|
| Tiles: Sell 5 / Buy 5 / Hold 15 / Next rebalance Mon 30 Nov | 20 Nov | `ui.model_plan` | 20 Nov | CURRENT | | |
| "Results and corporate actions before the fill": board meetings to 5 Dec, ex-dates "collected to 20 Nov" | 20 Nov / 5 Dec ahead | `data/results_calendar.csv` (fetched 21 Nov), NSE actions | 21 Nov fetch | CURRENT | | |
| Sell table (rule broken, since entry, amount) | 20 Nov | `exit_watch`, ranking | 20 Nov | CURRENT | | |
| "What swaps have added so far … Jan 2026 to Nov 2026" | windows to 20 Nov where 21/63 sessions exist | `src/engine/swap_evidence.py` | 20 Nov | CURRENT | | |
| Buy table, weights and amounts ("model book's value today, ₹1,46,26,738") | 20 Nov | `book_series`, `model_plan` | 20 Nov | CURRENT | | |
| "The book after the trades", industry and size | 20 Nov | Portfolio `Weight %` | 20 Nov | CURRENT | | |
| Hold table (rank 3M/1M/now, distance to lines) | 20 Nov | `rank_trails`, ranking | 20 Nov | CURRENT | | |
| Qualified list frame | 20 Nov | ranking | 20 Nov | CURRENT | | |

### Portfolio (`/portfolio`, which includes the track record)

| Element | Last date shown | Source | Source's last date | Class | Why | Proposed fix |
|---|---|---|---|---|---|---|
| Tiles: portfolio value, since inception, day P&L, month so far, below its peak | 20 Nov | `ui.book_series` | 20 Nov | CURRENT | | |
| Current book table (price, weight, today, since entry, rank) | 20 Nov | `build_portfolio_tracker` | 20 Nov | CURRENT | | |
| Industry exposure now | 20 Nov | holdings `Weight %` | 20 Nov | CURRENT | | |
| "The book by size, each rebalance" and "Industries, each rebalance" (Jan … Nov) | 2 Nov fill | `data/book_exposure.csv` + live month | file 1 Oct; Nov worked out live | CURRENT | Rows are written when a month is frozen; Nov is the live month | |
| Returns by period "to 20 Nov"; this year against other indices | 20 Nov | `portfolio_report`, `data/benchmark_indices.csv` | 20 Nov | CURRENT | | |
| Equity and drawdown chart; below peak, largest fall, worst day | 20 Nov | `growth` spec 2025-12-31 … 2026-11-20 | 20 Nov | CURRENT | | |
| "Worst month-end −9.9%, March" | month-ends | `portfolio_report` | | RULE, SHOWN | Labelled "Counting month-end values only"; the daily measures sit beside it | |
| Risk: 220 sessions, volatility, beta, tracking error, capture, correlation | 20 Nov | `portfolio_report.risk` | 20 Nov | CURRENT | | |
| Calendar returns (Nov so far), month-by-month chart | Nov 2026 so far | ledger + live month | 20 Nov | CURRENT | | |
| Day by day, last 20 sessions | 20 Nov | spec 26 Oct … 20 Nov | 20 Nov | CURRENT | | |
| Trades and trade history | 20 Nov | ledger, tradebook | 20 Nov | CURRENT | | |
| Three systems: Nifty 750 row | 20 Nov | `_systems` `portfolio_page.py:177-210` | 20 Nov | CURRENT | | |
| Three systems: Nano Cap and Combined "This month" | not stated | `_record_mtd` on `_comparison_price_frame` | ledgers to Oct 2026 | CANNOT TELL | The row gives no date, and the last session of the Nano Cap price frame was not checked | Print the session each system's month-so-far ends on |

### Sectors (`/sectors`)

| Element | Last date shown | Source | Source's last date | Class | Why | Proposed fix |
|---|---|---|---|---|---|---|
| "What is leading?" and "By size, against Nifty Total Market" 6M / 1M | 20 Nov | `mq.leaders_answer`, `data/benchmark_indices.csv` | 20 Nov | CURRENT | | |
| Industries by six months and one month; bar chart | 20 Nov | `leaders_answer` | 20 Nov | CURRENT | | |
| Month-by-month heatmap, "Nov MTD" column | 20 Nov | `mq.industry_months` `market_questions.py:540` | 20 Nov | CURRENT | | |
| Heatmap "Run" and "12 months" columns; headline "Healthcare has beaten all ranked stocks in each of the last 6 completed months" | Oct 2026 | same | | RULE, SHOWN | "Completed months" stated; the MTD column (Healthcare −1.5) is beside it | The headline could add that November so far is behind |
| Industry leaderboard (3M / 6M median, shares) | 20 Nov | sector view | 20 Nov | CURRENT | | |
| Sector leadership map, "19 Oct to 20 Nov" | 20 Nov | `src/ui/charts.py` | 20 Nov | CURRENT | | |

### RRG (`/rrg`)

| Element | Last date shown | Source | Source's last date | Class | Why | Proposed fix |
|---|---|---|---|---|---|---|
| Chart "Weekly · tail 6w · lookback 12w · 20 Nov 2026", quadrant lists | week to 20 Nov | `rrg_view` | 20 Nov | CURRENT | | |
| Behaviour on a non-Friday session | — | weekly resample | — | CANNOT TELL | 20 Nov is a Friday; whether a mid-week page shows the last Friday or the session was not observed | Test with a mid-week fixture |

### Screener (`/screener`)

| Element | Last date shown | Source | Source's last date | Class | Why | Proposed fix |
|---|---|---|---|---|---|---|
| Ranking table, filter counts | 20 Nov | ranking | 20 Nov | CURRENT | | |
| "Since 21 Oct (one month)": jumps, entered and left the top 50 | 20 Nov | `ranking_view.py:658-664` | 20 Nov | CURRENT | | |
| Status line: prices, market caps, all-time highs "20 Nov · latest session" | 20 Nov | `data/nse_market_caps.csv` (AsOf 20 Nov), `data/nse_all_time_highs.csv` (20 Nov) | 20 Nov | CURRENT | | |

### Stock page (`/screener?stock=SGMART`)

| Element | Last date shown | Source | Source's last date | Class | Why | Proposed fix |
|---|---|---|---|---|---|---|
| Price "Close · Fri 20 Nov 2026", 1M / 3M / 12M | 20 Nov | ranking | 20 Nov | CURRENT | | |
| Price and RS chart | 20 Nov | lightweight-charts, 2026-05-22 … 2026-11-20 | 20 Nov | CURRENT | | |
| Filters, 52W high, ATH dates | 20 Nov | ranking, `data/nse_all_time_highs.csv` | 20 Nov | CURRENT | | |
| Returns and risk by window | 20 Nov | stock view | 20 Nov | CURRENT | | |
| Rank path "#15 6M → #28 3M → #69 2M → #27 1M → #3 Now" | "Now" = 20 Nov; others undated | `stock_view` | | CANNOT TELL | The past points carry no dates on the page | Print each point's session |
| Industry peers table | 20 Nov | ranking | 20 Nov | CURRENT | | |

### Watchlist (`/watchlist`)

| Element | Last date shown | Source | Source's last date | Class | Why | Proposed fix |
|---|---|---|---|---|---|---|
| Whole page | — | `watchlist_store` | — | CANNOT TELL | Empty in a fresh browser ("No symbols saved yet"); no figure was rendered | Check with a saved list |

### Backtest (`/backtest`, default tab)

| Element | Last date shown | Source | Source's last date | Class | Why | Proposed fix |
|---|---|---|---|---|---|---|
| "Tested 1 Jan to 30 Oct 2026"; tiles: strategy return +45.2%, ahead of the index, Sharpe, max drawdown, months ahead | 30 Oct | `backtest_view.py:587-605` | prices 20 Nov | RULE, SHOWN | "Last completed month" is stated, and the CY cell "Jan–20 Nov" +53.4% is on the page | |
| Growth of ₹100 chart ("Strategy 145.18 on 30 Oct 2026") | 30 Oct | lightweight-charts, 2026-01-01 … 2026-10-30 | 20 Nov | RULE, NOT SHOWN | The chart has no point after 30 Oct and no note of its own | Extend the line to 20 Nov, dashed, and mark it as the month in progress |
| Rebalance periods table (last row 1 Oct → 30 Oct) | 30 Oct | engine periods | 20 Nov | RULE, NOT SHOWN | The 2 Nov period, in progress, is missing | Add the open period, to 20 Nov |
| Monthly grid, NOV column, CY/FY/quarter cells | 20 Nov | `backtest_view.py:73-80, 749-754` | 20 Nov | CURRENT | | |
| "History from 2010" tab | — | R2 `prices/nse_long_close` | 16 Nov | CANNOT TELL | Not opened in this audit | Audit with the next pass |

### Configuration (`/configuration`)

| Element | Last date shown | Source | Source's last date | Class | Why | Proposed fix |
|---|---|---|---|---|---|---|
| "Last synced 21 Nov 2026 At 09:01" | 21 Nov | `data/indices_sync_meta.json` | 21 Nov 09:01 | CURRENT | | |
| Source freshness table: prices, market caps, all-time highs "20 Nov · latest session", ranked from | 20 Nov | `config_view` | 20 Nov | CURRENT | The four rows are right, but the table leaves out every lagging source: `breadth_history.csv` (16 Nov), the long NSE file (16 Nov), `nse_dii.csv` (18 Nov), `nse_prices/closes.parquet` (5 Nov), `momentum_health*` (30 Oct) | Add a row for each file a page reads, with its last date and its stated rule |
| Data files table | — | | | CURRENT | No dates | |

### Guide (`/guide`)

| Element | Last date shown | Source | Source's last date | Class | Why | Proposed fix |
|---|---|---|---|---|---|---|
| Method text and research figures ("Jan 2010 to Oct 2026", 15.4% a year etc.) | Oct 2026 | static text, `guide_view.py` | | RULE, SHOWN | A dated study, not a reading of the market | |

## Data files the pages read, and why some lag

| File | Last row | Read by | Lags? | Cause, with evidence |
|---|---|---|---|---|
| R2 `prices/screener` (app prices) | 20 Nov | every page | No | Header chip, Screener status line |
| `data/benchmarks.csv` | 20 Nov | Breadth, Dashboard | No | |
| `data/benchmark_indices.csv` | 20 Nov, all 11 indices | Dashboard, Portfolio, Sectors, Breadth | No | |
| `data/nse_total_market.csv` | 20 Nov | Breadth | No | |
| `data/nsdl_fpi_daily.csv` | 20 Nov | Dashboard | No | |
| `data/fii_dii_flows.csv` | 20 Nov (DII and FII/FPI); starts 6 Nov | Dashboard (DII, only for months collected from their first session) | No | `fii_dii.yml:8-9` runs 14:47 and 17:47 UTC on weekdays; last run 20 Nov 23:24 UTC |
| `data/nse_dii.csv` | day rows 18 Nov; month rows Oct 2026 | Dashboard DII tile and bars | **Yes, 2 sessions** | NSE posts its category-turnover workbook about two days after the session (`scripts/collect_nse_dii.py:7-9`). This is a source lag. A page can still show the provisional figures for 19 and 20 Nov from `fii_dii_flows.csv` |
| `data/breadth_history.csv` | **16 Nov** (both universes; 4,187 Nifty 500 rows, 1,252 Total Market rows) | Breadth, Dashboard (spliced with live readings after 16 Nov) | **Yes, 4 sessions** | `scripts/build_breadth_history.py:55-58` reads the long NSE file (`nse_long.load`), and that file ends 16 Nov 2026 (read from R2 in this audit: 4,675 sessions, last 2026-11-16). The long file is rebuilt weekly (`nse_long_prices.yml:25`, cron `30 3 * * 6`, Saturdays). The last build was a manual dispatch on 17 Nov 09:30 UTC (run 44056264012). As of about 09:30 UTC on 21 Nov, the scheduled Saturday run had not started; scheduled runs start late (14 Nov's 03:30 cron started 10:46 UTC). `daily_sync.yml:441` re-runs the build every night on the same long file, so the output does not move. On failure the step only warns (`|| echo "::warning::…"`), and no check compares the file's last date with the price date |
| `data/signal_tests.json` | `through: 2026-10` | Dashboard signal tests | Rule | Completed months only; rebuilt with breadth |
| `data/momentum_health.csv` | last return month Oct 2026 (formation 30 Sep) | Dashboard momentum tiles, bars, qualify history | Rule | `momentum_health.yml:8`, cron `23 6 2-6 * *`. A month's spread needs the next month's return |
| `data/momentum_health_latest.json` | **30 Oct** | Dashboard "Stocks that qualify" | **Yes, in effect** | Written by the same monthly job (`scripts/build_momentum_health.py:36-48`, `latest_qualified` reads the latest complete month-end only, `src/engine/momentum_health.py:100-126`). No daily reading exists, although the measure (a count, not a return) can be taken any day: 42.4% on 16 Nov |
| `data/track_record.json` (+ `_nano`, `_combined`) | months to Oct 2026 | Portfolio, Dashboard | Rule | Frozen months; the live month is added at run time (`model_record.with_live_month`) |
| `data/book_exposure.csv` | 1 Oct 2026 | Portfolio | Rule | Rows are written when a month is frozen (`monthly_track_record`); the Nov fill is worked out live |
| `data/former_member_prices.parquet` | 13 Nov | record replay for stocks that left the index | Yes (not on a page figure seen) | Rebuilt only when the index loses or regains a name (`daily_sync`). No page figure seen depends on it after 13 Nov; not verified for a holding that left the index |
| `data/nse_prices/closes.parquet` | **5 Nov** | `price_source.ranking_frames`, to fill Screener gaps with NSE closes | Yes | Extended only by `monthly_track_record.yml:83` (`sync_nse_prices.py --update`), 1st–5th of the month. Today Screener covers 750/750, so no fill is used. A Screener gap after 5 Nov could not be filled from this file |
| `data/reference/weekly_fill_nano.parquet` | 30 Oct | Nano Cap history fill | Rule | History over Screener's weekly stretch; rebuilt only when a list member is missing |
| `data/results_calendar.csv` | fetched 21 Nov; dates to 5 Dec | Actions, Dashboard | No | |
| `data/nse_market_caps.csv`, `data/nse_all_time_highs.csv` | 20 Nov | Screener, stock page | No | |
| R2 `prices/nse_long_close` (long NSE file) | **16 Nov** | Backtest "History from 2010", breadth and momentum builds | Yes, weekly | As for `breadth_history.csv` above |

## What could not be checked

- The live readings quoted here (10-month gaps on 20 Nov, the qualify share on 16 Nov, the trend score of +0.9,
  the 5 vs 0 signal count) come from the site's own functions and files. No second source was used. The index
  closes they rest on match the header (Nifty 500 24,088.8) and S148's Screener check, but no index close for
  20 Nov was compared with NSE's own archive in this audit.
- The qualify share was computed on the long NSE file, which ends 16 Nov. The 20 Nov figure was not computed.
- Whether NSE has published the category-turnover workbooks for 19 and 20 Nov was not checked. That would
  show whether the 18 Nov end of `nse_dii.csv` is NSE's lag or ours.
- The Backtest's "History from 2010" tab, Configuration's expanders ("All sessions, by date"), the Screener's
  "View all" lists and the Portfolio trade history's CSV were not opened.
- Watchlist: empty in a fresh browser, so no figure was rendered.
- RRG and every weekly chart: today is a Friday. Behaviour on a mid-week session was not seen.
- The Nano Cap and Combined month-so-far end session (Portfolio, Three systems).
- The deployed site was not opened. This audit ran the same code and the same R2 data locally, at commit
  `6981beb`.
- Hover readouts were read at rest only. A series whose final point is hidden under a readout was not
  checked separately: every spec's last date is quoted from the spec itself.

## Seen on the way, outside staleness (for S154)

- Portfolio's rank caption says "on 20 Aug, 20 Oct, 20 Nov" (`src/ui/views/portfolio_page.py:333`), but
  20 Oct 2026 was an NSE holiday (Dussehra, `data/reference/nse/holidays.csv:17`). The Dashboard gives the
  same reading as "1M ago 19 Oct". Some 3M ranks also differ by one place between pages (SGMART #28 on
  Portfolio, #27 on Actions; GLAND #58 and #59; PVRINOX #118 and #119).
- The Screener counts its one-month rank change "Since 21 Oct" (`ranking_view.py:658-664`), the first session
  on or after the date. The Dashboard and Portfolio read 19 Oct, on or before. These are two window rules for
  "a month ago" (S148 settled on "on or before").
- The Sectors leadership map's text alternative says "against the Nifty 500's +2.0%". The +2.0% is the
  equal-weighted 750's one-month return (`src/ui/charts.py:555`; Dashboard: "Equal-weighted 750 1M +2.0").

## Proposed CI test (extends S154 (c))

**Name:** `tests/test_page_dates.py::test_every_figure_ends_on_the_pages_session_or_names_its_rule`, run with the
headless check (`scripts/headless_smoke.py`), which already renders each page with `AppTest` and reads every
chart frame's `srcdoc` (`scripts/headless_smoke.py:137-145`).

**What it does, per page in `_PAGES` plus `/screener?stock=<a holding>`:**

1. Read the page's session from the footer "Data to D Mon YYYY" (or the header chip). Fail if the two
   disagree.
2. For every chart frame, parse the spec and take its last date (`dates[-1]`, `full[-1]`, lightweight-charts
   `time`). For every HTML part, take each date in the text: "D Mon YYYY", "D Mon", "to D Mon", "Latest · …",
   and month names next to "month-end" or "last month".
3. A date before the session passes only when the element carries a declared rule. The rule is a
   `data-rule="month_end|weekly|source_lag"` attribute on the HTML part, or a `"rule"` key in the chart spec,
   with a non-empty `"live"` value, which is today's reading drawn beside it. The text must also contain the
   words the rule names, such as "month-end" and "today". A rule without a live reading fails. This is the
   owner's standard: a rule may use completed months, but today's reading must be shown.
4. Separately, in `tests/test_market_questions.py`: build a fixture ending mid-month whose last close is above
   its 10-month average while the last month-end is below it (the 20 Nov 2026 case: Nifty 500 21,895.9 on
   30 Oct, 24,088.8 on 20 Nov, average 22,599.0). Assert that `trend_answer` exposes both readings on every
   10-month `Measure` (a `live` field), and that the verdict text names which one it uses. Assert the same for
   the Dashboard's `_signals` rows `trend_slow` and `qualify` (`dashboard_home_view.py:1269-1289`): a row whose
   value is a month-end reading must also carry today's.
5. A data-date check in the nightly job: `breadth_history.csv`, `momentum_health_latest.json`,
   `nse_dii.csv`, `nse_prices/closes.parquet` and the long NSE file each get a stated maximum lag against
   `benchmarks.csv`'s last date (for example breadth 1 session, DII 2 sessions with the reason). The job fails
   loudly rather than `|| echo "::warning::"` when a file is past it, and the Configuration freshness table
   lists each one.

**Done when:** the test fails on today's code for the Breadth trend verdict, title, evidence rows, "By size"
10-month columns and "Behind the answer" chart, the Dashboard's two signal rows and opening sentence, the
"12 months" tile, the DII tile and the Backtest growth chart. It must pass once each shows today's reading or
ends on 20 Nov, and the live site must pass it (S164's own "done when").
