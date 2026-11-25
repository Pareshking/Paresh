# Indices requirements: everything proposed, in one list

Started 21 Nov 2026 for S170, before any code, from:
- the three research briefs (`docs/archive/INDICES_RESEARCH_LITERATURE_2026-11-21.md`,
  `docs/INDICES_RESEARCH_DATA_2026-11-21.md`, `docs/archive/INDICES_RESEARCH_DESIGN_2026-11-21.md`);
- the owner's decisions of 21 Nov (a separate page; total return where NSE publishes
  TRI, otherwise price with a note);
- the S168 store of every NSE index, built here the same day (3,644 sessions,
  21 Feb 2012 to 20 Nov 2026, 194 indices);
- the rules of `docs/PAGE_DESIGN.md`.

Checked with:

    node scripts/check_dashboard_requirements.mjs <url> docs/INDICES_REQUIREMENTS.md

Each row's **Marker** is text that must appear on the rendered page. A row is changed or
dropped only with the owner's word. The `Order:` line is added when the owner approves
the section order.

Scope: a new page at `/indices`. Index data only. Industries stay on Sectors, trend and
participation on Market (called Breadth until 21 Nov), and the book's own momentum on the Dashboard.

## What a reader comes with

1. Is the market cheap or dear against its own recent past, and for which size?
2. Which investing styles are paying, measured against their own parent index?
3. How long and how deep can a style lag? This puts momentum's lag in proportion.
4. Over whole years, how often has each style led, and how far does each size fall in a
   normal year?

