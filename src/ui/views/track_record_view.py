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

from src.engine.extra_universe import SYSTEM_750, SYSTEM_NAMES, SYSTEMS
from src.engine.model_record import record_run
from src.engine.systems import inception, ledger_path, membership_for
from src.engine.track_record import (
    load_ledger,
    summary_stats,
)
from src.ui import page_kit as kit
from src.ui.theme import render_saas_table


@st.cache_data(show_spinner=False, ttl=3600)
def _comparison_price_frame(system: str, selected_system: str, _fallback: pd.DataFrame) -> pd.DataFrame:
    """Build the MTD price frame from the system's own canonical universe.

    The Portfolio page normally loads the selected system's prices. That frame
    is valid for Nifty 750, but it cannot be reused for Nano Cap because Nano
    is deliberately disjoint from the 750; Combined may contain both. The
    comparison must therefore resolve each system independently.

    Screener is the canonical current ranking-price source. Membership comes
    from the same point-in-time system timeline used by record_run(). No
    fallback to another system is allowed: doing so would silently report a
    wrong MTD portfolio under the right system name.
    """
    # For the system currently selected in Portfolio, use the exact same
    # validated price frame already consumed by record_run(). This keeps the
    # headline MTD and the side-by-side MTD numerically identical. Other systems
    # still resolve their own independent canonical price frame below.
    if system == selected_system:
        return _fallback
    history = membership_for(system)
    if not history:
        return pd.DataFrame()
    try:
        from src.loaders import price_source

        chosen = price_source.from_screener(price_source.fetch_screener_store())
        if chosen is None or chosen.close.empty:
            return pd.DataFrame()

        # Keep every symbol appearing in the system's membership timeline.
        # record_run() itself applies the point-in-time membership and former-
        # member logic, so the price frame should not be narrowed to the
        # currently selected Portfolio's symbols.
        symbols = set()
        baseline = history.get("baseline") or {}
        symbols.update(str(s).upper() for s in (baseline.get("symbols") or []))
        for change in history.get("changes") or []:
            symbols.update(str(s).upper() for s in (change.get("add") or []))
            symbols.update(str(s).upper() for s in (change.get("remove") or []))
        if not symbols:
            return pd.DataFrame()

        available = [c for c in chosen.close.columns
                     if str(c).upper() in symbols]
        return chosen.close.loc[:, available] if available else pd.DataFrame()
    except Exception:
        # A missing canonical source is a data condition, not permission to
        # substitute the currently selected system's prices.
        return pd.DataFrame()


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


def _pct(v: float | int | None) -> str:
    if v is None or pd.isna(v):
        return "—"
    try:
        return f"{float(v) * 100:+.1f}%"
    except (TypeError, ValueError):
        return "—"


def grid_display(grid: pd.DataFrame) -> pd.DataFrame:
    if grid.empty:
        return grid
    out = grid.copy()
    for col in out.columns:
        if col == "YEAR":
            out[col] = out[col].astype(int).astype(str)
        elif col in ("SERIES", "SYSTEM"):
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
    """Show the selected monthly book using the app's shared table treatment."""
    if not books:
        with kit.card("Ranks by month", "tr_ranks", "needs the price history"):
            st.info("No monthly books to show yet.")
        return

    keys = sorted(books)
    month = st.selectbox(
        "Month",
        keys,
        index=len(keys) - 1,
        key="tr_rank_month",
        format_func=lambda k: pd.Period(k, freq="M").strftime("%B %Y"),
        label_visibility="collapsed",
    )
    df = books[month]
    a = df.attrs
    end_word = "latest session" if a.get("in_progress") else "month end"

    with kit.card(
        f"Ranks by month · {pd.Period(month, freq='M').strftime('%B %Y')}",
        "tr_ranks",
        f"{a.get('start')} → {a.get('end')} · {end_word}",
    ):
        show = df.copy()
        for col in ("Above EMA start", "Above EMA end", "In index end"):
            if col in show.columns:
                show[col] = show[col].map({True: "Yes", False: "No"}).fillna("—")

        # Keep the useful ranking fields first; the shared SaaS renderer gives
        # this table the same visual language as Calendar returns and the rest
        # of the Portfolio page.
        preferred = [
            "Symbol", "Rank at start", "Rank at end", "Weight %",
            "% of 52w high start", "% of 52w high end",
            "Above EMA start", "Above EMA end", "In index end",
        ]
        cols = [c for c in preferred if c in show.columns]
        rest = [c for c in show.columns if c not in cols]
        show = show[cols + rest]
        render_saas_table(show, max_height=620)

        st.download_button(
            "Export CSV",
            df.to_csv(index=False).encode(),
            f"ranks_{month}.csv",
            "text/csv",
            key="dl_tr_ranks",
        )


