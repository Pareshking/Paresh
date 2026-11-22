"""
Interactive visualizations for NSE Momentum Dashboard.
The correlation heatmap and other Highcharts frames.
"""

import json
import pandas as pd
import streamlit as st
from src.ui import formats as _fmt
from src.ui.tokens import FONTS, resolve

# Each chart is its own document, so it loads the theme's fonts itself.
_HEAD = "<!DOCTYPE html><html lang='en'><head><title>Chart</title><meta charset='utf-8'><link rel='stylesheet' href='" + FONTS["font_css"] + "'>"


def _titled(title: str) -> str:
    """The frame head with a title that says what the chart is (audit F22/F26)."""
    return _HEAD.replace("<title>Chart</title>", f"<title>{title}</title>")



# The stock page's chart is src/ui/stock_chart.render_price_chart (S182): price and the ranking's
# 50D EMA, Volume, RS against Nifty Total Market. The old Highcharts-era overlay picker is gone.


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
        # The frame's document can still measure 0 wide when the chart is
        # created, and Highcharts then falls back to its 600px default and
        # never looks again: on a phone the heatmap drew 600px inside a 324px
        # frame whose host is overflow:hidden, so the right of it was simply
        # cut off (owner, 10 Nov 2026: "other places also have similar
        # issue"). Reflow once the frame has a width, and on every resize.
        "const c=Highcharts.charts[Highcharts.charts.length-1];"
        "const fit=function(){try{c.reflow();}catch(e){}};"
        "requestAnimationFrame(fit);window.addEventListener('resize',fit);"
        "if(window.ResizeObserver){new ResizeObserver(fit)"
        ".observe(document.getElementById('c'));}"
        "})();</script></body></html>"
    )
    st.iframe(resolve(page), height=height + 8)


# Twenty muted, distinct hues for the categorical charts (the RRG's
# industries, the sector leadership map and its table): mid-tones that sit
# with the Ledger ink, greys, blue and rust, dark enough to read on white.
CATEGORICAL = (
    "#4F79A8", "#B9643F", "#4E9384", "#8268A9", "#B08D3E", "#6F98BC", "#AE5F74",
    "#76955C", "#8D7462", "#3F8297", "#C2875A", "#717CB0", "#99628A", "#628F6B",
    "#A9776A", "#5A7590", "#9C9053", "#86789E", "#B86F66", "#668785",
)
def leadership_colours(board: pd.DataFrame) -> dict[str, str]:
    """The sector leadership map's colours (owner, 8 Nov 2026, S97 g): every
    sector a quiet grey, the leader (best return against the Nifty 500 today)
    in blue and the laggard (worst) in rust; the sector a reader taps turns ink
    in the chart itself. With twenty hues no dot could be matched to its name;
    grey plus three answers "who is leading?" at a glance, and it is still not
    green and red (13 Oct)."""
    colours = {s: "var(--c-quiet)" for s in board["Sector"]}
    if len(board) >= 2:
        ranked = board.sort_values("x_now")
        colours[ranked["Sector"].iloc[-1]] = "var(--c-up)"
        colours[ranked["Sector"].iloc[0]] = "var(--c-down)"
    return colours


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
        {x:r.x1,y:r.y1,dataLabels:(r.x1-xmin)/xspan>0.62?{align:'right',x:-6}:{},marker:{fillColor:col(r),lineColor:'var(--c-white)',lineWidth:1,radius:4.5,symbol:'circle'}}]}));
function paint(chart){
  chart.series.forEach(s=>{const on=!focus||s.name===focus,me=focus&&s.name===focus;
    const c=me?'var(--c-ink)':col(s.options.row);
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
    title:{text:months+'-month return vs all ranked stocks (equal weight) →',style:{color:'var(--c-muted_2)',fontSize:'11px'}},
    labels:{format:'{value}%',style:{color:'var(--c-muted_2)',fontSize:'11px'}},plotLines:[{value:0,color:'var(--c-rule_strong)',width:1,zIndex:2}]},
  yAxis:{min:0,max:100,tickInterval:20,endOnTick:false,gridLineColor:'var(--c-grid)',
    title:{text:'↑ Stocks above their '+span+'D EMA',style:{color:'var(--c-muted_2)',fontSize:'11px'}},
    labels:{format:'{value}%',style:{color:'var(--c-muted_2)',fontSize:'11px'}},plotLines:[{value:50,color:'var(--c-rule_strong)',width:1,dashStyle:'Dash',zIndex:2}]},
  tooltip:{useHTML:true,backgroundColor:'var(--c-white)',borderColor:'var(--c-rule)',borderWidth:1,borderRadius:3,shadow:false,padding:8,style:{color:'var(--c-ink)',fontSize:'12px',lineHeight:'17px'},
    formatter:function(){const r=this.series.options.row;
      return '<b>'+e(r.full)+'</b> · '+r.stocks+' stocks<br>'+
      '<span style="opacity:.7">'+e(then)+'</span> '+pct(r.x0)+' vs all ranked stocks · '+r.a0+' of '+r.o0+' above<br>'+
      '<span style="opacity:.7">'+e(now)+'</span> <b>'+pct(r.x1)+'</b> vs all ranked stocks · <b>'+r.a1+' of '+r.o1+'</b> above<br>'+
      '<span style="opacity:.7">Sector '+pct(r.ret)+', all ranked stocks '+pct(r.bench)+(months===1?' this month':' in '+months+' months')+'</span>'+
      (r.lead?'<br>Led by <b>'+e(r.lead)+'</b>':'');}},
  plotOptions:{series:{animation:false,dashStyle:'ShortDash',lineWidth:1.2,marker:{enabled:true},stickyTracking:false,findNearestPointBy:'xy',
    states:{hover:{lineWidthPlus:1.5},inactive:{opacity:0.18}},cursor:'pointer',
    dataLabels:{enabled:true,allowOverlap:false,crop:false,overflow:'allow',x:6,align:'left',verticalAlign:'middle',
      style:{fontSize:'11px',fontWeight:'500',color:'var(--c-text_2)',textOutline:'2px var(--c-white)'},formatter:function(){return e(this.series.name);}},
    // A name near the right edge reads leftward, so a phone does not cut it off (21 Nov 2026).

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
    colour = leadership_colours(board)
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
            f"{span}D EMA ({_fmt.pct(r['y0'], signed_=False, fraction=False)} on {then})."
            for r in rows)) +
        "<div id='pin'></div><div id='c' aria-hidden='true' style='width:100%;height:500px'></div><script>"
        + lib() + "</script><script>" + js + "</script></body></html>"
    )
    st.iframe(resolve(page), height=530)
