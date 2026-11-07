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

from html import escape as _esc

import numpy as np
import pandas as pd
import streamlit as st
from src.ui.tokens import resolve

from src.ui.system_param import stock_href
from src.ui.system_param import suffix as system_suffix
from src.ui.theme import _spark_window_key, is_tick_true
from src.ui import formats as _fmt

# Readable names for the index tags the ranking stores.
INDEX_NAMES = {
    "N50": "Nifty 50", "NN50": "Next 50", "MID150": "Midcap 150",
    "SMALL250": "Smallcap 250", "MICRO250": "Microcap 250",
}

# (key, header, sort type). One registry; Executive, Core and Quant are column
# sets drawn from it, so a column looks and sorts the same in every view. The
# phone list keeps only rank, stock, path and the price cell, which carries the
# 3M return under the price.
PERIOD_WINDOWS = (1, 3, 6, 9, 12)
_ALL = {
    "rank": ("Rank", "num"), "stock": ("Symbol", "text"), "price": ("CMP", "num"),
    "d1m": ("1M Δ", "num"), "d3m": ("3M Δ", "num"),
    "idx": ("Index", "text"), "ind": ("Industry", "text"),
    "mcap": ("MCAP (Cr)", "num"),
    "hi": ("From 52W high", "num"), "ath": ("% ATH", "num"), "ema": ("vs 50D EMA", "num"),
    "vol": ("Volume", "text"),
    "above": ("Above 50D EMA", "num"), "near": ("Near 52W high", "num"), "athf": ("At ATH", "num"),
    "nh1": ("New Highs 1M", "num"), "nh3": ("New Highs 3M", "num"),
    "stop": ("Stop Loss", "num"), "chand": ("Chand Exit", "num"),
    "gap": ("Gap", "text"), "ffill": ("FFill %", "num"), "hz": ("Horizons", "num"),
    "spark": ("60D Spark", None),
}
for _w in PERIOD_WINDOWS:
    _ALL[f"r{_w}"] = (f"{_w}M Ret", "num")
    _ALL[f"sh{_w}"] = (f"{_w}M Sharpe", "num")
    _ALL[f"dd{_w}"] = (f"Max DD {_w}M", "num")

# Full Quant is the master: the research view's own columns, in its own order.
# Executive and Core are this set with columns hidden, nothing else. Sharpe is
# a quant-view statistic (not comparable like a return) and the drawdown shown
# outside Quant is the 3M one.
_QUANT_KEYS = (
    ("rank", "stock", "price", "d1m", "d3m", "idx", "ind", "mcap")
    + tuple(f"{k}{w}" for w in PERIOD_WINDOWS for k in ("r", "sh", "dd"))
    + ("hi", "ath", "ema", "vol", "above", "near", "athf", "nh1", "nh3", "stop", "chand",
       "gap", "ffill", "hz", "spark")
)
_CORE_KEYS = ("rank", "stock", "price", "d1m", "d3m", "idx", "ind", "mcap",
              "r1", "r3", "r6", "r12", "dd3", "hi", "ema", "vol", "above", "near", "spark")
_EXEC_KEYS = ("rank", "stock", "price", "d1m", "idx", "ind", "r3", "r12", "dd3",
              "hi", "ema", "above", "near", "spark")
# Group labels over the columns, in order.
_QUANT_GROUPS = (
    ("Identity", ("rank", "stock", "price")),
    ("Rank dynamics", ("d1m", "d3m")),
    ("Classification", ("idx", "ind", "mcap")),
    *((f"{w}M factor momentum", (f"r{w}", f"sh{w}", f"dd{w}")) for w in PERIOD_WINDOWS),
    ("Technicals & filters", ("hi", "ath", "ema", "vol", "above", "near", "athf", "nh1", "nh3")),
    ("Risk & exits", ("stop", "chand")),
    ("Data health", ("gap", "ffill", "hz")),
    ("Trend", ("spark",)),
)
_RISK_KEYS = ("stop", "chand")
# A ranking built from closing prices carries no ATR, so those columns would be
# an em dash on every row; they are dropped with their headers.
_ATR_COLUMNS = ("ATR", "ATR %", "Stop Loss", "Chand Exit")

ROW_PX = 36   # Ledger density (owner, 7 Nov); the phone list keeps 44 for touch
PHONE_ROW_PX = 36   # Ledger density (owner, 7 Nov); the phone list keeps 44 for touch
VISIBLE_ROWS = 25


