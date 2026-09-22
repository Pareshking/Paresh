import pandas as pd

from scripts.build_nse_index_prices import INDEX_NAMES, _records, _number


def test_all_five_research_indices_are_defined():
    assert set(INDEX_NAMES) == {
        "nifty50",
        "nifty_next50",
        "nifty_midcap150",
        "nifty_smallcap250",
        "nifty_microcap250",
    }


def test_index_source_contract():
    from scripts.build_nse_index_prices import INDEX_NAMES, INDEX_SLUGS, DEEP_DAYS
    assert set(INDEX_NAMES) == {
        "nifty50", "nifty_next50", "nifty_midcap150",
        "nifty_smallcap250", "nifty_microcap250",
    }
    assert set(INDEX_SLUGS) == set(INDEX_NAMES)
    assert DEEP_DAYS == 3650

def test_index_price_archive_contract(tmp_path):
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-09-18"] * 5),
            "index": list(INDEX_NAMES),
            "open": [1.0] * 5,
            "high": [2.0] * 5,
            "low": [0.5] * 5,
            "close": [1.5] * 5,
            "source": ["NSE historical indices API"] * 5,
            "evidence_date": pd.to_datetime(["2026-09-22"] * 5),
        }
    )
    path = tmp_path / "index_prices.parquet"
    frame.to_parquet(path, index=False)
    loaded = pd.read_parquet(path)
    assert set(loaded["index"]) == set(INDEX_NAMES)
    assert loaded["close"].notna().all()
    assert loaded[["index", "date"]].duplicated().sum() == 0
