"""
Reusable UI Components and Widgets for NSE Momentum Dashboard.
Inspired by Investrack, Stockin.id, and Tickerboom financial terminal designs.
"""

import html
import re
from typing import Any

import pandas as pd
import streamlit as st

from src.core.types import MarketRegime, RegimeData, SignalAlert
from src.ui.theme import is_tick_true



def count_above_ema(rank_df: pd.DataFrame, column: str = "Above 50 EMA") -> int:
    """Count stocks with `column` truthy, handling duplicate/unexpected columns."""
    ema_col = rank_df.get(column)
    if ema_col is None:
        return 0
    if isinstance(ema_col, pd.DataFrame):
        ema_col = ema_col.iloc[:, -1]
    if not isinstance(ema_col, pd.Series):
        ema_col = pd.Series(ema_col, index=rank_df.index)
    return int(to_bool_mask(ema_col).sum())


def to_bool_mask(values: "pd.Series | None") -> pd.Series:
    """Coerce a qualification column to a real boolean mask.

    "Above 50 EMA" and "Near 52W High" carry tick marks rather than booleans.
    Under pandas 3 they land in the string dtype, where summing CONCATENATES
    instead of counting, and an empty column sums to '' -- so
    ``int(col.sum())`` raised ``ValueError: invalid literal for int() with
    base 10: ''`` and took the Screener down in production. Using the column
    directly with ``&`` is unsafe for the same reason.

    Every other consumer already coerced these with .map(); this centralises
    that rule so the two representations cannot drift apart again.
    """
    if values is None:
        return pd.Series(dtype=bool)
    return pd.Series(
        [is_tick_true(v) for v in values],
        index=values.index,
        dtype=bool,
    )


def compute_signals(rank_df: pd.DataFrame) -> list[SignalAlert]:
    """The Screener's signal chips: only what no other line on the page says.

    Regime and breadth are the market line's; the top-50 moves are the
    Screener's closing section (owner, 2026-09-27: no figure shown twice).
    """
    signals: list[SignalAlert] = []

    # Qualified count check (Safely parse boolean or string icons)
    ab_ema = (
        to_bool_mask(rank_df["Above 50 EMA"])
        if "Above 50 EMA" in rank_df.columns
        else pd.Series(True, index=rank_df.index)
    )
    nr_hi = (
        to_bool_mask(rank_df["Near 52W High"])
        if "Near 52W High" in rank_df.columns
        else pd.Series(True, index=rank_df.index)
    )
    rk_col = rank_df.get(
        "Composite Rank", rank_df.get("Rank", pd.Series(1, index=rank_df.index))
    )
    # Force native, index-aligned boolean masks. Pandas 3 / PyArrow-backed
    # columns can otherwise produce mixed-dtype logical operations at runtime.
    ab_ema = pd.Series(ab_ema, index=rank_df.index, dtype="bool")
    nr_hi = pd.Series(nr_hi, index=rank_df.index, dtype="bool")
    has_rank = pd.Series(rk_col.notna(), index=rank_df.index, dtype="bool")
    qualified = rank_df[ab_ema & nr_hi & has_rank]
    if len(qualified) < 15:
        signals.append(
            SignalAlert(
                icon="⚠️",
                text=f"Only {len(qualified)} stocks pass both filters (the portfolio wants at least 20)",
                color="#B54708",
                category="risk",
            )
        )

    return signals



YEARLY_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                 "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def yearly_summary(grid: pd.DataFrame) -> pd.DataFrame:
    """One row per year: strategy, benchmark and alpha for the calendar year.

    Read straight from the grid's CY RETURN cells, so every number here is the
    one printed in that year's block below (owner, 9 Oct 2026). Nothing is
    recomputed. `months` counts the strategy's months with a return, so a year
    the window starts or ends inside reads as part of a year, not a whole one.
    """
    columns = ["YEAR", "STRATEGY", "BENCHMARK", "ALPHA", "MONTHS", "FIRST", "LAST"]
    if grid is None or grid.empty or "CY RETURN" not in grid.columns:
        return pd.DataFrame(columns=columns)
    rows = []
    for year, block in grid.groupby("YEAR", sort=True):
        by = {str(s).lower(): r for s, r in zip(block["SERIES"], block.to_dict("records"))}
        strat = by.get("strategy")
        alpha = by.get("alpha")
        bench = next((r for s, r in by.items() if s not in ("strategy", "alpha")), None)
        if strat is None:
            continue
        held = [m for m in YEARLY_MONTHS if m in strat and strat[m] is not None and pd.notna(strat[m])]
        rows.append({
            "YEAR": int(year),
            "STRATEGY": strat.get("CY RETURN"),
            "BENCHMARK": bench.get("CY RETURN") if bench is not None else None,
            "ALPHA": alpha.get("CY RETURN") if alpha is not None else None,
            "MONTHS": len(held),
            "FIRST": held[0] if held else None,
            "LAST": held[-1] if held else None,
        })
    return pd.DataFrame(rows, columns=columns)


