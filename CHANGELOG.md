# Changelog

## 2026-11-11 — The Dashboard shows the book before the market (pending approval)

- **Book at risk, How risky is the book?, Next rebalance and Coming up for the book now come first**, above the four market questions. On a phone, Book at risk starts 619 px down instead of 2,578 px, so the first sale is on the first screen. The market's own cards (momentum health, qualify count, size leadership, flows) follow the market questions.
- **The book's card headings are the same size as the rest of the page** (they were forced to 15 px).
- **In Book at risk, a sale is a filled chip and Watch an outlined one**; the two were text colours almost impossible to tell apart. Clear rows draw a light grey bar instead of the darkest mark on the card.

## 2026-11-11 — The corporate-actions guard was not looking at anything

- **The nightly check for splits and demergers hiding in the price history had been scanning nothing, while the run reported green.** It read a local file (`data_cache/screener_prices.parquet`) that nothing writes on a GitHub runner — the store a sync downloads is streamed to a temp file, read, and deleted — so it printed "no screener closes to check" and exited in under half a second on every run. The step's warning said "new find or failure", which reads like a find, and seven consecutive green runs carried it before anyone opened the step log.
- It now falls back to the published store, the same one the ranking is built from, and the log line names the source and the size: *scanned screener from published store: 401 sessions × 1,227 symbols at ±35%*. A run that could not scan exits with a different code from a run that found something, and the workflow prints a different warning for each.
- No price changed. One session is flagged and was already on the log (POLICYBZR, −36.0% on 24 Sep 2026, matching no standard split ratio — the usual cause is a demerger). Whether anything was missed in the window is not established: the log's newest entry is 29 Sep, which fits the check having been blind since 28 Oct but is not proof, since no new implausible session need have occurred.

## 2026-11-11 — The monthly returns say which months they are

- **Portfolio and Backtest show the same months and could disagree, with nothing to tell a reader why.** January read −0.2% on one page and 0.0% on the other, October −4.3% against −4.0%. Portfolio's grid now says it is "as recorded each month", and Backtest's says it is "re-run on today's prices", each naming the other. The figures themselves are unchanged.
- Why they differ is written down in `docs/MONTHS_THAT_DIFFER.md`: January and February come down to **one holding** — the twentieth slot, awarded after the 40% industry cap, which is TITAN on one price basis and ANURAS on the other, worth +0.2173 points of January against an observed +0.2170. October is a month whose store carried BSE closes for about forty names. The rights-issue adjustment that had been blamed for years turns out not to touch either: removing all 44 rights rows leaves both months unchanged to six decimals.

## 2026-11-11 — One volatility convention across the whole site

- **Every standard deviation on the site is now the population one.** The engine's position sizing had always spelled out `std(ddof=0)`; every figure the site *reported* quietly took pandas' default, the sample SD, because nobody had written the argument. Owner, 11 November 2026: "OK, match everything." Unified on `ddof=0` — the convention that was actually chosen, and the one the Guide already claimed for the ranking's own volatility.
- **What moved, on the real data (closes of 9 Nov 2026).** The Dashboard's book volatility 16.945% → 16.878% and the Nifty 500's beside it 12.412% → 12.363% — both still print 16.9% and 12.4% at the one decimal the card shows, so that card is character-identical before and after. The Backtest tab has no volatility figure of its own, but the Sharpe divides by it: over the ten completed months its volatility 23.428% → 23.371% and the Sharpe 1.5787 → 1.5825, which still prints 1.58. The two differ by exactly `sqrt((n-1)/n)`, so a short window moves most.
- **The RRG's numbers moved visibly**, because its z-scores divide by the spread of a twenty-industry cross-section rather than of a few hundred sessions. The largest shift was Utilities, 86.33 · 88.87 → 85.97 · 88.59; Media Entertainment & Publication 117.30 · 105.78 → 117.75 · 105.93; Construction Materials' momentum 112.53 → 112.86. **No industry changed quadrant** — a quadrant turns on the sign of the numerator, which no positive divisor can flip — and nothing else on the page moved.
- **No recorded return moved, and nothing about position sizing changed.** The record is sized equal weight, so the inverse-volatility estimate is not in its path; a replay of all ten frozen months is identical to ten decimal places, and the canonical parity check passes unchanged. Volatility appears in neither the pinned configuration nor the ledger.
- The convention is written down in `docs/TRACK_RECORD.md` with the owner's date and words, and `tests/test_volatility_convention.py` reads every call site with `ast` and fails if one drops back to the sample SD. Two research scripts are exempt and say why: one replicates a published paper, the other has to follow an external vendor's RRG rather than ours.

## 2026-11-11 — The index lists are read from the repository, not downloaded again

- **The first page view no longer waits for six CSV files the repository already
  holds.** The six niftyindices constituent lists were downloaded on every cold
  start and again every hour — about 4 seconds of a 9 second load — although the
  nightly sync writes and commits those same files to `data/indices/`. They are
  now read from the committed copy while the sync that writes them is current (a
  file whose last download is more than 24 hours old is still fetched, so a night
  without a successful sync changes nothing). Measured on the real code path with
  the site's own loader: **6 requests per cold start, now 0**. No row of the
  universe changes — the lists loaded from disk were compared with the lists
  loaded from NSE, symbol for symbol.
- The same change stops the nightly jobs asking for the same file several times
  in one run: a `daily_sync` run made **17 requests for those 6 files and now
  makes 6**, the Screener store (8.79 MB) is downloaded once a run instead of
  twice, and the newest NSE bundle once a run instead of twice. Nothing that is
  published or displayed differs; these are the same bytes, fetched once.
## 2026-11-11 — The Guide on tax, and an audit of method and evidence

- **The Backtest shows the month in progress.** Both tabs stopped at the last completed month, so on 11 Nov the grid ended at October while Portfolio already showed November. November now appears to date, marked in the caption with the day it reached ("to 6 Nov 2026"), and the year table reads "Jan–6 Nov". The figures at the top still stop at the last completed month. The History tab shows it when its end month is the latest one.
- **The Guide compares the strategy with simply holding the index, after tax.** From Jan 2010 to Oct 2026, both price only and both sold at the end: 15.1% a year against 9.4%. The lead is 8.5 points a year before tax and 5.8 after, because the index pays tax only once at the end.
- **The Guide shows what costs do.** The Nifty 500 backtest earns 18.6% a year at 30 bps a round trip, 17.5% at 50 and 16.2% at 75. STT and stamp duty take about 22 of the 30 bps; the spread has not been measured.
- **The Guide no longer says tax is "not modelled anywhere"** a few lines above an after-tax test result. Every figure is before tax; tax was estimated in that one test only.
- Audit of method and evidence: `docs/AUDIT_2026-11-11.md` (costs, tax against an index fund, dividends, how long the record must run before it can show anything).

## 2026-11-10 — Calendar returns can be slid again on a phone

- **The months after April could not be reached on a phone.** The table of monthly returns sits in a box that scrolls sideways, inside a grid. A grid item will not shrink below its own content unless it is told it may, so the year section stretched to the table's full width — 1,292px inside a 358px column — the scrolling box stretched with it and had nothing left to scroll, and the wrapper simply cut the rest off. One line (`.cr-year { min-width: 0 }`) puts the scroll back; after it the scrolling box is 358px wide with 1,292px inside it. Every table on all eleven pages was then checked at phone width: none is unreachable.

## 2026-11-10 — Launch testing: the four content items left over

- **A second breadth chart dated a month by the calendar, not by the market.** The month-end chart labelled October 2026's close "31 Oct 2026", a Saturday on which nothing traded and which `data/benchmarks.csv` has no row for, while the Dashboard called the same close "the 30 Oct month-end". Both now say 30 Oct, as the source does. Each bucket is dated by the session that closed it, the same rule the weekly chart got yesterday; the values are untouched — only the label moves.
- **The Guide now says that a stock needs 30 closes before it has a moving average.** From the 30 November signal a stock with fewer than 30 daily closes has no 50-day average at all, so it cannot pass the trend filter and cannot be bought — a recent listing waits about six weeks of trading. The rule was in the code and nowhere a reader could find it.
- **The Guide now says the 52-week high is read from closes**, not from the highest price touched during a day, so every stock reads a little nearer its high than an intraday chart would show and every count of stocks near their high is a count on that basis. `docs/TRACK_RECORD.md` carries both rules, with the measurement that says what the basis costs (50 names against 22 on the live universe).
- **The Guide names the members-only scoring rule**: from the 30 November ranking the score is worked out over that day's index members only, so the same stock gets the same score on every page; earlier months stay as recorded.
- **Watchlist has the same footer as every other page.** An empty watchlist returned before the footer was drawn, so a fresh browser saw the empty state and nothing else — the only page of eleven without it.

## 2026-11-10 — Portfolio's first view, and one dependency gone

- **The Portfolio page no longer builds the momentum engine to read one price frame off it.** It took the whole engine as an argument and used exactly one attribute of it, `calc.prices`, so the first visit after a restart paid for an engine the page never scores with. The frame now comes from `pipeline.ranked_prices`, which applies the same four steps the engine path applies and is checked against it by `tests/test_ranked_prices_match_the_engine.py`. Measured on one box, same walk, before and after: the first view 7,725 ms → 7,234 ms on average of two runs (and 8,828 → 8,087 ms through `scripts/launch_perf.py`), the process's peak memory at that page 611 MB → 509 MB, resident 516 MB → 393 MB. **No figure moved**: the whole Portfolio page, 655 lines of rendered text including every frame, is byte-identical before and after, and so is the Screener's.
- `streamlit-lightweight-charts` is no longer installed. It had no caller: the stock page draws through the self-hosted TradingView library (`src/ui/lw_chart.py`), and the component renderer kept beside it "for reverting" was never reached. The pin, `src/ui/lightweight_chart.py` and its 18 tests are gone — 2,823 KB and 18 files out of the installed environment.
- The log line for an unconfigured R2 index-levels read now carries its own elapsed time. It was believed to cost three seconds of the cold start; it costs 0 ms, and the gap that suggested otherwise belongs to the dashboard's own rendering.

## 2026-11-10 — A cost basis the record cannot prove is gone from Portfolio

- The Portfolio holdings table measured a position against the price it was **first** bought at. Until the 30 November signal the model put every holding back to 5% at each rebalance, so a winner was trimmed month after month and today's shares are several lots at several prices. On that reading CUPID's 2,022 shares "cost" ₹2.56 lakh, against the ₹6.88 lakh the account actually struck them at on 2 November, and the ₹4.37 lakh of "P&L" it implied is neither realised nor unrealised: most of it was banked by the trims and is already inside the record's monthly returns. The two columns left the visible table in #492 but stayed in the frame and in the Holdings CSV; they are now gone from both, with a test that fails if either returns.
- They are not replaced by a better estimate. The ledger stores one return per month and the replay stores a weight and a price per rebalance — no shares, no rupees, no lots — so no honest rupee cost exists to print. What the table shows instead is what the record can stand behind: the value at the fill where today's shares were set, the move since, and the price's rise per share since entry. **No figure on the page moved**; the return column simply stopped being derived from a basis it did not need.
- The book now says this under it in one caption, and the headline's "Invested: ₹1,00,00,000" reads "Started with ₹1,00,00,000" — the account has compounded since, and what it holds today is the book struck at the last rebalance.

