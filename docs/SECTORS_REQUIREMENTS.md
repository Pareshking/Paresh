# Sectors requirements: everything agreed, in one list

Started 21 Nov 2026, before any change, from the live page that day (`src/ui/views/sector_view.py`,
`market_questions_view.py` "What is leading?"), the owner's decisions in `CHANGELOG.md` and S147, and the rules
learned on the four redesigned pages (`docs/PAGE_DESIGN.md` §2a, `docs/FIGURE_INVENTORY.md`). Checked with:

    node scripts/check_dashboard_requirements.mjs <url> docs/SECTORS_REQUIREMENTS.md

**Status, 21 Nov 2026:** the makeover is **approved** (owner: "Sector and Backtest approved", mock-up v2) and
**built**. The rows the check reads are "The approved rows" in the makeover section below (1-21, with the `Order:`
line). The rows of the page before the makeover are kept for the record as "was 1"-"was 18", which the check does not
read; "The live rows, one by one" says what became of each.

## What a reader comes with

1. Which industries and which sizes are leading the market, and which are lagging?
2. Is that lead new or lasting (one month against six; the run of months)?
3. What would change the answer?
4. Which stocks in an industry lead it, and how do they rank?
5. Where does breadth sit by industry (the leadership map)?

## The page before the makeover (21 Nov 2026; replaced, see "The live rows, one by one")

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| was 1 | "What is leading?": the answer, one sentence, what would change it | Owner 7 Nov (CHANGELOG "Sectors answers") | Top | What is leading? + What would change the answer |
| was 2 | By size: each NSE size index against the market, 6 months and 1 month, and all ranked stocks equal-weighted | Owner 7 Nov; S147 | Top | Nifty 50 + Midcap 150 + Smallcap 250 + Microcap 250 + equal weight |
| was 3 | Industries in four groups: ahead on both, gaining, fading, behind on both, each with 6M · 1M | Owner 7 Nov | Groups | Ahead on both + Gaining + Fading + Behind on both |
| was 4 | Every industry as a bar for six months with a ring for the last month | Owner 7 Nov | Bars | Rings: the last month |
| was 5 | Month by month: each industry against the market for 12 completed months and the month so far, its run and 12-month total, with a worked example | Owner 7 Nov | Months | Run + 12 months + For example |
| was 6 | Industry leaderboard, sortable (3M median, 6M median, share passing, top-50 count), with leaders | Live page | Leaderboard | Industry leaderboard |
| was 7 | Stocks in an industry: the industry's stocks in the Screener's table | Live page | Stocks | Stocks in an industry |
| was 8 | Sector leadership map: one month's return against the share above an EMA (20/50/100/200), a month ago to now, 1M or 3M | Live page | Map | Sector leadership map |
| was 9 | Industry or sector grouping switch (NSE industry) | Live page | Top | NSE industry |
| was 10 | RRG and Sectors agree on each industry's standing: one construction for an industry and its benchmark; 100 is the benchmark | S147, owner 19-20 Nov | Whole page | Sectors |

