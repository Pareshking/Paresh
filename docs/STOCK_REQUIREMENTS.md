# Stock page requirements: everything agreed, in one list

Started 21 Nov 2026, before any change, from three places: every item on the live stock
page that day (`src/ui/views/stock_view.py`, with `src/ui/charts.render_stock_chart` and the
Screener table it borrows for peers), the owner's decisions about the stock page recorded
in `CHANGELOG.md`, `docs/TODO.md` and the git log (dated below), and the rules learned on
the redesigned pages (`docs/PAGE_DESIGN.md`). Checked with:

    node scripts/check_dashboard_requirements.mjs <url> docs/STOCK_REQUIREMENTS.md

Each row's **Marker** is text that must appear on the rendered page (see
`docs/ACTIONS_REQUIREMENTS.md` for the syntax). A row is changed or dropped only with the
owner's word. Rows 22-46 were proposed with the mock-ups and approved with mock-up v2 (owner,
23 Nov 2026: "Stock v2 approved"). Built in S182 (f); CI reads the list on
`/stock?stock=SANSERA`, with `scripts/layout_audit.mjs` at 412 and 1400 px and
`scripts/chart_hover_audit.mjs` for row 48.

Order: 1 · Rank → 2 · Filters and sell rules → 3 · Returns and falls → 4 · Price → 5 · Sector → 6 · Data → Data to

Scope: `/?stock=SYMBOL`, a route of the Screener view (`ranking_view.py:272`), for every
system (750, > ₹2,000 Cr, Combined). The Screener list itself is `SCREENER_REQUIREMENTS.md`.
Owner, 22 Nov 2026: "Stock page and Watchlist first" (TODO S174); one of the three
data-heavy pages that S151 counts.

## What a reader comes with

1. Where does this stock stand: its rank of 750, its place among the qualified, and is it
   inside the book's lines (buys the top 20 qualified, keeps to the 40th)?
2. Does the model book hold it, and how far is it from each sell rule before the next
   month-end check?
3. Is the move real: returns against the market over each window, and the falls it took on
   the way?
4. Where does the price sit: its 52-week range, its 50D EMA and the −20% line, and how far
   a fall would have to go to fail a filter?
5. Can I trust the figures: corporate actions, gaps, short history, one date, and how it
   compares with the rest of its industry?

