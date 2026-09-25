from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.engine.calendar_momentum import _calendar_period_metrics, apply_calendar_momentum, latest_as_of_date
from src.engine.momentum import MomentumEngine
from src.engine.pipeline import carried_symbols, carry_last_prints, last_ranked_session
from src.loaders.indices_loader import fetch_indices_data
from src.loaders.mcap_loader import fetch_market_caps
from src.loaders.price_loader import extract_ohlcv, fetch_price_history

OUT = Path("artifacts")
OUT.mkdir(exist_ok=True)

# fetch_indices_data() returns the investable universe after deterministic
# filtering of explicit DUMMY/placeholder constituents. Do not hard-code the
# raw NSE row count: constituent counts can change during index rebalances.
idx = fetch_indices_data(["NIFTY TOTAL MARKET"])
if idx.empty:
    raise AssertionError("NIFTY TOTAL MARKET returned an empty investable universe")

symbols = idx["Symbol"].astype(str).str.strip().str.upper()
if symbols.str.startswith("DUMMY").any():
    dummy_symbols = symbols[symbols.str.startswith("DUMMY")].tolist()
    raise AssertionError(f"DUMMY constituents leaked into investable universe: {dummy_symbols}")
if symbols.duplicated().any():
    duplicates = symbols[symbols.duplicated()].tolist()
    raise AssertionError(f"Duplicate symbols in investable universe: {duplicates}")
symbols = symbols.tolist()

raw = fetch_price_history(symbols, period="2y", force_refresh=False)
if raw.empty:
    raise AssertionError("Price history is empty")
adj, close, high, low, volume, open_p = extract_ohlcv(raw, symbols)
if len(adj.columns) < 700:
    raise AssertionError(f"Too few price series after extraction: {len(adj.columns)}")

# Rank the session PRODUCTION would rank, not the frame's last row.
#
# This script built the engine by hand and scored whatever row happened to be
# last. Since real sessions stopped being deleted from the history, that row is
# routinely one the vendor is still publishing: on a fresh CI checkout Yahoo's
# newest Indian session held 430 of 750 closes, the engine ranked the 430 names
# it could price, and the finite-score assertion below read that as corruption.
# `main` was red for days over a working engine and a late vendor.
#
# pipeline.last_ranked_session is the rule app.py and scripts/sync_data.py
# already use, so this validates what production computes instead of a session
# production skips. Trimming, not floor-lowering: the assertions stay strict.
_cut = last_ranked_session(adj)
if _cut is not None and _cut < len(adj.index) - 1:
    _stop = adj.index[_cut]
    print(
        f"Ranking as of {str(_stop)[:10]} rather than {str(adj.index[-1])[:10]}: "
        "the newer session(s) are still being published."
    )
    adj, close, high, low, volume = (
        f.loc[:_stop] if f is not None else None
        for f in (adj, close, high, low, volume)
    )

# Owner decision 2B, exactly as pipeline.build_engine applies it: a few
# stragglers that printed recently are ranked on their last print instead of
# holding the whole session back. Without this, this script ranked a
# different set of names than production on any day with a straggler.
_carried = carried_symbols(adj)
if _carried:
    adj, close, high, low = (
        carry_last_prints(f, _carried) for f in (adj, close, high, low)
    )
    print(f"Carried on their last print (2B): {', '.join(_carried)}")

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
)
# Coverage is measured against the session actually being ranked, not against a
# constant.
#
# `len(rank_df) < 700` conflated two different claims: "the engine ranked what
# it could" and "the vendor has finished publishing". Only the first is this
# repository's to guarantee. Yahoo backfills a thin Indian session over hours or
# days, so on 2026-09-17 just 368 of 750 symbols had a close for 2026-09-16 --
# and the check failed on `main` with the engine working perfectly, having
# ranked every symbol it was able to price. A fixed floor makes vendor latency
# indistinguishable from a ranking defect, and the alarm that cries wolf is the
# one nobody reads.
#
# So the assertion is a ratio against the priceable universe. It still catches
# the real failure -- the engine dropping names it had prices for -- while a
# late vendor produces a loud warning and a pass.
priced_session = pd.DatetimeIndex(adj.index)[-1]
priced_session_date = pd.Timestamp(priced_session).date()
priceable = int(adj.loc[priced_session].notna().sum())

# Below this the vendor is mid-backfill, not the engine mid-failure.
COVERAGE_WARN_BELOW = 500
# Of what COULD be ranked, essentially all of it should be. The slack absorbs
# symbols that carry a close but fail the observation minimum.
RANKED_SHARE_FLOOR = 0.95

if priceable == 0:
    raise AssertionError(
        f"No symbol has a close on {priced_session_date}: the price frame's "
        "last session is empty, which no amount of vendor lag explains."
    )

if len(rank_df) < priceable * RANKED_SHARE_FLOOR:
    raise AssertionError(
        f"Ranking covers {len(rank_df)} of the {priceable} symbols priced on "
        f"{priced_session_date} ({len(rank_df) / priceable:.1%}); the engine "
        "dropped names it had prices for."
    )

if priceable < COVERAGE_WARN_BELOW:
    print(
        f"WARNING: only {priceable} of {len(adj.columns)} symbols have a close "
        f"on {priced_session_date} ({priceable / len(adj.columns):.1%}). The "
        "vendor is still backfilling that session, so the ranking below covers "
        f"{len(rank_df)} names -- thin by data availability, not by defect. "
        "This resolves itself once a fully covered session becomes the last row."
    )

required = {"Symbol", "Score", "Rank", "CMP", "52W High"} | {
    f"{m}M {kind}" for m in (1, 3, 6, 9, 12) for kind in ("Return", "Sharpe")
}
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
# Every row the engine ranked must carry a finite Score and Rank. A fixed floor
# of 700 was a COVERAGE test wearing a corruption test's name -- the exact
# conflation the comment thirty lines above rejects, repeated here and left
# behind when that one was fixed. How many names were priceable is the vendor's
# business and is asserted as a ratio above; that none of them came back NaN is
# this engine's business, and is absolute.
if rank_df.empty:
    raise AssertionError("Ranking produced no rows")
if int(valid.sum()) != len(rank_df):
    raise AssertionError(
        f"{len(rank_df) - int(valid.sum())} of {len(rank_df)} ranked rows carry "
        "a non-finite Score or Rank"
    )
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
    "universe_requested": int(len(idx)),
    "universe_loaded": int(len(idx)),
    "price_series": int(len(adj.columns)),
    "ranked_stocks": int(len(rank_df)),
    # What the coverage assertion actually measured, so a thin run is legible
    # from the artifact rather than only from the console.
    "priced_session": str(priced_session_date),
    "priceable_on_session": priceable,
    "ranked_share_of_priceable": round(len(rank_df) / priceable, 4),
    "vendor_backfill_warning": bool(priceable < COVERAGE_WARN_BELOW),
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
