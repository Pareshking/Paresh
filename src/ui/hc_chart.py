"""One chart component for every time series in the app.

Highcharts Stock, drawn in an st.iframe with the library inlined (src/ui/vendor;
Highsoft EULA, non-commercial personal use), so there is no CDN to fail and no
third-party Streamlit component to render blank.

What a reader gets: a crosshair, and a legend that shows the date and EVERY
series' value under it (the latest value when the pointer is away). Panes stack,
share one time axis and one crosshair.

A pane is a dict:
    {"height": 260,
     "series": [{"name": "Strategy", "type": "line", "color": "#4F46E5",
                 "fmt": "rupee", "data": [("2026-01-31", 2_000_000.0), ...]}],
     "levels": [{"value": 60, "color": "#067647", "title": "60%"}]}
Series types: line, area, histogram, baseline (fills above/below zero).
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

_VENDOR = Path(__file__).parent / "vendor" / "highstock.js"

INDIGO, GREY, INK, AMBER, GREEN, RED = "#4F46E5", "#98A1AE", "#0E1726", "#B54708", "#067647", "#B42318"
GAP_PX = 8
LEGEND_PX = 26


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
    """A series' data as JSON rows. (t, v) pairs; (t, o, h, l, c) for a candlestick,
    whose value is the close; an optional "colors" list colours each bar."""
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
    spec = {
        "gap": GAP_PX,
        "leg": LEGEND_PX,
        "panes": [
            {
                "height": int(p.get("height", 240)),
                "levels": p.get("levels", []),
                "top": p.get("top"),
                "series": [{**s, "data": _rows(s)} for s in p["series"]],
            }
            for p in panes
        ],
    }
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' "
        "content='width=device-width,initial-scale=1'><style>"
        "*{box-sizing:border-box}html,body{margin:0;background:transparent;"
        "font-family:'Geist',system-ui,-apple-system,'Segoe UI',sans-serif;color:#0E1726}"
        ".lg{font-size:12px;line-height:1.5;min-height:20px;padding:0 2px 4px;"
        "display:flex;flex-wrap:wrap;gap:2px 14px;pointer-events:none}"
        ".lg .d{color:#5E6878;font-weight:600}"
        ".lg i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px}"
        ".lg b{font-family:'Geist Mono',ui-monospace,monospace;font-weight:600}"
        "</style></head><body><div id='root'></div><script>"
        + _lib()
        + "</script><script>(function(){"
        "const SPEC=" + _json(spec) + ";"
        + _JS
        + "})();</script></body></html>"
    )


_JS = r"""
const fmts={
  pct:v=>(v>0?'+':v<0?'\u2212':'')+Math.abs(v).toFixed(1)+'%',
  num:v=>v.toFixed(2),
  int:v=>Math.round(v).toLocaleString('en-US'),
  rupee:v=>'\u20b9'+Math.round(v).toLocaleString('en-US'),
  share:v=>v.toFixed(0)+'%',
  share1:v=>v.toFixed(1)+'%',
};
const axf=Object.assign({},fmts,{rupee:v=>{const a=Math.abs(v),sg=v<0?'\u2212':'';
  return a>=1e7?sg+'\u20b9'+(a/1e7).toFixed(a%1e7?2:0)+'Cr':a>=1e5?sg+'\u20b9'+(a/1e5).toFixed(a%1e5?1:0)+'L':sg+'\u20b9'+Math.round(a).toLocaleString('en-US');}});
