import pandas as pd

from scripts.sync_screener import _validate_current_price_coverage


def test_current_price_coverage_excludes_dummy_symbols():
    closes = pd.DataFrame({"HEGAM": [13.0, 14.0], "DUMMYHEG": [None, None]})
    missing, empty = _validate_current_price_coverage(
        ["HEGAM", "DUMMYHEG"], closes
    )
    assert missing == []
    assert empty == []


def test_current_price_coverage_detects_missing_symbol():
    closes = pd.DataFrame({"HEGAM": [13.0, 14.0]})
    missing, empty = _validate_current_price_coverage(
        ["HEGAM", "REQUIRED"], closes
    )
    assert missing == ["REQUIRED"]
    assert empty == []


def test_current_price_coverage_detects_empty_symbol_column():
    closes = pd.DataFrame({"HEGAM": [13.0, 14.0], "REQUIRED": [None, None]})
    missing, empty = _validate_current_price_coverage(
        ["HEGAM", "REQUIRED"], closes
    )
    assert missing == []
    assert empty == ["REQUIRED"]
