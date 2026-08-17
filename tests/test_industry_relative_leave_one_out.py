import numpy as np
import pandas as pd
from src.engine.momentum import MomentumEngine

def test_industry_relative_is_leave_one_out():
    idx = pd.date_range("2026-01-01", periods=5, freq="D")
    prices = pd.DataFrame({"AAA":[100,101,102,103,104], "BBB":[100,101,102,103,104], "CCC":[100,101,102,103,104]}, index=idx)
    engine = MomentumEngine(prices)
    engine.momentum_scores = pd.DataFrame([[1.0, 2.0, 10.0]] * 5, index=idx, columns=["AAA","BBB","CCC"])
    rank_df = pd.DataFrame({"Symbol":["AAA","BBB","CCC"], "Industry":["X","X","Y"]})
    ranks = engine.calculate_industry_relative(rank_df)
    assert ranks["AAA"] == 2
    assert ranks["BBB"] == 1
    assert ranks["CCC"] == 3

def test_industry_relative_preserves_missing_score_semantics():
    idx = pd.date_range("2026-01-01", periods=3, freq="D")
    prices = pd.DataFrame({"AAA":[100,101,102], "BBB":[100,101,102]}, index=idx)
    engine = MomentumEngine(prices)
    engine.momentum_scores = pd.DataFrame([[1.0, np.nan]] * 3, index=idx, columns=["AAA","BBB"])
    rank_df = pd.DataFrame({"Symbol":["AAA","BBB"], "Industry":["X","X"]})
    ranks = engine.calculate_industry_relative(rank_df)
    assert ranks["AAA"] == 1.5
    assert ranks["BBB"] == 1.5
