# Momentum health (S91)

How momentum itself has been paying, from this site's own ranking. Owner, 7 Nov 2026:
"build it". The method was written and checked against an independent series before
it went on the Dashboard, as S91 required.

## Long-only headline (owner, 8 Nov 2026: "Lead with winners vs index")

The book never shorts, so the Dashboard now leads with what a long-only momentum book
earns: hold the top 100 of the ranking (one fifth of the Nifty 500), equal weight, for the
next month, and compare its 12-month return with the Nifty 500's
(`momentum_health.long_only`). It is split into **momentum** (top 100 less the
equal-weighted average member, the `ew` column) and **breadth** (the average member less
the index; it carries the small-stock effect, since the index is cap-weighted).
The top fifth is also shown split in two: the top 50 and ranks 51-100 (owner, 8 Nov
2026, "give bifurcation of top two deciles also"). Over 201 months the top decile led
the Nifty 500 by 1.01 pts a month against 0.59 for the second, and that order held in
every five-year block (2010-14 2.33 / 1.83, 2015-19 1.14 / 0.96, 2020-24 3.11 / 2.49):
blending the two halves halves the signal, which is why the split is on the card.
Winners minus losers stays as a reference row and keeps the IIMA check below.

The headline stays the top 100, not the top 50 or a 20-stock basket, although a
20-stock basket tracks our own book best (correlation 0.93 against 0.85, same sign 92%
of months). That correlation is close to circular - a 20-name momentum basket nearly IS
the book - so it would turn the card into a second copy of the Track Record. It is also
noisier (a full year behind the index 25% of the time against 19%) and today it would
print +29.7 rather than +11.9, which flatters us by 18 points. The broad basket is the
independent reading. Research: `scripts/research/decile_split.py`, run on a GitHub
runner (`decile_research.yml`).

Each leg is compounded over the 12 months and the legs are then subtracted, so the
headline is the gap between two 12-month returns a reader can check against the index
(owner, 8 Nov 2026). The card said a sum of the 12 monthly gaps until then; the two drift
apart when months are large (to Oct 2026: 12.9 summed, 12.2 compounded, and the percentile
56th rather than 65th). Subtraction keeps the split exact, since
(top - ew) + (ew - index) = top - index. The IIMA check below still uses 12-month sums, as
the comparison was built that way.

Why (`scripts/research/long_only_momentum_health.py`, 201 months, Feb 2010 to Oct 2026):

| Trailing 12 months against our book's 12-month lead over the Nifty 500 | Correlation | Same sign |
|---|---|---|
| Top 100 less the Nifty 500 | +0.81 | 86% |
| Top 100 less the average member | +0.43 | 80% |
| Winners minus losers | +0.44 | 79% |

The long leg (top 100 less the average member) earned 62% of winners minus losers over
the whole period (51% in 2010-14, 61% in 2015-19, 76% in 2020-24), close to Israel and
Moskowitz (JFE 108(2), 2013), who find about half of momentum profits on the long side in
US data. In the 12 months to Oct 2026 winners minus losers was +8.9 points but the long leg
+11.3: the short leg cost -2.4, a loss a long-only book never takes.

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
