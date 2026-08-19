"""Two engine fixes that a screenshot surfaced.

1. A calendar window's OPENING price was looked up on one exact session, and
   Yahoo holes sessions routinely -- a median of 33 symbols per session in the
   published snapshot, 135 on 2026-07-21. The 1M window anchors on that day, so
   18% of the universe showed "—" for 1M Return and 1M Sharpe while 3M and 6M
   were complete. Nothing was wrong with the download; the anchor was brittle.

2. The cross-section z-score ran as a Python loop over every date. It is a
   matrix operation, and it was the single hottest path in the engine.
"""
import numpy as np
import pandas as pd
import pytest

from src.engine.calendar_momentum import (
    ANCHOR_STALENESS_LIMIT,
    _winsorised_cross_section_z,
)
from src.engine.momentum import MomentumEngine


def _prices(n_days: int = 400, n_syms: int = 12) -> pd.DataFrame:
    idx = pd.bdate_range(end="2026-08-19", periods=n_days)
    rng = np.random.default_rng(11)
    data = {
        f"S{i}": 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.015, n_days)))
        for i in range(n_syms)
    }
    return pd.DataFrame(data, index=idx)


# ── 1. The window anchor ────────────────────────────────────────────────────

def test_a_hole_on_the_anchor_day_no_longer_voids_the_window():
    """The exact failure from the screenshot, reproduced and fixed."""
    prices = _prices()
    eng_full = MomentumEngine(prices)
    full = eng_full.calculate_sharpe_momentum()

    # Punch a hole in one symbol on the session the 1M window opens from.
    holed = prices.copy()
    anchor_day = holed.index[-22]
    holed.loc[anchor_day, "S0"] = np.nan

    eng_holed = MomentumEngine(holed)
    eng_holed.calculate_sharpe_momentum()
    one_month = eng_holed.period_metrics[1]["return"]

    assert pd.notna(one_month["S0"]), (
        "one missing print on the anchor day must not void the whole horizon"
    )
    assert not full.empty


def test_a_symbol_with_no_recent_price_still_scores_nan():
    """The anchor bridges holes; it must not invent a price for a dead stock."""
    prices = _prices()
    prices.iloc[-40:, prices.columns.get_loc("S1")] = np.nan

    eng = MomentumEngine(prices)
    eng.calculate_sharpe_momentum()

    assert pd.isna(eng.period_metrics[1]["return"]["S1"])


def test_the_staleness_limit_is_a_trading_week():
    """Long enough to bridge Yahoo's holes, short enough to stay honest."""
    assert ANCHOR_STALENESS_LIMIT == 5


# ── 2. The vectorised z-score ───────────────────────────────────────────────

def _loop_reference(score: pd.DataFrame) -> pd.DataFrame:
    """The implementation this replaced, kept as the oracle."""
    rows = []
    for _, row in score.iterrows():
        clean = row.dropna()
        if len(clean) < 3 or float(clean.std(ddof=0)) == 0.0:
            rows.append(pd.Series(np.nan, index=score.columns))
            continue
        m, sd = float(clean.mean()), float(clean.std(ddof=0))
        clipped = clean.clip(m - 3.0 * sd, m + 3.0 * sd)
        c_sd = float(clipped.std(ddof=0))
        rows.append(((clipped - float(clipped.mean())) / (c_sd + 1e-12)).reindex(score.columns))
    return pd.DataFrame(rows, index=score.index, columns=score.columns).clip(-3.0, 3.0)


def test_vectorised_z_matches_the_loop_it_replaced():
    rng = np.random.default_rng(3)
    score = pd.DataFrame(
        rng.normal(size=(120, 40)),
        index=pd.bdate_range(end="2026-08-19", periods=120),
        columns=[f"S{i}" for i in range(40)],
    )
    score.iloc[:5] = np.nan                    # warmup rows
    score.iloc[10, :38] = np.nan               # a row with too few observations
    score.iloc[20] = 4.0                       # a row with zero spread
    score.iloc[30, 3] = 500.0                  # an outlier to winsorise

    got = _winsorised_cross_section_z(score)
    want = _loop_reference(score)

    assert ((got.notna()) == (want.notna())).all().all()
    both = got.notna() & want.notna()
    assert np.allclose(got.values[both.values], want.values[both.values], atol=1e-12)


@pytest.mark.parametrize("case", ["all_nan", "too_few", "zero_spread"])
def test_degenerate_rows_stay_nan(case):
    score = pd.DataFrame(np.random.default_rng(5).normal(size=(6, 10)))
    if case == "all_nan":
        score.iloc[2] = np.nan
    elif case == "too_few":
        score.iloc[2, 2:] = np.nan
    else:
        score.iloc[2] = 1.0

    assert _winsorised_cross_section_z(score).iloc[2].isna().all()