def _render_yearly_summary(grid: pd.DataFrame, bench_name: str) -> None:
    """The year-by-year block above the monthly grids (presentation only).

    Laid out like the monthly blocks below it (owner, 9 Oct 2026): Strategy,
    the index and Alpha as rows, one column per year; a year the window only
    partly covers names its months under the year.
    """
    table = yearly_summary(grid)
    if table.empty:
        return

    def cell(value):
        if value is None or pd.isna(value):
            return '<td class="cr-empty">—</td>'
        number = float(value)
        tone = "positive" if number > 0 else "negative" if number < 0 else "flat"
        return f'<td class="cr-value {tone}">{number:+.1%}</td>'

    heads = []
    for row in table.itertuples(index=False):
        span = ("" if row.MONTHS == 12 else
                f"{row.FIRST.title()}–{row.LAST.title()}" if row.MONTHS > 1 else
                (row.FIRST or "").title())
        sub = f'<span class="cr-part">{html.escape(span)}</span>' if span else ""
        heads.append(f"<th>{row.YEAR}{sub}</th>")
    series = [("Strategy", "strategy", "STRATEGY"), (bench_name, "benchmark", "BENCHMARK"),
              ("Alpha", "alpha", "ALPHA")]
    body = "".join(
        f'<tr><th scope="row" class="cr-series {klass}">{html.escape(label)}</th>'
        + "".join(cell(v) for v in table[col]) + "</tr>"
        for label, klass, col in series
    )
    st.html(
        '<section class="cr-year cr-yearly"><div class="cr-year-head">'
        '<div><span class="cr-kicker">YEAR BY YEAR</span><h3>Calendar years</h3></div>'
        '<span class="cr-year-note">The CY column of each year below</span>'
        '</div><div class="cr-scroll"><table class="cr-table cr-yearly-table">'
        f'<thead><tr><th class="cr-series-head">Series</th>{"".join(heads)}</tr></thead>'
        f'<tbody>{body}</tbody></table></div></section>'
        '<style>.cr-yearly{margin-bottom:14px}'
        f'.cr-yearly-table{{min-width:{120 + 74 * len(table)}px}}'
        '.cr-yearly-table .cr-part{display:block;font-weight:600;letter-spacing:0;'
        'text-transform:none;color:#8a93a6;font-size:9px;margin-top:2px}</style>'
    )


