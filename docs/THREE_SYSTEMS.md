# Three systems — Nifty 750, Nano Cap, Combined

One app, three universes, one strategy. Owner decisions of 2026-09-27; built in
#240 and #242–#246. Update this file with every PR that changes how a system is
defined, ranked, booked or recorded.

_Last updated: 2026-09-27_

## The systems

| | Nifty 750 (default) | Nano Cap | Combined |
|---|---|---|---|
| Stocks | NSE's Nifty Total Market | every main-board stock ≥ ₹2,000 Cr outside the 750 | both, ranked as one list |
| Key | `750` | `nano` | `combined` |
| Membership | NSE constituents, `data/membership_history.json` | month-end list, `data/nanocap_membership.json` | union of the two on each date |
| Industry | NSE industry | TradingView sector (`scripts/classify_missing.py`) | TradingView sector |
| Track record | since Jan 2026, `data/track_record.json` | from Oct 2026, `data/track_record_nano.json` | from Oct 2026, `data/track_record_combined.json` |
| Backtest | last 6 completed months | from Sep 2026, a month more each month-end | same as Nano Cap |

The strategy is the same for all three (`TRACK_RECORD_CONFIG`). What differs is
who may be held, since when, and where the frozen months are kept — all of it
in `src/engine/systems.py` and nowhere else.

## Choosing a system

- Configuration → System (radio, short name + one-line caption). Every page
  follows the choice: Screener, Actions, Sectors, RRG, Portfolio, Watchlist,
  Breadth, Backtest, Track Record. Holdings and watchlist are shared.
- The choice lives in the session (`cfg_system`) **and** in the address as
  `?sys=nano` / `?sys=combined` (nothing for the 750), because a stock link
  reloads the page and a reload is a new session (`src/ui/system_param.py`).
  Every stock link carries it; Back keeps it; a shared link opens the same
  system.
- If Nano Cap or Combined cannot be loaded, the app says so and shows the 750.

## Membership

- `scripts/build_extra_universe.py` runs in the daily sync and acts only when
  a new month-end session is in R2. It reads NSE's market-cap file for that
  session: EQ/BE series, ≥ ₹2,000 Cr, not in the 750, not an ETF, category
  Listed. Writes `data/indices/ind_nanocap_list.csv` and appends the month to
  `data/nanocap_membership.json`.
- A list is in force from the session it was built on — the close that
  signals the next month's book — until the next list.
- The daily sync collects the last three NSE sessions itself before this step
  (the NSE collector's own schedule has not fired reliably).

## Prices

- The ranking reads Screener first, Yahoo for gaps (`price_source.keep_and_fill`).
- The 750 come from the 750's price files; Nano Cap stocks from their own Yahoo
  file (`prices_extra.parquet`, nightly). `extra_universe_loader.join_prices`
  keeps one copy per stock: a stock that left the 750 for Nano Cap (HEG,
  Sep 2026) is priced from the Nano Cap file, not the stale 750 copy.
- Market caps: the 750's cache; the Nano Cap list's own figures for the rest.

## Nightly precompute

`scripts/precompute_systems.py` (daily sync, after the extra Yahoo download)
ranks Nano Cap and Combined with the same function as the 750 and stamps each
table with the same contract. Published as `rankings_nano.parquet` /
`rankings_combined.parquet` (release) and `snapshots/rankings_nano` /
`snapshots/rankings_combined` (R2). The app uses a table only when every
contract term matches; otherwise it ranks live, as before. First published
2026-09-27 (daily sync run 36313661283: Nano Cap 396 rows, Combined 1,146,
both release and R2, verified). Production's acceptance check, replayed from
the published files and main's code with the 750 as control: all three
accepted, no contract term differs.

## Track record and model book

- Each system has its own append-only ledger. Nano Cap and Combined start
  with **October 2026**: the first book is signalled at the **30 Sep 2026**
  close and filled 1 Oct. The 750's record is untouched.
- `monthly_track_record.yml` (2nd–5th of each month) freezes all three; the
  Nano Cap and Combined step warns rather than fails.
- Actions shows the selected system's model book; before October, Nano Cap and
  Combined show "My holdings" only, with a "No model book yet" note.
- Track Record ends with **Three systems, side by side**: the last 12 frozen
  months for each, and the Nifty 500.

## Backtest

`systems.backtest_months` counts completed months since September 2026 for
Nano Cap and Combined: 0 until 30 Sep (the page shows "Building"), 1 from
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
| 2–5 Nov 2026 | October frozen in all three ledgers | comparison panel shows Oct 2026 |

Rehearsed on today's data (synthetic 1 Oct and 3 Nov sessions): books of 20
signalled 30 Sep, filled 1 Oct; October frozen into both new ledgers; the
backtest reports 1–30 Sep on the point-in-time list.

## Open items

- NSE as the middle price source, once its adjusted prices rank like
  Screener's (`docs/NSE_DATA_LEDGER.md`, To do 3–4).
