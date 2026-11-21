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
| Top-minus-bottom fifth, site composite | 0.69 | -32% | -0.31 |
| Top-minus-bottom fifth, total 12-1 | 0.83 | -45% | -0.28 |
| **Top-minus-bottom fifth, residual CAPM** | **1.27** | **-11%** | **-0.02** |
| Top-20 live-shape book, site composite | 0.56 (16.7% a year) | -34.7% | 1.17 |
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
| C1 + C2 | 15.2% | 0.51 | -35.4% |

- **C1 is nearly inert:** average equity 97%. The 22.5% anchor (Microcap 250's
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
| 0 (live) | 19.3% | 0.65 | -35.4% | 23.9% / 0.92 | 15.2% / 0.46 | -30.4% |
| 1 | 20.8% | 0.72 | -32.6% | 27.3% / 1.07 | 15.3% / 0.47 | -28.3% |
| 3 | 21.5% | 0.74 | -33.9% | 27.8% / 1.08 | 16.0% / 0.49 | -27.1% |
| **5** | **23.3%** | **0.79** | **-32.1%** | **29.4% / 1.11** | **18.0% / 0.56** | **-26.7%** |
| 7 | 22.2% | 0.76 | -36.9% | 28.1% / 1.10 | 17.1% / 0.52 | -31.7% |
| 10 | 20.5% | 0.70 | -34.5% | 25.4% / 0.94 | 16.3% / 0.51 | -29.0% |
| 21 | 19.4% | 0.64 | -35.5% | 25.4% / 0.95 | 14.3% / 0.42 | -26.6% |

- **Skip 5 passes the rule, by a hair:** Sharpe +0.146 overall, +0.191 in 2010-17 and
  +0.103 in 2018-26 (the bar is +0.10); CAGR +4.0 pp, +5.5 and +2.8; worst 12 months
  better in both halves; max drawdown 9% smaller (not the 25% alternative).
- Every skip from 1 to 10 beats skip 0 on CAGR in both halves, but only skip 5 clears
  the Sharpe bar in 2018-26 (3: +0.03, 7: +0.06, 10: +0.05).
- Skip 5 beat skip 0 in 12 of 17 calendar years and 56% of months; mean monthly lead
  0.29 pts (t 2.7, before any allowance for having tried seven skips).
- Recent years do not show it: 2025 -21.6% both; 2026 to date 11.5% vs 14.1%.
- Likely mechanism: short-term reversal. A stock that spiked in the final week tends to
  give some back; the 1-month window carries 10% of the composite's weight.

## Skip 5 across universes (21 Nov 2026)

Owner, 21 Nov 2026: is the skip-5 edge in other universes, and does it survive a different
list of names? `scripts/research/score_skip_universes.py`, the engine with the record's
configuration, NSE long closes of 16 Nov 2026.

**Every index with point-in-time membership, from its first month** (CAGR; gap = skip 5
minus skip 0, points a month; t of the monthly gap):

| Universe | From | Skip 0 | Skip 3 | Skip 5 | Skip 7 | Gap | t | Months ahead |
|---|---|---|---|---|---|---|---|---|
| Nifty 50 | 2010 | 4.5% | 4.8% | 4.5% | 4.1% | 0.00 | -0.04 | 51% |
| Nifty Next 50 | 2010 | 10.9% | 10.3% | 10.1% | 10.4% | -0.06 | -1.77 | 45% |
| Nifty 100 | 2010 | 9.9% | 9.9% | 8.9% | 9.7% | -0.08 | -1.84 | 45% |
| Midcap 150 | Apr 2016 | 18.8% | 19.9% | 20.4% | 18.1% | +0.11 | 1.17 | 52% |
| Smallcap 250 | Apr 2016 | 23.0% | 23.2% | 22.3% | 22.8% | -0.06 | -0.47 | 43% |
| Microcap 250 | Oct 2021 | 27.4% | 27.8% | 26.8% | 28.0% | -0.02 | -0.13 | 44% |
| Nifty 500 | 2010 | 19.3% | 21.5% | 23.3% | 22.2% | +0.29 | 2.71 | 56% |
| Nifty 750 | Nov 2021 | 15.7% | 16.7% | 21.2% | 19.4% | +0.41 | 1.76 | 67% |

- No size segment shows it; only the two broad lists do, and they are one result (the 750
  holds the 500, over years inside the 500's). The 500's gain from April 2016 (+0.26 a month)
  is not in its parts over the same months (Midcap 150 +0.11, Smallcap 250 -0.06).
- The Nifty 50 row is near-uninformative: 20 holdings kept to the top 40 of 50 is close
  to the index.
- The 750's skip-0 run reproduces the frozen live record for 2026 (six of ten months to
  0.01 pts; the rest within 0.25, Screener vs NSE prices).

**Size mix of the book** (average share of holdings at each rebalance):

| | Nifty 100 | Midcap 150 | Smallcap 250 | Microcap 250 |
|---|---|---|---|---|
| Nifty 500 from Apr 2016, skip 0 / skip 5 | 23% / 23% | 34% / 34% | 42% / 42% | - |
| Nifty 750 from Nov 2021, skip 0 / skip 5 | 14% / 14% | 21% / 22% | 26% / 27% | 39% / 36% |

Skip 5 does not tilt the book to a size: the gain is not a hidden size bet.

**Random universes** (pass rule fixed before results: skip 5 ahead in at least 75% of
draws and a median gap above 0). 100 draws each; a draw drops a random 20% of the index's
ever-members, the same names for both skips:

| | Draws | Skip 5 ahead | Median CAGR gap | 10th-90th percentile | Full list |
|---|---|---|---|---|---|
| Nifty 500, 2010-26 | 100 | **92%** | **+1.6 pp** | +0.5 to +2.5 pp | +4.0 pp |
| Nifty 750, Nov 2021-26 | 100 | 73% | +1.0 pp | -1.7 to +3.1 pp | +5.5 pp |

- Nifty 500 passes: the sign does not hang on a few names. The 750 misses by 2 draws
  (60 months only).
- **The full lists' gaps are luckier than every draw** (500: +4.0 against a draw maximum
  of +3.6; 750: +5.5 against +5.4). A fair expectation is about +1 to +1.5 pp a year, not 4.
