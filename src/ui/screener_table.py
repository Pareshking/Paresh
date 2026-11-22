"""The Screener's ranking table, as drawn in the approved light design.

One HTML table serves the desktop and the phone. It lives in an st.iframe so
it can sort by column and keep its header and first two columns pinned; below
640px its own CSS turns it into the compact phone list (rank, stock and its
industry, a 60-session line, price and 3M), because Streamlit cannot tell
Python how wide the screen is.

Every row of the view is in the table -- sorting a page of 25 would sort the
wrong 25 -- and the frame is tall enough to show about 25 rows at once; the
rest scroll inside it.

Three column sets are drawn from one registry: Executive, Core and Full Quant.
The phone list shows the industry under the symbol; on a desktop the Index and
Industry columns carry it.

Colour follows one rule: a figure whose SIGN is the signal (a return, a
Sharpe, the distance from the 50 EMA, a rank change) is green above zero and
red below, and always carries a + or − so the colour is never the only cue. A
distance from a peak (drawdown, % from the 52-week high or the all-time high)
is never above zero, so colouring it would paint the whole column red: it is
plain. Pass and fail are ✓ and ✗, not coloured dots.
"""
from __future__ import annotations

import json
import re

from html import escape as _esc

import numpy as np
import pandas as pd
import streamlit as st
from src.ui.tokens import resolve

from src.ui.system_param import stock_href
from src.ui.system_param import suffix as system_suffix
from src.ui.theme import _spark_window_key, is_tick_true
from src.ui import formats as _fmt
from src.ui.industry_names import short_industry

# Readable names for the index tags the ranking stores.
INDEX_NAMES = {
    "N50": "Nifty 50", "NN50": "Next 50", "MID150": "Midcap 150",
    "SMALL250": "Smallcap 250", "MICRO250": "Microcap 250",
    "NANO250": "Nano Cap", "NANO": "> ₹2,000 Cr",      # S175: the Nifty 1000's other 250; the ₹2,000 Cr list
}

# (key, header, sort type). One registry; Executive, Core and Quant are column
# sets drawn from it, so a column looks and sorts the same in every view. The
# phone list keeps only rank, stock, path and the price cell, which carries the
# 3M return under the price.
PERIOD_WINDOWS = (1, 3, 6, 9, 12)
# The model book's lines (TRACK_RECORD_CONFIG: top_n 20, buffer_n 40,
# high_pct 0.80), drawn under those qualified places in rank order.
BUY_CUT, KEEP_CUT, NEAR_HIGH_GAP_PCT = 20, 40, 20
_ALL = {
    "rank": ("Rank", "num"), "stock": ("Stock", "text"), "price": ("Price", "num"),
    # Rank among the 750 three months and a month ago, read on the session on or
    # before that date: the date every page's rank trail uses (S154; Screener
    # decision A, 21 Nov 2026). They replace the ▲/▼ change columns (PAGE_DESIGN
    # §2: 3M ago, 1M ago and now side by side, as numbers).
    "p3": ("3M ago", "num"), "p1": ("1M ago", "num"),
    # Places moved in a month: shown only for Big movers, which sorts on it.
    "d1m": ("Places, 1M", "num"),
    # S87 (owner, 7 Nov): place among the stocks that pass both filters (the
    # list the book buys from: top 20, kept while in the top 40), now and on the
    # trail's two dates, from the Dashboard's own function (`rank_trails`), and
    # the composite score the ranking is sorted by.
    "q3": ("3M ago", "num"), "q1": ("1M ago", "num"),
    "qrank": ("Now", "num"), "score": ("Score", "num"),
    # "NSE index": the one column where an index's short form is allowed; NSE's 22 groups are sectors (glossary 2, 3).
    "idx": ("NSE index", "text"), "ind": ("Sector", "text"),
    "mcap": ("Market cap, Cr", "num"),
    "hi": ("From 52W high", "num"), "ath": ("From all-time high", "num"), "ema": ("vs 50D EMA", "num"),
    "vol": ("Volume", "text"),
    "above": ("Above 50D EMA", "num"), "near": ("Near 52W high", "num"), "athf": ("At all-time high", "num"),
    "nh1": ("New highs 1M", "num"), "nh3": ("New highs 3M", "num"),
    "stop": ("Stop loss", "num"), "chand": ("Chandelier exit", "num"),
    "gap": ("Price gap", "text"), "ffill": ("Filled", "num"), "hz": ("Horizons", "num"),
    "spark": ("60D", None),
    # The Watchlist's plan column: what the model book does with the stock at the
    # next rebalance; its header is that day ("30 Nov"), passed in by the page.
    "plan": ("Plan", "text"),
}
for _w in PERIOD_WINDOWS:
    _ALL[f"r{_w}"] = (f"{_w}M return", "num")
    _ALL[f"sh{_w}"] = (f"{_w}M Sharpe", "num")
    _ALL[f"dd{_w}"] = (f"{_w}M max drawdown", "num")   # glossary 8
# Columns where 1 is best: a first click sorts them smallest first.
_RANK_KEYS = ("rank", "p3", "p1", "q3", "q1", "qrank")

# Full Quant is the master: the research view's own columns, in its own order.
# Executive and Core are this set with columns hidden, nothing else. Sharpe is
# a quant-view statistic (not comparable like a return) and the drawdown shown
# outside Quant is the 3M one.
_QUANT_KEYS = (
    ("rank", "stock", "price", "p3", "p1", "q3", "q1", "qrank", "score", "idx", "ind", "mcap")
    + tuple(f"{k}{w}" for w in PERIOD_WINDOWS for k in ("r", "sh", "dd"))
    + ("hi", "ath", "ema", "vol", "above", "near", "athf", "nh1", "nh3", "stop", "chand",
       "gap", "ffill", "hz", "spark")
)
_CORE_KEYS = ("rank", "stock", "price", "p3", "p1", "qrank", "idx", "ind", "mcap",
              "r1", "r3", "r6", "r12", "dd3", "hi", "ema", "vol", "above", "near", "spark")
