# The three months that differ between Portfolio and Backtest

_Written 11 Nov 2026. Read-only investigation: no data file, price or ledger was
changed. Answers TODO 12 / S60 (Jan and Feb 2026 "cause not traced stock by
stock") and records why `ledger_parity` calls exactly three months "accepted"._

On the 2026 run the strategy's January, February and October differ between the
two pages; every other month, and the Nifty 500 row in all ten months, agrees to
five decimals.

| Month | Portfolio (frozen ledger) | Backtest (today's replay) | Difference |
|---|---|---|---|
| 2026-01 | −0.2123% | +0.0047% | +0.2170 pp |
| 2026-02 | +0.6951% | +0.8013% | +0.1062 pp |
| 2026-10 | −4.2507% | −4.0215% | +0.2292 pp |
| the other seven | identical to six decimals | | ≤ 0.000027 pp |

Figures from `scripts/canonical_parity_check.py` on the published release assets,
11 Nov 2026 (ranking artifact `2026-11-09_1968x752_94d2c6cb8d26`, ledger
2026-01…2026-10):

```
PASS  ledger_parity: {"counts": {"match": 7, "accepted": 3, "drift": 0},
                      "max_drift_pp": 2.7456721171659204e-05,
                      "accepted": ["2026-01", "2026-02", "2026-10"]}
```

The benchmark drifts in the same run are −2.5e-07, −2.6e-07 and +7.1e-08 (as
fractions) — that is why the index row looks identical on both pages.

---

## 1. Why the two pages can differ at all

They are not two computations of the same thing.

- **Portfolio / Track Record** print `data/track_record.json`: the value frozen
  when the month closed, on the data of that day. `docs/TRACK_RECORD.md` §2:
  "A closed month is written once and frozen … **The stored value always wins.**"
- **Backtest**, with its default controls and no History index chosen, runs
  `run_backtest` on `nse_prices.basis_frame(...)` — the same frame and engine the
  record replay uses (`src/ui/views/backtest_view.py:390` and
  `src/engine/model_record.py` `record_run_uncached`) — and renders its calendar
  grid from `ledger_from_curves(eq, bm)` (`backtest_view.py:665`). Its months are
  **today's** replay of the same rules on **today's** prices.

So a difference is never a disagreement about arithmetic; it is the distance
between the data vintage a month was struck on and today's. For these three
months it is **categorical** — a different holding — not rounding: see §3 and §4.

## 2. What "accepted" means in `ledger_parity`

`scripts/canonical_parity_check.py:219-225` passes the file
`src/engine/parity_accepted_drift.json` into the comparison:

```python
accepted = load_accepted_drift()
rep = compare_monthly_ledger(ledger, res["equity_curve"], res["benchmark"], accepted=accepted)
record("ledger_parity", bool(rep["passed"]), counts=rep["counts"],
       max_drift_pp=max((abs(r.get("strategy_drift") or 0) for r in rep["rows"]
                         if r["status"] != "accepted"), default=0) * 100,
       accepted=[r["month"] for r in rep["rows"] if r["status"] == "accepted"])
```

and the condition itself is `src/engine/parity_audit.py:41-47`:

```python
def _is_accepted(entry, stored, current, tolerance) -> bool:
    """Accepted only for the exact stored value and a replay still at the
    accepted one: a different stored value or a further move fails again."""
    if not isinstance(entry, dict) or "stored" not in entry or "replay" not in entry:
        return False
    return (abs(float(entry["stored"]) - stored) <= 1e-9
            and abs(float(entry["replay"]) - current) <= tolerance)
```

A month therefore reads **accepted** when, and only when, all of this holds:

1. the frozen value is **exactly** the one written in
   `parity_accepted_drift.json` (1e-9);
2. today's replay is within 0.05 pp (`DEFAULT_TOLERANCE = 5e-4`) of the replay
   recorded there;
3. the owner wrote a `reason` and a `decided` date beside it.

Its status is set at `parity_audit.py:112` only after `drifts` is empty, so an
accepted month that moves **again** by more than 0.05 pp, or whose stored value
is ever rewritten, goes back to `drift` and the gate fails. Note also that
`max_drift_pp` is computed over the **non-accepted** rows only — the "0.000027 pp"
in the output describes the seven matching months, not these three.

**What a reader should conclude from "accepted":** *"this month no longer
reproduces, a human has looked at why, and the owner decided to keep the frozen
number rather than rebuild it."* It is not "within tolerance" and not "checked
and equal". The seven `match` months are the ones where the replay still
reproduces the record. Three accepted months in a ten-month ledger means 30% of
the record cannot be reproduced from today's data.

## 3. January and February: one holding in the first book

Both months are explained by a single name, and the same one.

**The replay on NSE's closes as published reproduces both frozen months.** Same
code, same membership, same config; the only change is `screener=None`, so the
Screener leg of the blend is not applied (`nse_prices.basis_frame`):

| Month | Frozen | Replay, Screener-primary | Replay, NSE as published |
|---|---|---|---|
| 2026-01 | −0.002123 | +0.000047 | **−0.002122** |
| 2026-02 | +0.006951 | +0.008013 | **+0.006951** |
| 2026-03 | −0.098934 | −0.098934 | −0.098936 |
| 2026-10 | −0.042507 | −0.040215 | −0.040215 |

(ten-month table in full in the run log; every other month agrees on both bases
to six decimals.)

**The difference is exactly one holding in the first book.** Replaying the record
on each basis and diffing the tradebooks:

```
books differing between the bases:
  2026-01-01: screener-only ['TITAN']  nse-only ['ANURAS']
```

No other rebalance in 2026 differs. The slot is the **twentieth**, awarded after
the hard 40% industry cap has skipped the over-full industries: under the
Screener-primary frame the backtester fills it with its rank #25 (TITAN,
Consumer Durables), under NSE's published closes with its rank #24 (ANURAS,
Chemicals). The two frames also reorder ranks #15/#19 (MARUTI, BELRISE) without
changing the book.

