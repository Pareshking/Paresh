from src.core.universe_reconciliation import reconcile_symbols


def test_reconcile_symbols_identifies_missing_and_extra():
    result = reconcile_symbols(
        expected=["RELIANCE", "HEGAM", "TCS"],
        actual=["RELIANCE", "TCS", "OLDNAME"],
    )
    assert result["expected_count"] == 3
    assert result["published_count"] == 3
    assert result["missing"] == ["HEGAM"]
    assert result["extra"] == ["OLDNAME"]
    assert result["duplicates"] == []


def test_reconcile_symbols_excludes_dummy_without_aliasing_real_symbols():
    result = reconcile_symbols(
        expected=["HEGAM", "DUMMYHEG"],
        actual=["HEGAM", "DUMMYHEG", "HEG"],
    )
    assert result["expected_count"] == 1
    assert result["published_count"] == 2
    assert result["missing"] == []
    assert result["extra"] == ["HEG"]
    assert result["duplicates"] == []


def test_reconcile_symbols_detects_duplicate_published_symbol():
    result = reconcile_symbols(
        expected=["HEGAM", "TCS"],
        actual=["HEGAM", "HEGAM", "TCS"],
    )
    assert result["missing"] == []
    assert result["extra"] == []
    assert result["duplicates"] == ["HEGAM"]


def test_too_new_names_are_listed_apart_from_missing():
    # S215: a new listing under 63 sessions is not a loss; a missing name still is.
    result = reconcile_symbols(
        expected=["TCS", "ZETWERK", "HEGAM"],
        actual=["TCS"],
        too_new=["ZETWERK", "NOTEXPECTED"],
    )
    assert result["missing"] == ["HEGAM"]
    assert result["new_listings"] == ["ZETWERK"]


def test_too_new_to_rank_counts_from_first_price_not_prices_held():
    import numpy as np
    import pandas as pd

    from src.engine.momentum import too_new_to_rank

    idx = pd.bdate_range("2026-01-01", periods=100)
    frame = pd.DataFrame(index=idx, data={
        "OLD": 1.0,                                         # full history: ranked
        "NEW": [np.nan] * 60 + [1.0] * 40,                  # listed 40 rows ago: too new
        "HOLEY": [1.0] * 5 + [np.nan] * 90 + [1.0] * 5,     # old, 10 prices held: a real gap, not new
        "NONE": np.nan,                                     # no price at all: a real gap
    })
    assert too_new_to_rank(frame) == ["NEW"]
    assert too_new_to_rank(pd.DataFrame()) == []
