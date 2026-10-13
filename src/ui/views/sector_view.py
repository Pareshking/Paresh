"""
Sectors: industries ranked by how their stocks are doing, one row each.

Every figure is read straight off the ranking table, so the page needs no
momentum engine: a median of each group's returns, and shares of its stocks
that pass the Screener's own filters.
"""

import html

import numpy as np
import pandas as pd
import streamlit as st

from src.ui.system_param import stock_href
from src.ui import page_kit as kit
from src.engine.pipeline import price_fingerprint
from src.engine.sector_breadth import EMA_SPANS, sector_leadership
from src.loaders import benchmark_store
from src.ui.charts import render_industry_map, render_leadership_map, sector_colours
from src.ui.components import gap_count, render_data_quality_footer, to_bool_mask
from src.ui.screener_table import _CSS as TABLE_CSS, _JS as TABLE_JS, ROW_PX, render_screener_table

RANK_BY = {
    "3M median": "3M Return",
    "6M median": "6M Return",
    "Share passing": "Pass %",
    "Top-50 count": "Top 50",
}
# A group of one is a stock, not an industry trend.
MIN_STOCKS = 2
# Labels on the leadership map; the tooltip keeps NSE's full name.
SHORT_NAMES = {
    "Automobile and Auto Components": "Auto",
    "Fast Moving Consumer Goods": "FMCG",
    "Information Technology": "IT",
    "Media Entertainment & Publication": "Media",
    "Oil Gas & Consumable Fuels": "Oil & Gas",
    "Metals & Mining": "Metals",
    "Construction Materials": "Cement & Materials",
    "Consumer Durables": "Cons. Durables",
    "Consumer Services": "Cons. Services",
    "Financial Services": "Financials",
    "Telecommunication": "Telecom",
}


@st.cache_data(show_spinner=False, ttl=3600)
def _leadership(prices_hash: str, _prices: pd.DataFrame, groups: tuple, span: int,
                months: int = 1) -> pd.DataFrame:
    bench = benchmark_store.history("max")
    return sector_leadership(_prices, pd.Series(dict(groups)), bench, span, months=months)


LEAD_PERIODS = {"1M": 1, "3M": 3}


def _ago(months: int) -> str:
    return "a month ago" if months == 1 else f"{months} months ago"


def render_leadership_section(rank_df: pd.DataFrame, adj_close: pd.DataFrame, col: str) -> None:
    """Sector leadership: return against the Nifty 500 across, breadth up, one
    or three months ago and today, for the 20/50/100/200-day EMA."""
    if col not in rank_df.columns or adj_close is None or adj_close.empty:
        return
    groups = tuple(sorted(rank_df[["Symbol", col]].dropna().astype(str).itertuples(index=False, name=None)))
    # Pills like the Rank by control at the top of the page, not underlined
    # tabs (owner, 13 Oct): one row for the EMA, one for the period.
    span = int(st.session_state.get("sec_lead_span") or 200)
    months = LEAD_PERIODS.get(st.session_state.get("sec_lead_period") or "1M", 1)
    with kit.card("Sector leadership map", "sec_lead", f"hollow dot {_ago(months)} · filled dot today"):
        kit.caption(f"Right: beat the Nifty 500 over the {'month' if months == 1 else f'{months} months'}. "
                    "Up: more of its stocks above the EMA. Each sector keeps its colour; tap one to pick it out.")
        with st.container(horizontal=True, gap="small", vertical_alignment="center", key="sec_lead_controls"):
            st.segmented_control("EMA", list(EMA_SPANS), default=200, required=True, key="sec_lead_span",
                                 format_func=lambda n: f"{n} EMA", label_visibility="collapsed")
            st.segmented_control("Period", list(LEAD_PERIODS), default="1M", required=True,
                                 key="sec_lead_period", label_visibility="collapsed",
                                 help="1M: each dot is a month apart. 3M: three months apart, "
                                      "for the slower trend underneath.")
        board = _leadership(price_fingerprint(adj_close), adj_close, groups, span, months)
        if board.empty:
            st.info("Not enough price history to compare the two periods.")
            return
        names = board.sort_values("Sector")["Sector"].tolist()
        focus = st.selectbox("Pick out a sector", ["All sectors", *names], key="sec_lead_focus",
                             format_func=lambda n: SHORT_NAMES.get(n, n) if n != "All sectors" else n,
                             label_visibility="collapsed", width=240)
        render_leadership_map(board, span, None if focus == "All sectors" else focus, SHORT_NAMES)
        then, now = pd.Timestamp(board["Then"].iloc[0]), pd.Timestamp(board["Now"].iloc[0])
        fell = int((board["y_now"] < board["y_then"]).sum())
        ahead_narrow = board[(board["x_now"] > 0) & (board["y_now"] < 0.5)]
        kit.caption(
            f"{then:%d %b} to {now:%d %b}: breadth fell in {fell} of {len(board)} sectors."
            + (f" Ahead of the Nifty 500 with under half above the {span}-day EMA: "
               f"{', '.join(SHORT_NAMES.get(n, n) for n in ahead_narrow['Sector'])}."
               if len(ahead_narrow) else "")
        )
        # How to read it, worked on one sector: the picked one, else the
        # first that beat the index on narrow breadth, else the leader
        # (owner, 13 Oct: "how to interpret it, with an example").
        example = (focus if focus != "All sectors" else
                   (ahead_narrow["Sector"].iloc[0] if len(ahead_narrow)
                    else board.sort_values("x_now", ascending=False)["Sector"].iloc[0]))
        with st.expander(f"How to read this · worked example: {SHORT_NAMES.get(example, example)}"):
            st.markdown(leadership_explainer(board.set_index("Sector").loc[example], example, span))
        st.iframe(leadership_table_html(board, span), height=28 + 42 + len(board) * ROW_PX + 6)
        kit.caption("Sector return is the equal-weighted mean of its stocks' price returns, not an "
                    "NSE sector index; the share counts stocks with a close and an EMA that day. "
                    "Click a header to sort.")


