"""One chart component for every time series in the app.

TradingView Lightweight Charts, the same library the stock page uses, drawn in
an st.iframe; the library is served once from the app's static folder (Apache-2.0),
with a pinned CDN copy as fallback, and no third-party Streamlit component.

What a reader gets that the old Altair charts could not give: a crosshair, and
a legend that shows the date and EVERY series' value under it (the latest value
when the pointer is away). Panes stack, share one time axis and one crosshair.

A pane is a dict:
    {"height": 260,
     "series": [{"name": "Strategy", "type": "line", "color": "var(--c-ink)",
                 "fmt": "rupee", "data": [("2026-01-31", 2_000_000.0), ...]}],
     "levels": [{"value": 60, "color": "var(--c-up)", "title": "60%"}]}
Series types: line, area, histogram, baseline (fills above/below zero), candlestick
(rows of (t, o, h, l, c); "up"/"down" colours; the legend reads the close).
A histogram with "volume": True sits on its own hidden scale in the bottom fifth of
the pane; an optional "colors" list colours each bar.
fmt: pct (value is already in percent, signed), share (percent, unsigned, whole),
share1 (percent, unsigned, one decimal), price (₹, whole rupees: a share price, S173),
num, int, rupee, lvl (a level such as an index set to 100, one decimal, unsigned). A series may set "range": [lo, hi] to pin the value axis.
A series may set "abs": True to show magnitudes in the legend (new lows are
drawn below zero but read as positive counts).

`one_line=True` (the stock page, S182 / STOCK_REQUIREMENTS row 48): each pane's
readout is one line at a fixed height that never wraps, the date first in the
top pane only, so moving the pointer can never move a plot (the #589 rule for
these charts); arrow keys step the reading a session at a time.

`ranges` (the stock page, S193 H2; owner, 23 Nov 2026: one period picker, in the chart): the panes carry
the longest range once, and chips in the frame redraw them in place, with no page rerun:
    {"default": "12M", "why": "lately", "chips": [["6M", "2026-05-20"], ["12M", ...], ["3Y", ...]],
     "follow": {"sel": "h2.sp-price-h", "html": {"6M": "...", ...}}}
Each chip names the first session of its range. A series with "rebase": True (relative strength) is set to
100 again at that session. `follow` rewrites one element of the host page (the stock heading's
relative-strength words) so it reads the range the chart shows.
"""
from __future__ import annotations

import html as _html
import json
from pathlib import Path

import pandas as pd
import streamlit as st
from src.ui import formats as _fmt
from src.ui.tokens import FONTS, resolve, series_var

_STATIC = Path(__file__).resolve().parents[2] / "static"
LW_VERSION = "5.2.1"
_LW_FILE = "lightweight-charts.standalone.production.js"

INDIGO, GREY, INK, GREEN, RED = "var(--c-ink)", "var(--c-faint)", "var(--c-ink)", "var(--c-up)", "var(--c-down)"
GAP_PX = 6
# The legend sits above each plot on one line (a coloured dash, the name, the
# value), not over the data; this is the room it takes. A legend that wraps on
# a phone takes its second line from the plot, so the frame never grows.
LEGEND_PX = 20
# A pane never draws two series in one colour: a later repeat takes the next
# of these that the pane has not used. Never caution (it means a warning) and
# never a SERIES colour (each means one series, S193 G): ink, blue and greys.
SPARE = ("var(--c-ink)", "var(--c-up)", "var(--c-muted)", "var(--c-faint)", "var(--c-quiet)", "var(--c-down)")


def colour_for(name: str, default: str = INK) -> str:
    """A named series' colour (tokens.SERIES), else `default`."""
    try:
        return series_var(name)
    except KeyError:
        return default


def _js_str(text: str) -> str:
    # A JS string literal that cannot close the <script> block it sits in.
    return json.dumps(text).replace("<", "\\u003c")


