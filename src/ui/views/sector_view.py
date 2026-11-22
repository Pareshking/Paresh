"""
Sectors (S174): which sectors lead the 750, whether a lead is broad, and NSE's own sector
indices beside each sector.

Built from the mock-up the owner approved on 21 Nov 2026 (v2, docs/SECTORS_REQUIREMENTS.md,
"Owner's decisions"), in the Dashboard's type system and chart kit. A sector is NSE's (the
"Industry" column of NSE's index lists, NSE's sector level); every sector figure is the
equal-weighted index of its ranked stocks against the same over all of them, "the 750"
(src/engine/sectors_page.py). The grouping switch regroups every section built from the
ranked stocks; NSE's indices match NSE's sectors only, so with a TradingView grouping their
sections give way to one line.
"""

from __future__ import annotations

import html

import numpy as np
import pandas as pd
import streamlit as st

from src.engine import market_questions as mq
from src.engine import sectors_page as sp
from src.engine.pipeline import price_fingerprint
from src.ui import formats as _fmt
from src.ui.components import gap_count, render_data_quality_footer, to_bool_mask
from src.ui.industry_names import INDUSTRY_SHORT as SHORT_NAMES
from src.ui.screener_table import render_screener_table
from src.ui.system_param import page_href, stock_href
from src.ui.views.dashboard_home_view import HOME_CSS, Chart, emit, how, sg

e = html.escape
KICK = '<p class="dh-kick">{}</p>'
# A group of one is a stock, not a sector trend (the stocks picker and industry_board keep groups of two).
MIN_STOCKS = 2

GROUPINGS = {"NSE sector": "Industry", "TradingView sector": "TV_Sector", "TradingView industry": "TV_Industry"}
# Owner, 21 Nov 2026 (item 12): with a TradingView grouping the NSE index sections hide and the page says why, once.
NSE_ONLY = "NSE’s indices match NSE’s sectors; switch to NSE sectors to see them."
GROUP_WORDS = {"ahead on both": ("Ahead on both", "ahead over six months and over the last month"),
               "gaining": ("Gaining", "behind over six months, ahead over the last month"),
               "fading": ("Fading", "ahead over six months, behind over the last month"),
               "behind on both": ("Behind on both", "behind over six months and over the last month")}

SX_CSS = """
.sx-toc{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:var(--fs-13);margin:14px 0 0}
.sx-toc a{color:var(--c-muted);text-decoration:none;border-bottom:1px solid var(--c-rule_strong)}
.sx-only{font-size:var(--fs-15);color:var(--c-ink);background:var(--c-fill);border-left:3px solid var(--c-rule_strong);padding:10px 14px;max-width:80ch}
.sx-ix th[scope=row]{font-weight:500;white-space:nowrap}
.sx-ix tr.sx-grp th{background:var(--c-fill);font-size:var(--fs-12);color:var(--c-text_2);font-weight:600;text-align:left}
.sx-ix tr.sx-grp th span{font-weight:400;color:var(--c-muted);margin-left:6px}
.sx-ix tr.sx-ours th{font-style:italic;font-weight:400}
.sx-ix .sx-s{display:none}
.sx-mo th[scope=row]{white-space:nowrap}
@media (max-width:640px){.sx-ix .sx-f{display:none}.sx-ix .sx-s{display:inline}
.sx-ix th[scope=row],.sx-ix thead th:first-child,.sx-mo th[scope=row],.sx-mo thead th:first-child{position:sticky;left:0;background:var(--c-white);z-index:1;box-shadow:1px 0 0 var(--c-rule_soft);padding-right:10px!important}
.sx-ix tr.sx-grp th{position:static}.sx-ix th,.sx-ix td,.sx-mo th,.sx-mo td{padding:6px 4px 6px 0!important;font-size:var(--fs-12)}}
"""


# ── Kept from the live page: the stocks' own flags by group (the leaderboard's figures) ─────


def _leader_link(sym: str) -> str:
    if not sym or sym == "–":
        return "–"
    return (f'<a class="ib-lead" href="{stock_href(sym)}" target="_self">'
            f'{html.escape(sym)}</a>')


def _pct(v) -> str:
    return _fmt.pct(v)


def _tone(v) -> str:
    if v is None or pd.isna(v):
        return ""
    return "up" if v > 0 else "down" if v < 0 else ""


def industry_board(rank_df: pd.DataFrame, col: str = "Industry") -> tuple[pd.DataFrame, list[str]]:
    """One row per group, and the names left out for having one stock.

    3M / 6M are medians (the typical stock), so one runaway stock cannot carry its group.
    "Above 50 EMA" and "Near 52W high" are the Screener's own flags, the same ones its filters use.
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


def _reading(dx: float, dy: float) -> str:
    """What the map's line says, in one sentence."""
    if abs(dy) < 0.5:
        # Breadth did not move: "more of its stocks" would be wrong (found for the Sectors build, 21 Nov 2026).
        return f"it did {'better' if dx >= 0 else 'worse'} against the 750 with the same share of its stocks in an uptrend."
    if dx >= 0 and dy >= 0:
        return "it beat the 750 by more and more of its stocks are in an uptrend: broad strength building."
    if dx >= 0:
        return ("it did better against the 750, but fewer of its stocks are in an uptrend: "
                "a few names are carrying it, so the lead is narrow.")
    if dy >= 0:
        return ("it did worse against the 750, but more of its stocks are back above the line: "
                "a possible early turn.")
    return "it did worse against the 750 and fewer of its stocks are in an uptrend: weak and weakening."