# The Watchlist (S182, mock-up approved 22 Nov 2026): Core with the qualified place
# 3M and 1M ago beside "Now" and the plan's word after it. Its phone list keeps the
# stock, the price, the qualified place and the plan (the page names what it drops).
_WATCH_KEYS = ("rank", "stock", "price", "p3", "p1", "q3", "q1", "qrank", "plan", "idx", "ind", "mcap",
               "r1", "r3", "r6", "r12", "dd3", "hi", "ema", "vol", "above", "near", "spark")
_WATCH_PHONE = {"stock", "price", "qrank", "plan"}
_EXEC_KEYS = ("rank", "stock", "price", "p1", "qrank", "idx", "ind", "r3", "r12", "dd3",
              "hi", "ema", "above", "near", "spark")
# Group labels over the columns, in order.
# Sentence case, as every other table's labels (PAGE_DESIGN §3); the pinned
# rank and stock carry no group label.
_QUANT_GROUPS = (
    ("", ("rank", "stock", "price")),
    ("Rank before", ("p3", "p1", "d1m")),
    ("Qualified", ("q3", "q1", "qrank")),
    ("Plan", ("plan",)),
    ("Score", ("score",)),
    ("Company", ("idx", "ind", "mcap")),
    *((f"{w} month{'s' if w > 1 else ''}", (f"r{w}", f"sh{w}", f"dd{w}")) for w in PERIOD_WINDOWS),
    ("Filters and highs", ("hi", "ath", "ema", "vol", "above", "near", "athf", "nh1", "nh3")),
    ("Exits", ("stop", "chand")),
    ("Data health", ("gap", "ffill", "hz")),
    ("Trend", ("spark",)),
)
_WINDOW_GROUPS = {f"{w} month{'s' if w > 1 else ''}" for w in PERIOD_WINDOWS}
_RISK_KEYS = ("stop", "chand")
# A ranking built from closing prices carries no ATR, so those columns would be
# an em dash on every row; they are dropped with their headers.
_ATR_COLUMNS = ("ATR", "ATR %", "Stop Loss", "Chand Exit")

ROW_PX = 36   # Ledger density (owner, 7 Nov); the phone list keeps 44 for touch
PHONE_ROW_PX = 36   # Ledger density (owner, 7 Nov); the phone list keeps 44 for touch
VISIBLE_ROWS = 25
GROUP_ROW_PX = 40   # a heading row of the Watchlist's groups (14 + 20 + 6 px)


def columns_for(density: str, available=None, movers: bool = False) -> list[tuple[str, str, str | None]]:
    """The columns of a view. `available` is the ranking's column names, used to
    drop the ATR-derived ones when the ranking carries none. `movers` adds the
    places moved in a month after the past ranks (Big movers sorts on it)."""
    d = str(density)
    keys = _EXEC_KEYS if d.startswith("Executive") else (
        _QUANT_KEYS if d.startswith(("Full", "Quant")) else
        _WATCH_KEYS if d.startswith("Watchlist") else _CORE_KEYS)
    if available is not None and not any(c in available for c in _ATR_COLUMNS):
        keys = tuple(k for k in keys if k not in _RISK_KEYS)
    if available is not None and "Qualified (-1M)" not in available:
        keys = tuple(k for k in keys if k not in ("q3", "q1"))
    if movers:
        at = keys.index("p1") + 1 if "p1" in keys else 3
        keys = keys[:at] + ("d1m",) + keys[at:]
    return [(k, *_ALL[k]) for k in keys]


def column_count(density: str, available=None) -> int:
    return len(columns_for(density, available))


def column_groups(keys: list[str]) -> list[tuple[str, int, bool]]:
    """The group row over `keys`: (label, colspan, pinned), left to right.

    Built from RUNS of neighbouring columns. Counting each group's columns
    wherever they sit put "3M" over 3M and 6M Ret and "12M" over Max DD 3M in
    Core, whose order is r1 r3 r6 r12 dd3 (owner, 7 Nov). Where a view shows
    only part of the per-window groups (Executive, Core), those columns are
    grouped as Returns and Risk instead. Rank and Symbol are pinned when the
    table scrolls sideways, so their group label is its own pinned cell.
    """
    group_of = {k: label for label, ks in _QUANT_GROUPS for k in ks}
    windowed = {label: ks for label, ks in _QUANT_GROUPS if label in _WINDOW_GROUPS}
    partial = any(not set(ks) <= set(keys) for ks in windowed.values())

    def label(k: str) -> str:
        g = group_of.get(k, "")
        if g in windowed and partial:
            return "Returns" if k.startswith("r") else "Risk"
        return g

    pin = 2 if list(keys[:2]) == ["rank", "stock"] else 0
    out: list[tuple[str, int, bool]] = []
    if pin:
        out.append((label("rank"), pin, True))
    for i, k in enumerate(keys[pin:], pin):
        lab = label(k)
        # The pinned cell already names the Identity group, so the rest of it
        # (CMP) is an unlabelled cell rather than the same word twice.
        if pin and i == pin and lab == label("rank"):
            lab = ""
        if out and not out[-1][2] and out[-1][0] == lab:
            out[-1] = (lab, out[-1][1] + 1, False)
        else:
            out.append((lab, 1, False))
    return out


