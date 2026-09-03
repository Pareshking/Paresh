# Raw-Price Rebuild — Design Document

**Status:** Parked — documented, not started. Implemented only after explicit
approval.

**Tracker ref:** V1_AUDIT_TRACKER.md → NEXT 9

---

## 1. The problem with Yahoo's adjusted prices

The daily sync calls yfinance with `auto_adjust=True`. Yahoo Finance returns
prices where every split, bonus or demerger has already been folded into the
entire history, backwards. The chart looks smooth. But:

### 1.1 The past keeps changing

If INDIAGLYCO announces a 1:5 split today, Yahoo halves every stored price
overnight. A price that was ₹1,000 last year is now ₹200 in their data. If we
downloaded and stored the file yesterday, our stored file and today's download
disagree for the same historical date.

Consequence: the track record's frozen months were struck against one set of
numbers. If a price revision happens and the track record is re-run, it
produces different rankings — a different book — for the same frozen month.
The append-only ledger protects the final return figure, but the position
selection and entry dates inside each month would silently shift.

### 1.2 Demergers are never adjusted by Yahoo

A split has a clean ratio (2:1, 4:1). Yahoo knows how to handle those.

A demerger spins off a subsidiary. The parent loses a fraction of its value
that varies by deal terms — no clean published ratio. Yahoo logs a large
negative session and never corrects it. Our `detect()` function in
`corporate_actions.py` catches these (threshold 35%) and the `classify_ratio()`
function marks them `unmatched`. But we can only neutralise them if we can
put the correct adjustment ratio into `corporate_actions_log.json`. For
pure demergers that ratio is often not standardised in a machine-readable
public source.

### 1.3 The current workaround

`src/engine/corporate_actions.py` already does the right thing at read time:
`adjust_prices(prices, events)` reads the stored (Yahoo-adjusted) prices,
applies the events from `data/corporate_actions_log.json`, and returns a
corrected frame. It never touches the stored file. This handles the 12 events
now recorded, including TDPOWERSYS, ABFRL, REDTAPE, QUESS, PARAS and the five
probable demergers.

The limitation: if Yahoo silently revises a price for an event that was NOT
caught and logged, we have no way to detect or undo it. The stored history
changes beneath us without a record.

---

## 2. What the rebuild means

Store the original unadjusted (raw) OHLCV prices from the day of first
download. Keep them permanently. Apply our own adjustments from
`corporate_actions_log.json` at read time, in memory. Never let Yahoo's
retroactive rewrites touch the stored file.

### 2.1 Why it has to be all stocks, not just the 12 flagged ones

The price matrix is a single DataFrame — 750+ stocks × N dates. You cannot
mix raw prices for some columns and Yahoo-adjusted for others: a stock that
split 4:1 would show prices 4× lower than its neighbours on the same date, and
every cross-sectional rank would be corrupted.

The switch is at download time. yfinance's `auto_adjust` flag applies to the
entire download batch, not individual tickers. So raw storage is universal;
the `corporate_actions_log.json` is the selective part — it lists only the
events where an explicit adjustment needs to be applied.

For stocks with no events in the log: raw ≈ Yahoo-adjusted (no splits have
happened), so the practical difference is zero until an event occurs.

---

## 3. Implementation plan

### Step 1 — Download raw

In `scripts/sync_data.py`, change the yfinance download call from
`auto_adjust=True` to `auto_adjust=False`. Save the raw close prices as
`prices_raw.parquet` in `data_cache/` alongside the existing snapshot.

Key detail: raw OHLCV prices use the split-unadjusted close column, which
yfinance returns as `"Close"` (not `"Adj Close"`) when `auto_adjust=False`.
Dividends appear as a separate column and are ignored for this purpose.

### Step 2 — Read-time adjustment in the loader

In `src/loaders/price_loader.py` (or the equivalent cache-loader path):

1. Load `prices_raw.parquet` instead of the adjusted snapshot.
2. Call `adjust_prices(raw_frame, load_events())` from
   `src/engine/corporate_actions.py`.
3. Return the adjusted frame.

The rest of the application — screener, backtester, track record, portfolio —
sees no change. They all call the same loader and get the same adjusted frame
they always did, except it is now derived from stable raw numbers rather than
Yahoo's retroactively-mutable ones.

### Step 3 — Publish raw asset

In `.github/workflows/daily_sync.yml`, publish `prices_raw.parquet` as a
release asset under the `data-latest` tag, alongside the existing
`prices.parquet` (2-year app snapshot) and `prices_full.parquet` (10-year
track record archive).

The raw file is larger than the adjusted snapshot (splits inflate historical
per-share prices numerically — the file size is similar but there are no
retroactive rewrites to remove rows). Upload with `--clobber` like the others.

