"""
Interactive visualizations for NSE Momentum Dashboard.
Includes Candlestick + Volume + RSI drilldown, animated Canvas RRG,
ECharts-powered charts, and Sector Treemaps.
"""

import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.core.logger import logger
from src.ui.theme import clean_html


def compute_rsi_series(prices: pd.Series, period: int = 14) -> pd.Series:
    """Computes 14-period Relative Strength Index (RSI)."""
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


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
        "Overlays", ["20 EMA", "50 EMA", "200 SMA"],
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
    rsi_full = compute_rsi_series(full_close, 14)

    try:
        from src.ui.lightweight_chart import ChartUnavailable, render_lightweight_chart

        render_lightweight_chart(
            symbol,
            close,
            open_=_col(open_prices),
            high=_col(high_prices),
            low=_col(low_prices),
            volume=_col(volume_data),
            overlays=chosen,
            rsi=rsi_full,
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
        chrome=False,
    )


def render_candlestick_drilldown(
    symbol: str,
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
    high_prices: pd.DataFrame | None = None,
    low_prices: pd.DataFrame | None = None,
    volume_data: pd.DataFrame | None = None,
    chrome: bool = True,
) -> None:
    """Renders the single-stock technical terminal: candlesticks with optional
    moving-average overlays, volume, and RSI (14).

    No exit levels are drawn on the price panel. Both the 2xATR stop and the
    chandelier exit were horizontal lines a few percent apart that crowded the
    price action; both numbers are stated exactly in the key-level tiles.

    `chrome` draws the header card, the KPI row and the right-hand spec panel.
    The stock detail page turns it off because it renders richer versions of
    all three above the chart.
    """
    if symbol not in adj_close.columns:
        st.warning(f"No price data available for {symbol}")
        return

    row = rank_df[rank_df["Symbol"] == symbol]
    if row.empty:
        st.warning(f"{symbol} not found in rankings.")
        return
    row_s = row.iloc[0]

    # Header Card with Logo Badge, Symbol, Company, Industry
    industry = row_s.get("Industry", "—")
    tv_sector = row_s.get("TV_Sector", "")
    cmp_val = row_s.get("CMP", 0)
    ret_3m = row_s.get("3M Return", 0)
    ret_6m = row_s.get("6M Return", 0)
    ret_clr = "#059669" if ret_3m >= 0 else "#e11d48"
    rank_num = int(row_s["Rank"]) if pd.notna(row_s.get("Rank")) else "—"

    header_html = f"""
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px; margin-bottom: 14px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03); flex-wrap: wrap; gap: 12px;">
        <div style="display: flex; align-items: center; gap: 14px;">
            <div style="width: 44px; height: 44px; border-radius: 12px; background-color: #f1f5f9; border: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.1rem; color: #0f172a;">
                {symbol[:2]}
            </div>
            <div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-weight: 800; font-size: 1.3rem; color: #0f172a; letter-spacing: -0.02em;">
                        {symbol}
                    </span>
                    <span style="font-family: 'IBM Plex Mono', monospace; font-size: 0.75rem; font-weight: 700; background-color: #eef2ff; color: #4f46e5; border: 1px solid #c7d2fe; padding: 2px 8px; border-radius: 20px;">
                        Rank #{rank_num}
                    </span>
                </div>
                <div style="font-size: 0.78rem; color: #64748b;">
                    NSE: {symbol} · {industry} {f'· {tv_sector}' if tv_sector else ''}
                </div>
            </div>
        </div>

        <div style="display: flex; align-items: baseline; gap: 14px;">
            <div>
                <span style="font-family: 'IBM Plex Mono', monospace; font-size: 1.6rem; font-weight: 800; color: #0f172a;">
                    ₹{cmp_val:,.0f}
                </span>
            </div>
            <div style="font-family: 'IBM Plex Mono', monospace; font-size: 0.9rem; font-weight: 700; color: {ret_clr}; background-color: {ret_clr}15; padding: 4px 10px; border-radius: 8px; border: 1px solid {ret_clr}30;">
                3M: {ret_3m:+.1%}
            </div>
        </div>
    </div>
    """
    # The stock page renders its own identity band and statistics, and renders
    # them better, so it asks for the chart WITHOUT this chrome. Keeping the
    # chrome behind a flag means the older inline drilldown keeps working
    # unchanged rather than being rewritten to suit the new page.
    if chrome:
        st.markdown(clean_html(header_html), unsafe_allow_html=True)

        # 4 KPI metric cards row
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("3M Sharpe Ratio", f"{row_s.get('3M Sharpe', 0):.2f}")
        k2.metric("6M Return", f"{ret_6m:.1%}")
        k3.metric("ATR Volatility %", f"{row_s.get('ATR %', 0):.1f}%")
        k4.metric("Market Cap", f"₹{row_s.get('Market Cap (Cr)', 0):,.0f} Cr")

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

    # Without the chrome the chart takes the full width; the spec panel's
    # contents already appear as key-level tiles on the stock page.
    if chrome:
        c_chart, c_spec = st.columns([2.6, 1.1])
    else:
        c_chart, c_spec = st.container(), None

    with c_chart:
        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            row_heights=[0.62, 0.18, 0.20],
            vertical_spacing=0.03,
        )

        # 1. Main Candlestick / Price Chart
        if _has_ohlc:
            _high = high_prices[symbol].dropna().iloc[-_n_days:]
            _low = low_prices[symbol].dropna().iloc[-_n_days:]
            _open = _close.shift(1).fillna(_close)
            fig.add_trace(
                go.Candlestick(
                    x=_close.index,
                    open=_open,
                    high=_high,
                    low=_low,
                    close=_close,
                    increasing_line_color="#059669",
                    decreasing_line_color="#e11d48",
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
                    line={"color": "#0f172a", "width": 2.6},
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
            ("200 SMA", lambda c: c.rolling(200, min_periods=30).mean(), "#d97706", 50),
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
                    line={"color": "#64748b", "width": 1.2},
                    name="20D Vol Avg",
                    showlegend=False,
                ),
                row=2,
                col=1,
            )

        # 3. RSI (14) Subplot
        full_stock_close = adj_close[symbol].dropna()
        if len(full_stock_close) >= 15:
            rsi_series = compute_rsi_series(full_stock_close, 14).iloc[-_n_days:]
            fig.add_trace(
                go.Scatter(
                    x=rsi_series.index,
                    y=rsi_series.values,
                    mode="lines",
                    line={"color": "#0284c7", "width": 1.5},
                    name="RSI (14)",
                    showlegend=False,
                ),
                row=3,
                col=1,
            )
            fig.add_hline(
                y=70,
                line_color="#e11d48",
                line_dash="dot",
                line_width=1,
                opacity=0.7,
                row=3,
                col=1,
            )
            fig.add_hline(
                y=30,
                line_color="#059669",
                line_dash="dot",
                line_width=1,
                opacity=0.7,
                row=3,
                col=1,
            )

        fig.update_layout(
            template="plotly_white",
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
            font={
                "family": "Plus Jakarta Sans, sans-serif",
                "size": 10,
                "color": "#334155",
            },
            xaxis_rangeslider_visible=False,
            yaxis={"title": "Price (₹)", "gridcolor": "#f1f5f9", "zeroline": False},
            # rangemode="tozero" because a volume axis has no meaningful
            # negative half. Production rendered this panel with an axis
            # running to -250M and no bars at all; whatever left the trace
            # empty, an axis that cannot go below zero cannot present that as
            # a plausible reading.
            yaxis2={
                "title": "Volume",
                "gridcolor": "#f1f5f9",
                "zeroline": False,
                "rangemode": "tozero",
            },
            yaxis3={
                "title": "RSI (14)",
                "range": [0, 100],
                "gridcolor": "#f1f5f9",
                "zeroline": False,
            },
            xaxis2={"gridcolor": "#f1f5f9"},
            xaxis3={"gridcolor": "#f1f5f9"},
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "left",
                "x": 0,
                "bgcolor": "rgba(255, 255, 255, 0.9)",
                "bordercolor": "#e2e8f0",
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
        fig.update_xaxes(gridcolor="#f1f5f9")
        if not _vol_available:
            fig.add_annotation(
                text="Volume unavailable for this symbol",
                xref="paper", yref="y2", x=0.5, y=0, showarrow=False,
                font={"size": 10, "color": "#94a3b8"},
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

    if c_spec is None:
        return

    with c_spec:
        sl_raw = row_s.get("Stop Loss")
        sl_str = (
            f"₹{float(sl_raw):,.0f}"
            if pd.notna(sl_raw) and isinstance(sl_raw, (int, float))
            else "—"
        )

        ch_raw = row_s.get("Chand Exit")
        ch_str = (
            f"₹{float(ch_raw):,.0f}"
            if pd.notna(ch_raw) and isinstance(ch_raw, (int, float))
            else "—"
        )

        hi_raw = row_s.get("52W High")
        hi_str = (
            f"₹{float(hi_raw):,.0f}"
            if pd.notna(hi_raw) and isinstance(hi_raw, (int, float))
            else "—"
        )

        pct_hi_raw = row_s.get("% High")
        pct_hi_str = (
            f"{float(pct_hi_raw):+.1f}%"
            if pd.notna(pct_hi_raw) and isinstance(pct_hi_raw, (int, float))
            else "—"
        )
        pct_hi_clr = (
            "#059669"
            if (pd.notna(pct_hi_raw) and float(pct_hi_raw) >= -10)
            else "#d97706"
        )

        pct_ema_raw = row_s.get("% 50 EMA")
        pct_ema_str = (
            f"{float(pct_ema_raw):+.1f}%"
            if pd.notna(pct_ema_raw) and isinstance(pct_ema_raw, (int, float))
            else "—"
        )
        pct_ema_clr = (
            "#059669"
            if (pd.notna(pct_ema_raw) and float(pct_ema_raw) >= 0)
            else "#e11d48"
        )

        pers_raw = row_s.get("Persistence")
        pers_str = (
            f"{float(pers_raw):.0f}%"
            if pd.notna(pers_raw) and isinstance(pers_raw, (int, float))
            else "—"
        )

        vol_sig = row_s.get("Volume", "Normal") or "Normal"
        gap_stat = row_s.get("Data Gap", "Clean") or "Clean"

        spec_html = f"""
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 14px; padding: 16px; height: 490px; overflow-y: auto;">
            <div style="font-weight: 700; font-size: 0.92rem; color: #0f172a; margin-bottom: 12px; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">
                Technical Specifications
            </div>
            
            <div class="stock-card-metric-row" style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-top: 1px solid #f1f5f9; font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem;">
                <span style="color: #64748b;">Stop Loss (2×ATR)</span>
                <strong style="color: #e11d48;">{sl_str}</strong>
            </div>
            <div class="stock-card-metric-row" style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-top: 1px solid #f1f5f9; font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem;">
                <span style="color: #64748b;">Chandelier Exit (3×ATR)</span>
                <strong style="color: #d97706;">{ch_str}</strong>
            </div>
            <div class="stock-card-metric-row" style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-top: 1px solid #f1f5f9; font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem;">
                <span style="color: #64748b;">52W High</span>
                <strong style="color: #0f172a;">{hi_str}</strong>
            </div>
            <div class="stock-card-metric-row" style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-top: 1px solid #f1f5f9; font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem;">
                <span style="color: #64748b;">Distance to 52W High</span>
                <strong style="color: {pct_hi_clr};">{pct_hi_str}</strong>
            </div>
            <div class="stock-card-metric-row" style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-top: 1px solid #f1f5f9; font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem;">
                <span style="color: #64748b;">vs 50 EMA</span>
                <strong style="color: {pct_ema_clr};">{pct_ema_str}</strong>
            </div>
            <div class="stock-card-metric-row" style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-top: 1px solid #f1f5f9; font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem;">
                <span style="color: #64748b;">Persistence (Pos Days)</span>
                <strong style="color: #0f172a;">{pers_str}</strong>
            </div>
            <div class="stock-card-metric-row" style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-top: 1px solid #f1f5f9; font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem;">
                <span style="color: #64748b;">Volume Signal</span>
                <strong style="color: #4f46e5;">{vol_sig}</strong>
            </div>
            <div class="stock-card-metric-row" style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-top: 1px solid #f1f5f9; font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem;">
                <span style="color: #64748b;">Data Quality</span>
                <strong style="color: {'#d97706' if gap_stat == '🔴' else '#059669'};">{gap_stat}</strong>
            </div>
        </div>
        """
        st.markdown(clean_html(spec_html), unsafe_allow_html=True)


def render_sector_treemap(
    rank_df: pd.DataFrame,
    taxonomy_col: str = "Industry",
    return_col: str = "3M Return",
    size_by: str = "Market Cap",
) -> None:
    """Renders Finviz-style 2-Level Hierarchical Treemap Heatmap with dynamic box sizing and return colors."""
    # Degrade rather than raise when an optional column is absent: this view is
    # reachable with several taxonomies and return horizons, and a missing one
    # previously surfaced as a bare KeyError on the Sectors tab.
    required = [taxonomy_col, return_col, "Symbol"]
    missing = [c for c in required if c not in rank_df.columns]
    if missing:
        st.info(f"Treemap unavailable: missing {', '.join(missing)}.")
        return

    valid_df = rank_df.dropna(subset=required).copy()
    valid_df[taxonomy_col] = valid_df[taxonomy_col].astype(str).str.strip()
    valid_df = valid_df[
        valid_df[taxonomy_col].ne("") & valid_df[taxonomy_col].ne("nan")
    ]

    if valid_df.empty:
        st.info("Insufficient sector data for Treemap.")
        return

    # Color mapping: Cap outliers for clean color dynamic range (-30% to +30%)
    valid_df["Ret_Capped"] = valid_df[return_col].clip(lower=-0.30, upper=0.30)
    valid_df["Ret_Pct_Str"] = valid_df[return_col].map(
        lambda x: f"{x:+.1%}" if pd.notna(x) else "—"
    )

    # Dynamic Tile Sizing: Proportional to Market Cap, 3M Return, 6M Return, or Momentum
    if size_by == "3M Return":
        min_r = valid_df["3M Return"].min()
        offset = abs(min_r) + 0.10 if min_r < 0 else 0.10
        valid_df["Tile_Weight"] = ((valid_df["3M Return"] + offset) * 1000).clip(
            lower=10
        )
        size_label = "3M Return"
    elif size_by == "6M Return":
        min_r = valid_df["6M Return"].min() if "6M Return" in valid_df.columns else 0
        offset = abs(min_r) + 0.10 if min_r < 0 else 0.10
        valid_df["Tile_Weight"] = (
            (valid_df.get("6M Return", valid_df["3M Return"]) + offset) * 1000
        ).clip(lower=10)
        size_label = "6M Return"
    elif size_by == "Momentum":
        # Sized by Momentum: #1 ranked top momentum stocks get the largest tiles
        n_stocks = len(valid_df)
        if "Rank" in valid_df.columns:
            valid_df["Tile_Weight"] = (n_stocks - valid_df["Rank"] + 1).clip(lower=1)
        elif "Composite Rank" in valid_df.columns:
            valid_df["Tile_Weight"] = (n_stocks - valid_df["Composite Rank"] + 1).clip(
                lower=1
            )
        elif "Score" in valid_df.columns:
            s_min = valid_df["Score"].min()
            valid_df["Tile_Weight"] = (valid_df["Score"] - s_min + 0.5).clip(
                lower=0.1
            ) * 100
        else:
            valid_df["Tile_Weight"] = 100
        size_label = "Momentum Rank"
    else:
        # Sized by Market Cap (Default).
        # Tile AREA is the datum here, so an unknown market cap must not be
        # given a fabricated one. Substituting a flat 1000 Cr rendered such a
        # stock as a mid-size tile, and when the market-cap feed failed
        # wholesale it produced a uniformly sized map still labelled as
        # market-cap weighted. Unknown caps are excluded and disclosed.
        if "Market Cap (Cr)" not in valid_df.columns:
            st.info("Treemap unavailable: missing Market Cap (Cr).")
            return
        mcap = pd.to_numeric(valid_df["Market Cap (Cr)"], errors="coerce")
        known = mcap.notna() & (mcap > 0)
        excluded = int((~known).sum())
        valid_df = valid_df[known].copy()
        if valid_df.empty:
            st.info(
                "Market capitalisation is unavailable for these stocks, so a "
                "market-cap treemap cannot be drawn. Choose another sizing basis."
            )
            return
        if excluded:
            st.caption(
                f"{excluded} stock(s) excluded from the treemap: market "
                "capitalisation unavailable."
            )
        valid_df["Tile_Weight"] = mcap[known]
        size_label = "Market Cap (Cr)"

    groups = _build_treemap_groups(valid_df, taxonomy_col, return_col)
    html = _build_treemap_html(json.dumps(groups), return_col, size_label)
    st.iframe(html, height=700)


def _lerp_color(t: float) -> str:
    """Map t in [0, 1] to the 5-stop return heat-map color scale."""
    stops = [
        (0.00, (0xbe, 0x12, 0x3c)),
        (0.35, (0xfc, 0xa5, 0xa5)),
        (0.50, (0xf1, 0xf5, 0xf9)),
        (0.65, (0x86, 0xef, 0xac)),
        (1.00, (0x04, 0x78, 0x57)),
    ]
    t = float(np.clip(t, 0.0, 1.0))
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            r = int(round(c0[0] + f * (c1[0] - c0[0])))
            g = int(round(c0[1] + f * (c1[1] - c0[1])))
            b = int(round(c0[2] + f * (c1[2] - c0[2])))
            return f"#{r:02x}{g:02x}{b:02x}"
    c = stops[-1][1]
    return f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"


def _build_treemap_groups(
    valid_df: pd.DataFrame,
    taxonomy_col: str,
    return_col: str,
) -> list[dict]:
    """Build ECharts-compatible nested treemap data from a flat ranked DataFrame."""
    groups: list[dict] = []
    for grp_name, grp_df in valid_df.groupby(taxonomy_col, sort=False):
        children: list[dict] = []
        for _, row in grp_df.iterrows():
            ret_capped = float(row["Ret_Capped"]) if pd.notna(row.get("Ret_Capped")) else 0.0
            color = _lerp_color((ret_capped + 0.30) / 0.60)
            child: dict = {
                "name": str(row["Symbol"]),
                "value": float(row["Tile_Weight"]),
                "itemStyle": {"color": color},
                "ret_str": str(row["Ret_Pct_Str"]),
            }
            if "CMP" in valid_df.columns and pd.notna(row.get("CMP")):
                child["cmp"] = float(row["CMP"])
            if "Market Cap (Cr)" in valid_df.columns and pd.notna(row.get("Market Cap (Cr)")):
                child["mcap"] = float(row["Market Cap (Cr)"])
            if "Rank" in valid_df.columns and pd.notna(row.get("Rank")):
                child["rank"] = int(row["Rank"])
            if "3M Sharpe" in valid_df.columns and pd.notna(row.get("3M Sharpe")):
                child["sharpe"] = round(float(row["3M Sharpe"]), 2)
            children.append(child)

        grp_rets = grp_df["Ret_Capped"].dropna()
        grp_avg_ret = float(grp_rets.mean()) if not grp_rets.empty else 0.0
        groups.append({
            "name": str(grp_name),
            "value": sum(c["value"] for c in children),
            "itemStyle": {"color": _lerp_color((grp_avg_ret + 0.30) / 0.60), "opacity": 0.5},
            "n_stocks": len(children),
            "avg_ret": f"{grp_avg_ret:+.1%}",
            "children": children,
        })
    return groups


def _build_treemap_html(data_json: str, return_col: str, size_label: str) -> str:
    """Build a self-contained ECharts treemap HTML component.

    Features matching the old Plotly treemap:
    - Click a sector header → zooms into that sector (drill down)
    - Breadcrumb bar at bottom → click to navigate back
    - Rich hover tooltip: rank, return, CMP, market cap, Sharpe
    - Two-line label on tiles: ticker + return %
    """
    rc = json.dumps(return_col)
    sl = json.dumps(size_label)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:100%;height:100%;overflow:hidden;background:transparent;
  font-family:'Plus Jakarta Sans',system-ui,sans-serif}}
