# S193 item B, group 2: are the sentences true to the data? Portfolio, Actions, Screener, Stock (RELIANCE)

Captured 23 Nov 2026 (prices of 20 Nov 2026), main at `2c91ca2`, systems 750 / 1000 / nano. Input: `b_g2.json` (97 entries, #0-#96 below).

**How each figure was checked.** I recomputed figures with pandas from the raw inputs the app reads:
- NSE's daily long file, `data_cache/nse_long_close.parquet`.
- Screener's store, `screener_prices.parquet`: the app's "deep" history. It is **weekly before mid-2025** (52 closes a year from 2017 to 2024; 108 in 2025).
- `data/nse_total_market.csv`, `data/benchmarks.csv`, the ledgers (`track_record*.json`), `book_exposure.csv`, `nse_market_caps.csv`, `results_calendar.csv`, `reference/nse/corporate_actions_recent.json`, `nse_prices/actions.parquet`, `nanocap_membership.json`.
- Each system's published ranking, read with `ranking_store.fetch_snapshot`. Only the ranks and the past-rank columns are taken from it.
- For holdings, share counts and trades, I parsed the page text and revalued them at NSE closes.

**Not checked independently.**
- Ranks and scores: I did not re-implement the ranking engine, so 381/1000, 294/750, 447/1,127, 810, 778 and the score are as published. The places among the qualified *were* recomputed, from filter flags I worked out myself and the published rank order.
- The book's daily equity series: beta, tracking error, the beat counts and the daily path.
- Volume.

| # | page | systems | sentence (short) | verdict | evidence (recomputed, source) | code | suggested fix |
|---|---|---|---|---|---|---|---|
| 0 | actions | all | "3 sells and 3 buys on Mon 30 Nov: ₹14.1 lakh out, ₹14.1 lakh in" | MISLEADING (minor) | The amounts are right. Sells ₹14,05,304 = shares × NSE 20 Nov close (SETL 1,246×357.5 and the others reproduce exactly). 750 ₹34.0/34.1 lakh, nano ₹22.6/22.6. But the trades fill on Tue 1 Dec (same page: "fills Tue 1 Dec"; Portfolio: signal 30 Oct, bought 2 Nov) | actions_page.py:149 | "… at the 30 Nov check, filled 1 Dec: …" |
| 1 | actions | 1000 | "BLISSGVS #31 · 9 places from the buffer; can fall 0.3% to its 50D EMA" | TRUE | Qualified place 31 (my filters + snapshot order); 40−31=9. EMA50 from NSE closes: fall 0.3% | exit_watch.py:102 | |
| 2 | actions | all | "Board meetings … announced to 5 Dec; ex-dates … collected to 10 Dec" | TRUE | results_calendar max 2026-12-05; corporate_actions_recent max ex 2026-12-10 | actions_page.py:453,459 | |
| 3 | actions | all | "Each buy gets 4.4% … the buys share the 13.3% the sells free up, which is less than the 5% buy size (the rule since 8 Nov)" | MISLEADING | The arithmetic is right: 3×4.44=13.3; 750 5×4.65=23.3; nano 6×4.1=24.6. (1) "which" attaches to 13.3%, and 13.3% is not less than 5%. The real comparison is 4.4% vs 5% (or 13.3% vs 3×5%). (2) The rule was decided on 8 Nov but applies from the 30 Nov signal (DATA_CORRECTNESS.md:111, TODO S111) | actions_page.py:402-405 | "…share the 13.3% the sells free up, 4.4% each, less than the 5% a buy gets under the rule from the 30 Nov signal (decided 8 Nov)." |
| 4 | actions | all | "Now: each stock at its weight today … Size by NSE's index lists …" | TRUE-static | Matches THREE_SYSTEMS.md definitions | actions_page.py | |
| 5 | actions | all | "Ordered by the least room on any rule …" | TRUE-static | Definitions; the hold table's figures reproduce (BLISSGVS 0.3%/7.9%, SONACOMS 5.2%/17.0%) | actions_page.py | |
| 6 | actions | all | "Data to 20 Nov 2026 · NSE. 1000 stocks ranked; 0 with a price gap, 6 with a short history" | TRUE | Fewer than 126 sessions recomputed from the price files: 1000→6, 750→5, nano→15 (same names). nano gaps: 2 🔴 | actions_page.py:325 | |
| 7 | portfolio | 1000 | "up 5.5% since 1 November, 2.6 points behind" | TRUE | Holdings (page share counts × NSE 20 Nov) ₹1,05,39,139 + ₹11,184 = ₹1,05,50,323 → +5.50%. NTM 2 Nov close 12,554.75 → 13,572.35 = +8.11%; lead −2.6 | portfolio_page.py:349-351 | |
| 8 | portfolio | 1000 | "₹1 Cr put in on 1 November 2026, run by the Nifty 1000 rules" | MISLEADING | THREE_SYSTEMS.md: "November is reconstructed (its 30 Oct book uses a list not public until 16 Nov)". The page says nothing of this, and there is no ledger (`track_record_1000.json` absent) | portfolio_page.py:346 | Add "November reconstructed: the 30 Oct list was published on 16 Nov" |
| 9 | portfolio | all | "20 holdings · tap a column…" | TRUE | 20 rows parsed on each page | portfolio_page.py:420 | |
| 10 | portfolio | all | "P&L … starts at the 2 Nov fill … Holdings X + Y not invested = value" | TRUE | Sums reproduce on all three. Entry prices = NSE 2 Nov close for 1000 buys | portfolio_page.py:411-418 | |
| 11 | portfolio | 1000 | "now, against the 1000, and at every rebalance since 1 Nov 2026" | TRUE | One rebalance (Nov) | portfolio_page.py:487 | |
| 12 | portfolio | 1000,750 | "mark: the sector's weight in the 1000 by market value" | TRUE | From nse_market_caps.csv × rank_df industries: Fin 25.8, CapG 8.8, Auto 7.4, HC 7.4, Oil 7.2 (1000), as shown | portfolio_page.py:488 | |
| 13 | portfolio | 1000 | "began Nov 2026 10% in Large Cap and Mid Cap and is now 90% Small, Micro and Nano Cap" | TRUE | Nov size split 5+5 / 30+25+35 (page bars; Actions "now" 5.3+4.6). "Began" and "now" are the same single rebalance | portfolio_page.py:477-482 | |
| 14 | portfolio | 1000 | "From the record's second year the table adds 12 months …" | TRUE-static | | portfolio_page.py | |
| 15 | portfolio | 1000 | "mostly Nano Cap and Small Cap … The mix holds the four NSE size indices in the book's own size split" | MISLEADING | Nano Cap (35%) has no NSE index, so the mix row is "–". The table beside it shows every index at 0.0% (see C4). Nothing on the page is a mix | portfolio_page.py:536 | Say the mix cannot be built while the book holds Nano/Ultra Nano Cap (no NSE index), or leave it out |
| 16 | portfolio | 1000 | "The growth chart starts once the book has two sessions; it has 1." | FALSE | The book has 14 sessions since the 2 Nov fill (NSE sessions 2–20 Nov). The app's equity has a single point, dated 30 Nov (a future date, in the chart table) | portfolio_page.py:627 | Build the live month's daily path for a system with no frozen month (as for the 750's live month); never date a point after as_of |
| 17 | portfolio | 1000 | "Top: what ₹100 put in on 1 Nov 2026 has grown to …" | TRUE-static | | portfolio_page.py:628 | |
| 18 | portfolio | all | "A drawdown is today's value against the highest value before it …" | TRUE-static | | portfolio_page.py:630 | |
| 19 | portfolio | 1000 | "· from December 2027 also the last 12 months and each year" | FALSE | The record starts 2 Nov 2026, so 12 months are complete in Nov 2027. The code adds a year to the equity's first point, which is 30 Nov 2026. 750 (Jan 2027) and nano (Oct 2027) are right | portfolio_page.py:612-613 | Base `second` on inception/first fill, not `p.equity.index[0]` |
| 20 | portfolio | all | "Volatility: … Beta: … Tracking error: … Capture: …" | TRUE-static | | portfolio_page.py:642 | |
| 21 | portfolio | all | "Tracking error X% means: … between about A% and B% …" | FALSE (1000); MISLEADING (nano); 750 arithmetic TRUE, TE not checked | 1000: "0.0% … between +10% and +10%". There are no risk figures (`rk` is None), and te falls back to 0. nano: 22.9% from 34 daily gaps, extrapolated to "over 12 months … two years in three". 750: ±16.6 → −7/+27; 16.6/√250=1.05 | portfolio_page.py:633-644 | Hide the paragraph when `rk` is None; below ~60 sessions, say the figure rests on N sessions |
| 22 | portfolio | all | "every month, quarter and year; each new year adds a row" | TRUE-static | | portfolio_page.py:967 | |
| 23 | portfolio | all | "2027 · from January, a row group like the one above" | TRUE-static | | portfolio_page.py | |
| 24 | portfolio | 1000 | "* Nov 2026, the first month: from the fill, 2 Nov …" | TRUE | NTM 2 Nov → 20 Nov +8.1%. Recorded Nifty 500 Jan (750) −3.47% = 1 Jan → 30 Jan close; nano Oct 0.17% = 1 Oct → 30 Oct, both from the fill | portfolio_page.py | |
| 25 | portfolio | all | "Frozen months stay as recorded against the Nifty 500 …" | MISLEADING (1000) | The 1000 has no frozen month and no ledger. Its row "Nifty 500, as recorded +8.3*" is worked out live, not recorded. Each live Nov column is also labelled "as recorded" (750 +10.0, nano +10.0) | portfolio_page.py:944-946 | Show the note and "as recorded" only for frozen months |
| 26 | portfolio | 1000 | "Day by day starts once the book has six sessions; it has 0." | FALSE | 14 sessions since the fill (13 daily returns); same cause as #16 | portfolio_page.py:739 | As #16 |
| 27 | portfolio | all | "Trade history: every trade and every rebalance line, with CSV" | TRUE-static | 750: 100 trade rows parsed = "100 trades" | portfolio_page.py | |
| 28 | portfolio | all | "“Since 1 Oct” is the window all three have traded …" | MISLEADING | The table is headed "Four systems". "All three" leaves out the Nifty 1000 without naming it, so the reader has to work out which three. The table itself has faults too (see C1-C3) | portfolio_page.py:887 | "…the window the 750, > ₹2,000 Cr and Combined have all traded; the Nifty 1000 joins from Dec" |
| 29 | screener | all | "N of the top 50 can be bought; M of the 50 were not in the top 50 a month ago" | FALSE (nano); TRUE (750, 1000) | nano: 22 of today's top 50 were not in last month's. Three had no rank a month ago (MILKYMIST #4, INDOMIM #18, MOLBIO #30), and `prev > 50` drops NaN, so the page says 19. 49/50 buyable: TRUE (my filters agree); nano 38 per snapshot, 41 by my filters (3 short-history names) | ranking_view.py:718-722 | Count `prev.isna() | (prev > 50)` |
| 30 | screener | all | "The N ranked stocks … buys the top 20 qualified and keeps … top 40" | TRUE | 1000/750/377 rows; TRACK_RECORD_CONFIG top 20, buffer 40 (on qualified rank, backtester.py:272) | ranking_view.py:725-727 | |
| 31 | screener | all | "Qualified: above the 50D EMA and within 20% of the 52W high …" | TRUE-static | My qualified counts: 341 (1000), 290 (750), 0 disagreements | screener | |
| 32 | screener | all | "Rank before: … on 20 Aug and 19 Oct" | TRUE | 20 Aug 2026 is a session; 20 Oct 2026 was Dussehra (holidays.csv), so 19 Oct | ranking_view.py | |
| 33 | screener | all | "Held: … the two rows where those places fall are named" | TRUE-static | | ranking_view.py | |
| 34 | screener | all | "Big movers: 150 places …; Volume spike 1.5×" | TRUE-static | | ranking_view.py | |
| 35 | screener | 1000,750 | "23 stocks entered the top 50 and 23 left; MAXHEALTH climbed 713 places, #972 → #259" | TRUE | From snapshot Rank/Rank(−1M): 23/23; MAXHEALTH is the largest climb (750: 527, #729 → #202) | ranking_view.py:897-902 | |
| 36 | screener | all | "Ranks among the ranked stocks on 19 Oct, the last session on or before …" | TRUE | As #32 | ranking_view.py:903 | |
| 37 | screener | 1000 | "Nifty 1000 · 1000 of 1000 stocks ranked as one list" | TRUE | 1000 rows; every one has ≥30 closes | ranking_view.py | |
| 38 | screener | all | "54.2% below its 52W high; the filter is within 20%" | TRUE | ALOKINDS 7.93 vs 252-session high 17.30 = −54.2%; NETWORK18 −45.7%; MOSCHIP −34.9% (NSE closes) | screener_table.py:414 | |
| 39 | screener | 1000,750 | "A holding is kept to here: the 40th qualified" | TRUE-static | | screener | |
| 40 | stock | 1000 | "Reliance … 381st of 1000, passes both filters and is not in the model book" | TRUE | Close 1377.5 > EMA50 1277.0; 13.5% below 1592.3 (NSE). Not among the 20 holdings. Rank as published | stock_lines.py:132 | |
| 41 | stock | 1000,750 | "₹1,378 at the close on 20 Nov 2026. Down 11.1% in 12 months, against +0.8% … ₹18.64 lakh Cr" | TRUE | NSE: 1549.1 (20 Nov 2025) → 1377.5 = −11.08%. NTM same sessions +0.77%. Market cap 18,64,107 Cr (NSE file) | stock_lines.py | |
| 42 | stock | 1000 | "Also 294th of 750 … 447th of 1,127 in Combined" | TRUE | Snapshots 750 rank 294; combined 1,127 rows, rank 447 | stock_view.py:249 | |
| 43 | stock | 1000 | "283rd of the 341 that pass both filters, past the keep line" | TRUE | Recomputed: 341 qualified, RELIANCE 283rd (750: 235th of 290) | stock_lines.py:217 | |
| 44 | stock | 1000,750 | "A past rank is how today's rule ranks … Score 0.222, all five horizons" | TRUE | Snapshot score 0.2219 / 0.2014; Horizons Scored 5 (score not re-implemented) | stock_lines.py | |
| 45 | stock | 1000,750 | "A holding would be sold if this holds at the 30 Nov check: it is ranks #283 …" | TRUE (grammar) | 283 > 40. "it is ranks" is ungrammatical | stock_lines.py:332 | "it ranks #283 of the qualified" |
| 46 | stock | 1000,750 | "no board meeting is announced before then (last results meeting 30 Oct)" | TRUE | results_calendar: RELIANCE 2026-10-30 results (held), nothing later; no ex-date in corporate_actions_recent | stock_lines.py:390-401 | |
| 47 | stock | 1000,750 | "The all-time closing high is ₹1,597, on 12 Jul 2024." | FALSE | NSE daily long file: ₹1,600.90 on 8 Jul 2024; 15 Jul (1,597.22) is also above 12 Jul (1,596.73). The figure comes from Screener's store, which is weekly before mid-2025 and has no close for 8-11 Jul 2024 | stock_lines.py:414; ATH from sync_data.py:378-391 | Take the ATH snapshot from NSE's daily long file, not Screener's store |
| 48 | stock | 1000,750 | "Down 11.1% … its max drawdown was 27.3%" | TRUE | 12M max drawdown on NSE closes −27.28% | stock_lines.py:526-535 | |
| 49 | stock | 1000,750 | "One line is 1% of return …" | TRUE-static | | | |
| 50 | stock | 1000,750 | "Price returns … first session on or after the same date …" | TRUE-static | 1M from 21 Oct reproduces +13.9%, NTM +9.9%, lead +4.0. Note: the rank table on the same page uses 19 Oct (on or before), see C7 | stock_lines.py | |
| 51 | stock | 1000,750 | "Above its 50D EMA on 18 of the last 60 sessions; … 11.8% behind in 12 months" | MISLEADING | 18/60 TRUE (NSE). "11.8% behind" is the RS ratio (0.889/1.008 = −11.76%), written with "%". The table beside it says −11.8 pts by subtraction (−11.85). Glossary #4: a gap is pts, never % | stock_lines.py:570-576 (rs_words) | "…it has lagged Nifty Total Market by 11.8 points in 12 months", or keep the RS wording but not as "% behind" |
| 52 | stock | 1000,750 | "Three panes: price with its 50D EMA (none before 30 sessions) …" | TRUE-static | min_periods=30 (stock_chart.py:236) | stock_lines.py:579 | |
| 53 | stock | 1000 | "Fourteenth of 26 Oil & Gas stocks; 10 of them pass both filters" | TRUE | 26 "Oil Gas & Consumable Fuels" in the 1000; RELIANCE 14th by rank; 10 qualified (my filters). 750: 8th of 19, 8 pass | stock_lines.py:30-50 | |
| 54 | stock | 1000,750 | "The eight best-ranked of the sector's 26, with this stock" | MISLEADING (1000); TRUE (750) | 1000: the table shows the 7 best plus RELIANCE (14th). AEGISLOG, 8th best (rank 243), is left out | stock_view.py:391; stock_lines.py:591 | "The seven best-ranked of the sector's 26, and this stock (14th)" when the stock is outside the eight |
| 55 | stock | 1000,750 | "1 corporate action in NSE's lists, the latest a bonus ex 28 Oct 2024" | MISLEADING | NSE's action file starts 2024-10-04. The long record also rescales RELIANCE's 20 Jul 2023 Jio Financial demerger (19 Jul 2023 close 1,309.9 = 2,841.85×0.5×0.922). The page names no start date | stock_lines.py:712 | "1 corporate action in NSE's lists since Oct 2024 …" (the `since` is used only on the none-found path) |
| 56 | stock | 1000,750 | "A close on every session of the last 12 months; none carried forward" | TRUE | 248/248 sessions present (NSE) | stock_lines.py:678 | |
| 57 | stock | 1000,750 | "More than 126 sessions of prices, so the 52W high counts" | TRUE | | stock_lines.py:685 | |
| 58 | stock | 1000,750 | "Ranked on all five horizons" | TRUE | Horizons Scored 5 | stock_lines.py:688 | |
| 59 | stock | 1000,750 | "The price is the 20 Nov close, the ranking's own day" | TRUE | | stock_lines.py:693 | |
| 60 | stock | 1000,750 | "All-time high from the long record, not a two-year window" | FALSE | "ATH Source = snapshot" means Screener's store (weekly before mid-2025), not NSE's long record. It misses the true high (#47) | stock_lines.py:699 | Fix the source (#47), or say "from Screener's weekly-then-daily history" |
| 61 | stock | 1000,750 | "Bonus, ex 28 Oct 2024: Bonus 1:1; prices before it are scaled by 0.5" | TRUE | actions.parquet factor 0.5; long file is smooth 25 → 28 Oct 2024 (1,327.85 → 1,334.35) | stock_lines.py | |
| 62 | stock | 1000,750 | "Price: ₹1,549 … 50D EMA: ₹1,448 on 20 Nov 2025 … high ₹1,525 …" | FALSE (EMA part) | Price/low/high/RS reproduce (1,549, 1,378, 1,158, 1,592, RS 88.2/81.1/105.7). EMA50 on NSE daily closes is ₹1,454 on 20 Nov 2025 with a high of ₹1,527. The app computes it over Screener's store (weekly until mid-2025): ₹1,448 / ₹1,525 | stock_view.py:531-544; stock_chart.py:264-266 | Chart and EMA from NSE's daily long file, or start the EMA where the store turns daily (the 3Y range shows weekly points) |
| 63 | actions | 750 | "In their first month the record's 90 buys beat NTM by +3.1 points; the 70 sold, by +0.1 … three months +10.6 against +2.4. 9 of the 70 were bought back" | FALSE (not reproduced) | From the page's own 100 trades on NSE closes (21/63 sessions, as the code): 91 buys +2.7 pts, 71 sold +0.6; 3M +9.9 vs +2.7. On Screener's store: 90/+2.8, 70/+0.5. JBCHEPHARM (bought 1 Apr, sold 4 May) has no price in the app's frame and is dropped silently. Re-bought 9: TRUE. Also, `_ahead` counts sessions separately in stock and NTM, and NTM lacks 1 Feb and 8 Nov 2026, so windows over those days end on different dates | actions_page.py:262; swap_evidence.py:33-40 | Align the market to the stock's sessions; report trades dropped for lack of price; recheck the +3.1/+0.1 |
| 64 | portfolio | 750 | "up 46.3% since 1 January, 45.1 points ahead" | TRUE | Ledger Jan-Oct chained +38.26% × live Nov +5.8% = +46.3% (holdings ₹1,46,06,517 + ₹20,221 at NSE closes). NTM 1 Jan close → 20 Nov +1.17%; lead 45.1 | portfolio_page.py:349-351 | |
| 65 | portfolio | 750 | "₹1 Cr put in on 1 January 2026, run by the Nifty 750 rules" | MISLEADING | track_record.json: Jan-Sep 2026 are `origin: backfill`, finalized 1 Oct 2026; only Oct is `recorded`. No page text says the first nine months were worked out afterwards | portfolio_page.py:346 | "…; Jan-Sep worked out on 1 Oct 2026 from the rules, recorded month by month from October" |
| 66 | portfolio | 750 | "now, against the 750, and at every rebalance since 1 Jan 2026" | TRUE | book_exposure.csv rows from 2026-01-01 | portfolio_page.py:487 | |
| 67 | portfolio | 750 | "began the year 65% in Large Cap and Mid Cap and is now 90% Small Cap and Micro Cap" | TRUE | book_exposure Jan Large 30 + Mid 35 = 65; Nov tradebook Small 55 + Micro 35 = 90 (Actions now 55.4+34.6) | portfolio_page.py:477-482 | |
| 68 | portfolio | 750 | "From the record's second year …" | TRUE-static | | | |
| 69 | portfolio | 750 | "mostly Small Cap and Micro Cap … The mix holds the four NSE size indices …" | TRUE | Small 55 + Micro 35; the mix row is shown (+7.5%; mix value not recomputed) | portfolio_page.py:536 | |
| 70 | portfolio | 750 | "Top: what ₹100 put in on 1 Jan 2026 has grown to …" | TRUE-static | | | |
| 71 | portfolio | 750 | "Since 1 Jan 2026, 220 sessions" | TRUE | NSE price calendar 1 Jan-20 Nov 2026: 220 (incl. Sun 1 Feb budget and 8 Nov muhurat sessions; nse_total_market.csv has 218, lacking both) | portfolio_page.py:611 | |
| 72 | portfolio | 750,nano | "a 1% day for the index is a 1.0% (0.7%) book day" | NOT CHECKED | No independent daily book series (replay inside the app) | portfolio_page.py:603 | |
| 73 | portfolio | 750 | "* Jan 2026, the first month: from the fill, 1 Jan" | TRUE | Recorded Nifty 500 Jan −3.47% = 1 Jan → 30 Jan (benchmarks.csv) | | |
| 74 | portfolio | 750,nano | "Sessions the book beat NTM, 56% (41%)" | NOT CHECKED | 122/219 = 55.7%, 14/34 = 41.2% agree with #76; the daily book is not recomputed | portfolio_page.py:749 | |
| 75 | portfolio | 750,nano | "The book against NTM, last 20 sessions" | TRUE-static | | | |
| 76 | portfolio | 750,nano | "beat NTM on 122 of 219 (14 of 34) sessions" | NOT CHECKED | Session counts right (220/35 prices → 219/34 returns); the beats are not recomputed | portfolio_page.py:747 | |
| 77 | stock | 750 | "Reliance … 294th of 750, passes both filters …" | TRUE | As #40 | | |
| 78 | stock | 750 | "Also 381st of 1,000 … 447th of 1,127" | TRUE | Snapshots | | |
| 79 | stock | 750 | "235th of the 290 that pass both filters" | TRUE | Recomputed | | |
| 80 | stock | 750 | "Eighth of 19 Oil & Gas; 8 of them pass" | TRUE | Recomputed | | |
| 81 | actions | nano | "KABRAEXTRU can fall 2.7% to its 50D EMA; 4.1% to the −20% line" | TRUE | Screener closes: 720.2 vs EMA; 0.8×high gives 4.1% | exit_watch.py | |
| 82 | actions | nano | "PASHUPATI (to sell) Interim Dividend - Re 0.02 Per Share, 23 Nov" | TRUE | corporate_actions_recent.json ex 23-Nov-2026 | actions_page.py:449-457 | |
| 83 | portfolio | nano | "down 8.3% since 1 October, 17.9 points behind" | TRUE | Holdings at NSE/Screener closes ₹91,59,340 + ₹7,859 → −8.33%; NTM 1 Oct close → 20 Nov +9.61%; −17.9. Contradicted on the same page and others: see C2, C3 | portfolio_page.py:349-351 | |
| 84 | portfolio | nano | "₹1 Cr put in on 1 October 2026, run by the > ₹2,000 Cr rules" | TRUE | Ledger Oct `recorded`, finalized 3 Nov | | |
| 85 | portfolio | nano | "now, against the &gt; ₹2,000 Cr list …" | FALSE (display) | The page shows the literal "&gt;": `uni` is escaped at :435 and again by `_head` | portfolio_page.py:435,487 | Escape once (drop `e()` at :435 or in `_head`) |
| 86 | portfolio | nano | "mark: the sector's weight in the > ₹2,000 Cr list by market value" | TRUE-static | Definition (nano weights not recomputed) | portfolio_page.py:488 | |
| 87 | portfolio | nano | "began Oct 2026 0% in Large and Mid Cap and is now 100% Small Cap, Micro Cap, Nano Cap and Ultra Nano Cap" | MISLEADING | Nov split: Nano 40 / Ultra Nano 60. The book holds no Small or Micro Cap and, outside the 750, never can. The code always names Small and Micro | portfolio_page.py:478-482 | Name only the groups with weight > 0: "now 100% Nano Cap and Ultra Nano Cap" |
| 88 | portfolio | nano | "From the record's second year …" | TRUE-static | | | |
| 89 | portfolio | nano | "mostly Ultra Nano Cap and Nano Cap … The mix holds the four NSE size indices …" | MISLEADING | 60/40 is right, but neither group has an NSE index; the mix row reads "–" | portfolio_page.py:536 | As #15 |
| 90 | portfolio | nano | "Top: what ₹100 put in on 1 Oct 2026 …" | TRUE-static | | | |
| 91 | portfolio | nano | "Since 1 Oct 2026, 35 sessions" | TRUE | 35 price sessions incl. 8 Nov | | |
| 92 | portfolio | nano | "* Oct 2026, the first month: from the fill, 1 Oct" | TRUE | Recorded Nifty 500 Oct 0.17% = 1 Oct → 30 Oct | | |
| 93 | screener | nano | "19 stocks entered the top 50 and 22 left; JLHL climbed 233 places" | FALSE | 22 entered (3 had no rank a month ago, see #29). Both lists hold 50, so entered must equal left. JLHL 307 → 74 is the largest climb: TRUE | ranking_view.py:648 | `(now <= 50) & ~(prev <= 50)`; optionally say "3 of them new listings" |
| 94 | screener | nano | "377 of 411 stocks ranked … 34 too new (under three months)" | TRUE | nanocap_membership 2026-10-30: 411; the 34 unranked have 18-62 closes each | ranking_view.py:665 | |
| 95 | stock | nano | "RELIANCE is not in the current ranking of the > ₹2,000 Cr list." | TRUE | Not in the 377; the list is ≥ ₹2,000 Cr *outside the 750* | stock_view.py:433 | |
| 96 | stock | nano | "Not a member of > ₹2,000 Cr list. Ranks 294th of 750 …" | MISLEADING | The ranks are TRUE. But RELIANCE is ₹18.64 lakh Cr: "not a member of > ₹2,000 Cr" reads as false. It is left out because it is in the 750. Missing "the". The 740-character page drops price, chart, returns and filters, although all are on hand. It is not a data fault, but a dead end for a watchlist or shared link with `?sys=nano` | watchlist_lines.py:393; stock_view.py:433 | "RELIANCE is in the Nifty 750, so it is not in the > ₹2,000 Cr list (stocks of ₹2,000 Cr or more outside the 750)", and show the page in the system it belongs to |

## Contradictions within a page or across pages and systems

| # | where | what | evidence | code | fix |
|---|---|---|---|---|---|
| C1 | Portfolio · Four systems (nano, 1000 pages) | The Nifty 750 row is labelled "this book" on every page | Hard-coded `"this book" if sid == SYSTEM_750` | portfolio_page.py:228 | Compare with `system` |
| C2 | Portfolio · Four systems | > ₹2,000 Cr since start −8.5% and Nov −2.9% on the 750 and 1000 pages; −8.3% and −2.8% on its own page | Its holdings at NSE/Screener closes give −8.33% | portfolio_page.py:236 (`_comparison_price_frame`) | Read each system's live month from its own frame |
| C3 | Portfolio (nano) | Header: NTM +9.6% "since 1 October", lead −17.9. "Since 1 Oct 2026 against other indices": NTM +8.5%, lead −16.9 | 8.5% is from the 30 Sep close (equity's first point); 9.6% is from the 1 Oct fill | portfolio_page.py:505-512 | Use `first_fill` for `ytd_start` when the book began after 31 Dec |
| C4 | Portfolio (1000) | "Since 1 Nov 2026 against other indices": every index 0.0% while the header says NTM +8.1% | `ytd_start` = equity's first point = 30 Nov 2026, after as_of | portfolio_page.py:505-512 | As C3 |
| C5 | Portfolio (1000) | Growth table row "30 Nov 2026 · 100.0" (a future date) while the book is +5.5% | Live month's point dated at month-end | portfolio_view `_daily_with_live` | As #16 |
| C6 | Portfolio across systems | "Month so far · Nov" NTM +9.8% (750, nano) and +8.1% (1000) | 1000 from its 2 Nov fill (footnoted), others from 30 Oct | portfolio_page.py:275-290 | Footnote the tile as well as the calendar |
| C7 | Stock | The rank table reads 1M on 19 Oct (on or before); the returns table's 1M runs from 21 Oct (on or after) | Both stated; 1M return 14.6% vs 13.9% by the two bases | stock_lines.py | Pick one convention for "a month ago" |

## Counts by verdict (97 entries)

| verdict | count |
|---|---|
| TRUE (data checked) | 49 |
| TRUE-static (no data) | 21 |
| FALSE | 11 (#16, 19, 21, 26, 29, 47, 60, 62, 63, 85, 93) |
| MISLEADING | 13 (#0, 3, 8, 15, 25, 28, 51, 54, 55, 65, 87, 89, 96) |
| NOT CHECKED | 3 (#72, 74, 76: no independent daily book) |

Plus 7 contradictions (C1-C7), five of them false figures or labels on the page (C1-C5).
