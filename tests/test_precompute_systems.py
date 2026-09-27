"""Nano Cap and Combined precompute: one universe, one frame, one file name per system."""

import pandas as pd

from src.loaders import extra_universe_loader as xl
from src.loaders import ranking_store


def _prices(symbols, value, dtype="float64"):
    idx = pd.bdate_range("2026-09-01", periods=3)
    cols = pd.MultiIndex.from_tuples([(s, "Close") for s in symbols])
    return pd.DataFrame(value, index=idx, columns=cols, dtype=dtype)


def _list(symbols, tag):
    return pd.DataFrame({"Symbol": symbols, "Indices": tag})


def test_a_stock_that_left_the_750_is_priced_once_from_the_extra_file():
    # HEG, 2026-09: still in the 750's Yahoo file, now on the Nano Cap list.
    core = _prices(["ABB", "HEG"], 1.0, "float32")
    extra = _prices(["HEG"], 2.0)
    joined = xl.join_prices(core, extra, ["HEG"])
    assert not joined.columns.duplicated().any()
    assert joined[("HEG", "Close")].eq(2.0).all()
    assert joined[("ABB", "Close")].eq(1.0).all()


def test_the_750_alone_is_passed_through_untouched():
    core = _prices(["ABB", "HEG"], 1.0)
    assert xl.join_prices(core, None, []) is core


def test_combined_drops_nano_rows_already_in_the_750_and_splits_by_tag():
    base = _list(["ABB", "TCS"], "NIFTY 500")
    extra = _list(["TCS", "HEG"], xl.xu.SHORT_FORM)
    combined = xl.system_universe("combined", base, extra)
    assert combined["Symbol"].tolist() == ["ABB", "TCS", "HEG"]
    assert xl.split_symbols("combined", combined) == (["ABB", "TCS"], ["HEG"])
    assert xl.split_symbols("nano", extra) == ([], ["TCS", "HEG"])
    assert xl.system_universe("750", base, extra) is base


def test_each_system_has_its_own_published_file_and_dataset():
    assert ranking_store.asset_name("750") == "rankings.parquet"
    assert ranking_store.dataset_name("750") == "snapshots/rankings"
    assert ranking_store.asset_name("nano") == "rankings_nano.parquet"
    assert ranking_store.dataset_name("combined") == "snapshots/rankings_combined"