@st.cache_data(show_spinner=False, ttl=3600)
def _year_paths(window_key: str, _prices: pd.DataFrame) -> dict[str, tuple[str, bool]]:
    """Each symbol's closes over the window (the last 60 sessions, the "60D"
    column) as the line's heights, built once per window.

    At most about 50 points, as much as an 88px line can show. Sent as
    whole-pixel heights ("12,10,13,...") and drawn by the table's script
    (audit F62): the 750 inline polylines were 563 KB of a 2.4 MB frame.
    """
    out: dict[str, tuple[str, bool]] = {}
    step = max(1, len(_prices) // 50)
    for col in _prices.columns:
        s = pd.to_numeric(_prices[col], errors="coerce").dropna().to_numpy(dtype="float64")
        if len(s) < 5:
            continue
        pts = np.append(s[::step], s[-1]) if (len(s) - 1) % step else s[::step]
        lo, hi = float(pts.min()), float(pts.max())
        span = (hi - lo) or 1.0
        ys = ",".join(str(int(round(24 - (v - lo) / span * 21))) for v in pts)
        out[str(col)] = (ys, bool(s[-1] >= s[0]))
    return out


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(f) else f


def _signed(v: float, digits: int = 1, plus: bool = True) -> str:
    """A number with a true minus sign (U+2212), and + when `plus`.

    One signer for the whole site (duplicate audit, 10 Nov 2026): this was a
    line-for-line copy of formats.signed."""
    return _fmt.signed(v, digits, plus=plus)


def _price_html(v: float | None) -> str:
    """The price with paise, and beside it the price rounded to the rupee for
    the phone's compact list (rounded, not cut: ₹2,373.50 reads ₹2,374)."""
    if v is None:
        return "–"
    return (f'<span class="px-d">{_fmt.price(v)}</span>'
            f'<span class="px-m">{_fmt.price(v)}</span>')


def _peak_cell(v: float | None, title: str = "") -> str:
    """% below a peak: plain, never coloured; "New high" at the peak itself."""
    if v is None:
        return '<td class="n muted" data-v="">–</td>'
    txt = "New high" if v >= 0 else f"{_signed(v, plus=False)}%"
    return f'<td class="n" data-v="{v}"{title}>{txt}</td>'


def _pct_cell(v: float | None, cls_extra: str = "") -> tuple[str, str]:
    if v is None:
        return f'<td class="n muted {cls_extra}" data-v="">–</td>', ""
    cls = "pos" if v > 0 else "neg" if v < 0 else ""
    # Signed from the ROUNDED value, so −0.04% is "0.0%" and not "−0.0%".
    txt = _fmt.pct(v)
    return f'<td class="n {cls} {cls_extra}" data-v="{v:.6f}">{txt}</td>', txt


def _tick(on: bool, yes: str = "Yes", no: str = "No") -> str:
    """Pass or fail as a glyph that does not need colour vision to read."""
    return (f'<span class="tick yes" title="{yes}">✓</span>' if on
            else f'<span class="tick no" title="{no}">✗</span>')


# A sort key needs no more than 8 significant digits: a raw float's 17
# (data-v="0.16724790293698052") were ~120 KB of the 2 MB table (20 Nov 2026,
# TODO S141). Shown text is never touched; only the attribute the header sort reads.
_LONG_KEY = re.compile(r'data-v="(-?\d+\.\d{9,}(?:[eE][-+]?\d+)?)"')


def _short_sort_keys(html: str) -> str:
    return _LONG_KEY.sub(lambda m: f'data-v="{float(m.group(1)):.8g}"', html)


def _row_html(row: dict, cols: list, paths: dict, highlight: str = "") -> str:
    sym = str(row.get("Symbol", ""))
    sym_s = _esc(sym)
    is_hl = bool(highlight) and sym.upper() == highlight.upper()
    name = str(row.get("Company Name") or "").strip()
    ind = str(row.get("Industry") or "").strip()
    tag = str(row.get("Indices") or "").split(",")[0].strip()
    # Sector and index first, company last: the symbol already names the
    # stock, and the name is the part that can be cut off when it is long.
    # The phone list's only line under the symbol, cut to ~130px: the
    # industry alone fits, where "industry · index · company" was cut in the
    # middle of the index name. The company name is the link's tooltip.
    sub = short_industry(ind)
    rank = _num(row.get("Rank"))
    cmp_v = _num(row.get("CMP"))
    r3 = _num(row.get("3M Return"))
    cells: dict[str, str] = {}

    cells["rank"] = (f'<td class="c-rank" data-v="{rank if rank is not None else ""}">'
                     f'{int(rank) if rank is not None else "–"}</td>')
    qr = _num(row.get("Qualified Rank"))
    # "Out": not among the qualified that day, the word the Dashboard's rank
    # trail uses for the same thing (S154).
    for key, col, cls in (("q3", "Qualified (-3M)", " past"), ("q1", "Qualified (-1M)", " past"),
                          ("qrank", "Qualified Rank", "")):
        q = _num(row.get(col))
        cells[key] = (f'<td class="n{cls}" data-v="{"" if q is None else q}">'
                      f'{"Out" if q is None else int(q)}</td>')
    for key, col in (("p3", "Rank (-3M)"), ("p1", "Rank (-1M)")):
        p_ = _num(row.get(col))
        cells[key] = (f'<td class="n past" data-v="{"" if p_ is None else p_}">'
                      f'{"–" if p_ is None else int(p_)}</td>')
    # The book's two lines, named on the row they fall under (rank order only).
    # A page that writes its own note under each name (the Watchlist: how far the
    # stock is from its line) names the lines there instead.
    place_note = str(row.get("Place Note") or "").strip()
    cut_txt = "" if place_note else (
        "The book buys to here: the 20th qualified" if qr == BUY_CUT else
        "A holding is kept to here: the 40th qualified" if qr == KEEP_CUT else "")
    sc = _num(row.get("Score"))
    cells["score"] = (f'<td class="n" data-v="{"" if sc is None else sc}">'
                      f'{"–" if sc is None else f"{sc:.2f}"}</td>')
    held = bool(row.get("Held"))
    cells["stock"] = (
        f'<td class="c-stock" data-v="{sym_s}"><a href="{stock_href(sym)}" '
        f'data-stock="{sym_s}" title="Open {_esc(name) if name and name != "nan" else sym_s}"><span class="sym">{sym_s}'
        f'{"<em class=me>This stock</em>" if is_hl else ""}'
        f'{"<em class=held title=\'In the model book\'>Held</em>" if held else ""}</span>'
        f'{f"<span class=pnote>{_esc(place_note)}</span>" if place_note else ""}'
        f'<span class="sub">{_esc(sub)}</span>'
        f'{f"<span class=cutnote>{cut_txt}</span>" if cut_txt else ""}</a></td>'
    )
    word = str(row.get("Plan") or "").strip()
    tone = {"Buy": " pos", "Sell": " neg"}.get(word, "")
    cells["plan"] = f'<td class="c-plan{tone}" data-v="{_esc(word)}">{_esc(word) or "–"}</td>'
    r3_txt = "–" if r3 is None else f"{'+' if r3 > 0 else '−' if r3 < 0 else ''}{abs(r3) * 100:.1f}%"
    r3_cls = "" if r3 is None else ("pos" if r3 > 0 else "neg" if r3 < 0 else "")
    cells["price"] = (
        f'<td class="n c-price" data-v="{cmp_v if cmp_v is not None else ""}">'
        # Paise on a desktop (audit F66); the phone's compact list hides them,
        # where the extra three characters pushed the trend line off.
        f'{_price_html(cmp_v)}'
        f'<span class="m-only {r3_cls}">{r3_txt} 3M</span></td>'
    )
    d = _num(row.get("Rank Δ 1M"))
    cells["d1m"] = ('<td class="n" data-v="">–</td>' if d is None else
                    f'<td class="n {"pos" if d > 0 else "neg" if d < 0 else ""}" data-v="{d}">'
                    f'{_signed(d, 0) if d else "0"}</td>')
    mc = _num(row.get("Market Cap (Cr)"))
    cells["mcap"] = (f'<td class="n" data-v="{"" if mc is None else mc}">'
                     f'{"–" if mc is None else _fmt.inr(mc)}</td>')
    for w in PERIOD_WINDOWS:
        cells[f"r{w}"] = _pct_cell(_num(row.get(f"{w}M Return")))[0]
        sh = _num(row.get(f"{w}M Sharpe"))
        sh_cls = "" if sh is None else "pos" if sh > 0 else "neg" if sh < 0 else ""
        cells[f"sh{w}"] = (f'<td class="n {sh_cls}" data-v="{"" if sh is None else sh}">'
                           f'{"–" if sh is None else _signed(sh, 2, plus=False)}</td>')
        dd = _num(row.get(f"Max DD {w}M"))
        cells[f"dd{w}"] = (f'<td class="n" data-v="{"" if dd is None else dd}">'
                           f'{"–" if dd is None else _signed(-abs(dd), plus=False) + "%"}</td>')
    ath_v = _num(row.get("% ATH"))
    peak = str(row.get("ATH Date") or "").strip()
    ath_title = f' title="Peak printed {_esc(peak)}"' if peak else ""
    cells["ath"] = _peak_cell(ath_v, ath_title)
    em = _num(row.get("% 50 EMA"))
    cells["ema"] = (f'<td class="n {"" if em is None else "pos" if em > 0 else "neg" if em < 0 else ""}" '
                    f'data-v="{"" if em is None else em}">{"–" if em is None else _signed(em) + "%"}</td>')
    vol = str(row.get("Volume") or "Normal")
    # "High" is one day's volume at 1.5x or more its 20-day average
    # (momentum.py): a spike, not a high-volume stock (S87 item 3).
    vchip = ('<span class="vol" title="Today\'s volume 1.5x or more its 20-day average">Spike</span>'
             if vol == "High" else '<span class="muted">Normal</span>')
    cells["vol"] = f'<td data-v="{_esc(vol)}">{vchip}</td>'
    for key, col in (("stop", "Stop Loss"), ("chand", "Chand Exit")):
        v = _num(row.get(col))
        cells[key] = (f'<td class="n" data-v="{"" if v is None else v}">'
                      f'{"–" if v is None else _fmt.price(v)}</td>')
    from src.engine.momentum import CARRIED_MARK

    gap = str(row.get("Data Gap") or "🟢")
    carried = CARRIED_MARK in gap
    gap_title = (' title="No price on the ranking date; ranked on its last print"'
                 if carried else "")
    has_gap = "🔴" in gap
    cells["gap"] = (f'<td class="c-tick" data-v="{1 if has_gap else 0}"{gap_title}>'
                    f'{_tick(not has_gap, "No gap", "Gap")}{CARRIED_MARK if carried else ""}</td>')
    ff = _num(row.get("FFill %"))
    cells["ffill"] = f'<td class="n" data-v="{0 if ff is None else ff}">{0 if ff is None else ff:.1f}%</td>'
    hz = _num(row.get("Horizons Scored"))
    n_w = len(PERIOD_WINDOWS)
    cells["hz"] = (f'<td class="n{" muted" if hz is None else "" if hz >= n_w else " neg"}" '
                   f'data-v="{"" if hz is None else hz}">{"–" if hz is None else f"{int(hz)}/{n_w}"}</td>')
    tag = str(row.get("Indices") or "").split(",")[0].strip()
    # The index's name, not the ranking's tag (MICRO250): no internal names
    # on the page (PAGE_DESIGN §2). Sorted by size, largest first.
    # A page may name the index itself ("Index Name": the Watchlist names the systems'
    # own tags, NANO and NANO250, which this map does not know).
    idx_name = str(row.get("Index Name") or "").strip() or INDEX_NAMES.get(tag, tag)
    idx_order = list(INDEX_NAMES).index(tag) if tag in INDEX_NAMES else 9
    idx_html = (f'<span class="tag">{_esc(idx_name)}</span>' if tag
                else '<span class="muted">–</span>')
    cells["idx"] = f'<td data-v="{idx_order}">{idx_html}</td>'
    ind_full = str(row.get("Industry") or "").strip()
    ind_short = short_industry(ind_full)
    ind_txt = ind_short if len(ind_short) <= 24 else ind_short[:23] + "…"
    cells["ind"] = f'<td data-v="{_esc(ind_full)}" title="{_esc(ind_full)}">{_esc(ind_txt) or "–"}</td>'
    # A failed filter says by how much (S87 item 6): the distance below the
    # 50D EMA, and below the 52W high against the within-20% rule.
    hi_v = _num(row.get("% High"))
    miss = {
        "above": (None if em is None or em >= 0 else
                  (f"{abs(em):.1f}% below its 50D EMA", f"−{abs(em):.1f}%")),
        "near": (None if hi_v is None else
                 (f"{abs(hi_v):.1f}% below its 52W high; the filter is within {NEAR_HIGH_GAP_PCT}%",
                  f"−{abs(hi_v):.0f}%")),
    }
    for key, col in (("above", "Above 50 EMA"), ("near", "Near 52W High"), ("athf", "At ATH")):
        on = is_tick_true(row.get(col))
        why = None if on else miss.get(key)
        if why:
            cells[key] = (f'<td class="c-tick" data-v="{int(on)}" title="{_esc(why[0])}">'
                          f'<span class="tick no" aria-hidden="true">✗</span>'
                          f'<span class="miss">{why[1]}</span><span class="sr">{_esc(why[0])}</span></td>')
        else:
            cells[key] = f'<td class="c-tick" data-v="{int(on)}">{_tick(on)}</td>'
    for key, col in (("nh1", "New Highs 1M"), ("nh3", "New Highs 3M")):
        n = _num(row.get(col))
        cells[key] = (f'<td class="n" data-v="{"" if n is None else n}">'
                      f'{"–" if n is None else int(n)}</td>')
    cells["hi"] = _peak_cell(_num(row.get("% High")))
    poly, up = paths.get(sym, ("", True))
    cells["spark"] = (f'<td class="c-path{"" if up else " dn"}" data-p="{poly}"></td>'
                      if poly else '<td class="c-path muted">–</td>')
    classes = " ".join(c for c in ("hl" if is_hl else "", "cut" if cut_txt else "") if c)
    hl = f' class="{classes}"' if classes else ""
    return _short_sort_keys(f'<tr data-stock="{sym_s}"{hl}>' + "".join(cells[c[0]] for c in cols) + "</tr>")


_CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:'IBM Plex Sans',-apple-system,'Segoe UI',Roboto,sans-serif;color:var(--c-ink);background:transparent;-webkit-font-smoothing:antialiased}
.wrap{height:100vh;overflow:auto;background:var(--c-white);border:0;border-top:1px solid var(--c-ink);border-radius:0}
.edge{position:fixed;top:0;right:0;width:56px;height:100vh;pointer-events:none;z-index:6;background:linear-gradient(to right,rgba(255,255,255,0),var(--c-white) 62%);border-right:1px solid var(--c-rule_strong);opacity:0;transition:opacity .15s}
.edge.on{opacity:1}
/* A reader must be able to tell that columns continue past the edge (design audit, 9 Nov 2026: 580px of columns sat outside a 1240px frame on a 1400px desktop). The fade is the cue; this is its label. */
.edge-n{position:fixed;bottom:8px;right:10px;z-index:7;pointer-events:none;font-size:var(--fs-12);color:var(--c-muted);background:var(--c-white);padding:2px 6px;border:1px solid var(--c-rule);border-radius:4px;opacity:0;transition:opacity .15s}.edge-n.on{opacity:1}
@media (prefers-reduced-motion: reduce){*{transition:none!important;animation:none!important}}
tr[data-stock]{cursor:pointer}
table{border-collapse:separate;border-spacing:0;width:100%;min-width:1180px}
thead th{position:sticky;top:0;z-index:3;background:var(--c-subtle);border-bottom:1px solid var(--c-rule);height:42px;padding:0 10px;
  font-size: var(--fs-12);font-weight:600;color:var(--c-muted);text-align:right;white-space:nowrap;cursor:pointer;user-select:none}