## The page

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 1 | Kicker "Indices"; a title answering question 1 with its numbers; one lede saying what is measured (NSE's indices, price, to the page's session) | PAGE_DESIGN §2a | Top | Indices + P/E |
| 2 | **Valuation.** One row each for Nifty 50, Nifty 500, Total Market, Midcap 150, Smallcap 250 and Microcap 250. P/E 3M ago, 1M ago and now, as numbers in their own columns. Then the percentile of now within the index's history since 31 Mar 2021, drawn as a line bar. P/B and dividend yield appear under "Show the table". On the 1000 (`?sys=1000`) a Nifty 1000 row follows Total Market: its P/E now, and "–" for the percentile and the past readings, with one note giving the first day NSE's files carry its P/E (16 Nov 2026) (S219-7, owner 23 Nov 2026) | Design §5.1; literature item 8; S219-7 | Section 1 | P/E + since 31 Mar 2021 |
| 3 | The percentile counts only from 31 Mar 2021, or from the index's launch if later. On that day NSE's P/E basis changed (Nifty 50 40.43 to 33.20 with price flat). The page says so in one line | DATA_CORRECTNESS §5 (S168) | Section 1 | basis |
| 4 | One band chart of the Nifty 500's weekly P/E since 2012. The middle half since Apr 2021 is shaded, the 31 Mar 2021 break is marked, and a crosshair shows the date and P/E. The earlier years are drawn muted, not spliced in | Design §2.2 | Section 1 | Nifty 500 P/E |
| 5 | No P/B percentile. Its basis changed on 29 Sep 2023 and again on 23 Sep 2024, which leaves too little history | DATA_CORRECTNESS §5 | Section 1 | P/B |
| 6 | "Describing is not forecasting": no claim that a low P/E means higher returns until a fixed rule is tested on our record (S150 style) | Literature §5.1; Goyal & Welch 2008 | Section 1 | not a forecast |
| 7 | **Styles.** One row per style: Momentum (Nifty200 Momentum 30 against Nifty 200), Quality (Nifty200 Quality 30 against Nifty 200), Value (Nifty500 Value 50 against Nifty 500), Low volatility (Nifty100 Low Volatility 30 against Nifty 100), Alpha (Nifty100 Alpha 30 against Nifty 100), Equal weight (Nifty50 Equal Weight against Nifty 50). Each row names its NSE index and parent. Columns: the 12-month lead over the parent as read 3M ago, 1M ago and now, with now drawn as a line bar from zero | Design §5.2 | Section 2 | Lead over parent |
| 8 | Each style row gives its dividend-yield gap to the parent (Value +1.79 pts). A price lead understates a high-yield style by about that much a year | Owner 21 Nov (price with a note); literature item 1 | Section 2 | yield |
| 9 | Each style row shows its live date, the day NSE's daily file first listed it (Momentum 25 Aug 2020, matching NSE's press release). Only live history is used: no back-calculated years | Literature item 2; Huang, Song & Xiang 2024 | Section 2 | live since |
| 10 | **Style drawdowns.** A two-pane chart for the chosen style, picked by chips: the relative line (style ÷ parent, 100 at launch) and its fall from the relative peak, with one crosshair. Beside it, a table per style: fall now, worst fall with its dates, and the date it recovered or "not yet" | Design §5.4 | Section 3 | Max DD, relative |
| 11 | **Calendar years.** A table with one row per year and one column per style, giving the lead over the parent. Each style starts at its first full live year, and this year is marked year to date. Figures carry only the sign colour, no heat colours. The heading counts the years each style led | Design §5.3 | Section 4 | year to date |
| 12 | **Size by year.** One row of small multiples each for large (Nifty 100), mid (Midcap 150), small (Smallcap 250) and micro (Microcap 250, from 2022), the size indices the rest of the site uses, all from 2017 (NSE's file lists 150 and 250 from Apr 2016). Each calendar year's return is a bar and its worst fall within the year a dot, all on one scale. The heading gives the median fall per size | Design §5.5; JPM Guide practice; owner 21 Nov ("why don't we use Midcap 150, Smallcap 250") | Section 5 | within the year |
| 18 | **Every index.** NSE's broad, theme and strategy indices (112 on 20 Nov; 110 once Nifty Consumer Services and Nifty Commercial & Transport Services moved to Sector, owner 21 Nov, Sectors item 4) in three families; the 37 sector indices are on Sectors (owner, 21 Nov), and the note says so (`data/reference/nse_index_groups.csv`; the grouping is ours, after NSE's four headings). Each family is a table sorted by 1-year price return, with 1M, 3M, 6M, 9M, 1Y, distance from the 1-year high and P/E. Indices younger than a year are listed last with their launch date. Each family's heading states its leader, laggard and count up. Bond, rate, leveraged and inverse indices, VIX and the dollar Nifty are left out | Owner 21 Nov ("Where are the other indices for theme, sector, industries") | Section 6 | Every index |
| 13 | Data to the page's session at the foot, with the count of indices read; no source named | Owner 20, 21 Nov; PAGE_DESIGN | Foot | Data to |
| 14 | Every figure ends on the page's session; "1M ago" and "3M ago" are the last session on or before the same date (the Dashboard's rule) | S148, S154 | Whole page | Data to |
| 15 | Headings in the serif, each a sentence stating the finding; notes 13.5 px, lines of about 80 characters; tables use sentence-case headers and Plex Mono right-aligned figures | PAGE_DESIGN §2, §3 | Sections | Indices |
| 16 | Layout audit clean at 412 and 1400 px; the page joins the CI step | PAGE_DESIGN §8 | Whole page | Indices |
| 17 | Dashboard: the freed section 7 space gets three lines, "Indices: valuation and styles". They give the Nifty 500 P/E percentile with 1M and 3M beside it, the best and worst style by 12-month lead, and a link. No chart. "At a glance" links to Indices, not Breadth | Design §6; S169 | Dashboard | Indices |

## Not on this page, and why

- **Day changes, an 8-window return table, heat carpets.** The first are on the Dashboard's glance. The other two carry too many figures, with meaning in colour alone (Design §2.7).
- **Trend status of each index.** Market (then Breadth) answers it, and a second framing of the same index's trend would compete.
- **The momentum-crash flag** (Daniel & Moskowitz). It is a TEST item with about one bear state since 2012, so it waits for a test.
- **P/E bands with buy or sell levels, RSI/MACD, seasonality, flows as a predictor, the market-cap-to-GDP ratio.** Literature §5.
- **A size × style matrix.** NSE has no mid or small value or growth indices with history.

## Data checks run on 21 Nov 2026 (S168 store, to 20 Nov)

