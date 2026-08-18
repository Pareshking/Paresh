"""An empty ranking must explain itself instead of crashing a downstream tab.

Production served a run where the engine ranked 0 of 750 stocks. Nothing said
so: the header showed 0, twelve tabs rendered empty frames, and the Qualified
tab then died in Arrow --
``TypeError: operation 'and_' not supported for dtype 'str' with dtype
'float64'`` -- because .map() hands back the SOURCE dtype when there are no
rows to infer from. The mask fix is in test_qualification_mask.py; this covers
the other half, which is saying why the ranking was empty at all.
"""
import numpy as np
import pandas as pd

from src.engine.momentum import MomentumEngine


def _prices(rows: int, cols: int = 3) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=rows, freq="B")
    base = np.arange(rows, dtype=float) + 100.0
    return pd.DataFrame(
        {f"S{i}": base * (1.0 + 0.01 * i) for i in range(cols)}, index=idx
    )


def _index_info(cols: int = 3) -> pd.DataFrame:
    return pd.DataFrame({
        "Symbol": [f"S{i}" for i in range(cols)],
        "Industry": ["Test"] * cols,
    })


def test_short_history_yields_empty_ranking_with_a_reason():
    """Below the 63-observation minimum nothing can be scored."""
    calc = MomentumEngine(_prices(rows=20))
    rank_df = calc.get_rankings(_index_info(), pd.Series(dtype=float))

    assert rank_df.empty
    diag = calc.ranking_diagnostics
    assert diag["universe"] == 3
    assert diag["with_price_history"] == 3       # prices were there ...
    assert diag["meeting_min_observations"] == 0  # ... just not enough of them
    assert diag["scored"] == 0


def test_healthy_history_reports_a_full_ranking():
    calc = MomentumEngine(_prices(rows=300))
    rank_df = calc.get_rankings(_index_info(), pd.Series(dtype=float))

    diag = calc.ranking_diagnostics
    assert diag["universe"] == 3
    assert diag["meeting_min_observations"] == 3
    assert diag["scored"] == len(rank_df) > 0


def test_diagnostics_exist_before_any_ranking_runs():
    """app.py reads this attribute defensively; it must always be present."""
    assert MomentumEngine(_prices(rows=300)).ranking_diagnostics == {}
