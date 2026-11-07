# Pre-launch design audit (7 Nov 2026, closes of 6 Nov)

Four independent audits of all 12 pages at 1440 and 390 px on the real store:
visual design and typography (V), data formatting and copy (D), UX and mobile
(U), accessibility and performance (A). Merged and deduplicated into 78 items.
TODO row S94 tracks this file; each item is closed here with its commit.

## Verdict

1. **Not launch-ready.** 17 P0: 4 wrong or contradictory figures, 1 broken core task, 7 WCAG A failures, 5 old-theme blocks that look unfinished beside the redrawn pages.
2. **Better than the old look where redrawn** (Dashboard, Screener, header, line charts). Stock page, Configuration, Guide, Portfolio's lower half, Backtest, RRG and Actions were only recoloured. Navigation is worse than before (everything behind one ☰).
3. **Foundations are right:** figures reconcile almost everywhere, the palette survives colour blindness, nothing scrolls sideways at 320 px, fonts load. What remains is consolidation: one tile, one table, one type scale, one formatter, a max-width.
4. **About 12 focused sessions to launch-ready (all P0 and P1), about 15 for everything.**

## Status of the P0s

| ID | P0 | Status |
|---|---|---|
| F1 | ACUTAAS shown at three ranks (47 overall; 45 "qualified" on Actions/Dashboard; 44 in Portfolio's ranks-by-month, re-scored by the backtester) | Owner, 7 Nov: "any rank used must be originated from screener". Qualified rank = place among the Screener's rows passing both filters (ACUTAAS 45). Being traced: why the backtester orders one stock differently (not index membership: all 44 above it were members on 4 Nov), and whether the model's own picks use the Screener's ranking |
| F2 | Alpha caption says "compounded"; it is plain subtraction, shown as % instead of points | **Done**: caption corrected (ddd2eca); owner keeps % |
| F3 | Backtest current book shows 5.0% weight on every row; Portfolio 4.7–5.6% | **Done**: "Target weight %", duplicate entry weight dropped |
| F4 | Sectors: median on the board, mean on the map; "Cement & Materials" vs "Construction Materials" | **Done**: NSE's name only, "Above 50D EMA", the map caption names its mean and dates and the board's median |
| F19 | Back button trapped the reader on a stock page (redirect replayed) | **Done** f6ba815 |
| F20 | Sortable headers not usable by keyboard, no aria-sort | **Done**: focusable headers, Enter/Space, aria-sort (Screener, sector table, peers) |
| F21 | Every tab titled "Paresh Patel" | **Done** 1c18c7a |
| F22 | Frame documents have no lang or title | **Done** 123e381 |
| F23 | Menu button's accessible name is "☰" | **Done** 123e381 |
| F24 | RRG week slider has no label | **Done** 123e381 |
| F25 | Lists built from divs (Dashboard risk, Actions, movers, Sectors board) | Open |
| F26 | Charts have no text alternative | Open |
| F42 | Five different figure-tile designs | Open |
| F43 | Calendar-returns card still old theme (shadow, gradient, indigo) | Open |
| F49 | Stock page is the old card layout recoloured | Open |
| F50 | Configuration looks like the old SaaS theme | Open |
| F51 | Guide is boxed cards and marketing headings | Open |

Also done since the audits: Dashboard two-column layout (a8c3a8c); the token
style element's blank block (a8c3a8c; a residual band is F37); D3 1M windows
from daily index closes (d5fdc55, live after the next nightly run; F18 adds the test).

## Plan by phase (ID · severity · title · effort)

**Phase 1, figures.** F1 P0 one qualified rank (M) · F2 P0 alpha in points, right caption (S) · F3 P0 Backtest weights (S) · F4 P0 Sectors median/mean, one name (S) · F5 P1 one formatter: true minus, ₹ sign, dates (S) · F6 P1 lakh/crore grouping (S) · F7 P1 one 200D EMA; regime pill wording (S) · F8 P1 one EMA distance per row (S) · F9 P1 Backtest re-run vs track record labels (S) · F10 P1 no annualised figure under 12 months (S) · F11 P1 rounding that does not reconcile (S) · F12 P1 three universe counts explained (S) · F13 P1 internal names ("Personal", "release files", "Canonical book") (S) · F14 P1 signal words that read as advice (S) · F15 P1 "Leading" on Sectors vs RRG (S) · F16 P1 one name per metric (M) · F17 P1 industry short names, no mid-word cuts (S) · F18 P1 test the 1M windows; label MTD vs 1M (S)

**Phase 2, interactions and accessibility A.** F19 P0 Back trap (S, done) · F20 P0 keyboard sort (S) · F21 P0 page titles (S, done) · F22 P0 frame lang/title (S) · F23 P0 menu name (S) · F24 P0 RRG slider label (S) · F25 P0 real tables (M) · F26 P0 chart text alternatives (M) · F27 P1 skip link, roving focus in the 750-row table (M) · F28 P1 visible focus (S) · F29 P1 faint grey text 3.5:1 (S) · F30 P1 tap targets (M) · F31 P1 navigation: inline top pages on desktop, regrouped menu (S) · F32 P1 sticky phone header, menu height (S) · F33 P1 Dashboard links onward (S) · F34 P1 Screener scroll trap, cut-off columns (M) · F35 P1 filters lost on Back (M) · F36 P1 search shows "[STOCK]" tags (S)

**Phase 3, design system on every page.** F37 P1 residual blank band at the top (S) · F38 P1 max-width 1240 px, 16 px phone gutter (S) · F39 P1 six-step type scale (24 sizes in use) (M) · F40 P1 only the font weights loaded (S) · F41 P1 Mono only for figures (S) · F42 P0 one figure-tile component (M) · F43 P0 one month-grid component (M) · F44 P1 one table style (M) · F45 P1 one radius, no shadows (S) · F46 P1 no emoji; one tag style (S) · F47 P1 chart axes: one tick kind, ₹ and % formats (S) · F48 P1 header and footer: date once, no pills (S)

**Phase 4, page redraws.** F49 P0 stock page (L) · F50 P0 Configuration (M) · F51 P0 Guide (M) · F52 P1 Portfolio lower half (M) · F53 P1 Backtest (M) · F54 P1 Actions (M) · F55 P1 Sectors (M) · F56 P1 RRG table (S) · F57 P1 Breadth (S) · F58 P1 Dashboard headline and phone rows (M) · F59 P1 Watchlist states (M)

**Phase 5, performance.** F60 P1 chart libraries inlined in every frame, 0.4–0.9 MB per page (M) · F61 P1 fonts requested up to 11× per page (M) · F62 P1 750 inline SVG sparklines (S) · F63 P2 Portfolio/Backtest settle 6–8 s (M)

**Phase 6, polish (P2).** F64 neutral counts not coloured · F65 greyscale cue for up/down · F66 two decimals for prices · F67 missing vs unchanged · F68 units in headers · F69 statistics' basis (annualised, per month) · F70 costs worded one way · F71 Dashboard copy · F72 first sort click descending for returns · F73 error, 404 and confirmation states · F74 reduced motion · F75 main landmark · F76 icon words in button names · F77 enforce tokens (60 literals left) · F78 movers limited to the top 100

## Decisions for the owner

Owner's answers, 7 Nov 2026: 1 every rank from the Screener's ranking; 2 yes
(lakh/crore); 3 yes (keep blue/rust); 4 yes (Sans figures, Mono only in dense
tables); 5 yes (keep 11 pages, remove duplicate blocks); 6 keep four pages
inline on desktop beside the menu; 7 the brand stays "Paresh Patel"; 8 yes
("Trend: up"); 9 yes (unpark Screener items 13 and 9). Still open: the model's
own scoring (S95) and alpha as % or points (owner chose % on 12 Oct).

| # | Decision | Recommendation |
|---|---|---|
| 1 | Qualified rank (F1): with the index-membership gate (ACUTAAS 44) or without (45)? | The gate the model uses on the rebalance day, confirmed in the backtester; one function for every page; label "Rank 47 of 750" and "#45 qualified". This month's sell does not change. |
| 2 | Indian lakh/crore grouping (F6) | Yes: "₹28,27,942", "₹28.3 lakh", "₹1,26,433 Cr"; index levels stay as NSE prints them. |
| 3 | Blue for up, rust for down | Keep; add a greyscale cue (F65) and stop colouring counts (F64). |
| 4 | Figures in Plex Mono or Plex Sans tabular (F41) | Sans tabular in tiles and sentences, Mono only in dense tables. |
| 5 | Pages to merge or drop | Keep all 11; remove duplicate blocks instead (Sectors' second ranking and bubble map, Backtest's copy of Portfolio). |
| 6 | Desktop navigation (F31) | Dashboard · Actions · Screener · Portfolio inline beside "Menu"; menu regrouped as My book / Market / Method. (Owner asked for menu only on 7 Nov; this would change that.) |
| 7 | Brand in the header | "NSE Momentum · Paresh Patel". |
| 8 | Regime pill wording (F7) | "Trend: up" instead of "Bullish". |
| 9 | Parked Screener items | Unpark 13 (keyboard sort, now WCAG A) and 9 (one 52W name); optionally 3 and 8; keep 4–7 parked. |

## Not checked

No screen reader, no axe-core, no Safari/iOS, no Streamlit Cloud or phone
timings, the old site not run side by side, the stale-data banner not seen,
focus order inside popovers not walked.
