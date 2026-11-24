"""The market questions, drawn for the pages that own them (engine: src/engine/market_questions.py).

The Market page's breadth and trend sections (`render_breadth_questions`) and the
Sectors page's leaders section (`render_leaders_section`): each answer, a five-band
scale with today, a month ago and a year ago marked, the measures that vote, and
what changed.
"""
from __future__ import annotations

import hashlib
import html

import pandas as pd
import streamlit as st

from src.engine import market_questions as mq
from src.engine.pipeline import known_fingerprint
from src.ui import formats as _fmt

_VOTE_WORD = {
    "breadth": {mq.UP: "Broad", mq.MID: "Between", mq.DOWN: "Narrow"},
    "trend": {mq.UP: "Up", mq.MID: "Between", mq.DOWN: "Down"},
}

_CSS = """<style>
.mq-scale{position:relative;margin:4px 0 4px;height:22px}
.mq-scale .bar{position:absolute;left:0;right:0;top:9px;height:4px;background:linear-gradient(90deg,var(--c-down) 0,var(--c-rule) 35%,var(--c-rule) 65%,var(--c-up) 100%);opacity:.55}
.mq-scale i{position:absolute;top:4px;width:14px;height:14px;margin-left:-7px;border-radius:50%;box-sizing:border-box}
.mq-scale i.now{background:var(--c-ink);border:2px solid var(--c-white);z-index:3}
.mq-scale i.m{background:var(--c-white);border:2px solid var(--c-ink);z-index:2}
.mq-scale i.y{background:var(--c-white);border:2px dashed var(--c-muted);z-index:1}
.mq-ends{display:flex;justify-content:space-between;font-size:var(--fs-12);color:var(--c-muted);margin-bottom:6px}
.mq-key{font-size:var(--fs-12);color:var(--c-muted);margin:0 0 10px}
.mq-key b{font-weight:600;color:var(--c-ink)}
</style>"""


def _columns_key(prices: pd.DataFrame, syms: list) -> str:
    """Names prices[syms] exactly: the whole frame's fingerprint, computed once in
    app.py's loader (S208), and the columns taken, in order."""
    cols = hashlib.md5(",".join(map(str, syms)).encode()).hexdigest()[:12]
    return f"{known_fingerprint(prices)}_{len(syms)}c{cols}"


def _num(v: float | None, unit: str) -> str:
    if v is None:
        return "–"
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
            '<p class="mq-key">● Today · ○ A month ago · dashed ring: 12 months ago</p>')


def _tone(a: mq.Answer) -> str:
    return "up" if a.score >= 0.25 else "down" if a.score <= -0.25 else ""


# Anchors for the Dashboard's "On this page" line (owner, 8 Nov 2026: the
# Breadth page's section links, on the Dashboard too).
def _t(v: float | None) -> str:
    return "" if v is None else ("up" if v > 0 else "down" if v < 0 else "")


@st.cache_data(show_spinner=False, ttl=3600)
def _past_stamp() -> str:
    """The breadth history file's revision, for cache keys."""
    from src.engine import pit_breadth
    return str(pit_breadth.FILE.stat().st_mtime) if pit_breadth.FILE.exists() else "-"


def _answers(_key: str, _prices: pd.DataFrame, _industry: pd.Series, _bench: pd.Series,
             _size: dict[str, pd.Series], pit: bool = True, name: str = mq.MARKET):
    from src.engine import pit_breadth
    # The members-of-the-day history is the 750's: under another system's universe it is not joined (S194 L4).
    past = pit_breadth.load("total_market") if pit else None
    # "Ahead of the market" against Nifty Total Market alone, daily from NSE (owner, 21 Nov 2026): its one-year
    # readings start in Nov 2022, which is history enough here. `_bench` is that index joined to the Nifty 500
    # before its launch (mq.join_market), for the trend's longer readings.
    tm = total_market()
    breadth = (mq.breadth_answer(_prices, tm, past, market=mq.MARKET) if len(tm)
               else mq.breadth_answer(_prices, _bench, past, market=f"the {mq.EARLIER}"))
    share = pit_breadth.splice(mq._share_above_ema(_prices, 200), past, "above_200")
    trend = mq.trend_answer(_bench, _size, share, name)
    leaders = mq.leaders_answer(_prices, _industry, _bench, _size, market_name=the(name))
    return breadth, trend, leaders


def the(name: str) -> str:
    """The index's name as a sentence carries it: "the Nifty 500", but "Nifty Total Market" (GLOSSARY 1)."""
    return f"the {name}" if name == mq.EARLIER else name


def market_close(earlier: pd.Series | None) -> tuple[pd.Series, str]:
    """The market the Market page's trend is read against (S165): Nifty Total Market, joined to `earlier`, the
    Nifty 500, before Total Market's first session; and the name to print. Total Market from
    data/benchmark_indices.csv, the file the Dashboard, Portfolio and the header's regime read, so the header's
    200D EMA reading and this page's agree (it also holds NSE's weekend and Muhurat sessions)."""
    from src.loaders import benchmark_indices as bi
    return mq.join_market(earlier, bi.series(bi.TOTAL_MARKET))


