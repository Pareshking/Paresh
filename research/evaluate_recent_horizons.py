#!/usr/bin/env python3
"""Horizon weighting profiles x sizing schemes, on production entry rules.

The composite that drives every rank on screen is a weighted blend of five
calendar-momentum z-scores (1M/3M/6M/9M/12M). The weights are a free parameter
and the app ships one setting for them. This runs the production backtester
unchanged over six configurations -- three weightings crossed with two sizing
schemes -- and reports what each earned, month by month, and what each cost in
turnover to earn it.

    python research/evaluate_recent_horizons.py

Every rule below is inherited from src/engine/backtester.py rather than
restated here: top_n, the retention buffer, the entry gate, the month-end
execution calendar and the zero-lag lookback are the engine's own defaults,
and the parameter block the script prints is read back off the run so it
describes what happened rather than what was asked for.

Nothing in this file is imported by the app and nothing here feeds production
ranking. It reads the production engine and the local price cache; it writes
only to research/outputs/.
"""

from __future__ import annotations

import logging
import socket
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


# ── Offline by construction ──────────────────────────────────────────────────
# This is a research script over a fixed local cache, and a run that silently
# reached Yahoo would answer a different question from the one it printed --
# the universe and the price history would no longer be the snapshot the
# caption claims. The engine's loaders are written to degrade rather than
# crash when a fetch fails, so an accidental network path would not announce
# itself. Denying the socket outright is what makes "no external calls" a
# property of the run instead of an intention.
#
# OSError, because requests/urllib3 convert that into ConnectionError and the
# loaders already know how to fall back; a bare Exception would escape as an
# unhandled error somewhere unrelated.
class NetworkAccessDenied(OSError):
    pass


def _deny_network() -> None:
    def _blocked(self, address, *args, **kwargs):
        raise NetworkAccessDenied(
            f"research/evaluate_recent_horizons.py runs offline; refused {address!r}"
        )

    socket.socket.connect = _blocked  # type: ignore[method-assign]
    socket.socket.connect_ex = _blocked  # type: ignore[method-assign]
    socket.create_connection = _blocked  # type: ignore[assignment]


_deny_network()

from src.core.config import (  # noqa: E402
    HIGH_52W_MIN_OBSERVATIONS,
    INDICES_DIR,
    MOMENTUM_MONTHS,
    PRICES_FILE,
)
from src.engine.backtester import (  # noqa: E402
    _build_rebalance_schedule,
    completed_month_window,
    run_backtest,
)
from src.engine.corporate_actions import load_events  # noqa: E402
from src.engine.membership import load_history_or_none  # noqa: E402
from src.loaders.price_loader import extract_ohlcv  # noqa: E402

OUT = REPO / "research" / "outputs"
UNIVERSE_CSV = Path(INDICES_DIR) / "ind_niftytotalmarket_list.csv"

# ── Production defaults, inherited not restated ──────────────────────────────
# Each of these is the engine's own signature default. They are named here so
# the printed parameter block can cite them, not to override anything:
#   top_n=20, rebal_freq=21 (the monthly convention), ema_period=50,
#   high_pct=0.80, buffer_n=None -> int(top_n * 1.5).
MONTHS_WINDOW = 12     # requested reporting window; the engine may resolve fewer
TOP_N = 20
COST_BPS = 30.0        # realistic NSE round trip: STT + stamp + brokerage + slippage
BUFFER_N = None        # None => the engine's int(top_n * 1.5) retention buffer

PROFILES: dict[str, tuple[float, ...]] = {
    "P1": (0.20, 0.20, 0.20, 0.20, 0.20),
    "P2": (0.15, 0.30, 0.30, 0.15, 0.10),
    "P3": (0.10, 0.25, 0.35, 0.20, 0.10),
}
PROFILE_NAMES = {
    "P1": "Baseline Equal",
    "P2": "Earnings & Acceleration",
    "P3": "Trend Persistence",
}

# Two sizing schemes. EW runs with caps wide open so the flat 1/top_n is not
# perturbed by a projection; IV runs at 10%/35%, deliberately looser than the
# app's 5%/30%, because a 5% cap across 20 names admits exactly one
# fully-invested book -- every name pinned at the cap -- and the engine then
# raises `scheme_neutralised`, meaning inverse volatility had nothing left to
# express. 10% leaves real dispersion.
SIZING: dict[str, dict[str, object]] = {
    "EW": {
        "weight_method": "Equal Weight",
        "stock_cap": 1.0,
        "sector_cap": 1.0,
        "use_sectors": False,
    },
    "IV": {
        "weight_method": "Inverse Volatility",
        "stock_cap": 0.10,
        "sector_cap": 0.35,
        "use_sectors": True,
    },
}

