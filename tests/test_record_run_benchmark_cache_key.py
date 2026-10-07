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
