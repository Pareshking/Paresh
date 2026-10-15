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
/* On a phone the chart is drawn wider than the screen and swiped sideways
   (owner, 15 Oct: "larger chart, I will slide the page"). */
/* The page keeps vertical swipes and pinch-zoom; a sideways drag is moved by the
   script below, never by the browser, so reaching the edge cannot turn into
   the browser's swipe-back (it did, in a touch test, with native scrolling). */
#scroller{width:100%;overflow:hidden;touch-action:pan-y pinch-zoom}
#hint{display:none;font-size:11px;color:#5E6878;text-align:center;padding:2px 0 0}
body.wide #hint{display:block}
#controls{display:flex;gap:8px;align-items:center;justify-content:center;padding:6px 4px 2px;flex-wrap:wrap}
.ctrl-btn{background:#F1F3F6;border:1px solid #E3E6EB;border-radius:6px;padding:4px 14px;font-size:12px;
  cursor:pointer;color:#3C4657;font-family:inherit}
.ctrl-btn:hover{background:#E3E6EB}
.ctrl-btn.active{background:#4F46E5;color:#fff;border-color:#4F46E5}
#scrub{width:180px;accent-color:#4F46E5;cursor:pointer}
#frame-lbl{font-size:12px;color:#5E6878;font-family:'Geist Mono',monospace;min-width:58px;text-align:center}
</style>"""
    _BODY = """<div id="scroller"><div id="c"></div></div>
<div id="hint">&#8592; swipe the chart to see every quadrant &#8594;</div>
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
  // A name to the right of a dot near the right edge ran off the chart
  // (Media Entertainment, 15 Oct): there it goes on the dot's left instead.
  const flip = d[last].x > minX + 0.62 * (maxX - minX);
  d[last] = {x:d[last].x, y:d[last].y, marker:{enabled:true, radius:on?8:4, fillColor:s.color, lineColor:'#fff', lineWidth:2},
    dataLabels:{enabled:on, format:esc(s.industry), align:flip?'right':'left', x:flip?-10:10, y:-6, allowOverlap:false, crop:true, overflow:'justify',
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
    chart.renderer.text(q.n.toUpperCase(), q.ax==='left'?x0+6:x1-6, q.ay==='top'?y0+14:y1-6)
      .attr({align:q.ax==='left'?'left':'right',zIndex:0}).css({color:q.t,fontSize:'10.5px',fontWeight:'700',letterSpacing:'.06em',opacity:.7}).add(g);
  });
}
let chart;
const WIDE_BELOW = 600, WIDE_W = 760;   // px: under this frame width, draw WIDE_W and swipe
function build(){
  const wide = window.innerWidth < WIDE_BELOW;
  document.body.classList.toggle('wide', wide);
  const ctrlH = document.getElementById('controls').getBoundingClientRect().height
    + document.getElementById('hint').getBoundingClientRect().height + 6;
  const h = Math.max(300, window.innerHeight - ctrlH);
  const w = wide ? WIDE_W : window.innerWidth;
  const c = document.getElementById('c');
  c.style.height = h + 'px';
  c.style.width = wide ? WIDE_W + 'px' : '100%';
  chart = Highcharts.chart('c', {
    // No zoom or pan: a finger drag must scroll the page or the swipe strip,
    // not zoom the chart (a phone swipe showed "Reset zoom", 15 Oct).
    chart:{height:h, width:w, backgroundColor:'transparent', style:{fontFamily:"Geist,system-ui,sans-serif"}, animation:false, spacing:[8,8,4,4],
      zooming:{type:undefined, pinchType:undefined, singleTouch:false, mouseWheel:{enabled:false}}, panning:{enabled:false},
      events:{render:function(){quadrants(this);}}},
    credits:{enabled:false}, accessibility:{enabled:false}, title:{text:null}, legend:{enabled:false}, exporting:{enabled:false},
    xAxis:{min:minX, max:maxX, startOnTick:false, endOnTick:false, gridLineWidth:0, lineColor:'#E3E6EB', tickColor:'#E3E6EB',
      title:{text:'RS →', style:{color:'#5E6878', fontSize:'12px'}}, labels:{style:{color:'#5E6878', fontSize:'12px'}},
      plotLines:[{value:100, color:'#0E1726', width:1, zIndex:3}]},
    yAxis:{min:minY, max:maxY, startOnTick:false, endOnTick:false, gridLineWidth:0, title:{text:'↑ Momentum', style:{color:'#5E6878', fontSize:'12px'}},
      labels:{style:{color:'#5E6878', fontSize:'12px'}}, plotLines:[{value:100, color:'#0E1726', width:1, zIndex:3}]},
    tooltip:{useHTML:true, outside:false, followTouchMove:false, backgroundColor:'rgba(15,23,42,.94)', borderWidth:0, shadow:false, style:{color:'#fff', fontSize:'12px'},
      formatter:function(){
        const s=this.series.options.custom.s;
        return '<b style="color:#fff">'+esc(s.industry)+'</b><br>Quadrant: <b>'+esc(s.quadrant)+'</b><br>RS: <b>'+this.x.toFixed(2)+
          '</b><br>Momentum: <b>'+this.y.toFixed(2)+'</b><br>Stocks: '+s.stocks;}},
    plotOptions:{series:{animation:false, turboThreshold:0, stickyTracking:false, cursor:'pointer', states:{inactive:{enabled:true}},
      point:{events:{click:function(){const n=this.series.name; selected=(selected===n)?null:n; draw();}}}}},
    series: DATA.sectors.map(seriesFor)
  });
  // Open on the 100 / 100 crossing, so each quadrant is one swipe away.
  if(wide){
    const sc = document.getElementById('scroller');
    sc.scrollLeft = Math.max(0, chart.xAxis[0].toPixels(100, false) - window.innerWidth / 2);
  }
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
(function(){                         // sideways drag on the wide chart
  const sc = document.getElementById('scroller');
  let x0 = null, y0 = 0, l0 = 0, sideways = null;
  sc.addEventListener('touchstart', e => {
    if(!document.body.classList.contains('wide') || e.touches.length !== 1) { x0 = null; return; }
    x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; l0 = sc.scrollLeft; sideways = null;
  }, {passive:true});
  sc.addEventListener('touchmove', e => {
    if(x0 === null) return;
    const dx = e.touches[0].clientX - x0, dy = e.touches[0].clientY - y0;
    if(sideways === null && Math.abs(dx) + Math.abs(dy) > 6) sideways = Math.abs(dx) > Math.abs(dy);
    if(sideways) sc.scrollLeft = l0 - dx;
  }, {passive:true});
  sc.addEventListener('touchend', () => { x0 = null; }, {passive:true});
})();
let lastW = window.innerWidth;
window.addEventListener('resize',function(){
  if(window.innerWidth === lastW) return;
  lastW = window.innerWidth; chart.destroy(); build();
});
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


def render_industry_map(board: pd.DataFrame, x_col: str = "3M Return",
                        x_label: str = "Median 3-month return") -> None:
    """Industries as bubbles: median return (`x_col`, 3M by default) across, share passing both filters up,
    size = number of stocks. Top-right is strong and broad; bottom-left is weak and narrow."""
    from src.ui.highcharts_lib import lib, script_json

    need = {"Industry", x_col, "Pass %", "Stocks", "Top 50"}
    x_tip = f"{x_col.split(' ')[0]} median"
    if board.empty or not need <= set(board.columns):
        return
    rows = []
    for _, r in board.iterrows():
        if pd.isna(r[x_col]):
            continue
        rows.append({"name": str(r["Industry"]), "x": round(float(r[x_col]) * 100, 1),
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
        "const xmax=Math.max.apply(null,rows.map(r=>r.x));const ymax=Math.min(100,Math.max(10,Math.ceil(Math.max.apply(null,rows.map(r=>r.y))*1.15/10)*10));const top5=new Set(rows.slice().sort((a,b)=>b.x-a.x).slice(0,5).map(r=>r.name));const col=r=>r.x>=0?'#067647':'#B42318';"
        "Highcharts.chart('c',{chart:{type:'bubble',backgroundColor:'transparent',animation:false,spacing:[8,12,4,4],"
        "style:{fontFamily:'Geist,system-ui,sans-serif'},zooming:{type:null}},"
        "credits:{enabled:false},accessibility:{enabled:false},title:{text:null},legend:{enabled:false},exporting:{enabled:false},"
        "xAxis:{maxPadding:0.06,title:{text:" + script_json(x_label + " \u2192") + ",style:{color:'#5E6878',fontSize:'12px'}},gridLineWidth:0,"
        "labels:{format:'{value}%',style:{color:'#5E6878',fontSize:'12px'}},plotLines:[{value:0,color:'#98A1AE',width:1,dashStyle:'Dash'}]},"
        "yAxis:{title:{text:'\\u2191 Share passing both filters',style:{color:'#5E6878',fontSize:'12px'}},min:0,max:ymax,endOnTick:false,tickInterval:ymax>60?20:10,gridLineColor:'#EDEFF3',"
        "labels:{format:'{value}%',style:{color:'#5E6878',fontSize:'12px'}}},"
        "tooltip:{useHTML:true,backgroundColor:'rgba(15,23,42,.94)',borderWidth:0,shadow:false,style:{color:'#fff',fontSize:'12px'},"
        "formatter:function(){const p=this.point;return '<b>'+e(p.name)+'</b><br>" + x_tip + " <b>'+(p.x>0?'+':'')+p.x.toFixed(1)+'%</b>"
        "<br>Passing both <b>'+p.y.toFixed(0)+'%</b><br>'+p.z+' stocks \\u00b7 '+p.top50+' in the top 50';}},"
        "plotOptions:{bubble:{fillOpacity:0.62,minSize:10,maxSize:46,animation:false,marker:{lineWidth:1,lineColor:'#fff'},"
        "dataLabels:{enabled:true,allowOverlap:false,crop:false,overflow:'allow',style:{fontSize:'11px',fontWeight:'600',color:'#3C4657',textOutline:'2px #fff'},"
        "formatter:function(){return e(this.point.name);}}}},"
        "series:[{data:rows.map(r=>({name:r.name,x:r.x,y:r.y,z:r.z,top50:r.top50,color:col(r),labelrank:(top5.has(r.name)?1e6:0)+(r.x>=0?1000:0)+r.z,dataLabels:{allowOverlap:top5.has(r.name),align:(r.x>=(xmax*0.7)?'right':'center'),x:(r.x>=(xmax*0.7)?-14:0)}}))}]});"
        "})();</script></body></html>"
    )
    st.iframe(page, height=428)


# Twenty soft, distinct hues for the sector leadership map: pastel enough to
# overlap, dark enough to read on white.
SECTOR_SOFT_PALETTE = (
    "#7FA8D9", "#EE8E8E", "#79C2A0", "#F2AE6B", "#AD95D8", "#E3C25E", "#6CC1C8",
    "#E58FB7", "#A3BE7C", "#8E9EEB", "#F49F85", "#C29BCB", "#8CC4E8", "#C9A66B",
    "#86B86F", "#E07A8A", "#7FA99B", "#B4A0E6", "#D49A6A", "#93A7BD",
)



def sector_colours(names) -> dict[str, str]:
    """One soft colour per sector, fixed by name so the map, its table and
    every EMA tab agree (owner, 13 Oct: subtle colours, not green and red)."""
    return {name: SECTOR_SOFT_PALETTE[i % len(SECTOR_SOFT_PALETTE)]
            for i, name in enumerate(sorted(set(names)))}


_LEADERSHIP_JS = r"""
(function(){
const rows=__ROWS__, span=__SPAN__, months=__MONTHS__, then=__THEN__, now=__NOW__;
let focus=__FOCUS__;
const e=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=v=>(v>0?'+':v<0?'−':'')+Math.abs(v).toFixed(1)+'%';
const col=r=>r.c;
const xs=rows.flatMap(r=>[r.x0,r.x1]);
// Fit the data, keeping 0 in view: one far dot (a 3-month swing) made a
// symmetric axis squeeze every other line into the middle.
const xmin=Math.min(-1,Math.floor(Math.min.apply(null,xs)-0.5)), xmax=Math.max(1,Math.ceil(Math.max.apply(null,xs)+0.5));
const xspan=xmax-xmin, xtick=xspan>40?10:xspan>20?5:xspan>8?2:1;
const series=rows.map(r=>({name:r.name,id:r.name,color:col(r),row:r,
  data:[{x:r.x0,y:r.y0,marker:{fillColor:'#FFFFFF',lineColor:col(r),lineWidth:2,radius:5,symbol:'circle'},dataLabels:{enabled:false}},
        {x:r.x1,y:r.y1,marker:{fillColor:col(r),lineColor:'#3C4657',lineWidth:1,radius:6,symbol:'circle'}}]}));
function paint(chart){
  chart.series.forEach(s=>{const on=!focus||s.name===focus,me=focus&&s.name===focus;
    const c=col(s.options.row);
    s.update({opacity:on?1:0.12,lineWidth:me?3:1.6,zIndex:me?10:1,color:c,
      data:s.options.data.map((p,i)=>Object.assign({},p,{marker:Object.assign({},p.marker,i===0?{lineColor:c}:{fillColor:c})})),
      dataLabels:{enabled:on,style:{fontWeight:me?'700':'600',color:'#1F2937'}}},false);});
  chart.redraw(false);
  const tag=document.getElementById('pin');tag.textContent=focus?'Showing '+focus+' · tap it again to show all':'Tap a sector to pick it out';
}
const chart=Highcharts.chart('c',{chart:{type:'scatter',backgroundColor:'transparent',animation:false,spacing:[8,12,4,4],
  style:{fontFamily:'Geist,system-ui,sans-serif'},zooming:{type:'xy'}},
  credits:{enabled:false},accessibility:{enabled:false},title:{text:null},legend:{enabled:false},exporting:{enabled:false},
  xAxis:{min:xmin,max:xmax,tickInterval:xtick,gridLineWidth:1,gridLineColor:'#F1F2F5',
    title:{text:months+'-month return vs Nifty 500 →',style:{color:'#5E6878',fontSize:'12px'}},
    labels:{format:'{value}%',style:{color:'#5E6878',fontSize:'12px'}},plotLines:[{value:0,color:'#98A1AE',width:1,dashStyle:'Dash',zIndex:2}]},
  yAxis:{min:0,max:100,tickInterval:20,endOnTick:false,gridLineColor:'#EDEFF3',
    title:{text:'↑ Stocks above their '+span+'-day EMA',style:{color:'#5E6878',fontSize:'12px'}},
    labels:{format:'{value}%',style:{color:'#5E6878',fontSize:'12px'}},plotLines:[{value:50,color:'#98A1AE',width:1,dashStyle:'Dash',zIndex:2}]},
  tooltip:{useHTML:true,backgroundColor:'rgba(15,23,42,.94)',borderWidth:0,shadow:false,style:{color:'#fff',fontSize:'12px'},
    formatter:function(){const r=this.series.options.row;
      return '<b>'+e(r.full)+'</b> · '+r.stocks+' stocks<br>'+
      '<span style="opacity:.7">'+e(then)+'</span> '+pct(r.x0)+' vs Nifty 500 · '+r.a0+' of '+r.o0+' above<br>'+
      '<span style="opacity:.7">'+e(now)+'</span> <b>'+pct(r.x1)+'</b> vs Nifty 500 · <b>'+r.a1+' of '+r.o1+'</b> above<br>'+
      '<span style="opacity:.7">Sector '+pct(r.ret)+', Nifty 500 '+pct(r.bench)+(months===1?' this month':' in '+months+' months')+'</span>'+
      (r.lead?'<br>Led by <b>'+e(r.lead)+'</b>':'');}},
  plotOptions:{series:{animation:false,dashStyle:'ShortDash',lineWidth:1.5,marker:{enabled:true},stickyTracking:false,findNearestPointBy:'xy',
    states:{hover:{lineWidthPlus:1.5},inactive:{opacity:0.18}},cursor:'pointer',
    dataLabels:{enabled:true,allowOverlap:false,crop:false,overflow:'allow',x:6,align:'left',verticalAlign:'middle',
      style:{fontSize:'11px',fontWeight:'600',color:'#3C4657',textOutline:'2px #fff'},formatter:function(){return e(this.series.name);}},
    point:{events:{click:function(){focus=focus===this.series.name?null:this.series.name;paint(this.series.chart);}}}}},
  series:series});
paint(chart);
})();
"""


def render_leadership_map(board: pd.DataFrame, span: int, focus: str | None = None,
                          short: dict[str, str] | None = None) -> None:
    """Each sector a dashed line from a hollow dot (a month ago) to a filled dot
    (today): across is its 1-month return less the Nifty 500's, up is the share
    of its stocks above their `span`-day EMA.
    Tapping a sector (or picking it above) dims the rest."""
    from src.ui.highcharts_lib import lib, script_json

    if board.empty:
        return
    short = short or {}
    colour = sector_colours(board["Sector"])
    rows = [{
        "name": short.get(r.Sector, r.Sector), "full": r.Sector, "stocks": int(r.Stocks),
        "c": colour[r.Sector],
        "x0": round(r.x_then * 100, 2), "x1": round(r.x_now * 100, 2),
        "y0": round(r.y_then * 100, 1), "y1": round(r.y_now * 100, 1),
        "a0": int(r.above_then), "o0": int(r.obs_then), "a1": int(r.above_now), "o1": int(r.obs_now),
        "ret": round(r.ret_now * 100, 2), "bench": round(r.bench_now * 100, 2),
        "lead": ", ".join(f"{sym} {v * 100:+.1f}%" for sym, v in (getattr(r, "Leaders", None) or [])[:2]),
    } for r in board.itertuples()]
    months = int(board["Months"].iloc[0]) if "Months" in board.columns else 1
    then = f"{pd.Timestamp(board['Then'].iloc[0]):%d %b}"
    now = f"{pd.Timestamp(board['Now'].iloc[0]):%d %b}"
    js = (_LEADERSHIP_JS.replace("__ROWS__", script_json(rows)).replace("__SPAN__", str(int(span))).replace("__MONTHS__", str(months))
          .replace("__THEN__", script_json(then)).replace("__NOW__", script_json(now))
          .replace("__FOCUS__", script_json(short.get(focus, focus) if focus else None)))
    page = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'><style>*{box-sizing:border-box;margin:0}"
        "html,body{background:transparent;font-family:'Geist',system-ui,sans-serif}"
        "#pin{font-size:12px;color:#5E6878;padding:2px 4px 6px}</style></head>"
        "<body><div id='pin'></div><div id='c' style='width:100%;height:500px'></div><script>"
        + lib() + "</script><script>" + js + "</script></body></html>"
    )
    st.iframe(page, height=530)
