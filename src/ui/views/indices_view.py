"""Indices (S170): what the market costs, which styles pay, how far each size falls.

Built from the mock-up the owner approved on 21 Nov 2026 (v4, docs/INDICES_REQUIREMENTS.md),
in the Dashboard's type system and chart kit. Figures: src/engine/indices_page.py, from
the app's copy of NSE's daily index files (src/loaders/nse_indices.read_compact).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from src.ui import formats as _fmt
from src.ui import missing_words as mw
from src.ui import page_kit as kit

from src.engine import earnings_review as er
from src.engine import indices_page as ip
from src.ui import indices_data
from src.ui.views.dashboard_home_view import HOME_CSS, Chart, Cols, emit, how, html_of, sg, tone

e = __import__("html").escape
KICK = '<p class="dh-kick">{}</p>'
# The ranges Indices' date charts open on (S193 H, docs/PAGE_DESIGN.md 4.1): both are an index's record, so all
# of it. The P/E keeps its 3Y and 5Y chips; the calendar years have none.
PE_RANGE = {"default": "all", "why": "record", "chips": ["3Y", "5Y", "all"]}
SIZE_RANGE = {"default": "all", "why": "record"}

IX_CSS = """
.ix-yr .dh-num{min-width:58px}
.dh-how-t td:first-child{white-space:nowrap}
.ix-every th[scope=row]{font-weight:500;white-space:normal;min-width:170px}
.ix-every .dh-sub{white-space:nowrap}
.ix-q td.up{color:var(--c-up)}.ix-q td.down{color:var(--c-down)}.ix-q th[scope=row]{min-width:0;white-space:nowrap}.ix-q thead th{white-space:normal}
.ix-fam{margin:8px 0 0!important;font-family:var(--font-serif)!important;font-weight:400!important;font-size:var(--fs-24)!important;line-height:1.3!important}
@media (max-width:640px){.ix-every th[scope=row],.ix-every thead th:first-child{white-space:nowrap;min-width:0;position:sticky;left:0;background:var(--c-white);z-index:1;box-shadow:1px 0 0 var(--c-rule_soft);padding-right:10px!important}.ix-every th,.ix-every td{padding:6px 4px 6px 0!important;font-size:var(--fs-12)}
.ix-hide-s{display:none}}
"""


def _d(day: pd.Timestamp) -> str:
    return f"{day:%-d %b}"


def _dy(day: pd.Timestamp) -> str:
    return f"{day:%-d %b %Y}"


def _short(name: str) -> str:
    return name.replace("Nifty India Corporate Group Index - ", "").replace("NIFTY", "Nifty")


def _ord(v: float) -> str:
    n = int(round(v))
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _kt(v: float | None) -> str:
    """Up/down class inside a chart frame (the kit's names, not the page's)."""
    return "" if v is None else "up" if v > 0 else "down" if v < 0 else ""


def _num(v: float | None, digits: int = 1, unit: str = "") -> str:
    return f'<td class="dh-num {tone(v) if v is not None else "dh-muted"}">{e(sg(v, digits, unit))}</td>'


# ── Sections ─────────────────────────────────────────────────────────────────


def head(vals: list[ip.Valuation], as_of: pd.Timestamp) -> list:
    by = {v.key: v for v in vals}
    big, small = by.get("nifty_50"), by.get("nifty_smallcap_250")
    since = f"{ip.PE_FROM:%b %Y}"
    if not (big and small):
        title = "NSE's index P/Es are not in yet."
    elif round(big.pct_now) != 50 and round(small.pct_now) != 50 and (big.pct_now < 50) != (small.pct_now < 50):
        # One under its median, one over (S203 ix.head.1 a, a'). Cheaper than its usual reads blue, dearer rust (S219 2).
        b_word, s_word = ("below", "above") if big.pct_now < 50 else ("above", "below")
        title = ("The Nifty 50's P/E is " + kit.verdict(f"{b_word} its median", big.pct_now < 50)
                 + f" since {since}; the Nifty Smallcap 250's is " + kit.verdict(f"{s_word} it", small.pct_now < 50) + ".")
    else:
        def at(v: ip.Valuation, first: bool) -> str:
            if round(v.pct_now) == 50:
                return "at its median" + (f" since {since}" if first else "")
            words = f"at the {_ord(v.pct_now)} percentile" if first else f"at the {_ord(v.pct_now)}"
            return kit.verdict(words, v.pct_now < 50) + (f" of its days since {since}" if first else "")
        title = f"The Nifty 50's P/E is {at(big, True)}; the Nifty Smallcap 250's {at(small, False)}."
    return [f'<div class="dh-sec">{KICK.format("Indices")}<h1 id="s-top" class="dh-h1">{title}</h1>'
            f'<p class="dh-lede">NSE\'s own indices, read at the {_d(as_of)} close: what each index costs against its '
            'recent past, which investing styles beat their parent index, and how deep a median year\'s max drawdown goes '
            'for each size. Price returns; dividends are not added.</p></div>']


# The chosen system's own index, when it has no row of its own among the six (S219-7, owner 23 Nov 2026).
SYSTEM_INDEX = {"1000": "nifty_1000"}
_WORDS = {6: "six", 7: "seven"}


def _young_row(y: ip.YoungValuation) -> tuple[dict, list, str]:
    """A chart row, a table row and the one sentence for an index whose P/E record is too short."""
    pb = "–" if y.pb_now is None else f"{y.pb_now:.2f}"
    dy = "–" if y.dy_now is None else f"{y.dy_now:.1f}%"
    row = {"name": y.name, "sub": f"P/E in NSE’s files from {_dy(y.first)}", "bar": None, "ago": None,
           "vals": [mw.DASH, mw.DASH, f"{y.pe_now:.2f}", mw.DASH], "cls": ["muted", "muted", "b", "muted"],
           "read": [[f"{y.pe_now:.2f}", "P/E now"], [pb, "P/B"], [dy, "dividend yield"]]}
    table = [y.name, f"{y.pe_now:.2f}", pb, dy, mw.DASH, mw.DASH, mw.DASH]
    note = (f" {mw.DASH} for the {y.name}: {mw.index_too_new()} for a percentile or a past reading (NSE’s daily files "
            f"carry its P/E from {_dy(y.first)}).")
    return row, table, note


def _share(v: float) -> str:
    """A whole share, half up (glossary 12): 79.5 -> "80"."""
    return _fmt.fixed(v, 0)


def _against_past(p: float) -> str:
    """Where today's P/E sits among past days, either way (S203 ix.val.1): `p` is the share of days it was lower."""
    if _fmt.half_up(p) == 50:
        return "at its median"
    return f"cheaper than on {_share(100 - p)}% of days" if p < 50 else f"dearer than on {_share(p)}% of days"