#chart{{width:100%;height:100%}}
</style>
</head>
<body>
<div id="chart"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/echarts/5.4.3/echarts.min.js"></script>
<script>
const DATA={data_json};
const RETURN_COL={rc};
const SIZE_LABEL={sl};
const dark=window.matchMedia&&window.matchMedia('(prefers-color-scheme:dark)').matches;
const bg=dark?'#0f172a':'#ffffff';
const fg=dark?'#e2e8f0':'#0f172a';
const bd=dark?'#334155':'#ffffff';
const chart=echarts.init(document.getElementById('chart'),null,{{renderer:'canvas',backgroundColor:bg}});
function fmt(n){{return n.toLocaleString('en-IN',{{maximumFractionDigits:0}})}}
const opt={{
  backgroundColor:bg,
  tooltip:{{
    trigger:'item',confine:true,enterable:false,
    backgroundColor:dark?'rgba(15,23,42,0.96)':'rgba(255,255,255,0.98)',
    borderColor:dark?'#334155':'#e2e8f0',
    borderWidth:1,
    textStyle:{{color:fg,fontSize:12,fontFamily:'IBM Plex Mono,monospace'}},
    formatter:function(p){{
      const d=p.data;
      if(d.children!==undefined){{
        // Sector/group tile
        let s=`<span style="font-weight:700;font-size:13px">${{d.name}}</span>`;
        s+=`<br>Avg return: <b>${{d.avg_ret||'—'}}</b>`;
        s+=`<br>Stocks: <b>${{d.n_stocks||d.children.length}}</b>`;
        s+=`<br><span style="color:#94a3b8;font-size:11px">Click to zoom into sector →</span>`;
        return s;
      }}
      // Individual stock tile
      let s=`<span style="font-weight:700;font-size:13px">${{d.name}}</span>`;
      s+=`<br>${{RETURN_COL}}: <b>${{d.ret_str||'—'}}</b>`;
      if(d.rank!=null)s+=`<br>Rank: <b>#${{d.rank}}</b>`;
      if(d.cmp!=null)s+=`<br>CMP: <b>₹${{fmt(d.cmp)}}</b>`;
      if(d.mcap!=null)s+=`<br>Mcap: <b>₹${{fmt(d.mcap)}} Cr</b>`;
      if(d.sharpe!=null)s+=`<br>3M Sharpe: <b>${{d.sharpe}}</b>`;
      s+=`<br><span style="color:#94a3b8;font-size:11px">Sized by: ${{SIZE_LABEL}}</span>`;
      return s;
    }}
  }},
  series:[{{
    type:'treemap',
    top:4,bottom:28,left:4,right:4,
    roam:false,
    nodeClick:'zoomToNode',
    zoomToNodeRatio:0.32*0.32,
    breadcrumb:{{
      show:true,
      bottom:0,
      height:24,
      emptyItemWidth:25,
      itemStyle:{{
        color:dark?'#1e293b':'#f1f5f9',
        borderColor:dark?'#334155':'#e2e8f0',
        borderWidth:1,
        shadowBlur:0,
        textStyle:{{color:fg,fontSize:11,fontFamily:'IBM Plex Mono,monospace',fontWeight:'600'}}
      }},
      emphasis:{{
        itemStyle:{{color:dark?'#334155':'#e2e8f0'}}
      }}
    }},
    levels:[
      {{
        itemStyle:{{borderColor:bd,borderWidth:3,gapWidth:3}},
        upperLabel:{{
          show:true,height:26,
          color:'#ffffff',fontSize:12,fontWeight:'bold',
          fontFamily:'IBM Plex Mono,monospace',
          padding:[4,6],
          overflow:'truncate',
          backgroundColor:'rgba(0,0,0,0.35)'
        }}
      }},
      {{
        itemStyle:{{borderColor:bd,borderWidth:1,gapWidth:1}},
        label:{{
          show:true,
          color:'#0f172a',
          fontSize:10,fontWeight:'bold',
          fontFamily:'IBM Plex Mono,monospace',
          lineOverflow:'truncate',
          formatter:function(p){{
            const d=p.data;
            // Two-line: ticker on top, return below — mirrors Plotly behavior
            return d.name+'\\n'+(d.ret_str||'');
          }},
          overflow:'truncate'
        }},
        emphasis:{{
          label:{{
            color:'#0f172a',fontSize:11,fontWeight:'bold'
          }},
          itemStyle:{{opacity:0.85}}
        }}
      }}
    ],
    data:DATA
  }}]
}};
chart.setOption(opt);
window.addEventListener('resize',()=>chart.resize());
// Double-click anywhere restores the full view (matches Plotly double-click reset)
chart.getZr().on('dblclick',function(){{
  chart.dispatchAction({{type:'treemapRootToNode',seriesIndex:0,targetNode:0}});
}});
</script>
</body>
</html>"""


def _build_rrg_html(data_json: str) -> str:
    """Build the self-contained animated Canvas RRG HTML component."""
    _CSS = """
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:transparent;height:100%;overflow:hidden}
body{font-family:'Plus Jakarta Sans',system-ui,sans-serif}
#wrap{position:relative;width:100%}
canvas{display:block;width:100%;cursor:default}
#controls{display:flex;gap:8px;align-items:center;justify-content:center;
  padding:8px 4px 2px;flex-wrap:wrap}
