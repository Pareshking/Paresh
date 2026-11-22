"""data/benchmark_indices.csv: Nifty Total Market and NSE's momentum indices (S148, S149)."""
import pandas as pd
import pytest

from src.loaders import benchmark_indices as bi


def _rows(index, dates, closes, source):
    return pd.DataFrame({"date": pd.to_datetime(dates), "index": index, "close": closes, "source": source})


def test_daily_beats_weekly_and_a_newer_fetch_beats_an_older_one():
    weekly = _rows("x", ["2026-01-02", "2026-01-09"], [100.0, 101.0], "screener_weekly")
    daily_old = _rows("x", ["2026-01-09", "2026-01-12"], [101.5, 102.0], "screener_daily")
    daily_new = _rows("x", ["2026-01-12"], [102.4], "screener_daily")
    out = bi.merge(bi.merge(weekly, daily_old), daily_new)
    s = bi.series("x", frame=out)
    assert s.loc["2026-01-02"] == 100.0          # weekly kept where no daily exists
    assert s.loc["2026-01-09"] == 101.5          # daily replaced weekly
    assert s.loc["2026-01-12"] == 102.4          # the later fetch replaced the earlier
    assert len(s) == 3


def test_indices_do_not_overwrite_each_other():
    out = bi.merge(_rows("a", ["2026-01-02"], [1.0], "screener_daily"),
                   _rows("b", ["2026-01-02"], [2.0], "screener_daily"))
    assert bi.series("a", frame=out).iloc[0] == 1.0 and bi.series("b", frame=out).iloc[0] == 2.0


def test_round_trip_keeps_two_decimals(tmp_path):
    p = tmp_path / "b.csv"
    bi.write(_rows("x", ["2026-01-02"], [19384.3], "screener_daily"), p)
    assert "19384.30" in p.read_text()
    assert bi.series("x", path=p).iloc[0] == pytest.approx(19384.3)


def test_unknown_index_and_missing_file_are_empty(tmp_path):
    assert bi.series("nope", path=tmp_path / "missing.csv").empty


def test_etf_check_agrees_on_a_tracking_etf_and_flags_a_broken_series():
    idx = pd.bdate_range("2026-09-01", "2026-11-19")
    index = pd.Series(range(100, 100 + len(idx)), index=idx, dtype=float)
    etf = index / 1000 * 0.999                       # same moves, a different level
    ri, re_, ok = bi.etf_check(index, etf, idx[-1])
    assert ok and ri == pytest.approx(re_, abs=1e-9)
    broken = index.copy()
    broken.iloc[-5:] *= 1.08                         # an 8% jump the ETF never made
    assert bi.etf_check(broken, etf, idx[-1])[2] is False


def test_the_committed_file_covers_the_live_record_daily():
    """The live record starts in Jan 2026: Nifty Total Market must be daily from before it."""
    s = bi.series(bi.TOTAL_MARKET)
    assert not s.empty
    since = s[s.index >= "2025-12-01"]
    gaps = since.index.to_series().diff().dt.days.dropna()
    assert since.index[0] <= pd.Timestamp("2025-12-31") and gaps.max() <= 5, gaps.max()
    for key in bi.SERIES:
        assert not bi.series(key).empty, key


def test_a_row_for_a_session_that_has_not_closed_is_dropped():
    import sys
    from datetime import datetime
    sys.path.insert(0, "scripts")
    import build_benchmark_indices as bb
    from src.core import market_time as mt
    real = mt.ist_now
    try:
        mt.ist_now = lambda: datetime(2026, 11, 20, 8, 20, tzinfo=mt.INDIA_TZ)
        close = pd.Series([25514.30, 25434.40], index=pd.to_datetime(["2026-11-19", "2026-11-20"]))
        kept = bb.complete_only(close)
    finally:
        mt.ist_now = real
    assert list(kept.index) == [pd.Timestamp("2026-11-19")]


def _store(rows):
    """A minimal app copy of NSE's store: (date, key, close, derived)."""
    f = pd.DataFrame(rows, columns=["date", "key", "close", "derived"])
    f["date"] = pd.to_datetime(f["date"])
    return f


def test_nse_close_beats_screener_daily_and_weekly_and_a_derived_close_is_labelled():
    # 25 sessions so live_from (a run of 20 with no gap) starts the series on day one.
    days = pd.bdate_range("2026-01-01", periods=25)
    rows = [(d, "nifty_total_market", 1000.0 + i, i == 3) for i, d in enumerate(days)]
    nse = bi.nse_rows(_store(rows))
    assert set(nse["index"]) == {bi.TOTAL_MARKET}
    assert (nse["source"] == bi.NSE_DERIVED).sum() == 1
    scr = pd.concat([_rows(bi.TOTAL_MARKET, [days[0]], [999.0], "screener_weekly"),
                     _rows(bi.TOTAL_MARKET, [days[1], days[-1] + pd.offsets.BDay()], [1.5, 2000.0],
                           "screener_daily")])
    out = bi.merge(scr, nse)
    s = bi.series(bi.TOTAL_MARKET, frame=out)
    assert s.loc[days[0]] == 1000.0 and s.loc[days[1]] == 1001.0   # NSE beat weekly and daily
    assert s.iloc[-1] == 2000.0                                      # Screener fills after NSE's last
    assert len(s) == 26


def test_cross_check_reports_a_screener_close_that_differs_from_nses():
    nse = _rows("x", ["2026-01-02", "2026-01-05", "2026-01-06"], [100.0, 101.0, 102.0], bi.NSE)
    nse.loc[2, "source"] = bi.NSE_DERIVED                       # derived closes are not compared
    other = _rows("x", ["2026-01-02", "2026-01-05", "2026-01-06"], [100.01, 103.0, 150.0],
                  "screener_daily")
    bad = bi.cross_check(nse, other)
    assert list(bad["date"]) == [pd.Timestamp("2026-01-05")]


def test_every_series_has_a_key_in_nses_store():
    from src.loaders import nse_indices as ni
    keys = set(ni.read_compact()["key"])
    assert {bi.nse_key(k) for k in bi.SERIES} <= keys


def test_the_committed_file_is_nses_own_close_wherever_the_store_has_one():
    """S167 (b): no Screener row where NSE's store holds that session."""
    f = bi.read()
    assert not (f["source"] == "screener_weekly").any()
    tm = bi.series(bi.TOTAL_MARKET)
    assert tm.index[0] == pd.Timestamp("2021-10-14")
