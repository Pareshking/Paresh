# S193 item B, group 1: are the Dashboard's sentences true to the data?

Page text captured 23 Nov 2026 from main (prices to 20 Nov 2026). Each figure was worked out again with pandas from the
repo's raw data: `data/nse_indices_history.parquet` (NSE index closes), `data/nse_total_market.csv`,
`data/nsdl_fpi_daily.csv`, `data/nse_dii.csv`, `data/benchmarks.csv`, `data/breadth_history.csv`,
`data/momentum_health*.csv`, `data/signal_tests.json`, `data/track_record*.json`, `data_cache/nse_long_close.parquet`,
`data/indices/*.csv` and `data/reference/nse/holidays.csv`. The app's own output was not used as evidence.
Code locations are on main at 2c91ca2. "#n" is the entry's position (from 0) in b_g1.json.

## FALSE and MISLEADING first

| # | page | systems | sentence (short) | verdict | evidence (recomputed) | code | suggested fix |
|---|---|---|---|---|---|---|---|
| 0, 12, 56, 66, 71 | dashboard | all | "at the last month-end, which the tests read, 3 and 2" | **FALSE** | At the 30 Oct close all 5 passing signals were in their weaker state: Nifty 500 −3.9% below its 200D EMA (off), Oct FPI −₹34,843 Cr, under the ₹14,372 Cr cut (off), 10-month −3.1% (off), qualify 16.6% (on, weaker), breadth 27.5% of the Nifty 500 above the 200D EMA (on, weaker). So the count is **0 and 5**. The code takes today's state for 3 of the 5 (`me_on="same"`) | dashboard_home_view.py:1329-1337 (`row`, `me_on="same"`), :449 `_month_end_count` | Give trend_fast, fpi and breadth_thin real month-end readings (the 30 Oct close, October's FPI total), or drop the clause |
| 66, 71 | dashboard | nano | "on today's readings 4 point to a stronger month … 1 to a weaker one" | **FALSE**; contradicts the 750 and 1000 pages ("5 … 0") for the same Nifty 500 signals on the same day | The "Stocks that qualify" row on nano falls back to month-ends because `data/qualified_now.json` is missing (S193 A6 fix). Today's share recomputed (Nifty 500 members above their 50D EMA and within 20% of the 52W high): **44.0%** (off, so the stronger state), not 17% | :1281-1303 `_qualify_saved`/`_qualify_today`; :1384-1392 | Make sure the nightly job writes `qualified_now.json` (and the loader fetches it); until then, show "–" rather than a month-end value under "Now" |
| 75 | dashboard | nano | "Stocks that qualify … 27% or fewer: on · month-ends", cells 44% · 20% · 17% | **FALSE** | The cells are the 31 Jul, 30 Sep and 30 Oct month-ends (44.2, 19.6, 16.6) under columns headed 3M ago / 1M ago / Now. Today's figure is 44%; 750 and 1000 show 46% · 15% · 44% | :1386-1392 | As above; if month-ends are shown, head the columns with their dates |
| 1 | dashboard | 1000 | "the book, up 5.5%, is level with the best of them" | **FALSE** | Best momentum index from the 2 Nov close: Nifty Midcap150 Momentum 50 +4.56%. The book is 0.9 points ahead. The KPI on the same page says "Ahead of 5". The "is ahead of them" branch can never be reached, because `>= hi - 0.05` is tested first | dashboard_home_view.py:278 | Test `book > hi + 0.05` first ("is ahead of all of them") |
| 68 | dashboard | nano | "the book, down 2.8%, is within their range" | **FALSE** | The momentum indices rose 4.31 to 5.66% (30 Oct to 20 Nov); −2.8% is below every one of them | :278 (else branch) | Add a "below all of them" branch when book < lo |
| 0, 1 | dashboard | 1000 vs 750/nano | "So far in November … Nifty Total Market is up 8.1%" (1000) and "up 9.8%" (750, nano) | **MISLEADING** (contradicts across systems) | Nifty Total Market: 30 Oct 12,360.40 → 20 Nov 13,572.35 = **+9.81%**; from the 2 Nov close (12,554.75) = **+8.11%**. The 1000 counts from its first fill (A12), so its momentum indices read 2.9-4.6% against 4.3-5.7% on the other pages. Its KPI says "Since 1 Nov 2026", but 1 Nov was a Sunday | dashboard_insights.py:128-130; dashboard_home_view.py:290 | In a first month, say "since the 2 Nov fill" in the lede, the KPI and the table head |
| 2/3 table | dashboard | nano | October column: Nifty Total Market −1.2% beside the book's −5.7% | **MISLEADING** (in the table, not a b_g1 entry) | Nano's October book runs from the 1 Oct fill; Nifty Total Market from 1 Oct is **−0.18%**, not −1.16% (that is 30 Sep to 30 Oct). `_last_month` uses the calendar month and so breaks the A12 rule that `book_month` applies | dashboard_home_view.py:1062-1071 | Use `di.first_fill` in `_last_month` for the system's first month |
| 4 | dashboard | 1000, nano | "January to October stay as recorded against the Nifty 500" | MISLEADING (minor) | The 1000's record starts Nov 2026 (no Jan-Oct months). Nano's starts Oct 2026 (its benchmark +0.17% is the Nifty 500 from the fill) | :324 | Say it only for months the system actually has |
| 15 | dashboard | 1000 | "This system's own record begins with December 2026, the first month after its 30 Nov month-end" | MISLEADING | The same page gives the 1000's book record "Since 1 Nov 2026", 0 of 1 months. The Nifty 1000 membership baseline is 30 Oct 2026 (`membership_history.json`), which would allow a November row, and the November "month so far" tile (−2.3) is shown. The date is hard-coded | system_momentum.py:170 | Name what begins in December ("its top-fifth record"), or start that record at November, labelled reconstructed |
| 25 | dashboard | all | "momentum's next-month lead (the top 100 of this ranking less the Nifty 500)" | MISLEADING | `momentum_health.csv` is the Nifty 500's top fifth (about 100 of 500) by this site's score. On the 1000 and nano pages "this ranking" reads as that system's own list | :593 | "the top 100 of the Nifty 500 by this site's score, less the Nifty 500" |
| 31 vs 18 | dashboard | all | "Tested here · 130 months, 33 heavy" against the signal row "on in 33 of 129 months" | MISLEADING (minor) | Recomputed: 130 months of flows (Jan 2016-Oct 2026), 129 with a next month to test. All other figures match: 1.40 vs 0.36, 67% vs 53%, halves 1.08/0.38 and 1.84/0.29, correlations +0.536 and −0.072 | :637 | Show `len(nxt)` (129) as the months tested |
| 35, 76 | dashboard | all | "Large Cap momentum is failing: 6 to 7 points behind the Nifty 200 over every window" | MISLEADING (minor) | Nifty200 Momentum 30 less the Nifty 200: −6.75, −6.37, −7.46. The table beside it shows −7.5, the sentence "7" | :753 | Use one decimal: "6.4 to 7.5 points" |
| 55 | dashboard | nano | "A light month. 6 of 20 would change; 10 in an average month" | MISLEADING | Nano has had one rebalance after its first fill (2 Nov, 10 bought, per its Portfolio page), so the "average" is a single month | :938-943 | Give an average only from 3 or more rebalances; otherwise "10 at the last rebalance" |
| 56, 71 | dashboard | 750, nano | "2 losing months in a row" | MISLEADING | 750: October lead −0.75 (−6.44 against −5.68), and November is unfinished (−1.7 so far). Nano: a one-month record (Oct −0.72) plus November so far (−3.3). `losing_streak` counts the month in progress | dashboard_insights.py:198-211; dashboard_home_view.py:522 | "October, and November so far" |
| 67 | dashboard | nano | "The book is −12.6 points behind Nifty Total Market" | MISLEADING (double sign: "−… behind") | −2.8 − 9.81 = −12.6; the figure is right | :269 | `abs(gap)` in the "behind" title; the "ahead" title has the same `sg()` |
| 70 | dashboard | nano | "Health Technology are climbing in, 2 of the 6; 2 of the 3 falling out are Durables" | MISLEADING | The 6 climbers are 2 Health Technology (BLISSGVS, APLLTD) and **2 Finance** (ALGOQUANT, SGFIN): a tie shown as a lead. The same list mixes TradingView names (Finance, Health Technology) with NSE short names (Cons. Services, Durables). BLISSGVS is "Rising in" here but "Faded from #1" in the holdings table on the same page | :345-347 | Name both when tied; one sector naming per system; agree a word for "out a month ago, back now" |
| 79 | dashboard | nano | "counted over today's members (no members-of-the-day history for this universe)" | MISLEADING (minor) | `data/nanocap_membership.json` holds the list's month-ends from 31 Aug 2026 (3 lists) | :849-850 | "no members-of-the-day history before Sep 2026" |
| 39 | dashboard | 1000 | "Over 12 months … the median stock fell 2.9%" (and share beating 46%) | **LEAD**: not reproduced | On NSE's 1000 list (`ind_nifty1000_list.csv`), long close: 12M median **−3.8%**, share beating Nifty Total Market 44.5%. The 1M (22.5%), 3M (28.3%) and 6M (40.4%) shares do reproduce, and the 750's figures match (25.2%, median −3.6%) | dashboard_insights.py:491; dashboard_home_view.py:1000-1001 (`ranked_px`) | Check which stocks and which prices the 1000's `ranked_px` holds for 12M (newer listings, the other 250's price source) |
| 40 | dashboard | 1000 | "now … Nifty Microcap 250 the narrowest" | **LEAD**: not reproduced | From the long close, share above the 200D EMA on 20 Nov: Nano Cap (the 1000's other 250) **37.2%**, Microcap 250 38.6%, so Nano Cap is the narrower. The page shows Nano Cap 40%, Micro 38%. The other lists agree within about 1 point (Nifty 100 66.7 vs 66) | :999 `size_breadth(adj_close,…)` | Compare the 1000's `adj_close` for the other 250 against NSE's closes (8 of the 250 have no 200D EMA here) |

## Every entry

| # | systems | sentence (short) | verdict | evidence | code |
|---|---|---|---|---|---|
| 0 | 1000, 750 | Brief: keeping pace; 3/5 go; 5/0 today, 3/2 at month-end; only 22%/25% beat | FALSE (the month-end count); 1000's base date MISLEADING | 5/0 today is right. 22.5% and 25.2% are right. The month-end count is 0/5 (see above) | dashboard_home_view.py:1204-1231 |
| 1 | 1000, 750 | NTM up 8.1/9.8%; momentum 2.9-4.6 / 4.3-5.7; book level with best | 1000 FALSE; 750 TRUE | Index returns all reproduce (see above). 750: book 5.8 vs best 5.66, so "level" holds (the KPI says "Ahead of 5") | :271-280 |
| 2 | all | Each row … Nifty Total Market (about 750 stocks) | TRUE | `ind_niftytotalmarket_list.csv` has 752 rows | :319 |
| 3 | all | Right of the zero line … | TRUE-static | – | :321 |
| 4 | all | pts note; January to October as recorded against the Nifty 500 | 750 TRUE; 1000 and nano MISLEADING (minor) | 750's Jan-Oct ledger benchmark = Nifty 500 | :324 |
| 5 | 1000, nano | 3/6 sells, 3/6 buys, 2 on the edge, 5 sessions away | TRUE | 24 Nov is an NSE holiday (holidays.csv), so 23, 25, 26, 27, 30 Nov = 5 sessions. Counts match the lists shown | :430-437; actions_view.py:84 |
| 6 | all | 2.6% / 7.7% below its 50D EMA; more than 20% below 52W high | TRUE | Long close: SETL −2.56% (−23.6% from high), SHILPAMED −7.74% (−20.9%), SKYGOLD −2.62% (−17.5%, so correctly no high flag). The "50D EMA · 5.2%" room is (P−EMA)/P (ANANDRATHI 5.5% over the EMA = 5.2% of price) | :400-437 |
| 7 | 1000, 750 | Automobile and Auto Components · ahead on both | TRUE (agrees with the Auto card; the sector figures were not recomputed) | Auto card +11.8/+5.3 (1000), +10.1/+6.0 (750). The same sector is "Auto" in the table on the same page | :910-916 |
| 8 | 1000, 750 | Checked 30 Nov, filled 1 Dec; other 12 have more room; 3M ago 20 Aug, 1M 19 Oct; cut-off #40 | TRUE | 20 − 8 rows shown = 12. 20 Oct 2026 has no session (Dussehra), so 19 Oct is right. Whether "more room" holds across mixed units (EMA % against rank places) was NOT CHECKED | :437 |
| 9 | 1000 | 3 of 20 would change; no results due before the check | TRUE (partly) | `results_calendar.csv` 20-30 Nov: none of the 8 holdings shown or the 3 buys. The other 12 holdings were not listed, so not checked | :936-947 |
| 10 | all | Leadership turnover · 21/18/22 of the top 40 new | NOT CHECKED | Needs the rank history (rank engine) | :352 |
| 11 | 1000 | Financials climbing in, 2 of 6; 2 of 3 out are Telecom | TRUE | Matches the table (ANANDRATHI and KOTAKBANK; STLTECH and HFCL) | :345-349 |
| 12 | 1000 | No year of own record; 5 pass, 2 not confirmed; 5/0 today, 3/2 at month-end | FALSE (the month-end count) | `signal_tests.json`: 5 passed, 2 not. Today 5/0 is right. Month-end 0/5. "a reading the page used to count for momentum" NOT CHECKED (history) | :517-525 |
| 13 | 1000, 750 | This system's top fifth against the 1000/750 … | TRUE-static | – | :566 |
| 14 | 1000 | Tiles note (own record not yet begun) | TRUE | No `momentum_health_1000.csv` | :560-575 |
| 15 | 1000 | Own record begins Dec 2026 …; long record: deepest 12.5% from Dec 2024, 5 others took 6-23 months | First part MISLEADING; long record TRUE | Recomputed from momentum_health.csv (top against ew): −12.5% from Dec 2024, not made back; the others −9.7, −9.3, −6.8, −6.2, −5.0 took 19, 8, 7, 23, 6 months | system_momentum.py:164-176; dashboard_home_view.py:470-485 |
| 16 | all | all months since 2010 average +0.8 | TRUE | Mean of (top − nifty500) over 201 months, 2010-02 to 2026-10 = 0.800 | :585 |
| 17 | all | −0.2 on vs +1.2 off; both halves; on in 52 of 201 | TRUE | signal_tests.json breadth_thin: −0.23, 1.16, 52, 201 | :550 |
| 18 | all | FPI net, last 20 sessions · top quarter: on | TRUE | 20-session total ₹1,35,634 Cr, the highest in the record. Note: "on" is decided by the month so far (₹1.22 lakh Cr) against a monthly cut, while the cells show 20-session totals | :1352-1360 |
| 19 | all | 10-month … 30 Oct −3.1% | TRUE | Recomputed −3.11% (30 Oct against Jan-Oct month-ends). Today +6.12%, higher than 59.8% of month-ends since 2000 | :1362-1370 |
| 20 | 1000, 750 | qualify · 27% or fewer · 30 Oct 17% | TRUE | Quartile of the month-end series 27.4%. 30 Oct 16.6% (momentum_health_latest.json, matched by my own recount). Today 44.0% recomputed | :1384-1392 |
| 21 | all | Nifty 500 above the 200D EMA · 40% or fewer | TRUE | breadth_history: 57.2, 34.5, 50.5; lower than 56.6% of days since Dec 2009 | :1395-1399 |
| 22 | all | above the 50D EMA · up 15+ pts in a month | TRUE | 19.8 (30 Oct) to 55.2 = +35 pts, so on | :1400-1405 |
| 23 | all | +1.6 on vs +0.8 off, 4 of 201; halves disagree | TRUE | signal_tests.json rebound: 1.58, 0.78, 4, halves 3.35 / −1.75 | :548-556 |
| 24 | all | from its 52W high · within 3% after a 5-pt jump | TRUE | −0.04% now (from −9.14% at 30 Oct), so on; higher than 88.6% of days | :1406-1411 |
| 25 | all | The test, fixed before looking … top 100 of this ranking … | MISLEADING ("this ranking") | See above; the rest TRUE-static | :590-597 |
| 26 | all | FPI ₹1.22 lakh Cr, most since 2016; sold ₹3.18 lakh Cr over 11 months; DII selling | TRUE | Nov ₹1,22,265 Cr, ranked 1 (previous Dec 2023 ₹66,135 Cr). Dec 2025-Oct 2026 = −₹3,17,756 Cr, 8 of 11 negative, 38% bought back. DII 2-18 Nov −₹49,808 Cr, 11 of 12 sessions negative | :600-620 |
| 27 | all | dashed line ₹14,372 Cr or more | TRUE | 75th percentile of the 130 months = ₹14,372 Cr | :646 |
| 28 | all | usual range since 2016, −13 to +14 thousand Cr | TRUE | Quartiles −12,682 and +14,372 | :1167 |
| 29 | all | Above the line … after such months momentum led by more | TRUE | 1.40 vs 0.36 | :653 |
| 30 | all | What heavy foreign buying has meant · Jan 2016 to Oct 2026 | TRUE | First and last months of the joined table | :658 |
| 31 | all | 1.4 vs 0.4; 67% vs 53%; halves; 130 months, 33 heavy | TRUE (figures); MISLEADING (minor), 130 against 129 | See above | :630-637 |
| 32 | all | correlation +0.54 / −0.07 | TRUE | +0.536, −0.072 | :638 |
| 33 | all | Nifty 50 trailed the Nifty 500 by 0.4 in heavy months | TRUE | −0.353 (rounds half up to 0.4) | :640 |
| 34 | all | Sources footnote (FPI; DII NSE to Oct, provisional from Nov…) | TRUE | nse_dii.csv scopes: "NSE, total DII" for months; "banks + insurance + mutual funds" for Nov days | :665 |
| 35 | 1000, 750 | Large Cap failing 6 to 7 pts; Nifty 100 broadest; Mid+Small level; 35%/60% of book | Figures TRUE; "6 to 7" MISLEADING (minor) | Size table reproduces exactly (e.g. Large +2.7/+2.8/+1.6, momentum −6.7/−6.4/−7.5). 1000: 5+30 = 35%; 750: 5+55 = 60% | :743-757 |
| 36 | all | Nifty 100 · Nifty200 Momentum 30 against the Nifty 200 | TRUE-static | dashboard_insights.SIZES | :770 |
| 37 | all | Nifty Midcap 150 · Nifty Midcap150 Momentum 50 | TRUE-static | – | :770 |
| 38 | all | Nifty Smallcap 250 · Nifty Smallcap250 Momentum Quality 100 | TRUE-static | – | :770 |
| 39 | 1000, 750 | Only 22%/25% beat over the month; 12M EW beat by 5.8/5.7; median −2.9/−3.6 | 750 TRUE; 1000 1M TRUE, 12M LEAD | See above | :700-706 |
| 40 | 1000 | A month ago Nano Cap held up best; now Nifty 100 broadest, Microcap 250 narrowest, 25% of book | "best a month ago" and "broadest" TRUE; "narrowest" LEAD | 19 Oct: Nano 46.9 against Micro 45.9; now Nano 37.2 against Micro 38.6 | :725-736 |
| 41 | 1000, 750 | The share of each NSE size list above its 200D EMA | TRUE-static | – | :684 |
| 42 | 1000, 750 | Above 60% broad, below 40% narrow; triangle a month ago | TRUE-static | – | :686 |
| 43 | all | Size lists are NSE's as of today …; no microcap momentum index | TRUE-static | – | :780 |
| 44 | all | 60/70/46% in sectors beating; 16/20/16% in 3/3/2 that lag | TRUE (agrees with the cards; the sector figures were not recomputed, which needs the ranked list) | 59.9/24.1/15.9; 69.7/9.8/20.4; 45.6/38.8/15.5 | :803 |
| 45 | all | The book's weight in each sector … | TRUE-static | – | :820 |
| 46 | all | Blue/amber/rust key | TRUE-static | – | :821 |
| 47 | all | Ahead of all ranked stocks over 6M and 1M | TRUE-static | – | :811 |
| 48 | 1000 | Ahead on one window: Financials (1M), Capital Goods (6M), Durables (6M) | TRUE | Cards −1.2/+3.7, +0.5/−4.6, +2.7/−1.8 | :812 |
| 49 | all | Each sector's stocks, equal-weighted … | TRUE-static | – | :830 |
| 50 | 1000 | counted over today's members | TRUE | The Nifty 1000 has membership only from 30 Oct 2026. Aside: the 1000's breadth series has "–" gaps through 2024-25 | :849-853 |
| 51 | all | When the top line rises while the bottom falls … | TRUE-static | – | :853 |
| 52 | all | Each line is 0.25% … | TRUE-static | – | static/dash_charts.js |
| 53 | all | Strong, ahead of all ranked stocks on both windows | TRUE-static | – | :811 |
| 54 | 750 | 5 sells, 5 buys, 5 sessions; both Capital Goods holdings go as their sector slides | TRUE | DIACABS and SYRMA (both Capital Goods) are Sell; the Capital Goods card reads −2.1/−6.0 | :430-447 |
| 55 | 750, nano | A light month. 5/6 of 20; 8/10 in an average month | 750 TRUE (Portfolio: "8 of 20 on average, from February"); nano MISLEADING | See above | :938-943 |
| 56 | 750 | Ahead over a year, but 2 losing months in a row; counts | FALSE (counts) and MISLEADING (streak) | 12M lead +16.03 recomputed | :517-525 |
| 57 | 750 | Tiles note (own record from December 2021) | TRUE | momentum_health_750.csv first month 2021-12 | :560-575 |
| 58 | 750 | top fifth less all members, equal weight, points | TRUE-static | – | – |
| 59 | 750 | usual range since 2021, −0.9 to +1.9 pts | TRUE | Quartiles −0.857 and +1.869 over 59 months | :1089 |
| 60 | 750 | 0.8% below Sep 2026 best; deepest 10.4% Dec 2024-Sep 2025, made back by Mar 2026; long record … | TRUE | Recomputed relative line: −0.80%, peak 2026-09; −10.42%, peak 2024-12, low 2025-09, recovered 2026-03 | :488-509 |
| 61 | 750 | Each finished month, the return of the best-ranked fifth … | TRUE | Bars: Oct −0.75, Sep +1.74, Aug +3.57 | – |
| 62 | 750 | Bars above the line … | TRUE-static | – | – |
| 63 | 750 | A month ago Microcap 250 held up best; now Nifty 100 broadest, Microcap narrowest, 35% of book | TRUE | Long close 19 Oct: Micro 45.9 the highest of the four NSE lists; now Micro 38.6 the lowest; book Micro 35% | :725-736 |
| 64 | 750 | Ahead on one window: FMCG (1M), Durables (6M) | TRUE | Cards −1.8/+0.5, +4.1/−2.0 | :812 |
| 65 | 750 | counted over the members of each date, leavers included | TRUE (not checked in depth) | breadth_history has `total_market` rows from 29 Oct 2021, so the 3-year chart is covered | :849 |
| 66 | nano | Brief: behind NTM and momentum; 6 go; 4/1 today; 3/2 at month-end; only 17% | FALSE (both counts); the 17% NOT CHECKED (the list's prices are not all in the long close) | See above | :1204-1231 |
| 67 | nano | −12.6 points behind | MISLEADING (sign) | −2.8 − 9.81 | :269 |
| 68 | nano | book, down 2.8%, is within their range | FALSE | 4.31 to 5.66 | :278 |
| 69 | nano | other 12 holdings have more room than KABRAEXTRU | TRUE | 20 − 8 rows shown | :437 |
| 70 | nano | Health Technology climbing in 2 of 6; 2 of 3 out Durables | MISLEADING (a tie with Finance) | See above | :345-347 |
| 71 | nano | No year of own record; 2 losing months in a row; counts 4/1, 3/2 | FALSE (counts) and MISLEADING (streak) | momentum_health_nano.csv: 1 month (Oct, −0.72) | :517-525 |
| 72 | nano | top fifth against the > ₹2,000 Cr list … | TRUE-static | – | :566 |
| 73 | nano | Tiles note (own record from October 2026) | TRUE | First month 2026-10 | :560-575 |
| 74 | nano | being collected from October 2026: 1 month so far; long record … | TRUE | 1 row; long record as #15 | system_momentum.py:172-176 |
| 75 | nano | qualify · 27% or fewer: on · month-ends | FALSE ("Now" is 30 Oct) | See above | :1386-1392 |
| 76 | nano | Large Cap failing 6 to 7; Mid+Small level; 0% of this book | TRUE; "6 to 7" minor as #35 (the "0% of this book" clause could be dropped when 0) | Book: Nano Cap 41%, Ultra Nano 59% | :753-757 |
| 77 | nano | Only 17% beat; 12M EW beat by 12.0; median −1.9% | NOT CHECKED (the list's prices are not all in the long close: PASHUPATI, KINGFA, KABRAEXTRU missing) | Arithmetic agrees: 12.8 − 0.8 = 12.0 | :700-706 |
| 78 | nano | Ahead on one window: Process Industries (6M), Finance (1M), Distribution Services (6M) | TRUE | Cards +1.9/−3.2, −10.0/+3.5, +18.8/−6.0 | :812 |
| 79 | nano | counted over today's members (no members-of-the-day history) | MISLEADING (minor) | nanocap_membership.json has lists from 31 Aug 2026 | :849-850 |

## Found along the way (not b_g1 entries)

- **SETL's sector differs by system on the same day**: "Capital Goods · fading" on the 1000 and "Health Technology · ahead on both" on nano. Nano uses TradingView's sectors, the others NSE's.
- **The nano book's month so far** reads −2.8% on the Dashboard and −2.9% on Portfolio ("Four systems, side by side"), for the same session.
- The chart readout "+₹1,22,265 foreign · a heavy-buying month" breaks PAGE_DESIGN §3a rule 2 (it should read +₹1.22 lakh Cr).
- `data/benchmarks.csv` already holds a 23 Nov row (source "screener"). The page cuts at 20 Nov for its trails; the percentile figures are unchanged with or without that row.
- The month-so-far figures for the book (+5.5%, +5.8%, −2.8%) were NOT recomputed: that needs the book's holdings and weights. Earlier months reproduce from the ledgers (750: product to Oct +38.26% × 1.058 = +46.3%; 8 of 11 ahead of Nifty Total Market, behind in Jul, Oct, Nov).

## Not checked, and why

Rank trails and leadership turnover (#10) need the rank engine re-run. The sector 6M/1M figures (#7, #44) need the ranked list with its sectors. Book month-to-date needs the holdings. Nano's own-universe figures (#66 17%, #77) need prices not all in the NSE long close.

## Counts (80 entries, one verdict per entry, by its worst part)

| Verdict | Count | Entries |
|---|---|---|
| FALSE | 8 | #0, 1, 12, 56, 66, 68, 71, 75 |
| MISLEADING | 9 | #4, 15, 25, 31, 35, 55, 67, 70, 79 (the 1000's base date sits inside #0/#1; the streak inside #56/#71) |
| LEAD (not reproduced; needs a check) | 2 | #39 (1000, 12M), #40 (1000, narrowest) |
| NOT CHECKED | 2 | #10, #77 |
| TRUE (including TRUE-static) | 59 | the rest |
