# Momentum health (S91)

How momentum itself has been paying, from this site's own ranking. Owner, 7 Nov 2026:
"build it". The method was written and checked against an independent series before
it went on the Dashboard, as S91 required.

## Method

- **Universe:** the Nifty 500's point-in-time members each month-end
  (`src/engine/index_universe.py`, from Jan 2010). Earlier months are left out: before
  the membership history begins, the only list is everyone who was *ever* a member,
  which knows the future.
- **Prices:** NSE's long adjusted closes (`src/loaders/nse_long.py`), the History
  backtest's prices.
- **Ranking:** the site's composite score at each month-end, scored among that day's
  members (`rank_history.snapshots`, the backtester's `_composite_z_score` with the live
  lookback weights). No filters: every scored member counts.
- **Spread:** the next month's equal-weighted return of the top fifth minus the bottom
  fifth, in points. A month still in progress is not counted.
- **Reading:** the sum of the last 12 spreads; its percentile among every past 12-month
  sum; a crash flag when the latest month's spread is negative and in the worst 10% of all months.

Code: `src/engine/momentum_health.py`; data: `data/momentum_health.csv`, rebuilt monthly
by `scripts/build_momentum_health.py` (`.github/workflows/momentum_health.yml`), which
refuses to write when there are fewer than 24 months, the newest month is more than two
months old, or a month has fewer than 100 stocks scored.

## Independent check

IIM Ahmedabad's Indian Fama-French-Momentum data library publishes a monthly WML
(winners minus losers) factor, survivorship-bias adjusted:
https://faculty.iima.ac.in/iffm/Indian-Fama-French-Momentum/ (file
`2025-12_FourFactors_and_Market_Returns_Monthly_SurvivorshipBiasAdjusted.csv`, read 7 Nov 2026).

| | Value |
|---|---|
| Months compared | 191 (Feb 2010 - Dec 2025) |
| Correlation, monthly | 0.829 |
| Correlation, 12-month sums | 0.837 |
| Same sign | 81% of months |
| Worst IIMA months, ours alongside (2008-2025 run, before the 2010 cut) | May 2009 -25.0 / -28.4; Dec 2008 -20.3 / -17.0; Jan 2012 -18.0 / -20.1; Apr 2020 -13.5 / -13.2 |

They are not the same series and are not expected to match: IIMA sorts on the
classic 12-1 month return over a wider universe with value weights; ours sorts on the
site's own five-horizon score over the Nifty 500, equal weighted. The check is that
they move together, which they do.

## Not checked

- Months after Dec 2025 (IIMA's file ends there).
- The Total Market (750) universe: its membership history begins Nov 2021, too short
  for a percentile; the Nifty 500 is used for depth.
