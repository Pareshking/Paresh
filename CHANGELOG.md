# Changelog

## 2026-10-13 — Less empty space, fewer cramped boxes

- The figure strip under each page's title (Sectors, Actions, Breadth, Portfolio, Backtest) fills the row however many figures it has. It was a fixed six columns, so four figures left two empty columns and long industry names wrapped onto four lines. Names now read smaller, at most two lines; on a phone the figures sit two to a row.
- Screener: Biggest jumps, Entered top 50 and Left top 50 sit side by side on a wide screen, compact (about 1,000px shorter).
- Figure boxes inside cards (Portfolio's month, alpha, drawdown; Backtest): values read at their intended size and the boxes are as tall as their text (74px, was 104px). A page-wide paragraph style had shrunk every value to 14px grey.
- Portfolio: industry exposure runs in two columns; "How they move together" is a collapsed section, like Actions' Buy candidates, with the average in its heading.
- Sectors leadership map: one soft colour per sector, the same on every EMA tab, instead of green and red; a one-line intro; the table sits under "Figures by sector", collapsed.

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
