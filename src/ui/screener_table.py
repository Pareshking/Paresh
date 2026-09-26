"""The Screener's ranking table, as drawn in the approved light design.

One HTML table serves the desktop and the phone. It lives in an st.iframe so
it can sort by column and keep its header and first two columns pinned; below
640px its own CSS turns it into the compact phone list (rank, stock, 12-month
line, price and 3M), because Streamlit cannot tell Python how wide the screen
is.

Every row of the view is in the table -- sorting a page of 25 would sort the
wrong 25 -- and the frame is tall enough to show about 25 rows at once; the
rest scroll inside it.

Two column sets are drawn here, Executive and Core. Full Quant, the 30-odd
column research view, stays on theme.render_master_screener_table.
"""
from __future__ import annotations

from html import escape as _esc
from urllib.parse import quote as _urlq

import numpy as np
import pandas as pd
import streamlit as st

from src.ui.theme import _spark_window_key, is_tick_true

# Readable names for the index tags the ranking stores.
INDEX_NAMES = {
    "N50": "Nifty 50", "NN50": "Next 50", "MID150": "Midcap 150",
    "SMALL250": "Smallcap 250", "MICRO250": "Microcap 250",
}

# (key, header, sort type). The phone list keeps only rank, stock, path and
# the price cell, which carries the 3M return under the price.
_CORE = [
    ("rank", "#", "num"), ("stock", "Stock", "text"), ("price", "Price", "num"),
    ("d1m", "Rank Δ 1M", "num"), ("r1", "1M", "num"), ("r3", "3M", "num"),
    ("r6", "6M", "num"), ("r12", "12M", "num"), ("sh3", "Sharpe 3M", "num"),
    ("dd12", "Max DD 12M", "num"), ("hi", "From 52W high", "num"),
    ("path", "12-month path", None), ("flt", "Filters", "num"),
]
_EXEC_KEYS = ("rank", "stock", "price", "d1m", "r3", "r12", "path", "flt")

ROW_PX = 44
PHONE_ROW_PX = 44
VISIBLE_ROWS = 25


def columns_for(density: str) -> list[tuple[str, str, str | None]]:
    if str(density).startswith("Executive"):
        return [c for c in _CORE if c[0] in _EXEC_KEYS]
    return list(_CORE)


def column_count(density: str) -> int:
    return len(columns_for(density))


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


def _pct_cell(v: float | None, cls_extra: str = "") -> tuple[str, str]:
    if v is None:
        return f'<td class="n muted {cls_extra}" data-v="">—</td>', ""
    cls = "pos" if v > 0 else "neg" if v < 0 else ""
    txt = f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v) * 100:.1f}%"
    return f'<td class="n {cls} {cls_extra}" data-v="{v:.6f}">{txt}</td>', txt


