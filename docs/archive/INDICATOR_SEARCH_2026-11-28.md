# Indicator search on the monthly momentum book (S239, 28 Nov 2026)

Owner, 28 Nov 2026: "check other indicators with our monthly rebalancing portfolio ... test individual indicators,
combinations ... understand each indicator, their usage, strength, weakness ... index or universe strength or
anything". Read-only research; no live rule changed. Follows `RS_SUPERTREND_2026-11-28.md` (same day).
Scripts: `scripts/research/indicator_screen.py` (Level A), `overextension_gate.py` (Level B),
`rs_daily_exit.py` (daily exit, combinations, power). Long file of 27 Nov 2026 (release `data-latest`).

## Why two levels, and what was already tried

Earlier studies tried about 2,900 settings (`RISK_OVERLAYS_2026-11-19.md`: 13 passed, all one idea, and the best of
2010-17 ranked 2,578th in 2018-26; `MOMENTUM_ABC_2026-11-20.md`: residual momentum, skip-recent, vol targeting,
breadth). Running every indicator and combination through the engine would find "winners" by chance. So:

- **Level A** (cheap, broad): at each month-end, among the 60 best-ranked names that pass the book's gates (the pool
  the book picks from), does the indicator rank next month's returns? Rank correlation per month, its t over 183
  months (Apr 2011 - Sep 2026), each indicator's direction written down first. Bar: t >= 3.0 (27 tried) and t >= 1.5
  in each half. Three random columns as a placebo (largest |t| 1.73).
- **Level B** (engine, only for what comes close): a gate in `run_backtest`, with a random gate blocking the same
  share of buys as the null.

## Level A: 27 indicators, 0 pass

| Group | Indicators (direction) | Best t | Read |
|---|---|---|---|
| Trend / RS | RS vs its 50D EMA, 6-month RS, MACD, EMA slope, distance to 52W high, new-high days (+) | 1.6 | Nothing. RS vs its EMA points the WRONG way (t -2.3): within the pool, names furthest above their RS average do worse next month |
| Overextension | Bollinger %B, RSI(14), close over 50D / 200D EMA, last month's return (higher = worse) | **3.17** (%B; 2010-17 3.2, 2018-26 1.5) | The only family with the same sign in every form: RSI 2.3, close/50D EMA 2.2 |
| Smoothness | Efficiency ratio, trend R², Clenow slope x R², frog-in-the-pan (+) | 1.4 | Nothing |
| Risk | Volatility, downside vol, beta, idio vol, worst fall, vol ratio (lower = better) | 1.5 | Nothing |
| Volume (traded value) | Value surge, up-day value share, Amihud, size proxy | 0.6 | Nothing |
| Industry | Industry 3M return, stock vs industry 6M (+) | 1.5 | Industry 3M: 2010-17 only |
| Reference | **The composite score itself** | **0.9** | Inside the top 60, our own rank order does not predict next month |

## Level B: the overextension gate in the engine

Baseline 18.81% a year (record rules, Nifty 500 as it stood, Jan 2010 - Nov 2026, monthly reset, 30 bps).

| Gate (mode) | Blocks of new buys | Run | 2010-17 | 2018-26 | Worst fall | Null p90 | Verdict |
|---|---|---|---|---|---|---|---|
| %B > 1 blocked (entry) | 16% | +2.47 | +4.01 | +1.15 | -38.4% | +2.09 | passes |
| %B > 1 blocked (both) | | +1.48 | +3.29 | -0.04 | -36.2% | | fails 2018-26 |
| RSI > 70 blocked (entry) | 47% | +2.01 | +1.30 | +2.63 | -35.6% | +2.37 | inside the null |
| RSI > 70 blocked (both) | | +0.49 | +0.11 | +0.79 | -32.7% | | fails |
| %B top fifth blocked (entry) | 60% | +3.70 | +4.09 | +3.36 | -35.4% | +2.44 | passes |
| %B top fifth blocked (both) | | +3.23 | +5.12 | +1.65 | -38.1% | | passes |

The null is wide: a random gate blocking 60% of buys ranged up to +5.84 pts (mean +0.37), because picking lower
inside a pool whose order carries no information costs nothing.

## Follow-ups (owner approved or asked, same day)

**Daily exit on an RS flip (approved):** fails badly. Supertrend(10,3) on RS flipped in 76% of holding-months, the
book sat 41% of its days in cash, and the names sold rose +1.28% on average by the month's end. Against a replay
without exits: Supertrend (10,3) / (14,3) / (20,3) -14.5 / -14.6 / -14.9 pts a year; RS below its 50D EMA -9.9.
Cash at 0% in the replay; at 6.5% about 2.7 pts would come back, not 10-15.

**Combinations, once (asked):** they do not add up, which is the clearest sign of noise.

| Cell | Run | 2010-17 | 2018-26 |
|---|---|---|---|
| Skip 5 alone | +4.25 | +5.92 | +2.86 |
| Skip 5 + RS above 50D EMA | +3.87 | +6.66 | +1.55 |
| Skip 5 + %B top fifth blocked | **+1.41** | +2.54 | +0.46 |
| Skip 5 + %B > 1 blocked | +5.40 | +8.94 | +2.45 |

Two rules that each add 3.7-4.3 pts give +1.4 together; a near-identical pair gives +5.4.

**Forward power:** years of a shadow record needed to see each in-sample gain at t = 2 (monthly difference against
the baseline): skip 5 ~6, %B > 1 ~10, RS above 50D EMA ~11, %B top fifth ~15. A 12-month review cannot confirm
any of them; it can only check behaviour (TRACK_RECORD.md sections 9-11 already say so).

## What this says

1. Price-based indicators re-describe the same price history the score already uses; 27 of them added nothing the
   score does not have.
2. The one recurring signal is **short-term overextension** (skip 5 and %B are the same mechanism: do not buy
   into a fresh spike). It is already recorded forward as the skip-5 shadow.
3. The ranking adds nothing inside the top 60: the book's edge is the pool (the gates and the top group), not the
   order. Gains are more likely from information prices do not hold (earnings, quality, ownership), from the
   universe chosen, and from costs and tax.
4. We hold no history for fundamentals: `screener_quarters.csv` has 13 quarters (Sep 2023 - Sep 2026) with no
   announcement dates; FII flows are market-wide. An earnings test from 2010 needs dated quarterly results.

Not checked: OHLC versions (ADX, Stochastic, true ATR; the long file has closes only); the Nifty 750 or smaller
universes; the six-monthly reset default; tax; cash at 6.5% in the daily-exit replay.