def _render_calendar_returns(grid: pd.DataFrame) -> None:
    """Render the calendar return grid as year-separated, responsive HTML tables.

    The underlying grid remains the engine's canonical compounded monthly/CY/FY
    data. This is presentation only: no returns are recalculated here.
    """
    if grid.empty:
        st.info("No full month in this window yet.")
        return

    month_cols = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                  "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    summary_cols = ["CY RETURN", "FY RETURN", "Q1", "Q2", "Q3", "Q4"]
    columns = month_cols + summary_cols

    def cell(value, *, summary=False):
        if value is None or pd.isna(value):
            return '<td class="cr-empty">—</td>'
        number = float(value)
        tone = "positive" if number > 0 else "negative" if number < 0 else "flat"
        extra = " cr-summary" if summary else ""
        return f'<td class="cr-value {tone}{extra}">{number:+.1%}</td>'

    blocks = []
    for year, year_df in grid.groupby("YEAR", sort=True):
        rows = []
        for _, row in year_df.iterrows():
            series = str(row.get("SERIES", ""))
            series_class = (
                "strategy" if series.lower() == "strategy"
                else "alpha" if series.lower() == "alpha"
                else "benchmark"
            )
            cells = "".join(cell(row.get(col), summary=col in summary_cols)
                            for col in columns)
            rows.append(
                f'<tr><th scope="row" class="cr-series {series_class}">'
                f'{html.escape(series)}</th>{cells}</tr>'
            )
        header = "".join(
            f'<th class="{"cr-summary-head" if col in summary_cols else ""}">{col}</th>'
            for col in columns
        )
        blocks.append(
            f'<section class="cr-year"><div class="cr-year-head">'
            f'<div><span class="cr-kicker">CALENDAR YEAR</span>'
            f'<h3>{int(year)}</h3></div>'
            f'<span class="cr-year-note">Monthly returns · compounded summaries</span>'
            f'</div><div class="cr-scroll"><table class="cr-table">'
            f'<thead><tr><th class="cr-series-head">Series</th>{header}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></section>'
        )

    st.html("""
    <style>
      .cr-wrap { display:grid; gap:14px; font-family:inherit; color:#172033; }
      .cr-year { background:#fff; border:1px solid #e2e7ef; border-radius:13px;
        overflow:hidden; box-shadow:0 2px 8px rgba(20,32,54,.035); }
      .cr-year-head { display:flex; align-items:center; justify-content:space-between;
        gap:12px; padding:13px 16px; background:linear-gradient(110deg,#f7f8ff,#fff);
        border-bottom:1px solid #e8ebf2; }
      .cr-kicker { display:block; font-size:9px; font-weight:800; letter-spacing:.13em;
        color:#68738a; }
      .cr-year-head h3 { margin:2px 0 0; font-size:21px; line-height:1.2;
        letter-spacing:-.04em; color:#172033; font-weight:750; }
      .cr-year-note { color:#778196; font-size:11px; text-align:right; }
      .cr-scroll { overflow-x:auto; -webkit-overflow-scrolling:touch; }
      .cr-table { border-collapse:separate; border-spacing:0; width:100%;
        min-width:980px; font-size:11px; font-variant-numeric:tabular-nums; }
      .cr-table th,.cr-table td { padding:10px 8px; text-align:center;
        border-bottom:1px solid #edf0f5; white-space:nowrap; }
      .cr-table thead th { background:#f8f9fc; color:#6b7486; font-size:9px;
        font-weight:800; letter-spacing:.045em; }
      .cr-table thead th:first-child { text-align:left; padding-left:15px; }
      .cr-table tbody tr:last-child th,.cr-table tbody tr:last-child td { border-bottom:0; }
      .cr-table tbody tr:hover { background:#fafbff; }
      .cr-series { text-align:left !important; padding-left:15px !important;
        font-size:11px; font-weight:750; color:#253047; min-width:86px; }
      .cr-series.strategy { border-left:3px solid #4f46e5; }
      .cr-series.benchmark { border-left:3px solid #94a3b8; }
      .cr-series.alpha { border-left:3px solid #d97706; }
      .cr-value { font-weight:650; }
      .cr-value.positive { color:#087443; }
      .cr-value.negative { color:#b42318; }
      .cr-value.flat,.cr-empty { color:#a0a8b7; }
      .cr-empty { background:#fbfcfe; }
      .cr-summary-head { background:#eef1ff !important; color:#4542a7 !important; }
      .cr-summary { background:#f7f8ff; font-weight:800; }
      .cr-table td.cr-summary { border-left:1px solid #e8eaff; }
      @media(max-width:640px) {
        .cr-year-head { padding:11px 12px; }
        .cr-year-head h3 { font-size:19px; }
        .cr-year-note { max-width:130px; font-size:10px; }
        .cr-table { min-width:940px; }
        .cr-table th,.cr-table td { padding:10px 7px; }
      }
    </style>
    """)
    st.html('<div class="cr-wrap">' + "".join(blocks) + '</div>')

# Every primary page is directly reachable on desktop. The compact
# popover remains the mobile/tablet navigation for the pages that do not fit.
_TOP_ROW_PAGES = tuple(p for p in (
    "Screener", "Portfolio", "Actions", "Sectors", "RRG", "Watchlist",
    "Market Breadth", "Backtest", "Configuration", "Guide",
))


