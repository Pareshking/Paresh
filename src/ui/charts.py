"""
Interactive visualizations for NSE Momentum Dashboard.
Stock chart and the Relative Rotation Graph, both Highcharts.
"""

import json
import pandas as pd
import streamlit as st



def compute_rs_series(stock: pd.Series, benchmark: pd.Series) -> pd.Series:
    """Relative Strength of stock vs benchmark, indexed to 100 at the first common date.

    Values > 100 mean the stock has outperformed the benchmark since the start
    of the window; values < 100 mean underperformance.
    """
    aligned = pd.DataFrame({"s": stock, "b": benchmark}).dropna()
    if aligned.empty or len(aligned) < 2:
        return pd.Series(dtype=float)
    ratio = aligned["s"] / aligned["b"]
    return (ratio / ratio.iloc[0]) * 100


TF_SESSIONS = {"1M": 22, "3M": 64, "6M": 126, "1Y": 252, "All": 5000}


def render_stock_chart(
    symbol: str,
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
    high_prices: pd.DataFrame | None = None,
    low_prices: pd.DataFrame | None = None,
    volume_data: pd.DataFrame | None = None,
    open_prices: pd.DataFrame | None = None,
) -> None:
    """Price with toggleable overlays, volume and a relative-strength pane (Highcharts Stock)."""
    if symbol not in adj_close.columns:
        st.warning(f"No price data available for {symbol}")
        return

    c_tf, c_ma = st.columns([1.5, 2], vertical_alignment="center")
    tf = c_tf.segmented_control(
        "Timeframe", list(TF_SESSIONS), default="6M",
        key=f"lw_tf_{symbol}", label_visibility="collapsed",
    ) or "6M"
    overlays = c_ma.pills(
        "Overlays", ["20 EMA", "50 EMA", "200 SMA", "Nifty 500"],
        selection_mode="multi", default=["20 EMA", "50 EMA"],
        key=f"lw_ma_{symbol}", label_visibility="collapsed",
    ) or []

    n = TF_SESSIONS.get(tf, 126)
    close = adj_close[symbol].dropna().iloc[-n:]
    if close.empty:
        st.warning(f"No price data available for {symbol}")
        return

    def _col(df):
        return df[symbol] if df is not None and symbol in df.columns else None

    # Overlays are computed on the FULL history and then trimmed, so a 200-day
    # average is a real 200-day average even when only 22 sessions are shown.
    full_close = adj_close[symbol].dropna()
    specs = {
        "20 EMA": full_close.ewm(span=20, min_periods=5).mean(),
        "50 EMA": full_close.ewm(span=50, min_periods=10).mean(),
        "200 SMA": full_close.rolling(200, min_periods=30).mean(),
    }
    chosen = {k: v for k, v in specs.items() if k in overlays}

    # Benchmark is always fetched — used both for the price overlay (if selected)
    # and for the Relative Strength pane shown beneath the chart.
    _bench_full: pd.Series | None = None
    try:
        from src.loaders.price_loader import fetch_benchmark_history
        _bench_full = fetch_benchmark_history(period="5y")
    except Exception:
        pass

    if "Nifty 500" in overlays and _bench_full is not None:
        bench_window = _bench_full.reindex(close.index, method="ffill").dropna()
        if len(bench_window) >= 2 and not close.empty:
            chosen["Nifty 500"] = bench_window / bench_window.iloc[0] * close.iloc[0]

    # Relative Strength vs Nifty 500 — computed over the full history so the
    # ratio is stable regardless of the chosen display window.
    rs_full: pd.Series | None = None
    if _bench_full is not None and not full_close.empty:
        rs_full = compute_rs_series(full_close, _bench_full)

    from src.ui.stock_chart import ChartUnavailable, render_stock_panes

    try:
        render_stock_panes(
            symbol,
            close,
            open_=_col(open_prices),
            high=_col(high_prices),
            low=_col(low_prices),
            volume=_col(volume_data),
            overlays=chosen,
            rs=rs_full,
        )
    except ChartUnavailable as exc:
        st.warning(f"No chart for {symbol}: {exc}")


