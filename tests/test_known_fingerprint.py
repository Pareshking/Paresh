"""S208: each page reads the price fingerprint app.py computed once, never a stale one.

app.py hashes each price frame's whole history (owner decision 3B) once, in the cached
loader that builds it, and records the result against the rerun's copy with
pipeline.remember_fingerprint. The pages call pipeline.known_fingerprint, which returns
the recorded value only for that very object; any other frame is hashed in full.
"""
from __future__ import annotations

import gc
import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.engine import pipeline
from src.engine.pipeline import known_fingerprint, price_fingerprint, remember_fingerprint

ROOT = Path(__file__).resolve().parents[1]


def _frame(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2024-01-01", periods=60)
    return pd.DataFrame(rng.random((60, 5)), index=idx, columns=list("ABCDE"))


def test_a_recorded_frame_is_not_hashed_again(monkeypatch):
    df = _frame()
    remember_fingerprint(df, price_fingerprint(df))
    calls = []
    monkeypatch.setattr(pipeline, "price_fingerprint", lambda f: calls.append(1) or "x")
    for _ in range(5):
        known_fingerprint(df)
    assert calls == []


def test_any_other_frame_is_hashed_in_full():
    df = _frame()
    remember_fingerprint(df, "recorded")
    assert known_fingerprint(df) == "recorded"
    # A slice, a column subset and a copy are new objects: hashed as before.
    for other in (df.iloc[:-1], df[["A", "B"]], df.copy(deep=False), df * 2):
        assert known_fingerprint(other) == price_fingerprint(other)


def test_a_dead_frame_is_forgotten_so_a_recycled_id_never_matches():
    df = _frame()
    key = id(df)
    remember_fingerprint(df, "recorded")
    del df
    gc.collect()
    assert key not in pipeline._KNOWN_FINGERPRINTS


def test_the_shallow_copy_app_records_fingerprints_like_the_shared_frame():
    # app.py records the fingerprint of the cached frame against the rerun's shallow copy.
    df = _frame(1)
    assert price_fingerprint(df.copy(deep=False)) == price_fingerprint(df)


def test_market_questions_key_names_the_columns_taken():
    from src.ui.views.market_questions_view import _columns_key

    df = _frame(2)
    remember_fingerprint(df, price_fingerprint(df))
    assert _columns_key(df, ["A", "B"]) == _columns_key(df, ["A", "B"])
    assert _columns_key(df, ["A", "B"]) != _columns_key(df, ["A", "C"])
    assert _columns_key(df, ["A", "B"]) != _columns_key(df, ["B", "A"])
    other = df.copy()
    other.iloc[0, 0] = 99.0
    assert _columns_key(other, ["A", "B"]) != _columns_key(df, ["A", "B"])


def test_the_five_pages_read_the_recorded_fingerprint():
    views = ["dashboard_home_view", "market_view", "sector_view", "ranking_view", "market_questions_view"]
    for name in views:
        src = (ROOT / "src" / "ui" / "views" / f"{name}.py").read_text(encoding="utf-8")
        assert not re.search(r"\bprice_fingerprint\(", src), f"{name} hashes a price frame itself"
        assert "known_fingerprint(" in src, name


def test_app_records_both_frames_it_hashes_once():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "pipeline.remember_fingerprint(adj_close, _adj_close_hash)" in src
    assert "pipeline.remember_fingerprint(deep_view, deep_fingerprint)" in src
    # The deep fingerprint is computed inside the cached builder, once per data state.
    body = src[src.index("def _resolved_prices_shared("):src.index("def _resolve_price_source(")]
    assert "_price_hash(deep)" in body
