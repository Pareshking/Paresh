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
from src.engine.pipeline import known_fingerprint
from src.ui import formats as _fmt
from src.ui import missing_words as mw
from src.ui import page_kit as kit
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
# The > ₹2,000 Cr list and Combined carry TradingView's sector in "Industry" (docs/THREE_SYSTEMS.md), so their
# default grouping is TradingView's and NSE's indices are not set against it (S193 B: the list's page called
# TradingView sectors "NSE sector" and compared them with NSE's indices where two names matched).
TV_ONLY = "This list’s stocks carry TradingView’s sectors, so NSE’s sector indices, built on NSE’s sectors, are not set beside them."
GROUPINGS_TV = {"TradingView sector": "Industry", "TradingView industry": "TV_Industry"}
# NSE's four levels (S226; owner, 24 Nov 2026: "use Screener 4 level for any filtering"), offered when app.py's
# display copy carries them (src/loaders/nse_classification.with_nse_levels, each level at 90% of the stocks or
# more). TradingView's groupings are then not offered; they stay the fallback while the file is short.
GROUPINGS_NSE = {"NSE sector": "Industry", "NSE macro sector": "NSE_Macro", "NSE industry": "NSE_Industry",
                 "NSE basic industry": "NSE_Basic_Industry"}
NSE_LEVEL_COLS = ("NSE_Macro", "NSE_Industry", "NSE_Basic_Industry")


def noun_for(col: str) -> str:
    """What the page calls one group of the grouping `col`: a sector, or an industry."""
    return "industry" if col in ("TV_Industry", "NSE_Industry", "NSE_Basic_Industry") else "sector"


def groupings(rank_df: pd.DataFrame, system: str | None) -> tuple[dict[str, str], bool]:
    """The grouping picker's choices for this frame, and whether "Industry" holds NSE's sectors.

    A display copy says itself whether its "Industry" is NSE's (`attrs["nse_sectors"]`); a frame without
    the mark is read by the system, as before S226.
    """
    nse_sectors = bool(rank_df.attrs.get("nse_sectors", not tv_sectors(system)))
    if any(c in rank_df.columns for c in NSE_LEVEL_COLS):
        base = GROUPINGS_NSE if nse_sectors else {"TradingView sector": "Industry", **{
            k: v for k, v in GROUPINGS_NSE.items() if v != "Industry"}}
    else:
        base = GROUPINGS if nse_sectors else GROUPINGS_TV
    return {k: v for k, v in base.items() if v == "Industry" or v in rank_df.columns}, nse_sectors


def tv_sectors(system: str | None) -> bool:
    from src.engine.extra_universe import SYSTEM_COMBINED, SYSTEM_NANO
    return system in (SYSTEM_NANO, SYSTEM_COMBINED)
GROUP_WORDS = {"ahead on both": ("Ahead on both", "ahead over 6 months and over 1 month"),
               "gaining": ("Gaining", "behind over 6 months, ahead over 1 month"),
               "fading": ("Fading", "ahead over 6 months, behind over 1 month"),
               "behind on both": ("Behind on both", "behind over 6 months and over 1 month")}

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
            out["nse"] = {"as_of": ld.when, "groups": sp.sector_indices(f, ld, smap, counts),
                          "gaps": sp.broad_or_narrow(f, ld, smap), "pairs": sp.pair_series(f, ld, smap)}
    return out


# ── Sections ─────────────────────────────────────────────────────────────────