def columns_for(density: str, available=None) -> list[tuple[str, str, str | None]]:
    """The columns of a view. `available` is the ranking's column names, used to
    drop the ATR-derived ones when the ranking carries none."""
    d = str(density)
    keys = _EXEC_KEYS if d.startswith("Executive") else (
        _QUANT_KEYS if d.startswith(("Full", "Quant")) else _CORE_KEYS)
    if available is not None and not any(c in available for c in _ATR_COLUMNS):
        keys = tuple(k for k in keys if k not in _RISK_KEYS)
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
    windowed = {label: ks for label, ks in _QUANT_GROUPS if "momentum" in label}
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
    """Each symbol's last year of closes as a polyline, built once per window.

    About 50 points: one per week is as much as an 88px line can show.
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
        n = len(pts) - 1
        poly = " ".join(
            f"{2 + i * 84 / n:.1f},{24 - (v - lo) / span * 21:.1f}" for i, v in enumerate(pts)
        )
        out[str(col)] = (poly, bool(s[-1] >= s[0]))
    return out


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(f) else f


def _signed(v: float, digits: int = 1, plus: bool = True) -> str:
    """A number with a true minus sign (U+2212), and + when `plus`."""
    r = round(v, digits)
    sign = "+" if (r > 0 and plus) else "−" if r < 0 else ""
    return f"{sign}{abs(r):.{digits}f}"


def _price_html(v: float | None) -> str:
    """The price with paise, and beside it the price rounded to the rupee for
    the phone's compact list (rounded, not cut: ₹2,373.50 reads ₹2,374)."""
    if v is None:
        return "—"
    return (f'<span class="px-d">{_fmt.inr(v, 2)}</span>'
            f'<span class="px-m">{_fmt.inr(v)}</span>')


def _peak_cell(v: float | None, title: str = "") -> str:
    """% below a peak: plain, never coloured; "New high" at the peak itself."""
    if v is None:
        return '<td class="n muted" data-v="">—</td>'
    txt = "New high" if v >= 0 else f"{_signed(v, plus=False)}%"
    return f'<td class="n" data-v="{v}"{title}>{txt}</td>'


def _pct_cell(v: float | None, cls_extra: str = "") -> tuple[str, str]:
    if v is None:
        return f'<td class="n muted {cls_extra}" data-v="">—</td>', ""
    cls = "pos" if v > 0 else "neg" if v < 0 else ""
    txt = f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v) * 100:.1f}%"
    return f'<td class="n {cls} {cls_extra}" data-v="{v:.6f}">{txt}</td>', txt


