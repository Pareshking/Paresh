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
fmt: pct (value is already in percent, signed), share (percent, unsigned),
num, int, rupee. A series may set "range": [lo, hi] to pin the value axis.
A series may set "abs": True to show magnitudes in the legend (new lows are
drawn below zero but read as positive counts).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st
from src.ui.tokens import resolve

_VENDOR = Path(__file__).parent / "vendor" / "lightweight-charts.standalone.production.js"

INDIGO, GREY, INK, AMBER, GREEN, RED = "var(--c-ink)", "var(--c-faint)", "var(--c-ink)", "var(--c-caution)", "var(--c-up)", "var(--c-down)"
GAP_PX = 6
LEGEND_PX = 0


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


def chart_html(panes: list[dict]) -> str:
    spec = [
        {
            "height": int(p.get("height", 240)),
            "levels": p.get("levels", []),
            "top": p.get("top"),
            "series": [
                {**s, "data": _rows(s)}
                for s in p["series"]
            ],
        }
        for p in panes
    ]
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' "
        "content='width=device-width,initial-scale=1'><style>"
        "*{box-sizing:border-box}html,body{margin:0;background:transparent;"
        "font-family:'IBM Plex Sans',system-ui,-apple-system,'Segoe UI',sans-serif;color:var(--c-ink)}"
        ".pane{position:relative;width:100%;margin-bottom:" + str(GAP_PX) + "px}"
        ".lg{position:absolute;left:8px;top:4px;z-index:5;font-size:12px;line-height:1.5;"
        "pointer-events:none;display:flex;flex-wrap:wrap;gap:2px 14px;max-width:calc(100% - 70px)}"
        ".lg .d{color:var(--c-muted);font-weight:600}"
        ".lg i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px}"
        ".lg b{font-family:'IBM Plex Mono',ui-monospace,monospace;font-weight:600}"
        "</style></head><body><div id='root'></div><script>"
        + _lib()
        + "</script><script>(function(){"
        "const SPEC=" + _json(spec) + ";"
        + _JS
        + "})();</script></body></html>"
    )


