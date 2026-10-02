# Point-in-time membership from NSE's own notices

**Date:** 2026-10-01 · **Status:** applied, covers 2025-12-31 onward

## The problem

The daily sync only began recording the Nifty Total Market list (the app's
750-stock universe) on **2026-08-19**. Every backtest rebalance before that was
scored on *today's* list, so the book could hold names before the index did.
Index additions skew toward recent winners and this screen buys exactly those,
so the bias runs in a known direction. Seen in the Backtest on 1 Sep 2026:
MBAPL, PAISALO, SHREEJISPG and SIGMAADV were "sold" as `Rebalance Exit` although
none was in the index (all four joined on 2026-09-30).

## The fix

NSE Indices announces every change to every Nifty index in a press release
(<https://www.niftyindices.com/press-release>). Each notice has a
"Nifty Total Market" table of the names included and excluded, with symbols.
The list on an earlier date is the later list with those changes undone.

```
data/membership_notices.json                 the changes read from the notices (+ URL, SHA-256)
scripts/parse_index_notices.py               notice text -> included / excluded symbols
scripts/extend_membership_from_notices.py    ledger | apply | check
data/membership_history.json                 baseline now 2025-12-31, then every change
```

Rewound from the 2026-08-19 list through four notices:

| effective | notice | change |
|---|---|---|
| 2026-03-30 | `ind_prs23022026.pdf` | semi-annual review, 59 in / 59 out |
| 2026-05-12 | `ind_prs04052026.pdf` | GSPL → RATNAMANI (amalgamation) |
| 2026-05-15 | `ind_prs08052026.pdf` | CIGNITITEC → SANOFICONR (amalgamation) |
| 2026-07-17 | `ind_prs13072026_1.pdf` | JBCHEPHARM → GRINDWELL (amalgamation) |

A change takes effect **on** the notice's effective date ("effective from
March 30, 2026 (close of March 27, 2026)" means the 30th's list is the new one).

## How it is checked

Nothing is guessed. `apply` stops unless all of these hold:

1. **Every step fits.** Rewinding a change needs each symbol it included to be in
   the list after it and each symbol it excluded to be absent. The list stays at
   750 names at every date.
2. **Independent notices agree.** The rewound 2025-12-31 list must match the last
   thing each of 73 symbols was told by the notices from the 2025-09-30 review,
   2025-10-28, 2025-12-26 and 2025-12-31. Those are separate documents on the
   other side of the start date, so this is a forward check on the backward walk.
3. **A known answer.** The parser reproduces the 2026-09-30 change the daily sync
   recorded on its own, symbol for symbol (53 in, 53 out, no difference).
4. **The March Total Market table equals what its Nifty 500 and Microcap 250
   tables imply**, and every table's serial numbers run 1..n (a dropped row is an
   error, not a shorter list).
5. Replaying the new history reproduces the 2026-08-19 list exactly.

`tests/test_membership_from_notices.py` holds these, and `check` re-verifies the
committed files at any time.

## What it does not cover

- **Ticker changes** are not exits, so NSE issues no notice for them. The one in
  the window, `SUNDARMHLD` -> `TSFINV` (Sundaram Finance Holdings -> TSF Investments,
  ISIN INE202Z01029, effective 2025-10-16), is recorded under `symbol_aliases` in the
  ledger. It is visible in our own data: `TSFINV` is in the list continuously from
  2025-12-31 to 2026-09-29, and the 30 Sep notice lists it among the exclusions. The
  NSE approval reference (NSE/LIST/362) comes from the owner and was not fetched.
- **Demerger placeholders** (`DUMMYVEDL1…4`, `DUMMYHDLVR`, `DUMMYALCAR`,
  `DUMMYINXGN`, `DUMMYTRVN`, `DUMMYHEG`, `DUMMYINGL1/2`) are held at zero price
  for a few weeks and are not tradeable. The central `is_tradeable_symbol` filter
  drops them everywhere, and with no price they could never be selected anyway.
- **Before 2025-12-31** there is no record, so `members_on` answers `None` and the
  backtester reports those rebalances as scored on today's list.

## Extending further back