## Rules learned on the four pages (21 Nov 2026; carried into the approved rows)

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| was 11 | The title answers the first question; the page's name is the kicker | PAGE_DESIGN §2a | Top | Sectors |
| was 12 | One source per figure: index closes from `data/benchmark_indices.csv` (and NSE's Total Market file), cut at one session | S154, S148 | By size | Microcap 250 |
| was 13 | One benchmark per comparison, named the same in caption, axis and note (the map said "all ranked stocks" in its caption and "Nifty 500" on its axis, found 21 Nov) | S154 | Map, By size | Sectors |
| was 14 | One count of industries everywhere (the page said 20 in the header, 19 in the answer and "at least five stocks" in the note, found 21 Nov) | S154 | Whole page | Sectors |
| was 15 | The qualified rank in "Stocks in an industry" is the one on Actions and Portfolio (it read "—" for every stock, found and fixed 21 Nov) | S154 | Stocks | Qualified # |
| was 16 | Charts from the site's kit where they are charts; serif headings, notes 13.5 px, long notes in two columns, "What it is" open on a wide screen | PAGE_DESIGN §2a | Whole page | Sectors |
| was 17 | Data date only, no sources named; data-quality counts kept | Owner 20-21 Nov | Footer | Data to |
| was 18 | Layout audit clean at 412 and 1400 px | Owner 20 Nov | Whole page | Sectors |

## Decided (owner, 21 Nov 2026: "go as recommended")

- **The market for the size rows:** Nifty 50, Midcap 150, Smallcap 250 and Microcap 250 are read against Nifty
  Total Market (`market_questions_view.total_market()`: NSE's daily archive from Oct 2021 joined with
  `benchmark_indices.csv`), named in the heading; the "All ranked stocks, equal weight" row stays, as it is the
  industries' own yardstick. Moved by up to 0.5 pts against the Nifty 500 readings (Microcap 1M −10.2 → −9.8).
- **Median or average:** the four groups, bars and months keep each industry's equal-weighted average (the RRG's
  construction, S147); the leaderboard keeps the median, labelled "typical stock" in its column and note.
- **The leadership map:** one market, all ranked stocks equal-weighted, named the same in caption, axis, tooltip
  and note (the tooltip called it the Nifty 500, found 21 Nov).

## Found while checking the built page (21 Nov 2026)