.ctrl-btn{background:#f1f5f9;border:1px solid #e2e8f0;border-radius:6px;
  padding:4px 14px;font-size:11.5px;cursor:pointer;color:#334155;
  font-family:inherit;transition:background .15s}
.ctrl-btn:hover{background:#e2e8f0}
.ctrl-btn.active{background:#1e40af;color:#fff;border-color:#1e40af}
#scrub{width:180px;accent-color:#2563eb;cursor:pointer}
#frame-lbl{font-size:10.5px;color:#64748b;font-family:'IBM Plex Mono',monospace;
  min-width:58px;text-align:center}
#tip{position:absolute;pointer-events:none;background:rgba(15,23,42,.92);
  color:#fff;padding:8px 11px;border-radius:8px;font-size:11px;line-height:1.65;
  display:none;z-index:10;max-width:195px;white-space:nowrap}
@media(prefers-color-scheme:dark){
  .ctrl-btn{background:#1e293b;border-color:#334155;color:#cbd5e1}
  .ctrl-btn:hover{background:#334155}
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

const canvas = document.getElementById('rrg');
const ctx    = canvas.getContext('2d');
const tip    = document.getElementById('tip');
const btnPlay = document.getElementById('btn-play');
const scrub   = document.getElementById('scrub');
const frameLbl = document.getElementById('frame-lbl');

// ── Bounds ─────────────────────────────────────────────────────────────────
const allR = DATA.sectors.flatMap(s => s.trail_r.length ? s.trail_r : [s.rs_ratio]);
const allM = DATA.sectors.flatMap(s => s.trail_m.length ? s.trail_m : [s.rs_momentum]);
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
  H = Math.min(Math.round(W * 0.62), 530);
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
function drawTicks() {
  ctx.font = '9px IBM Plex Mono,monospace';
  ctx.fillStyle = '#94a3b8';
  ctx.textAlign = 'center';
  const availW = W - PAD.l - PAD.r;
  const xStep = Math.max(2, Math.ceil((maxX - minX) / Math.floor(availW / 30)));
  for (let v = Math.ceil(minX / xStep) * xStep; v <= maxX; v += xStep) {
    const xp = tx(v);
    ctx.fillText(v.toFixed(0), xp, H - PAD.b + 14);
    ctx.beginPath();
    ctx.moveTo(xp, H - PAD.b);
    ctx.lineTo(xp, H - PAD.b + 4);
    ctx.strokeStyle = '#cbd5e1';
    ctx.lineWidth = 0.8;
    ctx.stroke();
  }
  ctx.textAlign = 'right';
  const yStep = (maxY - minY) > 8 ? 1 : 0.5;
  for (let v = Math.ceil(minY * 2) / 2; v <= maxY; v += yStep) {
    const yp = ty(v);
    ctx.fillText(v.toFixed(1), PAD.l - 6, yp + 3);
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
  const bg   = dark ? '#0f172a' : '#ffffff';
  const gridC = dark ? '#1e293b' : '#e2e8f0';
  const crossC = dark ? '#334155' : '#94a3b8';
  const textC  = dark ? '#94a3b8' : '#64748b';

  // canvas background
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  // quadrant fills
  const quads = [
    {x0:minX, x1:100, y0:100, y1:maxY, fill:'rgba(224,231,255,0.45)', lbl:'Improving', lc:'#3b82f6', ax:'left',  lxr:0.04, lyr:0.07},
    {x0:100,  x1:maxX,y0:100, y1:maxY, fill:'rgba(220,252,231,0.45)', lbl:'Leading',   lc:'#15803d', ax:'right', lxr:0.96, lyr:0.07},
    {x0:minX, x1:100, y0:minY,y1:100,  fill:'rgba(254,226,226,0.45)', lbl:'Lagging',   lc:'#dc2626', ax:'left',  lxr:0.04, lyr:0.93},
    {x0:100,  x1:maxX,y0:minY,y1:100,  fill:'rgba(254,249,195,0.45)', lbl:'Weakening', lc:'#ca8a04', ax:'right', lxr:0.96, lyr:0.93},
  ];
  for (const q of quads) {
    const px0 = tx(q.x0), py0 = ty(q.y1), px1 = tx(q.x1), py1 = ty(q.y0);
    ctx.fillStyle = q.fill;
    ctx.fillRect(px0, py0, px1 - px0, py1 - py0);
    const lx = PAD.l + q.lxr * (W - PAD.l - PAD.r);
    const ly = PAD.t + q.lyr * (H - PAD.t - PAD.b);
    ctx.font = 'bold 12.5px Plus Jakarta Sans,system-ui';
    ctx.fillStyle = q.lc;
    ctx.textAlign = q.ax;
    ctx.globalAlpha = 0.85;
    ctx.fillText(q.lbl, lx, ly);
    ctx.globalAlpha = 1;
  }

  // watermark
  ctx.font = '10.5px Plus Jakarta Sans,system-ui';
  ctx.fillStyle = textC;
  ctx.textAlign = 'center';
  ctx.globalAlpha = 0.28;
  ctx.fillText('RRG ®  Quantum Momentum', tx(100), ty(maxY - (maxY - 100) * 0.13));
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
  ctx.font = 'bold 10px Plus Jakarta Sans,system-ui';
  ctx.fillStyle = textC;
  ctx.textAlign = 'center';
  ctx.fillText('JdK RS-Ratio →', tx((minX + maxX) / 2), H - 6);
  ctx.save();
  ctx.translate(13, ty((minY + maxY) / 2));
  ctx.rotate(-Math.PI / 2);
  ctx.fillText('↑ JdK RS-Momentum', 0, 0);
  ctx.restore();

  // ── Selected sector banner ────────────────────────────────────────────────
  if (selectedSector) {
    const sel = DATA.sectors.find(s => s.industry === selectedSector);
    if (sel) {
      const hIdx = Math.max(Math.min(frame, sel.trail_r.length - 1), 0);
      const hr = sel.trail_r.length > 0 ? sel.trail_r[hIdx] : sel.rs_ratio;
      const hm = sel.trail_m.length > 0 ? sel.trail_m[hIdx] : sel.rs_momentum;
      ctx.save();
      ctx.font = 'bold 12px Plus Jakarta Sans,system-ui';
      ctx.fillStyle = sel.color;
      ctx.textAlign = 'center';
      ctx.fillText(sel.industry + '  ·  ' + sel.quadrant + '  ·  R:' + hr.toFixed(1) + '  M:' + hm.toFixed(1), W / 2, 18);
      ctx.font = '10px Plus Jakarta Sans,system-ui';
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
      ctx.font = (active && hasUserSel ? 'bold 11px' : '9px') + ' Plus Jakarta Sans,system-ui';
      ctx.fillStyle = s.color;
      ctx.textAlign = 'left';
      ctx.fillText(' ' + s.industry, hx + (hasUserSel ? 12 : 9), hy - 4);
    }

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
      '<b style="color:' + nearest.color + '">' + nearest.industry + '</b><br>' +
      'Quadrant: <b>' + nearest.quadrant + '</b><br>' +
      'RS-Ratio: <b>' + hr.toFixed(2) + '</b><br>' +
      'RS-Momentum: <b>' + hm.toFixed(2) + '</b><br>' +
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
        "#ec4899", "#2563eb", "#16a34a", "#0891b2", "#8b5cf6",
        "#d97706", "#dc2626", "#059669", "#ea580c", "#6366f1",
        "#0284c7", "#9333ea", "#64748b",
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

    payload = json.dumps({
        "sectors": sectors_data,
        "highlight": list(highlight_industries or []),
        "date": current_date_str,
    })

    st.iframe(_build_rrg_html(payload), height=700)


def _build_echarts_html(option_json: str) -> str:
    """Generic self-contained ECharts 5.4 HTML page with dark-mode awareness."""
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:100%;height:100%;overflow:hidden;background:transparent;
  font-family:'Plus Jakarta Sans',system-ui,sans-serif}}
#c{{width:100%;height:100%}}
</style>
</head>
<body>
<div id="c"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/echarts/5.4.3/echarts.min.js"></script>
<script>
(function(){{
const dark=window.matchMedia&&window.matchMedia('(prefers-color-scheme:dark)').matches;
const bg=dark?'#0f172a':'#ffffff';
const fg=dark?'#e2e8f0':'#334155';
const grid=dark?'#1e293b':'#f1f5f9';
const chart=echarts.init(document.getElementById('c'),null,{{backgroundColor:bg}});
const opt={option_json};
opt.backgroundColor=bg;
if(!opt.textStyle)opt.textStyle={{}};
opt.textStyle.color=fg;
opt.textStyle.fontFamily='Plus Jakarta Sans,system-ui,sans-serif';
if(opt.title){{
  const t=Array.isArray(opt.title)?opt.title[0]:opt.title;
  if(!t.textStyle)t.textStyle={{}};
  t.textStyle.color=fg;
}}
(opt.yAxis?[].concat(opt.yAxis):[]).forEach(a=>{{
  if(a.splitLine&&!a.splitLine.lineStyle)a.splitLine.lineStyle={{}};
  if(a.splitLine)a.splitLine.lineStyle.color=grid;
}});
chart.setOption(opt);
window.addEventListener('resize',()=>chart.resize());
}})();
</script>
</body>
</html>"""


def _ts_ms(index: pd.Index) -> list[int]:
    """Convert pandas DatetimeIndex to Unix millisecond timestamps."""
    return [int(pd.Timestamp(ts).timestamp() * 1000) for ts in index]


def render_breadth_chart(breadth_df: pd.DataFrame, ma_type: str = "SMA") -> None:
    """Renders Moving Average Breadth time series with bull/bear zones."""
    line_colors = ["#4f46e5", "#059669", "#0284c7", "#d97706", "#e11d48"]
    tms = _ts_ms(breadth_df.index)
    series: list[dict] = []
    for i, col in enumerate(breadth_df.columns):
        vals = breadth_df[col]
        data = [[tms[j], None if pd.isna(v) else round(float(v), 4)] for j, v in enumerate(vals)]
        entry: dict = {
            "name": f"Above {col}",
            "type": "line",
            "data": data,
            "lineStyle": {"color": line_colors[i % len(line_colors)], "width": 2},
            "itemStyle": {"color": line_colors[i % len(line_colors)]},
            "symbol": "none",
            "connectNulls": False,
        }
        if i == 0:
            entry["markArea"] = {
                "silent": True,
                "data": [
                    [{"yAxis": 60, "itemStyle": {"color": "rgba(5,150,105,0.05)"}}, {"yAxis": 80}],
                    [{"yAxis": 20, "itemStyle": {"color": "rgba(225,29,72,0.05)"}}, {"yAxis": 40}],
                ],
            }
            entry["markLine"] = {
                "silent": True, "symbol": ["none", "none"], "label": {"show": False},
                "data": [
                    {"yAxis": 60, "lineStyle": {"color": "#059669", "type": "dotted", "width": 1}},
                    {"yAxis": 40, "lineStyle": {"color": "#e11d48", "type": "dotted", "width": 1}},
                ],
            }
        series.append(entry)

    option = {
        "title": {"text": f"Market Breadth (% Stocks Above {ma_type})", "left": "left", "top": 5,
                  "textStyle": {"fontSize": 14, "fontWeight": "bold"}},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
        "legend": {"top": 38, "left": 0, "type": "scroll"},
        "grid": {"left": 60, "right": 20, "top": 82, "bottom": 40},
        "xAxis": {"type": "time", "splitLine": {"show": False}},
        "yAxis": {"type": "value", "min": 0, "max": 100,
                  "axisLabel": {"formatter": "{value}%"},
                  "splitLine": {"lineStyle": {"color": "#f1f5f9"}}},
        "series": series,
    }
    st.iframe(_build_echarts_html(json.dumps(option)), height=400)


def render_hl_timeseries_chart(
    hl_df: pd.DataFrame, window_label: str = "52W", is_pct: bool = True
) -> None:
    """Renders Daily New Highs / New Lows mirrored area chart."""
    h_col = "% New Highs" if is_pct else "New Highs"
    l_col = "% New Lows" if is_pct else "New Lows"
    y_suf = "%" if is_pct else ""

    tms = _ts_ms(hl_df.index)
    h_data = [[tms[j], None if pd.isna(v) else round(float(v), 4)] for j, v in enumerate(hl_df[h_col])]
    l_data = [[tms[j], None if pd.isna(v) else round(-float(v), 4)] for j, v in enumerate(hl_df[l_col])]
    y_max = float(max(hl_df[h_col].max(), hl_df[l_col].max()) * 1.15) if not hl_df.empty else 10

    option = {
        "title": {"text": f"Daily New {window_label} Highs & Lows", "left": "left", "top": 5,
                  "textStyle": {"fontSize": 14, "fontWeight": "bold"}},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
        "legend": {"top": 38, "left": 0},
        "grid": {"left": 60, "right": 20, "top": 82, "bottom": 40},
        "xAxis": {"type": "time", "splitLine": {"show": False}},
        "yAxis": {"type": "value", "min": -y_max, "max": y_max,
                  "name": "% of Universe" if is_pct else "Stock Count",
                  "axisLabel": {"formatter": "{value}" + y_suf},
                  "splitLine": {"lineStyle": {"color": "#f1f5f9"}}},
        "series": [
            {"name": f"New {window_label} Highs", "type": "line", "data": h_data,
             "lineStyle": {"color": "#059669", "width": 1.8},
             "itemStyle": {"color": "#059669"}, "symbol": "none",
             "areaStyle": {"color": "rgba(5,150,105,0.08)"}, "connectNulls": False,
             "markLine": {"silent": True, "symbol": ["none", "none"],
                          "data": [{"yAxis": 0, "lineStyle": {"color": "#94a3b8", "width": 1}}],
                          "label": {"show": False}}},
            {"name": f"New {window_label} Lows", "type": "line", "data": l_data,
             "lineStyle": {"color": "#e11d48", "width": 1.8},
             "itemStyle": {"color": "#e11d48"}, "symbol": "none",
             "areaStyle": {"color": "rgba(225,29,72,0.08)"}, "connectNulls": False},
        ],
    }
    st.iframe(_build_echarts_html(json.dumps(option)), height=370)


def render_backtest_equity_chart(equity_curve: pd.Series, benchmark: pd.Series) -> None:
    """Renders cumulative strategy returns vs benchmark."""
    strat_pct = (equity_curve - 1) * 100
    bench_pct = (benchmark - 1) * 100
    tms_s = _ts_ms(equity_curve.index)
    tms_b = _ts_ms(benchmark.index)
    s_data = [[tms_s[j], None if pd.isna(v) else round(float(v), 4)] for j, v in enumerate(strat_pct)]
    b_data = [[tms_b[j], None if pd.isna(v) else round(float(v), 4)] for j, v in enumerate(bench_pct)]

    option = {
        "title": {"text": "Cumulative Return: Strategy (Net) vs Benchmark",
                  "left": "left", "top": 5, "textStyle": {"fontSize": 14, "fontWeight": "bold"}},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
        "legend": {"top": 38, "left": 0},
        "grid": {"left": 60, "right": 20, "top": 82, "bottom": 40},
        "xAxis": {"type": "time", "splitLine": {"show": False}},
        "yAxis": {"type": "value", "name": "Return %",
                  "axisLabel": {"formatter": "{value}%"},
                  "splitLine": {"lineStyle": {"color": "#f1f5f9"}}},
        "series": [
            {"name": "Momentum Strategy (Net)", "type": "line", "data": s_data,
             "lineStyle": {"color": "#059669", "width": 2.2},
             "itemStyle": {"color": "#059669"}, "symbol": "none",
             "areaStyle": {"color": "rgba(5,150,105,0.06)"}, "connectNulls": False,
             "markLine": {"silent": True, "symbol": ["none", "none"],
                          "data": [{"yAxis": 0, "lineStyle": {"color": "#cbd5e1", "width": 1}}],
                          "label": {"show": False}}},
            {"name": "Benchmark (Nifty 500 · ^CRSLDX)", "type": "line", "data": b_data,
             "lineStyle": {"color": "#64748b", "width": 1.5, "type": "dotted"},
             "itemStyle": {"color": "#64748b"}, "symbol": "none", "connectNulls": False},
        ],
    }
    st.iframe(_build_echarts_html(json.dumps(option)), height=390)


def render_net_hl_bar_chart(net: pd.Series) -> None:
    """Renders the Daily Net New Highs (Highs − Lows) bar chart."""
    if net.empty:
        return
    tms = _ts_ms(net.index)
    data = [{"value": [tms[j], None if pd.isna(v) else float(v)],
              "itemStyle": {"color": "#059669" if pd.notna(v) and v >= 0 else "#e11d48"}}
            for j, v in enumerate(net)]
    option = {
        "title": {"text": "Daily Net New Highs (Highs − Lows)", "left": "left", "top": 5,
                  "textStyle": {"fontSize": 13, "fontWeight": "bold"}},
        "tooltip": {"trigger": "axis"},
        "grid": {"left": 55, "right": 20, "top": 50, "bottom": 40},
        "xAxis": {"type": "time", "splitLine": {"show": False}},
        "yAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "#f1f5f9"}}},
        "series": [{
            "type": "bar", "data": data,
            "markLine": {"silent": True, "symbol": ["none", "none"],
                         "data": [{"yAxis": 0, "lineStyle": {"color": "#94a3b8", "width": 1}}],
                         "label": {"show": False}},
        }],
    }
    st.iframe(_build_echarts_html(json.dumps(option)), height=300)


def render_correlation_heatmap(
    corr_df: pd.DataFrame, syms: list[str], n_disp: int
) -> None:
    """Renders a 90-day return correlation matrix heatmap via ECharts."""
    try:
        disp = list(syms[: int(n_disp)])
        sub = corr_df.loc[disp, disp]
        # Data: [x_sym, y_sym, corr_value]
        heat_data = [
            [xs, ys, None if pd.isna(sub.at[xs, ys]) else round(float(sub.at[xs, ys]), 2)]
            for xs in disp
            for ys in disp
        ]
        syms_json = json.dumps(disp)
        data_json = json.dumps(heat_data)
        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:100%;height:100%;overflow:hidden;background:transparent;
  font-family:'Plus Jakarta Sans',system-ui,sans-serif}}
#c{{width:100%;height:100%}}
</style>
</head>
<body>
<div id="c"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/echarts/5.4.3/echarts.min.js"></script>
<script>
(function(){{
const dark=window.matchMedia&&window.matchMedia('(prefers-color-scheme:dark)').matches;
const bg=dark?'#0f172a':'#ffffff';
const fg=dark?'#e2e8f0':'#334155';
const chart=echarts.init(document.getElementById('c'),null,{{backgroundColor:bg}});
const syms={syms_json};
const data={data_json};
chart.setOption({{
  backgroundColor:bg,
  textStyle:{{color:fg,fontFamily:'Plus Jakarta Sans,system-ui,sans-serif',fontSize:11}},
  tooltip:{{trigger:'item',formatter:function(p){{
    const d=p.data;
    return '<b>'+d[0]+'</b> × <b>'+d[1]+'</b><br>Corr: <b>'+(d[2]!=null?d[2].toFixed(2):'—')+'</b>';
  }}}},
  grid:{{left:60,right:70,top:20,bottom:60}},
  xAxis:{{type:'category',data:syms,splitArea:{{show:true}},
    axisLabel:{{rotate:-45,fontSize:10,color:fg,fontFamily:'JetBrains Mono,monospace'}}}},
  yAxis:{{type:'category',data:syms,inverse:true,splitArea:{{show:true}},
    axisLabel:{{fontSize:10,color:fg,fontFamily:'JetBrains Mono,monospace'}}}},
  visualMap:{{min:-0.2,max:1.0,calculable:false,orient:'vertical',right:0,top:'center',
    inRange:{{color:['#ffffff','#f0f9ff','#bae6fd','#38bdf8','#0284c7']}},
    textStyle:{{fontSize:9,color:fg}}}},
  series:[{{type:'heatmap',data:data,
    label:{{show:true,fontSize:10,color:'#0f172a',fontFamily:'JetBrains Mono,monospace',
      formatter:function(p){{return p.data[2]!=null?p.data[2].toFixed(2):'—';}}
    }}
  }}]
}});
window.addEventListener('resize',()=>chart.resize());
}})();
</script>
</body>
</html>"""
        st.iframe(html, height=420)
    except Exception:
        st.info("Unable to render correlation heatmap.")


