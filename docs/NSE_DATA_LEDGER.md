# NSE data ledger — status, decisions, next steps

Living tracker for the data-collection rebuild. Update it with every PR that
touches this work, so it can be picked up cold.

_Last updated: 2026-10-02_

## Decisions (owner)

| Date | Decision |
|---|---|
| 2026-09-27 | Collect everything NSE publishes daily into R2; **Screener stays the price the ranking uses** until NSE's record is complete and compared. |
| 2026-09-27 | Cross-source rule: flag any day a source's one-day move differs from NSE's by more than **7%** (moves, not levels: Yahoo's dividend adjustment drifts its level). Same-day Screener close must match NSE within 1%. |
| 2026-09-27 | **Sample first:** collect back to 2025-04-01 (~370 sessions), run every check on it, then extend to ten years. _(Done; extent later cut to three years, below.)_ |
| 2026-09-27 | Deleted from R2: `snapshots/application`, `prices/yahoo/bootstrap` (432 → 300 MB). |
| 2026-09-27 | Extra universe ("Nano Cap", name TBC): option **A** — selectable in Configuration, default stays the 750; the model portfolio, Actions and track record are **not** changed. Membership refreshed on the **last trading day of each month**, used from the 1st. _(Superseded the same day by the three systems, below: every page follows the choice.)_ |
| 2026-09-27 | App should read its data from R2 (owner added the R2 keys to Streamlit secrets). |
| 2026-09-27 | Sample year checked (368/368 days, all read back). Owner: **start the ten-year backfill** (`--since 2016-01-01`, 150 days a run) _(cut to three years, below)_. Screener's weekly deep check: every **30** days, not 7. Nano Cap is ranked **as its own index**, never combined with the 750. _(Superseded: Combined is now a third system, ranked as one list.)_ |
| 2026-09-27 | NSE history: **three years** (from 2023-10-01), not ten — the backtest needs ~18 months. Price order everywhere: **Screener → NSE → Yahoo** (NSE once its adjustment layer exists). Three systems: **Nifty 750** (default), **Nano Cap**, **Combined**; every page follows; B and C records from Oct 2026; comparison panel; liquidity floor option (off). |
| 2026-09-27 | Extra universe: **every stock ≥ ₹2,000 Cr** outside the 750 (458 on 25 Sep), not a fixed 250. Screener pacing to be tuned so NSE, Yahoo and Screener all land before 06:00 IST. |
| 2026-10-02 | **No Yahoo anywhere**; Yahoo's R2 data deleted. Price order Screener → NSE. |
| 2026-10-02 | **NSE history back to 2010** (was three years), for long backtests. Prices from the GitHub mirror of NSE's full bhavcopy (checked equal to NSE's file on every row), corporate actions from NSE's yearly list; not 3,400 bundle requests. |
| 2026-10-02 | **SS** (a friend's site, used gently, named "SS" everywhere) collected nightly at **22:02 IST**; Screener canonical for now, SS recommended as primary next. |
| 2026-10-02 | **Every adjustment automatic**: rights factor from NSE's terms (applied only where SS left the issue raw); two-of-three vote with **NSE as judge**; renames from NSE's symbol-change list and **ISINs** (owner's idea), the ledger only for exceptions. Rules: `docs/PRICE_PIPELINE.md`. |

## What is running

_2 Oct 2026:_ `nse_collect.yml` now backfills to **2010-01-01** on a weekday
calendar (holidays remembered in `nse/closed_days`; the old calendar came from
the deleted Yahoo file, so the backfill had silently been skipping), with a
per-run time budget. `nse/prices_daily` holds 10 Jun 2010 to date; Jan–Jun 2010
are being collected. `nse/corporate_actions_history` holds NSE's list for
2010 – 2026. The 2023 notes below are kept for the record.

- `nse_collect.yml`, every 4 hours: the schedule fired for the first time on
  2026-09-27 (10:04 UTC, ~1.5 h late; GitHub schedules run late). Newest 7
  days + up to 150 older, 2.5 s apart, floor `--since 2023-10-01` (three
  years). Stops quietly if NSE refuses.
- `daily_sync.yml` also collects the last 3 NSE sessions itself, before it
  builds the month-end Nano Cap list, so that list never waits on the
  collector's schedule.
- R2 datasets, one file per trading day: `nse/prices_daily` (~3,800
  securities, unadjusted OHLC + index closes), `nse/corporate_actions`
  (Bc file, purpose parsed to kind + price factor), `nse/market_caps`
  (~3,190 securities), `nse/source_checks` (disagreements, newest day).
- Held: **complete back to 2023-10-03**, the first session of the three-year
  window (1 Oct 2023 was a Sunday, 2 Oct a holiday), as of 2026-09-27.
  From here each run only adds the newest days.

## Findings so far

- 2026-09-25: NSE vs Screener closes agree for 749/750; NSE vs Yahoo moves
  agree for all 750. Only flag: HEG (no price on either; demerger 2026-09-07).
- NSE's list for Nifty Total Market has 755 rows: 750 stocks + 5 `DUMMY*`
  placeholders left by demergers.
- 13 of our 750 rank below 1,000 by NSE market cap (NFL … AWFIS ₹1,841 Cr):
  NSE indices rank on **free-float** market cap averaged over six months and
  reconstitute only twice a year, so members drift below the full-cap cut.
- Outside our 750: 458 stocks ≥ ₹2,000 Cr, 293 ≥ ₹3,000 Cr, 153 ≥ ₹5,000 Cr.
  The largest 250 run ₹1,66,876 → ₹3,527 Cr.

## Parser fixes

- 2026-09-27: NSE writes splits as `FVSPLT FRM RS 10 TO RE 1` (and spacing
  variants) — the first sample recognised none; now read, factor = to/from.
  `SCH AGMT-BONUS NCRPS 4:1` (preference-share bonus) is its own kind with no
  equity price factor. Same-day actions multiply (BAJFINANCE 2025-06-16:
  bonus 4:1 × split 2:1 = 0.1). Days stored before the fix keep NSE's raw
  wording, and readers re-parse it, so nothing in R2 needs rewriting.

- 2026-09-27: NSE's Bc file also writes ISO dates (`2025-12-05`), which the
  reader parsed day-first (12 May): every action dated on the 1st-12th of a
  month in such a file was stored with day and month swapped. Found through
  CAMS (1:5 split, record date 5 Dec 2025, stored as 2025-05-12; owner asked
  for a news check). The reader now reads ISO as ISO; stored rows are
  repaired on read by `repair_swapped_dates` (a date outside the listing's
  window whose swap falls inside it).

## Done (2026-09-27)

- Sample year checked; parser reads every split wording (`FVSPLT FRM RS 10
  TO RE 1`, `RS 2 TO 1`, `RS 5 TO RS 1`), preference-share bonuses, ISO dates
  (CAMS), extra commas in the Bc file (#235, #238, #239).
- App reads rankings, Screener store and price snapshot from R2 first,
  release files as fallback (#223); production QA prints the source.
- Extra universe built: every stock ≥ ₹2,000 Cr outside the 750, month-end
  lists, point in time. Screener and Yahoo fetch these stocks (Yahoo in
  batches; a new stock in any universe gets its full history automatically).
  Screener pacing has random jitter; its deep check is monthly.
- Three systems — Nifty 750, Nano Cap, Combined — every page follows;
  per-system track records from Oct 2026, comparison panel, nightly
  precompute (first publish accepted, 27 Sep), backtest from Sep 2026,
  liquidity floor option.
  See `docs/THREE_SYSTEMS.md`.
- Missing Screener days filled from Yahoo's daily moves (400-day window).
- Open/high/low features removed (candles, ATR, stop loss, chandelier).
- R2 retention audit limited to the datasets it deletes from (#243).
- NSE history complete back to 2023-10-03; the collector's schedule fires.
- Every Nano Cap stock has a TradingView sector (41 were Unclassified): the
  nightly sync asks TradingView's screener, then Screener.in (NSE's sector
  mapped onto TradingView's). Value Research Online answers scripts with a
  Cloudflare challenge, so it cannot be a source.

## To do

1. **30 Sep → 1 Oct**: the October Nano Cap list builds on the 30 Sep
   evening; first Nano Cap / Combined books on 1 Oct; their backtest shows
   September. Check each (`docs/THREE_SYSTEMS.md`, Calendar).
2. **Early November**: October freezes into all three ledgers.
3. **NSE adjustment layer** (`src/loaders/nse_adjusted.py`). First
   reports (runs 36323013380, 36327550737): rankings already close
   (Spearman 0.993 / 0.970 / 0.985; top 20 19/20 in each system), but
   NSE's daily file does **not** adjust its previous close for splits
   (ADANIPOWER 1:5, 22 Sep 2025: previous close 709.40, close 170.25), so
   the first method missed every split and bonus (135 stocks off Screener
   by 2-10x). Now: the Bc file's splits and bonuses, each applied only where
   the price moved by its factor; moves beyond 1.8x with no action are
   listed. The five sessions the report found missing (12 Nov 2023,
   20 Jan, 2 Mar, 18 May 2024, 1 Feb 2026) were collected with
   `nse_collect.yml` → dates. Third report (run 36329721602): 300 applied,
   drift beyond 1% down from 135 to 58, Spearman 0.9993 / 0.9934 / 0.9975,
   top 20 20/20, 19/20, 20/20. What remained: ex-dates Bc prints
   month-first (E2E, MCX, VGL, SILVERTUC: now tried swapped) and demergers
   (VEDL, HEG, SIEMENS, RAYMOND, ABFRL: now priced at the ex-date's fall).
   Fourth report (run 36331991821, 27 Sep): 1,117 of 1,167 stocks within 1%
   of Screener throughout, 50 beyond; Spearman 0.9997 / 0.9984 / 0.9991, top
   20 in common 20/20, 19/20, 20/20, top 50 50/50 in all three. **Owner
   decision, 2 Oct 2026: yes, NSE becomes the middle source**, skipping the
   ~50 stocks still beyond 1% (largest: PGIL, GOLDIAM, HCC, UTKARSHBNK,
   STALLION, LLOYDSENGG). Wired in 2 Oct (below).
4. **NSE as the middle price source** everywhere: Screener → NSE → Yahoo.
   Approved and wired 2 Oct 2026: `price_source.keep_and_fill` fills a missing
   Screener price from NSE's adjusted daily move first (`nse_prices.middle_close`,
   from the committed `data/nse_prices`), and only then from Yahoo's. A stock
   whose NSE and Screener levels drift past 1% is skipped and falls through to
   Yahoo. The app, the nightly precompute and the parity check all pass NSE, so
   they rank the same frame. If NSE data is missing or unreadable the order is
   Screener → Yahoo as before.
5. Timing: all three sources (NSE, Yahoo, Screener) in before 06:00 IST;
   Screener's nightly run for 1,167 stocks takes ~37 min.