## From the live page (21 Nov 2026)

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 1 | Back to the page the reader came from; stock links open the stock page directly | CHANGELOG 7 Nov 2026 ("Stock links open the stock page directly, so Back returns to the page you came from"); Screener filters kept in the address (7 Nov) | Toolbar | Back to screener |
| 2 | Watchlist star: add or remove, kept in this browser | Live page (`watchlist_store.toggle`) | Toolbar | Add to watchlist\|In watchlist |
| 3 | Share gives the short public link `/?stock=SYMBOL` | Owner 20 Nov 2026: "Let's not change the url, happy with slow loading" (commit 4d3754d, #569, reverting #568) | Toolbar | Share |
| 4 | A link to the stock on TradingView, in a new tab | Live page | Toolbar | TradingView |
| 5 | Company name, symbol, index membership by exact tag (a MID150 stock never gets a Nifty 50 badge), industry | Live page; the exact-tag fix in `_render_identity` | Top | SANSERA\|Stock |
| 6 | Price with paise and its close date; market cap in Cr | CHANGELOG 7 Nov ("Share prices carry paise everywhere ... every level on the stock page (₹2,340.00, 52W high ₹2,406.00)") | Top | ₹ + 20 Nov |
| 7 | Name, price and rank in Source Serif 4 | CHANGELOG 7 Nov ("Editorial type on every page": "the stock page's name, price and rank ... are in Source Serif 4"); THEME.md (`--fs-44`) | Top | Rank of 750 |
| 8 | Rank of all ranked stocks, with where it stood before and the score; horizons scored | Live page; CHANGELOG 7 Oct (S23: "the stock page's past ranks (-2M, -3M, -6M)") | Rank | Score + horizons scored |
| 9 | Passes both filters, one or neither, and by how much: distance to the 50D EMA, distance to the 52W high (with its date); the all-time high | Live page; names: CHANGELOG 7 Nov ("From 52W high" for the distance, "Near 52W high" for the filter), 12 Oct ("52W high and 50D EMA in labels"); the 52W high from day closes (owner 10 Nov, DATA_CORRECTNESS §5) and only after 126 sessions (S3, owner 13 Oct) | Filters | 50D EMA + 52W high |
| 10 | If you hold it: Sell, Watch or Clear against the three sell rules, from the function Actions and the Dashboard use (`exit_watch.assess`), with a link to Actions | Live page | Filters | Actions → |
| 11 | A corporate action in the price history is named, with the note that history before it is rescaled | Live page (`corporate_actions.load_events`); DATA_CORRECTNESS §4 for the rules | Data | split\|bonus\|rights\|demerger |
| 12 | Price chart in rupees with paise, the 50D EMA, and relative strength against the market beneath | CHANGELOG 7 Nov ("The stock chart's price axis and legend read in rupees with paise"); 1 Oct and 10 Nov (Lightweight Charts, `src/ui/lw_chart.py`) | Price | 50D EMA |
| 13 | Where the price sits: 52W low, the −20% line, 50D EMA, 52W high on one track | Live page (`_render_price_ladder`) | Filters | 52W low + −20% line |
| 14 | Returns and falls by window (1, 3, 6, 9, 12 months), against the market and the typical stock, with Sharpe | Live page (`_render_gain_vs_pain`) | Returns | 12M + Sharpe |
| 15 | Sharpe is the window's, as the ranking scores it, not annualised, and says so | CHANGELOG 12 Oct ("Wrong statements fixed: the stock page called its Sharpe annualised") | Returns | not annualised |
| 16 | True minus signs; a value that rounds to zero is not "−0.0%" | CHANGELOG 10 Nov ("the stock page used an ASCII hyphen where the rest of the site uses a true minus"; `src/ui/formats.py`) | Whole page | − |
| 17 | On a phone, return and fall figures stay inside their cells | CHANGELOG 9 Nov | Returns | [phone] 12M |
| 18 | The industry's best-ranked stocks in the Screener's columns, this stock marked | Live page (`_render_peers`) | Industry | this stock |
| 19 | Data checks for the stock: gap-filled prices, data gaps, a carried price, short history, all-time-high basis, horizons scored | Live page (`_render_data_health`) | Data | 126 sessions\|horizons |
| 20 | A stock not in the current ranking says so, with a way back | Live page (`render_stock_view`). The state cannot show on SANSERA's page, which CI reads, so the marker is the way back; the words are checked by `tests/test_stock_page_v2.py::test_a_stock_not_in_the_ranking_says_so_with_a_way_back` | Top | Back to screener |
| 21 | Works for each system; picking Combined is kept after a stock page | CHANGELOG (#242, "Combined no longer reverts after a stock page") | Whole page | Rank of |

## Rules from the redesigned pages and the data checks (approved with mock-up v2, 23 Nov 2026)

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 22 | Approved 23 Nov 2026 (mock-up v2). The title answers the first question in the serif (rank, filters, held or not); "Stock" and the symbol are the small kicker above it; a lede gives the close, its date and the year against the market | PAGE_DESIGN §2, §2a | Top | [css .kicker] Stock + passes both filters\|passes only the\|fails both filters |
| 23 | Approved 23 Nov 2026 (mock-up v2). Four tiles: close, rank of 750, place among the qualified, and (when held) the model book's return since entry; tile figures in the serif at 30 px | PAGE_DESIGN §2a | Top | Place among the qualified |
| 24 | Approved 23 Nov 2026 (mock-up v2). Section headings are sentences that state the finding, in the serif, 30 px (24 px on a phone), each ending in a full stop | PAGE_DESIGN §2, §2a, §8 | Sections | sell rules |
| 25 | Approved 23 Nov 2026 (mock-up v2). Rank trail 3M ago · 1M ago · now, as numbers in their own columns, for the rank of 750 and for the place among the qualified, read from `dashboard_insights.rank_trails` on the last session on or before each date (the Dashboard's, Portfolio's and the Screener's dates); a three-point trail with the 20th and 40th lines dashed. The 6M and 2M steps go | PAGE_DESIGN §2, §4.3, §6a; Screener decision A (21 Nov) | Rank | 3M ago + 1M ago + Now |
| 26 | Approved 23 Nov 2026 (mock-up v2). One section for filters and sell rules: the ladder, then each rule's line, the fall that reaches it, and today's state (above the 50D EMA, within 20% of the 52W high, in the top 40 of the qualified); the next check date | PAGE_DESIGN §2 (no figure twice: the verdict, ladder and exit status each repeated the 50D EMA) | Filters | Fall to reach it |
| 27 | Approved 23 Nov 2026 (mock-up v2). When the model book holds the stock, say so with shares, weight, first buy date and price, return since entry, from Portfolio's own function (`build_portfolio_tracker`), and link to Actions for the plan | PAGE_DESIGN §2 (link, do not repeat), §5.4 (same number as the owning page) | Filters | The model book holds it\|The model book does not hold it |
| 28 | Approved 23 Nov 2026 (mock-up v2). Results or corporate actions announced before the next check, from the calendar Actions reads (`data/results_calendar.csv`) | ACTIONS_REQUIREMENTS row 28 (owner 21 Nov) | Filters | board meeting |
| 29 | Approved 23 Nov 2026 (mock-up v2). The market is Nifty Total Market and is named; its return covers the same sessions as the stock's (first session on or after the date back) | S165 (owner 21 Nov: "Switch to Nifty total market indices everywhere"); data check below (the live 1M figure starts two sessions earlier than the stock's) | Returns, Price | Nifty Total Market |
| 30 | Approved 23 Nov 2026 (mock-up v2). Returns as line bars on one scale (5% a line), the market as a small triangle; the stock, the market, the lead in pts, the typical stock, the largest fall, Sharpe and the rank by return as numbers; a phone drops the last four with a note saying which | PAGE_DESIGN §4.2, §3; ACTIONS_REQUIREMENTS row 14 | Returns | One line is 5% + Lead + [phone] On a wider screen |
| 31 | Approved 23 Nov 2026 (mock-up v2). One name for the fall: "Max drawdown", as the Screener's column ("3M max drawdown") (wording per docs/GLOSSARY.md, 23 Nov 2026) | S173; Screener table | Returns | Max drawdown |
| 32 | Approved 23 Nov 2026 (mock-up v2). "Rank by return" as a place ("37th") instead of "Top 5%" | PAGE_DESIGN §3 (one figure per cell, numbers) | Returns | Rank by return |
| 33 | Approved 23 Nov 2026 (mock-up v2). Chart: price and the 50D EMA the rule uses, the stock against Nifty Total Market beneath (100 at the start of the range); 6M · 12M · 3Y; values under the pointer in each pane's heading, readout above on touch, arrow keys, latest values at rest; the 20 EMA, the 200 SMA and the 1M, 3M, All ranges go | PAGE_DESIGN §4.1, §4.3 | Price | 6M + 12M + 3Y + Against Nifty Total Market |
| 34 | Approved 23 Nov 2026 (mock-up v2). The chart's 50D EMA is the ranking's (30 prints before it exists, `EMA_MIN_PRINTS`), not `ewm(min_periods=10)` | DATA_CORRECTNESS §5 (owner 10 Nov: 30 prints) | Price | 50D EMA |
| 35 | Approved 23 Nov 2026 (mock-up v2). Volume: either dropped or labelled "shares traded, NSE and BSE" (the figure adds both exchanges). Settled by row 49 (owner 22 Nov: kept, headed "Volume", no exchange named) | Data check below; PAGE_DESIGN §5.3 | Price | Price |
| 36 | Approved 23 Nov 2026 (mock-up v2). Industry in the short names other pages use (Auto, FMCG), one classification; TradingView's sector beside NSE's industry goes | PAGE_DESIGN §8 ("one name, one thing"); SCREENER_REQUIREMENTS row 18 | Top, Industry | Auto\|FMCG\|Healthcare |
| 37 | Approved 23 Nov 2026 (mock-up v2). Industry peers: the eight best-ranked with their qualified place filled in (today it reads "Out" for every row), and a link to the Screener for the whole industry instead of a "Show all" window | Data check below; PAGE_DESIGN §2 (no "More" buttons; link to the owning page) | Industry | on the Screener |
| 38 | Approved 23 Nov 2026 (mock-up v2). Corporate actions from NSE's action list (kind, terms, ex-date, factor), not the log of large one-day moves; a stock with none says so | Data check below (MBAPL) | Data | NSE’s lists\|NSE's lists |
| 39 | Approved 23 Nov 2026 (mock-up v2). Data checks in plain sight, not in a fold | PAGE_DESIGN §2 ("Everything visible") | Data | ranked on all five horizons\|Ranked on all five horizons |
| 40 | Approved 23 Nov 2026 (mock-up v2). The Factsheet window goes: it repeated the returns table, rank and levels; stop loss and chandelier exit are not model rules (built: no Factsheet; the toolbar is Back, watchlist, Share, TradingView) | PAGE_DESIGN §2 ("no figure twice") | Toolbar | Share |
| 41 | Approved 23 Nov 2026 (mock-up v2). Sentence case everywhere: no ELIGIBLE, NOT ELIGIBLE, PASS or FAIL in capitals | PAGE_DESIGN §3, §8 | Whole page | [css .kicker] Rank |
| 42 | Approved 23 Nov 2026 (mock-up v2). Highs and lows say they are closing prices (they differ from an intraday 52-week high quoted elsewhere); the all-time high gets a line only when it differs from the 52W high | Owner 10 Nov (closing high), PAGE_DESIGN §2 | Filters | closing prices |
| 43 | Approved 23 Nov 2026 (mock-up v2). Notes 13.5 px, no line over about 80 characters, a long note in two columns on a wide screen | PAGE_DESIGN §2a | Notes | Price returns |
| 44 | Approved 23 Nov 2026 (mock-up v2). Data date at the foot, no source named | Owner 20, 21 Nov; PAGE_DESIGN §2 | Foot | Data to |
| 45 | Approved 23 Nov 2026 (mock-up v2). Every figure ends on the page's session (price, ranking, index) | S148, PAGE_DESIGN §5.3 | Whole page | Data to |
| 46 | Approved 23 Nov 2026 (mock-up v2). Layout audit clean at 412 and 1400 px; the page joins CI's step with this list | PAGE_DESIGN §7, §8 | Whole page | Rank of 750 |

## The owner's review of mock-up v1 (22 Nov 2026, ~08:35 UTC, relayed by the coordinating session)

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 47 | Today's price chart stays, with its relative-strength pane against the market beneath. It may be restyled, not left out or replaced by the mock-up's own drawing; row 33 applies to it only as restyling | Owner 22 Nov 2026: "needs current chart where RS is also there, can be re-design but not left out" | Price | Price and relative strength |
| 48 | The chart does not move on hover: the readout above it keeps one height and width at every date (one line at 412 px, tabular figures, the height of its longest reading), as #589 fixed on the live charts; a browser check fails if the chart's top moves between two hover positions, at 412 and 1400 px | Owner 22 Nov 2026: "Mock up chart is jumping so when you modify existing chart, ensure that mistake don't get repeated"; mock-up v1's readout wrapped to two lines on 28 Aug 2026 ("₹3,859.00" / "50D EMA ₹3,476.75") and not on 8 Jun 2026; #589 (CHANGELOG 21 Nov, "Charts no longer jump on hover") | Price | 50D EMA |
| 49 | The volume pane stays, headed "Volume", no exchange named on the page | Owner 22 Nov 2026: "Don't show exchange but show volume" | Price | Volume |
| 50 | No stop loss and no chandelier exit anywhere on the page; code that only they reach goes, and a test fails if either is shown | Owner 22 Nov 2026: "we don't have exit or SL so remove it" | Whole page | Rank of 750 |
| 51 | Prices, moving averages and ₹ levels in whole rupees, below ₹100 too; returns to at most one decimal (11.1%, not 11.11%); display only, exports and calculations exact; the chart readout too | Owner 22 Nov 2026: "price etc, Moving averages etc should be in round numbers, return only with Max one decimal values like 11.1% not 11.11%"; then whole rupees for all prices, below ₹100 included | Whole page | Rank of 750 |
| 52 | The owner's style sheet, through the one shared formatter (S173) and its page-scanning test: ₹ Cr without decimals; dates as "20 Nov 2026"; a true minus and an explicit + on changes; "–" for missing data with the reason in a footnote; one word per thing ("sector", "pts", "50D EMA", "Nifty Total Market"); the standard foot; weights to one decimal | Owner 22 Nov 2026, the 8-rule style sheet (relayed by the coordinating session) | Whole page | Data to |

## Data checks run on 21 Nov 2026 (prices to Fri 20 Nov 2026)

The app on this branch, opened with `?stock=` for each stock; the precomputed ranking was
accepted ("750 rows, as of 2026-11-20", price source Screener). Five stocks:

| Stock | Why | Rank · qualified | Close |
|---|---|---|---|
| SANSERA | Held by the model book since 2 Mar 2026; Smallcap 250 (the mock-up's stock) | 12 · 12th | ₹4,798.40 |
| DIVISLAB | Held; Next 50, large cap | 2 · 2nd | ₹11,180.50 |
| MBAPL | Held; Microcap 250, ₹8,954 Cr (small cap); 1:5 split ex 3 Jul 2026 | 9 · 9th | ₹195.14 |
| CONCORDBIO | 1:1 bonus ex 4 Nov 2026 (recent action); fails both filters | 591 · out | ₹548.20 |
| RELIANCE | Nifty 50, not held, passes both filters | 294 · 235th | ₹1,377.50 |

**Source 1, NSE's own files.** `sec_bhavdata_full_DDMMYYYY.csv` downloaded from
nsearchives.nseindia.com on 21 Nov for every day 1-20 Nov 2026, earlier sessions from the
committed copy of NSE's raw closes (`data/nse_prices/closes.parquet`, to 5 Nov), joined on
30 Oct (NSE's own previous close equals the committed close for all five). Adjusted with
the factors in NSE's own action list (`data/nse_prices/actions.parquet`: MBAPL ×0.2 before
3 Jul 2026, CONCORDBIO ×0.5 before 4 Nov 2026, RELIANCE ×0.5 before Oct 2024). The app
ranks on Screener's closes, so this is a second source for the levels.

- **Matched, all five, to the paisa or 0.01:** the 20 Nov close; the 52W high and its date
  (SANSERA ₹4,798.40 on 20 Nov, DIVISLAB ₹11,565.50 on 9 Nov, MBAPL ₹198.83 on Sunday 8 Nov,
  the Muhurat session; CONCORDBIO ₹793.75 on 19 Aug; RELIANCE ₹1,592.30 on 2 Jan); the 52W
  low the ladder draws (SANSERA ₹1,534.60 on 17 Nov 2025); the 1M, 3M, 6M and 12M returns
  (SANSERA +21.63%, +23.03%, +93.00%, +200.92%); the distance to the 50D EMA; and,
  recomputed from NSE's closes with the ranking's formula, all five Sharpes and all five
  largest falls of each stock.
- **All 750:** the 20 Nov close equals NSE's for 750 of 750. Over the last 252 sessions
  185,974 cells are in both; 1,158 differ by more than 0.5%, all on 9 stocks with a rights
  issue or demerger whose factor the check did not work out (OLAELEC, NATCOPHARM, HCG, HCC,
  SMLMAH rights; INDIAGLYCO, VEDL, GENUSPOWER, HINDUNILVR demergers). One worked by hand:
  SMLMAH's rights 2:7 at ₹3,506 ex 20 Nov 2026 (NSE's notice in
  `data/reference/nse/corporate_actions_recent.json`) gives a theoretical ex-rights price of
  (7 × 5,677.60 + 2 × 3,506) / 9 = ₹5,195.02, the app's adjusted 19 Nov close to the paisa.
  IRB differs by at most 0.03% (rounding).
- **NSE's file dates its own content.** For a non-session day nsearchives answers 200 with
  the previous session's file (1 Nov gave 30 Oct's, 10 Nov 9 Nov's, 15 Nov 13 Nov's), as
  DATA_CORRECTNESS §5 found for the index archive: a collector must read `DATE1`, not the
  file name.

**Source 2, BSE's bhavcopy.** 14 sessions downloaded from bseindia.com on 21 Nov (the 52W
high and low dates and every return window's first day), matched by ISIN, raw closes with
the same factors. SANSERA, DIVISLAB, RELIANCE and CONCORDBIO agree with NSE within 0.44% on
every date (largest DIVISLAB 21 Oct, ₹9,150.00 against ₹9,190.00), the usual gap between two
exchanges. **MBAPL is not on BSE** (no row for ISIN INE900L01028 or the name), so its prices
have no second exchange; Screener's close is the app's own source, not a second vote.

**Benchmarks.** Nifty 500 24,088.80 and Nifty Total Market 13,572.35 on 20 Nov equal NSE's
`ind_close_all_20112026.csv`; Total Market's closes on every window's first day (21 Oct,
20 Aug, 20 May, 20 Feb 2026, 20 Nov 2025) equal NSE's files.

**Found, for the build:**

1. **The market is the Nifty 500, on different dates.** The returns block, the chart overlay
   and relative strength use the Nifty 500 (`fetch_benchmark_history`, `^CRSLDX`), not Nifty
   Total Market (S165). And `_benchmark_returns` starts each window on the last session on
   or before the date while the stock's window starts on the first session on or after: 20
   Oct was Dussehra, so the page sets SANSERA's +21.6% (from 21 Oct) beside the Nifty 500's
   +9.3% (from 19 Oct). Over the same sessions the Nifty 500 made +10.3% and Total Market
   +9.9%. 3M to 12M fall on sessions and agree.
2. **The peers table says "Out" for every stock's qualified place**, SANSERA's included,
   under a verdict saying it passes both filters. `render_screener_table` reads "Qualified
   Rank" and the trail columns that `ranking_view` adds (`ranking_view.py:491-498`); the
   stock page passes the bare ranking.
3. **The corporate-action note reads the wrong record.** It lists the moves of 35% or more
   in `data/corporate_actions_log.json`, typed by guess. For MBAPL it tells the reader "On
   14 Nov 2020 the price moved +900.7% ... looks like a 10:1 reverse split. On 17 Nov 2020
   ... −90.0% ... a 1:10 split" (both `"source": "yahoo"`). NSE's own bhavcopies
   (`cm13NOV2020bhav.csv`, `cm14NOV2020bhav.csv`, `cm17NOV2020bhav.csv`, downloaded 21 Nov)
   show MBAPL (BE) closing ₹70.00, ₹70.05, ₹70.05: no move. MBAPL's real 1:5 split of 3 Jul
   2026 and CONCORDBIO's 1:1 bonus of 4 Nov 2026 are not in the log, so the page says
   nothing about them.
4. **Two meanings of a past rank.** The page's path reads the rank of 750 (SANSERA #50 6M,
   #16 3M, #12 2M, #13 1M); Portfolio's trail reads the qualified place (16th, 11th, 12th on
   20 Aug, 20 Oct, 20 Nov). Neither label says which. Not checked: whether the published
   ranking's `Rank (-1M)` is already read on or before the date (Screener decision A needed
   a ranking run after its merge).