The arithmetic closes, from the record's own frame:

| | 1 Jan close | last Jan session | January | 30 Jan → 1 Feb |
|---|---|---|---|---|
| TITAN | 4,049.30 | 3,977.40 | −1.7756% | +0.1986% |
| ANURAS | 1,326.50 | 1,245.30 | −6.1214% | −1.7506% |

- **January:** (−1.7756 − (−6.1214)) × 5% of the book = **+0.2173 pp**, against
  the observed +0.2170 pp.
- **February:** the February book is identical on both bases; the fill is on
  1 Feb, so the first day of February is still carried on January's book.
  (0.1986 − (−1.7506)) × 5% = **+0.0975 pp**, against the observed +0.1062 pp,
  the small remainder being the sale proceeds and the 30 bps charged on the
  different exit. ANURAS is sold at the February signal ("Trend Breakdown
  (< 50 EMA)", exit price 1,223.50), TITAN at the same signal in the other run.

**Why the two bases pick different names.** Not one stock's price: the frames
differ broadly inside the 12-month formation window — **310 of 1,096 columns,
27,185 cells**, and for about 150 names the coverage differs by up to 302
sessions, so the cross-sectional z-scores of the momentum score are struck over a
slightly different pool. Swapping single columns from one frame into the other
(CCAVENUE, KMEW, TRIVENI, VEDL, HEGAM, GENUSPOWER, TITAN, INDIAGLYCO, INOXGREEN,
HINDUNILVR, HCC, IRB — the twelve largest differences in the Dec 2025 – Mar 2026
window) left January at +0.000047 in every case; only VEDL moved it at all, by
1e-6. The flip is the aggregate, not a single bad close.

**The recorded cause (S56 / #435, "the rights-issue adjustment") is refuted for
today's drift.** Dropping **every** rights row from
`data/nse_prices/actions.parquet` in memory (44 of 297 rows) and replaying gives
January +0.000047 and February +0.008013 — unchanged to six decimals. The rights
rows do change the record's frame, but only between **30 Sep 2024 and 25 Sep
2025** (797 cells, 15 symbols), the stretch where NSE's closes fill Screener's
weekly history; from 26 Sep 2025 Screener's own daily closes are primary and the
rights rows reach nothing. #435 may still be what moved the replay in October
2026 — the reconciliation of 2 Oct recorded "Live replay vs rebuilt ledger: 9/9,
max drift 0.00003 pp", and the gate went red after #435 merged on 13 Oct — but it
is not what holds the two numbers apart now.

**What is therefore left as the cause.** The frozen Jan and Feb were struck on
1 Oct 2026 with `price_basis: "screener_primary"` (ledger `price_basis`, and the
fourth rebuild entry's `"prices": "screener_primary"`), and on that day that
basis produced the ANURAS book — which is what NSE's published closes still
produce. Today's Screener store does not. The Screener store is republished whole
every night and **is not archived**, so the store of 1 Oct cannot be re-read and
the restated column cannot be named. S89 is the proof that the store does get
restated: between the 26 Oct and 5 Nov Screener nights it carried BSE closes for
about 43 stocks. **Not checked / not checkable here:** which Screener column
changed between 1 Oct and today, because that store is gone.

## 4. October: a store that no longer exists

October needs no basis argument: **both** bases give −4.0215% today (table in
§3). The frozen −4.2507% came from the data of 2 Nov 2026 (`data_as_of`), when
the published Screener store carried BSE closes for about 43 stocks (S89,
`parity_accepted_drift.json` 2026-10). On BSE's 31 Aug closes SKYGOLD (806.50)
beat AETHER in a near-tie that NSE's own bhavcopy prices the other way (SKYGOLD
807.10, AETHER 1,691.30), so the September book held SKYGOLD and October's return
is that book's.

Today's replay shows the NSE outcome: AETHER bought at the 31 Aug signal
("New Momentum Leader (Rank #17)", 1,683.70 on 1 Sep) and SKYGOLD not bought
until the 30 Sep signal (810.65 on 1 Oct). S89 also records that swapping BSE's
closes for SKYGOLD, DIACABS and GRWRHITECH into the store reproduces −0.042507
exactly. So October's two figures describe two different books, and the book the
account actually held was the NSE one — the live model filled the NSE book
(S89).

## 5. Which number to believe

| Month | Believe | Why |
|---|---|---|
| 2026-01 | **the Backtest's +0.0% is the better estimate of what the rules would do on today's prices; the ledger's −0.2% is the record** | Neither is wrong arithmetic. The frozen −0.2123% is what the rules gave on the data of 1 Oct 2026, and it is the record: Portfolio must keep printing it. But today only the NSE-as-published basis reproduces it, and the record's own basis does not, so it cannot be re-derived from the live data. |
| 2026-02 | same as January | Same single holding carried into the first day of February. |
| 2026-10 | **−4.0% (the Backtest's) is the truer figure**; −4.25% stays the record | The frozen month describes a book built on BSE closes served inside the Screener store; the live model filled the NSE book. The owner decided on 7 Nov 2026 to keep −4.25% and accept the drift (S89), so the record stands, but a reader asking "what did the account do in October" should read −4.0%. |

For the since-inception figure: the ten frozen months compound to **+38.2574%**
(Jan–Sep alone is the published +44.40%, October takes it back); the same ten
months on today's replay compound to **+39.0362%**, **0.78 pp** apart. Portfolio
and Track Record must stay on the ledger, as the contract requires, or the
monthly and cumulative columns would mix two series.

Neither page needs a fix. What is missing is the label: the Backtest page's
calendar grid for 2026 is **a replay, not the record**, and nothing on it says so.
(TODO S122.)

## 6. Can it happen again? — November, December and after

**Yes, and the condition is precise:** a month drifts when, between its freeze and
the replay, an input changes enough to move either a close inside the month or a
momentum score at the signal date past a marginal, cap-constrained selection
boundary. The inputs that can change are:

1. **the Screener store** (`SCREENER_STORE_URL`, the record's primary basis,
   republished nightly, not archived) — the live cause of all three months here;
2. NSE's committed closes (`data/nse_prices`) and their actions;
3. point-in-time membership, rebuilt from NSE notices (one notice's effective
   date was misparsed as recently as 7 Nov 2026, `DATA_CORRECTNESS.md` §5);
4. `data/former_member_prices.parquet` for names the index has since dropped.

Rounding is not among them: the seven matching months agree to 0.000027 pp, so a
drift always means a changed input, and usually a changed holding.

**What is in place for November and December.** The S92 guards make a *wrong*
freeze much less likely, and both are the right mechanisms:

- `scripts/update_track_record.py` refuses to freeze while `ledger_parity` is red
  on an unaccepted month (`parity_audit.freeze_refusal`) — had it existed on
  3 Nov, October would not have been struck;
- `scripts/check_screener_outvotes.py` holds the Screener publish when the
  three-source vote outvotes Screener on more than `SCREENER_OUTVOTE_LIMIT` = 10
  names in one night — the 28 Oct – 5 Nov window ran at 39–53.

Those stop the *bad-store* case (October's). They do **not** stop the *quiet
restatement* case (January's and February's): a store republished a fortnight
after the freeze with a handful of changed closes passes the outvote check and
still moves a marginal slot. So November and December will be frozen correctly if
the guards hold, and may still drift later. The honest promise to the owner is
therefore:

- November and December will be **frozen on the book the model actually held**,
  provided the two S92 guards stay in the workflows and their runs are read
  (`monthly_track_record.yml` fails the job on a refusal; the Screener night logs
  `Screener outvoted on N stock(s) (limit 10)`);
- they will **appear identically on both pages only for as long as the Screener
  store that struck them is still the store the replay reads.** Nothing today
  guarantees that, and nothing can prove it after the fact, because the store is
  not archived. The one change that would make every future month permanently
  reproducible is to **archive the store (or the record's frame) with each
  freeze** — not built; proposed as TODO S122.

**The 2010 History run is a separate question and will never match.** The History
mode replaces the frame and the universe: prices come from the long file
(`src/loaders/nse_long.py`, NSE's closes adjusted for splits, bonuses,
demergers, rights **and dividends of 10% or more**) and membership from the
chosen index's own timeline (`_history_inputs`, `backtest_view.py:121-166`),
while the record runs on Screener-primary closes with no dividend adjustment over
the Nifty Total Market 750. Its default index is the Nifty 500, which on 2026
gives +17.2% against the record's +44.4% for stock-coverage reasons alone
(`DATA_CORRECTNESS.md` §5, TODO S51). Choosing Nifty Total Market brings the
universe into line; the price basis still differs, so **November and December on
the 2010 run will be close to, but not equal to, the record's months, and that is
correct behaviour, not a fault.** The page should say which basis it is on (it
does: "Prices: NSE closes, adjusted for …"), and a reader comparing the two
should compare the 2026 live run, not the History run, with the ledger.

## 7. What was not checked

- Which Screener column changed between 1 Oct 2026 and today: the store of
  1 Oct is not kept, and no archive of it exists in this container.
- Whether #435 (rights) was the trigger in October 2026: only that it is not the
  cause today. Re-running the code of 13 Oct on the data of 13 Oct was not done.
- Nano Cap's accepted October (−5.72% stored, −6.10% replay, S93) — same shape,
  not traced here.
- Anything on the rendered pages: these are engine figures
  (`record_run_uncached`, `canonical_parity_check.py`), not screenshots.
- `_clean_price_df`'s narrowing warning did not fire in any replay here: the
  record's frame carried 1,096 columns against a 752-name universe, so the
  intersection lost nothing.

## 8. How to reproduce

```bash
python scripts/canonical_parity_check.py --report parity_report.json   # 7 match, 3 accepted
```

The basis comparison is the same replay with the Screener leg switched off:
`nse_prices.basis_frame(..., screener=None)` into
`model_record.record_run_uncached`, then `track_record.calendar_month_returns`
on `result["equity_curve"]`; the book difference is the two runs' `tradebook`
rows for `Period Start == 2026-01-01`. Nothing in `data/` is written by either.