thead th.t-left{text-align:left}
/* Sentence case, as every table on the site outside this frame
   (design audit, 9 Nov 2026): the grid shouted where the rest spoke. */
thead th{text-transform:none;letter-spacing:0;font-size: var(--fs-12)}
thead tr.grp-row th{font-size: var(--fs-12)}
td.n.pos,td.n.neg{font-weight:600}
thead tr.grp-row th{top:0;height:28px;font-size: var(--fs-12);font-weight:500;letter-spacing:0em;text-transform:none;text-align:center;color:var(--c-muted);border-bottom:1px solid var(--c-rule);border-left:1px solid var(--c-rule);cursor:default}
thead tr.grp-row + tr.hdr th{top:28px}
.tag{display:inline-block;font-size: var(--fs-12);font-weight:600;padding:0;border-radius:0;background:transparent;color:var(--c-text_2);border:0}
td.c-tick{text-align:center}
td.c-stock .sub{display:none}
.wide .m-only{display:none!important}
thead th[data-type=""]{cursor:default}
thead th .ar{color:var(--c-faint);margin-left:3px}
thead th:focus-visible{outline:2px solid var(--c-ink);outline-offset:-2px}
thead th.on{color:var(--c-ink)}
thead th.on .ar{color:var(--c-ink)}
td{height:""" + str(ROW_PX) + """px;padding:0 10px;border-bottom:1px solid var(--c-rule_soft);font-size: var(--fs-13);white-space:nowrap;background:var(--c-white)}
tbody tr:hover td{background:var(--c-subtle);cursor:pointer}
td.n{text-align:right;font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums}
.pos{color:var(--c-up)}.neg{color:var(--c-down)}.muted{color:var(--c-muted)}
td.n.past{color:var(--c-faint)}
/* The book's lines are named on their row, in rank order only (Screener redesign, 21 Nov 2026). */
.cutnote{display:none;font-size: var(--fs-12);font-weight:500;color:var(--c-text_2);white-space:nowrap}
table.byrank tr.cut .cutnote{display:block}
/* The Watchlist's rows (S182): a note under the name, the plan's word, and a heading row per line of the book. */
.pnote{display:block;font-size: var(--fs-12);font-weight:400;color:var(--c-muted);white-space:nowrap}
td.c-plan{text-align:left;font-weight:600}
tr.gh td{height:auto;padding:14px 10px 6px;background:var(--c-white);border-bottom:1px solid var(--c-rule_strong);cursor:default;white-space:nowrap}
tbody tr.gh:hover td{background:var(--c-white);cursor:default}
tr.gh .gh-in{position:sticky;left:10px;display:inline-flex;gap:8px;align-items:baseline}
.gh-t{font-weight:600;font-size: var(--fs-13);color:var(--c-ink)}
.gh-n{font-family:'IBM Plex Mono',ui-monospace,monospace;font-variant-numeric:tabular-nums;font-size: var(--fs-12);color:var(--c-ink)}
.gh-w{font-size: var(--fs-12);color:var(--c-muted)}
table:not(.grouped) tr.gh{display:none}
table.byrank tr.cut td.c-stock .sub{display:none!important}
tr.hdr th:nth-child(1),td.c-rank{position:sticky;left:0;z-index:2;width:52px;min-width:52px;text-align:left}
thead tr.hdr th:nth-child(1){z-index:4}
tr.hdr th:nth-child(2),td.c-stock{position:sticky;left:52px;z-index:2;text-align:left;max-width:380px;box-shadow:1px 0 0 var(--c-rule_soft)}
thead tr.hdr th:nth-child(2){z-index:4}
thead tr.grp-row th.pin{position:sticky;left:0;z-index:5;border-left:0;box-shadow:1px 0 0 var(--c-rule)}
.tick{font-weight:700;font-size: var(--fs-13)}.tick.yes{color:var(--c-up)}.tick.no{color:var(--c-muted)}
.vol{font-weight:600}
.miss{margin-left:4px;font-size: var(--fs-12);color:var(--c-muted);font-variant-numeric:tabular-nums}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.held{margin-left:6px;font-style:normal;font-size: var(--fs-12);font-weight:600;padding:1px 5px;border-radius:4px;border:1px solid var(--c-ink);color:var(--c-ink)}
table.byrank tr.cut td{box-shadow:inset 0 -2px 0 var(--c-ink)}
.lbl-m{display:none}
td.c-rank{font-family:'IBM Plex Mono',ui-monospace,monospace;font-weight:600}
td.c-stock a{display:flex;flex-direction:column;align-items:flex-start;gap:1px;min-width:0;line-height:1.2;text-decoration:none;color:inherit}
td.c-stock .sym{font-weight: 600;font-size: var(--fs-13);color:var(--c-ink)}
td.c-stock .sub{font-size: var(--fs-12);color:var(--c-muted);overflow:hidden;text-overflow:ellipsis;max-width:340px}
.chip{display:inline-block;font-family:'IBM Plex Mono',ui-monospace,monospace;font-size: var(--fs-12);font-weight:600;padding:0;border-radius:0;background:transparent!important}
.chip.up{background:var(--c-up_tint);color:var(--c-up)}.chip.down{background:var(--c-down_tint);color:var(--c-down)}.chip.flat{background:var(--c-fill);color:var(--c-muted)}
td.c-path{padding-left:14px}
td.c-flt{text-align:left}
.pass{font-size: var(--fs-12);font-weight:600;color:var(--c-up)}.fail{font-size: var(--fs-12);font-weight:600;color:var(--c-muted)}
.ath{margin-left:6px;font-size: var(--fs-12);font-weight:700;padding:2px 6px;border-radius:6px;background:var(--c-fill);color:var(--c-ink)}
.m-only{display:none}
.px-m{display:none}
@media (max-width:640px){.wrap:not(.wide) .px-d{display:none}.wrap:not(.wide) .px-m{display:inline}}
tbody tr.hl td{background:var(--c-subtle)}
.me{margin-left:6px;font-style:normal;font-size: var(--fs-12);font-weight:700;padding:2px 6px;border-radius:6px;background:var(--c-fill);color:var(--c-ink)}
@media (max-width:640px){
  table{min-width:0}
  th,td{padding:0 8px}
  td{height:""" + str(PHONE_ROW_PX) + """px}
  .d-only{display:none}
  tr.hdr th:nth-child(1),td.c-rank{width:34px;min-width:34px}
  tr.hdr th:nth-child(2),td.c-stock{left:34px;box-shadow:none;max-width:150px}
  td.c-stock .sym{font-size: var(--fs-13)}
  td.c-stock .sub{display:block;font-size: var(--fs-12);max-width:130px}
  .wide td.c-stock .sub{display:none}
  .wrap:not(.wide) tr.grp-row{display:none}
  .wrap:not(.wide) thead tr.hdr th{top:0}
  td.c-path{padding-left:0}
  td.c-path svg{width:54px}
  th .lbl-d{display:none}
  th .lbl-m{display:inline}
  td.c-price{line-height:1.25}
  .m-only{display:block;font-size: var(--fs-12);font-weight:600}
}
"""

# Opening a stock. This frame may not navigate the page around it (no
# allow-top-navigation), but it has allow-same-origin, so it adds a script to
# the parent document -- which navigates itself, as it is always allowed to.
# If the parent is ever cross-origin the injection throws, and allow-popups
# opens the stock in a new tab instead.
_JS = """
// More columns to the right: a fade on the right edge while there are
// (audit F34: "VOL..." and "TECHNIC..." were cut with no cue).
(function(){const w=document.querySelector('.wrap'),e=document.querySelector('.edge'),
    n=document.querySelector('.edge-n');
  if(!w||!e)return;
  function upd(){const more=w.scrollLeft+w.clientWidth<w.scrollWidth-2;
    e.classList.toggle('on',more);if(n)n.classList.toggle('on',more&&w.scrollLeft<4);}
  w.addEventListener('scroll',upd,{passive:true});window.addEventListener('resize',upd);upd();})();
