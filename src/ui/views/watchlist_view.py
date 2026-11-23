"""
The reader's watchlist (S182; mock-up v1 approved by the owner, 22 Nov 2026).

The list lives in the reader's own browser (src/ui/watchlist_store.py): private
to them, kept across visits, and added to from any stock page with one click.

The page answers for the names the reader chose what the Screener cannot: which
of them the book would buy, keep or sell at the next rebalance, how far each is
from the book's lines, why a name is missing, and what is due before the fill.
The words and their sources are in src/ui/watchlist_lines.py; the table is the
Screener's own (src/ui/screener_table.py), fed the Screener's qualified place and
"Held" marks (ranking_view.with_book_columns, S184).

Order (approved): Watchlist → Against the book's lines → Not ranked → Before the
fill → Data to.
"""

import html

import pandas as pd
import streamlit as st

from src.core.market_time import ist_now

from src.ui import formats
from src.ui import watchlist_lines as wl
from src.ui import watchlist_store
from src.ui.components import gap_count, render_data_quality_footer
from src.ui.screener_table import render_screener_table

e = html.escape


# There used to be a second layer: data/user_watchlist.json on the server's
# disk, read back whenever the reader had no list of their own. On the public
# deployment that file is shared by every visitor, so one reader's saved
# watchlist became every other reader's default. The list is per-reader now,
# in their browser; the server never stores it.
def _save_from_input() -> None:
    watchlist_store.save(watchlist_store.parse(st.session_state.get("wl_input_main", "")))


def _add_picked() -> None:
    """A stock chosen in the name search is added to the end of the list (S219-5)."""
    sym = st.session_state.get("wl_add_pick")
    st.session_state["wl_add_pick"] = None
    cur = watchlist_store.symbols()
    if sym and sym not in cur:
        watchlist_store.save(cur + [sym])


def search_options(rank_df: pd.DataFrame, listed=()) -> dict[str, str]:
    """{symbol: "SYMBOL · Company name"} for the ranked stocks not yet listed, in rank order: the
    Screener's search box (ranking_view, one selectbox, index None) with the company's name in the
    label, so typing a name or a symbol finds the stock (S219-5, owner 23 Nov 2026)."""
    if rank_df is None or rank_df.empty or "Symbol" not in rank_df:
        return {}
    df = rank_df.sort_values("Rank") if "Rank" in rank_df else rank_df
    names = df["Company Name"] if "Company Name" in df else pd.Series("", index=df.index)
    seen = set(listed)
    out: dict[str, str] = {}
    for sym, name in zip(df["Symbol"].astype(str), names):
        if sym in seen or sym in out:
            continue
        nm = str(name).strip() if isinstance(name, str) else ""
        out[sym] = f"{sym} · {nm}" if nm and nm != sym else sym
    return out


def _remove_picked() -> None:
    sym = st.session_state.pop("wl_remove_pick", None)
    if sym:
        watchlist_store.save([s for s in watchlist_store.symbols() if s != sym])


def _replace(old: str, new: str) -> None:
    """A renamed symbol swapped for its new ticker, in place."""
    cur = watchlist_store.symbols()
    watchlist_store.save([new if s == old else s for s in cur])


@st.cache_data(show_spinner=False, ttl=3600)
def _nse_lists() -> tuple[pd.DataFrame, set]:
    """NSE's ticker changes and the symbols it lists today (data/reference/nse)."""
    from src.loaders import nse_identity
    return nse_identity.symbol_changes(), set(nse_identity.current_isins().values())


WL_CSS = """
.wl-head{display:flex;flex-direction:column;gap:8px;padding-top:8px}
.qp-kick{margin:0;font-size:var(--fs-12);font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--c-muted)}
.dh .wl-title{max-width:36ch}
.wl-kept{margin:2px 0 0;font-size:var(--fs-13);color:var(--c-muted);max-width:80ch}
.wl-phone{display:none}
.wl-tab{border-collapse:collapse;width:100%;font-size:var(--fs-13);border-top:1.5px solid var(--c-ink)}
.wl-tab th{font-size:var(--fs-12);font-weight:600;color:var(--c-muted);text-align:left;padding:8px;border-bottom:1px solid var(--c-rule_strong)}
.wl-tab td{padding:8px;border-bottom:1px solid var(--c-rule);vertical-align:top;text-align:left}
.wl-tab th[scope=row]{white-space:nowrap;font-family:var(--font-mono);font-weight:600;color:var(--c-ink);font-size:var(--fs-13);text-align:left;vertical-align:top}
.wl-tab a{color:var(--c-ink)}
.wl-wrap{overflow-x:auto}
.wl-keys{columns:2;column-gap:40px;font-size:var(--fs-13);color:var(--c-muted)}
.wl-keys p{margin:0 0 6px;break-inside:avoid;max-width:80ch;line-height:1.5}
.wl-keys b{color:var(--c-ink);font-weight:600}
@media (max-width:900px){.wl-keys{columns:1}}
.wl-list{margin:0;padding-left:18px;font-size:var(--fs-13)}
@media (max-width:640px){.wl-phone{display:block}.wl-tab td,.wl-tab th{padding:6px 4px}}
"""


