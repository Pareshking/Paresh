# Changelog

## 2026-10-10 — Ranking: "View all" on the top-50 cards opens and closes the list

- On the Biggest Jumps, Entered top 50 and Left top 50 cards, "View all" used to open the rest of the list under itself: the button stayed above the new rows, the column header was repeated, and the header's "View all" button did nothing. Both buttons now open the full list in the same table, then read "Show less" and close it again.
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
