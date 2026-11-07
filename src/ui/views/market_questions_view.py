"""The Dashboard's three market questions, drawn (engine: src/engine/market_questions.py).

Each question is one column: the question, the answer in a word or two, one
sentence, a five-band scale with today, a month ago and a year ago marked, the
measures that vote (now and a year ago, with the vote in words and the cut-off
on hover), what changed, and a link to the page that owns the detail.
"""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from src.engine import market_questions as mq
from src.engine import size_leadership as sl
from src.engine.pipeline import price_fingerprint
from src.ui import formats as _fmt
from src.ui.system_param import page_href

_VOTE_WORD = {
    "breadth": {mq.UP: "Broad", mq.MID: "Between", mq.DOWN: "Narrow"},
    "trend": {mq.UP: "Up", mq.MID: "Between", mq.DOWN: "Down"},
}

_CSS = """<style>
.mq-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 32px;margin:4px 0 18px;
  border-top:1px solid var(--c-ink)}
.mq{padding:14px 0 0;min-width:0}
.mq h2{font-size:15px!important;font-weight:600!important;color:var(--c-ink)!important;margin:0 0 6px!important;padding:0!important;letter-spacing:0!important}
.mq-v{font-size:24px;font-weight:600;line-height:1.15;color:var(--c-ink);margin:0 0 6px}
.mq-v.up{color:var(--c-up)}.mq-v.down{color:var(--c-down)}
.mq-s{font-size:14px;line-height:1.5;color:var(--c-text_2);margin:0 0 12px}
.mq-scale{position:relative;margin:4px 0 4px;height:22px}
.mq-scale .bar{position:absolute;left:0;right:0;top:9px;height:4px;background:linear-gradient(90deg,var(--c-down) 0,var(--c-rule) 35%,var(--c-rule) 65%,var(--c-up) 100%);opacity:.55}
.mq-scale i{position:absolute;top:4px;width:14px;height:14px;margin-left:-7px;border-radius:50%;box-sizing:border-box}
.mq-scale i.now{background:var(--c-ink);border:2px solid var(--c-white);z-index:3}
.mq-scale i.m{background:var(--c-white);border:2px solid var(--c-ink);z-index:2}
.mq-scale i.y{background:var(--c-white);border:2px dashed var(--c-muted);z-index:1}
.mq-ends{display:flex;justify-content:space-between;font-size:12px;color:var(--c-muted);margin-bottom:6px}
.mq-key{font-size:12px;color:var(--c-muted);margin:0 0 10px}
.mq-key b{font-weight:600;color:var(--c-ink)}
.mq table{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}
.mq th{font-size:12px;font-weight:500;color:var(--c-muted);text-align:right;padding:4px 0 4px 8px;border-bottom:1px solid var(--c-rule_strong)}
.mq th:first-child{text-align:left;padding-left:0}
.mq td{padding:6px 0 6px 8px;border-bottom:1px solid var(--c-rule);text-align:right;vertical-align:top;color:var(--c-ink)}
.mq td:first-child{text-align:left;padding-left:0;color:var(--c-text_2)}
.mq td.up{color:var(--c-up);font-weight:600}.mq td.down{color:var(--c-down);font-weight:600}.mq td.mid{color:var(--c-muted)}
.mq-ch{font-size:13px;line-height:1.5;color:var(--c-text_2);margin:10px 0 4px}
.mq-more{font-size:13px;color:var(--c-ink)!important;text-decoration:underline;text-decoration-color:var(--c-rule_strong);text-underline-offset:3px}
.mq-note{font-size:12px;color:var(--c-muted);margin:0 0 6px}
@media (max-width:1100px){.mq-grid{grid-template-columns:1fr;gap:0}.mq{padding-bottom:12px}}
</style>"""


def _num(v: float | None, unit: str) -> str:
    if v is None:
        return "—"
    if unit == "pct":
        return _fmt.pct(v, signed_=False, digits=0, fraction=False)
    return _fmt.signed(v, 1)


def _pos(score: float | None) -> float:
    return 50.0 if score is None else max(0.0, min(100.0, (score + 1) * 50))