def _list(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _plural(noun: str) -> str:
    """ "sectors", "industries" (the grouping's noun; "industrys" was printed before, 24 Nov 2026)."""
    return noun[:-1] + "ies" if noun.endswith("y") else noun + "s"


def _poss(name: str) -> str:
    """A group's possessive: "Healthcare’s", and "Financials’" for a name that is a plural in form."""
    return name + ("’" if name.endswith("s") else "’s")


def _d(day) -> str:
    return f"{pd.Timestamp(day):%-d %b}"


def _count_of(k: int, n: int) -> str:
    """ "7 of 19", "None of 19" (rule 11: a count in a sentence is a figure; "none" a fixed word). """
    return f"None of {n}" if k == 0 else f"{k} of {n}"


def _rose(v: float) -> str:
    """ "rose 2.3%" / "fell 1.0%": the verb carries the sign, the figure is unsigned (rule 2). """
    return f"{'fell' if v < 0 else 'rose'} {_fmt.fixed(abs(v), 1)}%"


def head_title(ld: sp.Leads, sh, noun: str, uni: str = "750") -> str:
    """The h1 (S203 se.head.1): the sectors ahead on both windows (three named, the rest counted), then the two
    furthest behind over 6 months."""
    both = [sh(r.name) for r in ld.rows if r.group == "ahead on both"]
    worst = sorted(ld.rows, key=lambda r: r.lead6)[:2]
    if both:
        names = _list(both) if len(both) <= 3 else f"{', '.join(both[:3])} and {len(both) - 3} more"
        verb = "leads" if len(both) == 1 else "lead"
        title = f'<span class="dh-up">{e(names)}</span> {verb} the {uni} over 6 months and 1 month'
    else:
        title = f"No {noun} leads the {uni} on both 6 months and 1 month"
    if len(worst) == 2 and worst[1].lead6 < 0:
        title += (f'; <span class="dh-down">{e(sh(worst[0].name))} and {e(sh(worst[1].name))}</span> trail it by '
                  f"{int(np.floor(min(-worst[0].lead6, -worst[1].lead6)))} points or more over 6 months")
    return title + "."


def head_lede(ld: sp.Leads, noun: str, nse: dict | None, uni: str = "750") -> str:
    """The lede (S203 se.head.2): the count ahead on both; then, where NSE's indices are set beside the sectors, the
    month's two returns and how many sector indices beat their sector; then the close the figures are read to."""
    n_both = sum(r.group == "ahead on both" for r in ld.rows)
    n = len(ld.rows)
    lede = (f"{_count_of(n_both, n)} {noun if n == 1 else _plural(noun)} {'is' if n_both <= 1 else 'are'} ahead of the "
            f"{uni}, equal-weighted, over both windows.")
    if nse and nse.get("gaps"):
        tm1, m1 = ld.gap.get("1"), ld.market_ret.get(1)
        if tm1 is not None and m1 is not None:
            lede += f" Over 1 month, Nifty Total Market {_rose(m1 - tm1)} and the {uni}, equal-weighted, {_rose(m1)}."
        k, m = sum(g.gap1 < 0 for g in nse["gaps"]), len(nse["gaps"])
        lede += (f" All {m} sector indices beat" if k == m and m > 1 else f" {_count_of(k, m)} sector "
                 f"{'index' if m == 1 else 'indices'} beat") + " their sector’s ranked stocks over the month."
        late = [x.name for g in nse.get("groups") or [] for x in g.indices if x.headline and x.late is not None]
        if late:
            lede += " " + _fmt.closes_not_in(late, nse["as_of"])
    return lede + f" Price returns, to the {ld.when:%-d %b %Y} close."


def head(ld: sp.Leads, sh, noun: str, nse: dict | None, uni: str = "750") -> list:
    nouns = _plural(noun)
    title, lede = head_title(ld, sh, noun, uni), head_lede(ld, noun, nse, uni)
    links = [("s-lead", f"Which {nouns} lead"), ("s-broad", "Broad or narrow"), ("s-indices", "NSE’s sector indices"),
             ("s-months", "Month by month"), ("s-map", "Sector leadership map"), ("s-inside", f"Inside each {noun}"),
             ("s-stocks", f"Stocks in a {noun}")]
    if nse is None:
        links = [x for x in links if x[0] not in ("s-broad", "s-indices")]
    nav = "".join(f'<a href="#{a}">{e(t)}</a>' for a, t in links)
    return [f'<div class="dh-sec">{KICK.format("Sectors")}<h1 id="s-top" class="dh-h1">{title}</h1>'
            f'<p class="dh-lede">{e(lede)}</p><nav class="sx-toc" aria-label="On this page">{nav}</nav></div>']


def lead_headline(ld: sp.Leads, sh, noun: str) -> str:
    """Section 1's h2 (S203 se.lead.1): the counts ahead and behind on both windows, then the sector behind on both
    that fell furthest from a 6-month lead 3 months ago."""
    nouns = _plural(noun)
    n_both = sum(r.group == "ahead on both" for r in ld.rows)
    n_behind = sum(r.group == "behind on both" for r in ld.rows)
    ahead = (f"No {noun} leads" if n_both == 0 else f"1 {noun} leads" if n_both == 1 else f"{n_both} {nouns} lead")
    behind = "none trails" if n_behind == 0 else "1 trails" if n_behind == 1 else f"{n_behind} trail"
    h2 = (f'<span class="dh-up">{ahead} on both 6 months and 1 month</span>; '
          f'<span class="dh-down">{behind} on both</span>.')
    fell = max(ld.rows, key=lambda r: (r.lead6_3m or 0) - r.lead6 if r.group == "behind on both" else -1e9)
    if fell.group == "behind on both" and fell.lead6_3m is not None and fell.lead6_3m > 0:
        h2 += (f" {e(sh(fell.name))} is among them; its 6-month lead was {_fmt.fixed(fell.lead6_3m, 1)} points "
               f"on {_d(ld.d3)}.")
    return h2


def lead_example(ld: sp.Leads, sh, uni: str = "750") -> str:
    """The worked example in "How it is built" (S203 se.lead.4, owner's answer 4): the table's top row, filled."""
    ex = ld.rows[0]
    return (f"{_poss(sh(ex.name))} {ex.stocks} stocks returned {sg(ex.returns.get(6), 1, '%')} over 6 months and the {uni} "
            f"{sg(ld.market_ret.get(6), 1, '%')}, a lead of {sg(ex.lead6)} points.")


def section_lead(ld: sp.Leads, sh, noun: str, nse_sectors: bool = True, uni: str = "750") -> list:
    nouns = _plural(noun)
    h2 = lead_headline(ld, sh, noun)

    def rd(r_name, l6, l1, ago, l3=None, l12=None):
        return [[sg(l6) + " pts", "6M lead now", _kt(l6)], [sg(ago) + " pts", "a month ago"],
                [sg(l1) + " pts", "one-month lead", _kt(l1)], [sg(l3) + " pts", "three-month", _kt(l3)],
                [sg(l12) + " pts", "12M", _kt(l12)]]
    g = ld.gap
    rows = []
    if g.get("6") is not None:
        rows.append({"name": f"The {uni} against Nifty Total Market", "sub": "equal-weighted vs cap-weighted", "ref": True,
                     "bar": _r(g["6"]), "ago": _r(g.get("6_1m")),
                     "vals": [sg(g.get("6_3m")), sg(g.get("6_1m")), sg(g["6"]), sg(g.get("1")), sg(g.get("3")), sg(g.get("12"))],
                     "cls": ["muted", "muted", _kt(g["6"]) + " b", _kt(g.get("1")), _kt(g.get("3")), _kt(g.get("12"))],
                     "read": rd(f"The {uni}", g["6"], g.get("1"), g.get("6_1m"), g.get("3"), g.get("12"))})
    for key, (label, what) in GROUP_WORDS.items():
        rs = [r for r in ld.rows if r.group == key]
        if not rs:
            continue
        rows.append({"heading": f"{label} · {len(rs)}", "sub": what})
        for r in rs:
            rows.append({"name": sh(r.name), "sub": f"{r.stocks} stocks", "bar": _r(r.lead6), "ago": _r(r.lead6_1m),
                         "vals": [sg(r.lead6_3m), sg(r.lead6_1m), sg(r.lead6), sg(r.lead1), sg(r.lead3), sg(r.lead12)],
                         "cls": ["muted", "muted", _kt(r.lead6) + " b", _kt(r.lead1), _kt(r.lead3), _kt(r.lead12)],
                         "read": rd(r.name, r.lead6, r.lead1, r.lead6_1m, r.lead3, r.lead12)})
    spec = {"label": f"{noun.capitalize()} · lead, pts", "barHead": f"Six-month lead over the {uni}, pts",
            "head": [_d(ld.d3), _d(ld.d1), "Now", "1M", "3M", "12M"], "rows": rows, "lo": -20, "hi": 20, "step": 1,
            "rest": "Latest · the first row"}
    sw = sp.nearest_switches(ld)
    ent = "; ".join(f"<b>{e(sh(n))}</b> {sg(v)} points" for n, v in sw["entrants"])   # S203 se.lead.3
    ext = "; ".join(f"<b>{e(sh(n))}</b> {sg(v)} points" for n, v in sw["exits"])
    would = ('<div class="dh-sec dh-sec-cont"><h3 class="dh-h3">What would change the answer</h3><ul class="dh-note">'
             + (f"<li>Nearest to moving ahead over 6 months: {ent}.</li>" if ent else "")
             + (f"<li>Nearest to falling behind: {ext}.</li>" if ext else "")
             + "</ul><p class=\"dh-note\">Which sizes lead, against Nifty Total Market at 1M, 3M and 6M: on the Dashboard, "
             f'<a href="{page_href("./")}#s-size" target="_self">Size, and where momentum works →</a></p></div>')
    left = ", ".join(f"{k} ({v})" for k, v in sorted(ld.left_out.items(), key=lambda kv: -kv[1]))
    what = (f"A {noun} here is the equal-weighted index of its ranked stocks, rebalanced daily, and so is the {uni}. "
            f"{len(ld.rows)} have five or more ranked stocks and are shown"
            + (f"; left out with fewer: {left}" if left else "") + ". Comparing like with like keeps a rally of large "
            f"companies from reading as every one lagging; that gap is the first row, the {uni} against Nifty Total Market. "
            f"{lead_example(ld, sh, uni)} The grouping switch at the top "
            + ("regroups the page by NSE sector (the default), TradingView sector or TradingView industry." if nse_sectors else
               "regroups the page by TradingView sector (the default: this list’s stocks carry TradingView’s sectors) "
               "or TradingView industry."))
    read = ("Each line is 1 point; the bar is the 6M lead now, the triangle the same reading a month ago, and the "
            "numbers the reading 3 months ago, a month ago, now, then the 1M, 3M and 12M leads now. "
            "Describing is not forecasting: a lead on both windows has not been tested here as a signal for the next month.")
    table = how(what, read, [noun.capitalize(), "Stocks", f"6M lead {_d(ld.d3)}", f"6M lead {_d(ld.d1)}", "6M lead now", "1M lead",
                             "3M lead", "12M lead"],
                [[sh(r.name), r.stocks, sg(r.lead6_3m), sg(r.lead6_1m), sg(r.lead6), sg(r.lead1), sg(r.lead3), sg(r.lead12)]
                 for r in ld.rows])
    # A 12M lead needs a year of the group's prices; a "–" says why, once for the column (S193 E).
    short = [sh(r.name) for r in ld.rows if r.lead12 is None]
    dash_note = (" " + mw.column_note("12M", f"{mw.TOO_NEW} (under 12 months of prices): {_list(short)}")   # se.lead.2
                 if short else "")
    return [f'<div class="dh-sec">{KICK.format(f"Which {nouns} lead")}<h2 id="s-lead" class="dh-h2">{h2}</h2>'
            f'<p class="dh-note">Lead: the {noun}’s return less the {uni}’s over the same sessions, both equal-weighted, in pts. '
            'Groups: ahead or behind over 6 months and over the last month; the 3M and 12M leads '
            f'are shown beside them and do not move a {noun} between groups.{e(dash_note)}</p></div>',
            Chart("trows", spec, {"label": f"Each {noun}'s lead over the {uni}", "note": "Each line is 1 pt · the triangle is a month ago"}),
            would, table]


def _late_headlines(nse: dict) -> str:
    """" NSE's 20 Nov close for Nifty Bank is not in yet, so its sector is left out here." or "" (S148, S193 E)."""
    late = [x.name for g in nse.get("groups") or [] for x in g.indices if x.headline and x.late is not None]
    if not late:
        return ""
    return f" {_fmt.closes_not_in(late, nse['as_of'])} {'Its sector is' if len(late) == 1 else 'Their sectors are'} left out here."


def broad_headline(ld: sp.Leads, gaps: list[sp.Gap], sh, uni: str = "750") -> str:
    """Section 2's h2 (S203 se.broad.1). The example is the widest gap (gaps are narrowest first), not a typed
    sector; the colour goes on the verdict clause only, never on the figures."""
    m3 = ld.gap.get("3")
    fin = gaps[0]
    narrow = [sh(g.sector) for g in gaps if m3 is not None and g.gap3 < m3]
    stocks = next((r.stocks for r in ld.rows if r.name == fin.sector), 0)
    h2 = f"{e(fin.index)} {_rose(fin.nse3)} over 3 months, while the sector’s {stocks} ranked stocks {_rose(fin.ours3)}."
    if m3 is None:
        return h2
    against = f"narrower than the {uni} against Nifty Total Market"
    if len(narrow) == 1:
        h2 += f' <span class="dh-down">Only {e(narrow[0])} is {against}.</span>'
    elif narrow:
        h2 += f' <span class="dh-down">{len(narrow)} sectors are {against}</span>: {e(_list(narrow))}.'
    else:
        h2 += f" No sector is {against}."
    return h2


def section_broad(ld: sp.Leads, nse: dict, sh, uni: str = "750") -> list:
    gaps = nse["gaps"]
    if not gaps:
        return []
    m3 = ld.gap.get("3")
    h2 = broad_headline(ld, gaps, sh, uni)
    rows = []
    if m3 is not None:
        o3, t3 = ld.market_ret.get(3), (ld.market_ret.get(3) or 0) - m3
        rows.append({"name": f"The {uni} against Nifty Total Market", "sub": "Nifty Total Market", "ref": True, "bar": _r(m3),
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
    pairs = [{"short": sh(g.sector), "ours_name": f"{sh(g.sector)}, the {uni}’s stocks", **{k: v for k, v in nse["pairs"][g.sector].items()}}
             for g in gaps if g.sector in nse["pairs"]]
    start = 0  # the widest gap, the headline's own example (S203 Q4; it was typed "Financial Services")
    return [f'<div class="dh-sec">{KICK.format("Broad or narrow")}<h2 id="s-broad" class="dh-h2">{h2}</h2>'
            '<p class="dh-note">Each sector’s ranked stocks, equal-weighted, against NSE’s index for the sector, which holds its own '
            'selection of the sector’s companies and weights them by free-float value: the two differ in stocks and in weights. '
            f'The bar is the gap over three months, 0.5 pt a line. The dashed line is the {uni}’s own gap to Nifty Total Market: '
            f'a bar left of it means the sector’s largest companies did more of the work than the largest companies did across the {uni}. '
            f'{_fmt.PTS_NOTE}{e(_late_headlines(nse))}</p></div>',
            Chart("trows", spec, {"label": "Each sector against its NSE index", "note": f"0.5 pt a line · dashed: the {uni} against Nifty Total Market"}),
            '<div class="dh-sec dh-sec-cont"><h3 class="dh-h3">12 months, each line set to 100 at the start (or at the index’s launch)</h3></div>',
            Chart("pairs", {"pairs": pairs, "start": start, "text": {"gap": "gap", "latest": "Latest", "month_end": "Month end"}},
                  {"label": "A sector's ranked stocks and NSE's index for it over 12 months", "table": "Show the table"})]


def indices_headline(allix: list[sp.IndexLine]) -> str:
    """Section 3's h2 (S203 se.ix.1): the leader and laggard over 12 months, then how many are too young for it."""
    full = sorted((x for x in allix if x.returns.get(12) is not None), key=lambda x: -x.returns[12])
    n, young = len(allix), sum(x.young for x in allix)
    if not full:
        return f"NSE’s {n} sector indices, each beside its sector."
    h2 = (f'Over 12 months, <span class="dh-up">{e(full[0].name)} leads NSE’s sector indices</span>, '
          f'{_fmt.moved(full[0].returns[12])}, and <span class="dh-down">{e(full[-1].name)} trails</span>, '
          f'{_fmt.moved(full[-1].returns[12])}.')
    young_txt = (f"None of the {n} is" if young == 0 else f"{young} of the {n} {'is' if young == 1 else 'are'}")
    return h2 + f" {young_txt} younger than 12 months."


def section_indices(ld: sp.Leads, nse: dict, sh, uni: str = "750") -> list:
    groups = nse["groups"]
    allix = [x for g in groups for x in g.indices]
    h2 = indices_headline(allix)

    def cells(ret, hi, pe, young_since=None, has_pe=True):
        out = "".join(_num(ret.get(m), "%") for m in (1, 3, 6, 9))
        out += (f'<td class="dh-num dh-muted">since {young_since}</td>' if young_since else _num(ret.get(12), "%"))
        hi_t = "–" if hi is None else ("at high" if abs(hi) < 0.05 else sg(hi, 1, "%"))
        # An equal-weighted group of our stocks has no P/E: the figure does not apply, a blank cell (R2).
        pe_t = mw.NOT_APPLICABLE if not has_pe else (mw.DASH if pe is None else f"{pe:.1f}")
        return out + f'<td class="dh-num dh-muted">{e(hi_t)}</td><td class="dh-num dh-muted">{pe_t}</td>'
    body = ""
    for g in groups:
        body += (f'<tr class="sx-grp"><th scope="colgroup" colspan="8">{e(sh(g.sector))}<span>{g.stocks} ranked stocks'
                 f'{"" if g.indices else " · no NSE sector index"}</span></th></tr>')
        if g.ours is not None:
            body += (f'<tr class="sx-ours"><th scope="row">The {uni}’s {g.ours.stocks} stocks<span class="dh-sub">equal-weighted</span></th>'
                     + cells(g.ours.returns, g.ours.from_high, None, has_pe=False) + "</tr>")
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
            "1, 3, 6, 9 and 12 months back. An index younger than 12 months shows its launch in NSE’s daily file. Themes, strategies "
            "and broad indices are on Indices.")
    late = [x.name for x in allix if x.late is not None]
    if late:
        note += " " + _fmt.closes_not_in(late, nse["as_of"]) + " Their figures read –."
    return [f'<div class="dh-sec">{KICK.format("NSE’s sector indices")}<h2 id="s-indices" class="dh-h2">{h2}</h2>'
            f'<p class="dh-note">{e(note)}</p><div class="dh-scroll"><table class="dh-tab dh-tab-s sx-ix"><thead><tr>'
            '<th scope="col">Index</th>' + "".join(f'<th scope="col" class="dh-num">{w}</th>' for w in ("1M", "3M", "6M", "9M", "12M"))
            + '<th scope="col" class="dh-num">From 52W high</th><th scope="col" class="dh-num">P/E</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div></div>']


def section_only_nse(nse_sectors: bool = True) -> list:
    return [f'<div class="dh-sec">{KICK.format("NSE’s sector indices")}<p id="s-broad" class="sx-only">'
            f'{e(NSE_ONLY if nse_sectors else TV_ONLY)}</p></div>']


def _month(label: str) -> str:
    """ "Oct 2026" -> "October" (the archive's :mon slot)."""
    return f"{pd.Timestamp(label):%B}"


def _names(names: list[str]) -> str:
    """Up to three names, the rest counted: "A, B, C and 2 more"."""
    return _list(names) if len(names) <= 3 else f"{', '.join(names[:3])} and {len(names) - 3} more"


def months_headline(months: pd.DataFrame, sh, noun: str, uni: str = "750") -> tuple[str, str]:
    """Section 4's h2 and its worked example (S203 se.mo.1, se.mo.2): the longest run of completed months on one
    side of the {uni}. A run of two is named, a longer one counted (owner's answer 1); ties name every sector."""
    cols = [c for c in months.columns if c not in ("run", "total")]
    longest = int(months["run"].abs().max()) if len(months) else 0
    if not longest:
        return f"No {noun} has beaten or trailed the {uni} two months running.", ""
    first = months[months["run"].abs() == longest].index[0]
    n = int(months.loc[first, "run"])
    tied = [sh(x) for x in months.index[months["run"] == n]]
    done = cols[:-1]
    inside = done[len(done) - abs(n):]
    side = "dh-up" if n > 0 else "dh-down"
    if abs(n) == 1:
        verb = "beat" if n > 0 else "trailed"
        h2 = (f'{e(_names(tied))} <span class="{side}">{verb} the {uni} in {_month(inside[0])}</span>, and no {noun} '
              "has a longer run.")
    else:
        verb = ("has " if len(tied) == 1 else "have ") + ("beaten" if n > 0 else "trailed")
        when = (f"in {_month(inside[0])} and {_month(inside[1])}" if abs(n) == 2 else
                f"in each of the last {abs(n)} completed months")
        h2 = (f'{e(_names(tied))} {verb.split()[0]} <span class="{side}">{verb.split()[1]} the {uni} {when}</span>, '
              f'the longest run{"" if len(tied) == 1 else "s"}.')
    row = months.loc[first]
    parts = [f"{c.split()[0]} {sg(row[c])}" for c in inside[::-1]]
    ex = (f"For example, {sh(first)}: {_list(parts)} points, {'all ' if abs(n) > 1 else ''}"
          f"{'ahead of' if n > 0 else 'behind'} the {uni}")
    before = done[: len(done) - abs(n)]
    if before and pd.notna(row[before[-1]]):
        v = float(row[before[-1]])
        # A hair on the other side prints "0.0" and gives no reason the run stops (S193 B: May was +0.0024).
        was = (f"{'ahead' if v > 0 else 'behind'} by less than 0.05" if abs(v) < 0.05 and v != 0 else sg(v))
        ex += f"; {before[-1].split()[0]} was {was}, so the count stops there and Run reads {abs(n)} {'ahead' if n > 0 else 'behind'}"
    ex += f". Its 12 months, {sg(row['total'])} points, is the 12 completed months added up."
    return h2, ex


def section_months(months: pd.DataFrame, sh, noun: str, uni: str = "750") -> list:
    if months is None or months.empty:
        return []
    cols = [c for c in months.columns if c not in ("run", "total")]
    labels = [c if c.endswith("so far") else c.replace(" 20", " ’") for c in cols]
    h2, ex = months_headline(months, sh, noun, uni)
    body = ""
    for name, r in months.iterrows():
        cells = "".join(f'<td class="dh-num {_cls(r[c])}{" dh-muted" if c.endswith("so far") and _cls(r[c]) == "" else ""}">'
                        f'{"–" if not pd.notna(r[c]) else e(sg(r[c]))}</td>' for c in cols)
        run = int(r["run"])
        run_t = (f"{abs(run)} ahead" if run > 0 else f"{abs(run)} behind") if run else "–"
        body += (f'<tr><th scope="row">{e(sh(name))}</th>{cells}<td class="dh-num">{run_t}</td>'
                 f'<td class="dh-num {_cls(r["total"])}">{e(sg(r["total"]))}</td></tr>')
    return [f'<div class="dh-sec">{KICK.format("Month by month")}<h2 id="s-months" class="dh-h2">{h2}</h2>'
            f'<p class="dh-note">Each cell is the {noun}’s lead over the {uni} in that calendar month, both equal-weighted, in pts; the '
            'last month column is the month so far. Run counts completed months in a row on the same side; the last column adds '
            'the 12 completed months. Today’s members throughout.</p>'
            f'<div class="dh-scroll"><table class="dh-tab dh-tab-s sx-mo"><thead><tr><th scope="col">{e(noun.capitalize())}, pts</th>'
            + "".join(f'<th scope="col" class="dh-num">{e(c)}</th>' for c in labels)
            + '<th scope="col" class="dh-num">Run, months</th><th scope="col" class="dh-num">12 months, summed, pts</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>' + (f'<p class="dh-note">{e(ex)}</p>' if ex else "") + "</div>"]


MAP_TEXT = {
    "ema": "D EMA", "pts": "pts", "all": "All sectors", "latest": "Latest", "stocks": "stocks", "above": "above",
    "month": "month", "months": "months", "right_of": "right of the 0 line", "left_of": "left of the 0 line",
    "above_w": "above", "below_w": "below", "how": "How to read it · worked example",
    "q_across": "Across: did it beat the {uni} over the {p}?",
    "a_across": "The {n} {name} stocks as an equal-weighted index, from the {then} close to the {now} close:",
    "a_market": "The {uni}, built the same way over the same closes:", "a_diff": "The difference,",
    "a_hollow": "The hollow dot is the same for the period before:",
    "q_up": "Up: how many of its stocks are in an uptrend?",
    "a_up": "A stock counts when its close is above its own {span}D EMA. Today", "ago_word": "before,",
    "a_up2": "An EMA needs {need} sessions of prices, so a recent listing can be missing.",
    "q_lift": "Heavy lifting.", "a_lift": "With equal weight each stock adds roughly its own return ÷ {n}. The two largest:",
    "adds": "about", "q_line": "The line, hollow dot to filled dot.", "a_line": "It moved",
    "right": "right", "left": "left", "up": "up", "down": "down", "no_move": "neither up nor down",
    "r_ru": "it beat the {uni} by more and more of its stocks are in an uptrend: broad strength building.",
    "r_rd": "it did better against the {uni}, but fewer of its stocks are in an uptrend: a few names carry it, so the lead is narrow.",
    "r_lu": "it did worse against the {uni}, but more of its stocks are back above the line: a possible early turn.",
    "r_ld": "it did worse against the {uni} and fewer of its stocks are in an uptrend: weak and weakening.",
    "r_flat_up": "it did better against the {uni} with the same share of its stocks in an uptrend.",
    "r_flat_down": "it did worse against the {uni} with the same share of its stocks in an uptrend.",
    "today": "Today it sits {side} and {half} the 50% line.",
    "four": "Right and up: broad strength building. Right and down: beating the {uni} on a few names. Left and up: lagging, but "
            "more stocks recovering. Left and down: weak and weakening.",
    "fell": "breadth fell in {n} of {of}.", "narrow": "Ahead of the {uni} with under half above the {span}D EMA:",
    "sector": "Sector", "lead": "Lead, pts,", "share": "Above EMA,",
    "x_axis": "lead over the {uni}, pts →", "y_axis": "↑ above the {span}D EMA",
}


def map_text(uni: str = "750") -> dict:
    """The map's fixed strings with the system's list filled in (rule 12); the JS fills the other slots."""
    return {k: v.replace("{uni}", uni) for k, v in MAP_TEXT.items()}


def map_headline(rows: list[dict], sh, noun: str, uni: str = "750") -> str:
    """Section 5's h2 (S203 se.map.1): where breadth rose, then who gained and lost most against the {uni}."""
    n = len(rows)
    rose = sum(_fmt.half_up(r["y1"]) > _fmt.half_up(r["y0"]) for r in rows)
    count = f"none of {n}" if rose == 0 else f"all {n}" if rose == n else f"{rose} of {n}"
    top = max(_fmt.half_up(r["x1"], 1) for r in rows)
    lead = [sh(r["name"]) for r in rows if _fmt.half_up(r["x1"], 1) == top]
    lag = min(rows, key=lambda r: r["x1"])
    return (f"Breadth rose in {count} {noun if n == 1 else _plural(noun)} from {rows[0]['then']} to {rows[0]['now']}. "
            f'<span class="dh-up">{e(_list(lead))} gained most on the {uni}</span>, '
            f'<span class="dh-down">{e(sh(lag["name"]))} lost most</span>.')


def section_map(views: dict, sh, noun: str, uni: str = "750") -> list:
    if not views or "200-1" not in views:
        return []
    rows = views["200-1"]
    h2 = map_headline(rows, sh, noun, uni)
    text = dict(map_text(uni), all=f"All {_plural(noun)}", sector=noun.capitalize())
    short = {r["name"]: sh(r["name"]) for v in views.values() for r in v}
    return [f'<div class="dh-sec">{KICK.format("Sector leadership map")}<h2 id="s-map" class="dh-h2">{h2}</h2>'
            f'<p class="dh-note">Across: the {noun}’s lead over the {uni} over the period, both equal-weighted, in pts (for 1M, '
            f'the one-month lead above). Up: the share of its stocks above the EMA. The hollow dot is the reading a period ago, the '
            'filled dot today. The leader is blue, the laggard rust, the rest grey; pick one to pick it out. Today’s members, '
            'five or more stocks each.</p></div>',
            Chart("lmap", {"views": views, "spans": list(sp.EMA_SPANS), "periods": list(sp.MAP_PERIODS), "start": [200, 1],
                           "short": short, "text": text},
                  {"label": f"Sector leadership map: the lead over the {uni} against the share above the EMA",
                   "pick": f"Pick out a {noun}", "table": "Show the table"})]


def _gap() -> str:
    """The "near the 52-week high" line from the rules, not typed (rule 9): "20" for high_pct 0.80."""
    from src.engine.track_record import TRACK_RECORD_CONFIG as cfg
    return _fmt.fixed((1 - cfg["high_pct"]) * 100, 0)


def inside_headline(allr: sp.Share, rest: list[sp.Share], sh, uni: str = "750") -> str:
    """Section 6's h2 (S203 se.in.1): the {uni}'s share above the 200D EMA against a month ago, then the sectors with
    the most and the fewest (ties named). `rest` is sorted by the share now, highest first."""
    now = _fmt.fixed(allr.now, 0)
    h2 = f"{now}% of the {uni}’s stocks are above their 200D EMA"
    if allr.b1 is not None:
        ago = _fmt.fixed(allr.b1, 0)
        move = "the same as" if ago == now else "up from" if allr.now > allr.b1 else "down from"
        h2 += f", {move} {ago}% a month ago"
    top, bot = _fmt.fixed(rest[0].now, 0), _fmt.fixed(rest[-1].now, 0)
    most = [sh(s.name) for s in rest if _fmt.fixed(s.now, 0) == top]
    fewest = [sh(s.name) for s in rest if _fmt.fixed(s.now, 0) == bot]
    return (h2 + f'. <span class="dh-up">{e(_list(most))} {"has" if len(most) == 1 else "have"} the most, {top}%</span>, '
            f'and <span class="dh-down">{e(_list(fewest))} the fewest, {bot}%</span>.')


def section_inside(ld: sp.Leads, shares: list[sp.Share], board: pd.DataFrame, rank_df: pd.DataFrame, sh, noun: str,
                   uni: str = "750") -> list:
    by = {s.name: s for s in shares}
    allr = by.get("All ranked stocks")
    rest = sorted((s for s in shares if s.name != "All ranked stocks" and s.now is not None), key=lambda s: -s.now)
    if not rest or allr is None or allr.now is None:
        return []
    h2 = inside_headline(allr, rest, sh, uni)
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
        # The reference row has no leaders of its own (blank); a group too small today reads "–", footnoted below.
        txt["leaders"] = leaders or (mw.NOT_APPLICABLE if ref else mw.DASH)
        return {"name": "All ranked stocks" if ref else sh(s.name), "sub": f"{s.stocks} stocks", "ref": ref, "v": vals, "t": txt,
                "c": {"med3": _kt(vals["med3"]), "b3": "muted", "b1": "muted"}}
    cols = [{"k": "name", "label": noun.capitalize()},
            {"k": "b3", "label": "Above 200D EMA, 3M ago", "num": True}, {"k": "b1", "label": "Above 200D EMA, 1M ago", "num": True},
            {"k": "now", "label": "Above 200D EMA, now", "num": True, "bar": True},
            {"k": "ema50", "label": "Above 50D EMA", "num": True}, {"k": "near", "label": "Near 52W high", "num": True},
            {"k": "pass", "label": "Pass both filters", "num": True}, {"k": "top50", "label": "In top 50", "num": True},
            {"k": "med3", "label": "Typical stock, 3M", "num": True}, {"k": "leaders", "label": "Leaders"}]
    small = [s for s in rest if s.name not in b.index]
    dash_note = (" " + mw.column_note("the filter columns and Leaders", f"{mw.too_few_stocks(sp.MIN_STOCKS)} "
                                      f"({', '.join(sh(s.name) for s in small)})")) if small else ""
    spec = {"cols": cols, "rows": [row(allr, True)] + [row(s, False) for s in rest], "sort": "now",
            "bar": {"lo": 0, "hi": 100, "step": 2, "lines": [40, 60], "ago": "b1"}}
    return [f'<div class="dh-sec">{KICK.format(f"Inside each {noun}")}<h2 id="s-inside" class="dh-h2">{h2}</h2>'
            f'<p class="dh-note">The share of each {noun}’s ranked stocks above their 200D EMA (exponential average of 200 sessions), '
            '2% a line; the dashed lines are 40% and 60%, below which a rise is narrow and above which it is broad; the triangle '
            f'marks a month ago. Then the ranking table’s own flags: above the 50D EMA, within {_gap()}% of the 52-week high, '
            'passing both (the Screener’s filters), in the top 50, and the typical (median) stock’s 3M return. Today’s members '
            f'throughout, so older readings leave out stocks that have since left the {uni}. Sort by any heading.'
            f'{e(dash_note)}</p></div>',
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


def page_parts(model: dict, rank_df: pd.DataFrame, col: str, nse_sectors: bool = True, uni: str = "750") -> list:
    """Every part of the page above "Stocks in a sector", in the approved order. `nse_sectors`: False
    where "Industry" holds TradingView's sectors (the list, Combined). `uni` is the system's list
    (`UNIVERSE_SHORT`), a slot in every sentence that names it (S203 se.uni.1, rule 12)."""
    ld: sp.Leads = model["ld"]
    nse_cols = col == "Industry" and nse_sectors
    nse = model["nse"] if nse_cols else None
    noun = noun_for(col)
    sh = (lambda n: SHORT_NAMES.get(n, n)) if nse_cols else (lambda n: n)
    board, _ = industry_board(rank_df, col)
    parts = head(ld, sh, noun, nse, uni) + section_lead(ld, sh, noun, nse_sectors, uni)
    if nse is not None:
        parts += section_broad(ld, nse, sh, uni) + section_indices(ld, nse, sh, uni)
    else:
        parts += section_only_nse(nse_sectors)
    parts += section_months(model["months"], sh, noun, uni) + section_map(model["map"], sh, noun, uni)
    parts += section_inside(ld, model["shares"], board, rank_df, sh, noun, uni)
    return parts


def stocks_heading(name: str, n: int) -> str:
    """Section 7's h2 (S203 se.stk.1): the group picked, named, with its count."""
    return f"{_poss(name)} {n} ranked stocks, best rank first."


def render_sector_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame,
                       history_prices: pd.DataFrame | None = None,
                       benchmark_close: pd.Series | None = None, system: str | None = None) -> None:
    from src.engine.extra_universe import UNIVERSE_SHORT
    if system is None:
        from src.ui import system_param
        system = system_param.current()
    universe = UNIVERSE_SHORT.get(system, "750")
    st.html(f"<style>{HOME_CSS}{SX_CSS}</style>")
    choices, nse_sectors = groupings(rank_df, system)
    with st.container(horizontal=True, horizontal_alignment="right", key="sector_grouping_row"):
        pick = st.selectbox("Grouping", list(choices), key="sector_tax_choice", width=260, label_visibility="collapsed",
                            format_func=lambda k: f"Grouping: {k}")
    col = choices.get(pick, "Industry")
    prices = history_prices if history_prices is not None else adj_close
    # Every figure and the footer end on the session the header shows (S193 E): a newer session the
    # ranking holds back while the vendor publishes it is left out here too.
    session = _fmt.session_of(adj_close if adj_close is not None else prices)
    if prices is not None and session is not None:
        prices = prices.loc[:session]
    from src.ui.views.market_questions_view import total_market
    tm = total_market()
    if prices is None or prices.empty:
        kit.page_empty(mw.NO_PRICES, mw.NO_PRICES_WHY, kicker="Sectors")
        return
    key = "|".join([known_fingerprint(prices), col, str(len(rank_df)), str(tm.index[-1]) if len(tm) else "-"])
    model = _model(key, rank_df, prices, col, tm)
    if model is None:
        kit.page_empty(*mw.no_groups(sp.MIN_STOCKS), kicker="Sectors")
        return
    emit(page_parts(model, rank_df, col, nse_sectors, universe))

    ld: sp.Leads = model["ld"]
    noun = noun_for(col)
    sh = (lambda n: SHORT_NAMES.get(n, n)) if col == "Industry" and nse_sectors else (lambda n: n)
    names = [r.name for r in ld.rows]
    top = next((r for r in ld.rows if r.group == "ahead on both"), ld.rows[0])
    # The heading names the group picked, so it is drawn into its place once the picker has a value (S203 se.stk.1).
    slot = st.empty()
    pick_name = st.selectbox(f"Pick a {noun}", names, index=names.index(top.name), key=f"sector_pick_{col}",
                             format_func=sh, width=260)
    members = rank_df[rank_df[col] == pick_name].sort_values("Rank")
    with slot.container():
        emit([f'<div class="dh-sec">{KICK.format(f"Stocks in a {noun}")}<h2 id="s-stocks" class="dh-h2">'
              f'{e(stocks_heading(sh(pick_name), len(members)))}</h2><p class="dh-note">The qualified rank is the place '
              'among the stocks that pass both filters, as on Actions and Portfolio.</p></div>'])
    from src.engine.exit_watch import qualified_ranks
    members = members.assign(**{"Qualified Rank": members["Symbol"].map(qualified_ranks(rank_df))})
    render_screener_table(members, adj_close, "Core")

    short_n = int((rank_df.get("Short History", pd.Series(dtype=str)) == "Yes").sum())
    st.html(f'<div class="dh"><p class="dh-foot">{_fmt.data_to(ld.when)}. {len(rank_df)} stocks ranked; '
            f'{gap_count(rank_df)} with a price gap, {short_n} with a short history.</p></div>')
    render_data_quality_footer(total_stocks=len(rank_df), gap_count=gap_count(rank_df), short_count=short_n)


__all__ = ["render_sector_view", "page_parts", "industry_board", "SHORT_NAMES", "NSE_ONLY"]
