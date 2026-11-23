"""The Dashboard's interactive charts (S151, v8; owner approved 20 Nov 2026).

Each chart is a small frame that loads the shared kit, app/static/dash_charts.js,
once (the browser caches it), and draws from a JSON spec. Every chart gives its
values under the pointer, under a finger dragged across it, and with the arrow
keys; at rest it shows its latest values. Colours are the theme's: the frame
cannot see the page's CSS variables, so `tokens.resolve` writes them in.

Kinds: "month" (straight-line bars, a period switch), "bars" (monthly bars
from a zero line), "shared" (breadth by size list), "segbar" (the book by
industry) and "breadth" (the index and its breadth,
two panes, one crosshair); for Portfolio "growth" (₹100 and how far below the
peak, the book and the market) and "holdings" (the book, sortable). Rules:
docs/PAGE_DESIGN.md section 4.
"""

from __future__ import annotations

import hashlib
import html as _html
import json
from pathlib import Path

import streamlit as st

from src.ui.tokens import FONTS, resolve

KINDS = ("month", "bars", "shared", "segbar", "breadth", "growth", "holdings", "history", "lines", "trows", "rel",
         "pairs", "lmap", "stable", "btgrowth")
# The kit's address carries its content hash, so a deploy is never drawn by a cached older kit.
_KIT = Path(__file__).resolve().parents[2] / "static" / "dash_charts.js"
KIT_SRC = "app/static/dash_charts.js?v=" + hashlib.sha256(_KIT.read_bytes()).hexdigest()[:12]