def _emit(parts: list) -> None:
    from src.ui.views.dashboard_home_view import emit
    emit(parts)


def _kick(text: str) -> str:
    return f'<p class="dh-kick">{e(text)}</p>'


def _universe(system_name: str, ranked_name: str | None) -> str:
    return ranked_name or system_name


def render_watchlist_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame | None = None,
                          book_symbols=None,
                          history_prices: pd.DataFrame | None = None, *,
                          benchmark_close: pd.Series | None = None, system: str = "750",
                          system_name: str = "Nifty 750", ranked_name: str | None = None,
                          ranked_note: str = "", members=(), other_rankings=None) -> None:
    """The reader's watchlist: edit it here, or star stocks on their pages.

    `system_name` is the system chosen; `ranked_name` the list actually ranked when
    it differs (the Nifty 1000 without its list ranks the 750), with `ranked_note`
    saying so. `members` is the chosen system's list (for "too new to rank");
    `other_rankings()` returns {system name: ranking} for the other systems' same
    session, read only when a symbol is not ranked here."""
    from src.ui.views.dashboard_home_view import HOME_CSS
    from src.ui.views.portfolio_page import PF_CSS
    from src.ui.views.ranking_view import with_book_columns

    universe = _universe(system_name, ranked_name)
    ln = wl.lines()
    user_symbols = watchlist_store.symbols()
    prices = history_prices if history_prices is not None else adj_close
    # The qualified place and "Held" come from the whole ranking, as on the
    # Screener; from the bare ranking every row read "Out" (S184, 22 Nov 2026).
    full = with_book_columns(rank_df, book_symbols, prices)
    matched = full[full["Symbol"].isin(user_symbols)].sort_values("Rank").copy()
    # The session the header shows, not the frame's last row (S193 E).
    as_of = (formats.session_of(adj_close if adj_close is not None and len(adj_close.index) else prices)
             if prices is not None and len(prices.index) else pd.Timestamp(ist_now().date()))

    plan = None
    if user_symbols and not matched.empty:
        try:
            with st.spinner("Reading the plan…"):
                plan = wl.book_plan(rank_df, prices, benchmark_close, system)
        except Exception:  # noqa: BLE001 -- a failure costs the plan's column, never the page
            plan = None

    st.html(f"<style>{HOME_CSS}{PF_CSS}{WL_CSS}</style>")
    when = f"Ranked in {wl.fmt_system(universe)} at the {wl.fmt_day(as_of)} close."
    if ranked_note:
        when += f" {ranked_note}"
    if not user_symbols:
        title = e("Your watchlist is empty.")
        lede = ("Search a stock by name, type symbols and save, or press “Add to watchlist” on any stock's page. "
                "The list is kept in this browser only.")
    else:
        title = wl.title(matched, len(user_symbols), plan, ln)
        lede = f"{when} {wl.plan_sentence(matched, plan)}"
    _emit([f'<div class="wl-head"><p class="qp-kick">Watchlist</p>'
           f'<h1 class="dh-h1 wl-title">{title}</h1><p class="dh-lede">{e(lede)}</p></div>'])

    current = ", ".join(user_symbols)
    if st.session_state.get("_wl_input_shown") != current:
        # Follow the stored list (a star on a stock page, the browser loading
        # it) without fighting the reader's typing between saves.
        st.session_state["wl_input_main"] = current
        st.session_state["_wl_input_shown"] = current

    opts = search_options(rank_df, user_symbols)
    with st.container(horizontal=True, key="wl_editbar", vertical_alignment="bottom"):
        # Add one stock by name or symbol, as the Screener's search; the box beside it still takes
        # several symbols pasted at once.
        st.selectbox("Add a stock", options=list(opts), index=None, format_func=lambda o: opts.get(o, o),
                     placeholder="Add a stock by name or symbol", key="wl_add_pick",
                     label_visibility="collapsed", on_change=_add_picked, width=280,
                     help="Type part of a company’s name or its symbol, then pick it: it is added and saved.")
        st.text_input(
            "Symbols",
            placeholder="Comma-separated symbols, e.g. RELIANCE, TCS, CUPID, INFY, DIACABS",
            key="wl_input_main",
            label_visibility="collapsed",
        )
        # Not disabled while the box is empty: Streamlit reads typed text only on
        # a rerun, so a disabled button would swallow the click that follows typing.
        st.button("Save watchlist", type="primary", key="wl_update_btn",
                  on_click=_save_from_input, help="Saved in this browser only.")
        if user_symbols:
            with st.popover("Remove a stock", icon=":material/remove_circle_outline:"):
                st.pills("Remove", user_symbols, key="wl_remove_pick",
                         on_change=_remove_picked, label_visibility="collapsed")
        if not matched.empty:
            # Exact figures, every column the ranking has (exports stay exact).
            st.download_button("Export CSV", matched.to_csv(index=False).encode(),
                               f"watchlist_momentum_{ist_now():%Y%m%d}.csv", "text/csv",
                               key="dl_wl_csv", icon=":material/download:")
    if user_symbols:
        _emit(['<p class="wl-kept">Kept in this browser only. Search a stock by name, or press “Add to watchlist” on its page, to add it; '
               'clear the box and save to empty the list.</p>'])

    # The empty list used to `return` here, which is why Watchlist was the only
    # page of eleven with no data-quality footer (slot 10, 10 Nov 2026): every
    # page ends the same way, the empty state too.
    if user_symbols:
        if matched.empty:
            _emit(_sec_lines_empty(universe))
        else:
            _lines_section(matched, prices, plan, ln, len(rank_df))
        missing = [s for s in user_symbols if s not in set(rank_df["Symbol"])]
        if missing:
            _not_ranked_section(missing, full, universe, members, other_rankings, ln)
        if not matched.empty and plan is not None:
            _fill_section(matched, plan)

    _emit([f'<p class="dh-foot">{e(_foot(as_of, user_symbols, matched, rank_df))}</p>'])
    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
        # No `as_of`: the page's own foot line above carries "Data to <date> · NSE" (S173 rule 7).
    )


