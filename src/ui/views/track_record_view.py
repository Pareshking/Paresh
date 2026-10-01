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
from src.engine.extra_universe import SYSTEM_750, SYSTEM_NAMES, SYSTEMS
from src.engine.model_record import record_run
from src.engine.systems import inception, ledger_path
from src.engine.track_record import (
    load_ledger,
    summary_stats,
)
from src.ui import page_kit as kit
from src.ui.theme import render_saas_table


def _record_mtd(
    adj_close: pd.DataFrame, benchmark_close: pd.Series | None, system: str = SYSTEM_750
) -> dict:
    """Month-to-date under the RECORD's configuration, not the Backtest tab's.

    The Backtest tab's sliders are for exploring. If MTD were taken from
    whatever they happen to be set to, the running month would be measured on a
    different strategy from every frozen month beside it, and the year-to-date
    column would silently mix the two. So run the pinned configuration.
    """
    return record_run(adj_close, benchmark_close, system).get("live_meta", {}) or {}


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


def _render_rank_months(books: dict) -> None:
    """For a month: the book, each name's rank and entry gates at its start and end, and
    what the next rebalance did with it."""
    if not books:
        with kit.card("Ranks by month", "tr_ranks", "needs the price history"):
            st.info("No monthly books to show yet.")
        return
    keys = sorted(books)
    month = st.selectbox("Month", keys, index=len(keys) - 1, key="tr_rank_month",
                         format_func=lambda k: pd.Period(k, freq="M").strftime("%B %Y"))
    df = books[month]
    a = df.attrs
    end_word = "latest session" if a.get("in_progress") else "month end"
    with kit.card(f"{pd.Period(month, freq='M').strftime('%B %Y')} book", "tr_ranks",
                  f"ranked on {a.get('start')} (start) and {a.get('end')} ({end_word})"):
        kit.caption(
            "Start = the signal date that opened the month; the book is bought at the next close. "
            "A name qualifies only while it is above its 50-day EMA, within 20% of its 52-week high "
            "and in the index; a blank end rank means it no longer qualified. The next rebalance "
            "sells it once it falls out of qualifying or past rank 40.")
        show = df.assign(**{
            "Above EMA start": df["Above EMA start"].map({True: "yes", False: "no"}),
            "Above EMA end": df["Above EMA end"].map({True: "yes", False: "no"}),
            "In index end": df["In index end"].map({True: "yes", False: "no"}),
        })
        st.dataframe(
            show, hide_index=True, width="stretch",
            column_config={
                "Weight %": kit.col_num("Weight %", "%.1f"),
                "Rank at start": kit.col_num("Rank at start", "%d"),
                "Rank at end": kit.col_num("Rank at end", "%d", help="Blank: failed a gate that day"),
                "% of 52w high start": kit.col_pct("% of 52w high start"),
                "% of 52w high end": kit.col_pct("% of 52w high end"),
            },
        )
        st.download_button("Export CSV", df.to_csv(index=False).encode(),
                           f"ranks_{month}.csv", "text/csv", key="dl_tr_ranks")


