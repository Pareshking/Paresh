# Inventory B: Screener, stock page, Watchlist (28 Nov 2026)

Read-only inventory for the S237 redesign. Sources: code at `525085e1` (main checkout, clean); live text captured
28 Nov 12:03 UTC (`s237/ours/ours_screener.txt`, `ours_screener_stock_RELIANCE.txt`, `ours_watchlist.txt`).
Rules G1-G4 from `docs/archive/S237_COMPARISON_2026-11-28.md`; G3 counts tick strips / line bars / ring scales as
NOT done. File:line refers to `/home/user/Paresh`.

**Not checked:** the screenshots themselves (text only); the Screener table's contents (it is an iframe, so it is
not in the live text, read from code only); the Watchlist with saved stocks (the capture was the empty state, so
its sections are from code only); Nano Cap / Nifty 1000 / Combined views; the phone layout.

**One conflict to settle before G4 is built on these pages:** PAGE_DESIGN.md:60 and SCREENER_REQUIREMENTS row 24
("no source named", owner 20 Nov) against G4 ("Source:" under every chart). TODO S237 says G4 was built on 13 chart
footers "naming the exchange only, no vendor names", which reconciles the two. None of these three pages uses the
`how(..., source=)` footer (`dashboard_home_view.how`), so `tests/test_s237_chart_sources.py` does not cover them.

---

## 0. Shared header (on all three pages; drawn by app.py before the page)

| # | Section | Anchor | What it shows | Data and source | Code | State |
|---|---|---|---|---|---|---|
| 0.1 | Skip links, brand "Paresh Patel", 11 page links (desktop) / menu popover (phone) | `#content` (skip target) | Navigation | `_PAGES` in app.py | app.py:1275-1289; components.py:212-266 | G7 open (the site's name is the owner's call) |
| 0.2 | Prices pill "Prices · closes of 27 Nov" (amber "Late:" when a source is behind) | – | One date pill | `data_freshness()` | components.py:96-118 (`_status_pill_html`), :238 | Fine as the date line. It sits in the header, not over the headline (G1, partly) |
| 0.3 | Stale / pending notices ("Late: …") | – | Alert line, shown only when there is a problem | `stale_prices_notice`, `pending_history_notice` | components.py:268-273 | Fine |
| 0.4 | Market line: "● Nifty Total Market 4.4% above its 200D EMA · Nifty Total Market 13,494 · Universe 750 · Above 50D EMA 353 (47%) · Near 52W high 374 (50%)" | – | A strip of 5 figures with no history | `regime_data`, `count_above_ema(rank_df)` | app.py:1341-1353; components.py:180-199 | **G2 open:** the whole phrase "Nifty Total Market 4.4% above its 200D EMA" is coloured (`.mkt-regime.mkt-up`, page.css:291). S237 G7: show the strip once, on Market, not on every page |

## 1. Screener (`/screener`)

Order (approved 21 Nov): Screener → Qualified: → What moved since → Data to. Route: app.py:1146-1160 → `render_ranking_view`, ranking_view.py:256.