def joined_note(close: pd.Series, name: str) -> str:
    """What the page says about the line it draws: which index, from when, and why."""
    if name != mq.MARKET:
        return (f"Nifty Total Market’s closes did not load, so this reads the {mq.EARLIER}, the nearest index with "
                "a long history.")
    from src.loaders import benchmark_indices as bi
    tm = bi.series(bi.TOTAL_MARKET).dropna()
    if close.empty or tm.empty or close.index[0] >= tm.index[0]:
        return ""
    return (f"Nifty Total Market from {tm.index[0]:%-d %b %Y}, when NSE launched it; before that the {mq.EARLIER}, "
            f"scaled to meet it on that day, so the trend’s ranges reach back to {close.index[0]:%Y}. NSE publishes "
            "no Nifty Total Market closes before its launch.")


def total_market() -> pd.Series:
    """Nifty Total Market's daily close: NSE's archive (data/nse_total_market.csv, from its first session) joined
    with data/benchmark_indices.csv for the latest sessions."""
    from pathlib import Path
    from src.loaders import benchmark_indices as bi
    f = Path(__file__).resolve().parents[3] / "data" / "nse_total_market.csv"
    nse = pd.Series(dtype=float)
    if f.exists():
        t = pd.read_csv(f, parse_dates=["date"])
        nse = pd.Series(pd.to_numeric(t["close"], errors="coerce").values, index=t["date"]).dropna()
    ours = bi.series(bi.TOTAL_MARKET).dropna()
    # The archive's close wins where it has one; every other session comes from the index file, not only those
    # after the archive ends: the archive lacks NSE's seven weekend sessions (Muhurat and Budget days, 12 Nov 2023
    # to 8 Nov 2026), which the index file holds from NSE's own files (S154, found 24 Nov 2026).
    return nse.combine_first(ours).sort_index()


def size_closes(levels: pd.DataFrame | None = None, ok: bool = True) -> dict[str, pd.Series]:
    """The size indices from data/benchmark_indices.csv, the file the Dashboard reads (S154; the R2 index file this
    read before was not reachable everywhere, and the Breadth page then showed only the market index, found 21 Nov 2026)."""
    from src.loaders import benchmark_indices as bi
    frame = bi.read()
    names = {"nifty50": "Nifty 50", "midcap150": "Nifty Midcap 150", "smallcap250": "Nifty Smallcap 250", "microcap250": "Nifty Microcap 250"}
    out = {}
    for key, name in names.items():
        s = bi.series(key, frame=frame).dropna()
        if len(s):
            out[name] = s
    return out


# ── Full question sections, for the pages that own the detail ───────────────

_PAGE_CSS = """<style>
.qp{border-top:1px solid var(--c-ink);padding:14px 0 6px;margin:0 0 22px}
.qp h2{font-size:var(--fs-17)!important;font-weight:600!important;color:var(--c-ink)!important;margin:0 0 10px!important;padding:0!important;letter-spacing:0!important;scroll-margin-top:72px}
.qp-top{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:0 40px;margin-bottom:14px}
.qp-v{font-size:var(--fs-30);font-weight:600;line-height:1.1;margin:0 0 6px;color:var(--c-ink)}
.qp-v.up{color:var(--c-up)}.qp-v.down{color:var(--c-down)}
.qp-s{font-size:var(--fs-15);line-height:1.55;color:var(--c-text_2);margin:0 0 12px}
.qp h3{font-size:var(--fs-13)!important;font-weight:600!important;color:var(--c-ink)!important;margin:0 0 6px!important;padding:0!important}
.qp ul{margin:0 0 12px;padding-left:18px}.qp li{font-size:var(--fs-13);line-height:1.55;color:var(--c-text_2);margin:2px 0}
.qp li b{color:var(--c-ink);font-weight:600}
.qp table{width:100%;border-collapse:collapse;font-size:var(--fs-13);font-variant-numeric:tabular-nums;margin:4px 0 6px}
.qp th{font-size:var(--fs-12);font-weight:500;color:var(--c-muted);text-align:right;padding:6px 0 6px 12px;border-bottom:1px solid var(--c-rule_strong);white-space:nowrap}
.qp th:first-child,.qp th.l{text-align:left;padding-left:0}
.qp td{padding:8px 0 8px 12px;border-bottom:1px solid var(--c-rule);text-align:right;vertical-align:top;color:var(--c-ink)}
.qp td:first-child{text-align:left;padding-left:0}
.qp td.rule{text-align:left;color:var(--c-muted);font-size:var(--fs-12)}
.qp td.up{color:var(--c-up);font-weight:600}.qp td.down{color:var(--c-down);font-weight:600}.qp td.mid{color:var(--c-muted)}
.qp-tag{font-size:var(--fs-12);color:var(--c-muted);margin-left:6px}
.qp-note{font-size:var(--fs-12);color:var(--c-muted);margin:6px 0 0}
@media (max-width:900px){.qp-top{grid-template-columns:1fr}.qp td.rule,.qp th.rule{display:none}}
/* Phone: each evidence row stacks, the measure on a line of its own, then
   the bar, the figure and the vote (the four columns did not fit 375px). */
@media (max-width:700px){
  .qp table.ev thead{display:none}
  .qp table.ev tr{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:4px 12px;
    align-items:center;border-bottom:1px solid var(--c-rule);padding:8px 0}
  .qp table.ev td{border:0;padding:0}
  .qp table.ev td:first-child{grid-column:1 / -1}
  .qp table.ev td:nth-child(2){text-align:left!important}
  .rng{width:100%!important;max-width:160px}
}
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
        sub.append(f"12 months ago {_num(m.year_ago, m.unit)}")
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
        '<table class="ev"><thead><tr><th scope="col">The evidence</th><th scope="col" style="text-align:center">'
        'Where today sits, lowest to highest</th><th scope="col">Now</th><th scope="col">Vote</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
        '<p class="qp-note">Each measure votes by its cut-offs; primary measures count twice. The bar runs from '
        'the lowest reading in the price history the site holds to the highest; the shaded part is the middle '
        'half. The verdict is at an end when the weighted vote is 0.6 or more either way, leaning at 0.25.</p>'
        '</section>')


def sentence_case(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def size_trend_html(bench: pd.Series, size: dict[str, pd.Series], late=(), day=None, name: str = mq.MARKET) -> str:
    """The market (`name`: the index `bench` holds) and each size index against its 10-month average and 200D
    EMA, and its distance from the 52W high: now and a month ago. `late`: size indices
    without a close for `day`, the page's session; their row reads "–" (S148, S193 E)."""
    series = {name: bench.dropna(), **{k: v.dropna() for k, v in size.items()}}
    d = mq.anchor_dates(series[name].index)
    late = [k for k in late if k not in size]
    rows = []
    for name in late:
        series[name] = None
    for name, s in series.items():
        if s is None:
            rows.append(f"<tr><td>{html.escape(name)}</td>" + "<td>–</td>" * 6 + "</tr>")
            continue
        if len(s) < 60:
            continue
        cells = []
        for f in (mq.ten_month_today, mq.ema_gap, mq.from_high):
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
            '<p class="qp-note">The 10-month columns read the close on each day against the average of the last '
            'ten monthly closes, the month in progress counted at that close, as a monthly chart draws it; at a '
            'month-end it is the classic month-end reading. Points are per cent.'
            + (f' {html.escape(_fmt.closes_not_in(late, day))}' if late and day is not None else '') + '</p>')


