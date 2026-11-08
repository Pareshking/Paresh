import pandas as pd

from scripts.build_nse_index_prices import INDEX_NAMES, SECTOR_NAMES


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
    monkeypatch.setattr("time.sleep", lambda s: None)

    out = tmp_path / "index_prices.parquet"
    result = mod.build(out, date(2026, 9, 1), date(2026, 9, 22))
    frame = pd.read_parquet(out)

    n = len(INDEX_NAMES) + len(SECTOR_NAMES)
    assert result == {"rows": 3 * n, "indices": n}
    assert set(frame["index"]) == set(INDEX_NAMES) | set(SECTOR_NAMES)
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


def test_the_latest_year_is_daily_where_screener_gives_daily_closes():
    """Screener's ten-year chart is weekly; its 400-day chart daily (7 Nov 2026)."""
    import pandas as pd
    from scripts import build_nse_index_prices as mod

    weekly = pd.Series([1.0, 2.0, 3.0, 4.0],
                       index=pd.to_datetime(["2025-09-05", "2025-09-12", "2026-10-02", "2026-10-09"]))
    daily = pd.Series([3.0, 3.1, 3.2, 4.0],
                      index=pd.to_datetime(["2026-10-02", "2026-10-05", "2026-10-06", "2026-10-09"]))
    merged = mod._merge_daily(weekly, daily)
    assert list(merged.index.strftime("%Y-%m-%d")) == [
        "2025-09-05", "2025-09-12", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-09"]
    assert merged["2026-10-06"] == 3.2
    assert mod._merge_daily(weekly, None).equals(weekly)


def test_a_sector_index_that_fails_is_left_out_and_a_size_index_still_stops_the_build(tmp_path, monkeypatch):
    """S109: the sector indices are optional; the five size indices are not."""
    from datetime import date

    import pytest

    from scripts import build_nse_index_prices as mod

    def down(*a, **k):
        raise RuntimeError("down")

    def official(name, start, end):
        if name == "NIFTY MEDIA":
            raise RuntimeError("no such series today")
        return _series(name)

    monkeypatch.setattr("time.sleep", lambda s: None)
    monkeypatch.setattr(mod, "_fetch_official", official)
    monkeypatch.setattr(mod, "_fetch_screener", down)
    frame_path = tmp_path / "a.parquet"
    mod.build(frame_path, date(2026, 9, 1), date(2026, 9, 22))
    got = set(pd.read_parquet(frame_path)["index"])
    assert "sector_media" not in got and set(INDEX_NAMES) <= got

    def official_size_down(name, start, end):
        if name == "NIFTY 50":
            raise RuntimeError("down")
        return _series(name)

    monkeypatch.setattr(mod, "_fetch_official", official_size_down)
    with pytest.raises(RuntimeError):
        mod.build(tmp_path / "b.parquet", date(2026, 9, 1), date(2026, 9, 22))