## 2026-11-10 — Launch testing: four things a reader would have seen

- **The site said yesterday's prices were stale this morning.** Today is Diwali-Balipratipada, a published NSE holiday, and the freshness line counted it as a trading day: "Prices: 9 Nov · 752/752 · 1 trading day behind" on the day 9 November *was* the latest session. It now reads "latest session". The walk that looks for price files still offers every day, holiday or not, because only the exchange can prove a day was closed — but the age of a figure is a different question, and a day NSE itself lists as closed is no longer counted. A wrong holiday file can now only make that count short; it can never make a real session read as stale.
- **A breadth chart labelled its newest bar four days in the future** — "5.5% on 13 Nov 2026" when the last session was the 9th — because a week in progress was dated by its Friday. It now carries the last session's date, which is also what the table beside it says.
- **The Guide contradicted itself** about the rule that changes on 30 November: "Caps" said no stock above 5% of the book, "Weighting" said a holding that stays is trimmed only above 15%. The second is what the model does, and what Portfolio already shows. "Caps" now says a new buy is never above 5% and a kept holding is cut only above 15%.
- The Guide also quoted the header as reading "Nifty 500 2.9% above its 200D EMA" — a number typed in by hand, against the 3.4% the header was actually showing. The quotation no longer carries a figure.
- `docs/LAUNCH_TEST_PLAN.md` holds all eleven slots and their measurements, and five commands now answer the launch questions on demand: `launch_gate.py`, `launch_consistency.py`, `launch_a11y.py`, `launch_perf.py` and `launch_security.py`.

## 2026-11-10 — One entry gate, from the 30 November signal

- The Screener and the backtest could disagree about the same stock on the same day. The 50-day EMA gate: the Screener will not quote an EMA until a stock has 30 prints, while the replay quoted one from as few as 10, so three stocks on 5 November (BAGMANE, BIRET and ICICILIFE) passed the replay's gate and failed the Screener's. The 52-week-high gate: the Screener measured it from intraday highs, the engine from the day's close.
- Both now follow one rule: 30 prints before an EMA is quoted, and the high is the day's close. The EMA rule starts at the 30 November signal, so every month the record has already frozen replays exactly as before and keeps its fingerprint. The high is the close everywhere from today; on the current price source the two were already the same series, so no figure moves.

## 2026-11-10 — One formatter, one constant, and 400 lines of dead code gone

- Three pages printed "−0.0%" for a value that rounds to zero, and the stock page used an ASCII hyphen where the rest of the site uses a true minus. Eight places formatted percentages their own way; they go through `src/ui/formats.py` now, which is the module that holds the rule, and a test fails if either slips back.
- The 52-week-high minimum, the risk-free rate and the model book's capital are read from the constants that already defined them instead of being retyped. A test that moved the 52-week constant to prove the gate respected it was certifying a number the backtester never read.
- Removed ~400 lines that nothing calls: an old sector bubble map and its palette, a second sector table, and a dozen helpers and constants left behind by earlier changes. Four one-off scripts and two superseded documents went too. No page's content changed.

## 2026-11-09 — Cash counts in the book's risk, and the qualified share is current

- "How risky is the book?" kept cash out of its weights, so a book 60% invested read as if every rupee were in stocks: beta and volatility a third too high and the size tiers summing to the whole book. Cash now damps both by its share and appears as its own row. It matters from the six-monthly reset, where a buy short of cash simply buys fewer shares.
- "How many stocks qualify?" read the September month-end on a 9 November page, because the monthly file can only carry a month once that month's return is in. The share is a count at the month-end, not a return, so the job now writes it as soon as the month closes and the card uses it.
- No research script runs a shell command built from its arguments.
- On a phone, "What is leading?" stacks its four groups instead of overflowing, and an industry name gets a line of its own rather than being cut to a third of itself.

## 2026-11-09 — The display sizes join the scale, and the tables agree

- Every heading and hero figure now comes from the theme: the page headline is one size on every page (the stock name was 44px against 52 elsewhere), section headings one size, and a new step covers the one big figure a page is about, a price or a rank. The stylesheet's own superseded copies are gone, so there is one definition per heading rather than four.
- "On this page" is one component instead of three hand-rolled copies, and Portfolio and Sectors have it: both run over four screens with no way to jump.
- The Screener grid says "more columns →" while any are off the right edge, instead of only fading.
- On a phone, the stock page's return and drawdown figures stay inside their cells; a long bar used to push the number out of sight. Actions now says which columns a phone leaves out instead of dropping them silently.
- Every table's column headers read the same way: sentence case, one weight. The Screener's grid was in capitals and the calendar's headers a lighter weight than everywhere else.

## 2026-11-09 — Muhurat trading counts as a trading day

- NSE held Muhurat trading on Sunday 8 November. The site's calendar skipped every weekend day outright, so the 8 Nov prices — the freshest it had, for all 752 stocks — could not be placed and the footer reported them as stale. A weekend day NSE has confirmed is now a trading day, and the collectors offer the exchange weekend dates so a session like this can be confirmed at all: the walk that would have recorded it was the same walk that skipped it. Market caps had stopped at 6 Nov for the same reason.

## 2026-11-09 — One theme file for the whole site

- `src/ui/tokens.py` now holds the whole look: colours, the eight type sizes, the spacing ladder, corners, shadows and the three font families. Change a value there and every page changes, framed tables and charts included. Documented in `docs/THEME.md`.
- The stylesheet's type sizes are on that scale: 255 hardcoded sizes became tokens, and the four steps that sat inside a 1.5px range (11, 12, 12.5, 13) became one. Tests fail if a theme variable is used that the file does not define, or if the count of leftover hardcoded sizes rises.

## 2026-11-08 — Momentum health splits the top fifth into its two deciles

- The card now shows the top 50 and ranks 51-100 against the Nifty 500 as separate rows. Over 201 months the top decile led the index by 1.01 pts a month against 0.59 for the second, in every five-year block, so the blended "top 100" figure understates what the best-ranked names did. The headline stays the top 100: a 20-stock basket tracks our own book better (0.93 against 0.85) but is nearly the book itself, is behind the index over a full year 25% of the time against 19%, and would print +29.7 instead of +11.9.
- The bar strips under Momentum health and Flows print their figures (highest, lowest and latest month, with dates) instead of needing a hover, which touch cannot do. Measured first: an interactive chart costs about 6 requests, 190 KB and 130 ms here, so converting the Dashboard's four would add about half a second and 760 KB to the first page a reader sees.

## 2026-11-08 — Momentum health states two returns, and says "top 100"

- The headline is now the gap between two 12-month returns ("the top 100 returned +4.6% against the Nifty 500's −7.7%: 12.2 percentage points ahead"). It added the 12 monthly gaps before, which drifts from the real 12-month gap when months are large (12.9 summed against 12.2 compounded), and the card never said which it showed. The percentile is now ranked the same way: 56th, not 65th.
- "Top fifth" is written as "top 100" everywhere on the Dashboard (one fifth of the Nifty 500, about 100 stocks): "fifth" reads as "fifty".

## 2026-11-08 — Cards match the site's table style; audit Low items

