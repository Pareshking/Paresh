# Price pipeline: sources, the nightly run, and the rules

How prices reach the app, what runs each night, and the rules that keep every
adjustment automatic. Owner, 2026-10-02: "all the adjustment should be
automatic and no manual work, we have 3 source and those can give hints to
each other along with official read from NSE."

_Last updated: 2026-10-02_

## The three sources and NSE's own record

| Source | What it gives | Adjusts for | Where it lives |
|---|---|---|---|
| **Screener** | Close and volume (NSE + BSE volume), ~1,167 stocks, 10 years | Splits, bonuses, usually rights | R2 `prices/screener`, release `screener_prices.parquet` |
| **SS** | Daily OHLCV, NSE volume only, whole-paisa prices, 1,216 stocks, 1,000 sessions each (page 1) | Splits, bonuses, **most rights issues** (8 of 10 measured) | Release `ss_prices_YYYY.parquet` + `ss_manifest.json`; R2 `prices/ss` |
| **NSE** | The exchange's own bhavcopy: every security, unadjusted OHLC, value, volume | Nothing (raw), adjusted by us | R2 `nse/prices_daily`, 10 Jun 2010 to date; committed `data/nse_prices` (2 years, adjusted) |

The site behind SS belongs to a friend of the owner, who allowed its use on one
condition: "do not hammer my site by downloading entire universe in one go,
give some breathing to my website". Every SS request is 4 s apart, 40 stocks a
round, 5 minutes' rest between rounds. Its name stays "SS" everywhere.

**What the app ranks on:** Screener first, NSE for what Screener lacks
(`src/loaders/price_source.ranking_frames`); the liquidity floor uses
Screener's NSE + BSE volume. Owner, 2 Oct 2026: **keep Screener as the app's
source for now.** SS is collected and checked every night, not ranked on.

Measured 2 Oct on a year of 192 stocks: SS and Screener identical to the paisa
on 187. Screener's volume is NSE + BSE (exact on 99.9% of 1,165 stocks); SS's
is NSE's exactly.

## The nightly run (`ss_sync.yml`, weekdays 22:02 IST)

1. **SS, gently:** page 1 (1,000 sessions) for each stock, the next 40 not
   yet updated tonight (`sync_ss.py --stale-hours 12`), about four hours for
   the universe. A stock whose history SS restated, or that jumped past the
   limit, re-downloads whole. HTTP 403/429 stops the run and keeps what was
   fetched; the next run resumes.
2. **Saved** to the `data-latest` release and published to R2 as `prices/ss`
   (7 nightly copies + month-ends kept).
3. **The three-source check** (`scripts/reconcile_report.py`) over the last
   45 days. Its report is the run's summary page and is saved to the release
   (`reconcile_report.md`, `reconcile_summary.json`, CSV detail). It never
   changes a stored price.

GitHub starts scheduled runs late (often an hour or more), so the SS update
usually finishes between 02:00 and 05:00 IST.

Other nightly jobs: `screener_sync` (Screener store), `nse_collect` (every 4
hours: NSE's daily bundle into R2), `daily_sync` (rankings, benchmark,
membership).

## The rules

### Corporate actions

- **Splits, bonuses, consolidations:** from NSE's corporate-action file, each
  applied only where the price actually moved by its factor
  (`src/loaders/nse_adjusted.py`).
- **Rights issues** (`src/engine/reconcile.py`): the factor comes from NSE's
  terms, `(held·cum + new·issue) / ((held+new)·cum)`, with issue = face value
  + premium.
  - **Face value:** from NSE's corporate-action list, which states it; otherwise
    inferred from the factor SS or Screener applied (₹1, 2, 5 or 10), else ₹1.
    UTKARSHBNK, TIL and RELTD are ₹10, as inferred.
  - **Whether SS already adjusted it:** SS's ex-date move is compared with
    NSE's raw move (NSE never adjusts rights). Equal: SS left it raw, so the
    factor is applied. A gap equal to the factor: SS already adjusted, left
    alone. Another gap: SS used its own factor, kept and flagged. No NSE price:
    nothing applied, flagged.
  - Measured on 10 rights issues, Oct 2025 – Sep 2026: SS had adjusted 8; we
    adjusted ADANIENT and JAYKAY, matching Screener's own factor (0.9695,
    0.9239).