function openStock(sym){
  const search='?stock='+encodeURIComponent(sym)+SYS;
  try{const host=window.parent;const s=host.document.createElement('script');
      s.textContent='window.location.search='+JSON.stringify(search)+';';
      host.document.body.appendChild(s);s.remove();}
  catch(e){window.open(search,'_blank');}
}
document.addEventListener('click',function(ev){
  const tr=ev.target.closest?ev.target.closest('tr[data-stock]'):null;
  if(!tr)return;
  if(ev.target.closest('a')&&(ev.metaKey||ev.ctrlKey||ev.shiftKey||ev.button===1))return;
  ev.preventDefault();openStock(tr.getAttribute('data-stock'));
});
// Sparklines from their heights (audit F62), for the rows that are SHOWN only
// (20 Nov 2026, TODO S141): the Screener sends all 750 rows so a header sort
// ranks every stock, but shows 50; drawing the 700 hidden ones took ~1.2 s of
// a throttled phone's ~1.6 s. Rows a sort or "Show all" brings into view are
// drawn then.
function drawSpark(td){const p=td.getAttribute('data-p');if(!p)return;const y=p.split(',');const n=y.length-1;
  let pts='';for(let i=0;i<=n;i++){pts+=(2+i*84/n).toFixed(1)+','+y[i]+' ';}
  td.innerHTML='<svg width="88" height="26" viewBox="0 0 88 26" aria-hidden="true"><polyline fill="none" stroke="'
    +(td.classList.contains('dn')?'var(--c-down)':'var(--c-up)')+'" stroke-width="1.7" stroke-linejoin="round" stroke-linecap="round" points="'+pts+'"/></svg>';
  td.removeAttribute('data-p');}
