# To do

The one list of what is still open. Tick an item when it is done and verified,
with the date and the PR or run that proves it; move it to **Done** at the
bottom. Add anything promised in a conversation here the same day.

_Last updated: 2026-10-03_

## Now

| # | What | How we know it is done | Status |
|---|---|---|---|
| 1 | Merge PR #255: Production QA waits for the page's run before judging the ☰ menu | #255 merged; post-merge V1 Production QA green | [x] 28 Sep (#255) |
| 2 | Read the 4th NSE comparison (run on b1cb342: demergers and month-first ex-dates handled) | Report read, results given to the owner: drift beyond 1% (was 58), Spearman and top 20/50 per system | [x] 27 Sep, run 36331991821: 50 stocks, Spearman 0.9997 / 0.9984 / 0.9991 |
| 3 | Decide: NSE as the middle price source (Screener → NSE → Yahoo) | Owner says yes or no after item 2 (Claude recommends yes, skipping the ~50 stocks still off) | [x] 2 Oct: owner said yes |
| 4 | If yes: switch the price order in the app | PR merged; precompute accepted in production; docs updated | [x] code merged 2 Oct (see CHANGELOG); [ ] confirm the next nightly precompute is accepted |

## Prices: SS, three-source check, NSE history (2 Oct 2026)

Rules and status: `docs/PRICE_PIPELINE.md`.

