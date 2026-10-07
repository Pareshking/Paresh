"""Yahoo is not a price source any more (owner, 2026-10-02).

Screener first, NSE for what it lacks: for the ranking, the backtest, the
track record, the benchmark, market caps and all-time highs. These tests pin
the order and the absence, so a Yahoo path cannot quietly come back.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from src.loaders import benchmark_store as bs
from src.loaders import price_source as ps

ROOT = Path(__file__).resolve().parents[1]


def _store(symbols, idx):
    rng = np.random.default_rng(3)
    cols = {}
    for s in symbols:
        cols[(s, "Close")] = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx)))), index=idx)
        cols[(s, "Volume")] = pd.Series(1e5, index=idx)
    store = pd.DataFrame(cols)
    store.columns = pd.MultiIndex.from_tuples(store.columns)
    return store


IDX = pd.bdate_range(end="2026-09-30", periods=320)


# ── The ranking frame ────────────────────────────────────────────────────────

def test_screener_is_the_source_when_it_can_serve():
    src = ps.ranking_frames(_store(["A", "B"], IDX), ["A", "B"], None)
    assert src.source == "screener"
    assert list(src.close.columns) == ["A", "B"]
    assert src.high is None and src.low is None and not src.intraday


def test_nse_fills_what_screener_lacks_and_nothing_else_does():
    store = _store(["A"], IDX)
    # NSE tracks Screener (they agree to the paisa on 95% of sessions); a stock
    # drifting past 1% is excluded by eligible_middle and stays unfilled.
    nse = store.xs("Close", axis=1, level=-1)[["A"]].copy()
    store.loc[IDX[-5]:, ("A", "Close")] = np.nan          # Screener has a hole
    src = ps.ranking_frames(store, ["A"], nse)
    assert src.source == "screener"
    assert np.allclose(src.close["A"].iloc[-5:], nse["A"].iloc[-5:])


def test_nse_ranks_alone_when_screener_cannot_serve():
    nse = pd.DataFrame({"A": np.linspace(100, 110, len(IDX))}, index=IDX)
    src = ps.ranking_frames(None, ["A"], nse)
    assert src.source == "nse"
    assert src.volume.isna().all().all()            # NSE's file has no volume; none invented


def test_neither_source_means_no_frame_not_a_yahoo_download():
    assert ps.ranking_frames(None, ["A"], None) is None


def test_a_short_nse_file_is_refused_like_a_short_screener_store():
    short = pd.DataFrame({"A": [1.0, 2.0]}, index=IDX[-2:])
    assert ps.ranking_frames(None, ["A"], short) is None


def test_a_stale_yahoo_setting_is_ignored():
    assert ps.preferred() == "screener"


def test_the_app_and_the_precompute_build_the_frame_the_same_way():
    """Both must call price_source, or the precomputed ranking's contract misses."""
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    sync = (ROOT / "scripts" / "sync_data.py").read_text(encoding="utf-8")
    assert "_ps.frames_from(" in app
    assert "price_source.ranking_frames(" in sync
    assert "nse_prices.middle_close(" in sync and "_nse.middle_close(" in app


# ── Nothing reaches for Yahoo ────────────────────────────────────────────────

