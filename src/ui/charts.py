"""
Light-themed interactive Plotly visualizations for NSE Momentum Dashboard.
Includes Candlestick + Volume + RSI, Chandelier Exits, RRG with trails, and Sector Treemaps.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

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


def render_candlestick_drilldown(
    symbol: str,
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
    high_prices: pd.DataFrame | None = None,
    low_prices: pd.DataFrame | None = None,
    volume_data: pd.DataFrame | None = None,
) -> None:
    """Renders single-stock technical terminal with Candlestick, Chandelier Stops, Volume, and RSI (14)."""
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
    st.markdown(clean_html(header_html), unsafe_allow_html=True)

    # 4 KPI metric cards row
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("3M Sharpe Ratio", f"{row_s.get('3M Sharpe', 0):.2f}")
    k2.metric("6M Return", f"{ret_6m:.1%}")
    k3.metric("ATR Volatility %", f"{row_s.get('ATR %', 0):.1f}%")
    k4.metric("Market Cap", f"₹{row_s.get('Market Cap (Cr)', 0):,.0f} Cr")

    # Timeframe selection pills
    c_tf, _ = st.columns([1.5, 3], vertical_alignment="center")
    tf_choice = c_tf.segmented_control(
        "Timeframe",
        ["1M", "3M", "6M", "1Y", "All"],
        default="6M",
        key=f"tf_choice_{symbol}",
        label_visibility="collapsed",
    )
    if not tf_choice:
        tf_choice = "6M"

    tf_days_map = {"1M": 22, "3M": 64, "6M": 126, "1Y": 252, "All": 500}
    _n_days = tf_days_map.get(tf_choice, 126)

    _close = adj_close[symbol].dropna().iloc[-_n_days:]
    _has_ohlc = (
        high_prices is not None
        and symbol in high_prices.columns
        and low_prices is not None
        and symbol in low_prices.columns
    )

    c_chart, c_spec = st.columns([2.6, 1.1])

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
                    line={"color": "#059669", "width": 2},
                    fill="tozeroy",
                    fillcolor="rgba(5, 150, 105, 0.05)",
                    name="Close",
                ),
                row=1,
                col=1,
            )

        # 50 EMA & 200 SMA
        if len(_close) >= 20:
            ema50 = _close.ewm(span=50).mean()
            fig.add_trace(
                go.Scatter(
                    x=ema50.index,
                    y=ema50.values,
                    mode="lines",
                    line={"color": "#4f46e5", "width": 1.2, "dash": "dot"},
                    name="50 EMA",
                ),
                row=1,
                col=1,
            )
        if len(_close) >= 50:
            sma200 = _close.rolling(200, min_periods=30).mean()
            fig.add_trace(
                go.Scatter(
                    x=sma200.index,
                    y=sma200.values,
                    mode="lines",
                    line={"color": "#d97706", "width": 1.2, "dash": "dash"},
                    name="200 SMA",
                ),
                row=1,
                col=1,
            )

        # Chandelier & ATR Trailing Stops
        _sl = row_s.get("Stop Loss", None)
        _ch = row_s.get("Chand Exit", None)
        if _ch and pd.notna(_ch) and _ch > 0:
            fig.add_hline(
                y=_ch,
                line_color="#d97706",
                line_dash="dot",
                line_width=1,
                annotation_text=f"Chandelier Exit ₹{_ch:.0f}",
                annotation_position="top right",
                annotation_font_color="#d97706",
                annotation_font_size=9,
                row=1,
                col=1,
            )
        if _sl and pd.notna(_sl) and _sl > 0:
            fig.add_hline(
                y=_sl,
                line_color="#e11d48",
                line_dash="dash",
                line_width=1,
                annotation_text=f"2×ATR Stop ₹{_sl:.0f}",
                annotation_position="bottom right",
                annotation_font_color="#e11d48",
                annotation_font_size=9,
                row=1,
                col=1,
            )

        # 2. Volume Subplot
        if volume_data is not None and symbol in volume_data.columns:
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
            yaxis2={"title": "Volume", "gridcolor": "#f1f5f9", "zeroline": False},
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
        )
        fig.update_xaxes(gridcolor="#f1f5f9")
        st.plotly_chart(fig, width="stretch", key=f"drill_chart_{symbol}")

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
    valid_df = rank_df.dropna(subset=[taxonomy_col, return_col, "Symbol"]).copy()
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
        # Sized by Market Cap (Default)
        valid_df["Tile_Weight"] = (
            valid_df["Market Cap (Cr)"].fillna(1000).clip(lower=100)
        )
        size_label = "Market Cap (Cr)"

    # Hierarchical Finviz-style Treemap
    fig = px.treemap(
        valid_df,
        path=[taxonomy_col, "Symbol"],
        values="Tile_Weight",
        color="Ret_Capped",
        color_continuous_scale=[
            (0.00, "#be123c"),  # Deep Crimson
            (0.35, "#fca5a5"),  # Soft Red
            (0.50, "#f1f5f9"),  # Neutral Gray
            (0.65, "#86efac"),  # Soft Mint Green
            (1.00, "#047857"),  # Deep Forest Emerald
        ],
        color_continuous_midpoint=0.0,
        hover_data={
            "Symbol": True,
            "CMP": ":,.0f",
            return_col: ":.1%",
            "Market Cap (Cr)": ":,.0f",
            "Ret_Capped": False,
            "Tile_Weight": False,
        },
    )

    fig.update_traces(
        textinfo="label+text",
        texttemplate="<b>%{label}</b><br>%{customdata[2]:.1%}",
        textfont={"family": "IBM Plex Mono, monospace", "size": 11, "color": "#0f172a"},
        marker={
            "cornerradius": 4,
            "pad": {"t": 24, "l": 4, "r": 4, "b": 4},
            "line": {"width": 1.5, "color": "#ffffff"},
        },
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Parent Group: %{parent}<br>"
            "CMP: ₹%{customdata[1]:,.0f}<br>"
            f"{return_col}: %{{customdata[2]:+.1%}}<br>"
            "Market Cap: ₹%{customdata[3]:,.0f} Cr<br>"
            f"<b>Sized by:</b> {size_label}<extra></extra>"
        ),
    )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        margin={"l": 4, "r": 4, "t": 4, "b": 4},
        height=680,
        coloraxis_colorbar={
            "title": {
                "text": f"{return_col}",
                "font": {"family": "IBM Plex Mono", "size": 10, "color": "#475569"},
            },
            "tickformat": "+.0%",
            "thickness": 12,
            "len": 0.7,
            "tickfont": {"family": "IBM Plex Mono", "size": 9},
        },
        font={
            "family": "Plus Jakarta Sans, sans-serif",
            "size": 11,
            "color": "#0f172a",
        },
    )
    st.plotly_chart(
        fig, width="stretch", key=f"sector_treemap_{taxonomy_col}_{size_by}"
    )


def render_rrg_chart(
    rrg_df: pd.DataFrame,
    highlight_industries: list[str] | None = None,
    current_date_str: str = "",
) -> None:
    """Renders Sharpely / Bloomberg-grade Relative Rotation Graph (RRG) with pastel quadrants and smooth spline trails."""
    if rrg_df.empty:
        st.info("Not enough historical data to compute Relative Rotation Graph.")
        return

    # Extract dynamic bounds to ensure background rectangles fill 100% of data area
    all_r = [float(x) for x in rrg_df["RS_Ratio"].dropna().tolist()]
    t_r_col = (
        rrg_df["Trail_R"] if "Trail_R" in rrg_df.columns else rrg_df.get("trail_r", [])
    )
    for trails in t_r_col:
        if isinstance(trails, (list, np.ndarray)):
            all_r.extend([float(x) for x in trails])

    all_m = [float(x) for x in rrg_df["RS_Momentum"].dropna().tolist()]
    t_m_col = (
        rrg_df["Trail_M"] if "Trail_M" in rrg_df.columns else rrg_df.get("trail_m", [])
    )
    for trails in t_m_col:
        if isinstance(trails, (list, np.ndarray)):
            all_m.extend([float(x) for x in trails])

    min_x = min(88.0, (min(all_r) - 2.0) if all_r else 90.0)
    max_x = max(112.0, (max(all_r) + 2.0) if all_r else 110.0)
    min_y = min(96.0, (min(all_m) - 1.5) if all_m else 97.0)
    max_y = max(105.0, (max(all_m) + 1.5) if all_m else 104.5)

    # Sharpely-grade Distinct Vibrant Sector Palette
    VIBRANT_PALETTE = [
        "#ec4899",  # Vivid Pink / Magenta (like NIFTYIT)
        "#2563eb",  # Royal Blue (like NIFTYBANK)
        "#16a34a",  # Fresh Grass Green (like NIFTYFMCG)
        "#0891b2",  # Vivid Cyan / Teal (like NIFTYPHARMA)
        "#8b5cf6",  # Electric Violet
        "#d97706",  # Warm Amber
        "#dc2626",  # Bright Crimson Red
        "#059669",  # Emerald
        "#ea580c",  # Deep Orange
        "#6366f1",  # Indigo
        "#0284c7",  # Sky Blue
        "#9333ea",  # Purple
        "#64748b",  # Slate Blue
    ]

    has_filter = highlight_industries is not None and len(highlight_industries) > 0

    fig = go.Figure()

    # ── 1. Sharpely Pastel Quadrant Shading ──────────────────────────────────
    # Top-Left: Improving (Soft Lavender-Blue)
    fig.add_shape(
        type="rect",
        x0=min_x,
        x1=100,
        y0=100,
        y1=max_y,
        fillcolor="rgba(224, 231, 255, 0.45)",
        line_width=0,
        layer="below",
    )
    # Top-Right: Leading (Soft Mint Green)
    fig.add_shape(
        type="rect",
        x0=100,
        x1=max_x,
        y0=100,
        y1=max_y,
        fillcolor="rgba(220, 252, 231, 0.45)",
        line_width=0,
        layer="below",
    )
    # Bottom-Left: Lagging (Soft Peach-Pink)
    fig.add_shape(
        type="rect",
        x0=min_x,
        x1=100,
        y0=min_y,
        y1=100,
        fillcolor="rgba(254, 226, 226, 0.45)",
        line_width=0,
        layer="below",
    )
    # Bottom-Right: Weakening (Soft Pale Yellow)
    fig.add_shape(
        type="rect",
        x0=100,
        x1=max_x,
        y0=min_y,
        y1=100,
        fillcolor="rgba(254, 249, 195, 0.45)",
        line_width=0,
        layer="below",
    )

    # ── 2. Sharpely Quadrant Watermark Annotations ───────────────────────────
    # Improving (Top-Left)
    fig.add_annotation(
        x=min_x + (100 - min_x) * 0.05,
        y=max_y - (max_y - 100) * 0.06,
        text="<b>Improving</b>",
        showarrow=False,
        xanchor="left",
        yanchor="top",
        font={
            "size": 14,
            "color": "#3b82f6",
            "family": "Plus Jakarta Sans, sans-serif",
        },
        opacity=0.9,
    )
    # Leading (Top-Right)
    fig.add_annotation(
        x=max_x - (max_x - 100) * 0.05,
        y=max_y - (max_y - 100) * 0.06,
        text="<b>Leading</b>",
        showarrow=False,
        xanchor="right",
        yanchor="top",
        font={
            "size": 14,
            "color": "#15803d",
            "family": "Plus Jakarta Sans, sans-serif",
        },
        opacity=0.9,
    )
    # Lagging (Bottom-Left)
    fig.add_annotation(
        x=min_x + (100 - min_x) * 0.05,
        y=min_y + (100 - min_y) * 0.06,
        text="<b>Lagging</b>",
        showarrow=False,
        xanchor="left",
        yanchor="bottom",
        font={
            "size": 14,
            "color": "#dc2626",
            "family": "Plus Jakarta Sans, sans-serif",
        },
        opacity=0.9,
    )
    # Weakening (Bottom-Right)
    fig.add_annotation(
        x=max_x - (max_x - 100) * 0.05,
        y=min_y + (100 - min_y) * 0.06,
        text="<b>Weakening</b>",
        showarrow=False,
        xanchor="right",
        yanchor="bottom",
        font={
            "size": 14,
            "color": "#ca8a04",
            "family": "Plus Jakarta Sans, sans-serif",
        },
        opacity=0.9,
    )

    # Central Watermark Brand Tag
    fig.add_annotation(
        x=100,
        y=max_y - (max_y - 100) * 0.12,
        text="<b>RRG ® Powered by Quantum Momentum</b>",
        showarrow=False,
        xanchor="center",
        yanchor="middle",
        font={
            "size": 12,
            "color": "#94a3b8",
            "family": "Plus Jakarta Sans, sans-serif",
        },
        opacity=0.35,
    )

    # ── 3. Reference Crosshairs (100, 100) ───────────────────────────────────
    fig.add_hline(y=100, line_color="#94a3b8", line_width=1.5)
    fig.add_vline(x=100, line_color="#94a3b8", line_width=1.5)

    # ── 4. Unselected Sectors (Faint ghost trails when filtered) ─────────────
    # ── 4. Unselected Sectors (Faint ghost trails when filtered) ─────────────
    if has_filter:
        for _, row in rrg_df.iterrows():
            if row["Industry"] in highlight_industries:
                continue
            t_r = row.get("Trail_R") if "Trail_R" in row else row.get("trail_r", [])
            t_m = row.get("Trail_M") if "Trail_M" in row else row.get("trail_m", [])
            if t_r and t_m and len(t_r) > 1:
                fig.add_trace(
                    go.Scatter(
                        x=t_r,
                        y=t_m,
                        mode="lines",
                        line={
                            "color": "#cbd5e1",
                            "width": 1,
                            "shape": "spline",
                            "smoothing": 1.3,
                        },
                        opacity=0.25,
                        showlegend=False,
                        hoverinfo="skip",
                    )
                )
            fig.add_trace(
                go.Scatter(
                    x=[row["RS_Ratio"]],
                    y=[row["RS_Momentum"]],
                    mode="markers",
                    marker={"size": 4, "color": "#cbd5e1", "opacity": 0.3},
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

    # ── 5. Active Highlighted Sectors (Smooth Spline Trails & Circular Dots) ──
    for idx, (_, row) in enumerate(rrg_df.iterrows()):
        is_highlighted = not has_filter or row["Industry"] in highlight_industries
        if has_filter and not is_highlighted:
            continue

        sec_clr = VIBRANT_PALETTE[idx % len(VIBRANT_PALETTE)]
        trail_r = row.get("Trail_R") if "Trail_R" in row else row.get("trail_r", [])
        trail_m = row.get("Trail_M") if "Trail_M" in row else row.get("trail_m", [])

        # Plot smooth spline rotation trail with historical dots
        if trail_r and trail_m and len(trail_r) > 1 and len(trail_m) > 1:
            fig.add_trace(
                go.Scatter(
                    x=trail_r,
                    y=trail_m,
                    mode="lines+markers",
                    line={
                        "color": sec_clr,
                        "width": 2.5,
                        "shape": "spline",
                        "smoothing": 1.3,
                    },
                    marker={"size": 6, "color": sec_clr, "symbol": "circle"},
                    opacity=0.90,
                    showlegend=False,
                    hovertemplate=(
                        f"<b>{row['Industry']} Trail</b><br>"
                        "RS-Ratio: %{x:.2f}<br>"
                        "RS-Momentum: %{y:.2f}<extra></extra>"
                    ),
                )
            )

        # Plot prominent solid head marker with label right above/beside
        fig.add_trace(
            go.Scatter(
                x=[row["RS_Ratio"]],
                y=[row["RS_Momentum"]],
                mode="markers+text",
                marker={
                    "size": 12,
                    "color": sec_clr,
                    "line": {"width": 2, "color": "#ffffff"},
                },
                text=[f" <b>{row['Industry']}</b>"],
                textposition="top center",
                textfont={
                    "size": 10.5,
                    "color": sec_clr,
                    "family": "Plus Jakarta Sans, sans-serif",
                },
                name=f"{row['Industry']}",
                showlegend=True,
                hovertemplate=(
                    f"<b style='font-size:13px; color:{sec_clr};'>{row['Industry']}</b><br>"
                    f"Quadrant: <b>{row['Quadrant']}</b><br>"
                    f"JdK RS-Ratio: <b>{row['RS_Ratio']:.2f}</b><br>"
                    f"JdK RS-Momentum: <b>{row['RS_Momentum']:.2f}</b><br>"
                    f"Stocks: <b>{row['Stocks']}</b><extra></extra>"
                ),
            )
        )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={
            "family": "Plus Jakarta Sans, sans-serif",
            "size": 11,
            "color": "#334155",
        },
        xaxis={
            "title": "<b>JdK RS-Ratio</b>",
            "range": [min_x, max_x],
            "gridcolor": "#e2e8f0",
            "zeroline": False,
            "dtick": 1.0,
            "tickangle": -45,
            "tickfont": {"family": "IBM Plex Mono", "size": 9.5, "color": "#64748b"},
        },
        yaxis={
            "title": "<b>JdK RS-Momentum</b>",
            "range": [min_y, max_y],
            "gridcolor": "#e2e8f0",
            "zeroline": False,
            "dtick": 0.5,
            "tickfont": {"family": "IBM Plex Mono", "size": 9.5, "color": "#64748b"},
        },
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.22,
            "xanchor": "center",
            "x": 0.5,
            "font": {"family": "IBM Plex Mono", "size": 10, "color": "#334155"},
        },
        height=640,
        margin={"l": 45, "r": 45, "t": 25, "b": 65},
        hovermode="closest",
    )
    st.plotly_chart(fig, width="stretch", key=f"sharpely_rrg_chart_{current_date_str}")


def render_breadth_chart(breadth_df: pd.DataFrame, ma_type: str = "SMA") -> None:
    """Renders Moving Average Breadth time series with bull/bear zones."""
    fig = go.Figure()
    line_colors = ["#4f46e5", "#059669", "#0284c7", "#d97706", "#e11d48"]

    for i, col in enumerate(breadth_df.columns):
        fig.add_trace(
            go.Scatter(
                x=breadth_df.index,
                y=breadth_df[col],
                name=f"Above {col}",
                mode="lines",
                line={"color": line_colors[i % len(line_colors)], "width": 2},
            )
        )

    fig.add_hrect(y0=60, y1=80, fillcolor="rgba(5, 150, 105, 0.05)", line_width=0)
    fig.add_hrect(y0=20, y1=40, fillcolor="rgba(225, 29, 72, 0.05)", line_width=0)
    fig.add_hline(
        y=60, line_color="#059669", line_dash="dot", line_width=1, opacity=0.7
    )
    fig.add_hline(
        y=40, line_color="#e11d48", line_dash="dot", line_width=1, opacity=0.7
    )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={
            "family": "Plus Jakarta Sans, sans-serif",
            "size": 11,
            "color": "#334155",
        },
        title={
            "text": f"<b>Market Breadth (% Stocks Above {ma_type})</b>",
            "font": {"size": 14, "color": "#0f172a"},
        },
        yaxis={
            "title": "% Stocks Above MA",
            "range": [0, 100],
            "gridcolor": "#f1f5f9",
            "ticksuffix": "%",
        },
        xaxis={"gridcolor": "#f1f5f9"},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "bgcolor": "rgba(255, 255, 255, 0.9)",
            "bordercolor": "#e2e8f0",
        },
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
        height=360,
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch", key="breadth_chart_view")


def render_hl_timeseries_chart(
    hl_df: pd.DataFrame, window_label: str = "52W", is_pct: bool = True
) -> None:
    """Renders Daily New Highs / New Lows area charts."""
    h_col = "% New Highs" if is_pct else "New Highs"
    l_col = "% New Lows" if is_pct else "New Lows"
    y_suf = "%" if is_pct else ""

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=hl_df.index,
            y=hl_df[h_col],
            name=f"New {window_label} Highs",
            mode="lines",
            line={"color": "#059669", "width": 1.8},
            fill="tozeroy",
            fillcolor="rgba(5, 150, 105, 0.08)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=hl_df.index,
            y=-hl_df[l_col],
            name=f"New {window_label} Lows",
            mode="lines",
            line={"color": "#e11d48", "width": 1.8},
            fill="tozeroy",
            fillcolor="rgba(225, 29, 72, 0.08)",
        )
    )
    fig.add_hline(y=0, line_color="#94a3b8", line_width=1)

    y_max = (
        max(hl_df[h_col].max(), hl_df[l_col].max()) * 1.15 if not hl_df.empty else 10
    )
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={
            "family": "Plus Jakarta Sans, sans-serif",
            "size": 11,
            "color": "#334155",
        },
        title={
            "text": f"<b>Daily New {window_label} Highs & Lows</b>",
            "font": {"size": 14, "color": "#0f172a"},
        },
        yaxis={
            "title": "% of Universe" if is_pct else "Stock Count",
            "gridcolor": "#f1f5f9",
            "ticksuffix": y_suf,
            "range": [-y_max, y_max],
        },
        xaxis={"gridcolor": "#f1f5f9"},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "bgcolor": "rgba(255, 255, 255, 0.9)",
            "bordercolor": "#e2e8f0",
        },
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
        height=340,
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch", key="hl_chart_view")


def render_backtest_equity_chart(equity_curve: pd.Series, benchmark: pd.Series) -> None:
    """Renders cumulative strategy returns vs benchmark."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=equity_curve.index,
            y=(equity_curve - 1) * 100,
            name="Momentum Strategy (Net)",
            mode="lines",
            line={"color": "#059669", "width": 2.2},
            fill="tozeroy",
            fillcolor="rgba(5, 150, 105, 0.06)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=benchmark.index,
            y=(benchmark - 1) * 100,
            name="Benchmark (Equal-Weight Universe)",
            mode="lines",
            line={"color": "#64748b", "width": 1.5, "dash": "dot"},
        )
    )
    fig.add_hline(y=0, line_color="#cbd5e1", line_width=1)

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={
            "family": "Plus Jakarta Sans, sans-serif",
            "size": 11,
            "color": "#334155",
        },
        title={
            "text": "<b>Cumulative Return: Strategy (Net) vs Benchmark</b>",
            "font": {"size": 14, "color": "#0f172a"},
        },
        yaxis={"title": "Return %", "gridcolor": "#f1f5f9", "ticksuffix": "%"},
        xaxis={"gridcolor": "#f1f5f9"},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "bgcolor": "rgba(255, 255, 255, 0.9)",
            "bordercolor": "#e2e8f0",
        },
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
        height=360,
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch", key="backtest_equity_chart_view")