| # | What | How we know it is done | Status |
|---|---|---|---|
| S1 | SS store for every symbol, page 1 | 1,216 stored; the 20 failures are renamed symbols stored under their new names | [x] 2 Oct, `ss_sync` run 36981505043 |
| S2 | Rights factor, two-of-three vote with NSE as judge, nightly report | Merged; real run on 1,214 stocks: all 10 rights issues settled, 0 unexplained level shifts | [x] 2 Oct (#330) |
| S3 | Nightly 22:02 IST: SS update, release + R2 `prices/ss`, three-source report | First scheduled run's summary shows the report; `prices/ss` on R2 | [ ] first run tonight (2 Oct) |
| S4 | NSE history on R2 back to 2010 | `nse/prices_daily` from 10 Jun 2010 (0 failures), `nse/corporate_actions_history` 2010 – 2026 | [x] 2 Oct (#336, #342) |
| S5 | Missing-days check 2010 – today: every weekday R2 lacks asked of NSE once (a bundle = a missing day, now saved; none = a holiday, recorded in `nse/closed_days`), incl. Jan – 9 Jun 2010 (the mirror starts 10 Jun) | `nse_collect` run shows 0 days to go since 2010-01-01 | [x] 2 Oct: 114 sessions found and saved, 130 holidays recorded; confirmation run 37037900424: 4,216 sessions 2010-01-04 to 2026-10-01, **0 days to go** |
| S14 | History before 2010 for the 1 Jan 2010 ranking: 2008 – 2009 from NSE's classic bhavcopy, corporate actions from 2008 | `nse_history_import` with `pre2010_since=2008-01-01` | [x] 2 Oct, run 37039302479: 488 sessions, 0 failed; the 17 Oct 2009 Muhurat session fetched 3 Oct (run 37057071481) |
| S15 | History audit 2008 – 2026 and its fixes | Audit run green; each finding fixed or explained | [x] 3 Oct, run 37047812302: (1) 500 of 584 unconfirmed splits/bonuses were one action counted twice (daily Bc + yearly list) — fixed (#348); (2) 13 weekend special sessions 2010 – 2020 missing — collected (run 37054756653); (3) every holiday from 2021 held as a copy of the day before (the mirror files one) — importer reads the file's own date, builder drops copies, calendar check (`nse_calendar.py`); (4) mirror turnover in rupees, not lakhs, 2010 – 2018 (value x 1e5) — importer reads the unit, builder rescales |
| S16 | Long NSE price file for backtests (`nse_long_*.parquet`, release) | Built, units ~1 every year, no copies, 0 calendar flags | [x] rebuilt 3 Oct with every fix (run 37076597258): 1,419 series, 0 unpriced, 16 renames refused (all real breaks); index coverage 0.00% unpriced member-months in every index (was Nifty 500 2.31%) |
| S17 | Backtest "History from 2010": any index (Nifty 50/100/500, Midcap, Smallcap, Microcap, Total Market), months, traded-value floor; no market-cap cutoff, no rights (owner, 3 Oct) | #346 merged; Nifty 500 from Jan 2010 run on the real file | [x] 3 Oct (#346, #360): two tabs, lazily run; Nifty 50 against the Nifty 50 (#360) |
| S18 | Industry for the 217 index members no current list labels | `data/reference/historical_industries.csv`: NSE's four levels, each web-checked (owner's format) | [x] 3 Oct (#346): 171 high, 43 medium, 3 low |
| S19 | The long file against independent prices, every stock, every day (owner, 3 Oct: production-level price series for every index stock) | `scripts/audit_long_prices.py` against Yahoo, eod2, Tijori, Screener, SS, TejHQ, NSE MarketLens; every move beyond 21% up or down confirmed or explained | [x] 3 Oct: faults and fixes in `docs/PRICE_PIPELINE.md` (#348, #350, #353, #354, #355); 94% of 3.7M stock-days within 2% of eod2, 32 fake moves left before #355's fixes |
| S20 | Reference histories backed up, protected from R2 clean-up | `reference/*` and `prices/screener/max_history` on R2, `PROTECTED_DATASETS` in `r2_retention.py`, local copy | [x] 3 Oct: 8 datasets on R2 (#352, #355), release `ref_*`, `C:\Users\Quali\Paresh_reference_backup\2026-10-03` |
| S21 | Re-audit the file built with #355 (BZ days, 19 corrections) | Fake moves in index windows explained or fixed | [x] 3 Oct: big moves 1,226 down / 246 up confirmed, 1 + 1 fake; 50 largest History trades checked on the web, 49 real, PFIZER a dividend (S31); rights issues and small bonuses now adjusted (MarketLens breaks where ours moved 52 -> 1); Nifty 500 2010-2026 19.8%/yr vs 10.3%, Sharpe 0.69, max drawdown -37% |
| S22 | J&K Bank 2015-02-09: -18% that MarketLens shows and Yahoo does not | Find the action; correct or leave | [ ] |
| S23 | Decide: fill Screener's sparse history (weekly before the latest year) with NSE's daily closes in the app's price frame | Owner decision: Screener's 9M/12M momentum windows reach further than a year on the sparse stretch (2026 Total Market backtest: ~1 holding a month differs) | [ ] owner |
| S24 | SS full history (history mode, 912 stocks back to listing) | `ss_sync` mode=history runs complete; SS added to the audit | [ ] run 37061786684 started 3 Oct |
| S25 | Renames refused for a consolidation on the rename day (NANDAN -> NDL +976%, SIGNET -> SIGIND +688%, SEINVEST -> PAISALO +854%) | Take that day's factor out of the move before the continuity check | [ ] low (small caps) |
| S26 | TUBEINVEST -> CHOLAHLDNG (-26%, a demerger at the rename) refused | Demerger factor or notes.json entry, if it matters | [ ] |
| S27 | Suspended or delisted holdings are valued at their last price | Checked 3 Oct: 7 of 1,570 History exits used a price 9 - 28 days old, all takeovers/open offers (UTV, Alfa Laval, Patni, Nirma, Chemplast) where holders were bought out near the last price | [x] no change needed |
| S28 | data/benchmarks.csv rewritten by the daily sync with formatting only (19384.30 -> 19384.3) | benchmark_store.write uses float_format="%.2f" and keeps 19384.30 locally on the same code; the sync run 37066457318 still dropped the zero: find which step rewrites it | [ ] small |
| S29 | Screener full history (weekly before the latest year) as a source | On R2 `prices/screener/max_history` and release; kept apart from the app's store | [x] 3 Oct |
| S30 | Tapetide MCP (needs the owner's token) for disputed cases only | Owner adds a token if wanted | [ ] owner, optional |
| S31 | Large dividends read as falls (PFIZER Rs 360 on 5 Dec 2013, 21% of the price; 23 stocks paid 10%+ in one go) | Owner: adjust dividends above a threshold (say 10%), all dividends, or none (today: none, like Screener and the live system). `large_dividends.csv` in the audit lists them | [x] 3 Oct: owner chose option 1, dividends of 10% or more adjusted (28 events) |
| S32 | Audits after every rebuild: Screener point-by-point, raw bars, ISIN lineage, calendar (`audit_against_screener.py`, `audit_raw_bars.py`) | Run by nse_long_prices.yml; `long_price_audit_latest.zip` on the release | [x] 3 Oct |
| S33 | Yahoo level breaks where ours moved (408 in the 3 Oct audit), the bar errors and every gap in the file, checked against NSE's own rows, BSE and the web (owner, 3 Oct) | Each explained or corrected; the method and the explained findings in `docs/DATA_CORRECTNESS.md` | [x] 3 Oct: the 408 are 33 stocks (5 hold 320), Yahoo stale; 240 close-outside-range rows are series T0, 1,372 average-price rows are turnover rounded to lakhs. Gaps: BSE bhavcopy 2008-2026 downloaded (4,625 sessions, 15.4M rows; 20 sessions Jun 2008 - Jan 2010 have no BSE file) and every gap of 5+ sessions checked: 147 NSE-only (BSE traded; 60 stocks, 4,995 sessions), 79 no BSE trading either, 18 partly, 182 not checked. The 26 Oct 2023 - 17 Apr 2026 gap (GOODYEAR, NOVARTIND, KENNAMET, KIRLFER, GRAUWEIL; FORCEMOT to 14 Feb 2024) is NSE's withdrawal of dealings under Permitted to Trade (NSE Indices notice 17 Oct 2023, circular NSE/CML/58560), not a halt and not a download fault; only DYNAMATECH and ZODIACLOTH (9 sessions, Aug 2013) were index members in a gap. One fault: KESORAMIND's demerger (10 Mar 2025, -95%) was unadjusted: notes.json correction x0.0474 (#372); [ ] rebuild the long file and rerun the audit after merge |
| S34 | BSE bhavcopy on R2 as scratch (owner, 3 Oct: upload everything, raw included, delete after the data is aligned) and the gap check as a standing audit | `bse_bhavcopy_r2.yml` green; objects under `scratch/bse_bhavcopy_2026-10-03/` (19 raw tars, table, gap CSV, MANIFEST.json); then delete the prefix when NSE and BSE are aligned | [ ] workflow added in #372, run after it is merged or from the branch |
| S35 | The 182 gaps not checked against BSE (no NSE close under the current symbol: renamed stocks; no BSE price match; 27 NSE-only matches flagged ambiguous) | Match by rename chain and by name; every gap classified | [ ] |
| S36 | Why NSE has no rows for 77 stocks for about a month in Aug - Oct 2013 (MAITHANALL, IOLCP, SAKSOFT, NEXTMEDIA ...); NSE's 20 Aug 2013 bhavcopy has no row in any series | Find NSE's notice; or record as unexplained | [ ] low (no index member affected) |
| S37 | Read NSE circular NSE/CML/58560 (25 Sep 2023) and find the notice that put the six stocks back (FORCEMOT 14 Feb 2024; the others 20 Apr 2026): dates now come from NSE's files only | Circular and reinstatement notices read and quoted in `DATA_CORRECTNESS.md` | [ ] low |
| S38 | Fill gaps like Goodyear's from BSE in the long file (the price exists on BSE) | Owner decision: only matters for a stock that is an index member during a gap, and two stocks were (9 sessions, 2013) | [ ] owner, low |
| S39 | Backtest tab: Calendar returns (year by month, CY / FY / quarters, Strategy / index / Alpha) in both modes, as on Portfolio (owner, 3 Oct) | PR merged; look at History from 2010 on the live site | [x] 3 Oct, PR below; checked on two real index series 2010 - 2026 (years compound to the curve's total exactly), not yet on a real strategy run |
| S40 | The Alpha row's CY / FY / quarter cells on Portfolio and Track Record are the monthly alphas compounded, not the year's strategy return minus the index's (2010 at +17.7% against +25.2% reads -6.4%, not -7.5%); the Backtest tab uses the plain difference | Owner decides: change Portfolio and Track Record to the difference too (`build_combined_grid(..., alpha_as_difference=True)`), or keep | [ ] owner |
| S6 | Renames from NSE's symbol-change list and ISINs | 575 found, 0 conflicts, all 21 ledger renames among them | [x] 2 Oct (#341) |
| S7 | Adjustment check across 2010 – 2026 (splits, bonuses, rights, demergers, renames) | Report: unexplained jumps listed and explained or fixed | [x] 3 Oct: see S19 |
| S8 | Long backtests on the 2010+ NSE history, Nifty 500 universe (S13) | Owner reviews the results | [ ] owner reviews: Nifty 500 2010 - 2026 18.3% a year (Sharpe 0.63, max DD -38%), Total Market Nov 2021 - Sep 2026 19.2% (vs 7.9%) |
| S9 | SS as the app's primary source? | Owner decision | [x] 2 Oct, owner: **keep Screener as the app's source for now** (and its NSE + BSE volume for the liquidity floor); SS stays collected and checked nightly |
| S10 | Remove dead Yahoo code and the `yfinance` dependency | PR merged | [ ] (other session's list too) |
| S11 | Membership × bhavcopy check and its fixes (join follows NSE's symbol-change list; KBL, ASIANHOTEL, PROVOGUE; REIT series RR) | Report; owner approves fixes | [x] 2 Oct, `reports/membership_bhavcopy_check_2026-10-02.md`; owner approved |
| S12 | Tata Motors DVR counted with Tata Motors (one company, one slot) | Owner decision; test | [x] 2 Oct (`backtester.SAME_COMPANY`) |
| S13 | Long backtest universe: **Nifty 500, 2010 to date** (no point-in-time Total Market list before 29 Oct 2021; the 750 backtest starts Nov 2021) | Owner decision | [x] 2 Oct, owner: Nifty 500 |

## Handover (2026-10-03, 04:50 IST)

Merged today: #345 - #355, #357 - #362 (long price file, its audit and every
fix, raw pack, the Backtest page's two tabs, docs). #356 closed (superseded by
#358 and #362). Running on GitHub while the laptop is off: the long price
rebuild (run 37076597258) and the SS history download (ss_sync mode=history,
run 37061786684). Next session: S21, then S23 (owner decision), S22, S25,
S26, S28, S10. Backups: R2 `reference/*` + `prices/screener/max_history`
(protected), release `ref_*`, local `C:\Users\Quali\Paresh_reference_backup\2026-10-03`.

## UI and data overhaul (raised 1 Oct 2026)

Full findings and work packages: `docs/UI_OVERHAUL_PLAN.md`.

| # | What | How we know it is done | Status |
|---|---|---|---|
| U0 | Owner approves the plan and decisions D1-D6 | Owner reply | [x] 1 Oct (all approved) |
| U1 | Engine fixes: open trades kept (NaT filter), live-month changes in the tradebook, `record_run` moved out of the view | Tests; Portfolio shows Open trades and rebalances after Aug | [x] 1 Oct, branch ccr-31392d93-bokbml (1,817 tests pass); live check after merge |
| U2a | Type tokens: one UI family (Geist; Bricolage dropped), mono for numbers only; Portfolio/Backtest/Full Quant tables restyled to the Screener look | PR merged; look at Portfolio and Backtest on the live site | [x] merged (#304) |
| U2b | Full Quant moves onto the one Screener table (WP5.2): one column registry; Core drops Sharpe, uses 3M DD; sub-line fixed (sector · index · company). Table/Grid toggles next (WP1.3) | PR merged | [x] merged (#304) |
| U2c | One chart component (WP2): `src/ui/lw_chart.py`, Lightweight Charts vendored, crosshair + all-series legend; Breadth, Portfolio equity+drawdown, Backtest and Track Record growth moved onto it. RRG is Highcharts | PR merged; check hover on the live site | [x] merged (#304) |
| U3 | Portfolio rebuild and Track Record merge (WP3, WP4): Portfolio is one page (book, exposure, equity+drawdown, calendar, record, trades, rebalances); `/track-record` redirects to it | PR merged; live check | [x] merged (#304) |
| U4 | Screener (WP5): done in PR (Quant master table, movers tabs, not-qualified preset, new-highs counts). Breadth charts, RRG benchmark/wording and Configuration summary done in PR. Track Record merged into Portfolio; text sweep (Sectors, Actions, Guide) and heading glossary (Open, Unrealised P&L) done in PR | PR merged; live check | [x] merged (#304) |
| U5 | Data catalogue, NSE vs Yahoo comparison, R2 policy (WP10) | `docs/DATA_CATALOGUE.md` written (datasets, writers, readers, retention, source order, comparison status). Freshness table now in Configuration. Still open: fourth NSE report and the price-order decision | [ ] partly done |
| U6 | Hide the TradingView logo on every Lightweight chart (`layout.attributionLogo: false` in `lw_chart.py` and `lightweight_chart.py`); the vendored v4.2.0 draws it by default | PR merged; no logo on the stock page | [x] 3 Oct (#364): 41 chart tests pass |
| U7 | Upgrade vendored Lightweight Charts v4.2.0 -> 5.x: `addSeries(LineSeries, ...)` calls, `tests/test_lw_chart.py`, look at the stock, Breadth, Backtest and Portfolio pages; native panes can replace the hand-synced stack later | Separate PR merged; logo still off; charts checked on the live site | [x] 3 Oct: v5.2.1, series via addSeries, rendered in Chromium (candles, volume, baseline, area, line, synced panes): no errors, no logo |
| U8 | Refresh every stock's TradingView sector and industry, not only the blank ones (`classify_missing.py --refresh`, weekly): 22 stale rows corrected, 5 Nano Cap labels | PR merged; nightly step green | [x] 3 Oct |

## Dated

| # | When | What | How we know it is done | Status |
|---|---|---|---|---|
| 5 | 30 Sep 2026, evening (check 18:30 UTC) | October Nano Cap list built; Nano Cap and Combined rankings published | `data/nanocap_membership.json` gains `2026-09-30`; `rankings_nano` / `rankings_combined` published and accepted | [x] 30 Sep, daily sync 36790408819: 429 stocks, Nano 391 / Combined 1,141 ranked |
| 6 | 1 Oct 2026 | First Nano Cap and Combined model books; their backtest shows September | Actions and Backtest with `?sys=nano` / `?sys=combined` | [ ] 2 Oct: daily sync green, `backtest_months` is 1 for both. Live check found the model book empty (engine returned nothing in a system's first month); fixed in the first-month book PR. Confirm on the live site after it deploys |
| 7 | 1–5 Nov 2026 | October frozen in all three ledgers | Track Record's "Three systems, side by side" shows Oct 2026 | [ ] |

## Portfolio (1 Oct 2026)

| # | What | How we know it is done | Status |
|---|---|---|---|
| P1 | Monthly view no longer crashes; Equity shows the marked month | #297 merged | [x] 1 Oct (#297) |
| P2 | On 1 Oct, September reads "Sep (closed)", not "Sep MTD"; Oct MTD says it is unavailable; "gap" → "Alpha"; Actions explains a fill due on the 1st. No ledger logic changed | #298 merged; V1 Production QA green on the merge commit | [x] 1 Oct: #298 (2e1e71e) and the QA wait fix #299 (a16a911); Production QA run 36839738078 incl. Portfolio visual QA, Full Validation 1214: green |
| P3 | PR #296 (another session): changes which month the ledger finalises (`ist_now()`); 19 tests fail. Owner to decide whether any of it is wanted; its Alpha rename and Actions note are in P2 | #296 closed, or rebased and green | [ ] owner |
| P4 | V1 Production QA was red on main from #317 (runs 753–756): `portfolio_production_qa.py` looked for the Equity/Monthly toggle the single Portfolio page replaced | Production QA green on main | [x] 2 Oct: #322 (4ca4c61) checks the card layout; run 757 green |

## Ongoing

| # | What | Cadence |
|---|---|---|
| 8 | Read the weekly NSE comparison; collect any missing session it lists (`nse_collect.yml` → dates); look at new unconfirmed actions and unexplained jumps | Sundays 06:40 UTC |
| 9 | Weekly R2 retention and recovery audit green (audit now reads 10 at a time, 40-min limit) | Weekly |

## Later

| # | What |
|---|---|
| 10 | All three price sources (NSE, Yahoo, Screener) in before 06:00 IST. Screener's nightly run for 1,167 stocks takes about 37 minutes |
| 11 | Delete merged remote branches (owner, by hand): `docs/BRANCH_CLEANUP_TODO.md` |

## Done (27 Sep 2026)

- System picker restyled; Combined no longer reverts after a stock page (#242)
- Industries for Nano Cap stocks from TradingView and Screener.in (#249; Value Research blocks scripts)
- Four flagged stocks in the production log resolved (#251)
- Top bar gains "Within 20% of 52W high"; repeated figures removed from every page; treemap and unused code removed (#252)
- Screener header on one row, so the table starts higher (#254)
- Portfolio (1 Oct): Monthly view crash fixed and Equity shows the marked month (#297); September reads "Sep (closed)", Alpha, Actions timing note (#298); Portfolio QA waits for the view to render (#299)
- R2 recovery audit no longer times out (#252: 7.5 and 15.5 min runs)
- NSE adjusted prices: splits and bonuses from the Bc file, confirmed by the price (#253); month-first ex-dates and demergers (#254); five missing sessions collected


## Done (30 Sep 2026)

- Streamlit hot-reload race and misleading pre-inception track-record warnings fixed in PR #263 (merge commit `3529e834352156fafbd8f8f8b359ac8fb13219fc`); concurrent reload regression and future-ledger regression added. Lint #237, V1 Full Validation #1061 and R2 Streamlit read-path gate #283 all green.

- Dynamic point-in-time membership history for all six production NSE indices merged in PR #258 (merge commit `73b095a49b52ab1a4a968e21e364610e94ed02a5`); pre-merge Lint, V1 Full Validation, R2 Focused Validation and R2 Streamlit read-path gates were green.
- Post-merge R2 historical evidence bootstrap run `36646326268` completed green: index constituent snapshots, point-in-time membership histories, combined universe, historical sector/industry classification, confirmed trading sessions, historical market caps and corporate-action evidence all published successfully.
- Post-merge R2 ranking calculation archive run `36646326289` completed green: canonical ranking artifact validated, published immutably and audited successfully.