def _sec_lines_empty(universe: str) -> list:
    return ['<section class="dh-sec">', _kick("Against the book's lines"),
            f'<h2 class="dh-h2">None of your symbols is ranked in {e(wl.fmt_system(universe))}.</h2>', "</section>"]


def _lines_section(matched: pd.DataFrame, prices, plan, ln, n_ranked: int) -> None:
    from src.ui.views.ranking_view import _month_ago
    table, heads = wl.grouped(matched, plan, ln)
    plan_label = wl.fmt_day(plan.check) if plan is not None else "Plan"
    _emit(['<section class="dh-sec">', _kick("Against the book's lines"),
           f'<h2 class="dh-h2">{e(wl.lines_heading(table, plan, ln))}</h2>',
           f'<p class="dh-note">Your stocks in rank order, grouped by where they sit against the book\'s lines: '
           f'it buys the top {ln.buy} qualified and keeps a holding while it is in the top {ln.keep}.</p>',
           "</section>"])
    render_screener_table(table, prices, "Watchlist", groups=heads, plan_label=plan_label)
    d3, d1 = _month_ago(prices, 3), _month_ago(prices, 1)
    trail = (f"on {wl.fmt_day(d3)} and {wl.fmt_day(d1)}" if d3 is not None and d1 is not None
             else "3 months and a month ago")
    n = len(table)
    keys = [
        f"<b>Qualified:</b> above the 50D EMA and within {ln.high_gap}% of the 52W high. The qualified place is "
        "the stock's place among them, the number Actions and the Dashboard use; “Out” means it failed a filter that day.",
        f"<b>Rank before:</b> the rank among the {n_ranked:,} ranked stocks {trail}, the dates the Dashboard's rank trail uses. "
        "Past figures are grey.",
        (f"<b>{e(plan_label)}:</b> what the model book does at the next rebalance if today's prices hold, from the "
         f"plan Actions shows; “{wl.MISSING}” where it neither holds nor buys the stock. <b>Held:</b> in the model book."
         if plan is not None else
         f"<b>Plan:</b> “{wl.MISSING}” on every row: the model book's plan could not be read just now. "
         "<b>Held:</b> in the model book."),
        "A click on a heading sorts every stock and drops the groups; Rank brings them back.",
    ]
    _emit([f'<p class="dh-note wl-phone">On a wider screen: rank among the {n_ranked:,} ranked stocks, the trail 3M and 1M ago, '
           'returns, filters and the 60-day line.</p>',
           '<div class="wl-keys">' + "".join(f"<p>{k}</p>" for k in keys) + "</div>"
           if n else ""])


