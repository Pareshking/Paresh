import pandas as pd

from scripts.build_nse_index_prices import INDEX_NAMES


def test_all_five_research_indices_are_defined():
    assert set(INDEX_NAMES) == {
        "nifty50",
        "nifty_next50",
        "nifty_midcap150",
        "nifty_smallcap250",
        "nifty_microcap250",
    }


def test_index_source_contract():
    from scripts.build_nse_index_prices import _fetch_official, _fetch_screener, _fetch_yahoo
    assert callable(_fetch_official)
    assert callable(_fetch_yahoo)
    assert callable(_fetch_screener)

def test_index_price_archive_contract(tmp_path):
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-09-18"] * 5),
            "index": list(INDEX_NAMES),
            "close": [1.5] * 5,
            "source": ["NSE Indices historical data"] * 5,
            "evidence_date": pd.to_datetime(["2026-09-22"] * 5),
        }
    )
    path = tmp_path / "index_prices.parquet"
    frame.to_parquet(path, index=False)
    loaded = pd.read_parquet(path)
    assert set(loaded["index"]) == set(INDEX_NAMES)
    assert loaded["close"].notna().all()
    assert loaded[["index", "date"]].duplicated().sum() == 0
