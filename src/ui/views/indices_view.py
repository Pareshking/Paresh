"""Indices (S170): what the market costs, which styles pay, how far each size falls.

Built from the mock-up the owner approved on 21 Nov 2026 (v4, docs/INDICES_REQUIREMENTS.md),
in the Dashboard's type system and chart kit. Figures: src/engine/indices_page.py, from
the app's copy of NSE's daily index files (src/loaders/nse_indices.read_compact).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.ui import formats as _fmt
from src.ui import missing_words as mw
from src.ui import page_kit as kit

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
    if big and small and big.pct_now < 50 <= small.pct_now:
        title = ('The Nifty 50 trades <span class="dh-up">below its usual P/E</span>; '
                 'the Nifty Smallcap 250 <span class="dh-down">above it</span>.')
    elif big and small:
        # Cheaper than its usual reads blue, dearer rust (S219 2).
        title = ("The Nifty 50 sits " + kit.verdict(f"at the {_ord(big.pct_now)} percentile", big.pct_now < 50)
                 + " of its P/E since 2021; the Nifty Smallcap 250 "
                 + kit.verdict(f"at the {_ord(small.pct_now)}", small.pct_now < 50) + ".")
    else:
        title = "NSE's indices: what each costs, and which styles pay."
    return [f'<div class="dh-sec">{KICK.format("Indices")}<h1 id="s-top" class="dh-h1">{title}</h1>'
            f'<p class="dh-lede">NSE\'s own indices, read at the {_d(as_of)} close: what each index costs against its '
            'recent past, which investing styles beat their parent index, and how deep a normal year\'s fall goes for '
            'each size. Price returns; dividends are not added.</p></div>']


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


def section_valuation(f: ip.Frames, vals: list[ip.Valuation], m1: pd.Timestamp, m3: pd.Timestamp,
                      young: ip.YoungValuation | None = None) -> list:
    by = {v.key: v for v in vals}
    n50, s250 = by.get("nifty_50"), by.get("nifty_smallcap_250")
    h2 = "Valuation against the index's own recent past."
    if n50 and s250:
        h2 = (f"The Nifty 50 at {n50.pe_now:.1f} times earnings is cheaper than {100 - n50.pct_now:.0f}% of days "
              f"since April 2021; the Nifty Smallcap 250 is dearer than {s250.pct_now:.0f}%.")
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
             '<p class="dh-note">P/E is NSE\'s trailing price to earnings. The percentile counts days from 31 Mar 2021, when '
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
        parts += [Chart("lines", {"dates": dates, "series": [
                        {"name": "Nifty 500 P/E, old basis", "color": "faint", "values": old, "width": 1.6},
                        {"name": "Nifty 500 P/E since 31 Mar 2021", "color": "ink", "values": new, "width": 2}],
                        "bands": [{"from": round(q25, 2), "to": round(q75, 2), "color": "up-soft"}],
                        "levels": [], "range": PE_RANGE},
                        {"label": "Nifty 500 P/E, weekly, since 2012"}),
                  how("The Nifty 500's trailing P/E each week since 2012. Grey is the old earnings basis, ink the basis "
                      "since 31 Mar 2021; the shaded band is the middle half of days since then "
                      f"({q25:.1f} to {q75:.1f}). The Nifty 500, not Nifty Total Market, because NSE's P/E for Nifty "
                      "Total Market starts at its launch, 14 Oct 2021, and this line shows the years before the "
                      "2021 change of basis.",
                      "A line above the band is dearer than three days in four since 2021; below it, cheaper. The two "
                      "colours are two definitions: do not read the 2021 drop as a fall in price.",
                      ["Index", "P/E", "P/B", "Div yield", "Percentile now", "A month ago", "3 months ago"],
                      [[v.name, f"{v.pe_now:.2f}", f"{v.pb_now:.2f}", f"{v.dy_now:.1f}%", f"{v.pct_now:.0f}",
                        f"{v.pct_1m:.0f}", f"{v.pct_3m:.0f}"] for v in vals] + ([young_table] if young_table else []))]
    return parts


def section_styles(sts: list[ip.Style], m1: pd.Timestamp, m3: pd.Timestamp) -> list:
    lead = sorted((s for s in sts if s.lead_now is not None), key=lambda s: -s.lead_now)
    ahead = [s.style.lower() for s in lead if s.lead_now > 0]
    behind = [s for s in lead if s.lead_now < -5]
    h2 = "Each style against the index it picks from, over the last 12 months."
    if ahead and behind:
        lo, hi = min(-s.lead_now for s in behind), max(-s.lead_now for s in behind)
        span = f"{lo:.0f}–{hi:.0f}" if round(lo) != round(hi) else f"{lo:.0f}"
        h2 = (f'Over 12 months, {" and ".join(ahead[:2])} <span class="dh-up">lead their parents</span>; '
              f'{" and ".join(s.style.lower() for s in behind)} <span class="dh-down">trail by {span} points</span>.')
    rows = [{"name": s.style, "sub": f"{s.name} against {s.parent_name} · live since {_dy(s.live)}",
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


def section_lag(sts: list[ip.Style]) -> list:
    if not sts:
        return []
    mom = next((s for s in sts if s.style == "Momentum"), sts[0])
    worst_now = abs(mom.from_peak.iloc[-1]) >= abs(mom.worst) - 0.05
    # S173 IX-2: the figure is the fall of a ratio (the relative line below its peak), not a gap of two returns.
    h2 = (f'{e(mom.style)}’s line against the {e(mom.parent_name)} is <span class="dh-down">{_fmt.fixed(abs(mom.from_peak.iloc[-1]), 1)}% '
          f'below its {mom.worst_peak:%B %Y} peak</span>' + (f", its deepest since launch in {mom.live.year}." if worst_now else "."))
    others = [s for s in sts if s is not mom and abs(s.from_peak.iloc[-1]) >= abs(s.worst) - 0.05 and s.worst < -5]
    rec = [s for s in sts if s.recovered is not None and s.worst <= -20]
    extra = ""
    if others:
        extra += " " + " and ".join(f"{s.style} is at its worst too ({sg(s.from_peak.iloc[-1])}%)" for s in others) + "."
    if rec:
        r = min(rec, key=lambda s: s.worst)
        extra += (f" {r.style} fell {abs(r.worst):.1f}% against the {r.parent_name} in {r.worst_peak.year}–{str(r.worst_low.year)[2:]}"
                  f" and took until {r.recovered:%B %Y} to recover.")
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
             '<th scope="col" class="dh-num">Now</th><th scope="col" class="dh-num">Max drawdown, relative</th>'
             '<th scope="col" class="dh-num">Worst, peak → low</th><th scope="col" class="dh-num">Recovered</th></tr></thead>'
             f'<tbody>{body}</tbody></table></div>')
    return [f'<div class="dh-sec">{KICK.format("How long a style can lag")}<h2 id="s-lag" class="dh-h2">{h2}</h2>'
            '<p class="dh-note">The relative line divides the style index by its parent, 100 at launch: rising means the '
            f'style is ahead. Below it, how far the line sits under its own best.{e(extra)}</p></div>',
            Chart("rel", {"styles": styles}, {"label": "A style index against its parent"}),
            f'<div class="dh-sec dh-sec-cont">{table}</div>']


def section_years(sts: list[ip.Style], as_of: pd.Timestamp) -> list:
    if not sts:
        return []
    # Whole years only: the year in progress is in the table, not in the count (S193 B: "7 years of 9" counted 2026).
    def whole(s):
        ys = {y: v for y, v in s.years.items() if y < as_of.year or (as_of.month == 12 and as_of.day >= 31)}
        return sum(v > 0 for v in ys.values()), len(ys)
    led = {s.style: whole(s) for s in sts}
    always = [s for s, (a, b) in led.items() if a == b and b > 1]
    best = max(led.items(), key=lambda kv: (kv[1][0] / kv[1][1] if kv[1][1] else 0, kv[1][1]))
    h2 = (f"No style led its parent every whole year; {best[0].lower()} came closest, {best[1][0]} of {best[1][1]}."
          if not always else f"{always[0]} led its parent in every year since launch.")
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


def section_size(sizes: list[ip.SizeYears], as_of: pd.Timestamp) -> list:
    if not sizes:
        return []
    by = {z.size: z for z in sizes}
    large, small = by.get("Large"), by.get("Small")
    h2 = "How far each size falls within a calendar year."
    if large and small and large.median_fall < 0:
        ratio = small.median_fall / large.median_fall
        word = "twice" if 1.8 <= ratio <= 2.2 else f"{ratio:.1f} times"
        h2 = (f"In a median year since {ip.SIZE_FROM_YEAR}, the Nifty Smallcap 250 fell {abs(small.median_fall):.0f}% at some point, "
              f"{word} the Large Cap index's {abs(large.median_fall):.0f}%.")
    allv = [x for z in sizes for v in z.years.values() for x in v]
    lo, hi = (min(allv) // 20) * 20, -((-max(allv)) // 20) * 20
    meds = ", ".join(f"{_fmt.size(z.size)} {sg(z.median_fall, 1, '%')}" for z in sizes)
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
                             for z in sizes] for y in sorted({y for z in sizes for y in z.years}, reverse=True)])
    return ([f'<div class="dh-sec">{KICK.format("Size, year by year")}<h2 id="s-size" class="dh-h2">{e(h2)}</h2>'
             f'<p class="dh-note">The bar is the calendar year\'s return; the dot is the max drawdown within it. '
             f'{as_of.year} is year to date. Median of whole years since {ip.SIZE_FROM_YEAR}: {e(meds)}'
             f'{" (micro from 2022)" if "Micro" in by else ""}.</p></div>'] + grid + [table])


GROUP_NOTE = {
    "Broad market": "Size and breadth: Nifty Total Market, the large, mid and small company indices.",
    "Theme": "Ideas that cut across sectors: defence, manufacturing, PSUs, business groups, new listings.",
    "Strategy": "Rules-based selections and weightings: momentum, quality, value, low volatility, equal weight, dividends.",
}


def section_every(f: ip.Frames, rows: dict[str, list[ip.IndexRow]], as_of: pd.Timestamp) -> list:
    n = sum(len(v) for v in rows.values())
    tm = ip.ret(f.close["nifty_total_market"], 12, as_of) if "nifty_total_market" in f.close else None
    themes = [r for r in rows.get("Theme", []) if r.returns[12] is not None]
    late = ip.late_names(x for v in rows.values() for x in v)
    late_txt = f" {_fmt.closes_not_in(late, as_of)} Their figures read –." if late else ""
    h2 = f"NSE's {n} broad, theme and strategy indices over 12 months."
    if tm is not None and themes:
        h2 = (f"Over 12 months Nifty Total Market is {'up' if tm >= 0 else 'down'} {abs(tm):.1f}%; among themes, "
              f"{_short(themes[0].name)} leads at {sg(themes[0].returns[12], 1, '%')} and "
              f"{_short(themes[-1].name)} trails at {sg(themes[-1].returns[12], 1, '%')}.")
    parts = [f'<div class="dh-sec">{KICK.format("Every index")}<h2 id="s-every" class="dh-h2">{e(h2)}</h2>'
             f'<p class="dh-note">NSE\'s {n} broad, theme and strategy indices, in three families, each sorted by its '
             f'price return over 12 months. Each window ends on {_dy(as_of)} and starts on the last session on or before the same '
             'date 1, 3, 6, 9 and 12 months back. Indices younger than 12 months are listed last, with their launch date in the 12M column. '
             "NSE's sector indices are on Sectors, beside the sectors they match. Bond, rate, leveraged and inverse "
             f'indices, India VIX and the dollar Nifty are left out.{e(late_txt)}</p></div>']
    for g in ip.PAGE_FAMILIES:
        xs = rows.get(g, [])
        full = [x for x in xs if x.returns[12] is not None]
        if not xs:
            continue
        lead = (f"{g}: {sum(x.returns[12] > 0 for x in full)} of {len(full)} up over the year; "
                f"{_short(full[0].name)} leads at {sg(full[0].returns[12], 1, '%')}, "
                f"{_short(full[-1].name)} trails at {sg(full[-1].returns[12], 1, '%')}.") if full else g
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


def page_parts(f: ip.Frames, system: str | None = None) -> list:
    as_of = f.as_of
    n50 = f.close["nifty_50"].dropna()
    m1 = ip.on_or_before(n50, ip.months_back(as_of, 1))
    m3 = ip.on_or_before(n50, ip.months_back(as_of, 3))
    vals, sts = ip.valuation(f), ip.styles(f)
    every = ip.every_index(f)
    n = sum(len(v) for v in every.values())
    young = ip.young_valuation(f, SYSTEM_INDEX[system]) if system in SYSTEM_INDEX else None
    return (head(vals, as_of) + section_valuation(f, vals, m1, m3, young) + section_styles(sts, m1, m3) + section_lag(sts)
            + section_years(sts, as_of) + section_size(ip.size_years(f), as_of) + section_every(f, every, as_of)
            + [f'<p class="dh-foot">{_fmt.data_to(as_of, "NSE")} · {n} broad, theme and strategy indices</p>'])


def render_indices_view() -> None:
    st.html(f"<style>{HOME_CSS}{IX_CSS}</style>")
    f = indices_data.frames()
    if f is None:
        st.html('<div class="dh"><div class="dh-sec"><p class="dh-kick">Indices</p><h1 class="dh-h1">No index data yet.</h1>'
                '<p class="dh-lede">The copy of NSE\'s daily index files this page reads is not in yet; the page fills '
                'once it is.</p></div></div>')
        return
    from src.ui import system_param
    emit(page_parts(f, system_param.current()))


__all__ = ["render_indices_view", "page_parts", "html_of"]
