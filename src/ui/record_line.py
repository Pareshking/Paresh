"""One measure against its own record (S237 G3, tipsheet's valuation and breadth pages): the figure now, its usual
range (the middle half of the days held, as the site's other bands), the highest and lowest day, a year ago, and
the line chart that shows them, the band shaded and the two extremes labelled.
"""
from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from src.engine import indices_page as ip
from src.ui import formats as _fmt


def facts(series: pd.Series, as_of: pd.Timestamp | None = None, since: pd.Timestamp | None = None,
          min_days: int = 250) -> dict | None:
    """The record's readings; None when it holds fewer than `min_days` days."""
    r = series.dropna()
    if since is not None:
        r = r[r.index >= since]
    if as_of is not None:
        r = r[r.index <= as_of]
    if len(r) < min_days:
        return None
    end = r.index[-1]
    y1 = ip.on_or_before(r, ip.months_back(end, 12))
    return {"now": float(r.iloc[-1]), "day": end, "q25": float(r.quantile(.25)), "q75": float(r.quantile(.75)),
            "hi": float(r.max()), "hi_d": r.idxmax(), "lo": float(r.min()), "lo_d": r.idxmin(),
            "ago": None if y1 is None else float(r[y1]),
            "since": r.index[0], "series": r}


def words(x: dict, fmt: Callable[[float], str], since_words: str) -> str:
    """"Below its usual range of 21.0 to 22.9, the middle half of days since 31 Mar 2021. The highest was 33.6, in
    April 2021; the lowest 18.9, in June 2022. Down from 22.8 a year ago." Compared as shown, so a figure that
    reads the same is "level"."""
    now, lo, hi = (fmt(v) for v in (x["now"], x["q25"], x["q75"]))
    shown = lambda v: float(fmt(v).rstrip("%"))  # noqa: E731
    n, a, b = shown(x["now"]), shown(x["q25"]), shown(x["q75"])
    where = "Inside its usual range" if a <= n <= b else "Below its usual range" if n < a else "Above its usual range"
    out = (f"{where} of {lo} to {hi}, the middle half of days since {since_words}. "
           f"The highest was {fmt(x['hi'])}, in {x['hi_d']:%B %Y}; the lowest {fmt(x['lo'])}, in {x['lo_d']:%B %Y}.")
    if x["ago"] is not None:
        g = shown(x["ago"])
        out += " Level with a year ago." if g == n else f" {'Down' if n < g else 'Up'} from {fmt(x['ago'])} a year ago."
    return out


def chart_spec(x: dict, name: str, fmt: Callable[[float], str], yfmt: str = "num", range_: dict | None = None,
               nd: int = 2) -> dict:
    """The "lines" spec: the record as one ink line, the usual range shaded and named, the extremes labelled."""
    r = x["series"]
    spec = {"dates": [f"{d:%Y-%m-%d}" for d in r.index], "yfmt": yfmt,
            "series": [{"name": name, "color": "ink", "values": [round(float(v), nd) for v in r], "width": 1.6}],
            "bands": [{"from": round(x["q25"], nd), "to": round(x["q75"], nd), "color": "fill",
                       "label": f"usual range, {fmt(x['q25'])} to {fmt(x['q75'])}"}],
            "marks": [{"date": f"{x['hi_d']:%Y-%m-%d}", "v": round(x["hi"], nd), "label": f"{fmt(x['hi'])}, {x['hi_d']:%b %Y}"},
                      {"date": f"{x['lo_d']:%Y-%m-%d}", "v": round(x["lo"], nd), "label": f"{fmt(x['lo'])}, {x['lo_d']:%b %Y}",
                       "below": True}],
            "levels": []}
    if range_ is not None:
        spec["range"] = range_
    return spec


def table(x: dict, fmt: Callable[[float], str]) -> list[list[str]]:
    rows = [["Now", fmt(x["now"])], ["Usual range", f"{fmt(x['q25'])} to {fmt(x['q75'])}"],
            [f"Highest, {_fmt.date(x['hi_d'])}", fmt(x["hi"])], [f"Lowest, {_fmt.date(x['lo_d'])}", fmt(x["lo"])]]
    return rows + ([["A year ago", fmt(x["ago"])]] if x["ago"] is not None else [])