def bucket_by_last_session(s: pd.Series, freq: str) -> pd.Series:
    """`s` bucketed by calendar period, each bucket dated by its last session.

    `to_period(freq).to_timestamp(how="end")` dates a bucket by the calendar
    period's last day, which is not the day the market last dealt in it:
    October 2026 closed on Friday 30 Oct at 21895.90 and `benchmarks.csv` has
    no 31 Oct row at all, yet the month-end bar read "31 Oct 2026" while the
    Dashboard called the same close "the 30 Oct month-end" (slot 10, TODO
    S117). Same fault the weekly chart had with "13 Nov 2026". The value of a
    bucket is unchanged - it is the same last close - only its label moves, on
    to a date the source actually carries.
    """
    per = s.index.to_period(freq)
    out = s.groupby(per).last()
    closed_on = s.index.to_series().groupby(per).last()
    out.index = pd.DatetimeIndex(closed_on.reindex(out.index).to_numpy()).normalize()
    return out


@st.cache_data(show_spinner=False, ttl=3600)
def _chart_series(key: str, _prices: pd.DataFrame, _bench: pd.Series, pit: bool = True):
    """The series behind the Breadth charts, computed once per price set."""
    from src.engine import pit_breadth
    past = pit_breadth.load("total_market") if pit else None
    share200 = pit_breadth.splice(mq._share_above_ema(_prices, 200), past, "above_200").dropna()
    nnh = pit_breadth.splice(mq._net_new_highs(_prices), past, "net_new_highs").dropna()
    weekly = nnh.groupby(nnh.index.to_period("W-FRI")).last()
    # Each bucket is dated its Friday, which for the week in progress is a date
    # that has not happened: on Monday 9 Nov 2026 the last bar read "5.5% on
    # 13 Nov 2026", four days ahead of the last session, while the table beside
    # it called the same +5.5 "this week". The monthly chart drops its
    # incomplete bucket, but dropping this one would leave the chart and that
    # table disagreeing, so the label is clamped to the last session instead.
    weekly.index = weekly.index.to_timestamp(how="end").normalize()
    last = nnh.index[-1].normalize()
    weekly.index = weekly.index.where(weekly.index <= last, last)
    return share200, weekly, nnh


def _moved(v: float) -> str:
    return f"rose {abs(v):.1f}%" if v > 0 else f"fell {abs(v):.1f}%" if v < 0 else "was flat"


def _chart_head(title: str, note: str) -> None:
    st.html(f'<div class="qp-ch"><h3 class="qp-ch-h">{html.escape(title)}</h3>'
            f'<p class="qp-note" style="margin:0 0 4px">{html.escape(note)}</p></div>')


def _dates(idx) -> list[str]:
    return [f"{d:%Y-%m-%d}" for d in pd.DatetimeIndex(idx)]


def _vals(s: pd.Series, nd: int = 2) -> list:
    return [None if pd.isna(v) else round(float(v), nd) for v in s.to_numpy()]


