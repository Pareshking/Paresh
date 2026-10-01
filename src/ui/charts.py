"""
Interactive visualizations for NSE Momentum Dashboard.
Includes Candlestick + Volume + Relative Strength drilldown, animated Canvas RRG,
and ECharts-powered charts.
"""

import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.core.logger import logger


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
    """Price with toggleable overlays, volume and RSI.

    Drawn with TradingView Lightweight Charts, where drag pans and pinch zooms
    -- Plotly's drag selects a zoom box, so on a phone reading the chart
    rearranged it. Lightweight Charts is a THIRD-PARTY COMPONENT and a
    component that fails to load renders as blank space rather than an error,
    so any failure falls back to the Plotly renderer. A prettier chart is not
    worth an empty one.
    """
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

    try:
        from src.ui.lightweight_chart import render_lightweight_chart

        render_lightweight_chart(
            symbol,
            close,
            open_=_col(open_prices),
            high=_col(high_prices),
            low=_col(low_prices),
            volume=_col(volume_data),
            overlays=chosen,
            rs=rs_full,
        )
        return
    except Exception as exc:  # ChartUnavailable or anything the component throws
        logger.info("Lightweight chart unavailable (%s); using Plotly.", exc)

    render_candlestick_drilldown(
        symbol,
        rank_df,
        adj_close,
        high_prices=high_prices,
        low_prices=low_prices,
        volume_data=volume_data,
    )


