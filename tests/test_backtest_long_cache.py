"""S208: the Backtest page's long file is one shared object, and its readers leave it alone.

`_long_file` moved from st.cache_data (a fresh unpickled copy on every rerun) to
st.cache_resource (the one stored object), which is only safe while no caller writes
to it. The run's price frame and its whole-history fingerprint (owner decision 3B) are
computed once in a cached loader instead of on every rerun.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engine import backtest_page as bp
from src.engine import index_universe as iu
from src.engine import pipeline
from src.loaders import nse_long
from src.ui.views import backtest_view as bv


@pytest.fixture
def page(monkeypatch):
    rng = np.random.default_rng(208)
    idx = pd.bdate_range("2020-01-01", "2023-06-30")
    cols = [f"S{i}" for i in range(12)]
    close = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.01, (len(idx), len(cols))), axis=0)),
                         index=idx, columns=cols).astype("float32")
    report = {"built": "2023-07-01", "last_session": "2023-06-30", "symbols_priced": len(cols)}
    monkeypatch.setattr(nse_long, "load", lambda **_: (close, None, report))
    monkeypatch.setattr(iu, "index_history", lambda key: {"members": cols[:8]})
    monkeypatch.setattr(iu, "first_month", lambda membership: pd.Period("2021-02", freq="M"))
    monkeypatch.setattr(iu, "ever_members", lambda membership: cols[:8])
    monkeypatch.setattr(iu, "INDICES", {"nifty_test": "Nifty Test"})
    monkeypatch.setattr(bp, "industry_map", lambda columns, current: ({c: "X" for c in columns}, 0))
    monkeypatch.setattr(bp, "index_file_industries", lambda: {})

    calls = {"n": 0}
    real = pipeline.price_fingerprint

    def counted(df):
        calls["n"] += 1
        return real(df)

    monkeypatch.setattr(bv, "price_fingerprint", counted)
    for cached in (bv._long_file, bv._long_value, bv._run_frame_shared, bv._traded_shared):
        cached.clear()
    yield close, calls
    for cached in (bv._long_file, bv._long_value, bv._run_frame_shared, bv._traded_shared):
        cached.clear()


def _rerun():
    bounds = bv._history_bounds()
    choice = {"index": "nifty_test", "start": bounds["months"][0], "end": bounds["months"][-1], "floor": 0}
    return bv._history_inputs(pd.DataFrame(), choice, bounds)


def test_the_cached_long_file_is_unchanged_after_page_runs(page):
    close, _calls = page
    stored = bv._long_file()[0]
    assert stored is close  # cache_resource hands out the one stored object
    before = pd.util.hash_pandas_object(stored, index=True).to_numpy().copy()
    snapshot = stored.copy(deep=True)

    for _ in range(3):
        h = _rerun()
        # A reader that writes to its frame gets its own copy (copy-on-write) ...
        h["close"].iloc[0, 0] = -1.0
        h["close"]["S0"] = 0.0

    # ... and neither the shared long file nor the shared run frame sees it.
    assert bv._long_file()[0] is stored
    assert (pd.util.hash_pandas_object(stored, index=True).to_numpy() == before).all()
    pd.testing.assert_frame_equal(stored, snapshot)
    assert _rerun()["close"].iloc[0, 0] != -1.0


def test_the_run_fingerprint_is_hashed_once_not_per_rerun(page):
    _close, calls = page
    runs = [_rerun() for _ in range(5)]
    assert calls["n"] == 1  # was one whole-history hash per rerun in _run
    h = runs[-1]
    assert h["close_fingerprint"] == pipeline.price_fingerprint(h["close"])  # still every row (3B)
    assert h["close"].dtypes.eq("float64").all()  # frame_for's float64 kept (owner)


def test_traded_value_and_its_fingerprint_are_computed_once(page, monkeypatch):
    close, calls = page
    value = (close * 1e6).astype("float64")
    monkeypatch.setattr(nse_long, "load_value", lambda: value)
    averaged = {"n": 0}
    real_average = nse_long.average_value

    def counted_average(frame):
        averaged["n"] += 1
        return real_average(frame)

    monkeypatch.setattr(nse_long, "average_value", counted_average)

    def rerun_with_floor():
        bounds = bv._history_bounds()
        choice = {"index": "nifty_test", "start": bounds["months"][0], "end": bounds["months"][-1], "floor": 5.0}
        return bv._history_inputs(pd.DataFrame(), choice, bounds)

    runs = [rerun_with_floor() for _ in range(4)]
    assert averaged["n"] == 1  # was once per rerun
    assert calls["n"] == 2  # the run frame once, the traded value once
    h = runs[-1]
    assert h["traded_fingerprint"] == pipeline.price_fingerprint(h["traded_value"])
    expected = real_average(value.reindex(columns=list(h["close"].columns)).loc[:h["close"].index[-1]])
    pd.testing.assert_frame_equal(h["traded_value"], expected)