- The answer sentence printed the whole market series in place of its name ("+2.2 pts against 2016-09-23
  1.000000 ... dtype: float64"): a parameter shared its name with a local series. Renamed; test
  `test_the_size_sentence_names_the_market_not_its_series`.
- Map names near the right edge were cut off on a phone ("Healthcare", "Construct…"); they now read leftward.
- The month table's "Run" and "12 months" headings sat off their right-aligned numbers (layout audit).
- No data date on the page (row 17): "Data to 20 Nov 2026. 750 stocks ranked; 0 with a price gap, 5 with a short
  history." added, as on Breadth and Actions.

## Proposed for the next redesign (owner, 21 Nov 2026: "yes with your recommendation"; rewritten as M2-M5 of the makeover proposal below)

NSE's sector indices move here from the Indices page (S170), so a reader asking "how is pharma doing?" finds
one place. Themes, strategy and broad indices stay on Indices; Breadth, Sectors and Indices stay separate pages
(not merged: about 15 sections on one page, three questions on different time scales, and the Dashboard is
already the page that summarises; a "Market" heading grouping the three in the menu is the alternative if the
menu feels long).

Numbered P1-P3 until built, so the requirements check does not read them yet; each gets a number and its marker when the redesign builds it.

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| P1 | NSE's sector indices (35 on 20 Nov, `data/reference/nse_index_groups.csv` group "Sector") with 1M, 3M, 1Y price return, distance from the 1-year high and P/E; those younger than a year last, with their launch date | Owner 21 Nov | Section | NSE's sector indices |
| P2 | Each industry's equal-weighted figure from the 750 beside NSE's cap-weighted index for the same industry, each labelled for what it measures: agreeing means a broad move, an index well ahead of the median means a few large companies carry it | My recommendation, owner 21 Nov | Section | cap-weighted + equal-weighted |
| P3 | One mapping table, industry ↔ NSE sector index, committed with its reasons (NSE's sectors are finer in places: Capital Markets, Hospitals, NBFC; some industries have none), shown to the owner before it is used | Same | Data | — |

---

# The makeover, 21 Nov 2026: proposed (v1), decided item by item, approved (v2) and built

Mock-up: `docs/mockups/sectors_v2.html` (v2, with the owner's 13 decisions; v1 `docs/mockups/sectors_v1.html` was the proposal) (desktop and phone, light and dark; real figures, closes of 20 Nov 2026).
Figures: `scripts/sectors_mockup_figures.py`, run on the ranking table and the Screener price store (the release
files `rankings.parquet` and `screener_prices.parquet`; the app reads the same from R2) and the app's committed
copy of NSE's daily index files. The map, to be read first: `docs/SECTORS_INDEX_MAP_PROPOSAL.md`.

The owner's frame (21 Nov 2026): NSE's sector indices move here from Indices (S170); themes, strategy and broad
indices stay on Indices; Breadth, Sectors and Indices are not merged; RRG is gone and Sectors carries industry
leadership (S169); the market is Nifty Total Market (S165); one name and one unit for each idea (S173); every
figure says where it comes from (S172).

## What a reader comes with (revised)

1. Which sectors are ahead of the market, and is that new or lasting?
2. Is a sector's move broad, or carried by a few large companies?
3. What do NSE's own sector indices say, beside the sector's ranked stocks?
4. How many of a sector's stocks are in an uptrend, and which stocks lead it?

Which sizes lead is the Dashboard's question ("Size, and where momentum works"); see decision C.

## P1-P3 as written, read critically

- **P1 alone is a second Indices table.** 35 rows of index returns with nothing beside them repeat the form of
  Indices' every-index table; their value here is the comparison with the sector's own stocks (P2). Proposed:
  one table, each sector's 750 figure on the first line of its own group of NSE indices (M4).
- **P1's windows are older than the owner's last word.** P1 says 1M, 3M, 1Y; later on 21 Nov the owner approved
  1M, 3M, 6M, 9M and 1Y for Indices' every-index table ("add missing months"). Proposed: the same five here.
- **P2 as written mixes in size.** Every sector's gap to its cap-weighted index contains part of the market-wide
  gap between the equal-weighted 750 and Nifty Total Market: over the three months to 20 Nov the 750 returned
  −3.9% and Total Market +2.2%, a gap of −6.1 pts, and 14 of the 16 sectors show a negative gap. Read alone, P2
  would say "a few large companies carry it" of nearly every sector. Proposed: the 750's own gap is the first row
  and a dashed line on every bar; only a gap beyond it means large companies did more of the work in that sector
  than in the market (on 20 Nov: Financials −11.7 pts and IT −8.6 pts).
- **P2's wording says "median".** The owner decided (21 Nov) that the sector figures are equal-weighted averages
  and only the leaderboard keeps the median. Proposed wording: "equal-weighted".
- **P2 is thin for five sectors today.** Nifty Capital Goods (the largest sector, 121 stocks), Construction, Power
  and Telecommunications entered NSE's daily file on 15 Jun 2026, Cement on 17 Feb 2026: no 6M or 1Y yet. Proposed:
  the gap reads 3M and 1M, which all 16 headline indices have (decision D; map question MQ1).
- **P2 compares membership as well as weighting.** An NSE sector index holds its own selection of the sector; the
  750's stocks are another. No constituent list or method could be read here (niftyindices.com refuses this
  machine), so the page says "different stocks and different weights", not only "different weights".
- **P3 is sound**, but must also say that the site's "industry" is NSE's **sector** level (22 groups), so NSE's
  finer indices (Bank, NBFC, Capital Markets, Hospitals) have no equal-weighted twin, and that two indices our
  groups file calls themes match NSE sectors (map MQ4).
- **Already redundant on the live page:** each sector's six-month and one-month figures appear twice (the four
  group lists, then the bars with rings); the size-index rows repeat the Dashboard's size table (with the Nifty 50
  where the Dashboard and Indices mean the Nifty 100 by "Large"); the leaderboard's 3M and 6M medians are a third
  reading of returns beside the equal-weighted ones.

## The approved rows (built 21 Nov 2026; the check reads them)

