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



## Multi-index 2026 reconstruction

The same PIT timeline now covers all six index families from **2025-12-31** through the **2026-09-30** review. The source audit is in `data/membership_history_2026_audit.json`; it records the reference dataset, official notice URLs, corporate-action dates, aliases, and the placeholder policy.

| Index | Baseline | Final CSV count after dropping `DUMMY*` |
|---|---:|---:|
| Nifty 50 | 2025-12-31 | 50 |
| Nifty Next 50 | 2025-12-31 | 50 |
| Nifty Midcap 150 | 2025-12-31 | 150 |
| Nifty Smallcap 250 | 2025-12-31 | 250 |
| Nifty Microcap 250 | 2025-12-31 | 250 |
| Nifty Total Market | 2025-12-31 | 750 |

The current CSVs are the end-state anchor. The independent [aditya-jha/nse-historical-membership](https://github.com/aditya-jha/nse-historical-membership) project accelerated extraction of the March and May notice tables, but its inferred closures and ticker canonicalization were not treated as authoritative membership events.

2026 transitions added beyond the semi-annual reviews include:

- **15–24 June:** real listed Vedanta demerged entities enter and are removed on the dates specified by NSE; the DUMMY placeholders are never counted.
- **15 April:** `AKZOINDIA → JSWDULUX` is a ticker/name continuity event, not a membership exit.
- **17 July:** NSE replacement tables specify Smallcap 250 `JBCHEPHARM → PFOCUS`, Microcap 250 `PFOCUS → GRINDWELL`, and Total Market `JBCHEPHARM → GRINDWELL`.
- **7–23 September:** `DUMMYHEG` is excluded from tradable counts; the resulting listed entity is recorded as `HEGAM` from 23 September, replacing `HEG` in Smallcap 250 and Total Market.
- **30 September:** official semi-annual replacement events remain the final event in each timeline.

Nifty Microcap 250 has **249 tradable names at the 2025-12-31 baseline** and reaches 250 on the 2026-03-30 review. This reflects the March notice's special Allcargo/DUMMYALCAR handling after excluding placeholders; the history does not pad the baseline with a fake symbol. Temporary counts of 54, 52 and 51 in Next 50 and Total Market during 15–24 June reflect real listed demerged entities before their official exclusions, not DUMMY rows.

The regression tests replay each timeline against today's CSV after the shared DUMMY filter, assert chronological event ordering, and verify the alias and mid-year replacement events. This is a 2026 completion, not a claim that all six histories are reconstructed back to their index launch dates.
