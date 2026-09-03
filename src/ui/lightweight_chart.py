"""TradingView Lightweight Charts renderer for the stock page.

Why this and not Plotly: Plotly's interaction model is built for analysis
notebooks -- drag selects a box, and on a touch screen that means reading the
chart rearranges it. Lightweight Charts is built for price series, so drag pans,
pinch zooms, and the crosshair is the reading tool. It is also what most broker
terminals use, so the behaviour is already familiar.

It is a THIRD-PARTY COMPONENT, which is a real risk on Streamlit Cloud: a
component that fails to load renders as a blank space, not an error. So the
caller keeps the Plotly renderer and falls back to it whenever this module
cannot produce a chart. A prettier chart is not worth an empty one.

Candles use the REAL open. The Plotly version synthesised it as the previous
close, which draws bodies spanning close-to-close -- not what a candle means.
"""

from __future__ import annotations

import pandas as pd

import streamlit as st

# Palette shared with the rest of the app.
UP = "#059669"
DOWN = "#e11d48"
INK = "#0f172a"
GRID = "#f1f5f9"
MUTED = "#94a3b8"
MA_COLOURS = {"20 EMA": "#0ea5e9", "50 EMA": "#7c3aed", "200 SMA": "#d97706"}


class ChartUnavailable(RuntimeError):
    """The component could not be used; the caller should fall back."""


def _times(index: pd.DatetimeIndex) -> list[str]:
    return [pd.Timestamp(t).strftime("%Y-%m-%d") for t in index]


def _series(index: pd.DatetimeIndex, values) -> list[dict]:
    out = []
    for t, v in zip(_times(index), values):
        if pd.notna(v):
            out.append({"time": t, "value": float(v)})
    return out


def _candles(idx, o, h, l, c) -> list[dict]:
    rows = []
    for t, ov, hv, lv, cv in zip(_times(idx), o, h, l, c):
        if pd.isna(cv):
            continue
        # A missing open/high/low degrades that bar to a flat close rather than
        # dropping the session out of the series entirely.
        ov = float(ov) if pd.notna(ov) else float(cv)
        hv = float(hv) if pd.notna(hv) else max(ov, float(cv))
        lv = float(lv) if pd.notna(lv) else min(ov, float(cv))
        rows.append({"time": t, "open": ov, "high": hv, "low": lv, "close": float(cv)})
    return rows


def _volume(idx, vol, closes, opens) -> list[dict]:
    rows = []
    for t, v, c, o in zip(_times(idx), vol, closes, opens):
        if pd.isna(v) or float(v) <= 0:
            continue
        rising = pd.notna(c) and pd.notna(o) and float(c) >= float(o)
        rows.append({
            "time": t,
            "value": float(v),
            "color": "rgba(5,150,105,0.5)" if rising else "rgba(225,29,72,0.4)",
        })
    return rows


def _base_chart(height: int) -> dict:
    return {
        "height": height,
        "layout": {
            "background": {"type": "solid", "color": "#ffffff"},
            "textColor": "#475569",
            "fontFamily": "IBM Plex Mono, monospace",
        },
        "grid": {
            "vertLines": {"color": GRID},
            "horzLines": {"color": GRID},
        },
        "rightPriceScale": {"borderColor": "#e2e8f0"},
        "timeScale": {"borderColor": "#e2e8f0", "timeVisible": False},
        "crosshair": {"mode": 1},
    }


def render_lightweight_chart(
    symbol: str,
    close: pd.Series,
    *,
    open_: pd.Series | None = None,
    high: pd.Series | None = None,
    low: pd.Series | None = None,
    volume: pd.Series | None = None,
    overlays: dict[str, pd.Series] | None = None,
    rs: pd.Series | None = None,
    height: int = 420,
) -> None:
    """Render price (+ overlays, volume) and a Relative Strength pane beneath it.

    Raises ChartUnavailable when the component is missing or the data cannot
    make a chart, so the caller can fall back to Plotly.
    """
    try:
        from streamlit_lightweight_charts import renderLightweightCharts
    except Exception as exc:  # pragma: no cover - import guard
        raise ChartUnavailable(f"component unavailable: {exc}") from exc

    close = close.dropna()
    if close.empty:
        raise ChartUnavailable("no close prices")

    idx = close.index

    def _align(s: pd.Series | None) -> pd.Series:
        if s is None:
            return pd.Series(index=idx, dtype=float)
        return s.reindex(idx)

    o, h, l = _align(open_), _align(high), _align(low)
    candles = _candles(idx, o.values, h.values, l.values, close.values)
    if not candles:
        raise ChartUnavailable("no candle rows")

    series: list[dict] = [{
        "type": "Candlestick",
        "data": candles,
        "options": {
            "upColor": UP, "downColor": DOWN,
            "borderUpColor": UP, "borderDownColor": DOWN,
            "wickUpColor": UP, "wickDownColor": DOWN,
        },
    }]

    for name, values in (overlays or {}).items():
        data = _series(idx, _align(values).values)
        if data:
            series.append({
                "type": "Line",
                "data": data,
                "options": {
                    "color": MA_COLOURS.get(name, MUTED),
                    "lineWidth": 2,
                    "priceLineVisible": False,
                    "lastValueVisible": False,
                    "title": name,
                },
            })

    vol_rows = _volume(idx, _align(volume).values, close.values, o.values)
    if vol_rows:
        # Volume shares the price pane on its own hidden scale, pinned to the
        # bottom fifth -- the standard terminal layout, and it keeps the price
        # scale from being squashed by share counts.
        series.append({
            "type": "Histogram",
            "data": vol_rows,
            "options": {
                "priceFormat": {"type": "volume"},
                "priceScaleId": "volume",
                "lastValueVisible": False,
                "priceLineVisible": False,
            },
            "priceScale": {
                "scaleMargins": {"top": 0.8, "bottom": 0.0},
                "visible": False,
            },
        })

    charts = [{"chart": _base_chart(height), "series": series}]

    rs_rows = _series(idx, _align(rs).values) if rs is not None else []
    if rs_rows:
        rs_chart = _base_chart(120)
        rs_chart["rightPriceScale"] = {
            "borderColor": "#e2e8f0",
            "autoScale": True,
            "scaleMargins": {"top": 0.1, "bottom": 0.1},
        }
        charts.append({
            "chart": rs_chart,
            "series": [{
                "type": "Line",
                "data": rs_rows,
                "options": {
                    "color": "#7c3aed", "lineWidth": 2,
                    "priceLineVisible": False,
                    "title": "RS vs Nifty 500",
                    "lastValueVisible": True,
                },
            }],
        })

    try:
        renderLightweightCharts(charts, key=f"lw_{symbol}")
    except Exception as exc:
        raise ChartUnavailable(f"render failed: {exc}") from exc

    if not vol_rows:
        st.caption("Volume unavailable for this symbol.")
