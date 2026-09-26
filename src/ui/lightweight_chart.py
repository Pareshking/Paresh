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

WHAT IT DRAWS FOLLOWS WHAT THE SOURCE HAS. Yahoo carries a real open, high and
low, so the price reads as candles, and the candles use the REAL open -- the
Plotly version synthesised it as the previous close, which draws bodies
spanning close-to-close, not what a candle means.

Screener carries CLOSE AND VOLUME ONLY; no intraday range exists in that source
at all. There the price reads as a single dark line. This module used to degrade
each bar to a flat close instead, which drew a column of dojis -- 250 one-pixel
dashes that read as a rendering fault rather than as a price. A line is not a
worse candle. It is the honest shape of a close-only series, and it is what the
Plotly renderer already fell back to.
"""

from __future__ import annotations

import pandas as pd

import streamlit as st

# Palette shared with the rest of the app.
UP = "#067647"
DOWN = "#B42318"
INK = "#0E1726"
GRID = "#F1F3F6"
MUTED = "#6B7482"
MA_COLOURS = {"20 EMA": "#0ea5e9", "50 EMA": "#7c3aed", "200 SMA": "#B54708"}

# Half the sessions must carry a real range before the price is drawn as
# candles. A single surviving high does not earn candle bodies for the other
# 249 sessions -- half a candle chart is the exact shape this threshold exists
# to replace.
MIN_INTRADAY_SHARE = 0.5


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


def has_intraday_range(close: pd.Series, high: pd.Series, low: pd.Series) -> bool:
    """Is there a genuine high and low to draw candles from?

    Two separate failures, and both are live in production.

    price_source returns high and low as an explicit None on the screener
    frame, and says so: "passing an explicit None is what keeps `intraday`
    honest". That is the designed signal, and the caller reads it before
    aligning anything.

    But a column can also be PRESENT AND EMPTY. Yahoo published 2026-09-18
    with all 750 volumes and not one price, so `High` existed as a full column
    of NaN -- a None check alone would have called that intraday and drawn 250
    dojis. Counting the bars is what catches it.

    The open is deliberately not part of this test: a candle is made by its
    range, and `_candles` already degrades a bar whose open is missing to a
    flat close rather than dropping the session.
    """
    rated = int(close.notna().to_numpy().sum())
    if not rated:
        return False
    usable = int((close.notna() & high.notna() & low.notna()).to_numpy().sum())
    return usable >= rated * MIN_INTRADAY_SHARE


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


def _rising(close: pd.Series, opens: pd.Series) -> pd.Series:
    """Which sessions closed up, for the volume bars.

    A candle chart compares the close to its own open. A close-only source has
    no open, so the comparison falls back to the PREVIOUS CLOSE -- the same
    question ("did it go up?") asked with what the source actually has.

    This was not cosmetic. The old test was `pd.notna(c) and pd.notna(o)`, so a
    frame with no opens at all failed it on every single session and the whole
    volume pane rendered red, on a screen whose price had risen fourfold.

    The first bar has no predecessor and no open; it is drawn as rising rather
    than inventing a fall.
    """
    basis = opens.where(opens.notna(), close.shift(1)).fillna(close)
    return close >= basis


def _volume(idx, vol, rising) -> list[dict]:
    rows = []
    for t, v, up in zip(_times(idx), vol, rising):
        if pd.isna(v) or float(v) <= 0:
            continue
        rows.append({
            "time": t,
            "value": float(v),
            "color": "rgba(5,150,105,0.5)" if bool(up) else "rgba(225,29,72,0.4)",
        })
    return rows


def _base_chart(height: int) -> dict:
    return {
        "height": height,
        "layout": {
            "background": {"type": "solid", "color": "#ffffff"},
            "textColor": "#3C4657",
            "fontFamily": "Geist Mono, monospace",
        },
        "grid": {
            "vertLines": {"color": GRID},
            "horzLines": {"color": GRID},
        },
        "rightPriceScale": {"borderColor": "#E3E6EB"},
        "timeScale": {"borderColor": "#E3E6EB", "timeVisible": False},
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

    Candles when the source carries a real intraday range, a dark close line
    when it does not. Raises ChartUnavailable when the component is missing or
    the data cannot make a chart, so the caller can fall back to Plotly.
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

    # An explicit None is the source saying it has no intraday data; an all-NaN
    # column is a source that stalled. Neither can be drawn as a candle.
    intraday = (
        high is not None
        and low is not None
        and has_intraday_range(close, h, l)
    )

    if intraday:
        price = _candles(idx, o.values, h.values, l.values, close.values)
        if not price:
            raise ChartUnavailable("no candle rows")
        price_series = {
            "type": "Candlestick",
            "data": price,
            "options": {
                "upColor": UP, "downColor": DOWN,
                "borderUpColor": UP, "borderDownColor": DOWN,
                "wickUpColor": UP, "wickDownColor": DOWN,
            },
        }
    else:
        price = _series(idx, close.values)
        if not price:
            raise ChartUnavailable("no close rows")
        price_series = {
            "type": "Line",
            "data": price,
            # Black, and heavier than the overlays. The price is the subject;
            # the moving averages are commentary, and it has to stay readable
            # with two of them crossing it. It does NOT change colour with the
            # session: without an open there is no up or down bar to colour,
            # and a line that switched would assert something the source does
            # not carry.
            "options": {
                "color": INK,
                "lineWidth": 2,
                "priceLineVisible": True,
                "lastValueVisible": True,
                "crosshairMarkerVisible": True,
            },
        }

    series: list[dict] = [price_series]

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

    vol_rows = _volume(idx, _align(volume).values, _rising(close, o).values)
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
            "borderColor": "#E3E6EB",
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
