# Screener requirements: everything agreed, in one list

Started 21 Nov 2026, before any change, from three places: every item on the live
Screener that day (`src/ui/views/ranking_view.py`, `src/ui/screener_table.py`), the
owner's decisions about the Screener recorded in `CHANGELOG.md` (dated below), and the
rules learned on Dashboard, Portfolio, Actions and Breadth (`docs/PAGE_DESIGN.md`).
Checked with:

    node scripts/check_dashboard_requirements.mjs <url> docs/SCREENER_REQUIREMENTS.md

Each row's **Marker** is text that must appear on the rendered page (see
`docs/ACTIONS_REQUIREMENTS.md` for the syntax). A row is changed or dropped only with
the owner's word. The `Order:` line is added when the owner approves the section order.

Scope: the ranking list at `/screener`. The stock page (`?stock=SYMBOL`) is a route of
the same view but is its own redesign (PAGE_DESIGN §7, "Stock page").

## What a reader comes with

1. Which stocks lead the 750 today, and which of them can the book buy?
2. Where does a given stock stand: its rank, its place among the qualified, against the
   book's lines (buys the top 20 qualified, keeps to the 40th)?
3. What moved this month: who climbed, who entered and who left the top of the list?
4. Narrow the list: an index, an industry, the qualified only, the big movers.
5. Can I trust a row: a price gap, a short history, fewer horizons scored?

## From the live page (21 Nov 2026)

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 1 | Every ranked stock in one table, rank order; the first 50 shown and a button for all; a header click sorts every row | Owner 7 Nov ("Screener paging") | Table | Show all 750 + Rank |
| 2 | Search by stock (opens its page), industry, sector, sub-industry or index; options read "LAURUSLABS · Healthcare" | Owner 7 Nov; audit F36 | Toolbar | Search stock, industry or index |
| 3 | Presets with their counts: all, top 50 qualified, top 50 not qualified, pass both filters, big movers (150+ places in a month), volume spike (1.5x the 20-day average) | Owner 13 Oct, 7 Nov | Toolbar | Top 50 qualified + Top 50 not qualified + Pass both filters + Big movers + Volume spike |
| 4 | Filters: index (several), only stocks that pass both filters, columns (Executive, Core, Full Quant; Full Quant first on desktop and phone), reset; all kept in the address, so Back from a stock returns to the same list | Owner 7 Nov; audit F35 | Toolbar | Filters |
| 5 | Qualified # (place among the stocks passing both filters, the number Actions uses) and Score (the composite the rank sorts on) | Owner 7 Nov (S87) | Table | Qualified + Score |
| 6 | Held tag on the model book's stocks; lines at the 20th qualified (the book buys the top 20) and the 40th (keeps a holding while in the top 40) | Owner 7 Nov (S87) | Table | Held + top 20 + top 40 |
| 7 | A failed filter says by how much ("✗ −8.7%" below the 50D EMA) | Owner 7 Nov | Table | ✗ |
| 8 | One colour rule: returns, Sharpe, distance to the 50D EMA and rank changes up/down with + or −; drawdowns and distance below a high plain; true minus signs; "New high" at the high | Owner 7 Nov | Table | Return |
| 9 | Export CSV with every column the ranking carries, in rank order (rank-change order for big movers), and saying so | Owner 7 Nov | Toolbar | Export CSV |
| 10 | What moved in the month: biggest jumps, entered the top 50, left the top 50, with the session the month counts from in the heading | Owner 7 Nov, 13 Oct | After the table | Biggest jumps + Entered the top 50\|Entered top 50 + Left the top 50\|Left top 50 + Since |
| 11 | Nano Cap and Combined: what is ranked, and the stocks too new to rank (the 750 shows none; no test covers this today, the build adds one) | Owner 27 Sep | Foot | stocks ranked |
| 12 | The data-quality counts (price gaps, short history) on this page | Owner 8 Nov | Foot | short history |
| 13 | Phone: rank and stock fixed while the table scrolls sideways; the industry under the symbol; the trend column headed 60D | Owner 7 Nov | Table | [phone] Rank |
| 14 | The wheel scrolls the page, not the table; "Show all" redraws the table at full height, no box scrolling inside the page | Owner 7, 8 Nov | Table | Show all 750 |

