"""scripts/index_symbol_map.py: join a day's bhavcopy tickers to the point-in-time index membership."""
import pytest

from scripts import index_symbol_map as m

H = m.load()


def test_a_rename_is_followed_in_both_directions_on_its_own_dates():
    # ZOMATO became ETERNAL on 2025-04-09; the history files the stock under ETERNAL.
    before = m.bhavcopy_symbols(H, "nifty_50", "2025-03-28")
    after = m.bhavcopy_symbols(H, "nifty_50", "2025-04-10")
    assert before["ZOMATO"] == "ETERNAL" and "ETERNAL" not in before
    assert after["ETERNAL"] == "ETERNAL" and "ZOMATO" not in after


def test_a_multi_hop_rename_chain_resolves_to_the_ticker_of_the_day():
    ledger = {"symbol_changes": {"changes": [
        {"old_symbol": "A", "new_symbol": "B", "last_old_date": "2015-01-01", "first_new_date": "2015-01-02"},
        {"old_symbol": "B", "new_symbol": "C", "last_old_date": "2020-01-01", "first_new_date": "2020-01-02"}]}}
    assert m.symbol_on(ledger, "C", "2014-06-01") == "A"
    assert m.symbol_on(ledger, "C", "2018-06-01") == "B"
    assert m.symbol_on(ledger, "C", "2021-06-01") == "C"
    assert m.symbol_on(ledger, "A", "2021-06-01") == "C"   # an old name in the history still lands on the day's ticker


def test_a_name_with_no_rename_is_unchanged():
    assert m.symbol_on(H, "RELIANCE", "2012-01-02") == "RELIANCE"


@pytest.mark.parametrize("index, size", [("nifty_50", 50), ("nifty_next_50", 50), ("nifty_500", 500)])
def test_sizes_survive_the_mapping(index, size):
    mapping = m.bhavcopy_symbols(H, index, "2015-06-30")
    assert len(mapping) == size


def test_an_index_has_no_answer_before_its_first_record():
    assert m.members(H, "nifty_50", "2009-01-01") is None
    assert m.bhavcopy_symbols(H, "nifty_50", "2009-01-01") is None
    assert m.coverage(H, "nifty_50", "2009-01-01", set())["recorded"] is False


def test_unknown_index_is_an_error_not_an_empty_set():
    with pytest.raises(KeyError):
        m.members(H, "nifty_999", "2020-01-01")


def test_coverage_reports_members_with_no_bhavcopy_row(tmp_path):
    mapping = m.bhavcopy_symbols(H, "nifty_50", "2025-03-28")
    keep = sorted(mapping)[:-2]
    old = tmp_path / "old.csv"
    old.write_text("SYMBOL,SERIES,CLOSE\n" + "\n".join(f"{s},EQ,1" for s in keep) + "\n")
    new = tmp_path / "new.csv"
    new.write_text("TckrSymb,SctySrs\n" + "\n".join(f"{s},EQ" for s in keep) + "\n")
    for path in (old, new):
        rep = m.coverage(H, "nifty_50", "2025-03-28", m.read_bhavcopy_symbols(path))
        assert rep["members"] == 50 and rep["matched"] == 48 and rep["missing"] == sorted(mapping)[-2:]


def test_a_file_without_a_symbol_column_is_rejected(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("NAME,CLOSE\nx,1\n")
    with pytest.raises(ValueError):
        m.read_bhavcopy_symbols(bad)
