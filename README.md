# NSE Quantitative Momentum Terminal

Institutional-grade quantitative multi-system momentum ranking, portfolio construction, delivery accumulation, and walk-forward backtesting platform for Indian equities (NSE).

Built with Python, Streamlit, and Plotly with a **Pure Paper White (`#FFFFFF`), high-density, full-widescreen financial terminal interface**.

---

## Quantitative Momentum Systems

| # | System | Quantitative Signal & Formula |
|---|--------|-------------------------------|
| 1 | **Sharpe Momentum** | Multi-window Z(Sharpe) across 5 lookbacks (1M, 3M, 6M, 9M, 12M) — Sharpe carries directional sign;  scales trend quality |
| 2 | **Vectorized Exp-Regression** | Vectorized rolling OLS: $\beta = r \times \frac{\sigma_y}{\sigma_x}$, $\text{Score} = (e^{\beta \times 252} - 1) \times R^2$ |
| 3 | **Residual / Idiosyncratic Alpha** | Rolling regression against broad market proxy: $\alpha_{\text{ann}} = (\mu_i - \beta_i \mu_m) \times 252$ |
| 4 | **Industry-Relative Momentum** | Stock composite score minus industry/sector peer group average |
| 5 | **Momentum Acceleration** | Short-term momentum ($0.10 \times 1\text{M} + 0.35 \times 3\text{M} + 0.55 \times 6\text{M}$) minus Long-term momentum ($0.45 \times 9\text{M} + 0.55 \times 12\text{M}$) |

---

## Core Capabilities & Modules

1. **📊 Stock Rankings**: Full universe screening, search by Symbol/Industry/Index/Sector, multi-factor ranking, rank delta movers (1M & 3M), single-stock candlestick deep-dive with EMAs and ATR Stop Loss, and CSV export.
2. **🏆 Qualified Picks**: High-conviction screen (Price > 50 EMA, within 20% of 52W High), 90-day return correlation matrix heatmap, and industry concentration analysis.
3. **🏭 Industry & RRG**: Industry rankings with % 52W High and % 20 EMA, plus an interactive Relative Rotation Graph (RRG) with customizable lookback and trail lengths.
4. **🔬 Multi-Strategy Overlay**: Consensus picks appearing in top-$N$ across Residual Alpha, Industry-Relative, and Acceleration systems.
5. **💼 Portfolio Optimization**: Equal Weight, Inverse Volatility, and Mean-Variance Optimization (MVO with Ledoit-Wolf covariance shrinkage + SLSQP solver with sector/stock caps and volatility targeting).
6. **📦 Delivery Accumulation**: NSE Bhavcopy 45-day rolling delivery and volume surge analysis with Dual Surge accumulation detection.
7. **👁️ Watchlist**: Custom portfolio tracking against full universe quantitative rankings.
8. **📡 Market Breadth**: 10D/20D/50D/100D/200D Moving Average Breadth across indices, daily 52W High/Low time series, and Net New Highs.
9. **📈 Strategy Backtest**: Walk-forward historical backtesting with zero look-ahead bias (rank at $T$, invest at $T+1$), equity curve vs benchmark, and period win-rates.
10. **⚙️ Config & Diagnostics**: Custom index constituents, dynamic lookback factor weights, risk parameters, and disk cache diagnostics.

---

## Project Structure

```
├── .streamlit/
│   └── config.toml          # Light theme & server configuration
├── data/
│   ├── indices/             # Local offline fallback CSVs for index constituents
│   └── nse_tv_classification.csv # TradingView 119 industry / 20 sector taxonomy
├── src/
│   ├── core/                # Config, typed dataclasses, and logging
│   ├── loaders/             # Indices, prices, market cap, delivery, and TV loaders
│   ├── engine/              # Momentum, portfolio optimizer, breadth, and backtester
│   └── ui/                  # Pure White design system, components, charts, and views
├── app.py                   # Main Streamlit application entry point
├── requirements.txt         # Dependencies
└── README.md
```

---

## Running Locally

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch application
streamlit run app.py
```

---

## Data Integrity & Multi-Tier Caching

- **Holiday Filtering**: Exchange closures with >70% NaNs are automatically dropped.
- **Data Gap Tracking**: Stocks with >10% forward-filled rows are flagged 🔴.
- **Short History Masking**: Stocks with history shorter than window size are safely masked.
- **Multi-Tier Caching**: Parquet storage in `data_cache/` survives restarts while session TTL caches prevent redundant calculations.

---

## Disclaimer

Educational and research use only. Not financial or investment advice.