def _signed_pct(v: float) -> tuple[str, str]:
    cls = "pos" if v > 0 else "neg" if v < 0 else ""
    return cls, f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v) * 100:.1f}%"


def _reading(dx: float, dy: float) -> str:
    """What the line's direction says, in one sentence."""
    if dx >= 0 and dy >= 0:
        return "it beat the index and more of its stocks are in an uptrend: broad strength building."
    if dx >= 0:
        return ("it did better against the index, but fewer of its stocks are in an uptrend: "
                "a few names are carrying it, so the lead is narrow.")
    if dy >= 0:
        return ("it did worse against the index, but more of its stocks are back above the line: "
                "a possible early turn.")
    return "it did worse against the index and fewer of its stocks are in an uptrend: weak and weakening."


def _leaders_txt(leaders, n: int, sep: str = ", ") -> str:
    """'NAZARA +35.4%, SUNTV +20.1%' from the engine's (symbol, return) pairs."""
    return sep.join(f"{html.escape(sym)} {_signed_pct(ret)[1]}" for sym, ret in (leaders or [])[:n])


def leadership_explainer(r: pd.Series, name: str, span: int) -> str:
    """The method behind one sector's two dots, with its own numbers."""
    then, now = pd.Timestamp(r["Then"]), pd.Timestamp(r["Now"])
    m = int(r.get("Months", 1) or 1)
    period = "month" if m == 1 else f"{m} months"
    ret, bench, x1, x0 = r["ret_now"] * 100, r["bench_now"] * 100, r["x_now"] * 100, r["x_then"] * 100
    y1, y0 = r["y_now"] * 100, r["y_then"] * 100
    dx, dy = x1 - x0, y1 - y0
    side = "right of" if x1 >= 0 else "left of"
    half = "above" if y1 >= 50 else "below"
    n = int(r["Stocks"])
    lifts = "; ".join(
        f"{html.escape(sym)} {rv * 100:+.1f}%, which adds {rv * 100 / n:+.2f} points to the sector's {ret:+.1f}%"
        for sym, rv in (r.get("Leaders") or [])[:2])
    return f"""**Across: did the sector beat the Nifty 500 over the {period}?**  
Each of the {n} {html.escape(name)} stocks' price change from the {then:%d %b} close to the {now:%d %b} close, averaged with equal weight: **{ret:+.1f}%**. The Nifty 500 over the same closes: **{bench:+.1f}%**. The difference, {ret:+.2f} − ({bench:+.2f}) = **{x1:+.2f}%**, places the filled dot {side} the 0 line. The hollow dot is the same sum for the {period} before: {x0:+.1f}%.

**Up: how many of its stocks are in an uptrend?**  
A stock counts when its close is above its own {span}-day EMA (exponential average of its closes). Today {int(r['above_now'])} of {int(r['obs_now'])} = **{y1:.0f}%**; {_ago(m)} {int(r['above_then'])} of {int(r['obs_then'])} = {y0:.0f}%. Only stocks with a close and an EMA that day are counted; an EMA needs {int(span * 0.8)} sessions of prices, so a recent listing can be missing.

**Heavy lifting**  
With equal weight each stock adds its own return ÷ {n} to the sector's. The two largest over the {period}: {lifts or "none"}.

**The line: hollow dot ({_ago(m)}) to filled dot (today)**  
It moved {abs(dx):.1f} points {'right' if dx >= 0 else 'left'} and {abs(dy):.0f} points {'up' if dy >= 0 else 'down'}: {_reading(dx, dy)} Today it sits {side} 0 and {half} the 50% line.

**The four directions**  
Right and up: broad strength building. Right and down: beating the index on a few names. Left and up: lagging, but more stocks recovering. Left and down: weak and weakening. A longer line is a bigger change.
"""


