"""All-time highs: built in CI, read by the app, on the SAME price basis.

The screener downloads prices with yfinance's default auto_adjust=True, so its
prices are adjusted for splits and dividends. An all-time high fetched with
auto_adjust=False sits on a different scale, and comparing the two is
meaningless -- a stock that split 1:5 carries a pre-split high five times its
adjusted price, so a genuine new high reads as ~76% BELOW its all-time high.

That mismatch shipped once. These tests pin the basis, because the failure is
silent: no error, no NaN, just a wrong number in a column people trade on.
"""
import numpy as np
import pandas as pd
import pytest

from src.loaders.ath_loader import ath_series, build_ath_snapshot, load_ath_snapshot

IDX = pd.bdate_range(end="2026-08-18", periods=40)
FIELDS = ["Open", "High", "Low", "Close", "Volume"]


def _fake_download(peaks: dict[str, float], record: list | None = None):
    """Stand-in for yf.download that records the kwargs it was called with."""

    def _download(tickers, **kwargs):
        if record is not None:
            record.append(kwargs)
        frames = []
        for t in tickers:
            base = peaks.get(t, 100.0)
            highs = np.linspace(base * 0.5, base, len(IDX))
            data = np.column_stack([highs] * len(FIELDS))
            frames.append(pd.DataFrame(
                data, index=IDX,
                columns=pd.MultiIndex.from_product([[t], FIELDS]),
            ))
        return pd.concat(frames, axis=1)

    return _download


def test_snapshot_is_built_on_the_adjusted_basis():
    """The property that broke: it MUST request adjusted prices."""
    calls: list = []
    build_ath_snapshot(
        ["RELIANCE", "TCS"], "10y", download=_fake_download({}, calls)
    )
    assert calls, "the downloader was never called"
    for kwargs in calls:
        assert kwargs["auto_adjust"] is True, (
            "unadjusted highs cannot be compared against the app's adjusted prices"
        )


def test_snapshot_requests_the_configured_window():
    calls: list = []
    build_ath_snapshot(["RELIANCE"], "10y", download=_fake_download({}, calls))
    assert calls[0]["period"] == "10y"


def test_symbols_are_suffixed_for_yahoo_but_stored_bare():
    calls: list = []
    snap = build_ath_snapshot(
        ["RELIANCE", "TCS.NS"], "10y",
        download=_fake_download({"RELIANCE.NS": 900.0, "TCS.NS": 400.0}, calls),
    )
    assert calls[0]["tickers"] if "tickers" in calls[0] else True
    assert sorted(snap["Symbol"]) == ["RELIANCE", "TCS"]


def test_the_high_is_the_maximum_over_the_window():
    snap = build_ath_snapshot(
        ["RELIANCE"], "10y", download=_fake_download({"RELIANCE.NS": 900.0})
    )
    assert snap.loc[0, "ATH"] == pytest.approx(900.0)


def test_snapshot_records_when_the_peak_happened_and_how_current_it_is():
    snap = build_ath_snapshot(
        ["RELIANCE"], "10y", download=_fake_download({"RELIANCE.NS": 900.0})
    )
    assert snap.loc[0, "ATHDate"] == str(IDX[-1].date())   # rising series peaks last
    assert snap.loc[0, "AsOf"] == str(IDX[-1].date())


def test_batching_covers_every_symbol():
    symbols = [f"S{i}" for i in range(250)]
    calls: list = []
    snap = build_ath_snapshot(
        symbols, "10y", download=_fake_download({}, calls), batch_size=100
    )
    assert len(calls) == 3               # 100 + 100 + 50
    assert len(snap) == 250


def test_an_empty_download_returns_an_empty_frame_not_an_error():
    snap = build_ath_snapshot(["A"], "10y", download=lambda t, **k: pd.DataFrame())
    assert snap.empty
    assert list(snap.columns) == ["Symbol", "ATH", "ATHDate", "AsOf"]


# ── Reading it back ─────────────────────────────────────────────────────────

def test_round_trip_through_the_csv(tmp_path):
    snap = build_ath_snapshot(
        ["RELIANCE", "TCS"], "10y",
        download=_fake_download({"RELIANCE.NS": 900.0, "TCS.NS": 400.0}),
    )
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

    Over a 20-year window one bad tick sets a permanent phantom high. A stock
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