function drawShown(){
  const cells=Array.from(document.querySelectorAll('tbody tr')).filter(function(r){return r.offsetParent!==null;})
    .map(function(r){return r.querySelector('td.c-path[data-p]');}).filter(Boolean);
  cells.slice(0,60).forEach(drawSpark);let i=60;
  function more(){const end=Math.min(i+120,cells.length);for(;i<end;i++)drawSpark(cells[i]);if(i<cells.length)(window.requestIdleCallback||setTimeout)(more);}
  more();}
drawShown();
const ths=document.querySelectorAll('thead tr.hdr th');const tbody=document.querySelector('tbody');const tbl=document.querySelector('table');
// A grouped table (the Watchlist's lines of the book): its first order is kept, and a
// sort by Rank, smallest first, brings it and its heading rows back. Others have none.
const firstOrder=Array.from(tbody.rows);const grouped=!!tbody.querySelector('tr.gh');
// Sortable from the keyboard too (pre-launch audit F20, WCAG 2.1.1/4.1.2):
// each sortable header is focusable, sorts on Enter or Space, and says how
// it is sorted (aria-sort); the arrow glyph is decoration.
function ariaSort(d){return d==='asc'?'ascending':d==='desc'?'descending':'none';}
ths.forEach(function(th,i){
  const type=th.getAttribute('data-type');if(!type)return;
  th.tabIndex=0;
  th.setAttribute('aria-sort',ariaSort(th.getAttribute('data-dir')));
  const ar=th.querySelector('.ar');if(ar)ar.setAttribute('aria-hidden','true');
  th.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();th.click();}});
  th.addEventListener('click',function(){
    const cur=th.getAttribute('data-dir');
    const dir=cur?(cur==='asc'?'desc':'asc'):(th.getAttribute('data-first')||'asc');
    ths.forEach(function(o){o.removeAttribute('data-dir');o.classList.remove('on');const a=o.querySelector('.ar');if(a&&o.getAttribute('data-type')){a.textContent='↕';o.setAttribute('aria-sort','none');}});
    th.setAttribute('data-dir',dir);th.classList.add('on');th.querySelector('.ar').textContent=dir==='asc'?'↑':'↓';
    th.setAttribute('aria-sort',ariaSort(dir));
    const k0=th.getAttribute('data-k');
    if(grouped&&k0==='rank'&&dir==='asc'){
      firstOrder.forEach(function(r){tbody.appendChild(r);});tbl.classList.add('grouped');drawShown();return;}
    if(grouped)tbl.classList.remove('grouped');
    const rows=Array.from(tbody.rows).filter(function(r){return !r.classList.contains('gh');});
    rows.sort(function(a,b){
      const va=a.cells[i].getAttribute('data-v'),vb=b.cells[i].getAttribute('data-v');
      const ea=(va===null||va===''),eb=(vb===null||vb==='');
      if(ea||eb)return ea===eb?0:(ea?1:-1);
      if(type==='num'){const d=parseFloat(va)-parseFloat(vb);return dir==='asc'?d:-d;}
      return dir==='asc'?va.localeCompare(vb):vb.localeCompare(va);
    });
    rows.forEach(function(r){tbody.appendChild(r);});
    drawShown();   // the rows this order brings into view
    // The lines under the 20th and 40th qualified stock mean something only
    // in rank order.
    const k=th.getAttribute('data-k');
    tbl.classList.toggle('byrank',dir==='asc'&&(k==='rank'||k==='qrank'));
  });
});
"""


def table_html(view: pd.DataFrame, prices_df: pd.DataFrame | None, density: str,
               highlight: str = "", sort_key: str = "rank", sort_desc: bool = False,
               page_rows: int | None = None, full: bool = False, *,
               groups: list | None = None, plan_label: str = "Plan") -> str:
    """The whole table document, for st.iframe. Split out so tests can read it.

    `highlight` is a symbol whose row is tinted and tagged "This stock" (the
    stock page's peers). `sort_key`/`sort_desc` name the column the rows
    arrive sorted by, so its header carries the arrow: the column headers are
    the page's one sort control.

    The Watchlist (density "Watchlist") passes `groups`, a heading row before
    the row of a given symbol: (symbol, title, count, what it means), and
    `plan_label`, the plan column's header (the next rebalance, "30 Nov")."""
    cols = columns_for(density, view.columns, movers=sort_key == "d1m")
    watch = str(density).startswith("Watchlist")
    paths: dict = {}
    if prices_df is not None and not prices_df.empty:
        window = prices_df.iloc[-min(60, len(prices_df)):]
        paths = _year_paths(_spark_window_key(window), window)
    # Full Quant keeps every column on a phone and scrolls sideways, as before;
    # the compact phone list is for the shorter Executive and Core sets.
    wide = len(cols) > len(_CORE_KEYS) and not watch
    phone_keep = _WATCH_PHONE if watch else {"rank", "stock", "spark", "price"}
    head_cells = []
    if sort_key not in {c[0] for c in cols}:
        sort_key, sort_desc = "rank", False
    keys_shown = {c[0] for c in cols}
    for k, label, t in cols:
        if k == "qrank" and "q1" not in keys_shown:
            # "Now" reads only beside the 3M and 1M places; alone (Core,
            # Executive, Sectors' industry table) it is the qualified place.
            label = "Qualified #"
        if k == "plan":
            label = plan_label
        cls =("t-left " if (k in ("rank", "stock") or t == "text") else "") + (
            "" if (k in phone_keep or wide) else "d-only")
        on = k == sort_key
        if on:
            cls += " on"
        arrow = ('<span class="ar">' + (("↓" if sort_desc else "↑") if on else "↕")
                 + "</span>") if t else ""
        dir_attr = f' data-dir="{"desc" if sort_desc else "asc"}"' if on else ""
        # The trend column's header is "60D" on a phone, where the full label
        # does not fit; it was blank there.
        text = (f'<span class="lbl-d">{_esc(label)}</span><span class="lbl-m">60D</span>'
                if k == "spark" else
                # On the Watchlist's phone list "Now" stands without its group row.
                f'<span class="lbl-d">{_esc(label)}</span><span class="lbl-m">Qualified</span>'
                if watch and k == "qrank" else f"<span>{_esc(label)}</span>")
        # A first click sorts a figure largest first (audit F72: returns opened
        # worst first); a rank, where 1 is best, still opens ascending.
        first = ' data-first="asc"' if (t != "num" or k in _RANK_KEYS) else ' data-first="desc"'
        head_cells.append(f'<th class="{cls.strip()}" data-k="{k}" data-type="{t or ""}"{first}{dir_attr}>{text}{arrow}</th>')
    head = "".join(head_cells)
    parts = [
        f'<th colspan="{n}" class="grp{" pin" if pinned else ""}">{_esc(label)}</th>'
        for label, n, pinned in column_groups([c[0] for c in cols])
    ]
    group_row = '<tr class="grp-row">' + "".join(parts) + "</tr>"
    body = []
    heads = {str(g[0]): g for g in (groups or ())}
    for row in view.to_dict("records"):
        g = heads.get(str(row.get("Symbol", "")))
        if g:
            body.append(f'<tr class="gh"><td colspan="{len(cols)}"><span class="gh-in">'
                        f'<span class="gh-t">{_esc(str(g[1]))}</span><span class="gh-n">{int(g[2])}</span>'
                        f'<span class="gh-w">{_esc(str(g[3]))}</span></span></td></tr>')
        tr = _row_html(row, cols, paths, highlight)
        body.append(tr)
    # Desktop-only cells carry the d-only class too, so the phone hides whole
    # columns rather than leaving a header without its cells.
    hide = [] if wide else [i for i, c in enumerate(cols) if c[0] not in phone_keep]
    body_html = "".join(body)
    if hide:
        # A grouped table's heading rows are one cell wide, the first: never hidden.
        cell = "tr:not(.gh)>td" if groups else "td"
        css_hide = ",".join(f"{cell}:nth-child({i + 1})" for i in hide)
        extra = "@media (max-width:640px){" + css_hide + "{display:none}}"
    else:
        extra = ""
    wide_cls = " wide" if wide else ""
    by_rank = ' class="byrank"' if sort_key in ("rank", "qrank") and not sort_desc else ""
    # The first `page_rows` rows, the rest a click away (owner, 7 Nov: the
    # table scrolled inside its frame, so the wheel never reached the page).
    # Every row stays in the table, so a header sort ranks all of them and
    # the first `page_rows` of that order show.
    paged = bool(page_rows) and len(view) > int(page_rows)
    if paged:
        wide_cls += " paged"
    # The rest of the rows are behind a Streamlit button under the frame
    # (render_screener_table), which redraws the frame at full height: an
    # in-frame "Show all" turned the table into a ~1,900px box scrolling
    # inside the scrolling page, and on a phone a swipe moved the page, not
    # the box (owner, 8 Nov: blank space after row 750).
    more = ""
    paged_css = (f".paged tbody tr:nth-child(n+{int(page_rows) + 1}){{display:none}}"
                 ".wrap.paged{height:auto;overflow-y:visible}") if paged else ""
    if full:
        paged_css += ".wrap{height:auto;overflow-y:visible}"
    if wide:
        extra += "@media (max-width:640px){table{min-width:%dpx}}" % (len(cols) * 92)
    if watch:
        # The phone list drops the rank, so the stock is the pinned first column; the
        # note under the name gives way to the industry there.
        extra += ("@media (max-width:640px){tr.hdr th:nth-child(2),td.c-stock{left:0}"
                  ".pnote{display:none}tr.gh .gh-in{left:8px}}")
    if groups:
        by_rank = ' class="byrank grouped"' if by_rank else ' class="grouped"'
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>Ranking table</title>"
        "<link href='app/static/fonts.css' rel='stylesheet'>"
        f"<style>{_CSS}@media (min-width:641px){{table{{min-width:{max(1180, len(cols) * 92)}px}}}}{extra}{paged_css}</style></head><body><div class='edge' aria-hidden='true'></div><div class='edge-n' aria-hidden='true'>more columns \u2192</div><div class='wrap{wide_cls}'><table{by_rank}>"
        f"<thead>{group_row}<tr class=\"hdr\">{head}</tr></thead><tbody>{body_html}</tbody></table></div>{more}"
        f"<script>const SYS={json.dumps(system_suffix())};{_JS}</script></body></html>"
    )