def leadership_table_html(board: pd.DataFrame, span: int) -> str:
    """The leadership figures in the Screener table's design ("Stocks in an
    industry"): sortable headers, the sector's map colour as a dot."""
    colour = sector_colours(board["Sector"])
    rows = []
    for i, r in enumerate(board.sort_values("x_now", ascending=False).itertuples(), start=1):
        name = html.escape(r.Sector)
        cells = [f'<td class="c-rank" data-v="{i}">{i}</td>',
                 f'<td class="c-stock" data-v="{name}"><a><span class="sym">'
                 f'<i class="dot" style="background:{colour[r.Sector]}"></i><span class="nm-full">{name}</span>'
                 f'<span class="nm-short">{html.escape(SHORT_NAMES.get(r.Sector, r.Sector))}</span></span>'
                 f'<span class="sub"><span class="nm-full">{int(r.Stocks)} stocks · led by {_leaders_txt(r.Leaders, 2)}</span>'
                 f'<span class="nm-short">{html.escape(", ".join(sym for sym, _ in (r.Leaders or [])[:2]))}</span>'
                 f'</span></a></td>']
        for x, a, o, y, extra in ((r.x_now, r.above_now, r.obs_now, r.y_now, ""),
                                  (r.x_then, r.above_then, r.obs_then, r.y_then, " d-only")):
            cls, txt = _signed_pct(x)
            cells.append(f'<td class="n {cls}{extra}" data-v="{x:.6f}">{txt}</td>')
            cells.append(f'<td class="n{extra}" data-v="{y:.6f}">{a} of {o}'
                         f'<span class="pc">{y * 100:.0f}%</span></td>')
        d = round((r.y_now - r.y_then) * 100)
        chip = ("up", f"▲ {d}") if d > 0 else ("down", f"▼ {abs(d)}") if d < 0 else ("flat", "— 0")
        cells.append(f'<td class="n" data-v="{d}"><span class="chip {chip[0]}">{chip[1]}'
                     '<span class="nm-full"> pts</span></span></td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    then, now = pd.Timestamp(board["Then"].iloc[0]), pd.Timestamp(board["Now"].iloc[0])
    ago_head = _ago(int(board["Months"].iloc[0])).capitalize()
    # (label, phone label, sort type, class, arrow)
    heads = [("#", "#", "num", "t-left on", "↓"), ("Sector", "Sector", "text", "t-left", "↕"),
             ("Vs Nifty 500", "Vs N500", "num", "", "↕"), (f"Above {span} EMA", "Above", "num", "", "↕"),
             ("Vs Nifty 500", "", "num", "d-only", "↕"), (f"Above {span} EMA", "", "num", "d-only", "↕"),
             ("Breadth", "Δ", "num", "", "↕")]
    head = "".join(f'<th class="{c}" data-type="{t}"><span class="nm-full">{html.escape(h)}</span>'
                   f'<span class="nm-short">{html.escape(m)}</span><span class="ar">{a}</span></th>'
                   for h, m, t, c, a in heads)
    groups = ('<tr class="grp-row"><th colspan="2" class="grp">Sector</th>'
              f'<th colspan="2" class="grp">Today · {now:%d %b}</th>'
              f'<th colspan="2" class="grp d-only">{ago_head} · {then:%d %b}</th>'
              '<th class="grp">Change</th></tr>')
    css = (TABLE_CSS + "table{min-width:0}.wrap{height:auto}td.c-stock .sub{display:block}"
           "tbody tr:hover td{cursor:default}"
           ".dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px;"
           "border:1px solid rgba(14,23,38,.25);vertical-align:0}"
           "td .pc{display:inline-block;min-width:38px;margin-left:8px;color:#5E6878;font-weight:500}"
           ".nm-short{display:none}"
           "@media (max-width:640px){td .pc{display:none}.nm-full{display:none}.nm-short{display:inline}"
           "th,td{padding:0 6px}td{font-size:12.5px}th:nth-child(1),td.c-rank{width:26px;min-width:26px}"
           "th:nth-child(2),td.c-stock{left:26px;max-width:116px}"
           "td.c-stock .sub{display:block}"
           "td.c-stock .sym{display:block;max-width:104px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
           "thead th .ar{display:none}}")
    return ("<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<link href='https://fonts.googleapis.com/css2?family=Geist:wght@400..700&"
            "family=Geist+Mono:wght@400..700&display=swap' rel='stylesheet'>"
            f"<style>{css}</style></head><body><div class='wrap'><table>"
            f"<thead>{groups}<tr class=\"hdr\">{head}</tr></thead><tbody>{''.join(rows)}</tbody>"
            f"</table></div><script>const SYS='';{TABLE_JS}</script></body></html>")


def _leader_link(sym: str) -> str:
    if not sym or sym == "—":
        return "—"
    return (f'<a class="ib-lead" href="{stock_href(sym)}" target="_self">'
            f'{html.escape(sym)}</a>')


def _pct(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v) * 100:.1f}%"


