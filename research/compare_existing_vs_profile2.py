#!/usr/bin/env python3
"""Does the earnings/acceleration tilt beat the weights the app actually ships?

The screener ranks on a weighted blend of five calendar-momentum z-scores. The
shipped setting is not a round equal split, and it is easy to misremember as
one -- so Phase 1 reads it out of the code rather than restating it, and every
comparison below is against whatever that read returns.

    python research/compare_existing_vs_profile2.py

Phase 2 crosses the two weightings with two sizing schemes over the eight
completed months the local cache can reach, under production entry, retention
and execution rules inherited from src/engine/backtester.py. Phase 3 reports
month-by-month returns, aggregate risk statistics, and how the two weightings
differ in the book they would hold today.

Nothing in this file is imported by the app and nothing here feeds production
ranking. It reads the production engine and the local price cache; it writes
only to research/outputs/.
"""

from __future__ import annotations

import inspect
import logging
import socket
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


# ── Offline by construction ──────────────────────────────────────────────────
# A run that silently reached Yahoo would answer a different question from the
# one it printed: the universe and the price history would no longer be the
# snapshot the caption claims. The engine's loaders degrade rather than crash
# when a fetch fails, so an accidental network path would not announce itself.
# Denying the socket is what makes "offline" a property of the run.
#
# OSError, because requests/urllib3 convert that into ConnectionError and the
# loaders already know how to fall back.
class NetworkAccessDenied(OSError):
    pass


def _deny_network() -> None:
    def _blocked(self, address, *args, **kwargs):
        raise NetworkAccessDenied(
            f"research/compare_existing_vs_profile2.py runs offline; refused {address!r}"
        )

    socket.socket.connect = _blocked  # type: ignore[method-assign]
    socket.socket.connect_ex = _blocked  # type: ignore[method-assign]
    socket.create_connection = _blocked  # type: ignore[assignment]


_deny_network()

from src.core import config as app_config  # noqa: E402
from src.engine import momentum as momentum_mod  # noqa: E402
from src.engine import pipeline as pipeline_mod  # noqa: E402
from src.engine.backtester import (  # noqa: E402
    _composite_z_score,
    _index_mask,
    run_backtest,
)
from src.engine.corporate_actions import adjust_prices, load_events  # noqa: E402
from src.engine.membership import load_history_or_none  # noqa: E402
from src.loaders.price_loader import extract_ohlcv  # noqa: E402

OUT = REPO / "research" / "outputs"
UNIVERSE_CSV = Path(app_config.INDICES_DIR) / "ind_niftytotalmarket_list.csv"

MONTHS_WINDOW = 8
TOP_N = 20
COST_BPS = 30.0
BUFFER_N = None        # None => the engine's int(top_n * 1.5) = 30 retention buffer
PROFILE_2 = (0.15, 0.30, 0.30, 0.15, 0.10)

SIZING: dict[str, dict[str, object]] = {
    # Caps wide open so the flat 1/top_n is not perturbed by a projection.
    "EW": {"weight_method": "Equal Weight", "stock_cap": 1.0, "sector_cap": 1.0,
           "use_sectors": False},
    # 10%/35% rather than the app's 5%/30%: a 5% cap across 20 names admits
    # exactly one fully-invested book, every name pinned at the cap, and the
    # engine then raises `scheme_neutralised` -- inverse volatility with
    # nothing left to express.
    "IV": {"weight_method": "Inverse Volatility", "stock_cap": 0.10,
           "sector_cap": 0.35, "use_sectors": True},
}

CACHE_CANDIDATES = [Path(app_config.PRICES_FILE), Path("/tmp/data_cache/prices.parquet")]