- Next rebalance and Flows list their items as hairline rows like the market-question tables (they used bold grey labels with no rules). Momentum health shows its momentum and breadth rows again (the monthly file now carries the average stock's return).
- Rebalances table: "Qualified rank at start / end"; Portfolio: "Overall Rank Now", so the two ranks are not confused.
- Phone: section links and the menu button are at least 44 px tall.
- Flows says NSDL's figures are by reporting date (each report covers the session before).

## 2026-11-08 — The record moves to a six-monthly reset from 30 Nov

- From the 30 Nov 2026 rebalance every holding goes back to 5% twice a year, in March and September, instead of every month. In between, winners run (cut back only above 15%) and each new buy is 5% of the account at the last reset, paid from cash. This replaces the "winners run to 15%" change announced earlier today. Tested over 2010-26 with an estimate of Indian capital-gains tax: 15.3% a year after tax against 15.4% for the monthly reset, with far fewer trades; best of the four rules tested in 2026. Months before the change keep their figures.

## 2026-11-08 — Header says what it measures; Configuration's site-wide buttons hidden

- The header's first item now reads "Nifty 500 2.9% above its 200D EMA" (it said "Trend: up" next to a Dashboard that said "No clear trend"); the separate distance item is folded into it.
- Configuration no longer shows visitors "Sync from niftyindices.com" and "Clear cached files": both clear the shared caches for everyone.
- The Nifty 500 history now follows NSE's rename of ICICIPRULI to ICICILIFE (23 Oct); it matches NSE's list, 500 of 500.

## 2026-11-08 — Momentum health leads with winners against the Nifty 500

- The book never shorts, so Momentum health now leads with what a long-only momentum book earns: the top fifth of our ranking against the Nifty 500 over 12 months (+12.9 points to October, 65th percentile since 2010). It is split into momentum (winners against the average stock, +11.3) and breadth (the average stock against the index, +1.6); winners minus losers (+8.9) stays as a reference row. Since 2010 the new figure moved with our book's lead over the index far more closely (correlation 0.81 against 0.44).

## 2026-11-08 — Winners run to 15% from the 30 Nov rebalance

- Until now every monthly rebalance put each holding back to 5% of the book, selling part of a winner and topping up a laggard. From the 30 Nov 2026 rebalance a holding that stays keeps the weight its price gave it, cut back only above 15%; the money from sales and cuts buys the new names in equal parts, and no industry is above 40% after a rebalance. Tested first: on the Nifty 500 from 2010 the reset earned 18.8% a year and letting winners run 18.2%; from February to October 2026, +38.6% against +45.5%. Months before the change keep the old rule and their figures.

## 2026-11-08 — The data line on the Screener only

- The line of data dates and counts at the foot of the page (prices, market caps, all-time highs, gap-filled and short-history counts, where the data came from) now shows on the Screener only. Other pages keep the copyright; the header's price chip still gives the closes' date.

## 2026-11-08 — Dashboard: coming up for the book

- A new card under Next rebalance lists the holdings' and planned buys' board meetings for the next five weeks, by day, from NSE's board-meeting calendar, with the rebalance check in its place: "3 holdings report before the 30 Nov check; 17 of 20 have reported this season". Collected nightly; dates are as companies announced them.

## 2026-11-08 — Dashboard: how many stocks qualify, and the next rebalance's churn

- A new card shows the share of the Nifty 500 passing the strategy's own filters at each month-end, with how our strategy's backtest did against the Nifty 500 in the months that followed few qualifiers since 2010: after the fewest (27% or less) the portfolio trailed the index by 0.8 pts a month on average, against a 1.2-pt lead after the rest, and the pattern held in each five-year block. At the end of September: 20%, fewer than in 87% of month-ends.
- The monthly momentum job now also writes the strategy's own monthly return and the Nifty 500's beside momentum's, so the Dashboard's evidence is about the book, not only the momentum factor.
- Next rebalance now says how many holdings would change against the record's monthly average (2 of 20 against 8).

## 2026-11-08 — Dashboard: how risky is the book?

- A new card under Book at risk describes the whole book: its beta and volatility against the Nifty 500, how much of it is in small and micro caps (90% today), its drawdown from the record's peak beside the index's over the same dates, and how quickly each position could be sold at the model book's size.

## 2026-11-08 — Dashboard: which sectors lead, and is leadership changing?

- The Dashboard answers "Which sectors lead?" and "Is leadership changing?" from NSE's own sector indices (Bank, IT, Pharma, Auto, FMCG, Metal, Realty, Media, PSU Bank, Financial Services, PSE, Energy, Infrastructure): each index's return against the Nifty 500 over three months and over the last month. They replace "What is leading?" once the nightly index job has collected the sector indices. A relative rotation graph was tried first and not used: it agreed with StockCharts' weekly India RRG on 64% of indices, below the 80% bar set.

## 2026-11-08 — Dashboard: links to its sections

- The Dashboard now opens with a line of links to its sections, as the Breadth page does: the three market questions, Book at risk, Next rebalance, Momentum health, Size leadership and Flows. A section left out for missing data gets no link.

## 2026-11-08 — Alpha in points; the sector map picks out the leader and laggard

- Alpha, the strategy's return less the index's, now reads in points ("+8.3 pts") on Backtest, Portfolio and the record, so it is not read as a percentage of the index's return. Returns stay in %.
- The sector leadership map draws every sector in grey and picks out the leader in blue and the laggard in rust; the sector you tap turns ink.
- paresh.streamlit.app/home showed "Page not found" over the Dashboard; it now opens the Dashboard.
- Every section now starts the same distance below what comes before it (it ranged from 11 to 44 px), and Portfolio's "Since inception" figure carries a small line of the book's record, as the Dashboard's index figures do.

## 2026-11-08 — SS prices: 3 s between requests, no rests

- The nightly SS download now waits at least 3 s between requests and no longer rests 5 minutes every 40 stocks, as SS's owner said is enough. The run should take about 75 minutes instead of about four and a half hours; the prices and their checks are unchanged.

## 2026-11-08 — Price history: INFIBEAM's 2025 rights issue

- INFIBEAM's rights issue of 26 Jun 2025 (67 for 267 at Rs 10) is now adjusted at its real issue price. NSE's list stated face value Rs 10 on that one row instead of Re 1, so the issue read as Rs 19 and the ex-date showed a -15.7% fall the holder did not have; it now shows -7.7%, as MarketLens and SS (-7.6%). The rule: a rights issue's face value must agree with the stock's history unless a split or consolidation came between. Shows after the next long-file rebuild.

## 2026-11-08 — Flows from NSDL's record, back to 2016

- The Flows panel now draws foreign investors' equity flows from NSDL's confirmed FPI record (custodians' reports), backfilled from January 2016 and added to each weekday: the last 20 reporting days' total, the last 12 months as monthly bars. To 6 Nov 2026: +Rs 35,410 Cr over 20 days, -Rs 2,78,785 Cr over 12 months. Checked: 2024 sums to Rs 427 Cr and 2023 to Rs 1.71 lakh Cr, as NSDL's published annual figures (BDO India, Jan 2025). Domestic institutions (DII) come from NSE's daily figures from 6 Nov 2026, shown once five sessions are in.
- Price history: three renames that were 1:10 consolidations at an ISIN change are now joined (NANDAN, SEINVEST, SIGNET), with NSE's evidence in `notes.json`; the long file picks them up at its next rebuild.

## 2026-11-08 — Flows: the trend, not one day

- The Flows panel no longer leads with a single day's FII and DII figures (owner: one day's flow is misleading). Until five sessions are collected it says how many are in and lists them small; from five it leads with the total over the last 20 sessions (or all of them, while fewer) with a bar for each day. NSE and MSEI publish only the latest day, so the history grows from 6 Nov 2026; the daily job now also records whether GitHub's runner can reach NSDL, whose FPI record goes back years.

## 2026-11-08 — Screener: no blank space after "Show all"

- On a phone, "Show all" turned the table into a box of about 1,900 px that scrolled inside the scrolling page; a swipe moved the page rather than the box, and the end of the list showed blank space (owner, 8 Nov). "Show all" is now a button under the table that redraws it at its full height, so only the page scrolls; "Show first 50" goes back.
- pyarrow is pinned back to 24.0.0: Streamlit Cloud replaces 26.0.0 with a version below 25 at every start (apache/arrow#50471), so production was running 24 regardless. The combination it runs (pyarrow 24 with pandas 3.1.0, numpy 2.5.4, streamlit 1.66.1) was checked: suite, audit baseline and parity unchanged.
- The NSE price join no longer fragments its frame (a pandas warning on every load).

## 2026-11-07 — Screener frame lighter

- The Screener's 60-day lines are sent as a short list of heights and drawn in the browser, the rows on screen first: the table's frame is 2.0 MB instead of 2.4 MB, and the lines look the same (audit F62).
- Momentum health reads "42nd percentile", not "42th".

## 2026-11-07 — Dashboard: momentum health and flows

- **Momentum health**: how momentum itself has been paying. Each month-end the Nifty 500's members are ranked by this site's score, and the next month's return of the top fifth minus the bottom fifth is that month's spread. The panel shows the last 12 months' sum (+8.9 points to October 2026), its percentile since 2010 (42nd, about usual), the last 24 months as bars, and a flag in a crash month. Checked against IIM Ahmedabad's independent Indian momentum factor: correlation 0.83 month by month, Feb 2010 to Dec 2025 (`docs/MOMENTUM_HEALTH.md`). Rebuilt monthly by a checked job.
- **Flows**: NSE's provisional FII/FPI and DII cash-market net buying for the day, collected each trading evening by a checked job. NSE keeps no history of these, so the record starts on 6 Nov 2026 and grows from there.

## 2026-11-07 — Screener: where each stock stands against the book

- New columns: **Qualified #** (place among the stocks that pass both filters, the list the model book buys from, the same number Actions uses) and, in Full Quant, **Score** (the composite the ranking is sorted by).
- Stocks in the model book carry a **Held** tag. In rank order, lines mark the 20th qualified stock (the book buys the top 20) and the 40th (it keeps a holding while in the top 40).
- A failed filter says by how much: "✗ −8.7%" below the 50D EMA, "✗ −22%" below the 52W high (the filter is within 20%).
- "High volume" is now **Volume spike**: it was always one day's volume at 1.5x its 20-day average. One caption under the chips explains them.

## 2026-11-07 — Fonts served by the site

- IBM Plex Sans, IBM Plex Mono and Source Serif 4 are now served from the site itself (`static/fonts`, SIL Open Font Licence) instead of Google Fonts. A page and its chart frames made about 9 requests to Google per visit; now none. Text looks the same. This does not lower the server's memory: the font files (377 KB, Latin and Latin Extended) are cached by the browser after the first visit (audit F61).

## 2026-11-07 — Library updates

- streamlit 1.66.1, pandas 3.1.0, numpy 2.5.4, pyarrow 26.0.0, and the last workflow still on older GitHub Actions moved to checkout/setup-python/upload-artifact v7 (owner). Nothing a reader sees changes: on the same pinned inputs the 750 ranking, the 12-month backtest and the track-record parity report are identical, and eight pages screenshot pixel-identical.
- From the earlier audit (#471): Portfolio, Backtest and Actions no longer rebuild the NSE price frame on every visit (about 2-3x faster locally, numbers identical); two scheduled data jobs that never succeeded are manual only; NSE's daily files are collected on trading-day evenings and weekend sessions are picked up; the full validation runs daily; the Total Market check follows NSE's own list.
- The monthly freeze now checks that the app can rank with the NSE closes it has just written before it freezes or commits anything (S82).

## 2026-11-07 — Portfolio: a ₹1 crore model book

- The model book on Portfolio now starts at ₹1 crore instead of ₹20 lakh (owner, 7 Nov). Every return is unchanged (since inception +41.4%, November +2.3%); rupee figures are five times larger and share counts are whole shares of the larger book. The Kite basket on Actions starts at the same ₹1 crore.
- Fixed: Portfolio sized the current book on the account at the month-end before the fill, not at the fill, which left out the old book's last day and the fill's trading costs. At ₹1 crore that read as cash of −₹34,041; at ₹20 lakh, rounding down to whole shares hid it. The book is now sized on the account at the fill (today's ledger value over the book's growth since the fill), so cash is only the rounding left over: ₹19,065.

## 2026-11-07 — Screener opens on Full Quant

- The Screener's Columns control now starts on Full Quant (every column) on desktop and phone, instead of Core. On a phone the table keeps Rank and Symbol fixed and scrolls sideways. Executive and Core are one tap away; a link with `cols=core` or `cols=exec` still opens those.

## 2026-11-07 — Chart pages load faster

- Every chart frame used to carry its own copy of the chart library, 0.2 to 0.5 MB each, never cached. The libraries are now served once from the app (`static/`) and cached by the browser, with a pinned copy from jsDelivr if that address does not load (audit F60).

## 2026-11-07 — Size against the Nifty 500 on the same dates

- "What is leading?" compared each size index with the Nifty 500 up to each series' own last close. While the nightly index file is still weekly it ends earlier than the Nifty 500, so the two windows differed: the live site read Microcap 250 +7.0 points over six months against +3.7 on the same dates. Both now end on the size index's last close.

## 2026-11-07 — Breadth: the charts behind each answer

- Sectors: under the four groups, every industry as a bar for its six months against the Nifty 500 with a ring for the last month, so the groups can be seen at a glance.

- Under each question, "Behind the answer": two charts, each headed by a sentence saying what it shows. Taking part: the Nifty 500 above the share of stocks above their 200D EMA on one time axis, and net new 52W highs week by week. Uptrend: the Nifty 500's month-end closes against its 10-month average, and each size index against the Nifty 500 over the year.
- Fixed: net new 52W highs counted a stock once for every day it set a high in the week (bars reached +140%); each stock now counts once. This week reads +2.3% of stocks, not +8.5%, and votes "between", not "broad".

## 2026-11-07 — Editorial type on every page

- The Dashboard has a strip of the indices under its headline: the Nifty 500, Nifty 50, Midcap 150, Smallcap 250 and Microcap 250, each with the day's move, its last three months as a line and its move over a month, from NSE's index closes. On 6 Nov the day's moves match tipsheet's own strip to within 0.03 points (theirs is total return).

- Rolled out on the owner's word after the prototype: page titles, section and card headings, verdicts, headline figures in tiles, the stock page's name, price and rank, the Guide's and Configuration's headings and the calendar years are in Source Serif 4; the Guide's text is 16px.

## 2026-11-07 — Editorial type, prototype on the Dashboard and Breadth

- A serif (Source Serif 4) for page titles, question headings, verdicts and headline figures, prose at 17px in a reading column; Plex Sans stays for text and Plex Mono for dense tables. Only the Dashboard and Breadth use it until the owner has seen it.
- The Dashboard opens with the month's news as its title: "The book rose 2.3% this month; the Nifty 500 rose 7.1%", the risk and the next rebalance beneath.
- Breadth's evidence rows show where today sits in the measure's own history: a bar from the lowest to the highest reading, the middle half shaded, today's percentile and the year-ago reading under the figure.
- Fixed: net new 52W highs and the year-long measures had no year-ago reading on the app's deep price history, which holds fewer rows a year in its early years; the 52 weeks are now a calendar window, a reading needs enough stocks behind it, and a missing day takes each stock's last price that week.

## 2026-11-07 — Sentence case; column headings on Sectors' groups

- Labels, card notes, tile notes and captions start with a capital everywhere ("Least room first", "Held since 2 Nov", "Today · A month ago"), set once in the shared components.
- Sectors' four industry groups have column headings (Industry; 6M · 1M, pts) and a line saying what the figures are.

## 2026-11-07 — Sectors answers "What is leading?"

- Sectors opens with the answer: the size index furthest ahead over six months, and the industries ahead over both six months and one month; then the size indices against the Nifty 500 (6 months, 1 month).
- Industries in four groups: ahead on both, gaining (ahead over the month only), fading (ahead over six months only), behind on both, each with its two figures.
- Month by month against the Nifty 500: each industry's median stock less the index, for the last 12 completed months and the month so far, shaded by size, with its current run ("4 behind") and its 12-month total; the longest current run is named above it.
- What would change the answer: the industries nearest to moving ahead over six months, and those nearest to falling behind.
- The leaderboard, the stocks of one industry and the leadership map follow. The four figure tiles that repeated the leaderboard are gone.

## 2026-11-07 — Breadth answers two questions

- Market breadth now opens with "Are most stocks taking part?" and "Is the market in an uptrend?". Each has its verdict, the scale (today, a month ago, a year ago), what has changed over the month, what would change the answer (the measures one step from another verdict, with the reading each would need), and the evidence with every cut-off written out.
- The trend section ends with the size indices side by side: the Nifty 500, Nifty 50, Midcap 150, Smallcap 250 and Microcap 250 against their 10-month average and 200D EMA, and their distance from the 52W high, a month ago and now.
- Today's charts follow, with their period and settings beside the heading. The figure tiles that repeated the evidence are gone.

## 2026-11-07 — Owner's answers: Screener paging, menu groups, page width

- The Screener shows the first 50 rows and a "Show all 750" button. The mouse wheel over the table now scrolls the page (it scrolled the table inside its frame). Every row stays in the table, so a click on a header sorts all 750 and the first 50 of that order show.
- The menu is grouped by what you are doing: My book (Dashboard, Portfolio, Actions, Watchlist), Market (Screener, Sectors, RRG, Market Breadth), Method (Backtest, Configuration, Guide).
- Pages are at most 1,240px wide, centred, on wide screens; phones get a 16px margin each side (was 8px).
- Kept as they are, by the owner: "Personal" as the price source's name, alpha in %, the 20 soft sector colours on the leadership map.

## 2026-11-07 — Dashboard answers three questions about the market

- "Are most stocks taking part?", "Is the market in an uptrend?" and "What is leading?" sit under the book's line, tipsheet's question pages as the model and the app's own data as the source.
- Each gives a verdict in a word or two, one sentence, a five-band scale marking today, a month ago and a year ago, and the measures that vote: now, a year ago, the vote in words, the cut-off on hover. Primary measures count twice.
- Breadth: stocks above their 200D and 50D EMA, stocks ahead of the Nifty 500 over a year, net new 52W highs this week, the median stock against the index. Trend: the Nifty 500 against its 10-month average (completed months) and its 200D EMA, its distance from the 52W high, the 10-month rule for the Nifty 50, Midcap 150, Smallcap 250 and Microcap 250, and the share of stocks above their 200D EMA. Leading: the size index furthest ahead over six months, and NSE industries grouped by six months and one month against the Nifty 500.
- On 6 Nov the trend reads "No clear trend", as tipsheet's independent page does, and 45% of stocks beat the Nifty 500 over the year (tipsheet: 43%).
- No forward returns or "what history says": the store does not reach back far enough to test them, and the site makes no outcome claims. A past verdict shows only when most of its measures can be read that far back.
- The industries list that sat lower on the Dashboard is folded into "What is leading?".

## 2026-11-07 — No repeated blocks (owner's decision 5)

- The data-freshness line at the foot of each page is plain text instead of four pills, with no emoji; a late source still leads, in amber.
- Figures outside the dense tables (tiles, chart legends, bars, lists, the stock page) are in Plex Sans with even-width digits; Plex Mono stays in the Screener and other dense tables (owner's decision 4). The small figure rows under charts now match the headline tiles: sentence-case labels, centred.
- Watchlist: an empty list says so in a plain line, not a blue alert box.
- A first click on a figure's column header sorts it largest first; Rank still starts from 1.
- The Screener table fades at its right edge while more columns lie to the right, and the pointer shows a row opens its stock.
- Breadth's list of new highs and lows reads "New 52W high" and "New 52W low" without emoji; the rotation graph's quadrant lists lose their tinted cards.
- Levels and shares in tables (weight, turnover, % of the 52W high) no longer carry a plus sign; changes (drift, distance from the EMA) still do.
- Trading costs are worded one way everywhere: "30 bps a round trip", charged on one-way turnover (the settings, the Tested line, Method, the export and the Guide).
- Backtest's Sharpe says its basis: daily returns, annualised, over the 6.5% risk-free rate.
- Portfolio's "Three systems, side by side" reads like the calendar grid: monthly figures right-aligned and coloured by sign, dashes aligned with them. Any table column of ready-made percentages now does the same.
- No text below 12px anywhere (labels at 8.5–11.5px were raised), and near-duplicate sizes folded together (13→13.5, 14.5→14, 16→15, 19→18).
- Readers whose system asks for less motion get no transitions or animations.
- Share prices carry paise everywhere: the Screener's price and stop-loss columns and every level on the stock page (₹2,340.00, 52W high ₹2,406.00).
- Plain counts are no longer coloured as warnings: Actions' Hold count, Breadth's share in the neutral band and Configuration's possible demergers read in ink; Sell and Buy keep their colours.
- Chart date axes show month names only ("Jun · Jul · Aug"), with the year at the turn of the year; day ticks appear only on charts shorter than about ten weeks.
- The stock chart's price axis and legend read in rupees with paise (₹2,340.00), grouped the Indian way.
- Only the font weights the site loads are used (400–700); 650, 750 and 800 were being faked by the browser.

- Sectors: one ranking and one map. The industry bubble map (it repeated the leaderboard) and the sortable sector table under the leadership map (a second ranking of the same sectors) are gone; the map's figures are in its text alternative and worked example. The leaderboard loses its box.
- Backtest: research runs only. The live account, today's book and this month's changes are no longer repeated there; a line points to Portfolio.

## 2026-11-07 — Names, Actions, emoji

- One name for the 52-week measure: "From 52W high" for the distance and "Near 52W high" for the filter, on the Screener, Sectors and in the header; "50D EMA" in Screener headings.
- A holding close to its 50D EMA reads "can fall 2.8% to its 50D EMA", the same figure as its cushion; it read "2.9% above" beside "2.8% cushion".
- "Leading" is kept for the rotation graph: Sectors' first figure is "Top industry" and the Dashboard's list is "Industries by 3M median return".
- Actions: the sell, buy and hold lists are open rows with the status as a coloured word, read as tables by screen readers; a negative return in the buy list is no longer drawn in blue.
- No emoji in tables: Bought, Sold, Held, Yes, No and the rotation quadrants are plain words.
- Industry names under a stock wrap instead of being cut mid-word.
- The Guide says the Kite basket holds the buys only; sells are placed by hand.
- Every other table (Portfolio's book, Configuration, Backtest's trades and the rest) is drawn like the Screener's: no box, a rule above, white headings, hairline rows; status badges are coloured words; a text column's heading sits over its text.
- The Screener's filters (preset, indices, pass-both, columns) are kept in the address, so Back from a stock page returns to the same filtered list, and a filtered list can be bookmarked or shared.
- On touch screens stock links and small controls (the × on a chosen index, the ? help icons) are easier to hit: 38–44px instead of 15–22px.
- On a phone or tablet the header (name, date, menu) stays at the top as the page scrolls, and the menu fits the screen.
- Dashboard blocks link onward: the book at risk and the next rebalance to Actions, the industries to Sectors.
- The Screener's search list reads "LAURUSLABS · Healthcare" and "Healthcare · industry", not "[STOCK]" and "[INDUSTRY]".

## 2026-11-07 — Keyboard and contrast

- A "Skip to content" link is the first stop for the keyboard on every page; it jumps past the header and market line.
- Every link, button, tab and slider shows a 2px ink ring when focused by keyboard.
- The faint grey used for small text is darker (#70706B): 5.0:1 on white, up from 3.5:1. A test keeps every text colour at 4.5:1 or better.
- The stale-prices warning no longer starts with an emoji.

## 2026-11-07 — One figure tile, one minus, no part-year annualising

- Every row of headline figures (Portfolio, Backtest, Actions, Sectors, Configuration and the rest) is drawn the same way: between two hairlines, cells split by a hairline, centred, no boxes or shadows.
- Configuration and Backtest's settings line lose their rounded boxes and tinted panels; the score-weight bar is shades of ink, not indigo. Corners are 4px everywhere and decorative shadows are gone.
- Every negative figure uses a true minus (−8.4%, not -8.4%), including Portfolio's P&L tiles, Backtest's figures and the Sectors worked example.
- The stock page drops its rounded cards and tinted verdict panel for the same open, ruled layout as the rest of the site; figures in Plex Sans.
- Calendar returns (Portfolio, Backtest) in the same open style: no box, shadow, gradient or indigo, and no text below 12px.
- Dates read "6 Nov", not "06 Nov", everywhere.
- Backtest shows no annualised return for a window under a year ("needs 12 months; this is 10 months") instead of scaling a part-year up.

## 2026-11-07 — Guide rewritten

- One reading column with plain headings and formulas as text; no tabs, boxes or marketing headings. Every statement checked against the code, including the record's caps (5% a stock, 40% an industry, at most 8 of 20 from one industry), which the old Guide left out.
- Removed: the "market regime playbooks". They gave equity and cash allocations (100%, 85%, 70%, 40%) that the model never applies; the model holds 20 stocks in every market. Also removed: the claim that inverse volatility cuts drawdown, and quadrant colours that no longer match the graph.
- Moved here from the Guide, what was taken out of the engine earlier and why: single-window Sharpe, multi-window pure Sharpe, exponential regression, residual alpha, industry-relative and momentum acceleration scores (none fed the rank, each added columns and failure modes); mean-variance optimisation (it fell back to equal weight on any error while still calling itself MVO); R-squared (never part of the score).

## 2026-11-07 — Screen readers: tables and charts

- The book at risk, the exit watch, the movers cards and the industry leaderboard read as tables to a screen reader (row by row, with column names). They look the same.
- Every chart says what it shows in words: each line's first and last value with dates, its low and high; the rotation graph's industries by quadrant; the most and least alike holdings; each industry and sector with its figures.
- Chart legends group rupees the Indian way (₹28,27,942) and write a minus as −, like the rest of the site; dates read "Sep" and "6 Oct".
- Portfolio's chart ended ₹1 below the value above it (₹28,27,941 against ₹28,27,942): today's point is now the account value itself.

## 2026-11-07 — One ranking everywhere

- Every rank on the site comes from the Screener's ranking (owner). Portfolio's "Ranks by month" now scores each date's index members only, as the Screener does, so a stock has the same qualified rank on every page (ACUTAAS 45th, not 44th).
- The model follows the same rule from the 30 Nov 2026 rebalance. Months already in the record are unchanged; had the rule applied from the start, two of eleven books would have differed by one stock.
- Stock links open the stock page directly, so Back returns to the page you came from; each browser tab names its page; the alpha caption says what alpha is (a difference, not compounded).

## 2026-11-07 — Dashboard home page; charts in the tipsheet style

- The site opens on a Dashboard (the Screener moves to /screener and second in the menu). One line says how the book is doing this month against the Nifty 500, how many holdings are close to a rule or would be sold, and when the next rebalance is. Below it: the book at risk (least room first, each with its nearest rule), the next rebalance if the month ended today (the same plan as Actions), size leadership and the five leading industries (as ranked on Sectors).
- Size leadership: Nifty 50, Midcap 150, Smallcap 250 and Microcap 250 against the Nifty 500 over 1, 3 and 6 months, from NSE's index closes (the nightly index file on R2). Shown only when that file's Nifty 50 equals NSE's own daily close; otherwise the page says why it is left out.
- Charts: a one-line legend above the plot, a faint horizontal grid only, small grey axis labels, sparse dates, thin lines with a dot on the latest point, a flat pale fill for drawdowns, white tooltips. No figure changed.
- Fixed: the caution colour (amber) was invisible everywhere for a few hours after the theme moved to one file.

## 2026-11-07 — New look: Paper B · Ledger, white ground

- The owner chose "Paper B · Ledger" on a white ground. Every page now uses IBM Plex Sans, with IBM Plex Mono for figures, ink on white, and neutral greys with no warm tint.
- Up is blue and down is rust, always with + or −. Selection and the active page are ink, so blue only ever means up. The old green, red and indigo are gone everywhere they were used, including charts.
- Cards are thin rules, not boxes: no shadows, square corners, chips at 4px. The Screener table drops its zebra stripes and its rows are 36px on desktop (44px on a phone, for touch).
- The theme now lives in one file, `src/ui/tokens.py`: every colour and font, by name. Change a value there and the whole site follows, the Screener table and the charts included.
- Navigation is the menu button (☰) on every screen, in its old style (Research, Monitoring, System); the row of page links on desktop is gone.
- The dashboard home page is designed but not built yet.

## 2026-11-07 — Five figures that disagreed or misled, corrected

- Actions, Hold: the order was right but looked wrong (PVRINOX above LAURUSLABS though its EMA cushion is larger). Holds are ordered by the least room on any rule, with a full rank buffer of 40 places counted as a 20% fall, as the bars are drawn; PVRINOX's 24 places count as 12.0%, under LAURUSLABS's 12.6%. Every row now names its nearest rule ("rank buffer · 24 places") instead of "clear of all three", and a caption states the scale.
- Backtest, current book: "MTD return" showed +3.2% "by weight" against Portfolio's +2.3% for the same book. It averaged today's holdings and left out the 9 stocks sold on 2 Nov and the rebalance costs. It now shows the account's figure, the same one as Portfolio.
- Portfolio: the "Max drawdown" card (−13.5%) is labelled "daily"; the −9.9% under the calendar is on month-end values. Both are right; each now names its basis.
- Configuration: "Price History: Missing" is gone. The app ranks from the published price store, not that file; the table no longer shows server paths.
- Guide: no longer claims a liquidity filter (the floor is off) or that a weighting "maximises upside" or "minimises drawdowns"; the formulas read as text, not raw LaTeX.

## 2026-11-07 — Screener: headers over the right columns, one sort, clearer colours and phone list

- The group labels above the table sit over their own columns. In Core and Executive "3M" covered 3M and 6M returns and "12M" sat over the 3-month drawdown; these views now group the columns as Returns and Risk. In Full Quant, "Rank dynamics" no longer sticks over Symbol when the table scrolls sideways.
- The block under the table is headed "Since 6 Oct (one month)" (the session the 1M rank change counts from), not "Since last month-end", which it never measured.
- The column headers are the only way to sort: the "Sort by" buttons in Filters & sort are gone. Big movers opens sorted by rank change, and its header says so. Export CSV says the file is in rank order (rank-change order for Big movers).
- Colour follows one rule. Returns, Sharpe, % from the 50 EMA and rank changes are green above zero and red below, always with + or −. Drawdowns and % below a high are plain. A negative Sharpe used to show green. Every minus is a true minus, a stock at its high reads "New high", and pass/fail is ✓ / ✗ instead of coloured dots.
- On a phone the preset chips and the market strip fade at the right edge to show they scroll, the line under each symbol is its industry, and the trend column is headed 60D. The strip no longer puts a red tint behind "Bullish" and "3.1% above".

## 2026-10-15 — A nightly ranking that fails is no longer silent

- On 14 Oct the nightly job could not build the 750 and Combined rankings (the same error that took the site down), but it still showed green and published the 13 Oct ranking again. The app then computed the ranking itself on every fresh start on 15 Oct, which is why memory and CPU stayed high. A manual run on the fixed code published all three rankings on 14 Oct prices at 11:39 UTC.
- Now a ranking that cannot be built is not republished from the day before, and the nightly job fails at its last step (after everything else is published), so the failure alert fires.

## 2026-10-15 — RRG: a wider chart you swipe on a phone; names stay inside the chart

- On a phone the Relative rotation chart is now drawn 760 px wide and 600 px tall and opens on the 100 / 100 crossing; swipe it sideways to reach every quadrant (owner: "larger chart, I will slide the page"). Swiping up or down still scrolls the page. Before, it was squeezed into the screen width with names cut off and overlapping.
- An industry's name stays inside the chart: near the right edge it sits on the dot's left. On desktop this brings back Media Entertainment (cut off) and Oil Gas (hidden).
- Quadrant titles are smaller and in the far corners, out of the way of the dots.
- A finger drag no longer zooms the chart.

## 2026-10-15 — Site down on 14-15 Oct: one new listing's prices; fixed, and a new store is now checked before it goes live

- From 22:35 UTC on 14 Oct every page failed with "Encountered all NA values". That night's Screener update gave TRIVENIPT (Triveni Power Transmission, listed after its demerger) its first close, on 14 Oct; NSE's only close for it is on 12 Oct. The check that compares NSE's prices with Screener's before NSE fills a gap had no shared day to compare, and raised. No price was wrong.
- A stock the two sources share no day for is now left out of the NSE fill, so it keeps Screener's own closes. For every other stock the price frame is identical, cell for cell (checked on the 14 Oct store: 1,199 stocks).
- The NSE fill is optional. If it ever raises again, the ranking goes ahead on Screener's prices, says so in its notes, and logs the error, instead of failing every page.
- The nightly Screener job now runs the app's own price shaping on the new store before publishing it. If that fails, neither copy is published: the site keeps the last good prices and the failure alert fires. Run on the 14 Oct store with the old code, it refuses the store with the same error.

## 2026-10-13 — Long file rebuilt in full every Saturday; old BSE copies trimmed to two

- The Saturday long-file build now reads every session and corporate-action day from R2 again every week, not only on the second Saturday (owner). Each build adjusts NSE's raw closes from scratch, with every action counted once, so a full rebuild cannot apply an adjustment twice.
- R2 keeps the newest two copies of BSE's daily table (`bse/daily`, one a month, each the whole history) and deletes older ones (owner). Today there is one copy, so nothing is deleted before December. The table stays protected otherwise: it can never go below two copies or be retired.

## 2026-10-13 — About 85 MB less memory at peak

- The app now has pyarrow use the system allocator. With four readers at once, Portfolio peaked at 877 - 929 MB instead of 960 - 1,001 MB, and Backtest at 801 - 840 MB instead of 858 - 936 MB (three runs each). What every page shows is unchanged.

## 2026-10-13 — Nano Cap and Combined: daily prices over Screener's weekly stretch

- Screener's history before Sep 2025 is one close a week. For the 750 those weeks have been filled with NSE's daily moves since 7 Oct; Nano Cap and Combined stayed weekly, because NSE's committed file held most Nano Cap stocks only from Oct 2026. They are now filled the same way (owner: "do it"): 362 of 362 Nano Cap stocks and 1,061 of 1,061 in Combined, 106 sessions added. Every Screener close stays as it is, and a week where NSE's move differs from Screener's by more than 2% stays weekly (38 weeks, all thin trading or a close a few paise apart, none a missed split).
- Checked against independent references: of the 66,576 filled days a reference covers, 66,575 agree within 2% with at least one (SS 99.99%, TejHQ 99.98%, eod2 99.99%, Tijori 99.80%, Yahoo 99.37%); the one left is RAYMOND's demerger ex-date. 1,352 days come from BSE before a stock listed on NSE (ADVAIT, JAYKAY, SHUKRAPHAR and nine more), which no reference covers.
- The 750's frame is unchanged, cell for cell. A stock that joins the Nano Cap list later is added by the daily sync, with no hand step.

## 2026-10-13 — Yahoo removed: no code downloads from it, `yfinance` is no longer a dependency

- Owner, 13 Oct: "Yahoo removal: remove it" (TODO S10). Nothing the app shows changes: the ranking, backtest, track record and benchmark already came from Screener, NSE and `data/benchmarks.csv` (since 2 Oct).
- Removed: `yfinance` from `requirements.txt`; the Yahoo downloader and its price cache in `price_loader.py` (`fetch_price_history` and its helpers) and the snapshot seeding behind it (`price_store.py`); the Nano Cap Yahoo download (`extra_universe_loader.download`/`load_prices`, `scripts/sync_extra_yahoo.py`); the raw Yahoo R2 build (`r2/raw/yahoo.py`, `scripts/r2_build_yahoo_raw.py`, `r2_yahoo_raw_build.yml`, `r2_yahoo_raw_retry.yml`); two research scripts that downloaded ten years from Yahoo and their workflow (`v1_hypothesis_backtest.py`, `v1_recent6m_monthstart.py`, `v1-recent6m-monthstart.yml`).
- `scripts/build_nse_index_prices.py` keeps NSE Indices' own history first and Screener's index chart second; the Yahoo fallback between them is gone. `scripts/full_validation.py` ranks the frame production ranks (`price_source.ranking_frames`).
- Kept: `extract_ohlcv`, the benchmark and market-regime readers, and Yahoo as a stored audit reference (`reference/yahoo_close` on R2, read by `scripts/audit_long_prices.py`).

## 2026-10-13 — The long price file keeps itself up to date, and its audits can fail it (S47)

- NSE's yearly corporate-action list is imported every month (the 2nd, 21:13 UTC), last year and this year, instead of by hand (last done 2 Oct).
- Once a month (the second Saturday) the long-file build reads every session and corporate-action day from R2 again instead of only the new ones, so a file revised after it was first read is picked up.
- The audits now fail their job when a finding is worse than today's known count: a new fake move, a new level break where ours moved, a lost session, a new unpriced stock (`scripts/audit_limits.py`, each limit named with the run it comes from). The file is still published and the report uploaded first. The history audit runs monthly (the 3rd) with these limits.
- A failed scheduled import or history audit opens an issue, as the long-file build already did.

## 2026-10-13 — Sector map: how to read it, 1M or 3M, the heavy lifters; Big movers means big

- Under the Sector leadership map, **How to read this** works one sector through with its own numbers: its stocks' average move against the Nifty 500 over the same closes (across), how many of its stocks are above their EMA (up), and what the line's direction means. It uses the sector you pick, else the first that beat the index on narrow breadth.
- The map's controls are pill buttons like the Rank by row at the top of Sectors (EMA: 20/50/100/200; period: **1M** or **3M**). 3M puts the hollow dot three months back, for the slower trend underneath.
- Each sector names the two stocks doing the heavy lifting, in the table (under the sector's name) and the chart's tooltip. With equal weight each stock adds its return ÷ the number of stocks, so the two largest returns are the two largest contributions.
- Screener: **Big movers** is a rank move of 150 places or more in a month (about 118 stocks today), not 15 (630 of 750) (owner).
- Backtest: shorter price and download notes.

## 2026-10-13 — Sectors: 6M, Share passing and Top-50 count change the whole page

- The Rank by buttons re-sorted only the leaderboard further down; the tiles (Leading, Rising, Weakest) and the Industry map always read the 3-month median, so on a phone nothing visible changed. They now follow the choice: with 6M median, Services leads (+17.9% in 6 months), 12 of 20 industries are rising and the map runs on the 6-month median. The subtitle names the measure.
- Actions counted sessions to the next rebalance as weekdays: "14 sessions away" from 12 Oct, though NSE is shut on Tuesday 20 Oct (Dussehra). It now reads NSE's published holiday list (`data/reference/nse/holidays.csv`, from NSE's holiday master, via `nse_calendar.published_holidays`): 13 sessions. The check and fill dates skip holidays too (31 Mar 2026, Mahavir Jayanti, would have moved March's check to the 30th).
- The figures themselves were right: each industry's 3M and 6M median equals the same median computed from NSE's own closes over the same window (13 Jul and 13 Apr to 12 Oct).

## 2026-10-13 — /screener opens the Screener

- Typing or bookmarking the address `/screener` showed "Page not found" before the Screener loaded. It now opens the Screener directly.

## 2026-10-13 — Backtest: download the rules and every trade

- The Backtest tab (Live and History from 2010) has a Download card under the calendar returns: one ZIP of two CSV files. `backtest_trades.csv` has every position, closed or still open, in entry order, with sector, signal and fill dates, entry rank and weight, exit rank and reason, mark for open trades, holding days and price return. `backtest_rules.csv` has the run's entry, exit, timing, sizing and cost rules, the price basis, how much of the run used point-in-time membership, and what each trade column means. It is written from the settings of the run itself.
- The trade records gain sector, signal dates and entry rank, weight and exit rank (`closed_trades` in `backtester.py`); nothing already on the page changes.
- The History tab's price caption said "no dividends"; the long file has taken out dividends of 10% or more since #370, so it now says so.

## 2026-10-13 — Less empty space, fewer cramped boxes

- The figure strip under each page's title (Sectors, Actions, Breadth, Portfolio, Backtest) fills the row however many figures it has. It was a fixed six columns, so four figures left two empty columns and long industry names wrapped onto four lines. Names now read smaller, at most two lines; on a phone the figures sit two to a row.
- Screener: Biggest jumps, Entered top 50 and Left top 50 sit side by side on a wide screen, compact (about 1,000px shorter).
- Figure boxes inside cards (Portfolio's month, alpha, drawdown; Backtest): values read at their intended size and the boxes are as tall as their text (74px, was 104px). A page-wide paragraph style had shrunk every value to 14px grey.
- Portfolio: industry exposure runs in two columns; "How they move together" is a collapsed section, like Actions' Buy candidates, with the average in its heading.
- Sectors leadership map: one soft colour per sector, the same on every EMA tab, instead of green and red; a one-line intro; its table is drawn like "Stocks in an industry" (sortable headers, each sector's map colour as a dot, today and a month ago grouped; on a phone, short names and today's columns).

## 2026-10-13 — The track record keeps January and February 2026 as frozen

- The owner keeps the 750's frozen January (-0.21%) and February (+0.70%) 2026 months, though today's replay, after the rights-issue fix (S56), gives +0.00% and +0.80%. The parity gate now lists these two as accepted (`src/engine/parity_accepted_drift.json`) and passes; any other drift, or a further move in these two, still fails it.

## 2026-10-13 — Sectors: a leadership map, a month ago and today

- At the bottom of **Sectors**, each NSE industry (of the 750) is a line from a hollow dot (a month ago) to a filled dot (today). Across: the industry's 1-month return less the Nifty 500's. Up: the share of its stocks above their EMA, in tabs for the 20, 50, 100 and 200-day EMA. It shows a sector beating the index while most of its stocks fall.
- Pick a sector above the map, or tap it, to dim the rest. A table under the map gives each figure as counts ("14 of 43 above").
- The sector return is the equal-weighted mean of its stocks' price returns, not an NSE sector index.

## 2026-10-13 — Primary popover buttons read white on indigo

- The Actions page's **Kite basket** label read grey on indigo, hard to see on a phone. A popover's button has its own test id, so the rule that whitens primary-button labels missed it. Every primary button (plain, popover, download, form submit) is now matched by its kind, so the label is white on all of them.

## 2026-10-12 — NSE's prices take rights issues into account

- The NSE closes the app keeps as its middle price source (Screener first, NSE second) moved raw across rights issues: 14 since Sep 2024, HCC -23% on 5 Dec 2025, as if holders had lost it. Their corporate-action file was written before rights rows were kept and had no face value to price them. It now keeps the face value, and each monthly update re-reads every corporate action from NSE's files on R2. The 13 rights issues with an NSE close before them now match the long price file's adjustment to four decimals (S56).
- Frozen track-record months are not rewritten; any month whose replay now differs is listed for the owner.

## 2026-10-12 — The Recommendation is recorded forward, beside the live system

- From November 2026 the Recommendation (live weights, 30 holdings, keep while in the top 90, 200D EMA) keeps its own monthly record on the Nifty 750, frozen like the others on the 1st-5th of each month (`data/track_record_shadow.json`). It is never traded: Actions, Portfolio and the live records are unchanged (owner, 12 Oct).
- "Three systems, side by side" gains a row, **Recommendation (shadow)**, with its frozen months; the first, November, appears after it is frozen in early December.

## 2026-10-12 — One Nifty 500 figure on Portfolio; the live month counts its fill day

- Portfolio showed the Nifty 500 since inception twice, -8.4% in the top row and -7.6% in the record, for the same months. Both were off by a day. The top row counted from the 31 Dec close, a day before the first book was bought (+0.16%). The record's running month started at the 1 Oct fill close, so 1 Oct itself, earned by the September book (the index fell 0.97% that day), was in neither September nor October until October was frozen. Now the running month runs from the last close of the month before, with the old book to the fill and the new book after it, exactly as the month will be frozen; the top row counts from the first fill. Both rows read the same figure (-8.5% on 12 Oct), and the strategy's month to date includes its fill day too.
- On the fill day itself the record still says the month "has a new book but no return yet"; the old book's fill-day move shows from the next session.
- Since inception reads "after costs · since Jan 2026" (each system's own start) instead of "after costs · YTD", which was wrong for Nano Cap and Combined (started Oct 2026) and would be for the 750 from January 2027.

## 2026-10-12 — Backtest names the recommended settings

- Backtest settings open with one line: **Recommendation: 30 holdings · keep while in the top 90 · 200D EMA · within 20% of the 52W high · live lookback weights.** These beat the live settings on all five indexes tested (Nifty 500, 100, Midcap 150, Smallcap 250, Total Market; research of 12 Oct, `scripts/research_regime_sweep.py`). A note only: the page's defaults, the track record and the model book are unchanged (owner).

## 2026-10-12 — The Kite basket is sized on your capital; Configuration says where its limits act

- The Kite basket on Actions sized every buy order on ₹10 lakh, half the model book's ₹20 lakh, since 30 Sep: it read a capital box Portfolio no longer has. The Kite basket button now opens a capital box, starting at Portfolio's ₹20 lakh, so the model book's basket matches Portfolio and your own holdings can be sized on your account. The value is kept while you move between pages.
- Configuration said its stock and sector caps, volatility target and liquidity floor changed the Portfolio page. They do not: since 30 Sep Portfolio and Actions show the track record's model book on its own limits (5% a stock, 40% a sector, no floor). The section now says the limits act on the Backtest only, and its summary reads "Backtest max per stock · per sector" and "Backtest liquidity floor".
- Volatility targeting is gone from Configuration (owner): no page used it.

## 2026-10-12 — One word for one thing on every page

- The same thing now has the same name everywhere (owner's choices, 12 Oct): **Max drawdown** (Backtest said "Worst fall"); **Ahead of the index**, in % (Backtest said "Ahead of Nifty 500", the month cards said "pts"); **Nifty 500**, not "NIFTY 500" (header, Portfolio); **52W high** and **50D EMA** in labels, "52-week high" and "50-day EMA" in sentences.
- Trade tables say what happened: **Bought / Sold / Held** on Portfolio's rebalances, Backtest's rebalance log and this month's changes, and Ranks by month ("Retained" is now "Held"). Plans and filters say **Buy / Sell / Hold**, as Actions does. Before, one book was written five ways (BUY, 🟢 BOUGHT, bought, Retained, kept).
- Backtest's current book uses Portfolio's column names (Current Price, P&L %, Holding Days, Sector / Industry) and tiles (MTD return); its filters read Month, Outcome, Action and Rebalance, as on Portfolio, not "Filter Month".
- Dates read 01 Oct 2026 everywhere: no more "1 Oct" on Actions, "Oct-2026" in the trade month, or 2026-10-10 in the History caption and Ranks by month.
- Links to places that moved: Configuration → "Momentum score" and "Portfolio limits" (were "Momentum Signal", "Portfolio risk"); the Guide's Kite basket is on Actions, not Portfolio; Guide "tabs" are pages; a note pointing to a Provenance section that does not exist is gone. The Backtest help no longer names Screener as a source ("Personal").
- Wrong statements fixed: the stock page called its Sharpe annualised (it is the window's, as the ranking scores it); the Guide gave the market regime as Nifty above its 50 EMA (the header uses the Nifty 500 against its 200-day average), told bear-market readers to exit on trailing stops (the model has none), and to trade at 09:20 (the model fills at the close). Breadth's events table said "52W High" whatever window was picked. History's growth chart called a Nifty 50 benchmark "Nifty 500".
- British spelling throughout (realised, initialise, normalised, winsorised).

## 2026-10-12 — Backtest: the headline figures in one row, a line each

- The six headline figures sit in one row of six, as on Portfolio, instead of two half-empty rows of three whose notes ran to two or three lines. Each note is now one short line: "+3258.0% before costs", "Nifty 500 +10.3%", "±0.25 · Sortino 1.04", "Calmar 0.53", "70% up · turnover 50%". The cost and the window were already in the Tested line; the risk-free rate and how each ratio is made are under Method.
- "Ahead of Nifty 500" is a percent, as on Track Record: +1972.2% rather than +1972.2 pts. The number is the same, the strategy's total return minus the index's.
- "Annualised" no longer says "not a CAGR" over 16 years: over a year or more it is one. Under a year it still says it is a part-year scaled up ("scaled up from 0.7 yrs"), and the Calmar, which divides that figure, is left out.
- "Equal weight made no difference to this run" no longer shows on every equal-weight run: equal weight is the one book the cap allows, so the note is shown only for another scheme.
- Shorter notes and captions elsewhere on the page (canonical account, current book, calendar returns, cash and survivorship notes); nothing they said is gone.

## 2026-10-10 — A failed price update shows on the site, and one new stock no longer holds back the night

- The site showed 8 Oct prices all of Saturday 10 Oct with a green status. The night's Screener update had stopped because TRIVENIPT, listed on 9 Oct, has no Screener page yet, so no stock got 9 Oct; and one trading day behind counted as current. Now prices are behind when a session's closes are missing at 09:00 IST the next day (weekends and NSE holidays skipped), and every page says so under the header, phone included: "Prices stop at 08 Oct; 09 Oct's closes were due by 10 Oct, 09:00 IST."
- A new index member Screener has no history for no longer stops the update for every other stock. It is named under the header ("No price history for new index member TRIVENIPT (since 10 Oct)"), and the night's run still fails, so the failure alert on GitHub opens. A stock that had history and lost it still stops the night.

## 2026-10-10 — Ranking: "View all" on the top-50 cards opens and closes the list

- On the Biggest Jumps, Entered top 50 and Left top 50 cards, "View all" used to open the rest of the list under itself: the button stayed above the new rows, the column header was repeated, and a second "View all" in the card's header did nothing. Each card now has one button, under its rows: it opens the full list in the same table, then reads "Show less" and closes it again.
- A stock's 1M % on the Left top 50 card was always red, gains included (ACMESOLAR +1.9%). Now gains are green and losses red on every card.

## 2026-10-09 — Backtest: settings with Apply, more entry rules, year-by-year; the queued message says whose run it is

- Backtest settings are one panel with an Apply button: nothing runs until Apply, so changing five weights runs one backtest, not five. History's index, start and end month and traded-value floor are in the same panel. It is a full-width section rather than a pop-up, so it reads on a phone.
- The parameter sweep is gone from the Backtest page (owner): it was heavy for a shared server and easy to fit to luck; single what-ifs are the Apply form's job. Before it left, it was fixed to test what the page shows (below), which is why its earlier "winners" on History from 2010 should not be relied on.
- The all-time-high rule says where the price history starts ("ATH since Jan 2008") and applies to a stock only once it has 3 years of prices on file (adjustable): a stock already trading in January 2008 may have peaked before the file begins. A stock that listed later is held to it at once.
- The parameter sweep tests what the page shows. It used to ignore the page's window, index, floor and keep-rank: a sweep on History from 2010 scored only the last 6 months against the Nifty 750's members, so its "best" settings were chosen on April-September 2026. It now runs the page's own window and list (its holdout halves are about 100 months each), and it is slower for it: about 2 minutes for 3 combinations on History.
- Rules to keep a holding can differ from the rules to buy it (EMA, 52-week high, all-time high; blank keeps the buy rule), and holdings, the keep-while-ranked-within number and the rebalance interval take any number (for example 23 holdings kept while ranked within 77).
- New entry and exit rules for research: the EMA a stock must close above (any period, 50 by default), how far below its 52-week high it may be (20% by default), an optional all-time-high rule (within X% of the highest close on file), and the score as Sharpe (the live system) or the plain lookback return. With the defaults every result is unchanged.
- Calendar returns opens with a year-by-year block laid out like the monthly ones (Strategy, the index and Alpha as rows, one column per year): with the months covered when a year is only partly in the window ("Jan–Sep"). Every number is the CY figure of that year's block below it, so the two never disagree.
- With one reader the Backtest page could say "Another reader's backtest is computing" when no one else was there: changing a setting abandons the page's run, but a backtest already under way cannot be stopped and finishes first. The message is now amber and says "Your previous settings are still computing" when it is the reader's own earlier run.

## 2026-10-08 — History from 2010: memory no longer climbs with every change

- Changing History-from-2010 settings (index, floor, rebalance, holdings, lookback weights) made the app a little bigger each time, by 70-130 MB, until Streamlit Cloud stopped it. Each backtest's memory was freed but never handed back to the system. The app now hands it back after every page (about 5 ms). The same series of changes now stays near 500 MB instead of climbing past 900 MB. Results are unchanged.

## 2026-10-08 — Backtests: the crash fixed, one at a time, a sweep ceiling

- The History-from-2010 backtest took the app down on 8 Oct: to keep each month's 52-week highs (about 3 MB in all) it kept the whole 252-day calculation window behind every one, about 580 MB. One reader opening History now peaks at 751 MB instead of 1,156 MB. Results are unchanged.
- Only one backtest computes at a time across the server. Another reader's new backtest shows "Backtest running: request queued" and starts when the first finishes; a result already computed is shown at once. The parameter sweep runs at most 50 combinations from the page (it was 400).
- The app writes a line to its log each time its memory peak rises by 50 MB, naming the page, so production memory can be read from the Streamlit Cloud log.

## 2026-10-08 — Memory: the app stays inside Streamlit Cloud's limit

- Streamlit Cloud restricted the app for using too much memory. Each rerun of each session had been unpickling its own copy of the same price frames (~130 MB a click), and every weight setting a reader tried kept a 56 MB engine for an hour with no ceiling. The price frames are now one shared copy, and the engine and backtest caches have a size limit. With 4 readers at once, peak memory fell from 1.9 GB to 1.4 GB and the Screener answers in 4 s instead of 18 s. Rankings and prices are unchanged (`docs/MEMORY_AUDIT_2026-10-08.md`).
- Every cold start had been skipping the R2 copy of the ranking for the release file because of an import race between two threads; fixed.
- Holdings CSV uploads are limited to 5 MB.
- The ranking engine is now shared between readers too (each gets its own view of it), and the Track Record comparison prices the other systems from the app's own Screener copy instead of downloading it again; with 4 readers on Portfolio, peak memory 1.44 GB -> 1.05 GB. The comparison's own system could be shown a price frame up to an hour old after new prices arrived; fixed.

## 2026-10-07 — Long-file build: corporate actions read in parallel and from a pack

- The weekly long-file build spent ~32 of its ~33 minutes reading every session's corporate-action file from R2 one by one; the computation takes ~15 s. The files are now read 16 at a time and kept in `nse_actions_pack.parquet` on the release, so a build reads only the new days (and the newest 10 again). Every factor is still recomputed from all of them; a file that cannot be read stops the build.

## 2026-10-07 — Ranking: Screener's weekly stretch filled with NSE's daily closes (S23)

- Owner decision (7 Oct 2026): Screener's store is daily for about its latest year and weekly before it, so a 9M or 12M window that reached back before ~Sep 2025 scored a mix of daily and weekly moves and could open on a close up to a week from its date. The ranking frame now fills the weekly stretch with NSE's daily closes, spliced by ratio: each of Screener's weekly closes stays exactly as Screener has it, and the sessions between two of them follow NSE's daily moves from the earlier one. An interval where NSE's move differs from Screener's by more than 2% (an action one side adjusted and the other did not) stays weekly. Live 750, 6 Oct 2026 data: 128,025 prices for 695 stocks, 106 sessions added (7 Oct 2024 - 25 Sep 2025), 12 intervals kept weekly.
- Checked against SS, Tijori, Yahoo and eod2: the daily move of every filled day but 3 agrees within 2% with at least one of them (the 3 are the ITC, QUESS and SIEMENS demerger days, priced at the ex-date fall as decided).
- Today's ranking does not change (its 12-month window is already daily); the stock page's past ranks (-2M, -3M, -6M) do. Replayed month-ends Jan - Apr 2026: at most 1 of the top 20 differs. `ATH` / `% ATH` move for 124 stocks: a daily closing high between two weekly closes now counts.
- Nano Cap and Combined are not filled: NSE's committed file has 98 of the 429 Nano Cap stocks, and a filled session where a stock has no price would delete that stock's weekly returns.
- Switch: `UMIYA_SCREENER_WEEKLY_FILL=0` turns it off (default on). The setting is part of the ranking contract, so the first night after deploy the precomputed table is rebuilt and the app computes the ranking itself until then.

## 2026-10-07 — History from 2010: NSE-only gaps filled from BSE

- The long NSE price file fills a stretch NSE has no row for with BSE's close where BSE traded the same company (by ISIN), the two exchanges meet within 2% at both ends of the gap, and BSE traded on at least half its sessions (`src/loaders/bse_fill.py`, TODO S38). The fill is in raw prices, before any split, bonus or other factor, so those apply to the filled days as to NSE's own; a day NSE has a price for is never changed. A holding or a momentum window across GOODYEAR, NOVARTIND, KENNAMET, KIRLFER and GRAUWEIL from 26 Oct 2023 to 17 Apr 2026 (and FORCEMOT, BESTAGRO and 15 smaller gaps) now sees real prices. Takes effect with the next long-file build.
- Every filled day and every refused gap is listed in the build and the audit zip (`bse_fill_cells.csv`, `bse_fill_gaps.csv`, `bse_fill_verify.json`).
- GRAUWEIL's 1:1 bonus of 10 Apr 2024, which fell inside NSE's gap, is a `notes.json` correction: before it the gap read as a 41% loss.
- BSE's daily table is kept on the release (`bse_daily.parquet`) and on R2 (`bse/daily`, protected), refreshed weekly by the new `bse_daily.yml`.

## 2026-10-07 — Data-quality sweep: two actions counted twice, benchmark decimals

- History from 2010: a corporate action that also reached the build at its date with day and month swapped is now taken once (`nse_bundle.drop_swapped_twins`): ALLCARGO's demerger (12 Nov 2025) had also priced 11 Dec's -3.6% away, and HCG's rights (2 Mar 2026) had been applied on 3 Feb too. Takes effect with the next long-file build; neither stock was in the Nifty 500.
- `data/benchmarks.csv` keeps two decimals on every row (pandas 3 had written 19384.30 as 19384.3 on days with no new rows). Formatting only.
- Sweep report: `reports/dq_sweep_2026-10-07.md` (40 random closes, 20 actions, 50 History trades, every adjustment step checked).

## 2026-10-03 — Backtest: calendar returns

- The Backtest tab (Live and History from 2010) shows Calendar returns under the growth chart: Strategy, the index and Alpha by year and month, with CY, FY (April - March) and quarters, built by the code the Portfolio page uses (`ledger_from_curves`, `build_combined_grid`). Alpha's year and quarter cells are the plain difference between strategy and index; Portfolio keeps its compounded-monthly convention (TODO S40).

## 2026-10-03 — Data correctness: BSE gap audit, KESORAMIND

- `scripts/bse_bhavcopy.py` and `scripts/audit_gaps_against_bse.py`: BSE's bhavcopy 2008 - today, and every gap in the long NSE file classified (NSE-only, suspension, not checked). Findings and method: `docs/DATA_CORRECTNESS.md`, loaded by the new `CLAUDE.md`.
- KESORAMIND's 10 Mar 2025 demerger priced at the ex-date fall (x0.0474, `notes.json`); takes effect with the next long-file build.

## 2026-10-03 — Lightweight Charts 5.2.1

- Vendored TradingView Lightweight Charts upgraded v4.2.0 -> v5.2.1; every series is created with `addSeries`. The TradingView logo is hidden on all charts (`attributionLogo: false`, #364 and this change). The `streamlit-lightweight-charts` component renderer is untouched.

## 2026-10-02 — SS, the three-source check, NSE history from 2010

- **SS store**: daily OHLCV for 1,216 stocks (1,000 sessions each), downloaded gently (4 s apart, 40 a round, 5-minute rests), saved to the release. From tonight `ss_sync.yml` updates it each weeknight at 22:02 IST and publishes it to R2 (`prices/ss`, 7 copies + month-ends kept).
- **Three-source check** (`src/engine/reconcile.py`, `scripts/reconcile_report.py`), the last step of the nightly run: rights factors from NSE's terms, applied only where NSE shows a source left the issue raw (SS had adjusted 8 of 10 itself); face values from NSE's list; a two-of-three vote on every day's move with NSE as judge; level shifts tagged with their corporate action. It reports; it changes no stored price.
- **Renames automatic** (`src/loaders/nse_identity.py`): NSE's symbol-change list plus ISINs (the owner's suggestion) find 575 renames with no conflict, the 21 kept by hand among them and GUJGASLTD → GUJENERGY, which the hand list lacked. A rename is joined only where the two price series meet.
- **NSE history from 10 Jun 2010** on R2: NSE's full bhavcopy imported from a public GitHub mirror (equal to NSE's own file on every row checked), corporate actions 2010 – 2026 from NSE's yearly list. The bundle collector, whose backfill had silently stopped when the Yahoo calendar was deleted, now runs on a weekday calendar back to 2010.
- Rules and status: `docs/PRICE_PIPELINE.md`.

## 2026-10-02 — Nano Cap and Combined show their first book

- Fixed: with Nano Cap or Combined selected, Actions said "the model book is not available: the strategy needs about 18 months of price history". The cause was not history. Their first book is signalled at the 30 Sep close and filled 1 Oct, which sits outside the window of completed months, and no earlier month holds a rebalance, so the replay returned nothing for the whole of October. The engine now returns that first book (current book, this month's changes, month-to-date) when no month has completed yet. Equity curve, monthly table and stats stay empty until the month closes. Existing results are unchanged.
- Fixed: the Backtest page crashed for Nano Cap and Combined (`LossySetitemError` while joining NSE history into a float32 column). With no completed month it now says so.

## 2026-10-02 — NSE is the middle price source

- Owner decision: Screener → NSE → Yahoo. A missing Screener price is now filled from NSE's adjusted daily move first, then Yahoo's. Stocks whose NSE and Screener levels drift past 1% (about 50 in the 27 Sep report) are skipped and fall through to Yahoo. Missing NSE data leaves the old Screener → Yahoo order.
- Industry map always labels the five strongest industries; October freeze window documented as 1st–5th.

## 2026-10-02 — Canonical reconciliation, hard caps, parity gate

- Reconciled every account representation on the published data: Portfolio, Actions and Backtest books identical; Actions reproduces the 1-Oct rebalance; ledger 9/9 against the replay.
- Fixed: `record_run`'s cache ignored the benchmark, so one failed benchmark download served a 0% benchmark (alpha = strategy return) to every page for up to an hour.
- Owner decision: hard caps everywhere — 5% per stock, 40% per NSE industry, enforced at selection, never relaxed; the shortfall is cash. Defaults moved 30% → 40%.
- Track record rebuilt under the capped config (`4cc739e503d7`, logged in `rebuilds`): cumulative +46.57% → +44.40%; benchmark unchanged.
- New: canonical parity gate (`scripts/canonical_parity_check.py`, `canonical_parity.yml`) fails CI on any disagreement.
- Record: `docs/CANONICAL_RECONCILIATION_2026-10-02.md`.

## 2026-10-01 — UI overhaul (draft PR)

- Open trades and the current month's rebalances now reach Portfolio (engine fix).
- One table for the Screener: Full Quant is the master, Executive and Core hide columns; Table/Grid toggles removed.
- Time series use TradingView Lightweight Charts (hover legend; Breadth, Portfolio, Backtest, stock page with candles, volume, overlays and RS); Highcharts for the Relative Rotation Graph, the holdings correlation heatmap and the Sectors industry map. The component-based Lightweight renderer (`src/ui/lightweight_chart.py`, `streamlit-lightweight-charts`) is kept for reverting. The old fallback chart and its extra dependencies are gone.
- Portfolio sizes holdings at the latest rebalance (fixes negative cash / over 100% invested). Configuration has a data-freshness table.
- Portfolio absorbs the Track Record page; `/track-record` redirects.
- RRG benchmarks are Nifty 500 / Nifty 50; Configuration summary is a tidy list.
- New highs: 1M and 3M counts in Breadth and Full Quant.


## 2026-09-30 — Streamlit reload and track-record warning hardening

- Fixed a concurrency race in the custom Streamlit hot-reload path. The reload/import window is now serialized across script threads, preventing transient `KeyError` failures while `src.*` and `r2.*` modules are rebuilt.
- Added a concurrent reload regression test.
- Confirmed that `data/track_record_nano.json` and `data/track_record_combined.json` are intentionally absent before their October 2026 inception.
- Changed pre-inception missing-ledger logging from WARNING to INFO; missing ledgers at/after inception remain warnings, and corrupt ledgers still fail safely rather than being replaced with an empty record.
- PR #263 merged as `3529e834352156fafbd8f8f8b359ac8fb13219fc`.
- Validation: Lint #237, V1 Full Validation #1061, R2 Streamlit read-path gate #283 — all green.


## 2026-09-25 — Full code audit (merged up to #177)

- Owner decisions shipped:
  - 1B: ranking windows count back from the last price date.
  - 2B: up to five stragglers are ranked on their last print (⏸) instead of holding the ranking back.
  - 3B: the price fingerprint covers the whole history.
- UI read line by line:
  - escaping of every user- or vendor-supplied string;
  - exact index-tag matching;
  - cache keys that change when the history changes;
  - the navigation menu now closes when a page is chosen.
- Production QA:
  - a newer build that contains the triggering commit is no longer a mismatch;
  - the menu-reachability and nav-styling checks now measure what they claim;
  - a Reset that cannot be clicked is now a failure.
- Runtime dependencies pinned to the tested versions. The R2 read gate is skipped on Dependabot PRs and re-runs on main when `requirements.txt` changes.
- The Yahoo index-price fallback only accepts an exact index name.
- R2 storage size report added. Retention is awaiting the owner's decision.

## 2026-09-23 — Production ranking and Streamlit runtime hardening

- Enforced 100% current-universe coverage for canonical ranking sessions, eliminating the 749/750 acceptance path caused by the former 90% coverage floor.
- Added explicit symbol reconciliation diagnostics for precomputed-ranking rejection paths: missing, extra and duplicate symbols.
- Kept NSE DUMMY* placeholder filtering as the canonical tradability rule; no ticker aliases are introduced.
- Confirmed the canonical ranking source remains Screener/R2; Yahoo-origin data remains a separate deep-history/archive/healing feed.
- Reduced repeated Streamlit work by memoizing ranking-contract validation and Screener-frame shaping using correctness-preserving cache identities.
- Suppressed duplicate source-selection and precomputed-acceptance log messages when the logical decision is unchanged.
- Added production documentation covering the R2 path, 750-row completeness contract, Streamlit engine-skipped semantics and verification state.
- Verified the post-merge live deployment: main loaded successfully, the R2 Screener store was read, and a **750-row precomputed ranking was accepted**.

## 2026-09-22 — R2 production publication hardening

- R2 publication uses immutable content-addressed revisions, manifests and current pointers with read-back/hash verification.
- R2-focused CI is isolated from V1 Stage-4B research validation.
- Screener remains the canonical V1 ranking price source; Yahoo is separate archive/deep history.
