# Index membership joined to NSE bhavcopy, 2010–2026

_2 Oct 2026. Read-only check of `data/membership_history.json` (main @ b7f77a6) against NSE's daily bhavcopy. Nothing in the repo was changed._

## What was used

- **Membership:** `data/membership_history.json` through `scripts/index_symbol_map.py` (`coverage()`, `bhavcopy_symbols()`, `symbol_on()`), exactly as on main.
- **Bhavcopy:** NSE's full bhavcopy (`sec_bhavdata_full_DDMMYYYY.csv`) from the public mirror tilak999/NSE-Data-bank.
  - It equals NSE's own file on close and volume for every row checked (2 Jan 2012, 1,491 rows; 10 Aug 2026, 2,712 rows).
  - 4 Jan 2010 is from NSE's own daily bundle (`Pd040110.csv`), as the mirror starts on 10 Jun 2010.
  - ISINs come from the mirror's old-format files (`cm…bhav.csv`, ISIN column from 22 Jun 2011).
- **Reference files:** `data/reference/nse/symbolchange.csv`, `isin_history.csv`, `equity_l.csv`.
- **Market caps:** NSE's bundle market-cap file. It exists only in recent years; 2015 and 2020 bundles have none.
- **"Missing"** means no row in *any* series that day. Members trading outside EQ are counted separately.

## Dates checked (35)

- The last session of every year, 2010–2025, and 30 Sep 2026.
- 4 Jan 2010, the first session after the baselines.
- 3–4 effective dates per index from `changes`: the first, the last and two in between. A date that wasn't a session uses the next one.

All 7 indices were checked on every date they have a record. Midcap 150 and Smallcap 250 start in 2016, Microcap 250 in 2021-09 and Total Market in 2021-10.

## 1. Match rates

| Index | Member-days | Helper as on main | With NSE's symbol-change list in the join |
|---|---|---|---|
| Nifty 50 | 1,753 | 97.78% (39 missing) | **100%** |
| Nifty Next 50 | 1,750 | 99.49% (9) | **100%** |
| Nifty 500 | 17,520 | 98.65% (237) | 99.95% (9) |
| Midcap 150 | 3,750 | 99.89% (4) | **100%** |
| Smallcap 250 | 6,250 | 99.58% (26) | 99.98% (1) |
| Microcap 250 | 3,250 | 99.23% (25) | 99.97% (1) |
| Total Market | 9,758 | 99.56% (43) | 99.98% (2) |

## 2. Every missing member, with its cause

### a. Renames not in the history's ledger (252 of the 262 missing rows, 46 companies)

On each of those dates, that day's bhavcopy has the company under its old ticker, and NSE's `symbolchange.csv` dates the change. None of the 46 pairs is in `symbol_changes` (105 entries, all renames found in index notices).

Examples:

| Old ticker → today's ticker | Changed on |
|---|---|
| TATAMOTORS → TMPV | 24 Oct 2025 |
| INFOSYSTCH → INFY | 29 Jun 2011 |
| HEROHONDA → HEROMOTOCO | 8 Aug 2011 |
| MUNDRAPORT → ADANIPORTS | 17 Jan 2012 |
| UNIPHOS → UPL | 23 Oct 2013 |
| NEYVELILIG → NLCINDIA | 4 Aug 2016 |
| MERCK → PGHL | 11 Jun 2019 |
| KALPATPOWR → KPIL | 6 Jun 2023 |
| TIDEWATER → VEEDOL | 9 Oct 2024 |

The full list is in `classified.csv`. **These memberships are right; the join cannot translate.**

### b. Renames in no NSE list (3 companies, 6 rows)

Each is proven by the company name, ISIN or listing date in NSE's own files:

| History symbol | Bhavcopy ticker | Dates | Evidence |
|---|---|---|---|
| KIRLOSBROS | **KBL** | 4 Jan 2010 | NSE `Pd040110.csv`: KBL = "KIRLOSKAR BROTHERS LTD"; `equity_l.csv`: KIRLOSBROS listed 20 Apr 2010 |
| ASIANHOTNR | **ASIANHOTEL** | 4 Jan 2010 | `Pd040110.csv`: ASIANHOTEL = "ASIAN HOTELS LTD"; ASIANHOTNR listed 7 Apr 2010, ISIN INE363A01022 |
| PROVOGE | **PROVOGUE** | 4 Jan 2010 – 30 Dec 2011 | `isin_history.csv`: PROVOGUE INE968G01025 to 6 Mar 2012, PROVOGE INE968G01033 from 26 Mar 2012 (same issuer prefix INE968G01) |

### c. No trade that day (4 companies, 6 rows): not membership errors

| Symbol | Dates | Evidence | History |
|---|---|---|---|
| DYNAMATECH | 1 Nov 2013 | Traded 31 Oct 2013 (EQ); no row on 1 Nov | — |
| ZODIACLOTH | 31 Dec 2013 | Traded 30 Dec 2013; no row on 31 Dec or 2 Jan 2014 | — |
| FRETAIL | 30 Sep 2022 | No row on 29–30 Sep; BE on 3 Oct | Removed from Microcap / Total Market on 25 Oct 2022 (`ind_prs20102022`) |
| RELINFRA | 31 Dec 2025 | BE on sampled days Sep–Dec 2025, then absent 22 Dec 2025 – 30 Jan 2026 and intermittently after | Member of Nifty 500 / Smallcap 250 from 23 Sep 2025 (`ind_prs15092025_1`) to 30 Mar 2026 (`ind_prs23022026`) |