def _status_pill_html() -> str:
    """Green "Prices · closes of 25 Sep", or amber naming the stale source."""
    try:
        items = data_freshness()
    except Exception:
        items = []
    stale = [i for i in items if i.get("stale")]
    prices = next((i for i in items if i.get("label") == "Prices"), None)
    if stale:
        lead, tail = f"{stale[0]['label']} · ", str(stale[0]["as_of"])
        cls = "hdr-pill hdr-pill-warn"
    elif prices is not None:
        lead, tail = "Prices · closes of ", str(prices["as_of"])
        cls = "hdr-pill"
    else:
        return ""
    # The lead words drop on a phone; the date and the colour carry it there.
    return (f'<span class="{cls}" title="{html.escape(lead + tail)}"><span class="hdr-dot"></span>'
            f'<span><span class="hdr-pill-lead">{html.escape(lead)}</span>{html.escape(tail)}</span></span>')


def render_header_kpi_bar(
    regime: RegimeData,
    total_stocks: int,
    above_ema: int,
    pct_above_ema: float,
    near_high: int | None = None,
    nav_pages: list | None = None,
    active_page: object | None = None,
) -> None:
    """Top bar (brand, page links, data status, and responsive menu) and market line.

    Desktop exposes every primary page directly; the compact menu is reserved
    for narrower viewports where the full navigation no longer fits.
    """
    bullish = regime.status == MarketRegime.BULLISH
    regime_cls = "mkt-up" if bullish else "mkt-down"
    dist = regime.distance_pct
    dist_text = f"{abs(dist):.1f}% {'above' if dist >= 0 else 'below'}"
    market_html = f"""
    <div role="status" aria-label="Market status dashboard" class="mkt-snapshot">
        <div class="mkt-item mkt-regime-item">
            <span class="{regime_cls} mkt-regime"><span class="mkt-dot">●</span>{html.escape(regime.status.value.title())}</span>
        </div>
        <div class="mkt-item mkt-index">
            <span class="mkt-label">NIFTY 500</span>
            <strong>{regime.current_price:,.0f}</strong>
        </div>
        <div class="mkt-item mkt-distance">
            <strong class="{'mkt-up' if dist >= 0 else 'mkt-down'}">{dist_text}</strong>
            <span class="mkt-label">200D average</span>
        </div>
        <div class="mkt-item">
            <span class="mkt-label">Universe</span>
            <strong>{total_stocks}</strong>
        </div>
        <div class="mkt-item">
            <span class="mkt-label">Above 50D EMA</span>
            <strong>{above_ema} <em>({pct_above_ema:.0f}%)</em></strong>
        </div>
        {"" if near_high is None else f'<div class="mkt-item"><span class="mkt-label">Within 20% 52W High</span><strong>{near_high} <em>({near_high / total_stocks * 100 if total_stocks else 0:.0f}%)</em></strong></div>'}
    </div>
    """

    # One menu key per page. Streamlit keeps a keyed popover open across the
    # rerun its own contents trigger, and choosing a page IS such a rerun: on
    # desktop the menu stayed open over the page just chosen until the reader
    # clicked elsewhere (production QA run 570's screenshot, which is also
    # why that run could not click "Reset to defaults"). A key that changes
    # with the page makes the next page's menu a new, closed popover.
    _page_slug = re.sub(
        r"[^A-Za-z0-9_-]", "_", str(getattr(active_page, "url_path", "") or "home"))
    with st.container(key="app_header_shell", width="stretch", horizontal=True,
                      vertical_alignment="center", gap="small", wrap=False):
        # The brand is the way home: a page link to the Screener, so it opens
        # in place like every other page link (and clears ?stock=). Named
        # exactly "Paresh Patel", as the owner asked.
        if nav_pages:
            with st.container(key="app_brand", width="content"):
                st.page_link(nav_pages[0], label="Paresh Patel")
        else:
            st.html('<span class="hdr-title">Paresh Patel</span>', width="content")
        if nav_pages:
            # Desktop shows the complete primary navigation directly. CSS hides
            # this row below 900px, where the compact popover takes over.
            with st.container(key="app_toplinks", horizontal=True,
                              vertical_alignment="center", gap=None, width="stretch"):
                for _i, _p in enumerate(nav_pages):
                    if getattr(_p, "title", "") not in _TOP_ROW_PAGES:
                        continue
                    _state = "navon" if _p is active_page else "navoff"
                    with st.container(key=f"{_state}_top_{_i}", width="content"):
                        st.page_link(_p)
        pill = _status_pill_html()
        if pill:
            st.html(pill, width="content")
        if nav_pages:
            # Mobile/tablet only. Desktop CSS hides the popover trigger.
            with st.popover(
                    "☰",
                    type="tertiary",
                    help="Open navigation",
                    width=320,
                    key=f"app_nav_menu_{_page_slug}",
                ):
                    st.markdown("**Research**")
                    for _i, _p in enumerate(nav_pages[:5]):
                        _state = "navon" if _p is active_page else "navoff"
                        with st.container(key=f"{_state}_research_{_i}", width="stretch"):
                            st.page_link(_p)

                    st.markdown("**Monitoring**")
                    for _i, _p in enumerate(nav_pages[5:9], start=5):
                        _state = "navon" if _p is active_page else "navoff"
                        with st.container(key=f"{_state}_monitoring_{_i}", width="stretch"):
                            st.page_link(_p)

                    st.markdown("**System**")
                    for _i, _p in enumerate(nav_pages[9:], start=9):
                        _state = "navon" if _p is active_page else "navoff"
                        with st.container(key=f"{_state}_system_{_i}", width="stretch"):
                            st.page_link(_p)
    st.html(market_html)