_JS = r"""
const root=document.getElementById('root');
const fmts={
  pct:v=>(v>0?'+':v<0?'−':'')+Math.abs(v).toFixed(1)+'%',
  num:v=>v.toFixed(2),
  int:v=>Math.round(v).toLocaleString('en-US'),
  rupee:v=>'₹'+Math.round(v).toLocaleString('en-US'),
  share:v=>v.toFixed(0)+'%',
  share1:v=>v.toFixed(1)+'%',
};
const charts=[], legends=[], seriesByPane=[];
let syncing=false;
function colorOf(s){return s.color||'var(--c-ink)';}
SPEC.forEach((p,pi)=>{
  const wrap=document.createElement('div');wrap.className='pane';wrap.style.height=p.height+'px';
  const lg=document.createElement('div');lg.className='lg';wrap.appendChild(lg);
  root.appendChild(wrap);
  const chart=LightweightCharts.createChart(wrap,{
    width:wrap.clientWidth,height:p.height,
    layout:{background:{type:'solid',color:'transparent'},textColor:'var(--c-muted)',fontFamily:"IBM Plex Sans,system-ui,sans-serif",fontSize:12,attributionLogo:false},
    grid:{vertLines:{visible:false},horzLines:{color:'var(--c-rule_soft)'}},
    rightPriceScale:{borderVisible:false,scaleMargins:{top:(p.top!==null&&p.top!==undefined)?p.top:0.16,bottom:p.series.some(x=>x.volume)?0.24:0.06}},
    timeScale:{visible:pi===SPEC.length-1,borderVisible:false,timeVisible:false,fixLeftEdge:true,fixRightEdge:true,rightOffset:0},
    crosshair:{mode:0,vertLine:{color:'var(--c-faint)',width:1,style:3,labelBackgroundColor:'var(--c-ink)'},horzLine:{color:'var(--c-faint)',width:1,style:3,labelBackgroundColor:'var(--c-ink)'}},
    handleScroll:{mouseWheel:false,pressedMouseMove:true,horzTouchDrag:true,vertTouchDrag:false},
    handleScale:{mouseWheel:false,pinch:true,axisPressedMouseMove:false},
    localization:{priceFormatter:p.series.length&&p.series[0].fmt?fmts[p.series[0].fmt]||undefined:undefined},
  });
  const ss=[];
  p.series.forEach(s=>{
    let ser;
    const f=fmts[s.fmt||'num'];
    const pf={type:'custom',formatter:f,minMove:0.01};
    if(s.type==='candlestick'){
      ser=chart.addSeries(LightweightCharts.CandlestickSeries,{upColor:s.up||'var(--c-up)',downColor:s.down||'var(--c-down)',borderUpColor:s.up||'var(--c-up)',borderDownColor:s.down||'var(--c-down)',wickUpColor:s.up||'var(--c-up)',wickDownColor:s.down||'var(--c-down)',priceFormat:pf,priceLineVisible:false,lastValueVisible:false});
    }else if(s.type==='histogram'&&s.volume){
      ser=chart.addSeries(LightweightCharts.HistogramSeries,{color:colorOf(s),priceFormat:pf,priceScaleId:'vol',priceLineVisible:false,lastValueVisible:false});
      chart.priceScale('vol').applyOptions({scaleMargins:{top:0.8,bottom:0},visible:false});
    }else if(s.type==='histogram'){
      ser=chart.addSeries(LightweightCharts.HistogramSeries,{color:colorOf(s),priceFormat:pf,priceLineVisible:false,lastValueVisible:false});
    }else if(s.type==='area'){
      ser=chart.addSeries(LightweightCharts.AreaSeries,{lineColor:colorOf(s),topColor:colorOf(s)+'33',bottomColor:colorOf(s)+'05',lineWidth:2,priceFormat:pf,priceLineVisible:false,lastValueVisible:false});
    }else if(s.type==='baseline'){
      ser=chart.addSeries(LightweightCharts.BaselineSeries,{baseValue:{type:'price',price:s.base||0},
        topLineColor:s.color||'var(--c-up)',bottomLineColor:s.negColor||'var(--c-down)',
        topFillColor1:(s.color||'var(--c-up)')+'33',topFillColor2:(s.color||'var(--c-up)')+'05',
        bottomFillColor1:(s.negColor||'var(--c-down)')+'05',bottomFillColor2:(s.negColor||'var(--c-down)')+'33',
        lineWidth:2,priceFormat:pf,priceLineVisible:false,lastValueVisible:false});
    }else{
      ser=chart.addSeries(LightweightCharts.LineSeries,{color:colorOf(s),lineWidth:s.width||2,priceFormat:pf,priceLineVisible:false,lastValueVisible:false,crosshairMarkerRadius:4});
    }
    if(s.range){ser.applyOptions({autoscaleInfoProvider:()=>({priceRange:{minValue:s.range[0],maxValue:s.range[1]}})});}
    ser.setData(s.data.map(d=>d.open!==undefined?{time:d.time,open:d.open,high:d.high,low:d.low,close:d.close}:(d.color?{time:d.time,value:d.value,color:d.color}:{time:d.time,value:d.value})));
    ss.push(ser);
  });
  (p.levels||[]).forEach(l=>{
    if(ss.length)ss[0].createPriceLine({price:l.value,color:l.color||'var(--c-faint)',lineWidth:1,lineStyle:2,axisLabelVisible:true,title:''});
  });
  chart.timeScale().fitContent();
  charts.push(chart);legends.push(lg);seriesByPane.push(ss);
});
function dateText(t){
  if(typeof t==='string')t=t;
  else if(t&&t.year)t=t.year+'-'+String(t.month).padStart(2,'0')+'-'+String(t.day).padStart(2,'0');
  const d=new Date(t+'T00:00:00');
  return isNaN(d)?String(t):d.toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'});
}
function paint(pi,time){
  const p=SPEC[pi],lg=legends[pi];
  let html='';
  let shown=null;
  p.series.forEach((s,si)=>{
    const data=s.data;let pt=null;
    if(time){
      // the point at this date, else the latest one at or before it
      const key=typeof time==='string'?time:time.year+'-'+String(time.month).padStart(2,'0')+'-'+String(time.day).padStart(2,'0');
      for(let i=data.length-1;i>=0;i--){if(data[i].time<=key){pt=data[i];break;}}
    }else{pt=data[data.length-1];}
    if(!pt)return;
    if(!shown)shown=pt.time;
    let v=pt.value;if(s.abs)v=Math.abs(v);
    const f=fmts[s.fmt||'num'];
    html+='<span><i style="background:'+colorOf(s)+'"></i>'+s.name+' <b>'+f(v)+'</b></span>';
  });
  lg.innerHTML=(shown?'<span class="d">'+dateText(shown)+'</span>':'')+html;
}
SPEC.forEach((p,pi)=>paint(pi,null));
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
        const key=typeof param.time==='string'?param.time:param.time.year+'-'+String(param.time.month).padStart(2,'0')+'-'+String(param.time.day).padStart(2,'0');
        let pt=null;for(let i=d.length-1;i>=0;i--){if(d[i].time<=key){pt=d[i];break;}}
        if(pt)o.setCrosshairPosition(pt.value,pt.time,ser);
      });
    }
    syncing=false;
  });
  c.timeScale().subscribeVisibleLogicalRangeChange(r=>{
    if(syncing||!r)return;syncing=true;
    charts.forEach((o,oi)=>{if(oi!==ci)o.timeScale().setVisibleLogicalRange(r);});
    syncing=false;
  });
});
function resize(){charts.forEach((c,i)=>c.applyOptions({width:root.clientWidth}));}
window.addEventListener('resize',resize);
if(window.ResizeObserver)new ResizeObserver(resize).observe(root);
"""


def render(panes: list[dict], key: str | None = None) -> None:
    """Draw the panes in one iframe. Does nothing if no pane has two points."""
    live = [p for p in panes if any(len(s["data"]) >= 2 for s in p["series"])]
    if not live:
        return
    height = sum(int(p.get("height", 240)) + GAP_PX for p in live) + 4
    st.iframe(resolve(chart_html(live)), height=height)
