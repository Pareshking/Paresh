"""One chart component for every time series in the app.

TradingView Lightweight Charts, the same library the stock page uses, drawn in
an st.iframe with the library inlined (src/ui/vendor, Apache-2.0), so there is
no CDN to fail and no third-party Streamlit component to render blank.

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
share1 (percent, unsigned, one decimal), price (₹, two decimals: a share price),
num, int, rupee. A series may set "range": [lo, hi] to pin the value axis.
A series may set "abs": True to show magnitudes in the legend (new lows are
drawn below zero but read as positive counts).
"""
from __future__ import annotations

import html as _html
import json
from pathlib import Path

import pandas as pd
import streamlit as st
from src.ui import formats as _fmt
from src.ui.tokens import FONTS, resolve

_VENDOR = Path(__file__).parent / "vendor" / "lightweight-charts.standalone.production.js"

INDIGO, GREY, INK, AMBER, GREEN, RED = "var(--c-ink)", "var(--c-faint)", "var(--c-ink)", "var(--c-caution)", "var(--c-up)", "var(--c-down)"
GAP_PX = 6
# The legend sits above each plot on one line (a coloured dash, the name, the
# value), not over the data; this is the room it takes. A legend that wraps on
# a phone takes its second line from the plot, so the frame never grows.
LEGEND_PX = 20
# A pane never draws two series in one colour: a later repeat takes the next
# of these that the pane has not used.
SPARE = ("var(--c-ink)", "var(--c-up)", "var(--c-caution)", "var(--c-teal)", "var(--c-violet)", "var(--c-faint)", "var(--c-down)")


def _lib() -> str:
    try:
        return _VENDOR.read_text(encoding="utf-8")
    except OSError:
        return ""


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
        return _fmt.inr(v, 2)
    if fmt == "int":
        r = round(v)
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


def chart_html(panes: list[dict]) -> str:
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
    names = [s.get("name") for p in panes for s in p["series"] if s.get("name")]
    title = "Chart: " + ", ".join(dict.fromkeys(names)) if names else "Chart"
    return (
        "<!DOCTYPE html><html lang='en'><head><title>" + _html.escape(title) + "</title><meta charset='utf-8'><meta name='viewport' "
        "content='width=device-width,initial-scale=1'>"
        "<link rel='stylesheet' href='" + FONTS["google_css"] + "'><style>"
        "*{box-sizing:border-box}html,body{margin:0;background:transparent;"
        "font-family:'IBM Plex Sans',system-ui,-apple-system,'Segoe UI',sans-serif;color:var(--c-ink)}"
        ".pane{position:relative;width:100%;margin-bottom:" + str(GAP_PX) + "px}"
        ".lg{display:flex;flex-wrap:wrap;align-items:center;gap:0 16px;min-height:" + str(LEGEND_PX) + "px;"
        "padding:0 2px 4px;font-size:12px;line-height:18px;color:var(--c-muted);pointer-events:none}"
        ".lg .d{color:var(--c-faint);font-variant-numeric:tabular-nums;font-size:12px}"
        ".lg i{display:inline-block;width:12px;height:2px;border-radius:1px;margin-right:6px;vertical-align:middle;position:relative;top:-1px}"
        ".lg i.sq{width:8px;height:8px;border-radius:1px;top:-1px}"
        ".lg b{font-variant-numeric:tabular-nums;font-weight:500;color:var(--c-ink);margin-left:4px}"
        ".plot{position:relative;width:100%}"
        ".dot{position:absolute;width:6px;height:6px;margin:-3px 0 0 -3px;border-radius:50%;"
        "pointer-events:none;z-index:4;display:none}"
        ".sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}"
        "</style></head><body><p class='sr'>" + _html.escape(summary(panes)) + "</p>"
        "<div id='root' aria-hidden='true'></div><script>"
        + _lib()
        + "</script><script>(function(){"
        "const SPEC=" + _json(spec) + ";"
        "const LEGEND_PX=" + str(LEGEND_PX) + ";"
        + _JS
        + "})();</script></body></html>"
    )