def _breadth_charts(bench: pd.Series, share200: pd.Series, weekly: pd.Series,
                    nnh: pd.Series | None = None, pit: bool = True, universe: str = "750",
                    name: str = mq.MARKET) -> None:
    """The index above the share above the 200D EMA (the Dashboard's chart, one spec), and net new highs
    week by week with its usual range: the site's chart kit (Breadth, 21 Nov 2026)."""
    from src.ui import dash_charts as dc
    from src.ui.views.dashboard_home_view import _breadth_spec
    if share200.empty:
        return
    end = share200.index[-1]
    since = end - pd.DateOffset(years=3)
    y0 = mq._on_or_before(bench.dropna().index, end - pd.DateOffset(years=1))
    b1 = mq._on_or_before(bench.dropna().index, end)
    s0 = mq._on_or_before(share200.index, end - pd.DateOffset(years=1))
    left, right = st.columns(2, gap="medium")
    with left:
        if y0 is not None and b1 is not None and s0 is not None:
            ret = (float(bench.loc[b1]) / float(bench.loc[y0]) - 1) * 100
            _chart_head(f"Over the year {the(name)} {_moved(ret)}; the share of stocks above their "
                        f"200D EMA went from {share200.loc[s0]:.0f}% to {share200.iloc[-1]:.0f}%",
                        "The index above, the share of the ranked stocks above their own 200D EMA below, "
                        "on one time axis. When the index rises while the lower line falls, fewer stocks "
                        "are carrying it. " + ("Members of each date, leavers included." if pit else
                                               "Today\u2019s members throughout."))
        spec = _breadth_spec(bench.dropna(), share200, end, universe)
        if spec:
            # 12M of three years, as on the Dashboard (S193 H); the index named and coloured as it is (S165).
            spec = {**spec, "range": dc.RANGE_BY_KIND["breadth"], "idx": name,
                    "idxc": "--s-market" if name == mq.MARKET else "--s-n500"}
            dc.render("breadth", spec, label=f"{sentence_case(the(name))} and the share of stocks above their 200D EMA",
                      note="Tap or drag for a date")
    with right:
        if not weekly.empty:
            w = weekly.loc[since:].dropna()
            daily = nnh if nnh is not None and len(nnh) else weekly
            a = mq._on_or_before(daily.index, end - pd.DateOffset(years=1))
            _chart_head(f"Net new 52W highs this week: {_fmt.signed(daily.iloc[-1], 1)}% of stocks"
                        + (f"; 12 months ago {_fmt.signed(daily.loc[a], 1)}%" if a is not None else ""),
                        "Each week, the stocks that made a new 52-week high in the seven days to its last session "
                        "less those that made a new low, each counted once, as a share of the stocks that could "
                        "make one, on daily closes throughout. Above zero, more stocks are making highs.")
            allw = weekly.dropna()
            q1, q3 = float(allw.quantile(0.25)), float(allw.quantile(0.75))
            # Three years sent, 12M shown (S193 H: recent movement opens on 12M), 3Y a chip away.
            dc.render("bars", {"values": _vals(w, 1), "labels": [f"{d:%b ’%y}" for d in w.index],
                               "dates": _dates(w.index), "range": {"default": "12M", "why": "lately", "chips": ["12M", "3Y"]},
                               "full": [f"week to {d:%-d %b %Y}" for d in w.index], "unit": "% of stocks, net new highs",
                               "dp": 1, "xn": 6, "height": 260, "band": [q1, q3, ""]},
                      label="Net new 52-week highs each week")
            st.html(f'<p class="qp-note">Shaded: the usual range since {allw.index[0]:%b %Y}, '
                    f'{_fmt.signed(q1, 1)} to {_fmt.signed(q3, 1)} (the middle half of all weeks).</p>')


# The one time-range chart that does not open on 12M (S193 H, owner 23 Nov 2026: "Go with your recommendation").
TEN_MONTH_RANGE = {"default": "3Y", "why": "fixed",
                   "note": "Monthly closes against a 10-month average: twelve points would show almost no history "
                           "of the line crossing the average, so it opens on three years"}


