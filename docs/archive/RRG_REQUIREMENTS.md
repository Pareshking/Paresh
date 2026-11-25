# RRG requirements: everything agreed, in one list

> **Superseded, 21 Nov 2026: the RRG page was removed (S169, #587).** Kept as the record of what
> was agreed; nothing below is built or checked any more. Why (owner, 21 Nov: "How about we remove
> the RRG instead? And must focus our energy on sector page"): the JdK formula is not published,
> and our reconstruction put NSE's sector indices in StockCharts' quadrant on 35% of index-weeks
> (25% by chance); it also read 10 of 19 industries differently from Sectors
> (`docs/archive/RRG_ANALYSIS_2026-11-21.md`). What went: `src/ui/views/rrg_view.py`, `compute_rrg_data`,
> the menu entry, the Guide's rotation-graph section, the Dashboard's section 7 and the quadrant
> badges on its section 6 (`docs/DASHBOARD_REQUIREMENTS.md`, rows 34-36 dropped). Industry
> leadership is on Sectors. `/rrg` is not redirected (owner: "not required"): it is neither a page
> nor a moved address in `app.py` (`_PAGES`, `_MOVED`). No CI step reads this list.

Started 21 Nov 2026, before any change, from four places: every item on the live RRG page that
day (`src/ui/views/rrg_view.py`, `src/ui/charts.py` `render_rrg_chart`), the owner's decisions
about RRG recorded in `CHANGELOG.md` (dated below), the rules learned on Dashboard, Portfolio,
Actions, Breadth, Sectors and Screener (`docs/PAGE_DESIGN.md`), and the data and method check
`docs/archive/RRG_ANALYSIS_2026-11-21.md`. Checked with:

    node scripts/check_dashboard_requirements.mjs <url> docs/archive/RRG_REQUIREMENTS.md

Each row's **Marker** is text that must appear on the rendered page (see
`docs/ACTIONS_REQUIREMENTS.md` for the syntax: ` + ` joins texts that must all appear, `\|`
separates alternatives, `[click X]` reads the page after tapping X). A row is changed or dropped
only with the owner's word. The `Order:` line is added when the owner approves the section order.

Rows 1-15 hold on the live page today (checked 21 Nov: 15 of 15). Row 16 is a live item that does
not show. Rows 17 onwards are what the redesign must add; most fail until it is built, and a few
(22, 28, 35) pass on text the live page already has, so for them the layout audit and the tests are
the check. Rows marked **(D1)** follow the owner's decision D1 below and are
written for the recommended option (c); under option (b) they are rewritten before the mock-up.

Scope: `/rrg`. The Dashboard's section 7 and its strong/weak cards read the same function
(`compute_rrg_data`); any change here is re-checked there with `docs/DASHBOARD_REQUIREMENTS.md`.

## What a reader comes with

1. Which industries are gaining on the market now, and which are losing ground?
2. Which are turning: improving from behind, or rolling over from ahead, and since when?
3. Where do the book's industries sit?
4. Can I trust it: does it agree with Sectors and with a published RRG, and what is it built from?
5. Has a quadrant meant anything for the next month? (Not tested; the page says so.)

## From the live page (21 Nov 2026)

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 1 | The page names what is compared with what ("Industries against all ranked stocks, equal-weighted") | Live page; CHANGELOG 20 Nov ("Industries are compared with the stocks they compete with") | Top | Relative rotation + against |
| 2 | Three scopes: industries, top stocks, TradingView sectors | Live page | Top | Industries + Top stocks + TV sectors |
| 3 | Settings: benchmark, timeframe, tail, lookback, an as-of date over the last 120 sessions | Live page | Chart settings | [click Chart settings] Benchmark + [click Chart settings] Lookback + [click Chart settings] As of |
| 4 | The settings and the date drawn are stated over the chart ("Weekly · tail 6w · lookback 12w · 20 Nov 2026") | Live page | Over the chart | lookback + tail |
| 5 | One tap shows the top of a quadrant (up to 8); the chart opens on Leading, or the six strongest when Leading is empty | Live page | Chart | Leading + Improving + Weakening + Lagging |
| 6 | Each shown name is a chip that removes it; "+ Add" searches every name; "Clear" | Live page | Chart | + Add + Clear |
| 7 | Tails, the four quadrants, tap a dot to isolate it; on a phone the chart is 760 px wide and opens on the 100 / 100 crossing, swiped sideways, vertical swipes scroll the page | Owner 15 Oct ("larger chart, I will slide the page") | Chart | Tap a dot |
| 8 | Every name listed by quadrant, strongest first, with both figures and a count per quadrant | Live page; CHANGELOG 7 Nov ("Screen readers: tables and charts") | Lists | Quadrants + RS · Momentum |
| 9 | Export the figures as CSV | Live page | Lists | Export CSV |
| 10 | Top stocks link to their stock page | Live page | Lists | Top stocks |
| 11 | Quadrant words plain, no emoji, no tinted cards | Owner 7 Nov ("No emoji in tables"; "No repeated blocks") | Lists | Leading |
| 12 | "Leading" is the rotation chart's word; Sectors and the Dashboard do not use it for another measure | CHANGELOG 7 Nov ("Names, Actions, emoji") | Whole page | Leading |
| 13 | Default benchmark: every ranked stock, equal-weighted and rebalanced daily, the industries' own construction; the Nifty indices stay as choices | Owner 20 Nov (S147 (b), "approved") | Settings, subtitle | all ranked stocks |
| 14 | 100 is the benchmark line on both axes; the cross-section does not set the centre | Owner 20 Nov (S147 (a)); CHANGELOG 20 Nov | Chart | Leading |
| 15 | Industries need two or more ranked stocks | Live page | Chart | Industries |
| 16 | The data-quality counts (price gaps, short history), with the data date. The live page calls `render_data_quality_footer`, but no count is in its text on 21 Nov, so this row fails today | Owner 8 Nov | Foot | short history + Data to |

## Rules learned on the redesigned pages that RRG must honour

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 17 | The title answers the first question ("Media, Textiles and Services gain on the market; IT and Telecom have turned down."); "Relative rotation" is the small kicker | PAGE_DESIGN §2a | Top | Relative rotation + on the market |
| 18 | One verdict paragraph first; section headings are sentences that state the finding, in the serif | PAGE_DESIGN §2, §2a | Top, sections | gaining on the market |
| 19 | Readings that move show 3 months ago, 1 month ago and now side by side, as numbers | PAGE_DESIGN §2 (owner 20 Nov) | Lists | 3M ago + 1M ago |
| 20 | The book's industries filled on the chart and sized by holdings, with their weight in the lists | PAGE_DESIGN §4.3 | Chart, lists | Held |
| 21 | Values under the pointer, a readout above the chart on touch, the latest values at rest, arrow keys move it | PAGE_DESIGN §4.1 | Chart | Latest |
| 22 | Quadrant colours one meaning everywhere: Leading and Improving blue, Weakening amber, Lagging rust, the same in chart, lists and the Dashboard | PAGE_DESIGN §8 | Whole page | Weakening |
| 23 | Short industry names from the one map (`src/ui/industry_names.py`), NSE's full name in the tooltip | Screener decision 21 Nov; PAGE_DESIGN §8 | Chart, lists | FMCG |
| 24 | No internal names ("peer index", "Sector Indices" for industries); true minus signs; "pts" for points | PAGE_DESIGN §2, §8 | Whole page | pts |
| 25 | "Describing is not forecasting": no claim about next month unless a signal test passes (§5.6) | PAGE_DESIGN §2, §5.6 | Note | not forecasting |
| 26 | "What it is · how to read it" in plain sight on a wide screen, folded on a phone | PAGE_DESIGN §2a | Under the chart | What it is |
| 27 | Data date only at the foot, with the counts; no source named | Owner 20, 21 Nov | Foot | Data to |
| 28 | Layout audit clean at 412 and 1400 px (`scripts/layout_audit.mjs`), and the page joins the CI step | Owner 20 Nov; PAGE_DESIGN §8 | Whole page | Relative rotation |

## Fixes from the data and method check (21 Nov 2026)

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 29 | **(D1)** One reading of an industry across the site: the chart's two axes are Sectors' figures, the industry's return less all ranked stocks' over six months (across) and one month (up), in pts, from `peer_index`; RRG and Sectors put every industry in the same group, and a test checks every industry, not two | S147 (b) reopened 21 Nov; analysis §4.2 (10 of 19 differed) | Chart, lists | six months + one month |
| 30 | The axis words say what is measured; nothing says "ahead of the benchmark" unless the figure is a return gap over a stated window (IT, Consumer Services, Telecom read right of 100 while behind over 12 weeks, 20 Nov) | Analysis §4.1 | Chart, settings | ahead of all ranked stocks |
| 31 | Sectors and RRG each say in one line how their reading relates to the other's, and link to it | S147; PAGE_DESIGN §2 (link, do not repeat) | Note | on Sectors |
| 32 | No JdK, ® or "RRG Research" claim; a note that published RRGs use a licensed formula and can place an industry differently (ours matched StockCharts' India RRG on 35 of 101 index-weeks) | Analysis §2, §3.2 | Note | licensed formula |
| 33 | The tail's points are each week's last session (Friday, or the last session before a holiday), the current point is the data date, labelled "week to date" on a mid-week session; the vertical figure is measured from the same points | Analysis §4.4 (tail on Mondays and 8 Nov, last step 4 sessions) | Chart | weekly closes |
| 34 | Figures are plain pts, not scaled by the industries on the chart, so a reading compares across days, scopes and the Dashboard (Textiles 107.1 with all 20, 112.2 without two) | Analysis §4.6 | Lists | pts |
| 35 | No "Daily" setting that redraws the same across-axis; a tail is stated in weeks | Analysis §4.7 | Settings | tail |
| 36 | One line: industries are NSE's classification, each an equal-weighted index of its ranked stocks, not NSE's sector indices (Financial Services −1.5% vs Nifty Financial Services +10.2% over 3 months to 20 Nov) | Analysis §3.3; S166 item 8 | Note | not NSE's sector indices |
| 37 | The as-of view and the tail say that members and classification are today's (or are made point-in-time) | PAGE_DESIGN §5.1; analysis §4.10 | Note | today's members |
| 38 | A test pins the tail dates on a Friday and on a mid-week fixture, and that the last point is the page's session | S164; staleness audit "CANNOT TELL" row | Tests | Data to |

## From the TODO list

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 39 | S147 closed only when its "done when" holds: every industry's reading is one reading on RRG and Sectors (row 29), or both pages state why they differ (option (b)); the row's tick is corrected in `docs/TODO.md` | TODO S147, reopened 21 Nov | Both pages | on Sectors |
| 40 | One source per index series: the Nifty choices read `data/benchmark_indices.csv` through the loader the other pages use, not `fetch_benchmark_history` on `data/benchmarks.csv` (both equal NSE's archive on all 552 shared sessions, checked 21 Nov) | TODO S154 | Settings | Nifty Total Market |
| 41 | The index benchmark offered is Nifty Total Market, named; the Nifty 500 only where the owner keeps it, with its reason on the page | TODO S165 | Settings | Nifty Total Market |
| 42 | Every point ends on the page's session or says why not | TODO S164 | Chart, lists | Data to |
| 43 | The method page or note states that industries are equal-weighted against an equal-weighted market, and why (S147), for the S166 methods review | TODO S166 item 8 | Note | equal-weighted index of its |

## Data checks run on 21 Nov 2026 (closes of 20 Nov)

- **Reproduced.** `compute_rrg_data` on the app's own frames gives every figure on the page (Media
  118.04 · 105.86; page 118.0 · 105.9). Sectors' "What is leading?" likewise.
- **RRG against Sectors.** 9 of 19 industries agree, 10 differ (FMCG, Construction Materials,
  Consumer Durables, Power, Construction, Healthcare, Oil Gas, IT, Consumer Services, Telecom);
  Utilities (4 stocks) is not on Sectors. All 10 are window and smoothing; construction is the same
  (Sectors' figures on the RRG's frame move ≤0.05 pts; the two markets differ ≤0.03% a day).
- **Against the licensed RRG.** Our method on NSE's sector indices (NSE's `ind_close_all` files)
  against the Nifty 500: 35 of 101 index-weeks in StockCharts' quadrant over seven "Week Ahead" notes
  (Feb to 14 Nov 2026); RS-Ratio side 74%, momentum side 55%. Two open reimplementations: 36 of 101.
- **Construction.** Our industries against NSE's matching index: 3-month correlation 0.29 to 0.98
  (14 of 18 at 0.77 or more), 3-month gaps +1.5 to −11.6 pts. All ranked stocks against Nifty500 Equal
  Weight: correlation 0.98, −0.3 pts over 3 months.
- **Benchmarks.** `data/benchmarks.csv` (Nifty 500, Nifty 50) and `data/nse_total_market.csv` equal
  NSE's archive on every shared session (552 and 549).
- **Dates.** Every point ends 20 Nov; the tail starts 9 Oct; no week is dropped.
- **This list against the live page** (local run of `6981beb`, 21 Nov): 19 of 44 checks met, rows 1-15,
  22, 28, 35 and the order (no Order line yet).
- **Not checked:** the deployed site and R2 (release files served this run); the page at 412 px and in
  dark theme; Top stocks and TV sectors scopes in a browser; survivorship in the tail; any signal test.

## Decisions for the owner (recommendation first)

- **D1. One reading or two (S147).** Recommended **(c)**: the chart draws Sectors' six-month and
  one-month figures with weekly tails, so the pages agree by construction and any point can be checked
  on a price chart; Sectors links here instead of repeating it. Second choice **(b)**: keep the JdK-style
  reconstruction with rows 30, 32-35 and a stated reason on both pages, each industry's plain 12-week
  and 1-week figures beside its point. Not recommended: forcing the reconstruction's windows to match.
- **D2. Default benchmark.** Recommended: all ranked stocks, equal-weighted (S147), named; Nifty Total
  Market as the index choice (S165), with one sentence that against it most equal-weighted industries
  read behind (17 of 20 on 20 Nov). Drop Nifty 50 unless wanted.
- **D3. Name.** Recommended: "Relative rotation"; no ®, no JdK.
- **D4. Scopes.** Recommended: Industries and Top stocks; TradingView sectors only if the owner wants
  a second taxonomy here (Sectors already offers it).
- **D5. Daily setting.** Recommended: remove it (row 35).