def _scale(a: mq.Answer) -> str:
    dots = (f'<i class="y" style="left:{_pos(a.score_year_ago):.1f}%"></i>' if a.score_year_ago is not None else "")
    dots += (f'<i class="m" style="left:{_pos(a.score_month_ago):.1f}%"></i>' if a.score_month_ago is not None else "")
    dots += f'<i class="now" style="left:{_pos(a.score):.1f}%"></i>'
    return (f'<div class="mq-scale" aria-hidden="true"><span class="bar"></span>{dots}</div>'
            f'<div class="mq-ends" aria-hidden="true"><span>{html.escape(a.words[0])}</span>'
            f'<span>{html.escape(a.words[2])}</span><span>{html.escape(a.words[4])}</span></div>'
            '<p class="mq-key">● Today · ○ A month ago · dashed ring: A year ago</p>')


def _tone(a: mq.Answer) -> str:
    return "up" if a.score >= 0.25 else "down" if a.score <= -0.25 else ""


def _changed(a: mq.Answer) -> str:
    def word(s):
        return mq.word_for(s, a.words) if s is not None else "not known"
    return (f"A month ago: {word(a.score_month_ago).lower()}. "
            f"A year ago: {word(a.score_year_ago).lower()}.")


def _answer_html(a: mq.Answer, kind: str, href: str, link: str) -> str:
    words = _VOTE_WORD[kind]
    rows = "".join(
        f'<tr><td title="{html.escape(m.rule)}">{html.escape(m.name)}{" (primary)" if m.primary else ""}</td>'
        f'<td>{_num(m.now, m.unit)}</td><td>{_num(m.year_ago, m.unit)}</td>'
        f'<td class="{m.vote}">{words[m.vote]}</td></tr>'
        for m in a.measures)
    return (
        f'<section class="mq" aria-label="{html.escape(a.question)}"><h2>{html.escape(a.question)}</h2>'
        f'<p class="mq-v {_tone(a)}">{html.escape(a.verdict)}</p>'
        f'<p class="mq-s">{html.escape(a.sentence)}</p>{_scale(a)}'
        '<table><thead><tr><th scope="col">Measure</th><th scope="col">Now</th>'
        f'<th scope="col">A year ago</th><th scope="col">Vote</th></tr></thead><tbody>{rows}</tbody></table>'
        f'<p class="mq-ch">{html.escape(_changed(a))}</p>'
        f'<a class="mq-more" href="{html.escape(href)}" target="_self">{html.escape(link)} →</a></section>')


def _leaders_html(ld: mq.Leaders, href: str) -> str:
    sec = ld.sectors
    both = sec[sec["group"] == "ahead on both"]["Industry"].head(3).tolist()
    best = max((x for x in ld.size if x[1] is not None), key=lambda x: x[1], default=None)
    verdict = "; ".join([x for x in [best[0] if best else "", ", ".join(both)] if x]) or "No clear leader"
    groups = []
    for g in ("ahead on both", "gaining", "fading", "behind on both"):
        names = sec[sec["group"] == g]["Industry"].tolist()
        shown = (", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")) if names else "None"
        groups.append(f'<tr><td>{g.capitalize()}</td><td style="text-align:left">'
                      f'{len(names)} · {html.escape(shown)}</td></tr>')
    return (
        '<section class="mq" aria-label="What is leading?"><h2>What is leading?</h2>'
        f'<p class="mq-v">{html.escape(verdict)}</p><p class="mq-s">{html.escape(ld.sentence)}</p>'
        # The size indices' figures are the Size leadership block's, below.
        + ('<table><thead><tr><th scope="col">Industries, median stock against the Nifty 500</th>'
           f'<th scope="col" style="text-align:left">6M and 1M</th></tr></thead><tbody>{"".join(groups)}</tbody></table>')
        + f'<p class="mq-ch">Industries are NSE\'s, at least five stocks each; points are the median stock\'s return less the Nifty 500\'s.</p>'
        f'<a class="mq-more" href="{html.escape(href)}" target="_self">Sectors →</a></section>')


def _t(v: float | None) -> str:
    return "" if v is None else ("up" if v > 0 else "down" if v < 0 else "")


@st.cache_data(show_spinner=False, ttl=3600)
def _answers(_key: str, _prices: pd.DataFrame, _industry: pd.Series, _bench: pd.Series,
             _size: dict[str, pd.Series]):
    breadth = mq.breadth_answer(_prices, _bench)
    share = mq._share_above_ema(_prices, 200)
    trend = mq.trend_answer(_bench, _size, share)
    leaders = mq.leaders_answer(_prices, _industry, _bench, _size)
    return breadth, trend, leaders