def valuation_headline(n50: ip.Valuation | None, s250: ip.Valuation | None) -> str:
    """The valuation heading, two sentences (S203 ix.val.1): direction from each index's own percentile, the date
    from the data."""
    since = (n50 or s250).since if (n50 or s250) else ip.PE_FROM
    if not (n50 and s250):
        return f"Each index's P/E against its own past since {_dy(since)}."
    small = _against_past(s250.pct_now).replace(" of days", "")
    return (f"At {_fmt.fixed(n50.pe_now, 1)} times earnings, the Nifty 50 is {_against_past(n50.pct_now)} since {_dy(since)}. "
            f"The Nifty Smallcap 250 is {small}.")


def section_valuation(f: ip.Frames, vals: list[ip.Valuation], m1: pd.Timestamp, m3: pd.Timestamp,
                      young: ip.YoungValuation | None = None) -> list:
    by = {v.key: v for v in vals}
    n50, s250 = by.get("nifty_50"), by.get("nifty_smallcap_250")
    h2 = valuation_headline(n50, s250)
    rows = [{"name": v.name, "sub": f"percentile since {_dy(v.since)}", "bar": round(v.pct_now, 1), "ago": round(v.pct_1m, 1),
             "vals": [f"{v.pe_3m:.2f}", f"{v.pe_1m:.2f}", f"{v.pe_now:.2f}", f"{v.pct_now:.0f}"],
             "cls": ["muted", "muted", "b", ""],
             "read": [[f"{v.pe_now:.2f}", "P/E now"], [_ord(v.pct_now), "percentile"],
                      [_ord(v.pct_1m), "a month ago"], [f"{v.pb_now:.2f}", "P/B"], [f"{v.dy_now:.1f}%", "dividend yield"]]}
            for v in vals]
    young_table, young_note = None, ""
    if young is not None and young.key not in by:
        yrow, young_table, young_note = _young_row(young)
        # After the broad market rows (Nifty 50, Nifty 500, Nifty Total Market), before the sizes.
        at = next((i + 1 for i, v in enumerate(vals) if v.key == "nifty_total_market"), len(rows))
        rows.insert(at, yrow)
    spec = {"label": "Index", "barHead": "Percentile of P/E since 2021", "head": [_d(m3), _d(m1), "Now", "Pctile"],
            "rows": rows, "lo": 0, "hi": 100, "step": 2, "lines": [25, 75], "rest": "Latest · the first row"}
    pe = ip.weekly(f.pe["nifty_500"]) if "nifty_500" in f.pe else pd.Series(dtype=float)
    reg = f.pe["nifty_500"].dropna()
    reg = reg[reg.index >= ip.PE_FROM]
    parts = [f'<div class="dh-sec">{KICK.format("Valuation")}<h2 id="s-valuation" class="dh-h2">{e(h2)}</h2>'
             f'<p class="dh-note">P/E is NSE\'s trailing price to earnings. The percentile counts days from {_dy(ip.PE_FROM)}, when '
             'NSE changed the earnings basis (the Nifty 50 went from 40.4 to 33.2 overnight with the price flat), so older '
             'readings are a different measure. Dashed lines mark the middle half; the triangle is a month ago. Each line is '
             '2 percentile points. Describing is not forecasting: this is not a forecast of returns. P/B gets no percentile: '
             f'its basis changed on 29 Sep 2023 and again on 23 Sep 2024.{e(young_note)}</p></div>',
             Chart("trows", spec, {"label": f"P/E of {_WORDS.get(len(rows), len(rows))} broad indices",
                                   "note": "Each line is 2 percentile points"})]
    if len(pe) and len(reg):
        dates = [f"{d:%Y-%m-%d}" for d in pe.index]
        old = [round(float(v), 2) if d < ip.PE_FROM else None for d, v in pe.items()]
        new = [round(float(v), 2) if d >= ip.PE_FROM else None for d, v in pe.items()]
        q25, q75 = float(reg.quantile(.25)), float(reg.quantile(.75))
        tm_pe = f.pe["nifty_total_market"].dropna() if "nifty_total_market" in f.pe else pd.Series(dtype=float)
        tm_from = f", {_dy(tm_pe.index[0])}" if len(tm_pe) else ""   # from the index file, as mk.size.2 (S203 ix.val.4)
        parts += [Chart("lines", {"dates": dates, "series": [
                        {"name": "Nifty 500 P/E, old basis", "color": "faint", "values": old, "width": 1.6},
                        {"name": "Nifty 500 P/E since 31 Mar 2021", "color": "ink", "values": new, "width": 2}],
                        "bands": [{"from": round(q25, 2), "to": round(q75, 2), "color": "up-soft"}],
                        "levels": [], "range": PE_RANGE},
                        {"label": "Nifty 500 P/E, weekly, since 2012"}),
                  how("The Nifty 500's trailing P/E each week since 2012. Grey is the old earnings basis, ink the basis "
                      "since 31 Mar 2021; the shaded band is the middle half of days since then "
                      f"({q25:.1f} to {q75:.1f}). The Nifty 500, not Nifty Total Market, because NSE's P/E for Nifty "
                      f"Total Market starts at its launch{tm_from}, and this line shows the years before the "
                      "2021 change of basis.",
                      "A line above the band is dearer than three days in four since 2021; below it, cheaper. The two "
                      "colours are two definitions: do not read the 2021 drop as a fall in price.",
                      ["Index", "P/E", "P/B", "Div yield", "Percentile now", "A month ago", "3 months ago"],
                      [[v.name, f"{v.pe_now:.2f}", f"{v.pb_now:.2f}", f"{v.dy_now:.1f}%", f"{v.pct_now:.0f}",
                        f"{v.pct_1m:.0f}", f"{v.pct_3m:.0f}"] for v in vals] + ([young_table] if young_table else []), source="NSE Indices' published P/E")]
    return parts


