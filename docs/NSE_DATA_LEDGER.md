# NSE data ledger — status, decisions, next steps

Living tracker for the data-collection rebuild. Update it with every PR that
touches this work, so it can be picked up cold.

_Last updated: 2026-09-27_

## Decisions (owner)

| Date | Decision |
|---|---|
| 2026-09-27 | Collect everything NSE publishes daily into R2; **Screener stays the price the ranking uses** until NSE's record is complete and compared. |
| 2026-09-27 | Cross-source rule: flag any day a source's one-day move differs from NSE's by more than **7%** (moves, not levels: Yahoo's dividend adjustment drifts its level). Same-day Screener close must match NSE within 1%. |
| 2026-09-27 | **Sample first:** collect back to 2025-04-01 (~370 sessions), run every check on it, then extend to ten years. |
| 2026-09-27 | Deleted from R2: `snapshots/application`, `prices/yahoo/bootstrap` (432 → 300 MB). |
| 2026-09-27 | Extra universe ("Nano Cap", name TBC): option **A** — selectable in Configuration, default stays the 750; the model portfolio, Actions and track record are **not** changed. Membership refreshed on the **last trading day of each month**, used from the 1st. |
| 2026-09-27 | App should read its data from R2 (owner added the R2 keys to Streamlit secrets). |
| 2026-09-27 | Sample year checked (368/368 days, all read back). Owner: **start the ten-year backfill** (`--since 2016-01-01`, 150 days a run). Screener's weekly deep check: every **30** days, not 7. Nano Cap is ranked **as its own index**, never combined with the 750. |
| 2026-09-27 | Extra universe: **every stock ≥ ₹2,000 Cr** outside the 750 (458 on 25 Sep), not a fixed 250. Screener pacing to be tuned so NSE, Yahoo and Screener all land before 06:00 IST. |

## What is running

- `nse_collect.yml`, every 4 hours: newest days + up to 100 older, 2.5 s
  apart, floor `--since 2025-04-01`. Stops quietly if NSE refuses.
- R2 datasets, one file per trading day: `nse/prices_daily` (~3,800
  securities, unadjusted OHLC + index closes), `nse/corporate_actions`
  (Bc file, purpose parsed to kind + price factor), `nse/market_caps`
  (~3,190 securities), `nse/source_checks` (disagreements, newest day).
- Held: 147 sessions (2026-02-20 → 2026-09-25) as of 2026-09-27 02:30 UTC.

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

## Next steps

1. **Sample checks** once ~370 sessions are in — run `nse_sample_check.yml`
   (scripts/nse_sample_check.py; read only, report in the job summary):
   - every stored day parses; row counts steady; no gaps against the
     trading calendar;
   - cross-source check over every day, not just the newest: level and 7%
     move rules, list of disagreements per stock and date;
   - corporate actions: every split/bonus in the sample shows as a step in
     NSE's unadjusted prices on its ex-date, matches Screener's restatement
     and `data/corporate_actions_log.json`; list the misses;
   - measured storage per day → projection for ten years.
2. Owner signs off → move `--since` back to 2016-01-01.
3. App reads from R2 — **live since #223** (src/loaders/app_source.py):
   rankings (`snapshots/rankings`), Screener store (`prices/screener`) and
   the two-year price snapshot (`app/prices_snapshot`, newest 3 kept), each
   verified by SHA-256; release files only as fallback. First
   `app/prices_snapshot` publication verified 2026-09-27 (2026-09-25 data);
   production process loaded 3017392. Production QA now prints the footer's
   "Data from:" value (`data loaded from`) so the source is checked on every
   deploy; the record of it survives a code reload (it used to go blank).
4. Extra universe ("Nano Cap", name TBC; src/engine/extra_universe.py):
   - **membership — built**: `scripts/build_extra_universe.py` runs in the
     daily sync, and only acts when a new month-end session is in R2. It
     reads NSE's own market-cap file for that session: EQ/BE series, ≥ ₹2,000
     Cr, not in the 750, not an ETF, category Listed. It writes
     `data/indices/ind_nanocap_list.csv` (NSE index-file columns) and
     `data/nanocap_membership.json` (every month, point in time; in use from
     the 1st). Industry is the TradingView sector, else "Unclassified".
   - collection — next: Screener and Yahoo fetch these stocks too; Screener
     pacing gets random jitter; all three sources in before 06:00 IST
     (Screener runs ~21:35 UTC today, ~20 min for 750, ~+12 min for ~460).
   - app — **built**: Configuration › Ranking universe (750 default | Nano
     Cap). Nano Cap is ranked among its own stocks (src/loaders/
     extra_universe_loader.py: own list, own Yahoo file, list market caps).
     Screener, Sectors, RRG, Watchlist, Breadth, Backtest follow the choice;
     Portfolio, Actions, Track Record stay on the 750 and say so. Local run:
     361 of 417 ranked, 56 too new (listed < minimum history). To do:
     "Unclassified" industries from Screener.in.
5. Adjusted-price layer from NSE raw + corporate actions; compare rankings
   with the Screener-based ones before any switch.
