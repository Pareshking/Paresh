# Price pipeline: sources, the nightly run, and the rules

How prices reach the app, what runs each night, and the rules that keep every
adjustment automatic. Owner, 2026-10-02: "all the adjustment should be
automatic and no manual work, we have 3 source and those can give hints to
each other along with official read from NSE."

_Last updated: 2026-10-07_

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
PIRAMALFIN). The check runs on NSE's raw closes, and the closes are adjusted after the
join, so a split or bonus filed under the new symbol reaches back into the old
symbol's years (INFOSYSTCH → INFY, then three 1:1 bonuses; from #356). `notes.json` still overrides, and holds the three renames no NSE record
has (KBL → KIRLOSBROS, ASIANHOTEL → ASIANHOTNR, PROVOGUE → PROVOGE), found by
joining index membership to the bhavcopy (`reports/membership_bhavcopy_check_2026-10-02.md`).
The membership join (`scripts/index_symbol_map.py`) uses the same NSE list.
Asking for an old name returns its successor's joined series. NSE prices are
read for series EQ, BE and RR (REITs, which are index members).

## NSE history back to 2010 (R2)

| Dataset | Coverage | Source |
|---|---|---|
| `nse/prices_daily` | **2008 – today** (4,216 sessions from 4 Jan 2010 confirmed complete, 0 days missing; 2008–2009 being imported) | NSE's daily bundle (`nse_collect`, from 4 Jan 2010); NSE's classic bhavcopy archive for 2008–2009 (`fetch_nse_bhavcopy.py`: a ranking on 1 Jan 2010 needs a year of history before it); the GitHub mirror [tilak999/NSE-Data-bank](https://github.com/tilak999/NSE-Data-bank) of NSE's full bhavcopy for Jun 2010 – Sep 2023 |
| `nse/corporate_actions` | Oct 2023 – today, per listing day | NSE's daily Bc file |
| `nse/corporate_actions_history` | 2008 – 2026, one file per ex-date year, with face values | NSE's corporate-action list, one request a year |
| `nse/closed_days` | Days with no bundle a week later | `nse_collect`, so each holiday is asked once |

The mirror is NSE's file unchanged: equal to NSE's own on close and volume for
every row of 2 Jan 2012 (1,491) and 10 Aug 2026 (2,712). Imported 2 Oct by
`nse_history_import.yml` (8 sessions at a time, 0 failures).

### Which days are sessions (3 Oct 2026)

NSE never publishes a bhavcopy on a holiday (its bundle URL answers 404). The
GitHub mirror, though, files a copy of the previous session under every holiday
from 2021 (`sec_bhavdata_full_26012024.csv` is 25 Jan's file, `DATE1`
25-Jan-2024), and 73 such copies reached R2 as trading days. Three checks now:

1. **The file's own date:** the importer refuses a file whose rows are dated
   another day (`nse_backfill.NotThatDay`).
2. **Copies:** a session repeating the one before for over 90% of stocks (close
   and volume) is dropped by the long-file builder and listed by the audit
   (`nse_adjusted.copied_sessions`).
3. **The calendar** (`src/loaders/nse_calendar.py`): no session on a weekend
   unless NSE announced it (`data/reference/nse/special_sessions.csv`: Muhurat,
   Budget days, special Saturdays), on a fixed holiday (26 Jan, 1 May, 15 Aug,
   2 Oct, 25 Dec), or on NSE's published list (`data/reference/nse/holidays.csv`,
   from its holiday-master API; a `muhurat` day there is a holiday with an
   evening session).

**Traded value:** the mirror's `TURNOVER_LACS` holds rupees, not lakhs, in its
2010 – 2018 files; R2's rows for those years carry value x 1e5. The importer now
reads the unit off average price x quantity, and the long-file builder scales a
day back when its value over close x volume is near 1e5 (R2 is not rewritten).