Numbered from the proposal's M1-M21 (row n was Mn). Rows 3 and 21 show nothing a reader can find on the default page:
3 is data, checked by `tests/test_sectors_page.py`; 21 appears only with a TradingView grouping chosen and is checked by
`tests/test_sectors_grouping_switch.py`. Their marker, "Grouping", is the control that leads to them.

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 1 | Kicker "Sectors"; the title names the sectors ahead of the 750 on both six months and one month and the two furthest behind, with the gap in pts; the lede counts the sectors ahead on both and gives the month's Nifty Total Market and 750 returns | PAGE_DESIGN §2a; live row 11 | Top | Sectors + lead the 750 |
| 2 | **Broad or narrow.** For each of the 18 sectors with a headline index (the map, MQ4 yes), the 750's stocks equal-weighted against that index over 3M, the gap as a line bar (0.5 pt a line, ±12), the 1M gap beside. First row: the 750 against Nifty Total Market, whose 3M gap is a dashed line on every bar. The note says the two differ in stocks and in weights | P2, revised | Section 2 | Broad or narrow + Gap 3M, pts + The 750 vs Total Market |
| 3 | The map, approved, committed as `data/reference/nse_sector_index_map.csv` with a reason per row; a test fails if a "Sector" index sits under no sector or under two. `nse_index_groups.csv` moves Nifty Consumer Services and Nifty Commercial & Transport Services from Theme to Sector (owner, MQ4), so they leave Indices | P3 | Data | Grouping |
| 4 | **NSE's sector indices.** Every index in the "Sector" group (37 on 20 Nov, with the two moved by MQ4), grouped under its sector in the order of section 1; the first line of each group is the sector's ranked stocks, equal-weighted; the headline index next, marked "for the sector". Columns 1M, 3M, 6M, 9M, 1Y, From 52W high, P/E (the Indices page's columns). An index younger than a year comes last in its group with "since" and its launch in the 1Y column. A sector with no index says so. On a phone names drop "Nifty" and stay on one line, pinned, while the numbers scroll | P1, with Indices' windows | Section 3 | NSE’s sector indices + for the sector + since 15 Jun 2026 |
| 5 | One-year chart for the chosen sector (chips): the 750's stocks equal-weighted (ink, with area) and the headline index (blue), both 100 a year ago or at the index's launch; crosshair, readout above the chart with both values and the gap, arrow keys, latest at rest; "Show the table" gives month-ends | PAGE_DESIGN §4.1 | Section 2 | One year, each line 100 + Show the table |
| 6 | **Which sectors lead.** One table: groups as heading rows (Ahead on both, Gaining, Fading, Behind on both, each with its count and meaning); the six-month lead over the 750 read 3M ago, 1M ago and now, now as a line bar (1 pt a line, ±20) with a triangle a month ago; the 1M lead beside. First row: the 750 against Nifty Total Market. On a phone the past readings and the 1M lead sit under the bar | Live rows 3 and 4, merged; PAGE_DESIGN §2 (3M ago, 1M ago, now), §3 (group rows) | Section 1 | Ahead on both + Gaining + Fading + Behind on both + Six-month lead |
| 7 | What would change the answer: the three nearest to moving ahead over six months and the three nearest to falling behind, in pts | Live row 1 | Section 1 | What would change the answer |
| 8 | A worked example of one lead with its own numbers, and "Describing is not forecasting" | Live page (worked examples); PAGE_DESIGN §2 | Section 1 | For example, Healthcare + Describing is not forecasting |
| 9 | Month by month as live row 5: 12 completed months and the month so far, Run, the 12 months summed, a worked example; sign colour only, no shades | Live row 5; Indices row 11 (no heat colours) | Section 4 | Month by month + 12 months, summed + so far |
| 10 | **Inside each sector**, below the leadership map (owner, item 10). The share above the 200D EMA 3M ago, 1M ago and now (2% a line, dashed 40% and 60%, triangle a month ago), then Above 50D EMA, Near 52W high, Pass both filters, In top 50, Typical stock 3M (the median), Leaders; first row all 750; sortable by any column | Live rows 6 and 8, merged | Section 5 | Inside each sector + Above 200D EMA + Typical stock, 3M + Pass both filters |
| 11 | Stocks in a sector: a picker and the Screener's table, with the qualified rank shown on Actions and Portfolio | Live rows 7 and 15 | Section 6 | Stocks in a sector + Qualified rank |
| 12 | No size-index rows; the 750 against Nifty Total Market stays as the first row of sections 1 and 2; a link to the Dashboard's "Size, and where momentum works" | Decision C; changes live row 2 | Section 1 | The 750 vs Total Market + Size, and where momentum works |
| 13 | One word for NSE's 22 groups: "sector" in every heading, label, control, note and chart on the page; the one note that explains NSE's "Industry" column and the grouping control's "TradingView industry" are the only places the other word appears | Decision B; S173 | Whole page | Which sectors lead |
| 14 | One market: "the 750" is the ranked stocks equal-weighted, "Nifty Total Market" the cap-weighted index; never "the index", "all ranked stocks" or "the market" for the 750 | S165, S173; changes live row 13 | Whole page | Nifty Total Market |
| 15 | One count: the 19 sectors with five or more ranked stocks in every section; the note names those left out (Utilities, 4; Diversified and Forest Materials, 1 each) | S154; changes live row 14 (the leaderboard showed 20) | Whole page | 19 have five or more ranked stocks |
| 16 | One source and one session: stock figures from the ranking table and the price store (R2); every index figure, Nifty Total Market included, from the app's copy of NSE's daily index files; all cut at the ranking table's session | S148, S154, decision I; changes live row 12 | Whole page | Data to |
| 17 | Units: pts for a lead or a gap (a difference of two returns), % for a return or a share; each line bar states its step; minus is U+2212 | S173; PAGE_DESIGN §8 | Whole page | 0.5 pt a line + 2% a line |
| 18 | **The grouping switch at the top**, NSE sector by default with the full page; TradingView sector and TradingView industry as the other choices. With a TradingView grouping every section built from the ranked stocks regroups (which lead, the leadership map, month by month, inside each sector, stocks in a sector); "The 750 vs Total Market" stays; the broad-or-narrow section, the NSE index table and any index column hide, with one line in their place (M21). No section ignores the switch | Owner 21 Nov, item 12 (kept); live row 9 | Top | Grouping + NSE sector + TradingView sector |
| 19 | Data date and counts at the foot; layout audit clean at 412 and 1400 px; the page stays in CI's requirements and layout step | Live rows 16-18 | Foot | Data to + stocks ranked |
| 20 | **Sector leadership map**, kept: across, the sector's 1M lead over the 750 in pts (section 1's 1M lead, the same number); up, the share of its stocks above the EMA; a hollow dot a month ago, a filled dot today, a line between; leader blue, laggard rust, the rest grey; EMA (20, 50, 100, 200 days, 200 by default) and period (1M, 3M, 1M by default) as switches; a sector picker; values under the pointer with the readout above, arrow keys, the leader at rest; on a phone only the leader, laggard and picked sector are labelled, the rest named on tap; the caption counts where breadth fell and names sectors ahead on narrow breadth; the worked example ("How to read it") with the decided names ("sector", "the 750", leads in pts, not %); "Show the table"; five or more stocks per sector, so it counts the same 19 | Owner 21 Nov, item 10 (kept); live row 8 | Section 5 | Sector leadership map + 200D EMA + Heavy lifting |
| 21 | With a TradingView grouping chosen, the page says once, where the NSE index sections were: "NSE's indices match NSE's sectors; switch to NSE sectors to see them." A test renders the page under each grouping and fails if a section built from ranked stocks keeps NSE's sectors, or if an NSE index figure shows (`tests/test_sectors_grouping_switch.py`, written in the build) | Owner 21 Nov, item 12 | Broad or narrow, NSE's sector indices | Grouping |