SHOW_ALL_KEY = "scr_show_all"


def render_screener_table(view: pd.DataFrame, prices_df: pd.DataFrame | None,
                          density: str, *, highlight: str = "", sort_key: str = "rank",
                          sort_desc: bool = False, page_rows: int | None = None,
                          groups: list | None = None, plan_label: str = "Plan") -> None:
    if view.empty:
        st.info("No stocks match these filters. Clear the search or pick another preset.")
        return
    head_px = 44 + 28 + 6
    if page_rows:
        # The Screener: the frame is as tall as the rows it shows, so only the
        # page scrolls (never a box inside it). The first `page_rows`, then
        # every row once the reader asks; each frame fits its rows exactly.
        show_all = bool(st.session_state.get(SHOW_ALL_KEY)) or len(view) <= page_rows
        n = len(view) if show_all else page_rows
        st.iframe(resolve(table_html(view, prices_df, density, highlight, sort_key, sort_desc,
                                     None if show_all else page_rows, full=True)),
                  height=head_px + n * ROW_PX)
        if len(view) > page_rows:
            label = f"Show first {page_rows}" if show_all else f"Show all {len(view):,}"
            if st.button(label, key="scr_show_all_btn", type="secondary"):
                st.session_state[SHOW_ALL_KEY] = not show_all
                st.rerun()
        return
    rows = min(len(view), VISIBLE_ROWS)
    height = 44 + rows * ROW_PX + 4 + 28
    if groups:
        # The Watchlist shows every row and its heading rows, so only the page scrolls.
        height = 44 + len(view) * ROW_PX + len(groups) * GROUP_ROW_PX + 4 + 28
    st.iframe(resolve(table_html(view, prices_df, density, highlight, sort_key, sort_desc, page_rows,
                                 groups=groups, plan_label=plan_label)),
              height=height)

