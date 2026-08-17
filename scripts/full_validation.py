from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.engine.calendar_momentum import _calendar_period_metrics, apply_calendar_momentum, latest_as_of_date
from src.engine.momentum import MomentumEngine
from src.loaders.indices_loader import fetch_indices_data
from src.loaders.mcap_loader import fetch_market_caps
from src.loaders.price_loader import extract_ohlcv, fetch_price_history

OUT = Path("artifacts")
OUT.mkdir(exist_ok=True)

EXPECTED_NIFTY_TOTAL_MARKET_CONSTITUENTS = 752
idx = fetch_indices_data(["NIFTY TOTAL MARKET"])
if len(idx) != EXPECTED_NIFTY_TOTAL_MARKET_CONSTITUENTS:
    raise AssertionError(
        f"Expected {EXPECTED_NIFTY_TOTAL_MARKET_CONSTITUENTS} NIFTY TOTAL MARKET constituents, got {len(idx)}"
    )

symbols = idx["Symbol"].astype(str).str.strip().str.upper().tolist()
raw = fetch_price_history(symbols, period="2y", force_refresh=False)
if raw.empty:
    raise AssertionError("Price history is empty")
adj, close, high, low, volume = extract_ohlcv(raw, symbols)
if len(adj.columns) < 700:
    raise AssertionError(f"Too few price series after extraction: {len(adj.columns)}")

mcaps = fetch_market_caps(symbols, force_refresh=False)
calc = MomentumEngine(
    adj,
    high_df=high,
    low_df=low,
    close_df=close,
    volume_df=volume,
    weights=[0.10, 0.30, 0.30, 0.20, 0.10],
)
apply_calendar_momentum(calc)
rank_df = calc.get_rankings(
    idx,
    mcaps,
    close_prices_df=close,
    high_prices_df=high,
    compute_exp_reg=True,
)
if len(rank_df) < 700:
    raise AssertionError(f"Ranking output unexpectedly small: {len(rank_df)}")

required = {"Symbol", "Score", "Rank", "3M Return", "6M Return", "CMP", "52W High"}
missing = sorted(required - set(rank_df.columns))
if missing:
    raise AssertionError(f"Ranking schema missing columns: {missing}")

# Validate canonical calendar factors at the latest as-of date.
as_of = latest_as_of_date(pd.DatetimeIndex(adj.index))
factors: dict[str, pd.Series] = {}
for months in (1, 3, 6, 9, 12):
    score, ret, sharpe, _ = _calendar_period_metrics(
        adj, calc.log_ret, months, latest_as_of=as_of
    )
    latest = score.iloc[-1].rename(f"{months}M")
    factors[f"{months}M"] = latest

factor_df = pd.DataFrame(factors).replace([np.inf, -np.inf], np.nan)
corr = factor_df.corr(method="pearson")
corr.to_csv(OUT / "factor_correlation.csv")

# Score/rank monotonicity and finite-value checks.
score = pd.to_numeric(rank_df["Score"], errors="coerce")
rank = pd.to_numeric(rank_df["Rank"], errors="coerce")
valid = score.notna() & rank.notna()
if valid.sum() < 700:
    raise AssertionError("Too few finite ranked scores")
if not np.isfinite(score[valid]).all():
    raise AssertionError("Non-finite ranking scores detected")
if not rank[valid].is_monotonic_increasing:
    raise AssertionError("Rank column is not monotonically increasing")
if not score[valid].is_monotonic_decreasing:
    raise AssertionError("Score column is not monotonically decreasing by rank")

# Factor-level distributions.
distribution = {}
for col in factor_df.columns:
    s = factor_df[col].dropna()
    distribution[col] = {
        "n": int(s.size),
        "min": float(s.min()),
        "p05": float(s.quantile(0.05)),
        "median": float(s.median()),
        "p95": float(s.quantile(0.95)),
        "max": float(s.max()),
        "mean": float(s.mean()),
        "std_population": float(s.std(ddof=0)),
    }

rank_summary = rank_df[["Symbol", "Rank", "Score", "3M Return", "6M Return"]].copy()
rank_summary.to_csv(OUT / "ranking_summary.csv", index=False)

report = {
    "universe_requested": EXPECTED_NIFTY_TOTAL_MARKET_CONSTITUENTS,
    "universe_loaded": int(len(idx)),
    "price_series": int(len(adj.columns)),
    "ranked_stocks": int(len(rank_df)),
    "latest_as_of": str(as_of),
    "required_schema_ok": True,
    "rank_monotonic": True,
    "score_monotonic_by_rank": True,
    "factor_distribution": distribution,
    "factor_correlation": corr.round(6).to_dict(),
    "top_10": rank_df[["Symbol", "Rank", "Score", "3M Return", "6M Return"]].head(10).to_dict("records"),
}
(OUT / "quant_validation.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
print(json.dumps(report, indent=2, default=str))