Order: Sectors → Which sectors lead → Broad or narrow → NSE’s sector indices → Month by month → Sector leadership map → Inside each sector → Stocks in a sector → Data to

## The live rows, one by one (nothing dropped without a decision)

| Live row | In the proposal |
|---|---|
| 1 What is leading?, what would change it | Kept: title and lede (M1), M7 |
| 2 By size | Changed: size rows go to the Dashboard (M12, decision C); the 750 row stays |
| 3 Four groups | Kept, as heading rows of one table (M6, decision F) |
| 4 Bars with rings | Merged into M6: bar now, triangle a month ago, 1M lead as a number |
| 5 Month by month | Kept (M9); shades dropped (decision H) |
| 6 Leaderboard | Merged into M10 (owner, item 10: the leaderboard merges, the map stays); its 6M median dropped, as section 1 carries six months |
| 7 Stocks in an industry | Kept, as "Stocks in a sector" (M11) |
| 8 Leadership map | Kept (owner, item 10) as M20, with its switches and worked example, renamed; sits above "Inside each sector" |
| 9 Classification switch | Kept (owner, item 12) as M18 and M21: every section regroups, the NSE index sections hide with one line |
| 10 One construction; 100 is the benchmark | Kept: every sector figure is the equal-weighted index of S147 |
| 11-18 | Kept as M1, M16, M14, M15, M11, the site's type and chart rules, M19 |

