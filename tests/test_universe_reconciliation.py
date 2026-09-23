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
