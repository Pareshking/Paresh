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


def _series(name, n=3, close=100.0):
    return pd.DataFrame({
        "date": pd.bdate_range("2026-09-16", periods=n),
        "open": close, "high": close, "low": close,
        "close": [close + i for i in range(n)],
    })


def test_build_falls_back_per_index_and_writes_one_row_per_index_date(tmp_path, monkeypatch):
    """Runs the real build(); only the two network fetchers are faked.

    These two tests used to check that the fetchers were callable and that a
    hand-made frame round-tripped through parquet -- neither ran build().
    """
    from datetime import date

    from scripts import build_nse_index_prices as mod

    def official(name, start, end):
        if name == "NIFTY MICROCAP 250":
            raise RuntimeError("official source down for this index")
        return _series(name)

    def screener(key, name, start, end):
        frame = _series(name, close=50.0)
        frame["index"], frame["source"] = key, "screener"
        return frame

    monkeypatch.setattr(mod, "_fetch_official", official)
    monkeypatch.setattr(mod, "_fetch_screener", screener)

    out = tmp_path / "index_prices.parquet"
    result = mod.build(out, date(2026, 9, 1), date(2026, 9, 22))
    frame = pd.read_parquet(out)

    assert result == {"rows": 15, "indices": 5}
    assert set(frame["index"]) == set(INDEX_NAMES)
    assert not frame[["index", "date"]].duplicated().any()
    micro = frame[frame["index"] == "nifty_microcap250"]
    assert (micro["source"] == "Screener index chart (NSE index)").all()
    assert (frame.loc[frame["index"] != "nifty_microcap250", "source"] == "NSE Indices historical data").all()


def test_build_refuses_a_null_close(tmp_path, monkeypatch):
    from datetime import date

    import pytest

    from scripts import build_nse_index_prices as mod

    def official(name, start, end):
        frame = _series(name)
        frame.loc[1, "close"] = None
        return frame

    monkeypatch.setattr(mod, "_fetch_official", official)
    with pytest.raises(RuntimeError, match="null close"):
        mod.build(tmp_path / "x.parquet", date(2026, 9, 1), date(2026, 9, 22))


def test_there_is_no_yahoo_fallback():
    from pathlib import Path

    from scripts import build_nse_index_prices as mod

    text = Path(mod.__file__).read_text(encoding="utf-8")
    assert "yfinance" not in text and "yf." not in text
    assert not hasattr(mod, "_fetch_yahoo")