CSS = """
:root{--bg:var(--c-white);--ink:var(--c-ink);--text2:var(--c-text_2);--muted:var(--c-muted);--faint:var(--c-faint);
--rule:var(--c-rule_strong);--rule-soft:var(--c-rule_soft);--fill:var(--c-fill);--up:var(--c-up);--up-soft:var(--c-up_tint);
--down:var(--c-down);--down-soft:var(--c-down_tint);--caution:var(--c-caution);--caution-soft:var(--c-caution_tint);
--mid:var(--c-mid);--s-book:var(--c-s_book);--s-market:var(--c-s_market);--s-n500:var(--c-s_n500);
--s-mom50:var(--c-s_mom50);--s-dii:var(--c-s_dii);--tip-bg:var(--c-ink);--tip-fg:var(--c-white);--tip-muted:var(--c-quiet)}
*{box-sizing:border-box}html,body{margin:0;overflow-x:hidden;overflow-x:clip;background:transparent;color:var(--ink);
font-family:'IBM Plex Sans',system-ui,-apple-system,'Segoe UI',sans-serif;font-size:13.5px;line-height:1.45}
.card{display:flex;flex-direction:column;gap:8px;padding:2px 10px 6px}
.cap{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:6px 14px;font-size:12px;color:var(--muted)}
.up{color:var(--up)}.down{color:var(--down)}.watch{color:var(--caution)}.turning{color:var(--muted)}.muted{color:var(--muted)}.b{font-weight:600}
.readout{display:flex;flex-wrap:wrap;gap:4px 18px;font-size:13px;align-items:baseline;min-height:22px}
.readout .d{color:var(--muted);font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:12px}
.ph{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 14px;font-size:12px;color:var(--muted)}.ph>b{color:var(--ink);font-size:13px}
.ph .d{font-family:'IBM Plex Mono',ui-monospace,monospace;width:100%}.ph span{display:inline-flex;align-items:baseline;gap:5px;white-space:nowrap}
.ph span b{font-family:'IBM Plex Mono',ui-monospace,monospace;font-weight:600;font-size:14px;color:var(--ink);font-variant-numeric:tabular-nums}.ph span b.down{color:var(--down)}
.ph i{width:12px;height:0;border-top:2px solid;display:inline-block;transform:translateY(-3px)}.ph i.dash{border-top-style:dashed}
.ro{display:flex;align-items:baseline;gap:6px}.ro i{width:10px;height:3px;border-radius:2px;display:inline-block;transform:translateY(-3px)}
.ro b{font-family:'IBM Plex Mono',ui-monospace,monospace;font-weight:600;font-size:15px;font-variant-numeric:tabular-nums}.ro span{color:var(--muted)}
.chips{display:flex;flex-wrap:wrap;max-width:100%;gap:4px;background:var(--fill);border-radius:8px;padding:3px}
.chip{font:600 12px 'IBM Plex Sans',system-ui,sans-serif;color:var(--muted);background:none;border:0;border-radius:6px;padding:6px 10px;min-height:32px;cursor:pointer}
.chips:empty{display:none}
.chip[aria-pressed="true"]{background:var(--bg);color:var(--ink);box-shadow:0 1px 2px rgba(0,0,0,.12)}
.chip:focus-visible,.chart:focus-visible,.trow:focus-visible,.shrow:focus-visible,.segbar i:focus-visible{outline:2px solid var(--up);outline-offset:2px}
.chart{position:relative;touch-action:pan-y;-webkit-user-select:none;user-select:none}
.chart svg{display:block;width:100%;overflow:visible}
.chart text{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:11px;fill:var(--faint);paint-order:stroke;stroke:var(--bg);stroke-width:4px;stroke-linejoin:round}
.chart text.lbl-end{font-family:'IBM Plex Sans',system-ui,sans-serif;font-size:12px;font-weight:600}
.chart text.lbl-v{font-weight:600}
.chart text.lbl-band{font-family:'IBM Plex Sans',system-ui,sans-serif;font-style:italic;font-size:11px;fill:var(--muted)}
.tip{position:absolute;top:0;pointer-events:none;background:var(--tip-bg);color:var(--tip-fg);border-radius:8px;padding:8px 10px;font-size:12px;
box-shadow:0 6px 20px rgba(0,0,0,.18);white-space:nowrap;opacity:0;transform:translateY(4px);transition:opacity .12s,transform .12s;z-index:2}
.tip.on{opacity:1;transform:none}.tip .t-d{color:var(--tip-muted);font-family:'IBM Plex Mono',monospace;font-size:11px;margin-bottom:3px}
.tip .t-r{display:flex;align-items:center;gap:8px;justify-content:space-between}.tip .t-r b{font-family:'IBM Plex Mono',monospace}
.tip .t-k{display:flex;align-items:center;gap:6px}.tip .t-k i{width:8px;height:8px;border-radius:50%;display:inline-block}
.tt{--pitch:8px;display:grid;gap:0;height:24px;position:relative;grid-template-columns:repeat(var(--n),var(--pitch));width:calc(var(--n) * var(--pitch));max-width:100%}
.tt i{display:block;width:50%;justify-self:center;background:var(--rule)}.tt i.f{background:var(--ink)}
.tt .zero,.tt .line{position:absolute;top:-3px;bottom:-3px;width:0;border-left:1px dashed var(--muted)}
.tt .zero{border-left:2px solid var(--ink);top:-5px;bottom:-5px}
.tt .ago{position:absolute;bottom:-9px;width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;border-bottom:6px solid var(--muted);transform:translateX(-50%)}
.trow{display:grid;grid-template-columns:minmax(0,230px) max-content 72px;justify-content:start;gap:6px 16px;align-items:center;padding:7px 8px 12px;margin:0 -8px;border-radius:6px}
.trow:hover,.trow.on{background:var(--fill)}
.nm{font-size:14px;min-width:0}.nm small{display:block;font-size:12px;color:var(--muted);font-weight:400}
.vl{font-family:'IBM Plex Mono',monospace;font-weight:600;text-align:right;font-variant-numeric:tabular-nums}
.seg-axis{display:grid;grid-template-columns:minmax(0,230px) calc(var(--n) * 8px) 72px;justify-content:start;gap:16px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--faint)}
.seg-axis div{position:relative;height:14px}.seg-axis div span{position:absolute;transform:translateX(-50%)}
.sh-head,.shrow{display:grid;grid-template-columns:minmax(0,130px) max-content 56px 56px 56px;justify-content:start;gap:6px 12px;align-items:center}
.sh-head{font-size:12px;color:var(--muted);padding:0 8px 4px;margin:0 -8px;border-bottom:1px solid var(--ink)}
.num{text-align:right;font-family:'IBM Plex Mono',monospace;font-variant-numeric:tabular-nums}.sh-head .num{font-family:inherit}
.shrow{padding:9px 8px 14px;margin:0 -8px;border-radius:6px;border-bottom:1px solid var(--rule-soft)}.shrow:hover,.shrow.on{background:var(--fill)}
.tr-head,.trrow{display:grid;grid-template-columns:minmax(0,240px) calc(var(--tn,50) * var(--pitch,8px)) repeat(var(--nv,3),60px);justify-content:start;gap:6px 12px;align-items:center}
.tr-head{font-size:12px;color:var(--muted);padding:0 8px 4px;margin:0 -8px;border-bottom:1px solid var(--ink)}.tr-head .num{font-family:inherit}
.trrow{padding:9px 8px 13px;margin:0 -8px;border-radius:6px;border-bottom:1px solid var(--rule-soft)}.trrow:hover,.trrow.on{background:var(--fill)}
.trrow .num.b{font-weight:600}
.trgrp{padding:10px 8px 6px;margin:0 -8px;font-size:12.5px;color:var(--text2);background:var(--fill);border-bottom:1px solid var(--rule-soft)}.trgrp span{color:var(--muted);font-weight:400}.trrow.ref{border-bottom:1.5px solid var(--rule)}
.pick{font:13px 'IBM Plex Sans',system-ui,sans-serif;color:var(--ink);background:var(--bg);border:1px solid var(--rule);border-radius:6px;padding:6px 8px;min-height:32px}
.mcap,.mex p{margin:0;font-size:13.5px;color:var(--muted);max-width:80ch}.mex{display:grid;gap:8px}.mex b{color:var(--text2)}.mex .mh{color:var(--ink);font-weight:600}
@media (min-width:900px){.mex{grid-template-columns:1fr 1fr;column-gap:32px}.mex .mh{grid-column:1/-1}}
details summary{cursor:pointer;font-size:13px;color:var(--text2)}.ptab,.mtab{max-height:340px;overflow:auto;margin-top:6px}
.stab{overflow-x:auto}.ht.st{min-width:0;width:auto}.ht.st th,.ht.st td{padding:7px 12px 7px 0}.ht.st td.bar{text-align:right}.ht.st .bw{display:flex;align-items:center;justify-content:flex-end;gap:10px}.ht.st .bw .num{min-width:40px}.ht.st .tt{--pitch:6.8px;height:20px}.ht.st tr.ref th,.ht.st tr.ref td{border-bottom:1.5px solid var(--rule)}.ht.st thead th{white-space:normal;max-width:84px}.ht.st thead th:first-child{max-width:none}
.key{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12px;color:var(--muted)}.key span{display:flex;align-items:center;gap:6px}
.key .k-now{width:2px;height:14px;background:var(--ink)}.key .k-ago{width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;border-bottom:6px solid var(--muted)}
.key .k-line{width:0;height:14px;border-left:1px dashed var(--muted)}
.key .dot{width:10px;height:10px;border-radius:50%;background:var(--bg);box-shadow:inset 0 0 0 1.5px var(--muted)}.key .dot.held{background:var(--ink);box-shadow:none}
.segbar{display:flex;gap:2px;height:44px;border-radius:4px;overflow:hidden}
.segbar i{display:flex;align-items:center;padding-left:8px;font-style:normal;font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;cursor:pointer;color:var(--bg)}
.segbar i.dim{opacity:.3}
/* A frame is never under 150 px; on a wide screen the bar takes that room rather than leaving it empty. */
@media (min-width:601px){.segbar{height:64px}}
.seg-key i{width:12px;height:12px;border-radius:3px;display:inline-block}.seg-key b{font-family:'IBM Plex Mono',monospace;color:var(--ink)}
.seg-strong{background:var(--up)}.seg-strong.alt{background:color-mix(in srgb,var(--up) 70%,var(--bg))}
.segbar i.seg-turning{color:var(--ink)}.seg-turning{background:var(--mid)}.seg-turning.alt{background:color-mix(in srgb,var(--mid) 70%,var(--bg))}
.seg-weak{background:var(--down)}.seg-weak.alt{background:color-mix(in srgb,var(--down) 75%,var(--bg))}
.hold{overflow-x:auto}
.ht{width:100%;min-width:1120px;border-collapse:collapse;font-size:13.5px}
.ht th,.ht td{text-align:left;padding:7px 5px 7px 0;border-bottom:1px solid var(--rule-soft);vertical-align:middle}
.ht thead th{font-size:12px;color:var(--muted);font-weight:500;border-bottom:1px solid var(--ink);vertical-align:bottom;cursor:pointer;user-select:none;font-family:'IBM Plex Sans',system-ui,sans-serif}
.ht thead th.num{max-width:64px;white-space:normal;text-align:right}
.ht thead th:not(.num)[aria-sort="descending"]::after{content:" ↓"}.ht thead th:not(.num)[aria-sort="ascending"]::after{content:" ↑"}
.ht thead th.num[aria-sort="descending"]::before{content:"↓ "}.ht thead th.num[aria-sort="ascending"]::before{content:"↑ "}
.ht thead th:focus-visible{outline:2px solid var(--up);outline-offset:2px}
.ht tbody th,.ht tfoot th{font-weight:600;white-space:nowrap;position:sticky;left:0;background:var(--bg);z-index:1}
.ht .num{width:1%;white-space:nowrap}.ht td.num{text-align:right}.ht .nw{white-space:nowrap}
.ht .sym{font-family:'IBM Plex Mono',monospace;font-weight:600}.ht .ss{display:block;font-size:12px;color:var(--muted);font-weight:400;white-space:nowrap}
.ht .co{max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ht td.rk{white-space:nowrap;font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--muted)}.ht .rk b{color:var(--ink)}.ht .rk b.down{color:var(--down)}
.ht .rk{text-align:right!important}th.rk{position:relative}.vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}.rk3{display:inline-grid;grid-template-columns:repeat(3,5ch);gap:0 8px;text-align:right}.rk3 i{font-style:normal}th.rk .rk3{display:grid;margin-top:2px}
.ht tr.tot th,.ht tr.tot td{border-top:1px solid var(--ink);font-weight:600}
@media (max-width:640px){.ht .co{display:none}.ht{min-width:1040px}}
.hbody{max-height:380px;overflow:auto;border:1px solid var(--rule-soft);border-radius:4px}
.lt{width:100%;min-width:860px;border-collapse:collapse;font-size:13.5px}
.lt th,.lt td{text-align:left;padding:5px 10px;border-bottom:1px solid var(--rule-soft);white-space:nowrap;width:1%}
.lt td:last-child,.lt th:last-child{width:auto;white-space:normal}
.lt thead th{position:sticky;top:0;background:var(--bg);color:var(--muted);font-weight:500;z-index:1}
.lt .num{text-align:right;font-family:'IBM Plex Mono',monospace;font-variant-numeric:tabular-nums}.lt thead th.num{font-family:inherit}
.hnote{margin:4px 0 0;font-size:13.5px;color:var(--muted);max-width:72ch}

/* The readout is one line where it fits: the date, then the values (owner, 20 Nov: the numbers took half the chart). */
@media (max-width:600px){
.ht.st .tt{--pitch:3.4px}
.tt{--pitch:min(8px, calc((100vw - 24px) / var(--n)))}
.trow{grid-template-columns:minmax(0,1fr) 64px}.trow .tt{grid-column:1/-1;grid-row:2;height:22px}
.seg-axis{grid-template-columns:minmax(0,1fr)}.seg-axis>span{display:none}.seg-axis div{width:calc(var(--n) * min(8px, calc((100vw - 24px) / var(--n))))}
}
/* Breadth by size in a half-width column: the name above its bar, so names, bars and the three readings never collide. */
@media (max-width:760px){
.tt{--pitch:min(8px, calc((100vw - 24px) / var(--n)))}
.sh-head,.shrow{grid-template-columns:minmax(0,1fr) 44px 44px 48px}.shrow .tt{grid-column:1/-1;grid-row:2}.sh-head span:nth-child(2){display:none}
.tr-head,.trrow{grid-template-columns:minmax(0,1fr) repeat(var(--nv,3),52px)}.trrow .tt{grid-column:1/-1;grid-row:2}.tr-head span:nth-child(2){display:none}
}
"""

