# Inventory C: Portfolio and Backtest, every section, for the S237 redesign

Read-only inventory, 28 Nov 2026. Code read at HEAD of `claude/handover-session-setup-7bd5zk` (5 commits ahead of
`origin/main` 1311f248, none touching these files); live text from the 28 Nov capture (`s237/ours/ours_portfolio.txt`
12:04 UTC, `ours_backtest.txt` 12:07 UTC); phone first screens `ours_*_iphone13_first.png`.

S237 rules used (docs/archive/S237_COMPARISON_2026-11-28.md): **G1** first screen = date line, one headline answer,
two-sentence lede; **G2** colour on figures only, never on whole phrases; **G3** familiar lines/bars with history, a
shaded usual range, extremes labelled, small multiples (tick strips and ring scales count as NOT done); **G4** a
"Source:" line under every chart.

**About G4 in the capture.** `how()` (src/ui/views/dashboard_home_view.py:156-177) writes `Source: …` under a chart's
footer since #720 (on main). The 12:04 capture shows no "Source:" line on either page, so #720 was deployed after the
capture (inferred). In code, a chart gets a source line **only if it has a `how()` footer**; charts without one have none.

**Conflict to settle before G4 is called done.** Three owner-backed rules still say the opposite: PAGE_DESIGN.md:60
("No source line on the page", owner 20 Nov), PORTFOLIO_REQUIREMENTS.md row 22 ("Data date only, no sources") and
BACKTEST_REQUIREMENTS.md row 29 ("no source named"). TODO S237 records G4 as built. CLAUDE.md says an owner decision
beats a benchmark. So either the owner has since agreed (not found in TODO S237's text) or the rows need his word
(inferred: the docs were not updated).

Routing: `app.py:1184-1190` `_page_portfolio` → `render_portfolio_view` (src/ui/views/portfolio_view.py:468-475) →
`portfolio_page.render` (portfolio_page.py:1127). `app.py:1238-1249` `_page_backtest` → `render_backtest_view`
(backtest_view.py:1254). Pages are registered at app.py:1280 and 1285. `track-record` redirects to Portfolio
(app.py:1306).

---

## Page 1: Portfolio (`/portfolio`)

Data spine: `canonical_book.current_book` (canonical_book.py:27-73) → `engine.model_record.record_run` (the pinned
record replay plus the live book) → `book_series.book_series` (book_series.py:40-67: frozen months, then the live month
marked daily) → `portfolio_page.gather` (portfolio_page.py:136-184). `gather` also reads the index store
(`loaders.benchmark_indices`), `data/membership_history.json`, `data/book_exposure.csv` (`book_exposure.load`),
`data/nse_market_caps.csv` (`_market_weights` :187-200), the systems' ledgers (`engine.systems.ledger_path`), and
`track_record_view._record_mtd` / `_comparison_price_frame` (track_record_view.py:19-104) for each system's month so far.

| # | Section (heading / kicker as shown) | Anchor | What it shows (form) | Data and where it comes from | Code | Redesign state against S237 |
|---|---|---|---|---|---|---|
| P0 | Site chrome: "Paresh Patel", nav, "Prices · closes of 27 Nov" pill, strip "Nifty Total Market 4.4% above its 200D EMA · 13,494 · Universe 750 · Above 50D EMA 353 (47%) · Near 52W high 374 (50%)" | – | Header bar, status pill, a row of five figures | rank_df and index closes (app.py) | src/ui/components.py:100 (`_status_pill_html`), :143 (`render_header_kpi_bar`) | G7 owner (site name); the strip repeats on every page and pushes the page's answer down on a phone (ours_portfolio_iphone13_first.png). Not this page's to fix |
| P1 | Kicker "PORTFOLIO"; h1 "The book is up 46.8% since 1 Jan 2026, 46.2 points ahead of Nifty Total Market." | – | Sentence headline, serif 44 px (36 on a phone) | `history.strategy_total_return`; market from the first fill (`pr.ret`) | portfolio_page.py:361-374 (`header_title`), :424 | G1 partial: one headline answer, but **no date line** on the page's own first screen (the date sits only in the chrome pill and the footer). **G2 open**: `kit.verdict` colours the phrases "up 46.8%" and "46.2 points ahead of" (page_kit.py:164-169) |
| P2 | Lede "₹1 Cr was put in on 1 Jan 2026. The book follows the Nifty 750 rules and holds 20 stocks. Returns are after costs. The months January to September 2026 were worked out from the rules on 1 Oct 2026. Later months were recorded as they happened." | – | Paragraph, 17 px | `_provenance` reads the ledger's `origin == "backfill"` and `finalized_on` | :420-421, :330-343 | **G1 open**: five sentences, against two. Five lines on a phone, so the first screen ends at the first tile. The backfill fact matters (tipsheet makes it a mark on the chart, see P13) |
| P3 | Five tiles: Portfolio value ₹1,46,77,316 (started ₹1,00,00,000; ₹19,699 not invested) · Since 1 Jan 2026, after costs +46.8% (+₹46,77,316; NTM +0.6%) · Day P&L +1.3% (+₹1,87,944; NTM −0.5%) · Month so far · Nov +6.2% (3.0 pts behind NTM; NTM +9.2%) · Below its peak today −2.6% (Peak 7 Oct; Max DD −13.4%) | – | KPI tiles (`_kpis`, `pf-five`) | `series.value/holdings`, `p.table["Day P&L (₹)"]`, `months_of` (ledger `monthly_grid` + `pr.month_returns`), `pr.falls(p.equity)` | :376-416 | G2: coloured figures only (done). **Duplicates:** "+46.8%" is in the h1, and "Below its peak today −2.6% Peak 7 Oct" and "Max DD −13.4%" come again in P13a. PORTFOLIO_REQ row 21 says no figure twice |
| P4 | "On this page" pills: Current book · Sector & size · Returns · Equity, drawdown & risk · Calendar returns · Day by day · Trades · Systems side by side | nav to pf-* | Anchor pills (HTML links, not widgets) | `NAV` | :417, :425, :428-429 | Matches tipsheet's "On this page". Done |
| P5 | Error and empty states for the whole page: "The model book could not be read just now." · `page_empty(NO_MODEL_BOOK…)` · unpriced-members warning ("This book was formed without N members…") · "The track record could not be read just now." · "The model book’s holdings could not be valued just now." · spinner "Reading the record…" | – | Amber `kit.note`, page_empty | `current_book`, `unpriced_note` (canonical_book.py:76-91), `load_ledger` | :1141-1169 | Wording is fine. A redesign must keep all six |
| P6 | **Current book**: "20 holdings · tap a column to sort · red: past a sell rule’s line today (the rules are checked at month-end)" | `pf-book` | dash_charts **"holdings"**: a sortable table with columns Stock, Sector · size, Entry date (days held), Qty, Entry price, Price, Value, Weight, Today, P&L from 2 Nov, Since entry, vs 50D EMA, From 52W high, Rank 3M · 1M · now (a trail), and a totals row | `book_series.table` (portfolio_view.build_portfolio_tracker), `rank_df` "% 50 EMA" / "% High", `di.rank_trails` + `exit_watch.qualified_ranks`, `industry_state` (market_questions.leaders_answer), `bx.size_of` | :432-475 (spec), :478-496, static/dash_charts.js:358 | G2 done (red on the cells past a line). **G4 open**: no `how()` footer, so no Source line (it is a table, so arguably exempt (inferred)). The rank trail is a three-point sparkline: fine by PAGE_DESIGN §4.3 |
| P6a | Note under the book: "Entry price and since entry are from the day the stock was first bought. P&L in rupees starts at the 2 Nov fill… The plan for the next rebalance is on Actions." | – | Note paragraph, about 7 sentences | cfg `high_pct`, `buffer_n`, trail dates | :487-492 | Long (six ideas in one note); tipsheet would keep two lines and link Method. Suggest splitting: the arithmetic line under the totals row, the sell rules as the table caption |
| P7 | **Sector & size**: "now, against the 750, and at every rebalance since 1 Jan 2026" | `pf-exp` | Section head | – | :567 | – |
| P7a | "Sector exposure now": "bar: the book’s weight · mark: the sector’s weight in the 750 by market cap". Rows: Sector (n holdings), bar + dashed mark, Book %, The 750 %, Over / under, Status (Strong / Turning / Weak / Not held) | – | Hand-drawn HTML bar list (`pf-ilist`, not a dash_charts frame) | `p.table` weights; `_market_weights` (`nse_market_caps.csv` via `system_market_caps`); `industry_state` | :515-535, :568-569 | **G2 open (minor)**: the Status words are coloured (`dh-up`/`dh-down`/`dh-turning`, :522, :535). **G4 open**: no source line, no table, no readout. On a phone the "The 750" and "Status" columns are hidden (PF_CSS :1105), so the benchmark weight shows only as the mark |
| P7b | "The book by size, each rebalance": Large Cap · Mid Cap · Small Cap · Micro Cap, one stacked bar per month (Jan to Nov) with % labels ≥15, and a key | – | Hand-drawn HTML stacked bars (`dh-sizebar`) | `data/book_exposure.csv` (`bx.load`) merged with the live tradebook (`bx.exposure`) | :537-546, :570-572 | G3 partial: history at every rebalance is good. A labelled 100% stacked area is the tipsheet form ("What it held"). **G4 open**: no source, no table, no readout |
| P7c | Note: "At its first rebalance, Jan 2026, the book held 65% in Large Cap and Mid Cap. Now 90% is in Small Cap and Micro Cap. Each rebalance’s sector and size weights…" | – | Note | `size_shift` | :499-512, :563-564 | Good answer sentence. It could be the subsection's headline (G6 pattern) |
| P7d | "Sectors, each rebalance": "% of the book, the largest at any rebalance first". Every sector held, by month | – | Heat table (ink-intensity cells) | `book_exposure` kind=industry | :547-559, :572-574 | Readable. **G4 open**: no source. Small multiples (one tiny bar row a sector) would be the G3 form (suggestion) |
| P8 | **Returns**: "the book after costs · price returns on both sides" | `pf-ret` | Section head | – | :620 | – |
| P8a | "By period · to 27 Nov": Today, 1 week, Month so far · Nov, 1 month, 3 months, 6 months, This year (since 1 Jan 2026), FY 2026-27. Columns: The book / Nifty Total Market / Lead, pts / Momentum 50 | – | Table | `pr.periods(p.equity, p.market, p.mom, …)` (engine/portfolio_report.py) | :577-585, :621-624 | G2 done (figures coloured). The "This year" row repeats the h1. No chart (tipsheet shows these as a table too, under "Values on…") |
| P8b | Note: "Once the record is a year old, the table adds 12 months, 3 years, 5 years and a yearly rate since 1 Jan 2026. Nothing is annualised before then." (plus an index-late sentence when NTM lags) | – | Note | `index_late_note` | :612-619 | Fine |
| P8c | "This year against other indices · since 1 Jan 2026": The book, Nifty Microcap 250, **Mix in the book’s size split**, Smallcap 250, Nifty500 Momentum 50, Midcap 150, Nifty Total Market, Nifty 50, with the book's lead in pts | – | Table | `bi.series` for each index; `pr.size_mix(exposure, SIZE_INDEX)` | :590-611, :625-633 | Good content. A ranked bar (tipsheet /models/indices/ "Return a year … ranked") would read faster (suggestion) |
| P8d | Note: "Most of the book is in Small Cap and Micro Cap, so Nifty Total Market is not its only fair yardstick. The mix holds… pts = percentage points…" | – | Note | `yardstick_line`, `book_size_groups` | :636-666, :629-633 | Fine |
| P9 | **Equity, drawdown & risk**: "₹100 on 1 Jan, daily" | `pf-eq` | Section head | – | :754 | – |
| P9a | Growth chart: top pane ₹100 → book (area), Nifty500 Momentum 50, Nifty Total Market (dashed); bottom pane drawdown, book and NTM; readout above | – | dash_charts **"growth"** (two panes, one crosshair, linear scale) | `growth_spec` from `p.equity`, `p.market`, `p.mom`; `pr.drawdown_series` | :669-683, :755-757, dash_charts.js:335-356 | G3 partial: a familiar line with all its history. **Open:** extremes not labelled (the max-DD low of 23 Mar, the peak of 7 Oct); no mark for "worked out on 1 Oct 2026 / recorded since" (tipsheet marks "Rule published · Entered the library" on the same chart); no end labels (owner rule PAGE_DESIGN §4.1 "No end labels" conflicts with tipsheet's "6.8× …", so keep ours). The empty state "The growth chart starts once the book has two sessions; it has N." (:757) |
| P9b | Footer: "What it is / How to read it" (folded on a phone), **Source: the model book's record (NSE's closes, after costs); Nifty500 Momentum 50 and Nifty Total Market from NSE Indices.**, "Show the table" (Date, The book, Momentum 50, NTM, both below-peak; every 5th day) | – | `how()` block with folded table | the spec above | :758-766 | G4 done in code (not in the 12:04 capture). The table is only every 5th session, newest first. CSV links were declined by the owner (TODO S237) |
| P9c | Four tiles: Below its peak today −2.6% (Peak 7 Oct; NTM −0.6%, below its 20 Nov peak) · Max DD −13.4% (29 Jan → 23 Mar, recovered 22 Apr; NTM −14.9% (2 Jan → 30 Mar)) · Worst day −4.3% (1 Feb; NTM −2.0% that day) · Worst month-end −9.9% (March; counting month-end values only) | – | KPI tiles (`pf-four`) | `pr.falls`, `pr.worst_month_end`, `pr.daily_gaps` | :707-725, :767 | Duplicates P3's tile 5. The tiles could become labels on the chart (G3 "extremes labelled") and leave the header tile alone (suggestion) |
| P9d | "Risk · Since 1 Jan 2026, 224 sessions · from January 2027 also the last 12 months and each year" | – | Caption | `pr.risk` windows | :741-745, :768 | Fine |
| P9e | Five tiles: Volatility, a year 22.6% (NTM 15.6%; about 1.5×) · Beta 1.0 · Tracking error 16.7% (about 1.1 pts a typical day) · Up / down capture, 60 sessions 70% / 65% ("Falls less on bad days" coloured, "Rises less on good days") · How they move together, 90 sessions 0.13 ("Low: the list is well spread") | – | KPI tiles | `pr.risk`, `pr.capture`, `qualified_view.correlation` | :726-740, :768 | **G2 open (minor)**: the capture status phrase "Falls less on bad days" is coloured (`dh-up`/`dh-down`, :737). No chart: a rolling 60-session beta / volatility line with a usual range would be G3 once a year of history exists (suggestion; data from `p.equity`/`p.market` already in hand) |
| P9f | Risk by window table (only when `len(risks) > 1`: from Jan 2027): Window, Sessions, Volatility, NTM, Beta, Tracking error | – | Table (future state) | `pr.risk` | :746-753 | Not shown today. A redesign must keep a place for it |
| P9g | Footer: What it is / How to read it ("Worked out from 224 sessions, so a rough guide… A tracking error of 16.7% means…"), **Source: our calculation from the model book's daily values and Nifty Total Market's closes (NSE Indices).**, Show the table (Measure / The book / NTM). Empty state "No risk figures yet: …" | – | `how()` | – | :769-779 | G4 done in code. The source is under tiles, not under a chart |
| P10 | **Calendar returns**: "every month, quarter and year; each new year adds a row" | `pf-cal` | Section head | – | :1175 | – |
| P10a | "Month by month · the book’s lead over Nifty Total Market, points": one bar per month with value labels | – | dash_charts **"bars"** (vertical bars from zero, range "all"/record) | `month_bars_spec` ← `months_of` (lead = book − market) | :862-869, :1176-1177 | **G3 open**: no usual-range band (the bar kit supports `band`, dash_charts.js:269-281, but the spec sends none; with 11 months a band is thin, so the honest choice may be to say "too short for a usual range" (inferred)). **G4 open**: no `how()` footer, so no source line and no "What it is" (the grid below is its table, inferred). Captured text shows no bar caption after the pills, so check it renders |
| P10b | Pills: All · The book · Nifty Total Market · Lead · Momentum 50 | – | `st.pills` key `pf_cal_show` | – | :1178-1179 | A control (see the controls list). It filters the grid only, not the CY or FY tables |
| P10c | "Months and quarters": grid % × Jan…Dec, Jan–Mar, Apr–Jun, Jul–Sep, Oct–Dec, Year; a row group "2026 · Nov so far" with The book, Nifty Total Market, Lead pts, Momentum 50, **Nifty 500, as recorded** (muted); a ghost row "2027 · from January…"; footnote "* Jan 2026, the first month: from the fill, 1 Jan…" (+ a "before …" footnote for young systems) | – | Wide table (min-width 1060 px, scrolls sideways) | `pr.calendar(months_of(p))`; ledger `monthly_grid` "Strategy Net"/"Benchmark" | :782-828, :1180-1181 | G2 done (bold and colour on figures). On a phone it scrolls sideways (inferred from min-width) |
| P10d | "Calendar years · January to December": Year, Book, NTM, Lead pts, Momentum 50, Months ahead, Max DD (with NTM's) | – | Table | `pr.falls` per year slice | :829-846, :1182 | Fine |
| P10e | "Financial years · April to March": FY 2025-26 (Jan–Mar only, from the start), FY 2026-27 so far | – | Table | `pr.financial_years` | :847-858, :1183 | Fine |
| P10f | Note: "Frozen months stay as recorded against the Nifty 500, the benchmark when they were frozen; … Momentum 50 is NSE’s Nifty500 Momentum 50, a momentum index to judge the strategy by." | – | Note | `_frozen_note` | :315-320, :1184-1185 | Fine |
| P11 | **Day by day against Nifty Total Market**: "Day P&L in context" | `pf-day` | Section head | – | :892 | – |
| P11a | Four tiles: Today +1.8 pts (Book +1.3%, NTM −0.5%) · Last 5 sessions +0.3 pts · Last 20 sessions 9 of 20 · Since 2 Jan 125 of 223 (56%) | – | KPI tiles | `pr.daily_gaps(p.equity, p.market, fill)` | :872-887 | **G2 open (minor)**: "9 of 20" is in `dh-watch` (amber) as a verdict colour on a count (:885) |
| P11b | "The book against Nifty Total Market, last 20 sessions · points": 20 daily bars, the last labelled "Today" | – | dash_charts **"bars"** (range fixed, 20 sessions, with its reason) | the last 20 rows of `daily_gaps` | :888-894 | G3 partial: 223 sessions are computed and 20 drawn. A rolling 20-session "sessions ahead" line over the whole record with a usual range would show the context the tile names (suggestion) |
| P11c | Footer: What it is / How to read it, **Source: the model book's daily values; Nifty Total Market's closes from NSE Indices.**, Show the table (Session, Book, NTM, Lead) | – | `how()` | – | :895-898 | G4 done in code |
| P11d | Empty state: "Day by day starts once the book has six sessions; it has N." | – | Note | – | :874-877 | Keep |
| P12 | **Trades**: "80 closed · 20 open · 11 rebalances" | `pf-trades` | Section head | `trade_stats` ← `history["trades"]`, `history["tradebook"]` | :901-929, :954-981 | – |
| P12a | Five tiles: Trades won 40% (32 of 80; amber) · Average win +35.7% (Median +11.4%; "A few large winners carry it") · Average loss −11.0% (Median −9.2%) · Held, median 58 days (Winners 90 · losers 31) · Changed at a rebalance 8 of 20 (since February; latest November 9 · fewest September 4) | – | KPI tiles | as above, `changed_tile` | :941-971 | **G2 open (minor)**: "40%" in amber as a verdict colour. **Data shown poorly**: the mean and median disagree (and the sign does in P12b), which is a distribution. A return histogram or a dot strip of the 80 trades (a familiar form, G3) would show it |
| P12b | "Which rule closed each trade · 80 closed": Trend breakdown (closed below its 50D EMA) 50 · +10.4% · −7.0%; Rank dropped (fell out of the top 40) 27 · +4.8% · +1.4%; Off its high (more than 20% below the 52-week high) 3 · −11.0% · −16.3% | – | Table | `EXIT_NAMES` against "Reason for Exit" | :912-915, :972-985 | Fine. Average and median of opposite sign need a word, or the distribution above |
| P12c | "Best trades and worst trades · closed": STLTECH 1 Apr → 2 Nov +331.6% … IOC −24.2% (3 + 3) | – | Table | `closed.nlargest/nsmallest(3)` | :975-988 | Fine |
| P12d | Empty states: "Trades · no trades yet"; "No trade has closed yet; these figures start with the first exit." | – | – | – | :955-962 | Keep |
| P13 | Expander "Trade history: every trade and every rebalance line, with CSV to check them" (closed by default) | – | `st.expander` → dash_charts **"history"**: view chips Trades / Rebalance lines; filters All · Winners · Losers · Open / All · Buy · Sell · Hold; a per-rebalance bar strip (bought/sold/held); HISTORY_NOTE | `pr.trades_table(history["trades"], tradebook, …)`, `history_spec` | :1188-1195, :991-1019, dash_charts.js:393 | **G4 open**: no source line. A table, so G3 does not apply |
| P13a | Two download buttons: "Export CSV · 80 trades, 15 fields" (`model_book_trades_YYYYMMDD.csv`), "Export CSV · N lines" (`model_book_rebalances_YYYYMMDD.csv`) | – | `st.download_button` ×2 | `csv_bytes` (src/ui/export.py) | :1196-1202 | Inside the expander: a reader who never opens it does not see that CSVs exist. PORTFOLIO_REQ rows 18 and 47 are met |
| P14 | **Four systems, side by side**: "compared over the same window". Columns: System, Month so far · Nov, Since 1 Oct, all three, Since it started, Started. Rows: Nifty 750 (this book), Nifty 1000 ("Nov 2026 · joins from Dec"), > ₹2,000 Cr, Combined, Nifty Total Market | `pf-sys` | Table | `_systems` (:232-279): each system's ledger + `_record_mtd`; `common_window` | :1042-1065 | G2 done (figures). Table only: no small multiples of the systems' ₹100 lines over the common window (G3 suggestion, data in hand). Heading word count comes from `_NUMBER_WORDS` |
| P14a | Note: "“Since 1 Oct” is the window that the Nifty 750, the > ₹2,000 Cr and the Combined have all traded… – in Since 1 Oct: the system is too young (the Nifty 1000). **Shadow systems**, recorded but not traded: Recommendation (from Nov 2026), Near-high 90% (from Dec 2026), Breadth + long lookback (from Dec 2026), Skip 5 days (from Dec 2026)." | – | Note | `window_line`, `track_record.SHADOWS` | :1030-1039, :1054-1065 | Shadows are names only. PORTFOLIO_REQ row 17 says "on one line until they have one" (Recommendation has a month: its row could join, inferred) |
| P15 | Footer: "Data to 27 Nov 2026 · NSE." | – | `dh-foot` | `_fmt.data_to_html(p.as_of)` | :1203 | Fine. The date is in red when the backup copy is stale (formats.py:208) |

### Portfolio (a) controls and what they change

| Control | Kind | Changes | Code |
|---|---|---|---|
| System (750 / 1000 / > ₹2,000 Cr / Combined) | `?sys=` / session state, set off-page (the picker is on Configuration, inferred) | The whole page: book, ledger, exposure (only the 750 has `book_exposure.csv`), the header's provenance, the systems' "this book" row | portfolio_page.py:1138; src/ui/system_param.py:22-28; app.py:975-990 |
| "On this page" pills | Anchor links | Scroll only | :417, :428 |
| Holdings column headers | Sort in the "holdings" frame | Row order | dash_charts.js:358-391 |
| Chart pointer, finger, arrow keys | In-frame | The readout over the growth, month-bars and day-bars charts | dash_charts.js |
| "What it is · how to read it" | `<details>`, phone only | Unfolds the explainer | dashboard_home_view.py:174 |
| "Show the table" ×3 (growth, risk, day) | `<details>` | Unfolds the table | :766, :779, :898 |
| Calendar "Show" pills (All / The book / Nifty Total Market / Lead / Momentum 50) | `st.pills` `pf_cal_show` (reruns) | Rows of the Months and quarters grid only | :1178-1180, :786 |
| Trade history expander | `st.expander` | Shows the history frame and the CSVs | :1194 |
| History view chips (Trades / Rebalance lines) and filters | In-frame chips | Rows shown | :1016-1019 |
| Export CSV ×2 | `st.download_button` | Files | :1198-1202 |

### Portfolio (b) data read but shown poorly

1. **The record's split between backfill and live.** The ledger's `origin: backfill` and `finalized_on` (1 Oct 2026)
   are a sentence in the lede (:330-343). They are not a mark on the ₹100 chart (P9a), as tipsheet's "Entered the
   library" is. A display change only; nothing in the record moves.
2. **Daily lead history.** 223 sessions of `daily_gaps` are computed and 20 are drawn (P11b). The "Since 2 Jan
   125 of 223" tile has no picture.
3. **Trade returns.** The 80 closed trades' returns are summarised as mean and median that disagree in sign
   (P12a/b). They are not drawn as a distribution.
4. **The systems over the common window** (P14): only cumulative figures. Each system's daily path exists
   (ledgers plus `_record_mtd`) but no line is drawn.
5. **Shadow books** (P14a): `SHADOWS` are named, with no figure, even where a month exists (inferred for
   Recommendation from Nov 2026).
6. **Sector weight against the 750** (P7a): on a phone the benchmark column is hidden, leaving only a dashed mark.
7. **Duplicates.** Since-start appears in the h1, tile P3, P8a "This year", P8c, P10c Year, P10d and P14. Below-peak,
   peak date and Max DD appear in P3 and P9c. Month so far appears in P3, P8a and P14.
8. **Correlation 0.13** (P9e) is one number with no history; `qualified_view.correlation` could give a 90-session
   rolling line (inferred).

### Portfolio: what tipsheet's /models/ and /models/robust_momentum/ show that we don't

- Under every chart: Source, **Method, Table, Download CSV, JSON, Share image**. We have Source on 3 of 7 drawn
  charts (code), Table on 3. The owner declined CSV links (TODO S237).
- The growth chart is on a **log scale** with **marks for "Rule published" and "Entered the library"** and the end
  multiple labelled ("6.8× Robust equity momentum / 13.9× Benchmark"). Ours is linear (fine for 11 months), with no
  marks and no labels.
- The drawdown chart draws the model as a line over the **benchmark as a grey area**, with the latest values labelled.
- A tile "Against its benchmark −5.6 pts, **90% range before tax −8.7 to +1.4: could be luck**". We have no
  uncertainty on the lead. The data is in hand, so a bootstrap of the daily gaps is possible (suggestion; display only).
- **"Backtests and recorded returns"** table: the return split by basis (before publication, after, since library
  entry, frozen paper log, and how far the log differs from the recomputed backtest). Our equivalent is one sentence
  (P2).
- **"What it held"**: a 100% stacked area of holdings at every month-end. Ours is the stacked bars per rebalance
  plus the heat table (P7b/d).
- "The rule" in one paragraph and **"Sources"**, the research it comes from. We send the reader to the Guide
  (inferred).
- **After-tax return as the headline figure.** Ours is before tax and says "after costs". Tax on the record would
  be the owner's call (G8-like).
- The models index (/models/): one card per model with its current allocation bar and decision date. Our
  counterpart is P14, a table.
- We have what they don't: per-stock holdings with sell-rule distances, trades, the calendar grid and day by day.

---

## Page 2: Backtest (`/backtest`)

Data spine: `_history_bounds` → the long file `nse_long.load` (`data_cache/nse_long_close.parquet`, cached
`_long_file`, backtest_view.py:182-187) → `_history_inputs` (membership `engine.index_universe.index_history`,
`bp.industry_map`, optional traded value `_long_value`) → `run_backtest` (engine) → `gather` (:1001-1089): the Nifty
500 from `fetch_benchmark_history(period="max")`, the index store `indices_data.frames()` (Nifty Total Market,
Nifty200 Momentum 30, the Nifty 500's dividend yield), `data/backtest_reference.json` (`_reference`, the weekly
stored tests), `engine.backtest_page` (`bp.summary`, `falls`, `years_table`, `months`, `window`, `weekly_chart`,
`stale_exits`, `short_books`, `trade_stats`). The default page is served from stored parts (src/ui/backtest_snapshot.py,
key :40-47) when nothing has changed.

| # | Section (heading / kicker as shown) | Anchor | What it shows (form) | Data and where it comes from | Code | Redesign state against S237 |
|---|---|---|---|---|---|---|
| B0 | Site chrome (as P0) | – | – | – | components.py:100, :143 | As P0 |
| B1 | "**What was tested** Nifty 500 · Jan 2010 to Oct 2026 · 20 holdings · keep to rank 40 · rebalanced monthly, at the month’s last close · skip 0 days · Sharpe score · buy above its 50D EMA · within 20% of its 52-week high · six-monthly reset, winners run to 15% · 30 bps a round trip" | – | One line, first on the page (above the h1) | `tested_items(s, h)` | :474-513, emitted :1270, :1281-1282 | **G1 open**: on a phone it runs five lines and pushes the headline down; the lede is off the first screen (ours_backtest_iphone13_first.png). BACKTEST_REQ row 3 (owner) puts it **first**. Moving it is the owner's call; shortening it to "Nifty 500 · 2010–Oct 2026 · the record's rules · Change" with the full list in the expander is a suggestion |
| B2 | Expander "Change the test" (tune icon; remembers open or shut for the session) | – | `st.expander` + `st.form` with Apply | see controls | :320-438 | Keep. See B-controls |
| B2a | Info note when the chosen system is not the 750: "The … system does not change these runs: each run picks its own index in the settings below." | – | `kit.note` info | `system_param.current()` | :1243-1251, :1275 | Keep |
| B2b | Queue warning: "Backtest running: request queued. …" (two wordings); spinner "Running the backtest…" | – | `st.warning`, spinner | `compute_gate` | :1172-1190 | Keep |
| B3 | Kicker "BACKTEST"; h1 "Since January 2010, this rule made 18.7% a year, against a gain of 10.1% for the Nifty 500, before tax." | `s-top` | Sentence headline | `bp.summary(eq, bench)` | :527-546 | G1 partial: one answer, but no date line. **G2 open**: "made 18.7% a year" coloured via `kit.verdict` (:534) |
| B4 | Lede: "The record’s rules replayed on the Nifty 500 as it stood each month, 4 Jan 2010 to 30 Oct 2026, on NSE’s closes, after 30 bps a round trip. Price returns on both sides. A replay of the past, not a forecast." | – | Lede | – | :542-546 | G1: three sentences (close to two). Below the phone's first screen |
| B4a | Moved-start note ("…'s point-in-time list begins …, so the test starts there.") and, for a custom run, "**Warning:** These settings differ from the record’s…" | – | Note, `bt-warn` | `h["moved"]`, `f["default"]` | :547-551 | Keep. The warning word is coloured (`warn-word`), which is a label, fine |
| B5 | **1 · AHEAD OF THE NIFTY 500**; h2 "The rule is ahead of the Nifty 500 by 8.7 points a year; it was ahead in 121 of 202 months." | `s-lead` | Kicker + sentence h2 | `sm.lead`, `sm.ahead` | :555-565, :617 | **G2 open**: the whole clause "ahead of the Nifty 500 by 8.7 points a year" is in a coloured span (:561-562) |
| B5a | Four tiles: A year, compounded +18.7% (Nifty 500 10.1%) · Lead over the Nifty 500 +8.7 pts a year · ₹100 became ₹1,794 (Nifty 500 ₹501) · Months ahead 121 of 202 (60% · up in 130 months) | – | KPI tiles | `bp.summary` | :566-575 | G2 done (figures) |
| B5b | Chart: growth of ₹100, this rule and the Nifty 500 (dashed), **log scale**, weekly; lower pane below its peak (daily); readout "Latest · …" | – | dash_charts **"btgrowth"** (two panes, one crosshair) | `bp.weekly_chart(eq, {"n500": bench})` | :576-582, :618-619, dash_charts.js:636-670 | G3 mostly done: a familiar line over 16.8 years. **Open**: extremes not labelled (the −38.8% low of 23 Mar 2026, the July 2024 peak); no Nifty Total Market line, though it exists from Oct 2021 |
| B5c | Footer: What it is / How to read it, **Source: our replay on NSE's daily closes (the long price file, corporate actions applied); the Nifty 500 from NSE Indices.**, Show the table: Total return, A year compounded, A year before costs, Volatility, **Sharpe ± one standard error**, Sortino, Turnover one way a month | – | `how()` | `res["stats"]` | :607-616, :620-625 | G4 done in code (not in the capture). **Data shown poorly**: Sharpe ± stderr, Sortino and turnover are only in the folded table |
| B5d | Four notes: **Price returns, both sides.** (the dividend gap; about 0.8 pts a year smaller against total return) · **A year, compounded** is measured over calendar time, 16.8 years; pts · **Why the Nifty 500 and not Nifty Total Market.** · **The two halves.** To May 2018 ahead by 0.91 pts a month; after it, 0.50; median month +0.92 | – | Bold-led notes | `f["div_yield"]` (index store `dy`), `BOOK_YIELD`, `sm.split`, `sm.lead_first_half/second_half`, `median_lead` | :583-606, :626 | Four notes is a lot of text under one chart. "The two halves" is data, best as a small chart (a rolling 36-month lead line with its usual range, G3; suggestion) |
| B6 | **2 · FALLS FROM A PEAK**; h2 "The rule is 20.9% below its July 2024 peak. Its max drawdown since 2010, 38.8%, is not yet made back." | `s-falls` | Kicker + h2 | `bp.falls`, `bp.below_peak_now` | :629-644, :668 | **G2 open**: "20.9% below its July 2024 peak" in a `dh-down` span (:635) |
| B6a | Four tiles: Below its peak now −20.9% (Nifty 500 −10.6%) · Max DD −38.8% (Nifty 500 −38.3%) · Days below its peak 847 (since 5 Jul 2024; amber) · Recovered Not yet (needs +26.5%; amber) | – | KPI tiles | as above | :645-655 | "Not yet" in amber: a word coloured (G2 minor) |
| B6b | "Deepest drawdowns" table: Fall, Peak, Low, Back at the peak, Days below. Three rule rows (the open one marked), two Nifty 500 rows (muted) | – | Table | `bp.falls(eq, 3)`, `bp.falls(bench_cal, 2)` | :657-667 | **G3 open**: no chart of its own. The drawdown pane in B5b is the only picture, and its troughs are not labelled. An underwater chart with the three falls labelled (or labels on B5b's lower pane) is the tipsheet form |
| B6c | Note: "A fall runs from the highest close before it… Daily closes, as on Portfolio (`metrics.drawdown`)." | – | Note | – | :669-670 | **Internal name on the page**: `metrics.drawdown` in code type, against PAGE_DESIGN §2 "no internal names". No source line |
| B7 | **3 · YEAR BY YEAR**; h2 "The rule was ahead of the Nifty 500 in 12 of 16 whole years. 2025 was the worst, 28.9 points behind. 2026, to Oct, was ahead." | `s-years` | Kicker + h2 | `bp.years_table` | :707-751, :764 | **G2 open**: "12 of 16 whole years" (:741) and "28.9 points behind" (:745) in coloured spans |
| B7a | Year rows: Year (sub "Jan–Oct" for part years), a lead line bar (step 2.5 pts, dark zero line), This rule, Nifty 500, (universe index), Nifty Total Market (from 2022), Lead pts; readout on Tab; key "Each line is 2.5 pts" | – | dash_charts **"trows"** (line-bar rows: **tick strips**) | `years_table(eq, {n500, uidx, tm})` | :752-753, :765-766, dash_charts.js:453-466 | **G3 NOT done**: tick strips. BACKTEST_REQ rows 16 and 17 (owner-approved line bars, "Each line is 2.5 pts") must change with the owner's word. Familiar form: bars from zero per year (lead), or small multiples of rule vs index per year; the 17-year history allows a usual range of the yearly lead (shaded). **G4 open**: no `how()` footer, so no Source and no What it is |
| B7b | Note: "A dark zero line; a lead left of it is a year behind. The first year starts at the first fill, 4 Jan 2010. Nifty Total Market is NSE’s index, live from 14 Oct 2021, so it starts in 2022. November so far, to 27 Nov 2026, is not in the table: this rule is up 7.5%, the Nifty 500 up 9.4%." | – | Note | `res["live_meta"]` (strategy_mtd) | :754-762, :767 | The tick-strip explanation goes away with G3 |
| B7c | `<details>` "Show the table · month by month": a grid per year (This rule / Nifty 500 / Lead × Jan…Dec, Year) + note "Lead in pts…" | – | Folded table | `bp.months(eq, bench)` | :768, :782-806 | **Data shown poorly**: 202 months of lead sit folded with no picture. A monthly lead bar chart with a usual-range band (the bar kit has `band`) or a rolling 12-month lead line would be G3 (suggestion) |
| B8 | **4 · WHAT THE RESULT DEPENDS ON**; h2 "Tax costs the lead 2.8 points a year. Costs matter more than the rebalance rule." | `s-depends` | Kicker + h2 | `backtest_reference.json` rows, `after_tax` | :809-830, :864 | **G2 open**: "2.8 points a year" span is a figure plus words (:824), borderline |
| B8a | Rows: As tested 18.7% (bold), Monthly reset, Costs 60 bps, Costs 100 bps, After tax, Nifty 500 (price index), Nifty 500 after tax; a dashed line at the Nifty 500; optional column "From Mar 2012, a year"; key "Each line is 0.5%; the dashed line is the Nifty 500" | – | dash_charts **"trows"** (tick strips, 0 to hi %) | `ref["rows"]`, `ref["after_tax"]`, `ref["from_2012"]` | :835-866 | **G3 NOT done**: tick strips (BACKTEST_REQ row 19, owner-approved). A horizontal bar or dot chart on one 0–20% axis is the familiar form; a return-against-max-DD scatter (tipsheet /models/indices/) would add risk, but the stored tests hold no max DD per row (inferred), so it would need new runs. **G4 open**: no source line |
| B8b | Note: "The rows other than “As tested” and “Nifty 500” are re-run once a week on the default settings only (run of 25 Nov 2026). After tax: STCG 20.8%, LTCG 13% above Rs 1.25 lakh… These tests were run on the long file to 23 Nov 2026; this page reads the file to 27 Nov 2026… From 1 Mar 2012: …" | – | Note | `ref["built"]`, `ref["rates"]`, `long_last_session` | :867-874 | Long. "Rs 1.25 lakh" against the site's ₹ elsewhere (wording; S173 rule check, inferred) |
| B8c | Custom-run state: h2 "Costs, the rebalance rule and tax are tested for the default run only." + note | – | h2 + note | – | :875-878 | Keep in the redesign |
| B8d | "Against what you could buy" table: group "Since Nifty200 Momentum 30 went live · 31 Aug 2020 – 30 Oct 2026" (This rule, Nifty 500 +23.6% / −38.8%; Nifty200 Momentum 30; Nifty 500); group "Since Nifty Total Market went live · 1 Nov 2021 – 30 Oct 2026" (This rule Nifty 500; This rule, Nifty Total Market; NTM; Nifty 500). A year, Max DD | – | Grouped table | `bp.window`, `ref["total_market_universe"]` | :879-889 | Table only. A ₹100 line per window (small multiples, two panes) would be G3 (suggestion) |
| B8e | Note: "NSE’s Nifty200 Momentum 30 is the nearest index a fund tracks; it is a price index too. These windows are short and include this rule’s max drawdown." | – | Note | `_windows_cover_max_drawdown` | :890-892, :896-899 | Fine |
| B9 | **5 · CAN IT BE TRUSTED**; h2 "Survivorship and look-ahead are handled; costs, tax and the choice of rules are the soft spots; 3 checks are not made." | `s-trust` | Kicker + h2 | `trust_headline(checks)` | :688-704, :954-955 | **G2 open**: "costs, tax and the choice of rules" in an amber span (:700) |
| B9a | Checklist table: Check, What this run shows, Status. Rows: Survivorship, Look-ahead, Stocks that stopped trading (7 sales, ALFALAVAL…), Cash (April 2020: 10 stocks), Costs, Tax, Rules chosen after looking (the 12 Oct sweep, the shadow books), Sector cap, The index before Feb 2012 (S167), A second source for the result | – | Table | `stats["pit_periods"]`, `bp.stale_exits`, `bp.short_books`, `SHADOWS`, `h["unlabelled"]` | :902-958 | **G2 open (minor)**: Status words coloured (:952-953). Tipsheet's answer to "Rules chosen after looking" is a figure: back-tested excess against live excess, and a deflated Sharpe counting every rule tried. Ours is words only |
| B10 | **6 · TRADES**; h2 "1,582 trades closed; fewer than half won (47%). The winners paid for the losers: gains were 2.09 times the losses." | `s-trades` | Kicker + h2 | `bp.trade_stats(closed_trades)` | :961-971, :979 | **G2 open**: "fewer than half won (47%)" in a `dh-down` span (:967) |
| B10a | Five tiles: Trades closed 1,582 (20 still held) · Won 47% · Median holding 61 days · Median trade −0.9% (mean +5.1%) · Gains over losses 2.09× | – | KPI tiles | as above | :972-978 | **Data shown poorly**: the median below zero and the mean above it is a skewed distribution with no picture (histogram of 1,582 trade returns; data in `closed_trades`) |
| B10b | Note: "Every trade and the rebalance log are below; the live record’s trades are on Portfolio, which owns the record." (link) | – | Note + link | `page_href("portfolio")` | :980-981 | Fine |
| B10c | Empty state h2: "No trade closed in this run." | – | – | – | :963-964 | Keep |
| B11 | Download button "Download the rules and every trade (ZIP of 2 CSV files)" (`backtest_<index>_YYYYMM_YYYYMM.zip`); fallback caption "The download is not available for this run…" | – | `st.download_button` (built lazily on the stored default page) | `_export` → `rules_table(RunSpec…)`, `trades_table`, `export_zip` | :1194-1229, :1145, :1297-1299, :1323-1324 | Keep (owner, 8 Oct). It sits between section 6's note and the expander |
| B12 | Expander "Show the table · every trade and the rebalance log" (closed) | – | `st.expander` → dash_charts **"history"** (Trades / Rebalance lines; filters) + HISTORY_FILL note ("…Returns are before costs.") | `pr.trades_table(closed_trades, tradebook, …)`, `history_spec`, `_reason` | :1126-1129, :1146-1147, :1117-1123 | **G4 open**: no source. Same component as P13 |
| B13 | Footer: "Data to 30 Oct 2026 · NSE’s long price file, the last completed month · prices to 27 Nov 2026 · indices to 27 Nov 2026." | – | `dh-foot` | `sm.last`, `f["long_last"]`, `store.as_of` | :984-987, :1138 | Fine |
| B14 | Whole-page empty and error states: "No long price file yet." · "No completed month to test yet." · "No membership history for …" · "… has no completed month in the window chosen." · "Traded value is not available right now, so the floor is off…" · "The Nifty 500's closes are unavailable." · "Not enough price history for this window." · `kit.empty("No completed month in this window yet.")` | – | page_empty, notes | – | :241-256, :272-278, :295-301, :1284-1311 | Keep all eight in a redesign |
| B15 | Stored default page (no reader-visible text): the parts are cached under a key over settings, inputs, benchmark, index store, reference and code | – | – | src/ui/backtest_snapshot.py:40-47 (key), save/load | :1289-1302, :1325-1328 | **Redesign trap**: any change to the parts changes `code_fingerprint`, so the first visit after a deploy pays the full ~23 s run (docstring, backtest_snapshot.py:1-15) |

### Backtest (a) controls and what they change (all inside "Change the test"; nothing runs until Apply)

| Control (label as shown) | Kind / key | Changes | Code |
|---|---|---|---|
| Universe | selectbox `bt_hist_index` | Index and membership (point in time) | :331-333 |
| Start and end month | select_slider `bt_hist_months` | Window; a later list start moves it (B4a) | :335-338 |
| Minimum traded value (₹ Cr, 20-day average; 0 = off) | number_input `bt_hist_floor` | Liquidity floor (loads traded value) | :339-341 |
| Holdings | number_input `bt_top_n` | top_n | :345 |
| Keep a holding while its rank is within the top | `bt_keep_rank` | buffer_n (raised to holdings) | :346-350 |
| Rebalance every (trading days) | `bt_rebal_days` | 21 = month-end signal; else every N sessions | :352-356 |
| Weighting (Equal weight / Inverse volatility) | selectbox `bt_weight_scheme` | weight_method | :357-360 |
| Rebalance rule | selectbox `bt_rebalance_rule` | six-monthly reset or monthly reset | :361-368 |
| Cut a holding back when it grows past (% of the book) | `bt_hold_cap` | hold_cap (six-monthly rule only) | :369-374 |
| Trading cost (bps a round trip) | `bt_cost` | cost_bps | :375-380 |
| To buy / To keep holding: Close above its EMA of (sessions) ×2 | `bt_ema_period`, `bt_exit_ema` | Entry and exit EMA | :387-394 |
| Within this % of its 52-week high ×2 | `bt_52w_off`, `bt_exit_52w` | high_pct, exit_high_pct | :395-402 |
| Within this % of its all-time high ×2 | `bt_ath_off`, `bt_exit_ath` | ath_pct, exit_ath_pct | :403-409 |
| All-time-high rule: years of prices on file before it applies | `bt_ath_years` | ath_min_years | :410-415 |
| Score each lookback window by (Sharpe / Plain return) | radio `bt_score` | score_method | :419-423 |
| Leave out the latest sessions (days) | `bt_score_skip` | score_skip | :424-428 |
| Lookback weights 1M · 3M · 6M · 9M · 12M | sliders `btw_1..5` | Score weights | :429-434 |
| Apply | form_submit_button | Runs; a non-default run is live (not stored), shows the warning (B4a) and drops the stored tests (B8c) | :438, :456-468 |
| btgrowth pointer, finger, arrows; trows rows by Tab | In-frame | Readouts | dash_charts.js |
| Show the table (B5c), Show the table · month by month (B7c) | `<details>` | Unfold | :625, :768 |
| Download ZIP | download_button `dl_bt_export` | File | :1224 |
| Trade log expander + view chips and filters | expander + in-frame chips | Rows | :1146 |
| System (`?sys=`) | off-page | Nothing but the info note (B2a) | :1243-1251 |

Stock and sector caps come from Configuration (app.py:1243-1248: `stock_cap`, `sector_cap`, `weights`,
`liquidity_floor_cr`) and count in `is_default` (:467-468): a changed cap on Configuration makes the Backtest
"custom" (inferred).

### Backtest (b) data read but shown poorly

1. **The 202 monthly leads** (`bp.months`) appear only in the folded grid (B7c). There is no monthly bar with a
   usual range and no rolling lead line. "The two halves" (B5d) is a sentence where a picture would do the work.
2. **Year rows and sensitivity rows** are tick strips (B7a, B8a), not familiar bars.
3. **Drawdowns** (B6b): five falls in a table, with no labels on the drawdown pane.
4. **Trade returns** (B10a): a skewed distribution (median −0.9%, mean +5.1%) given as two numbers.
5. **Risk statistics** (Sharpe ± stderr, Sortino, volatility, turnover) are folded in B5c's table; the ± is the
   only uncertainty on the page.
6. **Nifty Total Market and the universe index**: read for B7a and B8d, but not drawn on the ₹100 chart.
7. **Stale exits and short books** (`bp.stale_exits`, `bp.short_books`) are sentences inside the checklist. Fine as
   is; listed for completeness.
8. **The stored test from Mar 2012** (`ref["from_2012"]`): a second column of tick-strip values (B8a), easy to miss.

### Backtest: what tipsheet's /lab/ and /models/indices/ show that we don't

- **A question headline** ("Which mix of Indian assets has done best, after costs and tax?") with the answer and
  the multiple-testing caveat in the lede ("With 141 portfolios tried, the in-sample winner ranked below the median
  out of sample in 66%…"). Ours puts the settings line above the headline.
- **After tax first.** We give after tax once, in B8 (default run only).
- **A 90% interval against the benchmark** in every row ("vs 60/40, 90% interval"), and in the model pages
  "could be luck". Ours: Sharpe ± stderr, folded.
- **Back-tested against live excess** ("Factor indices, before and after launch"), the figure behind our
  "Rules chosen after looking" soft spot. We could show the rule's lead before and after 1 Oct 2026 (the record's
  live date), or each shadow book's months. Display only; the record is not touched.
- **"Which asset won each year"**: ranked colour columns per year. Our counterpart is B7a's year rows.
- **Small multiples of growth on a log scale, one per family**, each with "How to read it" naming the fastest and
  slowest line. Ours: one chart.
- **Return against worst fall, scatter** (/models/indices/), and a ranked bar of returns a year.
- **A period table** (1 month, this year, 1, 3 and 5 years, since start, a year) with launch dates. We have
  no 1Y/3Y/5Y periods for the rule (inferred: `bp.window` could cut them).
- **A rebasing date range dragged under each chart** ("drag the date range below a chart … every line rebases").
  Ours changes the window only through the form and a full re-run.
- **"On this page" navigation.** The Backtest has numbered kickers but no nav pills (Portfolio has them, P4).
- Source + Method + Table + CSV + JSON under every chart. Ours: Source under B5c only; nothing under B7a or B8a.

---

## Sections per page

- **Portfolio**: 15 top-level rows (P0-P15), 44 rows with sub-sections. Eight anchored sections (`pf-book`,
  `pf-exp`, `pf-ret`, `pf-eq`, `pf-cal`, `pf-day`, `pf-trades`, `pf-sys`), plus the header, the trade-history
  expander and the footer. Six drawn frames: holdings, growth, month bars, day bars, history, plus the hand-drawn
  sector bars, size bars and heat table.
- **Backtest**: 15 top-level rows (B0-B15), 39 rows with sub-sections. Settings line, form, head, six numbered
  sections (`s-lead`, `s-falls`, `s-years`, `s-depends`, `s-trust`, `s-trades`), the download, the log expander and
  the footer. Four frames: btgrowth, trows ×2, history.

## The five most important redesign gaps

1. **Backtest §3 and §4 are tick strips** (G3 not done; G4: no footer, so no Source): `backtest_view.py:765`
   (year rows, "Each line is 2.5 pts") and `:865` (sensitivity rows, "Each line is 0.5%"). Replace with yearly lead
   bars from zero with a shaded usual range, and a horizontal bar or dot chart on one axis. Each with a `how()`
   footer. Needs the owner's word: BACKTEST_REQ rows 16, 17 and 19 fix line bars.
2. **Backtest first screen** (G1/G2): the five-line "What was tested" line and the form sit above the headline
   (`:1270-1282`, `:510-513`). The headline colours "made 18.7% a year" (`:533-535`). Every section h2 colours a
   clause (`:561`, `:635`, `:700`, `:741`, `:745`, `:967`). There is no date line. Moving the line needs the owner
   (BACKTEST_REQ row 3); recolouring is benchmark-decidable (G2).
3. **Portfolio first screen** (G1/G2): a five-sentence lede (`portfolio_page.py:420-421`, with `_provenance`
   `:330-343`) and coloured verdict phrases in the h1 (`:361-374` via `page_kit.py:164-169`). No chart on the first
   screen. The first tiles repeat in P9c (`:716-725` against `:403-416`).
4. **Portfolio charts lack the record's marks and history devices** (G3): the ₹100 chart (`:755`, `growth_spec`
   `:669-683`) has no "worked out on 1 Oct 2026 / recorded since" mark and no labelled max-DD trough. The month-lead
   bars (`:1177`, `month_bars_spec` `:862-869`) send no `band` and have no `how()`. The day bars draw 20 of 223
   sessions (`:888-894`). The sector, size and heat blocks (`:515-574`) are hand-drawn HTML with no readout or
   source.
5. **G4 is only where `how()` is used, and three owner rules still forbid sources.** No Source line under the
   Portfolio holdings (`:495`), sector and size blocks (`:568-574`), month bars (`:1177`) or history (`:1195`), or
   under the Backtest trows ×2 (`backtest_view.py:765`, `:865`) and history (`:1137`). Against: PAGE_DESIGN.md:60,
   PORTFOLIO_REQUIREMENTS row 22 and BACKTEST_REQUIREMENTS row 29 say "no source"; settle with the owner before
   calling G4 done.

Suggestions above that touch figures are display only: marks, labels, distributions, rolling lines from series the
pages already compute. None moves published ranks, the frozen track record or model-book money. A tax figure on the
live record, or total-return benchmarks (G8), stay the owner's.

## Not checked

- Rendering after #720's deploy (the Source lines and the month-bars caption) on the live site; the capture predates it (inferred).
- Desktop screenshots (`*_desktop_full.png`) were not opened; layout notes are from code and the phone first screens.
- The Configuration page's system picker (assumed from `system_param`).
- Whether `backtest_reference.json` holds a max DD per stored test (needed for a return-against-fall scatter).
- The shadow books' ledgers (whether "Recommendation" has a frozen month to show).
