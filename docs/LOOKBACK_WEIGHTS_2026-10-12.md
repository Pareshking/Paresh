# Lookback weights: is there a better mix? (12 Oct 2026)

**Answer: no mix tested is reliably better than the live weights (10 / 30 / 30 / 20 / 10
on 1, 3, 6, 9 and 12 months). Keep them.** The one finding that holds everywhere is
negative: putting half or more of the score on the 1-month window is worse. The live
weights already give it 10%.

Owner's question, 12 Oct: which lookbacks, or which combination of them, are best, and
what method finds that? Run on the laptop with `scripts/research_lookback_sweep.py`
(Streamlit Cloud cannot carry 72 sixteen-year backtests).

## What was run

- **Backtest:** the Backtest page's History tab, Nifty 500 point in time, Jan 2010 to
  Sep 2026 (201 months, 4,154 sessions), NSE closes from the long file built 10 Oct
  2026. Every setting at the live system's: 20 holdings, monthly rebalance, keep while
  in the top 40, equal weight, 5% stock cap, 40% industry cap, 30 bps, close above the
  50-day EMA, within 20% of the 52-week high, Sharpe score.
- **Check that it is the page's backtest:** the script's live-weights run gives
  +1814.2%, 19.6% a year, Sharpe 0.68, worst fall -38.7%, Calmar 0.51, 59% of months
  ahead, turnover 40%: the History tab's figures with the same settings, to the digit.
- **Grid:** every way to give four quarters to five windows (70 mixes, from 1M alone to
  12M alone), plus the live weights and equal weights. 72 backtests, 12-21 s each,
  5.5 minutes on 4 workers.
- **Environment:** pandas 3.0.6, numpy 2.4.6, as pinned in `requirements.txt`.

## Why the top row is not the answer

Trying 72 mixes and keeping the best is a search, and the best of any search looks good
partly by luck. Over 16 years a Sharpe ratio is only known to about ±0.25 (the page's
standard error), wider than most gaps between mixes. So each test below asks how far the
search itself can be trusted.

| Test | What it asks | Result |
|---|---|---|
| Paired bootstrap (63-session blocks, 2,000 draws) | Is a mix's Sharpe above the live weights' on the same days? | 3 of 71 mixes have a 90% range above zero, all chosen by this same data |
| Probability of backtest overfitting (16 blocks, all 12,870 half splits) | How often does the in-sample winner finish in the bottom half out of sample? | **49%**: a coin toss |
| Rank persistence (2010 to May 2018 against May 2018 to 2026) | Do the halves rank the mixes alike? | Spearman rho **0.17**; 2 of the first half's top 10 are in the second half's |
| Walk-forward (each year from 2014, hold the best mix on all earlier years) | Would re-tuning every year have beaten keeping the live weights? | Sharpe 0.77 against 0.71, **+0.06, 90% range -0.07 to +0.19**: not distinguishable |
| Deflated Sharpe ratio (N = 70) | Is the winner's Sharpe above zero after allowing for 70 trials? | 1.00. Momentum itself works; this test says nothing about one mix against another |
| Other indexes (seven candidates) | Does the Nifty 500 winner hold on other lists? | No (table below) |

## Nifty 500, 2010-2026

| Mix (1M / 3M / 6M / 9M / 12M) | Sharpe | vs live (90% range) | A year | Worst fall | Turnover |
|---|---|---|---|---|---|
| 0 / 25 / 50 / 25 / 0 | 0.84 | +0.16 (+0.09 to +0.24) | 23.3% | -35.8% | 37% |
| 0 / 25 / 25 / 50 / 0 | 0.80 | +0.11 (+0.02 to +0.19) | 22.2% | -37.0% | 36% |
| 0 / 0 / 75 / 25 / 0 | 0.78 | +0.10 (+0.00 to +0.20) | 21.8% | -39.3% | 36% |
| 0 / 0 / 100 / 0 / 0 | 0.78 | +0.09 (-0.01 to +0.21) | 21.8% | -38.8% | 39% |
| **10 / 30 / 30 / 20 / 10 (live)** | **0.68** | rank 38 of 72; grid median 0.69 | 19.6% | -38.7% | 40% |
| 20 / 20 / 20 / 20 / 20 | 0.66 | -0.02 (-0.10 to +0.06) | 19.1% | -40.2% | 43% |
| 75 / 0 / 0 / 25 / 0 | 0.51 | -0.18 (-0.35 to +0.01) | 15.1% | -44.9% | 79% |
| 100 / 0 / 0 / 0 / 0 | 0.38 | -0.31 (-0.49 to -0.08) | 12.4% | -47.0% | 86% |

Every row: `results.csv` in the run's output folder (rerun to regenerate; see below).

Average Sharpe of the grid's mixes by one window's weight (the other four share the rest):

