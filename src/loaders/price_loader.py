"""
Price history and OHLCV downloader with parquet caching and market regime detector.
Features multi-threaded batch downloads, resilient incremental date caching, and robust schema normalization.
"""

from __future__ import annotations

import os
import tempfile
import time
from datetime import date
from typing import Sequence

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from src.core import startup_metrics as metrics
from src.core.config import BENCHMARK_SYMBOL, PRICES_FILE
from src.core.tickers import is_tradeable_symbol, normalise_columns, normalise_symbol
from src.core.market_time import (
    ist_today,
    last_downloadable_session,
    session_is_complete,
    trading_days_behind,
)
from src.core.logger import logger
from src.core.types import MarketRegime, RegimeData

# Configure yfinance timezone cache to prevent repeated warning logs
try:
    _tz_cache_dir = os.path.join(tempfile.gettempdir(), "yf_tz_cache")
    os.makedirs(_tz_cache_dir, exist_ok=True)
    yf.set_tz_cache_location(_tz_cache_dir)
except Exception:
    pass


def _cache_is_current(last_cached_date: date) -> bool:
    """Is the cache holding the last COMPLETED session, and therefore final?

    Two conditions, and the second one is the one that was missing.

    The cache must hold the most recent trading day -- counted in trading days,
    so Friday's data read on a Sunday is current rather than two days behind.

    And that session must have CLOSED. The old gate asked only
    "last_cached_date >= today", which the first fetch of the morning satisfies
    with a row whose Close is simply the last trade so far. From that moment
    the cache was declared fresh and no further fetch ran for the rest of the
    day: the screener served the opening price at three in the afternoon, and
    the page dated it today -- true of the row, false of the number.

    Holidays are not enumerated (see recent_trading_days). On a holiday this
    returns False, costs one lookup that finds nothing, and serves the cache
    anyway. Wrong in the cheap direction: never claiming current when it is
    not.
    """
    behind = trading_days_behind(last_cached_date)
    if behind is None or behind > 0:
        return False
    return session_is_complete(last_cached_date)


# A session where this fraction of the universe never printed is not a session.
#
# Measured on the live 500-session frame, and the separation is not marginal:
# 2026-09-14 -- an NSE holiday -- sits alone at 61.3% coverage, the thinnest
# REAL trading day in two years is 2026-07-20 at 82.0%, and 496 of 500 sessions
# clear 82%. The oldest rows in the window sit at 90.3%, low only because a
# tenth of today's universe had not listed yet, so the floor has to stay well
# under that too. 70% is the midpoint of a twenty-point gap.
#
# THIS IS A BACKSTOP, NOT THE ANSWER. The authoritative test for "was this a
# trading day" is whether NSE published a bhavcopy for it, and this job already
# downloads those. A committed trading-day record derived from them would need
# no threshold at all. Until that exists, this catches the case that reaches
# the engine as phantom returns.
MIN_SESSION_COVERAGE: float = 0.70

# The third test, and the only one that needs neither a threshold nor a record.
# A holiday row from Yahoo is not a thin session, it is a quote sheet: open =
# high = low = close = the previous close, at zero volume. On 2026-09-14 that
# held for 551 of the 551 symbols the vendor answered for -- every one flat,
# every one at zero volume, not one matching the NEXT session.
#
# This is what closed_days cannot do on its own: a holiday has to be
# ESTABLISHED before the calendar can drop it, and four more were sitting in
# the live cache that nobody had established --
#
#   2026-01-15  88.8%   2026-05-01  88.9%   2026-05-28 100.0%
#   2026-06-26 100.0%   2026-09-14  73.5%
#
# -- two of them at FULL coverage, where no floor can ever reach them. Volume
# needs no prior knowledge of the calendar and does not move as the vendor
# backfills.
#
# Deliberately strict. A session is only called a non-session when the vendor
# SUPPLIED volume (absence of volume is never evidence of no trading, the same
# asymmetry trading_days is built on), when every supplied volume is zero, and
# when the bars are flat.
_ZERO_TRADE_MIN_NAMES: int = 20
_ZERO_TRADE_VOLUME_SHARE: float = 0.95
_ZERO_TRADE_FLAT_SHARE: float = 0.95


def _field_level(columns: pd.MultiIndex) -> int | None:
    """Which level of a (ticker, field) column index holds the OHLCV names."""
    for lvl in range(columns.nlevels):
        vals = {str(v).strip().lower() for v in columns.get_level_values(lvl)}
        if "close" in vals and "volume" in vals:
            return lvl
    return None


def _zero_trade_sessions(df: pd.DataFrame) -> pd.Series | None:
    """Dates on which nothing traded, whatever the vendor published for them.

    Returns a boolean mask over df.index, or None when the frame carries no
    volume to judge by -- a single-field price frame falls through to the
    coverage floor and the recorded calendar exactly as before.

    Coverage cannot separate a holiday from a vendor mid-publish, so a floor is
    always racing backfill: 2026-09-14 read 61% during its own sync, 86% the
    next day and 73.5% the day after, landing either side of the 70% line.
    Volume does not move. A closed exchange prints none on the day and none a
    week later, so this test is as good late as it is early.
    """
    if not isinstance(df.columns, pd.MultiIndex):
        return None
    lvl = _field_level(df.columns)
    if lvl is None:
        return None

    spelling = {str(v).strip().lower(): v for v in df.columns.get_level_values(lvl)}

    def _field(name: str) -> pd.DataFrame | None:
        key = spelling.get(name)
        if key is None:
            return None
        return df.xs(key, level=lvl, axis=1).apply(pd.to_numeric, errors="coerce")

    close, volume = _field("close"), _field("volume")
    if close is None or volume is None or close.shape[1] < _ZERO_TRADE_MIN_NAMES:
        return None
    volume = volume.reindex(columns=close.columns)

    has_close = close.notna()
    priced = has_close.sum(axis=1)
    # Volume the vendor actually supplied, for names it also priced.
    vol_known = (volume.notna() & has_close).sum(axis=1)
    traded = ((volume > 0) & has_close).sum(axis=1)

    # A bar with no range. Checked when the frame carries O/H/L and skipped when
    # it does not: zero volume across a whole session is already decisive, and
    # requiring a field the vendor omitted would silently disable the test.
    flat = priced
    ohl = [_field(n) for n in ("open", "high", "low")]
    if all(f is not None for f in ohl):
        same = has_close.copy()
        for other in ohl:
            same &= np.isclose(
                other.reindex(columns=close.columns).to_numpy(dtype=float),
                close.to_numpy(dtype=float),
                equal_nan=False,
            )
        flat = same.sum(axis=1)

    return (
        (priced >= _ZERO_TRADE_MIN_NAMES)
        & (traded == 0)
        & (vol_known >= priced * _ZERO_TRADE_VOLUME_SHARE)
        & (flat >= priced * _ZERO_TRADE_FLAT_SHARE)
    )


