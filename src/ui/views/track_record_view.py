"""Track Record: the frozen monthly history, month by month, against Nifty 500.

Everything on this tab except the MTD cell is read from data/track_record.json
and is never recomputed here. That is the point of the tab: the Backtest tab
answers "what would this strategy have done", recomputed from live prices every
run; this one answers "what did it post", and that answer must not move because
a price got revised or a slider got nudged.
"""

from __future__ import annotations


import pandas as pd
import streamlit as st

from src.core.market_time import ist_now
from src.engine.backtester import run_backtest
from src.engine.corporate_actions import load_events
from src.engine.membership import load_history_or_none
from src.engine.pipeline import price_fingerprint
from src.engine.track_record import (
    INCEPTION,
    TRACK_RECORD_CONFIG,
    build_combined_grid,
    load_ledger,
    months_to_cover,
    summary_stats,
)
from src.loaders.ranking_store import actions_digest
from src.ui import page_kit as kit
from src.ui.theme import render_saas_table


def record_run(adj_close: pd.DataFrame, benchmark_close: pd.Series | None) -> dict:
    """The strategy under the RECORD's pinned configuration, through today.

    One cached run serves the month-to-date here and the model book on the
    Exit watch page, so both describe the same portfolio.
    """
    if adj_close is None or adj_close.empty:
        return {}
    as_of = pd.Timestamp(adj_close.index[-1])
    months = months_to_cover(as_of)
    if months <= 0:
        return {}
    cfg = TRACK_RECORD_CONFIG
    # Whole-history fingerprint + applied events: the old key (date, width,
    # months) served an hour-stale MTD after a restatement or a new split.
    events = load_events()
    result = run_backtest(
        f"trackrec_{price_fingerprint(adj_close)}_{actions_digest(events)}_{months}",
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
        _actions=events,
    )
    return result or {}


def _record_mtd(
    adj_close: pd.DataFrame, benchmark_close: pd.Series | None
) -> dict:
    """Month-to-date under the RECORD's configuration, not the Backtest tab's.

    The Backtest tab's sliders are for exploring. If MTD were taken from
    whatever they happen to be set to, the running month would be measured on a
    different strategy from every frozen month beside it, and the year-to-date
    column would silently mix the two. So run the pinned configuration.
    """
    return record_run(adj_close, benchmark_close).get("live_meta", {}) or {}


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


def _tone(v: float | None) -> str:
    if v is None or pd.isna(v):
        return ""
    return "up" if v > 0 else "down" if v < 0 else ""


def month_cards_html(months: dict, mtd_period, mtd_val, mtd_bench) -> str:
    """One card per month: its return, the index's, and ahead or behind."""
    cards = []
    for key, e in sorted(months.items()):
        s, b = e.get("strategy"), e.get("benchmark")
        gap = "" if s is None or b is None else (
            f" · {'ahead' if s >= b else 'behind'} {abs(s - b) * 100:.1f} pts")
        tag = "recorded" if e.get("origin") == "recorded" else "backfilled"
        cards.append(
            f'<div class="mo {_tone(s)}"><span class="mo-h">{pd.Period(key, freq="M").strftime("%b %Y")}'
            f'<em>{tag}</em></span><span class="mo-v {_tone(s)}">{_pct(s).replace("-", "−")}</span>'
            f'<span class="mo-s">Nifty 500 {_pct(b).replace("-", "−")}{gap}</span></div>'
        )
    if mtd_period is not None and mtd_val is not None:
        cards.append(
            f'<div class="mo live"><span class="mo-h" style="color:#3730A3">{mtd_period.strftime("%b %Y")} · so far</span>'
            f'<span class="mo-v {_tone(mtd_val)}">{_pct(mtd_val).replace("-", "−")}</span>'
            f'<span class="mo-s">Nifty 500 {_pct(mtd_bench).replace("-", "−")} · moves every session until the month closes</span></div>'
        )
    return f'<div class="mo-grid">{"".join(cards)}</div>'