def _trend_charts(bench: pd.Series, size: dict[str, pd.Series], name: str = mq.MARKET) -> None:
    from src.ui import dash_charts as dc
    b = bench.dropna()
    # Every month dated by its last session; the month in progress is today's
    # close, so the chart ends on the page's session (staleness audit, 21 Nov
    # 2026: it ended on 30 Oct while the page read 20 Nov).
    m = bucket_by_last_session(b, "M")
    avg = m.rolling(10).mean()
    since = b.index[-1] - pd.DateOffset(years=3)
    today = mq.ten_month_today(b, b.index[-1])
    me, me_at = mq.ten_month_gap(b, b.index[-1]), mq.last_month_end(b, b.index[-1])
    left, right = st.columns(2, gap="medium")
    with left:
        if today is not None:
            side = lambda v: f"{abs(v):.1f}% {'above' if v >= 0 else 'below'}"  # noqa: E731
            month_end = ("" if me is None or me_at is None or me_at == b.index[-1] else
                         f"; at the {me_at:%-d %b} month-end it was {side(me)}")
            _chart_head(f"{sentence_case(the(name))} is {side(today)} its 10-month average on {b.index[-1]:%-d %b}{month_end}",
                        f"Monthly closes against the average of the last ten, {b.index[-1]:%B} at today's close. Above "
                        "the average the 10-month rule reads up; the classic rule reads only month-ends. Three years; "
                        "price only.")
        mm, aa = m.loc[since:], avg.loc[since:]
        dc.render("lines", {"dates": _dates(mm.index), "yfmt": "num", "range": TEN_MONTH_RANGE, "series": [
            {"name": f"{name}, monthly close ({b.index[-1]:%b}: today)", "values": _vals(mm, 1),
             "color": "s-market" if name == mq.MARKET else "s-n500"},
            {"name": "10-month average", "values": _vals(aa.reindex(mm.index), 1), "color": "muted", "dash": True}]},
            label=f"{sentence_case(the(name))}’s monthly closes and its 10-month average")
    with right:
        rel = {}
        for size_name, s in size.items():
            s = s.dropna()
            start = s.index[-1] - pd.DateOffset(years=1)
            s0 = mq._on_or_before(s.index, start)
            b0 = mq._on_or_before(b.index, start)
            if s0 is None or b0 is None:
                continue
            bb = b.reindex(s.loc[s0:].index, method="ffill")
            rel[size_name] = (s.loc[s0:] / float(s.loc[s0])) / (bb / float(b.loc[b0])) * 100
        if rel:
            last = {k: float(v.dropna().iloc[-1]) - 100 for k, v in rel.items() if len(v.dropna())}
            best, worst = max(last, key=last.get), min(last, key=last.get)
            _chart_head(f"Over 12 months, {best} did best against {the(name)} ({_fmt.signed(last[best], 1)} pts) and "
                        f"{worst} worst ({_fmt.signed(last[worst], 1)} pts)",
                        f"Each size index divided by {the(name)}, set to 100 at the start 12 months ago (the dashed line); above 100 it has "
                        f"done better. Price only. {_fmt.PTS_NOTE}")
            idx = sorted(set().union(*[set(v.dropna().index) for v in rel.values()]))
            from src.ui.tokens import LINE_CYCLE
            dc.render("lines", {"dates": _dates(idx), "yfmt": "num", "range": {"default": "12M", "why": "lately"},
                                "levels": [{"v": 100, "label": "", "color": "muted"}],
                                "series": [{"name": k, "values": _vals(v.reindex(idx).ffill(), 2), "color": LINE_CYCLE[i % len(LINE_CYCLE)][0],
                                            "dash": LINE_CYCLE[i % len(LINE_CYCLE)][1]}
                                           for i, (k, v) in enumerate(rel.items())]},
                      label=f"Each size index against {the(name)} over the year")


_CHART_CSS = """<style>
.qp-ch-h{font-family:var(--font-serif,serif)!important;font-weight:500!important;font-size:var(--fs-17)!important;
  line-height:1.3!important;color:var(--c-ink)!important;margin:6px 0 4px!important;padding:0!important;max-width:30em}
.qp-behind{font-family:var(--font-serif,serif);font-weight:400;font-size:var(--fs-24);color:var(--c-ink);margin:8px 0 0}
.qp-kick{margin:6px 0 0;font-size:var(--fs-12);font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--c-muted)}
.qp-title{margin:4px 0 6px!important;padding:0!important;font-family:var(--font-serif,serif)!important;font-weight:400!important;
  font-size:var(--fs-44)!important;line-height:1.1!important;max-width:36ch;color:var(--c-ink)}
.qp-sub{margin:0 0 6px;font-size:var(--fs-17);color:var(--c-text_2);max-width:80ch}
.qp-scroll td:first-child,.qp-scroll th:first-child{white-space:nowrap}
@media (max-width:640px){.qp-title{font-size:var(--fs-30)!important}}
</style>"""