const FONT="Geist,system-ui,-apple-system,'Segoe UI',sans-serif";
const GAP=SPEC.gap, LEG=SPEC.leg;
const root=document.getElementById('root');
const lg=document.createElement('div');lg.className='lg';root.appendChild(lg);
const box=document.createElement('div');root.appendChild(box);
function ms(d){const p=d.split('-');return Date.UTC(+p[0],+p[1]-1,+p[2]);}
function dateText(t){return new Date(t).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric',timeZone:'UTC'});}
const yAxis=[],series=[],meta=[];
let top=4;
SPEC.panes.forEach((p,pi)=>{
  const first=p.series[0]||{};
  const rng=first.range;
  const ax={top:top,height:p.height,offset:0,opposite:true,title:{text:null},lineWidth:0,
    gridLineColor:'#EDEFF3',gridLineWidth:1,tickAmount:p.tickAmount||undefined,
    labels:{align:'left',x:6,y:4,style:{color:'#5E6878',fontSize:'12px'},formatter:function(){return (axf[first.fmt||'num'])(this.value);}},
    startOnTick:false,endOnTick:false,maxPadding:(p.top!=null?p.top:0.08),minPadding:0.04,
    plotLines:(p.levels||[]).map(l=>({value:l.value,color:l.color||'#98A1AE',width:1,dashStyle:'Dash',zIndex:3}))};
  if(rng){ax.min=rng[0];ax.max=rng[1];ax.startOnTick=false;ax.endOnTick=false;}
  if(p.series.some(s=>s.volume))ax.height=Math.round(p.height*0.78);
  yAxis.push(ax);
  const pAx=yAxis.length-1;
  let volAx=-1;
  if(p.series.some(s=>s.volume)){
    volAx=yAxis.length;
    yAxis.push({top:top+Math.round(p.height*0.8),height:Math.round(p.height*0.2),offset:0,opposite:true,title:{text:null},
      labels:{enabled:false},gridLineWidth:0,lineWidth:0,startOnTick:false,endOnTick:false,min:0});
  }
  p.series.forEach(s=>{
    const col=s.color||'#4F46E5';
    const data=s.data.map(d=>d.open!==undefined?[ms(d.time),d.open,d.high,d.low,d.close]:(d.color?{x:ms(d.time),y:d.value,color:d.color}:[ms(d.time),d.value]));
    const o={name:s.name,data:data,yAxis:s.volume?volAx:pAx,color:col,marker:{enabled:false,states:{hover:{enabled:true,radius:4}}},
      states:{hover:{lineWidthPlus:0}},enableMouseTracking:true,showInLegend:false,animation:false,dataGrouping:{enabled:false},
      lineWidth:s.width||2,threshold:null};
    if(s.type==='histogram'){o.type='column';o.threshold=0;o.pointPadding=0;o.groupPadding=0.05;o.borderWidth=0;o.borderRadius=0;}
    else if(s.type==='candlestick'){o.type='candlestick';o.color=s.down||'#B42318';o.upColor=s.up||'#067647';o.lineColor=o.color;o.upLineColor=o.upColor;}
    else if(s.type==='area'){o.type='area';o.threshold=0;o.fillColor={linearGradient:{x1:0,y1:0,x2:0,y2:1},stops:[[0,col+'33'],[1,col+'05']]};}
    else if(s.type==='baseline'){o.type='area';o.threshold=s.base||0;o.negativeColor=s.negColor||'#B42318';o.fillOpacity=0.18;o.negativeFillColor=(s.negColor||'#B42318')+'2E';}
    else{o.type='line';}
    series.push(o);meta.push({name:s.name,fmt:s.fmt||'num',abs:!!s.abs,color:col,data:s.data});
  });
  top+=p.height+GAP;
});
const total=top+LEG;
box.style.height=total+'px';
function latestAtOrBefore(data,key){let pt=null;for(let i=data.length-1;i>=0;i--){if(data[i].time<=key){pt=data[i];break;}}return pt;}
function paint(key){
  let html='',shown=null;
  meta.forEach(m=>{
    const pt=key==null?m.data[m.data.length-1]:latestAtOrBefore(m.data,key);
    if(!pt)return;
    if(!shown)shown=pt.time;
    const v=m.abs?Math.abs(pt.value):pt.value;
    html+='<span><i style="background:'+m.color+'"></i>'+m.name+' <b>'+fmts[m.fmt](v)+'</b></span>';
  });
  lg.innerHTML=(shown?'<span class="d">'+dateText(ms(shown))+'</span>':'')+html;
}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
meta.forEach(m=>{m.name=esc(m.name);});
paint(null);
const chart=Highcharts.stockChart(box,{
  chart:{height:total,backgroundColor:'transparent',spacing:[4,0,0,0],marginRight:64,marginTop:4,marginBottom:LEG,style:{fontFamily:FONT},
    panning:{enabled:true,type:'x'},pinchType:'x',zooming:{mouseWheel:false},animation:false},
  credits:{enabled:false},accessibility:{enabled:false},navigator:{enabled:false},scrollbar:{enabled:false},rangeSelector:{enabled:false},legend:{enabled:false},
  title:{text:null},exporting:{enabled:false},
  xAxis:{type:'datetime',lineWidth:0,tickLength:0,crosshair:{color:'#98A1AE',width:1,dashStyle:'Dash'},
    labels:{style:{color:'#5E6878',fontSize:'12px'},y:18},ordinal:false},
  yAxis:yAxis,
  tooltip:{shared:true,split:false,enabled:true,backgroundColor:'transparent',borderWidth:0,shadow:false,
    positioner:function(){return {x:-9999,y:-9999};},
    formatter:function(){paint(new Date(this.x).toISOString().slice(0,10));return false;}},
  plotOptions:{series:{animation:false,turboThreshold:0,stickyTracking:true}},
  series:series
});
box.addEventListener('mouseleave',()=>paint(null));
box.addEventListener('touchend',()=>setTimeout(()=>paint(null),2500));
"""


def render(panes: list[dict], key: str | None = None) -> None:
    """Draw the panes in one iframe. Does nothing if no pane has two points."""
    live = [p for p in panes if any(len(s["data"]) >= 2 for s in p["series"])]
    if not live:
        return
    height = sum(int(p.get("height", 240)) + GAP_PX for p in live) + LEGEND_PX + 4 + 40
    st.iframe(chart_html(live), height=height)