PROFIT_WORDS = {"pat": "profit after tax as reported",
                "pat_xoi": "profit after tax without other income (taken out after tax for companies other than banks "
                           "and lenders, whose other income is part of the business)"}


def earnings_headline(lt: er.Latest, scope: str = "all") -> str:
    """The earnings heading (S171): the Nifty 500's profit growth in the latest complete quarter, all companies and
    the median company."""
    v = lt.values.get("Nifty 500", {})
    agg, med = v.get("pat_agg_yoy"), v.get("pat_median_yoy")
    q = er.quarter_label(lt.quarter)
    if agg is None:
        return f"Profit growth in {q}."
    verb = "rose" if agg >= 0 else "fell"
    tail = ("" if med is None else
            f"; the median company's profit {'rose' if med >= 0 else 'fell'} {_pc(abs(med))}")
    who = "the Nifty 500's profit" + (" without financials" if scope == "ex_financials" else "")
    return f"In {q} {who} {verb} {_pc(abs(agg))} from a year earlier{tail}."


def _pc(v: float) -> str:
    """One decimal, rounded half up as every table cell is (30.25 reads 30.3% in the heading and the table alike)."""
    return f"{_fmt.half_up(v, 1)}%"


def _source_note(q: str, as_of) -> str:
    return (f"Our calculation from companies' reported results: each company's quarterly results, added up over the "
            f"companies in the index at the quarter end; last updated {_dy(as_of)}. Profit is "
            f"{PROFIT_WORDS[er.PROFIT]}. Tata Motors, demerged on 1 Oct 2025, is left out of the quarters it would "
            "distort (Q2 and Q3 FY26, Q2 FY27), and Rajesh Exports from every index: its reported revenue, about a third "
            "of the Nifty Microcap 250's, would alone set that index's growth.")


def section_partial(pt: er.Latest | None, every: str = "all companies") -> str:
    """The quarter still coming in (owner, 25 Nov 2026: "Show partial one"): shown from one in ten Nifty 500 companies
    reported until nine in ten, when it joins the tables below."""
    if pt is None:
        return ""
    q = er.quarter_label(pt.quarter)
    rows = ""
    for name in er.LATEST_INDICES:
        v, got = pt.values.get(name, {}), pt.reported.get(name)
        if got and got[0] < 0.1 * got[1]:
            v = {}                      # fewer than one in ten of the index: too few to say anything yet
        rows += (f'<tr><th scope="row">{e(_short(name))}</th>'
                 f'<td class="dh-num">{e(sg(v.get("pat_agg_yoy"), 1, "%"))}</td>'
                 f'<td class="dh-num">{e(sg(v.get("sales_agg_yoy"), 1, "%"))}</td>'
                 f'<td class="dh-num">{e(f"{got[0]:,} of {got[1]:,}" if got else "–")}</td></tr>')
    n500 = pt.reported.get("Nifty 500")
    lede = f"{q} so far" + (f": {n500[0]} of {n500[1]} Nifty 500 companies have reported." if n500 else ".")
    return (f'<h3 class="dh-h3">{e(lede)}</h3><div class="dh-scroll"><table class="dh-tab dh-tab-s ix-every"><thead><tr>'
            f'<th scope="col">Index</th><th scope="col" class="dh-num">Profit, {every}</th>'
            f'<th scope="col" class="dh-num">Revenue, {every}</th><th scope="col" class="dh-num">Companies reported</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div><p class="dh-note">Each company that has reported, against its '
            f"own quarter a year earlier. The larger companies tend to report first, so these figures move as the rest "
            f"report; an index shows – until one in ten of its companies have. {q} joins the tables below once nine in ten "
            f"Nifty 500 companies have reported.</p>")


# Without financials (S231; decided by benchmark, owner to confirm): NSE's own Corporate Earnings Review reports
# figures ex-Financials; a bank's "revenue" is interest earned and its profit moves with provisions, not sales.
EX_FIN_NOTE = ("Without financials leaves out the companies in NSE's macro sector Financial Services (banks, NBFCs, "
               "insurers, capital-market companies), by NSE's classification; companies reported then counts the rest.")


