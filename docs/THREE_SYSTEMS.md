# Four systems — Nifty 750, Nifty 1000, > ₹2,000 Cr, Combined

One app, four universes, one strategy. Owner decisions of 2026-09-27 (the first
three; built in #240 and #242–#246) and 2026-11-21 (Nifty 1000, and Nano Cap
shown as "> ₹2,000 Cr"; S175). This file covers all four systems; it keeps its
name so links to it hold.
Update this file with every PR that changes how a system is defined, ranked,
booked or recorded.

_Last updated: 2026-11-21_

## The systems

| | Nifty 750 (default) | Nifty 1000 | > ₹2,000 Cr (key `nano`) | Combined |
|---|---|---|---|---|
| Stocks | NSE's Nifty Total Market | NSE's Nifty 1000: the 750 plus **NIFTY NANOCAP 250** (our name for NSE's other 250; not an index NSE publishes; tag `NANO250`) | every main-board stock ≥ ₹2,000 Cr outside the 750 | the 750 and > ₹2,000 Cr, ranked as one list |
| Key | `750` | `1000` | `nano` (unchanged: ledger, nightly files, `?sys=nano`) | `combined` |
| Membership | NSE constituents, `data/membership_history.json` | `membership_history.json` `indices.nifty_1000`, from 30 Oct 2026; **reconstructed** until NSE's first list we record (NSE first published the index on 16 Nov 2026), see the entry's `note` and `src/engine/nifty1000_backfill.py` | month-end list, `data/nanocap_membership.json` | union of the 750 and > ₹2,000 Cr on each date |
| Industry | NSE industry | NSE industry (NSE's list names one for all 1,000) | TradingView sector (`scripts/classify_missing.py`) | TradingView sector |
| Market caps | NSE's file, `data/nse_market_caps.csv` | the same file, which the daily sync now writes for all 1,000 | the list's own month-end figures | both |
| Track record | since Jan 2026, `data/track_record.json` | from Nov 2026, `data/track_record_1000.json`; **November is reconstructed** (its 30 Oct book uses a list not public until 16 Nov); a month is frozen only when every member has a close on its signal day | from Oct 2026, `data/track_record_nano.json` | from Oct 2026, `data/track_record_combined.json` |
| Backtest | last 6 completed months | from Nov 2026, a month more each month-end | from Sep 2026, a month more each month-end | same as > ₹2,000 Cr |

Sections below written before 21 Nov 2026 call > ₹2,000 Cr "Nano Cap"; it is
the same system under the same key.

The strategy is the same for all four (`TRACK_RECORD_CONFIG`). What differs is
who may be held, since when, and where the frozen months are kept — all of it
in `src/engine/systems.py` and nowhere else.

Nifty 1000 prices: the 750's as before; the other 250 are collected by the
nightly Screener sync on the ₹2,000 Cr list's best-effort path (from 22 Nov
2026). On 21 Nov, 58 of the 250 had no price history with us; until they do,
they are listed as "not ranked yet" under the Screener and the monthly freeze
refuses the Nifty 1000 (TODO S175).

On main at `ca3ccf3` (21 Nov 2026, 19:52 UTC) neither
`data/indices/ind_nifty1000_list.csv` nor `indices.nifty_1000` is on disk yet:
the first daily sync after #591 downloads the list and builds the entry, and
until then Configuration does not offer the Nifty 1000
(`config_view`, `os.path.exists(NIFTY_1000_PATH)`).

## Choosing a system

- Configuration → System (a segmented control of the short names; the chosen
  system's one-line caption under it). Every page
  follows the choice: Dashboard, Actions, Screener, Portfolio, Market, Sectors,
  Watchlist, Backtest. Holdings and watchlist are shared. (RRG was removed on
  21 Nov 2026, #587; Track Record is part of Portfolio and `/track-record`
  redirects there; Breadth is the Market page, `/market`, #596.)
- The choice lives in the session (`cfg_system`) **and** in the address as
  `?sys=1000` / `?sys=nano` / `?sys=combined` (nothing for the 750), because a stock link
  reloads the page and a reload is a new session (`src/ui/system_param.py`).
  Every stock link carries it; Back keeps it; a shared link opens the same
  system.
- If Nifty 1000, > ₹2,000 Cr or Combined cannot be loaded, the app says so and shows the 750.
- Nifty 1000 is offered once its list (`data/indices/ind_nifty1000_list.csv`) is on disk.

## Membership

The 750 system's point-in-time membership is backed by the multi-index `data/membership_history.json` produced by the daily sync. The 2026-09-30 rollout covers NIFTY TOTAL MARKET, NIFTY 50, NIFTY NEXT 50, MIDCAP 150, SMALLCAP 250 and MICROCAP 250. `DUMMY*` NSE placeholders are excluded from the recorded membership. The implementation was merged in PR #258 (merge commit `73b095a49b52ab1a4a968e21e364610e94ed02a5`), and post-merge R2 historical-evidence bootstrap run `36646326268` published the membership histories successfully.


- `scripts/build_extra_universe.py` runs in the daily sync and acts only when
  a new month-end session is in R2. It reads NSE's market-cap file for that
  session: EQ/BE series, ≥ ₹2,000 Cr, not in the 750, not an ETF, category
  Listed. Writes `data/indices/ind_nanocap_list.csv` and appends the month to
  `data/nanocap_membership.json`. From the 30 Nov 2026 build the list carries
  ISINs, taken by symbol from NSE's equity list
  (`data/reference/nse/equity_l.csv`; 410 of 411 on 21 Nov, #594).
- The Nifty 1000 is NSE's own list (`ind_nifty1000_list.csv`, from
  niftyindices.com, `RECORDED_INDICES_URLS`). The daily sync folds it into
  `membership_history.json` as `indices.nifty_1000`; a failed or short
  download (under 950 rows) keeps the committed list and does not fail the
  750's sync. It is kept out of the 750's ranked universe, the long NSE price
  file (`all_ever_members`) and the membership freeze hash (#591).
- A list is in force from the session it was built on — the close that
  signals the next month's book — until the next list.
- The daily sync collects the last three NSE sessions itself before this step
  (the NSE collector's own schedule has not fired reliably).

## Prices

- The ranking reads Screener first, NSE for gaps (`price_source.ranking_frames`);
  the Screener store holds the 750, the ₹2,000 Cr list and the Nifty 1000's
  other 250 alike. The two extra lists are collected after the 750, best
  effort, outside the 750's coverage gate (`sync_screener.extra_symbols`).
  Yahoo is not a source (owner, 2 Oct 2026); the Nano Cap Yahoo file
  (`prices_extra.parquet`) and the code that downloaded it were removed on
  13 Oct 2026 (TODO S10).
- Market caps: NSE's file for the 750 and the Nifty 1000 (the daily sync writes
  all 1,000 into `nse_market_caps.csv`; the 750's own ranking still gets the
  750's caps only); the ₹2,000 Cr list's own figures for the rest.

## Nightly precompute

`scripts/precompute_systems.py` (daily sync) ranks > ₹2,000 Cr, Combined and
(from #594) the Nifty 1000 with the same function as the 750 and stamps each
table with the same contract. Published as `rankings_nano.parquet` /
`rankings_combined.parquet` / `rankings_1000.parquet` (release) and
`snapshots/rankings_nano` / `snapshots/rankings_combined` /
`snapshots/rankings_1000` (R2, protected by `r2_retention.py`). The app uses a table only when every
contract term matches; otherwise it ranks live, as before. First published
2026-09-27 (daily sync run 36313661283: Nano Cap 396 rows, Combined 1,146,
both release and R2, verified). Production's acceptance check, replayed from
the published files and main's code with the 750 as control: all three
accepted, no contract term differs.

## Track record and model book

- Each system has its own append-only ledger. Nano Cap and Combined start
  with **October 2026**: the first book is signalled at the **30 Sep 2026**
  close and filled 1 Oct. The 750's record is untouched.
- The absence of the Nano Cap and Combined ledger files before their October
  inception is intentional. The loader now treats that pre-inception state as
  informational rather than an operational warning. Once a system has reached
  its inception, a missing ledger is again a warning.
- The Nifty 1000 starts with **November 2026**: the book signalled at the
  30 Oct close (reconstructed membership, above). Its ledger,
  `data/track_record_1000.json`, is written by the first freeze that passes;
  `update_track_record.py --system 1000` refuses a month while any member has
  no close on its signal day (58 on 30 Oct, #594).
- `monthly_track_record.yml` (1st–5th of each month) freezes all four; the
  step for the other three (`nano`, `combined`, `1000`) warns rather than fails.
- Actions shows the selected system's model book; before October, Nano Cap and Combined show "My holdings" only, with a "No model book yet" note.
- Portfolio (which holds the track record; `/track-record` redirects there)
  ends with **Three systems, side by side** (the heading in code): every
  system in `SYSTEMS` with a frozen month or a month to date: this month, since the
  window all have traded and since its own start, with Nifty Total Market
  (`portfolio_page._systems`).

### Shadow record

Beside the live systems, the Recommendation's shadow record (owner, 12 Oct 2026): the
750 under `SHADOW_CONFIG` (30 holdings, keep in the top 90, 200D EMA) from
November 2026, in `data/track_record_shadow.json`. Three more from December
2026: Near-high 90%, Breadth + long lookback (S144) and Skip 5 days (S160)
(`SHADOWS` in `src/engine/track_record.py`). Never traded; Portfolio names them
in the note under "Three systems, side by side", whose rows are the live
systems only. See `docs/TRACK_RECORD.md` §9–11.

## Backtest

`systems.backtest_months` counts completed months since September 2026 for the
₹2,000 Cr list and Combined, and since November 2026 for the Nifty 1000
(`BACKTEST_START`): 0 until 30 Sep (the page shows "Building"), 1 from
1 Oct, growing monthly. It runs on that system's point-in-time membership, so
it is never judged against a list that did not exist yet.

## Liquidity floor

Configuration → Portfolio limits: off by default, a floor in ₹ Cr of 20-day
average traded value (close × volume, Screener's). Applies to the Portfolio
book and the Backtest (at each rebalance, on the value known that day), in
every system. The track record never uses it (`src/engine/liquidity.py`).

## Calendar

| When | What happens | Check |
|---|---|---|
| 30 Sep 2026 (Wed) evening | daily sync collects NSE, builds the October Nano Cap list | `nanocap_membership.json` gains `2026-09-30` |
| 1 Oct 2026 | first Nano Cap / Combined books filled; their backtest shows September | Actions and Backtest with `?sys=nano` |
| 1–5 Nov 2026 | October frozen in all three ledgers | comparison panel shows Oct 2026 |

Rehearsed on today's data (synthetic 1 Oct and 3 Nov sessions): books of 20
signalled 30 Sep, filled 1 Oct; October frozen into both new ledgers; the
backtest reports 1–30 Sep on the point-in-time list.

## Open items

- NSE as the middle price source, once its adjusted prices rank like
  Screener's (`docs/archive/NSE_DATA_LEDGER.md`, To do 3–4).


## 2026-09-30 — Nano/750 universe correction

PR #273, merged as `811c3f5a6eb89074d39618fd47e2629f9d254834`, made the effective Nano Cap universe dynamically disjoint from the current Nifty 750. The persisted Nano list remains the month-end candidate/history source. Effective Nano is now the qualifying candidate set minus the current 750, with the hard invariant `intersection(NIFTY_750, NANO) == ∅`.

The existing ₹2,000 Cr cutoff and eligibility rules are unchanged. A stock entering the 750 leaves effective Nano immediately; a stock leaving the 750 can enter effective Nano immediately if it remains a qualifying candidate. Historical Nano membership records are not rewritten.

Production and nightly precompute now use the same definition. `extra_universe_loader.system_universe()` applies the effective-Nano subtraction for Nano and Combined, and `scripts/precompute_systems.py` always loads the current 750 before building Nano/Combined artifacts. Regression tests cover both a current-750 overlap and a stock leaving the 750.

**Identity note:** HEG and HEGAM are different companies/symbols. The September 2026 `HEG → HEGAM` event is an index constituent change, not duplicate-company evidence.
