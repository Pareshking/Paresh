import pandas as pd

from src.core.history_loading import materialize_deep_history


def test_deep_history_materializes_only_requested_symbols():
    source = pd.DataFrame(
        {"AAA": [1.0, 2.0], "BBB": [3.0, 4.0], "CCC": [5.0, 6.0]},
        index=pd.date_range("2026-01-01", periods=2),
    )
    result = materialize_deep_history(source, ["BBB", "CCC"])
    assert list(result.columns) == ["BBB", "CCC"]
    assert result.equals(source[["BBB", "CCC"]])
    result.iloc[0, 0] = 999.0
    assert source.iloc[0, 1] == 3.0


def test_deep_history_returns_none_when_no_requested_symbol_exists():
    source = pd.DataFrame({"AAA": [1.0]})
    assert materialize_deep_history(source, ["MISSING"]) is None