def _drop_phantom_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """Drop dates where too little of the universe traded to be a real session.

    An exchange holiday on which the vendor still emits partial data is not the
    case clean_holidays was built for. That guard drops a row only when more
    than 70% of the universe is NaN -- a genuine exchange-wide blank. A holiday
    where Yahoo answers for 460 of 750 symbols sits at 39% NaN and sails
    through, and the engine then scores a one-day move into a day nobody
    traded, and another back out of it.

    2026-09-14 is exactly that, and it arrived through the healing path: the
    incremental top-up had skipped it (the cache jumped 09-11 to 09-15, and
    being append-only it could never revisit), so the accident of that bug was
    hiding this one. Re-requesting 45 days of settled history found the row
    Yahoo was offering and merged it in. The published snapshot and the
    precomputed ranking both carried it.

    Dropping is the safe direction whatever the cause. If it really is a
    holiday, the row is fiction. If it were instead a genuine partial outage,
    removing it makes the return span 09-11 to 09-15 -- which is what a holder
    actually experienced -- rather than inventing a close for 460 names and
    leaving 290 with none.

    THREE TESTS, in descending order of authority. A recorded closure drops the
    row at any coverage, because the calendar is a fact. Zero trading drops it
    at any coverage too, because a session on which not one priced symbol
    changed hands was not a session -- and unlike the calendar, that needs
    nobody to have established the holiday first. The coverage floor is the
    backstop for what neither can see: a vendor publishing nothing at all for a
    session that really happened.
    """
    if df is None or df.empty or df.shape[1] < 50:
        return df

    # Coverage is measured against the symbols that EXISTED on that date, not
    # against today's universe. A stock that listed in 2023 is legitimately NaN
    # for every session before it, so judging an old row against all 750 names
    # makes deep history look like an outage and deletes it.
    #
    # That is not hypothetical: it cost three years. The archive rebuilt from a
    # ten-year download arrived with 2476 sessions and was cut to 1731, and the
    # oldest surviving row sat at 70.1% -- one tick above the floor. The cut
    # date, 2019-09-20, was simply where 70% of today's constituents happened
    # to have listed. Nothing was wrong with the prices.
    #
    # A symbol counts as alive from its first real print onward. Before that it
    # contributes to neither the numerator nor the denominator, so a complete
    # 2016 session reads 100% on the 520 names that existed, exactly as a
    # complete 2026 session reads 100% on 750.
    values = df.notna().to_numpy()
    alive = np.logical_or.accumulate(values, axis=0)
    alive_count = alive.sum(axis=1)
    covered = values.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.where(alive_count > 0, covered / np.maximum(alive_count, 1), 1.0)
    coverage = pd.Series(ratio, index=df.index)

    # Below this there are too few listed names for the ratio to mean anything,
    # and a handful of blanks would read as an exchange-wide outage.
    _MIN_ALIVE = 50
    phantom = ((coverage < MIN_SESSION_COVERAGE) & (alive_count >= _MIN_ALIVE)).to_numpy()
    dates = pd.DatetimeIndex(df.index)
    shut = np.zeros(len(dates), dtype=bool)

    # Evidence, alongside the record below rather than instead of it. A recorded
    # closure is a fact about the calendar and needs no corroboration; this
    # catches the holidays nobody has recorded yet, including the ones sitting
    # at full coverage where no floor can reach them.
    _zt = _zero_trade_sessions(df)
    zt = _zt.to_numpy() if _zt is not None else np.zeros(len(dates), dtype=bool)

    # The record outranks the coverage guess in BOTH directions, and the two
    # halves are consulted separately because they carry different claims.
    #
    # A confirmed date is one NSE published a bhavcopy for, so it traded --
    # whatever the vendor has managed to publish since. Without this,
    # 2026-09-16 was dropped at 20% coverage three seconds before the same run
    # fetched NSE's bhavcopy FOR 2026-09-16.
    #
    # A closed date is one established as a holiday. It is dropped at ANY
    # coverage, which is the whole point: 2026-09-14 was a holiday Yahoo kept
    # answering for, and its coverage wandered 61% -> 86% -> 73.5% across three
    # days, landing either side of the floor. No threshold decides it; the
    # calendar does.
    #
    # An unrecorded date is neither, and falls through to the coverage floor
    # exactly as before -- absence is never evidence of a closure. See
    # src/loaders/trading_days.
    try:
        from src.loaders.trading_days import load_closed, load_confirmed

        confirmed = load_confirmed()
        if confirmed:
            vouched = np.array([d.date().isoformat() in confirmed for d in dates])
            rescued = int((phantom & vouched).sum())
            if rescued:
                logger.info(
                    "Keeping %d thin session(s) NSE confirmed as trading days "
                    "(%s); the exchange outranks the coverage floor.",
                    rescued,
                    ", ".join(
                        str(d.date()) for i, d in enumerate(dates)
                        if phantom[i] and vouched[i]
                    )[:120],
                )
                metrics.note("price_sessions_rescued_by_nse", rescued)
            phantom = phantom & ~vouched

        closed = load_closed()
        if closed:
            shut = np.array([d.date().isoformat() in closed for d in dates])
            # A confirmation would have beaten this, but record_closed refuses
            # to store a date NSE vouched for, so the two can never both hold.
            if shut.any():
                logger.info(
                    "Dropping %d session(s) recorded as market holidays (%s); "
                    "the vendor answered for them anyway.",
                    int(shut.sum()),
                    ", ".join(
                        f"{d.date()} at {coverage.iloc[i]*100:.0f}%"
                        for i, d in enumerate(dates) if shut[i]
                    )[:160],
                )
                metrics.note("price_holiday_rows_dropped", int(shut.sum()))
    except Exception as exc:
        logger.warning(
            "Trading-day record unavailable (%s); falling back to coverage alone.",
            type(exc).__name__,
        )

    if zt.any():
        logger.warning(
            "Dropping %d session(s) on which nothing traded -- every priced "
            "symbol flat at zero volume (%s). A quote sheet is not a session.",
            int(zt.sum()),
            ", ".join(
                f"{d.date()} at {coverage.iloc[i]*100:.0f}%"
                for i, d in enumerate(dates) if zt[i]
            )[:200],
        )
        metrics.note("price_zero_trade_sessions_dropped", int(zt.sum()))
        # The DATES, not just the count, so the nightly job can write them into
        # the calendar. A count cannot be recorded against anything.
        metrics.note(
            "price_zero_trade_dates",
            ",".join(str(d.date()) for i, d in enumerate(dates) if zt[i]),
        )
        metrics.note(
            "price_zero_trade_coverage",
            ",".join(
                f"{d.date()}:{coverage.iloc[i]*100:.0f}"
                for i, d in enumerate(dates) if zt[i]
            ),
        )
        # A confirmation rescues a THIN session from the floor; it does not
        # rescue one where nothing changed hands. A bhavcopy 200 says the
        # endpoint answered, zero volume across the whole universe says nobody
        # traded, and the second is the more specific claim. record_closed
        # already refuses to store a closure for a confirmed date, so a
        # disagreement here means one of the two sources is wrong -- reported,
        # not silently resolved.
        _conflict = zt & ~shut
        _vouched_zt = [
            d for i, d in enumerate(dates)
            if _conflict[i] and not phantom[i] and coverage.iloc[i] >= 0.99
        ]
        if _vouched_zt:
            logger.info(
                "%d of those were at full vendor coverage (%s); no floor could "
                "have reached them.",
                len(_vouched_zt),
                ", ".join(str(d.date()) for d in _vouched_zt)[:120],
            )

    shut = shut | zt

    if not phantom.any():
        return df.loc[~shut] if shut.any() else df
    logger.warning(
        "Dropping %d session(s) where under %.0f%% of the universe traded "
        "(%s); an exchange holiday the vendor answered for anyway is not a "
        "session.",
        int(phantom.sum()), MIN_SESSION_COVERAGE * 100,
        ", ".join(
            f"{d.date()} at {coverage.iloc[i]*100:.0f}%"
            for i, d in enumerate(dates) if phantom[i]
        )[:200],
    )
    metrics.note("price_phantom_sessions_dropped", int(phantom.sum()))
    return df.loc[~(phantom | shut)]


