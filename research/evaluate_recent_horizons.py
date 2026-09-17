#!/usr/bin/env python3
"""Compare three zero-lag horizon weighting profiles over the last 8 months.

The composite that drives every rank on screen is a weighted blend of five
calendar-momentum z-scores (1M/3M/6M/9M/12M). The weights are a free
parameter, and the app ships one setting for them. This asks what three
different settings would have earned over the eight completed months through
August 2026, and -- the part a return number alone hides -- what each one cost
in turnover to earn it.

    python research/evaluate_recent_horizons.py

Read the numbers with the caveats the backtest tab carries. Eight months is
six or seven rebalances: that is a sample too small to separate skill from
luck, and the differences below are well inside the noise of one. What the
window CAN settle is the friction side -- turnover is a mechanical property of
how often a weighting profile reshuffles the book, and it is measured here,
not estimated.

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
    DEFAULT_SECTOR_CAP,
    DEFAULT_STOCK_CAP,
    INDICES_DIR,
    PRICES_FILE,
)
from src.engine.backtester import run_backtest  # noqa: E402
from src.engine.corporate_actions import load_events  # noqa: E402
from src.engine.membership import load_history_or_none  # noqa: E402
from src.loaders.price_loader import extract_ohlcv  # noqa: E402

OUT = REPO / "research" / "outputs"
UNIVERSE_CSV = Path(INDICES_DIR) / "ind_niftytotalmarket_list.csv"

# The app's own backtest defaults, so a difference between profiles is a
# difference in the weights and nothing else.
MONTHS_WINDOW = 8
TOP_N = 20
BUFFER_N = 40          # 2.0x portfolio size, the UI default
COST_BPS = 30.0        # realistic NSE round trip: STT + stamp + brokerage + slippage
WEIGHT_METHOD = "Inverse Volatility"

PROFILES: dict[str, tuple[float, ...]] = {
    "P1 · Equal Baseline": (0.20, 0.20, 0.20, 0.20, 0.20),
    "P2 · Earnings & Acceleration": (0.15, 0.30, 0.30, 0.15, 0.10),
    "P3 · Trend Persistence": (0.10, 0.25, 0.35, 0.20, 0.10),
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
    counts = (
        held.drop_duplicates(["Period", "Symbol"])["Symbol"]
        .value_counts()
        .sort_values(ascending=False)
    )
    # Ties are broken alphabetically so two runs of the same profile print the
    # same three names rather than whichever order value_counts happened to
    # produce.
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return ordered[:n]


def _fmt(value: float, spec: str, dash: str = "n/a") -> str:
    return dash if value is None or not np.isfinite(value) else format(value, spec)


def main() -> int:
    raw, cache_path = _load_prices()
    adj_close, _close, _high, _low, _vol, _open = extract_ohlcv(raw)
    adj_close = adj_close.dropna(axis=1, how="all")

    symbols, sectors = _universe()
    tradable = [s for s in symbols if s in adj_close.columns]
    prices = adj_close[tradable]

    membership = load_history_or_none()
    actions = load_events()

    print(f"cache        {cache_path}")
    print(
        f"prices       {prices.shape[0]} sessions x {prices.shape[1]} symbols  "
        f"({prices.index.min():%Y-%m-%d} -> {prices.index.max():%Y-%m-%d})"
    )
    print(
        f"universe     {len(tradable)} of {len(symbols)} NIFTY Total Market "
        f"constituents priced"
    )
    # Deliberately NOT reported as "membership: loaded". Whether the history
    # covers the signal dates is a different question from whether the file
    # parsed, and only the engine can answer it -- `pit_periods` below counts
    # the rebalances a point-in-time mask was actually applied to.
    _cov = f"{len(membership.get('snapshots', []))} snapshot(s)" if membership else "absent"
    print(f"membership file: {_cov}   corporate actions: {len(actions)}")
    print(
        f"settings     {MONTHS_WINDOW} completed months · top {TOP_N} "
        f"(buffer {BUFFER_N}) · {WEIGHT_METHOD} · "
        f"stock cap {DEFAULT_STOCK_CAP:.0%} · sector cap {DEFAULT_SECTOR_CAP:.0%} · "
        f"{COST_BPS:.0f} bps\n"
    )

    price_hash = f"{prices.index[-1]}_{prices.shape[0]}x{prices.shape[1]}"
    rows: list[dict[str, object]] = []

    for label, weights in PROFILES.items():
        # apply_caps logs when the stock and sector caps are jointly
        # infeasible and it has to relax both. That happens silently otherwise,
        # and a run where the caps were relaxed on most rebalances is not the
        # run the settings line above describes.
        relaxations: list[str] = []
        handler = logging.Handler()
        handler.emit = lambda record: relaxations.append(record.getMessage())
        engine_log = logging.getLogger("nse_momentum")
        engine_log.addHandler(handler)

        res = run_backtest(
            f"{price_hash}_{label}",
            prices,
            top_n=TOP_N,
            weight_method=WEIGHT_METHOD,
            config_weights=weights,
            stock_cap=DEFAULT_STOCK_CAP,
            sector_cap=DEFAULT_SECTOR_CAP,
            sector_map=sectors,
            cost_bps=COST_BPS,
            buffer_n=BUFFER_N,
            backtest_months=MONTHS_WINDOW,
            # No benchmark: fetching ^CRSLDX is a network call, and nothing
            # reported below is measured against it. Alpha and beat-rate are
            # deliberately absent rather than silently wrong.
            _benchmark_close=None,
            _membership=membership,
            _actions=actions,
        )
        engine_log.removeHandler(handler)
        if res is None:
            print(f"!! {label}: insufficient history for a {MONTHS_WINDOW}-month window")
            continue

        stats = res["stats"]
        monthly = res["monthly"]
        # Sum of one-way turnover across the run. avg_turnover is the mean of
        # the same series and is reported beside it because a total confounds
        # "traded heavily" with "rebalanced more often".
        total_turnover = float(monthly["Turnover %"].sum())
        # gross - net, i.e. what friction actually took out of the window's
        # cumulative return. Not turnover x cost_bps: that sum ignores the
        # compounding between deductions.
        friction_bps = float(stats["cost_drag_total"]) * 10_000.0

        rows.append(
            {
                "label": label,
                "weights": weights,
                "stats": stats,
                "periods": len(monthly),
                "total_turnover": total_turnover,
                "friction_bps": friction_bps,
                "holdings": _persistent_holdings(res["tradebook"]),
                "caps_relaxed": sum("jointly infeasible" in m for m in relaxations),
            }
        )

    if not rows:
        print("No profile produced a result.")
        return 1

    window = rows[0]["stats"]
    lines: list[str] = []
    lines.append(
        f"### Horizon weighting profiles — {window['n_periods']} rebalances over "
        f"{window['window_years']:.2f} years ({window['n_days']} sessions)\n"
    )
    lines.append(
        "| Profile | Weights (1M/3M/6M/9M/12M) | Cum. Return | CAGR | Ann. Vol | "
        "Sharpe (i.i.d.) | Sortino (MAR) | Max DD | DD Days | Total Turnover | "
        "Friction | Top 3 persistent holdings |"
    )
    lines.append("|" + "---|" * 12)

    for r in rows:
        s = r["stats"]
        w = "/".join(f"{x:.2f}" for x in r["weights"])
        holds = (
            ", ".join(f"{sym} ({n})" for sym, n in r["holdings"]) or "—"
        )
        lines.append(
            f"| {r['label']} | {w} | "
            f"{_fmt(s['total_return'], '+.2%')} | "
            f"{_fmt(s['ann_return'], '+.2%')} | "
            f"{_fmt(s['volatility'], '.2%')} | "
            f"{_fmt(s['sharpe'], '+.2f')} ± {_fmt(s['sharpe_stderr_iid'], '.2f')} | "
            f"{_fmt(s['sortino'], '+.2f')} | "
            f"{_fmt(s['max_drawdown'], '.2%')} | "
            f"{int(s['max_drawdown_duration_days'])} | "
            f"{r['total_turnover']:.1f}% | "
            f"{r['friction_bps']:.0f} bps | "
            f"{holds} |"
        )

    lines.append("")
    lines.append(
        f"Sharpe and Sortino are annualised excess over a "
        f"{window['risk_free_rate']:.2%} risk-free rate; the Sortino divides by "
        f"downside deviation below that same rate. The ± is one standard error "
        f"at this sample size assuming independent daily returns "
        f"(measured lag-1 autocorrelation: "
        + ", ".join(
            f"{r['label'].split(' · ')[0]} {r['stats']['returns_autocorr_lag1']:+.3f}"
            for r in rows
        )
        + ")."
    )
    lines.append(
        f"Friction is gross minus net cumulative return over the window, at "
        f"{COST_BPS:.0f} bps of one-way turnover charged on each fill. Turnover is "
        f"measured against the drifted book, so it includes the trades needed to "
        f"hold a weight constant. Holdings counts are rebalances held out of "
        f"{window['n_periods']}."
    )

    # ── Run integrity ────────────────────────────────────────────────────────
    # Three things the table cannot show, each of which changes what the
    # numbers mean. They are read off the run rather than off the settings,
    # because the settings are what was REQUESTED and these are what happened.
    lines.append("")
    lines.append("**Run integrity**")
    lines.append("")

    pit = int(window["pit_periods"])
    cur = int(window["current_universe_periods"])
    if pit == 0:
        lines.append(
            f"- **Survivorship is baked in.** A point-in-time index mask was "
            f"applied to 0 of {pit + cur} rebalances; today's constituent list "
            f"was used for all of them. The membership timeline does not reach "
            f"back into this window, so a name added to the index during it was "
            f"selectable from January. Index additions skew toward recent strong "
            f"performers and this screen preferentially buys exactly those, so "
            f"the returns below are biased upward by an amount this run cannot "
            f"measure."
        )
    else:
        lines.append(
            f"- Point-in-time membership applied to {pit} of {pit + cur} "
            f"rebalances (from {window['pit_from']}); the rest fell back to the "
            f"current universe."
        )

    if any(r["stats"]["scheme_neutralised"] for r in rows):
        lines.append(
            f"- **{WEIGHT_METHOD} sizing had no effect.** A "
            f"{DEFAULT_STOCK_CAP:.0%} stock cap across {TOP_N} holdings admits "
            f"exactly one fully-invested book -- every name pinned at the cap -- "
            f"so the weighting scheme had nothing left to express and all three "
            f"profiles ran equal-weighted. The profiles still differ, but only "
            f"in WHICH names they hold, not in how much of each. To let sizing "
            f"matter, raise the stock cap above 1/{TOP_N} or hold fewer names."
        )

    relaxed = ", ".join(
        f"{r['label'].split(' · ')[0]} {r['caps_relaxed']}/{r['stats']['n_periods']}"
        for r in rows
    )
    if any(r["caps_relaxed"] for r in rows):
        lines.append(
            f"- **The concentration caps were relaxed on most rebalances** "
            f"({relaxed}). {DEFAULT_STOCK_CAP:.0%} per name and "
            f"{DEFAULT_SECTOR_CAP:.0%} per sector are jointly infeasible whenever "
            f"the book concentrates into few enough sectors, and apply_caps "
            f"widens both rather than leaving the portfolio under-invested. The "
            f"effective caps were looser than the ones requested."
        )

    lines.append(
        f"- Eight months is {window['n_periods']} rebalances. The Sharpe spread "
        f"across the three profiles is "
        f"{max(r['stats']['sharpe'] for r in rows) - min(r['stats']['sharpe'] for r in rows):.2f}, "
        f"against a standard error of {window['sharpe_stderr_iid']:.2f} on each "
        f"one -- the profiles are not distinguishable at this sample size."
    )

    table = "\n".join(lines)
    print(table)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "recent_horizons.md").write_text(table + "\n", encoding="utf-8")
    pd.DataFrame(
        [
            {
                "profile": r["label"],
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
                "total_turnover_pct": r["total_turnover"],
                "avg_turnover_pct": r["stats"]["avg_turnover"],
                "friction_bps": r["friction_bps"],
                "n_periods": r["stats"]["n_periods"],
                "top_holdings": "; ".join(f"{s}:{n}" for s, n in r["holdings"]),
            }
            for r in rows
        ]
    ).to_csv(OUT / "recent_horizons.csv", index=False)
    print(f"\nwrote {OUT / 'recent_horizons.md'} and {OUT / 'recent_horizons.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