def size_closes(levels: pd.DataFrame | None, ok: bool) -> dict[str, pd.Series]:
    if levels is None or not ok:
        return {}
    cl = sl.closes(levels)
    return {name: cl[key] for key, name in sl.INDICES if key in cl.columns}


def render_market_questions(rank_df: pd.DataFrame, prices: pd.DataFrame, bench: pd.Series | None,
                            size: dict[str, pd.Series]) -> None:
    if prices is None or prices.empty or bench is None or bench.dropna().empty:
        return
    syms = [s for s in rank_df["Symbol"] if s in prices.columns]
    px = prices[syms]
    industry = rank_df.drop_duplicates("Symbol").set_index("Symbol").get("Industry", pd.Series(dtype=str))
    key = "|".join([price_fingerprint(px), str(bench.dropna().index[-1]), ",".join(sorted(size))])
    breadth, trend, leaders = _answers(key, px, industry, bench.dropna(), size)
    cols = []
    if breadth is not None:
        cols.append(_answer_html(breadth, "breadth", page_href("breadth"), "Market breadth"))
    if trend is not None:
        cols.append(_answer_html(trend, "trend", page_href("breadth"), "Market breadth"))
    if leaders is not None:
        cols.append(_leaders_html(leaders, page_href("sectors")))
    if not cols:
        return
    st.html(_CSS + f'<div class="mq-grid">{"".join(cols)}</div>'
            '<p class="mq-note">Counted over the stocks ranked today, so readings a year back leave out '
            'stocks that have since left the index. Each vote\'s cut-off shows on hover.</p>')


# ── Full question sections, for the pages that own the detail ───────────────

_PAGE_CSS = """<style>
.qp{border-top:1px solid var(--c-ink);padding:14px 0 6px;margin:0 0 22px}
.qp h2{font-size:20px!important;font-weight:600!important;color:var(--c-ink)!important;margin:0 0 10px!important;padding:0!important;letter-spacing:0!important;scroll-margin-top:72px}
.qp-top{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:0 40px;margin-bottom:14px}
.qp-v{font-size:30px;font-weight:600;line-height:1.1;margin:0 0 6px;color:var(--c-ink)}
.qp-v.up{color:var(--c-up)}.qp-v.down{color:var(--c-down)}
.qp-s{font-size:15px;line-height:1.55;color:var(--c-text_2);margin:0 0 12px}
.qp h3{font-size:14px!important;font-weight:600!important;color:var(--c-ink)!important;margin:0 0 6px!important;padding:0!important}
.qp ul{margin:0 0 12px;padding-left:18px}.qp li{font-size:14px;line-height:1.55;color:var(--c-text_2);margin:2px 0}
.qp li b{color:var(--c-ink);font-weight:600}
.qp table{width:100%;border-collapse:collapse;font-size:13.5px;font-variant-numeric:tabular-nums;margin:4px 0 6px}
.qp th{font-size:12px;font-weight:500;color:var(--c-muted);text-align:right;padding:6px 0 6px 12px;border-bottom:1px solid var(--c-rule_strong);white-space:nowrap}
.qp th:first-child,.qp th.l{text-align:left;padding-left:0}
.qp td{padding:8px 0 8px 12px;border-bottom:1px solid var(--c-rule);text-align:right;vertical-align:top;color:var(--c-ink)}
.qp td:first-child{text-align:left;padding-left:0}
.qp td.rule{text-align:left;color:var(--c-muted);font-size:12.5px}
.qp td.up{color:var(--c-up);font-weight:600}.qp td.down{color:var(--c-down);font-weight:600}.qp td.mid{color:var(--c-muted)}
.qp-tag{font-size:12px;color:var(--c-muted);margin-left:6px}
.qp-note{font-size:12.5px;color:var(--c-muted);margin:6px 0 0}
.qp-nav{display:flex;flex-wrap:wrap;gap:4px 18px;font-size:13.5px;margin:0 0 14px}
.qp-nav a{color:var(--c-ink)!important;text-decoration:underline;text-decoration-color:var(--c-rule_strong);text-underline-offset:3px}
@media (max-width:900px){.qp-top{grid-template-columns:1fr}.qp td.rule,.qp th.rule{display:none}}
</style>"""