def signal_chips_html(signals: list[SignalAlert]) -> str:
    """The Screener's signal chips, for its title row ("" when there are none)."""
    chips = "".join(
        f'<span class="sig-chip" style="color:{s.color};background:{s.color}14;'
        f'border-color:{s.color}2E;font-size:0.9rem">{html.escape(str(s.text))}</span>'
        for s in signals
    )
    return (f'<div class="sig-row" role="status" aria-label="Signals today">{chips}</div>'
            if chips else "")


def stat_pill(label: str, value: Any, color: str = "indigo") -> str:
    """Helper to generate styled badge HTML."""
    color_map = {
        "indigo": ("#eef2ff", "#4f46e5", "#c7d2fe"),
        "emerald": ("#E8F5EE", "#067647", "#a7f3d0"),
        "rose": ("#FDEDEB", "#B42318", "#F3C7C1"),
        "amber": ("#FEF6EA", "#B54708", "#F5D7A8"),
        "sky": ("#f0f9ff", "#0284c7", "#bae6fd"),
    }
    bg, fg, bdr = color_map.get(color, color_map["indigo"])
    return (
        f'<span style="display: inline-flex; align-items: center; gap: 6px; border-radius: 6px; '
        f"padding: 3px 10px; font-family: 'Geist Mono', monospace; font-size: 0.76rem; "
        f'background-color: {bg}; color: {fg}; border: 1px solid {bdr}; font-weight: 500; margin: 2px 4px 2px 0;">'
        f'{label}: <strong style="font-weight: 700;">{value}</strong></span>'
    )



# Sources whose age is worth stating, and how many trading days each may fall
# behind before it is called stale. Market caps publish only after
# the close, so being one trading day behind is their normal state, not a fault.
# (date fact, label, tolerance in trading days, "source is loaded" fact)
#
# The fourth entry matters. A source whose date is unknown used to be dropped
# from the ribbon entirely, so "Market caps" simply vanished when the committed
# snapshot predated AsOf stamping -- the reader saw a clean bar and had no way
# to tell a source was being used undated. If the loader says it loaded
# something, it gets a chip, dated or not.
_FRESHNESS_SOURCES: list[tuple[str, str, int, str | None]] = [
    ("price_as_of", "Prices", 1, "price_path"),
    ("mcap_as_of", "Market caps", 1, "mcap_path"),
    ("ath_as_of", "All-time highs", 3, "ath_path"),
]