def render_candlestick_drilldown(
    symbol: str,
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
    high_prices: pd.DataFrame | None = None,
    low_prices: pd.DataFrame | None = None,
    volume_data: pd.DataFrame | None = None,
) -> None:
    """Renders the single-stock technical terminal: candlesticks with optional
    moving-average overlays, volume, and RSI (14).

    No exit levels are drawn on the price panel. Both the 2xATR stop and the
    chandelier exit were horizontal lines a few percent apart that crowded the
    price action; both numbers are stated exactly in the key-level tiles.

    Only the Plotly fallback for the stock page, which draws its own identity
    band, statistics and key levels above the chart. The header card, KPI row
    and spec panel this function used to draw (behind a `chrome` flag that its
    one caller always turned off) were removed as unreachable.
    """
    if symbol not in adj_close.columns:
        st.warning(f"No price data available for {symbol}")
        return

    # Timeframe and overlay pills. The moving averages are toggleable because
    # they answer a question ("is it above its 20?") rather than being a
    # permanent fixture -- and three always-on lines make the price itself hard
    # to read on a phone.
    c_tf, c_ma = st.columns([1.5, 2], vertical_alignment="center")
    tf_choice = c_tf.segmented_control(
        "Timeframe",
        ["1M", "3M", "6M", "1Y", "All"],
        default="6M",
        key=f"tf_choice_{symbol}",
        label_visibility="collapsed",
    )
    if not tf_choice:
        tf_choice = "6M"

    overlays = c_ma.pills(
        "Overlays",
        ["20 EMA", "50 EMA", "200 SMA"],
        selection_mode="multi",
        default=["20 EMA", "50 EMA"],
        key=f"ma_overlays_{symbol}",
        label_visibility="collapsed",
    ) or []

    tf_days_map = {"1M": 22, "3M": 64, "6M": 126, "1Y": 252, "All": 500}
    _n_days = tf_days_map.get(tf_choice, 126)

    _close = adj_close[symbol].dropna().iloc[-_n_days:]
    _has_ohlc = (
        high_prices is not None
        and symbol in high_prices.columns
        and low_prices is not None
        and symbol in low_prices.columns
    )

    with st.container():
        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            row_heights=[0.62, 0.18, 0.20],
            vertical_spacing=0.03,
        )

        # 1. Main Candlestick / Price Chart
        if _has_ohlc:
            # On the CLOSE's dates. Each series dropped its own NaNs, so a
            # missing high shifted every later candle onto the wrong day.
            _high = high_prices[symbol].reindex(_close.index)
            _low = low_prices[symbol].reindex(_close.index)
            _open = _close.shift(1).fillna(_close)
            fig.add_trace(
                go.Candlestick(
                    x=_close.index,
                    open=_open,
                    high=_high,
                    low=_low,
                    close=_close,
                    increasing_line_color="#067647",
                    decreasing_line_color="#B42318",
                    name="Price",
                    showlegend=False,
                ),
                row=1,
                col=1,
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=_close.index,
                    y=_close.values,
                    mode="lines",
                    # Price is the subject; the overlays are commentary. It gets
                    # the darkest, heaviest line so it stays readable with two
                    # moving averages crossing it.
                    line={"color": "#0E1726", "width": 2.6},
                    name="Price",
                ),
                row=1,
                col=1,
            )

        # Moving-average overlays, drawn only when their pill is selected.
        # Distinct hues rather than dash patterns: at this line weight a dotted
        # indigo and a dashed amber read as the same grey on a phone screen.
        _ma_specs = [
            ("20 EMA", lambda c: c.ewm(span=20, min_periods=5).mean(), "#0ea5e9", 20),
            ("50 EMA", lambda c: c.ewm(span=50, min_periods=10).mean(), "#7c3aed", 20),
            ("200 SMA", lambda c: c.rolling(200, min_periods=30).mean(), "#B54708", 50),
        ]
        for _ma_name, _ma_calc, _ma_colour, _ma_min_len in _ma_specs:
            if _ma_name not in overlays or len(_close) < _ma_min_len:
                continue
            _ma_series = _ma_calc(_close)
            fig.add_trace(
                go.Scatter(
                    x=_ma_series.index,
                    y=_ma_series.values,
                    mode="lines",
                    line={"color": _ma_colour, "width": 1.6},
                    name=_ma_name,
                ),
                row=1,
                col=1,
            )

        # No exit levels are drawn on the price panel any more. Both the 2xATR
        # stop and the chandelier exit were horizontal lines a few percent
        # apart, crowding the price action they were meant to annotate, and
        # both numbers are stated exactly in the key-level tiles above -- where
        # they can be read rather than estimated off an axis.
        # 2. Volume Subplot
        _vol_available = (
            volume_data is not None
            and symbol in volume_data.columns
            and volume_data[symbol].dropna().gt(0).any()
        )
        if _vol_available:
            _vol = volume_data[symbol].dropna().iloc[-_n_days:]
            _vol_avg = _vol.rolling(20, min_periods=10).mean()
            _vol_colors = [
                (
                    "rgba(5, 150, 105, 0.6)"
                    if (pd.notna(a) and v > a)
                    else "rgba(225, 29, 72, 0.4)"
                )
                for v, a in zip(_vol.values, _vol_avg.values)
            ]
            fig.add_trace(
                go.Bar(
                    x=_vol.index,
                    y=_vol.values,
                    marker_color=_vol_colors,
                    name="Volume",
                    showlegend=False,
                ),
                row=2,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=_vol_avg.index,
                    y=_vol_avg.values,
                    mode="lines",
                    line={"color": "#5E6878", "width": 1.2},
                    name="20D Vol Avg",
                    showlegend=False,
                ),
                row=2,
                col=1,
            )

        # 3. Relative Strength vs Nifty 500 subplot
        full_stock_close = adj_close[symbol].dropna()
        _bench_fb: pd.Series | None = None
        try:
            from src.loaders.price_loader import fetch_benchmark_history
            _bench_fb = fetch_benchmark_history(period="5y")
        except Exception:
            pass
        if _bench_fb is not None and not full_stock_close.empty:
            rs_plotly = compute_rs_series(full_stock_close, _bench_fb)
            rs_plotly = rs_plotly.iloc[-_n_days:]
            if not rs_plotly.empty:
                fig.add_trace(
                    go.Scatter(
                        x=rs_plotly.index,
                        y=rs_plotly.values,
                        mode="lines",
                        line={"color": "#7c3aed", "width": 1.5},
                        name="Rel Strength",
                        showlegend=False,
                        fill="tozeroy",
                        fillcolor="rgba(124,58,237,0.06)",
                    ),
                    row=3,
                    col=1,
                )
                fig.add_hline(
                    y=100,
                    line_color="#5E6878",
                    line_dash="dot",
                    line_width=1,
                    opacity=0.6,
                    row=3,
                    col=1,
                )

        fig.update_layout(
            template="plotly_white",
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
            font={
                "family": "Geist, sans-serif",
                "size": 10,
                "color": "#3C4657",
            },
            xaxis_rangeslider_visible=False,
            yaxis={"title": "Price (₹)", "gridcolor": "#F1F3F6", "zeroline": False},
            # rangemode="tozero" because a volume axis has no meaningful
            # negative half. Production rendered this panel with an axis
            # running to -250M and no bars at all; whatever left the trace
            # empty, an axis that cannot go below zero cannot present that as
            # a plausible reading.
            yaxis2={
                "title": "Volume",
                "gridcolor": "#F1F3F6",
                "zeroline": False,
                "rangemode": "tozero",
            },
            yaxis3={
                "title": "Rel Strength vs Nifty 500",
                "gridcolor": "#F1F3F6",
                "zeroline": False,
            },
            xaxis2={"gridcolor": "#F1F3F6"},
            xaxis3={"gridcolor": "#F1F3F6"},
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "left",
                "x": 0,
                "bgcolor": "rgba(255, 255, 255, 0.9)",
                "bordercolor": "#E3E6EB",
            },
            margin={"l": 10, "r": 10, "t": 20, "b": 10},
            height=490,
            hovermode="x unified",
            # Plotly's default drag is box-zoom, which on a touch screen means
            # every stray tap zooms the chart and there is no obvious way back.
            # Reading is the common case and zooming is the rare one, so drag
            # is off and the modebar keeps the zoom tools for when it is wanted.
            dragmode=False,
        )
        fig.update_xaxes(gridcolor="#F1F3F6")
        if not _vol_available:
            fig.add_annotation(
                text="Volume unavailable for this symbol",
                xref="paper", yref="y2", x=0.5, y=0, showarrow=False,
                font={"size": 10, "color": "#667080"},
            )
        st.plotly_chart(
            fig,
            width="stretch",
            key=f"drill_chart_{symbol}",
            config={
                "scrollZoom": False,
                "doubleClick": "reset",
                "displaylogo": False,
                "modeBarButtonsToRemove": [
                    "select2d", "lasso2d", "autoScale2d", "toggleSpikelines",
                ],
            },
        )


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
    """Build the self-contained animated Canvas RRG HTML component."""
    _CSS = """
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:transparent;height:100%;overflow:hidden}
body{font-family:'Geist',system-ui,sans-serif}
#wrap{position:relative;width:100%}
canvas{display:block;width:100%;cursor:default}
#controls{display:flex;gap:8px;align-items:center;justify-content:center;
  padding:8px 4px 2px;flex-wrap:wrap}
.ctrl-btn{background:#F1F3F6;border:1px solid #E3E6EB;border-radius:6px;
  padding:4px 14px;font-size:11.5px;cursor:pointer;color:#3C4657;
  font-family:inherit;transition:background .15s}
.ctrl-btn:hover{background:#E3E6EB}
.ctrl-btn.active{background:#1e40af;color:#fff;border-color:#1e40af}
#scrub{width:180px;accent-color:#2563eb;cursor:pointer}
#frame-lbl{font-size:10.5px;color:#5E6878;font-family:'Geist Mono',monospace;
  min-width:58px;text-align:center}
#tip{position:absolute;pointer-events:none;background:rgba(15,23,42,.92);
  color:#fff;padding:8px 11px;border-radius:8px;font-size:11px;line-height:1.65;
  display:none;z-index:10;max-width:195px;white-space:nowrap}
@media(prefers-color-scheme:dark){
  .ctrl-btn{background:#1F2A3A;border-color:#3C4657;color:#D0D5DD}
  .ctrl-btn:hover{background:#3C4657}
}
</style>"""

    _HTML_WRAP = """
<div id="wrap"><canvas id="rrg"></canvas><div id="tip"></div></div>
<div id="controls">
  <button class="ctrl-btn" id="btn-play">&#9654; Play</button>
  <input type="range" id="scrub" min="0" value="100">
  <span id="frame-lbl">Current</span>
  <button class="ctrl-btn" id="btn-rst">&#8635; Reset</button>
</div>"""

    _JS = r"""
<script>
const DATA = """ + data_json + r""";

// Industry names come from third-party feeds and the tooltip is HTML.
function esc(v){return String(v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
const canvas = document.getElementById('rrg');
const ctx    = canvas.getContext('2d');
const tip    = document.getElementById('tip');
const btnPlay = document.getElementById('btn-play');
const scrub   = document.getElementById('scrub');
const frameLbl = document.getElementById('frame-lbl');

// ── Bounds ─────────────────────────────────────────────────────────────────
// Every current position, plus the trails of what is shown: a trail nobody
// looks at must not stretch the plot and squeeze everything else into a corner.
const _shown = s => !DATA.highlight.length || DATA.highlight.indexOf(s.industry) >= 0;
const allR = DATA.sectors.flatMap(s => (_shown(s) && s.trail_r.length) ? s.trail_r.concat([s.rs_ratio]) : [s.rs_ratio]);
const allM = DATA.sectors.flatMap(s => (_shown(s) && s.trail_m.length) ? s.trail_m.concat([s.rs_momentum]) : [s.rs_momentum]);
const minX = Math.min(88,  allR.length ? Math.min(...allR) - 2 : 90);
const maxX = Math.max(112, allR.length ? Math.max(...allR) + 2 : 110);
const minY = Math.min(96,  allM.length ? Math.min(...allM) - 1.5 : 97);
const maxY = Math.max(105, allM.length ? Math.max(...allM) + 1.5 : 104.5);

const maxFrames = Math.max(...DATA.sectors.map(s => s.trail_r.length), 1);
let frame = maxFrames - 1;
let playing = false;
let pulsePhase = 0;
let playTimer = null;
let selectedSector = null;

scrub.max   = maxFrames - 1;
scrub.value = maxFrames - 1;

// ── Padding ────────────────────────────────────────────────────────────────
const PAD = {t:40, r:16, b:52, l:50};

// ── Hit test (returns industry name or null) ───────────────────────────────
function hitTest(mx, my) {
  const radius = 36;
  let hit = null, minD = radius;
  for (let i = 0; i < DATA.sectors.length; i++) {
    const s = DATA.sectors[i];
    const hIdx = Math.max(Math.min(frame, s.trail_r.length - 1), 0);
    const hx = s.trail_r.length > 0 ? tx(s.trail_r[hIdx]) : tx(s.rs_ratio);
    const hy = s.trail_m.length > 0 ? ty(s.trail_m[hIdx]) : ty(s.rs_momentum);
    const d = Math.hypot(mx - hx, my - hy);
    if (d < minD) { minD = d; hit = s.industry; }
  }
  return hit;
}

// ── DPI-aware setup ────────────────────────────────────────────────────────
let W = 0, H = 0, dpr = 1;
function setupCanvas() {
  dpr = window.devicePixelRatio || 1;
  const rect = canvas.parentElement.getBoundingClientRect();
  W = Math.max(rect.width, 300);
  // Fill the frame the page gives the chart (taller on desktop, square-ish on
  // a phone), less the play controls underneath.
  const ctrl = document.getElementById('controls');
  const ctrlH = ctrl ? ctrl.getBoundingClientRect().height + 6 : 48;
  H = Math.max(280, Math.round(window.innerHeight - ctrlH));
  canvas.width  = W * dpr;
  canvas.height = H * dpr;
  canvas.style.width  = W + 'px';
  canvas.style.height = H + 'px';
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

// ── Coordinate mapping ─────────────────────────────────────────────────────
function tx(rx) { return PAD.l + (rx - minX) / (maxX - minX) * (W - PAD.l - PAD.r); }
function ty(ry) { return (H - PAD.b) - (ry - minY) / (maxY - minY) * (H - PAD.t - PAD.b); }

// ── Catmull-Rom smooth path ────────────────────────────────────────────────
function drawSmooth(pts, alpha) {
  if (pts.length < 2) return;
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(i - 1, 0)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(i + 2, pts.length - 1)];
    const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
    const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
    const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
    const cp2y = p2[1] - (p3[1] - p1[1]) / 6;
    ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1]);
  }
  ctx.stroke();
}

// ── Arrowhead at (x1,y1) pointing FROM (x0,y0) ────────────────────────────
function drawArrow(x0, y0, x1, y1, color) {
  const dx = x1 - x0, dy = y1 - y0;
  const len = Math.hypot(dx, dy);
  if (len < 4) return;
  const ang = Math.atan2(dy, dx);
  const sz = 9;
  ctx.save();
  ctx.translate(x1, y1);
  ctx.rotate(ang);
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.lineTo(-sz, -sz * 0.42);
  ctx.lineTo(-sz * 0.55, 0);
  ctx.lineTo(-sz, sz * 0.42);
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
  ctx.restore();
}

// ── Draw tick labels on axis ───────────────────────────────────────────────
// A readable step: one label per `px` pixels at most, rounded to 1/2/2.5/5.
function niceStep(range, avail, px) {
  const raw = range / Math.max(1, Math.floor(avail / px));
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  for (const m of [1, 2, 2.5, 5, 10]) { if (m * mag >= raw) return m * mag; }
  return 10 * mag;
}

function drawTicks() {
  ctx.font = '11px Geist Mono,monospace';
  ctx.fillStyle = '#5E6878';
  ctx.textAlign = 'center';
  const availW = W - PAD.l - PAD.r;
  const xStep = niceStep(maxX - minX, availW, 56);
  for (let v = Math.ceil(minX / xStep) * xStep; v <= maxX; v += xStep) {
    const xp = tx(v);
    ctx.fillText(Number.isInteger(xStep) ? v.toFixed(0) : v.toFixed(1), xp, H - PAD.b + 16);
    ctx.beginPath();
    ctx.moveTo(xp, H - PAD.b);
    ctx.lineTo(xp, H - PAD.b + 4);
    ctx.strokeStyle = '#D0D5DD';
    ctx.lineWidth = 0.8;
    ctx.stroke();
  }
  ctx.textAlign = 'right';
  const yStep = niceStep(maxY - minY, H - PAD.t - PAD.b, 34);
  for (let v = Math.ceil(minY / yStep) * yStep; v <= maxY; v += yStep) {
    const yp = ty(v);
    ctx.fillText(yStep < 1 ? v.toFixed(1) : v.toFixed(0), PAD.l - 6, yp + 4);
    ctx.beginPath();
    ctx.moveTo(PAD.l - 4, yp);
    ctx.lineTo(PAD.l, yp);
    ctx.stroke();
  }
}

// ── Main draw ─────────────────────────────────────────────────────────────
function draw() {
  setupCanvas();
  ctx.clearRect(0, 0, W, H);

  const dark = window.matchMedia('(prefers-color-scheme:dark)').matches;
  const bg   = dark ? '#0E1726' : '#ffffff';
  const gridC = dark ? '#1F2A3A' : '#E3E6EB';
  const crossC = dark ? '#3C4657' : '#667080';
  const textC  = dark ? '#667080' : '#5E6878';

  // canvas background
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  // quadrant fills
  const quads = [
    {x0:minX, x1:100, y0:100, y1:maxY, fill:'rgba(224,231,255,0.45)', lbl:'Improving', lc:'#3b82f6', ax:'left',  lxr:0.04, lyr:0.07},
    {x0:100,  x1:maxX,y0:100, y1:maxY, fill:'rgba(220,252,231,0.45)', lbl:'Leading',   lc:'#067647', ax:'right', lxr:0.96, lyr:0.07},
    {x0:minX, x1:100, y0:minY,y1:100,  fill:'rgba(254,226,226,0.45)', lbl:'Lagging',   lc:'#B42318', ax:'left',  lxr:0.04, lyr:0.93},
    {x0:100,  x1:maxX,y0:minY,y1:100,  fill:'rgba(254,249,195,0.45)', lbl:'Weakening', lc:'#ca8a04', ax:'right', lxr:0.96, lyr:0.93},
  ];
  for (const q of quads) {
    const px0 = tx(q.x0), py0 = ty(q.y1), px1 = tx(q.x1), py1 = ty(q.y0);
    ctx.fillStyle = q.fill;
    ctx.fillRect(px0, py0, px1 - px0, py1 - py0);
    const lx = PAD.l + q.lxr * (W - PAD.l - PAD.r);
    const ly = PAD.t + q.lyr * (H - PAD.t - PAD.b);
    ctx.font = 'bold 12.5px Geist,system-ui';
    ctx.fillStyle = q.lc;
    ctx.textAlign = q.ax;
    ctx.globalAlpha = 0.85;
    ctx.fillText(q.lbl, lx, ly);
    ctx.globalAlpha = 1;
  }

  // watermark
  ctx.font = '10.5px Geist,system-ui';
  ctx.fillStyle = textC;
  ctx.textAlign = 'center';
  ctx.globalAlpha = 0.28;
  ctx.globalAlpha = 1;

  // axis grid lines
  ctx.strokeStyle = gridC;
  ctx.lineWidth = 0.7;
  ctx.setLineDash([]);
  const availW2 = W - PAD.l - PAD.r;
  const xStepG = Math.max(2, Math.ceil((maxX - minX) / Math.floor(availW2 / 30)));
  for (let v = Math.ceil(minX / xStepG) * xStepG; v <= maxX; v += xStepG) {
    ctx.beginPath(); ctx.moveTo(tx(v), PAD.t); ctx.lineTo(tx(v), H - PAD.b); ctx.stroke();
  }
  const yStep = (maxY - minY) > 8 ? 1 : 0.5;
  for (let v = Math.ceil(minY*2)/2; v <= maxY; v += yStep) {
    ctx.beginPath(); ctx.moveTo(PAD.l, ty(v)); ctx.lineTo(W - PAD.r, ty(v)); ctx.stroke();
  }

  // crosshairs at (100, 100)
  ctx.strokeStyle = crossC;
  ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(PAD.l, ty(100)); ctx.lineTo(W - PAD.r, ty(100)); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(tx(100), PAD.t); ctx.lineTo(tx(100), H - PAD.b); ctx.stroke();

  // ticks and axis labels
  drawTicks();
  ctx.font = 'bold 10px Geist,system-ui';
  ctx.fillStyle = textC;
  ctx.textAlign = 'center';
  ctx.fillText('RS →', tx((minX + maxX) / 2), H - 6);
  ctx.save();
  ctx.translate(13, ty((minY + maxY) / 2));
  ctx.rotate(-Math.PI / 2);
  ctx.fillText('↑ Momentum', 0, 0);
  ctx.restore();

  // ── Selected sector banner ────────────────────────────────────────────────
  if (selectedSector) {
    const sel = DATA.sectors.find(s => s.industry === selectedSector);
    if (sel) {
      const hIdx = Math.max(Math.min(frame, sel.trail_r.length - 1), 0);
      const hr = sel.trail_r.length > 0 ? sel.trail_r[hIdx] : sel.rs_ratio;
      const hm = sel.trail_m.length > 0 ? sel.trail_m[hIdx] : sel.rs_momentum;
      ctx.save();
      ctx.font = 'bold 12px Geist,system-ui';
      ctx.fillStyle = sel.color;
      ctx.textAlign = 'center';
      ctx.fillText(sel.industry + '  ·  ' + sel.quadrant + '  ·  R:' + hr.toFixed(1) + '  M:' + hm.toFixed(1), W / 2, 18);
      ctx.font = '10px Geist,system-ui';
      ctx.fillStyle = textC;
      ctx.fillText('Tap dot again or empty area to deselect', W / 2, 31);
      ctx.restore();
    }
  }

  // ── Sectors ──────────────────────────────────────────────────────────────
  const hasFilter = DATA.highlight.length > 0;
  const hasUserSel = selectedSector !== null;

  for (let si = 0; si < DATA.sectors.length; si++) {
    const s = DATA.sectors[si];
    let active, alpha;
    if (hasUserSel) {
      active = (s.industry === selectedSector);
      alpha  = active ? 1.0 : 0.07;
    } else if (hasFilter) {
      active = DATA.highlight.indexOf(s.industry) >= 0;
      alpha  = active ? 1.0 : 0.12;
    } else {
      active = true;
      alpha  = 1.0;
    }
    const trailN = s.trail_r.length;
    const fend   = Math.min(frame + 1, trailN);
    // The axes are fitted to the shown trails; faded ones may run past them.
    ctx.save();
    if (!active) {
      ctx.beginPath();
      ctx.rect(PAD.l, PAD.t, W - PAD.l - PAD.r, H - PAD.t - PAD.b);
      ctx.clip();
    }

    // build pixel trail points up to current frame
    const pts = [];
    for (let i = 0; i < fend; i++) pts.push([tx(s.trail_r[i]), ty(s.trail_m[i])]);

    if (pts.length >= 2) {
      // smooth trail with graduated opacity
      for (let j = 1; j < pts.length; j++) {
        const segAlpha = 0.18 + 0.82 * (j / pts.length);
        ctx.globalAlpha = alpha * segAlpha;
        ctx.strokeStyle = s.color;
        ctx.lineWidth   = active ? 2.5 : 1.2;
        ctx.lineCap     = 'round';
        ctx.lineJoin    = 'round';
        drawSmooth(pts.slice(Math.max(j - 1, 0), j + 1), alpha * segAlpha);
      }
      // small historical dots on trail
      if (active) {
        for (let j = 0; j < pts.length - 1; j++) {
          const segAlpha = 0.22 + 0.6 * (j / pts.length);
          ctx.globalAlpha = alpha * segAlpha * 0.7;
          ctx.beginPath();
          ctx.arc(pts[j][0], pts[j][1], 3, 0, Math.PI * 2);
          ctx.fillStyle = s.color;
          ctx.fill();
        }
      }
      // direction arrow at tip
      if (active && pts.length >= 2) {
        ctx.globalAlpha = alpha;
        const last = pts[pts.length - 1];
        const prev = pts[pts.length - 2];
        drawArrow(prev[0], prev[1], last[0], last[1], s.color);
      }
    }

    // head dot position
    const hIdx = Math.max(Math.min(frame, trailN - 1), 0);
    const hx   = trailN > 0 ? tx(s.trail_r[hIdx]) : tx(s.rs_ratio);
    const hy   = trailN > 0 ? ty(s.trail_m[hIdx]) : ty(s.rs_momentum);

    // pulsing ring (only active sectors at the final / current frame)
    if (active && frame >= trailN - 1) {
      const pulse = 0.5 + 0.5 * Math.sin(pulsePhase);
      const ringR = 13 + pulse * 5;
      ctx.globalAlpha = alpha * (0.25 + 0.25 * pulse);
      ctx.beginPath();
      ctx.arc(hx, hy, ringR, 0, Math.PI * 2);
      ctx.strokeStyle = s.color;
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    // white border circle
    ctx.globalAlpha = alpha;
    ctx.beginPath();
    ctx.arc(hx, hy, active ? 9 : 5, 0, Math.PI * 2);
    ctx.fillStyle = bg;
    ctx.fill();
    // coloured fill
    ctx.beginPath();
    ctx.arc(hx, hy, active ? 7.5 : 4, 0, Math.PI * 2);
    ctx.fillStyle = s.color;
    ctx.fill();

    // label beside head — on mobile only show for selected; on wide show all
    const showLabel = hasUserSel ? active : (W >= 420);
    if (active && showLabel) {
      ctx.globalAlpha = 1;
      ctx.font = (active && hasUserSel ? 'bold 11px' : '9px') + ' Geist,system-ui';
      ctx.fillStyle = s.color;
      ctx.textAlign = 'left';
      ctx.fillText(' ' + s.industry, hx + (hasUserSel ? 12 : 9), hy - 4);
    }

    ctx.restore();
    ctx.globalAlpha = 1;
  }
}

// ── RAF loop ──────────────────────────────────────────────────────────────
function tick() {
  pulsePhase += 0.07;
  draw();
  requestAnimationFrame(tick);
}

// ── Playback ──────────────────────────────────────────────────────────────
function updateLabel() {
  const off = frame - (maxFrames - 1);
  frameLbl.textContent = off === 0 ? 'Current' : ('T' + off);
}

function stepPlay() {
  if (!playing) return;
  frame++;
  scrub.value = frame;
  updateLabel();
  if (frame >= maxFrames - 1) {
    playing = false;
    btnPlay.textContent = '▶ Play';
    btnPlay.classList.remove('active');
    return;
  }
  playTimer = setTimeout(stepPlay, 130);
}

btnPlay.addEventListener('click', function() {
  if (playing) {
    playing = false;
    clearTimeout(playTimer);
    btnPlay.textContent = '▶ Play';
    btnPlay.classList.remove('active');
  } else {
    playing = true;
    frame = 0;
    scrub.value = 0;
    updateLabel();
    btnPlay.textContent = '⏸ Pause';
    btnPlay.classList.add('active');
    stepPlay();
  }
});

scrub.addEventListener('input', function() {
  playing = false;
  clearTimeout(playTimer);
  btnPlay.textContent = '▶ Play';
  btnPlay.classList.remove('active');
  frame = parseInt(scrub.value);
  updateLabel();
});

document.getElementById('btn-rst').addEventListener('click', function() {
  playing = false;
  clearTimeout(playTimer);
  btnPlay.textContent = '▶ Play';
  btnPlay.classList.remove('active');
  frame = maxFrames - 1;
  scrub.value = maxFrames - 1;
  updateLabel();
});

// ── Hover tooltip ─────────────────────────────────────────────────────────
canvas.addEventListener('mousemove', function(e) {
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  let nearest = null, minD = 20;
  for (let i = 0; i < DATA.sectors.length; i++) {
    const s    = DATA.sectors[i];
    const hIdx = Math.max(Math.min(frame, s.trail_r.length - 1), 0);
    const hx   = s.trail_r.length > 0 ? tx(s.trail_r[hIdx]) : tx(s.rs_ratio);
    const hy   = s.trail_m.length > 0 ? ty(s.trail_m[hIdx]) : ty(s.rs_momentum);
    const d    = Math.hypot(mx - hx, my - hy);
    if (d < minD) { minD = d; nearest = s; }
  }
  if (nearest) {
    const hIdx = Math.max(Math.min(frame, nearest.trail_r.length - 1), 0);
    const hr   = nearest.trail_r.length > 0 ? nearest.trail_r[hIdx] : nearest.rs_ratio;
    const hm   = nearest.trail_m.length > 0 ? nearest.trail_m[hIdx] : nearest.rs_momentum;
    tip.style.display = 'block';
    tip.style.left    = (mx + 14) + 'px';
    tip.style.top     = (my - 8)  + 'px';
    tip.innerHTML =
      '<b style="color:' + nearest.color + '">' + esc(nearest.industry) + '</b><br>' +
      'Quadrant: <b>' + esc(nearest.quadrant) + '</b><br>' +
      'RS: <b>' + hr.toFixed(2) + '</b><br>' +
      'Momentum: <b>' + hm.toFixed(2) + '</b><br>' +
      'Stocks: ' + nearest.stocks;
    canvas.style.cursor = 'pointer';
  } else {
    tip.style.display  = 'none';
    canvas.style.cursor = 'default';
  }
});
canvas.addEventListener('mouseleave', function() { tip.style.display = 'none'; });

// ── Click / Tap to highlight ───────────────────────────────────────────────
canvas.addEventListener('click', function(e) {
  const rect = canvas.getBoundingClientRect();
  const hit = hitTest(e.clientX - rect.left, e.clientY - rect.top);
  selectedSector = (hit === selectedSector) ? null : hit;
});

canvas.addEventListener('touchend', function(e) {
  e.preventDefault();
  const t = e.changedTouches[0];
  const rect = canvas.getBoundingClientRect();
  const hit = hitTest(t.clientX - rect.left, t.clientY - rect.top);
  selectedSector = (hit === selectedSector) ? null : hit;
  tip.style.display = 'none';
}, {passive: false});

window.addEventListener('resize', setupCanvas);
updateLabel();
tick();
</script>"""

    return "<!DOCTYPE html><html><head><meta charset='utf-8'>" + _CSS + "</head><body>" + _HTML_WRAP + _JS + "</body></html>"


def render_rrg_chart(
    rrg_df: pd.DataFrame,
    highlight_industries: list[str] | None = None,
    current_date_str: str = "",
) -> None:
    """Animated Canvas RRG — 60 fps, Catmull-Rom trails, direction arrows, pulsing dots."""
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