5. **Volume adds two exchanges, unlabelled.** SANSERA 20 Nov: 208,200 on the chart = NSE
   199,519 + BSE 8,681.
6. **The chart's 50D EMA starts after 10 prints** (`charts.py`, `min_periods=10`), the
   ranking's after 30. Equal today for all five (SANSERA ₹4,285.85 on both); they differ for
   a stock listed under 30 sessions ago. The overlay offers a 200-day SMA where the site's
   rule is the 200D EMA.
7. **Two classifications on one line.** NSE's industry and TradingView's sector
   ("Automobile and Auto Components · Producer Manufacturing"; CONCORDBIO "Healthcare ·
   Commercial Services").
8. **"A year" two ways**, both correct: the 52W high and low are the last 252 sessions (from
   17 Nov 2025), the 12M return runs from 20 Nov 2025. The note should say so.

**One date, one source.** Price, ranking and both indices end on Fri 20 Nov 2026; the
header's date and the page's close date agree. The rank is internally consistent (rank is
the order of the score for all 750; SANSERA's qualified place, 12th, is Portfolio's now).

**Not checked:** the rank itself against an outside source (no one else publishes it; only
its inputs were checked); market caps (NSE's PR file is the app's own source); all-time
highs older than the two years NSE's committed file holds (RELIANCE ₹1,596.73 on 12 Jul
2024, CONCORDBIO ₹1,300.55 on 20 Sep 2024); dividends under 10% (kept in, by rule); NSE
closes before 30 Oct other than through the committed copy, except the BSE dates above and
MBAPL's 2020 days; the Nano Cap and Combined systems; stocks outside these five beyond the
close and the 252-session sweep.