_JS = r"""
const root=document.getElementById('root');
const fmts={
  pct:v=>(v>0?'+':v<0?'−':'')+Math.abs(v).toFixed(1)+'%',
  num:v=>(v<0?'−':'')+Math.abs(v).toFixed(2),
  int:v=>(Math.round(v)<0?'−':'')+Math.abs(Math.round(v)).toLocaleString('en-IN'),
  rupee:v=>(Math.round(v)<0?'−':'')+'₹'+Math.abs(Math.round(v)).toLocaleString('en-IN'),
  price:v=>(v<0?'−':'')+'₹'+Math.abs(v).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2}),
  share:v=>v.toFixed(0)+'%',
  share1:v=>v.toFixed(1)+'%',
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
const SPAN_DAYS=(function(){
  let lo=Infinity,hi=-Infinity;
  SPEC.forEach(p=>p.series.forEach(s=>{const d=s.data;if(!d.length)return;
    const a=asDate(d[0].time),b=asDate(d[d.length-1].time);
    if(!isNaN(a))lo=Math.min(lo,+a);if(!isNaN(b))hi=Math.max(hi,+b);}));
  return isFinite(lo)&&isFinite(hi)?(hi-lo)/864e5:0;})();
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
SPEC.forEach((p,pi)=>{
  const wrap=document.createElement('div');wrap.className='pane';wrap.style.height=(p.height+LEGEND_PX)+'px';
  const lg=document.createElement('div');lg.className='lg';wrap.appendChild(lg);
  const plot=document.createElement('div');plot.className='plot';wrap.appendChild(plot);
  root.appendChild(wrap);
  legends.push(lg);paint(pi,null);
  const ph=Math.max(60,p.height+LEGEND_PX-lg.offsetHeight);plot.style.height=ph+'px';
  const chart=LightweightCharts.createChart(plot,{
    width:plot.clientWidth,height:ph,
    layout:{background:{type:'solid',color:'transparent'},textColor:'var(--c-muted_2)',fontFamily:"IBM Plex Sans,system-ui,sans-serif",fontSize:11,attributionLogo:false},
    grid:{vertLines:{visible:false},horzLines:{color:'var(--c-grid)',style:0}},
    rightPriceScale:{borderVisible:false,ticksVisible:false,scaleMargins:{top:(p.top!==null&&p.top!==undefined)?p.top:0.08,bottom:p.series.some(x=>x.volume)?0.24:0.06}},
    timeScale:{visible:pi===SPEC.length-1,borderVisible:false,ticksVisible:false,timeVisible:false,allowBoldLabels:false,fixLeftEdge:true,fixRightEdge:true,rightOffset:0,
      tickMarkMaxCharacterLength:9,tickMarkFormatter:tick},
    crosshair:{mode:0,vertLine:{color:'var(--c-rule_strong)',width:1,style:0,labelBackgroundColor:'var(--c-ink_2)'},
      horzLine:{visible:false,labelVisible:true,labelBackgroundColor:'var(--c-ink_2)'}},
    handleScroll:{mouseWheel:false,pressedMouseMove:true,horzTouchDrag:true,vertTouchDrag:false},
    handleScale:{mouseWheel:false,pinch:true,axisPressedMouseMove:false},
    localization:{priceFormatter:p.series.length&&p.series[0].fmt?fmts[p.series[0].fmt]||undefined:undefined,
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
    ser.setData(s.data.map(d=>d.open!==undefined?{time:d.time,open:d.open,high:d.high,low:d.low,close:d.close}:(d.color?{time:d.time,value:d.value,color:d.color}:{time:d.time,value:d.value})));
    ss.push(ser);
    // the latest point marked with a small dot in the line's colour
    if(marked(s)&&s.data.length){
      const dot=document.createElement('div');dot.className='dot';dot.style.background=(s.type==='baseline'?(s.negColor||c):c);
      plot.appendChild(dot);ds.push({dot:dot,ser:ser,pt:s.data[s.data.length-1]});
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
      const x=charts[pi].timeScale().timeToCoordinate(o.pt.time), y=o.ser.priceToCoordinate(o.pt.value);
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
  lg.innerHTML=html+(shown?'<span class="d">'+dateText(shown)+'</span>':'');
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
if(window.ResizeObserver)new ResizeObserver(resize).observe(root);
later();
"""


def render(panes: list[dict], key: str | None = None) -> None:
    """Draw the panes in one iframe. Does nothing if no pane has two points."""
    live = [p for p in panes if any(len(s["data"]) >= 2 for s in p["series"])]
    if not live:
        return
    height = sum(int(p.get("height", 240)) + LEGEND_PX + GAP_PX for p in live) + 4
    st.iframe(resolve(chart_html(live)), height=height)