def render_market_page_questions(rank_df: pd.DataFrame, prices: pd.DataFrame, bench: pd.Series | None,
                                  size: dict[str, pd.Series], pit: bool = True, universe: str = "750",
                                  name: str = mq.MARKET) -> bool:
    """The Market page's two questions, each followed by the charts behind
    its answer. `bench` is the market, `name` the index it holds (`market_close`).
    Returns False when there is not enough data to answer them."""
    if prices is None or prices.empty or bench is None or bench.dropna().empty:
        return False
    syms = [s for s in rank_df["Symbol"] if s in prices.columns]
    px = prices[syms]
    # The prices' session bounds the index, as on the Dashboard: after the close the live index has
    # today while the stocks and the size indices end on the last nightly sync, and the rule below then
    # emptied every size row (23 Nov 2026: 23 Nov against 20 Nov; CI failed Market requirements 7 and 12).
    bench = bench[bench.index <= prices.index.max()]
    if bench.dropna().empty:
        return False
    # One session for every index (S148): a size index without the market's last close reads "–". Its row
    # stays in the table, with a sentence naming it (S193 E); the answers and charts leave it out.
    from src.engine import dashboard_insights as di
    end = bench.dropna().index[-1]
    late = [k for k, v in size.items() if v is not None and len(v.dropna()) and not len(di.as_of(v, end))]
    size = {k: di.as_of(v, end) for k, v in size.items()}
    size = {k: v for k, v in size.items() if len(v)}
    industry = rank_df.drop_duplicates("Symbol").set_index("Symbol").get("Industry", pd.Series(dtype=str))
    key = "|".join([_columns_key(prices, syms), str(bench.dropna().index[-1]), ",".join(sorted(size)), _past_stamp()])
    breadth, trend, _ = _answers(key, px, industry, bench.dropna(), size, pit, name)
    # The title answers both questions; the page's name is the kicker (PAGE_DESIGN 2a, 21 Nov 2026).
    title = ("Market breadth" if breadth is None or trend is None else
             f"{breadth.verdict} participation; {trend.verdict[0].lower() + trend.verdict[1:]}.")
    st.html(_CSS + _PAGE_CSS + _CHART_CSS +
            '<div class="qp-head"><p class="qp-kick">Market</p>'
            f'<h1 class="qp-title">{html.escape(title)}</h1>'
            '<p class="qp-sub">Two questions, answered from the ranked stocks and NSE’s index closes: are most stocks '
            f'taking part, and is {html.escape(the(name))} in an uptrend. Then today’s charts.</p></div>'
            '<nav class="qp-nav" aria-label="On this page">'
            '<a href="#q-breadth">Are most stocks taking part?</a>'
            f'<a href="#q-trend">Is {html.escape(the(name))} in an uptrend?</a><a href="#q-charts">Today\'s charts</a></nav>')
    if breadth is not None:
        st.html(question_section_html(breadth, "breadth", "q-breadth")
                + '<p class="qp-behind">Behind the answer</p>')
        share200, weekly, nnh = _chart_series(key, px, bench.dropna(), pit)
        _breadth_charts(bench.dropna(), share200, weekly, nnh, pit, universe, name)
    if trend is not None:
        sec = question_section_html(trend, "trend", "q-trend")
        table = size_trend_html(bench, size, late=late, day=end, name=name)
        if table:
            # In its own scroller, as the heat table is: a seven-column table
            # was 472 px wide inside a 390 px column (design audit, 8 Nov 2026).
            sec = sec.replace("</section>", "<h3 style='margin-top:14px'>By size</h3>"
                              + f'<div class="qp-scroll" tabindex="0" role="region" aria-label="By size: {html.escape(the(name))} and each size index against its averages and 52W high">'
                              + f'{table}</div>' + "</section>")
        # Which index the trend reads, and why it reaches before Total Market's launch (S165).
        why = joined_note(bench.dropna(), name)
        if why:
            sec = sec.replace("</section>", f'<p class="qp-note">{html.escape(why)}</p></section>')
        st.html(sec + '<p class="qp-behind">Behind the answer</p>')
        _trend_charts(bench.dropna(), size, name)
    st.html('<p class="qp-note" style="margin:10px 0 18px">Today counts the stocks ranked today. Every earlier '
            'reading counts the stocks in Nifty Total Market on that date, including those that have since left it, '
            'from NSE’s first recorded list (29 Oct 2021); counting today’s members back in time made the past look '
            'about 5 points broader than it was.</p>' if pit else
            '<p class="qp-note" style="margin:10px 0 18px">Every reading counts the stocks this system ranks today, '
            'back in time: a members-of-the-day history is kept for the Nifty 750 only, so the past may read a few '
            'points broader than it was.</p>')
    return breadth is not None or trend is not None


# ── Sectors: "What is leading?" in full ─────────────────────────────────────

