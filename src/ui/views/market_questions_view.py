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
    "breadth": {mq.UP: "broad", mq.MID: "between", mq.DOWN: "narrow"},
    "trend": {mq.UP: "up", mq.MID: "between", mq.DOWN: "down"},
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
            '<p class="mq-key">● today · ○ a month ago · dashed: a year ago</p>')


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
        shown = (", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")) if names else "none"
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
