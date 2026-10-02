"""All-time highs: built in CI, read by the app, on the SAME price basis.

The ranking reads Screener's closes (split and bonus adjusted, no dividends;
no Yahoo since 2026-10-02), so the all-time high is taken from that same
series. A high on any other basis sits on a different scale: a stock that
split 1:5 would carry a pre-split high five times its adjusted price, and a
genuine new high would read as ~80% BELOW its all-time high.

That mismatch shipped once. These tests pin the basis, because the failure is
silent: no error, no NaN, just a wrong number in a column people trade on.
"""
import numpy as np
import pandas as pd
import pytest

from src.loaders.ath_loader import ath_series, build_ath_snapshot, load_ath_snapshot

IDX = pd.bdate_range(end="2026-08-18", periods=40)


def _store(peaks: dict[str, float]) -> pd.DataFrame:
    """A Screener-shaped store: (symbol, Close) and (symbol, Volume), rising to each peak."""
    cols = {}
    for sym, peak in peaks.items():
        cols[(sym, "Close")] = pd.Series(np.linspace(peak * 0.5, peak, len(IDX)), index=IDX)
        cols[(sym, "Volume")] = pd.Series(1e5, index=IDX)
    store = pd.DataFrame(cols)
    store.columns = pd.MultiIndex.from_tuples(store.columns)
    return store


def test_snapshot_is_built_from_screener_closes_not_another_basis():
    """The property that broke: the high must come from the ranking's own closes."""
    store = _store({"RELIANCE": 900.0})
    # A volume spike must never be read as a price.
    store[("RELIANCE", "Volume")] = 1e9
    snap = build_ath_snapshot(["RELIANCE"], store)
    assert snap.loc[0, "ATH"] == pytest.approx(900.0)


def test_symbols_are_matched_case_insensitively_and_stored_bare():
    snap = build_ath_snapshot(["reliance", "TCS"], _store({"RELIANCE": 900.0, "TCS": 400.0}))
    assert sorted(snap["Symbol"]) == ["RELIANCE", "TCS"]


def test_symbols_the_store_lacks_are_left_out():
    snap = build_ath_snapshot(["RELIANCE", "NOPE"], _store({"RELIANCE": 900.0}))
    assert list(snap["Symbol"]) == ["RELIANCE"]


def test_the_high_is_the_maximum_over_the_history():
    snap = build_ath_snapshot(["RELIANCE"], _store({"RELIANCE": 900.0}))
    assert snap.loc[0, "ATH"] == pytest.approx(900.0)


def test_snapshot_records_when_the_peak_happened_and_how_current_it_is():
    snap = build_ath_snapshot(["RELIANCE"], _store({"RELIANCE": 900.0}))
    assert snap.loc[0, "ATHDate"] == str(IDX[-1].date())   # rising series peaks last
    assert snap.loc[0, "AsOf"] == str(IDX[-1].date())


@pytest.mark.parametrize("store", [pd.DataFrame(), None,
                                   pd.DataFrame({"flat": [1.0]})])
def test_an_unusable_store_returns_an_empty_frame_not_an_error(store, monkeypatch):
    from src.loaders import price_source
    monkeypatch.setattr(price_source, "fetch_screener_store", lambda *a, **k: None)
    snap = build_ath_snapshot(["A"], store)
    assert snap.empty
    assert list(snap.columns) == ["Symbol", "ATH", "ATHDate", "AsOf"]


# ── Reading it back ─────────────────────────────────────────────────────────

def test_round_trip_through_the_csv(tmp_path):
    snap = build_ath_snapshot(["RELIANCE", "TCS"], _store({"RELIANCE": 900.0, "TCS": 400.0}))
    path = tmp_path / "ath.csv"
    snap.to_csv(path, index=False)

    series = ath_series(str(path))
    assert series["RELIANCE"] == pytest.approx(900.0)
    assert series["TCS"] == pytest.approx(400.0)


def test_missing_snapshot_degrades_quietly(tmp_path):
    assert load_ath_snapshot(str(tmp_path / "nope.csv")).empty
    assert ath_series(str(tmp_path / "nope.csv")).empty


