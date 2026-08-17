import pandas as pd
from src.ui.ema_utils import count_above_ema

def test_count_above_ema_normal_series():
    df = pd.DataFrame({"Above 50 EMA": ["True", "False", "✅", "1"]})
    assert count_above_ema(df) == 3

def test_count_above_ema_duplicate_columns():
    df = pd.DataFrame([["False", "True"], ["False", "False"]], columns=["Above 50 EMA", "Above 50 EMA"])
    assert count_above_ema(df) == 1

def test_count_above_ema_missing_column():
    assert count_above_ema(pd.DataFrame({"Symbol": ["A", "B"]})) == 0