def leadership_explainer(r: pd.Series, name: str, span: int) -> str:
    """The method behind one sector's two dots on the map, with its own numbers (the frame draws the same text)."""
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
        f"{html.escape(sym)} {_fmt.pct(rv * 100, fraction=False)}, which adds about {_fmt.signed(rv * 100 / n, 2)} pts to the sector's {_fmt.pct(ret, fraction=False)}"
        for sym, rv in (r.get("Leaders") or [])[:2])
    moved = "neither up nor down" if abs(dy) < 0.5 else f"{abs(dy):.0f} pts {'up' if dy >= 0 else 'down'}"
    return f"""**Across: did the sector beat the 750 over the {period}?**
The {n} {html.escape(name)} stocks as an equal-weighted index, from the {then:%-d %b} close to the {now:%-d %b} close: **{_fmt.pct(ret, fraction=False)}**. The 750, built the same way over the same closes: **{_fmt.pct(bench, fraction=False)}**. The difference, **{_fmt.signed(x1, 2)} pts**, places the filled dot {side} the 0 line. The hollow dot is the same for the {period} before: {_fmt.signed(x0, 2)} pts.

**Up: how many of its stocks are in an uptrend?**
A stock counts when its close is above its own {span}D EMA. Today {int(r['above_now'])} of {int(r['obs_now'])} = **{y1:.0f}%**; before, {int(r['above_then'])} of {int(r['obs_then'])} = {y0:.0f}%. An EMA needs {int(span * 0.8)} sessions of prices, so a recent listing can be missing.

**Heavy lifting**
With equal weight each stock adds roughly its own return ÷ {n} to the sector's. The two largest over the {period}: {lifts or "none"}.

**The line, hollow dot to filled dot**
It moved {abs(dx):.1f} pts {'right' if dx >= 0 else 'left'} and {moved}: {_reading(dx, dy)} Today it sits {side} 0 and {half} the 50% line.
"""


# ── The page's figures, cached on the prices and the grouping ───────────────


@st.cache_data(show_spinner=False, ttl=3600)
def _model(key: str, _rank_df: pd.DataFrame, _prices: pd.DataFrame, col: str, _tm: pd.Series) -> dict | None:
    syms = [s for s in _rank_df["Symbol"] if s in _prices.columns]
    px = _prices[syms]
    groups = _rank_df.drop_duplicates("Symbol").set_index("Symbol")[col] if col in _rank_df else pd.Series(dtype=str)
    ld = sp.leads(px, groups, _tm)
    if ld is None or not ld.rows:
        return None
    out = {"ld": ld, "months": mq.industry_months(px, groups.reindex(px.columns), _tm),
           "shares": sp.ema_shares(px, groups, ld), "map": sp.leadership_views(px, groups, _tm if len(_tm) else ld.market),
           "nse": None}
    if col == "Industry":
        from src.ui import indices_data
        f = indices_data.frames()
        if f is not None:
            f = f.until(ld.when)
            smap = sp.sector_map()
            counts = groups.dropna().astype(str).value_counts().to_dict()
            out["nse"] = {"as_of": f.as_of, "groups": sp.sector_indices(f, ld, smap, counts),
                          "gaps": sp.broad_or_narrow(f, ld, smap), "pairs": sp.pair_series(f, ld, smap)}
    return out


# ── Sections ─────────────────────────────────────────────────────────────────