- **The store against other collectors.** Nifty 50 and Nifty 500 equal `data/benchmarks.csv` on all 3,644 sessions (largest gap 0.001%). Those rows came from the Kaggle dataset, SS and NSE's API. All three publish NSE's own figures, so this checks the collection, not NSE.
- **Eight faults in NSE's files**, each handled by a rule (DATA_CORRECTNESS §5):
  - dates in three formats;
  - 18 weekend sessions;
  - 12 trading days with no file;
  - two regenerated files with back-calculated rows;
  - a points change measured against the wrong day;
  - P/E and P/B basis changes.
- **Readings for the mock-up.**
  - Nifty 50 P/E 20.48 / 19.33 / 21.02 (20 Aug, 19 Oct, 20 Nov), 26th percentile since 31 Mar 2021. Smallcap 250 33.84 / 33.26 / 32.14, 76th percentile.
  - Momentum: 12-month lead −0.2 / −1.4 / −6.8 pts. Its relative line is 24.2% below its 14 Jun 2024 peak, the deepest since launch.
  - Median fall within a year, 2013–2025: large −11.5%, mid −15.2%, small −23.2%.
- **Not checked.**
  - Indices other than the Nifty 50 and Nifty 500 against a second source (niftyindices.com refuses this machine).
  - Total return. NSE's TRI is unreachable from here and from GitHub's runners.
  - Launch dates against NSE's press releases, except Nifty200 Momentum 30.

## Decided (owner, 21 Nov 2026: "yes with your recommendation")

A, B, C and D as recommended below. B is built: `nse_indices.derive_missing` fills the 11 days listed in
`data/reference/nse_index_missing_sessions.csv` (529 rows, `derived` true), the Nifty 50
and Nifty 500 equal the Kaggle/SS closes on all of them. Mock-up v2 (artifact
GLYdKBPes3KsBxAEzdCqxz, same link) carries rows 12 and 18 as changed. Owner, 21 Nov ("yes with your recommendation"): sector indices move to Sectors (`SECTORS_REQUIREMENTS.md` rows P1-P3), themes and strategy stay here, the three pages are not merged; earnings growth is TODO S171. v3 (same link).

**Approved, owner 21 Nov 2026** ("Everything approved once you add missing months like 1M, 3M, 6M, 9M and 1Y"): v4 adds 6M and 9M to every-index table (row 18); the style table keeps one 12-month lead read on three dates.

**Built 21 Nov 2026** (PR #587): 19 of 19 checks, layout audit clean at 412 and 1400 px. Found while building:
the mock-up's line bars were coloured, against PAGE_DESIGN 4.2 (two colours, ink and grey): built in the kit's
two-colour lines; the drawdown table's heading now says "Max drawdown, relative" (S173 IX-1, 24 Nov 2026); on a phone the every-index names
stay on one line, pinned while the numbers scroll, and an index younger than a year shows its launch date in the
1Y column.

Order: Indices → Valuation → Styles → How long a style can lag → Calendar years → Size, year by year → Every index → Data to

## Decisions as put to the owner

- **A. Returns basis.** NSE's TRI cannot be reached, so total return is not available as decided. Recommended: price returns, with each style's yield gap printed beside it (row 8). Rejected: a home-made "price plus yield" series, because it is our own construction presented as an index.
- **B. The 11 derivable missing days.** For 11 of the 12 days NSE has no file, the next session's close minus its points change gives the missing close. It matched the Kaggle/SS close exactly in 22 of 22 checks. Recommended: fill them by that rule for every index, with each filled row marked as derived. Alternative: leave the gaps, since they barely move monthly or yearly figures.
- **C. Which value index.** Recommended: Nifty500 Value 50 (live Oct 2018, parent Nifty 500). Alternatives: Nifty50 Value 20 (live 2014, a narrow 20 stocks) or Nifty200 Value 30 (live only since Jun 2024).
- **D. Dashboard section 5 (size against the market at 1/3/6M).** Recommended: it stays on the Dashboard. Indices shows size by calendar year and fall within the year, and the every-index table gives each size index's own return, not its lead over the market, so no figure appears twice. Since 21 Nov both pages mean the Nifty 100 by "Large".
