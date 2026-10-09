# To do

The one list of what is still open. Tick an item when it is done and verified,
with the date and the PR or run that proves it; move it to **Done** at the
bottom. Add anything promised in a conversation here the same day.

_Last updated: 2026-10-08_

## Now

| # | What | How we know it is done | Status |
|---|---|---|---|
| 1 | Merge PR #255: Production QA waits for the page's run before judging the ☰ menu | #255 merged; post-merge V1 Production QA green | [x] 28 Sep (#255) |
| 2 | Read the 4th NSE comparison (run on b1cb342: demergers and month-first ex-dates handled) | Report read, results given to the owner: drift beyond 1% (was 58), Spearman and top 20/50 per system | [x] 27 Sep, run 36331991821: 50 stocks, Spearman 0.9997 / 0.9984 / 0.9991 |
| 3 | Decide: NSE as the middle price source (Screener → NSE → Yahoo) | Owner says yes or no after item 2 (Claude recommends yes, skipping the ~50 stocks still off) | [x] 2 Oct: owner said yes |
| 4 | If yes: switch the price order in the app | PR merged; precompute accepted in production; docs updated | [x] code merged 2 Oct; 7 Oct: the nightly table is published and the app accepts it (headless run on main: "Precomputed ranking accepted: 750 rows, as of 2026-10-06") |

## Memory: Streamlit Cloud "over its resource limits" (8 Oct 2026)

Measurements and reasons: `docs/MEMORY_AUDIT_2026-10-08.md`.

