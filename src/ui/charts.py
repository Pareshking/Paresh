"""
Interactive visualizations for NSE Momentum Dashboard.
Stock chart and the Relative Rotation Graph, both Highcharts.
"""

import json
import pandas as pd
import streamlit as st
from src.ui import formats as _fmt
from src.ui.tokens import FONTS, resolve

# Each chart is its own document, so it loads the theme's fonts itself.
_HEAD = "<!DOCTYPE html><html lang='en'><head><title>Chart</title><meta charset='utf-8'><link rel='stylesheet' href='" + FONTS["google_css"] + "'>"


def _titled(title: str) -> str:
    """The frame head with a title that says what the chart is (audit F22/F26)."""
    return _HEAD.replace("<title>Chart</title>", f"<title>{title}</title>")



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


def _build_rrg_html(data_json: str, summary: str = "") -> str:
    """The Relative Rotation Graph as a self-contained Highcharts page.

    One line series per industry (its trail, ending in a larger dot), quadrants
    drawn behind, a tooltip with RS and Momentum, play/scrub through the trail,
    and tap-to-isolate. Highcharts is inlined, so nothing loads from the network.
    """
    from src.ui.highcharts_lib import lib as _lib

    _CSS = """<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:transparent;height:100%;overflow:hidden;font-family:'IBM Plex Sans',system-ui,sans-serif}
#c{width:100%}
/* On a phone the chart is drawn wider than the screen and swiped sideways
   (owner, 15 Oct: "larger chart, I will slide the page"). */
/* The page keeps vertical swipes (pan-y); a sideways drag is moved by the
   script below, never by the browser, so reaching the edge cannot turn into
   the browser's swipe-back (it did, in a touch test, with native scrolling). */
#scroller{width:100%;overflow:hidden;touch-action:pan-y}
#hint{display:none;font-size:11px;color:var(--c-faint);text-align:center;padding:2px 0 0}
body.wide #hint{display:block}
#controls{display:flex;gap:8px;align-items:center;justify-content:center;padding:6px 4px 2px;flex-wrap:wrap}
.ctrl-btn{background:transparent;border:1px solid var(--c-rule);border-radius:4px;padding:3px 12px;font-size:12px;
  cursor:pointer;color:var(--c-text_2);font-family:inherit}
.ctrl-btn:hover{border-color:var(--c-rule_strong);color:var(--c-ink)}
.ctrl-btn.active{background:var(--c-ink);color:#fff;border-color:var(--c-ink)}
#scrub{width:180px;cursor:pointer;-webkit-appearance:none;appearance:none;background:transparent;height:16px}
#scrub::-webkit-slider-runnable-track{height:2px;background:var(--c-rule_strong);border-radius:1px}
#scrub::-moz-range-track{height:2px;background:var(--c-rule_strong);border-radius:1px}
#scrub::-webkit-slider-thumb{-webkit-appearance:none;width:12px;height:12px;margin-top:-5px;border-radius:50%;background:var(--c-ink);border:2px solid var(--c-white)}
#scrub::-moz-range-thumb{width:10px;height:10px;border-radius:50%;background:var(--c-ink);border:2px solid var(--c-white)}
#frame-lbl{font-size:12px;color:var(--c-muted_2);font-family:'IBM Plex Mono',monospace;min-width:58px;text-align:center}
</style>"""
    _BODY = """<div id="scroller" aria-hidden="true"><div id="c"></div></div>
<div id="hint">&#8592; swipe the chart to see every quadrant &#8594;</div>
<div id="controls">
  <button class="ctrl-btn" id="btn-play">&#9654; Play</button>
  <input type="range" id="scrub" min="0" value="100" aria-label="Week shown">
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
  {n:'Improving', x0:minX, x1:100, y0:100, y1:maxY, c:'var(--c-fill_soft)',    t:'var(--c-muted)', ax:'left', ay:'top'},
  {n:'Leading',   x0:100, x1:maxX, y0:100, y1:maxY, c:'var(--c-up_tint_3)',    t:'var(--c-up)', ax:'right', ay:'top'},
  {n:'Lagging',   x0:minX, x1:100, y0:minY, y1:100, c:'var(--c-down_tint_2)',  t:'var(--c-down)', ax:'left', ay:'bottom'},
  {n:'Weakening', x0:100, x1:maxX, y0:minY, y1:100, c:'var(--c-caution_tint)', t:'var(--c-caution)', ax:'right', ay:'bottom'}];
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
  d[last] = {x:d[last].x, y:d[last].y, marker:{enabled:true, radius:on?5:3, fillColor:s.color, lineColor:'var(--c-white)', lineWidth:1.5},
    dataLabels:{enabled:on, format:esc(s.industry), align:flip?'right':'left', x:flip?-10:10, y:-6, allowOverlap:false, crop:true, overflow:'justify',
      style:{color:s.color, fontSize:'11px', fontWeight:'600', textOutline:'2px var(--c-white)'}}};
  return {name:s.industry, data:d, color:s.color, lineWidth:on?1.5:1, opacity:on?1:0.14, type:'line',
    marker:{enabled:on, radius:1.8, symbol:'circle', lineWidth:0}, states:{inactive:{opacity:on?1:0.14}, hover:{lineWidthPlus:0}},
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
      .attr({align:q.ax==='left'?'left':'right',zIndex:0}).css({color:q.t,fontSize:'10px',fontWeight:'600',letterSpacing:'.08em',opacity:.85}).add(g);
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
    chart:{height:h, width:w, backgroundColor:'transparent', style:{fontFamily:"IBM Plex Sans,system-ui,sans-serif"}, animation:false, spacing:[8,8,4,4],
      zooming:{type:undefined, pinchType:undefined, singleTouch:false, mouseWheel:{enabled:false}}, panning:{enabled:false},
      events:{render:function(){quadrants(this);}}},
    credits:{enabled:false}, accessibility:{enabled:false}, title:{text:null}, legend:{enabled:false}, exporting:{enabled:false},
    xAxis:{min:minX, max:maxX, startOnTick:false, endOnTick:false, gridLineWidth:0, lineWidth:0, tickLength:0,
      title:{text:'RS →', style:{color:'var(--c-muted_2)', fontSize:'11px'}}, labels:{style:{color:'var(--c-muted_2)', fontSize:'11px'}},
      plotLines:[{value:100, color:'var(--c-rule_strong)', width:1, zIndex:3}]},
    yAxis:{min:minY, max:maxY, startOnTick:false, endOnTick:false, gridLineWidth:0, title:{text:'↑ Momentum', style:{color:'var(--c-muted_2)', fontSize:'11px'}},
      labels:{style:{color:'var(--c-muted_2)', fontSize:'11px'}}, plotLines:[{value:100, color:'var(--c-rule_strong)', width:1, zIndex:3}]},
    tooltip:{useHTML:true, outside:false, followTouchMove:false, backgroundColor:'var(--c-white)',borderColor:'var(--c-rule)',borderWidth:1,borderRadius:3,shadow:false,padding:8,style:{color:'var(--c-ink)',fontSize:'12px',lineHeight:'17px'},
      formatter:function(){
        const s=this.series.options.custom.s;
        return '<b>'+esc(s.industry)+'</b><br>Quadrant: <b>'+esc(s.quadrant)+'</b><br>RS: <b>'+this.x.toFixed(2)+
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
    from src.ui.highcharts_lib import text_alternative
    return (_titled("Relative rotation graph") + _CSS + "</head><body>" + text_alternative(summary) + _BODY
            + "<script>" + _lib() + "</script><script>" + _JS + "</script></body></html>")


def rrg_summary(sectors: list[dict]) -> str:
    """The industries named under each quadrant, for a screen reader (audit F26)."""
    by: dict[str, list[str]] = {}
    for s in sorted(sectors, key=lambda s: -s["rs_ratio"]):
        by.setdefault(s["quadrant"], []).append(s["industry"])
    order = ["Leading", "Weakening", "Lagging", "Improving"]
    keys = [q for q in order if q in by] + [q for q in by if q not in order]
    return " ".join(f"{q}: {', '.join(by[q])}." for q in keys)


def correlation_summary(sub: pd.DataFrame) -> str:
    """The most and least alike pair among the stocks shown (audit F26)."""
    names = list(sub.index)
    pairs = [(float(sub.iat[i, j]), names[i], names[j])
             for i in range(len(names)) for j in range(i + 1, len(names))
             if pd.notna(sub.iat[i, j])]
    if not pairs:
        return f"Correlation of {len(names)} stocks."
    hi, lo = max(pairs), min(pairs)
    return (f"Correlation of daily returns of {len(names)} stocks. Most alike: {hi[1]} and {hi[2]} "
            f"({_fmt.signed(hi[0], 2, plus=False)}). Least alike: {lo[1]} and {lo[2]} "
            f"({_fmt.signed(lo[0], 2, plus=False)}).")


def render_rrg_chart(
    rrg_df: pd.DataFrame,
    highlight_industries: list[str] | None = None,
    current_date_str: str = "",
) -> None:
    """Relative Rotation Graph (Highcharts): trails, quadrants, play/scrub, tap to isolate."""
    if rrg_df.empty:
        st.info("Not enough historical data to compute Relative Rotation Graph.")
        return

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
            "color": CATEGORICAL[idx % len(CATEGORICAL)],
        })

    payload = _script_json({
        "sectors": sectors_data,
        "highlight": list(highlight_industries or []),
        "date": current_date_str,
    })

    # Sized by the page's stylesheet (.st-key-rrg_frame): tall on desktop, near
    # square on a phone. The chart inside fills whatever height it is given.
    with st.container(key="rrg_frame"):
        st.iframe(resolve(_build_rrg_html(payload, rrg_summary(sectors_data))), height=780)


def render_correlation_heatmap(corr: pd.DataFrame, syms: list[str]) -> None:
    """Pairwise correlation of the given stocks as a Highcharts heatmap.

    Darker indigo = move together more; the tooltip names both stocks and the
    value, and cells carry the number when there is room for it.
    """
    from src.ui.highcharts_lib import lib, script_json, text_alternative

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
        _titled("Correlation of the holdings") + "<style>*{box-sizing:border-box;margin:0}"
        "html,body{background:transparent;font-family:'IBM Plex Sans',system-ui,sans-serif}</style></head>"
        "<body>" + text_alternative(correlation_summary(sub)) +
        "<div id='c' aria-hidden='true' style='width:100%;height:" + str(height) + "px'></div><script>"
        + lib("highcharts-heatmap.js") + "</script><script>(function(){"
        "const syms=" + script_json(syms) + ", data=" + script_json(data) + ";"
        "const wide=document.getElementById('c').clientWidth/syms.length>=30;"
        "Highcharts.chart('c',{chart:{type:'heatmap',backgroundColor:'transparent',spacing:[4,4,4,4],"
        "style:{fontFamily:'IBM Plex Sans,system-ui,sans-serif'},animation:false},"
        "credits:{enabled:false},accessibility:{enabled:false},title:{text:null},legend:{enabled:true,"
        "align:'right',layout:'vertical',verticalAlign:'middle',symbolHeight:150,itemStyle:{color:'var(--c-muted_2)',fontSize:'11px'}},"
        "exporting:{enabled:false},"
        "xAxis:{categories:syms,opposite:true,labels:{rotation:-60,style:{color:'var(--c-muted)',fontSize:'11px'}},lineWidth:0,tickLength:0},"
        "yAxis:{categories:syms,reversed:true,title:{text:null},labels:{style:{color:'var(--c-muted)',fontSize:'11px'}},gridLineWidth:0},"
        "colorAxis:{min:-0.2,max:1,startOnTick:false,endOnTick:false,tickPositions:[0,0.25,0.5,0.75,1],labels:{format:'{value:.2f}',style:{color:'var(--c-muted_2)',fontSize:'11px'}},stops:[[0,'var(--c-subtle)'],[0.17,'var(--c-white)'],[0.6,'var(--c-up_line_2)'],[1,'var(--c-up_dark)']]},"
        "tooltip:{useHTML:true,backgroundColor:'var(--c-white)',borderColor:'var(--c-rule)',borderWidth:1,borderRadius:3,shadow:false,padding:8,style:{color:'var(--c-ink)',fontSize:'12px',lineHeight:'17px'},"
        "formatter:function(){const s=this.series.xAxis.categories,t=this.series.yAxis.categories;"
        "const e=v=>String(v).replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]));"
        "return '<b>'+e(t[this.point.y])+' \\u00d7 '+e(s[this.point.x])+'</b><br>Correlation <b>'+this.point.value.toFixed(2)+'</b>';}},"
        "plotOptions:{heatmap:{borderWidth:1,borderColor:'var(--c-white)',animation:false}},"
        "series:[{name:'Correlation',data:data,dataLabels:{enabled:wide,style:{fontSize:'10px',fontWeight:'400',fontFamily:'IBM Plex Mono,monospace',textOutline:'none'},"
        "formatter:function(){return this.point.value.toFixed(2);}}}]});"
        "})();</script></body></html>"
    )
    st.iframe(resolve(page), height=height + 8)


def render_industry_map(board: pd.DataFrame, x_col: str = "3M Return",
                        x_label: str = "Median 3-month return") -> None:
    """Industries as bubbles: median return (`x_col`, 3M by default) across, share passing both filters up,
    size = number of stocks. Top-right is strong and broad; bottom-left is weak and narrow."""
    from src.ui.highcharts_lib import lib, script_json, text_alternative

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
        _titled("Industry map") + "<style>*{box-sizing:border-box;margin:0}"
        "html,body{background:transparent;font-family:'IBM Plex Sans',system-ui,sans-serif}</style></head>"
        "<body>" + text_alternative(" ".join(
            f"{r['name']}: {x_label.lower()} {_fmt.pct(r['x'], fraction=False)}, "
            f"{_fmt.pct(r['y'], signed_=False, fraction=False)} pass both filters, {r['z']} stocks."
            for r in rows)) +
        "<div id='c' aria-hidden='true' style='width:100%;height:420px'></div><script>"
        + lib("highcharts-more.js") + "</script><script>(function(){"
        "const rows=" + script_json(rows) + ";"
        "const e=v=>String(v).replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]));"
        "const xmax=Math.max.apply(null,rows.map(r=>r.x));const ymax=Math.min(100,Math.max(10,Math.ceil(Math.max.apply(null,rows.map(r=>r.y))*1.15/10)*10));const top5=new Set(rows.slice().sort((a,b)=>b.x-a.x).slice(0,5).map(r=>r.name));const col=r=>r.x>=0?'var(--c-up)':'var(--c-down)';"
        "Highcharts.chart('c',{chart:{type:'bubble',backgroundColor:'transparent',animation:false,spacing:[8,12,4,4],"
        "style:{fontFamily:'IBM Plex Sans,system-ui,sans-serif'},zooming:{type:null}},"
        "credits:{enabled:false},accessibility:{enabled:false},title:{text:null},legend:{enabled:false},exporting:{enabled:false},"
        "xAxis:{maxPadding:0.06,title:{text:" + script_json(x_label + " \u2192") + ",style:{color:'var(--c-muted_2)',fontSize:'11px'}},gridLineWidth:0,"
        "labels:{format:'{value}%',style:{color:'var(--c-muted_2)',fontSize:'11px'}},lineWidth:0,tickLength:0,plotLines:[{value:0,color:'var(--c-rule_strong)',width:1}]},"
        "yAxis:{title:{text:'\\u2191 Share passing both filters',style:{color:'var(--c-muted_2)',fontSize:'11px'}},min:0,max:ymax,endOnTick:false,tickInterval:ymax>60?20:10,gridLineColor:'var(--c-grid)',"
        "labels:{format:'{value}%',style:{color:'var(--c-muted_2)',fontSize:'11px'}}},"
        "tooltip:{useHTML:true,backgroundColor:'var(--c-white)',borderColor:'var(--c-rule)',borderWidth:1,borderRadius:3,shadow:false,padding:8,style:{color:'var(--c-ink)',fontSize:'12px',lineHeight:'17px'},"
        "formatter:function(){const p=this.point;return '<b>'+e(p.name)+'</b><br>" + x_tip + " <b>'+(p.x>0?'+':'')+p.x.toFixed(1)+'%</b>"
        "<br>Passing both <b>'+p.y.toFixed(0)+'%</b><br>'+p.z+' stocks \\u00b7 '+p.top50+' in the top 50';}},"
        "plotOptions:{bubble:{fillOpacity:0.38,minSize:8,maxSize:40,animation:false,marker:{lineWidth:1},"
        "dataLabels:{enabled:true,allowOverlap:false,crop:false,overflow:'allow',style:{fontSize:'11px',fontWeight:'500',color:'var(--c-text_2)',textOutline:'2px var(--c-white)'},"
        "formatter:function(){return e(this.point.name);}}}},"
        "series:[{data:rows.map(r=>({name:r.name,x:r.x,y:r.y,z:r.z,top50:r.top50,color:col(r),labelrank:(top5.has(r.name)?1e6:0)+(r.x>=0?1000:0)+r.z,dataLabels:{allowOverlap:top5.has(r.name),align:(r.x>=(xmax*0.7)?'right':'center'),x:(r.x>=(xmax*0.7)?-14:0)}}))}]});"
        "})();</script></body></html>"
    )
    st.iframe(resolve(page), height=428)


# Twenty muted, distinct hues for the categorical charts (the RRG's
# industries, the sector leadership map and its table): mid-tones that sit
# with the Ledger ink, greys, blue and rust, dark enough to read on white.
CATEGORICAL = (
    "#4F79A8", "#B9643F", "#4E9384", "#8268A9", "#B08D3E", "#6F98BC", "#AE5F74",
    "#76955C", "#8D7462", "#3F8297", "#C2875A", "#717CB0", "#99628A", "#628F6B",
    "#A9776A", "#5A7590", "#9C9053", "#86789E", "#B86F66", "#668785",
)
SECTOR_SOFT_PALETTE = CATEGORICAL


def sector_colours(names) -> dict[str, str]:
    """One soft colour per sector, fixed by name so the map, its table and
    every EMA tab agree (owner, 13 Oct: subtle colours, not green and red)."""
    return {name: CATEGORICAL[i % len(CATEGORICAL)]
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
  data:[{x:r.x0,y:r.y0,marker:{fillColor:'var(--c-white)',lineColor:col(r),lineWidth:1.5,radius:3.5,symbol:'circle'},dataLabels:{enabled:false}},
        {x:r.x1,y:r.y1,marker:{fillColor:col(r),lineColor:'var(--c-white)',lineWidth:1,radius:4.5,symbol:'circle'}}]}));
function paint(chart){
  chart.series.forEach(s=>{const on=!focus||s.name===focus,me=focus&&s.name===focus;
    const c=col(s.options.row);
    s.update({opacity:on?1:0.12,lineWidth:me?2:1.2,zIndex:me?10:1,color:c,
      data:s.options.data.map((p,i)=>Object.assign({},p,{marker:Object.assign({},p.marker,i===0?{lineColor:c}:{fillColor:c})})),
      dataLabels:{enabled:on,style:{fontWeight:me?'600':'500',color:me?'var(--c-ink)':'var(--c-text_2)'}}},false);});
  chart.redraw(false);
  const tag=document.getElementById('pin');tag.textContent=focus?'Showing '+focus+' · tap it again to show all':'Tap a sector to pick it out';
}
const chart=Highcharts.chart('c',{chart:{type:'scatter',backgroundColor:'transparent',animation:false,spacing:[8,12,4,4],
  style:{fontFamily:'IBM Plex Sans,system-ui,sans-serif'},zooming:{type:'xy'}},
  credits:{enabled:false},accessibility:{enabled:false},title:{text:null},legend:{enabled:false},exporting:{enabled:false},
  xAxis:{min:xmin,max:xmax,tickInterval:xtick,gridLineWidth:0,lineWidth:0,tickLength:0,
    title:{text:months+'-month return vs Nifty 500 →',style:{color:'var(--c-muted_2)',fontSize:'11px'}},
    labels:{format:'{value}%',style:{color:'var(--c-muted_2)',fontSize:'11px'}},plotLines:[{value:0,color:'var(--c-rule_strong)',width:1,zIndex:2}]},
  yAxis:{min:0,max:100,tickInterval:20,endOnTick:false,gridLineColor:'var(--c-grid)',
    title:{text:'↑ Stocks above their '+span+'-day EMA',style:{color:'var(--c-muted_2)',fontSize:'11px'}},
    labels:{format:'{value}%',style:{color:'var(--c-muted_2)',fontSize:'11px'}},plotLines:[{value:50,color:'var(--c-rule_strong)',width:1,dashStyle:'Dash',zIndex:2}]},
  tooltip:{useHTML:true,backgroundColor:'var(--c-white)',borderColor:'var(--c-rule)',borderWidth:1,borderRadius:3,shadow:false,padding:8,style:{color:'var(--c-ink)',fontSize:'12px',lineHeight:'17px'},
    formatter:function(){const r=this.series.options.row;
      return '<b>'+e(r.full)+'</b> · '+r.stocks+' stocks<br>'+
      '<span style="opacity:.7">'+e(then)+'</span> '+pct(r.x0)+' vs Nifty 500 · '+r.a0+' of '+r.o0+' above<br>'+
      '<span style="opacity:.7">'+e(now)+'</span> <b>'+pct(r.x1)+'</b> vs Nifty 500 · <b>'+r.a1+' of '+r.o1+'</b> above<br>'+
      '<span style="opacity:.7">Sector '+pct(r.ret)+', Nifty 500 '+pct(r.bench)+(months===1?' this month':' in '+months+' months')+'</span>'+
      (r.lead?'<br>Led by <b>'+e(r.lead)+'</b>':'');}},
  plotOptions:{series:{animation:false,dashStyle:'ShortDash',lineWidth:1.2,marker:{enabled:true},stickyTracking:false,findNearestPointBy:'xy',
    states:{hover:{lineWidthPlus:1.5},inactive:{opacity:0.18}},cursor:'pointer',
    dataLabels:{enabled:true,allowOverlap:false,crop:false,overflow:'allow',x:6,align:'left',verticalAlign:'middle',
      style:{fontSize:'11px',fontWeight:'500',color:'var(--c-text_2)',textOutline:'2px var(--c-white)'},formatter:function(){return e(this.series.name);}},
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
    from src.ui.highcharts_lib import lib, script_json, text_alternative

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
        "lead": ", ".join(f"{sym} {_fmt.pct(v * 100, fraction=False)}" for sym, v in (getattr(r, "Leaders", None) or [])[:2]),
    } for r in board.itertuples()]
    months = int(board["Months"].iloc[0]) if "Months" in board.columns else 1
    then = f"{pd.Timestamp(board['Then'].iloc[0]):%-d %b}"
    now = f"{pd.Timestamp(board['Now'].iloc[0]):%-d %b}"
    js = (_LEADERSHIP_JS.replace("__ROWS__", script_json(rows)).replace("__SPAN__", str(int(span))).replace("__MONTHS__", str(months))
          .replace("__THEN__", script_json(then)).replace("__NOW__", script_json(now))
          .replace("__FOCUS__", script_json(short.get(focus, focus) if focus else None)))
    page = (
        _titled("Sector leadership map") + "<style>*{box-sizing:border-box;margin:0}"
        "html,body{background:transparent;font-family:'IBM Plex Sans',system-ui,sans-serif}"
        "#pin{font-size:12px;color:var(--c-faint);padding:2px 4px 6px}</style></head>"
        "<body>" + text_alternative(" ".join(
            f"{r['full']}: {months}-month return {_fmt.pct(r['ret'], fraction=False)} against the Nifty 500's "
            f"{_fmt.pct(r['bench'], fraction=False)}; {_fmt.pct(r['y1'], signed_=False, fraction=False)} above their "
            f"{span}-day EMA ({_fmt.pct(r['y0'], signed_=False, fraction=False)} on {then})."
            for r in rows)) +
        "<div id='pin'></div><div id='c' aria-hidden='true' style='width:100%;height:500px'></div><script>"
        + lib() + "</script><script>" + js + "</script></body></html>"
    )
    st.iframe(resolve(page), height=530)