def loader_js(files: list[tuple[str, str]], global_name: str) -> str:
    """JavaScript that loads `files` [(static name, CDN url)] in order while the
    frame is parsing, then the CDN copies if the static ones did not define
    `global_name` (audit F60). The library was copied into every chart frame,
    0.2-0.5 MB each and never cached; a script tag is fetched once and cached
    for every frame. Relative "app/static/" resolves against the app page, as
    the frame is a srcdoc document."""
    out = []
    for name, _cdn in files:
        out.append("document.write(" + _js_str(f'<script src="app/static/{name}"></script>') + ");")
    fallback = "".join("document.write(" + _js_str(f'<script src="{cdn}"></script>') + ");" for _n, cdn in files)
    check = f"<script>if(!window.{global_name}){{{fallback}}}</script>"
    out.append("document.write(" + _js_str(check) + ");")
    return "".join(out)


def _lib() -> str:
    """A loader for the library (static folder, then the pinned CDN copy):
    it was inlined into every frame (audit F60)."""
    return loader_js([(_LW_FILE, f"https://cdn.jsdelivr.net/npm/lightweight-charts@{LW_VERSION}/dist/{_LW_FILE}")],
                     "LightweightCharts")


def _json(obj) -> str:
    # "</" would close the <script> block that carries the data.
    return json.dumps(obj, separators=(",", ":")).replace("</", "<\\/")


def series_points(index, values, *, scale: float = 1.0) -> list[tuple[str, float]]:
    """(YYYY-MM-DD, value) pairs, dropping NaN and keeping one point per day."""
    out: dict[str, float] = {}
    for ts, v in zip(pd.DatetimeIndex(index), values):
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f == f:
            out[f"{ts:%Y-%m-%d}"] = f * scale
    return sorted(out.items())


def _rows(s: dict) -> list[dict]:
    colors = s.get("colors")
    out = []
    for i, row in enumerate(s["data"]):
        if len(row) == 5:
            t, o, h, lo, c = row
            r = {"time": t, "open": o, "high": h, "low": lo, "close": c, "value": c}
        else:
            t, v = row
            r = {"time": t, "value": v}
        if colors:
            r["color"] = colors[i]
        out.append(r)
    return out


def _distinct(series: list[dict]) -> list[dict]:
    """The pane's series with any repeated line colour swapped for a spare one."""
    used: set[str] = set()
    out = []
    for s in series:
        c = s.get("color") or INK
        if c in used and s.get("type", "line") in ("line", "area"):
            c = next((x for x in SPARE if x not in used), c)
            s = {**s, "color": c}
        used.add(c)
        out.append(s)
    return out


def _value(v: float, fmt: str | None) -> str:
    if fmt == "pct":
        return _fmt.pct(v, fraction=False)
    if fmt == "share":
        return _fmt.pct(v, signed_=False, digits=0, fraction=False)
    if fmt == "share1":
        return _fmt.pct(v, signed_=False, fraction=False)
    if fmt == "rupee":
        return _fmt.inr(v)
    if fmt == "price":
        return _fmt.price(v)
    if fmt == "lvl":
        return f"{v:,.1f}"
    if fmt == "int":
        r = _fmt.half_up(v, 0)
        return (_fmt.MINUS if r < 0 else "") + _fmt.indian_group(abs(r))
    return _fmt.signed(v, 2, plus=False)


def _day(t) -> str:
    return f"{pd.Timestamp(t):%-d %b %Y}"


def summary(panes: list[dict]) -> str:
    """What the chart shows, in words, for a reader who cannot see it (audit F26):
    each series' first and last value with their dates, and its low and high."""
    parts = []
    for p in panes:
        for s in p["series"]:
            data = s.get("data") or []
            if not data:
                continue
            pts = [(row[0], row[-1]) for row in data]  # a candle reads its close
            vals = [v for _, v in pts]
            fmt = s.get("fmt")
            if s.get("abs"):
                vals = [abs(v) for v in vals]
            name = s.get("name") or "Series"
            parts.append(
                f"{name}: {_value(vals[0], fmt)} on {_day(pts[0][0])}, "
                f"{_value(vals[-1], fmt)} on {_day(pts[-1][0])}; "
                f"low {_value(min(vals), fmt)}, high {_value(max(vals), fmt)}."
            )
    return " ".join(parts)