- The draws share 80% of their names and all of their history: they test robustness to
  the list, not to the period. Skip 5 was still picked on 2010-26.

Read together: a small edge on broad lists, robust to which names are in them, absent
inside every size segment and unexplained by size. The shadow book (section 11 of
`docs/TRACK_RECORD.md`) is the test; expect a gap of about 1 pp a year, which 12 months
cannot separate from noise.

## A, B and C combined (simplified book, full period)

| | No overlay | C1 | C2 | C1+C2 |
|---|---|---|---|---|
| Composite, skip 0 | 18.1 / 0.60 / -34.8 | 17.7 / 0.60 / -34.3 | 15.7 / 0.52 / -34.9 | 15.2 / 0.51 / -35.4 |
| Composite, skip 5 | 21.6 / 0.74 / -34.9 | 21.0 / 0.73 / -34.9 | 20.1 / 0.70 / -32.4 | 19.4 / 0.68 / -32.4 |
| Composite, skip 21 | 16.9 / 0.55 / -39.8 | 16.1 / 0.52 / -38.8 | 13.8 / 0.44 / -37.4 | 13.4 / 0.42 / -36.7 |
| Residual, skip 0 | 15.5 / 0.50 / -39.8 | 15.1 / 0.48 / -39.8 | 12.6 / 0.39 / -40.5 | 12.4 / 0.38 / -40.5 |
| Residual, skip 5 | 15.8 / 0.52 / -39.8 | 15.3 / 0.50 / -39.8 | 13.7 / 0.44 / -40.3 | 13.6 / 0.43 / -40.0 |
| Residual, skip 21 | 16.8 / 0.56 / -39.6 | 16.3 / 0.54 / -39.6 | 15.1 / 0.51 / -38.3 | 14.9 / 0.50 / -38.3 |

(CAGR % / Sharpe / max drawdown %.) Every standard deviation is the population one (ddof=0, the site's convention, S119). Every overlay lowers the return of every signal;
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
- Skip 5 is recorded forward as a shadow book (owner, 20 Nov 2026: "Record skip 5 as a
  shadow book"): `SHADOWS["skip5"]`, from the December 2026 book, never traded
  (`docs/TRACK_RECORD.md` section 11). Reviewed after 12 months.
- A and C: not pursued for a long-only book. Residual momentum would only pay in a
  long-short book (shorting through stock futures, F&O names only), a different product.