def _row_html(row: dict, cols: list, paths: dict) -> str:
    sym = str(row.get("Symbol", ""))
    sym_s = _esc(sym)
    name = str(row.get("Company Name") or "").strip()
    ind = str(row.get("Industry") or "").strip()
    tag = str(row.get("Indices") or "").split(",")[0].strip()
    sub = " · ".join(p for p in (name, ind, INDEX_NAMES.get(tag, tag)) if p and p != "nan")
    rank = _num(row.get("Rank"))
    cmp_v = _num(row.get("CMP"))
    r3 = _num(row.get("3M Return"))
    cells: dict[str, str] = {}

    cells["rank"] = (f'<td class="c-rank" data-v="{rank if rank is not None else ""}">'
                     f'{int(rank) if rank is not None else "—"}</td>')
    cells["stock"] = (
        f'<td class="c-stock" data-v="{sym_s}"><a href="?stock={_urlq(sym, safe="")}" '
        f'data-stock="{sym_s}" title="Open {sym_s}"><span class="sym">{sym_s}</span>'
        f'<span class="sub">{_esc(sub)}</span></a></td>'
    )
    r3_txt = "—" if r3 is None else f"{'+' if r3 > 0 else '−' if r3 < 0 else ''}{abs(r3) * 100:.1f}%"
    r3_cls = "" if r3 is None else ("pos" if r3 > 0 else "neg" if r3 < 0 else "")
    cells["price"] = (
        f'<td class="n c-price" data-v="{cmp_v if cmp_v is not None else ""}">'
        f'{"₹" + format(cmp_v, ",.2f") if cmp_v is not None else "—"}'
        f'<span class="m-only {r3_cls}">{r3_txt} 3M</span></td>'
    )
    d1 = _num(row.get("Rank Δ 1M"))
    if d1 is None:
        cells["d1m"] = '<td class="n" data-v="">—</td>'
    else:
        chip = ("up", f"▲ {int(d1)}") if d1 > 0 else ("down", f"▼ {abs(int(d1))}") if d1 < 0 else ("flat", "—")
        cells["d1m"] = f'<td class="n" data-v="{d1}"><span class="chip {chip[0]}">{chip[1]}</span></td>'
    for key, col in (("r1", "1M Return"), ("r3", "3M Return"), ("r6", "6M Return"), ("r12", "12M Return")):
        cells[key] = _pct_cell(_num(row.get(col)))[0]
    sh = _num(row.get("3M Sharpe"))
    cells["sh3"] = f'<td class="n" data-v="{"" if sh is None else sh}">{"—" if sh is None else f"{sh:.2f}"}</td>'
    dd = _num(row.get("Max DD 12M"))
    cells["dd12"] = (f'<td class="n neg" data-v="{"" if dd is None else dd}">'
                     f'{"—" if dd is None else f"−{abs(dd):.1f}%"}</td>')
    hi = _num(row.get("% High"))
    if hi is None:
        cells["hi"] = '<td class="n muted" data-v="">—</td>'
    elif hi >= -0.005:
        cells["hi"] = f'<td class="n" data-v="{hi}"><span class="chip up">At high</span></td>'
    else:
        # Two decimals under 0.1% so a stock a hair below its high does not
        # print as "−0.0%".
        cells["hi"] = f'<td class="n" data-v="{hi}">−{abs(hi):.{2 if abs(hi) < 0.1 else 1}f}%</td>'
    poly, up = paths.get(sym, ("", True))
    cells["path"] = (
        f'<td class="c-path"><svg width="88" height="26" viewBox="0 0 88 26" aria-hidden="true">'
        f'<polyline fill="none" stroke="{"#067647" if up else "#B42318"}" stroke-width="1.7" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{poly}"/></svg></td>'
        if poly else '<td class="c-path muted">—</td>'
    )
    passed = is_tick_true(row.get("Above 50 EMA")) and is_tick_true(row.get("Near 52W High"))
    ath = is_tick_true(row.get("At ATH"))
    flt = ('<span class="pass">✓ Pass</span>' if passed else '<span class="fail">Fails</span>')
    if ath:
        flt += '<span class="ath">ATH</span>'
    cells["flt"] = f'<td class="c-flt" data-v="{int(passed) * 2 + int(ath)}">{flt}</td>'
    return f'<tr data-stock="{sym_s}">' + "".join(cells[c[0]] for c in cols) + "</tr>"


_CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:'Geist',-apple-system,'Segoe UI',Roboto,sans-serif;color:#0E1726;background:transparent;-webkit-font-smoothing:antialiased}
.wrap{height:100vh;overflow:auto;background:#FFFFFF;border:1px solid #E3E6EB;border-radius:16px}
table{border-collapse:separate;border-spacing:0;width:100%;min-width:1180px}
thead th{position:sticky;top:0;z-index:3;background:#F4F5F8;border-bottom:1px solid #E3E6EB;height:42px;padding:0 10px;
  font-size:12px;font-weight:600;color:#5E6878;text-align:right;white-space:nowrap;cursor:pointer;user-select:none}
thead th.t-left{text-align:left}
thead th[data-type=""]{cursor:default}
thead th .ar{color:#A5ACB8;margin-left:3px}
thead th.on{color:#0E1726}
thead th.on .ar{color:#4F46E5}
td{height:""" + str(ROW_PX) + """px;padding:0 10px;border-bottom:1px solid #EDEFF3;font-size:13.5px;white-space:nowrap;background:#FFFFFF}
tbody tr:nth-child(even) td{background:#FAFBFC}
tbody tr:hover td{background:#F1F0FF;cursor:pointer}
td.n{text-align:right;font-family:'Geist Mono',ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums}
.pos{color:#067647}.neg{color:#B42318}.muted{color:#6B7482}
th:nth-child(1),td.c-rank{position:sticky;left:0;z-index:2;width:52px;min-width:52px;text-align:left}
thead th:nth-child(1){z-index:4}
th:nth-child(2),td.c-stock{position:sticky;left:52px;z-index:2;text-align:left;max-width:330px;box-shadow:1px 0 0 #EDEFF3}
thead th:nth-child(2){z-index:4}
td.c-rank{font-family:'Geist Mono',ui-monospace,monospace;font-weight:600}
td.c-stock a{display:flex;align-items:baseline;gap:8px;min-width:0;text-decoration:none;color:inherit}
td.c-stock .sym{font-weight:650;font-size:14px;color:#0E1726}
td.c-stock .sub{font-size:12.5px;color:#5E6878;overflow:hidden;text-overflow:ellipsis;max-width:190px}
.chip{display:inline-block;font-family:'Geist Mono',ui-monospace,monospace;font-size:12px;font-weight:600;padding:2px 7px;border-radius:7px}
.chip.up{background:#E8F5EE;color:#067647}.chip.down{background:#FDEDEB;color:#B42318}.chip.flat{background:#F1F3F6;color:#5E6878}
td.c-path{padding-left:14px}
td.c-flt{text-align:left}
.pass{font-size:12px;font-weight:600;color:#067647}.fail{font-size:12px;font-weight:600;color:#6B7482}
.ath{margin-left:6px;font-size:10.5px;font-weight:700;padding:2px 6px;border-radius:6px;background:#EEF0FF;color:#3730A3}
.m-only{display:none}
@media (max-width:640px){
  table{min-width:0}
  th,td{padding:0 8px}
  td{height:""" + str(PHONE_ROW_PX) + """px}
  .d-only{display:none}
  th:nth-child(1),td.c-rank{width:34px;min-width:34px}
  th:nth-child(2),td.c-stock{left:34px;box-shadow:none;max-width:none}
  td.c-stock a{flex-direction:column;align-items:flex-start;gap:1px}
  td.c-stock .sym{font-size:14px}
  td.c-stock .sub{font-size:12px;max-width:130px}
  td.c-path{padding-left:0}
  td.c-path svg{width:54px}
  th .lbl-d{display:none}
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
function openStock(sym){
  const search='?stock='+encodeURIComponent(sym);
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
const ths=document.querySelectorAll('thead th');const tbody=document.querySelector('tbody');
ths.forEach(function(th,i){
  const type=th.getAttribute('data-type');if(!type)return;
  th.addEventListener('click',function(){
    const dir=th.getAttribute('data-dir')==='asc'?'desc':'asc';
    ths.forEach(function(o){o.removeAttribute('data-dir');o.classList.remove('on');const a=o.querySelector('.ar');if(a&&o.getAttribute('data-type'))a.textContent='↕';});
    th.setAttribute('data-dir',dir);th.classList.add('on');th.querySelector('.ar').textContent=dir==='asc'?'↑':'↓';
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


def table_html(view: pd.DataFrame, prices_df: pd.DataFrame | None, density: str) -> str:
    """The whole table document, for st.iframe. Split out so tests can read it."""
    cols = columns_for(density)
    paths: dict = {}
    if prices_df is not None and not prices_df.empty:
        window = prices_df.iloc[-min(252, len(prices_df)):]
        paths = _year_paths(_spark_window_key(window), window)
    phone_keep = {"rank", "stock", "path", "price"}
    head_cells = []
    for k, label, t in cols:
        cls = ("t-left " if k in ("rank", "stock", "flt") else "") + ("" if k in phone_keep else "d-only")
        if k == "rank":
            cls += " on"
        arrow = ('<span class="ar">' + ("↑" if k == "rank" else "↕") + "</span>") if t else ""
        dir_attr = ' data-dir="asc"' if k == "rank" else ""
        head_cells.append(
            f'<th class="{cls.strip()}" data-type="{t or ""}"{dir_attr}>'
            f'<span class="{"lbl-d" if k == "path" else ""}">{_esc(label)}</span>{arrow}</th>'
        )
    head = "".join(head_cells)
    body = []
    for row in view.to_dict("records"):
        tr = _row_html(row, cols, paths)
        body.append(tr)
    # Desktop-only cells carry the d-only class too, so the phone hides whole
    # columns rather than leaving a header without its cells.
    hide = [i for i, c in enumerate(cols) if c[0] not in phone_keep]
    body_html = "".join(body)
    if hide:
        css_hide = ",".join(f"td:nth-child({i + 1})" for i in hide)
        extra = "@media (max-width:640px){" + css_hide + "{display:none}}"
    else:
        extra = ""
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<link rel='preconnect' href='https://fonts.googleapis.com'>"
        "<link href='https://fonts.googleapis.com/css2?family=Geist:wght@400..700&"
        "family=Geist+Mono:wght@400..700&display=swap' rel='stylesheet'>"
        f"<style>{_CSS}{extra}</style></head><body><div class='wrap'><table>"
        f"<thead><tr>{head}</tr></thead><tbody>{body_html}</tbody></table></div>"
        f"<script>{_JS}</script></body></html>"
    )


def render_screener_table(view: pd.DataFrame, prices_df: pd.DataFrame | None,
                          density: str) -> None:
    if view.empty:
        st.info("No stocks match these filters. Clear the search or pick another preset.")
        return
    rows = min(len(view), VISIBLE_ROWS)
    height = 44 + rows * ROW_PX + 4
    st.iframe(table_html(view, prices_df, density), height=height)