- **Demergers:** there is no single right factor; sources legitimately differ.
  NSE prices it at the ex-date's own fall. A lasting SS/Screener level shift on
  a demerger ex-date is tagged with the action, not flagged as unexplained.
- **Dividends** are not added back anywhere: the strategy is price-only, like
  the Nifty 500 price index it is compared with.

### The vote (every stock, every session)

One-day moves are compared on a shared calendar, so a move never spans a day a
source lacks. Within 0.5 percentage point: agreed.

- **Two of three agree:** their move is used; the odd source is named.
- **All three differ:** NSE's move is used (the exchange's record); flagged.
- **Two sources only:** NSE's move if NSE is one of them. Without NSE and more
  than 20% apart: the smaller move is used and flagged. One of the two has
  mishandled a corporate action (SS divided TVSHLTD by 47 for a
  preference-share bonus, Sep 2026).
- **The reconciled series** starts from SS's level and chains the settled
  moves; a session SS lacks is filled from the others and logged.
- NSE judges every stock: the report fills NSE's closes for stocks outside
  the committed set from NSE's raw daily files on R2, adjusted the same way.

What the vote found (Aug–Sep 2026, 1,210 stocks): SS outvoted 52 times (new
September listings ~1% off, a 10 Aug two-series day, TVSHLTD); Screener
outvoted 18 times (INA, MARSONS, JAYKAY, TVSHLTD: a non-NSE close); 1
unresolved (HEG's demerger day, NSE's 0% used).

### Renames (`src/loaders/nse_identity.py`)

An old symbol maps to today's listing from NSE's own records, no hand-kept
list:

1. NSE's symbol-change list (`data/reference/nse/symbolchange.csv`, 1999 on);
2. the same ISIN (`data/reference/nse/isin_history.csv`: every symbol–ISIN pair
   in NSE's bhavcopy, Jun 2011 – Jun 2021; `equity_l.csv` for today's);
3. the ISIN's first 9 characters (issuer and security type): an ISIN changes
   with the face value (20MICRONS INE144J01019 → …027 after ₹10 → ₹5).

575 renames, 267 confirmed by both records, 0 conflicts; the 21 renames once
kept by hand in `data/nse_prices/notes.json` are all among them, plus
GUJGASLTD → GUJENERGY (1 Jul 2026). An automatic rename is joined only where
the two price series meet (at most 15 days apart, within ±25%): a company
restructured in insolvency keeps its issuer code but not its price (DHFL →
PIRAMALFIN). `notes.json` still overrides. Asking for an old name returns its
successor's joined series.

## NSE history back to 2010 (R2)

| Dataset | Coverage | Source |
|---|---|---|
| `nse/prices_daily` | 10 Jun 2010 – today; Jan–Jun 2010 being collected | NSE's daily bundle (`nse_collect`), and for history the GitHub mirror [tilak999/NSE-Data-bank](https://github.com/tilak999/NSE-Data-bank) of NSE's full bhavcopy |
| `nse/corporate_actions` | Oct 2023 – today, per listing day | NSE's daily Bc file |
| `nse/corporate_actions_history` | 2010 – 2026, one file per ex-date year, with face values | NSE's corporate-action list, one request a year |
| `nse/closed_days` | Days with no bundle a week later | `nse_collect`, so each holiday is asked once |

The mirror is NSE's file unchanged: equal to NSE's own on close and volume for
every row of 2 Jan 2012 (1,491) and 10 Aug 2026 (2,712). Imported 2 Oct by
`nse_history_import.yml` (8 sessions at a time, 0 failures).

## Running it by hand

```
python scripts/reconcile_report.py --ss data_cache/ss --start 2025-10-01   # the three-source check
python scripts/sync_ss.py --stale-hours 12 --limit 40                      # one gentle SS round
python scripts/import_nse_history.py --prices --mirror mirror/data --workers 8
python scripts/import_nse_history.py --actions --from-year 2010
python scripts/build_isin_history.py --mirror mirror/historic_data         # once; history
```

Workflows on demand: `ss_sync.yml` (mode daily/backfill), `nse_collect.yml`
(backfill, minutes, since), `nse_history_import.yml`.

## To do

- Missing-days check, 2010 to today: `nse_collect` asks NSE once for every
  weekday R2 lacks; done when a run reports 0 days to go.
- Run the adjustment check across 2010–2026 on the full NSE history, then the
  long backtests.
- Remove the dead Yahoo code and the `yfinance` dependency.