| # | Section (as shown) | Anchor | What it shows | Data and source | Code | Redesign state |
|---|---|---|---|---|---|---|
| S1 | Kicker "SCREENER" + H1 "All of the top 50 pass both filters. 24 of them were not in the top 50 on 27 Oct." | – (`.scr-head`) | Headline in two sentences | `screener_title(rank_df, adj_close)`: top 50 by Rank, `_passes` (Above 50 EMA & Near 52W High), Rank (-1M) | ranking_view.py:421-422, 782-808; page_kit.py:43-58 | G1 partly: the answer comes first, but the headline is two sentences and there is no date line over it (the date is in the lede and the pill). Colour: none (G2 done) |
| S2 | Lede "The 750 ranked stocks of the 750, by momentum at the 27 Nov close. The book buys the top 20 qualified and keeps a holding while it is in the top 40." | – | Two sentences | `screener_lede`, `TRACK_RECORD_CONFIG` top_n / buffer_n, `screener_universe()` | ranking_view.py:811-833 | G1 done (two sentences). Wording: "The 750 ranked stocks of the 750" repeats itself (a wording fix) |
| S3 | Export CSV (page-head action, right) | – | Download button; its tooltip says rows are in rank order and the file has all N columns | `export_columns(view)` → `csv_bytes`; file `nse_momentum_rankings_YYYYMMDD.csv` | ranking_view.py:246-253, 645-659, 187-198 | Fine; it is the page's one download (S237 G4: owner, 28 Nov, wants no CSV everywhere) |
| S4 | Signal chip (only when it applies): "Fewer than 20 pass both filters: the book cannot fill its 20 places." | – (`.sig-row`) | Amber chip | `compute_signals(rank_df)` | ranking_view.py:423-425; components.py:54-94, 278-287 | Not shown on 28 Nov. **G2 open when shown:** the whole sentence is amber on a tinted ground |
| S5 | Toolbar: search box "Search stock, sector or index" | – (`st-key-scr_toolbar`) | Selectbox. A stock opens its page; an index, sector, NSE macro / industry / basic industry (or TradingView's two levels when NSE's are missing) filters the table. Renamed tickers (S227) and stocks listed in the last year that are not ranked yet (S236 F18) are found too | `search_options` from rank_df Symbol / Industry / Indices / NSE_* / TV_*; `renamed_on_nse`; `nse_identity.recent_listings` | ranking_view.py:332-414, 450-456, 469-479, 553-589 | Control (see 1a) |
| S6 | Toolbar: preset pills "All 750 · Top 50 qualified 50 · Top 50 not qualified 0 · Pass both filters 288 · Big movers 258 · Volume spike 84" | URL `view=` | Pills with their counts | `preset_counts`; `BIG_MOVE_PLACES` = 150; Volume == "High" | ranking_view.py:432-448, 480-488, 591-614 | Control. "Pass both filters 288" is the page's only breadth count, with no history (see 1b) |
| S7 | Toolbar: popover "Filters & columns" → Index pills (several; NSE names, our groups last), toggle "Only stocks that pass both filters", segmented "Columns" Executive (n) / Core (n) / Full Quant (n), caption "Click a column header to sort the table.", "Reset" | URL `idx=`, `pass=`, `cols=` | Popover; a bottom sheet on a phone | `INDEX_NAMES`, `column_count` | ranking_view.py:489-541, 667-677 | Control. "Executive / Core / Full Quant" are house words (S237 Words) |
| S8 | Key ("Qualified:", "Rank before:", "Held:", "Big movers: … Volume spike: …"); two columns on a wide screen, folded on a phone as "How to read the table" | – (`.scr-key`, `details.scr-key-narrow`) | 4 short paragraphs | `_key_numbers` from the rules (high_pct, top_n, buffer_n, VOLUME_SPIKE, VOLUME_WINDOW) | ranking_view.py:544, 837-873 | Fine (G2 done: bold labels in ink). It sits above the table, so on a desktop the table starts below a four-paragraph key |
| S9 | Ranking table (iframe): group row ("Rank before", "Qualified", "Company", "Filters and highs", "1 month" … "12 months" or Returns / Risk, "Exits", "Data health", "Trend") over the column headers | – (iframe, title "Ranking table") | HTML table; first 50 rows; sticky header plus Rank and Stock pinned; header-click sort with arrows; "more columns →" fade at the right edge; a row opens the stock | `with_book_columns(rank_df)` (Qualified Rank, Qualified (-3M/-1M), Held); `_new_high_counts` (New Highs 1M/3M); `_year_paths` (last 60 closes) | ranking_view.py:546-552, 627-633; screener_table.py:77-159, 683-798, 804-829 | Table: Full Quant by default, so about 35 columns at 1400 px. **G3 open:** "60D" sparkline (no axis, scale or usual range, only 60 sessions). Colour on figures only (G2 done in the table) |
| S9a | Columns in Full Quant order: Rank · Stock (symbol, "Held" tag, industry on a phone, cut-line note) · Price · 3M ago · 1M ago · Qualified # · Score · NSE index · Sector · Market cap, Cr · From 52W high · From all-time high · vs 50D EMA · Volume (Spike/Normal) · Above 50D EMA ✓/✗ −x% · Near 52W high ✓/✗ −x% · At all-time high · New highs 1M · New highs 3M · {1,3,6,9,12}M return / Sharpe / max DD (with † for since listing) · Stop loss · Chandelier exit (only when the ranking carries ATR) · Price gap ✓/✗ · Filled % · Horizons n/5 · 60D | – | Cells | rank_df columns (DISPLAY_COLS ranking_view.py:201-243) | screener_table.py:120-137, 310-482 | See 1b: Score, Sharpe, Filled, Horizons and New highs have no explanation in the key. Stop loss / Chandelier stay in Full Quant although the owner took them off the stock page (22 Nov), shown only when ATR exists |
| S9b | Cut-line notes on the 20th and 40th qualified rows: "The book buys to here: the 20th qualified" / "A holding is kept to here: the 40th qualified" (rank order only) | – | A rule under the row plus a note | `BUY_CUT`, `KEEP_CUT` | screener_table.py:345-348, 532-534, 556 | Fine |
| S9c | Phone list (<640 px): Rank, Stock + industry, 60D line, Price with "+x% 3M" under it (Executive / Core); Full Quant scrolls sideways | – | Compact list | same | screener_table.py:573-591, 703-706, 753-784 | Not checked live (phone) |
| S10 | "Show all 750" / "Show first 50" button | – | Button that redraws the frame at full height | `SHOW_ALL_KEY` | screener_table.py:815-828 | Fine |
| S11 | Empty state: "No stock matches these filters. Clear the search or pick another preset." | – (`.pg-empty`) | Plain line | `mw.NO_MATCH`, `NO_MATCH_WAY_OUT` | screener_table.py:808-813; page_kit.py:157-161 | Fine |
| S12 | Caption "† Max DD since listing: the stock has fewer months of prices than the window." | – | Footnote (when some row carries †) | `has_since_listing(view)` | ranking_view.py:634-636; screener_table.py:485-494 | Fine |
| S13 | Kicker "WHAT MOVED SINCE 27 OCT" + H2 "24 stocks entered the top 50 since 27 Oct and as many left. GREAVESCOT climbed furthest into it, 437 places, from 445th to 8th." | `#t50-movement` | Serif heading | `top50_changes`, `biggest_jumps(entered)`, `_month_ago` | ranking_view.py:1041-1067, 1081-1082 | **G2 open:** "24 stocks entered the top 50" (up colour) and "as many left" (down colour) are whole phrases (`.mv-h .up/.down`, ranking_view.py:959, 1048-1053) |
| S14 | Note "Ranks among the ranked stocks on 27 Oct, the last session on or before the same date a month back, against today. Every row shown." (+ "– in Rank 27 Oct and Places: …" when a stock was not ranked then) | – | Sentence | `mw.column_note`, `stock_too_new` | ranking_view.py:1068-1076 | Fine |
| S15 | "Biggest jumps 10": "The 10 that climbed most places anywhere in the ranking, 1 to 5." + table; "Biggest jumps, 6 to 10" table beside it | – (`.mv-grid`) | Two tables: Stock (sector, Held tag) · Rank 27 Oct (grey) · Now · Places (±, coloured) · 1M return (coloured) | `biggest_jumps(rank_df, 10)` | ranking_view.py:702-710, 985-991, 1016-1038, 1077-1078 | Tables only; colour on figures (G2 done). **G3 open:** a climb is shown as two numbers; a slope (dumbbell) chart would show it (inferred suggestion) |
| S16 | "Entered the top 50 24": "In the top 50 now, not on 27 Oct." + table (every row) | – | Table, same columns | `top50_changes` | ranking_view.py:685-699, 1085-1086 | Same as S15 |
| S17 | "Left the top 50 24": "In the top 50 on 27 Oct, not now." + table (every row, Held tags) | – | Table, same columns | same | ranking_view.py:1087-1088 | Same as S15 |
| S18 | System footnote (Nano Cap, Nifty 1000, Combined only): "N of the …'s M stocks are ranked, as one list / among themselves." + "K are not ranked yet: {reason}. A, B, C." (amber on the Nifty 1000, muted otherwise) | – (`.pg-note` / `.pg-info`) | Note listing every name | `system_note`, `not_ranked_reason`, `data["idx_info"]` | app.py:1091-1101; ranking_view.py:713-746, 662-663 | Not on the 750 (not seen live). The Nifty 1000's amber note puts colour on the whole note (G2, inferred) |
| S19 | Foot "Data to 27 Nov 2026 · NSE. 750 stocks ranked; 0 with a price gap, 5 with a short history." (+ amber "Late: …" per behind source) | – (`.qp-note`) | Sentence | `_fmt.data_to(session_of(adj_close))`, `gap_count`, Short History, `data_freshness` | ranking_view.py:664, 935-951 | Fine. G4 open: no chart on the page has a source line (only the 60D sparkline counts as a chart). No "© Paresh Patel" line here, unlike the stock page and Watchlist (inferred from code: the Screener does not call `render_data_quality_footer`) |