def render_record_sections(
    adj_close: pd.DataFrame | None = None,
    benchmark_close: pd.Series | None = None,
    system: str = SYSTEM_750,
) -> None:
    """The frozen record under the Portfolio's live book: since-inception figures,
    how much of it is evidence, each month, each month's ranks, provenance, and
    the three systems side by side. The equity curve and the calendar grid are
    the Portfolio's own cards, so they are not drawn twice."""
    live_meta = _record_mtd(adj_close, benchmark_close, system) if adj_close is not None else {}
    start = inception(system)
    try:
        ledger = load_ledger(ledger_path(system), start)
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

    if not months:
        st.info(f"No months frozen yet. {SYSTEM_NAMES[system]}'s record starts with "
                f"{start.strftime('%B %Y')}; each month is frozen early the next month.")
        if mtd_val is not None and mtd_period is not None:
            st.html(month_cards_html({}, mtd_period, mtd_val, mtd_bench))
        render_comparison()
        return

    # The running month counts, everywhere: it is real money, and excluding it
    # from the headline while the grid compounds it gave two answers.
    stats = summary_stats(
        ledger,
        mtd={"period": mtd_period, "strategy": mtd_val, "benchmark": mtd_bench,
             "as_of": lm.get("as_of")} if mtd_period is not None else None,
    )
    incl = stats.get("includes_mtd")
    # Not Jensen's alpha: a simple difference, price only on both sides.
    beat = stats["beat_rate"]
    n_beat = None if beat is None else round(beat * stats["months"])
    kit.readings([
        kit.Reading("Since inception", _pct(stats["total_return"]),
                    "after costs" + (f" · incl. {mtd_period.strftime('%b')} so far" if incl else ""),
                    _tone(stats["total_return"])),
        kit.Reading("Nifty 500", _pct(stats["bench_return"]), "price index", _tone(stats["bench_return"])),
        kit.Reading("Ahead of the index", _pct(stats["alpha"]).replace("%", " pts"),
                    (f"{n_beat} of {stats['months']} months beat it" if n_beat is not None else ""),
                    _tone(stats["alpha"])),
        kit.Reading("Worst month", _pct(stats["worst_month"]),
                    f"best {_pct(stats['best_month'])}", _tone(stats["worst_month"])),
    ], "Track record")

    # Annualising a sub-year record is an extrapolation, not a CAGR.
    elapsed = float(stats.get("elapsed_months", 0) or 0) / 12.0
    kit.caption(
        f"Annualised {_pct(stats['ann_return'])}"
        + (f" (from {elapsed:.2f} yr, not a CAGR)" if elapsed < 1 else "")
        + f" · {stats['positive_months']} of {stats['months']} months positive"
        + f" · worst month-to-month fall {_pct(stats['max_drawdown'])}"
    )

    # How much of this record is EVIDENCE and how much is reconstruction.
    _backfilled = int(stats.get("backfilled", 0) or 0)
    _recorded = int(stats.get("recorded", 0) or 0)
    if _backfilled:
        _lead = (f"{_backfilled} of {_backfilled + _recorded} months are backfilled"
                 + (": the whole record is a reconstruction." if not _recorded else "."))
        kit.note(_lead, "Rebuilt later, not frozen as each month closed; only months marked "
                        "recorded were frozen as they closed."
                 + (" Each is scored on the index as it stood." if int(stats.get("current_universe", 0) or 0) == 0
                    else " They carry the backtest's survivorship bias."))
    if len(stats.get("configs", [])) > 1:
        kit.note("More than one strategy configuration.",
                 f"({', '.join(stats['configs'])}) Months under different settings are not one "
                 "continuous series; Provenance shows where it changes.")

    which = st.segmented_control(
        "Record view", ["Month by month", "Ranks by month", "Provenance"],
        default="Month by month", key="tr_series_seg", label_visibility="collapsed",
    ) or "Month by month"

    if which == "Month by month":
        with kit.card("Month by month", "tr_months"):
            st.html(month_cards_html(months, mtd_period, mtd_val, mtd_bench))
    elif which == "Ranks by month":
        _render_rank_months(
            (record_run(adj_close, benchmark_close, system).get("month_books") or {})
            if adj_close is not None else {})
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
        with kit.card("Provenance", "tr_prov"):
            kit.caption("Recorded = frozen as the month closed. Backfilled = rebuilt later, "
                        "weaker evidence. Universe: the index as it stood, or today's list.")
            render_saas_table(prov)
            st.download_button(
                "Export provenance CSV",
                prov.to_csv(index=False).encode(),
                f"track_record_provenance_{ist_now():%Y%m%d}.csv",
                "text/csv",
                key="dl_tr_prov",
            )

    render_comparison()


def comparison_frame(ledgers: dict[str, dict]) -> pd.DataFrame:
    """Month by month, every system's frozen return beside Nifty 500's.

    Only frozen months: a system's live month-to-date belongs on its own
    record, and mixing a live cell into a comparison of closed months would
    compare unlike things. Months before a system's inception are blank.
    """
    keys = sorted({k for led in ledgers.values() for k in led.get("months", {})})
    if not keys:
        return pd.DataFrame()
    rows = []
    for key in keys[-12:][::-1]:
        row = {"Month": pd.Period(key, freq="M").strftime("%b %Y")}
        bench = None
        for sys_id in SYSTEMS:
            e = ledgers.get(sys_id, {}).get("months", {}).get(key)
            row[SYSTEM_NAMES[sys_id]] = _pct(e.get("strategy")) if e else "—"
            if e and e.get("benchmark") is not None and bench is None:
                bench = e.get("benchmark")
        row["Nifty 500"] = _pct(bench)
        rows.append(row)
    return pd.DataFrame(rows)


def render_comparison() -> None:
    """Owner, 2026-09-27: how the 750, Nano Cap and Combined each perform."""
    ledgers = {}
    for sys_id in SYSTEMS:
        try:
            ledgers[sys_id] = load_ledger(ledger_path(sys_id), inception(sys_id))
        except (ValueError, OSError):
            ledgers[sys_id] = {}
    table = comparison_frame(ledgers)
    with kit.card("Three systems, side by side", "tr_compare",
                  "frozen months only · last 12"):
        starts = ", ".join(f"{SYSTEM_NAMES[s]} from {inception(s).strftime('%b %Y')}"
                           for s in SYSTEMS)
        kit.caption(f"Each system's record starts on its own date: {starts}. "
                    "A dash is a month before that system's record began.")
        if table.empty:
            st.info("Nothing frozen yet.")
        else:
            render_saas_table(table)
