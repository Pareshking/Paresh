# Sizing and risk overlays on the momentum strategy (19 Nov 2026)

Owner, 19 Nov 2026: can Kelly / half-Kelly sizing or a risk overlay keep the upside
and limit the downside? Then: test the best 3 of each group in combination, and
test the criteria flipped. Read-only research; nothing in the live system changed.
Scripts and full tables were in the session scratchpad (`overlays/`); the numbers
below are copied from them. TODO S144.

## Set-up (fixed before any result)

- **Baseline:** the Backtest page's "History from 2010" defaults through the app's own
  `run_backtest`: point-in-time Nifty 500, 20 holdings kept while in the top 40, 50-day
  EMA, within 20% of the 52-week high, lookback weights 10/30/30/20/10, 30 bps.
  NSE long file of 17 Nov 2026 (last session 16 Nov). Jan 2010 - Oct 2026:
  **19.1% a year, max drawdown -38.8%** (Nifty 500 price index 10.2%).
- **Overlays:** decided at a month-end close, applied from the next session; a switch
  pays 30 bps on the share moved; cash 6.5% a year (0% as sensitivity).
- **Pass rule:** CAGR at most 0.5 pp below the baseline, max drawdown at least 25%
  smaller, worst 12 months better; in the full period, 2010-17 AND 2018-26; settings
  chosen on 2010-17 only; neighbouring settings must hold too.

## Results

| Study | Tried | Passed | What came closest |
|---|---|---|---|
| Single overlays (regime, breadth, votes, Kelly, vol target, drawdown brake, NAV filter, lookback weights, 52-week-high gate) | ~100 | 0 | Breadth > 60% else cash: 19.8% / -21.0%, but -2.2 pp in 2010-17 and knife-edge; gate 0.90: 20.6% / -32.8%, drawdown only 15% smaller |
| Best 3 per group, in pairs and triples | 2,781 | 13, all one idea | Breadth > 60% else 50% + long-heavy weights (0/10/20/30/40) [+ gate 0.90]: 21.7% / -23.1% |
| Criteria flipped (trend vs contrarian tilt on an 80/20 base) | 46 | 0 vs the 100% book | — |

- **Kelly:** half Kelly 13.1% a year (6.6% in 2018-26); leverage drew down 48-58%.
- **Selection decays:** the best 2010-17 combination ranked 2,578th of 2,781 in 2018-26
  (8.6% a year).
- **One crash carries most of it:** forced 100% invested through 2020, the passing
  combinations' drawdown returns to about -32% to -37%.
- **Signals point the normal way** (good breadth/trend -> better next month), but the
  worst-looking months were still positive on average, which is why exits miss rebounds.
- **Not modelled:** tax (each exit realises gains: STCG 20%), a total-return benchmark,
  historical industry labels.

## What was done with it

- No change to the live system. For a smaller drawdown, hold less of the strategy
  (for example 65% in it and 35% in a liquid or debt fund, rebalanced yearly).
- Two leads recorded forward as shadow books from the December 2026 book, never traded
  (TRACK_RECORD.md section 10): "Near-high 90%" and "Breadth + long lookback".