def _changes_html(a: mq.Answer, kind: str) -> str:
    items = mq.changes(a)[:3]
    if not items:
        return "<ul><li>A month-ago reading is not available.</li></ul>"
    words = _VOTE_WORD[kind]
    li = []
    for m, then, now in items:
        moved = "" if _vote_of(m, then) == m.vote else f", now {words[m.vote].lower()}"
        li.append(f"<li><b>{html.escape(m.name)}</b>: {_num(then, m.unit)} a month ago, "
                  f"{_num(now, m.unit)} now{moved}.</li>")
    was = mq.word_for(a.score_month_ago, a.words) if a.score_month_ago is not None else None
    head = (f"<li>The answer a month ago: <b>{html.escape(was.lower())}</b>.</li>" if was else "")
    return "<ul>" + head + "".join(li) + "</ul>"


def _vote_of(m: mq.Measure, v: float) -> str:
    return mq._vote(v, m.up_at, m.down_at)


def _would_html(a: mq.Answer) -> str:
    ww = mq.what_would_change(a)
    i = a.words.index(a.verdict) if a.verdict in a.words else 2
    li = []
    for side, step in (("higher", 1), ("lower", -1)):
        if not ww[side] or not 0 <= i + step < len(a.words):
            continue
        target = a.words[i + step].lower()
        bits = [f"{html.escape(m.name)} {_move_words(m, side)} {_num(c, m.unit)} "
                f"(now {_num(m.now, m.unit)})" for m, c in ww[side][:2]]
        li.append(f"<li>To <b>{html.escape(target)}</b>: {'; or '.join(bits)}.</li>")
    if not li:
        li.append("<li>No single measure moving one step would change the answer; it would take two or more.</li>")
    return "<ul>" + "".join(li) + "</ul>"


def _move_words(m: mq.Measure, side: str) -> str:
    """The cut-offs are inclusive (at the upper one is up, at the lower one is
    down), so leaving a vote means crossing past it, reaching one means at."""
    if side == "higher":
        return "rising above" if m.vote == mq.DOWN else "reaching"
    return "falling below" if m.vote == mq.UP else "falling to"


def _range_html(m: mq.Measure) -> str:
    h = m.history
    if not h or m.now is None:
        return '<span class="qp-note">Under a year of history</span>'
    lo, q1, q3, hi, _pct, _since = h
    span = (hi - lo) or 1.0
    x = lambda v: max(0.0, min(100.0, (v - lo) / span * 100))  # noqa: E731
    return (f'<span class="rng" title="Lowest {_num(lo, m.unit)}, highest {_num(hi, m.unit)}; '
            f'the shaded part is the middle half"><i class="t"></i>'
            f'<i class="m" style="left:{x(q1):.1f}%;width:{max(1.0, x(q3) - x(q1)):.1f}%"></i>'
            f'<i class="d {m.vote}" style="left:{x(m.now):.1f}%"></i></span>')


def _ordinal(n: float) -> str:
    k = int(round(n))
    suf = "th" if 10 <= k % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(k % 10, "th")
    return f"{k}{suf}"


def question_section_html(a: mq.Answer, kind: str, anchor: str) -> str:
    words = _VOTE_WORD[kind]
    rows = []
    for m in a.measures:
        sub = []
        if m.history:
            since = m.history[5]
            sub.append(f"{_ordinal(m.history[4])} percentile" + (f" since {since:%b %Y}" if since is not None else ""))
        sub.append(f"A year ago {_num(m.year_ago, m.unit)}")
        rows.append(
            f'<tr><td>{html.escape(m.name)}<br><span class="qp-note" style="margin:0">'
            f'{"Primary. " if m.primary else ""}{html.escape(sentence_case(m.rule))}</span></td>'
            f'<td style="text-align:center">{_range_html(m)}</td>'
            f'<td class="big">{_num(m.now, m.unit)}<br><span class="sub">{"<br>".join(sub)}</span></td>'
            f'<td class="{m.vote}">{words[m.vote]}</td></tr>')
    return (
        f'<section class="qp" aria-labelledby="{anchor}"><h2 id="{anchor}">{html.escape(a.question)}</h2>'
        '<div class="qp-top"><div>'
        f'<p class="qp-v {_tone(a)}">{html.escape(a.verdict)}</p><p class="qp-s">{html.escape(a.sentence)}</p>'
        f'{_scale(a)}</div><div><h3>What has changed</h3>{_changes_html(a, kind)}'
        f'<h3>What would change the answer</h3>{_would_html(a)}</div></div>'
        '<table><thead><tr><th scope="col">The evidence</th><th scope="col" style="text-align:center">'
        'Where today sits, lowest to highest</th><th scope="col">Now</th><th scope="col">Vote</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
        '<p class="qp-note">Each measure votes by its cut-offs; primary measures count twice. The bar runs from '
        'the lowest reading in the price history the site holds to the highest; the shaded part is the middle '
        'half. The verdict is at an end when the weighted vote is 0.6 or more either way, leaning at 0.25.</p>'
        '</section>')