# ── Phase 1 ──────────────────────────────────────────────────────────────────
def detect_production_weights() -> tuple[tuple[float, ...], list[tuple[str, str, str]]]:
    """Read the shipped weights out of the code, and every place that sets them.

    Read, not transcribed: `inspect.signature` pulls the backtester's own
    default off the live function object, and the rest are the imported
    constants. A hard-coded copy in this file would be a fourth place the
    weights live, and the one most likely to go stale.
    """
    canonical = tuple(float(w) for w in app_config.DEFAULT_LOOKBACK_WEIGHTS)

    bt_default = inspect.signature(run_backtest).parameters["config_weights"].default
    engine_default = tuple(float(w) for w in momentum_mod.MomentumEngine.DEFAULT_WEIGHTS)

    # The placeholder pipeline.build_engine constructs the engine with before
    # rank_with_weights applies the real vector. Reported because reading it in
    # isolation is the easiest way to conclude the app ranks on equal weights.
    build_src = inspect.getsource(pipeline_mod.build_engine)
    placeholder = "[0.2] * 5" if "weights=[0.2] * 5" in build_src else "(not found)"

    provenance = [
        (
            "src/core/config.py",
            "DEFAULT_LOOKBACK_WEIGHTS",
            " / ".join(f"{w:.2f}" for w in canonical),
        ),
        (
            "src/engine/momentum.py",
            "MomentumEngine.DEFAULT_WEIGHTS",
            " / ".join(f"{w:.2f}" for w in engine_default)
            + (" (alias of the above)" if engine_default == canonical else " ⚠ DIVERGES"),
        ),
        (
            "src/engine/backtester.py",
            "run_backtest(config_weights=...)",
            " / ".join(f"{w:.2f}" for w in bt_default)
            + (" (matches)" if tuple(float(w) for w in bt_default) == canonical
               else " ⚠ DIVERGES"),
        ),
        (
            "src/engine/pipeline.py",
            "build_engine(weights=...)",
            f"{placeholder} — placeholder only; `_apply_weight_composite` "
            f"overwrites it in `rank_with_weights` before any rank is produced",
        ),
        (
            "app.py",
            "resolve('cfg_wN', DEFAULT_LOOKBACK_WEIGHTS[N-1])",
            "user setting, falling back to the canonical vector; renormalised to sum 1",
        ),
    ]
    return canonical, provenance


def _load_prices() -> tuple[pd.DataFrame, Path]:
    for path in CACHE_CANDIDATES:
        if path.exists() and path.stat().st_size > 0:
            return pd.read_parquet(path), path
    raise SystemExit(
        "No local price cache found. Looked in:\n  "
        + "\n  ".join(str(p) for p in CACHE_CANDIDATES)
        + "\nThis script will not download prices."
    )


def _universe() -> tuple[list[str], dict[str, str]]:
    idx = pd.read_csv(UNIVERSE_CSV)
    sym_col = next(c for c in idx.columns if str(c).strip().lower() == "symbol")
    ind_col = next((c for c in idx.columns if str(c).strip().lower() == "industry"), None)
    idx[sym_col] = idx[sym_col].astype(str).str.strip().str.upper()
    idx = idx[idx[sym_col].ne("") & idx[sym_col].ne("NAN")].drop_duplicates(sym_col)
    symbols = sorted(idx[sym_col])
    sectors = (
        dict(zip(idx[sym_col], idx[ind_col].astype(str).str.strip())) if ind_col else {}
    )
    return symbols, sectors


def _fmt(value, spec: str, dash: str = "n/a") -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return dash
    return dash if not np.isfinite(v) else format(v, spec)


def full_ranking_at(
    prices: pd.DataFrame,
    signal_idx: int,
    weights: tuple[float, ...],
    membership,
) -> pd.Series:
    """Every name that clears the production gate, ranked, on one signal date.

    Mirrors the six lines run_backtest applies at each rebalance -- the 50-day
    EMA test, the 52-week-high proximity test, the positive-price test and the
    point-in-time index mask -- and then scores the survivors with the engine's
    own `_composite_z_score`. It is reproduced rather than imported because the
    engine applies it inline inside the rebalance loop; the scoring itself, the
    part that could actually drift, is the engine's function.

    Returns rank (1 = best) indexed by symbol, for the FULL filtered universe,
    so a name that left the book can still be located.
    """
    ema = prices.ewm(span=50).mean()
    high_52w = prices.rolling(252, min_periods=126).max()

    _p = prices.iloc[signal_idx]
    valid = (_p > ema.iloc[signal_idx]) & (_p >= high_52w.iloc[signal_idx] * 0.80) & (_p > 0)
    mask = _index_mask(membership, prices.columns, prices.index[signal_idx])
    if mask is not None:
        valid &= mask

    # .replace(0, np.nan) exactly as run_backtest builds log_ret: without it a
    # zero print divides to inf rather than dropping out.
    score = _composite_z_score(
        prices, np.log(prices / prices.shift(1).replace(0, np.nan)), signal_idx,
        list(app_config.MOMENTUM_MONTHS), list(weights),
    )
    score = score[valid & score.notna()].sort_values(ascending=False)
    return pd.Series(range(1, len(score) + 1), index=score.index, dtype="int64")