def growth_series(months: dict, mtd_period, mtd_val, mtd_bench):
    """Compounded growth of 1.0 from the start of the record, month by month."""
    labels, s_curve, b_curve = ["Start"], [1.0], [1.0]
    for key, e in sorted(months.items()):
        s_curve.append(s_curve[-1] * (1 + (e.get("strategy") or 0.0)))
        b_curve.append(b_curve[-1] * (1 + (e.get("benchmark") or 0.0)))
        labels.append(pd.Period(key, freq="M").strftime("%b"))
    if mtd_period is not None and mtd_val is not None:
        s_curve.append(s_curve[-1] * (1 + mtd_val))
        b_curve.append(b_curve[-1] * (1 + (mtd_bench or 0.0)))
        labels.append(mtd_period.strftime("%b") + "*")
    return labels, s_curve, b_curve


def render_track_record_view(
    adj_close: pd.DataFrame | None = None,
    benchmark_close: pd.Series | None = None,
) -> None:
    """The frozen monthly record with the live month beside it."""
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
    bench_name = f"Nifty 500 ({ledger.get('benchmark', '^CRSLDX')})"

    actions = kit.page_head(
        "Track record",
        f"Every month since {pd.Period(INCEPTION, freq='M').strftime('%B %Y')}, each frozen when it "
        f"closes and never recalculated · benchmark {bench_name}",
        actions=True,
    )

    if not months:
        st.info(
            "No months frozen yet. The ledger fills one month at a time: "
            "`scripts/update_track_record.py` runs on the 2nd of each month and "
            "commits the closed month to `data/track_record.json`. Run it "
            f"manually to backfill from {INCEPTION} onward."
        )
        if mtd_val is not None and mtd_period is not None:
            st.html(month_cards_html({}, mtd_period, mtd_val, mtd_bench))
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

    # Not Jensen's alpha, and not like-for-like: the strategy trades
    # dividend-adjusted prices (auto_adjust=True) while ^CRSLDX is the Nifty 500
    # PRICE index, which excludes dividends. The constituents' yield -- roughly
    # 1-1.5% a year -- therefore lands in the gap as if it were skill.
    beat = stats["beat_rate"]
    n_beat = None if beat is None else round(beat * stats["months"])
    since = "after costs, before tax" + (f" · includes {mtd_period.strftime('%B')} so far" if incl else "")
    kit.readings([
        kit.Reading("Since inception", _pct(stats["total_return"]), since, _tone(stats["total_return"])),
        kit.Reading("Nifty 500", _pct(stats["bench_return"]), "price index, same period", _tone(stats["bench_return"])),
        kit.Reading("Ahead of the index", _pct(stats["alpha"]).replace("%", " pts"),
                    (f"{n_beat} of {stats['months']} months beat it · " if n_beat is not None else "")
                    + "simple difference, not beta-adjusted", _tone(stats["alpha"])),
        kit.Reading("Worst month", _pct(stats["worst_month"]),
                    f"best {_pct(stats['best_month'])}", _tone(stats["worst_month"])),
    ], "Track record")

    # Annualising a sub-year record is an extrapolation, not a CAGR.
    elapsed = float(stats.get("elapsed_months", 0) or 0) / 12.0
    kit.caption(
        f"Annualised {_pct(stats['ann_return'])}"
        + (f" (scaled up from {elapsed:.2f} years, not a CAGR)" if elapsed < 1 else "")
        + f" · positive months {stats['positive_months']} of {stats['months']}"
        + f" · worst fall, month to month, {_pct(stats['max_drawdown'])}"
        + " · about 1–1.5% a year of the gap is dividends the price index leaves out."
    )

    # How much of this record is EVIDENCE and how much is reconstruction. A
    # backfilled month carries the backtest's survivorship and index-membership
    # biases; a recorded month was frozen as it closed and carries none of
    # them. That difference is the evidential value of the page, so it sits
    # above the chart, not in a tooltip.
    _backfilled = int(stats.get("backfilled", 0) or 0)
    _recorded = int(stats.get("recorded", 0) or 0)
    if _backfilled:
        kit.note(
            f"{_backfilled} of {_backfilled + _recorded} frozen months are backfilled"
            + (": the whole record is a reconstruction." if not _recorded else "."),
            "They were rebuilt later from today's index lists and prices, so they carry "
            "the backtest's survivorship bias. Only months marked recorded were frozen "
            "as they closed. Each month card says which it is.",
        )
    if len(stats.get("configs", [])) > 1:
        kit.note(
            "This record spans more than one strategy configuration.",
            f"({', '.join(stats['configs'])}) Months under different settings are not "
            "one continuous series; the Provenance view shows where the change lands.",
        )

    labels, s_curve, b_curve = growth_series(months, mtd_period, mtd_val, mtd_bench)
    with kit.card("Growth of ₹100", "tr_growth",
                  "indigo = strategy · grey = Nifty 500" + (" · * = month to date" if incl else "")):
        kit.growth_chart(labels, s_curve, b_curve, key="tr")

    grid = build_combined_grid(
        ledger,
        mtd_period=mtd_period,
        mtd_values={"strategy": mtd_val, "benchmark": mtd_bench, "alpha": lm.get("mtd_alpha")},
    )
    with actions:
        st.download_button(
            "Export CSV", grid.to_csv(index=False).encode(),
            f"track_record_{ist_now():%Y%m%d}.csv", "text/csv",
            key="dl_tr_combined", icon=":material/download:", disabled=grid.empty,
        )

    which = st.segmented_control(
        "Track Record View",
        ["Month by month", "Calendar grid", "Provenance"],
        default="Month by month",
        key="tr_series_seg",
        label_visibility="collapsed",
    ) or "Month by month"

    if which == "Month by month":
        with kit.card("Month by month", "tr_months", "rows for later years appear as they fill"):
            st.html(month_cards_html(months, mtd_period, mtd_val, mtd_bench))

    elif which == "Calendar grid":
        with kit.card("Calendar grid", "tr_grid", "strategy, Nifty 500 and the gap, per year"):
            if grid.empty:
                st.info("Nothing recorded yet.")
            else:
                has_mtd = mtd_period is not None and mtd_val is not None
                kit.caption(
                    "Calendar quarters (Q1 = Jan·Feb·Mar). CY compounds Jan–Dec; "
                    "FY compounds Apr of the row's year through Mar of the next. "
                    + (f"The {mtd_period.strftime('%b')} cells are live month-to-date, not frozen."
                       if has_mtd else "Frozen months only.")
                )
                render_saas_table(_grid_display(grid))

    else:
        # Origin, universe, freeze date and price date for every month: the
        # ledger records them, and they are what makes a month evidence.
        prov = pd.DataFrame(
            [
                {
                    "Month": key,
                    "Strategy": _pct(e.get("strategy")),
                    "Nifty 500": _pct(e.get("benchmark")),
                    "Alpha": _pct(e.get("alpha")),
                    "Origin": "Recorded" if e.get("origin") == "recorded" else "Backfilled",
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
        with kit.card("Provenance", "tr_prov", "where each month's figure came from"):
            kit.caption(
                "Recorded = frozen as the month closed, from the data as it then stood. "
                "Backfilled = reconstructed later, so it carries the backtest's biases and "
                "is weaker evidence. Universe says whether the month was scored against the "
                "index as it stood then or against today's list."
            )
            render_saas_table(prov)
            st.download_button(
                "Export provenance CSV",
                prov.to_csv(index=False).encode(),
                f"track_record_provenance_{ist_now():%Y%m%d}.csv",
                "text/csv",
                key="dl_tr_prov",
            )
