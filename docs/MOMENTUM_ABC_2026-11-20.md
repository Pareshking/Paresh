# Residual momentum, skipping the last days, vol-managed exposure (20 Nov 2026)

Owner, 20 Nov 2026, three proposals for the long-only strategy, each tested on
2010-to-date data, alone and in combination:

- **A. Residual momentum** (Blitz, Huij & Martens 2011): rank on factor-adjusted
  residual returns divided by residual volatility.
- **B. Skip the last days**: score the stock 0, 5 or 21 sessions before the
  signal, to avoid buying into a short spike that reverts.
- **C. Volatility-managed exposure** (Barroso & Santa-Clara; Daniel & Moskowitz):
  equity = min(1, 22.5% / the book's 63-day realised volatility), and a breadth
  overlay: below 30% of the Nifty 500 above its 200-day average, no new buys
  (exits go to cash, survivors are not sold); cash in an arbitrage fund.

Then: "write it up and run skip 5 in the engine". Read-only research; nothing in the
live system changed. TODO S160.

## Set-up (fixed before any result)

- **Universe and data:** point-in-time Nifty 500 (`index_universe`), NSE long adjusted
  closes (file of 16 Nov 2026; splits/bonuses/demergers, no dividends).
- **Simplified book** (`scripts/research/momentum_abc_overlays.py`, used to screen
  A x B x C): month-end signal, top 20 equal weight among stocks passing the live
  gates (above 50-day EMA, within 20% of the 52-week high), kept while in the top 40,
  30 bps on every rupee traded, buy-and-hold within the month, filled at the signal
  close. Cash: IIMA T-bill average minus 0.5% a year (about 6.2%) as an arbitrage-fund
  proxy. No stock/sector caps.
- **Engine** (`scripts/research/score_skip_engine.py`): the Backtest page's "History
  from 2010" run through `run_backtest` (the record's configuration, as
  `portfolio_history.py`), with the new research option `score_skip`.
- **Pass rule:** against the live signal (site composite, skip 0, no overlay), in the
  full period, 2010-17 AND 2018-26: CAGR at most 0.5 pp lower, worst 12 months no
  worse, and Sharpe at least 0.10 higher OR max drawdown at least 25% smaller.
  Overlays must also pass at neighbouring settings (vol target 20%/25%, breadth 25%/35%).

## A. Residual momentum

`scripts/research/residual_momentum.py`. Residuals from a 24-month regression (36 as
sensitivity; the price file starts Jan 2008, so 36 months only reach back to 2011) on
the Nifty 500 (CAPM) or on IIM Ahmedabad's Indian Fama-French factors (MF, SMB, HML;
file of Dec 2025, so it stops at Jan 2026). Score = sum / std of residuals in months
t-12 to t-2.

| Feb 2010 - Oct 2026, 24-month window | Sharpe | Max DD | Down-market beta |
|---|---|---|---|
| Top-minus-bottom fifth, site composite | 0.68 | -32% | -0.31 |
| Top-minus-bottom fifth, total 12-1 | 0.83 | -45% | -0.28 |
| **Top-minus-bottom fifth, residual CAPM** | **1.27** | **-12%** | **-0.02** |
| Top-20 live-shape book, site composite | 0.55 (16.7% a year) | -34.7% | 1.17 |
| Top-20 live-shape book, residual CAPM | 0.54 (16.5%) | -38.2% | 1.18 |
| Top-20 live-shape book, residual FF3 | 0.53 (16.1%) | -40.7% | 1.23 |

- The papers' result holds **long-short**: Sharpe roughly doubled, crash beta near
  zero, in both halves.
- It does **not** carry to a long-only book: the gain is the winners' and losers'
  similar betas cancelling, which a long-only book cannot use. Residual winners carry
  more market beta (top fifth down-market beta 1.31 vs 1.14); March 2020 -24.7% vs -21.2%.
- Fails the pass rule in every variant (both windows, both factor sets, a 50/50 blend
  with the composite). Best: FF3, 36 months, 18.1% vs 17.0%, won 2018-26, lost 2010-17,
  deeper drawdown.
- What held up: sector concentration. 30 Sep 2026, Capital Goods share of the top 20:
  total 12-1 45%, composite 20%, residual 15% (today's industry labels; 208 former
  members unlabelled).

## C. Vol-managed exposure and breadth overlay (simplified book)

| Site composite, skip 0 | CAGR | Sharpe | Max DD |
|---|---|---|---|
| No overlay | 18.1% | 0.60 | -34.8% |
| C1 vol target 22.5% | 17.7% | 0.60 | -34.3% |
| C2 breadth < 30% halt | 15.7% | 0.52 | -34.9% |
| C1 + C2 | 15.2% | 0.51 | -35.5% |

- **C1 is nearly inert:** average equity 96%. The 22.5% anchor (Microcap 250's
  long-run volatility) sits above our book's own (~21%), and a 63-day window reads calm
  before a crash and high just before the rebound. 20% and 25% targets: no better.
  Agrees with S144 (19 Nov), where vol targets also failed.
- **C2 costs 2-3 pp a year and does not reduce drawdown.** It fired in 31 of 200 months
  (Aug 2013, late 2018, Mar-May 2020, mid 2022, Jan-Apr 2025, Mar 2026): near bottoms,
  so the halt sits in cash through the rebound. 25% and 35% thresholds: no better.