RANGE_PX = 40   # the chips row over the first pane, when the chart carries ranges


def slice_panes(panes: list[dict], start: str) -> list[dict]:
    """The panes from `start` (YYYY-MM-DD) on, a "rebase" series set to 100 at its first point there:
    what the frame draws for a range chip (and the words a screen reader is given for it)."""
    out = []
    for p in panes:
        ser = []
        for s in p["series"]:
            keep = [(i, r) for i, r in enumerate(s.get("data") or []) if str(r[0]) >= start]
            data = [r for _, r in keep]
            if s.get("rebase") and data:
                base = data[0][-1]
                data = [(r[0], r[-1] / base * 100) for r in data] if base else data
            s2 = {**s, "data": data}
            if s.get("colors"):
                s2["colors"] = [s["colors"][i] for i, _ in keep]
            ser.append(s2)
        out.append({**p, "series": ser})
    return out


def chart_html(panes: list[dict], one_line: bool = False, label: str = "", ranges: dict | None = None) -> str:
    ranges = _check_ranges(ranges)
    summaries = ({lab: summary(slice_panes(panes, start)) for lab, start in ranges["chips"]} if ranges else {})
    spec = [
        {
            "height": int(p.get("height", 240)),
            "levels": p.get("levels", []),
            "top": p.get("top"),
            "series": [
                {**s, "data": _rows(s)}
                for s in _distinct(p["series"])
            ],
        }
        for p in panes
    ]
    first = summaries.get(ranges["default"]) if ranges else None
    names = [s.get("name") for p in panes for s in p["series"] if s.get("name")]
    title = "Chart: " + ", ".join(dict.fromkeys(names)) if names else "Chart"
    return (
        "<!DOCTYPE html><html lang='en'><head><title>" + _html.escape(title) + "</title><meta charset='utf-8'><meta name='viewport' "
        "content='width=device-width,initial-scale=1'>"
        "<link rel='stylesheet' href='" + FONTS["font_css"] + "'><style>"
        "*{box-sizing:border-box}html,body{margin:0;background:transparent;"
        "font-family:'IBM Plex Sans',system-ui,-apple-system,'Segoe UI',sans-serif;color:var(--c-ink)}"
        ".pane{position:relative;width:100%;margin-bottom:" + str(GAP_PX) + "px}"
        ".lg{display:flex;flex-wrap:wrap;align-items:center;gap:0 16px;min-height:" + str(LEGEND_PX) + "px;"
        "padding:0 2px 4px;font-size:var(--fs-12);line-height:18px;color:var(--c-muted);pointer-events:none}"
        ".lg .d{color:var(--c-faint);font-variant-numeric:tabular-nums;font-size:var(--fs-12)}"
        ".lg i{display:inline-block;width:12px;height:2px;border-radius:1px;margin-right:6px;vertical-align:middle;position:relative;top:-1px}"
        ".lg i.sq{width:8px;height:8px;border-radius:1px;top:-1px}"
        ".lg b{font-variant-numeric:tabular-nums;font-weight:500;color:var(--c-ink);margin-left:4px}"
        ".plot{position:relative;width:100%}"
        ".dot{position:absolute;width:6px;height:6px;margin:-3px 0 0 -3px;border-radius:50%;"
        "pointer-events:none;z-index:4;display:none}"
        ".sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}"
        # The range chips, as the chart kit's (dash_charts.py .chips): the one period picker (S193 H2).
        ".rg{display:flex;justify-content:flex-end;height:" + str(RANGE_PX - 6) + "px;margin-bottom:6px}"
        ".rg:empty{display:none}.rg span{display:flex;gap:4px;background:var(--c-fill);border-radius:8px;padding:3px}"
        ".rg button{font:600 var(--fs-12) 'IBM Plex Sans',system-ui,sans-serif;color:var(--c-muted);background:none;border:0;"
        "border-radius:6px;padding:4px 10px;min-height:28px;cursor:pointer}"
        ".rg button[aria-pressed='true']{background:var(--c-white);color:var(--c-ink);box-shadow:0 1px 2px rgba(0,0,0,.12)}"
        ".rg button:focus-visible{outline:2px solid var(--c-up);outline-offset:2px}"
        + (_ONE_LINE_CSS if one_line else "") +
        "</style></head><body><p class='sr'>" + _html.escape(first if first is not None else summary(panes)) + "</p>"
        + ("<div class='rg' role='group' aria-label='Range'></div>" if ranges else "")
        + ("<div id='root' role='img' tabindex='0' aria-label='" + _html.escape(label or "Chart. Arrow keys move the reading.", quote=True) + "'></div>"
           if one_line else "<div id='root' aria-hidden='true'></div>") + "<script>"
        + _lib()
        + "</script><script>(function(){"
        "const SPEC=" + _json(spec) + ";"
        "const LEGEND_PX=" + str(LEGEND_PX) + ";"
        "const ONE_LINE=" + ("true" if one_line else "false") + ";"
        "const RANGES=" + _json(ranges) + ";const SUMMARY=" + _json(summaries) + ";"
        + _JS
        + "})();</script></body></html>"
    )