**No error in the history was found.** Every one of the 262 missing rows is a ticker the join can't translate or a day with no trade.

## 3. The other direction

**Members trading outside EQ:**
- **252 member-days in BE** (trade-for-trade; e.g. ADANIPOWER, SUZLON, PATANJALI, JSWENERGY on some dates) and 2 in BE/E1. Normal; the membership is fine.
- **9 in RR**: the REITs **BAGMANE, BIRET, EMBASSY**, members on 30 Sep 2026. A price reader that keeps only EQ/BE (ours: `nse_adjusted.SERIES`) drops them.

**Large caps the history omits (31 Dec 2025, NSE full market cap):**
- **Top 50:** all are in the Nifty 100.
- **Top 300 not in the Nifty 500:**
  - **Recent IPOs** (not yet eligible at a semi-annual review): TATACAP, ICICIAMC, LGEINDIA, GROWW, MEESHO, LENSKART, PINELABS, ANTHEM, HDBFS, PWL.
  - **TMCV:** demerged and listed in Nov 2025.
  - **PIRAMALFIN:** added 30 Mar 2026 (open item 5).
  - **METROBRAND, TVSHLTD:** low free float. NSE ranks on free-float market cap.
- **Not checked before about 2023:** NSE's bundle carries no market-cap file then.

## 4. Fix (applied 2 Oct 2026 on the owner's go-ahead)

`data/membership_history.json` needs **no change**. The fix is in the join:

- **`scripts/index_symbol_map.py`, `symbol_on()`:** also follow NSE's `data/reference/nse/symbolchange.csv` after the history's own `symbol_changes`.
  - Tested on a scratch copy: Nifty 50, Next 50 and Midcap 150 reach 100% on all 35 dates.
- **Add the 3 renames in 2b** as dated aliases, with their evidence, wherever you prefer: `aliases`, a ledger beside the helper, or `data/nse_prices/notes.json` for the price join. With these, every member on every sample date has a bhavcopy row except the four no-trade days in 2c.

**Applied:**
- `scripts/index_symbol_map.load()` extends the ticker ledger in memory with NSE's `symbolchange.csv` and the 3 renames (`EXTRA_RENAMES`). `--notice-ledger-only` keeps the old behaviour. The history file is untouched.
- The 3 renames are in `data/nse_prices/notes.json` for the price join.
- `nse_adjusted.SERIES` includes RR.
- **Price readers must include series RR (REITs)** alongside EQ and BE.

## 5. Using the history in backtests (proposal)

1. **Membership mask:** on each rebalance (signal) date `d`, the universe is `members(h, index, d)`.
   - A change dated D counts from D (NSE's "close of D-1").
   - Rank only members; hold until the next rebalance's mask drops a name. Index exits don't force a sale mid-month unless the strategy wants that.
2. **Symbol join:** keep prices under today's ticker. Join each old ticker's series into it with NSE's symbol-change list plus ISINs (`src/loaders/nse_identity.py`, already on main), and the 3 aliases above.
   - Join only where the two series meet (at most 15 days apart, within ±25%).
   - A merger or demerger is an exit, never a join (the history already treats it so).
3. **Missing prices:**
   - **A day without a row** (no trade, or a BE/surveillance day): carry the last close for valuation, at most 5 sessions.
   - **An exit due on such a day:** sell at the first close within 5 sessions after the exit date. If none, record the exit at the last traded close, flagged "stale exit" (FRETAIL, RELINFRA cases).
   - **A member that stops trading for good** (delisted on merger): settle at the last close, or at the scheme's terms if recorded.
   - **Never fill from another company's series.**
4. **DVR and extra members:** Tata Motors DVR is a separate security with its own price and series.
   - **Option A:** keep it investable but count it with TATAMOTORS/TMPV for the 5% per-stock and 40% per-industry caps.
   - **Option B:** exclude it, as illiquid.
   - Your decision. The +1 member count must not be "corrected" away; the history is right to carry it.
5. **Before an index's first record:**
   - Midcap 150 and Smallcap 250 start 1 Apr 2016, Microcap 250 30 Sep 2021, Total Market 29 Oct 2021.
   - A "750" backtest before Oct 2021 has no point-in-time universe. The honest options are Nifty 500 only for 2010–2021, or start the 750 in Nov 2021.

## Limits

- **35 sample dates**, not every session. The helper can run on all 4,000+ once the prices are joined.
- **Membership:** a reconstruction from NSE notices, cross-checked against NSE's workbook. Not an NSE-certified record; compliance sign-off is yours.
- **Large-cap check:** only 31 Dec 2025.
- **Mirror:** checked equal to NSE on two full days, not on every file.

Detail (local, not committed): `reports/membership_bhavcopy_check/coverage.csv` (per date and index), `detail.csv`, `classified.csv`.
