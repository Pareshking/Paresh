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

import io
import os
import tempfile
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import requests

from src.core import startup_metrics as metrics
from src.core.config import (
    MOMENTUM_MONTHS,
    RANKING_PRICE_SOURCE,
    SCREENER_STORE_URL,
)
from src.core.logger import logger
from src.loaders import app_source

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
    if url is None:
        body = app_source.fetch_latest(app_source.SCREENER_STORE, "screener_store")
        if body is not None:
            try:
                frame = pd.read_parquet(io.BytesIO(body))
                if not frame.empty:
                    metrics.note("screener_store_fetch", "ok_r2")
                    app_source.record("screener_store", "r2")
                    return frame
            except Exception as exc:
                logger.info("Screener store from R2 unreadable (%s).", type(exc).__name__)
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
        if url is None:
            app_source.record("screener_store", "release")
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
    """Yahoo as the ranking source: closes only, like Screener.

    Owner, 2026-09-27: the app needs no open, high or low -- no candles, ATR,
    stop loss or chandelier exit. Dropping them here as well means a day
    ranked from Yahoo measures the 52-week high on closes exactly as a
    Screener day does, instead of switching definition with the source.
    """
    return PriceFrames(
        adj_close=adj_close, close=close, high=None, low=None, volume=volume,
        source="yahoo", intraday=False,
        notes=["52-week high measured on closing prices, not intraday highs"],
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
    """Always "screener": Yahoo is no longer a price source (owner, 2026-10-02).

    RANKING_PRICE_SOURCE is still read so an old UMIYA_PRICE_SOURCE=yahoo
    setting is reported rather than silently honoured.
    """
    if RANKING_PRICE_SOURCE and RANKING_PRICE_SOURCE != "screener":
        logger.warning("UMIYA_PRICE_SOURCE=%s ignored: Screener is the only primary source.",
                       RANKING_PRICE_SOURCE)
    return "screener"


def from_nse(middle_close: pd.DataFrame | None, symbols) -> PriceFrames | None:
    """NSE's adjusted closes as the whole source, for a night Screener cannot serve.

    NSE's committed file carries closes only, so volume is all-missing: the
    liquidity columns go blank rather than being invented.
    """
    if middle_close is None or middle_close.empty:
        return None
    keep = [c for c in middle_close.columns if c in set(symbols)]
    if not keep:
        return None
    close = middle_close[keep].astype(float)
    if not reaches_longest_lookback(close.index):
        metrics.note("price_source_rejected", "nse_too_short")
        return None
    volume = pd.DataFrame(np.nan, index=close.index, columns=keep)
    return PriceFrames(
        adj_close=close, close=close, high=None, low=None, volume=volume,
        source="nse", intraday=False,
        notes=["Screener unavailable: ranked on NSE's own closes (split/bonus adjusted)",
               "52-week high measured on closing prices, not intraday highs",
               "Volume unavailable from NSE's committed file"],
    )


def ranking_frames(store: pd.DataFrame | None, symbols,
                   middle_close: pd.DataFrame | None = None) -> PriceFrames | None:
    """The frame the ranking scores: Screener first, NSE for what it lacks.

    The ONE place the app and the nightly precompute build it, so both rank
    the same frame and the published ranking's contract matches. No Yahoo
    tier (owner, 2026-10-02). When Screener cannot serve, NSE's closes are the
    whole source; None when neither can.
    """
    return frames_from(from_screener(store) if store is not None else None,
                       symbols, middle_close)


def frames_from(chosen: PriceFrames | None, symbols,
                middle_close: pd.DataFrame | None = None) -> PriceFrames | None:
    """ranking_frames for a store already shaped by from_screener (the app memoises that)."""
    if chosen is not None and any(c in set(symbols) for c in chosen.close.columns):
        return keep_and_fill(chosen, symbols, None, middle_close)
    return from_nse(middle_close, symbols)


# ── Backup source: Screener first, Yahoo for what it lacks ───────────────────

# Owner, 2026-09-27: "Screener, NSE, and last is Yahoo". NSE took the middle
# place on 2026-10-02 (its corporate-action layer passed the fourth report).
BACKUP_SESSION_COVERAGE = 0.98


FILL_WINDOW_DAYS = 400    # the ranking's 12-month window, with room to spare


def fill_from_backup(primary: pd.DataFrame, backup: pd.DataFrame | None,
                     window_days: int = FILL_WINDOW_DAYS
                     ) -> tuple[pd.DataFrame, int, list]:
    """Primary closes with their gaps filled from the backup's daily MOVES.

    A missing primary price is the last primary price carried forward by the
    backup's one-day return, never the backup's own level: Yahoo adjusts for
    dividends, so its level drifts a few percent from Screener's while its
    daily move matches. Only gaps after a stock's first primary price are
    filled -- before it, there is nothing to chain from.

    A session newer than the primary's last is added only when the backup has
    it for at least BACKUP_SESSION_COVERAGE of the stocks: a half-published
    day is not a session to rank on.

    Only the last `window_days` are filled: the ranking reads no further back,
    and the nightly precompute and the app hold slightly different Yahoo
    copies of older history, which would make their fingerprints disagree.

    Returns (filled frame, cells filled, sessions added).
    """
    if backup is None or backup.empty or primary is None or primary.empty:
        return primary, 0, []
    backup = backup.reindex(columns=primary.columns)
    last = primary.index.max()
    newer = [d for d in backup.index if d > last
             and backup.loc[d].notna().mean() >= BACKUP_SESSION_COVERAGE]
    index = primary.index.union(pd.DatetimeIndex(newer))
    frame = primary.reindex(index)
    moves = backup.reindex(index.union(backup.index)).sort_index()
    moves = (moves / moves.shift(1)).reindex(index)
    before = int(frame.notna().sum().sum())
    values = frame.to_numpy(copy=True)
    step = moves.to_numpy()
    first = int(index.searchsorted(index.max() - pd.Timedelta(days=window_days)))
    for i in range(max(first, 1), len(values)):
        gap = pd.isna(values[i]) & ~pd.isna(values[i - 1]) & ~pd.isna(step[i])
        values[i][gap] = values[i - 1][gap] * step[i][gap]
    filled = pd.DataFrame(values, index=index, columns=primary.columns)
    return filled, int(filled.notna().sum().sum()) - before, newer


MIDDLE_MAX_DRIFT = 0.01   # a stock whose NSE and Screener levels drift past 1% is left to Yahoo


def eligible_middle(primary: pd.DataFrame, middle: pd.DataFrame | None
                    ) -> pd.DataFrame | None:
    """NSE's adjusted closes cut to the stocks that track Screener within 1%.

    Owner, 2026-10-02: NSE is the middle source, "skipping the ~50 stocks still
    off by more than 1%" (fourth NSE report). Those stocks keep falling through
    to Yahoo. Imported lazily: nse_adjusted imports this module.
    """
    if middle is None or middle.empty or primary is None or primary.empty:
        return None
    from src.loaders import nse_adjusted as na

    drift = na.level_drift(middle, primary)
    good = [c for c in middle.columns if c in drift.index
            and drift.at[c, "max_drift"] <= MIDDLE_MAX_DRIFT]
    return middle[good] if good else None


def keep_and_fill(chosen: PriceFrames, symbols, backup_close: pd.DataFrame | None,
                  middle_close: pd.DataFrame | None = None) -> PriceFrames:
    """The chosen frames cut to `symbols`, gaps filled Screener -> NSE -> Yahoo.

    The app and the nightly precompute both call this, so they rank the same
    frame and the published ranking's contract still matches. `middle_close`
    is NSE's adjusted closes (None leaves the old Screener -> Yahoo order).
    """
    keep = [c for c in chosen.close.columns if c in set(symbols)]
    close = chosen.close[keep]
    mid_cells, mid_added = 0, []
    middle = eligible_middle(close, middle_close)
    if middle is not None:
        close, mid_cells, mid_added = fill_from_backup(close, middle)
    close, n_cells, added = fill_from_backup(close, backup_close)
    chosen.adj_close = chosen.close = close
    chosen.volume = chosen.volume.reindex(index=close.index, columns=keep)
    if mid_cells or mid_added:
        metrics.note("price_nse_cells", mid_cells)
        metrics.note("price_nse_sessions", ",".join(str(d.date()) for d in mid_added))
        chosen.notes = list(chosen.notes) + [
            f"{mid_cells} missing Screener prices filled from NSE's daily moves"
            + (f"; sessions from NSE: {', '.join(str(d.date()) for d in mid_added)}"
               if mid_added else "")]
    if n_cells or added:
        metrics.note("price_backup_cells", n_cells)
        metrics.note("price_backup_sessions", ",".join(str(d.date()) for d in added))
        chosen.notes = list(chosen.notes) + [
            f"{n_cells} missing Screener prices filled from Yahoo's daily moves"
            + (f"; sessions from Yahoo: {', '.join(str(d.date()) for d in added)}" if added else "")]
    return chosen
