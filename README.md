# NSE Quantitative Momentum Terminal

Institutional-style quantitative multi-system momentum ranking, portfolio construction, delivery accumulation, and walk-forward backtesting platform for Indian equities (NSE).

## V1 quantitative status

The current V1 research model has been hardened against the main mathematical and architectural issues identified in the 2026 quantitative audit. The canonical System-1 signal is now calendar-period based and does **not** use .

### System-1 — Sharpe Momentum

Five calendar horizons:

- 1 month
- 3 months
- 6 months
- 9 months
- 12 months

For each as-of date, the engine:

1. subtracts the calendar horizon from the as-of date;
2. selects the first available market observation on or after that target date;
3. uses the actual valid daily observations through the as-of date;
4. calculates the approved period risk-adjusted momentum statistic;
5. standardizes the cross-section using the approved outlier-control sequence; and
6. combines the five standardized signals using the configured 10/30/30/20/10 weights.

The approved System-1 Sharpe methodology is intentionally retained. It is a **period risk-adjusted momentum statistic**, not conventional annualized Sharpe, and should not be compared numerically with institutional annualized Sharpe figures.

** is not part of System-1 and is not used to scale its score.**

### Other quantitative systems

| # | System | Description |
|---|--------|-------------|
| 1 | **Sharpe Momentum** | Multi-window Z-score across calendar 1M/3M/6M/9M/12M horizons; no  scaling |
| 2 | **Vectorized Exp-Regression** | Vectorized rolling regression-based trend signal |
| 3 | **Residual / Idiosyncratic Alpha** | Rolling regression against the common V1 market benchmark |
| 4 | **Industry-Relative Momentum** | Stock composite score relative to a **leave-one-out** industry/sector peer mean |
| 5 | **Momentum Acceleration** | Short-term momentum versus long-term momentum |

## Canonical V1 conventions

### Benchmark

The common V1 market benchmark is:

`^CRSLDX` — Nifty 500.

Where a market benchmark is required by a V1 quantitative module, this benchmark should be used consistently unless a module has an explicitly documented reason not to.

### Periods

System-1 uses **calendar months**, not fixed trading-row windows. The legacy 21/63/126/189/252 momentum-window definition has been removed from the root configuration.

Session-based windows may still exist in portfolio/risk components where they are intentionally part of the approved methodology. They must not be reused as System-1 economic horizons.

### Monthly backtest convention

For monthly V1 rebalancing:

- last available trading day of the month = signal/rebalance date at T close;
- first available trading day of the following month = execution at T+1.

The backtester must use the same canonical System-1 calendar-period engine as the live screener.

### Industry-relative methodology

For stock `i` in an industry with more than one valid member:

`Relative_i = Score_i - mean(Score_j for j != i)`

The stock's own score is therefore excluded from its peer benchmark. Missing values remain missing according to the existing ranking contract; singleton industries have no peer-relative comparison.

### Missing stock observations

Exchange-wide closures may be removed as holidays. A stock-specific missing observation must **not** be forward-filled for quantitative return/volatility calculations. This prevents synthetic zero returns and artificial smoothing.

### Cross-sectional normalization

The documented pipeline is:

`raw factor -> approved winsorization/outlier control -> Z-score -> final numerical clipping`

The implementation must not describe simple Z-score clipping as raw-score winsorization.

## Portfolio and risk methodology

Portfolio/risk mathematics is intentionally separate from System-1 signal mathematics. Approved session-based risk calculations are not converted to calendar horizons merely because System-1 uses calendar periods.

Examples include realized-volatility targeting, inverse-volatility weighting, covariance estimation and constrained ERC. These retain their approved session counts and annualization conventions.

## Research audit tracker

See [`docs/V1_AUDIT_TRACKER.md`](docs/V1_AUDIT_TRACKER.md) for the full audit roadmap, completed corrections, and remaining research tasks.

## Core capabilities

1. **Stock Rankings**: Full-universe screening, symbol/industry/index/sector search, multi-factor ranking, rank movers, single-stock deep-dive and CSV export.
2. **Qualified Picks**: High-conviction screening and concentration analysis.
3. **Industry & RRG**: Industry rankings and Relative Rotation Graph analysis.
4. **Multi-Strategy Overlay**: Consensus across Residual Alpha, Industry-Relative and Acceleration systems.
5. **Portfolio Optimization**: Equal Weight, Inverse Volatility and Mean-Variance Optimization with covariance shrinkage, constraints and volatility targeting.
6. **Delivery Accumulation**: NSE delivery/volume surge analysis.
7. **Watchlist**: Custom portfolio tracking against quantitative rankings.
8. **Market Breadth**: Moving-average breadth and high/low statistics.
9. **Strategy Backtest**: Walk-forward historical backtesting with rank at T close and execution at T+1.
10. **Config & Diagnostics**: Index constituents, factor weights, risk parameters and cache diagnostics.

## Data integrity

- Exchange-wide closure rows are filtered using the existing holiday-detection rule.
- Security-specific missing observations remain missing for quantitative calculations.
- Short-history securities are masked where the required statistical sample is unavailable.
- Data-gap diagnostics remain available to identify problematic securities.

## Project structure

```text
├── .streamlit/
├── data/
├── docs/
├── src/
│   ├── core/
│   ├── loaders/
│   ├── engine/
│   └── ui/
├── app.py
├── requirements.txt
└── README.md
```

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Disclaimer

Educational and research use only. Not financial or investment advice.
