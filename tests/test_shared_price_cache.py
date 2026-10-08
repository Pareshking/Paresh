"""The price frames are shared between sessions, and must stay unchanged.

Streamlit Cloud restricted the app for using too much memory (2026-10-08).
Measured locally the same day: every rerun of every session unpickled ~130 MB
of cache_data copies of the same price frames, and the weight-keyed engine
cache grew 56 MB per slider position with no ceiling. The price frames now live
in st.cache_resource, one object for every session, and each rerun gets a
shallow copy (app.py `_shared`).

That is only safe while a write to the copy cannot reach the shared frame. The
first group of tests pins that guarantee, which comes from pandas 3's
copy-on-write; a pandas without it fails here before it can silently let one
reader's edit show up in another reader's prices.
"""

import numpy as np
import pandas as pd
import pytest


def _shared(frame):
    # The same one-liner as app.py's _shared, which cannot be imported
    # without running the app script.
    return None if frame is None else frame.copy(deep=False)


@pytest.fixture
def base():
    idx = pd.bdate_range("2026-01-01", periods=5)
    return pd.DataFrame(np.arange(15.0).reshape(5, 3), index=idx, columns=["AAA", "BBB", "CCC"])


@pytest.mark.parametrize("write", [
    lambda d: d.loc.__setitem__((d.index[0], "AAA"), -1.0),
    lambda d: d.iloc.__setitem__((1, 1), -1.0),
    lambda d: d.__setitem__("AAA", 0.0),
    lambda d: d.__setitem__("NEW", 1.0),
    lambda d: d.fillna(0.0, inplace=True),
    lambda d: d.drop(columns=["BBB"], inplace=True),
    lambda d: d["CCC"].__setitem__(d.index[2], -1.0),
], ids=["loc", "iloc", "column", "new-column", "fillna-inplace", "drop-inplace", "chained"])
def test_a_write_to_a_rerun_copy_never_reaches_the_shared_frame(base, write):
    before = base.copy(deep=True)
    view = _shared(base)
    try:
        write(view)
    except Exception:
        pass  # chained assignment may warn or refuse; either way, not propagate
    pd.testing.assert_frame_equal(base, before)


def test_a_raw_numpy_write_is_refused_rather_than_shared(base):
    """Loud, not silent: the one write that would bypass copy-on-write raises."""
    view = _shared(base)
    with pytest.raises(ValueError):
        view.to_numpy()[0, 0] = 99.0
    with pytest.raises(ValueError):
        view["AAA"].to_numpy()[0] = 99.0
    assert base.iloc[0, 0] == 0.0


def test_none_passes_through():
    assert _shared(None) is None


# ── What app.py must keep doing ──────────────────────────────────────────────

def _app():
    return open("app.py", encoding="utf-8").read()


def _decorator_of(src: str, name: str) -> str:
    at = src.index(f"def {name}(")
    return src[src.rindex("@st.cache", 0, at):at]


@pytest.mark.parametrize("name", ["_fetch_screener_store", "_resolved_prices_shared",
                                  "_adjusted_frames_shared"])
def test_the_price_frames_are_one_shared_object(name):
    deco = _decorator_of(_app(), name)
    assert deco.startswith("@st.cache_resource"), (
        f"{name} is back on cache_data: every rerun of every session unpickles "
        "its own copy of the price frames again"
    )
    assert "max_entries=" in deco and "ttl=" in deco


@pytest.mark.parametrize("name", ["_run_engine_base", "run_momentum_pipeline"])
def test_the_engine_caches_are_bounded(name):
    deco = _decorator_of(_app(), name)
    assert "max_entries=" in deco, (
        f"{name} has no max_entries: each weight vector a reader tries keeps a "
        "56 MB engine for an hour"
    )


def test_the_backtest_cache_is_bounded():
    src = open("src/engine/backtester.py", encoding="utf-8").read()
    assert "max_entries=" in _decorator_of(src, "run_backtest")


def test_shared_frames_are_handed_out_as_copies():
    src = _app()
    body = src[src.index("def _resolve_price_source("):src.index("def _load_tv_cached(")]
    assert 'for name in ("adj_close", "close", "high", "low", "volume"):' in body
    assert "setattr(src, name, _shared(getattr(src, name)))" in body
    assert "return src, _shared(deep)" in body
    wrapper = src[src.index("def _adjust_for_corporate_actions("):]
    assert "_shared(v) for k, v in adjusted.items()" in wrapper[:600]


def test_r2_reader_is_imported_before_the_thread_pool():
    """The pool's ranking download and the script thread imported
    src.storage.reader at the same moment, and Python raised _DeadlockError on
    every cold start: the R2 ranking was skipped for the release file."""
    src = _app()
    eager = src.index("from src.storage import reader as _r2_reader")
    pool = src.index("concurrent.futures.ThreadPoolExecutor(")
    assert eager < pool



def test_every_refresh_drops_the_shared_frames_too():
    """Force Refresh, Sync and Clear cached files used to clear st.cache_data,
    which no longer holds the price frames."""
    for path in ("app.py", "src/ui/views/config_view.py"):
        src = open(path, encoding="utf-8").read()
        assert src.count("st.cache_data.clear()") == src.count("st.cache_resource.clear()"), path
