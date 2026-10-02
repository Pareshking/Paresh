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

## Portfolio performance relationship

The pinned replay (`record_run()`) is the source for the current model book and
live month-to-date return. Portfolio consumes that book and presents the same
account-level performance series: frozen monthly returns from this ledger,
plus the pinned replay's live MTD return until the month is frozen. The benchmark
uses the corresponding frozen/live benchmark series.

Portfolio equity must be the starting capital compounded by that same monthly
series. The displayed since-inception strategy and benchmark returns must
therefore reconcile to Track Record for the same system and as-of date. Internal
returns are decimal fractions; only the UI converts them to percentages.

Do not compare account-level return with the current holdings table's
unrealised P&L as if they were the same measure. Current-book unrealised P&L
excludes realised gains/losses on sold positions; total account performance
includes the full sequence of monthly portfolio returns and modeled costs.
Day P&L is a third measure, calculated from current positions between marks.

The current month may be **live MTD**, or **closed but awaiting freeze** after
the calendar month changes. It remains visible until the scheduled updater
freezes it. Existing frozen months remain immutable during normal runs; drift
is diagnostic and a history rebuild must be deliberate and recorded.

See [`track_record_portfolio_architecture.md`](track_record_portfolio_architecture.md)
for exact invariants and required cross-view reconciliation tests.

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

The Jan–Aug 2026 block was first backfilled on 2026-09-03 (only August recorded),
on today's index list and under the earlier accrual convention. **It was rebuilt on
2026-10-01** with `--force`, because two things had changed underneath it:

1. the pinned config gained `accrual: buy_and_hold` (fingerprint `5b356a6ba93b` ->
   `2aa2cb53f4d1`), so the old months and any new month would have been two series;
2. point-in-time membership now reaches back to 2025-12-31 (built from NSE's own
   notices, `docs/MEMBERSHIP_FROM_NOTICES.md`) and the stocks the index has since
   dropped have prices (`data/former_member_prices.parquet`), so every month is
   scored on the index as it stood (`universe: point_in_time`, 8 of 8 rebalances).

A forced rewrite is a reconstruction, so every rebuilt month is `backfill`,
August included. The ledger's `rebuilds` log keeps when, which months, the config
replaced and each month's previous value. Residual limits: four stocks that merged
away have no prices (`former_members.unavailable()`), and the prices are today's
vintage. Treat the block as a careful reconstruction, not as a record frozen as
each month closed.

Two further rebuilds on 2026-10-01 moved the price basis to NSE as published and
then to Screener-primary (`docs/NSE_PRICE_BASIS.md`). **The fourth, for the owner's
decision of 2026-10-02, made the 5% stock and 40% industry caps hard** (config
`4cc739e503d7`): previously the replay passed no sector map and no industry cap
bound at all. Jan–Sep moved by −1.77 to +1.96 pp; cumulative +46.57% → +44.40%.
Full record: `docs/CANONICAL_RECONCILIATION_2026-10-02.md`.

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
hard caps: 5% per stock · 40% per NSE industry (≤ 8 of 20 names), never relaxed
```

The caps are enforced at **selection** (`backtester._select_holdings` with
`sector_slots`): an over-full industry keeps its best-ranked names and the free slot
goes to the next-ranked name in an industry with room. The weight projection
(`portfolio.apply_caps`) never raises a cap; anything it cannot place is cash.
Between rebalances the book is held, so prices can carry an industry past 40% until
the next rebalance. Industry labels are the NSE index file's (TradingView mapped
only for former members) — today's labels, not point-in-time.

It is pinned rather than read from the UI because a track record must come from
one fixed setup or its months are not comparable. **Changing anything in this
dict changes the fingerprint**, which marks every month written afterwards as a
new regime and leaves earlier months untouched. The Track Record tab warns when
the record spans more than one fingerprint.

---

## 6. Operations

Automatic: `.github/workflows/monthly_track_record.yml` runs at 19:00 UTC on the
**1st–5th** of each month. Five days rather than one because the 1st can fall on
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

---

## 8. Three systems

Since 2026-09-27 the app runs three systems on the same pinned configuration
(`docs/THREE_SYSTEMS.md`). Each has its own ledger and inception:

| System | Ledger | First month |
|---|---|---|
| Nifty 750 | `data/track_record.json` | Jan 2026 (unchanged) |
| Nano Cap | `data/track_record_nano.json` | Oct 2026 |
| Combined | `data/track_record_combined.json` | Oct 2026 |

`src/engine/systems.py` names the ledger, the inception and the point-in-time
membership for each; `load_ledger(path, inception)` and `finalize_months` start
from the ledger's own inception.

### Pre-inception ledger behavior

Nano Cap and Combined ledger files are intentionally absent before their
October 2026 inception. Their first live book is signalled at the 30-Sep-2026
close and filled on 1-Oct-2026. Therefore a missing Nano/Combined ledger on
30 September is not evidence of a failed publication.

As of PR #263 (merge commit `3529e834352156fafbd8f8f8b359ac8fb13219fc`),
`load_ledger(path, inception)` distinguishes the two cases:

- **before inception:** return an empty ledger anchored to its declared
  inception and log informationally;
- **at/after inception:** log a warning because the ledger should now exist;
- **corrupt existing ledger:** raise/report the error and never silently reset
  it.

This distinction is deliberate: "not started yet" and "missing after start"
are different operational states.

Nano Cap and Combined have no backfilled months at all: their first book is
signalled at the 30 Sep 2026 close.

### Parity gate

`.github/workflows/canonical_parity.yml` runs `scripts/canonical_parity_check.py` on
every push/PR to `main` and after each daily sync and monthly freeze. It fails when
any frozen month stops reproducing, when the ledger was struck under a config other
than today's, when a rebalance breaches the hard caps, when Portfolio and Actions
would show different books, when Actions' planner disagrees with the executed
rebalance, or when the research defaults stop reproducing the account. A failure
after a scheduled sync opens an issue. A failing `ledger_parity` after a vendor
restatement is expected: the stored value stands until the owner decides to rebuild.