**One action, once:** NSE lists an action in its daily Bc file and its yearly
list, worded differently; `nse_adjusted._parsed` keeps one row per symbol,
ex-date, kind and factor (500 splits and bonuses had gone unapplied, #348).

## The long price file (backtests from 2010)

`scripts/build_nse_long_prices.py` (weekly, `nse_long_prices.yml`) reads every
session on R2 from 2008 and writes to the `data-latest` release: closes adjusted
for splits, bonuses, consolidations, demergers, rights issues and dividends
of 10% or more, renames joined (owner, 3 Oct 2026: correct data first), for every stock any index ever listed (1,380, plus 38 old
tickers and Tata Motors DVR: 1,418 series);
traded value in Rs Cr; and a report (units by year, copies dropped, calendar
flags). `src/loaders/nse_long.py` reads it; the Backtest page's "History from
2010" mode runs on it with each index's own point-in-time list
(`src/engine/index_universe.py`; Nifty 100 = Nifty 50 + Next 50).

### How the long file is checked (3 Oct 2026)

`scripts/audit_long_prices.py` compares it, every stock and every day, with
independent histories (all kept on R2 under `reference/`, protected from
clean-up): Yahoo, eod2, Tijori (only series whose level matches NSE
MarketLens), Screener's full history, SS, and -- as references that can show
a move is fake but never confirm one -- TejHQ (adjusts only within an ISIN)
and NSE MarketLens (leaves some old splits raw). It reports the share of days
on the same level, level breaks and which side moved, and every move beyond
21% up or down: confirmed when more references agree than are flat, fake
when more are flat.

What the audit found and what fixed it:

| Fault | Fix |
|---|---|
| A split worded without "from", or with a bonus in the same row, read as no factor (95 + 31 rows, 2008 - 2021) | `classify_purpose` (#350) |
| One action in both the Bc file and the yearly list, applied twice | dedupe (#348); once per session even under a month-first date (#353) |
| Old actions filed under today's symbol (TATACONSUM 2010 traded as TATAGLOBAL) | moved to the symbol that traded (`on_trading_symbol`, #353; 1,947 rows) |
| Actions in neither NSE list | TejHQ's list fills gaps only (#354) |
| A notes.json correction plus a later-listed action (SHRIRAMFIN) | a correction steps aside once an action covers it (#355) |
| Stocks in BZ (trade-for-trade) dropped out, 4,921 stock-days | every equity series read, ranked (`SERIES_RANK`, #355) |
| 2008 - 2009 splits no list has; rights and schemes of index stocks | 19 hand corrections in `notes.json`, each with its evidence (#355) |
| Rights issues never priced (M&MFIN 2020 read -33% in a day; CENTRALBK 2011, NDTV 2025, NCC 2014: 74 lasting steps against Screener) | `rights_factor`: the theoretical ex-rights price, (held x P + new x S) / ((held + new) x P), S = face value + premium from NSE's yearly list; applied only when S is under the last close. 141 priced, 7 at or above market, 5 with no issue price (3 Oct 2026) |
| Rights issues worded "Rhs", "Rht", "Rhts", "Right" in NSE's 2008-2013 lists (HINDALCO 3:7 at Rs 96, Aug 2008; TATASTLBSL 2013): 15 missed | `classify_purpose` reads the abbreviations (145 rights priced); TRENT's 2010 CCPS rights issue, worded without "rights", is a `notes.json` correction |
| Small bonuses (1:10, 1:5, 1:3) the day's move hid: KTKBANK 17 Mar 2020, KARURVYSYA 2018, GOLDIAM 2026 | a bonus or split with factor >= 0.7 is applied on NSE's word, once within 45 days (`SMALL_FACTOR`); 8 actions |
| SME actions missing from NSE's main list (JSLL 4:5 bonus 2023, 1:5 split 2025) | `notes.json` corrections |

Three more audits (3 Oct 2026), run by `nse_long_prices.yml` after every
build and published as `long_price_audit_latest.zip` on the release:

- `scripts/audit_against_screener.py`: every Screener point matched to our
  close on the same date (no Friday resampling: Screener's old points fall on
  any weekday). 97.8% of 887,093 intervals within 2%; each lasting level step
  is pinned to its interval and the other references vote on which side
  moved. After rights and small bonuses: 26 steps where ours is the odd one,
  most of them demergers we price and the references leave raw (ALEMBICLTD,
  MASTEK, TRIVENI, ZEEMEDIA, ABFRL 2025) or old splits only two raw
  references cover.
- `scripts/audit_raw_bars.py`: NSE's raw rows (the pack). Bar arithmetic:
  240 closes outside [low, high], all in series T0 (the build takes EQ's
  close those days), and 1,372 average prices off by rounding on tiny
  volumes. Calendar: the 73 sessions the build drops are all days the
  Nifty 50 did not trade; no session missing. Symbol changes against
  `isin_history.csv`: 95 same ISIN, none changed, 218 too old for the ISIN
  history. Dividends of 5% of the price or more: 199 (23 of 10% or more,
  PFIZER's Rs 360 on 5 Dec 2013 the best known) -- not adjusted, see below.

Web check of the 50 largest History trades (Nifty 500, 2010 - 2026; four
independent searches, NSE's own bhavcopies for 12 of them): 49 real, the 50th
(PFIZER Dec 2013, -32.6%) a real price fall of which Rs 360 was a dividend
(holder's return about -11%). An AI-written check that reproduced our own
numbers to the decimal was not counted as evidence.

### Gaps in the file, checked against BSE (3 Oct 2026)

The price audits compare only days both sources have, so a stretch NSE has no
rows for is invisible to them. `scripts/bse_bhavcopy.py` downloads BSE's bhavcopy
2008 - today into one table and `scripts/audit_gaps_against_bse.py` checks every gap
of 5 or more sessions against it: 147 are NSE-only (BSE traded the stock), 79 are
suspensions BSE shows too, 18 partly, 182 could not be matched. The largest, 26 Oct
2023 - 17 Apr 2026 (GOODYEAR, NOVARTIND, KENNAMET, KIRLFER, GRAUWEIL; FORCEMOT to
14 Feb 2024), is NSE's withdrawal of dealings under "Permitted to Trade"; no
backtest is affected because the stocks were out of the indices for it. The
method, the numbers and the explanation are in `docs/DATA_CORRECTNESS.md`
(sections 5 and 6). KESORAMIND's 10 Mar 2025 demerger (-95%, 1 UltraTech share per
52) was found by the same audit and is priced at the ex-date fall in `notes.json`.

### NSE-only gaps filled from BSE (owner, 7 Oct 2026, S38)

The build fills a stretch of 5+ sessions NSE has no row for with BSE's close
where BSE traded the same company (`src/loaders/bse_fill.py`). The rule:

- **Raw space.** BSE's closes go into NSE's raw closes before any action is
  confirmed or applied, so every factor (and `notes.json` correction) reaches the
  filled days as it reaches NSE's; an action dated inside a gap is confirmed on
  BSE's move. BSE's closes are never mixed with adjusted ones.
- **Same company** by ISIN (near the gap, else another period); the gap audit's
  price match only when no ISIN finds a code; an ambiguous match, or a code whose
  ISIN names another issuer, is refused.
- **BSE traded** on at least half the gap's sessions with a BSE file (else a
  suspension, not filled); only the sessions it traded are filled.
- **Junctions**: BSE within 2% of NSE (median of the 3 nearest common days) at
  both ends, else refused.
- **NSE's own days are never overwritten**; traded value is not filled.

BSE's table comes from the release asset `bse_daily.parquet`, extended weekly
with the new sessions by `bse_daily.yml` (Fridays 20:30 UTC, before the Saturday
build) and copied monthly to R2 `bse/daily` (protected from clean-up). Without
it the build fills nothing and says so (`bse_fill.status` in the report). Each
build writes `bse_fill_cells.csv` and `bse_fill_gaps.csv`; the audit step adds
`bse_fill_verify.json` (agreement with Tijori, Screener, Yahoo, eod2, SS) to
`long_price_audit_latest.zip`. Local rebuild of 7 Oct: 24 gaps filled (20 stocks,
3,443 sessions, GOODYEAR, NOVARTIND, KENNAMET, KIRLFER and GRAUWEIL across 26 Oct
2023 - 17 Apr 2026 among them), 387 refused; 98.6% of the filled cells a
reference covers are within 2% of one. Numbers and the refusals:
`docs/DATA_CORRECTNESS.md` section 6.

### Dividends: only the large ones are adjusted

Ordinary dividends stay in the price, as in Screener's (the live system's
source), so the History and Live backtests stay on one basis. A payout of 10%
of the last close or more is taken out (owner, 3 Oct 2026, option 1): factor
(P - D) / P on the ex-date, every amount in the text added ("Final Rs 6.50
and Special Rs 60" is 66.50), applied only where the price fell by at least
half of it (`nse_adjusted.LARGE_DIVIDEND`). 28 events 2008 - 2026: PFIZER's
Rs 360 and WYETH's Rs 145 on 5 Dec 2013, STAR 2013, PATNI 2010, IDFC 2023,
HINDZINC 2016, BPCL 2021 ... The four dividend falls the +-15% screen called
fake are gone; Nifty 500 History 2010 - 2026: 19.9%/yr, Sharpe 0.70, maximum
drawdown -37.1%.

### Screener's history is sparse before the latest year

Screener's store holds daily closes for about the latest year and weekly or
irregular ones before (726 rows since 2016 for a stock NSE has 2,500 - 4,600
days of). Where both have a day the closes are identical. But the momentum
windows count rows, so on Screener's sparse stretch "252 rows back" reaches
further than a year: GVT&D's 12-month return at end-May 2026 read +173% on
Screener against +125% on NSE, enough to swap a stock in or out of the top 20.
A 2026 Total Market backtest on each (same engine, settings and point-in-time
list) differs by about one holding a month and 0.3 - 0.5 points a month.

## Running it by hand

```
python scripts/reconcile_report.py --ss data_cache/ss --start 2025-10-01   # the three-source check
python scripts/sync_ss.py --stale-hours 12 --limit 40                      # one gentle SS round
python scripts/import_nse_history.py --prices --mirror mirror/data --workers 8
python scripts/import_nse_history.py --actions --from-year 2010
python scripts/build_isin_history.py --mirror mirror/historic_data         # once; history
python scripts/nse_history_audit.py --since 2010-01-01                     # the history audit
```

**The history audit** (`nse_history_audit.yml`, on demand; read only) checks
R2's NSE history: missing days, both by the calendar (weekdays neither held nor
a known closed day) and independently by NSE's own previous closes (a session
whose previous close does not match our previous session for most stocks);
every split, bonus and demerger with whether the price confirms it;
unexplained one-day moves beyond 1.8×; renames refused by the continuity
check.

Workflows on demand: `ss_sync.yml` (mode daily/backfill), `nse_collect.yml`
(backfill, minutes, since), `nse_history_import.yml`, `nse_history_audit.yml`.

## To do

- Missing-days check, 2010 to today: `nse_collect` asks NSE once for every
  weekday R2 lacks; done when a run reports 0 days to go.
- Run the adjustment check across 2010–2026 on the full NSE history, then the
  long backtests.
- Remove the dead Yahoo code and the `yfinance` dependency.
