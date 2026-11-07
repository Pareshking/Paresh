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

## Since 11:30 (7 Nov, 14:25 UTC)

- The owner's S97 answers built: Screener 50 rows + Show all (wheel moves the page), menu
  grouped My book / Market / Method, 1,240px pages and a 16px phone gutter (1a2f9c5).
- Question pages (S98, owner: "go for it"): the Dashboard answers three questions (e8cff18);
  Breadth answers "Are most stocks taking part?" and "Is the market in an uptrend?" with
  what changed and what would change the answer, and a size-index trend table (fc9e3a5);
  Sectors answers "What is leading?" with industries in four groups and a month-by-month
  grid of runs (47d426b). On 6 Nov the trend verdict matched tipsheet's independent page.
- Sentence case through the shared components; column headings on Sectors' groups (f247ed5).
- Editorial type prototype (owner: "I am with you"): Source Serif 4 for titles, verdicts and
  headline figures, 17px prose, a news headline on the Dashboard, range bars with
  percentiles in Breadth's evidence; Dashboard and Breadth only (9df73cf). Waiting on the
  owner: roll out to every page, or adjust first.
- Fixed with it: the deep price history is sparse in early years, so 52W windows are a
  calendar year, readings need enough stocks, and a missing day takes the week's last price.

## Progress (7 Nov, 11:30 UTC)

**All 17 P0 are fixed.** Every change was checked on the local app with the real
6 Nov store (desktop 1440 px, and an iPhone 13 viewport where it matters),
2447 tests pass, and CI was green on each pushed head except 0c1f937 (a failing
test that went out with it; fixed in 97fd85d).

| State | Items |
|---|---|
| Done | F1-F8, F10, F15-F17, F19-F30, F32, F33, F35, F36, F40-F46, F48-F51, F54-F56, F58, F59, F64, F66, F69 (Sharpe basis), F70 (costs one wording), F77 (no colour literals outside tokens, with a test; the sector palette is V14), F72, F74, F18 (tests on the shared 1M session and daily index closes, test_dashboard and test_nse_index_prices); decision 5 (Sectors one ranking and one map, Backtest research only) |
| Partly done | F39 (nothing under 12px; 24 sizes down to 22, the six-step scale not done), F12 closed (Traced 7 Nov from the files: 754 = NSE's Total Market file = the 750 + ENNATURE and IGLSPIRITS (India Glycols' demerger, listed 4 Nov, carried above the 750 until NSE's exclusion notice) + two unlisted placeholders DUMMYHEG and DUMMYINXGN; 752 = point-in-time membership on 6 Nov and the footer's price coverage = the 750 + ENNATURE and IGLSPIRITS; 750 ranked = the 752 members less ENNATURE and IGLSPIRITS, which have two sessions of prices: momentum.MIN_OBSERVATIONS (63) excludes a stock from the ranking until it has 63 real prices (momentum.py:502 drops unscored rows). Deliberate; they become rankable about 63 sessions after listing, if still members. The six short-history stocks the footer counts have 63 or more but under 126. Configuration's note now says so. Closed 7 Nov), F11 (Portfolio chart now ends on the headline value; levels unsigned), F27 (skip link done; roving focus in the 750-row table open), F34 (right-edge fade done; the inner scroll is S97b), F47 (₹ price axis and month-only date ticks done; % axes keep one decimal), F53 (Backtest is research only; its own layout untouched), F52 (Three systems table aligned and toned; rest of the lower half follows the shared table and grid) |
| Decided by the owner (S97) | F13 keep "Personal"; F31 regroup (done); F34 50 rows + Show all (done); F38 1,240px and 16px (done); alpha stays %; V14 keep the 20 sector hues |
| Open | F9, F14 (log wording comes from stored data), F37, F57, F60-F63 (speed; F60 plan: serve the chart libraries once from Streamlit's static folder instead of inlining 0.2-0.5 MB per frame, but how relative URLs resolve in Streamlit Cloud's frame must be checked on Cloud first, or every chart goes blank), F65, F67, F68, F71, F73, F76, F78 (polish); F75 not possible without script injection (Streamlit renders no main landmark; the skip link covers the need) |

Commits, in order: fef5a0c F25/F26 · fe3a09a F51 · bd28c0a F42/F50/F5/F10/F45 ·
36912b2 F49/dates · f4cb21f F43 · 2f84512 F27-F29 · 898a207 F8/F15-F17/F46/F54 ·
e5de325 F33/F36 · 91c1646 F32 · 0c1f937+97fd85d F35 · c7c82d6 F30 · 021763a F44 ·
a65c3f8 decision 5 · 9c6f0b5 F40/F48 · fe9f9ad F41 · ab21cbb F47 · 7bc597e F56 ·
4bc3321 · bbbb800 F34 part.

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
| F25 | Lists built from divs (Dashboard risk, Actions, movers, Sectors board) | **Done**: ARIA table roles on the grid lists (look unchanged); a test checks every row has as many cells as headers |
| F26 | Charts have no text alternative | **Done**: every chart frame carries its content in words (first, last, low, high per series; RRG quadrants; correlation extremes; each industry and sector) and a descriptive title; the drawing is aria-hidden |
| F42 | Five different figure-tile designs | **Done**: one tile for kit.readings and st.metric rows (hairlines, centred per the owner's 13 Oct choice, Plex Sans 600 tabular) |
| F43 | Calendar-returns card still old theme (shadow, gradient, indigo) | **Done**: one Ledger grid for Portfolio and Backtest; no box, shadow, gradient or indigo; nothing under 12px |
| F49 | Stock page is the old card layout recoloured | **Done**: cards open under an ink rule, verdict a ruled band without tint, Sans tabular figures, words-not-chips for pass/fail |
| F50 | Configuration looks like the old SaaS theme | **Done**: open sections under an ink rule, plain link index, ink-only weight bar; "Personal" label parked for the owner (F13) |
| F51 | Guide is boxed cards and marketing headings | **Done** fe3a09a: one reading column, checked against the code; regime playbooks removed; removed-engine list moved to CHANGELOG |

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