_SECTOR_CSS = """<style>
.qp-quad{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0 24px;margin:4px 0 14px}
.qp-quad div{border-top:1px solid var(--c-rule_strong);padding-top:8px}
.qp-quad b{display:block;font-size:var(--fs-13);font-weight:600;color:var(--c-ink);margin-bottom:4px}
.qp-quad b.up{color:var(--c-up)}.qp-quad b.down{color:var(--c-down)}
.qp-quad p{font-size:var(--fs-13);line-height:1.5;color:var(--c-text_2);margin:0 0 3px;display:flex;justify-content:space-between;gap:8px}
.qp-quad p span:last-child{font-variant-numeric:tabular-nums;color:var(--c-muted);white-space:nowrap}
.qp-quad p.qh{font-size:var(--fs-12);color:var(--c-muted);border-bottom:1px solid var(--c-rule);padding-bottom:3px;margin-bottom:5px}
.qp-heat{overflow-x:auto}
.qp-heat table{min-width:900px}
.qp-heat td{font-size:var(--fs-12);padding:6px 4px;text-align:center}
.qp-heat th{text-align:center;padding:6px 4px}
.qp-heat td:first-child,.qp-heat th:first-child{text-align:left;white-space:nowrap;padding-right:10px}
.qp-heat td.u2{background:var(--c-up_line_2);color:var(--c-ink)}.qp-heat td.u1{background:var(--c-up_tint)}
.qp-heat td.d1{background:var(--c-down_tint)}.qp-heat td.d2{background:var(--c-down_line_3);color:var(--c-ink)}
.qp-heat td.mtd{border-left:1px dashed var(--c-rule_strong)}
.qp-heat td.run,.qp-heat td.tot{text-align:right;font-weight:600}
.qp-heat th:nth-last-child(-n+2){text-align:right}
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
        return "–"
    return f"{abs(n)} {'ahead' if n > 0 else 'behind'}"


def run_example(months: pd.DataFrame) -> str:
    """A worked example of Run and 12 months, from the table's own numbers.

    Owner, 18 Nov 2026: "We should add one live example to explain it in
    page". The industry with the longest current run (the one the sentence
    above the table names), its completed months read back to the one that
    broke the run. Empty when no industry has a run.
    """
    if months is None or months.empty or "run" not in months:
        return ""
    longest = months["run"].abs().max()
    if not longest:
        return ""
    row = months[months["run"].abs() == longest].iloc[0]
    name = months[months["run"].abs() == longest].index[0]
    n = int(row["run"])
    side = "ahead" if n > 0 else "behind"
    completed = [c for c in months.columns if c not in ("run", "total") and not c.endswith("so far")]
    inside = completed[len(completed) - abs(n):][::-1]          # newest first

    def short(col: str) -> str:
        return col.split()[0]

    parts = [f"{short(c)} {_fmt.signed(row[c], 1)}" for c in inside]
    listed = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    text = (f"For example, {name}: {listed} points, "
            f"{'all ' if len(parts) > 1 else ''}{'ahead of' if n > 0 else 'behind'} all ranked stocks")
    before = completed[: len(completed) - abs(n)]
    if before and pd.notna(row[before[-1]]):
        other = "behind" if n > 0 else "ahead"
        text += (f"; {short(before[-1])} was {_fmt.signed(row[before[-1]], 1)}, {other}, "
                 f"so the count stops there and Run reads {abs(n)} {side}")
    else:
        text += f", so Run reads {abs(n)} {side}"
    if pd.notna(row.get("total")):
        text += (f". Its 12 months, {_fmt.signed(row['total'], 1)}, is the twelve completed "
                 f"months added up")
    return text + "."


def _rel_bars_html(sec: pd.DataFrame) -> str:
    """Each industry's six months against all ranked stocks as a bar from zero,
    with a dot for the last month: the quadrants as a picture."""
    if sec is None or sec.empty:
        return ""
    lim = max(5.0, float(sec[["rel_6m", "rel_1m"]].abs().max().max()))
    x = lambda v: 50 + max(-50.0, min(50.0, v / lim * 50))  # noqa: E731
    rows = []
    for r in sec.sort_values("rel_6m", ascending=False).itertuples():
        left, width = (50, x(r.rel_6m) - 50) if r.rel_6m >= 0 else (x(r.rel_6m), 50 - x(r.rel_6m))
        tone = "up" if r.rel_6m >= 0 else "down"
        rows.append(
            f'<div class="rb-row"><span class="rb-n">{html.escape(r.Industry)}</span>'
            f'<span class="rb-t"><i class="rb-z"></i><i class="rb-b {tone}" style="left:{left:.1f}%;width:{width:.1f}%"></i>'
            f'<i class="rb-d" style="left:{x(r.rel_1m):.1f}%" title="Last month {_num(r.rel_1m, "pts")}"></i></span>'
            f'<span class="rb-v">{_num(r.rel_6m, "pts")}<small> · {_num(r.rel_1m, "pts")}</small></span></div>')
    return ('<h3 style="margin-top:6px">Six months against all ranked stocks, and the last month</h3>'
            '<p class="qp-note" style="margin:0 0 8px">Bars: the industry\'s six-month return less all ranked '
            'stocks\', each equal-weighted. Rings: the last month. Right of the line is ahead of all ranked stocks.</p>'
            '<style>.rb-row{display:grid;grid-template-columns:minmax(0,260px) minmax(0,1fr) 120px;gap:12px;'
            'align-items:center;padding:3px 0;font-size:var(--fs-13)}.rb-n{color:var(--c-text_2);white-space:nowrap;'
            'overflow:hidden;text-overflow:ellipsis}.rb-t{position:relative;height:14px}'
            '.rb-z{position:absolute;left:50%;top:-2px;bottom:-2px;width:1px;background:var(--c-rule_strong)}'
            '.rb-b{position:absolute;top:3px;height:8px;border-radius:1px}.rb-b.up{background:var(--c-up)}'
            '.rb-b.down{background:var(--c-down)}.rb-d{position:absolute;top:1px;width:12px;height:12px;'
            'margin-left:-6px;border-radius:50%;border:2px solid var(--c-ink);background:var(--c-white);box-sizing:border-box}'
            '.rb-v{text-align:right;font-variant-numeric:tabular-nums;color:var(--c-ink)}'
            '.rb-v small{color:var(--c-muted);font-size:var(--fs-12)}'
            '@media (max-width:700px){.rb-row{grid-template-columns:110px minmax(0,1fr) 84px}}</style>'
            f'<div role="img" aria-label="Industries by six months against all ranked stocks, with the last month" '
            f'style="margin-bottom:24px">{"".join(rows)}</div>')


def leaders_section_html(ld: mq.Leaders, months: pd.DataFrame, market_name: str = mq.MARKET) -> str:
    sec = ld.sectors
    both = sec[sec["group"] == "ahead on both"]["Industry"].head(3).tolist()
    best = max((x for x in ld.size if x[1] is not None), key=lambda x: x[1], default=None)
    verdict = "; ".join([x for x in [best[0] if best else "", ", ".join(both)] if x]) or "No clear leader"

    # Size leadership first (S147): the equal-weighted ranked market against
    # the market index (`market_name`). Below zero, large companies led; the industries above are
    # read against that market, so this gap is not in them.
    gap6, gap1 = getattr(ld, "market_vs_index", (None, None))
    size_rows = (f'<tr><td>All ranked stocks, equal weight</td><td class="{_t(gap6)}">{_num(gap6, "pts")}</td>'
                 f'<td class="{_t(gap1)}">{_num(gap1, "pts")}</td></tr>' if gap6 is not None or gap1 is not None else "")
    size_rows += "".join(
        f'<tr><td>{html.escape(n)}</td><td class="{_t(r6)}">{_num(r6, "pts")}</td>'
        f'<td class="{_t(r1)}">{_num(r1, "pts")}</td></tr>' for n, r6, r1 in ld.size)
    size_html = (f'<h3>By size, against {html.escape(market_name)}</h3><table><thead><tr><th scope="col">Index</th>'
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
    bars_html = _rel_bars_html(sec)
    quad_html = ('<h3>Industries by six months and one month</h3>'
                 '<p class="qp-note" style="margin:0 0 6px">Each figure is the industry\'s return less all '
                 'ranked stocks\', each equal-weighted, in points: over six months, then over one month.</p>'
                 f'<div class="qp-quad">{"".join(quads)}</div>' + bars_html)

    heat_html = ""
    if months is not None and not months.empty:
        cols = [c for c in months.columns if c not in ("run", "total")]
        longest = months["run"].abs().max()
        lead_run = months[months["run"].abs() == longest]
        run_line = ""
        if longest and len(lead_run):
            n = int(lead_run["run"].iloc[0])
            run_line = (f'<p class="qp-s">{html.escape(lead_run.index[0])} has {"beaten" if n > 0 else "trailed"} '
                        f'all ranked stocks in each of the last {abs(n)} completed months, the longest current run.</p>')
        head = "".join(f'<th scope="col">{html.escape(c.replace(" 20", " ’"))}</th>' for c in cols)
        body = []
        for name, r in months.iterrows():
            cells = "".join(
                f'<td class="{_heat_cls(r[c])}{" mtd" if c.endswith("so far") else ""}">'
                f'{"–" if not pd.notna(r[c]) else _fmt.signed(r[c], 1)}</td>' for c in cols)
            body.append(f'<tr><td>{html.escape(name)}</td>{cells}<td class="run">{_run_text(int(r["run"]))}</td>'
                        f'<td class="tot {_t(r["total"])}">{_num(r["total"], "pts")}</td></tr>')
        example = run_example(months)
        heat_html = ('<h3>Month by month against all ranked stocks</h3>' + run_line +
                     '<div class="qp-heat"><table><thead><tr><th scope="col">Industry</th>' + head +
                     '<th scope="col">Run</th><th scope="col">12 months</th></tr></thead>'
                     f'<tbody>{"".join(body)}</tbody></table></div>'
                     '<p class="qp-note">Each cell is the industry\'s return in that month less all ranked '
                     'stocks\', each equal-weighted, in points; deeper shades are 4 points or more. The last column before Run '
                     'is the month so far. Run counts completed months in a row on the same side.</p>'
                     + (f'<p class="qp-note">{html.escape(example)}</p>' if example else ""))

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
            '<p class="qp-note">Industries are NSE\'s, five or more ranked stocks each, counted over the stocks '
            'ranked today. Each industry is an equal-weighted index of its stocks and is compared with the '
            'same index of every ranked stock, so a rally led by large companies does not read as every '
            f'industry lagging; that gap is the first row of By size. The size indices are read against {html.escape(market_name)}, '
            'company size against company size. The leaderboard below ranks by the typical (median) stock; '
            'everything else here uses the equal-weighted average.</p></section>')


@st.cache_data(show_spinner=False, ttl=3600)
def _leaders_full(key: str, _prices: pd.DataFrame, _industry: pd.Series, _bench: pd.Series,
                  _size: dict[str, pd.Series], market_name: str = mq.MARKET):
    return (mq.leaders_answer(_prices, _industry, _bench, _size, market_name=market_name),
            mq.industry_months(_prices, _industry, _bench))


def render_leaders_section(rank_df: pd.DataFrame, prices: pd.DataFrame, bench: pd.Series | None,
                           size: dict[str, pd.Series], market_name: str = mq.MARKET) -> bool:
    if prices is None or prices.empty or bench is None or bench.dropna().empty:
        return False
    syms = [s for s in rank_df["Symbol"] if s in prices.columns]
    px = prices[syms]
    # The prices' session bounds the index, as on the Dashboard: after the close the live index has
    # today while the stocks and the size indices end on the last nightly sync, and the rule below then
    # emptied every size row (23 Nov 2026: 23 Nov against 20 Nov; CI failed Market requirements 7 and 12).
    bench = bench[bench.index <= prices.index.max()]
    if bench.dropna().empty:
        return False
    # One session for every index (S148): a size index without the market's last close reads "–".
    from src.engine import dashboard_insights as di
    size = {k: di.as_of(v, bench.dropna().index[-1]) for k, v in size.items()}
    size = {k: v for k, v in size.items() if len(v)}
    industry = rank_df.drop_duplicates("Symbol").set_index("Symbol").get("Industry", pd.Series(dtype=str))
    key = "|".join([_columns_key(prices, syms), str(bench.dropna().index[-1]), ",".join(sorted(size)), _past_stamp(), "full"])
    leaders, months = _leaders_full(key, px, industry, bench.dropna(), size, market_name)
    if leaders is None:
        return False
    st.html(leaders_section_html(leaders, months, market_name))
    return True


# ── The market strip: each index's day, its last three months, its month ────