- The arbitrage-fund tax point is right but does not matter if the overlay loses money.

## B. Skip the last days

Simplified book, site composite, every skip: 0 → 18.1%, 1 → 20.2%, 3 → 19.7%,
5 → 21.6%, 7 → 21.2%, 10 → 19.1%, 15 → 18.2%, 21 → 16.9%. A plateau from 1 to 12
sessions, not one lucky value; a full month (21) is worse than none, because all five
windows (1 to 12 months) lose their most recent month.

**In the engine** (`run_backtest`, `score_skip`; gates, membership and fills stay on
the signal date):

| Skip | CAGR | Sharpe | Max DD | 2010-17 CAGR / Sharpe | 2018-26 CAGR / Sharpe | Worst 12m (2018-26) |
|---|---|---|---|---|---|---|
| 0 (live) | 19.3% | 0.65 | -35.4% | 23.9% / 0.91 | 15.2% / 0.46 | -30.4% |
| 1 | 20.8% | 0.72 | -32.6% | 27.3% / 1.07 | 15.3% / 0.47 | -28.3% |
| 3 | 21.5% | 0.74 | -33.9% | 27.8% / 1.07 | 16.0% / 0.49 | -27.1% |
| **5** | **23.3%** | **0.79** | **-32.1%** | **29.4% / 1.10** | **18.0% / 0.56** | **-26.7%** |
| 7 | 22.2% | 0.75 | -36.9% | 28.1% / 1.09 | 17.1% / 0.52 | -31.7% |
| 10 | 20.5% | 0.70 | -34.5% | 25.4% / 0.93 | 16.3% / 0.51 | -29.0% |
| 21 | 19.4% | 0.64 | -35.5% | 25.4% / 0.94 | 14.3% / 0.42 | -26.6% |

- **Skip 5 passes the rule, by a hair:** Sharpe +0.146 overall, +0.190 in 2010-17 and
  +0.103 in 2018-26 (the bar is +0.10); CAGR +4.0 pp, +5.5 and +2.8; worst 12 months
  better in both halves; max drawdown 9% smaller (not the 25% alternative).
- Every skip from 1 to 10 beats skip 0 on CAGR in both halves, but only skip 5 clears
  the Sharpe bar in 2018-26 (3: +0.03, 7: +0.06, 10: +0.05).
- Skip 5 beat skip 0 in 12 of 17 calendar years and 56% of months; mean monthly lead
  0.29 pts (t 2.7, before any allowance for having tried seven skips).
- Recent years do not show it: 2025 -21.6% both; 2026 to date 11.5% vs 14.1%.
- Likely mechanism: short-term reversal. A stock that spiked in the final week tends to
  give some back; the 1-month window carries 10% of the composite's weight.

## A, B and C combined (simplified book, full period)

| | No overlay | C1 | C2 | C1+C2 |
|---|---|---|---|---|
| Composite, skip 0 | 18.1 / 0.60 / -34.8 | 17.7 / 0.60 / -34.3 | 15.7 / 0.52 / -34.9 | 15.2 / 0.51 / -35.5 |
| Composite, skip 5 | 21.6 / 0.73 / -34.9 | 21.0 / 0.73 / -34.9 | 20.1 / 0.70 / -32.4 | 19.4 / 0.68 / -32.4 |
| Composite, skip 21 | 16.9 / 0.55 / -39.8 | 16.1 / 0.52 / -38.8 | 13.8 / 0.44 / -37.4 | 13.4 / 0.42 / -36.7 |
| Residual, skip 0 | 15.5 / 0.50 / -39.8 | 15.0 / 0.48 / -39.8 | 12.6 / 0.39 / -40.5 | 12.4 / 0.38 / -40.5 |
| Residual, skip 5 | 15.8 / 0.51 / -39.8 | 15.3 / 0.50 / -39.8 | 13.7 / 0.44 / -40.3 | 13.6 / 0.43 / -40.0 |
| Residual, skip 21 | 16.8 / 0.56 / -39.6 | 16.3 / 0.54 / -39.6 | 15.1 / 0.50 / -38.3 | 14.9 / 0.49 / -38.3 |

(CAGR % / Sharpe / max drawdown %.) Every overlay lowers the return of every signal;
no combination beats skip 5 alone.

## Not checked

- Tax (each exit realises gains), dividends (price-only closes), a total-return benchmark.
- The 750 and Nano Cap universes; only the Nifty 500 as it stood.
- Historical industry labels (today's are used for sector caps and concentration).
- The simplified book fills at the signal close; the engine fills the next session.
- Skip 5 was picked on the same history the engine then tested, and the strategy's
  other settings were chosen on it too: the engine run confirms the simplified one, it
  is not an out-of-sample test.
- The 29-32% Capital Goods figures for Nifty500 Momentum 50 and BSE Smallcap 500
  Momentum 50, and the Chiao et al. (2020) citation, were not verified.

## What was done with it

- No change to the live system or the record. `run_backtest` gained the research option
  `score_skip` (default 0, tested to leave the live run unchanged to the last trade).
- Lead for the owner's decision: skip 5 as a forward shadow book (as S144's leads),
  judged on months nobody could tune it on, before any change to the live ranking.
- A and C: not pursued for a long-only book. Residual momentum would only pay in a
  long-short book (shorting through stock futures, F&O names only), a different product.
