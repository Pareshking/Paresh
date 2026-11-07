"""Stock page chart: panes for price (candles or line), overlays, volume and RS.

TradingView Lightweight Charts (src/ui/lw_chart.py, library inlined, no third-party
component): drag pans, pinch zooms, and the crosshair is the reading tool, with a
legend that shows every series' value under the pointer.

WHAT IT DRAWS FOLLOWS WHAT THE SOURCE HAS. Yahoo carries a real open, high and
low, so the price reads as candles, and the candles use the REAL open -- the
earlier versions synthesised it as the previous close, which draws bodies
spanning close-to-close, not what a candle means.

Screener carries CLOSE AND VOLUME ONLY; no intraday range exists in that source
at all. There the price reads as a single dark line. This module used to degrade
each bar to a flat close instead, which drew a column of dojis -- 250 one-pixel
dashes that read as a rendering fault rather than as a price. A line is not a
worse candle. It is the honest shape of a close-only series, and it is what the
app always drew for a close-only source.
"""

from __future__ import annotations

from src.ui.tokens import C

import pandas as pd

import streamlit as st

from src.ui import lw_chart

# Palette shared with the rest of the app.
UP = C.up
DOWN = C.down
INK = C.ink
GRID = C.grid
MUTED = C.muted
MA_COLOURS = {"20 EMA": C.teal, "50 EMA": C.muted_2, "200 SMA": C.caution, "Nifty 500": C.violet}
# Volume is context, not a signal: pale tints of the up and down colours.
VOL_UP, VOL_DOWN = C.up_line, C.down_line_2

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
            "color": VOL_UP if bool(up) else VOL_DOWN,
        })
    return rows


def _tuples(idx, values) -> list[tuple[str, float]]:
    return [(t, float(v)) for t, v in zip(_times(idx), values) if pd.notna(v)]


def build_panes(
    close: pd.Series,
    *,
    open_: pd.Series | None = None,
    high: pd.Series | None = None,
    low: pd.Series | None = None,
    volume: pd.Series | None = None,
    overlays: dict[str, pd.Series] | None = None,
    rs: pd.Series | None = None,
    height: int = 420,
) -> tuple[list[dict], bool]:
    """The price pane (candles or a close line, overlays, volume) and an RS pane.

    Returns (panes, has_volume). Raises ChartUnavailable when the data cannot
    make a chart.
    """
    close = close.dropna()
    if close.empty:
        raise ChartUnavailable("no close prices")
    idx = close.index

    def _align(s: pd.Series | None) -> pd.Series:
        if s is None:
            return pd.Series(index=idx, dtype=float)
        return s.reindex(idx)

    o, h, lo = _align(open_), _align(high), _align(low)
    # An explicit None is the source saying it has no intraday data; an all-NaN
    # column is a source that stalled. Neither can be drawn as a candle.
    intraday = high is not None and low is not None and has_intraday_range(close, h, lo)

    if intraday:
        rows = [(r["time"], r["open"], r["high"], r["low"], r["close"])
                for r in _candles(idx, o.values, h.values, lo.values, close.values)]
        if not rows:
            raise ChartUnavailable("no candle rows")
        price = {"name": "Price", "type": "candlestick", "color": INK, "up": UP, "down": DOWN, "fmt": "price",
                 "data": rows}
    else:
        rows = _tuples(idx, close.values)
        if not rows:
            raise ChartUnavailable("no close rows")
        # Dark and heavier than the overlays: the price is the subject. It does not
        # change colour with the session; without an open there is no up or down
        # bar, and a line that switched would assert something the source lacks.
        price = {"name": "Price", "type": "line", "color": INK, "width": 2, "fmt": "price",
                 "data": rows}

    series: list[dict] = [price]
    for name, values in (overlays or {}).items():
        data = _tuples(idx, _align(values).values)
        if data:
            series.append({"name": name, "type": "line", "color": MA_COLOURS.get(name, MUTED),
                           "width": 1.5, "fmt": "price", "data": data})

    vol_rows = _volume(idx, _align(volume).values, _rising(close, o).values)
    if vol_rows:
        series.append({"name": "Volume", "type": "histogram", "volume": True, "fmt": "int",
                       "color": VOL_UP,
                       "data": [(r["time"], r["value"]) for r in vol_rows],
                       "colors": [r["color"] for r in vol_rows]})

    panes = [{"height": height, "series": series}]
    rs_rows = _tuples(idx, _align(rs).values) if rs is not None else []
    if rs_rows:
        panes.append({"height": 120, "series": [
            {"name": "RS vs Nifty 500", "type": "line", "color": C.up, "width": 1.5,
             "fmt": "num", "data": rs_rows}]})
    return panes, bool(vol_rows)


def render_stock_panes(symbol: str, close: pd.Series, **kw) -> None:
    """Draw the stock chart. Raises ChartUnavailable when the data cannot make one."""
    panes, has_volume = build_panes(close, **kw)
    try:
        lw_chart.render(panes, key=f"lw_{symbol}")
    except Exception as exc:
        raise ChartUnavailable(f"render failed: {exc}") from exc
    if not has_volume:
        st.caption("Volume unavailable for this symbol.")
