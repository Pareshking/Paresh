# Settings by market condition (12 Oct 2026)

**Answer: picking settings by market condition does not beat one fixed setting.
One fixed setting does beat the live one, and holds on all five indexes tested:
the live lookback weights with 30 holdings, keep while in the top 90 (3×) and a
200-day EMA.** The Backtest page names it as its Recommendation (#432). Its
defaults, the track record and the model book are unchanged (owner, 12 Oct).

Owner's question, 12 Oct: which settings work best in which market conditions?
Run on the laptop with `scripts/research_regime_sweep.py`. This follows the
lookback-weights study (`docs/LOOKBACK_WEIGHTS_2026-10-12.md`), which held every
setting but the weights at the live values.

## What was run

- **Backtest:** the Backtest page's History tab: Nifty 500 point in time, Jan 2010
  to Sep 2026 (201 months, 4,154 sessions), NSE closes from the long file built
  10 Oct 2026. Monthly rebalance, equal weight, 40% industry cap and 30 bps cost
  throughout.
- **Grid:** 1,728 combinations of six settings:

  | Setting | Values (live in bold) |
  |---|---|
  | Lookback weights (1M / 3M / 6M / 9M / 12M) | **live 10/30/30/20/10**, short 30/40/20/10/0, mid 0/25/50/25/0, long 0/0/30/30/40, equal 20 each, 12M alone |
  | Holdings | 10, **20**, 30 |
  | Keep while ranked within | 1×, **2×**, 3× the holdings |
  | Close above its EMA of | 20, **50**, 100, 200 sessions |
  | Within this % of the 52W high | 10%, **20%**, 30%, 50% |
  | Score | **Sharpe**, plain return |

  The stock cap is the live 5%, raised to 1/holdings where 5% cannot fill the book
  (10 holdings: 10%). About 2¼ hours on 4 workers.
- **Check that it is the page's backtest:** the live combination gives +1814.2%,
  Sharpe 0.68, max drawdown −38.7%: the History tab's figures and the lookback
  study's, to the digit.
- **Market conditions,** read for each month at its signal (the last close before
  the month), from what was known then:

  | Condition | Rule | Months |
  |---|---|---|
  | Trend | Nifty 500 above its 200-day average (the header's regime): up / down | 143 / 58 |
  | Volatility | 63-session volatility at or below its median over the five years before: calm / stormy | 132 / 69 |
  | Breadth | share of the index's stocks above their 50-day EMA at least half: broad / narrow | 109 / 92 |
  | Trend × volatility | the four pairs: up-calm, up-stormy, down-calm, down-stormy | 105 / 38 / 27 / 31 |

- **Environment:** pandas 3.0.6 and numpy 2.4.6 (`.venv`, as pinned). The report
  and the five-index check, rerun under the laptop's system pandas 2.3.3, came out
  identical.

## How far the per-condition rankings can be trusted

Over the whole history the live settings rank 808 of 1,728. The best combination
(long weights, 30 holdings, 3×, 200D EMA, within 20%) has Sharpe 0.98. The
probability of backtest overfitting is **37%**: the in-sample winner lands in the
bottom half out of sample about a third of the time.

Within a condition the history is shorter, and the rankings do not repeat. The
first and second halves of each condition's months rank the 1,728 combinations
(Spearman rho):

| Condition | Live Sharpe (rank) | Grid median | Halves agree (rho) | Top combination |
|---|---|---|---|---|
| Uptrend | 0.86 (718) | 0.83 | +0.31 | 12M or long, 30 holdings, 3×, 100–200D EMA, within 10–20%: 1.18 |
| Downtrend | 0.27 (970) | 0.28 | +0.13 | long, 10 holdings, 3×, 200D EMA, within 20%: 0.88 |
| Calm | 0.59 (697) | 0.56 | **−0.11** | long, 20 holdings, 3×, 200D EMA, within 50%: 0.89 |
| Stormy | 0.84 (1148) | 0.90 | **−0.18** | long, 30 holdings, 3×, 200D EMA, within 20%: 1.22 |
| Broad breadth | 1.29 (832) | 1.28 | +0.45 | long, 30 holdings, 3×, 200D EMA, within 20%: 1.80 |
| Narrow breadth | 0.01 (888) | 0.02 | +0.10 | mid, 30 holdings, 3×, 200D EMA, within 30%: 0.33 |

Only broad breadth (0.45) and the uptrend (0.31) keep any order between halves.
Calm and stormy reverse it. A table of "the best setting for each condition" is
mostly the luck of each condition's months.

## Which way each setting leans

The average Sharpe of every combination with a given value, by condition. This
averages over the other five settings, so it is steadier than any top-10 list.

| Setting | Value | Up | Down | Calm | Stormy | Broad | Narrow |
|---|---|---|---|---|---|---|---|
| Holdings | 10 | 0.71 | 0.31 | 0.47 | 0.81 | 1.11 | −0.00 |
| | 20 | 0.85 | 0.28 | 0.57 | 0.88 | 1.29 | −0.01 |
| | **30** | **0.93** | 0.30 | **0.63** | **0.96** | **1.39** | 0.01 |
| Keep | 1× | 0.79 | 0.28 | 0.52 | 0.86 | 1.20 | −0.01 |
| | 2× | 0.84 | 0.31 | 0.57 | 0.89 | 1.28 | −0.00 |
| | **3×** | **0.86** | 0.31 | **0.59** | **0.90** | **1.31** | 0.01 |
| EMA | 20 | 0.81 | 0.26 | 0.56 | 0.83 | 1.22 | −0.01 |
| | 50 | 0.85 | 0.24 | 0.56 | 0.86 | 1.29 | −0.05 |
| | 100 | 0.84 | 0.30 | 0.55 | 0.91 | 1.27 | 0.01 |
| | **200** | 0.84 | **0.38** | 0.58 | **0.93** | 1.28 | **0.05** |
| Within % of 52W high | 10% | **0.91** | 0.23 | 0.57 | **0.97** | **1.34** | −0.03 |
| | 20% | 0.83 | 0.31 | 0.56 | 0.87 | 1.25 | 0.02 |
| | 30% | 0.80 | 0.32 | 0.55 | 0.85 | 1.23 | 0.01 |
| | 50% | 0.79 | 0.32 | 0.55 | 0.84 | 1.23 | 0.00 |
| Score | return | 0.77 | 0.28 | 0.53 | 0.84 | 1.16 | 0.00 |
| | **Sharpe** | **0.89** | 0.31 | **0.59** | **0.93** | **1.37** | −0.00 |
| Weights | live | 0.85 | 0.30 | 0.58 | 0.88 | 1.25 | 0.04 |
| | short | 0.75 | 0.20 | 0.46 | 0.84 | 1.03 | 0.07 |
| | mid | 0.86 | 0.35 | 0.61 | 0.89 | 1.24 | 0.09 |
| | long | 0.86 | 0.34 | 0.59 | 0.90 | 1.38 | −0.06 |
| | 12M | 0.83 | 0.32 | 0.53 | 0.93 | 1.43 | −0.17 |

- **The same in every condition:** 30 holdings, keep 3×, Sharpe score. They lead,
  or tie, everywhere. These are not settings for one condition; they are better
  settings.
- **Condition-shaped, but small:** a 200D EMA helps most in downtrends and narrow
  markets (+0.14 and +0.10 against 50D). The tight 52W rule (within 10%) helps in
  uptrends and broad markets and hurts in downtrends. A 12M score does well in
  broad markets and badly in narrow ones.
- **Weights:** short-heavy is worst everywhere, as in the lookback study. The
  others sit within a few hundredths of the live weights except in broad and
  narrow markets.
- **Narrow breadth** (92 months, a Sharpe near 0 for every setting) is where
  momentum makes nothing, whatever the settings.

## Walk-forward: the test of picking by condition

Each year from 2014, learn from the years before only, then apply that year:

- **One best setting:** the combination with the best Sharpe on all earlier days.
- **By condition:** for each condition, the best combination on the earlier days
  in that condition, applied month by month as each month's condition comes. A
  condition with less than two years of earlier history falls back to the one
  best setting.

Sharpe over Jan 2014 to Sep 2026 (3,155 sessions), with 90% ranges from a paired
block bootstrap (63-session blocks, 2,000 draws):

| Rule | Sharpe | vs live | vs one best setting |
|---|---|---|---|
| Live settings | 0.71 | — | — |
| One best setting, re-picked yearly | 0.85 | +0.14 (−0.01 to +0.29), better in 94% of draws | — |
| By trend × volatility | 0.87 | +0.16 (0.00 to +0.34) | +0.02 (−0.11 to +0.16), 61% |
| By trend | 0.79 | +0.08 (−0.13 to +0.30) | −0.06 (−0.25 to +0.12), 29% |
| By volatility | 0.77 | +0.06 (−0.14 to +0.22) | −0.08 (−0.31 to +0.10), 20% |
| By breadth | 0.66 | −0.05 (−0.25 to +0.16) | −0.19 (−0.40 to 0.00), 5% |

Picking by condition is no better than one setting and, by breadth, worse. Its
gain over live is the one setting's gain: by trend × volatility, the most
frequent pick in up-stormy, down-calm and down-stormy was mid / 30 / 3× / 200D,
the one setting itself. Only up-calm had its own (12M, 30 holdings).

The "one best setting" barely moves from year to year:

| Year | Picked from the years before | Picked | Live | Difference |
|---|---|---|---|---|
| 2014 | 12M, 10 holdings, 1×, 20D EMA, within 20% | +46.2% | +77.3% | −31.1 |
| 2015 | mid, 30, 3×, 200D, within 20% | +18.6% | +11.7% | +7.0 |
| 2016 | mid, 30, 3×, 200D, within 20% | −0.4% | −2.0% | +1.6 |
| 2017 | mid, 30, 3×, 200D, within 30% | +65.9% | +54.9% | +11.0 |
| 2018 | mid, 30, 3×, 200D, within 30% | −11.8% | −9.0% | −2.9 |
| 2019 | mid, 30, 3×, 200D, within 20% | +19.6% | +8.1% | +11.5 |
| 2020 | mid, 30, 3×, 200D, within 20% | +37.2% | +26.2% | +11.0 |
| 2021 | mid, 30, 3×, 200D, within 30% | +89.4% | +90.4% | −1.1 |
| 2022 | mid, 30, 3×, 200D, within 30% | +8.8% | +5.0% | +3.8 |
| 2023 | mid, 30, 3×, 200D, within 30% | +39.7% | +37.0% | +2.6 |
| 2024 | mid, 30, 3×, 200D, within 30% | +20.7% | +14.7% | +6.1 |
| 2025 | mid, 30, 3×, 200D, within 30% | −13.7% | −21.6% | +7.9 |
| 2026 (Jan–Sep) | long, 30, 3×, 200D, within 20% | +16.4% | +17.8% | −1.4 |

Chained from 2014: 23.8% a year, max drawdown −34.4%. Live: 20.9% and −38.7%.
Ahead in 9 of 13 years. From 2015 on it is one setting (mid / 30 / 3× / 200D) with
only the 52W rule moving between 20% and 30%. 2014 shows the risk of choosing on
too little history: from four years, the pick was a noisy 10-stock, 20D-EMA
setting, 31 points behind.

## The same settings on other indexes

The settings were found on the Nifty 500, so its row is in-sample. Each one
against the live settings, same days. These lists share their stocks with the
Nifty 500, so this is a robustness check, not independent evidence. Total Market
(the live system's own list) starts in Nov 2021.

Sharpe minus live (90% range), share of bootstrap draws better:

| Settings | Nifty 500 (2010) | Nifty 100 (2010) | Midcap 150 (2016) | Smallcap 250 (2016) | Total Market (2021) |
|---|---|---|---|---|---|
| **Live weights, 30, 3×, 200D, within 20%** | +0.20 (+0.10 to +0.31), 100% | +0.15 (−0.01 to +0.32), 94% | +0.15 (+0.05 to +0.31), 99% | +0.10 (−0.04 to +0.23), 87% | +0.16 (−0.01 to +0.40), 95% |
| Mid, 30, 3×, 200D, within 30% (yearly pick) | +0.29 (+0.17 to +0.41), 100% | +0.15 (0.00 to +0.30), 96% | +0.16 (+0.03 to +0.34), 98% | −0.01 (−0.18 to +0.16), 44% | +0.19 (+0.01 to +0.50), 96% |
| Mid, 30, 3×, 200D, within 20% | +0.27 (+0.16 to +0.39), 100% | +0.16 (+0.01 to +0.33), 96% | +0.12 (+0.03 to +0.29), 98% | −0.01 (−0.15 to +0.14), 47% | +0.22 (+0.06 to +0.51), 98% |
| Long, 30, 3×, 200D, within 20% (grid best) | +0.30 (+0.13 to +0.47), 100% | +0.20 (+0.04 to +0.38), 98% | +0.06 (−0.08 to +0.25), 82% | +0.03 (−0.14 to +0.20), 60% | +0.38 (+0.18 to +0.73), 100% |
| Live Sharpe | 0.68 | 0.27 | 0.70 | 0.83 | 0.53 |

A year and max drawdown, live → live weights with 30 / 3× / 200D:

| | Nifty 500 | Nifty 100 | Midcap 150 | Smallcap 250 | Total Market |
|---|---|---|---|---|---|
| A year | 19.6% → 23.5% | 10.0% → 12.6% | 19.5% → 22.1% | 24.5% → 26.0% | 17.3% → 20.8% |
| Max drawdown | −38.7% → −34.8% | −28.7% → −33.5% | −35.5% → −34.9% | −40.5% → −36.5% | −41.0% → −35.4% |
| Turnover | 40 → 25 | 32 → 15 | 33 → 17 | 37 → 23 | 45 → 30 |

- **The holdings, keep and EMA change travels; the weights do not.** With the live
  weights, 30 / 3× / 200D is ahead on all five lists, with lower drawdown on four
  and about half the turnover. Mid and long weights add on some lists and nothing
  on the Smallcap 250, as the lookback study found.
- **The Nifty 100 is the exception on drawdown:** 30 holdings is 30% of that list.
- The live runs reproduce the lookback study's live figures on all five lists.

## Conclusion

1. **Do not switch settings by market condition.** The walk-forward shows no
   gain over one fixed setting, and the per-condition rankings do not repeat
   between halves of the history.
2. **The settings that help are the same in every condition:** 30 holdings, keep
   3×, Sharpe score, and a 200D EMA (most in downtrends and narrow markets).
3. **Recommendation:** live weights, 30 holdings, keep while in the top 90, 200D
   EMA, within 20% of the 52W high. Ahead of live on all five lists; lower
   turnover makes the gain less sensitive to costs. Its range touches zero on
   three of the four lists outside the Nifty 500, so the evidence is consistent
   but not conclusive.
4. **Keep the live lookback weights.** Mid and long weights look better on the
   Nifty 500 only, as in the lookback study.
5. **Owner, 12 Oct:** the recommendation is written on the Backtest page (#432).
   The defaults, the track record, the model book and the three systems are
   unchanged. The way to get evidence a backtest cannot give is to record the
   recommendation forward beside the live system (TODO 6).

## Past the edge of the grid (12 Oct, later)

The Recommendation sat at the grid's largest holdings (30), keep (3×) and EMA
(200), so the best values might lie beyond. `run --grid edge`: live weights,
within 20% of the 52W high, Sharpe score, and 30 / 40 / 50 holdings × keep 3× / 4×
× 200 / 250 / 300D EMA, on all five lists. Sharpe minus live, same days:

| Settings | Nifty 500 | Nifty 100 | Midcap 150 | Smallcap 250 | Total Market |
|---|---|---|---|---|---|
| **30, 3×, 200D (Recommendation)** | +0.20 | +0.15 | +0.15 | +0.10 | +0.16 |
| 30, 3×, 250D | +0.19 | +0.19 | +0.11 | +0.11 | +0.15 |
| 30, 3×, 300D | +0.19 | +0.15 | +0.10 | +0.11 | +0.15 |
| 30, 4×, 200D | +0.32 | +0.15 | +0.12 | +0.03 | +0.19 |
| 30, 4×, 250D | +0.35 | +0.20 | +0.08 | +0.01 | +0.17 |
| 40, 3×, 200D | +0.25 | +0.04 | +0.09 | +0.01 | +0.19 |
| 40, 4×, 200D | +0.30 | +0.04 | +0.06 | −0.06 | +0.17 |
| 50, 3×, 200D | +0.26 | −0.05 | +0.03 | +0.02 | +0.16 |
| 50, 4×, 200D | +0.22 | −0.05 | +0.03 | −0.03 | +0.24 |

- **No setting past the edge beats the Recommendation on every list.** Keeping
  4× or holding 40-50 adds on the Nifty 500 and Total Market and gives it back on
  the Midcap 150 and Smallcap 250 (and, at 40-50 names, on the Nifty 100, where
  that is half the list).
- **A slower EMA changes little:** at 30 holdings and 3×, 250D and 300D are within 0.05 of 200D on
  every list.
- **So the Recommendation, and the shadow record built on it, stay as they are.**
  The Nifty 500's best (30, 4×, 250D: +0.35) is the kind of in-sample peak the
  five-list check exists to catch.

## Not tested

- Switching costs: the walk-forward chains each pick's own returns, so it ignores
  the trades a switch would cause and the book each run carries. That flatters
  picking by condition, which still did not win.
- Rebalance interval, weighting (equal only), stock and industry caps, cost
  levels other than 30 bps, the all-time-high rule, separate keep rules.
- Other condition definitions (other averages, thresholds or windows). The three
  used are the header's regime and two common ones, fixed before the run.
- The live system's record runs on the Nifty 750 with its own membership and
  NSE-basis prices. The Total Market row is the nearest test (since Nov 2021).

## Rerun

```bash
.venv/Scripts/python scripts/research_regime_sweep.py run --out OUT --workers 4      # 1,728 backtests, ~2¼ h
.venv/Scripts/python scripts/research_regime_sweep.py report --out OUT                # report.md, summary.json, csvs
.venv/Scripts/python scripts/research_regime_sweep.py run --out OUT2 --index nifty_100 --combos "live_n30_k3_e200_h80_sharpe,mid_n30_k3_e200_h70_sharpe"
.venv/Scripts/python scripts/research_regime_sweep.py compare --out OUT OUT2
```

Names read `weights_nHOLDINGS_kKEEP_eEMA_hPCT_score`, where `h80` means at least
80% of the 52W high (within 20%). Each run saves its daily net returns, so
`report` and `compare` need no rerun; a stopped `run` resumes. Methods as in the
lookback note: the probability of backtest overfitting (Bailey, Borwein, López de
Prado and Zhu) and a paired block bootstrap.