# One line at a fixed height: the readout cannot wrap, so no reading can push a plot down
# (owner, 22 Nov 2026: "Mock up chart is jumping"; STOCK_REQUIREMENTS row 48).
_ONE_LINE_CSS = (
    ".lg{flex-wrap:nowrap;white-space:nowrap;overflow:hidden;height:" + str(LEGEND_PX) + "px;min-height:0;"
    "line-height:16px;padding-bottom:4px}"
    ".lg>span{flex:none}"
    "#root{outline:none;touch-action:pan-y}#root:focus-visible{box-shadow:0 0 0 2px var(--c-up)}"
)


_JS = r"""
const root=document.getElementById('root');
/* Ranges (S193 H2): every series keeps its full data in FULL; SPEC holds what is drawn. */
const FULL=SPEC.map(p=>p.series.map(s=>s.data.slice()));
function cut(label){
  const c=RANGES&&RANGES.chips.find(x=>x[0]===label);const from=c?c[1]:'';
  SPEC.forEach((p,pi)=>p.series.forEach((s,si)=>{let d=FULL[pi][si].filter(r=>r.time>=from);
    if(s.rebase&&d.length){const b=d[0].value;if(b)d=d.map(r=>Object.assign({},r,{value:r.value/b*100}));}
    s.data=d;}));
}
if(RANGES)cut(RANGES.default);
/* Half away from zero on the decimal value (glossary 12), as formats.half_up and dash_charts.js's rnd. */
const rnd=(v,dp=0)=>{const a=Math.abs(v),t=String(a);const r=/e/.test(t)?+a.toFixed(dp):+(Math.round(+(t+'e'+dp))+'e-'+dp);return v<0&&r?-r:r;};
const grp=(v,dp)=>Math.abs(rnd(v,dp)).toLocaleString('en-IN',{minimumFractionDigits:dp,maximumFractionDigits:dp});
const sgn=(v,dp,plus)=>{const r=rnd(v,dp);return r>0?(plus?'+':''):r<0?'−':'';};
const fmts={
  pct:v=>sgn(v,1,true)+Math.abs(rnd(v,1)).toFixed(1)+'%',
  num:v=>sgn(v,2)+Math.abs(rnd(v,2)).toFixed(2),
  int:v=>sgn(v,0)+grp(v,0),
  rupee:v=>sgn(v,0)+'₹'+grp(v,0),
  price:v=>sgn(v,0)+'₹'+grp(v,0),  // whole rupees (S173)
  share:v=>sgn(v,0)+Math.abs(rnd(v,0)).toFixed(0)+'%',
  share1:v=>sgn(v,1)+Math.abs(rnd(v,1)).toFixed(1)+'%',
  lvl:v=>sgn(v,1)+grp(v,1),
};
const MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function esc(v){return String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function asDate(t){
  if(t&&typeof t==='object'&&t.year)return new Date(t.year,t.month-1,t.day);
  if(typeof t==='number')return new Date(t*1000);
  return new Date(String(t)+'T00:00:00');
}
// Sparse, plain date ticks: "Jan 26 · May · Sep". Day ticks ("11 Jun") only
// on a chart shorter than about two and a half months; on a longer one they
// sat between the month names as a second kind of tick (audit F47/V13).
let SPAN_DAYS=0;
function spanDays(){
  let lo=Infinity,hi=-Infinity;
  SPEC.forEach(p=>p.series.forEach(s=>{const d=s.data;if(!d.length)return;
    const a=asDate(d[0].time),b=asDate(d[d.length-1].time);
    if(!isNaN(a))lo=Math.min(lo,+a);if(!isNaN(b))hi=Math.max(hi,+b);}));
  return isFinite(lo)&&isFinite(hi)?(hi-lo)/864e5:0;}
SPAN_DAYS=spanDays();
function tick(t,type){
  const d=asDate(t);if(isNaN(d))return null;
  if(type===0)return MON[d.getMonth()]+' '+String(d.getFullYear()).slice(2);
  if(type===1)return MON[d.getMonth()];
  if(type===2)return SPAN_DAYS<75?d.getDate()+' '+MON[d.getMonth()]:'';
  return null;
}
const charts=[], legends=[], seriesByPane=[], plots=[], dots=[];
let syncing=false;
function colorOf(s){return s.color||'var(--c-ink)';}
function tint(c,a){return /^#[0-9a-fA-F]{6}$/.test(c)?c+a:c;}
function marked(s){return s.type!=='histogram'&&s.type!=='candlestick';}
function pointOf(d){return d.open!==undefined?{time:d.time,open:d.open,high:d.high,low:d.low,close:d.close}:(d.color?{time:d.time,value:d.value,color:d.color}:{time:d.time,value:d.value});}
SPEC.forEach((p,pi)=>{
  const wrap=document.createElement('div');wrap.className='pane';wrap.style.height=(p.height+LEGEND_PX)+'px';
  const lg=document.createElement('div');lg.className='lg';wrap.appendChild(lg);
  const plot=document.createElement('div');plot.className='plot';wrap.appendChild(plot);
  root.appendChild(wrap);
  legends.push(lg);paint(pi,null);
  const ph=Math.max(60,p.height+LEGEND_PX-lg.offsetHeight);plot.style.height=ph+'px';
  const chart=LightweightCharts.createChart(plot,{
    width:plot.clientWidth,height:ph,
    layout:{background:{type:'solid',color:'transparent'},textColor:'var(--c-muted_2)',fontFamily:"IBM Plex Sans,system-ui,sans-serif",fontSize:12,attributionLogo:false},
    grid:{vertLines:{visible:false},horzLines:{color:'var(--c-grid)',style:0}},
    rightPriceScale:{borderVisible:false,ticksVisible:false,scaleMargins:{top:(p.top!==null&&p.top!==undefined)?p.top:0.08,bottom:p.series.some(x=>x.volume)?0.24:0.06}},
    timeScale:{visible:pi===SPEC.length-1,borderVisible:false,ticksVisible:false,timeVisible:false,allowBoldLabels:false,fixLeftEdge:true,fixRightEdge:true,rightOffset:0,
      tickMarkMaxCharacterLength:9,tickMarkFormatter:tick},
    crosshair:{mode:0,vertLine:{color:'var(--c-rule_strong)',width:1,style:0,labelBackgroundColor:'var(--c-ink_2)'},
      horzLine:{visible:false,labelVisible:true,labelBackgroundColor:'var(--c-ink_2)'}},
    handleScroll:{mouseWheel:false,pressedMouseMove:true,horzTouchDrag:true,vertTouchDrag:false},
    handleScale:{mouseWheel:false,pinch:true,axisPressedMouseMove:false},
    localization:{priceFormatter:(p.series.length&&p.series[0].fmt&&fmts[p.series[0].fmt])||fmts.num,  /* a true minus on every axis (S173 rule 4) */
      timeFormatter:t=>dateText(t)},
  });
  const ss=[], ds=[];
  p.series.forEach(s=>{
    let ser;
    const f=fmts[s.fmt||'num'];
    const pf={type:'custom',formatter:f,minMove:0.01};
    const c=colorOf(s), lw=s.width||1.5;
    const mk={crosshairMarkerRadius:3,crosshairMarkerBorderColor:'var(--c-white)',crosshairMarkerBorderWidth:1.5};
    if(s.type==='candlestick'){
      ser=chart.addSeries(LightweightCharts.CandlestickSeries,{upColor:s.up||'var(--c-up)',downColor:s.down||'var(--c-down)',borderUpColor:s.up||'var(--c-up)',borderDownColor:s.down||'var(--c-down)',wickUpColor:s.up||'var(--c-up)',wickDownColor:s.down||'var(--c-down)',priceFormat:pf,priceLineVisible:false,lastValueVisible:false});
    }else if(s.type==='histogram'&&s.volume){
      ser=chart.addSeries(LightweightCharts.HistogramSeries,{color:c,priceFormat:pf,priceScaleId:'vol',priceLineVisible:false,lastValueVisible:false});
      chart.priceScale('vol').applyOptions({scaleMargins:{top:0.8,bottom:0},visible:false});
    }else if(s.type==='histogram'){
      ser=chart.addSeries(LightweightCharts.HistogramSeries,{color:c,priceFormat:pf,priceLineVisible:false,lastValueVisible:false});
    }else if(s.type==='area'){
      // a flat pale tint under the line: no gradient
      ser=chart.addSeries(LightweightCharts.AreaSeries,Object.assign({lineColor:c,topColor:tint(c,'1A'),bottomColor:tint(c,'1A'),lineWidth:lw,priceFormat:pf,priceLineVisible:false,lastValueVisible:false},mk));
    }else if(s.type==='baseline'){
      const up=s.color||'var(--c-up)', dn=s.negColor||'var(--c-down)';
      // Below the base (a drawdown: below its high) is a flat pale tint.
      // When both sides share one colour only the side under the base is
      // filled, so a drawdown reads as the distance below the high.
      const topFill=up===dn?tint(up,'00'):tint(up,'1A');
      ser=chart.addSeries(LightweightCharts.BaselineSeries,Object.assign({baseValue:{type:'price',price:s.base||0},
        topLineColor:up,bottomLineColor:dn,topFillColor1:topFill,topFillColor2:topFill,
        bottomFillColor1:tint(dn,'1F'),bottomFillColor2:tint(dn,'1F'),
        lineWidth:lw,priceFormat:pf,priceLineVisible:false,lastValueVisible:false},mk));
    }else{
      ser=chart.addSeries(LightweightCharts.LineSeries,Object.assign({color:c,lineWidth:lw,priceFormat:pf,priceLineVisible:false,lastValueVisible:false},mk));
    }
    if(s.range){ser.applyOptions({autoscaleInfoProvider:()=>({priceRange:{minValue:s.range[0],maxValue:s.range[1]}})});}
    ser.setData(s.data.map(pointOf));
    ss.push(ser);
    // the latest point marked with a small dot in the line's colour
    if(marked(s)&&s.data.length){
      const dot=document.createElement('div');dot.className='dot';dot.style.background=(s.type==='baseline'?(s.negColor||c):c);
      plot.appendChild(dot);ds.push({dot:dot,ser:ser,s:s});
    }
  });
  (p.levels||[]).forEach(l=>{
    if(ss.length)ss[0].createPriceLine({price:l.value,color:tint(l.color||'var(--c-faint)','99'),lineWidth:1,lineStyle:3,
      axisLabelVisible:true,axisLabelColor:'var(--c-white)',axisLabelTextColor:l.color||'var(--c-muted)',title:''});
  });
  chart.timeScale().fitContent();
  charts.push(chart);seriesByPane.push(ss);plots.push(plot);dots.push(ds);
});
function placeDots(){
  dots.forEach((ds,pi)=>{
    const w=plots[pi].clientWidth-charts[pi].priceScale('right').width();
    ds.forEach(o=>{
      const pt=o.s.data[o.s.data.length-1];if(!pt){o.dot.style.display='none';return;}
      const x=charts[pi].timeScale().timeToCoordinate(pt.time), y=o.ser.priceToCoordinate(pt.value);
      if(x===null||y===null||x<0||x>w){o.dot.style.display='none';return;}
      o.dot.style.display='block';o.dot.style.left=x+'px';o.dot.style.top=y+'px';
    });
  });
}
function later(){requestAnimationFrame(()=>requestAnimationFrame(placeDots));}
function keyOf(t){return typeof t==='string'?t:t.year+'-'+String(t.month).padStart(2,'0')+'-'+String(t.day).padStart(2,'0');}
function dateText(t){
  const d=asDate(t);
  return isNaN(d)?String(t):d.toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});
}
function paint(pi,time){
  const p=SPEC[pi],lg=legends[pi];
  let html='';
  let shown=null;
  p.series.forEach((s,si)=>{
    const data=s.data;let pt=null;
    if(time){
      // the point at this date, else the latest one at or before it
      const key=keyOf(time);
      for(let i=data.length-1;i>=0;i--){if(data[i].time<=key){pt=data[i];break;}}
    }else{pt=data[data.length-1];}
    if(!pt)return;
    if(!shown)shown=pt.time;
    let v=pt.value;if(s.abs)v=Math.abs(v);
    const f=fmts[s.fmt||'num'];
    const sw=s.type==='baseline'?(s.negColor||colorOf(s)):colorOf(s);
    html+='<span><i class="'+(marked(s)?'':'sq')+'" style="background:'+sw+'"></i>'+esc(s.name)+'<b>'+f(v)+'</b></span>';
  });
  const day=shown?'<span class="d">'+dateText(shown)+'</span>':'';
  // One line: the date leads, in the top pane only (the panes share one date).
  lg.innerHTML=ONE_LINE?(pi===0?day+html:html):html+day;
}
charts.forEach((c,ci)=>{
  c.subscribeCrosshairMove(param=>{
    if(syncing)return;
    syncing=true;
    if(!param.time){
      charts.forEach((o,oi)=>{if(oi!==ci)o.clearCrosshairPosition();});
      SPEC.forEach((p,pi)=>paint(pi,null));
    }else{
      SPEC.forEach((p,pi)=>paint(pi,param.time));
      charts.forEach((o,oi)=>{
        if(oi===ci)return;
        const ser=seriesByPane[oi][0];
        const d=SPEC[oi].series[0].data;
        const key=keyOf(param.time);
        let pt=null;for(let i=d.length-1;i>=0;i--){if(d[i].time<=key){pt=d[i];break;}}
        if(pt)o.setCrosshairPosition(pt.value,pt.time,ser);
      });
    }
    syncing=false;
  });
  c.timeScale().subscribeVisibleLogicalRangeChange(r=>{
    later();
    if(syncing||!r)return;syncing=true;
    charts.forEach((o,oi)=>{if(oi!==ci)o.timeScale().setVisibleLogicalRange(r);});
    syncing=false;
  });
});
function resize(){
  charts.forEach((c,i)=>{
    const p=SPEC[i], h=Math.max(60,p.height+LEGEND_PX-legends[i].offsetHeight);
    plots[i].style.height=h+'px';c.applyOptions({width:root.clientWidth,height:h});
  });
  later();
}
window.addEventListener('resize',resize);
if(ONE_LINE){
  // Arrow keys step the reading a session at a time (PAGE_DESIGN 4.1); leaving the chart shows the latest.
  let ki=-1;
  const at=(d,key)=>{for(let i=d.length-1;i>=0;i--){if(d[i].time<=key)return d[i];}return null;};
  root.addEventListener('keydown',ev=>{
    if(ev.key!=='ArrowLeft'&&ev.key!=='ArrowRight')return;
    const d=SPEC[0].series[0].data;if(!d.length)return;
    ev.preventDefault();
    if(ki<0)ki=d.length-1;
    ki=Math.max(0,Math.min(d.length-1,ki+(ev.key==='ArrowLeft'?-1:1)));
    const t=d[ki].time;
    syncing=true;
    charts.forEach((c,ci)=>{const pt=at(SPEC[ci].series[0].data,t);if(pt)c.setCrosshairPosition(pt.value,pt.time,seriesByPane[ci][0]);});
    SPEC.forEach((p,pi)=>paint(pi,t));
    syncing=false;
  });
  root.addEventListener('blur',()=>{ki=-1;charts.forEach(c=>c.clearCrosshairPosition());SPEC.forEach((p,pi)=>paint(pi,null));});
}
if(window.ResizeObserver)new ResizeObserver(resize).observe(root);
/* The chips: one press redraws every pane from the data already here (no page rerun), sets relative strength
   to 100 at the range's first session, and rewrites the host heading that names the range (S193 H2). */
function mark(label){
  const d=SPEC[0].series[0].data, f=FULL[0][0];
  Object.assign(root.dataset,{rangeDefault:RANGES.default,rangeWhy:RANGES.why,rangeShown:label,
    rangeFrom:d.length?d[0].time:'',rangeTo:d.length?d[d.length-1].time:'',rangeFirst:f.length?f[0].time:''});
  const sr=document.querySelector('.sr');if(sr&&SUMMARY[label]!=null)sr.textContent=SUMMARY[label];
  const fw=RANGES.follow;
  if(fw&&fw.html&&fw.html[label]!=null){try{const h=window.parent.document.querySelector(fw.sel);if(h)h.innerHTML=fw.html[label];}catch(e){}}
}
function pick(label){
  cut(label);SPAN_DAYS=spanDays();
  SPEC.forEach((p,pi)=>p.series.forEach((s,si)=>seriesByPane[pi][si].setData(s.data.map(pointOf))));
  charts.forEach(c=>{c.clearCrosshairPosition();c.timeScale().fitContent();});
  SPEC.forEach((p,pi)=>paint(pi,null));mark(label);later();
}
if(RANGES){
  const rg=document.querySelector('.rg'), box=document.createElement('span');rg.appendChild(box);
  RANGES.chips.forEach(([label])=>{const b=document.createElement('button');b.type='button';b.textContent=label;
    b.setAttribute('aria-pressed',String(label===RANGES.default));
    b.addEventListener('click',()=>{box.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));pick(label);});
    box.appendChild(b);});
  mark(RANGES.default);
}
later();
"""


def _check_ranges(ranges: dict | None) -> dict | None:
    """A range set states its default and why (S193 H, as dash_charts.check_range), and the default is a chip."""
    if ranges is None:
        return None
    from src.ui.dash_charts import check_range
    check_range({**ranges, "chips": [c[0] for c in ranges.get("chips", [])]})
    if not ranges.get("chips"):
        raise ValueError("a chart with ranges has chips")
    return ranges


def render(panes: list[dict], key: str | None = None, one_line: bool = False, label: str = "",
           ranges: dict | None = None) -> None:
    """Draw the panes in one iframe. Does nothing if no pane has two points."""
    live = [p for p in panes if any(len(s["data"]) >= 2 for s in p["series"])]
    if not live:
        return
    height = sum(int(p.get("height", 240)) + LEGEND_PX + GAP_PX for p in live) + 4 + (RANGE_PX if ranges else 0)
    st.iframe(resolve(chart_html(live, one_line=one_line, label=label, ranges=ranges)), height=height)