### Step 4 — Backward compatibility

Keep the existing `prices.parquet` asset and its download path as a fallback.
If `prices_raw.parquet` is absent (during the transition, or on a fresh
environment), the loader falls back to the existing adjusted snapshot. This
means the app never breaks during the migration.

A config flag `USE_RAW_PRICES = True` (default) / `False` (fallback) in
`src/core/config.py` controls which path the loader takes, so a single env
var can revert to the old behaviour if a bug is found.

---

## 4. The corporate_actions_log.json role

This file is the master record. Every event in it represents:

- **What happened:** symbol, date, type (split, bonus, demerger)
- **What ratio to apply:** e.g. 0.25 for a 1:4 split (prices before the date
  are multiplied by 0.25 to bring them to post-split scale)
- **How it was classified:** `classify_ratio()` output — `1:2 split`,
  `1:4 split`, `unmatched`, etc.

The 12 events recorded as of September 2026:

| Symbol | Date | Approximate drop | Likely type |
|---|---|---|---|
| INDIAGLYCO | 2026-09-02 | −78.8% | Demerger |
| JSLL | 2026-09-02 | −78.3% | Demerger |
| REDTAPE | prior | −74.8% | 1:4 split |
| ABFRL | prior | −66.6% | 1:3 split |
| VEDL | prior | −64.9% | Demerger |
| SKFINDIA | prior | −54.8% | Demerger |
| STAR | prior | −54.0% | Demerger |
| QUESS | prior | −50.7% | 1:2 split |
| PARAS | prior | −50.1% | 1:2 split |
| TDPOWERSYS | prior | −49.2% | 1:2 split |
| TRIVENI | prior | −41.6% | Probable demerger |
| TMPV | prior | −40.2% | Probable demerger |

When a new split/demerger is detected by the daily sync's
`check_corporate_actions.py` step, a human reviews the event, looks up the
official NSE circular for the correct ratio, and adds it to the log. From
that point, `adjust_prices()` applies it at read time and the stock re-enters
the ranking at its correct relative price.

---

## 5. What you gain

| Benefit | Explanation |
|---|---|
| Stable history | Stored prices never change retroactively. A price on 2024-01-15 means the same thing today as it did when it was saved. |
| Track record integrity | The frozen months in the ledger were struck against prices that are now preserved verbatim. A re-run uses the same prices, so rankings match. |
| Demerger control | You decide the adjustment ratio from the official NSE circular, not Yahoo's guess. |
| Audit trail | Every price correction is explicit, dated, human-reviewed, and committed to git. |

---

## 6. What it costs

| Cost | Detail |
|---|---|
| Larger storage | Raw files are slightly larger per ticker (the price scale before splits is higher). In practice the parquet file size is similar; the difference is in the numbers, not rows. |
| More complex read path | One extra function call (`adjust_prices`) in the loader. Already written and tested. |
| Manual event curation | New splits/demergers need a human to confirm the ratio from the NSE circular before the log is updated. The `check_corporate_actions.py` step surfaces candidates automatically. |
| One-time migration | First run after the switch needs a clean raw download. The fallback to `prices.parquet` means no outage. |

---

## 7. What is NOT changing

- The `adjust_prices()` function in `src/engine/corporate_actions.py` — already
  written, tested, and correct.
- The `load_events()` function — already reads the log file.
- The track record append-only ledger — unchanged.
- The rest of the application — sees the same adjusted DataFrame it always did.
- The detection logic in `check_corporate_actions.py` — unchanged; it continues
  to surface new events for human review.

---

## 8. Files that change

| File | Change |
|---|---|
| `scripts/sync_data.py` | `auto_adjust=False`; save as `prices_raw.parquet` |
| `src/loaders/price_loader.py` | Load raw file; call `adjust_prices()`; fallback to existing snapshot |
| `src/core/config.py` | Add `USE_RAW_PRICES`, `PRICE_RAW_ASSET`, `PRICE_RAW_URL` |
| `.github/workflows/daily_sync.yml` | Publish `prices_raw.parquet` as release asset |
| `data/corporate_actions_log.json` | Ongoing — new events added as detected |
| `tests/` | New tests: loader returns same frame with/without raw flag; events applied in correct chronological order |

---

## 9. Decision gate

This is parked. Do not start implementation until the user says to proceed.

The question to answer before starting: is the one-time migration cost
(re-downloading all history with `auto_adjust=False`, publishing the raw
asset, flipping the loader) worth doing now, or after the next set of
features stabilises?

The corporate_actions_log.json and the `adjust_prices()` function are the
foundation. They exist. This document is the blueprint. The build happens
when ready.
