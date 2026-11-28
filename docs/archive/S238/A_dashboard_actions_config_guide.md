# Section inventory: Dashboard, Actions, Configuration, Guide (28 Nov 2026)

Read-only inventory for the S237 redesign. Code read at `525085e1` (branch `claude/handover-session-setup-7bd5zk`).
Live text: `s237/ours/ours_<page>.txt`, captured 28 Nov 12:01 UTC.

**Important: the code is newer than the live capture for the Dashboard.** Commit `1311f248` ("S237: Dashboard first
screen redesigned (owner approved); chart sources", 28 Nov 13:37 UTC) came after the capture. So the live text still
shows the old five-sentence verdict, the §1 H2 "The book is 3.0 points behind…" and no "Source:" lines. The code now
draws the date line, the headline, the two-sentence lede, a §1 label H2 and a source line under each chart. Each row
says which version it describes. "Live" means the 28 Nov text and "code" means HEAD.

S237 rules (docs/archive/S237_COMPARISON_2026-11-28.md):
- **G1**: date line, one headline answer, two-sentence lede.
- **G2**: colour on figures only.
- **G3**: familiar lines or bars with history, a shaded usual range, labelled extremes and small multiples. Tick strips and ring scales count as not done.
- **G4**: "Source:" under every chart, with the CSV beside "Show the table".
- **G6**: a question kicker on market pages.
- **G7**: the header strip.

Colour classes: `dh-up` / `dh-down` / `dh-watch` (blue / rust / amber).

---

## 0. Shared chrome (every page)

| # | Section | Anchor | What it shows | Data and where from | Code | Redesign state |
|---|---|---|---|---|---|---|
| 0.1 | Skip links, brand "Paresh Patel", quick links (11 pages), menu popover | `#content` (skip target) | Text links; a keyed popover menu holds the grouped page list | `_PAGES` → app.py | src/ui/components.py:143 `render_header_kpi_bar`; app.py:1275 | G7 open: the site's name is still the owner's name, so the owner has to decide it |
| 0.2 | Date pill "Prices · closes of 27 Nov" | – | Pill | `data_freshness()` → components.py:164 | components.py:100 `_status_pill_html`, used at :178 | G7: the date sits beside the name, as tipsheet does. Kept |
| 0.3 | Market strip: "● Nifty Total Market 4.4% above its 200D EMA · Nifty Total Market 13,494 · Universe 750 · Above 50D EMA 353 (47%) · Near 52W high 374 (50%)" | – | Five figures, the first coloured by regime | `regime_data`, `count_above_ema(rank_df)` → app.py:1338-1353 | components.py:180 (market_html); app.py:1344 | **G7 open** on Actions, Configuration and Guide: the strip shows on every page except the Dashboard (`show_market=…!="Dashboard"`, app.py:1352). S237 says show it once, on Market. The regime phrase is coloured as a whole ("4.4% above its 200D EMA"), so **G2 open** |
| 0.4 | Late/stale notices | – | Amber notice "Late: …" or an info status | `data_freshness()` | components.py:270-273 | Fine (shown only when data is late) |

---

## 1. Dashboard (`src/ui/views/dashboard_home_view.py`, `render_home_view` :1147)

Order in code (:1340-1361): brief → §1 → §2 → §3 → §4 (only if flows) → §5 → §6 → At a glance → footer.
The charts are drawn by `src/ui/dash_charts.py` frames with `static/dash_charts.js`.

| # | Section (as shown) | Anchor | What it shows | Data and where from | Code | Redesign state |
|---|---|---|---|---|---|---|
| D1 | Date line "End of day, 27 Nov 2026" | – (in `<section aria-label="Today in brief">`) | One line | `as_of` = `_fmt.session_of(adj_close)` | `_brief` :1645 (date at :1664) | **done (G1)** in code. Not in the live capture |
| D2 | Headline h1 "The book is up 6.2% so far in November, 3.0 points behind Nifty Total Market." | – | Serif h1. Only the figures are coloured ("up 6.2%", "3.0 points behind") | `di.book_month` (book MTD from `build_portfolio_history`; market from `benchmark_indices`) | `brief_head` :1600 | **done (G1, G2)** in code. Live still shows the old verdict paragraph |
| D3 | Lede, two sentences: "Of our 5 tested signals, **5** point to a stronger month for momentum and **none** to a weaker one. **6** holdings would be sold at the 30 Nov check; the rally is narrow, with only **31%** of the 750 ahead…" | – | Paragraph; colour on the bold counts only | `_signals` + `signal_tests.json`; `plan.sells`; `di.typical_stock` | `brief_lede` :1615 | **done (G1, G2)**. The second sentence joins two ideas with a semicolon and runs long; wording could be tighter |
| D4 | Section pills "1 The book · 2 Next rebalance · 3 Momentum · 4 Money flows · 5 Size · 6 Strong and weak · At a glance" | `nav.dh-pills` → `#s-month … #s-glance` | Anchor pills | static | `_brief` :1658 | Fine. G5: Streamlit's badge covers the pills on a phone (hosting, owner decision) |
| D4a | Fallback verdict (only when the book or market MTD is missing) | – | One paragraph of sentences | `brief_book`, `brief_signals` | `_brief` :1650-1657, :1669 | **G2 open**: whole sentences are coloured, e.g. `<span class="dh-down">6 holdings would be sold at the 30 Nov check.</span>` and `<span class="dh-watch">The rally is narrow: only 31%…</span>` (:1652, :1657) |
| D5 | Kicker "1 · The book, month so far · Nov" + H2 | `#s-month` | H2 is a label, "Against Nifty Total Market and NSE's momentum indices", unless the book trails only because momentum does, or the market has no figure | `bm` | `section_book` :326, H2 :406 | Done in code: the H2 no longer repeats the headline (G1). **G2 open (case-dependent)**: the style-lag title colours phrases, "…because `<span dh-down>`momentum does`</span>`, not `<span dh-up>`its stock picks`</span>`" (:351) |
| D6 | §1 lede: "Nifty Total Market is up 9.2% so far in November. NSE's 5 momentum indices are up 5.4% to 6.3%. The book is up 6.2%, within their range." | – | Three sentences, ink only | `_momentum_range`, `_against_momentum` | :361-367, :300, :284 | OK (G2) |
| D7 | Four KPI tiles: "The book, month so far · Nov +6.2%", "Momentum indices matched or beaten 3 of 5", "Since 1 Jan 2026, after costs +46.8%", "Months ahead of Nifty Total Market 8 of 11" | – | KPI tiles (label, value, status, sub) | `bm`, `since`/`since_mkt` (`di.window_return` from the first fill) | `_kpis` :275; :369-387 | **G2 partial**: each tile's whole status phrase is coloured ("3.0 pts behind Nifty Total Market" dh-down, "Ahead of 3" dh-up, "+46.2 pts on Nifty Total Market"). G3: "Months ahead 8 of 11" has no strip of the 11 months beside it (they are on Portfolio by decision #9) |
| D8 | Caption "The month · to 27 Nov, price return" + chart | – | **dash_charts kind "month"**: one row each for Nifty Total Market, the book and NSE's 5 momentum indices. Line-bar **tick strip** "Each line is 0.25%; filled lines right of the dark zero line are a gain"; period chips "November so far / October" | `bm.momentum_mtd`, `_last_month` :1393 (ledger + `window_return`) | Chart at :408; `_month_scale` :1371; JS `R.month` dash_charts.js:251, `track` :199 | **G3 open: tick strip ("Each line is 0.25%")** and no history. The owner chose this form (DASHBOARD_REQUIREMENTS #8, PAGE_DESIGN 4.2, "IIIIIIIII", 20 Nov), so replacing it needs the owner |
| D9 | how(): "What it is", "How to read it", "Source: NSE Indices' closes; the model book's record.", "Show the table" | – | Two short paragraphs (folded into `<details>` on a phone), source line, table in `<details>` | same | `how` :156 | **done (G4 source line)** in code (not live). **G4 partial**: no CSV beside "Show the table" |
| D10 | §1 note: "pts = percentage points… January to October stay as recorded against the Nifty 500… The book's month-by-month record is on Portfolio." Also the index-late sentence when NSE's close is not in | – | Note | `_frozen_span`, `index_late_note` :420 | :411-416 | Fine |
| D11 | Kicker "2 · What happens on 30 Nov" + H2 "6 sells and 6 buys at the 30 Nov check, 1 session away. 1 more holding is on the edge." plus an optional worst-faller line and an optional sector-go line | `#s-next` | H2 | `model_plan` (src/ui/model_plan.py), `assess`, `next_rebalance` | `section_rebalance` :522; `rebalance_head` :493; `worst_line` :508; `sector_go_line` :515 | Counts with their nouns are coloured ("6 sells"), which is acceptable. **G2 open**: `worst_line` colours a whole clause, "`<span dh-watch>`SYM fell from #12 to #35 in a month`</span>`" (:511), and `sector_go_line` colours "All 2 Telecom holdings go" (:518) |
| D12 | Holding grid "Holding, least room first · Nearest rule · rank trend · Rank 3M ago · 1M ago · Now · Rank trail · If unchanged" (8 rows, AT_RISK_ROWS) | – | CSS grid rows: symbol link, sector · state word, the nearest rule, a trend word ("Sliding fast"), three ranks, a **rank-trail sparkline** (3 points, dashed cut-off at #40), and a Sell/Watch/Clear badge | `assess`, `least_room`, `hist["ranks"]` (`di.rank_trails`), `ind_state` (`mq.leaders_answer`) | :544-560; `_rank_trail_svg` :469 | **G2 partial**: the sector state words ("ahead on both", "fading") and the trend words are coloured as phrases. The badges are fine. The trail has 3 points only (rank history exists in `rank_history.snapshots`) |
| D13 | Note "Checked at the Mon 30 Nov close, filled Tue 1 Dec. The other 12 holdings… Rank: how today's rule ranks… The trail: higher is a better rank…" | – | Note | – | :569-576 | Long (about 90 words); could be split |
| D14 | Right column "Would be bought" | – | Chips GREAVESCOT… | `plan.buys` | :578 | Fine |
| D15 | "Next in line: PGIL · ICIL · NAVINFLUOR · INDHOTEL" | – | Mono line | `plan.next_in_line` | :579 | Fine |
| D16 | Callout: "6 of 20 holdings would change, against 8 in an average month since February. No holding or buy has results announced before the 30 Nov check." | – | Callout box | `record["month_books"]`; `results_calendar.for_book` | `churn_line` :1113; `results_due_line` :1129; :580 | Fine. (b): "8 in an average month" is a number where the monthly churn history exists; no small bar |
| D17 | "Leadership turnover · 21 of today's top 40 were not there a month ago" table: Rising in / 3M ago / 1M ago / Now, then a "Fell out" group, then the sentence "Capital Goods and Textiles lead those climbing in…" | – | Small table + sentence | `di.leadership_turnover(hist["rank_table"])` | `_turnover_html` :433 | Fine. Climbers' "Now" cell coloured as a figure |
| D18 | Link "The plan, share by share, on Actions →" | – | Link | – | :581 | Fine |
| D19 | Kicker "3 · Is momentum still working?" + H2 "Momentum is ahead over 12 months, but has trailed in October and so far in November." | `#s-mom` | H2 | `sm.tiles`, `di.losing_streak` (system's own record, `momentum_health_750.csv`) | `section_momentum` :707; `momentum_head` :664 | **done (G6 question kicker)**. **G2 open**: "`<span dh-down>`has trailed in October and so far in November`</span>`" (:675) |
| D20 | §3 lede "We tested each signal on the Nifty 500's record since 2010: 5 pass and 2 are not confirmed. On today's readings, 5 point to a stronger month and none to a weaker one. At the 30 Oct month-end…" | – | Paragraph | `signals`, `tests` | `momentum_lede` :684; `readings_line` :605 | **G2 open**: `readings_line(colour=True)` colours the phrases "5 point to a stronger month" and "none to a weaker one" (:608-609) |
| D21 | Caption "This system's top fifth against the 750, equal weight, points, longest window first" + 4 tiles: "12 months +16.0 / Last 3 months +4.2 / October −0.8 / Month so far −1.4" | – | Tiles, each with a small **diverging bar** scaled to ±13 | `sm.tiles(own, mtd)`; `_month_so_far` :258 | :714-719, :753 | Acceptable as tiles. The mini bar has no scale or history; the history is in D24. Fine |
| D22 | Tile note "Each tile is the top fifth… This system's record starts in December 2021… – in a tile: the system is too young" | – | Note | – | :755-758 | Fine |
| D23 | Caption "Momentum's lead, every month · top fifth less all members, equal weight, points" + band note "shaded: the usual range since 2021, −0.9 to +1.9 pts (the middle half of all months)" + lag note ("…0.8% below its September 2026 best… deepest fall since December 2021 was 10.4%… On the Nifty 500's record since 2010… 12.5%… A description, not a forecast.") + link "NSE's momentum indices, style by style, on Indices →" | – | Caption, notes, link | `_lead_bars` :1412; `di.momentum_lag(own)`; `_long_record(spreads)` :250 | `_lag_note` :638; :759-761 | The band note is done. The lag note runs to about 90 words in one paragraph |
| D24 | Chart: momentum's lead by month | – | **dash_charts kind "bars"**: monthly bars from zero, coloured by sign, **shaded usual range (IQR)**, opens on "all" (LEAD_RANGE) | `momentum_health_750.csv` via `sm.read` → `_lead_bars` | :763; JS `R.bars` :269, `barPane` :95 | **G3 partial**: bars with history and a usual-range band (done), but **extremes not labelled** (`barPane` has no `marks`; only `linePane` has them, dash_charts.js:81). History from Dec 2021 only, though the Nifty 500 record since 2010 (`momentum_health.csv`, 2010-02 on) is read and quoted in words (D23) and not drawn |
| D25 | how() for D24, "Source: our calculation from NSE's daily closes and the ranking." + Show the table (Month, Lead) | – | as D9 | – | :764-768 | **done (G4 source)**; CSV open |
| D26 | Signals table, caption "What today's readings have meant for next month · Momentum's next-month lead after months like this, points · all months since 2010 average +0.8". Seven rows: Nifty 500 vs its 200D EMA; Heavy foreign buying; Nifty 500 vs its 10-month average; Stocks that qualify; Breadth thin; Participation jump; Sharp rebound. Columns: 3M ago · 1M ago · Now · In its own history · Months like this · Against the +0.8 average · Our test · What would flip it | (none; `.dh-sec-cont`) | Wide table (min 1080 px, first column sticky on a phone) with an in-cell **diverging bar** and Pass / Not confirmed badges | `_signals` :1767 (reads `momentum_health.csv`, `benchmarks.csv`, `nifty500_breadth`, `_qualify_today`, `signal_tests.json`) | :770-786 | **G2 open**: "Better than usual" / "Worse than usual" are coloured words. (b): "In its own history" is a sentence ("Lower than 50% of days since 2000") where 26 years of the series exist and no sparkline or percentile strip is drawn. No section anchor for the table |
| D27 | Notes: the optional "Now" column note; "The test, fixed before looking: … Describing is not forecasting; the live rules stay fully invested whatever this says." | – | Notes | – | :779-786 | Fine (requirement #23) |
| D28 | Kicker "4 · Money flows" + H2 "Foreign investors have bought ₹1.54 lakh Cr so far in November, the most in a month since 2016. They sold ₹3.18 lakh Cr over the 11 months before. Domestic institutions are net sellers so far in November, selling into the foreign buying." | `#s-flow` | H2 of three sentences | `di.flows_summary(nsdl)`; `_dii_now(nse_dii)` | `section_flows` :808; `flows_head` :789 | **G2 open**: the whole phrase "₹1.54 lakh Cr so far in November, the most in a month since 2016" is in `dh-up` (:797-799), and the whole DII sentence is in `dh-down` (:805). G6 open (market section, statement not question). The H2 has 3 sentences |
| D29 | Five KPI tiles: "Foreign, 2 to 27 Nov +₹1.54 lakh Cr", "Against the 750's market cap +0.3%", "Foreign, last 20 sessions +₹1.55 lakh Cr", "Foreign, the 11 months before −₹3.18 lakh Cr", "Domestic institutions, 2 to 25 Nov, on NSE −₹55,000 Cr" (+ provisional all-exchange note) | – | KPI tiles | `nsdl_fpi_daily.csv`, `system_market_caps` (`nse_market_caps.csv`), `nse_dii.csv`, `fii_dii_flows.csv` (`_dii_provisional_after` :1460) | :812-836 | **G2 partial**: the status phrases are coloured ("Record: largest month since 2016", "Net sellers in 8 of 11 months"). (b): the last-20-session figure has no daily history drawn, though NSDL's daily file is held |
| D30 | Left column: caption "Foreign investors, net, each month · ₹ thousand Cr, dashed line: a heavy-buying month, ₹14,000 Cr or more; teal: domestic institutions on NSE, stacked…" + chart + band note "shaded: foreign investors' usual range since 2016, −13 to +14 thousand Cr…" + how() "Source: NSDL's daily FPI reports; domestic institutions from NSE's category-wise turnover." | – | **dash_charts kind "bars"**: 12 monthly bars with value labels, the DII stacked in teal, a dashed heavy-buying level and an IQR band | `_fpi_bars` :1506 (`nsdl_fpi_daily.csv` from 2016-01-01; `_dii_months` :1435) | :864-878 | **G3 partial**: band done; **only 12 months are drawn** (`mo = allm.iloc[-12:]`, :1515), though data runs from Jan 2016 and the H2's claim "the most since 2016" cannot be seen; no range chips; extremes not labelled. G4 source done; CSV open |
| D31 | Right column "What heavy foreign buying has meant · Jan 2016 to Oct 2026": three evidence boxes. (1) "Better months for momentum next. …+1.4 points… +0.4… held in both halves" + badge "Tested here · 129 months…, in-sample". (2) "No forecast for the Nifty 500. … correlation +0.54 … −0.07". (3) "Not a large-cap story. … Nifty 50 trailed… by 0.4 points" | – | Boxed text | `di.flow_evidence(nsdl, spreads, bench)` | :838-858, :879-880 | **G2 open**: "Better months for momentum next." is a bold coloured phrase (:845). No chart of the after-heavy vs after-rest gap (a two-bar chart would do) |
| D32 | §4 note "Foreign: confirmed FPI equity figures, exchange and primary market. Domestic institutions: trades on NSE to October 2026…" | – | Note | – | :881-884 | Fine. Requirement #28 says "no sources named", which is in tension with G4 |
| D33 | Kicker "5 · Size, and where momentum works" + H2 "Large Cap momentum is failing: the Nifty200 Momentum 30 is 4.7 to 7.3 points behind… In Mid Cap and Small Cap, momentum is within 2.5 points of its index on every window. They hold 61% of the book." | `#s-size` | H2 | `di.size_table(closes, market, idx_end)`, `_book_sizes(risk)` | `section_size` :996; `size_head` :961 | **G2 open**: "`<span dh-down>`Large Cap momentum is failing`</span>`" and "`<span dh-up>`In Mid Cap and Small Cap, momentum is within 2.5 points of its index`</span>`" (:978, :980). G6 open |
| D34 | "The book by size, NSE index lists" + stacked size bar ("Small Cap 56% · Micro Cap 33%") | – | 100% stacked bar, labelled where ≥ 20% | `book_risk.tiers` → `_book_sizes` :1891 | :1018-1020 | Fine |
| D35 | Size table "Size · its index · its momentum index / Book / Size against Nifty Total Market 1M 3M 6M / Momentum against its size index 1M 3M 6M" (Large, Mid, Small, Micro) | – | Table; cells ≥ 3 pts highlighted | `di.size_table`; `di.SIZES` | :1021-1029 | **G3 open**: S237 asks for **small multiples for the four sizes** (lines over time on one scale); here there are only three windows as numbers. Index closes exist from 2016 or earlier (`benchmark_indices.csv`) |
| D36 | Left: "Is the rally shared? · share above the 200D EMA, by NSE size list" chart | – | **dash_charts kind "shared"**: one row per size list, a **tick strip** (step 2) from 0 to 100% with 40/60 lines, a triangle for a month ago, and 3M/1M/now figures | `di.size_breadth(adj_close, lists, as_of)` (`data/indices/*list.csv`, today's members) | `_shared_parts` :943 (Chart :952); JS `R.shared` :292 | **G3 open: tick strip** (step 2, "each line is 2%", inferred from step) and no history beyond 3M ago. The members are today's only, so history is survivor-biased (said in D39) |
| D37 | Right: "The typical stock against Nifty Total Market · The 750, three ways · %" table (Nifty Total Market / Equal-weighted 750 / Median stock / Share beating Nifty Total Market × 1M 3M 6M 12M) + sentence "Only 31% of the 750 beat… but **the median stock fell 3.5%**…" | – | Table + sentence | `di.typical_stock(ranked_px, market, idx_end)` | `_typical_html` :888 | Share cells < 30% are bold rust (figures, fine). (b): no history of "share beating" though it can be computed from prices (inferred) |
| D38 | "Is the rally shared? Now Nifty 100 is the broadest and Nifty Microcap 250 the narrowest… A month ago… 33% of the book is in Micro Cap." + how() "Source: our calculation from NSE's daily closes and NSE's index lists." | – | Sentence + how block | `shared_line` :913 | :953-958 | **G2 open**: `<b class="dh-up">Nifty 100 is the broadest</b>` and `<b class="dh-down">… the narrowest</b>` (:926-929). G4 source done; CSV open |
| D39 | §5 note "Size lists and members are NSE's as of today, so older readings leave out stocks… NSE has no microcap momentum index." | – | Note | – | :1028-1030 | Fine |
| D40 | Kicker "6 · Where the book is strong and weak" + H2 "66% of the book is in sectors ahead of all ranked stocks over 6M and 1M; 19% is in 3 behind on both." | `#s-book` | H2 | `mq.leaders_answer` sectors (rel_6m, rel_1m) × Portfolio's weights | `section_strong_weak` :1044; `strong_weak_head` :1032 | **G2 open**: "`<span dh-up>`66% of the book is in sectors ahead of all ranked stocks`</span>`" and "`<span dh-down>`19% is in 3 behind on both`</span>`" (:1037, :1041) |
| D41 | Chart: the book by sector status + key + how() "Source: the model book; sectors from NSE's classification." | – | **dash_charts kind "segbar"**: one segment per sector, sized by weight, coloured strong/turning/weak, with a readout | `weights` (book × industry), `sectors` | :1081-1085; JS `R.segbar` :303 | A stacked bar, familiar enough. No history (the book's sector mix by month exists in `month_books`, inferred). G4 source done; CSV open |
| D42 | Three cards "Strong 65.9% / Turning 14.5% / Weak 19.4%", each listing sectors with "N holdings", weight and "6M · 1M +10.1 · +1.7" | – | Cards | same | :1066-1079 | Card titles and totals coloured (labels, fine); the 6M·1M figures are coloured figures (fine) |
| D43 | §6 note "Each sector's stocks, equal-weighted, against all ranked stocks built the same way: 6M · 1M in points, as on Sectors." | – | Note | – | :1087-1088 | Fine |
| D44 | "At a glance" (h2, styled h3) + "Reference figures; the full readings are a page away" | `#s-glance` | Heading | – | `section_glance` :1091 | Fine |
| D45 | Chart: the index and its breadth, "The index and how many stocks carry it" + how() "Source: the index from NSE Indices; the share our calculation from NSE's daily closes." | – | **dash_charts kind "breadth"**: two panes on one crosshair. Top: Nifty Total Market line (dashed, area). Bottom: share above the 200D EMA with fixed 60–100 / 0–40 shaded zones. Chips 6M / 12M / 3Y (opens 12M) | `_breadth_spec` :1552 (`benchmarks.csv` + `mq.join_market`; `hist["above_200"]` via `pit_breadth.splice` of `breadth_history.csv`) | :1105-1110; JS `R.breadth` :315 | **G3 partial**: lines with history, done. The bands are fixed thresholds, not a usual range; extremes not labelled; **3 years only** (`_breadth_spec` cuts to 3Y) though the Nifty 500 runs from 1999 and breadth from 2021 (or longer through `daily_history`). G4 source done |
| D46 | Glance card "Indices, 27 Nov · Indices →": Nifty Total Market −0.5%, Nifty 50 −1.1%, Midcap 150 0.0%, Smallcap 250 +0.5%, Microcap 250 +0.8% | – | Key/value card | `bi.series` closes → `day()` | `_glance` :1947 | (b): one-day moves only; fine for a glance card (by decision, "one-day moves only in At a glance") |
| D47 | Glance card "Breadth, ranked stocks · Market →": "Above their 200D EMA 45% (32% a month ago)", "Above their 50D EMA 47% (18% a month ago)" | – | Key/value | `hist["above_50/200"]` → `di.trail_of` | :1957-1959 | Fine (the history is drawn in D45) |
| D48 | Glance card "The book's risk · Portfolio →": Beta 1.0; Volatility, a year 22.6% vs 15.6% (amber); Slowest exit MBAPL 0.03 days; Below its peak −2.6% | – | Key/value | `pr.risk(eq, market)`; `br.book_risk` (volume) | :1960-1970 | Fine. "Below its peak" has no history here (it is on Portfolio) |
| D49 | Glance card "Valuation and styles, 27 Nov · Indices →": "Nifty 500 P/E, percentile since 2021 22nd · 1M 4th · 3M 27th"; Leading style… +4.2 pts, 12M; Trailing style… −5.7 pts, 12M | – | Key/value | `indices_page.valuation`, `.styles` via `indices_data.frames()` | `_indices_glance` :1935; `indices_glance_rows` :1908 | Fine for a glance. Percentile "since 2021" is the Indices page's choice |
| D50 | Footer "Data to 27 Nov 2026 · NSE." | `p.dh-foot` | One line; the date turns red on a stale backup | `_fmt.data_to_html(as_of)` | :1360 | Fine. The comment at :1359 ("sources are not shown") is stale against G4 |
| D51 | Empty state (no model book): kicker "Dashboard", h1 `mw.NO_MODEL_BOOK`, one lede, footer | – | Page head | `current_book` empty | :1168-1172 | Fine (S193 R4) |

**Dashboard controls**
- Section pills (D4): anchor jumps only.
- "month" chart period chips "November so far / October" (D8): they switch the rows between this month and the last finished month.
- Range chips on the breadth chart, 6M / 12M / 3Y (D45). The lead-bars chart (D24) states range "all" with no chips. The flows chart (D30) states 12M with no chips, and only 12 months of data are sent.
- Every chart: values under the pointer, a dragged finger and the arrow keys, shown in a live readout.
- "Show the table" `<details>` under each of the 6 charts. On a phone, a "What it is · how to read it" `<details>`.
- Links: each symbol links to its stock page; Actions → (D18); Indices → (D23); four glance-card links.
- **No download anywhere on the Dashboard** (G4 asks for a CSV beside "Show the table").

**Dashboard: figures with data that the page shows poorly**
- `compare = _flow_compare(...)` (:1332) is worked out and passed to `section_flows(…, compare, …)` (:1353, param :809) but never used. NSE's provisional FPI net is not set against NSDL's anywhere on the page.
- The flows chart draws 12 months; NSDL runs from 2016 (:1515).
- The lead bars draw the system's record from Dec 2021. The Nifty 500's lead since 2010 is read (`spreads`) and quoted in words only (D23, D24).
- The breadth chart is cut to 3 years (:1552-1560); the index runs from 1999.
- The signals' "In its own history" is a sentence, not a strip or sparkline (D26).
- The size table has three windows as numbers, with no lines over time (D35).
- Rank trails are 3 points (3M, 1M, now) where `rank_history.snapshots` holds more (D12) (inferred that more dates are cheap).
- "8 in an average month" churn has no small bar of the months (D16).

---

## 2. Actions (`src/ui/views/actions_page.py` `render` :595; entry `actions_view.render_actions_view` :133; `qualified_view.render_qualified_view` :79)

Draw order (:603-648): the `top` container (header, filled last but drawn first), the `bar` (switch + Kite popover), notes,
then the sections in `section_change → sell → buy → after → hold`, the expander, the footer. The live order matches.

| # | Section (as shown) | Anchor | What it shows | Data and where from | Code | Redesign state |
|---|---|---|---|---|---|---|
| A0 | Shared header + market strip (0.1–0.3) | – | – | – | – | **G7 open** (the strip repeats on Actions) |
| A1 | Kicker "Actions" + h1 "6 sells and 6 buys at the 30 Nov check, filled on 1 Dec. ₹40.8 lakh out and ₹40.8 lakh in." | `.pf-head` | Serif h1; "6 sells" rust, "6 buys" blue | `model_plan` → `Plan`; amounts from `sell_rows`/`buy_rows` (`book_series` value) | `header` :133; `title` :159; `kit.verdict` page_kit.py:164 | **G1 partial**: headline answer and a one-sentence lede, done, but **no date line** ("End of day, 27 Nov 2026", as the Dashboard has). G2 ok: the count plus its noun. The empty case colours a whole phrase: "No trade at the 30 Nov check: `<span dh-up>`every holding is clear of the sell rules`</span>`" (:165), so **G2 open** there |
| A2 | Sub "What the model book would trade at the next rebalance, if today's prices hold." (My holdings: "Your holdings under the record's rules, if today's prices hold.") | – | One sentence | – | `subtitle` :174 | Fine |
| A3 | Four KPI tiles: "Sell 6 · break a sell rule at today's close · ₹40.8 lakh to sell", "Buy 6 · best qualified, not held · ₹40.8 lakh to buy", "Hold 14 · 1 close to a rule", "Next rebalance Mon 30 Nov · 1 session away · fills Tue 1 Dec" (+ "NSE holidays not yet published") | – | KPI tiles (`pf-four`) | `Plan`, `next_rebalance`, `_sessions_between`, `holiday_caveat` | `header` :133-151; `_kpis` portfolio_page.py:88 | The tile values are coloured figures (fine). The amount repeats the h1 |
| A4 | Control bar: segmented "Model book / My holdings" + popover "Kite basket" (download icon, primary) | key `ac_bar` | Segmented control + popover | `av.SOURCES` | :608-612, :631 | Fine. The live text shows the icon names "download", "expand_more" as text (screen-reader text from Material icons, inferred) |
| A4a | (My holdings only) "Your holdings" text input + "Save" + popover "Upload from Kite" (caption, file uploader, "Use these N holdings" button) | key `xw_editbar` | Form row | `holdings_store` (browser storage) | `actions_view._edit_holdings` :86 | Fine. The failure note is amber |
| A4b | Inside "Kite basket": (My holdings) "Capital (₹)" number input; caption (`kite_caption`); **"Download basket CSV"** | – | Popover body | `basket(p)` :91 | :631-642; `kite_caption` :281 | Fine |
| A5 | Notes: record-start info (Nano / Combined before inception; `record_start_line` :532) and the unpriced-holding warning (`unpriced_note`) | – | `kit.note` info / warning | `SYSTEM_INCEPTION`; `canonical_book.unpriced_note` | :612-613, :626-630 | Fine |
| A6 | Empty states: "Add your holdings above, or upload the holdings CSV from Kite…"; the no-model-book sentence | – | `kit.empty` | – | :620-625; `MY_EMPTY` :360 | Fine |
| A7 | "What could still change · before the 30 Nov close" | `#ac-change` | Section head (h2 + sub) | – | `section_change` :180 | G6 does not apply. Fine |
| A7.1 | "Holdings close to a sell rule · could still change to a sale": bullets "DIACABS is 33rd among the qualified, 7 places inside the top 40; can fall 2.1% before it reaches its 50D EMA." | – | List | `assess` WATCH rows | :183-189 | Fine. (b): "can fall 2.1%" has no visual of the distance (a cushion bar would do) |
| A7.2 | "Next in line · would come in if a buy drops out…": "PGIL · ICIL · NAVINFLUOR · INDHOTEL" | – | Mono line | `plan.next_in_line[:4]` | :186, :190-191 | Repeated in A9.4 as pills with ranks. Duplicate |
| A7.3 | "Results and corporate actions before the fill · to 1 Dec": list or "No board meeting or ex-date is announced for any holding, sell or buy before the 1 Dec fill." + note "Board meetings are from NSE's calendar, announced to 5 Dec. Ex-dates are from NSE's corporate actions, collected to 10 Dec…" | – | List / empty line + note | `results_calendar.load()`; `data/reference/nse/corporate_actions_recent.json` | `_events` :553; `events_note` :580; `_events_html` :196 | Fine. The note names NSE as the source, which is in tension with requirement #20 ("no data sources") but agrees with G4 |
| A8 | "Sell · 6 at today's close": table Holding (sector) / The rule it broke / Held since / Since entry / Shares / Amount + note "Sell in full. The basket carries these sells…" (+ phone note) | `#ac-sell` | Table | `sell_rows` :81 (`book_series` shares), `assess.why`, `book["Return %"]`, `book["Entry Date"]` | `section_sell` :238 | Since-entry is a coloured figure (fine). No chart, none needed |
| A9 | "Buy · best qualified, not held" | `#ac-buy` | Section head | – | `section_buy` :325 | – |
| A9.1 | Evidence box "What swaps have added so far. In their first month, the record's 91 buys were ahead by 3.0 points… The 71 stocks it sold… Over 3 months: +10.6 against +2.4 points. 9 of the 71 sold were bought back within 2 months. Jan 2026 to Nov 2026: a short record…; evidence, not proof." | – | Boxed paragraph (blue left rule) | `swap_evidence.from_record(hist, adj_close, Nifty Total Market, former_members)` | `swaps_html` :317; `swaps_sentences` :297; gather :483-491 | (b): about 60 words of figures with no chart. A two-bar "buys vs sold, 1M and 3M" or a per-rebalance strip would carry it. The data is per rebalance (inferred from `SwapEvidence`) |
| A9.2 | Buy table: Stock / Qualified / Price / 3M / 6M / From 52W high / Weight / Amount / Shares | – | Table (4 columns hidden on a phone, with a note) | `buy_rows` :69; `rank_df` CMP, 3M Return, 6M Return, % High; `qualified_ranks` | :331-354 | Coloured return figures (fine). (b): no price sparkline, though the Screener table has a 60D spark for the same stocks |
| A9.3 | Note "Amounts are the record's target weight of the model book's value today, ₹1,46,77,316. Each buy gets 4.6%, less than the 5% buy size… six-monthly rule…" | – | Note | `amounts_line` :271; `buy_limit_line` :515 | :355-356 | Fine |
| A9.4 | "Next in line" pills "#19 PGIL #20 ICIL #21 NAVINFLUOR #23 INDHOTEL" | – | Pills linking to stock pages | `plan.next_in_line[:4]`, `qrank` | :344-345, :357 | Duplicate of A7.2 |
| A10 | "The book after the trades · sector and size, now and after the trades": two tables, Sector Now/After/Change pts and Size Now/After/Change pts (+ Cash) + note on now/after and the size lists | `#ac-after` | Two tables side by side | `now_weights` (Portfolio's Weight %), `plan.weights`, `_sizes` (`membership_history.json`), `uninvested` | `section_after` :203 | (b): a now/after pair is a natural paired-bar or dumbbell chart; tables only. Change is a coloured figure (fine) |
| A11 | "Hold · closest to a sale first": table Holding / Status / Rank 3M / 1M / Now / Rank buffer (top 40) / To 50D EMA / To −20% from 52W high / Closest to / Since entry, then note (`hold_note`) | `#ac-hold` | Table, Status word coloured, cushions < 3% amber | `assess` (EMA cushion, High cushion, Rank room), `di.rank_trails` | `section_hold` :373; `hold_note` :363 | The status words are coloured (labels, acceptable). (b): the rank 3M/1M/now are numbers, while the Dashboard draws a rank-trail sparkline for the same data (D12); `CUSHION_HELP`/`BUFFER_HELP` (actions_view.py:32-35) look unused (inferred) |
| A12 | Expander "Buy candidates · the qualified list" (collapsed) | – | `st.expander` | – | :646 | Requirement #13 |
| A12.1 | Bar: caption "Best-ranked stocks passing both filters." + segmented "Top 10/15/20/25/30" + **"Export CSV"** | key `qual_pool_bar` | Caption + controls | `rank_df` (Above 50 EMA & Near 52W High) | qualified_view.py:79-104 | Fine |
| A12.2 | Card "The list": the Screener table (iframe) in "Core" columns, with a 60D sparkline column and a show-all button | `qual_list` | Table | `render_screener_table(view, adj_close, "Core")` | qualified_view.py:110; screener_table.py:804 | Fine (the Screener's own table) |
| A12.3 | Card "Where they come from": bar list of the top 6 sectors + "N others", then "A and B hold 45% of the list." | `qual_ind` | Horizontal bars (`kit.bar_list`) | `industry_rows` :66; `concentration_line` :120 | qualified_view.py:113-117 | **G4 open**: a chart with no source line (minor). Empty: "No stock passes both filters today." (`no_pass_lines` :51) |
| A13 | Footer "Data to 27 Nov 2026 · NSE. 750 stocks ranked; none with a price gap, 5 with a short history." | `p.dh-foot` | Line | `_fmt.foot_line(rank_df, as_of)` | `footer` :411 | Fine |

**Actions controls**
- "Model book / My holdings" (`xw_source`): switches the whole plan (sells, buys, amounts, basket contents).
- My holdings: the text input + Save writes the browser store. "Upload from Kite" parses a CSV; "Use these N holdings" saves it.
- "Kite basket" popover: the Capital box (My holdings only) resizes the buy amounts (`p.value`); **"Download basket CSV"** (`dl_actions_basket`).
- Expander: "Top N" (`qual_top_n`) trims the qualified list; **"Export CSV"** (`dl_qual_csv`); the screener table's own sort and show-all controls.
- Links: each symbol and next-in-line pill opens its stock page.

**Actions: figures with data that the page shows poorly**
- No date line (A1).
- Swap evidence is a paragraph of figures (A9.1).
- Now/after weights are tables only (A10).
- Hold ranks are numbers where the Dashboard draws a trail (A11).
- Next in line is shown twice (A7.2, A9.4).
- The buy table has no price spark (A9.2).
- `qualified_view.correlation` (:37) is defined here and used by Portfolio only. This is not a fault.

---

## 3. Configuration (`src/ui/views/config_view.py` `render_config_view` :671)

| # | Section (as shown) | Anchor | What it shows | Data and where from | Code | Redesign state |
|---|---|---|---|---|---|---|
| C0 | Shared header + market strip | – | – | – | – | **G7 open** |
| C1 | h1 "Configuration" + sub "Changes apply as you make them. The model book on Portfolio and Actions keeps the track record's own settings." | `.scr-head` | Page head, **no kicker** | – | `kit.page_head` :677 | **G1 open**: the page's name is the title. PAGE_DESIGN 2a wants a kicker "Configuration" over a title that answers, e.g. "The ranking uses the default weights on Nifty Total Market." No date line |
| C2 | "In effect": Universe Nifty Total Market · Score weights Default · Backtest max per stock · per sector 5% · 40% · Backtest liquidity floor Off | – | Key/value line | session state (`cfg_indices`, `cfg_system`, `_WINDOWS`, `_risk`) | `kit.kv_line` :689-697 | Fine (the answer is here; it could be the headline) |
| C3 | Section index "1 · Universe 2 · Momentum score 3 · Portfolio limits 4 · Data health" | `nav.cfg-index` → `#cfg-universe` etc. | Anchor links | `_SECTIONS` :74 | :699-704 | Fine |
| C4 | "1 Universe": "Which stocks are ranked, from the official NSE lists." | `#cfg-universe` | Left intro column (number, h2 with `title="Changes: every page"`, sentence), controls on the right | `_SECTIONS[0]` | `_section` :658 | The reach ("Changes: every page") is only a hover tooltip on the h2, invisible on a phone. It could be a visible line |
| C4.1 | Readings "Last synced 28 Nov 2026 at 01:13", "In the index files 752 · unique stocks across the synced lists", "Ranked now 750 · the header's Universe: members with 63+ days of prices" | – | `kit.readings` tiles | `get_sync_metadata()` | `_section_data_sync` :256-277 | Fine. 752 / 750 / the Guide's "751" (G3 row) are three counts a reader meets on three pages. See G-lead |
| C4.2 | Freshness table: Source / Latest / Age / Status (Current / Behind) | – | Table (`render_saas_table`; not in the live text capture, inferred to be an iframe/grid) | `data_freshness()` components.py:164 | `_freshness_table` :131 | (b): ages are words; no figure of how late each file usually runs |
| C4.3 | "Files the pages read" table (name, file, read by, date, rule…) + caption "Each file against the prices' session, by its own rule…" | – | Table + caption | `file_dates(session)` :219 over `FILE_RULES` :163 | :146-152 | Exposes file names (benchmarks.csv…) on a public page. PAGE_DESIGN rule 7 says "never an internal path" (lead, not checked against the rule's scope) |
| C4.4 | Warning "The last sync (…) did not complete…" (only on failure) | – | `kit.note` warning | sync_meta | :279-286 | Fine |
| C4.5 | "System" segmented: Nifty 750 / Nifty 1000 / > ₹2,000 Cr / Combined + caption ("Default · record since Jan 2026") + help tooltip | key `cfg_system_radio` | Segmented control | `SYSTEMS`, `membership_summary()`, `NIFTY_1000_PATH` | :288-318 | Fine. **This is the only place to switch system for every page** (inferred; the `?system=` URL param also works) |
| C4.6 | "Indices to rank" multiselect (Nifty Total Market…) | key `cfg_indices_multiselect` | Multiselect | `INDICES_URLS` | :320-332 | Fine |
| C4.7 | Button "Index files on disk (6)" (folder icon) → dialog "Index files on disk": one caption per list ("**Nifty Total Market**: `752` rows in NSE's file … KB · date") + note on demergers and DUMMY placeholders | key `dlg_cfg_index_files` | Tertiary button + `st.dialog` | `INDICES_LOCAL` files on disk | :334-336; `_index_files_dialog` :89 | The dialog's missing-file line prints the server path, "File missing at `{path}`" (:107), against "server paths are not shown" (:629 comment) |
| C4.8 | (Owner only, `?owner=KEY`) "Sync from niftyindices.com" + "Clear cached files", with a status box | key `cfg_sync_row` | Buttons | `sync_official_nse_indices` | :341-386; `owner_mode` :389 | Not visible to readers. Fine |
| C5 | "2 Momentum score": "How much each lookback window counts." | `#cfg-score` | Intro | – | `_SECTIONS[1]` | The tooltip reach "ranks on every page, and the backtest's starting weights" disagrees with the page sub (C1) and with the Guide ("for the Screener and the Backtest; the record and the model book … keep these"). It is unclear in words whether the Dashboard or Actions ranks move (lead, not checked in code) |
| C5.1 | "How the score weighs each window · Weight vector: 10% · 30% · 30% · 20% · 10%" + stacked bar "1M 10% 3M 30% 6M 30% 9M 20% 12M 10%" | – | Stacked bar in ink shades | `_WINDOWS` resolved state | `_section_momentum_signal` :426-454 | Fine. "Weight vector:" is pinned by the QA probe, so keep the wording |
| C5.2 | Button "Reset to defaults (weights only)" | key `cfg_w_reset` | Button | `DEFAULT_LOOKBACK_WEIGHTS` | :456-464 | The live text reads "Reset to defaults" (older); code has "(weights only)" |
| C5.3 | Five sliders 1M, 3M, 6M, 9M, 12M (0–1, step 0.05) with help tooltips | keys `cfg_w1`…`cfg_w5` | Sliders | `_WINDOW_HELP` :412 | :466-484 | On a phone, five sliders in 5 columns are narrow (inferred from the capture's iPhone image not checked) |
| C5.4 | Warning (all zero) + caption "Weights are normalised to 100%." | – | Note + caption | – | :490-499 | Fine |
| C6 | "3 Portfolio limits": "The Backtest's caps and floor. The track record's own limits: 5% a stock, 40% a sector, no floor." | `#cfg-limits` | Intro | – | `_SECTIONS[2]` | Fine |
| C6.1 | Sliders "Most in one sector (%)" (15–50) and "Most in one stock (%)" (2–15) | keys `cfg_sc`, `cfg_stc` | Two sliders | `_RISK_SETTINGS` :514 | `_section_portfolio_risk` :527-541 | Fine |
| C6.2 | Warnings: stock cap above sector cap; or "At 5% per stock and 20 backtest holdings, every stock sits at the cap… Raise it to 7% or more…" | – | `kit.note` warning | `bt_top_n` | :543-558 | The second warning shows **at the default settings**, so a first-time reader sees an amber warning about a normal state. It should be a neutral note (lead) |
| C6.3 | Toggle "Liquidity floor" + number input "Floor (₹ Cr a day)" (disabled when off) | keys `cfg_lf`, `cfg_lfv` | Toggle + input | `_RISK_SETTINGS` | :561-573 | Fine |
| C7 | "4 Data health": "Price corrections and data files." | `#cfg-health` | Intro | – | `_SECTIONS[3]` | Fine |
| C7.1 | Readings "Corporate actions adjusted 37 · sessions, before ranking", "Splits the provider missed 21 · a re-fetch fixes these", "Possible demergers 16 · no standard ratio" (or success "No corporate actions flagged…") | – | `kit.readings` | `load_events()` (corporate_actions log) | `_section_data_health` :584-597 | (b): counts with no dates in view; the dates sit behind a dialog. A small by-month bar is possible (inferred) |
| C7.2 | Button "All sessions, by date" → dialog "Corporate actions adjusted, by date": two captions + table Date / Symbol / Move / Ratio / Looks Like / Kind | key `dlg_cfg_sessions` | Button + `st.dialog` (large) | events | :621-623; `_spike_sessions_dialog` :114 | "Looks Like" is title case (glossary rule, minor) |
| C7.3 | "Data files" table: Dataset / Local copy / Size / File (Market Caps, TV Classification, NSE Classification) + caption "Prices come from the published price store, not a local file; their date and coverage are in the line at the foot of the page." | – | Table + caption | `MCAPS_FILE`, `TV_CLASSIFICATION_FILE`, `NSE_CLASSIFICATION_FILE` | :625-655 | "TV Classification" is a vendor's name on the page (lead against rule 7) |
| C8 | Footer "Data to 27 Nov 2026 · NSE" (left) and "© Paresh Patel" (right) | – | Footer bar | `render_data_quality_footer(as_of=prices date)` | :719-727; components.py:603 | Fine |

**Configuration controls**
- System (every page, via rerun). Indices to rank (the ranking; clears the data key).
- Index files dialog. Owner-only Sync and Clear cache.
- Reset weights and the five weight sliders. The page says they move the ranks; the Guide says the Screener and Backtest only. This needs one wording.
- Sector cap, stock cap, liquidity toggle and floor (Backtest only).
- "All sessions, by date" dialog.
- **No download** of the freshness or corporate-action tables.

**Configuration: figures with data that the page shows poorly**
- The corporate-action counts have no time axis.
- File ages are words, with no record of usual lateness.
- An amber warning shows at the default settings (C6.2).

---

## 4. Guide (`src/ui/views/guide_view.py` `render_guide_view` :276, body `_body` :58)

| # | Section (as shown) | Anchor | What it shows | Data and where from | Code | Redesign state |
|---|---|---|---|---|---|---|
| G0 | Shared header + market strip | – | – | – | – | **G7 open** |
| G1 | Kicker "Guide" + h1 "How the ranking picks the book, and how to act on it." + sub "The ranking, the filters, the book and the record, step by step." | `.scr-head` | Page head | – | `kit.page_head` :278 | Fine for a method page (G1's date line is not needed). The title and sub say the same thing twice |
| G2 | On-this-page nav: The five steps · The score · Filters · The book · Weighting · Acting on it · Questions | `nav` → `#steps #score #filters #book #weights #acting #faq` | Underlined links | static | :108-112 | Fine |
| G3 | "The five steps": ordered list Universe ("The 751 stocks of Nifty Total Market…"), Score, Filters, Book, Trades + line "The figures these steps produce are on Portfolio and Backtest…" | `#steps` | `<ol>` | `TRACK_RECORD_CONFIG`; `_members_now()` :46 (`membership_history.json`) | :114-130 | **Lead (not checked)**: "751" here, "750" in the header's Universe and "752" in Configuration's index files. Each is right by its own count (members today / ranked / rows incl. placeholder), but no page says why they differ |
| G4 | "The score" h2 with four h3s: "Windows are calendar months"; "Return over volatility, per window" (pre formula); "Ranked against the other stocks" (pre score formula + paragraph); "How it differs from NSE's and MSCI's momentum indices" (+ the members-only scoring paragraph) | `#score` | Text + `<pre>` formulas | config weights, `ANCHOR_STALENESS_LIMIT`, `members_only_scoring_from` | :132-158 | Fine. Tipsheet's methods pages draw a worked example; there is none here (suggestion) |
| G5 | "Filters" h2: list Trend / Near the high + paragraph + h3s "A stock needs 30 closes before it has a 50D EMA", "A new listing waits about 6 months", "The 52-week high is read from closes" (with `basis_note` from startup metrics) | `#filters` | Text | `EMA_MIN_PRINTS`, `MIN_OBSERVATIONS`, `HIGH_52W_MIN_OBSERVATIONS`, `startup_metrics.snapshot()` | :160-184 | The "52-week high" h3 runs about 130 words; it could be shorter |
| G6 | "The book" h2: list Size / Caps / Buffer / Costs / No stops | `#book` | `<ul>` | config | :186-204 | The "Caps" item runs about 100 words |
| G7 | "Weighting" h2: Equal weight; Six-monthly reset; the test paragraph ("…monthly reset earned 15.4% a year after tax and the six-monthly 15.3%…"); Inverse volatility + `<pre>` w_i formula | `#weights` | Text + formula | config; `PortfolioOptimizer.inverse_volatility` window | :206-227 | (b): **15.4% / 15.3% are typed** (:216), dated 8 Nov, not read from the Backtest's reference file. So does "14 Oct 2021". A link to Backtest §4 would carry live figures |
| G8 | "Acting on it" h2: ordered list of four steps (open Actions; sell then buy, Kite basket import path; place on the next session; hold) | `#acting` | `<ol>` | config | :229-239 | No link to Actions (bold word only). A real `page_href("actions")` link is cheap |
| G9 | "Questions" h2: seven Q&A (after tax? ranked 14th not in the book? rank vs qualified rank; Nifty Total Market's trend; "pts"; max drawdown; costs) | `#faq` | `<dl>` | config | :241-270 | "about 22 bps" is typed (:268). There is no glossary list; tipsheet pairs a glossary with methods (S237 "Guide / glossary, methods") and `docs/GLOSSARY.md` exists, so this could be a section (suggestion) |
| G10 | Footer: only "© Paresh Patel" (no date) | – | Footer bar | `render_data_quality_footer(...)` with no `as_of`, so `when` is "" (components.py:636-640) | guide_view.py:282-286 | The Guide is the only one of the four pages with **no "Data to" line**. Configuration passes `as_of` (config_view.py:723). Fine for a method page, but it is not the same across pages |

**Guide controls**: the anchor nav only. No popovers or downloads. The footer has no date (G10).

**Guide: figures with data that the page shows poorly**: the typed test results (G7, G9), no worked example of the score, and the
751 / 750 / 752 counts not reconciled (G3).

---

## Section counts

| Page | Rows (sections and sub-sections, including shared chrome, empty states and footers) |
|---|---|
| Dashboard | 52 (D1–D51 + D4a) + 4 shared chrome |
| Actions | 25 (A0–A13 with subs A4a–b, A7.1–3, A9.1–4, A12.1–3) |
| Configuration | 28 (C0–C8 with subs) |
| Guide | 11 (G0–G10) |

## Doc conflicts to settle before the redesign

1. G4 ("Source:" under every chart, now in code) against `docs/PAGE_DESIGN.md:60` ("No source line on the page… Owner, 20 Nov: 'Let's not show source'"), `DASHBOARD_REQUIREMENTS.md` rows 28 and 41 ("sources not shown"), `ACTIONS_REQUIREMENTS.md` row 20, and the comment at dashboard_home_view.py:1359. S237 lists G4 as "decided by benchmark", so the older rows need the owner's confirmation.
2. G3 against `DASHBOARD_REQUIREMENTS.md` #8 and PAGE_DESIGN 4.2: the "month" tick-strip chart is the owner's own choice (20 Nov).
3. What the weight sliders change: config_view.py:77-79 ("ranks on every page") against guide_view.py:146-148 ("for the Screener and the Backtest").
