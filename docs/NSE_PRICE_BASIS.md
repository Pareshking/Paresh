# NSE price basis for the Track Record

**Status:** applied 2026-10-01. The 750's record, its month-to-date, the Actions model book and the
Backtest page run on NSE's closes as published.

## Why not Yahoo
Yahoo's adjusted closes are restated: a dividend paid in September lowers every earlier price, and a
vendor correction rewrites months that have closed. A month rebuilt on them ranks on data that did not
exist when the month closed. Yahoo also has nothing for stocks that merged away (CIGNITITEC, GSPL,
GUJGASLTD, JBCHEPHARM).

NSE's daily closes never change. Ranking at a signal date uses only ratios inside the trailing window,
so a series correct up to that date gives the ranking, the 50-EMA gate and the 52-week-high gate as
they stood then. Check: the book on 30 Sep matches the published top 20 on 16 of 20 names on this
basis, against 7 of 20 on Yahoo's.

## What is committed (`data/nse_prices/`)
- `closes.parquet`: raw closes as NSE filed them, 2024-09-30 onward, for the 750, every name the
  membership record lists, and the old symbols of renames (EQ before BE; the two weekend Budget sessions
  included).
- `actions.parquet`: NSE's split, bonus, consolidation and demerger rows, one per action. Each is applied
  only where the price actually moved by its factor (`src/loaders/nse_adjusted.py`).
- `notes.json`: 21 ticker renames, each with its evidence (a series ends and its successor starts the next
  session, returns correlate), and one correction: SHRIRAMFIN's 1:5 split, never listed by NSE.

Dividends are not added back, so the strategy is price-only like the Nifty 500 price index it is compared
with. The Yahoo corporate-actions log is not applied to NSE series (it corrects Yahoo, and would
double-adjust). Three REITs (BAGMANE, BIRET, EMBASSY) and JSLL's early history come from Yahoo and are
listed in the run report. A file too short for the requested window is refused and the caller keeps Yahoo.

## Operating it
- `python scripts/sync_nse_prices.py --update` appends the sessions since the last one (the monthly
  workflow runs it before the freeze; if NSE refuses, the freeze refuses rather than mix bases).
- `--build --cache DIR` rebuilds from `scripts/fetch_nse_history.py` output. A weekend session goes in
  `notes.json` `special_sessions`.
- The config fingerprint includes `prices: nse_as_published`; the ledger records `price_basis`.
  `data/track_record.json` was rebuilt with `--force` (logged in `rebuilds`): monthly returns moved by
  at most 0.9 points, Jan to Aug compounded +45.1%.
- A stock that joins the index later is given its pre-join history from Yahoo, joined by level; a new
  ticker change needs a `renames` entry.