def _tick(on: bool, yes: str = "Yes", no: str = "No") -> str:
    """Pass or fail as a glyph that does not need colour vision to read."""
    return (f'<span class="tick yes" title="{yes}">✓</span>' if on
            else f'<span class="tick no" title="{no}">✗</span>')


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
    sub = ind if ind and ind != "nan" else ""
    rank = _num(row.get("Rank"))
    cmp_v = _num(row.get("CMP"))
    r3 = _num(row.get("3M Return"))
    cells: dict[str, str] = {}

    cells["rank"] = (f'<td class="c-rank" data-v="{rank if rank is not None else ""}">'
                     f'{int(rank) if rank is not None else "—"}</td>')
    cells["stock"] = (
        f'<td class="c-stock" data-v="{sym_s}"><a href="{stock_href(sym)}" '
        f'data-stock="{sym_s}" title="Open {_esc(name) if name and name != "nan" else sym_s}"><span class="sym">{sym_s}'
        f'{"<em class=me>This stock</em>" if is_hl else ""}</span>'
        f'<span class="sub">{_esc(sub)}</span></a></td>'
    )
    r3_txt = "—" if r3 is None else f"{'+' if r3 > 0 else '−' if r3 < 0 else ''}{abs(r3) * 100:.1f}%"
    r3_cls = "" if r3 is None else ("pos" if r3 > 0 else "neg" if r3 < 0 else "")
    cells["price"] = (
        f'<td class="n c-price" data-v="{cmp_v if cmp_v is not None else ""}">'
        # Paise on a desktop (audit F66); the phone's compact list hides them,
        # where the extra three characters pushed the trend line off.
        f'{_price_html(cmp_v)}'
        f'<span class="m-only {r3_cls}">{r3_txt} 3M</span></td>'
    )
    for key, col in (("d1m", "Rank Δ 1M"), ("d3m", "Rank Δ 3M")):
        d = _num(row.get(col))
        if d is None:
            cells[key] = '<td class="n" data-v="">—</td>'
        else:
            chip = ("up", f"▲ {int(d)}") if d > 0 else ("down", f"▼ {abs(int(d))}") if d < 0 else ("flat", "— 0")
            cells[key] = f'<td class="n" data-v="{d}"><span class="chip {chip[0]}">{chip[1]}</span></td>'
    mc = _num(row.get("Market Cap (Cr)"))
    cells["mcap"] = (f'<td class="n" data-v="{"" if mc is None else mc}">'
                     f'{"—" if mc is None else _fmt.inr(mc)}</td>')
    for w in PERIOD_WINDOWS:
        cells[f"r{w}"] = _pct_cell(_num(row.get(f"{w}M Return")))[0]
        sh = _num(row.get(f"{w}M Sharpe"))
        sh_cls = "" if sh is None else "pos" if sh > 0 else "neg" if sh < 0 else ""
        cells[f"sh{w}"] = (f'<td class="n {sh_cls}" data-v="{"" if sh is None else sh}">'
                           f'{"—" if sh is None else _signed(sh, 2, plus=False)}</td>')
        dd = _num(row.get(f"Max DD {w}M"))
        cells[f"dd{w}"] = (f'<td class="n" data-v="{"" if dd is None else dd}">'
                           f'{"—" if dd is None else _signed(-abs(dd), plus=False) + "%"}</td>')
    ath_v = _num(row.get("% ATH"))
    peak = str(row.get("ATH Date") or "").strip()
    ath_title = f' title="Peak printed {_esc(peak)}"' if peak else ""
    cells["ath"] = _peak_cell(ath_v, ath_title)
    em = _num(row.get("% 50 EMA"))
    cells["ema"] = (f'<td class="n {"" if em is None else "pos" if em > 0 else "neg" if em < 0 else ""}" '
                    f'data-v="{"" if em is None else em}">{"—" if em is None else _signed(em) + "%"}</td>')
    vol = str(row.get("Volume") or "Normal")
    vchip = ('<span class="vol">High</span>' if vol == "High"
             else '<span class="vol">Surge</span>' if vol == "Surge"
             else '<span class="muted">Normal</span>')
    cells["vol"] = f'<td data-v="{_esc(vol)}">{vchip}</td>'
    for key, col in (("stop", "Stop Loss"), ("chand", "Chand Exit")):
        v = _num(row.get(col))
        cells[key] = (f'<td class="n" data-v="{"" if v is None else v}">'
                      f'{"—" if v is None else _fmt.inr(v, 2)}</td>')
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
                   f'data-v="{"" if hz is None else hz}">{"—" if hz is None else f"{int(hz)}/{n_w}"}</td>')
    tag = str(row.get("Indices") or "").split(",")[0].strip()
    idx_html = (f'<span class="tag">{_esc(tag)}</span>' if tag
                else '<span class="muted">—</span>')
    cells["idx"] = f'<td data-v="{_esc(tag)}">{idx_html}</td>'
    ind_full = str(row.get("Industry") or "").strip()
    ind_txt = ind_full if len(ind_full) <= 21 else ind_full[:20] + "…"
    cells["ind"] = f'<td data-v="{_esc(ind_full)}" title="{_esc(ind_full)}">{_esc(ind_txt) or "—"}</td>'
    for key, col in (("above", "Above 50 EMA"), ("near", "Near 52W High"), ("athf", "At ATH")):
        on = is_tick_true(row.get(col))
        cells[key] = f'<td class="c-tick" data-v="{int(on)}">{_tick(on)}</td>'
    for key, col in (("nh1", "New Highs 1M"), ("nh3", "New Highs 3M")):
        n = _num(row.get(col))
        cells[key] = (f'<td class="n" data-v="{"" if n is None else n}">'
                      f'{"—" if n is None else int(n)}</td>')
    cells["hi"] = _peak_cell(_num(row.get("% High")))
    poly, up = paths.get(sym, ("", True))
    cells["spark"] = (
        f'<td class="c-path"><svg width="88" height="26" viewBox="0 0 88 26" aria-hidden="true">'
        f'<polyline fill="none" stroke="{"var(--c-up)" if up else "var(--c-down)"}" stroke-width="1.7" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{poly}"/></svg></td>'
        if poly else '<td class="c-path muted">—</td>'
    )
    hl = ' class="hl"' if is_hl else ""
    return f'<tr data-stock="{sym_s}"{hl}>' + "".join(cells[c[0]] for c in cols) + "</tr>"


_CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:'IBM Plex Sans',-apple-system,'Segoe UI',Roboto,sans-serif;color:var(--c-ink);background:transparent;-webkit-font-smoothing:antialiased}
.wrap{height:100vh;overflow:auto;background:var(--c-white);border:0;border-top:1px solid var(--c-ink);border-radius:0}
.edge{position:fixed;top:0;right:0;width:32px;height:100vh;pointer-events:none;z-index:6;background:linear-gradient(to right,rgba(255,255,255,0),var(--c-white));opacity:0;transition:opacity .15s}
.edge.on{opacity:1}
@media (prefers-reduced-motion: reduce){*{transition:none!important;animation:none!important}}
tr[data-stock]{cursor:pointer}
table{border-collapse:separate;border-spacing:0;width:100%;min-width:1180px}
thead th{position:sticky;top:0;z-index:3;background:var(--c-subtle);border-bottom:1px solid var(--c-rule);height:42px;padding:0 10px;
  font-size:12px;font-weight:600;color:var(--c-muted);text-align:right;white-space:nowrap;cursor:pointer;user-select:none}
thead th.t-left{text-align:left}
thead th{text-transform:uppercase;letter-spacing:.04em;font-size: 12px}
thead tr.grp-row th{font-size: 12px}
td.n.pos,td.n.neg{font-weight:600}
thead tr.grp-row th{top:0;height:28px;font-size: 12px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;text-align:center;color:var(--c-muted);border-bottom:1px solid var(--c-rule);border-left:1px solid var(--c-rule);cursor:default}
thead tr.grp-row + tr.hdr th{top:28px}
.tag{display:inline-block;font-size: 12px;font-weight:600;padding:0;border-radius:0;background:transparent;color:var(--c-text_2);border:0}
td.c-tick{text-align:center}
td.c-stock .sub{display:none}
.wide .m-only{display:none!important}
thead th[data-type=""]{cursor:default}
thead th .ar{color:var(--c-faint);margin-left:3px}
thead th:focus-visible{outline:2px solid var(--c-ink);outline-offset:-2px}
thead th.on{color:var(--c-ink)}
thead th.on .ar{color:var(--c-ink)}
td{height:""" + str(ROW_PX) + """px;padding:0 10px;border-bottom:1px solid var(--c-rule_soft);font-size:13.5px;white-space:nowrap;background:var(--c-white)}
tbody tr:hover td{background:var(--c-subtle);cursor:pointer}
td.n{text-align:right;font-family:'IBM Plex Mono',ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums}
.pos{color:var(--c-up)}.neg{color:var(--c-down)}.muted{color:var(--c-muted)}
tr.hdr th:nth-child(1),td.c-rank{position:sticky;left:0;z-index:2;width:52px;min-width:52px;text-align:left}
thead tr.hdr th:nth-child(1){z-index:4}
tr.hdr th:nth-child(2),td.c-stock{position:sticky;left:52px;z-index:2;text-align:left;max-width:380px;box-shadow:1px 0 0 var(--c-rule_soft)}
thead tr.hdr th:nth-child(2){z-index:4}
thead tr.grp-row th.pin{position:sticky;left:0;z-index:5;border-left:0;box-shadow:1px 0 0 var(--c-rule)}
.tick{font-weight:700;font-size:14px}.tick.yes{color:var(--c-up)}.tick.no{color:var(--c-muted)}
.vol{font-weight:600}
.lbl-m{display:none}
td.c-rank{font-family:'IBM Plex Mono',ui-monospace,monospace;font-weight:600}
td.c-stock a{display:flex;flex-direction:column;align-items:flex-start;gap:1px;min-width:0;line-height:1.2;text-decoration:none;color:inherit}
td.c-stock .sym{font-weight: 600;font-size:14px;color:var(--c-ink)}
td.c-stock .sub{font-size:12px;color:var(--c-muted);overflow:hidden;text-overflow:ellipsis;max-width:340px}
.chip{display:inline-block;font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:12px;font-weight:600;padding:0;border-radius:0;background:transparent!important}
.chip.up{background:var(--c-up_tint);color:var(--c-up)}.chip.down{background:var(--c-down_tint);color:var(--c-down)}.chip.flat{background:var(--c-fill);color:var(--c-muted)}
td.c-path{padding-left:14px}
td.c-flt{text-align:left}
.pass{font-size:12px;font-weight:600;color:var(--c-up)}.fail{font-size:12px;font-weight:600;color:var(--c-muted)}
.ath{margin-left:6px;font-size: 12px;font-weight:700;padding:2px 6px;border-radius:6px;background:var(--c-fill);color:var(--c-ink)}
.m-only{display:none}
.px-m{display:none}
@media (max-width:640px){.wrap:not(.wide) .px-d{display:none}.wrap:not(.wide) .px-m{display:inline}}
tbody tr.hl td{background:var(--c-subtle)}
.me{margin-left:6px;font-style:normal;font-size: 12px;font-weight:700;padding:2px 6px;border-radius:6px;background:var(--c-fill);color:var(--c-ink)}
@media (max-width:640px){
  table{min-width:0}
  th,td{padding:0 8px}
  td{height:""" + str(PHONE_ROW_PX) + """px}
  .d-only{display:none}
  tr.hdr th:nth-child(1),td.c-rank{width:34px;min-width:34px}
  tr.hdr th:nth-child(2),td.c-stock{left:34px;box-shadow:none;max-width:150px}
  td.c-stock .sym{font-size:14px}
  td.c-stock .sub{display:block;font-size:12px;max-width:130px}
  .wide td.c-stock .sub{display:none}
  .wrap:not(.wide) tr.grp-row{display:none}
  .wrap:not(.wide) thead tr.hdr th{top:0}
  td.c-path{padding-left:0}
  td.c-path svg{width:54px}
  th .lbl-d{display:none}
  th .lbl-m{display:inline}
  td.c-price{line-height:1.25}
  .m-only{display:block;font-size:12px;font-weight:600}
}
"""

# Opening a stock. This frame may not navigate the page around it (no
# allow-top-navigation), but it has allow-same-origin, so it adds a script to
# the parent document -- which navigates itself, as it is always allowed to.
# If the parent is ever cross-origin the injection throws, and allow-popups
# opens the stock in a new tab instead.
_JS = """
// "Show all": the rest of the rows, and the table scrolls in its frame again.
(function(){const b=document.getElementById('showall');if(!b)return;
  b.addEventListener('click',function(){const w=document.querySelector('.wrap');
    w.classList.remove('paged');b.remove();w.dispatchEvent(new Event('scroll'));});})();