def _script_json(obj) -> str:
    r"""``json.dumps`` for a value that is about to land inside a ``<script>``.

    These chart pages are handed to ``st.iframe``, whose srcdoc Streamlit
    renders with ``allow-scripts`` AND ``allow-same-origin`` -- anything that
    escapes the script block runs on the app's own origin.

    ``json.dumps`` escapes quotes and backslashes but NOT ``<``, and the HTML
    parser looks for the literal ``</script`` before JavaScript ever sees the
    string. So an Industry name or ticker of ``</script><img src=x onerror=...>``
    -- and every one of those strings arrives from the niftyindices.com CSVs,
    the NSE bhavcopy or Yahoo -- would close the block and inject markup.

    ``<\/`` is the same character to a JavaScript string literal and invisible
    to the HTML parser, so the data is unchanged and the block cannot be
    closed. U+2028/U+2029 are line terminators in JavaScript but not in JSON,
    which is a syntax error rather than an injection, and just as cheap to fix.
    """
    return (
        json.dumps(obj)
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _build_rrg_html(data_json: str) -> str:
    """The Relative Rotation Graph as a self-contained Highcharts page.

    One line series per industry (its trail, ending in a larger dot), quadrants
    drawn behind, a tooltip with RS and Momentum, play/scrub through the trail,
    and tap-to-isolate. Highcharts is inlined, so nothing loads from the network.
    """
    from src.ui.highcharts_lib import lib as _lib

    _CSS = """<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:transparent;height:100%;overflow:hidden;font-family:'Geist',system-ui,sans-serif}
#c{width:100%}
#controls{display:flex;gap:8px;align-items:center;justify-content:center;padding:6px 4px 2px;flex-wrap:wrap}
.ctrl-btn{background:#F1F3F6;border:1px solid #E3E6EB;border-radius:6px;padding:4px 14px;font-size:12px;
  cursor:pointer;color:#3C4657;font-family:inherit}
.ctrl-btn:hover{background:#E3E6EB}
.ctrl-btn.active{background:#4F46E5;color:#fff;border-color:#4F46E5}
#scrub{width:180px;accent-color:#4F46E5;cursor:pointer}
#frame-lbl{font-size:12px;color:#5E6878;font-family:'Geist Mono',monospace;min-width:58px;text-align:center}
</style>"""
    _BODY = """<div id="c"></div>
<div id="controls">
  <button class="ctrl-btn" id="btn-play">&#9654; Play</button>
  <input type="range" id="scrub" min="0" value="100">
  <span id="frame-lbl">Current</span>
  <button class="ctrl-btn" id="btn-rst">&#8635; Reset</button>
</div>"""
    _JS = r"""
const DATA = """ + data_json + r""";
function esc(v){return String(v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
const shown = s => !DATA.highlight.length || DATA.highlight.indexOf(s.industry) >= 0;
const allR = DATA.sectors.flatMap(s => (shown(s) && s.trail_r.length) ? s.trail_r.concat([s.rs_ratio]) : [s.rs_ratio]);
const allM = DATA.sectors.flatMap(s => (shown(s) && s.trail_m.length) ? s.trail_m.concat([s.rs_momentum]) : [s.rs_momentum]);
const minX = Math.min(88,  allR.length ? Math.min(...allR) - 2 : 90);
const maxX = Math.max(112, allR.length ? Math.max(...allR) + 2 : 110);
const minY = Math.min(96,  allM.length ? Math.min(...allM) - 1.5 : 97);
const maxY = Math.max(105, allM.length ? Math.max(...allM) + 1.5 : 104.5);
const maxFrames = Math.max(...DATA.sectors.map(s => s.trail_r.length), 1);
let frame = maxFrames - 1, playing = false, playTimer = null, selected = null;
const btnPlay = document.getElementById('btn-play'), scrub = document.getElementById('scrub'), lbl = document.getElementById('frame-lbl');
scrub.max = maxFrames - 1; scrub.value = maxFrames - 1;
const QUADS = [
  {n:'Improving', x0:minX, x1:100, y0:100, y1:maxY, c:'rgba(79,70,229,.07)', t:'#4F46E5', ax:'left', ay:'top'},
  {n:'Leading',   x0:100, x1:maxX, y0:100, y1:maxY, c:'rgba(6,118,71,.08)',  t:'#067647', ax:'right', ay:'top'},
  {n:'Lagging',   x0:minX, x1:100, y0:minY, y1:100, c:'rgba(180,35,24,.07)', t:'#B42318', ax:'left', ay:'bottom'},
  {n:'Weakening', x0:100, x1:maxX, y0:minY, y1:100, c:'rgba(181,71,8,.08)',  t:'#B54708', ax:'right', ay:'bottom'}];
function pts(s, f){
  const n = s.trail_r.length;
  if(!n) return [{x:s.rs_ratio, y:s.rs_momentum}];
  const e = Math.min(f, n-1);
  return s.trail_r.slice(0, e+1).map((r,i)=>({x:r, y:s.trail_m[i]}));
}
function seriesFor(s){
  const on = shown(s) && (selected===null || selected===s.industry);
  const d = pts(s, frame), last = d.length-1;
  d[last] = {x:d[last].x, y:d[last].y, marker:{enabled:true, radius:on?8:4, fillColor:s.color, lineColor:'#fff', lineWidth:2},
    dataLabels:{enabled:on, format:esc(s.industry), align:'left', x:10, y:-6, allowOverlap:false, crop:false, overflow:'allow',
      style:{color:s.color, fontSize:'11px', fontWeight:'600', textOutline:'2px #fff'}}};
  return {name:s.industry, data:d, color:s.color, lineWidth:on?2:1, opacity:on?1:0.14, type:'line',
    marker:{enabled:on, radius:3, symbol:'circle'}, states:{inactive:{opacity:on?1:0.14}, hover:{lineWidthPlus:0}},
    custom:{s:s}, enableMouseTracking:on};
}
function quadrants(chart){
  if(chart.quadG) chart.quadG.destroy();
  const g = chart.quadG = chart.renderer.g('q').attr({zIndex:0}).add();
  const X = chart.xAxis[0], Y = chart.yAxis[0];
  QUADS.forEach(q=>{
    const x0=X.toPixels(q.x0,false), x1=X.toPixels(q.x1,false), y0=Y.toPixels(q.y1,false), y1=Y.toPixels(q.y0,false);
    chart.renderer.rect(x0,y0,x1-x0,y1-y0).attr({fill:q.c,zIndex:0}).add(g);
    chart.renderer.text(q.n, q.ax==='left'?x0+10:x1-10, q.ay==='top'?y0+22:y1-12)
      .attr({align:q.ax==='left'?'left':'right',zIndex:1}).css({color:q.t,fontSize:'13px',fontWeight:'700',opacity:.85}).add(g);
  });
}
let chart;
function build(){
  const ctrlH = document.getElementById('controls').getBoundingClientRect().height + 6;
  const h = Math.max(300, window.innerHeight - ctrlH);
  document.getElementById('c').style.height = h + 'px';
  chart = Highcharts.chart('c', {
    chart:{height:h, backgroundColor:'transparent', style:{fontFamily:"Geist,system-ui,sans-serif"}, animation:false, spacing:[8,8,4,4],
      events:{render:function(){quadrants(this);}}},
    credits:{enabled:false}, accessibility:{enabled:false}, title:{text:null}, legend:{enabled:false}, exporting:{enabled:false},
    xAxis:{min:minX, max:maxX, startOnTick:false, endOnTick:false, gridLineWidth:0, lineColor:'#E3E6EB', tickColor:'#E3E6EB',
      title:{text:'RS →', style:{color:'#5E6878', fontSize:'12px'}}, labels:{style:{color:'#5E6878', fontSize:'12px'}},
      plotLines:[{value:100, color:'#0E1726', width:1, zIndex:3}]},
    yAxis:{min:minY, max:maxY, startOnTick:false, endOnTick:false, gridLineWidth:0, title:{text:'↑ Momentum', style:{color:'#5E6878', fontSize:'12px'}},
      labels:{style:{color:'#5E6878', fontSize:'12px'}}, plotLines:[{value:100, color:'#0E1726', width:1, zIndex:3}]},
    tooltip:{useHTML:true, outside:false, backgroundColor:'rgba(15,23,42,.94)', borderWidth:0, shadow:false, style:{color:'#fff', fontSize:'12px'},
      formatter:function(){
        const s=this.series.options.custom.s;
        return '<b style="color:#fff">'+esc(s.industry)+'</b><br>Quadrant: <b>'+esc(s.quadrant)+'</b><br>RS: <b>'+this.x.toFixed(2)+
          '</b><br>Momentum: <b>'+this.y.toFixed(2)+'</b><br>Stocks: '+s.stocks;}},
    plotOptions:{series:{animation:false, turboThreshold:0, stickyTracking:false, cursor:'pointer', states:{inactive:{enabled:true}},
      point:{events:{click:function(){const n=this.series.name; selected=(selected===n)?null:n; draw();}}}}},
    series: DATA.sectors.map(seriesFor)
  });
}
function draw(){
  DATA.sectors.forEach((s,i)=>{
    const o = seriesFor(s);
    chart.series[i].update({data:o.data, lineWidth:o.lineWidth, opacity:o.opacity, marker:o.marker, enableMouseTracking:o.enableMouseTracking, states:o.states}, false);
  });
  chart.redraw(false);
}
function updateLabel(){const off=frame-(maxFrames-1); lbl.textContent = off===0 ? 'Current' : ('T'+off);}
function stop(){playing=false; clearTimeout(playTimer); btnPlay.textContent='▶ Play'; btnPlay.classList.remove('active');}
function stepPlay(){
  if(!playing) return;
  frame++; scrub.value=frame; updateLabel(); draw();
  if(frame>=maxFrames-1){stop(); return;}
  playTimer=setTimeout(stepPlay,130);
}
btnPlay.addEventListener('click',function(){
  if(playing){stop(); return;}
  playing=true; frame=0; scrub.value=0; updateLabel(); draw();
  btnPlay.textContent='⏸ Pause'; btnPlay.classList.add('active'); playTimer=setTimeout(stepPlay,130);
});
scrub.addEventListener('input',function(){stop(); frame=parseInt(scrub.value); updateLabel(); draw();});
document.getElementById('btn-rst').addEventListener('click',function(){stop(); frame=maxFrames-1; scrub.value=maxFrames-1; selected=null; updateLabel(); draw();});
window.addEventListener('resize',function(){chart.destroy(); build();});
build(); updateLabel();
"""
    return ("<!DOCTYPE html><html><head><meta charset='utf-8'>" + _CSS + "</head><body>" + _BODY
            + "<script>" + _lib() + "</script><script>" + _JS + "</script></body></html>")


def render_rrg_chart(
    rrg_df: pd.DataFrame,
    highlight_industries: list[str] | None = None,
    current_date_str: str = "",
) -> None:
    """Relative Rotation Graph (Highcharts): trails, quadrants, play/scrub, tap to isolate."""
    if rrg_df.empty:
        st.info("Not enough historical data to compute Relative Rotation Graph.")
        return

    VIBRANT_PALETTE = [
        "#ec4899", "#2563eb", "#067647", "#0891b2", "#8b5cf6",
        "#B54708", "#B42318", "#067647", "#ea580c", "#6366f1",
        "#0284c7", "#9333ea", "#5E6878",
    ]

    sectors_data = []
    for idx, (_, row) in enumerate(rrg_df.iterrows()):
        trail_r = row.get("Trail_R") or []
        trail_m = row.get("Trail_M") or []
        if not isinstance(trail_r, list):
            trail_r = list(trail_r)
        if not isinstance(trail_m, list):
            trail_m = list(trail_m)
        sectors_data.append({
            "industry": str(row["Industry"]),
            "rs_ratio": float(row["RS_Ratio"]),
            "rs_momentum": float(row["RS_Momentum"]),
            "quadrant": str(row["Quadrant"]),
            "stocks": int(row.get("Stocks", 0)),
            "trail_r": [float(x) for x in trail_r],
            "trail_m": [float(x) for x in trail_m],
            "color": VIBRANT_PALETTE[idx % len(VIBRANT_PALETTE)],
        })

    payload = _script_json({
        "sectors": sectors_data,
        "highlight": list(highlight_industries or []),
        "date": current_date_str,
    })

    # Sized by the page's stylesheet (.st-key-rrg_frame): tall on desktop, near
    # square on a phone. The chart inside fills whatever height it is given.
    with st.container(key="rrg_frame"):
        st.iframe(_build_rrg_html(payload), height=780)


def render_correlation_heatmap(corr: pd.DataFrame, syms: list[str]) -> None:
    """Pairwise correlation of the given stocks as a Highcharts heatmap.

    Darker indigo = move together more; the tooltip names both stocks and the
    value, and cells carry the number when there is room for it.
    """
    from src.ui.highcharts_lib import lib, script_json

    syms = [s for s in syms if s in corr.index]
    if len(syms) < 2:
        return
    sub = corr.loc[syms, syms]
    data = []
    for yi, b in enumerate(syms):
        for xi, a in enumerate(syms):
            v = sub.at[a, b]
            if pd.notna(v):
                data.append([xi, yi, round(float(v), 2)])
    n = len(syms)
    height = min(720, 90 + 26 * n)
    page = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'><style>*{box-sizing:border-box;margin:0}"
        "html,body{background:transparent;font-family:'Geist',system-ui,sans-serif}</style></head>"
        "<body><div id='c' style='width:100%;height:" + str(height) + "px'></div><script>"
        + lib("highcharts-heatmap.js") + "</script><script>(function(){"
        "const syms=" + script_json(syms) + ", data=" + script_json(data) + ";"
        "const wide=document.getElementById('c').clientWidth/syms.length>=30;"
        "Highcharts.chart('c',{chart:{type:'heatmap',backgroundColor:'transparent',spacing:[4,4,4,4],"
        "style:{fontFamily:'Geist,system-ui,sans-serif'},animation:false},"
        "credits:{enabled:false},accessibility:{enabled:false},title:{text:null},legend:{enabled:true,"
        "align:'right',layout:'vertical',verticalAlign:'middle',symbolHeight:150,itemStyle:{color:'#5E6878',fontSize:'11px'}},"
        "exporting:{enabled:false},"
        "xAxis:{categories:syms,opposite:true,labels:{rotation:-60,style:{color:'#3C4657',fontSize:'11px'}},lineWidth:0,tickLength:0},"
        "yAxis:{categories:syms,reversed:true,title:{text:null},labels:{style:{color:'#3C4657',fontSize:'11px'}},gridLineWidth:0},"
        "colorAxis:{min:-0.2,max:1,startOnTick:false,endOnTick:false,tickPositions:[0,0.25,0.5,0.75,1],labels:{format:'{value:.2f}',style:{color:'#5E6878',fontSize:'11px'}},stops:[[0,'#F4F5F8'],[0.17,'#FFFFFF'],[0.6,'#A5A0F0'],[1,'#4338CA']]},"
        "tooltip:{useHTML:true,backgroundColor:'rgba(15,23,42,.94)',borderWidth:0,shadow:false,style:{color:'#fff',fontSize:'12px'},"
        "formatter:function(){const s=this.series.xAxis.categories,t=this.series.yAxis.categories;"
        "const e=v=>String(v).replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]));"
        "return '<b>'+e(t[this.point.y])+' \\u00d7 '+e(s[this.point.x])+'</b><br>Correlation <b>'+this.point.value.toFixed(2)+'</b>';}},"
        "plotOptions:{heatmap:{borderWidth:1,borderColor:'#fff',animation:false}},"
        "series:[{name:'Correlation',data:data,dataLabels:{enabled:wide,style:{fontSize:'10px',fontWeight:'500',textOutline:'none'},"
        "formatter:function(){return this.point.value.toFixed(2);}}}]});"
        "})();</script></body></html>"
    )
    st.iframe(page, height=height + 8)