def _drop_unsettled_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only sessions whose daily bar has finished moving.

    THE CACHE MUST HOLD SETTLED SESSIONS ONLY. Everything downstream assumes
    it: the download gate decides what to fetch by comparing the last cached
    date against the last settled session, the precomputed ranking fingerprints
    the frame and expects the same bytes tomorrow, and "price as of" on the
    page is a claim about a close.

    An in-progress session breaks all three at once, and the run of
    2026-09-16 shows how. The nightly job normally fires at 23:00 IST, safely
    past the settle window -- but dispatched by hand at 09:10 IST, minutes
    after the open, it wrote a row where 587 of 750 symbols had printed and
    163 had not. The precompute then ranked that frame and published a table
    with 587 rows in it, and because the frame and the table agreed with each
    other the contract had nothing to object to.

    ``heal_days`` is what let it through: a healing run deliberately skips the
    download gate, because it is reaching BACKWARD for sessions already held.
    Nothing stopped the same request also reaching forward into a session that
    had barely started. This is the guard for that, applied where the frame is
    built rather than where it is requested, so it holds however the fetch was
    reached.

    A future-dated row is unsettled by definition, so this subsumes
    :func:`_drop_future_rows`.
    """
    if df is None or df.empty:
        return df
    try:
        dates = pd.DatetimeIndex(df.index)
    except (TypeError, ValueError):
        return df
    try:
        unsettled = np.array([not session_is_complete(d.date()) for d in dates])
    except (TypeError, ValueError, AttributeError):
        return df
    if not unsettled.any():
        return df
    kept = df.loc[~unsettled]
    logger.info(
        "Dropping %d unsettled session(s) from the price frame (%s); a bar "
        "that is still moving is not a close.",
        int(unsettled.sum()),
        ", ".join(str(d.date()) for d in dates[unsettled][:3]),
    )
    metrics.note("price_unsettled_rows_dropped", int(unsettled.sum()))
    return kept


def _drop_future_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Discard price rows dated after today, IST.

    yfinance occasionally emits one when its timezone handling slips against a
    market five and a half hours ahead of UTC. A single such row used to pin
    the cache permanently: every later run found a last date at or beyond
    today, declared the cache fresh, and returned without fetching anything --
    for the life of the container, and with the page reporting the phantom
    date as the as-of.
    """
    if df is None or df.empty:
        return df
    try:
        future = pd.DatetimeIndex(df.index) > pd.Timestamp(ist_today())
    except (TypeError, ValueError):
        return df
    if not future.any():
        return df
    logger.warning(
        "Dropping %d price row(s) dated after today (last was %s).",
        int(future.sum()), df.index[-1],
    )
    metrics.note("price_future_rows_dropped", int(future.sum()))
    return df.loc[~future]


def _recover_stale_cache(last_cached_date: date):
    """Last resort when Yahoo adds nothing and the cache is genuinely behind.

    Only when the cache is MORE than one trading day behind. One day behind is
    the ordinary state of a morning before the session has produced anything --
    reaching for the snapshot there would spend ten megabytes to be told what
    the cache already knows, every hour of every trading day.

    Returns the recovered frame, or None to keep serving what we have.
    """
    behind = trading_days_behind(last_cached_date)
    if behind is not None and behind <= 1:
        return None

    metrics.note("price_cache_behind_trading_days", "unknown" if behind is None else behind)
    logger.warning(
        "Price cache is %s trading days behind and Yahoo returned nothing; "
        "trying the published snapshot.",
        "more than 30" if behind is None else behind,
    )
    try:
        from src.loaders.price_store import snapshot_frame_if_newer

        recovered = snapshot_frame_if_newer(last_cached_date)
    except Exception as exc:  # recovery must never take the app down
        logger.warning("Snapshot recovery failed (%s: %s).", type(exc).__name__, exc)
        return None

    if recovered is None or recovered.empty:
        metrics.note("price_path", "cache_stale_unrecovered")
        return None

    metrics.note("price_path", "snapshot_recovery")
    metrics.note("price_series_returned", len(recovered.columns))
    return _normalise_ticker_level(recovered)


def _normalise_ticker_level(df: pd.DataFrame) -> pd.DataFrame:
    """Ticker labels, normalised before any merge. See src/core/tickers."""
    return normalise_columns(df, level=0)