def test_malformed_snapshot_degrades_quietly(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("nonsense,columns\n1,2\n")
    assert load_ath_snapshot(str(path)).empty


def test_non_positive_highs_are_dropped(tmp_path):
    path = tmp_path / "ath.csv"
    pd.DataFrame({"Symbol": ["A", "B"], "ATH": [0.0, 500.0],
                  "ATHDate": ["", ""], "AsOf": ["", ""]}).to_csv(path, index=False)
    series = ath_series(str(path))
    assert "A" not in series.index and series["B"] == pytest.approx(500.0)


# ── The merge in the engine ─────────────────────────────────────────────────

def test_a_new_high_today_beats_a_day_old_snapshot(monkeypatch, tmp_path):
    """The snapshot is a day behind by construction."""
    from src.engine import momentum as mom

    n, cols = 300, 3
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    prices = pd.DataFrame(
        {f"S{i}": np.linspace(100, 500, n) for i in range(cols)}, index=idx
    )
    info = pd.DataFrame({"Symbol": [f"S{i}" for i in range(cols)],
                         "Industry": ["IT"] * cols})

    # Snapshot says the old peak was 300; today's window high is ~505.
    path = tmp_path / "ath.csv"
    pd.DataFrame({"Symbol": [f"S{i}" for i in range(cols)], "ATH": [300.0] * cols,
                  "ATHDate": ["2020-01-01"] * cols,
                  "AsOf": ["2026-08-17"] * cols}).to_csv(path, index=False)

    import src.loaders.ath_loader as al
    monkeypatch.setattr(al, "ath_series", lambda p=None: al.load_ath_snapshot(str(path)).set_index("Symbol")["ATH"])

    calc = mom.MomentumEngine(prices, high_df=prices, low_df=prices,
                              close_df=prices,
                              volume_df=pd.DataFrame(1e5, index=idx, columns=prices.columns))
    rank_df = calc.get_rankings(info, pd.Series(dtype=float),
                                close_prices_df=prices, high_prices_df=prices)
    # The in-window high must win, so a stock at a new high is not shown below one.
    assert (rank_df["ATH"] > 300.0).all()
    assert (rank_df["% ATH"] <= 0.01).all()


def test_source_is_labelled_so_a_two_year_high_is_never_called_all_time(monkeypatch):
    from src.engine import momentum as mom
    import src.loaders.ath_loader as al

    monkeypatch.setattr(al, "ath_series", lambda p=None: pd.Series(dtype=float))

    n, cols = 300, 3
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    prices = pd.DataFrame({f"S{i}": np.linspace(100, 200, n) for i in range(cols)}, index=idx)
    info = pd.DataFrame({"Symbol": [f"S{i}" for i in range(cols)], "Industry": ["IT"] * cols})

    calc = mom.MomentumEngine(prices, high_df=prices, low_df=prices, close_df=prices,
                              volume_df=pd.DataFrame(1e5, index=idx, columns=prices.columns))
    rank_df = calc.get_rankings(info, pd.Series(dtype=float),
                                close_prices_df=prices, high_prices_df=prices)
    assert (rank_df["ATH Source"] == "in_memory_window").all()


def test_peak_date_reaches_the_ranking(monkeypatch, tmp_path):
    """The peak date must travel with the number, not stay in the CSV.

    Over a long window one bad tick sets a permanent phantom high. A stock
    reading -90% from a peak dated 2007 is a very different claim from one
    dated last month, and the screener has to let a reader tell them apart.
    """
    from src.engine import momentum as mom
    import src.loaders.ath_loader as al

    n, cols = 300, 3
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    prices = pd.DataFrame(
        {f"S{i}": np.linspace(100, 200, n) for i in range(cols)}, index=idx
    )
    info = pd.DataFrame({"Symbol": [f"S{i}" for i in range(cols)],
                         "Industry": ["IT"] * cols})

    path = tmp_path / "ath.csv"
    pd.DataFrame({
        "Symbol": [f"S{i}" for i in range(cols)],
        "ATH": [5000.0] * cols,                 # a phantom peak
        "ATHDate": ["2007-01-08"] * cols,       # ... from long ago
        "AsOf": ["2026-08-18"] * cols,
    }).to_csv(path, index=False)

    monkeypatch.setattr(al, "ath_series",
                        lambda p=None: al.load_ath_snapshot(str(path)).set_index("Symbol")["ATH"])
    monkeypatch.setattr(al, "ath_date_series",
                        lambda p=None: al.load_ath_snapshot(str(path)).set_index("Symbol")["ATHDate"])

    calc = mom.MomentumEngine(prices, high_df=prices, low_df=prices, close_df=prices,
                              volume_df=pd.DataFrame(1e5, index=idx, columns=prices.columns))
    rank_df = calc.get_rankings(info, pd.Series(dtype=float),
                                close_prices_df=prices, high_prices_df=prices)

    assert "ATH Date" in rank_df.columns
    assert (rank_df["ATH Date"] == "2007-01-08").all()
    assert (rank_df["% ATH"] < -90).all()       # the phantom, now attributable


def test_missing_peak_dates_do_not_break_the_ranking(monkeypatch):
    from src.engine import momentum as mom
    import src.loaders.ath_loader as al

    monkeypatch.setattr(al, "ath_series", lambda p=None: pd.Series(dtype=float))
    monkeypatch.setattr(al, "ath_date_series", lambda p=None: pd.Series(dtype=object))

    n, cols = 300, 3
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    prices = pd.DataFrame({f"S{i}": np.linspace(100, 200, n) for i in range(cols)}, index=idx)
    info = pd.DataFrame({"Symbol": [f"S{i}" for i in range(cols)], "Industry": ["IT"] * cols})

    calc = mom.MomentumEngine(prices, high_df=prices, low_df=prices, close_df=prices,
                              volume_df=pd.DataFrame(1e5, index=idx, columns=prices.columns))
    rank_df = calc.get_rankings(info, pd.Series(dtype=float),
                                close_prices_df=prices, high_prices_df=prices)
    assert (rank_df["ATH Date"] == "").all()