def render_industry_map(board: pd.DataFrame) -> None:
    """Industries as bubbles: median 3M return across, share passing both filters up,
    size = number of stocks. Top-right is strong and broad; bottom-left is weak and narrow."""
    from src.ui.highcharts_lib import lib, script_json

    need = {"Industry", "3M Return", "Pass %", "Stocks", "Top 50"}
    if board.empty or not need <= set(board.columns):
        return
    rows = []
    for _, r in board.iterrows():
        if pd.isna(r["3M Return"]):
            continue
        rows.append({"name": str(r["Industry"]), "x": round(float(r["3M Return"]) * 100, 1),
                     "y": round(float(r["Pass %"]) * 100, 1), "z": int(r["Stocks"]),
                     "top50": int(r["Top 50"])})
    if len(rows) < 2:
        return
    page = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'><style>*{box-sizing:border-box;margin:0}"
        "html,body{background:transparent;font-family:'Geist',system-ui,sans-serif}</style></head>"
        "<body><div id='c' style='width:100%;height:420px'></div><script>"
        + lib("highcharts-more.js") + "</script><script>(function(){"
        "const rows=" + script_json(rows) + ";"
        "const e=v=>String(v).replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]));"
        "const xmax=Math.max.apply(null,rows.map(r=>r.x));const col=r=>r.x>=0?'#067647':'#B42318';"
        "Highcharts.chart('c',{chart:{type:'bubble',backgroundColor:'transparent',animation:false,spacing:[8,12,4,4],"
        "style:{fontFamily:'Geist,system-ui,sans-serif'},zooming:{type:null}},"
        "credits:{enabled:false},accessibility:{enabled:false},title:{text:null},legend:{enabled:false},exporting:{enabled:false},"
        "xAxis:{maxPadding:0.06,title:{text:'Median 3-month return \\u2192',style:{color:'#5E6878',fontSize:'12px'}},gridLineWidth:0,"
        "labels:{format:'{value}%',style:{color:'#5E6878',fontSize:'12px'}},plotLines:[{value:0,color:'#98A1AE',width:1,dashStyle:'Dash'}]},"
        "yAxis:{title:{text:'\\u2191 Share passing both filters',style:{color:'#5E6878',fontSize:'12px'}},min:0,max:100,gridLineColor:'#EDEFF3',"
        "labels:{format:'{value}%',style:{color:'#5E6878',fontSize:'12px'}}},"
        "tooltip:{useHTML:true,backgroundColor:'rgba(15,23,42,.94)',borderWidth:0,shadow:false,style:{color:'#fff',fontSize:'12px'},"
        "formatter:function(){const p=this.point;return '<b>'+e(p.name)+'</b><br>3M median <b>'+(p.x>0?'+':'')+p.x.toFixed(1)+'%</b>"
        "<br>Passing both <b>'+p.y.toFixed(0)+'%</b><br>'+p.z+' stocks \\u00b7 '+p.top50+' in the top 50';}},"
        "plotOptions:{bubble:{fillOpacity:0.62,minSize:10,maxSize:46,animation:false,marker:{lineWidth:1,lineColor:'#fff'},"
        "dataLabels:{enabled:true,allowOverlap:false,crop:false,overflow:'allow',style:{fontSize:'11px',fontWeight:'600',color:'#3C4657',textOutline:'2px #fff'},"
        "formatter:function(){return e(this.point.name);}}}},"
        "series:[{data:rows.map(r=>({name:r.name,x:r.x,y:r.y,z:r.z,top50:r.top50,color:col(r),labelrank:r.z,dataLabels:{align:(r.x>=(xmax*0.7)?'right':'center'),x:(r.x>=(xmax*0.7)?-14:0)}}))}]});"
        "})();</script></body></html>"
    )
    st.iframe(page, height=428)