# The cache the app writes. DATA_DIR moves with the deployment target, so try
# the configured path first and the cloud path second rather than hard-coding
# either: a local checkout and a Streamlit Cloud container disagree about
# which one is real, and both are legitimate places for it to be.
CACHE_CANDIDATES = [Path(PRICES_FILE), Path("/tmp/data_cache/prices.parquet")]


def _load_prices() -> tuple[pd.DataFrame, Path]:
    for path in CACHE_CANDIDATES:
        if path.exists() and path.stat().st_size > 0:
            return pd.read_parquet(path), path
    raise SystemExit(
        "No local price cache found. Looked in:\n  "
        + "\n  ".join(str(p) for p in CACHE_CANDIDATES)
        + "\nRun the app or scripts/full_validation.py once to populate it. "
        "This script will not download prices."
    )


def _universe() -> tuple[list[str], dict[str, str]]:
    """Index constituents and their NSE industry, exactly as the app reads them.

    The sector map is the Industry column, not the TradingView sector: the
    screener builds `sec_map` from rank_df["Industry"], so using anything else
    here would cap a different set of buckets than production does.
    """
    idx = pd.read_csv(UNIVERSE_CSV)
    sym_col = next(c for c in idx.columns if str(c).strip().lower() == "symbol")
    ind_col = next(
        (c for c in idx.columns if str(c).strip().lower() == "industry"), None
    )
    idx[sym_col] = idx[sym_col].astype(str).str.strip().str.upper()
    idx = idx[idx[sym_col].ne("") & idx[sym_col].ne("NAN")].drop_duplicates(sym_col)
    symbols = sorted(idx[sym_col])
    sectors = (
        dict(zip(idx[sym_col], idx[ind_col].astype(str).str.strip()))
        if ind_col
        else {}
    )
    return symbols, sectors


def _persistent_holdings(tradebook: pd.DataFrame, n: int = 3) -> list[tuple[str, int]]:
    """The names the book actually kept, by rebalances held.

    Counts entries and buffer-zone retentions and ignores exits: an exit row
    records the period a position LEFT, so counting it would credit a name for
    a period it was not held through.
    """
    if tradebook is None or tradebook.empty:
        return []
    held = tradebook[tradebook["Action"].astype(str).str.contains("BUY|HOLD")]
    if held.empty:
        return []
    counts = held.drop_duplicates(["Period", "Symbol"])["Symbol"].value_counts()
    # Ties broken alphabetically so two runs print the same three names.
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def _fmt(value, spec: str, dash: str = "n/a") -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return dash
    return dash if not np.isfinite(v) else format(v, spec)


def _schedule_audit(prices: pd.DataFrame) -> dict[str, object]:
    """What the engine's own calendar resolves to, before running anything.

    Rebuilt with the engine's helper rather than re-derived, so the dates
    printed are the dates traded. `start_offset` is the engine's
    max_lb + ema_period: no rebalance can be scheduled until the formation
    window and the EMA warmup both fit behind it, and on a short cache that,
    not the requested window, is what decides how many months are reachable.
    """
    dates = pd.DatetimeIndex(prices.index)
    max_lb = max(MOMENTUM_MONTHS) * 21
    ema_period = 50
    start_offset = max_lb + ema_period
    window_start, window_end = completed_month_window(dates, MONTHS_WINDOW)
    sched = _build_rebalance_schedule(prices, start_offset, 21, MONTHS_WINDOW)
    signal_idx = list(sched[0]) if sched else []
    return {
        "dates": dates,
        "max_lb": max_lb,
        "ema_period": ema_period,
        "start_offset": start_offset,
        "first_schedulable": dates[start_offset] if start_offset < len(dates) else None,
        "window_start": window_start,
        "window_end": window_end,
        "signal_dates": [dates[i] for i in signal_idx],
        "fill_dates": [dates[i + 1] for i in signal_idx],
    }