| Weight on the window | 0% | 25% | 50% | 75% | 100% |
|---|---|---|---|---|---|
| 1M | 0.72 | 0.67 | 0.64 | 0.55 | 0.38 |
| 3M | 0.68 | 0.69 | 0.66 | 0.70 | 0.65 |
| 6M | 0.65 | 0.69 | 0.71 | 0.74 | 0.78 |
| 9M | 0.66 | 0.69 | 0.72 | 0.72 | 0.70 |
| 12M | 0.67 | 0.69 | 0.68 | 0.68 | 0.68 |

The 6M tilt and the "drop 1M entirely" gain are first-half effects:

| Period | Live | Mixes with 1M at 0% | Mixes with 1M at 50%+ | Share of 1M-at-0% mixes beating live |
|---|---|---|---|---|
| 2010-2015 | 0.94 | 1.05 | 0.90 | 83% |
| 2016-2020 | 0.42 | 0.42 | 0.15 | 51% |
| 2021-2026 | 0.69 | 0.70 | 0.70 | 63% |
| 2010 to May 2018 | 0.85 | 0.94 | 0.79 | 89% |
| May 2018 to 2026 | 0.55 | 0.53 | 0.44 | 46% |

## The same candidates on other indexes

Sharpe minus the live weights' Sharpe, same days, same settings. These lists overlap
with the Nifty 500 (the Nifty 100, Midcap 150 and Smallcap 250 are its parts), so this
is a robustness check rather than independent evidence. The Total Market list (the live
system's own) starts in Nov 2021, too short to separate anything: every 90% range there
spans about ±0.2.

| Mix | Nifty 500 (2010) | Nifty 100 (2010) | Midcap 150 (2016) | Smallcap 250 (2016) | Total Market (2021) |
|---|---|---|---|---|---|
| 0 / 25 / 50 / 25 / 0 (Nifty 500 winner) | +0.16 | -0.01 | +0.01 | -0.01 | -0.01 |
| 0 / 25 / 25 / 50 / 0 | +0.11 | +0.04 | +0.05 | +0.01 | +0.09 |
| 0 / 30 / 30 / 20 / 10 (live without 1M) | +0.04 | +0.01 | +0.02 | -0.03 | +0.10 |
| 0 / 0 / 100 / 0 / 0 (6M alone) | +0.09 | -0.03 | -0.11 | -0.12 | +0.01 |
| 20 / 20 / 20 / 20 / 20 | -0.02 | +0.03 | +0.04 | +0.03 | +0.09 |
| Live Sharpe | 0.68 | 0.27 | 0.70 | 0.83 | 0.53 |

Outside the Nifty 500 no candidate's 90% range is clear of zero. The Nifty 500 winner
is at zero on all four other lists. A single window (6M alone) is fragile: -0.11 and
-0.12 on the mid and small caps.

## Conclusion

1. **Keep the live weights.** They sit mid-grid on the Nifty 500 and within noise of
   every candidate on every list.
2. **Avoid a short-window-heavy score.** 1M at 50% or more is worse in every period but
   2021-2026 (tied), with turnover near 80% a rebalance. This is the one finding that holds.
3. **Blend several windows; do not pick one.** Single-window scores swing most between lists.
4. **Do not re-tune the weights on backtests.** The walk-forward shows yearly re-tuning
   would not have helped by a margin distinguishable from luck.
5. **If a change is wanted anyway**, the only way to get evidence the backtest cannot
   give is to name one candidate now (0 / 25 / 25 / 50 / 0 was the steadiest across the
   lists) and record it forward beside the live system for a year or more, then compare.

## Not tested

- The other settings (holdings, keep-rank, EMA, 52-week-high floor, rebalance interval,
  score method) were held at the live values. Interactions with the weights are untested.
- A finer grid than quarters.
- Costs other than 30 bps; dividends (the long file has none, as the index has none).
- 2010-2013 rebalances sometimes held cash: the caps and filters left up to 50% of the
  book unplaced in that stretch. Every mix shares it.
- Rolling the weights mid-path: the walk-forward chains each picked mix's own returns,
  so it ignores the extra trades a switch would cause. That flatters re-tuning, if anything.

## Rerun

```bash
python scripts/research_lookback_sweep.py run --out OUT --workers 4             # 72 backtests, ~6 min
python scripts/research_lookback_sweep.py report --out OUT                       # results.csv, summary.json
python scripts/research_lookback_sweep.py run --out OUT2 --index nifty_100 --mixes "0.1,0.3,0.3,0.2,0.1;0,0.25,0.25,0.5,0"
python scripts/research_lookback_sweep.py compare --out OUT OUT2
```

Use the pinned environment (`requirements.txt`): the engine depends on pandas 3 copy
semantics. Each run saves its daily net returns, so `report` and `compare` need no rerun.
The methods are the probability of backtest overfitting (Bailey, Borwein, López de Prado
and Zhu) and the deflated Sharpe ratio (Bailey and López de Prado).