def _coalesce_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Merge columns that share a label, keeping the first non-null per row.

    A backstop for the case above. If two frames ever arrive with genuinely
    different level ORDER, normalising the labels is not enough and the union
    reappears; folding the duplicates together loses nothing, because the
    halves are disjoint in time.
    """
    if df is None or df.empty or not df.columns.duplicated().any():
        return df
    levels = list(range(df.columns.nlevels))
    merged = df.T.groupby(level=levels).first().T
    logger.warning(
        "Coalesced %d duplicate price columns after merge.",
        int(df.columns.duplicated().sum()),
    )
    return merged


# Every download in this module pins auto_adjust=True EXPLICITLY. It is also
# yfinance's current default, so nothing changes today -- that is the point.
# ath_loader.py sets it explicitly too, and the two must agree: a split-adjusted
# history compared against an unadjusted all-time high reports -76% where the
# truth is +20%. Leaving one side to a third-party default meant the invariant
# holding the whole comparison together was one dependency release away from
# flipping, silently, with no error anywhere.


def _extract_field(df: pd.DataFrame, field_names: list[str]) -> pd.DataFrame:
    """Extracts a specific price field across all symbols from flat or MultiIndex DataFrames."""
    if df is None or df.empty:
        return pd.DataFrame()

    if not isinstance(df.columns, pd.MultiIndex):
        # Flat DataFrame -- yfinance returns this shape when a batch collapses
        # to a single ticker. Normalise the ticker labels the SAME way as the
        # MultiIndex branches below. Without this the columns keep their ".NS"
        # suffix, nothing matches the universe symbols, every Score maps to NaN,
        # and get_rankings drops all 750 rows -- a silent empty ranking rather
        # than an error.
        out = df.copy()
        out.columns = [
            normalise_symbol(c) for c in out.columns
        ]
        return out

    # MultiIndex. The field may sit on either level depending on how yfinance
    # grouped the response, so try level 1 (Ticker, Field) then level 0.
    if df.columns.nlevels > 1:
        for level in (1, 0):
            extracted = _extract_by_coverage(df, field_names, level)
            if extracted is not None:
                return extracted

    return pd.DataFrame(index=df.index)


def _extract_by_coverage(
    df: pd.DataFrame, field_names: list[str], level: int
) -> pd.DataFrame | None:
    """Pick the candidate field that covers the MOST tickers, not the first one present.

    This took production down twice. yfinance rate-limits a ticker, returns
    that one ticker UNADJUSTED -- six fields including "Adj Close" -- while the
    other 749 come back auto-adjusted with five fields and no "Adj Close" at
    all. The old code took the first candidate name that appeared ANYWHERE, so
    "Adj Close" won on the strength of a single failed ticker and
    df.xs("Adj Close") returned exactly one all-NaN column.

    The screener then ranked 0 of 750 stocks. The giveaway in the logs was
    "Price cache saved: 500 rows (3751 series)" -- 3751 is 749x5 + 1x6, not a
    clean grid.

    Coverage decides, with the preference order breaking ties. When every
    ticker carries both fields the counts are equal and "Adj Close" still wins,
    so normal behaviour is unchanged.
    """
    labels = df.columns.get_level_values(level)
    lowered = [str(x).strip().lower() for x in labels]

    best_target = None
    best_coverage = 0
    for target in field_names:
        coverage = lowered.count(target.lower())
        if coverage > best_coverage:
            best_target, best_coverage = target, coverage

    if best_target is None or best_coverage == 0:
        return None

    n_tickers = len(set(df.columns.get_level_values(1 - level)))
    if best_coverage < n_tickers:
        logger.warning(
            "Price field '%s' covers only %d of %d tickers; the rest are missing "
            "this field entirely. Extracting the %d available.",
            best_target, best_coverage, n_tickers, best_coverage,
        )

    idx = lowered.index(best_target.lower())
    actual_label = labels[idx]
    extracted = df.xs(actual_label, level=level, axis=1)
    extracted.columns = [
        normalise_symbol(c) for c in extracted.columns
    ]
    return extracted


def _clean_price_df(df: pd.DataFrame, symbols: Sequence[str] | None = None) -> pd.DataFrame:
    """Cleans trailing empty rows, deduplicates columns, and filters valid symbols."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.loc[:, ~df.columns.duplicated()].copy()
    # Drop rows at the end that are all NaN
    valid_idx = out.dropna(how="all").index
    if not valid_idx.empty:
        out = out.loc[: valid_idx[-1]]
    # Preserve security-specific NaNs; do not manufacture zero-return observations.
    if symbols:
        valid_cols = [s.upper() for s in symbols if s.upper() in out.columns]
        if valid_cols:
            out = out[valid_cols]
        else:
            # Not one requested symbol is present. Silently returning the
            # unfiltered frame lets a symbol-namespace mismatch travel all the
            # way to the ranking, where it looks like "no stock qualified".
            logger.warning(
                "No requested symbol matched the price columns (%d columns, "
                "e.g. %s vs requested %s). Returning the frame unfiltered; the "
                "ranking will be empty if these labels do not match.",
                len(out.columns),
                list(out.columns[:3]),
                [str(x).upper() for x in list(symbols)[:3]],
            )
    return out


