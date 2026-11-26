"""record_run must not serve one page's benchmark to another.

Regression for: `_benchmark_close` is excluded from st.cache_data hashing and
the replay key omitted it, so an empty benchmark fetch cached a 0% benchmark
that a later call with a healthy benchmark received.
"""
import pandas as pd

from src.engine.model_record import _benchmark_key
from src.engine.track_record import INCEPTION


def _series(start, end, seed=1.0):
    idx = pd.bdate_range(start, end)
    return pd.Series([seed * (1 + 0.001 * i) for i in range(len(idx))], index=idx, name="^CRSLDX")


def test_empty_and_healthy_benchmark_get_different_keys():
    healthy = _series("2024-10-01", "2026-09-30")
    assert _benchmark_key(pd.Series(dtype=float), INCEPTION) == "nobench"
    assert _benchmark_key(None, INCEPTION) == "nobench"
    assert _benchmark_key(healthy, INCEPTION) != "nobench"


def test_short_and_long_downloads_of_same_index_share_a_key():
    long = _series("2021-10-01", "2026-09-30")
    short = long.loc["2024-10-01":]
    assert _benchmark_key(long, INCEPTION) == _benchmark_key(short, INCEPTION)


def test_changed_benchmark_inside_record_window_changes_key():
    base = _series("2024-10-01", "2026-09-30")
    changed = base.copy()
    changed.loc["2026-05-15":] *= 1.01
    assert _benchmark_key(base, INCEPTION) != _benchmark_key(changed, INCEPTION)


def test_strategy_and_benchmark_use_one_common_as_of_date():
    from src.engine.model_record import _align_benchmark_to_price_as_of

    prices = pd.DataFrame({"A": [100.0, 101.0]}, index=pd.to_datetime(["2026-10-06", "2026-10-07"]))
    benchmark = pd.Series([200.0, 202.0], index=pd.to_datetime(["2026-10-05", "2026-10-06"]))

    aligned_prices, aligned_benchmark = _align_benchmark_to_price_as_of(prices, benchmark)

    assert aligned_prices.index[-1] == pd.Timestamp("2026-10-06")
    assert aligned_benchmark.index[-1] == pd.Timestamp("2026-10-06")


def test_common_as_of_does_not_use_a_future_benchmark_close():
    from src.engine.model_record import _align_benchmark_to_price_as_of

    prices = pd.DataFrame({"A": [100.0, 101.0]}, index=pd.to_datetime(["2026-10-06", "2026-10-07"]))
    benchmark = pd.Series([200.0, 202.0, 204.0], index=pd.to_datetime(["2026-10-05", "2026-10-06", "2026-10-07"]))

    aligned_prices, aligned_benchmark = _align_benchmark_to_price_as_of(prices, benchmark)

    assert aligned_prices.index[-1] == pd.Timestamp("2026-10-07")
    assert aligned_benchmark.index[-1] == pd.Timestamp("2026-10-07")
    assert float(aligned_benchmark.iloc[-1]) == 204.0


def test_a_membership_change_with_the_same_prices_changes_the_run_key(monkeypatch):
    """S233: the membership reaches the run as _membership, which st.cache_data does not hash, so the
    key string has to carry it, or a new membership is served the old run."""
    from src.engine import model_record as mr
    from src.engine.extra_universe import SYSTEM_NANO

    idx = pd.bdate_range("2026-09-01", "2026-11-20")
    prices = pd.DataFrame({"A": range(1, len(idx) + 1), "B": range(2, len(idx) + 2)}, index=idx, dtype=float)
    keys = []
    monkeypatch.setattr(mr, "run_backtest", lambda key, *a, **k: keys.append(key) or {})
    monkeypatch.setattr(mr, "load_events", lambda: [])
    monkeypatch.setattr(mr, "record_sector_map", lambda cols, system: {})
    monkeypatch.setattr(mr.former_members, "with_former_members", lambda frame, membership: frame)
    for members in ({"2026-10": ["A"]}, {"2026-10": ["A", "B"]}):
        monkeypatch.setattr(mr, "membership_for", lambda system, m=members: {"schema_version": 2, "index": m})
        mr.record_run_uncached(prices, None, SYSTEM_NANO)
    assert len(keys) == 2 and keys[0] != keys[1]
