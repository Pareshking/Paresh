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
| S14 | History before 2010 for the 1 Jan 2010 ranking: 2008 – 2009 from NSE's classic bhavcopy, corporate actions from 2008 | `nse_history_import` with `pre2010_since=2008-01-01` | [x] 2 Oct, run 37039302479: 488 sessions, 0 failed; 17 Oct 2009 Muhurat (a Saturday) to fetch: [ ] |
| S15 | History audit 2008 – 2026 and its fixes | Audit run green; each finding fixed or explained | [x] 3 Oct, run 37047812302: (1) 500 of 584 unconfirmed splits/bonuses were one action counted twice (daily Bc + yearly list) — fixed (#348); (2) 13 weekend special sessions 2010 – 2020 missing — collected (run 37054756653); (3) every holiday from 2021 held as a copy of the day before (the mirror files one) — importer reads the file's own date, builder drops copies, calendar check (`nse_calendar.py`); (4) mirror turnover in rupees, not lakhs, 2010 – 2018 (value x 1e5) — importer reads the unit, builder rescales |
| S16 | Long NSE price file for backtests (`nse_long_*.parquet`, release) | Built, units ~1 every year, no copies, 0 calendar flags | [ ] rebuild after S15's fixes (#345 merged; first build 37051588704 predates them) |
| S17 | Backtest "History from 2010": any index (Nifty 50/100/500, Midcap, Smallcap, Microcap, Total Market), months, traded-value floor; no market-cap cutoff, no rights (owner, 3 Oct) | #346 merged; Nifty 500 from Jan 2010 run on the real file | [ ] |
| S18 | Industry for the 217 index members no current list labels | `data/reference/historical_industries.csv`: NSE's four levels, each web-checked (owner's format) | [x] 3 Oct (#346): 171 high, 43 medium, 3 low |
| S6 | Renames from NSE's symbol-change list and ISINs | 575 found, 0 conflicts, all 21 ledger renames among them | [x] 2 Oct (#341) |
| S7 | Adjustment check across 2010 – 2026 (splits, bonuses, rights, demergers, renames) | Report: unexplained jumps listed and explained or fixed | [ ] after S5 |
| S8 | Long backtests on the 2010+ NSE history, Nifty 500 universe (S13) | Owner reviews the results | [ ] after S7 |
| S9 | SS as the app's primary source? | Owner decision | [x] 2 Oct, owner: **keep Screener as the app's source for now** (and its NSE + BSE volume for the liquidity floor); SS stays collected and checked nightly |
| S10 | Remove dead Yahoo code and the `yfinance` dependency | PR merged | [ ] |
| S11 | Membership × bhavcopy check and its fixes (join follows NSE's symbol-change list; KBL, ASIANHOTEL, PROVOGUE; REIT series RR) | Report; owner approves fixes | [x] 2 Oct, `reports/membership_bhavcopy_check_2026-10-02.md`; owner approved |
| S12 | Tata Motors DVR counted with Tata Motors (one company, one slot) | Owner decision; test | [x] 2 Oct (`backtester.SAME_COMPANY`) |
| S13 | Long backtest universe: **Nifty 500, 2010 to date** (no point-in-time Total Market list before 29 Oct 2021; the 750 backtest starts Nov 2021) | Owner decision | [x] 2 Oct, owner: Nifty 500 |

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