## Owner's decisions (21 Nov 2026, one item at a time)

Each item was put to the owner with a recommendation, an example and the counter-argument; the answers:

| # | Item | Decision |
|---|---|---|
| Item 1 | Pair each sector with an NSE index (A) | **Yes**, young indices included, "—" with the launch date where a window is longer than their life (MQ1) |
| Item 2 | Financial Services' headline (MQ2) | **Nifty Financial Services** |
| Item 3 | Healthcare's headline (MQ3) | **Nifty Healthcare Index** |
| Item 4 | Nifty Consumer Services, Nifty Commercial & Transport Services (MQ4) | **Moved to Sector** in `nse_index_groups.csv` and made the headline for Consumer Services and Services: 18 sectors with an index |
| Item 5 | Nifty Sugar & Ethanol (MQ5) | **Under FMCG** |
| Item 6 | Nifty Energy (MQ6) | **Under Oil & Gas** |
| Item 7 | "Sector" or "industry" (B) | **"Sector"**, on this page now, on the rest through S173 |
| Item 8 | Size rows (C) | **Dropped**, with a link to the Dashboard's size section; "The 750 vs Total Market" kept as the yardstick |
| Item 9 | The sector table (D) | **One grouped table**, Indices' windows 1M, 3M, 6M, 9M, 1Y, broad-or-narrow gap on 1M and 3M |
| Item 10 | Leadership map (E) | **Kept** (owner: "keep it"), with its worked example and the decided names ("sector", "the 750"). The leaderboard still merges into "Inside each sector" (M10), below the map |
| Item 11 | The four lists and the bars (F) | **Headings in the sector table**; the bar chart goes |
| Item 12 | TradingView switch (G) | **Kept** (owner: "keep it"). NSE sectors by default with the full page; with a TradingView grouping every section built from the ranked stocks regroups, and the NSE index columns and the gap hide with one line saying why. No section silently ignores the switch |
| Item 13 | Month table colours (H) | **Sign colour only** |

Not put to a vote: MQ7 (NSE's finer indices against the 750's own banks, NBFCs and so on) waits for each stock's basic
industry, a TODO; I (Total Market from NSE's daily files, and the collector's date fix) is a data repair, S176.

