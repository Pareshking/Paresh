# Sectors requirements: everything agreed, in one list

Started 21 Nov 2026, before any change, from the live page that day (`src/ui/views/sector_view.py`,
`market_questions_view.py` "What is leading?"), the owner's decisions in `CHANGELOG.md` and S147, and the rules
learned on the four redesigned pages (`docs/PAGE_DESIGN.md` §2a, `docs/FIGURE_INVENTORY.md`). Checked with:

    node scripts/check_dashboard_requirements.mjs <url> docs/SECTORS_REQUIREMENTS.md

## What a reader comes with

1. Which industries and which sizes are leading the market, and which are lagging?
2. Is that lead new or lasting (one month against six; the run of months)?
3. What would change the answer?
4. Which stocks in an industry lead it, and how do they rank?
5. Where does breadth sit by industry (the leadership map)?

## From the live page (21 Nov 2026)

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 1 | "What is leading?": the answer, one sentence, what would change it | Owner 7 Nov (CHANGELOG "Sectors answers") | Top | What is leading? + What would change the answer |
| 2 | By size: each NSE size index against the market, 6 months and 1 month, and all ranked stocks equal-weighted | Owner 7 Nov; S147 | Top | Nifty 50 + Midcap 150 + Smallcap 250 + Microcap 250 + equal weight |
| 3 | Industries in four groups: ahead on both, gaining, fading, behind on both, each with 6M · 1M | Owner 7 Nov | Groups | Ahead on both + Gaining + Fading + Behind on both |
| 4 | Every industry as a bar for six months with a ring for the last month | Owner 7 Nov | Bars | Rings: the last month |
| 5 | Month by month: each industry against the market for 12 completed months and the month so far, its run and 12-month total, with a worked example | Owner 7 Nov | Months | Run + 12 months + For example |
| 6 | Industry leaderboard, sortable (3M median, 6M median, share passing, top-50 count), with leaders | Live page | Leaderboard | Industry leaderboard |
| 7 | Stocks in an industry: the industry's stocks in the Screener's table | Live page | Stocks | Stocks in an industry |
| 8 | Sector leadership map: one month's return against the share above an EMA (20/50/100/200), a month ago to now, 1M or 3M | Live page | Map | Sector leadership map |
| 9 | Industry or sector grouping switch (NSE industry) | Live page | Top | NSE industry |
| 10 | RRG and Sectors agree on each industry's standing: one construction for an industry and its benchmark; 100 is the benchmark | S147, owner 19-20 Nov | Whole page | Sectors |

## Rules learned on the four pages (21 Nov 2026)

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 11 | The title answers the first question; the page's name is the kicker | PAGE_DESIGN §2a | Top | Sectors |
| 12 | One source per figure: index closes from `data/benchmark_indices.csv` (and NSE's Total Market file), cut at one session | S154, S148 | By size | Microcap 250 |
| 13 | One benchmark per comparison, named the same in caption, axis and note (the map said "all ranked stocks" in its caption and "Nifty 500" on its axis, found 21 Nov) | S154 | Map, By size | Sectors |
| 14 | One count of industries everywhere (the page said 20 in the header, 19 in the answer and "at least five stocks" in the note, found 21 Nov) | S154 | Whole page | Sectors |
| 15 | The qualified rank in "Stocks in an industry" is the one on Actions and Portfolio (it read "—" for every stock, found and fixed 21 Nov) | S154 | Stocks | Qualified # |
| 16 | Charts from the site's kit where they are charts; serif headings, notes 13.5 px, long notes in two columns, "What it is" open on a wide screen | PAGE_DESIGN §2a | Whole page | Sectors |
| 17 | Data date only, no sources named; data-quality counts kept | Owner 20-21 Nov | Footer | Data to |
| 18 | Layout audit clean at 412 and 1400 px | Owner 20 Nov | Whole page | Sectors |

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

## Proposed for the next redesign (owner, 21 Nov 2026: "yes with your recommendation")

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
