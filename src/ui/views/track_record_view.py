"""Track Record: the frozen monthly history, month by month, against Nifty 500.

Everything on this tab except the MTD cell is read from data/track_record.json
and is never recomputed here. That is the point of the tab: the Backtest tab
answers "what would this strategy have done", recomputed from live prices every
run; this one answers "what did it post", and that answer must not move because
a price got revised or a slider got nudged.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from src.engine.backtester import run_backtest
from src.engine.track_record import (
    INCEPTION,
    MONTH_LABELS,
    TRACK_RECORD_CONFIG,
    build_grid,
    load_ledger,
    months_to_cover,
    summary_stats,
)
from src.ui.theme import render_saas_table


def _record_mtd(
    adj_close: pd.DataFrame, benchmark_close: pd.Series | None
) -> dict:
    """Month-to-date under the RECORD's configuration, not the Backtest tab's.

    The Backtest tab's sliders are for exploring. If MTD were taken from
    whatever they happen to be set to, the running month would be measured on a
    different strategy from every frozen month beside it, and the year-to-date
    column would silently mix the two. So run the pinned configuration.
    """
    if adj_close is None or adj_close.empty:
        return {}
    as_of = pd.Timestamp(adj_close.index[-1])
    months = months_to_cover(as_of)
    if months <= 0:
        return {}
    cfg = TRACK_RECORD_CONFIG
    result = run_backtest(
        f"trackrec_{as_of:%Y%m%d}_{adj_close.shape[1]}_{months}",
        adj_close,
        top_n=cfg["top_n"],
        rebal_freq=cfg["rebal_freq"],
        ema_period=cfg["ema_period"],
        high_pct=cfg["high_pct"],
        weight_method=cfg["weight_method"],
        config_weights=cfg["config_weights"],
        cost_bps=cfg["cost_bps"],
        buffer_n=cfg["buffer_n"],
        _benchmark_close=benchmark_close,
        backtest_months=months,
    )
    return (result or {}).get("live_meta", {}) or {}


def _pct(v: float | None) -> str:
    return "—" if v is None or pd.isna(v) else f"{v * 100:+.1f}%"


def _grid_display(grid: pd.DataFrame) -> pd.DataFrame:
    if grid.empty:
        return grid
    out = grid.copy()
    for col in out.columns:
        if col == "YEAR":
            out[col] = out[col].astype(int).astype(str)
        else:
            out[col] = out[col].map(_pct)
    return out


def render_track_record_view(
    adj_close: pd.DataFrame | None = None,
    benchmark_close: pd.Series | None = None,
) -> None:
    """Renders the frozen monthly track record with the live MTD beside it."""
    live_meta = _record_mtd(adj_close, benchmark_close) if adj_close is not None else {}
    try:
        ledger = load_ledger()
    except (ValueError, OSError) as exc:
        # A corrupt ledger is reported, never silently replaced with an empty
        # one -- that would present "no history" as a fact.
        st.error(f"Track record could not be read: {exc}")
        return

    months = ledger.get("months", {})
    lm = live_meta or {}
    mtd_val = lm.get("strategy_mtd")
    mtd_bench = lm.get("benchmark_mtd")
    mtd_period = pd.Period(lm["mtd_period"], freq="M") if lm.get("mtd_period") else None

    st.markdown(
        f"""
        <div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:7px 14px;margin-bottom:12px;font-family:IBM Plex Mono;font-size:0.76rem;color:#475569;display:flex;flex-wrap:wrap;gap:14px;align-items:center;'>
            <span>📒 <strong>Record:</strong> <span style='color:#0f172a;font-weight:600;'>{len(months)} frozen month(s) from {INCEPTION}</span></span>
            <span>📊 <strong>Benchmark:</strong> <span style='color:#0f172a;font-weight:600;'>Nifty 500 ({ledger.get('benchmark', '^CRSLDX')})</span></span>
            <span>🔒 <strong>Policy:</strong> <span style='color:#0f172a;font-weight:600;'>Append-only — a closed month is never recalculated</span></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not months:
        st.info(
            "No months frozen yet. The ledger fills one month at a time: "
            "`scripts/update_track_record.py` runs on the 2nd of each month and "
            "commits the closed month to `data/track_record.json`. Run it "
            "manually to backfill from "
            f"{INCEPTION} onward."
        )
        if mtd_val is not None and mtd_period is not None:
            st.metric(
                f"{mtd_period.strftime('%b %Y')} month-to-date (live, not yet frozen)",
                _pct(mtd_val),
                delta=(
                    f"{(mtd_val - mtd_bench) * 100:+.1f}% vs Nifty 500"
                    if mtd_bench is not None
                    else None
                ),
            )
        return

    stats = summary_stats(ledger)

    # ── Headline: frozen months only ─────────────────────────────────────────
    tr, br, al, dd = st.columns(4)
    tr.metric("Strategy (since inception)", _pct(stats["total_return"]))
    br.metric("Nifty 500", _pct(stats["bench_return"]))
    al.metric("Alpha", _pct(stats["alpha"]))
    dd.metric("Max Drawdown (monthly)", _pct(stats["max_drawdown"]))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Annualised", _pct(stats["ann_return"]))
    c2.metric("Positive Months", f"{stats['positive_months']} / {stats['months']}")
    c3.metric(
        "Beat Benchmark",
        f"{stats['beat_rate'] * 100:.0f}%" if stats["beat_rate"] is not None else "—",
    )
    c4.metric("Best / Worst", f"{_pct(stats['best_month'])} / {_pct(stats['worst_month'])}")

    if mtd_val is not None and mtd_period is not None:
        basis = lm.get("mtd_basis", "current book")
        frm = lm.get("mtd_from")
        st.info(
            f"**{mtd_period.strftime('%b %Y')} month-to-date: {_pct(mtd_val)}**"
            + (f" vs Nifty 500 {_pct(mtd_bench)}" if mtd_bench is not None else "")
            + f" — live figure on the {basis}"
            + (f" from {frm:%d %b %Y}" if frm is not None else "")
            + ". It moves every session and is **not** part of the frozen record "
            "until the month closes."
        )

    if len(stats.get("configs", [])) > 1:
        st.warning(
            "This record spans more than one strategy configuration "
            f"({', '.join(stats['configs'])}). Months produced under different "
            "settings are not a single continuous series — check the "
            "Provenance table below for where the change lands."
        )

    # ── Grids ────────────────────────────────────────────────────────────────
    which = st.segmented_control(
        "Track Record Series",
        ["📈 Strategy", "📊 Nifty 500", "⚡ Alpha", "🧾 Provenance"],
        default="📈 Strategy",
        key="tr_series_seg",
        label_visibility="collapsed",
    )
    if not which:
        which = "📈 Strategy"

    field = {
        "📈 Strategy": "strategy",
        "📊 Nifty 500": "benchmark",
        "⚡ Alpha": "alpha",
    }.get(which)

    if field is not None:
        # MTD belongs only to the series it was measured on.
        mtd_pair = None
        if mtd_period is not None:
            if field == "strategy" and mtd_val is not None:
                mtd_pair = (mtd_period, mtd_val)
            elif field == "benchmark" and mtd_bench is not None:
                mtd_pair = (mtd_period, mtd_bench)
            elif field == "alpha" and lm.get("mtd_alpha") is not None:
                mtd_pair = (mtd_period, lm["mtd_alpha"])

        grid = build_grid(ledger, field=field, mtd=mtd_pair)
        if grid.empty:
            st.info("No data recorded for this series yet.")
            return

        cols = ["YEAR"] + MONTH_LABELS + ["CY RETURN", "FY RETURN", "Q1", "Q2", "Q3", "Q4"]
        grid = grid[[c for c in cols if c in grid.columns]]
        st.caption(
            "Calendar quarters (Q1 = Jan·Feb·Mar). CY compounds Jan–Dec; "
            "FY compounds Apr of the row's year through Mar of the next. "
            + (
                f"The {mtd_period.strftime('%b')} cell is live month-to-date, not frozen."
                if mtd_pair is not None
                else "Frozen months only."
            )
        )
        render_saas_table(_grid_display(grid), key=f"tr_grid_{field}")
        st.download_button(
            "⬇️ Export Track Record (CSV)",
            grid.to_csv(index=False).encode(),
            f"track_record_{field}_{datetime.now():%Y%m%d}.csv",
            "text/csv",
            key=f"dl_tr_{field}",
        )
    else:
        prov = pd.DataFrame(
            [
                {
                    "Month": key,
                    "Strategy": _pct(e.get("strategy")),
                    "Nifty 500": _pct(e.get("benchmark")),
                    "Alpha": _pct(e.get("alpha")),
                    "Origin": (
                        "📼 Recorded"
                        if e.get("origin") == "recorded"
                        else "🔁 Backfilled"
                    ),
                    "Frozen On": e.get("finalized_on", "—"),
                    "Data As Of": e.get("data_as_of") or "—",
                    "Config": e.get("config", "—"),
                }
                for key, e in sorted(months.items())
            ]
        )
        st.caption(
            "When each month was written, the price data it was struck from, and "
            "the configuration fingerprint behind it. A change in the Config "
            "column marks a settings change — months either side of it were "
            "produced by different strategies. **📼 Recorded** months were frozen "
            "as they closed, from the data as it stood then; **🔁 Backfilled** "
            "months were reconstructed later from today's universe and prices, so "
            "they carry the backtest's biases and are weaker evidence."
        )
        render_saas_table(prov, key="tr_provenance")
        st.download_button(
            "⬇️ Export Provenance (CSV)",
            prov.to_csv(index=False).encode(),
            f"track_record_provenance_{datetime.now():%Y%m%d}.csv",
            "text/csv",
            key="dl_tr_prov",
        )