// More columns to the right: a fade on the right edge while there are
// (audit F34: "VOL..." and "TECHNIC..." were cut with no cue).
(function(){const w=document.querySelector('.wrap'),e=document.querySelector('.edge');
  if(!w||!e)return;
  function upd(){e.classList.toggle('on',w.scrollLeft+w.clientWidth<w.scrollWidth-2);}
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
const ths=document.querySelectorAll('thead tr.hdr th');const tbody=document.querySelector('tbody');
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
    const rows=Array.from(tbody.rows);
    rows.sort(function(a,b){
      const va=a.cells[i].getAttribute('data-v'),vb=b.cells[i].getAttribute('data-v');
      const ea=(va===null||va===''),eb=(vb===null||vb==='');
      if(ea||eb)return ea===eb?0:(ea?1:-1);
      if(type==='num'){const d=parseFloat(va)-parseFloat(vb);return dir==='asc'?d:-d;}
      return dir==='asc'?va.localeCompare(vb):vb.localeCompare(va);
    });
    rows.forEach(function(r){tbody.appendChild(r);});
  });
});
"""


def table_html(view: pd.DataFrame, prices_df: pd.DataFrame | None, density: str,
               highlight: str = "", sort_key: str = "rank", sort_desc: bool = False,
               page_rows: int | None = None) -> str:
    """The whole table document, for st.iframe. Split out so tests can read it.

    `highlight` is a symbol whose row is tinted and tagged "This stock" (the
    stock page's peers). `sort_key`/`sort_desc` name the column the rows
    arrive sorted by, so its header carries the arrow: the column headers are
    the page's one sort control."""
    cols = columns_for(density, view.columns)
    paths: dict = {}
    if prices_df is not None and not prices_df.empty:
        window = prices_df.iloc[-min(60, len(prices_df)):]
        paths = _year_paths(_spark_window_key(window), window)
    # Full Quant keeps every column on a phone and scrolls sideways, as before;
    # the compact phone list is for the shorter Executive and Core sets.
    wide = len(cols) > len(_CORE_KEYS)
    phone_keep = {"rank", "stock", "spark", "price"}
    head_cells = []
    if sort_key not in {c[0] for c in cols}:
        sort_key, sort_desc = "rank", False
    for k, label, t in cols:
        cls = ("t-left " if (k in ("rank", "stock") or t == "text") else "") + (
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
                if k == "spark" else f"<span>{_esc(label)}</span>")
        # A first click sorts a figure largest first (audit F72: returns opened
        # worst first); a rank, where 1 is best, still opens ascending.
        first = ' data-first="asc"' if (t != "num" or k == "rank") else ' data-first="desc"'
        head_cells.append(f'<th class="{cls.strip()}" data-type="{t or ""}"{first}{dir_attr}>{text}{arrow}</th>')
    head = "".join(head_cells)
    parts = [
        f'<th colspan="{n}" class="grp{" pin" if pinned else ""}">{_esc(label)}</th>'
        for label, n, pinned in column_groups([c[0] for c in cols])
    ]
    group_row = '<tr class="grp-row">' + "".join(parts) + "</tr>"
    body = []
    for row in view.to_dict("records"):
        tr = _row_html(row, cols, paths, highlight)
        body.append(tr)
    # Desktop-only cells carry the d-only class too, so the phone hides whole
    # columns rather than leaving a header without its cells.
    hide = [] if wide else [i for i, c in enumerate(cols) if c[0] not in phone_keep]
    body_html = "".join(body)
    if hide:
        css_hide = ",".join(f"td:nth-child({i + 1})" for i in hide)
        extra = "@media (max-width:640px){" + css_hide + "{display:none}}"
    else:
        extra = ""
    wide_cls = " wide" if wide else ""
    # The first `page_rows` rows, the rest a click away (owner, 7 Nov: the
    # table scrolled inside its frame, so the wheel never reached the page).
    # Every row stays in the table, so a header sort ranks all of them and
    # the first `page_rows` of that order show.
    paged = bool(page_rows) and len(view) > int(page_rows)
    if paged:
        wide_cls += " paged"
    more = (f'<button class="more" id="showall" type="button">Show all {len(view):,}</button>'
            if paged else "")
    paged_css = (f".paged tbody tr:nth-child(n+{int(page_rows) + 1}){{display:none}}"
                 ".wrap.paged{height:auto;overflow-y:visible}"
                 ".more{display:block;margin:10px 0 2px;padding:8px 14px;font:inherit;font-size:13.5px;"
                 "color:var(--c-ink);background:var(--c-white);border:1px solid var(--c-rule_strong);"
                 "border-radius:4px;cursor:pointer}.more:hover{border-color:var(--c-ink)}"
                 ".more:focus-visible{outline:2px solid var(--c-ink);outline-offset:2px}") if paged else ""
    if wide:
        extra += "@media (max-width:640px){table{min-width:%dpx}}" % (len(cols) * 92)
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>Ranking table</title>"
        "<link href='app/static/fonts.css' rel='stylesheet'>"
        f"<style>{_CSS}@media (min-width:641px){{table{{min-width:{max(1180, len(cols) * 92)}px}}}}{extra}{paged_css}</style></head><body><div class='edge' aria-hidden='true'></div><div class='wrap{wide_cls}'><table>"
        f"<thead>{group_row}<tr class=\"hdr\">{head}</tr></thead><tbody>{body_html}</tbody></table></div>{more}"
        f"<script>const SYS={json.dumps(system_suffix())};{_JS}</script></body></html>"
    )


def render_screener_table(view: pd.DataFrame, prices_df: pd.DataFrame | None,
                          density: str, *, highlight: str = "", sort_key: str = "rank",
                          sort_desc: bool = False, page_rows: int | None = None) -> None:
    if view.empty:
        st.info("No stocks match these filters. Clear the search or pick another preset.")
        return
    if page_rows and len(view) > page_rows:
        # Tall enough for the first rows and the button: the page scrolls,
        # not the table, until the reader asks for all of them.
        height = 44 + 28 + page_rows * ROW_PX + 4 + 56
    else:
        rows = min(len(view), VISIBLE_ROWS)
        height = 44 + rows * ROW_PX + 4 + 28
    st.iframe(resolve(table_html(view, prices_df, density, highlight, sort_key, sort_desc, page_rows)),
              height=height)

