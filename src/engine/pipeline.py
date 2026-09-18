"""The ranking pipeline, in one place, so two callers cannot drift apart.

The app runs this behind ``@st.cache_data`` wrappers; the nightly sync job runs
it bare, to precompute the same table before anyone is waiting for it. If the
two ever compute the ranking differently, the precomputed table is worse than
useless -- it is a WRONG answer served fast, and nothing downstream can tell.
So neither of them owns the arithmetic. Both call these two functions.

The split is not cosmetic. ``build_engine`` is the expensive half: five
calendar-period passes plus every weight-independent signal column (ATR, EMA,
52-week high, ATH, drawdown, persistence), about 30 seconds over 750 symbols on
a shared Streamlit Cloud core. ``rank_with_weights`` is the cheap half: a
weighted sum of z-scores already computed, plus the final table. Keeping them
apart is what lets a weight slider re-rank without re-deriving a single signal.
"""

from __future__ import annotations

import hashlib

import pandas as pd

from src.engine.calendar_momentum import _apply_weight_composite, _compute_period_z_scores
from src.engine.momentum import MomentumEngine

# Bump when a change alters the numbers this pipeline produces. A precomputed
# table recorded under a different version is discarded rather than trusted:
# the whole contract is that the artifact equals what the engine would have
# computed, and a changed engine breaks exactly that.
_PIPELINE_TAG: str = "v4_calendar_periods"


def _settings_digest() -> str:
    """Fingerprint the CONSTANTS that decide the numbers, not just the tag.

    A hand-maintained version string only invalidates the artifact when someone
    remembers to bump it, and the case where they forget is the dangerous one.
    Change MOMENTUM_MONTHS from [1,3,6,9,12] to [1,3,6,12,18] and deploy: the
    running app scores five different horizons immediately, while the published
    table is still last night's, computed over the old ones. Every other field
    in the contract -- the price frame, the universe, the weights -- would still
    match, so production would serve that table as though it described the new
    configuration. The screener would show a ranking for horizons nobody is
    running, and nothing anywhere would say so.

    The lookback WEIGHTS are not here: they are a reader's setting, travel in
    the contract as their own field, and change per session. These are the
    build-time constants behind them, which change only with a deploy.
    """
    from src.core.config import HIGH_52W_MIN_OBSERVATIONS, MOMENTUM_MONTHS
    from src.engine.calendar_momentum import ANCHOR_STALENESS_LIMIT
    from src.engine.momentum import MIN_OBSERVATIONS

    payload = "|".join(
        str(x) for x in (
            list(MOMENTUM_MONTHS),
            HIGH_52W_MIN_OBSERVATIONS,
            MIN_OBSERVATIONS,
            ANCHOR_STALENESS_LIMIT,
        )
    )
    return hashlib.md5(payload.encode()).hexdigest()[:8]


def pipeline_version() -> str:
    """The tag, plus a digest of the settings the tag is supposed to track."""
    return f"{_PIPELINE_TAG}_{_settings_digest()}"


# Module-level for the callers that read it as a constant. Both sides of the
# contract import THIS, so a config edit invalidates yesterday's artifact on the
# next process start without anyone having to notice.
PIPELINE_VERSION: str = pipeline_version()


def price_fingerprint(df: pd.DataFrame | None) -> str:
    """Memo key for the quant engine: shape, last session, AND last values.

    The values matter. Within a trading day the frame's last date and shape
    never change -- only the numbers in that final row do, as the session moves
    on. Keyed on shape and date alone, the engine kept returning the ranking it
    computed from the morning's prices while the loader underneath it went on
    refreshing them, so CMP, Score, Rank and every derived column were frozen
    on a page whose header dated them today.

    Hashing the last row is enough: everything before it is settled history,
    and a change there necessarily changes the length or the date too.

    This is also the precomputed table's validity contract, which is why it
    lives here rather than in app.py: the nightly job stamps the artifact with
    the fingerprint of the frame it ranked, and production only trusts the
    artifact when its own frame fingerprints identically.
    """
    if df is None or df.empty:
        return "empty"
    try:
        last = pd.to_numeric(df.iloc[-1], errors="coerce").to_numpy(dtype="float64")
        digest = hashlib.md5(last.tobytes()).hexdigest()[:12]
        return f"{df.index[-1]}_{df.shape[0]}x{df.shape[1]}_{digest}"
    except Exception:
        return "unknown"


def symbols_fingerprint(symbols) -> str:
    key = ",".join(sorted(str(s).upper() for s in symbols))
    return hashlib.md5(key.encode()).hexdigest()[:12]


# ── Which session is complete enough to rank on ──────────────────────────────
#
# The engine takes each symbol's CLOSING price as a real observation -- p1 is
# read straight from the frame, never forward-filled, deliberately (see
# calendar_momentum). So a symbol with no print on the final session scores NaN
# across every horizon and leaves the table entirely.
#
# That is correct per symbol and wrong for the universe, because Yahoo
# publishes an Indian session over about two days. Measured on the live
# snapshot for 2026-09-17: 20% of the universe at 23:30 IST that night, 50% by
# the next morning, 100% a day later. Ranking on that session does not produce
# a fresher table, it produces a table of whichever half the vendor happened to
# publish first -- 378 names instead of 750, selected by vendor latency.
#
# Until 2026-09-18 this never showed, because the coverage floor deleted the
# thin session outright and the ranking landed on the previous one by accident.
# Now that a real session is correctly KEPT in the history, the ranking has to
# choose its own date on purpose.
#
# History and ranking date are separate questions. The frame keeps every real
# session -- returns, charts and the archive need them -- while the engine
# stops at the newest session the vendor has actually finished.