def render_record_sections(
    adj_close: pd.DataFrame | None = None,
    benchmark_close: pd.Series | None = None,
    system: str = SYSTEM_750,
    show_reconstruction_note: bool = True,
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
        render_comparison(adj_close, benchmark_close, system)
        return

    # The running month counts, everywhere: it is real money, and excluding it
    # from the headline while the grid compounds it gave two answers.
    stats = summary_stats(
        ledger,
        mtd={"period": mtd_period, "strategy": mtd_val, "benchmark": mtd_bench,
             "as_of": lm.get("as_of")} if mtd_period is not None else None,
    )
    incl = stats.get("includes_mtd")
    if mtd_val is None and lm.get("rebalanced") and lm.get("fill_date") is not None:
        # The book is struck at the close of its fill session, so its first day of P&L is
        # the next one: the month has a portfolio but no return yet.
        _fill = pd.Timestamp(lm["fill_date"])
        kit.note(
            f"{_fill:%B %Y} has a new book but no return yet.",
            f"It was signalled on {pd.Timestamp(lm['signal_date']):%d %b} and bought at the "
            f"{_fill:%d %b} close ({lm.get('n_bought', 0)} bought, {lm.get('n_sold', 0)} sold, "
            f"{lm.get('n_held', 0)} kept). Month-to-date starts accruing the next session. "
            "See Ranks by month for the book and its ranks.",
        )

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
        + (" · prices are Personal closes (NSE where unavailable), no dividends, like the index."
           if ledger.get("price_basis") == "screener_primary"
           else " · prices are NSE closes, no dividends, like the index."
           if ledger.get("price_basis") == "nse_as_published"
           else " · about 1–1.5% a year of the gap is dividends the price index leaves out.")
    )

    # How much of this record is EVIDENCE and how much is reconstruction.
    _backfilled = int(stats.get("backfilled", 0) or 0)
    _recorded = int(stats.get("recorded", 0) or 0)
    if _backfilled and show_reconstruction_note:
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

    _render_rank_months(
        (record_run(adj_close, benchmark_close, system).get("month_books") or {})
        if adj_close is not None else {}
    )

    render_comparison(adj_close, benchmark_close, system)


def comparison_frame(
    ledgers: dict[str, dict],
    live_meta: dict[str, dict] | None = None,
) -> pd.DataFrame:
    """Calendar-style monthly returns for all three systems.

    A system is blank before its own inception. Its current-month cell uses
    that system's live MTD record, so the table never hides an active month
    merely because it has not been frozen yet.
    """
    live_meta = live_meta or {}
    frozen = {
        sys_id: ledgers.get(sys_id, {}).get("months", {})
        for sys_id in SYSTEMS
    }
    keys = sorted({k for months in frozen.values() for k in months})
    current_periods = [
        pd.Period(meta["mtd_period"], freq="M")
        for meta in live_meta.values()
        if meta.get("mtd_period")
    ]
    if current_periods:
        keys.append(str(max(current_periods)))
    if not keys:
        return pd.DataFrame()

    periods = sorted(set(pd.Period(k, freq="M") for k in keys))
    periods = periods[-12:]

    rows = []
    for year in sorted({p.year for p in periods}, reverse=True):
        year_periods = [p for p in periods if p.year == year]
        for sys_id in SYSTEMS:
            row = {"SYSTEM": SYSTEM_NAMES[sys_id], "YEAR": str(year)}
            start = inception(sys_id)
            months = frozen[sys_id]
            live = live_meta.get(sys_id, {})
            live_period = (
                pd.Period(live["mtd_period"], freq="M")
                if live.get("mtd_period") else None
            )
            for p in year_periods:
                key = str(p)
                if p < start:
                    row[p.strftime("%b").upper()] = None
                    continue
                entry = months.get(key)
                if entry is not None:
                    row[p.strftime("%b").upper()] = entry.get("strategy")
                elif live_period is not None and p == live_period:
                    row[p.strftime("%b").upper()] = live.get("strategy_mtd")
                else:
                    row[p.strftime("%b").upper()] = None
            rows.append(row)

    columns = ["SYSTEM", "YEAR"] + [p.strftime("%b").upper() for p in periods]
    return pd.DataFrame(rows)[columns]


def render_comparison(
    adj_close: pd.DataFrame | None = None,
    benchmark_close: pd.Series | None = None,
    selected_system: str = SYSTEM_750,
) -> None:
    """Three systems in the same calendar-return treatment as the Portfolio."""
    ledgers = {}
    live_meta = {}
    for sys_id in SYSTEMS:
        try:
            ledgers[sys_id] = load_ledger(ledger_path(sys_id), inception(sys_id))
        except (ValueError, OSError):
            ledgers[sys_id] = {}
        if adj_close is not None and not adj_close.empty:
            system_prices = _comparison_price_frame(sys_id, selected_system, adj_close)
            live_meta[sys_id] = _record_mtd(system_prices, benchmark_close, sys_id)

    table = comparison_frame(ledgers, live_meta)
    with kit.card(
        "Three systems, side by side",
        "tr_compare",
        "monthly returns · latest 12 months",
    ):
        if table.empty:
            st.info("Nothing recorded yet.")
        else:
            render_saas_table(grid_display(table))
            starts = " · ".join(
                f"{SYSTEM_NAMES[s]}: {inception(s).strftime('%b %Y')}" for s in SYSTEMS
            )
            kit.caption(
                f"Each system starts on its own date — {starts}. "
                "A dash means the system had not started yet."
            )