## Mock-up v1 (21 Nov 2026), reviewed by the owner 22 Nov 2026 (rows 47-48; v2 to follow)

One responsive page with real data for SANSERA, light and dark, phone and desktop. The
PAGE_DESIGN §8 audit (Playwright, 412 and 1400 px, both themes) and
`scripts/layout_audit.mjs` (on a copy wrapped in the app's containers) are clean. Proposed
order:

1. Title, lede, tiles (rank, qualified place, held)
2. Rank: 3M · 1M · now, the rank of 750 and the qualified place, with the trail
3. Filters and sell rules: the ladder, each rule's line and the fall that reaches it, the
   model book's position, the next check
4. Returns and falls against Nifty Total Market, line bars
5. Price: price and 50D EMA, the stock against the market
6. Industry: the eight best-ranked, qualified places filled
7. Data: corporate actions from NSE's list, checks in plain sight
8. Foot: data date

## Open questions for the owner

**Settled 22 Nov 2026** (owner's answers and rules relayed by the coordinating session; B-F decided by the existing rules, which the coordinating session said are not the owner's to answer):

- **A. Volume pane:** kept, labelled "Volume", no exchange named on the page; the figure stays the total traded on NSE and BSE, recorded in `DATA_CATALOGUE.md` (owner: "Don't show exchange but show volume").
- **B. Tile figures:** in the serif at 30 px, regular weight (PAGE_DESIGN §2a, "Tile figures in the serif at 30 px").
- **C. Term:** "Largest fall from a peak", the word Backtest and Portfolio use (S173; BACKTEST_REQUIREMENTS row 30, PAGE_DESIGN §6a).
- **D. Caution colour:** #9E6300, 4.96:1 on white and 4.62:1 on the subtle ground #F7F7F5, so it passes WCAG AA for normal text; #A86A00 was 4.44:1.
- **E. Dark theme:** none in this build; THEME.md as it is (the live site is light only).
- **F. Score:** kept under the rank trail, as the live page has it.
- **G. Stop loss and chandelier exit:** removed from the page, with any code only they reach, and a test that the page no longer shows them (owner: "we don't have exit or SL so remove it").

- **A. Volume pane:** drop it, or keep it labelled "NSE and BSE"? The mock-up leaves it out.
- **B. Tile figures:** PAGE_DESIGN §2a sets them in the serif, §8 lists tiles with figures in
  Plex Mono. The mock-up follows §2a (the later rule).
- **C. "Largest fall" or "Max drawdown":** the owner chose "Max drawdown" on 12 Oct; the
  Screener now says "largest fall" and S173 is open. The mock-up uses "Largest fall".
- **D. Caution colour:** the mock-up uses the Dashboard mock-up's #A86A00 / #E3B341 (still
  waiting for the owner). #A86A00 is 4.44:1 on white, under 4.5, so it is used for marks only.
- **E. Dark theme:** the live site is light only (`theme.py`: "The owner asked for a light
  app"); the mock-up has a dark version because the redesign process asks for one.
- **F. Score:** kept as a note under the rank trail; drop it?
- **G. Stop loss and chandelier exit** leave with the Factsheet. Keep them anywhere?