Download the notices (the site's CDN may refuse a request that has no referer):

```
curl -A "Mozilla/5.0" -e https://www.niftyindices.com/ -O \
  https://www.niftyindices.com/Press_Release/ind_prs23022026.pdf
python scripts/extend_membership_from_notices.py ledger --pdf-dir <dir>
python scripts/extend_membership_from_notices.py apply --start 2025-09-30
python scripts/extend_membership_from_notices.py check
```

`ledger` rebuilds the whole file from the PDFs in the folder, so keep every notice
from the earliest one wanted through today. The press-release page lists every
notice with its title and date.

## Prices for the names the index dropped

Membership alone is half of it. The deep price history is the *current* 750's, so a
name the index held in March and dropped by September had no prices, and the
backtest could only pick from survivors (the mirror image of the hindsight bias:
the dropped names are mostly the weaker ones). Measured on the 2026 month ends,
54 to 98 of the 750 members had no prices at all.

- `data/former_member_prices.parquet` (+ `.json`): adjusted closes from Yahoo for
  the 104 former members that have history, filed under their current ticker.
  `scripts/sync_former_member_prices.py` rebuilds it; the monthly workflow runs it
  before freezing a month.
- `src/loaders/former_members.py` joins it onto a price frame, adding only names the
  membership record lists. The backtester's mask still decides who may be held on
  each date; the extra columns select nothing on their own.
- Wired in at the Backtest page, `record_run` (Track Record, Actions and Portfolio)
  and `scripts/update_track_record.py`.
- **Ticker changes** are recorded in the history's `aliases` and followed by
  `members_on(..., canonical=True)`: `HEG` -> `HEGAM` on 2026-09-23 (identical
  prices on every overlapping day). Yahoo files a renamed stock's whole past under
  its new ticker.
- **Merged away:** `CIGNITITEC`, `GSPL`, `GUJGASLTD`, `JBCHEPHARM` have nothing on Yahoo,
  but NSE's own record has all four (see `docs/NSE_PRICE_BASIS.md`), so none is unpriceable now.
- **Sector cap:** a former member has no NSE industry on file, so its TradingView
  industry is mapped to the NSE industry most current members with that
  TradingView industry carry (82% correct leave-one-out on the 750).


## Extension to 2010 and to the other indices (2026-10-02)

`nse_index_rebuild/` rebuilds every index announcement by announcement, backward from NSE's current lists, and
`nse_index_rebuild/merge_into_history.py` folds the result into `data/membership_history.json`:

| index | history now starts |
|---|---|
| `nifty_50`, `nifty_next_50`, `nifty_500` (new entry) | 2010-01-01 |
| `nifty_midcap_150`, `nifty_smallcap_250` | 2016-04-01 (launch) |
| `nifty_microcap_250` | 2021-09-30 |
| `nifty_total_market` (flat keys kept identical) | 2021-10-29 |

Existing baselines and changes are untouched; the reconstruction is prepended after checking that it lands on each
existing baseline exactly. Symbols use today's ticker (renames are not exits), except tickers this file already
records under their old name (`HEG`, `GUJGASLTD`). Tata Motors DVR, an additional security above the nominal size,
is a member while NSE counted it.

**Status: research-grade reconstruction, adopted for production use by the repo owner.** Intervals resting on open
items are listed under the top-level `caveats` key (Jindal Saw / Provogue 2012-03-07 from a secondary source, the
2020 Gayatri / Fluorochemicals window, the inferred PEL / PIRAMALFIN rename, and 2010-2011 exits named without a
symbol). Not done: independent checkpoints against archived constituent files, a blind second review, a data freeze.
Evidence, rules and checks are in `nse_index_rebuild/` (`PROTOCOL.md`).

## Joining a bhavcopy to the history (`scripts/index_symbol_map.py`)

`data/membership_history.json` files members under today's ticker; a bhavcopy carries the ticker of its day. The helper
turns one into the other with the dated ticker-change ledger (`symbol_changes`) in the same file.

```
python scripts/index_symbol_map.py NIFTY_50 2025-03-28
    ZOMATO    (history: ETERNAL)          # the bhavcopy of that day says ZOMATO
python scripts/index_symbol_map.py NIFTY_500 2012-01-02 --bhavcopy cm02JAN2012bhav.csv
    0 of 500 ... / "no bhavcopy row:" lines for members the file does not carry
```

Library calls: `members(h, index, date)`, `bhavcopy_symbols(h, index, date)` (`{ticker that day: history symbol}`),
`symbol_on(h, symbol, date)`, `coverage(h, index, date, tickers)`. Old (`SYMBOL`) and new (`TckrSymb`) bhavcopy layouts are read.

What it does not do: the ledger covers renames of index members found in NSE's notices, not every rename on the exchange, so
a member with no bhavcopy row is reported, never guessed (suspended, delisted, or renamed outside the ledger). Mergers and
demergers are exits and entries on their real dates, not renames. Joining on ISIN, where the bhavcopy has one, covers renames
the ledger misses.