def _tone(v) -> str:
    if v is None or pd.isna(v):
        return ""
    return "up" if v > 0 else "down" if v < 0 else ""


def industry_board(rank_df: pd.DataFrame, col: str = "Industry") -> tuple[pd.DataFrame, list[str]]:
    """One row per industry, and the names left out for having one stock.

    3M / 6M are medians, so one runaway stock cannot carry its group. "Above
    50 EMA" and "Near 52W high" are the Screener's own flags, the same ones
    its filters use.
    """
    if col not in rank_df.columns or rank_df.empty:
        return pd.DataFrame(), []
    df = rank_df.assign(
        _grp=rank_df[col].replace("", np.nan),
        _ema=to_bool_mask(rank_df.get("Above 50 EMA", pd.Series(False, index=rank_df.index))).to_numpy(),
        _near=to_bool_mask(rank_df.get("Near 52W High", pd.Series(False, index=rank_df.index))).to_numpy(),
        _rank=pd.to_numeric(rank_df.get("Rank"), errors="coerce"),
    ).dropna(subset=["_grp"])
    rows, singles = [], []
    for name, g in df.groupby("_grp"):
        if len(g) < MIN_STOCKS:
            singles.append(str(name))
            continue
        lead = g.sort_values("_rank")["Symbol"].tolist()
        rows.append({
            "Industry": str(name),
            "Stocks": len(g),
            "3M Return": pd.to_numeric(g.get("3M Return"), errors="coerce").median(),
            "6M Return": pd.to_numeric(g.get("6M Return"), errors="coerce").median(),
            "EMA %": float(g["_ema"].mean()),
            "Near %": float(g["_near"].mean()),
            "Pass": int((g["_ema"] & g["_near"]).sum()),
            "Pass %": float((g["_ema"] & g["_near"]).mean()),
            "Top 50": int((g["_rank"] <= 50).sum()),
            "Best": g["_rank"].min(),
            "Leaders": lead[:3],
        })
    return pd.DataFrame(rows), sorted(singles)


def board_html(board: pd.DataFrame) -> str:
    """The leaderboard as a table; on a phone each row folds to name, one
    line of detail and the 3M figure."""
    lim = max(0.05, float(board["3M Return"].abs().max() or 0))
    rows = []
    for i, (_, r) in enumerate(board.iterrows(), start=1):
        v = r["3M Return"]
        w = 0 if pd.isna(v) else min(50.0, abs(v) / lim * 50)
        side = "left:50%" if (v or 0) >= 0 else "right:50%"
        leads = "".join(_leader_link(s) for s in r["Leaders"][:2])
        rows.append(
            f'<div class="ib-row" role="row">'
            f'<span class="ib-n">{i}</span>'
            f'<span class="ib-name"><b>{html.escape(r["Industry"])}</b>'
            f'<small>{r["Stocks"]} stocks · {r["EMA %"] * 100:.0f}% above 50-day EMA · {r["Top 50"]} in top 50</small></span>'
            f'<span class="ib-num ib-d">{r["Stocks"]}</span>'
            f'<span class="ib-3m"><b class="{_tone(v)}">{_pct(v)}</b>'
            f'<span class="ib-bar"><i class="{_tone(v)}" style="{side};width:{w:.1f}%"></i><em></em></span></span>'
            f'<span class="ib-num ib-d {_tone(r["6M Return"])}">{_pct(r["6M Return"])}</span>'
            f'<span class="ib-num ib-d">{r["EMA %"] * 100:.0f}%</span>'
            f'<span class="ib-num ib-d">{r["Near %"] * 100:.0f}%</span>'
            f'<span class="ib-num ib-d">{r["Pass"]}</span>'
            f'<span class="ib-num ib-d">{r["Top 50"]}</span>'
            f'<span class="ib-leads ib-d">{leads}</span></div>'
        )
    head = ('<div class="ib-row ib-head" role="row"><span>#</span><span>Industry</span>'
            '<span class="ib-num ib-d">Stocks</span><span class="ib-3m">3M (median)</span>'
            '<span class="ib-num ib-d">6M</span><span class="ib-num ib-d" title="Share above their 50-day EMA">Above EMA</span>'
            '<span class="ib-num ib-d" title="Share within 20% of their 52-week high">Near high</span><span class="ib-num ib-d">Pass both</span>'
            '<span class="ib-num ib-d">Top 50</span><span class="ib-d">Leaders</span></div>')
    return f'<div class="ib" role="table" aria-label="Industry leaderboard">{head}{"".join(rows)}</div>'