def _decompose_fields(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Decompose a MultiIndex price DataFrame into per-field DataFrames in one pass.

    The old path called _extract_by_coverage six times, each invoking
    get_level_values + a linear label scan across all columns. For a
    750-symbol × 5-field frame (3 750 columns) that is roughly 45 000 string
    comparisons. This function does it in two get_level_values calls + one O(m)
    dict build, then six O(1) dict lookups.

    Returns an empty dict for flat DataFrames — callers fall back to
    _extract_field per-field in that case (flat frames are rare in practice).
    """
    if not isinstance(df.columns, pd.MultiIndex):
        return {}

    KNOWN_FIELDS = {
        "adj close", "adjclose", "close", "high", "low", "volume", "vol", "open"
    }

    lv0_raw = df.columns.get_level_values(0)
    lv1_raw = df.columns.get_level_values(1)
    lv0 = [str(x).strip().lower() for x in lv0_raw]
    lv1 = [str(x).strip().lower() for x in lv1_raw]

    # Identify which level carries price field names vs ticker names.
    n_known_lv1 = sum(1 for x in lv1 if x in KNOWN_FIELDS)
    n_known_lv0 = sum(1 for x in lv0 if x in KNOWN_FIELDS)
    if n_known_lv1 >= n_known_lv0:
        field_labels, ticker_raw = lv1, lv0_raw
    else:
        field_labels, ticker_raw = lv0, lv1_raw

    # Build field-name → column-position list in one scan.
    field_to_cols: dict[str, list[int]] = {}
    for i, fl in enumerate(field_labels):
        field_to_cols.setdefault(fl, []).append(i)

    n_tickers = len(set(ticker_raw))

    def _pick(candidates: list[str]) -> pd.DataFrame:
        best_name: str | None = None
        best_pos: list[int] = []
        for cand in candidates:
            pos = field_to_cols.get(cand.strip().lower(), [])
            if len(pos) > len(best_pos):
                best_name, best_pos = cand, pos
        if not best_pos:
            return pd.DataFrame(index=df.index)
        if len(best_pos) < n_tickers:
            logger.warning(
                "Price field '%s' covers only %d of %d tickers; the rest are "
                "missing this field entirely. Extracting the %d available.",
                best_name, len(best_pos), n_tickers, len(best_pos),
            )
        out = df.iloc[:, best_pos].copy()
        out.columns = [normalise_symbol(ticker_raw[i]) for i in best_pos]
        return out

    return {
        "adj_close": _pick(["Adj Close", "AdjClose", "Close"]),
        "close":     _pick(["Close", "Adj Close", "AdjClose"]),
        "high":      _pick(["High"]),
        "low":       _pick(["Low"]),
        "volume":    _pick(["Volume", "Vol"]),
        "open":      _pick(["Open"]),
    }


def extract_ohlcv(
    prices_df: pd.DataFrame,
    symbols: Sequence[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Extracts (Adj Close, Close, High, Low, Volume, Open) DataFrames from raw
    yfinance price data. Open is last so existing five-value unpacking keeps
    working where it is still used.
    """
    if prices_df is None or prices_df.empty:
        empty = pd.DataFrame()
        return empty, empty, empty, empty, empty, empty

    if isinstance(prices_df.columns, pd.MultiIndex):
        fields = _decompose_fields(prices_df)
        adj_close = fields.get("adj_close", pd.DataFrame())
        close_p   = fields.get("close",     pd.DataFrame())
        high_p    = fields.get("high",      pd.DataFrame())
        low_p     = fields.get("low",       pd.DataFrame())
        vol_p     = fields.get("volume",    pd.DataFrame())
        open_p    = fields.get("open",      pd.DataFrame())
    else:
        # Flat DataFrame — rare (single-ticker response). _extract_field handles
        # this by returning all columns; the field-name argument is ignored.
        open_p    = _extract_field(prices_df, ["Open"])
        adj_close = _extract_field(prices_df, ["Adj Close", "AdjClose", "Close"])
        close_p   = _extract_field(prices_df, ["Close", "Adj Close", "AdjClose"])
        high_p    = _extract_field(prices_df, ["High"])
        low_p     = _extract_field(prices_df, ["Low"])
        vol_p     = _extract_field(prices_df, ["Volume", "Vol"])

    # Fallbacks if some fields are missing
    if adj_close.empty and not close_p.empty:
        adj_close = close_p.copy()
    if close_p.empty and not adj_close.empty:
        close_p = adj_close.copy()
    if high_p.empty and not close_p.empty:
        high_p = close_p.copy()
    if low_p.empty and not close_p.empty:
        low_p = close_p.copy()
    if open_p.empty and not close_p.empty:
        open_p = close_p.copy()
    if vol_p.empty and not close_p.empty:
        vol_p = pd.DataFrame(0.0, index=close_p.index, columns=close_p.columns)

    adj_close = _clean_price_df(adj_close, symbols)
    close_p   = _clean_price_df(close_p,   symbols)
    high_p    = _clean_price_df(high_p,    symbols)
    low_p     = _clean_price_df(low_p,     symbols)
    vol_p     = _clean_price_df(vol_p,     symbols)
    open_p    = _clean_price_df(open_p,    symbols)

    return adj_close, close_p, high_p, low_p, vol_p, open_p


def _note_price_as_of(df: pd.DataFrame | None) -> None:
    """Record the last session the price frame actually contains.

    The data-quality footer reports how old each source is, and it can only
    report what the loaders record. Every return path from fetch_price_history
    must call this: a path that forgets simply drops "Prices" from the footer
    with no visible sign, which is how the freshest-looking footer can be the
    one hiding the stalest data.
    """
    try:
        if df is None or df.empty or len(df.index) == 0:
            return
        metrics.note("price_as_of", pd.Timestamp(df.index[-1]).date().isoformat())
    except Exception:  # telemetry must never break a data path
        pass


def _download_range(tickers: list[str], start_date: pd.Timestamp) -> pd.DataFrame:
    """One vendor call for everything from `start_date` forward."""
    start_str = start_date.strftime("%Y-%m-%d")
    logger.info(
        f"Downloading incremental prices from {start_str} for {len(tickers)} tickers…"
    )
    return yf.download(
        tickers,
        start=start_str,
        progress=False,
        group_by="ticker",
        threads=True,
        auto_adjust=True,
    )


def _read_local_price_cache() -> pd.DataFrame | None:
    """The stored frame, cleaned of rows that are not settled sessions, or None.

    ONLY the read is guarded, and that is the whole point of this being its own
    function. The try/except used to span the entire cached path -- ticker
    renaming, the cell-by-cell merge, the parquet write -- and report every one
    of them as "cache read failed" before falling through to a full 750-symbol
    download from Yahoo. A bug in the merge therefore looked like a cold cache
    and was answered with the exact request the published snapshot exists to
    avoid, which Yahoo rate-limits. Past this function a failure is a real
    failure and raises.
    """
    try:
        cached = pd.read_parquet(PRICES_FILE)
        return _drop_phantom_sessions(_drop_unsettled_rows(_drop_future_rows(cached)))
    except Exception as e:
        logger.warning(
            "Price cache read failed (%s: %s); falling back to a full download.",
            type(e).__name__, e,
        )
        return None


def _cached_symbols(df: pd.DataFrame) -> set[str]:
    """Return canonical ticker symbols present in a raw price cache."""
    if df is None or df.empty:
        return set()
    if isinstance(df.columns, pd.MultiIndex):
        raw = df.columns.get_level_values(0)
    else:
        raw = df.columns
    return {
        normalise_symbol(value)
        for value in raw
        if is_tradeable_symbol(normalise_symbol(value))
    }


def _new_cache_symbols(symbols: Sequence[str], cached: pd.DataFrame) -> list[str]:
    """Find current-universe symbols absent from the Yahoo price cache.

    A new NSE constituent must not inherit the cache's last-date incremental
    path: that path can only fetch forward from a date the symbol already has.
    New symbols therefore get a full configured history acquisition first.
    """
    requested = {
        normalise_symbol(symbol)
        for symbol in symbols
        if is_tradeable_symbol(normalise_symbol(symbol))
    }
    missing = sorted(requested - _cached_symbols(cached))
    if missing:
        logger.info(
            "Detected %d new price-cache symbol(s) requiring full history: %s",
            len(missing),
            ", ".join(missing[:20]) + ("…" if len(missing) > 20 else ""),
        )
        metrics.note("price_new_symbols_detected", len(missing))
    return missing


def _download_full_symbol_history(
    symbols: Sequence[str], period: str
) -> pd.DataFrame:
    """Acquire full available Yahoo history for only newly missing symbols.

    This deliberately uses the canonical symbol name and Yahoo's mechanical
    .NS transport suffix. It is not an alias/remapping layer: if Yahoo has
    not published a newly renamed NSE symbol yet, that symbol simply remains
    unresolved until a later run.
    """
    if not symbols:
        return pd.DataFrame()

    yf_symbols = [
        s + ".NS" if not s.upper().endswith(".NS") else s
        for s in symbols
        if is_tradeable_symbol(normalise_symbol(s))
    ]
    if not yf_symbols:
        return pd.DataFrame()

    metrics.note("price_new_symbols_requested", len(yf_symbols))
    frames: list[pd.DataFrame] = []
    for start in range(0, len(yf_symbols), 100):
        batch = yf_symbols[start:start + 100]
        logger.info(
            "Downloading full history for %d new price-cache symbol(s) "
            "(period=%s).",
            len(batch),
            period,
        )
        try:
            got = yf.download(
                batch,
                period=period,
                progress=False,
                group_by="ticker",
                threads=True,
                auto_adjust=True,
            )
            if got is not None and not got.empty:
                frames.append(got)
        except Exception as exc:
            logger.warning(
                "Full-history new-symbol batch failed (%s): %s",
                type(exc).__name__,
                exc,
            )

    if not frames:
        return pd.DataFrame()

    data = pd.concat(frames, axis=1, sort=True) if len(frames) > 1 else frames[0]

    # A batch can partially answer. Retry only the new symbols that did not
    # appear in that response; never turn this into a 750-symbol refresh.
    returned = _cached_symbols(data)
    missing = [
        symbol for symbol in symbols
        if normalise_symbol(symbol) not in returned
    ]
    for symbol in missing:
        ticker = (
            symbol + ".NS"
            if not str(symbol).upper().endswith(".NS")
            else str(symbol)
        )
        try:
            retry = yf.download(
                ticker,
                period=period,
                progress=False,
                threads=False,
                auto_adjust=True,
            )
            if retry is not None and not retry.empty:
                if retry.index.tz is not None:
                    retry.index = retry.index.tz_localize(None)
                if isinstance(retry.columns, pd.MultiIndex):
                    # yfinance's default group_by="column" puts a single
                    # ticker's columns in (Price, Ticker) order, so the LAST
                    # level is the ticker, not the field. Find the level that
                    # actually carries the field names.
                    lvl = _field_level(retry.columns)
                    fields = list(retry.columns.get_level_values(
                        lvl if lvl is not None else -1
                    ))
                else:
                    fields = list(retry.columns)
                retry.columns = pd.MultiIndex.from_product(
                    [[normalise_symbol(symbol)], fields],
                    names=["Ticker", "Price"],
                )
                data = pd.concat([data, retry], axis=1, sort=True)
                logger.info("Recovered new price-cache symbol %s on individual retry.", symbol)
        except Exception as exc:
            logger.warning(
                "Individual full-history retry failed for new symbol %s (%s): %s",
                symbol,
                type(exc).__name__,
                exc,
            )

    if data.index.tz is not None:
        data.index = data.index.tz_localize(None)
    if data.index.duplicated().any():
        data = data[~data.index.duplicated(keep="last")]

    if isinstance(data.columns, pd.MultiIndex):
        tickers = [normalise_symbol(value) for value in data.columns.get_level_values(0)]
        prices = list(data.columns.get_level_values(1))
        names = data.columns.names if data.columns.names else ["Ticker", "Price"]
        data.columns = pd.MultiIndex.from_arrays([tickers, prices], names=names)
    else:
        data.columns = [normalise_symbol(value) for value in data.columns]

    return data.dropna(how="all")


def _fetch_incremental_updates(
    symbols: Sequence[str], last_cached_date: date, heal_days: int
) -> pd.DataFrame | None:
    """Ask the vendor for the sessions after the cache -- and, healing, before it.

    The start date is INCLUSIVE of the last cached session when that session is
    still open, so today's partial row is re-requested and its later values
    replace the earlier ones (the merge keeps the vendor's value where it has
    one). Asking from the following day instead is what froze the price at
    whatever minute the row was first written.
    """
    start_date = pd.Timestamp(last_cached_date)
    if session_is_complete(last_cached_date):
        start_date += pd.Timedelta(days=1)
    if heal_days > 0:
        # Reach back over settled history too, so a close the vendor filled in
        # after the fact is actually asked for.
        start_date = min(
            start_date,
            pd.Timestamp(last_cached_date) - pd.Timedelta(days=heal_days),
        )
        metrics.note("price_heal_days", int(heal_days))
        metrics.note("price_heal_from", str(start_date.date()))
    yf_tickers = [
        s + ".NS" if not s.upper().endswith(".NS") else s
        for s in symbols
    ]
    metrics.note("price_path", "cache_incremental")
    return _download_range(yf_tickers, start_date)


def _count_true_cells(mask: pd.DataFrame) -> int:
    """Count truthy cells safely, including pandas nullable booleans."""
    return int(mask.fillna(False).to_numpy(dtype=bool).sum())


def _merge_and_save_cache(cached: pd.DataFrame, new_data: pd.DataFrame) -> pd.DataFrame:
    """Fold the vendor's answer into the cache, cell by cell, and persist it.

    Labels FIRST, then the concat. yfinance says "INDIGO.NS" and the cache says
    "INDIGO", so joining them while they still disagree unions the two into
    separate columns per series; renaming afterwards just collapses the labels
    and leaves the frame duplicated.

    Then merge CELL BY CELL over the overlap, not row by row. keep="last" on a
    duplicated date takes the vendor's whole row, including the cells where it
    sent nothing -- one rate-limited ticker in a batch therefore erased a close
    the cache already held, and the append-only path never asked for that date
    again, so the hole was permanent. The 572 interior gaps measured in the
    published snapshot are this, five partial fetches deep. combine_first keeps
    the vendor's value wherever it HAS one (so a revised close, or a restated
    split-adjusted history, still wins) and falls back to the cache where it
    does not.
    """
    # Clean timezone
    if new_data.index.tz is not None:
        new_data.index = new_data.index.tz_localize(None)
    if cached.index.tz is not None:
        cached.index = cached.index.tz_localize(None)

    cached = _normalise_ticker_level(cached)
    new_data = _normalise_ticker_level(new_data)

    overlap = cached.index.intersection(new_data.index)
    if len(overlap):
        healed = new_data.loc[overlap].combine_first(cached.loc[overlap])
        # The frames can carry nullable/object-backed cells after a
        # yfinance merge. Their boolean mask can therefore contain pandas
        # NA values; reducing that object array with sum() can produce float
        # NaN, and int(NaN) aborts the entire nightly sync. This is telemetry
        # only: never let the repair counter make a valid merge fail.
        repaired_mask = cached.loc[overlap].isna() & healed.notna()
        repaired = _count_true_cells(repaired_mask)
        if repaired:
            metrics.note("price_cells_repaired", repaired)
            logger.info(
                "Backfilled %d previously missing price cells across "
                "%d overlapping sessions.", repaired, len(overlap),
            )
        combined = pd.concat(
            [cached.drop(index=overlap), healed,
             new_data.drop(index=overlap)],
            axis=0,
        )
    else:
        combined = pd.concat([cached, new_data], axis=0)
    if combined.index.duplicated().any():
        combined = combined[~combined.index.duplicated(keep="last")]
    combined = _coalesce_duplicate_columns(combined)
    combined = combined.sort_index()
    # heal_days skips the download gate on purpose, so this is the only thing
    # standing between a healing run and an in-progress session landing in the
    # cache.
    combined = _drop_phantom_sessions(_drop_unsettled_rows(combined))

    try:
        combined.to_parquet(PRICES_FILE, compression="snappy")
        logger.info(
            f"Price cache updated incrementally: {len(combined)} rows ({len(combined.columns)} series)"
        )
    except Exception as e:
        logger.warning(f"Price cache save failed (incremental): {e}")
    return combined


def fetch_price_history(
    symbols: Sequence[str],
    period: str = "2y",
    force_refresh: bool = False,
    heal_days: int = 0,
) -> pd.DataFrame:
    """Fetch daily OHLCV data for symbols with resilient caching and incremental updates.

    Caches data in PRICES_FILE (Snappy parquet). If the cache exists and already contains
    rows up to the most recent close, returns the cache immediately.

    ``heal_days`` re-requests that many calendar days of ALREADY CACHED history
    alongside the new sessions, and merges the answer cell by cell rather than
    row by row. It exists because the incremental path is append-only: it asks
    from the last cached date forward, so a close the vendor fills in LATER --
    Yahoo routinely backfills an Indian symbol days after the session -- is
    never requested again and the hole is permanent.

    Production measured 572 such holes across 337 symbols in the published
    snapshot, clustered on five dates where 11-18% of the universe went missing
    at once. That shape is a partial download failure, not 337 independent
    events, and every one of them was frozen in by an append-only top-up.

    It costs nothing extra in requests -- the same single ``yf.download`` call
    simply starts earlier -- so it belongs to the nightly job, where nobody is
    waiting. Production leaves it at 0 and serves the healed snapshot.
    """
    if not symbols:
        return pd.DataFrame()

    # Seed an empty cache from the published snapshot before deciding anything
    # else. Hooking in HERE rather than adding a new branch means every path
    # below is unchanged: once the file exists, the cache is either fresh or
    # the incremental path tops it up with the few sessions published since.
    # A failed seed is a no-op, so the worst case is exactly the old behaviour.
    if not force_refresh and not os.path.exists(PRICES_FILE):
        from src.loaders.price_store import seed_price_cache_from_snapshot

        seed_price_cache_from_snapshot()


    # ── 1. Load existing cache if present ────────────────────────────────────
    if not force_refresh and os.path.exists(PRICES_FILE):
        cached = _read_local_price_cache()

        if cached is not None and not cached.empty:
            # A newly arrived NSE constituent is the one case where the
            # incremental path cannot work: there is no last cached date for
            # that symbol to start from. Acquire its full available history
            # before the ordinary freshness/incremental gate. Existing symbols
            # continue through exactly the same path as before.
            missing_symbols = _new_cache_symbols(symbols, cached)
            if missing_symbols:
                new_history = _download_full_symbol_history(
                    missing_symbols, period
                )
                if new_history is not None and not new_history.empty:
                    cached = _merge_and_save_cache(cached, new_history)
                    metrics.note(
                        "price_new_symbols_acquired",
                        len(_cached_symbols(cached).intersection(missing_symbols)),
                    )
                else:
                    logger.warning(
                        "No full history returned for new price-cache symbols: %s",
                        ", ".join(missing_symbols[:20]),
                    )

            last_cached_date = cached.index[-1].date()
            # Indian market date, not the server's, throughout -- see
            # src/core/market_time. The two notions of "today" used to sit
            # in this one branch and disagreed for the 5h30m each day when
            # UTC is still on the previous calendar day.
            if _cache_is_current(last_cached_date):
                logger.info(f"Price cache up-to-date: {len(cached.columns)} series")
                metrics.note("price_path", "cache_fresh")
                metrics.note("price_series_returned", len(cached.columns))
                _note_price_as_of(cached)
                return cached

            # Nothing to ASK FOR yet. _cache_is_current above asks whether
            # the cache is final; this asks whether the vendor could even
            # answer, and the two differ for most of every day. At 06:43 IST
            # the cache holding yesterday's close is not "current" -- today
            # is a trading day and today's bar is missing -- but today's
            # session has not opened, so the request that follows costs 25
            # seconds of a reader's cold start to be told nothing. See
            # DOWNLOAD_SETTLES in src/core/market_time.
            #
            # heal_days skips this gate deliberately: a healing run is not
            # after the newest session, it is after the ones already held.
            if not heal_days:
                target = last_downloadable_session()
                if target is not None and last_cached_date >= target:
                    logger.info(
                        "Price cache holds the last settled session (%s); "
                        "next bar is not downloadable yet, serving cache "
                        "(%d series).",
                        last_cached_date, len(cached.columns),
                    )
                    metrics.note("price_path", "cache_pre_settle")
                    metrics.note("price_series_returned", len(cached.columns))
                    _note_price_as_of(cached)
                    return cached

            new_data = _fetch_incremental_updates(symbols, last_cached_date, heal_days)

            if new_data is not None and not new_data.empty:
                combined = _merge_and_save_cache(cached, new_data)
                _note_price_as_of(combined)
                return combined
            else:
                # Yahoo had nothing to add. Before the close that is the
                # normal answer; days behind the last session it means the
                # provider is refusing this host, and the old code simply
                # returned the same frame every hour for as long as the
                # container lived. The daily snapshot is rebuilt by a job
                # Yahoo does answer, so it is the way out.
                recovered = _recover_stale_cache(last_cached_date)
                if recovered is not None:
                    _note_price_as_of(recovered)
                    return recovered
                logger.info("No new price data available from Yahoo Finance; returning existing cache.")
                _note_price_as_of(cached)
                return cached

    # ── 2. Full download fallback (cache missing or forced refresh) ──────────
    yf_symbols = [s + ".NS" if not s.upper().endswith(".NS") else s for s in symbols]
    logger.info(
        f"Downloading full price history for {len(yf_symbols)} stocks (period={period})…"
    )

    metrics.note("price_path", "full_download")
    metrics.note("price_symbols_requested", len(yf_symbols))
    BATCH_SIZE = 100
    all_batches: list[pd.DataFrame] = []
    for batch_start in range(0, len(yf_symbols), BATCH_SIZE):
        batch = yf_symbols[batch_start : batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(yf_symbols) + BATCH_SIZE - 1) // BATCH_SIZE
        logger.debug(f"Downloading batch {batch_num}/{total_batches} ({len(batch)} tickers)")
        metrics.incr("price_batches_attempted")
        try:
            batch_data = yf.download(
                batch,
                period=period,
                progress=False,
                group_by="ticker",
                threads=True,
                auto_adjust=True,
            )
            if batch_data is not None and not batch_data.empty:
                all_batches.append(batch_data)
            else:
                metrics.incr("price_batches_empty")
        except Exception as e:
            metrics.incr("price_batch_errors")
            logger.warning(f"Batch {batch_num} error: {e}")
        if batch_start + BATCH_SIZE < len(yf_symbols):
            time.sleep(1.2)

    if not all_batches:
        logger.error("All price download batches returned empty")
        return pd.DataFrame()

    data = pd.concat(all_batches, axis=1) if len(all_batches) > 1 else all_batches[0]

    # Retry missing symbols individually with exponential backoff
    if isinstance(data.columns, pd.MultiIndex) and not data.empty:
        got = set(data.columns.get_level_values(0).unique())
        missing = [t for t in yf_symbols if t not in got]
        metrics.note("price_missing_after_batches", len(missing))
        if missing:
            logger.info(f"Retrying {len(missing)} missing tickers individually…")
            for tkr in missing:
                metrics.incr("price_individual_retries")
                try:
                    s = yf.download(tkr, period=period, progress=False, threads=False, auto_adjust=True)
                    if not s.empty:
                        metrics.incr("price_individual_retry_recovered")
                        if s.index.tz is not None:
                            s.index = s.index.tz_localize(None)
                        if isinstance(s.columns, pd.MultiIndex):
                            lvl0 = s.columns.get_level_values(0).tolist()
                            lvl1 = s.columns.get_level_values(1).tolist()
                            price_fields = {
                                "Open",
                                "High",
                                "Low",
                                "Close",
                                "Adj Close",
                                "Volume",
                            }
                            if all(v in price_fields for v in lvl1):
                                mi = pd.MultiIndex.from_arrays(
                                    [[tkr] * len(lvl1), lvl1], names=["Ticker", "Price"]
                                )
                            else:
                                mi = pd.MultiIndex.from_arrays(
                                    [[tkr] * len(lvl0), lvl0], names=["Ticker", "Price"]
                                )
                            s.columns = mi
                        else:
                            mi = pd.MultiIndex.from_product(
                                [[tkr], s.columns], names=["Ticker", "Price"]
                            )
                            s.columns = mi
                        data = pd.concat([data, s], axis=1)
                except Exception as ex:
                    logger.debug(f"Failed retry for {tkr}: {ex}")

    if data.empty:
        return data

    # Clean timezones and deduplicate index
    if data.index.tz is not None:
        data.index = data.index.tz_localize(None)
    if data.index.duplicated().any():
        data = data[~data.index.duplicated(keep="last")]

    # Normalize column names
    if isinstance(data.columns, pd.MultiIndex):
        tickers = [
            normalise_symbol(c)
            for c in data.columns.get_level_values(0)
        ]
        prices = list(data.columns.get_level_values(1))
        names = (
            data.columns.names
            if data.columns.names and data.columns.names[0]
            else ["Ticker", "Price"]
        )
        data.columns = pd.MultiIndex.from_arrays([tickers, prices], names=names)
    else:
        data.columns = [normalise_symbol(c) for c in data.columns]

    data = data.dropna(how="all")

    # A FULL REFRESH MUST NOT BE ABLE TO LOSE HISTORY.
    #
    # This path used to write straight over the cache. That makes the widest
    # download in the system the only one with no protection: a batch of 100
    # that comes back empty, or a ticker that answers with some sessions
    # missing, replaced good stored history with a worse copy and nothing
    # noticed. The retry loop above only catches tickers absent ENTIRELY --
    # a partial series looks like a successful fetch.
    #
    # That was survivable while the weekly FORCE_FULL run published nothing,
    # because the damage stayed in a cache nobody read. It is not survivable
    # now that the run publishes the snapshot production seeds from: one bad
    # Friday would hand every reader a thinner history than the one it
    # replaced, and the append-only daily path could never fill it back in.
    #
    # So the vendor's answer wins wherever it HAS a value -- which is what
    # makes a restatement land, the whole point of a full refresh -- and the
    # cache survives wherever it does not. The merge is the same one the
    # incremental path uses, for the same reason.
    if os.path.exists(PRICES_FILE):
        try:
            previous = pd.read_parquet(PRICES_FILE)
            previous = _drop_future_rows(_normalise_ticker_level(previous))
            if not previous.empty:
                merged = data.combine_first(previous)
                rescued_mask = data.reindex_like(merged).isna() & merged.notna()
                # Same nullable-mask hardening as the incremental merge above:
                # this counter is diagnostic and must never make a successful
                # full-refresh reconciliation fail.
                rescued = _count_true_cells(rescued_mask)
                lost_cols = len(set(previous.columns) - set(data.columns))
                lost_rows = len(previous.index.difference(data.index))
                if rescued or lost_cols or lost_rows:
                    metrics.note("price_full_refresh_cells_rescued", rescued)
                    metrics.note("price_full_refresh_series_missing", lost_cols)
                    metrics.note("price_full_refresh_rows_missing", lost_rows)
                    logger.warning(
                        "Full refresh came back thinner than the cache it "
                        "replaces: %d series and %d sessions absent, %d cells "
                        "preserved from the previous copy. A wholesale "
                        "overwrite would have destroyed them.",
                        lost_cols, lost_rows, rescued,
                    )
                data = merged.sort_index()
        except Exception as exc:
            # Never let the guard cost the refresh. Writing the fresh download
            # unmerged is the old behaviour, which is worse but not broken.
            logger.warning(
                "Could not merge the full refresh with the existing cache "
                "(%s: %s); writing the download as-is.",
                type(exc).__name__, exc,
            )

    data = _drop_phantom_sessions(_drop_unsettled_rows(data))

    metrics.note("price_series_returned", len(data.columns))
    _note_price_as_of(data)
    # Save to parquet cache
    try:
        data.to_parquet(PRICES_FILE, compression="snappy")
        logger.info(f"Price cache saved: {len(data)} rows ({len(data.columns)} series)")
    except Exception as e:
        logger.warning(f"Price cache save failed: {e}")

    return data


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_benchmark_history(
    period: str = "2y", symbol: str = BENCHMARK_SYMBOL
) -> pd.Series:
    """Return a benchmark price series, the V1 benchmark by default."""
    try:
        data = yf.download(
            symbol, period=period, progress=False, threads=False,
            auto_adjust=True,
        )
        if data is None or data.empty:
            return pd.Series(dtype=float, name=symbol)
        if data.index.tz is not None:
            data.index = data.index.tz_localize(None)
        if isinstance(data.columns, pd.MultiIndex):
            close_df = _extract_field(data, ["Close", "Adj Close", "AdjClose"])
            series = close_df.iloc[:, 0] if not close_df.empty else data.iloc[:, 0]
        else:
            series = data["Close"] if "Close" in data.columns else data.iloc[:, 0]
        series = pd.to_numeric(series, errors="coerce").dropna()
        series.name = symbol
        return series
    except Exception as e:
        logger.warning(f"Failed to fetch benchmark {symbol}: {e}")
        return pd.Series(dtype=float, name=symbol)


@st.cache_data(show_spinner=False, ttl=3600)
def get_market_regime(benchmark_symbol: str = BENCHMARK_SYMBOL) -> RegimeData:
    """
    Computes market regime by comparing benchmark index price with its 200 DMA.
    Reuses fetch_benchmark_history (2y window, already cached) so no second
    HTTP round-trip is needed at cold start.
    """
    try:
        # The argument is honoured rather than decorative: this read
        # BENCHMARK_SYMBOL internally, so asking for any other index
        # silently returned the Nifty 500 regime under that index's name.
        close_s = fetch_benchmark_history(period="2y", symbol=benchmark_symbol)

        if close_s is None or close_s.empty:
            return RegimeData(
                status=MarketRegime.UNKNOWN,
                current_price=0.0,
                dma_200=0.0,
                distance_pct=0.0,
            )

        close_s = pd.to_numeric(close_s, errors="coerce").dropna()
        price = float(close_s.iloc[-1])
        dma = float(close_s.rolling(200, min_periods=100).mean().iloc[-1])
        dist = ((price - dma) / dma * 100) if dma > 0 else 0.0
        status = MarketRegime.BULLISH if price >= dma else MarketRegime.BEARISH

        return RegimeData(
            status=status,
            current_price=price,
            dma_200=dma,
            distance_pct=dist,
        )
    except Exception as e:
        logger.warning(f"Failed to compute market regime: {e}")
        return RegimeData(
            status=MarketRegime.UNKNOWN,
            current_price=0.0,
            dma_200=0.0,
            distance_pct=0.0,
        )
