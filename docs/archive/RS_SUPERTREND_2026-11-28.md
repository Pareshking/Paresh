# Relative strength and its Supertrend as a gate on the momentum book (28 Nov 2026)

Owner's question: does relative strength (RS) of a stock against the index, or the Supertrend of that RS line, improve
entry or exit, so that a high-ranked but weak stock is not bought? Read-only research; no live rule changed.
Script: `scripts/research/rs_supertrend.py` (engine hook `run_backtest(extra_gate=, extra_gate_mode=)`, default off).

## Set-up (fixed before any result was read)

- Baseline: the record's rules, Nifty 500 as it stood, Jan 2010 - Nov 2026, monthly reset, 30 bps. **18.81% a year**
  (2010-17 22.99%, 2018-26 15.15%, worst fall -38.7%); the 18.8% (monthly reset) that `docs/BACKTEST_REQUIREMENTS.md` A15 quotes.
- RS = adjusted close / Nifty 500 close. Supertrend on RS uses a **close-only** range (|change in RS|): the long file
  has no highs or lows, so this is not the OHLC Supertrend a charting site draws. Not checked: that version.
- Gate read at the month-end signal close only (the engine rebalances monthly; an intramonth Supertrend flip exit is
  not testable here). `entry`: only bullish names can be bought; `exit`: a held name that turns bearish is sold;
  `both`.
- Pass rule: +0.5 pts a year in the run AND in both halves, worst fall no deeper, and neighbouring settings too.
- Tried: 5 Supertrend settings x 3 modes, 2 plain RS tests x 3 modes = 21 cells, then the controls below.

## Results (a year, pts against the baseline: run / 2010-17 / 2018-26)

| Gate (mode) | Run | 2010-17 | 2018-26 | Worst fall |
|---|---|---|---|---|
| Supertrend 10,3 entry | +1.85 | +3.67 | **+0.33** | -36.4% |
| Supertrend 10,3 exit | +0.65 | -1.77 | +2.72 | -35.2% |
| Supertrend 10,3 both | +0.80 | -0.15 | +1.58 | -38.3% |
| Supertrend 14,3 / 20,3 entry | +1.73 / +1.39 | +4.81 / +3.87 | **-0.82 / -0.67** | -36.3% / -35.5% |
| Supertrend 7,2 / 10,2 (all modes) | -0.80 to +0.39 | | | |
| RS above its 50D EMA, entry / exit | +0.37 / +0.89 | +0.33 / +0.30 | +0.39 / +1.39 | |
| **RS above its 50D EMA, both** | **+1.30** | +1.01 | +1.55 | -37.0% |
| Stock beat the index over 6 months | -0.01 to +0.25 | | | |

- **No Supertrend cell passes**: every one that gains in the run gains in 2010-17 and is flat or negative in 2018-26.
- One cell passes (RS above its 50D EMA, entry and exit), but it is a knife-edge: the same gate on a 30, 40, 70, 100,
  150, 200-day EMA gives +0.02, +0.11, +0.43, -0.02, -0.04, 0.00 pts; the 20-day gives -1.1.
- **The gate barely binds**: on the baseline's own picks the RS-above-50D-EMA gate fails 0.6% of new buys and 5.1% of
  kept names; the 6-month test fails 0.2% / 0.1%. The Supertrend (10,3) is the only one that binds (18.4% / 34.8%),
  and it did not pass. The book's own filters (above the 50D EMA, within 20% of the 52-week high) already select
  names that are outrunning the index.
- **Noise floor**: a gate that fails a *random* 5% of month-end candidates, 40 seeds, moves a year by +0.44 pts on
  average (std 0.82); 10 of 40 seeds meet the pass rule and 5 of 40 reach +1.3 pts. A random 1% gate: std 0.38,
  1 of 40 meets the pass rule. So +1.3 pts from 0.6% / 5% of decisions, found as the best of 21 cells, is inside
  what chance gives.

## What this does and does not show

- RS divides each stock by one index value per date, so it cannot change the cross-sectional rank on a plain return
  score; it can only act as an absolute-trend gate on the stock's own line. (Shown for return scores by algebra,
  not tested for the Sharpe score.)
- Not tested: intramonth (daily) exits on a Supertrend flip; an OHLC Supertrend; weekly Supertrend; sector or
  Nifty Total Market as the reference line; Nifty 750 / smaller-cap universes; tax; the six-monthly reset default.
- The Supertrend-entry cells (+1.4 to +1.9 pts, 2010-17 only) are the ones that would look good on a chart; their
  second-half result is why they are not a candidate.
