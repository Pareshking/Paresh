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


@pytest.mark.parametrize("path,name", [
    ("src/loaders/screener_cache.py", "fetch_screener_store"),
    ("app.py", "_resolved_prices_shared"),
    ("app.py", "_adjusted_frames_shared"),
    ("app.py", "_run_engine_base"),
    ("app.py", "_ranked_shared"),
    ("src/ui/views/track_record_view.py", "_system_prices"),
])
def test_the_price_frames_are_one_shared_object(path, name):
    deco = _decorator_of(open(path, encoding="utf-8").read(), name)
    assert deco.startswith("@st.cache_resource"), (
        f"{name} is back on cache_data: every rerun of every session unpickles "
        "its own copy of the price frames again"
    )
    assert "max_entries=" in deco and "ttl=" in deco


def test_the_engine_is_handed_out_as_a_view():
    src = _app()
    ranked = src[src.index("def _ranked_shared("):src.index("def run_momentum_pipeline(")]
    assert "pipeline.engine_view(_calc)" in ranked, "ranking would write on the shared base engine"
    wrapper = src[src.index("def run_momentum_pipeline("):src.index("def _system_universe(")]
    assert "return pipeline.engine_view(calc), _shared(rank_df)" in wrapper


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


# ── The shared engine (TODO S62) ─────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine_inputs():
    idx = pd.bdate_range("2024-01-01", periods=420)
    rng = np.random.default_rng(7)
    cols = [f"S{i:02d}" for i in range(30)]
    close = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, (len(idx), len(cols))), axis=0)),
                         index=idx, columns=cols)
    volume = pd.DataFrame(1e5, index=idx, columns=cols)
    info = pd.DataFrame({"Symbol": cols, "Company Name": cols, "Industry": ["A", "B", "C"] * 10})
    caps = pd.Series(1e4, index=cols)
    return close, volume, info, caps


def _build(engine_inputs):
    from src.engine import pipeline

    close, volume, info, caps = engine_inputs
    return pipeline.build_engine(close, None, None, close, volume, info, caps)


def _snapshot(calc):
    import pickle

    return pickle.dumps({k: v for k, v in vars(calc).items()})


W_A = (0.10, 0.30, 0.30, 0.20, 0.10)
W_B = (0.50, 0.10, 0.10, 0.10, 0.20)


def test_ranking_on_a_view_leaves_the_shared_engine_untouched(engine_inputs):
    from src.engine import pipeline

    close, _, info, caps = engine_inputs
    base = _build(engine_inputs)
    before = _snapshot(base)
    for w in (W_A, W_B):
        pipeline.rank_with_weights(pipeline.engine_view(base), w, info, caps, close, close,
                                   intraday=False)
    assert _snapshot(base) == before, "rank_with_weights wrote through a view onto the shared engine"


def test_a_view_ranks_exactly_as_a_private_copy_did(engine_inputs):
    """The old behaviour: cache_data handed every caller its own deep copy."""
    import copy

    from src.engine import pipeline

    close, _, info, caps = engine_inputs
    base = _build(engine_inputs)
    for w in (W_A, W_B, W_A):
        _, got = pipeline.rank_with_weights(pipeline.engine_view(base), w, info, caps, close, close,
                                            intraday=False)
        _, want = pipeline.rank_with_weights(copy.deepcopy(base), w, info, caps, close, close,
                                             intraday=False)
        assert len(want) == 30 and want["Score"].notna().all()
        pd.testing.assert_frame_equal(got, want)


def test_two_sessions_with_different_weights_do_not_see_each_other(engine_inputs):
    from src.engine import pipeline

    close, _, info, caps = engine_inputs
    base = _build(engine_inputs)
    a, rank_a = pipeline.rank_with_weights(pipeline.engine_view(base), W_A, info, caps, close, close,
                                           intraday=False)
    b, _ = pipeline.rank_with_weights(pipeline.engine_view(base), W_B, info, caps, close, close,
                                      intraday=False)
    assert a.weights == list(W_A) and b.weights == list(W_B)
    assert not a.momentum_scores.equals(b.momentum_scores)
    # A page writing into its view's frames and nested dicts reaches nobody else.
    view = pipeline.engine_view(a)
    view.prices.iloc[0, 0] = -1.0
    view._period_z_scores[1].iloc[-1, 0] = 99.0
    view.period_metrics[1]["poisoned"] = True
    view.weights.append(1.0)
    for other in (a, base):
        assert other.prices.iloc[0, 0] != -1.0
        assert other._period_z_scores[1].iloc[-1, 0] != 99.0
        assert "poisoned" not in other.period_metrics[1]
    assert a.weights == list(W_A)


# ── Track Record comparison (TODO S63) ───────────────────────────────────────

def test_the_comparison_prices_from_the_shared_store_not_a_second_download():
    src = open("src/ui/views/track_record_view.py", encoding="utf-8").read()
    fn = src[src.index("def _comparison_price_frame("):src.index("def _record_mtd(")]
    assert "fetch_screener_store(" not in fn
    assert "screener_cache.configured()" in fn


def test_the_selected_systems_prices_are_never_cached():
    """Its frame is the live one; a cache keyed on system names served it stale."""
    src = open("src/ui/views/track_record_view.py", encoding="utf-8").read()
    at = src.index("def _comparison_price_frame(")
    line_above = src[:at].rstrip().splitlines()[-1]
    assert not line_above.startswith("@st.cache"), line_above