def _not_ranked_section(missing: list, full: pd.DataFrame, universe: str, members, other_rankings, ln) -> None:
    from urllib.parse import quote

    from src.ui.system_param import suffix
    changes, listed = _nse_lists()
    others = {}
    try:
        others = other_rankings() if callable(other_rankings) else (other_rankings or {})
    except Exception:  # noqa: BLE001 -- another system's ranking is a pointer, never a reason to fail
        others = {}
    rows = wl.not_ranked(missing, full, universe=universe, members=members, changes=changes,
                         listed=listed, others=others, ln=ln)
    if not rows:
        return
    body = []
    for r in rows:
        where = e(r.where)
        if r.kind == wl.ELSEWHERE and r.system:
            sys_key = {v: k for k, v in _system_names().items()}.get(r.system)
            if sys_key:
                href = f"screener?stock={quote(r.symbol, safe='')}{suffix(sys_key)}"
                where += f' <a href="{e(href)}" target="_self">{e(r.link_label)}</a>'
        body.append(f'<tr><th scope="row">{e(r.symbol)}</th><td>{e(r.why)}</td><td>{where}</td></tr>')
    _emit(['<section class="dh-sec">', _kick("Not ranked"),
           f'<h2 class="dh-h2">{e(wl.not_ranked_heading(rows, universe))}</h2>',
           '<div class="wl-wrap"><table class="wl-tab"><thead><tr><th scope="col">Symbol</th>'
           '<th scope="col">Why it is not here</th><th scope="col">Where it is</th></tr></thead>'
           f'<tbody>{"".join(body)}</tbody></table></div>', "</section>"])
    swaps = [r for r in rows if r.replace_with]
    if swaps:
        with st.container(horizontal=True, key="wl_replace_bar"):
            for r in swaps:
                st.button(f"Replace with {r.replace_with}", key=f"wl_rep_{r.symbol}",
                          on_click=_replace, args=(r.symbol, r.replace_with),
                          help=f"Puts {r.replace_with} in place of {r.symbol} on your list.")


def _system_names() -> dict:
    from src.engine.extra_universe import SYSTEM_NAMES
    return dict(SYSTEM_NAMES)


def _fill_section(matched: pd.DataFrame, plan) -> None:
    """Actions row 28's check, run for the listed stocks: board meetings and ex-dates
    from the day after the data to the fill, in Actions' own words for its limits."""
    from src.engine import results_calendar as rc
    from src.ui.views.actions_page import _events
    syms = matched["Symbol"].astype(str).tolist()
    events, note = _events(syms, set(plan.sells), set(plan.buys), plan.as_of, plan.fill)
    role = {wl.BUY: "to buy", wl.SELL: "to sell", wl.HOLD: "held", wl.NEXT: "next in line"}
    items = "".join(
        f"<li><b>{e(str(sym))}</b>"
        + (f" ({e(role[plan.word(str(sym))])})" if plan.word(str(sym)) in role else "")
        + f" {e(str(what))}, {e(wl.fmt_day(d))}</li>" for d, sym, _r, what in events)
    cal = rc.load()
    rep = rc.for_book(cal, syms, [], plan.as_of + pd.Timedelta(days=1)) if cal is not None else None
    past = wl.reported_sentence(rep.reported if rep is not None else None, len(syms))
    _emit(['<section class="dh-sec">', _kick("Before the fill"),
           f'<h2 class="dh-h2">{e(wl.fill_heading(events, plan.fill))}</h2>',
           f'<ul class="wl-list">{items}</ul>' if items else "",
           f'<p class="dh-note">{e((past + " ") if past else "")}{e(note)}</p>', "</section>"])


def _foot(as_of, user_symbols: list, matched: pd.DataFrame, rank_df: pd.DataFrame) -> str:
    """The data date and the list's own data health; the exchange named, never the vendor (S173 rule 7)."""
    text = f"{formats.data_to(as_of)}."
    if not user_symbols:
        return text
    n, k = len(user_symbols), len(matched)
    text += f" {k} of your {wl.fmt_count(n, 'symbol')} ranked among the {len(rank_df):,}"
    if not k:
        return text + "."
    hz = pd.to_numeric(matched.get("Horizons Scored", pd.Series(dtype=float)), errors="coerce")
    full_n = int((hz >= 5).sum())
    gaps = gap_count(matched)
    scored = ("each scored on all five horizons" if full_n == k else
              f"{full_n} of the {k} scored on all five horizons")
    gap = "none with a price gap" if gaps == 0 else f"{wl.fmt_count(gaps, 'with a price gap', 'with a price gap')}"
    return f"{text}; {scored}, {gap}."