### 1a. Screener controls

| Control | Changes | Kept where |
|---|---|---|
| Search (stock) | Opens `?stock=SYM` | – |
| Search (index / sector / NSE levels / TV levels) | Filters the table only; the movers section stays on the whole ranking | session only (not in the URL; `?ind=` from the stock page seeds it once, ranking_view.py:458-466) |
| Preset pills | Filters the table; Big movers sorts by places moved and adds a "Places, 1M" column (screener_table.py:179-181) | URL `view=` |
| Index pills (several) | Filters the table by exact tag | URL `idx=` |
| Only pass both filters | Filters the table | URL `pass=1` |
| Columns Executive / Core / Full Quant | Column set; also phone layout (Full Quant scrolls sideways) | URL `cols=` |
| Reset | Clears all four and Show all | – |
| Column headers | Sort every row on the client (keyboard too); the cut lines show only in rank order | not kept |
| Show all / Show first 50 | Frame height and rows shown | session |
| Export CSV | Downloads the filtered rows, every column, in rank order (not the on-screen sort) | – |
| Row / symbol links | Open the stock page in the parent window | – |

### 1b. Screener: data read but shown poorly

- **Rank history:** only 3M ago and 1M ago as two grey numbers; `daily_history` (app.py:1163) and the deep closes hold a rank for every session, so a rank line over 12 months is possible (inferred: `rank_trails` / `rank_history_position` give any date).
- **Score** (composite, e.g. 0.359): no scale, no distribution, not explained in the key (screener_table.py:349-351).
- **Sharpe** per window: "not annualised" is said on the stock page only; the Screener gives no explanation, so the five Sharpe columns can't be read.
- **"60D" sparkline:** 60 sessions, no axis, no 52W context; 12M or 3Y closes are already loaded (`history_prices`).
- **Filled %, Horizons n/5, Price gap ✓/✗:** "Data health" columns with no key line.
- **New highs 1M / 3M:** counts with no reference (what is a lot?).
- **Market cap, Cr:** a full rupee figure in a 35-column grid, no size band; the NSE index column carries the size.
- **Big movers 258 / Pass both filters 288:** counts with no history. SCREENER_REQUIREMENTS already found that the 150-place rule drifted (118 → 268 stocks).
- **What moved:** Places and 1M return as numbers only; no picture of the climb.

## 2. Stock page (`/screener?stock=RELIANCE`)

Route: app.py:1328-1336 sends any `?stock=` to the Screener; ranking_view.py:284-322 → `render_stock_view`, stock_view.py:543.
Order (STOCK_REQUIREMENTS.md:18): 1 Rank → 2 Filters and sell rules → 3 Returns and falls → 4 Price → 5 Results → 6 Sector → 7 Data → Data to.
Content benchmark (S237): a broker's or Screener.in's company page.