| # | What | How we know it is done | Status |
|---|---|---|---|
| S61 | Shared price frames, bounded engine and backtest caches, import-deadlock fix, `MALLOC_ARENA_MAX` in the Dockerfile | PR merged with CI green; no "resource limits" email from Streamlit for 7 days after deploy; the startup metrics on production show no `r2_rankings=_DeadlockError` | [ ] PR open |
| S62 | Share the engine between sessions too (Portfolio still peaks at 1.44 GB with 4 sessions) | `calc.weights` no longer written on the cached engine; the 4-session Portfolio peak measured again with the audit's bench | [x] 8 Oct, PR #420 (2nd commit): `pipeline.engine_view`; Portfolio 1,440 -> 1,043-1,048 MB (two runs); every HTML element identical to #420's head with the engine forced. Target of 800 MB not reached, see S64 |
| S63 | `_comparison_price_frame` reads the cached Screener store instead of downloading it again | The comparison calls no downloader; it reads `src/loaders/screener_cache.py`, the store the app ranks from | [x] 8 Oct, PR #420 (2nd commit); also fixed: the selected system's frame was served from a cache keyed on names only, stale for up to an hour |
| S64 | Measure pyarrow's allocator: `pa.set_memory_pool(pa.system_memory_pool())` at startup (settable on Streamlit Cloud, unlike an env var) | 3 runs each way of the audit's bench; adopt only if the Portfolio peak drops beyond the run-to-run spread (~50 MB) with output identical | [ ] one run so far: 922 vs 1,045 MB |
| S65 | One backtest computing at a time across the server; a ceiling on the web sweep (owner, 8 Oct: the cheapest option first) | A second reader's new backtest shows "Backtest running: request queued" and runs after; a cached result is never queued; the page refuses a sweep over 50 combinations | [x] 8 Oct, this PR: `src/engine/compute_gate.py`; seen live in the app (queued message, both results rendered); two large History backtests at once rose +286 / +322 MB gated vs +410 / +391 MB on main |
| S66 | The History-from-2010 backtest held ~580 MB of rolling frames to keep ~3 MB of 52-week highs (each kept row was a view of its window); production went down at 12:52 UTC on 8 Oct during backtests | One reader opening History peaks well under 1 GB; values identical | [x] 8 Oct, this PR: `.copy()` in `_rolling_high_at`; single-reader History peak 1,156 -> 751 MB; values asserted equal to pandas' full rolling max |
| S67 | Memory telemetry on production (ported from #417, bounded): checkpoints at stage and page boundaries, a log line each time the process peak climbs 50 MB | Streamlit Cloud's log shows `Memory peak ... at page:...` lines after deploy | [ ] code in this PR; needs the deploy |
| S68 | Separate Streamlit app for the Backtest page (own container and memory, so a backtest cannot take down the Screener) | **Deferred** (owner, 8 Oct): decide from production telemetry. Revisit if the Streamlit Cloud log shows `Memory peak ... at page:backtest` lines near the container limit, or another restart without a Python error during backtests, after #421 is live | [ ] deferred |
| S69 | Every History-from-2010 parameter change grew the process 70-130 MB for good (owner saw it fail on production, 8 Oct): freed memory stayed in each rerun thread's malloc arena | Same clicks in the app stay near 500 MB resident instead of climbing; trim cost measured | [ ] this PR: `src/core/memory.release_freed_memory()` after every page; History session 830 -> 483 MB resident, weight changes +5-30 MB instead of +70-130 MB, ~5 ms per call |
| S70 | The queued message said "another reader's" when the only reader was the owner: Streamlit abandons a rerun when a slider moves but cannot stop a backtest part-way, so the reader's own earlier settings held the gate (owner, 9 Oct) | The message is amber and says whose run it is | [ ] this PR: `compute_gate.holder()`; reproduced with one reader, two lookback-weight changes |
| S71 | Every slider tick in Change settings started a full backtest (~20 s on History from 2010), most of them abandoned | One backtest per decision | [x] 9 Oct, this PR: every setting in one form with an Apply button (owner: yes) |
| S72 | Calendar returns: a year-by-year table (strategy, index, alpha) above the monthly grids (owner, 9 Oct) | The table's numbers equal each year's CY cells; part years labelled | [ ] this PR: `components.yearly_summary`; laid out like the monthly blocks (rows Strategy / index / Alpha, one column per year; owner, 9 Oct) |
| S73 | Backtest research options (owner, 9 Oct): EMA period, distance from the 52-week high, an all-time-high gate, and the score as Sharpe or plain lookback return; History's window and floor in the same form | Defaults identical to the live system to the last trade; each option changes the run | [ ] this PR: 2010 Nifty 500 history with defaults identical to 5dd3a90 (equity curve, 5,800 trades); plain return, ATH 20%, EMA 20, 52W 25% each differ |
| S74 | The parameter sweep did not test what the page showed: no window, universe, floor, actions or keep-rank were passed, so a History sweep scored the last 6 months (Apr-Sep 2026) on the Nifty 750's membership with no floor and keep-rank 1.5x instead of the page's | The sweep's base run equals the page's run; History holdout halves are ~100 months each | [x] 9 Oct, this PR: run_parameter_sweep takes the page's months, membership, actions, floor and traded value; base gets buffer_n. Nifty 500 2010: base run was Sharpe 4.74 over Apr-Sep 2026 vs the page's 0.68 over 2010-2026; now identical. Holdout read 3 + 3 months, now 101 + 100 |
| S75 | Separate rules to KEEP a holding (EMA, 52W, ATH; blank = same as buy) and free numbers for holdings, keep-rank and rebalance days (owner, 9 Oct: e.g. 23 holdings kept within top 77) | Keep rules equal to buy rules change nothing; looser keep rules buy and sell less | [x] 9 Oct, this PR: defaults identical on the 2010 history (equity, 5,800 trades); keep within 30% of 52W high: 46 -> 40 buys on the test fixture |
| S76 | A History sweep now really runs the 2010-2026 window: 3 combinations with holdout took 116 s locally, so the 50-combination cap is ~30 minutes | Owner decides: a lower cap for History sweeps, a time estimate before Run, or sweeps run as a nightly job | [ ] proposal |

## Prices: SS, three-source check, NSE history (2 Oct 2026)

Rules and status: `docs/PRICE_PIPELINE.md`.

| # | What | How we know it is done | Status |
|---|---|---|---|
| S1 | SS store for every symbol, page 1 | 1,216 stored; the 20 failures are renamed symbols stored under their new names | [x] 2 Oct, `ss_sync` run 36981505043 |
| S2 | Rights factor, two-of-three vote with NSE as judge, nightly report | Merged; real run on 1,214 stocks: all 10 rights issues settled, 0 unexplained level shifts | [x] 2 Oct (#330) |
| S3 | Nightly 22:02 IST: SS update, release + R2 `prices/ss`, three-source report | First scheduled run's summary shows the report; `prices/ss` on R2 | [x] scheduled runs green 5 and 6 Oct (37384853534, 37531426257); report on the release (`reconcile_*`) |
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
| S22 | J&K Bank 2015-02-09: -18% that MarketLens shows and Yahoo does not | Find the action; correct or leave | [x] 7 Oct: no action; a real fall on Q3 results (profit -67%), 8M shares; eod2, MarketLens, TejHQ the same, Yahoo stale. No change (`reports/dq_sweep_2026-10-07.md`) |
| S23 | Decide: fill Screener's sparse history (weekly before the latest year) with NSE's daily closes in the app's price frame | Owner decision: Screener's 9M/12M momentum windows reach further than a year on the sparse stretch (2026 Total Market backtest: ~1 holding a month differs) | [x] 7 Oct (#401): NSE's daily moves spliced to Screener's level by ratio, 2% check; 699 of 699 stocks of the 750 (the seven NSE's file lacks from the long file and BSE, SHILCTECH's 1:2 bonus of 6 Jun 2025 applied); filled days agree with SS 99.92%, Tijori 99.89%; ranking republished (daily sync 37656613953) |
| S24 | SS full history (history mode, 912 stocks back to listing) | `ss_sync` mode=history runs complete; SS added to the audit | [ ] history run 37633025189 (7 Oct) still running at 23:00 IST (340-minute limit); one more run after it; then read the manifest (stocks with full_history) |
| S25 | Renames refused for a consolidation on the rename day (NANDAN -> NDL +976%, SIGNET -> SIGIND +688%, SEINVEST -> PAISALO +854%) | Take that day's factor out of the move before the continuity check | [ ] low (small caps) |
| S26 | TUBEINVEST -> CHOLAHLDNG (-26%, a demerger at the rename) refused | Demerger factor or notes.json entry, if it matters | [x] 7 Oct: left as is. TUBEINVEST left the Nifty 500 after Apr 2017, before its series ends (23 Aug 2017); CHOLAHLDNG only ranks about seven months later than it could |
| S27 | Suspended or delisted holdings are valued at their last price | Checked 3 Oct: 7 of 1,570 History exits used a price 9 - 28 days old, all takeovers/open offers (UTV, Alfa Laval, Patni, Nirma, Chemplast) where holders were bought out near the last price | [x] no change needed |
| S28 | data/benchmarks.csv rewritten by the daily sync with formatting only (19384.30 -> 19384.3) | benchmark_store.write uses float_format="%.2f" and keeps 19384.30 locally on the same code; the sync run 37066457318 still dropped the zero: find which step rewrites it | [x] 7 Oct: pandas 3 made the closes `object` when a day added no rows, so `%.2f` was skipped; `merge` skips empty frames, `write` casts to float (sweep PR). [ ] next daily sync after merge writes two decimals |
| S29 | Screener full history (weekly before the latest year) as a source | On R2 `prices/screener/max_history` and release; kept apart from the app's store | [x] 3 Oct |
| S30 | Tapetide MCP (needs the owner's token) for disputed cases only | Owner adds a token if wanted | [x] 7 Oct: not needed now. Tapetide is a third-party NSE/BSE data service (MCP server, GitHub Tapetide-hq) needing the owner's token; it would only be a tie-breaker, and no disputed case is left unanswered |
| S31 | Large dividends read as falls (PFIZER Rs 360 on 5 Dec 2013, 21% of the price; 23 stocks paid 10%+ in one go) | Owner: adjust dividends above a threshold (say 10%), all dividends, or none (today: none, like Screener and the live system). `large_dividends.csv` in the audit lists them | [x] 3 Oct: owner chose option 1, dividends of 10% or more adjusted (28 events) |
| S32 | Audits after every rebuild: Screener point-by-point, raw bars, ISIN lineage, calendar (`audit_against_screener.py`, `audit_raw_bars.py`) | Run by nse_long_prices.yml; `long_price_audit_latest.zip` on the release | [x] 3 Oct |
| S33 | Yahoo level breaks where ours moved (408 in the 3 Oct audit), the bar errors and every gap in the file, checked against NSE's own rows, BSE and the web (owner, 3 Oct) | Each explained or corrected; the method and the explained findings in `docs/DATA_CORRECTNESS.md` | [x] 3 Oct: the 408 are 33 stocks (5 hold 320), Yahoo stale; 240 close-outside-range rows are series T0, 1,372 average-price rows are turnover rounded to lakhs. Gaps: BSE bhavcopy 2008-2026 downloaded (4,625 sessions, 15.4M rows; 20 sessions Jun 2008 - Jan 2010 have no BSE file) and every gap of 5+ sessions checked: 147 NSE-only (BSE traded; 60 stocks, 4,995 sessions), 79 no BSE trading either, 18 partly, 182 not checked. The 26 Oct 2023 - 17 Apr 2026 gap (GOODYEAR, NOVARTIND, KENNAMET, KIRLFER, GRAUWEIL; FORCEMOT to 14 Feb 2024) is NSE's withdrawal of dealings under Permitted to Trade (NSE Indices notice 17 Oct 2023, circular NSE/CML/58560), not a halt and not a download fault; only DYNAMATECH and ZODIACLOTH (9 sessions, Aug 2013) were index members in a gap. One fault: KESORAMIND's demerger (10 Mar 2025, -95%) was unadjusted: notes.json correction x0.0474 (#372); [x] long file rebuilt 3 Oct (run 37113597811): KESORAMIND's 10 Mar 2025 move 0.0474 -> 1.0006, the only one of 1,419 series that changed |
| S34 | BSE bhavcopy on R2 as scratch (owner, 3 Oct: upload everything, raw included, delete after the data is aligned) and the gap check as a standing audit | `bse_bhavcopy_r2.yml` green; objects under `scratch/bse_bhavcopy_2026-10-03/` (19 raw tars, table, gap CSV, status, MANIFEST.json); then delete the prefix when NSE and BSE are aligned | [x] 3 Oct, run 37113590210: 23 objects, each read back and SHA-256 checked; same gap counts as the local run. [ ] delete the prefix when aligned; [ ] standing audit (run the workflow after each long-file build) not scheduled |
| S35 | The 182 gaps not checked against BSE (no NSE close under the current symbol: renamed stocks; no BSE price match; 27 NSE-only matches flagged ambiguous) | Match by rename chain and by name; every gap classified | [ ] |
| S36 | Why NSE has no rows for 77 stocks for about a month in Aug - Oct 2013 (MAITHANALL, IOLCP, SAKSOFT, NEXTMEDIA ...); NSE's 20 Aug 2013 bhavcopy has no row in any series | Find NSE's notice; or record as unexplained | [ ] low (no index member affected) |
| S37 | Read NSE circular NSE/CML/58560 (25 Sep 2023) and find the notice that put the six stocks back (FORCEMOT 14 Feb 2024; the others 20 Apr 2026): dates now come from NSE's files only | Circular and reinstatement notices read and quoted in `DATA_CORRECTNESS.md` | [ ] low |
| S38 | Fill gaps like Goodyear's from BSE in the long file (the price exists on BSE) | Owner decision: only matters for a stock that is an index member during a gap, and two stocks were (9 sessions, 2013) | [x] 7 Oct (#400): NSE-only gaps filled from BSE's raw closes before the factors apply; BSE table workflow `bse_daily.yml` (run 37652902758: 4,628 sessions to 7 Oct, release + R2 `bse/daily`, protected); long-file build 37653298431: 24 gaps, 20 stocks, 3,443 cells filled (GOODYEAR, NOVARTIND, KENNAMET, KIRLFER, GRAUWEIL 614 sessions each), 387 refused with reasons |
| S39 | Backtest tab: Calendar returns (year by month, CY / FY / quarters, Strategy / index / Alpha) in both modes, as on Portfolio (owner, 3 Oct) | PR merged; look at History from 2010 on the live site | [x] 3 Oct, PR below; 7 Oct on a real strategy run (Nifty 500 History 2010 - 2026): the 201 monthly returns compound to the run's total exactly (18.9115x strategy, 4.0535x index) |
| S40 | The Alpha row's CY / FY / quarter cells on Portfolio and Track Record are the monthly alphas compounded, not the year's strategy return minus the index's (2010 at +17.7% against +25.2% reads -6.4%, not -7.5%); the Backtest tab uses the plain difference | Owner decides: change Portfolio and Track Record to the difference too (`build_combined_grid(..., alpha_as_difference=True)`), or keep | [x] 7 Oct (#403): the plain difference on every page (2010: -7.5 pts, not -6.4%) |
| S41 | Nifty 500 baseline of 31 Dec 2009: NSE's own list of 2 Jan 2010 (Wayback) has Zandu Pharmaceutical Works (ZANDUREALT) where ours has 3IINFOTECH; the other three differences that day are renames and a spelling (`check_nifty500_against_wayback.py`, 3 Oct) | Find the notice or list that settles it, correct the baseline or record why not; add ASIANHOTEL -> ASIANHOTNR and KBL -> KIRLOSBROS to the rename ledger | [x] 7 Oct: it does reach the first backtest month (the Jan 2010 rebalance ranks on the 31 Dec 2009 baseline) but changes nothing: Zandu (ZANDUPHARM then) was -14% over 2009 against +87% to +473% for the 20 bought; 3IINFOTECH was never bought. Rename ledger entries still to add |
| S42 | Index membership checked against NSE's published Nifty 500 list at 17 dates, 2010 - 2026 | 16 of 17 agree exactly; script and method in `docs/DATA_CORRECTNESS.md` section 8. The Nifty 50, Next 50, Midcap 150, Smallcap 250, Microcap 250 and Total Market have no such independent file beyond `wayback_check.py` | [x] 3 Oct |
| S44 | ANDHRAPAP rights 3:11 + warrants, ex 23 Feb 2010: NSE's text has no price, so nothing was applied to a -20% day; Rs 50 is quoted only in search summaries | A primary source (letter of offer, BSE notice) for the price; then a notes.json correction or leave. Not a Nifty 500 member until Apr 2016, so no backtest reads it | [ ] low |
| S46 | Data safety (owner, 7 Oct: clean-up must never delete the work): every NSE / index / ranking dataset protected in `r2_retention.py`, a scheduled run deletes at most 50 keys, the long file / SS / Screener stores are never replaced by smaller ones; local copy of the raw pack and long files in `C:/Users/Quali/Paresh_reference_backup/2026-10-07` | PR #396 merged; next Sunday's retention run and Saturday's long-file build green | [x] 7 Oct (#396); the first build under the guard (37653298431) passed it |
| S47 | Long-file gaps found by the R2 review (7 Oct): the yearly corporate-action list is imported by hand only (last 2 Oct); a session collected once is never re-read; the audit cannot fail the build | Schedule the yearly-list import monthly; a monthly full rebuild; audit thresholds that fail the job | [ ] |
| S48 | `src/ui/theme.py`: "% OF 52W HIGH START" and "% OF 52W HIGH END" are in both FRACTION_ and SCALED_PERCENT_COLUMNS (fraction wins); `membership_history.json` caveats name `docs/INDEX_MEMBERSHIP_PIT.md`, which does not exist | Check the unit on the live table; fix the list; fix the reference | [x] 7 Oct: the 52W columns declared once (#397); every "... %" column in src/ now declares a unit, after "Entry Weight %" crashed the Backtest page (#404), with a test that fails on any new undeclared one |
| S49 | Open PRs reviewed 7 Oct: #387, #388, #392 superseded by main (#386, #389 - #391, #393; #392's own test is wrong); #377 needs an admin-only switch before merging; #378 contradicts DATA_CORRECTNESS (Wayback check, refused renames) | Owner: close #387, #388, #392, #378; #377 change or close | [x] 7 Oct: #387, #388, #392, #378, #377 closed on the owner's decision, with reasons; #399 closed as superseded (its fix was already on main) |
| S50 | Portfolio wording (owner, 7 Oct): record caption without a sub-year annualised figure, drawdown named as the fall from a peak, no quarter / FY note, correlation reading in its heading | PR #397 merged; look at Portfolio on the live site | [x] 7 Oct (#397), plus #402: Production QA no longer waits for the removed live-month note |
| S51 | Live 2026 vs History 2026 (owner, 7 Oct: "half"): History's default universe is the Nifty 500, Live's is the 750 | Explained | [x] 7 Oct: same engine and NSE prices, the 750 from Jan 2026 gives +44.4% (Live's figure exactly), the Nifty 500 +16.2% to +17.2%; the gap is Apr, May, Aug, where the 750 held 7 - 10 stocks outside the Nifty 500 (STLTECH +70.5% and +82.0%, MTARTECH +70.0%, TDPOWERSYS +34.8%, SHILPAMED +42.7%; each move identical in NSE, Yahoo, eod2, Tijori, SS). For a like-for-like History run choose Nifty Total Market |
| S52 | BSE gap fill follow-ups (#400): the 3 Oct gap audit's price-only match picked another company for 47 of its 147 "NSE-only" gaps; 82 gaps refused at a junction are not each explained; `bse/daily` on R2 grows ~250 MB a copy, one a month (~3 GB a year) | Audit script matches by ISIN; junction refusals sampled; owner keeps or trims the R2 copies | [ ] draft #408: the gap audit now maps BSE codes by ISIN first (bse_fill.map_code): 97 NSE-only gaps in 35 stocks, not 123 in 47 (44 were another company's code); 15 of 82 junction refusals sampled (11 thin trading, 3 exchanges apart, 1 float edge at exactly 2%, ASIANELEC). Open: keep or trim the `bse/daily` copies on R2 |
| S53 | Weekly-fill follow-ups (#401): four Screener weekly closes disagree with SS, Yahoo and eod2 (PTCIL Oct 2024, SKYGOLD Oct 2024, SHAILY Feb 2025, MANORAMA Mar 2025); five intervals look like an action one side adjusted (UPL, THANGAMAYL, M&MFIN, LLOYDSENGG, LLOYDSENT); Nano Cap and Combined are not filled; the Backtest / Track Record blend fills Screener's sparse dates without the 2% check | Each looked up; decide on Nano Cap / Combined | [ ] |
| S54 | Long-file build speed: ~32 of its ~33 minutes are `read_actions` fetching every session's corporate-action file from R2 one by one (~9,400 requests); the computation itself takes ~15 s | Read them in parallel and keep an actions pack on the release (only new days read); a monthly full re-read (S47) | [x] 7 Oct (#407): build step 32 - 36 min -> 6.2 min with parallel reads (run 37663816040, no pack yet) -> 2.5 min with the pack (run 37664949192: 10 of 1,958 action days read); both files identical to the slow build's (every cell, 1,045 steps, 3,443 BSE cells) |
| S55 | Streamlit 1.64.0 -> 1.65.0 (owner, 7 Oct) | Merged; full suite and headless smoke on 1.65.0; live pages checked | [x] 7 Oct (#405): full suite and headless smoke on 1.65.0; V1 Production QA on 3bf4066 green (every live page opened without an error) |
| S56 | The committed `data/nse_prices/actions.parquet` has no rights issues (52 bonus, 39 split, 18 demerger rows): the app's NSE middle source, the weekly fill and the Backtest / Track Record blend move raw across rights ex-dates (14 since Sep 2024; HCC -23% raw on 5 Dec 2025). The long file is right (#408 report) | Find why the sync drops rights rows; add them; check the 750 record's months against a rights-adjusted replay | [ ] high |
| S57 | Nano Cap / Combined weekly fill: windows from Aug 2025 need 363 stocks; the long file + BSE cover 351, +8 NSE-only listings 359 (#408) | Owner: extend the weekly fill to them | [ ] owner |
| S58 | `blend_screener` (Backtest / Track Record frames): 15 of 39,537 junctions step over 2% (7 the missing rights of S56, 5 BSE-priced Screener closes, 3 demergers) | Fix S56; then leave or spread the rest | [ ] owner, after S56 |
| S59 | UI audit (owner, 7 Oct: too verbose, repeated text, look-alike blocks built differently): ~1,000 removable lines over 15 component families; 15 PRs proposed, Actions first. Found on the way: the Kite basket sized on Rs 10 lakh while Portfolio uses Rs 20 lakh; Portfolio ignores the Configuration caps / floor / volatility setting; Volatility targeting changes nothing; the stock page calls its Sharpe annualised | Owner approves the plan; each PR merged with its tests | [ ] owner |
| S60 | The 750 replayed on the long file from Jan 2026 gives Live's Jan - Sep total (+44.4%) but not its months (Jan -4.47% vs -0.21%, Feb +4.44% vs +0.70%, Apr +17.66% vs +18.78%) | Explain each month: price basis (Screener vs NSE long file, S56 rights), the Jan 2026 first book (signalled at the 31 Dec close), the record's config | [ ] |
| S45 | Rebuild the long file after the sweep PR (swapped-date twins: ALLCARGO demerger counted twice, HCG rights twice) | `nse_long_prices.yml` run on main; ALLCARGO has no step on 2025-12-11 and HCG none on 2026-02-03; audit zip read | [x] 7 Oct, run 37653298431 (size guard passed): only ALLCARGO (11 Dec 2025 now NSE's real -3.6%), HCG (3 Feb 2026 now NSE's real +1.81%) and GRAUWEIL (bonus, BSE fill) changed against the 3 Oct file; 3,448 cells added (BSE fill), 0 lost; sessions to 6 Oct |
| S43 | Two older open PRs not merged on 3 Oct: #331 (2026 membership rebuild: conflicts in 3 files, and its `membership_history.json` has no Nifty 500 and only 2025-12-31 baselines, where `main` has Nifty 50 / Next 50 / Nifty 500 back to 2010, so it would delete history) and #24 (Stage 4B pharma packets: 49 commits sharing no history with `main`) | Owner decides: close #331 (what it adds, the HEG/AKZO/DUMMY handling, may already be on `main`; check before closing); rebase or recreate #24 on `main` | [x] 7 Oct: #331 and #24 closed on the owner's decision, with the reasons in each |
| S6 | Renames from NSE's symbol-change list and ISINs | 575 found, 0 conflicts, all 21 ledger renames among them | [x] 2 Oct (#341) |
| S7 | Adjustment check across 2010 – 2026 (splits, bonuses, rights, demergers, renames) | Report: unexplained jumps listed and explained or fixed | [x] 3 Oct: see S19 |
| S8 | Long backtests on the 2010+ NSE history, Nifty 500 universe (S13) | Owner reviews the results | [x] 7 Oct: every one of 201 months recomputed independently from the rules (filters, score, buffer, caps; no engine code): the book equals the engine's every month, 0 rule breaks, fills on each month's first session, returns within 0.04 pts; all 1,590 trades re-priced: 1,583 within 2 pts of a reference, the other 4 are dividends of 10%+ and a MarketLens raw bonus; Tijori 1,258 / 1,260 within 2 pts. `reports/dq_sweep_2026-10-07.md` |
| S9 | SS as the app's primary source? | Owner decision | [x] 2 Oct, owner: **keep Screener as the app's source for now** (and its NSE + BSE volume for the liquidity floor); SS stays collected and checked nightly |
| S10 | Remove dead Yahoo code and the `yfinance` dependency | PR merged | [ ] (other session's list too) |
| S11 | Membership × bhavcopy check and its fixes (join follows NSE's symbol-change list; KBL, ASIANHOTEL, PROVOGUE; REIT series RR) | Report; owner approves fixes | [x] 2 Oct, `reports/membership_bhavcopy_check_2026-10-02.md`; owner approved |
| S12 | Tata Motors DVR counted with Tata Motors (one company, one slot) | Owner decision; test | [x] 2 Oct (`backtester.SAME_COMPANY`) |
| S13 | Long backtest universe: **Nifty 500, 2010 to date** (no point-in-time Total Market list before 29 Oct 2021; the 750 backtest starts Nov 2021) | Owner decision | [x] 2 Oct, owner: Nifty 500 |

## Handover (2026-10-08, ~01:15 IST) - start here tomorrow

Merged on 7 Oct, evening: #394 - #397, #400 - #412. The overnight cloud
run was called off (owner works on the laptop instead); the queue is
written down on branch `fix/rights-in-committed-actions`
(`docs/handoff/OVERNIGHT_2026-10-08.md`, `UI_AUDIT_2026-10-07.md`). No code
started: the `fix/s56-rights-actions` worktree has no changes. Running on
GitHub: SS history run 37666859753 (S24).

In order:

0. **Live app froze (owner, 8 Oct ~01:20 IST):** "downloading data" on every
   click after tonight's merges, which it did not do before. #410 (History
   precompute, shared long file), #411 (startup import fix) and #412 (reload
   in place) were reverted to put the app back as it was. Find the cause
   locally first: suspect #412 re-running the in-place reload on every rerun,
   which would reset module-level data. Then bring the three back one at a
   time, each checked on the live site with several clicks across pages
   before the next. Done when History opens from the stored run on the live
   site, no page shows "Loading market data" on a click, and the startup
   log has no deadlock.
1. **S56 (high).** Cause found: `data/nse_prices/actions.parquet` was last
   written by #302 (1 Oct), before #330 made `sync_nse_prices.keep_actions`
   keep rights rows; `--update` only appends new sessions' actions; and
   `nse_prices.ACTION_COLS` has no `face_value`, so even kept rights rows
   cannot be priced (`nse_adjusted._rights` needs face value + premium).
   Fix: add `face_value` to ACTION_COLS (reindex where missing); add
   `sync_nse_prices.py --refresh-actions` (re-read every action in the
   committed window with `scripts/nse_history_audit.read_actions`, swapped
   twins dropped) and make `--update` refresh too; a workflow_dispatch input
   that runs it on GitHub (R2 keys) and commits `data/nse_prices`. Then
   replay the 750 record's Jan - Sep 2026 months with rights applied and
   record any month that changes for the owner (frozen months are not
   rewritten). Evidence: `reports/followups_s52_s53_2026-10-07.md`
   (14 rights ex-dates since Sep 2024; HCC -23% raw on 5 Dec 2025).
   Then S58 and S60, which depend on it.
2. **Bug: Kite basket sized on Rs 10 lakh** while Portfolio uses Rs 20 lakh
   (`actions_view.py` ~292 reads a capital nothing sets): use the Portfolio
   capital; add a test.
3. **Bug: Volatility targeting changes nothing** (`config_view.py` ~402 - 406;
   `portfolio_view` ~493 discards it): remove the control (owner's choice).
4. **S59 UI audit, the 15 PRs** in the audit's order (Actions text pass
   first). Each: full tests, `scripts/headless_smoke.py`, a local look;
   `scripts/portfolio_production_qa.py` changes in the same PR as the
   Portfolio text it checks. Batch merges (each merge redeploys).
5. **S24:** when run 37666859753 ends, read `ss_manifest.json`
   (full_history count); if stocks still lack it,
   `gh workflow run ss_sync.yml -f mode=history -f rounds=17 -f per_round=40`.
6. **Storage clean-up:** `data-latest` release leftovers that nothing in the
   repo or workflows reads (grep first; record, do not delete, if unsure).
7. **Owner decisions waiting:** S52 keep or trim the `bse/daily` copies on
   R2; S57 extend the weekly fill to Nano Cap / Combined; S58 after S56.
8. **Smaller open rows:** S28 (check the next daily sync writes two
   decimals), S34 (standing audit not scheduled), S35, S47, S53, S10;
   low: S25, S36, S37, S44.

Owner approved items 1 - 6 and merging each PR once CI is green on its
current head.

## Handover (2026-10-03, 04:50 IST)

Merged today: #345 - #355, #357 - #362 (long price file, its audit and every
fix, raw pack, the Backtest page's two tabs, docs). #356 closed (superseded by
#358 and #362). Running on GitHub while the laptop is off: the long price
rebuild (run 37076597258) and the SS history download (ss_sync mode=history,
run 37061786684). Next session: S21, then S23 (owner decision), S22, S25,
S26, S28, S10. Backups: R2 `reference/*` + `prices/screener/max_history`
(protected), release `ref_*`, local `C:\Users\Quali\Paresh_reference_backup\2026-10-03`.

## Data-quality sweep (planned 3 Oct 2026 for a cloud session; run 7 Oct on the laptop)

Owner, 3 Oct: fine-comb the data, random checks, verify backtest trades
against real prices. The cloud session of 3 Oct left no commits, report or
PR, so the sweep was run on 7 Oct. Report: `reports/dq_sweep_2026-10-07.md`.

| # | What | How we know it is done | Status |
|---|---|---|---|
| Q1 | Read the live rebuild (run 37113597811, with #372; it replaced 37107876721) and its audit zip; read the SS history run (S24, 37061786684) | Every new flag fixed or explained here | [x] 7 Oct: 5 breaks where ours moved are rights issues at their terms; 255 of 266 Screener shifts side with ours, 10 are rules in force, 1 open (S44); all 1,096 adjustment steps matched to an action: 2 faults (ALLCARGO, HCG: one action applied twice at a swapped date), fixed in the sweep PR, rebuild S45. SS history incomplete (S24) |
| Q2 | Random checks: 40 random (stock, day) closes against NSE's raw rows x our factors and the references; 20 random corporate actions | Mismatch table in the report; each mismatch fixed or explained | [x] 7 Oct: 40 / 40 closes = raw x the later listed steps, 38 / 40 within 2% of a reference (2 demergers the references do not adjust); 20 / 20 actions as the terms and the references give, or a rule in force |
| Q3 | Backtest trades: Nifty 500 History 2010 - 2026; 25 random + the 25 largest trades | Table in the same report; 0 unexplained | [x] 7 Oct: 19.9%/yr vs 10.3%, Sharpe 0.68, max DD -38.7%; 50 / 50 trades: prices = closes, return by hand = engine, member on entry, within 2 points of a reference |
| Q4 | S22 (J&K Bank 2015-02-09), S28 (benchmarks.csv zeros); S26 if time | PR merged or reason written | [x] 7 Oct: S22 real (no change), S28 fixed, S26 reason written |
| Q5 | Handover: TODO ticked, report committed, PR green | PR link in this row | [x] report and TODO committed; draft PR #394 (https://github.com/Pareshking/Paresh/pull/394), merge when the owner says |

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
| U5 | Data catalogue, NSE vs Yahoo comparison, R2 policy (WP10) | `docs/DATA_CATALOGUE.md` written (datasets, writers, readers, retention, source order, comparison status). Freshness table now in Configuration. Fourth NSE report read (item 2) and price order decided (item 3) | [x] |
| U6 | Hide the TradingView logo on every Lightweight chart (`layout.attributionLogo: false` in `lw_chart.py` and `lightweight_chart.py`); the vendored v4.2.0 draws it by default | PR merged; no logo on the stock page | [x] 3 Oct (#364): 41 chart tests pass |
| U7 | Upgrade vendored Lightweight Charts v4.2.0 -> 5.x: `addSeries(LineSeries, ...)` calls, `tests/test_lw_chart.py`, look at the stock, Breadth, Backtest and Portfolio pages; native panes can replace the hand-synced stack later | Separate PR merged; logo still off; charts checked on the live site | [x] 3 Oct: v5.2.1, series via addSeries, rendered in Chromium (candles, volume, baseline, area, line, synced panes): no errors, no logo |
| U8 | Refresh every stock's TradingView sector and industry, not only the blank ones (`classify_missing.py --refresh`, weekly): 22 stale rows corrected, 5 Nano Cap labels | PR merged; nightly step green | [x] 3 Oct |

## Dated

| # | When | What | How we know it is done | Status |
|---|---|---|---|---|
| 5 | 30 Sep 2026, evening (check 18:30 UTC) | October Nano Cap list built; Nano Cap and Combined rankings published | `data/nanocap_membership.json` gains `2026-09-30`; `rankings_nano` / `rankings_combined` published and accepted | [x] 30 Sep, daily sync 36790408819: 429 stocks, Nano 391 / Combined 1,141 ranked |
| 6 | 1 Oct 2026 | First Nano Cap and Combined model books; their backtest shows September | Actions and Backtest with `?sys=nano` / `?sys=combined` | [x] 7 Oct: the first-month crash ("months must be positive", from 8c93129) fixed in #395; Actions for Nano Cap shows its 20-stock book on the live site |
| 7 | 1–5 Nov 2026 | October frozen in all three ledgers | Track Record's "Three systems, side by side" shows Oct 2026 | [ ] |

## Portfolio (1 Oct 2026)

| # | What | How we know it is done | Status |
|---|---|---|---|
| P1 | Monthly view no longer crashes; Equity shows the marked month | #297 merged | [x] 1 Oct (#297) |
| P2 | On 1 Oct, September reads "Sep (closed)", not "Sep MTD"; Oct MTD says it is unavailable; "gap" → "Alpha"; Actions explains a fill due on the 1st. No ledger logic changed | #298 merged; V1 Production QA green on the merge commit | [x] 1 Oct: #298 (2e1e71e) and the QA wait fix #299 (a16a911); Production QA run 36839738078 incl. Portfolio visual QA, Full Validation 1214: green |
| P3 | PR #296 (another session): changes which month the ledger finalises (`ist_now()`); 19 tests fail. Owner to decide whether any of it is wanted; its Alpha rename and Actions note are in P2 | #296 closed, or rebased and green | [x] #296 was closed on 1 Oct without merging; its Alpha rename and Actions note are in P2 |
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