Next: mock-up v2 with items 10 and 12, shown to the owner before the build. **Done:** `docs/mockups/sectors_v2.html` (rows M1-M21 above updated to match; M13 now excepts the grouping control's TradingView labels).

## Decisions for the owner (as proposed)

- **A. The sector ↔ index map.** Recommended: approve `SECTORS_INDEX_MAP_PROPOSAL.md` with its questions MQ1-MQ7 as
  recommended there (16 headline indices; 18 if MQ4 is yes). Against: wait for NSE's methodology documents, which
  this machine cannot reach, so each match could be checked on constituents rather than on names.
- **B. "Sector" or "industry".** Recommended: "sector", NSE's own word for these 22 groups, the page's name, and the
  word in "NSE's sector indices"; on this page now, on every page through S173 (Dashboard "industry status",
  Portfolio, Actions, the Screener's column). Against: "industry" is on every page and in tests today; changing one
  page first leaves the site using both words until S173 reaches the rest.
- **C. Size rows.** Recommended: drop the four size-index rows and link to the Dashboard's size section, which shows
  the same comparison at 1M, 3M and 6M and means the Nifty 100 by "Large" (Sectors uses the Nifty 50, which the
  owner called "no benchmark at all"). Keep the 750 against Total Market: it is the yardstick the sector leads are
  read against. Against: a reader asking "which sizes lead?" on Sectors has to change page; the alternative is to
  keep them through the Dashboard's function with the Nifty 100 (PAGE_DESIGN §5.4), at the cost of a repeat.
- **D. P1 and P2 in one table, and their windows.** Recommended: one grouped table (M4) with Indices' windows (1M,
  3M, 6M, 9M, 1Y), and the broad-or-narrow gap on 3M and 1M (M2), the windows all 16 headline indices have.
  Against: P1 as written (a separate 35-row table with 1M, 3M, 1Y) is quicker to scan for one index; a 6M gap would
  match section 1 but leaves five sectors blank until Dec 2026.
- **E. Leadership map and leaderboard into one table.** Recommended: M10. The map's across axis (a month's return
  against the 750) is section 1's 1M lead, and its EMA and period switches hid figures behind taps; the shares 3M
  ago, 1M ago and now follow the page rule and match the Dashboard's "Is the rally shared?". Against: the scatter
  showed return and breadth for every sector at once, and the owner asked for its worked example (13 Oct).
- **F. Four lists and the bars into one table.** Recommended: M6, so each sector's six-month and one-month figures
  appear once, with the readings 3M and 1M ago added. Against: the four lists were the owner's 7 Nov layout and read
  faster as four short columns on a wide screen.
- **G. The TradingView switch.** Recommended: drop it; no NSE index matches TradingView's groups, "What is leading?"
  already ignores it, and two classifications on one page break "one name, one thing". Against: TradingView's finer
  groups let a reader find a small theme; that could live on the Screener as a filter instead.
- **H. Month table colours.** Recommended: sign colour only, as Indices' calendar table. Against: shades find the big
  months faster.
- **I. Nifty Total Market from one file.** `data/nse_total_market.csv` (read by `market_questions_view.total_market`)
  holds three April 2023 sessions under month-first dates: 6 Apr 2023's close 8,220.95 as 4 Jun 2023; 10 Apr's
  8,237.65 as 4 Oct 2023, replacing that day's real 9,608.10, so the series shows a false 15% one-day fall and
  rebound; and 11 Apr's 8,280.95 as 4 Nov 2023, a Saturday. NSE's daily index files in the S168 copy have all of
  them right; the two sources agree on the other 1,253 shared sessions. Recommended: read Total Market from the S168
  copy on this page, and fix `scripts/collect_nse_total_market.py` with the S168 date rule (TODO S176). No figure on
  the 20 Nov page is affected (its windows start in Nov 2025); readings over 2023 on other pages are. Against: none
  for this page.

## Names and units changed on this page (S173)

| Before (live page, 21 Nov) | After | Why |
|---|---|---|
| "industry" in the leaderboard, groups, months and stocks; "sector" in the map, its picker and caption | "sector" everywhere (decision B) | One name; NSE calls this level the sector |
| "all ranked stocks", "every ranked stock", "the market" (bars note), "the index" (map explainer: "beat the index") for the equal-weighted yardstick | "the 750", equal-weighted, said once per section | "The market" is Nifty Total Market (S165); the yardstick is not an index |
| "All ranked stocks, equal weight" | "The 750 vs Total Market" | "equal-weighted" is the word elsewhere |
| "6 months" / "1 month" (size headers), "6M · 1M, pts" (lists), "Six months … the last month" (bars) | "1M", "3M", "6M", "1Y" in headers; words in sentences | One form per place |
| "12 months" (month table column) | "12 months, summed" | It adds twelve monthly leads; it is not a 1Y return |
| "Nov 2026 MTD" | "Nov so far" | Plain words |
| Map explainer prints a lead as "+x%", and the hollow dot's lead as a % | pts | A difference of two returns is pts |
| "in points" (notes) beside "pts" (cells) | "pts" | One unit name |
| "Above 50D EMA" (header), "above 50-day EMA" (row), "200 EMA" (pills), "200-day EMA" (caption) | "50D EMA", "200D EMA", spelled out once in the note | One label |
| "Near 52W high" (header) / "within 20% of their 52-week high" (tooltip); Indices: "distance from the 1-year high" | "Near 52W high" (the filter) and "From 52W high" (the distance), on Indices too | One label per idea (a cross-page item for S173) |
| "Pass both" / "Share passing" (Rank by) | "Pass both filters" | One label |
| "Top-50 count" / "Top 50" / "in top 50" | "In top 50" | One label |
| "3M median" / "3M, typical stock" / "typical (median) stock" | "Typical stock, 3M" (the median, said in the note) | One label |
| Full NSE names in tables ("Media Entertainment & Publication"), short ones in the title and map | Short names everywhere (`industry_names.INDUSTRY_SHORT`, adding "Constr. Materials"), NSE's name in the note | Labels never wrap |
| "20 industries" (leaderboard) and "19" ("What is leading?") | 19 everywhere, the rest named | One count (live row 14) |
| Heat shades at 4 pts in the month table | Sign colour only | As Indices (decision H) |

