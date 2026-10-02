# Point-in-time index membership, one file (2010 to date)

`data/index_membership_pit.csv` holds the membership of seven NSE indices as one table, built by
`nse_index_rebuild/export_pit.py` from the announcement-by-announcement reconstruction in
`nse_index_rebuild/` (backward from today's NSE lists).

| column | meaning |
|---|---|
| `index` | `NIFTY_50`, `NIFTY_NEXT_50`, `NIFTY_MIDCAP_150`, `NIFTY_SMALLCAP_250`, `NIFTY_MICROCAP_250`, `NIFTY_TOTAL_MARKET`, `NIFTY_500` |
| `symbol` | ticker the stock traded under during the interval |
| `current_symbol` | today's ticker (follows `rules/aliases.csv`); use it to join prices |
| `from_date` | first day the stock is a member |
| `to_date` | last day it is a member; blank = member today |
| `caveat` | blank when the row has no open item (see below) |

A stock is a member on day `d` when `from_date <= d` and (`to_date` is blank or `d <= to_date`).

```python
import pandas as pd
m = pd.read_csv("data/index_membership_pit.csv", dtype=str).fillna("")
def members(index, d):
    s = m[(m["index"] == index) & (m["from_date"] <= d) & ((m["to_date"] == "") | (m["to_date"] >= d))]
    return sorted(s["current_symbol"])
```

## Coverage

| index | first date |
|---|---|
| Nifty 50, Nifty Next 50, Nifty 500 | 2010-01-01 (start of the announcement archive) |
| Nifty Midcap 150, Smallcap 250 | 2016-04-01 (launch) |
| Nifty Microcap 250 | 2021-09-30 (first reconstructed snapshot) |
| Nifty Total Market | 2021-10-29 (first reconstructed snapshot) |

Sizes: 50 / 50 / 150 / 250 / 250 / 750 / 500 at every date. Nifty 50 holds 51 from 2016-04-01 to 2017-05-26 and
Total Market and Nifty 500 hold one extra for the Tata Motors DVR additional security while NSE counted it
(see `nse_index_rebuild/PROTOCOL.md`). DUMMY placeholders are excluded.

## Caveats (rows with a non-blank `caveat`)

These are the items the verification protocol could not close. They are 29 rows of 5,409; filter them
out if a backtest must avoid every unproven item.

| code | rows | what it means |
|---|---|---|
| `WEB_SECONDARY_2012-03-07` | 2 | Jindal Saw in / Provogue out of Nifty 500 on 2012-03-07 rests on a third-party list; the NSE notice is unavailable |
| `AMBIGUOUS_2020-03-27_TO_2020-06-25` | 1 | Gayatri Projects / Gujarat Fluorochemicals swap in Smallcap 250: NSE's own notices disagree on the date |
| `INFERRED_MERGER_SUCCESSOR` | 12 | PEL to PIRAMALFIN rename is inferred from the merger, not an NSE circular |
| `UNMAPPED_NAME_ONLY_NOTICE` | 14 | 2010-2011 exits listed by company name only, no symbol in the notice |

(Some rows carry more than one code, so the counts overlap.)

## What has and has not been verified

- Every date replays exactly (`export_pit.py` re-derives all 383 snapshots from this file and today's NSE lists).
- From 2025-12-31 it agrees on membership with the existing `data/membership_history.json` for all six indices
  both cover; the only differences are ticker-rename timing (`AKZOINDIA`/`JSWDULUX`, `HEG`/`HEGAM`).
- Nifty 500 equals Nifty 50 + Next 50 + Midcap 150 + Smallcap 250 from October 2016, and Total Market equals
  Nifty 500 + Microcap 250 since 2021, on every compared date, apart from the DVR share.
- Not done: independent checkpoints against archived constituent files (the first Wayback pass found no usable
  captures), a blind second review of the parsed events, and a data freeze. Historical membership before 2025 is
  therefore a reconstruction from NSE press releases, not an NSE-certified record. Compliance sign-off for
  regulatory use is not something this repo supplies.

Regenerate with `cd nse_index_rebuild && python3 export_pit.py`.