def data_freshness() -> list[dict]:
    """Age of each data source, judged in trading days.

    Read from the startup telemetry the loaders already record, so the twelve
    views that render the footer need no extra arguments and cannot disagree
    with each other about how old the data is.

    Trading days, not calendar days: a Monday showing Friday's market caps is
    current, and a festival cluster must not read as an outage.
    """
    from datetime import date as _date

    from src.core import startup_metrics as _metrics
    from src.core.market_time import ist_today, trading_days_behind

    facts = _metrics.snapshot().get("facts", {})
    items: list[dict] = []
    for key, label, tolerance, presence_key in _FRESHNESS_SOURCES:
        raw = facts.get(key)
        if not raw:
            # No date. If the loader reported using this source anyway, say so
            # rather than omitting the row -- an undated snapshot could be any
            # age, which is the definition of stale.
            presence = str(facts.get(presence_key) or "").strip() if presence_key else ""
            if key == "ath_as_of" and presence in {"absent", "unreadable", "malformed"}:
                # The snapshot is missing, so the engine fell back to the high
                # water mark of the two-year window. That is NOT an all-time
                # high, and the column should not be read as one.
                items.append({
                    "label": label,
                    "as_of": "2y window, not all-time",
                    "date": None,
                    "behind": None,
                    "stale": True,
                    "source": presence,
                })
            elif presence and presence not in {"absent", "unreadable", "malformed"}:
                items.append({
                    "label": label,
                    "as_of": "date unknown",
                    "date": None,
                    "behind": None,
                    "stale": True,
                    "source": presence,
                })
            continue
        try:
            as_of = _date.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
        behind = trading_days_behind(as_of)
        # None means older than the horizon entirely, which is stale by any
        # reading. Anything within tolerance is simply the publication lag.
        stale = behind is None or behind > tolerance
        items.append({
            "label": label,
            "as_of": as_of.strftime("%d %b"),
            # The date itself, for callers that need a different format or the
            # year. Re-parsing "28 Aug" to get it back is how a second, subtly
            # different notion of the as-of date gets born.
            "date": as_of,
            "behind": behind,
            # behind == 0 means "the most recent TRADING day", which on a
            # weekend or a holiday is not today. The ribbon needs to tell those
            # apart: printing "21 Aug - today" on a Sunday reads as a bug in
            # the pipeline, and a freshness indicator that raises a false alarm
            # is failing at the one job it has.
            "is_today": as_of == ist_today(),
            "stale": stale,
            "source": facts.get(presence_key) if presence_key else None,
        })

    # Coverage on the priced row, and the session held back behind it.
    #
    # The ranking stops at the newest session the vendor has finished, so the
    # frame can visibly reach a later date than the table is labelled with. On
    # 2026-09-18 that was 17 Sep in the frame against 16 Sep on the table, and
    # with only the date shown it reads as the pipeline being a day stale --
    # or, worse, as the table silently describing 17 Sep. Naming both, with
    # the coverage that decided it, is the difference between a deliberate
    # wait and an apparent fault.
    prices = next((i for i in items if i["label"] == "Prices"), None)
    if prices is not None:
        prices["coverage"] = str(facts.get("price_coverage") or "").strip() or None

    # WHICH source produced the ranking, and on what the 52-week high is
    # measured. Not a detail: on screener data the high is taken from CLOSES
    # because no intraday high exists in that feed, which moves the
    # "within 5% of the 52-week high" gate from 22 names to 50 on the live
    # universe. A reader comparing this screener against a chart elsewhere has
    # to be able to see why the two disagree.
    source = str(facts.get("price_source") or "").strip()
    if source:
        # Which history produced the table, under its display name. The reader
        # needs this to make sense of the 52-week-high chip below and of the
        # ATR columns being present or absent -- those follow from the source,
        # and without it they look arbitrary.
        from src.loaders.price_source import display_name

        items.append({
            "label": "Ranked from",
            "as_of": display_name(source),
            "date": None,
            "behind": 0,
            "is_today": False,
            "stale": False,
            "phrase": "",
            "source": source,
        })
    if source and prices is not None:
        prices["source"] = source
        basis = str(facts.get("price_high_basis") or "").strip()
        if basis:
            prices["high_basis"] = basis

    deferred_day = str(facts.get("price_deferred_as_of") or "").strip()
    if deferred_day:
        try:
            _d = _date.fromisoformat(deferred_day[:10])
        except ValueError:
            _d = None
        if _d is not None:
            cov = str(facts.get("price_deferred_coverage") or "").strip()
            items.append({
                "label": "Latest session",
                "as_of": _d.strftime("%d %b"),
                "date": _d,
                "behind": 0,
                "is_today": _d == ist_today(),
                # Not a fault and must not render as one. The vendor publishes
                # an Indian session over roughly a day and a half; waiting for
                # it is the correct behaviour, and an amber chip here would
                # train the reader to ignore the ones that do mean something.
                "stale": False,
                "coverage": cov or None,
                "phrase": " · still publishing",
                "source": "deferred",
            })
    return items


