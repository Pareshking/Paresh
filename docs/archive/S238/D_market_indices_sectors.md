# D. Market, Indices, Sectors: an inventory, section by section (28 Nov 2026)

Read from the worktree `scratchpad/wt` (branch s237-fullpage, head `f2849bb3` "S237 full-page preview: Market evidence
at a glance; small lines as images (WIP)"). File:line refers to that worktree. Live text of the OLD pages:
`scratchpad/s237/ours/ours_*.txt`; tipsheet text: `scratchpad/s237/tips/`. Rules: `docs/archive/S237_COMPARISON_2026-11-28.md`
(G1 first screen, G2 colour on figures only, G3 lines/bars with history + usual range + labelled extremes, small multiples;
tick strips and ring scales count as NOT done, G4 "Source:" under every chart, G6 question kicker).

**What the WIP has touched.** The last commits that changed each file: `market_questions_view.py` f2849bb3 (WIP, the
full-page Market preview), `indices_view.py` 21030089 (WIP, lower sections), `record_line.py` new in S237.
**Not touched by the full-page work:** `market_view.py` (last change a2511bed, #717) and `sector_view.py`
(last change 1311f248, #720). So everything from Market's "Today's charts" down, and all of Sectors, is the
pre-S237 design.

Routing (`app.py`): `/market` → `_page_market` (app.py:1232) → `render_market_view(_nse_display(), adj_close,
history_prices=_daily_history(), …)`; `/indices` → `_page_indices` (app.py:1228) → `render_indices_view()`;
`/sectors` → `_page_sectors` (app.py:1177) → `render_sector_view(...)`. Pages registered at app.py:1281-1283. The
header and its market strip come from `render_header_kpi_bar(..., show_market=title != "Dashboard")` (app.py:1343-1352),
so all three pages carry the strip.

Chart kinds named below are `src/ui/dash_charts.py` KINDS (line 29): "lines", "bars", "breadth", "rel", "trows",
"pairs", "lmap", "stable".

---

## 1. Market (`/market`)

Order on the page: site header + market strip → first screen (date line, question, lede, nav) → feature (share above
200D EMA against its record) → Q1 breadth section → "Behind the answer" charts → Q2 trend section with "By size" →
"Behind the answer" charts → members note → "Today's charts" heading + Chart settings popover → Participation (or
Participation by index) → New highs against new lows → Stocks making new highs and lows → footer line.

| # | Section (as shown) | Anchor | What it shows | Data, from where | Code | State vs S237 |
|---|---|---|---|---|---|---|
| M0 | **Market strip** (header, every page but Dashboard): "● Nifty Total Market 4.4% above its 200D EMA · Nifty Total Market 13,494 · Universe 750 · Above 50D EMA 353 (47%) · Near 52W high 374 (50%)" | none (`role=status`, class `mkt-snapshot`) | One coloured regime phrase, then four label/figure tiles in a strip | `get_market_regime(TOTAL_MARKET_REGIME)` (app.py:1037); `count_above_ema(rank_df)` and `count_above_ema(rank_df, "Near 52W High")` (app.py:1340-1349) | `src/ui/components.py:162-201`, emitted at 275 | **G2 open:** the whole phrase "Nifty Total Market 4.4% above its 200D EMA" carries `mkt-up`/`mkt-down`. G7 (strip once, on Market only) open: still on Indices and Sectors. Duplicates the feature's figures (50D share here, 200D share below). |
| M1 | **First screen.** Date line "Market · end of day, 27 Nov 2026"; H1 "Is Nifty Total Market rising, and are most stocks rising with it?"; lede: "**45%** of the 750 closed above their 200D EMA, a reading lower than on N% of days since Oct 2021: participation is about usual. Nifty Total Market is in a strong uptrend." | `qp-head` (no id on h1) | Sentence block; the 45% coloured by its vote | `head_lede()` from `breadth` and `trend` answers (`_answers` → `mq.breadth_answer`, `mq.trend_answer`, `src/engine/market_questions.py:284, 472`) | `market_questions_view.py:629-647` (lede), `697-703` (title, date) | **done (G1, G6, G2)**: date line, question, two sentences, colour on the figure only. Falls back to the old statement title `market_title()` (44-60) and `market_sub()` (63-66) when there is no lede. |
| M1a | **On this page** nav: "Are most stocks taking part? · Is Nifty Total Market in an uptrend? · Today's charts" | `qp-nav` | 3 anchor links | static | `market_questions_view.py:704-706` | Lists 3 of the page's ~8 blocks: Participation, New highs/lows, the events list and "By size" have no link. |
| M2 | **Feature: "Above their 200D EMA"** kicker, big "45%", "of the 750, 27 Nov 2026", record in words ("Inside its usual range of a to b, the middle half of days since Oct 2021. The highest was …, in …; the lowest …. Up from 44% a year ago."); right: line of every day since Oct 2021, usual range shaded, highest and lowest labelled; note "… Source: NSE closes." | none | Big figure + sentence (left 1/3); dash_charts **"lines"** with `bands` + `marks`, range "all" (right 2/3) | `_chart_series()` → `pit_breadth.splice(mq._share_above_ema(px,200), past, "above_200")` (members-of-the-day history `data/breadth_history.csv` via `pit_breadth.load("total_market")`, 750 only); `record_line.facts/words/chart_spec` | `market_questions_view.py:707-722`; `feature_html` 650-655; `record_line.py:15-61` | **done (G3, G4)**: line with history, band, labelled extremes, Source line. History only from Oct 2021 (tipsheet: 1999). No CSV/table under it (G4's "data a click away" half). |
| M3 | **Q1 "Are most stocks taking part?"** verdict word ("About usual", 30 px, coloured up/down), one sentence ("45% of the ranked stocks are above their 200D EMA, and 45% beat Nifty Total Market over 12 months."), five-band **scale** with today ●, a month ago ○, 12 months ago dashed ring; key line | `q-breadth` (h2) | Verdict tile + sentence + dot-on-gradient scale | `mq.breadth_answer` (engine 284-330): measures share above 200D EMA (primary), stocks ahead of Nifty Total Market over 12M (primary, `data/nse_total_market.csv` via `total_market()` 161-175), above 50D EMA, net new 52W highs this week, median stock less Nifty Total Market 12M | `question_section_html` 332-361; `_scale` 88-95; CSS 27-37 | **G3 open: ring scale** (`.mq-scale` dots and dashed ring). **G2 open:** the verdict word is coloured (`.qp-v.up/.down`, 198-199), a phrase not a figure. G6 done (h2 is a question). |
| M3a | Q1 **"What has changed"** list: "The answer a month ago: narrow." then up to 3 measures "X: a month ago, now, now between." | inside `q-breadth` | Bulleted sentences | `mq.changes(a)` (engine 629) | `_changes_html` 238-250; empty: `no_month_ago` 228-235 | Text only; fine. Tipsheet puts the month-ago and year-ago marks on its scale too but leads with a lede that names one measure on each side when they disagree ("They disagree: …"). |
| M3b | Q1 **"What would change the answer"**: "To narrow: … falling to 45% (now 45%); or …" | inside `q-breadth` | Bulleted sentences | `mq.what_would_change` (engine 650) | `_would_html` 257-270 | Text only. |
| M3c | Q1 **"The evidence"**: grid of glance cards, one per measure: name, rule ("Primary. 60% or more is broad…"), figure (30 px serif) + vote word coloured, a **small line** (inline SVG image) of the measure's record with its middle half shaded and today's dot coloured, "Nth percentile since Oct 2021 · 12 months ago x" | inside `q-breadth` (`qp-glance`) | Small multiples, `record_line.spark_svg` 240×56 | `Measure.series`, `Measure.history` (engine `history_stats` 136) | `_glance_card` 313-329; grid 353; CSS 658-668 | **done (G3 small multiples)**, new in WIP f2849bb3. Open: no axis/extremes labels on the small lines, no one-scale note; vote word coloured (G2, minor). No Source line under the grid (G4 open: the note at 354-356 explains the lines but names no source). |
| M3d | Q1 **"Show the table"** expander: table "The evidence · Where today sits, lowest to highest · Now · Vote" with a **range bar** per row (lowest→highest, middle half shaded, dot) | inside `q-breadth` (`details.qp-ev`) | HTML table with `.rng` strip bars | as M3c | 357-360; `_range_html` 289-299 | The old tick/range strip survives inside the expander. Acceptable as the table behind the cards (inferred); vote cells coloured (`td.up/down`, 210). |
| M4 | **"Behind the answer"** (Q1), left: chart head "Over 12 months, Nifty Total Market rose 0.3%, and the share of stocks above their 200D EMA went from 44% to 45%." + note; **"breadth"** two-pane chart: index above, share above 200D EMA below, 3 years sent, opens 12M | none (`qp-behind` p) | dash_charts "breadth" | `_breadth_spec` (`dashboard_home_view.py:1552`) on `bench` (Nifty Total Market joined to Nifty 500, `market_close` 138-144, `data/benchmark_indices.csv`) and `share200` | `_breadth_charts` 509-538; `year_head` 452-457 | G3 partial: familiar lines, but no usual-range band on the share pane and 3Y only though the share runs from Oct 2021. **G4 open: no Source line.** Same data as M2, drawn twice (M2's line and this pane). |
| M4b | **"Behind the answer"** (Q1), right: head "Net new 52-week highs this week: +2.7% of stocks, against −5.3% 12 months ago." + method note; weekly **"bars"** with shaded usual range (`band` q1-q3), chips 12M/3Y; note "Shaded: the usual range since Oct 2021, −1.8 to +11.9" | none | dash_charts "bars" with band | `pit_breadth.splice(mq._net_new_highs(px), past, "net_new_highs")` weekly W-FRI, clamped to last session (`_chart_series` 426-443) | 539-557; `highs_head` 460-463 | G3 mostly done (bars, history, band); extremes not labelled. **G4 open: no Source line.** |
| M5 | **Q2 "Is Nifty Total Market in an uptrend?"** verdict "Strong uptrend", sentence "7 of 8 measures say up, none say down.", ring scale, What has changed, What would change, The evidence glance cards (Total Market vs 10-month average (primary), vs 200D EMA (primary), from 52W high, Nifty 50/Midcap 150/Smallcap 250/Microcap 250 vs 10-month average, stocks above 200D EMA), Show the table | `q-trend` | as M3-M3d | `mq.trend_answer(_bench, _size, share, name, past)` (engine 472-505); size closes `size_closes()` 178-189 from `data/benchmark_indices.csv`; ranges back to 1999/2000 via the Nifty 500 join | `question_section_html` 727; 726-740 | As M3: **G3 open: ring scale**; **G2 open: verdict word coloured**; glance cards done. Tipsheet adds a "trend ensemble score" (24 rules) and names the disagreeing pair. |
| M5a | **"By size"** (inside Q2): table Index × {Against its 10-month average, Against its 200D EMA, From its 52W high} × {A month ago, Now} for Total Market, Nifty 50, Midcap 150, Smallcap 250, Microcap 250; method note; late-close sentence | inside `q-trend` (`qp-scroll`, no id) | 7-column table, figures toned (52W column not toned) | `size_trend_html` → `mq.ten_month_today`, `mq.ema_gap`, `mq.from_high` (engine 372, 421, 432) | `size_trend_html` 368-404; inserted 728-734 | Table only; no chart. Tipsheet "Big companies, small companies" draws the share above 200D EMA by size as four lines since 2018, plus a table with a year ago, "rose that day", median stock 1M. Not in nav. |
| M5b | **Joined-index note**: "Nifty Total Market from 14 Oct 2021, when NSE launched it. Before that it is the Nifty 500, scaled …" | inside `q-trend` | Note | `joined_note` 147-158 | 736-738 | Fine. |
| M6 | **"Behind the answer"** (Q2), left: head "Nifty Total Market is 5.6% above its 10-month average on 27 Nov. At the 30 Oct month-end it was 2.9% below." + note; **"lines"**: monthly closes and the dashed 10-month average, 3 years, fixed range (`TEN_MONTH_RANGE`, 561-563) | none | dash_charts "lines" | `bucket_by_last_session(b, "M")` 407-423, `rolling(10)` | `_trend_charts` 566-589; `ten_month_head` 466-477 | G3 partial (line, 3Y; data held back to 1999 not shown; no extremes). **G4 open: no Source line.** |
| M6b | **"Behind the answer"** (Q2), right: head "Over 12 months, Nifty Microcap 250 did best against Nifty Total Market, 7.4% above its line; Nifty 50 did worst, 2.7% below it" + note; **"lines"**: each size index ÷ Total Market, 100 a year ago, level at 100 | none | dash_charts "lines" (4 lines) | `size_closes()` / `bench` | 590-613; `size_line_head` 485-493 | G3 partial (12M only, no band). **G4 open: no Source line.** Headline lacks a full stop (old page too). |
| M7 | **Members note**: "Today counts the stocks ranked today. Every earlier reading counts the stocks in Nifty Total Market on that date …" (or the non-750 version) | none | Note | `pit` flag (`system == SYSTEM_750`, market_view.py:101) | `market_questions_view.py:741-747` | Fine; sits between the questions and Today's charts, far from the charts it qualifies (inferred reader cost). |
| M8 | **"Today's charts"** h2 + **Chart settings** popover (icon tune) | `q-charts` | Heading + popover with 5 controls (see controls) | session_state keys `br_ma_type`, `br_sel_mas`, `br_bview`, `hl_win_sel`, `hl_fmt_radio` | `market_view.py:115-130` | **G6 open:** a noun heading, no answer sentence. **Not touched by WIP.** Empty state "Pick at least one EMA or SMA under Chart settings." (132-134) returns early and hides the rest of the page (highs/lows, events, footer). |
| M9 | **"Participation"** card, aside "above each EMA": **"lines"** of the share above each chosen average (default 50D, 200D EMA), 60% "broad" and 40% "narrow" levels, chips 3M/6M/12M, opens 12M; 50D/200D EMA lines are members-of-the-day when the history covers the window | `s-br-part` (kit.card) | dash_charts "lines" | `compute_ma_breadth(ph, adj_close, sel_mas, lookback=_lookback(), ma_type)` (`src/engine/breadth.py:49`); `pit_breadth.splice` for 50D/200D | `market_view.py:147-161`; `_participation_chart` 54-71 | G3 partial: familiar lines but **one year only** (`_lookback` 46-51) though breadth history runs from Oct 2021; fixed 40/60 levels instead of a usual-range band; no labelled extremes. **G4 open: no Source line.** No headline sentence with the reading (tipsheet: "Short against long trends, last two years", values labelled at line ends). |
| M9b | **"Participation by index"** card (Chart settings → By Index), aside "above 50D EMA": one bar per index: Nifty 50, Next 50, Midcap 150, Smallcap 250, Microcap 250, Nanocap 250 (where ranked), "47% · 50" | `s-br-idx` | `kit.bar_list` horizontal bars, amber when ≤ 40% | rank_df `Indices` tags (`index_members` 30-38), EWM/rolling 50 on `adj_close` | `market_view.py:162-190`; `page_kit.py:209-220` | **G3 open: today only, no history**; always 50D whatever "Periods" says; amber colour on the bar (third colour). Empty: "No index tags on the ranked stocks." G4 open. |
| M10 | **"New highs against new lows"** card: daily **"bars"**, highs up, lows down (`color2 --down`), chips 3M/6M/12M; % of universe or count | `s-br-hl` | dash_charts "bars" with `also` | `compute_hl_timeseries(ph, adj_close, window=hl_window, lookback)` (`breadth.py:95`) | `market_view.py:192-194`; `_highs_lows_chart` 74-85 | G3 partial: bars, one year, no usual range, no extremes, no net line. Daily, while M4b is weekly net: two forms of the same measure. **G4 open.** No headline. |
| M11 | **"Stocks making new highs and lows"** card, aside "last 20 sessions": segmented filter All / Highs / Lows; table of events (symbol, sector, event, date …) max height 420 | `s-br-events` | `render_saas_table` | `get_recent_hl_events(adj_close, rank_df, window=hl_window, lookback=20)` (`breadth.py:167`); column Industry renamed Sector | `market_view.py:196-210` | Pre-S237 card style. Empty: "No stock made a new high or low in the last 20 sessions." No count sentence ("N stocks made a new 52W high this week"); not split into two lists (highs, lows) side by side as the brief asked (inferred). Old live text showed only the filter chips: the table may render as a widget the text capture missed (inferred). |
| M12 | **Footer**: "Data to 27 Nov 2026 · NSE. 750 stocks ranked; 0 with a price gap, 5 with a short history." | none (`qp-note`) | Note | `_fmt.data_to_html(_fmt.session_of(adj_close))`, `gap_count(rank_df)`, `Short History` | `market_view.py:212-215` | No `render_data_quality_footer` here (Sectors has it): inconsistent footers across the three pages. |

Not rendered although computed: `leaders_answer` (sector leaders) is computed in `_answers` (`market_questions_view.py:129`) and discarded (`breadth, trend, _ =`, 696): a cost per cache miss for nothing.

Empty states: `render_market_page_questions` returns False with nothing on screen when prices or the index are missing
(677-686); `render_market_view` ignores the return value (market_view.py:112-113), so the page then opens straight on
"Today's charts" with no heading or explanation. (Inferred from the code; not run.)

### Market: what tipsheet shows that we do not (one line each)

- M0 strip: tipsheet has no per-page strip; it puts "Data to 27 November 2026" beside the wordmark.
- M1: theirs adds a "Written for …" line and a 13-link "On this page" covering every section.
- M2: their record runs from 1999 (weekly), with "What it is / How to read it", Source, Method, Data, Full history and numbers, Share image.
- M3/M5: theirs has no ring dots on a gradient for the evidence; they show "Breadth at a glance": 15 small lines with "2016–2026 · usual a to b" under each.
- M3/M5 extra measures we lack: stocks above 20D EMA, equal weight minus Nifty 500/Nifty 50 (1Y), stocks 20%+ below high, median stock's fall from 52W and all-time high, dispersion of 1M returns, McClellan oscillator, share of NSE indices above 200D, 50D-above-200D share.
- (no section of ours) "Is participation improving?": 21- and 63-session change in the share above 20D/200D, table + weekly change line.
- M4b/M10: theirs are weekly highs minus lows over 3 years in stocks, plus all-time highs/lows weekly from 2003 and "how far the typical stock is from its highs" (52W and all-time) since 2000.
- M5a By size: theirs draws share above 200D by size (AMFI ranks) as four lines since 2018, with a year ago, rose that day, median 1M.
- (none of ours) "Is the average stock keeping up with the index?" equal weight minus cap weight, 3 indices, percentile; concentration (largest 10/100 share of market value) and top-10 companies table.
- (none of ours) "How many stocks beat the index?" weekly since 1999 with median; median stock vs index lines with the middle-half band.
- (none of ours) lifetime returns of every listed company; sector index table with 52-week small line, vs 200D, off high, trend "Up since Nov '26".
- M9 Participation: theirs "Short against long trends, last two years": 20D, 50D, 200D lines, values at line ends, Source.
- M11 events list: tipsheet has no stock list on this page (ours is an extra).

### Market: controls and what they change

| Control | Where | Changes |
|---|---|---|
| Chart settings → Average EMA / SMA (`br_ma_type`) | market_view.py:118 | M9 lines and M9b bars (rerun) |
| Chart settings → Periods 10D…200D multiselect (`br_sel_mas`, default 50D, 200D) | 120 | M9 lines; none selected hides everything below (empty state) |
| Chart settings → Participation by Universe / By Index (`br_bview`) | 122 | Swaps M9 for M9b |
| Chart settings → "New high / low means" 52-day / 126-day / 52-week (`hl_win_sel`) | 124-128 | M10 and M11 (window); label "52-day" for 52 sessions next to "52-week" reads as a trap (inferred) |
| Chart settings → "Show highs and lows as" % of Universe / Stock Count (`hl_fmt_radio`) | 129-130 | M10 units |
| Range chips 3M/6M/12M | M9, M10 (client-side, `PERIOD` 45) | dates shown only |
| Range chips 12M/3Y | M4b | dates shown |
| Range on M4 (12M of 3Y, `RANGE_BY_KIND["breadth"]`), M6 fixed 3Y, M6b 12M, M2 "all" | dash_charts | dates shown |
| Events filter All / Highs / Lows (`hl_ev_filter`) | 201-209 | M11 rows |
| Show the table (details) | M3d, M5 | evidence table |
| System (`?system=`) | `system_param.current()` market_view.py:97-101 | universe, members-of-the-day history only under the 750 |

### Market: data read but shown poorly

- Breadth history from Oct 2021 (`data/breadth_history.csv`) is read, but Today's charts send one year (`_lookback`, market_view.py:46-51) and M4 three years.
- Nifty Total Market/Nifty 500 joined history to 1999 (`fetch_benchmark_history(period="max")`, market_view.py:105-110) feeds percentiles but is drawn only 3Y (M6) or 12M (M6b).
- Each measure's whole record is now in the glance small lines, but without the dates or the usual-range figures on the card (tipsheet writes "2016–2026 · usual 38% to 78%").
- `leaders_answer` computed, not shown (above).
- Participation by index: computed for today only from `adj_close`; the same members over time would give a by-size history (tipsheet's four lines).
- The strip's "Near 52W high" (within 20%) appears nowhere in the page body.

---

## 2. Indices (`/indices`)

Order (`page_parts`, indices_view.py:735-752): header + strip → first screen (date line, question, lede, scope line,
pills) → Nifty 50 P/E feature → Valuation (cards + Nifty 500 chart) → [Companies switch] → Earnings (latest table,
partial quarter, quarterly profit/revenue tables, profit growth chart) → Styles → How long a style can lag → Calendar
years → Size, year by year → Every index (Broad market, Theme, Strategy) → foot. Rendered in two `emit` calls so the
earnings switch sits between Valuation and Earnings (763-769).

| # | Section (as shown) | Anchor | What it shows | Data, from where | Code | State vs S237 |
|---|---|---|---|---|---|---|
| I0 | Market strip (as M0) | – | as M0 | as M0 | components.py:162-201 | G2 open, G7 open (as M0) |
| I1 | **First screen**: "Indices · end of day, 27 Nov 2026"; H1 "Are NSE's indices cheap or dear against their own past?"; lede "The Nifty 50 trades at 20.9 times trailing earnings, cheaper than on **79%** of days since 31 Mar 2021; the Nifty Smallcap 250, at 32.1, is dearer than on **77%**. A P/E says what you are paying, not what happens next."; "NSE's own indices. Price returns; dividends are not added."; pills P/E · Earnings · Styles · Lags · Calendar years · Size · Every index | `s-top` (h1), nav `dh-pills` | Sentence block + pill nav | `ip.valuation(f)` (indices_page.py:119) on `indices_data.frames()` ← `nse_indices.read_compact()` (`data/nse_indices_history.parquet` + `data/nse_indices_recent.csv`, inferred from benchmark_indices.py:19) | `head` 109-119; `head_lede` 95-102; `_pct_word` 85-92 | **done (G1, G2, G6)**. Empty: "NSE's index P/Es are not in yet." (99). Pills are all nouns. |
| I2 | **Feature "Nifty 50 P/E"**: big 20.9, "times earnings, 27 Nov 2026", record in words; right: **"lines"** of daily P/E since 31 Mar 2021, usual range band, highest and lowest labelled, chips 3Y/5Y/all; How it is / How to read it; "Source: NSE Indices' published P/E."; Show the table (Now, Usual range, Highest, Lowest, A year ago) | none | Big figure + "lines" + `how()` | `record_line.facts(f.pe["nifty_50"], since=ip.PE_FROM)` | `section_pe_feature` 122-141 | **done (G3, G4)**. History only from Mar 2021 by design (basis change); tipsheet shows 1999+ with "record 34.9, Feb 2021" and adds CAPE (which bridges the basis change). |
| I3 | **Valuation** kicker; h2 "Against its own past, the X is the cheapest, at the Nth percentile; the Y the dearest, at the Nth." (or two-sentence fallback); long note (basis change, P/B no percentile, young index note) | `s-valuation` | Sentence + note | `spread_headline` 184-191 / `valuation_headline` 173-181 | `section_valuation` 214-238 | G6 partial: kicker is a noun ("Valuation"), h2 a statement. Colour none. |
| I3a | **P/E cards** (small multiples): Nifty 50, 500, Total Market, [system's own index, e.g. Nifty 1000, "too new for a percentile"], Midcap 150, Smallcap 250, Microcap 250: name, P/E (30 px), "cheaper than on **79%** of days since Mar 2021; usual a to b", weekly small line with middle half shaded | inside `s-valuation` (`ix-grid`) | Small multiples, `spark_svg` | `f.pe[key]` weekly (`ip.weekly`) | `_pe_card` 194-211; young card 221-228 | **done (G3 small multiples, G2 figure only)** (WIP). No Source line under the grid (the chart below carries one). No P/B or dividend yield on the cards (they are in the table). |
| I3b | **Nifty 500 P/E, weekly, since 2012**: "lines", old basis grey + basis since 2021 ink, usual-range band, chips 3Y/5Y/all; how(); "Source: NSE Indices' published P/E."; Show the table: Index, P/E, P/B, Div yield, Percentile now, A month ago, 3 months ago | none | dash_charts "lines" + table | `f.pe["nifty_500"]` | 239-261 | **done (G3, G4)**; extremes not labelled (no `marks`). The table holds P/B and yield that appear nowhere else on screen. |
| I4 | **Companies switch** "All companies / All but financials" (segmented, right-aligned) | `ix_earn_scope_row` | Control | `er.SCOPES`; shown only when `er.ours(scope="ex_financials")` exists | indices_view.py:764-769 | Not labelled on screen (`label_visibility="collapsed"`); sits above the Earnings kicker, reads as belonging to Valuation (inferred). |
| I5 | **Earnings** kicker; h2 "In Q2 FY27 the Nifty 500's profit rose 30.4% from a year earlier; the median company's profit rose 21.2%."; note (method, Tata Motors, Rajesh Exports, last updated); table Index × Profit all, Profit median, Revenue all, Revenue median, Companies reported (Nifty 50, Next 50, Midcap 150, Smallcap 250, Microcap 250, 500, Total Market, 1000) | `s-earnings` | Table, figures not toned | `er.ours(scope)` ← `data/reference/screener_earnings.csv` (built weekly by `scripts/screener_earnings.py`, earnings_review.py:94) | `section_earnings` 330-356; `earnings_headline` 270-282 | Table only. G6: noun kicker. Not in the S237 first-screen work. Tipsheet has no earnings section on these pages. |
| I5a | **"Qn FYyy so far: N of 500 Nifty 500 companies have reported."** partial-quarter table (Profit, Revenue, Companies reported); shown from 10% to 90% reported | inside `s-earnings` | h3 + table | `er.partial(scope)` | `section_partial` 298-321 | Table only. Empty: rows read "–" under 1 in 10. |
| I5b | **"Profit growth, each quarter"** and **"Revenue growth, each quarter"**: Quarter × 7 indices, newest first, "so far" row on top; cells tinted (heat) | inside `s-earnings` | Two heat tables (`ix-heat`) | `er.ours_history(i, measure, scope)` ← `data/reference/screener_quarters.csv` (earnings_review.py:172) | `earnings_quarters` 362-399 | **G2 open: background tints on whole cells** (`.ix-heat td.up{background:up_tint}`, IX_CSS line 47) rather than colour on the figure. A line chart per index would be the G3 form (only Nifty 50/500 profit is charted, I5c). |
| I5c | **Profit growth chart**: "lines" Nifty 50 and Nifty 500, zero level, range all; how() with table (quarter, profit and revenue for both) | none | dash_charts "lines" + how | `er.ours_history(...)` | `earnings_history` 402-427 | G3 partial (short history Q2 FY25→; no band). **G4 open: `how(...)` has no `source=`** (420-427): no Source line under this chart. |
| I6 | **Styles** kicker; h2 "Over 12 months, equal weight and value lead their parents; quality and momentum trail by more than 5 points: **5.0–5.7**."; note; diverging HTML bars per style (Momentum, Quality, Value, Low volatility, Alpha, Equal weight), each "X against Parent", value right; how() with Source "NSE Indices' daily closes" and table Style, Against, 3M-ago, 1M-ago, Now, Yield gap | `s-styles` | HTML bars (`ix-bars`) + how | `ip.styles(f)` (indices_page.py:207), pairs `STYLES` (26-31) | `section_styles` 470-491; `styles_headline` 444-467 | G2 done (colour on the span of figures). **G3 open: today's lead only, no history** although the style and parent series run from launch; the how() source line sits under a table, not a chart. Tipsheet "Which investing styles are paying?": 3M/1Y/3Y/5Y leads, live since, and a small line per factor of the rolling 1-year lead with usual range ("below its usual range; higher than 15% of readings since 2006"). |
| I7 | **"How long a style can lag"** kicker; h2 "Momentum's line against the Nifty 200 is **23.3%** below its June 2024 peak[, its deepest since launch]."; note with other styles at their deepest and the deepest recovered fall; **"rel"** two-pane chart (relative line, fall from relative peak), chips per style; table Style, Now, Max DD relative, Worst peak → low, Recovered | `s-lag` | dash_charts "rel" + table | `Style.rel`, `Style.from_peak`, `worst`, `recovered` (ip.styles) weekly | `section_lag` 520-544; `lag_headline` 494-502; `lag_extra` 505-517 | G3 done in form (lines, record since launch); **G4 open: no how()/Source under the "rel" chart** (543). Extremes on the chart not labelled (inferred). Tipsheet draws all six factors on one chart from a common start (Aug 2020), the fair comparison. |
| I8 | **Calendar years** kicker; h2 "No style led its parent every whole year; equal weight came closest, 6 of 8."; table Year × style lead, year-to-date row, foot "Years led 3 of 5 …"; heat tints | `s-years` | Heat table (`ix-yr ix-heat`) | `Style.years` (ip.calendar_lead 197) | `section_years` 560-580 | **G2 open: heat background tints**, against INDICES_REQUIREMENTS row 11 ("Figures carry only the sign colour, no heat colours"). No chart; no Source line. The year-to-date row label shows blank in the old live text ("\t−2.9 …"): the `dh-sub` year label may not render as text (inferred). |
| I9 | **"Size, year by year"** kicker; h2 "In a median year since 2017, the Nifty Smallcap 250's max drawdown was 21.9%, twice the Nifty 100's 11.1%."; note with medians; four **"bars"** small multiples (Large, Mid, Small, Micro) in 2 columns, bar = year's return, dot = max drawdown, one scale; how() with Source "NSE Indices' daily closes" and table | `s-size` | dash_charts "bars" with `dots`, small multiples | `ip.size_years(f)` (indices_page.py:253), SIZES 35-37 | `section_size` 601-638; `size_headline` 583-598 | **done (G3 small multiples on one scale, G4)**. History from 2017 only (store from 2012; NSE file has Midcap/Smallcap from Apr 2016). Tipsheet's per-index page uses the J.P. Morgan "worst fall in the year" from 2000 with total return. |
| I10 | **Every index** kicker; h2 "Over 12 months, Nifty Total Market is up x%. Among themes, A leads, up y%, and B trails, down z%."; note (count, windows, younger listed last, sector indices on Sectors, exclusions, late closes) | `s-every` | Sentence + note | `ip.every_index(f)` (292), `PAGE_FAMILIES` (40) | `section_every` 692-702; `every_headline` 648-667 | G6: noun kicker. |
| I10a | **Broad market / Theme / Strategy** family tables: h3 "Theme: 18 of 30 are up over 12 months; A leads and B trails."; family note; columns Index, **12 months** (weekly small line in the cell), 1M, 3M, 6M, 9M, 12M (toned), From 12M high, P/E; column "–" footnotes | inside `s-every` | Tables with inline small lines (`ix-sp`, 120×28) | `f.close[key]` weekly last year (`_year_line` 683-689); `IndexRow.returns`, `from_high`, `pe` | 703-731 | **done (G3 inline small lines)** (WIP 21030089); small lines and the last two columns hidden on a phone (`ix-hide-s`). No sort, no search, no Source line. Tipsheet: one table of 125 with family filter, search, sort, returns vs "trend and risk" switch, 1D/1W/YTD/3Y/5Y/10Y, a page per index. |
| I11 | **Foot**: "Data to 27 Nov 2026 · NSE · N broad, theme and strategy indices" | none (`dh-foot`) | Note | `f.as_of`, count | indices_view.py:752 | Fine. |

Empty state: `kit.page_empty(mw.NO_INDEX_DATA, mw.NO_INDEX_DATA_WHY, kicker="Indices")` when the index copy is missing (757-760).

### Indices: what tipsheet shows that we do not

- I1/I2: CAPE for Nifty 50 and the broad market (bridges the 2021 basis change; percentiles since 1999); P/E history to 1999.
- I3a/I3b: "Every index against its own history" for 22 indices including sectors, with P/E, P/B, CAPE and dividend-yield percentiles, sortable; "9 of 22 above the middle of their own history".
- (none of ours) "Are mid and small caps dear against large caps?" relative P/B and P/E to Nifty 50, monthly since 2005, and a tested "valuation and later returns" table.
- I5: tipsheet has no earnings section (ours is an extra).
- I6: leads at 3M, 1Y, 3Y, 5Y with live-since date, total return; rolling 1-year lead small lines with usual range; back-calculated vs live years; mid/small-cap factor indices.
- I7: all six factors from a common live start on one chart.
- I8: tipsheet has no calendar-years style table; it has back-calculated vs live lead per year.
- I9: per index, total vs price return per period, calendar-year total return + worst fall since 2000.
- I10a: 1D, 1W, YTD, 3Y, 5Y, 10Y columns, total return, family filter, search, sort, a page for each index; "did worse after launch" test.

### Indices: controls and what they change

| Control | Where | Changes |
|---|---|---|
| Companies: All companies / All but financials (`ix_earn_scope`) | indices_view.py:766-768 | I5-I5c (rerun; only the "post" part redraws) |
| Range chips 3Y/5Y/all (`PE_RANGE`) | I2, I3b | dates shown |
| Style chips in the "rel" chart | I7 | which style the two panes draw |
| "What it is · how to read it" and "Show the table" details (`how()`) | I2, I3b, I5c, I6, I9 | open the text and the table |
| Pills | I1 | jump to sections |
| System (`?system=`) | 761-762 | adds the system's own index card (`SYSTEM_INDEX`, 145) |

### Indices: data read but shown poorly

- The store holds 194 indices from Feb 2012 (INDICES_REQUIREMENTS); the every-index table shows 1M-12M only; 3Y/5Y/10Y and YTD are computable and not shown.
- P/B and dividend yield are read for every valuation index (`ip.valuation`) but appear only in a collapsed table (I3b); the cards show P/E alone.
- Style series from launch are read; the Styles section shows only the lead now and two earlier readings in a table.
- Earnings quarters (screener_quarters.csv) for 7 indices sit in two heat tables; only two indices are charted.
- Size years from 2017 while the store reaches 2012 (Nifty 100) and Apr 2016 (mid, small).

---

## 3. Sectors (`/sectors`)

Not touched by the S237 full-page work (last change #720). Order (`page_parts`, sector_view.py:733-751, then
render_sector_view 789-812; requirements `Order:` line SECTORS_REQUIREMENTS.md:173): header + strip → Grouping
picker → Sectors (h1, lede, toc) → Which sectors lead → Broad or narrow → NSE's sector indices → Month by month →
Sector leadership map → Inside each sector → Stocks in a sector → foot + data-quality footer.

RRG: the RRG page was removed on 21 Nov 2026 (S169, #587; `docs/RRG_REQUIREMENTS.md` "Superseded"). Its job,
rotation, is now the **Sector leadership map** (S5 below). There is no RRG code in the three views.

| # | Section (as shown) | Anchor | What it shows | Data, from where | Code | State vs S237 |
|---|---|---|---|---|---|---|
| S0 | Market strip (as M0) | – | as M0 | as M0 | components.py:162-201 | G2 open, G7 open |
| S0a | **Grouping picker** "Grouping: NSE sector" (selectbox, right) | `sector_grouping_row` | Control | `groupings(rank_df, system)` 60-72; NSE levels when `NSE_Macro/NSE_Industry/NSE_Basic_Industry` columns exist | sector_view.py:768-772 | Sits above the page's first line, before the kicker (inferred reader cost: the first thing seen is a control). |
| S1 | **Sectors** kicker; H1 "**Healthcare, Services, Media and 2 more** lead the 750 over 6 months and 1 month; **Construction and Constr. Materials** trail it by 15 points or more over 6 months."; lede "N of 19 sectors are ahead of the 750, equal-weighted, over both windows. Over 1 month, Nifty Total Market rose x% and the 750, equal-weighted, rose y%. N of M sector indices beat their sector's ranked stocks over the month. Price returns, to the 27 Nov 2026 close."; toc (7 links) | `s-top` | Kicker + statement h1 + 3-4 sentence lede + text links | `sp.leads(px, groups, tm)` (sectors_page.py:109); `tm = total_market()` | `head` 250-260; `head_title` 213-227; `head_lede` 230-247 | **G1 open:** no date line ("Sectors" kicker), statement headline of two clauses, lede of 3-4 sentences. **G6 open:** no question. **G2 open:** `<span class="dh-up">Healthcare, Services, Media and 2 more</span>` and `<span class="dh-down">Construction and Constr. Materials</span>` colour whole name lists (221, 225). |
| S2 | **"Which sectors lead"** kicker; h2 "**5 sectors lead on both 6 months and 1 month**; **4 trail on both**. X is among them; its 6-month lead was … on …"; note | `s-lead` | Sentence + note | `lead_headline` 263-277 | `section_lead` 357-360 | **G2 open:** both clauses wrapped in `dh-up`/`dh-down` (271-272). G6: kicker is "Which sectors lead" (question form without "?"; near-done). |
| S2a | **Lead chart**: dash_charts **"trows"**: one row per sector grouped Ahead on both / Gaining / Fading / Behind on both, reference row "The 750 against Nifty Total Market"; bar = 6M lead now on a −20..+20 tick strip ("Each line is 1 pt"), triangle a month ago, numbers 6M lead 3M ago, 1M ago, now, 1M, 3M, 12M | none | "trows" tick-strip rows | `ld.rows` (`lead6`, `lead6_1m`, `lead6_3m`, `lead1`, `lead3`, `lead12`), `ld.gap` | 305-329, Chart 361 | **G3 open: tick strips** ("Each line is 1 point"); no history of the lead (only 3 readings). |
| S2b | **"What would change the answer"**: "Nearest to moving ahead over 6 months: A +x points; …", "Nearest to falling behind: …"; link to the Dashboard's "Size, and where momentum works →" | none (h3) | List + link | `sp.nearest_switches(ld)` (sectors_page.py:147) | 330-337 | Text; colour none. |
| S2c | how(): What it is (method, groups left out, worked example "Healthcare's 21 stocks returned …", grouping switch words), How to read it; "Source: our calculation from NSE's daily closes; sectors from NSE's classification."; Show the table (sector, stocks, 6M leads, 1M, 3M, 12M) | none | how() | `lead_example` 280-284; `switch_words` 287-297 | 338-352 | **done (G4)** for this chart; the only Source line on the page. |
| S3 | **"Broad or narrow"** kicker; h2 "Nifty Financial Services rose x% over 3 months, while the sector's N ranked stocks rose y%. **3 sectors are narrower than the 750 against Nifty Total Market**: A, B and C."; note | `s-broad` | Sentence + note | `sp.broad_or_narrow(f, ld, smap)` (254) with `data/reference/nse_sector_index_map.csv` (sectors_page.py:26) and `indices_data.frames()` | `section_broad` 393-423; `broad_headline` 373-390 | **G2 open:** "Only X is narrower …" / "N sectors are narrower …" coloured clauses (385, 387); the docstring (374-375) states the opposite rule ("colour on the verdict clause only, never on the figures"). G6 open (noun kicker). |
| S3a | **Gap chart**: "trows", each sector: stocks 3M %, its NSE index 3M %, gap 3M (bar, −12..+12, "0.5 pt a line"), gap 1M; dashed line at the 750's own gap | none | "trows" tick strips | `Gap` rows | 399-414, Chart 424 | **G3 open: tick strips.** **G4 open:** no Source line. |
| S3b | **"12 months, each line set to 100 at the start (or at the index's launch)"**: dash_charts **"pairs"**: per sector, the 750's stocks (equal-weighted) and NSE's index, chips per sector, Latest / Month end, Show the table | none (h3) | "pairs" lines, one pair at a time | `sp.pair_series(f, ld, smap)` (272) | 415-427 | G3 partial: familiar lines, 12M only, one sector at a time (not small multiples). **G4 open:** no Source line. |
| S4 | **"NSE's sector indices"** kicker; h2 "Over 12 months, **Nifty Pharma leads NSE's sector indices**, up x%, and **Nifty Y trails**, down z%. N of the 37 are younger than 12 months."; long note | `s-indices` | Sentence + note | `sp.sector_indices(f, ld, smap, counts, sp.finer_stocks(...))` (217, 188; `nse_finer_index_stocks.csv`) | `section_indices` 443-488; `indices_headline` 430-440 | **G2 open:** leader and laggard clauses coloured (436-437). |
| S4a | **Sector index table**: groups per sector ("Healthcare · 21 ranked stocks"), first row "The 750's N stocks, equal-weighted", then each NSE index ("for the sector" marks the headline one), finer-index rows of our stocks; columns 1M, 3M, 6M, 9M, 12M (toned; "since <launch>" for young), From 52W high, P/E | none | Grouped table | as S4; `ip.Frames` closes and P/E | 448-488 | Table only; no small line per index (Indices' every-index table now has one, I10a); no trend status, no vs 200D; no Source line. Phone shows short names (`sx-s`). |
| S4x | **NSE-only line** (TradingView or other grouping): "NSE's indices match NSE's sectors; switch to NSE sectors to see them." / TV_ONLY | `s-broad` (p) | Boxed note (`sx-only`, grey fill, left rule) | `NSE_ONLY` 41, `TV_ONLY` 45 | `section_only_nse` 491-493 | Empty state; replaces S3-S4. |
| S5 | **"Month by month"** kicker; h2 "Healthcare **has beaten the 750 in each of the last 6 completed months**, the longest run."; note; table sector × 12 completed months + "Nov so far", Run (months), 12 months summed; worked example under it | `s-months` | Table, cells toned | `mq.industry_months(px, groups, tm)` (market_questions.py:678) | `section_months` 543-564; `months_headline` 506-540 | **G2 open:** the run clause coloured (521, 527). 14 numeric columns of red/blue figures; no chart. G4 open (no source). |
| S6 | **"Sector leadership map"** kicker; h2 "Breadth rose in 15 of 19 sectors from 27 Oct to 27 Nov. **Textiles gained most on the 750**, **Telecom lost most**."; note; dash_charts **"lmap"**: scatter, x = lead over the 750 over the period (pts), y = share above the EMA; hollow dot a period ago → filled dot today; chips EMA 20/50/100/200 and period 1M/3M; leader blue, laggard rust, rest grey; click to fade; "Pick out a sector" list; Show the table; worked example ("How to read it · worked example") | `s-map` | Scatter with two-point trails (the RRG's replacement) | `sp.leadership_views(px, groups, tm)` (321) with `EMA_SPANS` (20,50,100,200), `MAP_PERIODS` (1,3) | `section_map` 614-629; `map_headline` 601-611; `MAP_TEXT` 567-593 | **G2 open:** both clauses coloured (610-611). G3: a scatter, not a familiar time form; only two points per sector (no tail of weeks as an RRG would show). **G4 open:** no Source line. Tipsheet's nearest form: "Every market by trend and momentum", one panel per family (small multiples), faint dots for the other families. |
| S7 | **"Inside each sector"** kicker; h2 "45% of the 750's stocks are above their 200D EMA, up from 32% a month ago. **Services has the most, 71%**, and **Metals the fewest, 12%**."; note; dash_charts **"stable"**: sortable table: Sector, Above 200D EMA 3M ago, 1M ago, now (bar 0-100, "2% a line", dashed 40% and 60%, triangle a month ago), Above 50D EMA, Near 52W high, Pass both filters, In top 50, Typical stock 3M, Leaders (2 symbols) | `s-inside` | "stable" sortable table with a tick-strip bar column | `sp.ema_shares(px, groups, ld)` (300); `industry_board(rank_df, col)` 120-153 (Screener flags) | `section_inside` 654-705; `inside_headline` 638-651 | **G2 open:** "Services has the most, 71%" and "Metals the fewest, 12%" coloured whole (650-651). **G3 open: tick strip** ("2% a line"). G4 open. Same 200D share as Market's M2 (45%), told again here. |
| S8 | **"Stocks in a sector"** kicker; h2 "Textiles' 12 ranked stocks, best rank first." (drawn into a slot after the picker); note on qualified rank; **"Pick a sector"** selectbox (default first "ahead on both"); Screener table ("Core" density) with a Qualified Rank column | `s-stocks` | Heading + selectbox + `render_screener_table` | `rank_df[rank_df[col] == pick]`; `qualified_ranks(rank_df)` (`src/engine/exit_watch.py`) | sector_view.py:791-807 | Pre-S237. The kicker is a noun; fine as a list. Leader links elsewhere go to `?stock=` (103-107). |
| S9 | **Foot**: "Data to 27 Nov 2026 · NSE. 750 stocks ranked; 0 with a price gap, 5 with a short history." then `render_data_quality_footer` (data-quality bar, "© Paresh Patel") | none | Two footers | `ld.when`, `gap_count`, `Short History` | 809-812; components.py:603 | Two footers repeat the counts (inferred from the old text, which shows one line then "© Paresh Patel"); Market and Indices have only the first kind. |

Empty states: `kit.page_empty(mw.NO_PRICES, mw.NO_PRICES_WHY, kicker="Sectors")` (781-783); `kit.page_empty(*mw.no_groups(sp.MIN_STOCKS))` (786-788); NSE-only line S4x; "–" footnotes for 12M too new (353-356) and small groups in S7 (693-695); "no NSE sector index" in S4a group rows (458).

### Sectors: what tipsheet shows that we do not

- S1: "18 of 23 are in uptrends and 5 in downtrends on 27 Nov 2026. Leading on momentum: …" with a date and "Written for …".
- S2: momentum rank 0-100 against all 139 markets with a ring of where momentum stood; we have leads in points with a tick strip.
- (none of ours) "Sectors: share in an uptrend, week by week" since 2007, with 13-week average.
- (none of ours) a heat-strip of every member's uptrends and downtrends since its history begins, "Up since Nov '26".
- (none of ours) leadership turnover: "of the 5 strongest 26 weeks ago, 1 is still in the top 5".
- (none of ours) path efficiency, days above the 200D, distance from the 200D in volatility units, volatility.
- S4a: 52-week small line, vs 200D, 50D, off high, trend since, per index (their markets page); P/E percentile per sector index (their valuation page).
- S5: no counterpart (ours is an extra).
- S6: one panel per family of trend score against momentum rank, faint dots for the rest (small multiples).
- S7: no counterpart by sector; their "NSE indices above their 200-day average" is a single breadth line since 2005.

### Sectors: controls and what they change

| Control | Where | Changes |
|---|---|---|
| Grouping: NSE sector / NSE macro sector / NSE industry / NSE basic industry (or TradingView sector / industry on Nano and Combined) (`sector_tax_choice`) | sector_view.py:769-772 | Every section; S3-S4 give way to S4x unless "NSE sector" |
| "pairs" chips per sector, Latest / Month end, Show the table | S3b | which sector's pair; readout |
| "lmap" chips EMA 20/50/100/200, period 1M/3M; click a dot or "Pick out a sector" to fade the rest; Show the table | S6 | the map's axes and highlight |
| "stable" column headings | S7 | sort |
| "What it is · how to read it", "Show the table" | S2c | text and table |
| Pick a sector (`sector_pick_{col}`) | 798-799 | S8 heading and table |
| Screener table's own controls (sort, page) (inferred) | `render_screener_table` (screener_table.py:804) | S8 |
| System (`?system=`) | 763-766 | universe word (750, 1000 …), default grouping |

### Sectors: data read but shown poorly

- `industry_board` computes "6M Return", "Pass %", "Best" and three "Leaders"; S7 shows only 3M median, Pass count and two leaders (674-676).
- `leadership_views` builds 8 views (4 EMA spans × 2 periods) of two points each; the price history it reads would give a weekly trail (an RRG-style tail) and a history of each sector's breadth.
- NSE sector indices are read with closes from 2012 and P/E (`indices_data.frames()`, 171-178); the page shows 1M-12M returns and today's P/E, no P/E percentile against the index's own past (the Indices page computes this for broad indices, `ip.valuation`).
- `sp.pair_series` holds 12 months for every sector but draws one at a time; small multiples of the 19 pairs on one scale would show breadth of leadership at once.
- Month by month: 13 months × 19 sectors as coloured figures; a line per sector against the 750 (cumulative lead) would carry the same data with history.
- S7's 200D share repeats Market's M2 figure with no link between them.

---

## Cross-page notes

- **Sources (G4).** Source lines exist under: Market M2; Indices I2, I3b, I6 (under a table), I9; Sectors S2c. Missing under: Market M4, M4b, M6, M6b, M9, M9b, M10; Indices I5c, I7; Sectors S3a, S3b, S6, S7 (and tables S4a, S5). The owner's earlier rule "Data date only, no sources named on the page" (MARKET_REQUIREMENTS row 17, owner 20-21 Nov) conflicts with G4 ("none (decided by benchmark)"); the WIP already prints sources on Market and Indices, so row 17 needs updating (CLAUDE.md: "Where the benchmark goes against a decision the owner already took, keep the owner's decision") — the owner's call (inferred conflict).
- **Header strip (G7)** repeats Market's 50D figure on every page but the Dashboard.
- **Kickers (G6).** Market's sections are questions; Indices' and Sectors' kickers are nouns ("Valuation", "Styles", "Broad or narrow", "Month by month").
- **Two chart frames for one measure.** Share above the 200D EMA: Market M2 (record line), M4 (breadth pane), M9 (participation lines), Sectors S7 (tick strip), header strip (50D). New highs/lows: M4b weekly net bars and M10 daily up/down bars.

## Not checked

- No page was run; everything is read from code and from the 28 Nov captures of the OLD pages. Figures quoted in "What it shows" come from those captures (closes of 27 Nov) and will differ on the WIP page.
- The dash_charts JS (how "trows", "rel", "lmap", "stable", "pairs" draw, whether they label extremes) was not read; statements about chart internals beyond the spec passed are marked inferred.
- `docs/PAGE_DESIGN.md` was not re-read section by section for this inventory; the S237 G-rules were applied as stated in the brief.
- tipsheet pages read as text only; "what tipsheet shows" is from the text, not the screenshots.