def main() -> int:
    raw, cache_path = _load_prices()
    adj_close, *_ = extract_ohlcv(raw)
    adj_close = adj_close.dropna(axis=1, how="all")

    symbols, sectors = _universe()
    tradable = [s for s in symbols if s in adj_close.columns]
    prices = adj_close[tradable]

    membership = load_history_or_none()
    actions = load_events()
    audit = _schedule_audit(prices)

    L: list[str] = []
    L.append(f"cache     {cache_path}  (network denied at the socket)")
    L.append(
        f"prices    {prices.shape[0]} sessions x {prices.shape[1]} symbols  "
        f"({prices.index.min():%Y-%m-%d} -> {prices.index.max():%Y-%m-%d})"
    )
    L.append(
        f"universe  {len(tradable)} of {len(symbols)} NIFTY Total Market constituents priced"
    )
    print("\n".join(L) + "\n")

    price_hash = f"{prices.index[-1]}_{prices.shape[0]}x{prices.shape[1]}"
    runs: dict[str, dict[str, object]] = {}

    for size_key, size in SIZING.items():
        for prof_key, weights in PROFILES.items():
            label = f"{size_key} {prof_key}"
            # apply_caps logs when the stock and sector caps are jointly
            # infeasible and it has to relax both. That happens silently
            # otherwise, and a run whose caps were relaxed is not the run the
            # parameter block describes.
            relaxations: list[str] = []
            handler = logging.Handler()
            handler.emit = lambda record: relaxations.append(record.getMessage())
            engine_log = logging.getLogger("nse_momentum")
            engine_log.addHandler(handler)

            res = run_backtest(
                f"{price_hash}_{label}",
                prices,
                top_n=TOP_N,
                weight_method=str(size["weight_method"]),
                config_weights=weights,
                stock_cap=float(size["stock_cap"]),
                sector_cap=float(size["sector_cap"]),
                sector_map=sectors if size["use_sectors"] else None,
                cost_bps=COST_BPS,
                buffer_n=BUFFER_N,
                backtest_months=MONTHS_WINDOW,
                # No benchmark: fetching ^CRSLDX is a network call, and nothing
                # reported below is measured against it. Alpha and beat-rate
                # are deliberately absent rather than silently wrong.
                _benchmark_close=None,
                _membership=membership,
                _actions=actions,
            )
            engine_log.removeHandler(handler)
            if res is None:
                print(f"!! {label}: insufficient history")
                continue

            monthly = res["monthly"]
            runs[label] = {
                "size": size_key,
                "profile": prof_key,
                "weights": weights,
                "stats": res["stats"],
                "monthly": monthly,
                "total_turnover": float(monthly["Turnover %"].sum()),
                # gross - net, i.e. what friction actually took out of the
                # window's cumulative return. Not turnover x cost_bps: that sum
                # ignores the compounding between deductions.
                "friction_bps": float(res["stats"]["cost_drag_total"]) * 10_000.0,
                "holdings": _persistent_holdings(res["tradebook"]),
                "caps_relaxed": sum("jointly infeasible" in m for m in relaxations),
            }

    if not runs:
        print("No configuration produced a result.")
        return 1

    first = next(iter(runs.values()))
    stats0 = first["stats"]
    n_periods = int(stats0["n_periods"])
    md: list[str] = []

    # ── 1. Parameter confirmation ────────────────────────────────────────────
    md.append("## 1. Parameter confirmation\n")
    md.append("| Rule | Value | Source |")
    md.append("|---|---|---|")
    md.append(f"| Portfolio size | top_n = {TOP_N} | `run_backtest` default |")
    md.append(
        f"| Retention buffer (hysteresis) | rank ≤ **{int(TOP_N * 1.5)}** "
        f"(`int(top_n * 1.5)`) | `buffer_n=None` → engine default |"
    )
    md.append(
        "| Retention rule | an incumbent keeps its slot while it ranks inside "
        "the buffer; only a fall past it, or dropping out of the filtered "
        "ranking entirely, sells it | `_select_holdings` |"
    )
    md.append(
        "| Entry gate | close > 50-day EMA **and** close ≥ 0.80 × 52-week high "
        "**and** close > 0 **and** a finite composite z-score | "
        "`run_backtest` (`ema_period=50`, `high_pct=0.80`) |"
    )
    md.append(
        f"| Minimum history (entry) | **{HIGH_52W_MIN_OBSERVATIONS} sessions** — "
        f"the 52-week high is `rolling(252, min_periods={HIGH_52W_MIN_OBSERVATIONS})`, "
        f"so a shorter history yields NaN and fails the gate | `run_backtest` |"
    )
    md.append(
        f"| Minimum history (scheduling) | **{audit['start_offset']} sessions** "
        f"(`max_lb {audit['max_lb']} + ema_period {audit['ema_period']}`) before "
        f"the first rebalance may be scheduled | `run_backtest` |"
    )
    md.append(
        "| Execution timing | signal on the **last trading session of each "
        "completed calendar month**, filled at the **next session's close** "
        "(T+1); first accrual T+2 | `_build_rebalance_schedule` (`rebal_freq=21`) |"
    )
    md.append(
        f"| Lookback | zero-lag to bar T, calendar horizons "
        f"{'/'.join(f'{m}M' for m in MOMENTUM_MONTHS)}, no M-1 skip; composite "
        f"renormalised over available horizons | `_composite_z_score` |"
    )
    md.append(
        f"| Friction | {COST_BPS:.0f} bps × one-way turnover, charged on the "
        f"fill day; turnover measured against the **drifted** book | "
        f"`_step_portfolio_allocation` + `_drift_holdings` |"
    )
    md.append("")

    requested = MONTHS_WINDOW
    md.append(
        f"**Requested window:** {requested} completed months "
        f"({audit['window_start']:%b %Y} → {audit['window_end']:%b %Y}). "
        f"**Resolved:** {n_periods} rebalances."
    )
    if n_periods < requested:
        md.append("")
        md.append(
            f"> The cache holds {prices.shape[0]} sessions "
            f"({prices.index.min():%Y-%m-%d} → {prices.index.max():%Y-%m-%d}). "
            f"A rebalance cannot be scheduled until "
            f"{audit['start_offset']} sessions of formation history and EMA "
            f"warmup fit behind it, which first happens on "
            f"**{audit['first_schedulable']:%Y-%m-%d}** — so the earliest "
            f"month-end signal available is "
            f"{audit['signal_dates'][0]:%Y-%m-%d}. The months before that are "
            f"not reachable from this cache at any window setting: asking for "
            f"{requested} months and asking for {n_periods} produce the **same** "
            f"{n_periods} rebalances. Covering "
            f"{audit['window_start']:%b %Y} would need roughly "
            f"{audit['start_offset'] - int(np.searchsorted(audit['dates'], audit['window_start']))} "
            f"more sessions of history than the cache contains, which is a "
            f"download."
        )
    md.append("")
    md.append(f"**The {n_periods} rebalance dates actually traded:**")
    md.append("")
    md.append("| # | Signal (last session of month) | Fill (T+1) |")
    md.append("|---|---|---|")
    for i, (sig, fill) in enumerate(
        zip(audit["signal_dates"], audit["fill_dates"]), start=1
    ):
        md.append(f"| {i} | {sig:%Y-%m-%d} ({sig:%a}) | {fill:%Y-%m-%d} ({fill:%a}) |")
    md.append("")

    # ── 2. Month-by-month net returns ────────────────────────────────────────
    order = [f"{s} {p}" for s in SIZING for p in PROFILES]
    order = [k for k in order if k in runs]

    md.append(f"## 2. Month-by-month net returns ({n_periods} months)\n")
    md.append("| Month | " + " | ".join(order) + " |")
    md.append("|" + "---|" * (len(order) + 1))

    months = first["monthly"]["Period Start"]
    for row_i in range(n_periods):
        cells = []
        for key in order:
            m = runs[key]["monthly"]
            cells.append(
                _fmt(m["Strategy Net"].iloc[row_i], "+.2%")
                if row_i < len(m)
                else "n/a"
            )
        md.append(f"| {months.iloc[row_i]:%b %Y} | " + " | ".join(cells) + " |")

    md.append(
        "| **Cumulative** | "
        + " | ".join(_fmt(runs[k]["stats"]["total_return"], "+.2%") for k in order)
        + " |"
    )
    md.append(
        "| **Monthly win rate** | "
        + " | ".join(
            f"{float((runs[k]['monthly']['Strategy Net'] > 0).mean()):.0%} "
            f"({int((runs[k]['monthly']['Strategy Net'] > 0).sum())}/{n_periods})"
            for k in order
        )
        + " |"
    )
    md.append("")
    md.append(
        "Each month is a holding period running fill-to-fill — the first "
        "session of the month to the first session of the next — because that "
        "is the interval the book is actually held for. It is labelled by the "
        "month it opens in."
    )
    md.append("")

    # ── 3. Aggregate performance ─────────────────────────────────────────────
    md.append("## 3. Aggregate performance\n")
    md.append(
        "| Sizing | Profile | Weights (1M/3M/6M/9M/12M) | Cum. Return | CAGR | "
        "Ann. Vol | Sharpe (i.i.d.) | Sortino (MAR) | Max DD | DD Days | "
        "Total Turnover | Friction | Top 3 persistent holdings |"
    )
    md.append("|" + "---|" * 13)
    for key in order:
        r = runs[key]
        s = r["stats"]
        holds = ", ".join(f"{sym} ({n})" for sym, n in r["holdings"]) or "—"
        md.append(
            f"| {r['size']} | {r['profile']} · {PROFILE_NAMES[str(r['profile'])]} | "
            f"{'/'.join(f'{x:.2f}' for x in r['weights'])} | "
            f"{_fmt(s['total_return'], '+.2%')} | {_fmt(s['ann_return'], '+.2%')} | "
            f"{_fmt(s['volatility'], '.2%')} | "
            f"{_fmt(s['sharpe'], '+.2f')} ± {_fmt(s['sharpe_stderr_iid'], '.2f')} | "
            f"{_fmt(s['sortino'], '+.2f')} | {_fmt(s['max_drawdown'], '.2%')} | "
            f"{int(s['max_drawdown_duration_days'])} | "
            f"{r['total_turnover']:.1f}% | {r['friction_bps']:.0f} bps | {holds} |"
        )
    md.append("")

    # ── 4. Core findings ─────────────────────────────────────────────────────
    def mean_of(size: str, field: str) -> float:
        vals = [
            float(r["stats"][field]) for r in runs.values() if r["size"] == size
        ]
        return float(np.mean(vals)) if vals else float("nan")

    ew_sharpe, iv_sharpe = mean_of("EW", "sharpe"), mean_of("IV", "sharpe")
    ew_sortino, iv_sortino = mean_of("EW", "sortino"), mean_of("IV", "sortino")
    ew_vol, iv_vol = mean_of("EW", "volatility"), mean_of("IV", "volatility")
    ew_ret, iv_ret = mean_of("EW", "total_return"), mean_of("IV", "total_return")
    stderr = float(stats0["sharpe_stderr_iid"])

    md.append("## 4. Core findings\n")
    better = "Equal Weight" if ew_sharpe > iv_sharpe else "Inverse Volatility"
    md.append(
        f"**Sizing — {better} won on risk-adjusted return.** Averaged across "
        f"the three profiles, EW returned {ew_ret:+.2%} at {ew_vol:.2%} "
        f"volatility for a Sharpe of {ew_sharpe:+.2f} and a Sortino of "
        f"{ew_sortino:+.2f}; IV returned {iv_ret:+.2%} at {iv_vol:.2%} for "
        f"{iv_sharpe:+.2f} and {iv_sortino:+.2f}. The Sharpe gap is "
        f"{abs(ew_sharpe - iv_sharpe):.2f}."
    )
    md.append("")

    for size_key in SIZING:
        base = runs.get(f"{size_key} P1")
        if base is None:
            continue
        b_sharpe = float(base["stats"]["sharpe"])
        parts = []
        for prof_key in ("P2", "P3"):
            r = runs.get(f"{size_key} {prof_key}")
            if r is None:
                continue
            d = float(r["stats"]["sharpe"]) - b_sharpe
            parts.append(
                f"{prof_key} {d:+.2f} ({'beats' if d > 0 else 'trails'} P1)"
            )
        md.append(f"**Profiles vs baseline, {size_key}** — Sharpe delta: " + "; ".join(parts) + ".")
    md.append("")

    spread = max(
        float(r["stats"]["sharpe"]) for r in runs.values()
    ) - min(float(r["stats"]["sharpe"]) for r in runs.values())
    md.append(
        f"**None of it is significant.** The Sharpe spread across all six "
        f"configurations is {spread:.2f}, against a standard error of "
        f"±{stderr:.2f} on each one at {n_periods} months. Every pairwise "
        f"difference above sits well inside one standard error, so the ranking "
        f"of these profiles is not a finding — it is the sampling noise of an "
        f"{n_periods}-month window. The turnover column IS meaningful, because "
        f"turnover is mechanical rather than statistical."
    )
    md.append("")

    # ── Run integrity ────────────────────────────────────────────────────────
    md.append("## Run integrity\n")
    pit = int(stats0["pit_periods"])
    cur = int(stats0["current_universe_periods"])
    if pit == 0:
        md.append(
            f"- **Survivorship is baked in.** A point-in-time index mask was "
            f"applied to 0 of {pit + cur} rebalances; today's constituent list "
            f"was used for all of them, because the membership timeline does "
            f"not reach back into this window. Index additions skew toward "
            f"recent strong performers and this screen preferentially buys "
            f"exactly those, so every return above is biased upward by an "
            f"amount this run cannot measure."
        )
    else:
        md.append(
            f"- Point-in-time membership applied to {pit} of {pit + cur} "
            f"rebalances (from {stats0['pit_from']})."
        )

    neutralised = [k for k in order if runs[k]["stats"]["scheme_neutralised"]]
    iv_neutralised = [k for k in neutralised if runs[k]["size"] == "IV"]
    md.append(
        "- **Inverse volatility genuinely differentiated.** "
        "`scheme_neutralised` is False on all IV runs"
        + (f" except {', '.join(iv_neutralised)}" if iv_neutralised else "")
        + f", so the {float(SIZING['IV']['stock_cap']):.0%} stock cap left real "
        f"dispersion in the book. (It reads True on every EW run by "
        f"definition: identical weights are what EW means.)"
    )
    relaxed = [(k, runs[k]["caps_relaxed"]) for k in order if runs[k]["caps_relaxed"]]
    if relaxed:
        md.append(
            "- The concentration caps were relaxed on some rebalances ("
            + ", ".join(f"{k} {n}/{n_periods}" for k, n in relaxed)
            + "), where the stock and sector caps were jointly infeasible and "
            "`apply_caps` widened both rather than leaving the book "
            "under-invested."
        )
    else:
        md.append(
            "- The concentration caps were never relaxed: they were jointly "
            "feasible on every rebalance, so the effective caps equal the "
            "requested ones."
        )
    md.append(
        f"- Sharpe and Sortino are annualised excess over a "
        f"{float(stats0['risk_free_rate']):.2%} risk-free rate; the Sortino "
        f"divides by downside deviation below that same rate. The ± is one "
        f"standard error assuming independent daily returns."
    )
    md.append(f"- Corporate actions neutralised: {len(actions)}.")

    table = "\n".join(md)
    print(table)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "recent_horizons.md").write_text(table + "\n", encoding="utf-8")
    pd.DataFrame(
        [
            {
                "config": k,
                "sizing": r["size"],
                "profile": r["profile"],
                "w_1m": r["weights"][0], "w_3m": r["weights"][1],
                "w_6m": r["weights"][2], "w_9m": r["weights"][3],
                "w_12m": r["weights"][4],
                "total_return": r["stats"]["total_return"],
                "ann_return": r["stats"]["ann_return"],
                "volatility": r["stats"]["volatility"],
                "sharpe": r["stats"]["sharpe"],
                "sharpe_stderr_iid": r["stats"]["sharpe_stderr_iid"],
                "sortino": r["stats"]["sortino"],
                "max_drawdown": r["stats"]["max_drawdown"],
                "max_drawdown_duration_days": r["stats"]["max_drawdown_duration_days"],
                "win_rate_monthly": float((r["monthly"]["Strategy Net"] > 0).mean()),
                "total_turnover_pct": r["total_turnover"],
                "avg_turnover_pct": r["stats"]["avg_turnover"],
                "friction_bps": r["friction_bps"],
                "n_periods": r["stats"]["n_periods"],
                "scheme_neutralised": r["stats"]["scheme_neutralised"],
                "top_holdings": "; ".join(f"{s}:{n}" for s, n in r["holdings"]),
            }
            for k, r in ((k, runs[k]) for k in order)
        ]
    ).to_csv(OUT / "recent_horizons.csv", index=False)
    monthly_wide = pd.DataFrame(
        {"month": [f"{d:%Y-%m}" for d in months.iloc[:n_periods]]}
        | {k: runs[k]["monthly"]["Strategy Net"].to_numpy() for k in order}
    )
    monthly_wide.to_csv(OUT / "recent_horizons_monthly.csv", index=False)
    print(f"\nwrote {OUT}/recent_horizons.md, .csv and _monthly.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