BODY = {
    "month": ('<div class="cap"><span>{note}</span><span class="chips" role="group" aria-label="Period"></span></div>'
              '<div class="readout" aria-live="polite"></div><div class="seg-rows" role="list"></div>'
              '<div class="seg-axis" style="--n:{n}" aria-hidden="true"><span></span><div></div><span></span></div>'),
    "bars": '<div class="readout" aria-live="polite"></div><div class="chart" tabindex="0" role="img" aria-label="{label}"></div>',
    "shared": ('<div class="readout" aria-live="polite"></div><div class="sh-head" aria-hidden="true"><span>Size</span><span></span>'
               '<span class="num">3M ago</span><span class="num">1M ago</span><span class="num">Now</span></div><div id="rows" role="list"></div>'
               '<div class="key"><span><i class="k-now"></i>Now</span><span><i class="k-ago"></i>A month ago</span>'
               '<span><i class="k-line"></i>40% narrow · 60% broad</span><span>Each line {step}%</span></div>'),
    "segbar": ('<div class="readout" aria-live="polite"></div><div class="segbar" role="list" aria-label="{label}"></div>'
               '<div class="key seg-key"></div>'),
    "breadth": ('<div class="cap"><span>{note}</span><span class="chips" role="group" aria-label="Period">'
                '<button class="chip" type="button" data-range="126" aria-pressed="false">6M</button>'
                '<button class="chip" type="button" data-range="252" aria-pressed="false">12M</button>'
                '<button class="chip" type="button" data-range="0" aria-pressed="true">3Y</button></span></div>'
                '<div class="readout" aria-live="polite"></div>'
                '<div class="chart" data-pane="top" tabindex="0" role="img" aria-label="{label}"></div><div class="chart" data-pane="bottom" role="img"></div>'),
    "growth": ('<div class="ph" aria-live="polite"><span class="d"></span>'
               '<span><i style="color:var(--s-book)"></i>The book <b data-v="book"></b></span>'
               '<span><i style="color:var(--s-mom50)"></i>Momentum 50 <b data-v="mom"></b></span>'
               '<span><i class="dash" style="color:var(--s-market)"></i>Market <b data-v="market"></b></span></div>'
               '<div class="chart" data-pane="top" tabindex="0" role="img" aria-label="{label}"></div>'
               '<div class="ph"><b>Below the peak</b><span><i style="color:var(--down)"></i>book below peak <b data-v="dd"></b></span>'
               '<span><i class="dash" style="color:var(--s-market)"></i>market below peak <b data-v="ddm"></b></span></div>'
               '<div class="chart" data-pane="bottom" role="img" aria-label="The book\'s and the market\'s fall from their peaks"></div>'),
    "lines": ('<div class="cap"><span class="ph" aria-live="polite"></span><span class="chips" role="group" aria-label="Period"></span></div>'
              '<div class="chart" tabindex="0" role="img" aria-label="{label}"></div>'),
    "holdings": '<div class="hold" role="region" aria-label="{label}" tabindex="0"></div>',
    "trows": ('<div class="readout" aria-live="polite"></div><div class="tr-head" aria-hidden="true"></div>'
              '<div id="rows" role="list" aria-label="{label}"></div><div class="key">{note}</div>'),
    "rel": ('<div class="cap"><span class="chips" role="group" aria-label="Style"></span></div>'
            '<div class="readout" aria-live="polite"></div>'
            '<div class="chart" data-pane="top" tabindex="0" role="img" aria-label="{label}"></div>'
            '<div class="chart" data-pane="bottom" role="img" aria-label="How far the line sits below its best"></div>'),
    "btgrowth": ('<div class="ph p1" aria-live="polite"></div>'
                 '<div class="chart" data-pane="top" tabindex="0" role="img" aria-label="{label}"></div>'
                 '<div class="ph p2"></div>'
                 '<div class="chart" data-pane="bottom" role="img" aria-label="How far each sits below its own peak"></div>'),
    "history": ('<div class="cap"><span class="chips views" role="group" aria-label="View"></span>'
                '<span class="chips filters" role="group" aria-label="Show"></span></div>'
                '<div class="hbars" hidden><div class="readout" aria-live="polite"></div>'
                '<div class="chart" tabindex="0" role="img" aria-label="Holdings bought at each rebalance"></div></div>'
                '<div class="hbody" role="region" aria-label="{label}" tabindex="0"></div>'
                '<p class="hnote">{note}</p>'),
    "pairs": ('<div class="cap"><span class="chips" role="group" aria-label="Sector"></span></div>'
              '<div class="ph" aria-live="polite"></div><div class="chart" tabindex="0" role="img" aria-label="{label}"></div>'
              '<details><summary>{table}</summary><div class="ptab"></div></details>'),
    "lmap": ('<div class="cap"><span class="chips ema" role="group" aria-label="EMA"></span>'
             '<span class="chips per" role="group" aria-label="Period"></span>'
             '<select class="pick" aria-label="{pick}"></select></div>'
             '<div class="readout" aria-live="polite"></div><div class="chart" tabindex="0" role="img" aria-label="{label}"></div>'
             '<p class="mcap"></p><div class="mex"></div><details><summary>{table}</summary><div class="mtab"></div></details>'),
    "stable": '<div class="stab" role="region" aria-label="{label}" tabindex="0"></div><div class="key">{note}</div>',
}


def _json(obj) -> str:
    # "</" would close the <script> block that carries the data.
    return json.dumps(obj, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")


def frame_html(kind: str, spec: dict, **fill: str) -> str:
    """The chart's own document, theme values written in."""
    if kind not in KINDS:
        raise ValueError(f"unknown chart kind {kind!r}")
    class _Blank(dict):
        def __missing__(self, key):   # a label not given is left empty, not an error
            return ""
    body = BODY[kind].format_map(_Blank({k: _html.escape(str(v)) for k, v in fill.items()}))
    title = _html.escape(str(fill.get("label") or fill.get("note") or kind))
    return resolve(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>" + title + "</title>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<link rel='stylesheet' href='" + FONTS["font_css"] + "'><style>" + CSS + "</style></head>"
        "<body><div class='card' id='c'>" + body + "</div>"
        "<script src='" + KIT_SRC + "'></script>"
        "<script>window.DashCharts&&DashCharts.render(" + _json(kind) + "," + _json(spec) + ");</script>"
        "</body></html>")


def render(kind: str, spec: dict, **fill: str) -> None:
    """Draw one chart; the frame takes the height of what it draws."""
    st.iframe(frame_html(kind, spec, **fill), height="content")