def section_earnings(lt: er.Latest | None, pt: er.Latest | None = None, scope: str = "all") -> list:
    """Profit and revenue growth beside the P/E (S171): our calculation from Screener's company results (owner,
    25 Nov 2026: "We will use Screener data only")."""
    if lt is None:
        return []
    every = "all but financials" if scope == "ex_financials" else "all companies"
    cols = [("pat_agg_yoy", f"Profit, {every}"), ("pat_median_yoy", "Profit, median company"),
            ("sales_agg_yoy", f"Revenue, {every}"), ("sales_median_yoy", "Revenue, median company")]
    body = ""
    for name in er.LATEST_INDICES:
        v = lt.values.get(name, {})
        cells = "".join(f'<td class="dh-num">{e(sg(v.get(k), 1, "%"))}</td>' for k, _ in cols)
        got = lt.reported.get(name)
        cells += f'<td class="dh-num">{e(f"{got[0]:,} of {got[1]:,}" if got else "–")}</td>'
        body += f'<tr><th scope="row">{e(_short(name))}</th>{cells}</tr>'
    q = er.quarter_label(lt.quarter)
    note = (f"Growth in {q} over the same quarter a year earlier: all companies added together, and the median "
            f"company; companies reported counts those with both quarters, against the index's size. A quarter shows "
            f"once nine in ten Nifty 500 companies have reported it. The Nifty 1000 is here only: its members are today's, "
            f"which are right for the latest quarter but not for earlier ones. "
            + (EX_FIN_NOTE + " " if scope == "ex_financials" else "") + _source_note(q, lt.published))
    return [f'<div class="dh-sec dh-sec-cont">{KICK.format("Earnings")}<h2 id="s-earnings" class="dh-h2">'
            f'{e(earnings_headline(lt, scope))}</h2><p class="dh-note">{e(note)}</p>'
            '<div class="dh-scroll"><table class="dh-tab dh-tab-s ix-every"><thead><tr><th scope="col">Index</th>'
            + "".join(f'<th scope="col" class="dh-num">{e(h)}</th>' for _, h in cols)
            + '<th scope="col" class="dh-num">Companies reported</th>'
            + f'</tr></thead><tbody>{body}</tbody></table></div>' + section_partial(pt, every) + '</div>'] + earnings_quarters(scope) + earnings_history(scope)


QUARTER_HEADS = {i: i for i in er.OUR_INDICES}       # the glossary's full names (G3), headings may wrap


def earnings_quarters(scope: str = "all") -> list:
    """Each index's growth every quarter, newest first (owner, 25 Nov 2026: "a good table to see 8-10 quarter growth for
    Indices"): profit, then revenue, all companies added together, against the same quarter a year earlier."""
    out = []
    for measure, title in (("pat_agg_yoy", "Profit"), ("sales_agg_yoy", "Revenue")):
        hist = {i: er.ours_history(i, measure, scope=scope) for i in er.OUR_INDICES}
        idx = sorted({d for h in hist.values() for d in h.index}, reverse=True)
        if len(idx) < 2:
            return []
        rows = ""
        pt = er.partial(scope=scope)
        if pt is not None:              # the quarter coming in, top row (owner, 25 Nov 2026: "show partial also")
            got = pt.reported.get("Nifty 500")
            cells = ""
            for i in er.OUR_INDICES:
                n, v = pt.reported.get(i), pt.values.get(i, {}).get(measure)
                v = None if n and n[0] < 0.1 * n[1] else v
                cls = "" if v is None or _fmt.half_up(v, 1) == 0 else ("up" if v > 0 else "down")
                cells += f'<td class="dh-num {cls}">{e(sg(v, 1, "%"))}</td>'
            sub = f'<span class="dh-sub">{got[0]} of {got[1]} reported</span>' if got else ""
            rows += f'<tr><th scope="row">{e(er.quarter_label(pt.quarter))} so far{sub}</th>{cells}</tr>'
        for d, q in zip(idx, _quarters(idx)):
            cells = "".join(
                f'<td class="dh-num {"" if (v := hist[i].get(d)) is None or _fmt.half_up(v, 1) == 0 else ("up" if v > 0 else "down")}">'
                f'{e(sg(hist[i].get(d), 1, "%"))}</td>' for i in er.OUR_INDICES)
            rows += f'<tr><th scope="row">{e(er.quarter_label(q))}</th>{cells}</tr>'
        out.append(f'<div class="dh-sec dh-sec-cont"><h3 class="dh-h3">{title} growth, each quarter</h3>'
                   '<div class="dh-scroll"><table class="dh-tab dh-tab-s ix-every ix-q"><thead><tr><th scope="col">Quarter</th>'
                   + "".join(f'<th scope="col" class="dh-num">{e(QUARTER_HEADS[i])}</th>' for i in er.OUR_INDICES)
                   + f'</tr></thead><tbody>{rows}</tbody></table></div></div>')
    if out:
        who = "All the index's companies but financials" if scope == "ex_financials" else "All the index's companies"
        out[-1] = out[-1].replace("</table></div></div>", f'</table></div><p class="dh-note">{who} '
                                  "added together, each quarter against the same quarter a year earlier; the first row is "
                                  "the latest quarter. A quarter still coming in reads \"so far\", with how many Nifty 500 "
                                  "companies have reported; an index shows – until one in ten of its companies have. "
                                  "Profit as in the table above.</p></div>")
    return out


def earnings_history(scope: str = "all") -> list:
    """Profit growth each quarter, Nifty 50 and Nifty 500, from our calculation (S171)."""
    h = lambda i, m: er.ours_history(i, m, scope=scope)    # noqa: E731
    n50, n500 = h("Nifty 50", "pat_agg_yoy"), h("Nifty 500", "pat_agg_yoy")
    s50, s500 = h("Nifty 50", "sales_agg_yoy"), h("Nifty 500", "sales_agg_yoy")
    idx = sorted(set(n50.index) | set(n500.index))
    if len(idx) < 4:
        return []
    vals = lambda x: [None if d not in x.index else float(_fmt.half_up(float(x[d]), 1)) for d in idx]   # noqa: E731
    quarter = {d: er.quarter_label(q) for q in _quarters(idx) for d in [er.quarter_end(q)]}
    first, last = quarter[idx[0]], quarter[idx[-1]]
    return [Chart("lines", {"dates": [f"{d:%Y-%m-%d}" for d in idx], "yfmt": "growth",
                            "series": [{"name": "Nifty 50", "color": "ink", "values": vals(n50), "width": 2},
                                       {"name": "Nifty 500", "color": "s-n500", "values": vals(n500), "width": 2}],
                            "levels": [{"v": 0, "label": "", "color": "muted"}], "range": SIZE_RANGE},
                  {"label": f"Profit growth from a year earlier, each quarter, {first} to {last}",
                   "note": "Each quarter, dated at the quarter end; a quarter shows once nine in ten Nifty 500 "
                           "companies have reported it"}),
            how(f"All the index's companies added together, against the same quarter a year earlier, each quarter from "
                f"{first} to {last}, dated at the quarter end. Profit is {PROFIT_WORDS[er.PROFIT]}. Our calculation "
                "from companies' reported results; the history starts in " + first + " and grows a quarter at a time. Tata Motors is left out of Q2 and Q3 FY26 "
                "and Q2 FY27, the quarters its demerger of 1 Oct 2025 would distort.",
                "Above the zero line, profits grew on a year earlier; below it, they fell. Growth is over the same quarter "
                "a year before, so a weak quarter a year ago lifts this one.",
                ["Quarter", "Nifty 50 profit", "Nifty 500 profit", "Nifty 50 revenue", "Nifty 500 revenue"],
                [[quarter[d]] + [sg(x.get(d), 1, "%") for x in (n50, n500, s50, s500)] for d in reversed(idx)])]