def sentence_case(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def size_trend_html(bench: pd.Series, size: dict[str, pd.Series]) -> str:
    """The Nifty 500 and each size index against its 10-month average and 200D
    EMA, and its distance from the 52W high: now and a month ago."""
    series = {"Nifty 500": bench.dropna(), **{k: v.dropna() for k, v in size.items()}}
    d = mq.anchor_dates(series["Nifty 500"].index)
    rows = []
    for name, s in series.items():
        if len(s) < 60:
            continue
        cells = []
        for f in (mq.ten_month_gap, mq.ema_gap, mq.from_high):
            for k in ("month_ago", "now"):
                v = f(s, d[k])
                r = None if v is None else round(v, 1)   # tone what is shown: "0.0" is neither
                tone = "" if r is None or f is mq.from_high else ("up" if r > 0 else "down" if r < 0 else "")
                cells.append(f'<td class="{tone}">{_num(v, "pts")}</td>')
        rows.append(f"<tr><td>{html.escape(name)}</td>{''.join(cells)}</tr>")
    if not rows:
        return ""
    return ('<table><thead><tr><th scope="col" rowspan="2">Index</th>'
            '<th scope="colgroup" colspan="2">Against its 10-month average</th>'
            '<th scope="colgroup" colspan="2">Against its 200D EMA</th>'
            '<th scope="colgroup" colspan="2">From its 52W high</th></tr>'
            '<tr><th scope="col">A month ago</th><th scope="col">Now</th><th scope="col">A month ago</th>'
            '<th scope="col">Now</th><th scope="col">A month ago</th><th scope="col">Now</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>'
            '<p class="qp-note">The 10-month rule reads completed months: the last month-end close against '
            'the average of the last ten. Points are per cent.</p>')


def render_breadth_questions(rank_df: pd.DataFrame, prices: pd.DataFrame, bench: pd.Series | None,
                             size: dict[str, pd.Series]) -> bool:
    """The Breadth page's two questions. Returns False when there is not
    enough data to answer them."""
    if prices is None or prices.empty or bench is None or bench.dropna().empty:
        return False
    syms = [s for s in rank_df["Symbol"] if s in prices.columns]
    px = prices[syms]
    industry = rank_df.drop_duplicates("Symbol").set_index("Symbol").get("Industry", pd.Series(dtype=str))
    key = "|".join([price_fingerprint(px), str(bench.dropna().index[-1]), ",".join(sorted(size))])
    breadth, trend, _ = _answers(key, px, industry, bench.dropna(), size)
    parts = [_CSS, _PAGE_CSS, '<nav class="qp-nav" aria-label="On this page">'
             '<a href="#q-breadth">Are most stocks taking part?</a>'
             '<a href="#q-trend">Is the market in an uptrend?</a><a href="#q-charts">Today\'s charts</a></nav>']
    if breadth is not None:
        parts.append(question_section_html(breadth, "breadth", "q-breadth"))
    if trend is not None:
        sec = question_section_html(trend, "trend", "q-trend")
        table = size_trend_html(bench, size)
        if table:
            sec = sec.replace("</section>", "<h3 style='margin-top:14px'>By size</h3>" + table + "</section>")
        parts.append(sec)
    parts.append('<p class="qp-note" style="margin-bottom:18px">Counted over the stocks ranked today, so '
                 'readings a year back leave out stocks that have since left the index.</p>')
    st.html("".join(parts))
    return breadth is not None or trend is not None


# ── Sectors: "What is leading?" in full ─────────────────────────────────────

_SECTOR_CSS = """<style>
.qp-quad{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0 24px;margin:4px 0 14px}
.qp-quad div{border-top:1px solid var(--c-rule_strong);padding-top:8px}
.qp-quad b{display:block;font-size:13.5px;font-weight:600;color:var(--c-ink);margin-bottom:4px}
.qp-quad b.up{color:var(--c-up)}.qp-quad b.down{color:var(--c-down)}
.qp-quad p{font-size:13px;line-height:1.5;color:var(--c-text_2);margin:0 0 3px;display:flex;justify-content:space-between;gap:8px}
.qp-quad p span:last-child{font-variant-numeric:tabular-nums;color:var(--c-muted);white-space:nowrap}
.qp-quad p.qh{font-size:12px;color:var(--c-muted);border-bottom:1px solid var(--c-rule);padding-bottom:3px;margin-bottom:5px}
.qp-heat{overflow-x:auto}
.qp-heat table{min-width:900px}
.qp-heat td{font-size:12.5px;padding:6px 4px;text-align:center}
.qp-heat th{text-align:center;padding:6px 4px}
.qp-heat td:first-child,.qp-heat th:first-child{text-align:left;white-space:nowrap;padding-right:10px}
.qp-heat td.u2{background:var(--c-up_line_2);color:var(--c-ink)}.qp-heat td.u1{background:var(--c-up_tint)}
.qp-heat td.d1{background:var(--c-down_tint)}.qp-heat td.d2{background:var(--c-down_line_3);color:var(--c-ink)}
.qp-heat td.mtd{border-left:1px dashed var(--c-rule_strong)}
.qp-heat td.run,.qp-heat td.tot{text-align:right;font-weight:600}
@media (max-width:900px){.qp-quad{grid-template-columns:1fr 1fr;gap:12px 16px}}
</style>"""

_QUADS = (("ahead on both", "Ahead on both", "up"), ("gaining", "Gaining: ahead over the month", "up"),
          ("fading", "Fading: ahead over six months only", "down"), ("behind on both", "Behind on both", "down"))


def _heat_cls(v: float) -> str:
    if not pd.notna(v):
        return ""
    return "u2" if v >= 4 else "u1" if v > 0 else "d2" if v <= -4 else "d1" if v < 0 else ""


def _run_text(n: int) -> str:
    if not n:
        return "—"
    return f"{abs(n)} {'ahead' if n > 0 else 'behind'}"


def leaders_section_html(ld: mq.Leaders, months: pd.DataFrame) -> str:
    sec = ld.sectors
    both = sec[sec["group"] == "ahead on both"]["Industry"].head(3).tolist()
    best = max((x for x in ld.size if x[1] is not None), key=lambda x: x[1], default=None)
    verdict = "; ".join([x for x in [best[0] if best else "", ", ".join(both)] if x]) or "No clear leader"

    size_rows = "".join(
        f'<tr><td>{html.escape(n)}</td><td class="{_t(r6)}">{_num(r6, "pts")}</td>'
        f'<td class="{_t(r1)}">{_num(r1, "pts")}</td></tr>' for n, r6, r1 in ld.size)
    size_html = ('<h3>By size, against the Nifty 500</h3><table><thead><tr><th scope="col">Index</th>'
                 '<th scope="col">6 months</th><th scope="col">1 month</th></tr></thead>'
                 f'<tbody>{size_rows}</tbody></table>') if size_rows else ""

    quads = []
    for key, title, tone in _QUADS:
        g = sec[sec["group"] == key]
        items = "".join(f'<p><span>{html.escape(r.Industry)}</span><span>{_num(r.rel_6m, "pts")} · '
                        f'{_num(r.rel_1m, "pts")}</span></p>' for r in g.itertuples()) or "<p><span>None</span></p>"
        quads.append(f'<div><b class="{tone}">{html.escape(title)} ({len(g)})</b>'
                     '<p class="qh"><span>Industry</span><span>6M · 1M, pts</span></p>'
                     f'{items}</div>')
    quad_html = ('<h3>Industries by six months and one month</h3>'
                 '<p class="qp-note" style="margin:0 0 6px">Each figure is the median stock\'s return less '
                 'the Nifty 500\'s, in points: over six months, then over one month.</p>'
                 f'<div class="qp-quad">{"".join(quads)}</div>')

    heat_html = ""
    if months is not None and not months.empty:
        cols = [c for c in months.columns if c not in ("run", "total")]
        longest = months["run"].abs().max()
        lead_run = months[months["run"].abs() == longest]
        run_line = ""
        if longest and len(lead_run):
            n = int(lead_run["run"].iloc[0])
            run_line = (f'<p class="qp-s">{html.escape(lead_run.index[0])} has {"beaten" if n > 0 else "trailed"} '
                        f'the Nifty 500 in each of the last {abs(n)} completed months, the longest current run.</p>')
        head = "".join(f'<th scope="col">{html.escape(c.replace(" 20", " ’"))}</th>' for c in cols)
        body = []
        for name, r in months.iterrows():
            cells = "".join(
                f'<td class="{_heat_cls(r[c])}{" mtd" if c.endswith("MTD") else ""}">'
                f'{"—" if not pd.notna(r[c]) else _fmt.signed(r[c], 1)}</td>' for c in cols)
            body.append(f'<tr><td>{html.escape(name)}</td>{cells}<td class="run">{_run_text(int(r["run"]))}</td>'
                        f'<td class="tot {_t(r["total"])}">{_num(r["total"], "pts")}</td></tr>')
        heat_html = ('<h3>Month by month against the Nifty 500</h3>' + run_line +
                     '<div class="qp-heat"><table><thead><tr><th scope="col">Industry</th>' + head +
                     '<th scope="col">Run</th><th scope="col">12 months</th></tr></thead>'
                     f'<tbody>{"".join(body)}</tbody></table></div>'
                     '<p class="qp-note">Each cell is the median stock\'s return in that month less the '
                     'Nifty 500\'s, in points; deeper shades are 4 points or more. The last column before Run '
                     'is the month so far. Run counts completed months in a row on the same side.</p>')

    sw = mq.nearest_switches(sec)
    sw_items = []
    if sw["entrants"]:
        sw_items.append("<li>Nearest to moving ahead over six months: " + "; ".join(
            f"<b>{html.escape(n)}</b> {_num(v, 'pts')}" for n, v in sw["entrants"]) + ".</li>")
    if sw["exits"]:
        sw_items.append("<li>Nearest to falling behind: " + "; ".join(
            f"<b>{html.escape(n)}</b> {_num(v, 'pts')}" for n, v in sw["exits"]) + ".</li>")
    would = f'<h3>What would change the answer</h3><ul>{"".join(sw_items)}</ul>' if sw_items else ""

    return (_CSS + _PAGE_CSS + _SECTOR_CSS +
            '<section class="qp" aria-labelledby="q-lead"><h2 id="q-lead">What is leading?</h2>'
            f'<div class="qp-top"><div><p class="qp-v">{html.escape(verdict)}</p>'
            f'<p class="qp-s">{html.escape(ld.sentence)}</p>{size_html}</div>'
            f'<div>{would}</div></div>{quad_html}{heat_html}'
            '<p class="qp-note">Industries are NSE\'s, at least five stocks each, counted over the stocks '
            'ranked today; points are the median stock\'s return less the Nifty 500\'s.</p></section>')


@st.cache_data(show_spinner=False, ttl=3600)
def _leaders_full(_key: str, _prices: pd.DataFrame, _industry: pd.Series, _bench: pd.Series,
                  _size: dict[str, pd.Series]):
    return (mq.leaders_answer(_prices, _industry, _bench, _size),
            mq.industry_months(_prices, _industry, _bench))


def render_leaders_section(rank_df: pd.DataFrame, prices: pd.DataFrame, bench: pd.Series | None,
                           size: dict[str, pd.Series]) -> bool:
    if prices is None or prices.empty or bench is None or bench.dropna().empty:
        return False
    syms = [s for s in rank_df["Symbol"] if s in prices.columns]
    px = prices[syms]
    industry = rank_df.drop_duplicates("Symbol").set_index("Symbol").get("Industry", pd.Series(dtype=str))
    key = "|".join([price_fingerprint(px), str(bench.dropna().index[-1]), ",".join(sorted(size)), "full"])
    leaders, months = _leaders_full(key, px, industry, bench.dropna(), size)
    if leaders is None:
        return False
    st.html(leaders_section_html(leaders, months))
    return True
