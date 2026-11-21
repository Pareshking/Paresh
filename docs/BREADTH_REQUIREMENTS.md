# Breadth requirements: everything agreed, in one list

Started 21 Nov 2026, before any change, from the live page that day
(`src/ui/views/breadth_view.py`, `market_questions_view.py`), the owner's decisions in
`CHANGELOG.md` (dated below), and the rules learned on Dashboard, Portfolio and Actions
(`docs/PAGE_DESIGN.md` §2a, `docs/FIGURE_INVENTORY.md`). Checked with:

    node scripts/check_dashboard_requirements.mjs <url> docs/BREADTH_REQUIREMENTS.md

A row is changed or dropped only with the owner's word. The `Order:` line is added when
the owner approves the section order.

## What a reader comes with

1. Are most stocks taking part, or is a handful carrying the index?
2. Is the market in an uptrend?
3. In which sizes is it broad or narrow?
4. What changed this month, and what would change the answer?
5. Which stocks are making new highs and new lows?

## From the live page (21 Nov 2026)

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 1 | Two questions, each with a verdict word, one sentence, and a scale marking today, a month ago and a year ago | Owner 7 Nov ("tipsheet's question pages as the model") | Top | Are most stocks taking part? + Is the market in an uptrend? + A month ago + A year ago |
| 2 | What has changed this month, and what would change the answer (the measure, the reading it needs) | Owner 7 Nov | Each question | What has changed + What would change the answer |
| 3 | The evidence: each measure with its cut-offs written out, where today sits in its own history (percentile, middle half), a year ago, and its vote; primary measures count twice | Owner 7 Nov (CHANGELOG "Editorial type") | Each question | The evidence + percentile + Primary |
| 4 | Breadth counted over the members of each date, leavers included, from NSE's first recorded list (29 Oct 2021), said on the page | S150, owner 20 Nov | Note | leavers |
| 5 | Behind each answer, its chart: the index above the share of stocks above their 200D EMA; net new 52W highs week by week; the Nifty 500 against its 10-month average | Owner 7 Nov (CHANGELOG "the charts behind each answer") | Each question | Behind the answer |
| 6 | Net new 52W highs count each stock once in a week | Fixed 7 Nov | Chart | each counted once |
| 7 | By size: Nifty 500, Nifty 50, Midcap 150, Smallcap 250, Microcap 250 against their 10-month average, 200D EMA and 52W high, a month ago and now | Owner 7 Nov | Uptrend | Nifty 50 + Midcap 150 + Smallcap 250 + Microcap 250 |
| 8 | Today's charts: participation above each average (3M, 6M, 1Y; EMA or SMA; 10D to 200D), by index, new highs against new lows | Live page | Charts | Participation + New highs against new lows |
| 9 | The stocks making new highs and lows in the last 20 sessions, filterable | Live page | End | Stocks making new highs and lows + Highs + Lows |
| 10 | No forward returns or outcome claims unless tested (the S150 rule) | Owner 7 Nov; S150 | Whole page | Breadth |

## Rules learned on the three pages (21 Nov 2026), that Breadth must honour

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 11 | The title answers the first question; the page's name is the kicker | PAGE_DESIGN §2a | Top | Breadth |
| 12 | One source per figure: index closes from `data/benchmark_indices.csv`, the file the Dashboard reads (the live page reads R2 for "By size" and showed only the Nifty 500 row where R2 was not reachable, found 21 Nov) | S154, S148 | By size | Microcap 250 |
| 13 | Every figure ends on the page's session or reads "—"; a series a session behind says so | S148 | Whole page | Data to |
| 14 | A figure the Dashboard also shows (share above the 200D EMA, breadth by size) has the same value on both pages, from one function | S154 | Whole page | 200D EMA |
| 15 | Charts from the site's chart kit: values in the pane headings, readable on a phone, usual range shaded where the history is long; axis figures without needless decimals ("24000.00") | PAGE_DESIGN §4, §2a | Charts | Breadth |
| 16 | Serif headings and tile figures, notes 13.5 px, long notes in two columns on a wide screen, "What it is" open on a wide screen | PAGE_DESIGN §2a | Whole page | Breadth |
| 17 | Data date only, no sources named on the page; the data-quality counts kept | Owner 20, 21 Nov | Footer | Data to |
| 18 | Layout audit clean at 412 and 1400 px; numbers right-aligned under right-aligned headings | Owner 20 Nov | Whole page | Breadth |
| 19 | "Ahead of the market" over a year and the median stock against it read Nifty Total Market, named on the page | Owner 21 Nov ("Yes") | Breadth question | ahead of Nifty Total Market |

## Decided (owner, 21 Nov 2026: "go as recommended")

- **Overlap with the Dashboard:** the Dashboard keeps its short versions; this page is the full reading.
- **Today's charts:** the 50D and 200D EMA participation lines count the members of each date (history to its
  last date, today's count after it); the other averages count today's ranked stocks, said in each line's name.
- **Benchmark (owner, 21 Nov 2026: "Yes", Total Market with the shorter history):** "Stocks ahead of the market
  over a year" and "Median stock less the market" read Nifty Total Market, daily from NSE's archive
  (`data/nse_total_market.csv`, `scripts/collect_nse_total_market.py`, checked against `benchmark_indices.csv`);
  their history starts Nov 2022, a year after Total Market's first session. The trend rules keep the Nifty 500
  (history from 2000); the signal tests' Nifty 500 universe keeps the Nifty 500.

## Figures that also appear on another page

| Figure | Also on | Made by | Same function? |
|---|---|---|---|
| Share above the 200D EMA (now, a month ago) | Dashboard (At a glance, section 5) | `pit_breadth.splice(mq._share_above_ema)`; the chart is the Dashboard's `_breadth_spec` | Yes: 47% on both, 21 Nov |
| Share above the 50D EMA | Header strip, Dashboard | header 366 of 750 = 49%; Breadth 49% (21% a month ago), Dashboard 49% (21% a month ago) | Yes, 21 Nov |
| Near 52W high | Header strip | header count | Not on the page body |
| Size indices against their 200D EMA / 52W high | Dashboard section 5 (size against the market) | `data/benchmark_indices.csv` on both, cut at one session (`dashboard_insights.as_of`) | Yes, since 21 Nov |