@pytest.mark.parametrize("rel", [
    "app.py",
    "scripts/sync_data.py",
    "scripts/precompute_systems.py",
    "scripts/update_track_record.py",
    "scripts/sync_former_member_prices.py",
    "scripts/check_corporate_actions.py",
    "src/loaders/mcap_loader.py",
    "src/loaders/ath_loader.py",
    "src/loaders/benchmark_store.py",
    "scripts/build_benchmarks.py",
])
def test_no_runtime_path_downloads_from_yahoo(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    for needle in ("import yfinance", "yf.download", "fetch_price_history(", "extract_ohlcv("):
        assert needle not in text, f"{rel} still calls {needle}"


def test_the_benchmark_loader_reads_the_committed_file_not_yahoo():
    from src.loaders import price_loader

    body = (ROOT / "src/loaders/price_loader.py").read_text(encoding="utf-8")
    fn = body[body.index("def fetch_benchmark_history("):body.index("def get_market_regime(")]
    assert "benchmark_store" in fn and "yf." not in fn
    assert callable(price_loader.fetch_benchmark_history)


@pytest.mark.parametrize("workflow", ["daily_sync.yml", "weekly_full_sync.yml"])
def test_the_sync_workflows_publish_no_yahoo_price_file(workflow):
    text = (ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
    for asset in ("prices_full.parquet", "prices_snapshot.parquet", "prices_extra.parquet",
                  "sync_extra_yahoo.py", "--dataset prices/yahoo", "--dataset app/prices_"):
        assert asset not in text, f"{workflow} still handles {asset}"


def test_the_rankings_still_reach_the_release():
    """A missing Yahoo snapshot used to `exit 0` the step before the rankings uploaded."""
    wf = yaml.safe_load((ROOT / ".github/workflows/daily_sync.yml").read_text(encoding="utf-8"))
    steps = wf["jobs"]["sync"]["steps"]
    publish = next(s for s in steps if s.get("name") == "Publish rankings to the release")
    assert "exit 0" not in publish["run"]
    assert "rankings.parquet" in publish["run"] and "rankings_${SYS}.parquet" in publish["run"]


def test_the_daily_sync_extends_the_benchmark():
    wf = yaml.safe_load((ROOT / ".github/workflows/daily_sync.yml").read_text(encoding="utf-8"))
    runs = [s.get("run", "") for s in wf["jobs"]["sync"]["steps"]]
    assert any("scripts/build_benchmarks.py --update" in r for r in runs)


# ── The benchmark file ───────────────────────────────────────────────────────

def _bench(tmp_path, rows):
    frame = pd.DataFrame(rows, columns=bs.FIELDS).assign(date=lambda f: pd.to_datetime(f["date"]))
    bs.write(frame.set_index("date"), tmp_path / "b.csv")
    return tmp_path / "b.csv"


def test_benchmark_history_maps_the_old_yahoo_tickers(tmp_path):
    path = _bench(tmp_path, [["2026-09-29", 21000.0, 22000.0, "nse"],
                             ["2026-09-30", 21100.0, 22100.0, "nse"]])
    n500 = bs.history("2y", "^CRSLDX", path)
    n50 = bs.history("2y", "^NSEI", path)
    assert list(n500) == [21000.0, 21100.0] and n500.name == "^CRSLDX"
    assert list(n50) == [22000.0, 22100.0]


@pytest.mark.parametrize("period,expected", [("5d", 1), ("1mo", 2), ("2y", 3), ("max", 3), ("", 3)])
def test_benchmark_period_is_counted_back_from_the_last_row(tmp_path, period, expected):
    path = _bench(tmp_path, [["2025-01-15", 1.0, 1.0, "screener"],
                             ["2026-09-10", 2.0, 2.0, "nse"],
                             ["2026-09-30", 3.0, 3.0, "nse"]])
    assert len(bs.history(period, "^CRSLDX", path)) == expected


def test_an_unknown_symbol_or_missing_file_is_an_empty_series(tmp_path):
    assert bs.history("2y", "^UNKNOWN", _bench(tmp_path, [["2026-09-30", 1.0, 1.0, "nse"]])).empty
    assert bs.history("2y", "^CRSLDX", tmp_path / "absent.csv").empty


def test_an_nse_row_beats_a_screener_row_for_the_same_date():
    day = pd.Timestamp("2026-09-30")
    scr = pd.DataFrame({"nifty500": [1.0], "nifty50": [1.0], "source": ["screener"]},
                       index=pd.DatetimeIndex([day], name="date"))
    nse = pd.DataFrame({"nifty500": [2.0], "nifty50": [2.0], "source": ["nse"]},
                       index=pd.DatetimeIndex([day], name="date"))
    for a, b in ((scr, nse), (nse, scr)):
        merged = bs.merge(a, b)
        assert len(merged) == 1 and merged.iloc[0]["source"] == "nse"


def test_a_day_with_no_new_rows_keeps_two_decimals(tmp_path):
    # S28: on pandas 3 an empty frame from NSE made the closes object and
    # write() committed 19384.30 as 19384.3.
    day = pd.Timestamp("2026-09-30")
    have = pd.DataFrame({"nifty500": [19384.30], "nifty50": [24611.10], "source": ["nse"]},
                        index=pd.DatetimeIndex([day], name="date"))
    none = pd.DataFrame.from_dict({}, orient="index", columns=bs.FIELDS[1:3])
    none.index.name = "date"
    none["source"] = "nse"
    merged = bs.merge(have, none)
    assert merged["nifty500"].dtype == float
    path = tmp_path / "benchmarks.csv"
    bs.write(merged, path)
    assert path.read_text(encoding="utf-8").splitlines()[1] == "2026-09-30,19384.30,24611.10,nse"


def test_index_closes_read_the_bundle_index_rows():
    prices = pd.DataFrame({
        "mkt": ["Y", "Y", "N"],
        "security": ["Nifty 500", "Nifty 50", "RELIANCE INDUSTRIES"],
        "close": [21857.75, 22421.95, 1375.0],
    })
    assert bs.index_closes(prices) == {"nifty500": 21857.75, "nifty50": 22421.95}


def test_the_committed_benchmark_file_is_daily_and_recent():
    frame = bs.read()
    assert not frame.empty, "data/benchmarks.csv is missing"
    n500 = frame["nifty500"].dropna()
    last_year = n500[n500.index >= n500.index[-1] - pd.DateOffset(years=1)]
    assert len(last_year) >= 200, "the last year must be daily for the 200-day regime average"
    assert (frame["source"] == "nse").any()


def test_backfill_asks_only_for_weekdays():
    from datetime import date
    from scripts.build_benchmarks import weekdays_between

    days = weekdays_between(date(2026, 9, 25), date(2026, 9, 30))   # Fri .. Wed
    assert days == [date(2026, 9, 25), date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30)]


def test_source_rank_nse_then_ss_then_screener():
    day = pd.Timestamp("2026-09-30")

    def row(src, v):
        return pd.DataFrame({"nifty500": [v], "nifty50": [v], "source": [src]},
                            index=pd.DatetimeIndex([day], name="date"))

    assert bs.merge(row("screener", 1.0), row("ss", 2.0)).iloc[0]["source"] == "ss"
    assert bs.merge(row("ss", 2.0), row("nse", 3.0)).iloc[0]["source"] == "nse"


def test_the_benchmark_is_daily_for_the_whole_backtest_window():
    s = bs.read()["nifty500"].dropna()
    recent = s[s.index >= s.index[-1] - pd.DateOffset(years=5)]
    assert recent.index.to_series().diff().dt.days.max() <= 6, "a gap longer than a long weekend"


def test_kaggle_rows_rank_below_nse_and_ss_but_above_screener():
    day = pd.Timestamp("2015-10-08")

    def row(src, v):
        return pd.DataFrame({"nifty500": [v], "nifty50": [v], "source": [src]},
                            index=pd.DatetimeIndex([day], name="date"))

    assert bs.merge(row("kaggle", 1.0), row("ss", 2.0)).iloc[0]["source"] == "ss"
    assert bs.merge(row("screener", 1.0), row("kaggle", 2.0)).iloc[0]["source"] == "kaggle"


def test_the_benchmark_reaches_back_before_the_2010_ranking():
    s = bs.read()["nifty500"].dropna()
    assert s.index[0] <= pd.Timestamp("2009-01-02")
    assert (s.index.year == 2009).sum() >= 240        # daily through 2009