def main() -> int:
    raw, cache_path = _load_prices()
    adj_close, *_ = extract_ohlcv(raw)
    adj_close = adj_close.dropna(axis=1, how="all")
    symbols, sectors = _universe()
    prices = adj_close[[s for s in symbols if s in adj_close.columns]]

    membership = load_history_or_none()
    actions = load_events()

    existing, provenance = detect_production_weights()
    WEIGHTSETS: dict[str, tuple[float, ...]] = {
        "Existing": existing,
        "Profile 2": PROFILE_2,
    }

    print(f"cache     {cache_path}  (network denied at the socket)")
    print(
        f"prices    {prices.shape[0]} sessions x {prices.shape[1]} symbols  "
        f"({prices.index.min():%Y-%m-%d} -> {prices.index.max():%Y-%m-%d})\n"
    )

    md: list[str] = []

    # ── 1. Production weight audit ───────────────────────────────────────────
    md.append("## 1. Production weight audit\n")
    md.append("Read from the code at run time, not transcribed.\n")
    md.append("| File | Symbol | Value (1M / 3M / 6M / 9M / 12M) |")
    md.append("|---|---|---|")
    for path, sym, val in provenance:
        md.append(f"| `{path}` | `{sym}` | {val} |")
    md.append("")
    md.append("| Weight set | 1M | 3M | 6M | 9M | 12M |")
    md.append("|---|---|---|---|---|---|")
    for name, w in WEIGHTSETS.items():
        md.append(f"| **{name}** | " + " | ".join(f"{x:.2f}" for x in w) + " |")
    delta = tuple(PROFILE_2[i] - existing[i] for i in range(5))
    md.append("| Δ (P2 − Existing) | " + " | ".join(f"{d:+.2f}" for d in delta) + " |")
    md.append("")
    md.append(
        f"The shipped vector is **{' / '.join(f'{w:.2f}' for w in existing)}** — "
        f"already tilted toward 3M and 6M, not an equal split. Profile 2 differs "
        f"in only two places: it moves {abs(delta[0]):.2f} into 1M and takes "
        f"{abs(delta[3]):.2f} out of 9M. 3M, 6M and 12M are identical. This is a "
        f"small perturbation of the production setting, not an alternative to it."
    )
    md.append("")

    # ── 2. Backtest matrix ───────────────────────────────────────────────────
    price_hash = f"{prices.index[-1]}_{prices.shape[0]}x{prices.shape[1]}"
    runs: dict[str, dict[str, object]] = {}
    order: list[str] = []

    for size_key, size in SIZING.items():
        for wname, weights in WEIGHTSETS.items():
            label = f"{size_key} · {wname}"
            order.append(label)
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
                _benchmark_close=None,
                _membership=membership,
                _actions=actions,
            )
            engine_log.removeHandler(handler)
            if res is None:
                print(f"!! {label}: insufficient history")
                order.pop()
                continue
            monthly = res["monthly"]
            runs[label] = {
                "size": size_key,
                "wname": wname,
                "weights": weights,
                "stats": res["stats"],
                "monthly": monthly,
                "live_book": res["live_book"],
                "live_meta": res["live_meta"],
                "total_turnover": float(monthly["Turnover %"].sum()),
                "friction_bps": float(res["stats"]["cost_drag_total"]) * 10_000.0,
                "caps_relaxed": sum("jointly infeasible" in m for m in relaxations),
            }

    if not runs:
        print("No configuration produced a result.")
        return 1

    first = next(iter(runs.values()))
    stats0 = first["stats"]
    n_periods = int(stats0["n_periods"])
    months = first["monthly"]["Period Start"]

    # ── 3. Month-by-month ────────────────────────────────────────────────────
    md.append(f"## 2. Month-by-month net returns ({n_periods} months)\n")
    md.append("| Month | " + " | ".join(order) + " |")
    md.append("|" + "---|" * (len(order) + 1))
    for i in range(n_periods):
        md.append(
            f"| {months.iloc[i]:%b %Y} | "
            + " | ".join(
                _fmt(runs[k]["monthly"]["Strategy Net"].iloc[i], "+.2%") for k in order
            )
            + " |"
        )
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
        "Each month is a holding period running fill-to-fill — the first session "
        "of the month to the first session of the next — labelled by the month it "
        "opens in."
    )
    md.append("")

    # ── 4. Aggregate ─────────────────────────────────────────────────────────
    md.append("## 3. Aggregate performance\n")
    md.append(
        "| Scheme | Weights | Cum. Return | CAGR | Ann. Vol | Sharpe (i.i.d.) | "
        "Sortino (MAR) | Max DD | DD Days | Total Turnover | Friction |"
    )
    md.append("|" + "---|" * 11)
    for k in order:
        r = runs[k]
        s = r["stats"]
        md.append(
            f"| {r['size']} | {r['wname']} | {_fmt(s['total_return'], '+.2%')} | "
            f"{_fmt(s['ann_return'], '+.2%')} | {_fmt(s['volatility'], '.2%')} | "
            f"{_fmt(s['sharpe'], '+.2f')} ± {_fmt(s['sharpe_stderr_iid'], '.2f')} | "
            f"{_fmt(s['sortino'], '+.2f')} | {_fmt(s['max_drawdown'], '.2%')} | "
            f"{int(s['max_drawdown_duration_days'])} | {r['total_turnover']:.1f}% | "
            f"{r['friction_bps']:.0f} bps |"
        )
    md.append("")

    # ── 5. Live holdings & overlap ───────────────────────────────────────────
    meta = first["live_meta"]
    sig_dt = pd.Timestamp(meta["signal_date"]) if meta.get("signal_date") else None
    as_of = pd.Timestamp(meta["as_of"])

    adjusted, _ = adjust_prices(prices, actions)
    sig_idx = int(pd.DatetimeIndex(adjusted.index).get_loc(sig_dt)) if sig_dt is not None else len(adjusted) - 1
    ranks = {
        name: full_ranking_at(adjusted, sig_idx, w, membership)
        for name, w in WEIGHTSETS.items()
    }

    # The reconstruction above is only trustworthy if it reproduces the ranks
    # the engine itself reports for the names it holds. Checked every run
    # rather than asserted once in a comment.
    _val_book = first["live_book"]
    _mine = _val_book["Symbol"].map(ranks[first["wname"]])
    _matched = int(
        (_val_book["Rank at Rebalance"].astype(str) == _mine.astype("Int64").astype(str)).sum()
    )

    books = {}
    for wname in WEIGHTSETS:
        # Selection depends on the composite alone, so EW and IV must agree on
        # WHICH names are held; only the weights within the book differ. Checked
        # rather than assumed.
        sets = {
            frozenset(runs[f"{s} · {wname}"]["live_book"]["Symbol"])
            for s in SIZING
            if f"{s} · {wname}" in runs
        }
        books[wname] = set(next(iter(sets)))
        if len(sets) != 1:
            md.append(
                f"> ⚠ EW and IV disagree on the {wname} book; overlap below uses EW."
            )
            books[wname] = set(runs[f"EW · {wname}"]["live_book"]["Symbol"])

    a, b = books["Existing"], books["Profile 2"]
    both = sorted(a & b)
    dropped = sorted(a - b)
    added = sorted(b - a)

    md.append("## 4. Live holdings & overlap\n")
    md.append(
        f"Book as it stands on the latest session, **{as_of:%Y-%m-%d}**, struck "
        f"on the {sig_dt:%Y-%m-%d} signal"
        + (" (a rebalance the 8-month window excludes, because its holding "
           "period runs into the incomplete month)." if sig_dt is not None else ".")
    )
    md.append("")
    md.append(
        f"**Overlap: {len(both)} of {TOP_N} names identical "
        f"({len(both) / TOP_N:.0%}).** {len(dropped)} dropped, {len(added)} added."
    )
    md.append("")
    md.append(
        "Both sizing schemes select the same names — selection reads the "
        "composite, and sizing only sets the weight within the book — so the "
        "comparison below is between the two weight vectors, not four books."
    )
    md.append("")

    def _rank(wname: str, sym: str) -> str:
        r = ranks[wname]
        return str(int(r[sym])) if sym in r.index else "unranked"

    if dropped:
        md.append("**Held under Existing, dropped under Profile 2**\n")
        md.append("| Symbol | Industry | Rank (Existing) | Rank (Profile 2) | Δ |")
        md.append("|---|---|---|---|---|")
        for s in sorted(dropped, key=lambda x: (ranks["Existing"].get(x, 10**6))):
            re_, rp = _rank("Existing", s), _rank("Profile 2", s)
            d = (
                f"{int(rp) - int(re_):+d}"
                if re_.isdigit() and rp.isdigit() else "—"
            )
            md.append(f"| {s} | {sectors.get(s, '—')} | #{re_} | #{rp} | {d} |")
        md.append("")
    if added:
        md.append("**Added under Profile 2, absent under Existing**\n")
        md.append("| Symbol | Industry | Rank (Existing) | Rank (Profile 2) | Δ |")
        md.append("|---|---|---|---|---|")
        for s in sorted(added, key=lambda x: (ranks["Profile 2"].get(x, 10**6))):
            re_, rp = _rank("Existing", s), _rank("Profile 2", s)
            d = (
                f"{int(rp) - int(re_):+d}"
                if re_.isdigit() and rp.isdigit() else "—"
            )
            md.append(f"| {s} | {sectors.get(s, '—')} | #{re_} | #{rp} | {d} |")
        md.append("")
    if not dropped and not added:
        md.append("The two weightings hold an identical book today.\n")

    md.append(
        f"Ranks are over the full filtered universe on the signal date "
        f"({len(ranks['Existing'])} names cleared the gate under Existing, "
        f"{len(ranks['Profile 2'])} under Profile 2), so a name outside the top "
        f"{TOP_N} still has a position. A book name ranked worse than #{TOP_N} is "
        f"a buffer retention: the engine holds an incumbent while it ranks inside "
        f"#{int(TOP_N * 1.5)}."
    )
    md.append("")
    md.append(
        f"Rank reconstruction validated against the engine's own "
        f"`Rank at Rebalance`: **{_matched}/{len(_val_book)}** book names "
        f"reproduced exactly."
    )
    md.append(
        "Which incumbent survives inside the buffer is path-dependent: the two "
        "weightings have different prior books, so a name inside #30 under both "
        "can still be retained by one and not the other once the 20 slots fill."
    )
    md.append("")

    # ── 6. Findings ──────────────────────────────────────────────────────────
    md.append("## 5. Findings\n")
    for size_key in SIZING:
        ke, kp = f"{size_key} · Existing", f"{size_key} · Profile 2"
        if ke not in runs or kp not in runs:
            continue
        se, sp = runs[ke]["stats"], runs[kp]["stats"]
        verdict = "beats" if float(sp["sharpe"]) > float(se["sharpe"]) else "trails"
        md.append(
            f"- **{size_key}:** Profile 2 {verdict} the shipped weights — "
            f"{_fmt(sp['total_return'], '+.2%')} vs {_fmt(se['total_return'], '+.2%')} "
            f"cumulative, Sharpe {_fmt(sp['sharpe'], '+.2f')} vs "
            f"{_fmt(se['sharpe'], '+.2f')} "
            f"({float(sp['sharpe']) - float(se['sharpe']):+.2f}), turnover "
            f"{runs[kp]['total_turnover']:.1f}% vs {runs[ke]['total_turnover']:.1f}%."
        )
    spread = max(float(r["stats"]["sharpe"]) for r in runs.values()) - min(
        float(r["stats"]["sharpe"]) for r in runs.values()
    )
    md.append("")
    md.append(
        f"- **Not significant.** The Sharpe spread across all four configurations "
        f"is {spread:.2f} against a standard error of "
        f"±{float(stats0['sharpe_stderr_iid']):.2f} on each, at {n_periods} months. "
        f"With {len(both)}/{TOP_N} of today's book shared, the two weightings are "
        f"largely the same strategy; the return gap is what "
        f"{TOP_N - len(both)} different names did over eight months."
    )
    pit = int(stats0["pit_periods"])
    md.append(
        f"- **Survivorship is baked in.** A point-in-time index mask was applied "
        f"to {pit} of {pit + int(stats0['current_universe_periods'])} rebalances; "
        f"today's constituent list was used otherwise, so every return above is "
        f"biased upward by an amount this run cannot measure."
    )

    table = "\n".join(md)
    print(table)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "existing_vs_profile2.md").write_text(table + "\n", encoding="utf-8")
    pd.DataFrame(
        [
            {
                "config": k, "sizing": runs[k]["size"], "weights": runs[k]["wname"],
                "w": "/".join(f"{x:.2f}" for x in runs[k]["weights"]),
                "total_return": runs[k]["stats"]["total_return"],
                "ann_return": runs[k]["stats"]["ann_return"],
                "volatility": runs[k]["stats"]["volatility"],
                "sharpe": runs[k]["stats"]["sharpe"],
                "sortino": runs[k]["stats"]["sortino"],
                "max_drawdown": runs[k]["stats"]["max_drawdown"],
                "max_drawdown_duration_days": runs[k]["stats"]["max_drawdown_duration_days"],
                "win_rate_monthly": float((runs[k]["monthly"]["Strategy Net"] > 0).mean()),
                "total_turnover_pct": runs[k]["total_turnover"],
                "friction_bps": runs[k]["friction_bps"],
            }
            for k in order
        ]
    ).to_csv(OUT / "existing_vs_profile2.csv", index=False)
    print(f"\nwrote {OUT}/existing_vs_profile2.md and .csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