def age_phrase(item: dict) -> str:
    """How old a source is, in words. The one place that decides.

    Used by the freshness ribbon at the foot of the page and by the date in the
    header, which must agree: they are two renderings of one fact, and when
    they disagreed the header was the one people believed.
    """
    from src.core.market_time import session_is_complete

    # An item may state its own age in words. "Latest session" is the case:
    # it is not behind anything, it is ahead and still arriving, and every
    # phrase below would misdescribe that.
    # `is not None`, not truthiness: an item may deliberately want NO phrase.
    # "Ranked from: screener" needs no age suffix, and an empty string that
    # fell through to the age logic read as "Ranked from: screener - latest
    # session", which describes nothing.
    override = item.get("phrase")
    if override is not None:
        return str(override)

    behind = item.get("behind")
    if behind is None:
        return " · stale"
    if behind <= 0:
        if not item.get("is_today"):
            return " · latest session"
        # Today's row exists from the first trade of the day. Until the session
        # settles it is a running quote, not a close, and saying plainly
        # "today" invites the reader to treat a 09:20 print as the day's
        # result.
        day = item.get("date")
        if day is not None and not session_is_complete(day):
            return " · today, session open"
        return " · today"
    if behind == 1:
        return " · 1 trading day behind"
    return f" · {behind} trading days behind"


def header_as_of() -> tuple[str, str]:
    """The date for the header bar, and the colour to render it in.

    This is the PRICE DATA's own as-of date. The header used to print
    ``datetime.now()`` -- the server's wall clock, in the server's timezone,
    stamped beside the market status where every reader takes it for the date
    of the numbers next to it. It stayed reassuring no matter how old those
    numbers were: a price cache stuck on 21 August still announced 31 August at
    the top of the page, and the one honest indicator sat in a ribbon far below
    the fold.

    Two bugs in one line, in fact. ``datetime.now()`` is also naive server time,
    which on Streamlit Cloud is UTC -- so for the five and a half hours each
    evening when India is already on the next date, the header printed
    YESTERDAY even when everything was working.
    """
    prices = next(
        (i for i in data_freshness() if i["label"] == "Prices"), None
    )
    if prices is None or prices.get("date") is None:
        # Better an admission than a date. The loaders stamp this on every
        # return path; nothing arriving here means the pipeline did something
        # unexpected, which is not the moment to print a confident date.
        return "price date unknown", "#B54708"
    cov = str(prices.get("coverage") or "").strip()
    suffix = f" · {cov}" if cov else ""
    return (
        f"{prices['date'].strftime('%d %b %Y')}{suffix}{age_phrase(prices)}",
        "#B54708" if prices["stale"] else "#5E6878",
    )