| # | Section (as shown) | Anchor | What it shows | Data and source | Code | Redesign state |
|---|---|---|---|---|---|---|
| P0 | Browser tab "RELIANCE · Paresh Patel" | – | Title | requested symbol | ranking_view.py:307 | Fine |
| P1 | Renamed line (only for a renamed ticker): "NSE has listed OLD as NEW since …; the ranking files it under OLD until the list is rebuilt in January." | – (`.dh-sub`) | Sentence above the toolbar | `sl.renamed_on_nse` (S227) | stock_view.py:576-582, 617-620 | Fine. It is drawn above the toolbar, so it comes before Back (inferred order) |
| P2 | Toolbar: "← Back to screener" · "Add to watchlist" / "In watchlist" (star) · "Share" popover (caption + copyable `/?stock=SYM` code box) · "Chart on TradingView" (new tab) | – (`st-key-sp_actions`) | Buttons | `watchlist_store.toggle`; `_share_url`; `kit.tradingview_url` | stock_view.py:227-255; ranking_view.py:300-304 | Control. G1: the toolbar comes before the headline |
| P3 | Kicker "STOCK · RELIANCE · OIL & GAS · NIFTY 50" | – (`.kicker`) | Kicker | `sl.kicker(row, INDEX_NAMES)` | stock_view.py:261, 265; stock_lines.py:157-167 | Fine |
| P4 | H1 "Reliance Industries is 250th of 750, passes both filters and is not in the model book." | – (`.dh-h1`) | Serif headline | `sl.title` | stock_view.py:265; stock_lines.py:170-174 | G1 done for the headline (one sentence, no colour). No separate date line above it |
| P5 | Lede "₹1,383 at the 27 Nov 2026 close. Down 11.6% over 12 months, against up 0.3% for Nifty Total Market. Market cap ₹18.71 lakh Cr." | – | Three sentences | `sl.lede`: CMP, 52W High Date, 12M Return, market 12M (`_market()` → `benchmark_indices.TOTAL_MARKET`), Market Cap (Cr) | stock_view.py:266; stock_lines.py:177-198 | **G1 open:** three sentences, not two (a fourth paragraph follows, P6) |
| P6 | "It also ranks 324th of 1,000 in the Nifty 1000 and 385th of 1,129 in Combined. See it in the Nifty 1000 → · See it in Combined →" | – | Sentence + links | `wl.ranks_elsewhere(sym, other_rankings())` (app.py:1201-1212) | stock_view.py:267-268, 516-526, 642 | Fine. It pushes the tiles down on the first screen (G1) |
| P7 | Four tiles: "Close, 27 Nov ₹1,383 / +15.6% over 1M" · "Rank of 750 250 / 629 three months ago" · "Place among the qualified 217th of 288 / the book buys the top 20" (or "Out / fails …") · "In the model book +x% / since d, w% of the book" (when held) | – (`.sp-tiles`) | Tiles in the serif, 30 px | `sl.tiles`; `qualified_ranks`; `_holding` → Portfolio's `book_series` | stock_view.py:262-264, 269; stock_lines.py:207-228 | **G3 open:** single figures with no line or history. Tiles repeat the headline (rank) and the lede (close). The 1M figure is coloured (G2 done) |
| P8 | "1 · RANK" + H2 "217th of the 288 that pass both filters, past the book's keep line." | – (no id) | Serif heading | `sl.rank_heading` | stock_view.py:272-273, 300; stock_lines.py:252-260 | **G2 open:** the phrase "past the book's keep line" is coloured (down) |
| P8a | Rank table: rows "Rank of 750" 629 · 485 · 250 and "Place among the qualified" Out · Out · 217th; columns 3M ago (27 Aug) · 1M ago (27 Oct) · Now (27 Nov) | – | Small table | Rank (-3M/-1M), Qualified (-3M/-1M) via `with_book_columns` → `dashboard_insights.rank_trails` | stock_view.py:274-278, 301-303; stock_lines.py:238-245 | Fine as a table |
| P8b | Note "A past rank is how today's rule ranks the stock … Its score is 0.359, with all five horizons scored." | – | Paragraph | `sl.rank_note` (Score, Horizons Scored) | stock_view.py:304; stock_lines.py:263-272 | Score has no scale (1b) |
| P8c | Rank trail picture (220×170 image): 3 points with dashed "Buy line, 20th" and "Keep line, 40th"; caption "Place among the qualified; higher is better." | – (`.sp-trail img`) | 3-point line, an "Out" at the bottom | `sl.trail_points` | stock_view.py:279-299, 305; stock_lines.py:275-285 | **G3 open:** three points, no history (daily rank exists), "Out" has no value. **G4 open:** no source line |
| P9 | "2 · FILTERS AND SELL RULES" + H2 "It would be sold if held at the 30 Nov check if today's price holds: it is 217th among the qualified, past the top 40." | – | Serif heading | `exit_watch.assess` → `sl.rules_heading`; `next_rebalance` | stock_view.py:308-314, 337, 610-613; stock_lines.py:373-396 | **G2 open:** the clause "It would be sold if held" is coloured. Wording: "if held … if today's price holds" says "if" twice |
| P9a | Price ladder: 52W low ₹1,158 (28 Oct 2026) · −20% line ₹1,274 (filter line) · 50D EMA ₹1,292 (trend line) · 52W high ₹1,592 (2 Jan 2026), with a dot for the close | – (`.sp-ladder`, role=img) | A one-track strip with dots | `sl.ladder(row, closes, high_pct)` | stock_view.py:315-329, 338-339; stock_lines.py:300-332 | **G3 open:** a range strip with no history; the same levels could be lines on the price chart. G4 open |
| P9b | Rules table: Rule (Above its 50D EMA / Within 20% of its 52W high / In the top 40 of the qualified, each with "filter and sell rule" or "sell rule") · Line · Fall to reach it · Today (coloured) | – | Table; the phone drops "Line" | `sl.rules(row, a, q, ln, high_pct)` | stock_view.py:330-333, 340-342; stock_lines.py:335-370 | Colour on the "Today" figure (G2 done) |
| P9c | Book note: "The model book does not hold it." / "holds it: N shares, w% of the book, first bought on d at ₹p, up x% since." + "The rules are checked at the month-end close, next on 30 Nov 2026. No board meeting or ex-date is announced for it before the 1 Dec fill (its last results meeting was on 30 Oct)." + link "The plan, share by share, on Actions →" | – | Paragraph + link | `sl.holding_sentence`, `sl.calendar_sentence`; `_calendar` → actions_page `_events`, `results_calendar` | stock_view.py:207-222, 334-336; stock_lines.py:421-464 | Fine. The link is in the up colour (`a.sp-go`), colour on a phrase (G2, minor) |
| P9d | Highs note: "Highs and lows are closing prices over the last 12 months … The all-time closing high is ₹1,601, on 8 Jul 2024." | – | Paragraph | `sl.highs_note` (ATH, ATH Date, 52W High) | stock_view.py:343; stock_lines.py:467-478 | Fine |
| P10 | "3 · RETURNS AND FALLS" + H2 "Ahead of Nifty Total Market on 2 of 5 windows; its max drawdown over 12 months was 27.3%." | – | Serif heading | `sl.returns_heading`, `returns_tone` | stock_view.py:349, 368; stock_lines.py:587-606 | **G2 open:** the phrase "Ahead of Nifty Total Market on 2 of 5 windows" is coloured |
| P10a | Key "One line is 1% of return, one scale for every row" · "▲ Nifty Total Market, same sessions" | – (`.sp-key`) | Legend | `sl.line_step` | stock_view.py:369-370; stock_lines.py:551-562 | Part of G3 (see P10b) |
| P10b | Returns table: Window (1M…12M, "from 27 Oct 2026") · Return (line bars with a market triangle) · Stock · Nifty Total Market · Lead, pts · Typical stock · Max DD · Typical max DD · Sharpe · Rank by return; phone note "On a wider screen: …" | – (`.sp-ret`) | **Line bars (tick strip)** + table | `sl.windows(row, rank_df, index, market)`: n M Return, Max DD n M, n M Sharpe, median of the universe, `market_return` | stock_view.py:346-377, 627; stock_lines.py:483-584 | **G3 open:** line bars are the tick-strip form S237 counts as not done. Note: line bars are the owner's own chart (PAGE_DESIGN §4.2, 20 Nov), so replacing them changes an owner decision (owner approval needed; on Indices / Market the owner approved replacing them on 28 Nov). G4 open. Figures coloured on Stock and Lead only (G2 done) |
| P10c | Note "Price returns, without dividends. Each window runs … not annualised. Rank by return is its place among the 750 …" (+ "Nifty Total Market's 27 Nov close is not in yet" when late) | – (`.sp-cols`) | Two-column paragraph | `sl.returns_note`; `formats.closes_not_in` | stock_view.py:378-379; stock_lines.py:609-614 | Long (six sentences); G8: price return, not total return (the owner's call) |
| P11 | "4 · PRICE" + H2 "Above its 50D EMA on 22 of the last 60 sessions; against Nifty Total Market its relative strength fell 11.9% over 12 months." (the range chips rewrite "12 months") | – (`h2.sp-price-h`) | Serif heading | `sl.sessions_above(chart_close, ranking_ema)`, `relative_strength(window(...), market)`, `sl.price_heading` | stock_view.py:649-661; stock_lines.py:619-647 | **G2 open, and a wrong tone:** `_h2(pa, pb, pc)` gets no tone, so the clause is always in the **up** colour, here "its relative strength fell 11.9%" (stock_view.py:658, `_h2` default `tone="up"` at :153) |
| P11a | Caption "Price and relative strength · against Nifty Total Market" | – (`.sp-cap`) | Caption row | – | stock_view.py:662 | Fine |
| P11b | Lightweight Charts iframe: range chips 6M · 12M (default) · 3Y; pane 1 price line (or candles when the source has a real range) + 50D EMA; pane 2 "Volume" (up / down tints); pane 3 "RS against Nifty Total Market" (100 at the range start); one-line legend per pane, crosshair, keyboard reading; screen-reader summary | – (iframe) | Line chart, 3 panes | `daily_history.stock_close` (daily closes, NSE long file), `volume_data[sym]`, `_market()`; `ranking_ema` (EMA_MIN_PRINTS = 30) | stock_view.py:630-665; stock_chart.py:230-317; lw_chart.py:160-180, 206-536 | G3 partly: a familiar line with history up to 3Y, but no 52W high / low labelled, no usual range on RS, no "100" baseline label (inferred). **G4 open:** no source line. "Volume unavailable for this symbol." caption when there is none (stock_chart.py:316-317); empty "No chart for SYM. There are no closes to draw; the figures on the page still hold." (stock_chart.py:311-315) |
| P11c | Note "Three panes: price with its 50D EMA … Prices are adjusted for corporate actions." | – | Paragraph | `sl.PRICE_NOTE` | stock_view.py:666; stock_lines.py:650-653 | Long; it reads as a legend, and part of it could be a source line (G4) |
| P12 | "5 · RESULTS" + H2 "In Q2 FY27 net profit rose 33.8% from a year earlier on sales up 29.8%." | – | Serif heading | `earnings_review.company(sym)` → `Results` | stock_view.py:382-399, 671-672 | Colour on the figure "33.8%" only (G2 done) |
| P12a | Results table: Quarter (8 rows, Q2 FY27 … Q3 FY25) · Sales, Cr · YoY · Operating profit, Cr (PBT for lenders) · YoY · Net profit, Cr · YoY · EPS, ₹ · YoY; phone drops profit and EPS with a note | – | Table | `res.quarters[].values/growth` | stock_view.py:401-431 | **G3 open:** eight quarters as numbers only; a Screener.in-style bar chart of sales / profit by quarter is the benchmark form. G4: the note gives the basis and date, not "Source:" |
| P12b | Note "The company's reported results, consolidated, in ₹ Cr (EPS in ₹), each quarter against the same quarter a year earlier; last updated 25 Nov 2026." (+ the "–" growth reason, + the lender note) | – | Paragraph | `res.basis`, `res.read`, `res.lender` | stock_view.py:418-423, 432 | Fine. The section is skipped when there are no results (empty list, stock_view.py:386-387), without a sentence (inferred) |
| P13 | "6 · SECTOR" + H2 "6th of the 19 Oil & Gas stocks; 5 of them pass both filters." | – | Serif heading | `sl.peers(full, row)`, `sl.industry_heading` | stock_view.py:435, 458, 668; stock_lines.py:661-684 | Fine (no colour) |
| P13a | Peers table: Rank · Qualified · Stock (symbol + short name, "· this stock" row shaded) · Price · 1M · 3M · 6M · 12M · From 52W high · vs 50D EMA | – | Table (8 rows) | `full` = `with_book_columns(rank_df)`; `sl.from_high` | stock_view.py:439-463 | Colour on figures (G2 done). **G3 open:** no small multiples of the peers' lines; no sector median row (1b) |
| P13b | Note "The 8 best-ranked of the sector's 19, with this stock; returns in %." + "All 19 Oil & Gas stocks on the Screener →" (`screener?ind=`) | – | Sentence + link | `_peers_note` | stock_view.py:132-141, 464-465 | Fine |
| P14 | "7 · DATA" + H2 "1 corporate action in NSE's lists since October 2024, the latest a bonus ex 28 Oct 2024; prices before it are rescaled." (or "Nothing to correct: …") | – | Serif heading | `sl.data_checks(row, as_of, sl.nse_actions(actions.parquet), first ex-date)`, `sl.data_heading` | stock_view.py:174-183, 469-476, 669-670; stock_lines.py:705-793 | Fine |
| P14a | Checklist (two columns; ✓ or amber "!"): closes on every session / none carried forward · more than 126 sessions, so the 52-week high counts · ranked on all five horizons · the price is the 27 Nov close · all-time closing high over the full history · each corporate action "Bonus, ex 28 Oct 2024: Bonus 1:1; prices before it are scaled by 0.5" | – (`.sp-checks`) | List | FFill %, Data Gap, Short History, Horizons Scored, CARRIED_MARK, ATH Source; NSE's action list | stock_view.py:470-471, 476 | Fine (✓ in green as a mark). The bonus line repeats "Bonus" |
| P14b | Note "Corporate actions are read from NSE's own lists; the prices before an ex-date are scaled …" (only when there are actions) | – | Paragraph | – | stock_view.py:472-474 | Fine |
| P15 | Foot "Data to 27 Nov 2026 · NSE." | – (`.dh-foot`) | Sentence | `sl.foot(as_of)` | stock_view.py:673; stock_lines.py:796-797 | Fine |
| P16 | Footer bar "© Paresh Patel" (right) | – | Line | `render_data_quality_footer` (details=False) | stock_view.py:674-679; components.py:603-640 | Fine (not in the live text capture; inferred from code) |

**Stock page states** (other than the full page):

| State | What shows | Code |
|---|---|---|
| Not in this ranking | Toolbar; kicker "Stock · SYM"; H1 "SYM is not in the current ranking of the Nifty 750."; lede with why / where from `wl.not_ranked` (Not a member of … / In …, but too new to rank. It needs about three months of prices. / Listed on NSE, but in none of the systems' lists. / Not a symbol NSE lists today.) + one link: "See it in {system} →", or "{NEW}'s page →" (renamed), or "Back to the Screener →"; foot "Data to …". No tiles, no sections, no © footer | stock_view.py:481-513; watchlist_lines.py:368-447 |
| Renamed, another system files it under the old ticker (S236) | Same not-ranked page, lede "NSE changed the symbol from OLD to NEW on d; the ranking still files it as OLD. Not a member of … Ranks …" + links | stock_view.py:496-502; stock_lines.py:62-73 |
| Renamed, this ranking files it under the old ticker (S227) | Full page for the old row, with the renamed line P1 on top | stock_view.py:577-582, 617-620 |
| Too new, listed in the last year, not ranked (S236 F18: HEGRAPHITE) | Reached from the Screener search ("SYM — listed 27 Nov 2026"); not-ranked page, "too new to rank" wording when the stock is a member | ranking_view.py:410-413; stock_view.py:491 |
| Ranked but too new for a 52W high | Full page; the ladder / rules read "Not yet"; the data check "Fewer than 126 sessions of prices, so the 52W-high filter cannot pass yet"; `assess` gets the sessions in the window | stock_view.py:603-610; stock_lines.py:344, 760-761 |
| Market close late | Lede "Nifty Total Market's 27 Nov close is not in yet"; the market column is "–"; the returns note says so | stock_view.py:621-627, 378-379 |
| No chart data / no volume | "No chart for SYM. …" / "Volume unavailable for this symbol." | stock_chart.py:311-317 |
| No results / no sector peers | The section is dropped without a word | stock_view.py:386-387, 672 |

### 2a. Stock page controls

| Control | Changes |
|---|---|
| ← Back to screener | Clears `?stock=`, keeps `?system=` (`keep_system_only`), reruns: back to the Screener with the filters from the URL |
| Add to watchlist / In watchlist | Toggles the symbol in the browser's list (`watchlist_store.toggle`) |
| Share popover | Shows `/?stock=SYM` in a copyable code box |
| Chart on TradingView | Opens TradingView in a new tab |
| Range chips 6M · 12M · 3Y (in the chart) | Redraws all three panes on the client, rebases RS to 100, rewrites the P11 heading |
| Crosshair / arrow keys on the chart | The one-line readout per pane |
| "See it in … →", "{NEW}'s page →", peer symbol links, "All N {sector} stocks on the Screener →", "The plan, share by share, on Actions →" | Navigation |

### 2b. Stock page: data read but shown poorly

- **Rank:** three points (3M ago, 1M ago, now) as a table and a 3-point picture; the daily rank history exists (`rank_history_position` on the deep closes), so a 12M rank line with the buy and keep lines is possible (inferred).
- **Score 0.359:** no scale or distribution (is 0.359 high?); Horizons "all five" is clear.
- **Returns:** a single "Typical stock" median per window; the 750's spread (usual range) is already in `rank_df` (`vals` in `sl.windows`) and not shown.
- **Sharpe** "not annualised": the column has no reference value.
- **Rank by return** (119th … 453rd): five ordinals with no picture.
- **Price chart:** the full daily history is loaded (`daily_history.stock_close`); the longest range is 3Y, and the 52W high / low, ATH and −20% line from P9a are not marked on it.
- **Volume:** bars only, no 20-day average line, although the Volume spike rule uses one (`VOLUME_WINDOW`).
- **Market cap ₹18.71 lakh Cr:** one figure in the lede, no history or size rank.
- **Results:** eight quarters of figures with no chart; margins (operating profit / sales) are not worked out.
- **Peers:** no sector median or sector-index line; the "Qualified" place is the only cross-check.
- **Tiles:** close, rank and qualified place repeat the headline and lede.

## 3. Watchlist (`/watchlist`)

Route: app.py:1215-1225 → `render_watchlist_view`, watchlist_view.py:122. Order (approved 22 Nov, WATCHLIST_REQUIREMENTS.md:177):
Watchlist → Against the book's lines → Not ranked → Before the fill → Data to.
The live capture is the **empty state**; the filled sections are from code.

| # | Section (as shown) | Anchor | What it shows | Data and source | Code | Redesign state |
|---|---|---|---|---|---|---|
| W1 | Kicker "WATCHLIST" + H1 (empty) "Your watchlist is empty." / (filled) "3 of your 5 stocks are **in the top 20 qualified**. The book holds 2 of them; **1 would be sold** at the 30 Nov check." | – (`.wl-head`) | Serif headline | `wl.title(matched, n, plan, ln)`; `kit.verdict` | watchlist_view.py:166-174; watchlist_lines.py:230-266 | **G2 open (filled):** the phrases "in the top 20 qualified" / "would be sold" are coloured (`kit.verdict`, at most two). G1: two sentences, no date line |
| W2 | Lede (empty) "Search a stock by name, type symbols and save, or press 'Add to watchlist' on any stock's page. The list is kept in this browser only." / (filled) "Ranked in the Nifty 750 at the 27 Nov close. If today's prices hold, the model book would buy X and sell Y at the 30 Nov check. Z is next in line." (+ the Nifty 1000 fallback note) | – | Sentences | `wl.plan_sentence`, `wl.book_plan` (model_plan on the deep closes, the same plan as Actions); `ranked_note` (app.py:1193-1198) | watchlist_view.py:154-172; watchlist_lines.py:269-285 | Filled lede can run to three or four sentences (G1, inferred) |
| W3 | Edit bar: "Add a stock by name or symbol" select · text box "Comma-separated symbols, e.g. RELIANCE, TCS, …" · "Save watchlist" (primary) · "Remove a stock" popover (pills of the saved symbols) · "Export CSV" (when any are ranked) | – (`st-key-wl_editbar`) | Controls | `search_options(rank_df, saved)`; `watchlist_store.save/parse`; `csv_bytes(matched)` → `watchlist_momentum_YYYYMMDD.csv` | watchlist_view.py:38-78, 176-209 | Control. Two ways to add (a select and a free-text box) side by side |
| W4 | Kept line: "Kept in this browser only. Search a stock by name, or press 'Add to watchlist' on its page, to add it; clear the box and save to empty the list." (filled only) | – (`.wl-kept`) | Sentence | – | watchlist_view.py:210-212 | Fine |
| W5 | "AGAINST THE BOOK'S LINES" + H2 "X is the one buy. Y is the nearest below the buy line, 3 places short of the top 20." (or "None of your stocks is qualified: each fails a filter.") | – (`.dh-sec`) | Serif heading | `wl.lines_heading(table, plan, ln)` | watchlist_view.py:242-247; watchlist_lines.py:288-308 | Fine (no colour) |
| W5a | Note "Your stocks in rank order, grouped by where they sit against the book's lines: it buys the top 20 qualified and keeps a holding while it is in the top 40." | – | Sentence | `wl.lines()` | watchlist_view.py:248-249 | Fine |
| W5b | Table (the Screener's, density "Watchlist"): group heading rows "Top 20 qualified n · the book buys from these" / "21st to 40th qualified · kept if held, not bought" / "Qualified, past the 40th · a holding here is sold" / "Fails a filter · not bought; a holding is sold"; columns Rank · Stock (Held tag + place note, e.g. "3 places short of the top 20") · Price · 3M ago · 1M ago · Qualified 3M ago · 1M ago · Now · "30 Nov" plan (Buy / Sell / Hold / Next in line, coloured) · NSE index · Sector · Market cap · 1M/3M/6M/12M return · 3M max DD · From 52W high · vs 50D EMA · Volume · Above 50D EMA · Near 52W high · 60D; every row shown; phone keeps Stock, Price, Qualified, plan | – (iframe) | HTML table with group rows | `wl.grouped(matched, plan, ln)`; `with_book_columns(with_nse_levels(rank_df))` | watchlist_view.py:148-149, 244-251; watchlist_lines.py:101-140, 201-227; screener_table.py:133-135, 744-750, 832-837 | Same as Screener S9: **G3 open** (60D sparkline). Plan words Buy/Sell coloured as words, not figures (G2, minor) |
| W5c | Phone note "On a wider screen: rank among the 750 ranked stocks, the trail 3M and 1M ago, returns, filters and the 60-day line." | – (`.wl-phone`) | Sentence | – | watchlist_view.py:268-269 | Fine |
| W5d | Key: "Qualified: …", "Rank before: …", "30 Nov: what the model book would do … Held: in the model book.", "A click on a heading sorts every stock and drops the groups; Rank brings them back." | – (`.wl-keys`) | Two-column key | `ln.high_gap`, `_month_ago` | watchlist_view.py:252-271 | Fine; under the table (on the Screener it is above, so the two pages differ) |
| W6 | Empty-lines state: "AGAINST THE BOOK'S LINES" + H2 "None of your symbols is ranked in the Nifty 750." | – | Heading only | – | watchlist_view.py:218-219, 237-239 | Fine |
| W7 | "NOT RANKED" + H2 "2 of your symbols are not in the Nifty 750: 1 was renamed, 1 is in the Nifty 1000." | – | Serif heading | `wl.not_ranked_heading` | watchlist_view.py:274-298; watchlist_lines.py:450-465 | Fine |
| W7a | Table: Symbol · Why it is not here · Where it is (+ link "See it in …") | – (`.wl-tab`) | Table | `wl.not_ranked(missing, full, …, changes=symbolchange, listed=current ISINs, others=other_rankings())`; `_nse_lists` → `nse_identity` | watchlist_view.py:81-85, 284-301; watchlist_lines.py:378-447 | Fine |
| W7b | "Replace with NEW" buttons, one per renamed symbol | – (`st-key-wl_replace_bar`) | Buttons | `r.replace_with` | watchlist_view.py:302-308 | Control |
| W8 | "BEFORE THE FILL" + H2 "2 board meetings or ex-dates are announced before the 1 Dec fill, for X and Y." (or "No board meeting or ex-date is announced for your stocks before the 1 Dec fill.") | – | Serif heading | `actions_page._events(syms, sells, buys, as_of, fill)` | watchlist_view.py:316-332; watchlist_lines.py:470-478 | Fine |
| W8a | List "X (to sell) Board meeting, 29 Nov" … | – (`.wl-list`) | Bulleted list | events | watchlist_view.py:323-327, 333 | Fine; a date list, which could be a small calendar (inferred suggestion) |
| W8b | Note: "Every ranked stock on your list held its last results meeting between …" + Actions' note on the calendar's limits | – | Paragraph | `results_calendar.for_book`, `wl.reported_sentence` | watchlist_view.py:328-334; watchlist_lines.py:481-495 | Fine |
| W9 | Foot "Data to 27 Nov 2026 · NSE." (+ "; k of your n symbols are ranked among the 750; each scored on all five horizons, none with a price gap.") | – (`.dh-foot`) | Sentence | `_foot` | watchlist_view.py:228, 337-352 | Fine (seen live in the empty form) |
| W10 | Footer bar "© Paresh Patel" | – | Line | `render_data_quality_footer` | watchlist_view.py:229-234; components.py:634-641 | Fine (not in the live text; inferred from code) |

Also: spinner "Reading the plan…" while `wl.book_plan` runs (watchlist_view.py:157). If the plan fails, the plan column reads "–" on every row and the key says why (watchlist_view.py:261-265).

### 3a. Watchlist controls

| Control | Changes |
|---|---|
| Add a stock (select) | Adds the stock to the end of the list and saves (`_add_picked`) |
| Symbols box + Save watchlist | Replaces the list with the parsed symbols; an empty box empties the list |
| Remove a stock (popover pills) | Removes one symbol |
| Export CSV | The ranked rows, every column (not the not-ranked ones) |
| Replace with NEW | Swaps a renamed ticker in place |
| Table headers | Sort every row and drop the group rows; Rank ascending brings them back |
| Row / link | Opens the stock page; "See it in …" opens it in another system |
| System (Configuration, `?system=`) | The ranking the list is read against; the list is shared by all systems |

### 3b. Watchlist: data read but shown poorly

- **Qualified 3M ago / 1M ago / Now:** three numbers per stock; no rank line per stock (small multiples of the reader's names would fit this page best).
- **Place note** ("3 places short of the top 20") is in the table only; the headline names one stock.
- **Plan word** (Buy / Sell / Hold / Next in line): no reason given in the row (why it sells: a filter or the 40th line); the place note half-covers it.
- **The list's own performance:** returns are read per stock, but the list as a whole has no line (inferred: an equal-weight line from `prices` is cheap).
- **Market cap, 60D sparkline:** the same as the Screener (1b).

---

## The five most important redesign gaps (ranked by what they cost a reader)

1. **Stock page charts are still tick strips and single figures (G3).** Returns line bars (stock_view.py:346-377,
   stock_lines.py:551-584), the price ladder (stock_view.py:315-339), a 3-point rank trail (stock_view.py:279-305)
   and four tiles with no history (stock_lines.py:207-228), while the daily rank and the full daily closes are
   loaded. Benchmark (Screener.in / broker): a long price line with the 52W high / low and the rules' lines marked, a
   12M rank line against the buy and keep lines, and quarterly results as bars (stock_view.py:382-432 is a table
   only). Owner's call: line bars are his 20 Nov chart (PAGE_DESIGN §4.2).
2. **Colour on whole phrases (G2), with one wrong tone.** Stock page H2s colour clauses (`_h2`, stock_view.py:153-155;
   used at :300, :337, :368, :658). The price heading has no tone passed, so "its relative strength fell 11.9%" is in
   the **up** colour (stock_view.py:658). Also the Screener movers H2 (ranking_view.py:1048-1053, CSS :959), the
   Watchlist title (`kit.verdict`, watchlist_lines.py:240-265), the header's market line (components.py:183,
   page.css:291) and the Screener's amber signal chip (components.py:278-287).
3. **No source line under any chart on these three pages (G4).** The LW chart (stock_view.py:661-666), the rank trail
   image, the ladder, the returns bars and the Screener's 60D column carry none, and none of these pages uses the
   `how(..., source=)` footer the G4 test checks (tests/test_s237_chart_sources.py). The source line must name the
   exchange only, never the vendor (owner, 20 Nov: PAGE_DESIGN.md:60).
4. **First screen (G1).** Stock page: toolbar → kicker → H1 → a three-sentence lede → a fourth paragraph "It also
   ranks …" → four tiles repeating the H1 (stock_view.py:260-269, stock_lines.py:177-198). Screener: a two-sentence
   H1, then a four-paragraph key above the table (ranking_view.py:421-422, 544, 837-873). Watchlist: a two-sentence
   coloured H1 (watchlist_lines.py:230-266). None has a date line over the headline.
5. **The Screener table cannot be read and has no history (G3, Words).** Full Quant by default, so about 35 columns
   (ranking_view.py:37-40, screener_table.py:120-127), with Score, five Sharpe columns, Filled %, Horizons and New
   highs not in the key. Its only picture is a 60-session sparkline with no scale (screener_table.py:229-249,
   628-632). The movers section shows climbs as two numbers (ranking_view.py:1016-1038). The ranking holds daily
   ranks and years of closes that could feed a rank-change chart or longer lines.
