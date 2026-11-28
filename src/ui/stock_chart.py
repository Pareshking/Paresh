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

from src.ui.tokens import C, SERIES, series_colour

import pandas as pd

import streamlit as st

from src.ui import lw_chart
from src.ui import page_kit as kit

# Palette shared with the rest of the app.
UP = C.up
DOWN = C.down
INK = C.ink
GRID = C.grid
MUTED = C.muted
# Each overlay in its series colour (tokens.SERIES): one colour per series on every page (S193 G).
MA_COLOURS = {name: series_colour(name) for name in ("20 EMA", "50 EMA", "50D EMA", "200D EMA", "200 SMA", "Nifty 500")}
assert all(name in SERIES for name in MA_COLOURS)
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
    rs_name: str = "RS vs Nifty 500",
    volume_pane: int | None = None,
    rs_height: int = 120,
) -> tuple[list[dict], bool]:
    """The price pane (candles or a close line, overlays, volume) and an RS pane.

    `volume_pane`, when given, draws volume in its own pane of that height,
    headed "Volume", between price and RS (the stock page, STOCK_REQUIREMENTS
    row 49) instead of in the price pane's bottom fifth.

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
    vol_series = None
    if vol_rows:
        vol_series = {"name": "Volume", "type": "histogram", "volume": volume_pane is None, "fmt": "int",
                      "color": VOL_UP,
                      "data": [(r["time"], r["value"]) for r in vol_rows],
                      "colors": [r["color"] for r in vol_rows]}
        if volume_pane is None:
            series.append(vol_series)

    panes = [{"height": height, "series": series}]
    if vol_series is not None and volume_pane is not None:
        panes.append({"height": int(volume_pane), "series": [vol_series]})
    rs_rows = _tuples(idx, _align(rs).values) if rs is not None else []
    if rs_rows:
        panes.append({"height": rs_height, "series": [
            {"name": rs_name, "type": "line", "color": C.up, "width": 1.5,
             "fmt": "lvl" if volume_pane is not None else "num", "data": rs_rows}]})
    return panes, bool(vol_rows)


# ── The stock page's chart (S182, mock-up v2 approved 23 Nov 2026) ──────────────
# Today's chart kept and restyled (STOCK_REQUIREMENTS rows 33, 47-49): price with
# the 50D EMA the ranking uses, Volume in its own pane, and the stock against
# Nifty Total Market beneath, set to 100 at the start of the range; 6M, 12M, 3Y as chips in the chart
# (S193 H2; owner, 23 Nov 2026: one period picker): three years are sent once and a chip redraws in place.

# All: the whole record held (S239 item 4, owner 28 Nov 2026: "Restore the 9"; it went in the 23 Nov mock-up).
RANGES = {"6M": 6, "12M": 12, "3Y": 36, "All": None}   # 12M, not 1Y (glossary 6)
DEFAULT_RANGE = "12M"
RANGE_WHY = "lately"   # recent movement opens on 12M (S193 H1)
RANGE_WORDS = {"6M": "6 months", "12M": "12 months", "3Y": "3 years", "All": "the whole record"}
RS_NAME = "RS against Nifty Total Market"


def long_ema(close: pd.Series) -> pd.Series:
    """The 200D EMA as the breadth readings count it (`market_questions._share_above_ema`: span 200, none before
    160 prints), so the line on a stock's chart is the one Market's "above their 200D EMA" reads."""
    return close.dropna().ewm(span=200, min_periods=160).mean()


def ranking_ema(close: pd.Series) -> pd.Series:
    """The 50D EMA the ranking reads: none before 30 prints (`EMA_MIN_PRINTS`;
    owner 10 Nov 2026, DATA_CORRECTNESS §5). The chart used `min_periods=10`."""
    from src.engine.backtester import EMA_MIN_PRINTS
    return close.dropna().ewm(span=50, min_periods=int(EMA_MIN_PRINTS)).mean()


def window(close: pd.Series, months: int | None) -> pd.Series:
    """The sessions from the first on or after the date `months` back to the last; every session for None (All)."""
    c = close.dropna()
    if c.empty or months is None:
        return c
    start = c.index[-1] - pd.DateOffset(months=months)
    return c[c.index >= start]


def relative_strength(close: pd.Series, market: pd.Series | None) -> pd.Series:
    """The stock over the market, 100 at the first session of `close`; the market
    is carried to the stock's sessions (a market close on each of them)."""
    if market is None or close.empty:
        return pd.Series(dtype=float)
    m = pd.to_numeric(market, errors="coerce").dropna().sort_index()
    m = m.reindex(m.index.union(close.index)).ffill().reindex(close.index)
    both = pd.DataFrame({"s": close, "m": m}).dropna()
    if len(both) < 2:
        return pd.Series(dtype=float)
    ratio = both["s"] / both["m"]
    return ratio / ratio.iloc[0] * 100


def price_chart_panes(close_full: pd.Series, volume: pd.Series | None, market: pd.Series | None,
                      months: int | None) -> tuple[list[dict], bool]:
    """The three panes for a range: price, its 50D EMA and 200D EMA, Volume, RS against the market."""
    close = window(close_full, months)
    return build_panes(close, volume=volume, overlays={"50D EMA": ranking_ema(close_full), "200D EMA": long_ema(close_full)},
                       rs=relative_strength(close, market), rs_name=RS_NAME,
                       height=320, volume_pane=90, rs_height=130)


def range_starts(close_full: pd.Series) -> list[list[str]]:
    """[[label, first session YYYY-MM-DD], ...] for each range, by `window`'s rule."""
    out = []
    for lab, months in RANGES.items():
        w = window(close_full, months)
        if len(w):
            out.append([lab, f"{w.index[0]:%Y-%m-%d}"])
    return out


def chart_panes_all(close_full: pd.Series, volume: pd.Series | None, market: pd.Series | None
                    ) -> tuple[list[dict], bool, dict]:
    """The longest range's panes, sent once, and the chips that cut them (S193 H2). Relative strength is
    marked to be set to 100 again at each range's first session, so 6M and 12M read as they did."""
    panes, has_volume = price_chart_panes(close_full, volume, market, None)
    for p in panes:
        for s in p["series"]:
            if s.get("name") == RS_NAME:
                s["rebase"] = True
    ranges = {"default": DEFAULT_RANGE, "why": RANGE_WHY, "chips": range_starts(close_full)}
    return panes, has_volume, ranges


def render_price_chart(symbol: str, close_full: pd.Series, volume: pd.Series | None,
                       market: pd.Series | None, follow: dict | None = None) -> None:
    """The chart with its range chips, one line of readout per pane. `follow` ({"sel", "html": {range: ...}})
    is the host heading the chips rewrite."""
    try:
        panes, has_volume, ranges = chart_panes_all(close_full, volume, market)
        if follow:
            ranges["follow"] = follow
        lw_chart.render(panes, key=f"lw_{symbol}", one_line=True, ranges=ranges,
                        label=f"{symbol}: price, 50D EMA and 200D EMA, volume, and relative strength against "
                              "Nifty Total Market. Arrow keys move the reading; the range buttons above redraw it.")
    except ChartUnavailable as exc:
        from src.core.logger import logger
        logger.warning("No chart for %s: %s", symbol, exc)   # the cause goes to the log, not the page
        kit.empty(f"No chart for {symbol}.", "There are no closes to draw; the figures on the page still hold.")
        return
    if not has_volume:
        st.caption("Volume unavailable for this symbol.")