def render_freshness_ribbon() -> None:
    """A bottom ribbon mirroring the signal ribbon at the top of the page.

    Same chip language as render_signal_alerts, deliberately: the top strip
    tells you what the market did, this one tells you how current the numbers
    behind it are, and a reader should not have to learn two visual idioms to
    read the same page.

    Every source is shown with its as-of date, not just the stale ones. A
    warning that appears only on failure means the normal state tells the
    reader nothing; a date that is always present makes staleness self-evident
    and earns trust the rest of the time. Stale sources turn amber and lead.
    """
    items = data_freshness()
    if not items:
        return

    # Stale first: the thing a reader needs to notice should not be third.
    items = sorted(items, key=lambda i: (not i["stale"],))

    chips_html = ""
    for item in items:
        color = "#B54708" if item["stale"] else "#067647"
        icon = "&#9888;&#65039;" if item["stale"] else "&#9679;"
        age = age_phrase(item)
        label = html.escape(str(item["label"]))
        as_of = html.escape(str(item["as_of"]))
        cov = str(item.get("coverage") or "").strip()
        if cov:
            as_of = f"{as_of} · {html.escape(cov)}"
        chips_html += (
            f'<div style="display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 10px; '
            f'border-radius: 8px; background-color: {color}12; border: 1px solid {color}2E; '
            f"font-family: var(--font-ui); font-size: 12.5px; color: {color}; "
            f'font-weight: 600; white-space: nowrap; flex-shrink: 0;">'
            f"<span>{icon}</span><span>{label}: {as_of}{age}</span></div>"
        )

    st.markdown(
        '<div role="status" aria-label="Data freshness" style="display: flex; align-items: center; '
        "gap: 8px; overflow-x: auto; padding: 14px 0 4px; border-top: 1px solid #E3E6EB; "
        "margin-top: 22px; margin-bottom: 2px; "
        'scrollbar-width: thin; scrollbar-color: #D0D5DD transparent;">'
        f"{chips_html}</div>",
        unsafe_allow_html=True,
    )


def gap_count(rank_df: pd.DataFrame) -> int:
    """Stocks flagged 🔴 (gap-filled >10%) in the Data Gap column.

    Contains, not equals: the cell can carry more than one mark -- a stock
    ranked on its last print appends CARRIED_MARK -- and eleven views used to
    count with ``== "🔴"``, which silently dropped exactly those rows.
    """
    col = rank_df.get("Data Gap") if rank_df is not None else None
    if col is None:
        return 0
    return int(col.astype(str).str.contains("🔴", regex=False).sum())


def render_data_quality_footer(
    total_stocks: int, gap_count: int, short_count: int
) -> None:
    """Renders the data quality footer bar, including how old each source is.

    The signature is unchanged on purpose: twelve views call this, and the
    freshness figures come from the loaders' own telemetry rather than from
    twelve call sites that could drift apart.

    The as-of date is shown ALWAYS, not only when something is wrong. A
    warning that appears only on failure means the normal state tells the
    reader nothing; a date that is always present makes staleness
    self-evident and earns trust the rest of the time.

    Styling is inline to match the rest of this bar. The design-system
    stylesheet was reverted, so class-based styling would render unstyled.
    """
    # Drawn here rather than at twelve call sites, for the same reason the
    # freshness figures are read from telemetry: one place to change, and no
    # way for two tabs to disagree.
    #
    # The ribbon owns the as-of dates. This bar used to restate all of them one
    # line below it, plus a "some data is behind" flag duplicating the amber
    # chips -- the same three dates printed twice, a few pixels apart, in two
    # different visual idioms. The ribbon is the better of the two (it carries
    # the age, colours staleness, and leads with the stale source), so the bar
    # keeps only what is unique to it: coverage, data-quality counts, and the
    # stop-loss convention.
    render_freshness_ribbon()

    # Where this process loaded its published data from: R2 first, the
    # release files when R2 was unavailable (src/loaders/app_source.py).
    from src.loaders import app_source as _src

    _where = _src.summary()
    # Screener is an internal implementation detail. Never expose the
    # storage/provider name in the public UI; the user-facing source label is
    # the established "Personal" name whenever Screener contributes.
    _public_where = "Personal" if "screener" in _where.lower() else _where
    source_note = (
        f'<span style="color: #A5ACB8;">·</span><span>Data from: '
        f'<strong style="color: #0E1726;">{html.escape(_public_where)}</strong></span>'
        if _public_where else ""
    )
    footer_html = f"""
    <div style="display: flex; align-items: center; gap: 8px 12px; flex-wrap: wrap; padding: 6px 0 24px; font-family: var(--font-ui); font-size: 12.5px; color: #5E6878;">
        <span>Gap-filled over 10% (12 months): <strong style="color: {"#B54708" if gap_count else "#0E1726"};">{gap_count}</strong></span>
        <span style="color: #A5ACB8;">·</span>
        <span>Short history (under 126 sessions): <strong style="color: #0E1726;">{short_count}</strong></span>
        {source_note}
        <span style="margin-left: auto; color: #3C4657;">© Paresh Patel</span>
    </div>
    """
    st.html(footer_html)