def _quarters(idx) -> list[str]:
    """The quarter labels ("Q1FY27") for quarter-end dates."""
    out = []
    for d in idx:
        n = {6: 1, 9: 2, 12: 3, 3: 4}[d.month]
        fy = d.year + (0 if n == 4 else 1)
        out.append(f"Q{n}FY{fy % 100:02d}")
    return out


def _and(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def styles_headline(sts: list[ip.Style]) -> str:
    """The styles heading (S203 ix.sty.1): who leads its parent over 12 months, and who trails it by more than
    5 points. Three or more leaders are counted, not named."""
    lead = sorted((s for s in sts if s.lead_now is not None), key=lambda s: -s.lead_now)
    if not lead:
        return "Each style against the index it picks from, over the last 12 months."
    ahead = [s.style.lower() for s in lead if s.lead_now > 0]
    behind = [s for s in lead if s.lead_now < -5]
    if not ahead:
        worst = lead[-1]
        return (f"No style leads its parent over 12 months; {e(worst.style.lower())} trails most, by "
                f"{_fmt.fixed(abs(worst.lead_now), 1)} points.")
    if not behind:
        return (f"Over 12 months, {e(ahead[0])} leads its parent by the most, {_fmt.fixed(lead[0].lead_now, 1)} points; "
                "no style trails by more than 5.")
    if len(ahead) == 1:
        who, verb = ahead[0], "leads its parent"
    else:
        who, verb = (_and(ahead) if len(ahead) == 2 else f"{len(ahead)} styles"), "lead their parents"
    lo, hi = (_fmt.fixed(x, 1) for x in (min(-s.lead_now for s in behind), max(-s.lead_now for s in behind)))
    span = lo if lo == hi else f"{lo}–{hi}"
    trail = "trails" if len(behind) == 1 else "trail"
    return (f'Over 12 months, {e(who)} <span class="dh-up">{verb}</span>; {e(_and([s.style.lower() for s in behind]))} '
            f'<span class="dh-down">{trail} by more than 5 points: {span}</span>.')


def section_styles(sts: list[ip.Style], m1: pd.Timestamp, m3: pd.Timestamp) -> list:
    h2 = styles_headline(sts)
    rows =[{"name": s.style, "sub": f"{s.name} against {s.parent_name} · live since {_dy(s.live)}",
             "bar": None if s.lead_now is None else round(s.lead_now, 2), "ago": None if s.lead_1m is None else round(s.lead_1m, 2),
             "vals": [sg(s.lead_3m), sg(s.lead_1m), sg(s.lead_now), sg(s.dy_gap)],
             "cls": [_kt(s.lead_3m), _kt(s.lead_1m), _kt(s.lead_now) + " b", "muted"],
             "read": [[sg(s.lead_now) + " pts", "12M lead now", _kt(s.lead_now)], [sg(s.lead_1m) + " pts", "a month ago"],
                      [sg(s.dy_gap) + " pts", "dividend-yield gap, 12M"]]}
            for s in sts]
    spec = {"label": "Style", "barHead": "Lead over parent, 12 months, pts", "head": [_d(m3), _d(m1), "Now", "Yield gap"],
            "rows": rows, "lo": -15, "hi": 15, "step": 0.5, "rest": "Latest · the first row"}
    return [f'<div class="dh-sec">{KICK.format("Styles")}<h2 id="s-styles" class="dh-h2">{h2}</h2>'
            '<p class="dh-note">Each style index against the index it picks from: its price return over 12 months minus the '
            "parent's, read 3 months ago, a month ago and now. Only live history is used, from the day NSE first published "
            'the index. Each line is 0.5 points; a lead fills right of the dark zero line, a lag left. The yield gap is the '
            "style's dividend yield minus the parent's: a price lead understates a style by about that much every 12 months. "
            f"{_fmt.PTS_NOTE}</p></div>",
            Chart("trows", spec, {"label": "Six styles against their parents", "note": "Each line is 0.5 points"})]


def lag_headline(mom: ip.Style) -> str:
    """The lag heading (S203 ix.lag.1). S173 IX-2: the figure is the fall of a ratio (the relative line below its
    peak), not a gap of two returns."""
    now = abs(float(mom.from_peak.iloc[-1]))
    if _fmt.reads_zero(now):
        return f"{e(mom.style)}’s line against the {e(mom.parent_name)} is at its peak."
    deepest = now >= abs(mom.worst) - 0.05
    return (f'{e(mom.style)}’s line against the {e(mom.parent_name)} is <span class="dh-down">{_fmt.fixed(now, 1)}% '
            f'below its {mom.worst_peak:%B %Y} peak</span>' + (f", its deepest since launch in {mom.live.year}." if deepest else "."))


def lag_extra(sts: list[ip.Style], mom: ip.Style) -> str:
    """The note's sentences after the method (S203 ix.lag.2), each with a leading space: the other styles at their
    deepest now, one sentence each, then the deepest fall that recovered, with its months."""
    others = [s for s in sts if s is not mom and abs(s.from_peak.iloc[-1]) >= abs(s.worst) - 0.05 and s.worst < -5]
    extra = "".join(f" {s.style} is at its deepest too, {_fmt.fixed(abs(s.from_peak.iloc[-1]), 1)}% below its peak."
                    for s in others)
    rec = [s for s in sts if s.recovered is not None and s.worst <= -20]
    if rec:
        r = min(rec, key=lambda s: s.worst)
        # Months, not a "2018–20" span that gives none (dash.mom.6's form).
        extra += (f" {r.style} fell {_fmt.fixed(abs(r.worst), 1)}% against the {r.parent_name}, from {r.worst_peak:%b %Y} "
                  f"to {r.worst_low:%b %Y}, and was back by {r.recovered:%b %Y}.")
    return extra


def section_lag(sts: list[ip.Style]) -> list:
    if not sts:
        return []
    mom = next((s for s in sts if s.style == "Momentum"), sts[0])
    h2, extra = lag_headline(mom), lag_extra(sts, mom)
    styles = []
    for s in sts:
        rel, dd = ip.weekly(s.rel), ip.weekly(s.from_peak)
        styles.append({"style": s.style, "label": f"{s.name} ÷ {s.parent_name}",
                       "dates": [f"{d:%Y-%m-%d}" for d in rel.index],
                       "rel": [round(float(v), 2) for v in rel], "dd": [round(float(v), 2) for v in dd.reindex(rel.index)]})
    body = "".join(
        f'<tr><th scope="row">{e(s.style)}</th>{_num(s.from_peak.iloc[-1], 1, "%")}'
        f'<td class="dh-num">{e(sg(s.worst, 1, "%"))}</td>'
        f'<td class="dh-num dh-muted">{s.worst_peak:%-d %b %Y} → {s.worst_low:%-d %b %Y}</td>'
        f'<td class="dh-num dh-muted">{e(_dy(s.recovered)) if s.recovered is not None else "not yet"}</td></tr>' for s in sts)
    table = ('<div class="dh-scroll"><table class="dh-tab dh-tab-s"><thead><tr><th scope="col">Style</th>'
             '<th scope="col" class="dh-num">Now</th><th scope="col" class="dh-num">Max DD, relative</th>'
             '<th scope="col" class="dh-num">Worst, peak → low</th><th scope="col" class="dh-num">Recovered</th></tr></thead>'
             f'<tbody>{body}</tbody></table></div>')
    return [f'<div class="dh-sec">{KICK.format("How long a style can lag")}<h2 id="s-lag" class="dh-h2">{h2}</h2>'
            '<p class="dh-note">The relative line divides the style index by its parent, 100 at launch: rising means the '
            f'style is ahead. Below it, how far the line sits under its own best.{e(extra)}</p></div>',
            Chart("rel", {"styles": styles}, {"label": "A style index against its parent"}),
            f'<div class="dh-sec dh-sec-cont">{table}</div>']


def years_headline(led: dict[str, tuple[int, int]]) -> str:
    """The calendar-years heading (S203 ix.yr.1) from {style: (whole years led, whole years)}; a tie names both."""
    always = [s for s, (a, b) in led.items() if a == b and b > 1]
    if always:
        return f"{always[0]} led its parent in every whole year since launch."
    key = lambda ab: (ab[0] / ab[1] if ab[1] else 0, ab[1])  # noqa: E731
    top = max(key(v) for v in led.values())
    best = [s for s, v in led.items() if key(v) == top]
    a, b = led[best[0]]
    return (f"No style led its parent every whole year; {_and([s.lower() for s in best])} came closest, {a} of {b}"
            + (" each." if len(best) > 1 else "."))


def section_years(sts: list[ip.Style], as_of: pd.Timestamp) -> list:
    if not sts:
        return []
    # Whole years only: the year in progress is in the table, not in the count (S193 B: "7 years of 9" counted 2026).
    def whole(s):
        ys = {y: v for y, v in s.years.items() if y < as_of.year or (as_of.month == 12 and as_of.day >= 31)}
        return sum(v > 0 for v in ys.values()), len(ys)
    led = {s.style: whole(s) for s in sts}
    h2 = years_headline(led)
    years = sorted({y for s in sts for y in s.years}, reverse=True)
    head = "".join(f'<th scope="col" class="dh-num">{e(s.style)}</th>' for s in sts)
    body = ""
    for y in years:
        lab = f'{y}<span class="dh-sub">year to date</span>' if y == as_of.year else str(y)
        body += f'<tr><th scope="row" class="dh-num">{lab}</th>' + "".join(_num(s.years.get(y)) for s in sts) + "</tr>"
    foot = '<tr><th scope="row" class="dh-num">Years led</th>' + "".join(f'<td class="dh-num">{a} of {b}</td>' for a, b in led.values()) + "</tr>"
    return [f'<div class="dh-sec">{KICK.format("Calendar years")}<h2 id="s-years" class="dh-h2">{e(h2)}</h2>'
            '<p class="dh-note">Lead over the parent in each calendar year, in points of price return. Each style starts '
            'with its first full year after launch.</p>'
            f'<div class="dh-scroll"><table class="dh-tab dh-tab-s ix-yr"><thead><tr><th scope="col" class="dh-num">Year</th>{head}</tr></thead>'
            f'<tbody>{body}</tbody><tfoot>{foot}</tfoot></table></div></div>']


def size_headline(sizes: list[ip.SizeYears], from_year: int = ip.SIZE_FROM_YEAR) -> str:
    """The size heading (S203 ix.size.1): the small index's median max drawdown against the large one's; without a
    large figure to divide by, the size with the deepest."""
    by = {z.size: z for z in sizes}
    large, small = by.get("Large"), by.get("Small")
    if large and small and large.median_fall < 0 and np.isfinite(small.median_fall):
        ratio = small.median_fall / large.median_fall
        word = "twice" if 1.8 <= ratio <= 2.2 else f"{_fmt.fixed(ratio, 1)} times"
        return (f"In a median year since {from_year}, the {small.name}'s max drawdown was {_fmt.fixed(abs(small.median_fall), 1)}%, "
                f"{word} the {large.name}'s {_fmt.fixed(abs(large.median_fall), 1)}%.")
    known = [z for z in sizes if np.isfinite(z.median_fall)]
    if not known:
        return "How far each size falls within a calendar year."
    deep = min(known, key=lambda z: z.median_fall)
    return (f"In a median year since {from_year}, the {deep.name} had the deepest max drawdown, "
            f"{_fmt.fixed(abs(deep.median_fall), 1)}%.")


def section_size(sizes: list[ip.SizeYears], as_of: pd.Timestamp) -> list:
    if not sizes:
        return []
    by = {z.size: z for z in sizes}
    h2 = size_headline(sizes)
    allv = [x for z in sizes for v in z.years.values() for x in v]
    lo, hi = (min(allv) // 20) * 20, -((-max(allv)) // 20) * 20
    meds = ", ".join(f"{_fmt.size(z.size)} {sg(z.median_fall, 1, '%')}" for z in sizes)
    # The Micro Cap index's first whole year, from its own rows (S203 ix.size.2), when it starts later than the rest.
    micro_years = sorted(y for y in by["Micro"].years if y < as_of.year) if "Micro" in by else []
    micro = (f" ({_fmt.size('Micro')} from {micro_years[0]})"
             if micro_years and micro_years[0] > ip.SIZE_FROM_YEAR else "")
    charts = []
    for z in sizes:
        ys = sorted(z.years)
        spec = {"values": [round(z.years[y][0], 1) for y in ys], "dots": [round(z.years[y][1], 1) for y in ys],
                "labels": ["'" + str(y)[2:] for y in ys], "full": [str(y) + (" (year to date)" if y == as_of.year else "") for y in ys],
                "dates": [f"{min(as_of, pd.Timestamp(y, 12, 31)):%Y-%m-%d}" for y in ys],
                "unit": "Year's return", "dotName": "max drawdown within the year", "yrange": [lo, hi], "height": 200, "xn": 10}
        charts.append([f'<p class="dh-h3" style="margin:12px 0 0">{e(_fmt.size(z.size))} <span class="dh-muted" style="font-weight:400">'
                       f'{e(z.name)} · median max drawdown {e(sg(z.median_fall, 1, "%"))}</span></p>',
                       Chart("bars", {**spec, "range": SIZE_RANGE}, {"label": f"{z.name} by calendar year"})])
    grid = []
    for i in range(0, len(charts), 2):
        pair = charts[i:i + 2]
        grid.append(Cols(pair[0], pair[1] if len(pair) > 1 else [], (1, 1)))
    table = how("Each bar is a calendar year's price return; the dot is the max drawdown within that year. "
                f"One scale for all four, from {ip.SIZE_FROM_YEAR} (the Nifty Midcap 150 and Nifty Smallcap 250 start in NSE's file in "
                "Apr 2016; the Nifty Microcap 250 in May 2021).",
                "A tall bar with a deep dot is a year that rose in the end after a hard fall on the way: the fall is "
                "what a holder sat through.",
                ["Year"] + [_fmt.size(z.size) for z in sizes],
                [[str(y)] + [("–" if y not in z.years else f"{sg(z.years[y][0], 1, '%')} · {sg(z.years[y][1], 1, '%')}")
                             for z in sizes] for y in sorted({y for z in sizes for y in z.years}, reverse=True)], source="NSE Indices' daily closes")
    return ([f'<div class="dh-sec">{KICK.format("Size, year by year")}<h2 id="s-size" class="dh-h2">{e(h2)}</h2>'
             f'<p class="dh-note">The bar is the calendar year\'s return; the dot is the max drawdown within it. '
             f'{as_of.year} is year to date. Median of whole years since {ip.SIZE_FROM_YEAR}: {e(meds)}'
             f'{micro}.</p></div>'] + grid + [table])


GROUP_NOTE = {
    "Broad market": "Size and breadth: Nifty Total Market, the large, mid and small company indices.",
    "Theme": "Ideas that cut across sectors: defence, manufacturing, PSUs, business groups, new listings.",
    "Strategy": "Rules-based selections and weightings: momentum, quality, value, low volatility, equal weight, dividends.",
}


def every_headline(f: ip.Frames, rows: dict[str, list[ip.IndexRow]], as_of: pd.Timestamp) -> str:
    """The every-index heading (S203 ix.ev.1): Nifty Total Market over 12 months, or that its close is late; then
    the themes' leader and laggard, from the first and last rows of the Theme table."""
    out = []
    tm_close = f.close["nifty_total_market"].dropna() if "nifty_total_market" in f.close else pd.Series(dtype=float)
    if len(tm_close) and tm_close.index[-1] != as_of:
        out.append(f"Nifty Total Market’s {_d(as_of)} close is not in yet.")
    elif len(tm_close):
        tm = ip.ret(tm_close, 12, as_of)
        if tm is not None:
            out.append(f"Over 12 months, Nifty Total Market is {_fmt.moved(tm)}.")
    themes = [r for r in rows.get("Theme", []) if r.returns[12] is not None]
    if len(themes) == 1:
        out.append(f"{_short(themes[0].name)} is the only theme with 12 months.")
    elif themes:
        out.append(f"Among themes, {_short(themes[0].name)} leads, {_fmt.moved(themes[0].returns[12])}, and "
                   f"{_short(themes[-1].name)} trails, {_fmt.moved(themes[-1].returns[12])}.")
    if not out:
        return f"NSE's {sum(len(v) for v in rows.values())} broad, theme and strategy indices over 12 months."
    return " ".join(out)


def family_headline(g: str, xs: list[ip.IndexRow]) -> str:
    """A family's h3 (S203 ix.ev.3): how many are up over 12 months; the leader and laggard are the table's first and
    last rows, so their figures are not repeated."""
    full = [x for x in xs if x.returns[12] is not None]
    if not full:
        return g
    k, n = sum(x.returns[12] > 0 for x in full), len(full)
    if n == 1:
        return f"{g}: {_short(full[0].name)} is {_fmt.moved(full[0].returns[12])} over 12 months."
    count = "none is up" if k == 0 else "all are up" if k == n else f"{k} of {n} {'is' if k == 1 else 'are'} up"
    return f"{g}: {count} over 12 months; {_short(full[0].name)} leads and {_short(full[-1].name)} trails."


def section_every(f: ip.Frames, rows: dict[str, list[ip.IndexRow]], as_of: pd.Timestamp) -> list:
    n = sum(len(v) for v in rows.values())
    late = ip.late_names(x for v in rows.values() for x in v)
    late_txt = f" {_fmt.closes_not_in(late, as_of)} Their figures read –." if late else ""
    h2 = every_headline(f, rows, as_of)
    parts = [f'<div class="dh-sec">{KICK.format("Every index")}<h2 id="s-every" class="dh-h2">{e(h2)}</h2>'
             f'<p class="dh-note">NSE\'s {n} broad, theme and strategy indices, in three families, each sorted by its '
             f'price return over 12 months. Each window ends on {_dy(as_of)} and starts on the last session on or before the same '
             'date 1, 3, 6, 9 and 12 months back. Indices younger than 12 months are listed last, with their launch date in the 12M column. '
             "NSE's sector indices are on Sectors, beside the sectors they match. Bond, rate, leveraged and inverse "
             f'indices, India VIX and the dollar Nifty are left out.{e(late_txt)}</p></div>']
    for g in ip.PAGE_FAMILIES:
        xs = rows.get(g, [])
        if not xs:
            continue
        lead = family_headline(g, xs)
        body = ""
        dash = {}   # one footnote per column for its "–" (S193 E, R1)
        for x in xs:
            for m in ip.WINDOWS[:-1]:
                if x.returns[m] is None:
                    dash[f"{m}M"] = mw.not_published() if x.late is not None else mw.index_too_new()
            if x.from_high is None:
                dash["From 12M high"] = (mw.not_published() if x.late is not None else mw.index_too_new())
            if x.pe is None:
                dash["P/E"] = mw.no_pe()
            hi = "–" if x.from_high is None else ("at high" if abs(x.from_high) < 0.05 else sg(x.from_high, 1, "%"))
            cells = "".join(_num(x.returns[m], 1, "%") for m in ip.WINDOWS[:-1])
            cells += (_num(x.returns[12], 1, "%") if x.returns[12] is not None or x.late is not None
                      else f'<td class="dh-num dh-muted">{e(mw.since(x.live))}</td>')
            body += (f'<tr><th scope="row">{e(_short(x.name))}</th>' + cells
                     + f'<td class="dh-num dh-muted ix-hide-s">{e(hi)}</td>'
                     f'<td class="dh-num dh-muted ix-hide-s">{"–" if x.pe is None else f"{x.pe:.1f}"}</td></tr>')
        parts.append(f'<div class="dh-sec dh-sec-cont"><h3 class="ix-fam">{e(lead)}</h3><p class="dh-note">{e(GROUP_NOTE[g])}</p>'
                     '<div class="dh-scroll"><table class="dh-tab dh-tab-s ix-every"><thead><tr><th scope="col">Index</th>'
                     + "".join(f'<th scope="col" class="dh-num">{m}M</th>' for m in ip.WINDOWS)
                     + '<th scope="col" class="dh-num ix-hide-s">From 12M high</th><th scope="col" class="dh-num ix-hide-s">P/E</th>'
                     f'</tr></thead><tbody>{body}</tbody></table></div>'
                     + (f'<p class="dh-note">{e(mw.column_notes(dash))}</p>' if dash else "") + '</div>')
    return parts


def page_parts(f: ip.Frames, system: str | None = None, scope: str = "all", part: str = "all") -> list:
    """The page, or one part of it: "pre" (header and valuation), "post" (earnings onwards), for the earnings switch
    between the two (S231)."""
    as_of = f.as_of
    n50 = f.close["nifty_50"].dropna()
    m1 = ip.on_or_before(n50, ip.months_back(as_of, 1))
    m3 = ip.on_or_before(n50, ip.months_back(as_of, 3))
    vals, sts = ip.valuation(f), ip.styles(f)
    every = ip.every_index(f)
    n = sum(len(v) for v in every.values())
    young = ip.young_valuation(f, SYSTEM_INDEX[system]) if system in SYSTEM_INDEX else None
    pre = head(vals, as_of) + section_valuation(f, vals, m1, m3, young) if part != "post" else []
    if part == "pre":
        return pre
    return (pre + section_earnings(er.ours(scope=scope), er.partial(scope=scope), scope) + section_styles(sts, m1, m3)
            + section_lag(sts) + section_years(sts, as_of) + section_size(ip.size_years(f), as_of)
            + section_every(f, every, as_of)
            + [f'<p class="dh-foot">{_fmt.data_to_html(as_of, "NSE")} · {n} broad, theme and strategy indices</p>'])


def render_indices_view() -> None:
    st.html(f"<style>{HOME_CSS}{IX_CSS}</style>")
    f = indices_data.frames()
    if f is None:
        kit.page_empty(mw.NO_INDEX_DATA, mw.NO_INDEX_DATA_WHY, kicker="Indices")   # S203 ix.empty.1, R4
        return
    from src.ui import system_param
    system = system_param.current()
    emit(page_parts(f, system, part="pre"))
    scope = "all"
    if er.ours(scope="ex_financials") is not None:
        with st.container(horizontal=True, horizontal_alignment="right", key="ix_earn_scope_row"):
            scope = st.segmented_control("Companies", list(er.SCOPES), format_func=er.SCOPES.get, default="all",
                                         key="ix_earn_scope", label_visibility="collapsed") or "all"
    emit(page_parts(f, system, scope, part="post"))


__all__ = ["render_indices_view", "page_parts", "html_of"]
