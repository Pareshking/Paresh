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


def rank_with_weights(
    calc: MomentumEngine,
    weights,
    idx_info: pd.DataFrame,
    market_caps: pd.Series,
    close_prices: pd.DataFrame,
    high_prices: pd.DataFrame,
):
    """The cheap half: apply weights to z-scores already computed, then rank."""
    calc.weights = list(weights)
    _apply_weight_composite(calc, list(weights))
    rank_df = calc.get_rankings(
        idx_info,
        market_caps,
        close_prices_df=close_prices,
        high_prices_df=high_prices,
    )
    return calc, rank_df
