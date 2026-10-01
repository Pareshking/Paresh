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

- **`SUNDARMHLD`** was included 2025-09-30 and is absent on 2026-08-19, with no
  exit notice among the press releases. It is in neither the 08-19 nor the 09-30
  list, so it is not in the app's price universe and cannot be selected. The
  ledger records it as unexplained rather than hiding it. If a notice for it
  exists that this run did not find, it would also have swapped in one other
  name; that cannot be ruled out, only bounded to one name for part of the year.
- **Demerger placeholders** (`DUMMYVEDL1…4`, `DUMMYHDLVR`, `DUMMYALCAR`,
  `DUMMYINXGN`, `DUMMYTRVN`, `DUMMYHEG`, `DUMMYINGL1/2`) are held at zero price
  for a few weeks and are not tradeable. The central `is_tradeable_symbol` filter
  drops them everywhere, and with no price they could never be selected anyway.
- **Before 2025-12-31** there is no record, so `members_on` answers `None` and the
  backtester reports those rebalances as scored on today's list.
- The **Track Record's frozen months** (Jan–Aug, `origin: backfill`) were computed
  before this and are not recomputed by it.

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
