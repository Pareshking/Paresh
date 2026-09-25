"""Which price history the ranking is computed from, decided in one place.

Two sources now exist and they are NOT interchangeable. Choosing between them
per caller would let the app and the nightly precompute rank different data
while every field of the ranking contract still matched -- a wrong answer
served fast, which is worse than no artifact at all. So both ask here.

SCREENER finishes a session. Yahoo publishes an Indian session over a day and a
half and sometimes stalls outright: 2026-09-17 reached 378 of 750 symbols and
had not moved 44 hours later, while screener had all 750 the next morning.

WHAT CHANGES WHEN SCREENER DRIVES THE RANKING, because it is not a drop-in:

  * No intraday high or low exists in that source at all. The engine already
    falls back to closes when high_df is absent, so the 52-week high becomes a
    high of CLOSES. That is a DIFFERENT QUANTITY, not a worse estimate of the
    same one: on the live universe it moves the "within 5% of the 52-week high"
    gate from 22 names to 50, with 28 names crossing in or out.

  * ATR and everything derived from it are dropped rather than computed. True
    range collapses to |close - prev close| without a high and a low, measured
    at 0.47x the real ATR across 750 symbols -- so a 2xATR stop would sit 53%
    tighter than the same column shows today. A stop loss that is silently half
    the intended width is more dangerous than an absent one.

  * Corporate actions are already applied by screener. Our own adjustment is a
    no-op there and must stay one: measured, 0 events applied to the screener
    frame against 38 to the Yahoo frame, because _step_is_still_present sees
    the step is already gone. Never force it.

FALLING BACK. A source that cannot cover the longest lookback is not usable,
and quietly ranking anyway would publish a table whose 12-month column is NaN
for every symbol. The reach test below is the same one calendar_momentum makes
internally, so this decides in advance what the engine would decide silently.
"""

from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass, field

import pandas as pd
import requests

from src.core import startup_metrics as metrics
from src.core.config import (
    MOMENTUM_MONTHS,
    RANKING_PRICE_SOURCE,
    SCREENER_STORE_URL,
)
from src.core.logger import logger

DOWNLOAD_TIMEOUT_S: int = 30


@dataclass
class PriceFrames:
    """What the engine needs, plus what the caller must say out loud."""

    adj_close: pd.DataFrame
    close: pd.DataFrame
    high: pd.DataFrame | None
    low: pd.DataFrame | None
    volume: pd.DataFrame
    source: str
    intraday: bool
    notes: list[str] = field(default_factory=list)

    @property
    def high_basis(self) -> str:
        """How the 52-week high in this table was measured. For the UI."""
        return "intraday highs" if self.intraday else "closing prices"


def reaches_longest_lookback(index: pd.Index, months: int | None = None) -> bool:
    """Would the longest horizon actually fit in this history?

    calendar_momentum returns NaN for a window whose start predates the frame
    (the guard at 'The data does not reach back far enough'). Asking the same
    question here means a source is rejected BEFORE it produces a table with an
    empty 12-month column, rather than after.
    """
    if index is None or len(index) < 2:
        return False
    want = int(months or max(MOMENTUM_MONTHS))
    dates = pd.DatetimeIndex(index).normalize()
    target = dates[-1] - pd.DateOffset(months=want)
    return bool(target >= dates[0])


def fetch_screener_store(url: str | None = None) -> pd.DataFrame | None:
    """The published screener history, or None. Never raises."""
    target = url or SCREENER_STORE_URL
    started = time.perf_counter()
    tmp_path = None
    resp = None  # streamed: holds a pooled connection until closed
    try:
        resp = requests.get(target, timeout=DOWNLOAD_TIMEOUT_S, stream=True)
        if resp.status_code != 200:
            logger.info("Screener store unavailable (HTTP %s).", resp.status_code)
            metrics.note("screener_store_fetch", f"http_{resp.status_code}")
            return None
        fd, tmp_path = tempfile.mkstemp(suffix=".parquet")
        with os.fdopen(fd, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 18):
                fh.write(chunk)
        frame = pd.read_parquet(tmp_path)
        metrics.note("screener_store_fetch", "ok")
        metrics.note("screener_store_fetch_s", round(time.perf_counter() - started, 2))
        return frame
    except Exception as exc:
        logger.info("Screener store fetch failed (%s).", type(exc).__name__)
        metrics.note("screener_store_fetch", type(exc).__name__)
        return None
    finally:
        if resp is not None:
            resp.close()
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def from_screener(store: pd.DataFrame) -> PriceFrames | None:
    """Shape the screener store for the engine, or None if it cannot serve.

    high and low are returned as None rather than as copies of the close.
    MomentumEngine reads that as "no intraday data" and uses closes itself,
    which is the same arithmetic -- but passing an explicit None is what keeps
    `intraday` honest, and the ATR columns therefore dropped instead of
    computed at half their true width.
    """
    if store is None or store.empty:
        return None
    # Any shape that is not a (symbol, field) MultiIndex is refused outright.
    # pandas raises several different things for a wrong-shaped xs, and none of
    # them should reach a caller who only asked which source to rank.
    if not isinstance(store.columns, pd.MultiIndex):
        logger.warning("Screener store has flat columns; not usable.")
        return None
    try:
        close = store.xs("Close", axis=1, level=-1)
        volume = store.xs("Volume", axis=1, level=-1)
    except Exception as exc:
        logger.warning(
            "Screener store has an unexpected shape (%s); not usable.",
            type(exc).__name__,
        )
        return None
    if close.empty or close.shape[1] == 0:
        return None
    if not reaches_longest_lookback(close.index):
        first = pd.DatetimeIndex(close.index)[0].date()
        last = pd.DatetimeIndex(close.index)[-1].date()
        logger.info(
            "Screener history reaches %s-%s, short of the %d-month lookback; "
            "using Yahoo instead. One more collection night closes this.",
            first, last, max(MOMENTUM_MONTHS),
        )
        metrics.note("price_source_rejected", "screener_too_short")
        return None

    return PriceFrames(
        adj_close=close, close=close, high=None, low=None, volume=volume,
        source="screener", intraday=False,
        notes=[
            "52-week high measured on closing prices, not intraday highs",
            "ATR, stop loss and chandelier exit unavailable without a high and low",
        ],
    )


def from_yahoo(adj_close, close, high, low, volume) -> PriceFrames:
    return PriceFrames(
        adj_close=adj_close, close=close, high=high, low=low, volume=volume,
        source="yahoo", intraday=True, notes=[],
    )


# What a reader sees. The internal ids stay as they are -- they are the
# contract term, the config value and what the logs say -- so renaming here
# cannot change which table is accepted or which source is chosen.
_DISPLAY_NAMES: dict[str, str] = {
    "screener": "Personal",
    "yahoo": "Yahoo",
}


def display_name(source: str | None) -> str:
    """The label for the front end. Unknown ids pass through capitalised."""
    key = str(source or "").strip().lower()
    if not key:
        return ""
    return _DISPLAY_NAMES.get(key, key.replace("_", " ").title())


def preferred() -> str:
    return RANKING_PRICE_SOURCE or "yahoo"