## Rules learned on the four redesigned pages that the Screener must honour

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 15 | The title answers the first question; "Screener" is the small kicker above it | PAGE_DESIGN §2a | Top | Screener + qualif |
| 16 | Section headings in the serif, each a sentence stating the finding ("What moved" says who and how many) | PAGE_DESIGN §2, §2a | Sections | entered the top 50 |
| 17 | No internal names: index column and filters read "Microcap 250", not MICRO250; no "Ranked from: Personal" or "Data from: release files" | PAGE_DESIGN §2; owner 20 Nov ("Let's not show source") | Table, foot | Microcap 250 |
| 18 | One name, one thing: industries in the short names Actions, Portfolio and the Dashboard use (FMCG, Auto, Durables), from one map, not the two the code has today (`sector_view.py`, `dashboard_home_view.py`) | PAGE_DESIGN §8 | Table | FMCG |
| 19 | A rank a month and three months ago means the same on every page: the same dates as the Dashboard's rank trail (see decision A) | S154, PAGE_DESIGN §6a | Table | 1M ago + 3M ago |
| 20 | 3 months ago, 1 month ago and now side by side, as numbers, each in its own column | PAGE_DESIGN §2, §3 | Table | 3M ago + 1M ago |
| 21 | Everything visible: the movers lists show every row, no "View all" | PAGE_DESIGN §2 | Movers | Left the top 50\|Left top 50 |
| 22 | Notes 13.5 px, lines no longer than about 80 characters, a long key in two columns on a wide screen | PAGE_DESIGN §2a | Key | Qualified: |
| 23 | Tables: sentence-case headers and group labels, headings over their columns, figures in Plex Mono right-aligned, row labels never wrap | PAGE_DESIGN §3 | Table | Rank |
| 24 | Data date only at the foot, with the counts; no source named | Owner 20, 21 Nov | Foot | Data to |
| 25 | Every figure ends on the page's session; the movers' "since" date is the one the rank changes use | S148 | Whole page | Data to + Since |
| 26 | Layout audit clean at 412 and 1400 px, and the page joins the CI step | Owner 20 Nov; PAGE_DESIGN §8 | Whole page | Screener |

## Data checks run on 21 Nov 2026 (prices to 20 Nov)

- **Holds and sells agree with Actions.** Five held stocks sit outside the top 40 or fail
  a filter on the Screener (ACUTAAS #62, qualified 59th; DIACABS #44, 44th; SHILPAMED
  #46, fails; SKYGOLD #57, fails; SYRMA #100, fails): the same five Actions sells.
  Seventeen of the 20 holdings are in the top 50.
- **Counts.** 750 ranked; 290 pass both filters; 49 of the top 50 qualify (SHILPAMED,
  #46, does not); the 20th qualified is GLAND, the 40th AUROPHARMA.
- **Found: two meanings of "a month ago" (S154).** The Screener's rank change counts
  from the first session on or after the same date a month back (21 Oct); the
  Dashboard's rank trail from the last session on or before it (19 Oct). And the
  Screener's change is the rank among all 750, the Dashboard's trail the place among
  the qualified. KOTAKBANK reads "+59" (from #69) on the Screener and "#54 a month ago"
  on the Dashboard; both are right under their own definition, and a reader sees two
  numbers for one thing.
- **Found: two cut-offs for one idea.** The Screener lists 23 stocks that entered the
  top 50; the Dashboard says 18 of today's top 40 were not there a month ago.
- **Big movers has drifted.** The 150-place threshold was set on 13 Oct as about the
  biggest sixth (about 118 stocks); today it selects 268 of 750, over a third.
- **Not checked:** prices against a second source (the nightly checks own that; this
  page shows the ranking's own closes); Nano Cap and Combined views.

## Decided (owner, 21 Nov 2026: "With all your decisions")

Mock-up v1 (artifact `Q4hR2uCVg4EzbwfKJcYWDh`) approved with the three recommendations
below. Built the same day; the built page meets 27 of 27 checks and the layout audit is
clean at 412 and 1400 px.

Order: Screener → Qualified: → What moved since → Data to

- **A, as built.** Past ranks are read on the last session on or before the same date
  N months back (`calendar_momentum.rank_history_position`), in the engine as well. Not in
  the ranking's contract digest (it holds configuration constants; the digest change made
  CI's Stage-3 check refuse the live table on this PR), so the table published before the
  merge carries the old date until the next ranking run: run Daily sync after merging. The table shows the rank among the
  ranked stocks 3M and 1M ago, and the qualified place 3M ago, 1M ago and now from the
  Dashboard's own `rank_trails`: KOTAKBANK reads 65 (rank) and 54 (qualified) on 19 Oct
  on the Screener, 54 on the Dashboard.
- **B, as built.** Top 50 here, every row; the Dashboard keeps its top-40 count.
- **C, as built.** 150 places; the count is on the preset (267 on 20 Nov).

## The recommendations as put to the owner

- **A. "A month ago".** Recommended: the Dashboard's dates (on or before) on both pages,
  from one function; the Screener keeps the rank among all 750 as its rank and shows the
  qualified place beside it, so the Dashboard's trail number appears on both pages.
- **B. Movers cut-off.** Recommended: keep the top 50 here as the full reading and the
  Dashboard's top-40 turnover as its short version (the Breadth decision), each label
  saying which cut-off it counts.
- **C. Big movers.** Recommended: keep 150 places (a rule that moves with the market is
  harder to read) and let the count say how many; or change it to the biggest sixth.