def render_multi_strategy_growth_chart(strat_curves: dict[str, pd.Series]) -> None:
    """Renders comparative 6M/12M cumulative growth curves for all momentum models."""
    fig = go.Figure()
    palette = {
        "🎯 Consensus Model": ("#059669", 2.8, "solid"),
        "🔬 Residual (α) Momentum": ("#4f46e5", 1.8, "solid"),
        "🏭 Industry-Relative": ("#0284c7", 1.8, "solid"),
        "⚡ Momentum Acceleration": ("#d97706", 1.8, "solid"),
        "📊 Composite Multi-Window": ("#8b5cf6", 1.8, "solid"),
        "🏛️ Benchmark (Nifty 500)": ("#64748b", 1.5, "dash"),
    }

    for name, s_curve in strat_curves.items():
        if s_curve is None or s_curve.empty:
            continue
        clr, width, dash = palette.get(name, ("#64748b", 1.5, "solid"))
        fig.add_trace(
            go.Scatter(
                x=s_curve.index,
                y=(s_curve - 1) * 100,
                name=name,
                mode="lines",
                line={"color": clr, "width": width, "dash": dash},
                hovertemplate=f"<b>{name}</b>: %{{y:+.2f}}%<extra></extra>",
            )
        )

    fig.add_hline(y=0, line_color="#cbd5e1", line_width=1)

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={
            "family": "Plus Jakarta Sans, sans-serif",
            "size": 11,
            "color": "#334155",
        },
        title={
            "text": "<b>6-Month Cumulative Growth: Strategy Engines vs Benchmark</b>",
            "font": {"size": 14, "color": "#0f172a"},
        },
        yaxis={
            "title": "Cumulative Return %",
            "gridcolor": "#f1f5f9",
            "ticksuffix": "%",
        },
        xaxis={"gridcolor": "#f1f5f9"},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "bgcolor": "rgba(255, 255, 255, 0.9)",
            "bordercolor": "#e2e8f0",
        },
        margin={"l": 10, "r": 10, "t": 55, "b": 10},
        height=380,
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch", key="multi_strat_growth_chart")