def _list(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _words(n: int) -> str:
    return ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"][n] if n <= 12 else str(n)


def _d(day) -> str:
    return f"{pd.Timestamp(day):%-d %b}"


def head(ld: sp.Leads, sh, noun: str, nse: dict | None) -> list:
    both = [sh(r.name) for r in ld.rows if r.group == "ahead on both"]
    worst = sorted(ld.rows, key=lambda r: r.lead6)[:2]
    nouns = noun + "s"
    if both:
        lead_txt = f'<span class="dh-up">{e(_list(both[:3]))}</span> lead the 750 over six months and one month'
    else:
        lead_txt = f"No {noun} leads the 750 on both six months and one month"
    trail = ""
    if len(worst) == 2 and worst[1].lead6 < 0:
        trail = (f'; <span class="dh-down">{e(sh(worst[0].name))} and {e(sh(worst[1].name))}</span> trail by '
                 f"{int(np.floor(min(-worst[0].lead6, -worst[1].lead6)))} pts or more")
    title = lead_txt + trail + "."
    n_both = sum(r.group == "ahead on both" for r in ld.rows)
    lede = f"{_words(n_both).capitalize()} of {len(ld.rows)} {nouns} are ahead of the 750, equal-weighted, over both windows."
    if nse and nse["gaps"]:
        tm1, m1 = ld.gap.get("1"), ld.market_ret.get(1)
        below = sum(g.gap1 < 0 for g in nse["gaps"])
        if tm1 is not None and m1 is not None:
            tmr = m1 - tm1
            lede += (f" NSE’s indices tell a different month: Nifty Total Market {'rose' if tmr >= 0 else 'fell'} {abs(tmr):.1f}% and "
                     f"the 750, equal-weighted, {'rose' if m1 >= 0 else 'fell'} {abs(m1):.1f}%, so "
                     f"{'all ' + str(below) if below == len(nse['gaps']) else str(below) + ' of ' + str(len(nse['gaps']))} "
                     "sector indices beat their sector’s ranked stocks over the month.")
    lede += f" Price returns, closes of {ld.when:%-d %b %Y}."
    links = [("s-lead", f"Which {nouns} lead"), ("s-broad", "Broad or narrow"), ("s-indices", "NSE’s sector indices"),
             ("s-months", "Month by month"), ("s-map", "Sector leadership map"), ("s-inside", f"Inside each {noun}"),
             ("s-stocks", f"Stocks in a {noun}")]
    if nse is None:
        links = [x for x in links if x[0] not in ("s-broad", "s-indices")]
    nav = "".join(f'<a href="#{a}">{e(t)}</a>' for a, t in links)
    return [f'<div class="dh-sec">{KICK.format("Sectors")}<h1 id="s-top" class="dh-h1">{title}</h1>'
            f'<p class="dh-lede">{e(lede)}</p><nav class="sx-toc" aria-label="On this page">{nav}</nav></div>']


def section_lead(ld: sp.Leads, sh, noun: str) -> list:
    nouns = noun + "s"
    n_both = sum(r.group == "ahead on both" for r in ld.rows)
    n_behind = sum(r.group == "behind on both" for r in ld.rows)
    fell = max(ld.rows, key=lambda r: (r.lead6_3m or 0) - r.lead6 if r.group == "behind on both" else -1e9)
    h2 = (f'<span class="dh-up">{_words(n_both).capitalize()} {nouns} lead on both six months and one month</span>; '
          f'<span class="dh-down">{_words(n_behind)} trail on both</span>')
    if fell.group == "behind on both" and fell.lead6_3m is not None and fell.lead6_3m > 0:
        h2 += f", {e(sh(fell.name))} among them: its six-month lead read {sg(fell.lead6_3m)} pts on {_d(ld.d3)}"
    h2 += "."

    def rd(r_name, l6, l1, ago):
        return [[sg(l6) + " pts", "six-month lead now", _kt(l6)], [sg(ago) + " pts", "a month ago"], [sg(l1) + " pts", "one-month lead", _kt(l1)]]
    g = ld.gap
    rows = []
    if g.get("6") is not None:
        rows.append({"name": "The 750 vs Nifty Total Market", "sub": "equal-weighted vs cap-weighted", "ref": True,
                     "bar": _r(g["6"]), "ago": _r(g.get("6_1m")),
                     "vals": [sg(g.get("6_3m")), sg(g.get("6_1m")), sg(g["6"]), sg(g.get("1"))],
                     "cls": ["muted", "muted", _kt(g["6"]) + " b", _kt(g.get("1"))],
                     "read": rd("The 750", g["6"], g.get("1"), g.get("6_1m"))})
    for key, (label, what) in GROUP_WORDS.items():
        rs = [r for r in ld.rows if r.group == key]
        if not rs:
            continue
        rows.append({"heading": f"{label} · {len(rs)}", "sub": what})
        for r in rs:
            rows.append({"name": sh(r.name), "sub": f"{r.stocks} stocks", "bar": _r(r.lead6), "ago": _r(r.lead6_1m),
                         "vals": [sg(r.lead6_3m), sg(r.lead6_1m), sg(r.lead6), sg(r.lead1)],
                         "cls": ["muted", "muted", _kt(r.lead6) + " b", _kt(r.lead1)],
                         "read": rd(r.name, r.lead6, r.lead1, r.lead6_1m)})
    spec = {"label": f"{noun.capitalize()} · lead, pts", "barHead": "Six-month lead over the 750, pts",
            "head": [_d(ld.d3), _d(ld.d1), "Now", "1M"], "rows": rows, "lo": -20, "hi": 20, "step": 1,
            "rest": "Latest · the first row"}
    sw = sp.nearest_switches(ld)
    ent = "; ".join(f"<b>{e(sh(n))}</b> {sg(v)} pts" for n, v in sw["entrants"])
    ext = "; ".join(f"<b>{e(sh(n))}</b> {sg(v)} pts" for n, v in sw["exits"])
    would = ('<div class="dh-sec dh-sec-cont"><h3 class="dh-h3">What would change the answer</h3><ul class="dh-note">'
             + (f"<li>Nearest to moving ahead over six months: {ent}.</li>" if ent else "")
             + (f"<li>Nearest to falling behind: {ext}.</li>" if ext else "")
             + "</ul><p class=\"dh-note\">Which sizes lead, against Nifty Total Market at 1M, 3M and 6M: on the Dashboard, "
             f'<a href="{page_href("dashboard")}#s-size" target="_self">Size, and where momentum works →</a></p></div>')
    ex = next((r for r in ld.rows if r.name == "Healthcare"), ld.rows[0])
    left = ", ".join(f"{k} ({v})" for k, v in sorted(ld.left_out.items(), key=lambda kv: -kv[1]))
    what = (f"A {noun} here is the equal-weighted index of its ranked stocks, rebalanced daily, and so is the 750. "
            f"{len(ld.rows)} have five or more ranked stocks and are shown"
            + (f"; left out with fewer: {left}" if left else "") + ". Comparing like with like keeps a rally of large "
            "companies from reading as every one lagging; that gap is the first row, the 750 against Nifty Total Market. "
            f"For example, {sh(ex.name)}: its {ex.stocks} stocks returned {sg(ex.returns.get(6), 1, '%')} over six months and "
            f"the 750 {sg(ld.market_ret.get(6), 1, '%')}, a lead of {sg(ex.lead6)} pts. The grouping switch at the top "
            "regroups the page by NSE sector (the default), TradingView sector or TradingView industry.")
    read = ("Each line is 1 pt; the bar is the six-month lead now, the triangle the same reading a month ago, and the "
            "numbers the reading three months ago, a month ago, now, and the one-month lead. Describing is not "
            "forecasting: a lead on both windows has not been tested here as a signal for the next month.")
    table = how(what, read, [noun.capitalize(), "Stocks", f"6M lead {_d(ld.d3)}", f"6M lead {_d(ld.d1)}", "6M lead now", "1M lead"],
                [[sh(r.name), r.stocks, sg(r.lead6_3m), sg(r.lead6_1m), sg(r.lead6), sg(r.lead1)] for r in ld.rows])
    return [f'<div class="dh-sec">{KICK.format(f"Which {nouns} lead")}<h2 id="s-lead" class="dh-h2">{h2}</h2>'
            f'<p class="dh-note">Lead: the {noun}’s return less the 750’s over the same sessions, both equal-weighted, in pts. '
            'Groups: ahead or behind over six months and over the last month.</p></div>',
            Chart("trows", spec, {"label": f"Each {noun}'s lead over the 750", "note": "Each line is 1 pt · the triangle is a month ago"}),
            would, table]


def section_broad(ld: sp.Leads, nse: dict, sh) -> list:
    gaps = nse["gaps"]
    if not gaps:
        return []
    m3 = ld.gap.get("3")
    fin = next((g for g in gaps if g.sector == "Financial Services"), gaps[0])
    narrow = [sh(g.sector) for g in gaps if m3 is not None and g.gap3 < m3]
    stocks = next((r.stocks for r in ld.rows if r.name == fin.sector), 0)
    h2 = (f'<span class="dh-down">{e(fin.index)} {"rose" if fin.nse3 >= 0 else "fell"} {abs(fin.nse3):.1f}% in three months while '
          f'the sector’s {stocks} ranked stocks {"rose" if fin.ours3 >= 0 else "fell"} {abs(fin.ours3):.1f}%</span>'
          + (f"; only {e(_list(narrow))} {'is' if len(narrow) == 1 else 'are'} narrower than the market." if narrow else "."))
    rows = []
    if m3 is not None:
        o3, t3 = ld.market_ret.get(3), (ld.market_ret.get(3) or 0) - m3
        rows.append({"name": "The 750 vs Nifty Total Market", "sub": "Nifty Total Market", "ref": True, "bar": _r(m3),
                     "vals": [sg(o3, 1, "%"), sg(t3, 1, "%"), sg(m3), sg(ld.gap.get("1"))],
                     "cls": [_kt(o3), _kt(t3), _kt(m3) + " b", _kt(ld.gap.get("1"))],
                     "read": [[sg(m3) + " pts", "gap over 3M", _kt(m3)], [sg(ld.gap.get("1")) + " pts", "gap over 1M"]]})
    for g in gaps:
        young = g.live.year >= ld.when.year and (ld.when - g.live).days < 365
        rows.append({"name": sh(g.sector), "sub": g.index + (f", since {g.live:%-d %b %Y}" if young else ""), "bar": _r(g.gap3),
                     "vals": [sg(g.ours3, 1, "%"), sg(g.nse3, 1, "%"), sg(g.gap3), sg(g.gap1)],
                     "cls": [_kt(g.ours3), _kt(g.nse3), _kt(g.gap3) + " b", _kt(g.gap1)],
                     "read": [[sg(g.ours3, 1, "%"), "the sector’s stocks, 3M"], [sg(g.nse3, 1, "%"), g.index + ", 3M"],
                              [sg(g.gap3) + " pts", "gap", _kt(g.gap3)]]})
    spec = {"label": "Sector · its NSE index", "barHead": "Gap over 3M, pts", "head": ["Stocks 3M, %", "Index 3M, %", "Gap 3M, pts", "Gap 1M, pts"],
            "rows": rows, "lo": -12, "hi": 12, "step": 0.5, "lines": [_r(m3)] if m3 is not None else [], "rest": "Latest · the first row"}
    pairs = [{"short": sh(g.sector), "ours_name": f"{sh(g.sector)}, the 750’s stocks", **{k: v for k, v in nse["pairs"][g.sector].items()}}
             for g in gaps if g.sector in nse["pairs"]]
    start = next((i for i, p in enumerate(pairs) if p["short"] == sh("Financial Services")), 0)
    return [f'<div class="dh-sec">{KICK.format("Broad or narrow")}<h2 id="s-broad" class="dh-h2">{h2}</h2>'
            '<p class="dh-note">Each sector’s ranked stocks, equal-weighted, against NSE’s index for the sector, which holds its own '
            'selection of the sector’s companies and weights them by free-float value: the two differ in stocks and in weights. '
            'The bar is the gap over three months, 0.5 pt a line. The dashed line is the 750’s own gap to Nifty Total Market: '
            'a bar left of it means the sector’s largest companies did more of the work than in the market as a whole.</p></div>',
            Chart("trows", spec, {"label": "Each sector against its NSE index", "note": "0.5 pt a line · dashed: the 750 against Nifty Total Market"}),
            '<div class="dh-sec dh-sec-cont"><h3 class="dh-h3">One year, each line 100 a year ago (or at the index’s launch)</h3></div>',
            Chart("pairs", {"pairs": pairs, "start": start, "text": {"gap": "gap", "latest": "Latest", "month_end": "Month end"}},
                  {"label": "A sector's ranked stocks and NSE's index for it over one year", "table": "Show the table"})]


def section_indices(ld: sp.Leads, nse: dict, sh) -> list:
    groups = nse["groups"]
    allix = [x for g in groups for x in g.indices]
    full = sorted((x for x in allix if not x.young), key=lambda x: -x.returns[12])
    young = sum(x.young for x in allix)
    h2 = f"NSE’s {len(allix)} sector indices, each beside its sector."
    if full:
        h2 = (f'Over the year <span class="dh-up">{e(full[0].name)} leads NSE’s sector indices at {sg(full[0].returns[12], 1, "%")}</span> '
              f'and <span class="dh-down">{e(full[-1].name)} trails at {sg(full[-1].returns[12], 1, "%")}</span>; '
              f"{_words(young)} of the {len(allix)} are younger than a year.")

    def cells(ret, hi, pe, young_since=None):
        out = "".join(_num(ret.get(m), "%") for m in (1, 3, 6, 9))
        out += (f'<td class="dh-num dh-muted">since {young_since}</td>' if young_since else _num(ret.get(12), "%"))
        hi_t = "–" if hi is None else ("at high" if abs(hi) < 0.05 else sg(hi, 1, "%"))
        return out + f'<td class="dh-num dh-muted">{e(hi_t)}</td><td class="dh-num dh-muted">{"–" if pe is None else f"{pe:.1f}"}</td>'
    body = ""
    for g in groups:
        body += (f'<tr class="sx-grp"><th scope="colgroup" colspan="8">{e(sh(g.sector))}<span>{g.stocks} ranked stocks'
                 f'{"" if g.indices else " · no NSE sector index"}</span></th></tr>')
        if g.ours is not None:
            body += (f'<tr class="sx-ours"><th scope="row">The 750’s {g.ours.stocks} stocks<span class="dh-sub">equal-weighted</span></th>'
                     + cells(g.ours.returns, g.ours.from_high, None) + "</tr>")
        for x in g.indices:
            short = x.name.removeprefix("Nifty ")
            short = {"Small Finance Banks & Microfinance Institutions": "Small Fin. Banks & MFIs",
                     "MidSmall Financial Services": "MidSmall Fin. Services", "Financial Services 25/50": "Fin. Services 25/50",
                     "Financial Services Ex-Bank": "Fin. Services Ex-Bank", "Commercial & Transport Services": "Comm. & Transport Services"}.get(short, short)
            body += (f'<tr><th scope="row"><span class="sx-f">{e(x.name)}</span><span class="sx-s">{e(short)}</span>'
                     + ('<span class="dh-sub">for the sector</span>' if x.headline else "") + "</th>"
                     + cells(x.returns, x.from_high, x.pe, f"{x.live:%-d %b %Y}" if x.young else None) + "</tr>")
    note = (f"All {len(allix)} of NSE’s sector indices, each under the sector it belongs to; the first line of each group is the "
            "sector’s ranked stocks, equal-weighted, for comparison, and “for the sector” marks the index set beside it above. "
            f"Price returns; each window ends on {nse['as_of']:%-d %b %Y} and starts on the last session on or before the same date "
            "1, 3, 6, 9 and 12 months back. An index younger than a year shows its launch in NSE’s daily file. Themes, strategies "
            "and broad indices are on Indices.")
    return [f'<div class="dh-sec">{KICK.format("NSE’s sector indices")}<h2 id="s-indices" class="dh-h2">{h2}</h2>'
            f'<p class="dh-note">{e(note)}</p><div class="dh-scroll"><table class="dh-tab dh-tab-s sx-ix"><thead><tr>'
            '<th scope="col">Index</th>' + "".join(f'<th scope="col" class="dh-num">{w}</th>' for w in ("1M", "3M", "6M", "9M", "1Y"))
            + '<th scope="col" class="dh-num">From 52W high</th><th scope="col" class="dh-num">P/E</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div></div>']


def section_only_nse() -> list:
    return [f'<div class="dh-sec">{KICK.format("NSE’s sector indices")}<p id="s-broad" class="sx-only">{e(NSE_ONLY)}</p></div>']


def section_months(months: pd.DataFrame, sh, noun: str) -> list:
    if months is None or months.empty:
        return []
    cols = [c for c in months.columns if c not in ("run", "total")]
    labels = [c.replace(" MTD", " so far") if c.endswith("MTD") else c.replace(" 20", " ’") for c in cols]
    longest = months["run"].abs().max()
    h2 = "Each month against the 750."
    ex = ""
    if longest:
        name = months[months["run"].abs() == longest].index[0]
        row = months.loc[name]
        n = int(row["run"])
        h2 = (f'{e(sh(name))} has <span class="{"dh-up" if n > 0 else "dh-down"}">{"beaten" if n > 0 else "trailed"} the 750 in each '
              f'of the last {_words(abs(n))} completed months</span>, the longest run.')
        done = cols[:-1]
        inside = done[len(done) - abs(n):][::-1]
        parts = [f"{c.split()[0]} {sg(row[c])}" for c in inside]
        ex = f"For example, {sh(name)}: {_list(parts)} pts, all {'ahead of' if n > 0 else 'behind'} the 750"
        before = done[: len(done) - abs(n)]
        if before and pd.notna(row[before[-1]]):
            ex += f"; {before[-1].split()[0]} was {sg(row[before[-1]])}, so the count stops there and Run reads {abs(n)} {'ahead' if n > 0 else 'behind'}"
        ex += f". Its 12 months, {sg(row['total'])} pts, is the twelve completed months added up."
    body = ""
    for name, r in months.iterrows():
        cells = "".join(f'<td class="dh-num {_cls(r[c])}{" dh-muted" if c.endswith("MTD") and _cls(r[c]) == "" else ""}">'
                        f'{"–" if not pd.notna(r[c]) else e(sg(r[c]))}</td>' for c in cols)
        run = int(r["run"])
        run_t = (f"{abs(run)} ahead" if run > 0 else f"{abs(run)} behind") if run else "–"
        body += (f'<tr><th scope="row">{e(sh(name))}</th>{cells}<td class="dh-num">{run_t}</td>'
                 f'<td class="dh-num {_cls(r["total"])}">{e(sg(r["total"]))}</td></tr>')
    return [f'<div class="dh-sec">{KICK.format("Month by month")}<h2 id="s-months" class="dh-h2">{h2}</h2>'
            f'<p class="dh-note">Each cell is the {noun}’s lead over the 750 in that calendar month, both equal-weighted, in pts; the '
            'last month column is the month so far. Run counts completed months in a row on the same side; the last column adds '
            'the twelve completed months. Today’s members throughout.</p>'
            f'<div class="dh-scroll"><table class="dh-tab dh-tab-s sx-mo"><thead><tr><th scope="col">{e(noun.capitalize())}, pts</th>'
            + "".join(f'<th scope="col" class="dh-num">{e(c)}</th>' for c in labels)
            + '<th scope="col" class="dh-num">Run, months</th><th scope="col" class="dh-num">12 months, summed, pts</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>' + (f'<p class="dh-note">{e(ex)}</p>' if ex else "") + "</div>"]


MAP_TEXT = {
    "ema": "D EMA", "pts": "pts", "all": "All sectors", "latest": "Latest", "stocks": "stocks", "above": "above",
    "month": "month", "months": "months", "right_of": "right of the 0 line", "left_of": "left of the 0 line",
    "above_w": "above", "below_w": "below", "how": "How to read it · worked example",
    "q_across": "Across: did it beat the 750 over the {p}?",
    "a_across": "The {n} {name} stocks as an equal-weighted index, from the {then} close to the {now} close:",
    "a_market": "The 750, built the same way over the same closes:", "a_diff": "The difference,",
    "a_hollow": "The hollow dot is the same for the period before:",
    "q_up": "Up: how many of its stocks are in an uptrend?",
    "a_up": "A stock counts when its close is above its own {span}D EMA. Today", "ago_word": "before,",
    "a_up2": "An EMA needs {need} sessions of prices, so a recent listing can be missing.",
    "q_lift": "Heavy lifting.", "a_lift": "With equal weight each stock adds roughly its own return ÷ {n}. The two largest:",
    "adds": "about", "q_line": "The line, hollow dot to filled dot.", "a_line": "It moved",
    "right": "right", "left": "left", "up": "up", "down": "down", "no_move": "neither up nor down",
    "r_ru": "it beat the 750 by more and more of its stocks are in an uptrend: broad strength building.",
    "r_rd": "it did better against the 750, but fewer of its stocks are in an uptrend: a few names carry it, so the lead is narrow.",
    "r_lu": "it did worse against the 750, but more of its stocks are back above the line: a possible early turn.",
    "r_ld": "it did worse against the 750 and fewer of its stocks are in an uptrend: weak and weakening.",
    "r_flat_up": "it did better against the 750 with the same share of its stocks in an uptrend.",
    "r_flat_down": "it did worse against the 750 with the same share of its stocks in an uptrend.",
    "today": "Today it sits {side} and {half} the 50% line.",
    "four": "Right and up: broad strength building. Right and down: beating the 750 on a few names. Left and up: lagging, but "
            "more stocks recovering. Left and down: weak and weakening.",
    "fell": "breadth fell in {n} of {of}.", "narrow": "Ahead of the 750 with under half above the {span}D EMA:",
    "sector": "Sector", "lead": "Lead, pts,", "share": "Above EMA,",
    "x_axis": "lead over the 750, pts →", "y_axis": "↑ above the {span}D EMA",
}


def section_map(views: dict, sh, noun: str) -> list:
    if not views or "200-1" not in views:
        return []
    rows = views["200-1"]
    lead = max(rows, key=lambda r: r["x1"])
    lag = min(rows, key=lambda r: r["x1"])
    rose = sum(round(r["y1"]) > round(r["y0"]) for r in rows)
    h2 = (f"Breadth rose in {_words(rose)} of {len(rows)} {noun}s from {rows[0]['then']} to {rows[0]['now']}; "
          f'<span class="dh-up">{e(sh(lead["name"]))} gained most on the 750</span>, '
          f'<span class="dh-down">{e(sh(lag["name"]))} lost most</span>.')
    text = dict(MAP_TEXT, all=f"All {noun}s", sector=noun.capitalize())
    short = {r["name"]: sh(r["name"]) for v in views.values() for r in v}
    return [f'<div class="dh-sec">{KICK.format("Sector leadership map")}<h2 id="s-map" class="dh-h2">{h2}</h2>'
            f'<p class="dh-note">Across: the {noun}’s lead over the 750 over the period, both equal-weighted, in pts (for 1M, '
            f'the one-month lead above). Up: the share of its stocks above the EMA. The hollow dot is the reading a period ago, the '
            'filled dot today. The leader is blue, the laggard rust, the rest grey; pick one to pick it out. Today’s members, '
            'five or more stocks each.</p></div>',
            Chart("lmap", {"views": views, "spans": list(sp.EMA_SPANS), "periods": list(sp.MAP_PERIODS), "start": [200, 1],
                           "short": short, "text": text},
                  {"label": "Sector leadership map: the lead over the 750 against the share above the EMA",
                   "pick": f"Pick out a {noun}", "table": "Show the table"})]


def section_inside(ld: sp.Leads, shares: list[sp.Share], board: pd.DataFrame, rank_df: pd.DataFrame, sh, noun: str) -> list:
    by = {s.name: s for s in shares}
    allr = by.get("All ranked stocks")
    rest = sorted((s for s in shares if s.name != "All ranked stocks" and s.now is not None), key=lambda s: -s.now)
    if not rest or allr is None:
        return []
    top, bot = rest[0], rest[-1]
    h2 = (f"{allr.now:.0f}% of the 750 are above their 200D EMA, {'up' if (allr.now or 0) >= (allr.b1 or 0) else 'down'} from "
          f'{allr.b1:.0f}% a month ago; <span class="dh-up">{e(sh(top.name))} has the most at {top.now:.0f}%</span>, '
          f'<span class="dh-down">{e(sh(bot.name))} the fewest at {bot.now:.0f}%</span>.')
    b = board.set_index("Industry") if not board.empty else pd.DataFrame()
    ema_all = to_bool_mask(rank_df.get("Above 50 EMA", pd.Series(False, index=rank_df.index)))
    near_all = to_bool_mask(rank_df.get("Near 52W High", pd.Series(False, index=rank_df.index)))
    med_all = pd.to_numeric(rank_df.get("3M Return"), errors="coerce").median()

    def row(s: sp.Share, ref: bool):
        if ref:
            v = {"ema50": float(ema_all.mean() * 100), "near": float(near_all.mean() * 100), "pass": int((ema_all & near_all).sum()),
                 "top50": 50, "med3": None if pd.isna(med_all) else float(med_all * 100)}
            leaders = ""
        elif s.name in b.index:
            r = b.loc[s.name]
            v = {"ema50": r["EMA %"] * 100, "near": r["Near %"] * 100, "pass": int(r["Pass"]), "top50": int(r["Top 50"]),
                 "med3": None if pd.isna(r["3M Return"]) else float(r["3M Return"] * 100)}
            leaders = ", ".join(r["Leaders"][:2])
        else:
            v, leaders = {"ema50": None, "near": None, "pass": None, "top50": None, "med3": None}, ""
        vals = {"b3": _r(s.b3, 0), "b1": _r(s.b1, 0), "now": _r(s.now, 0), "ema50": _r(v["ema50"], 0), "near": _r(v["near"], 0),
                "pass": v["pass"], "top50": v["top50"], "med3": _r(v["med3"]), "leaders": leaders}
        txt = {k: ("–" if vals[k] is None else f"{vals[k]:.0f}%") for k in ("b3", "b1", "now", "ema50", "near")}
        txt["med3"] = sg(vals["med3"], 1, "%")
        txt["leaders"] = leaders or "–"
        return {"name": "All 750" if ref else sh(s.name), "sub": f"{s.stocks} stocks", "ref": ref, "v": vals, "t": txt,
                "c": {"med3": _kt(vals["med3"]), "b3": "muted", "b1": "muted"}}
    cols = [{"k": "name", "label": noun.capitalize()},
            {"k": "b3", "label": "Above 200D EMA, 3M ago", "num": True}, {"k": "b1", "label": "Above 200D EMA, 1M ago", "num": True},
            {"k": "now", "label": "Above 200D EMA, now", "num": True, "bar": True},
            {"k": "ema50", "label": "Above 50D EMA", "num": True}, {"k": "near", "label": "Near 52W high", "num": True},
            {"k": "pass", "label": "Pass both filters", "num": True}, {"k": "top50", "label": "In top 50", "num": True},
            {"k": "med3", "label": "Typical stock, 3M", "num": True}, {"k": "leaders", "label": "Leaders"}]
    spec = {"cols": cols, "rows": [row(allr, True)] + [row(s, False) for s in rest], "sort": "now",
            "bar": {"lo": 0, "hi": 100, "step": 2, "lines": [40, 60], "ago": "b1"}}
    return [f'<div class="dh-sec">{KICK.format(f"Inside each {noun}")}<h2 id="s-inside" class="dh-h2">{h2}</h2>'
            f'<p class="dh-note">The share of each {noun}’s ranked stocks above their 200D EMA (exponential average of 200 sessions), '
            '2% a line; the dashed lines are 40% and 60%, below which a rise is narrow and above which it is broad; the triangle '
            'marks a month ago. Then the ranking table’s own flags: above the 50D EMA, within 20% of the 52W high, passing both '
            '(the Screener’s filters), in the top 50, and the typical (median) stock’s 3M return. Today’s members throughout, so '
            'older readings leave out stocks that have since left the 750. Sort by any heading.</p></div>',
            Chart("stable", spec, {"label": f"Inside each {noun}", "note": "2% a line · dashed: 40% and 60% · the triangle is a month ago"})]


# ── Small formatting helpers ─────────────────────────────────────────────────


def _r(v, nd: int = 1):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return None
    return round(float(v), nd)


def _kt(v) -> str:
    """Up/down class inside a chart frame (the kit's names)."""
    return "" if v is None else "up" if v > 0 else "down" if v < 0 else ""


def _cls(v) -> str:
    return "" if v is None or not pd.notna(v) else ("dh-up" if v > 0 else "dh-down" if v < 0 else "")


def _num(v, unit: str = "") -> str:
    return f'<td class="dh-num {"dh-muted" if v is None else _cls(v)}">{e(sg(v, 1, unit))}</td>'


# ── The page ─────────────────────────────────────────────────────────────────


def page_parts(model: dict, rank_df: pd.DataFrame, col: str) -> list:
    """Every part of the page above "Stocks in a sector", in the approved order."""
    ld: sp.Leads = model["ld"]
    nse = model["nse"]
    noun = "industry" if col == "TV_Industry" else "sector"
    sh = (lambda n: SHORT_NAMES.get(n, n)) if col == "Industry" else (lambda n: n)
    board, _ = industry_board(rank_df, col)
    parts = head(ld, sh, noun, nse) + section_lead(ld, sh, noun)
    if col == "Industry" and nse is not None:
        parts += section_broad(ld, nse, sh) + section_indices(ld, nse, sh)
    else:
        parts += section_only_nse()
    parts += section_months(model["months"], sh, noun) + section_map(model["map"], sh, noun)
    parts += section_inside(ld, model["shares"], board, rank_df, sh, noun)
    return parts


def render_sector_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame,
                       history_prices: pd.DataFrame | None = None,
                       benchmark_close: pd.Series | None = None) -> None:
    st.html(f"<style>{HOME_CSS}{SX_CSS}</style>")
    choices = {k: v for k, v in GROUPINGS.items() if v == "Industry" or v in rank_df.columns}
    with st.container(horizontal=True, horizontal_alignment="right", key="sector_grouping_row"):
        pick = st.selectbox("Grouping", list(choices), key="sector_tax_choice", width=260, label_visibility="collapsed",
                            format_func=lambda k: f"Grouping: {k}")
    col = choices.get(pick, "Industry")
    prices = history_prices if history_prices is not None else adj_close
    from src.ui.views.market_questions_view import total_market
    tm = total_market()
    if prices is None or prices.empty:
        st.html('<div class="dh"><div class="dh-sec"><p class="dh-kick">Sectors</p><h1 class="dh-h1">No prices yet.</h1></div></div>')
        return
    key = "|".join([price_fingerprint(prices), col, str(len(rank_df)), str(tm.index[-1]) if len(tm) else "-"])
    model = _model(key, rank_df, prices, col, tm)
    if model is None:
        st.html('<div class="dh"><div class="dh-sec"><p class="dh-kick">Sectors</p>'
                f'<h1 class="dh-h1">No group has {sp.MIN_STOCKS} or more ranked stocks to compare.</h1></div></div>')
        return
    emit(page_parts(model, rank_df, col))

    ld: sp.Leads = model["ld"]
    noun = "industry" if col == "TV_Industry" else "sector"
    sh = (lambda n: SHORT_NAMES.get(n, n)) if col == "Industry" else (lambda n: n)
    names = [r.name for r in ld.rows]
    top = next((r for r in ld.rows if r.group == "ahead on both"), ld.rows[0])
    emit([f'<div class="dh-sec">{KICK.format(f"Stocks in a {noun}")}<h2 id="s-stocks" class="dh-h2">The {noun}’s ranked stocks, '
          'best rank first, in the Screener’s table.</h2><p class="dh-note">The qualified rank is the place among the stocks that pass '
          'both filters, as on Actions and Portfolio.</p></div>'])
    pick_name = st.selectbox(f"Pick a {noun}", names, index=names.index(top.name), key=f"sector_pick_{col}",
                             format_func=sh, width=260)
    members = rank_df[rank_df[col] == pick_name].sort_values("Rank")
    from src.engine.exit_watch import qualified_ranks
    members = members.assign(**{"Qualified Rank": members["Symbol"].map(qualified_ranks(rank_df))})
    render_screener_table(members, adj_close, "Core")

    short_n = int((rank_df.get("Short History", pd.Series(dtype=str)) == "Yes").sum())
    st.html(f'<div class="dh"><p class="dh-foot">{_fmt.data_to(ld.when)}. {len(rank_df)} stocks ranked; '
            f'{gap_count(rank_df)} with a price gap, {short_n} with a short history.</p></div>')
    render_data_quality_footer(total_stocks=len(rank_df), gap_count=gap_count(rank_df), short_count=short_n)


__all__ = ["render_sector_view", "page_parts", "industry_board", "leadership_explainer", "SHORT_NAMES", "NSE_ONLY"]