RANKING_COVERAGE_FLOOR: float = 0.90
MAX_UNRANKED_TAIL: int = 5


def last_ranked_session(
    adj_close: pd.DataFrame,
    floor: float = RANKING_COVERAGE_FLOOR,
    max_back: int = MAX_UNRANKED_TAIL,
) -> int | None:
    """Position of the newest session complete enough to rank on.

    Coverage is judged against the RECENT norm, not an absolute count, because
    absolute coverage falls off legitimately as you go back: a stock that
    listed in 2025 is NaN for every session before it, so an old row can sit at
    60% while being perfectly complete. The reference is the best coverage in
    the trailing month, which on any healthy frame is a finished session.

    Returns None -- meaning change nothing -- when no session in the last
    ``max_back`` qualifies. Walking back further would start hiding real
    sessions from the ranking to chase a threshold, which is the failure this
    whole area already had once.
    """
    if adj_close is None or adj_close.empty or adj_close.shape[1] == 0:
        return None
    covered = adj_close.notna().sum(axis=1).to_numpy()
    n = len(covered)
    if n == 0:
        return None
    reference = float(covered[max(0, n - 21):].max())
    if reference <= 0:
        return None
    need = floor * reference
    for back in range(0, min(max_back, n - 1) + 1):
        if covered[n - 1 - back] >= need:
            return n - 1 - back
    return None


def ranking_as_of(adj_close: pd.DataFrame) -> str:
    """The date the ranking actually describes, as the table will be labelled.

    Callers must take the as-of date from here rather than from the frame's
    last row, or the label and the table disagree -- the snapshot would be
    stamped with a session the engine never scored.
    """
    try:
        pos = last_ranked_session(adj_close)
        if pos is None:
            pos = len(adj_close.index) - 1
        return str(pd.DatetimeIndex(adj_close.index)[pos].date())
    except Exception:
        return ""


def _trim_to_ranked_session(*frames):
    """Cut every frame to the ranking date. Shape-preserving and idempotent."""
    ref = next((f for f in frames if isinstance(f, pd.DataFrame) and not f.empty), None)
    if ref is None:
        return frames, None
    pos = last_ranked_session(ref)
    if pos is None or pos >= len(ref.index) - 1:
        return frames, None
    cutoff = ref.index[pos]
    out = tuple(
        f.loc[:cutoff] if isinstance(f, pd.DataFrame) and not f.empty else f
        for f in frames
    )
    return out, cutoff


def build_engine(
    adj_close: pd.DataFrame,
    high_prices: pd.DataFrame,
    low_prices: pd.DataFrame,
    close_prices: pd.DataFrame,
    volume_data: pd.DataFrame,
    idx_info: pd.DataFrame,
    market_caps: pd.Series,
    corporate_actions: list | None = None,
) -> MomentumEngine:
    """The expensive half: everything that does not depend on the weights."""
    (adj_close, high_prices, low_prices, close_prices, volume_data), cutoff = (
        _trim_to_ranked_session(
            adj_close, high_prices, low_prices, close_prices, volume_data
        )
    )
    if cutoff is not None:
        from src.core.logger import logger

        logger.info(
            "Ranking as of %s: the newer session(s) are still filling in and "
            "would drop every symbol the vendor has not published yet.",
            str(cutoff)[:10],
        )
    calc = MomentumEngine(
        adj_close,
        high_df=high_prices,
        low_df=low_prices,
        close_df=close_prices,
        volume_df=volume_data,
        weights=[0.2] * 5,
        corporate_actions=corporate_actions,
    )
    _compute_period_z_scores(calc)
    calc._precompute_signals(idx_info, market_caps, close_prices, high_prices)
    return calc


# Columns that need a real intraday high and low. Without them true range
# collapses to |close - prev close|, measured at 0.47x true ATR across 750
# symbols -- so a 2xATR stop would sit 53% tighter than the same column shows
# on Yahoo data. A stop loss silently half its intended width is more dangerous
# than an absent one, so these are dropped rather than approximated.
_INTRADAY_ONLY_COLUMNS: tuple[str, ...] = (
    "ATR", "ATR %", "Stop Loss", "Chandelier Exit",
)


def rank_with_weights(
    calc: MomentumEngine,
    weights,
    idx_info: pd.DataFrame,
    market_caps: pd.Series,
    close_prices: pd.DataFrame,
    high_prices: pd.DataFrame,
    intraday: bool = True,
):
    """The cheap half: apply weights to z-scores already computed, then rank."""
    # The engine was built on the trimmed frames; these two are handed straight
    # to get_rankings, so they have to stop on the same session or the table
    # reads its prices one row past everything it scored.
    (close_prices, high_prices), _ = _trim_to_ranked_session(close_prices, high_prices)
    calc.weights = list(weights)
    _apply_weight_composite(calc, list(weights))
    rank_df = calc.get_rankings(
        idx_info,
        market_caps,
        close_prices_df=close_prices,
        high_prices_df=high_prices,
    )
    if not intraday and rank_df is not None and not rank_df.empty:
        drop = [c for c in _INTRADAY_ONLY_COLUMNS if c in rank_df.columns]
        if drop:
            rank_df = rank_df.drop(columns=drop)

    return calc, rank_df
