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
from src.engine.corporate_actions import load_events
from src.engine.membership import load_history_or_none
from src.engine.track_record import (
    INCEPTION,
    MONTH_LABELS,
    TRACK_RECORD_CONFIG,
    build_combined_grid,
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
        _membership=load_history_or_none(),
        _actions=load_events(),
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
        elif col == "SERIES":
            continue
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
            <span>📒 <strong>Record:</strong> <span style='color:#0f172a;font-weight:600;'>{len(months)} frozen month(s) from {INCEPTION}, plus the month in progress</span></span>
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

    # The running month counts, everywhere. It is real money, and excluding it
    # from the headline while the grid below compounds it into CY gave two
    # different answers to the same question.
    stats = summary_stats(
        ledger,
        mtd={
            "period": mtd_period,
            "strategy": mtd_val,
            "benchmark": mtd_bench,
            "as_of": lm.get("as_of"),
        }
        if mtd_period is not None
        else None,
    )
    incl = stats.get("includes_mtd")

    tr, br, al, dd = st.columns(4)
    tr.metric(
        "Strategy since inception (net of costs, pre-tax)",
        _pct(stats["total_return"]),
        help=(
            "Net of the modelled transaction-cost drag, including the live "
            "month. No capital-gains tax is deducted anywhere in this app."
        ),
    )
    br.metric("Nifty 500 (price index)", _pct(stats["bench_return"]))
    # Not Jensen's alpha, and not like-for-like: the strategy trades
    # dividend-adjusted prices (auto_adjust=True) while ^CRSLDX is the Nifty 500
    # PRICE index, which excludes dividends. The constituents' yield -- roughly
    # 1-1.5% a year -- therefore lands in this figure as if it were skill.
    al.metric(
        "Excess vs Nifty 500",
        _pct(stats["alpha"]),
        help=(
            "Simple difference of cumulative returns, not beta-adjusted alpha. "
            "The strategy compounds dividend-adjusted prices; ^CRSLDX is a "
            "price index that excludes dividends, so roughly 1-1.5% a year of "
            "this gap is constituent yield rather than outperformance."
        ),
    )
    dd.metric("Max Drawdown (monthly)", _pct(stats["max_drawdown"]))

    # Annualising a sub-year record is an extrapolation, not a CAGR. The
    # Backtest tab says so on its own equivalent figure; this tab, which readers
    # trust as the real record, did not.
    _elapsed_years = float(stats.get("elapsed_months", 0) or 0) / 12.0
    _ann_label = (
        "Annualised" if _elapsed_years >= 1.0
        else f"Annualised (scaled up from {_elapsed_years:.2f}y)"
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        _ann_label,
        _pct(stats["ann_return"]),
        help=(
            "Not a CAGR: no full year has been observed. The return actually "
            f"posted over {_elapsed_years:.2f} years is raised to the power of "
            f"1/{max(_elapsed_years, 1e-9):.2f}."
        ) if _elapsed_years < 1.0 else None,
    )
    c2.metric("Positive Months", f"{stats['positive_months']} / {stats['months']}")
    c3.metric(
        "Beat Benchmark",
        f"{stats['beat_rate'] * 100:.0f}%" if stats["beat_rate"] is not None else "—",
    )
    c4.metric("Best / Worst", f"{_pct(stats['best_month'])} / {_pct(stats['worst_month'])}")

    if incl:
        st.caption(
            f"Every figure above includes {mtd_period.strftime('%B')} "
            "month-to-date — today's reality, not the last closed month. "
            f"{stats['frozen_months']} of those months are frozen; the current "
            "one still moves each session, and for the annualised figure it "
            f"counts as the {stats['elapsed_months'] - stats['frozen_months']:.2f} "
            "of a month that has actually elapsed."
        )

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

    # How much of this record is EVIDENCE and how much is reconstruction.
    # summary_stats has counted this since it was written and nothing displayed
    # it: every month in the shipped ledger is `origin: "backfill"`, computed in
    # one pass on 2026-09-03 from today's universe and today's prices, and the
    # headline above reads "Strategy since inception" as though it were a live
    # record. A backfilled month carries the backtest's survivorship and
    # index-membership biases; a recorded month was frozen as it closed and
    # carries none of them. The difference is the entire evidential value of
    # the tab, so it goes above the numbers, not in a tooltip.
    _backfilled = int(stats.get("backfilled", 0) or 0)
    _recorded = int(stats.get("recorded", 0) or 0)
    if _backfilled:
        st.warning(
            f"**{_backfilled} of {_backfilled + _recorded} frozen months were "
            "BACKFILLED**"
            + (
                " — the whole record is a reconstruction, not an out-of-sample "
                "result."
                if not _recorded
                else "."
            )
            + " A backfilled month was rebuilt later from today's constituent "
            "list and today's prices, so it inherits the backtest's "
            "survivorship and index-membership bias. Only months marked "
            "*recorded* were frozen as they closed from the data as it then "
            "stood. See the Provenance view for which is which."
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
        "Track Record View",
        ["📊 Returns", "🧾 Provenance"],
        default="📊 Returns",
        key="tr_series_seg",
        label_visibility="collapsed",
    )
    if not which:
        which = "📊 Returns"

    if which == "📊 Returns":
        # One grid, three rows per year. Strategy, benchmark and alpha in
        # separate tabs meant the commonest question -- how did we do against
        # the index in June -- required switching views and remembering a
        # number. Now it is one glance down a column.
        grid = build_combined_grid(
            ledger,
            mtd_period=mtd_period,
            mtd_values={
                "strategy": mtd_val,
                "benchmark": mtd_bench,
                "alpha": lm.get("mtd_alpha"),
            },
        )
        if grid.empty:
            st.info("Nothing recorded yet.")
            return

        has_mtd = mtd_period is not None and mtd_val is not None
        st.caption(
            "Calendar quarters (Q1 = Jan·Feb·Mar). CY compounds Jan–Dec; "
            "FY compounds Apr of the row's year through Mar of the next. "
            + (
                f"The {mtd_period.strftime('%b')} cells are live month-to-date, "
                "not frozen."
                if has_mtd
                else "Frozen months only."
            )
        )
        render_saas_table(_grid_display(grid), key="tr_grid_combined")
        st.download_button(
            "⬇️ Export Track Record (CSV)",
            grid.to_csv(index=False).encode(),
            f"track_record_{datetime.now():%Y%m%d}.csv",
            "text/csv",
            key="dl_tr_combined",
        )

    else:
        # This view is named Provenance and used to show Month / Strategy /
        # Nifty 500 / Alpha -- the same four numbers as the Returns grid and no
        # provenance at all, while the ledger carried origin, config
        # fingerprint, freeze date and price date for every month.
        prov = pd.DataFrame(
            [
                {
                    "Month": key,
                    "Strategy": _pct(e.get("strategy")),
                    "Nifty 500": _pct(e.get("benchmark")),
                    "Alpha": _pct(e.get("alpha")),
                    "Origin": (
                        "✅ Recorded"
                        if e.get("origin") == "recorded"
                        else "⚠️ Backfilled"
                    ),
                    "Universe": (
                        "Point-in-time"
                        if e.get("universe") == "point_in_time"
                        else "Current list"
                    ),
                    "Frozen On": e.get("finalized_on") or "—",
                    "Priced From": e.get("data_as_of") or "—",
                    "Config": e.get("config") or "—",
                }
                for key, e in sorted(months.items())
            ]
        )
        st.caption(
            "**Recorded** = frozen as the month closed, from the data as it "
            "then stood. **Backfilled** = reconstructed later, so it carries "
            "the backtest's biases and is weaker evidence. **Universe** says "
            "whether that month was scored against the index as it actually "
            "stood or against today's constituent list."
        )
        render_saas_table(prov, key="tr_provenance")
        st.download_button(
            "⬇️ Export Provenance (CSV)",
            prov.to_csv(index=False).encode(),
            f"track_record_provenance_{datetime.now():%Y%m%d}.csv",
            "text/csv",
            key="dl_tr_prov",
        )
