# Track Record — contract and operations

`data/track_record.json` is the append-only monthly record of what the strategy
posted, from **January 2026**, measured against **Nifty 500 (`^CRSLDX`)**.

---

## 1. Why it exists

The Backtest tab recomputes everything from live prices on every run. That is
correct for a backtest and useless as a track record: a vendor price revision,
an index constituent change, or a nudged weight slider silently rewrites what
January returned. A record that changes when you change your mind is a rolling
opinion, not a record.

So the ledger is **append-only**. A closed month is written once and frozen.

---

## 2. The contract

| Rule | Enforced by |
|---|---|
| A stored month is never rewritten | `finalize_months()` skips any month already present |
| Re-running changes nothing | Idempotent by construction; the scheduled workflow runs 4 days a month and is a no-op after the first success |
| Only **closed** months enter | Months `>= current_month` are refused; MTD is never stored |
| Nothing before inception enters | Months `< 2026-01` are refused |
| A settings change cannot rewrite history | Each entry stores the config fingerprint that produced it |
| A corrupt ledger is never silently reset | `load_ledger()` raises rather than returning an empty ledger |
| Rewriting requires deliberate intent | `--force`, which is opt-in and loud |

`tests/test_track_record_ledger.py` pins all of the above — including a test
that freezes January at +10%, re-runs with a curve where January recomputes to
−40%, and asserts the stored +10% stands.

### Drift

`drift_report()` reports where a recompute now disagrees with what was frozen.
It is a diagnostic, not a correction: prices get revised and universes change.
**The stored value always wins.** The monthly updater prints any drift it finds.

---

## 3. Entry shape

```json
"2026-08": {
  "strategy":     0.126,
  "benchmark":   -0.0003,
  "alpha":        0.1263,
  "origin":       "recorded",
  "finalized_on": "2026-09-03",
  "config":       "5b356a6ba93b",
  "data_as_of":   "2026-09-03"
}
```

### `origin` — how much the month is worth

- **`recorded`** — frozen the month it closed, from the data as it stood then.
- **`backfill`** — reconstructed later from *today's* universe and prices.

This is not a formality. A backfilled month applies today's index membership to
a month before some of those stocks joined it, so it carries the backtest's
survivorship bias and flatters results by an unknown amount. Assigned
automatically: the month that just closed is `recorded`, anything older in the
same write is `backfill`. No flag to remember.

The Jan–Aug 2026 block was backfilled on 2026-09-03; only August is recorded.
Treat the backfilled block as the strategy's *shape*, not its record.

---

## 4. Conventions

Matching the reference tracker:

| Aggregate | Definition |
|---|---|
| Q1 / Q2 / Q3 / Q4 | Calendar quarters — Jan·Feb·Mar, Apr·May·Jun, Jul·Aug·Sep, Oct·Nov·Dec |
| CY Return | Jan–Dec compounded |
| FY Return | **Apr of the row's year through Mar of the next** (Indian financial year) |

All are chain-linked products of the monthly returns available, not sums.

Monthly returns are derived from the backtest's **equity curve resampled to
month ends**, not from its per-rebalance period table. The period table runs
fill-to-fill (03 Aug → 31 Aug), which is right for attributing a rebalance and
wrong for a column headed AUG.

### Month-to-date

Never stored. Computed live from the close the current book was filled at, on
the book actually held this month, and struck under the **pinned** record
configuration — not the Backtest tab's sliders. Measuring the running month on a
different strategy from the frozen months beside it would make the year-to-date
column silently mix two series.

MTD appears in its month's cell and compounds into the quarter and CY figures —
a year-to-date that ignored the running month would be wrong the other way — and
is labelled as unfrozen wherever it is shown.

---

## 5. Configuration

Pinned in `TRACK_RECORD_CONFIG` (`src/engine/track_record.py`), mirroring the
Backtest tab's defaults:

```
top_n 20 · monthly rebalance · 50 EMA · 80% of 52W high
equal weight · 30 bps cost · 2× persistence buffer (top 40)
weights 10/30/30/20/10 · benchmark ^CRSLDX
```

It is pinned rather than read from the UI because a track record must come from
one fixed setup or its months are not comparable. **Changing anything in this
dict changes the fingerprint**, which marks every month written afterwards as a
new regime and leaves earlier months untouched. The Track Record tab warns when
the record spans more than one fingerprint.

---

## 6. Operations

Automatic: `.github/workflows/monthly_track_record.yml` runs at 19:00 UTC on the
**2nd–5th** of each month. Four days rather than one because the 1st can fall on
a weekend, a holiday, or a missed sync; re-running is free precisely because the
ledger only appends. It commits the ledger back to the repo — the same
persistence path the daily data sync uses, and the only durable one, since
Streamlit Cloud's filesystem is ephemeral.

Manual:

```bash
python scripts/update_track_record.py --dry-run   # report, write nothing
python scripts/update_track_record.py             # freeze closed months
python scripts/update_track_record.py --force     # rewrite history (destroys the guarantee)
```

**Note on running locally:** the script needs ~750 symbols of price history from
Yahoo. Rate-limited environments fail every request while appearing to make
progress (yfinance reports network failures as `possibly delisted`). If a local
run shows a high failure rate, use the workflow instead — trigger it manually
from the Actions tab.

---

## 7. Known limitation — survivorship

Backfilled months use today's constituent list, because no point-in-time
membership exists for them. Git carries constituent snapshots only from
**19 Aug 2026** (when the daily sync began committing them), so Jan–Jul 2026
were necessarily scored against September membership.

Direction is known — index additions skew toward recent strong performers, and a
momentum screen preferentially buys exactly those, so the bias flatters.
Magnitude is **not** known and should not be asserted.

Going forward the daily sync accumulates real point-in-time membership, so
future backtests could reconstruct the universe as it actually stood. Until then
the recorded series — growing one month at a time from September 2026 — is the
only survivorship-free evidence here.

See `docs/V1_AUDIT_TRACKER.md` §5 for the standing decision to defer
survivorship work.