def render_sector_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame) -> None:
    """Industries ranked, then the stocks of the one picked."""
    has_tv = [c for c in ("TV_Industry", "TV_Sector") if c in rank_df.columns]
    tax = {"NSE industry": "Industry"}
    if "TV_Industry" in has_tv:
        tax["TradingView industry"] = "TV_Industry"
    if "TV_Sector" in has_tv:
        tax["TradingView sector"] = "TV_Sector"

    by = st.session_state.get("sector_rank_by") or "3M median"
    col = tax.get(st.session_state.get("sector_tax_choice") or "NSE industry", "Industry")
    board, singles = industry_board(rank_df, col)
    if not board.empty:
        board = board.sort_values([RANK_BY[by], "3M Return"], ascending=False,
                                  na_position="last").reset_index(drop=True)

    actions = kit.page_head(
        "Sectors",
        f"{len(board)} {'industries' if col == 'Industry' else 'groups'} · ranked by {by}",
        actions=True,
    )
    with actions:
        st.segmented_control("Rank by", list(RANK_BY), default="3M median", required=True,
                             key="sector_rank_by", label_visibility="collapsed")
        if len(tax) > 1:
            st.selectbox("Classification", list(tax), key="sector_tax_choice",
                         label_visibility="collapsed", width=190)

    if board.empty:
        st.info("No industry has two or more ranked stocks to compare.")
        return

    # The tiles and the map follow the measure picked above; they read 3M
    # whatever was picked, so 6M, Share passing and Top-50 count changed only
    # the leaderboard further down (owner, 13 Oct: "not showing correctly").
    ret = "6M Return" if by == "6M median" else "3M Return"
    span = "6M" if ret == "6M Return" else "3M"
    metric = RANK_BY[by]
    ranked = board.dropna(subset=[metric])
    lead, weak = ranked.iloc[0], ranked.iloc[-1]
    most = board.sort_values(["Top 50", ret], ascending=False).iloc[0]
    rising = int((board[ret] > 0).sum())
    best_sym = (rank_df[rank_df[col] == most.Industry].sort_values("Rank")["Symbol"].head(1).tolist() or ["—"])[0]

    def why(r) -> str:
        if metric == "Pass %":
            return f"{r['Pass %'] * 100:.0f}% pass both filters ({r.Pass} of {r.Stocks})"
        if metric == "Top 50":
            return f"{r['Top 50']} of the top 50 · median {span} {_pct(r[ret])}"
        return f"median {_pct(r[ret])} in {span[0]} months · {r['Top 50']} of the top 50"

    kit.readings([
        kit.Reading("Leading", lead.Industry, why(lead), _tone(lead[ret]) if metric == ret else ""),
        kit.Reading("Rising", f"{rising} of {len(board)}", f"median {span} above 0"),
        kit.Reading("Most in the top 50", most.Industry,
                    f"{most['Top 50']} stocks · best rank #{int(most.Best)} {best_sym}"),
        kit.Reading("Weakest", weak.Industry, why(weak), _tone(weak[ret]) if metric == ret else "down"),
    ], "Industries today")

    with kit.card("Industry map", "sec_map", "bubble size = stocks"):
        render_industry_map(board, x_col=ret, x_label=f"Median {span[0]}-month return")

    with kit.card("Industry leaderboard", "sec_board"):
        st.html(board_html(board))
        if singles:
            kit.caption(f"Not shown (one stock each): {', '.join(singles)}.")

    with kit.card("Stocks in an industry", "sec_stocks"):
        pick = st.selectbox("Industry", board["Industry"].tolist(), key="sector_pick",
                            label_visibility="collapsed")
        members = rank_df[rank_df[col] == pick].sort_values("Rank")
        render_screener_table(members, adj_close, "Core")

    render_leadership_section(rank_df, adj_close, col)

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
