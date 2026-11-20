"""The Dashboard's interactive charts (S151, v8; owner approved 20 Nov 2026).

Each chart is a small frame that loads the shared kit, app/static/dash_charts.js,
once (the browser caches it), and draws from a JSON spec. Every chart gives its
values under the pointer, under a finger dragged across it, and with the arrow
keys; at rest it shows its latest values. Colours are the theme's: the frame
cannot see the page's CSS variables, so `tokens.resolve` writes them in.

Kinds: "month" (straight-line bars, a period switch), "bars" (monthly bars
from a zero line), "shared" (breadth by size list), "segbar" (the book by
industry), "rrg" (relative rotation) and "breadth" (the index and its breadth,
two panes, one crosshair). Rules: docs/PAGE_DESIGN.md section 4.
"""

from __future__ import annotations

import hashlib
import html as _html
import json
from pathlib import Path

import streamlit as st

from src.ui.tokens import FONTS, resolve

KINDS = ("month", "bars", "shared", "segbar", "rrg", "breadth")
# The kit's address carries its content hash, so a deploy is never drawn by a cached older kit.
_KIT = Path(__file__).resolve().parents[2] / "static" / "dash_charts.js"
KIT_SRC = "app/static/dash_charts.js?v=" + hashlib.sha256(_KIT.read_bytes()).hexdigest()[:12]

CSS = """
:root{--bg:var(--c-white);--ink:var(--c-ink);--text2:var(--c-text_2);--muted:var(--c-muted);--faint:var(--c-faint);
--rule:var(--c-rule_strong);--rule-soft:var(--c-rule_soft);--fill:var(--c-fill);--up:var(--c-up);--up-soft:var(--c-up_tint);
--down:var(--c-down);--down-soft:var(--c-down_tint);--caution:var(--c-caution);--caution-soft:var(--c-caution_tint);
--tip-bg:var(--c-ink);--tip-fg:var(--c-white);--tip-muted:var(--c-quiet)}
*{box-sizing:border-box}html,body{margin:0;background:transparent;color:var(--ink);
font-family:'IBM Plex Sans',system-ui,-apple-system,'Segoe UI',sans-serif;font-size:13.5px;line-height:1.45}
.card{display:flex;flex-direction:column;gap:8px;padding:2px 2px 6px}
.cap{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:6px 14px;font-size:12px;color:var(--muted)}
.up{color:var(--up)}.down{color:var(--down)}.watch{color:var(--caution)}.muted{color:var(--muted)}.b{font-weight:600}
.readout{display:flex;flex-wrap:wrap;gap:4px 18px;font-size:13px;align-items:flex-end;min-height:40px}
.readout .d{color:var(--muted);font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:12px;width:100%}
.ro{display:flex;align-items:baseline;gap:6px}.ro i{width:10px;height:3px;border-radius:2px;display:inline-block;transform:translateY(-3px)}
.ro b{font-family:'IBM Plex Mono',ui-monospace,monospace;font-weight:600;font-size:15px;font-variant-numeric:tabular-nums}.ro span{color:var(--muted)}
.chips{display:flex;gap:4px;background:var(--fill);border-radius:8px;padding:3px}
.chip{font:600 12px 'IBM Plex Sans',system-ui,sans-serif;color:var(--muted);background:none;border:0;border-radius:6px;padding:6px 10px;min-height:32px;cursor:pointer}
.chip[aria-pressed="true"]{background:var(--bg);color:var(--ink);box-shadow:0 1px 2px rgba(0,0,0,.12)}
.chip:focus-visible,.chart:focus-visible,.trow:focus-visible,.shrow:focus-visible,.segbar i:focus-visible{outline:2px solid var(--up);outline-offset:2px}
.chart{position:relative;touch-action:pan-y;-webkit-user-select:none;user-select:none}
.chart svg{display:block;width:100%;overflow:visible}
.chart text{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:11px;fill:var(--faint);paint-order:stroke;stroke:var(--bg);stroke-width:4px;stroke-linejoin:round}
.chart text.lbl-end{font-family:'IBM Plex Sans',system-ui,sans-serif;font-size:12px;font-weight:600}
.chart text.lbl-v{font-weight:600}
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
.key{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12px;color:var(--muted)}.key span{display:flex;align-items:center;gap:6px}
.key .k-now{width:2px;height:14px;background:var(--ink)}.key .k-ago{width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;border-bottom:6px solid var(--muted)}
.key .k-line{width:0;height:14px;border-left:1px dashed var(--muted)}
.key .dot{width:10px;height:10px;border-radius:50%;background:var(--bg);box-shadow:inset 0 0 0 1.5px var(--muted)}.key .dot.held{background:var(--caution);box-shadow:none}
.segbar{display:flex;gap:2px;height:44px;border-radius:4px;overflow:hidden}
.segbar i{display:flex;align-items:center;padding-left:8px;font-style:normal;font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;cursor:pointer;color:var(--bg)}
.segbar i.dim{opacity:.3}
.seg-strong{background:var(--up)}.seg-strong.alt{background:color-mix(in srgb,var(--up) 70%,var(--bg))}
.seg-turning{background:color-mix(in srgb,var(--caution) 45%,var(--bg))}.seg-turning.alt{background:color-mix(in srgb,var(--caution) 30%,var(--bg))}
.seg-weak{background:var(--down)}.seg-weak.alt{background:color-mix(in srgb,var(--down) 75%,var(--bg))}
.rrg{aspect-ratio:1.45/1}
@media (max-width:600px){
.tt{--pitch:min(8px, calc((100vw - 24px) / var(--n)))}
.trow{grid-template-columns:minmax(0,1fr) 64px}.trow .tt{grid-column:1/-1;grid-row:2;height:22px}
.seg-axis{grid-template-columns:minmax(0,1fr)}.seg-axis>span{display:none}.seg-axis div{width:calc(var(--n) * min(8px, calc((100vw - 24px) / var(--n))))}
.sh-head,.shrow{grid-template-columns:minmax(0,1fr) 44px 44px 48px}.shrow .tt{grid-column:1/-1;grid-row:2}.sh-head span:nth-child(2){display:none}
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
    "segbar": '<div class="readout" aria-live="polite"></div><div class="segbar" role="list" aria-label="{label}"></div>',
    "rrg": ('<div class="readout" aria-live="polite"></div><div class="chart rrg" tabindex="0" role="img" aria-label="{label}"></div>'
            '<div class="key"><span><i class="dot held"></i>Held in the book, sized by holdings</span><span><i class="dot"></i>Not held</span></div>'),
    "breadth": ('<div class="cap"><span>{note}</span><span class="chips" role="group" aria-label="Period">'
                '<button class="chip" type="button" data-range="126" aria-pressed="false">6M</button>'
                '<button class="chip" type="button" data-range="252" aria-pressed="false">1Y</button>'
                '<button class="chip" type="button" data-range="0" aria-pressed="true">3Y</button></span></div>'
                '<div class="readout" aria-live="polite"></div>'
                '<div class="chart" data-pane="top" tabindex="0" role="img" aria-label="{label}"></div><div class="chart" data-pane="bottom" role="img"></div>'),
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