## Where each figure comes from (S172)

| Figure | Source | R2 or committed |
|---|---|---|
| Sector leads, month by month, the 750's line in the chart, 200D EMA shares | Price store (`prices/screener`), equal-weighted by `peer_index` | R2 (release file `screener_prices.parquet` as fallback) |
| Each stock's sector | Ranking table, whose "Industry" column the nightly job takes from NSE's index lists | R2 (`snapshots/rankings`); the lists are committed files, `data/indices/ind_*list.csv` |
| Above 50D EMA, Near 52W high, Pass both filters, In top 50, Typical stock 3M, Leaders, the stock table, counts | Ranking table | R2 |
| NSE sector index returns, From 52W high, P/E, launch dates; the index side of section 2 and the chart | `data/nse_indices_history.parquet` + `data/nse_indices_recent.csv` | **Committed** (the app's copy of the R2 store `indices/nse_close_all`) |
| Nifty Total Market (lede, first rows of sections 1 and 2) | Today `data/nse_total_market.csv` + `data/benchmark_indices.csv`; proposed the S168 copy above | **Committed** |
| Size-index rows (live page only; decision C) | `data/benchmark_indices.csv` | **Committed** |
| Which index is a sector index; the map | `data/reference/nse_index_groups.csv`; proposed `data/reference/nse_sector_index_map.csv` | Committed reference tables (stay in git under S172) |

## Checks run for the mock-up (closes of 20 Nov 2026)

- One session: the price store, the ranking table, NSE's index files and Total Market all end on 20 Nov 2026.
- The script's six-month and one-month leads equal `market_questions.leaders_answer` (the live page's function) to
  0.1 pt for all 19 sectors; it stops if one differs. This checks the script against the page, not the data.
- All 35 sector indices sit under exactly one sector; the script stops otherwise.
- Total Market: the two committed sources agree on 1,253 of 1,256 shared sessions; the three that differ are the
  April 2023 month-first dates (decision I). Nifty 50, Midcap 150, Smallcap 250 and Microcap 250 in
  `benchmark_indices.csv` equal the S168 copy on every shared session.
- The 750's month: +2.0% equal-weighted against Total Market's +8.8%, a gap of −6.8 pts; all 16 headline indices
  beat their sector's stocks over the month.
- Mock-up measured in Chromium at 412 and 1400 px, light and dark: no sideways page scroll, no row label over two
  lines, line-bar tracks at most 340 px (160 px on a phone). The repository's `layout_audit.mjs` waits for the
  app's own page markers, so it was not run on the static file.

**Not checked:** any sector index against a second source (niftyindices.com refuses this machine; no ETF on a sector
index is in the price store); any index's constituents or method, so how much of a section 2 gap is membership
rather than weighting; launch dates against NSE's press releases; each stock's sector against a source other than
NSE's own lists. The month table and the EMA shares use today's 750 and today's sectors (not point-in-time), and say
so.
