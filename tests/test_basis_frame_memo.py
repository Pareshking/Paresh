"""basis_frame's memo (audit A1, 7 Nov 2026): same inputs, same answer, no rebuild;
any changed input rebuilds; no caller can alter what the memo holds."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest

from src.loaders import nse_prices


@pytest.fixture
def counted(monkeypatch, tmp_path):
    for name in ("closes.parquet", "actions.parquet", "notes.json"):
        (tmp_path / name).write_text("x")
    calls = []

    def fake(other, history, *, months, directory, until, screener):
        calls.append((months, until, screener))
        frame = other.astype("float32") * (1 + months)
        return frame, {"used": True, "months": months, "nested": {"n": len(calls)}}

    monkeypatch.setattr(nse_prices, "_basis_frame_uncached", fake)
    store = pd.DataFrame({"a": [1.0]})
    monkeypatch.setattr(nse_prices, "screener_store", lambda: store)
    nse_prices._BASIS_MEMO.clear()
    yield calls, tmp_path, store, monkeypatch
    nse_prices._BASIS_MEMO.clear()


def _prices(seed: int = 0) -> pd.DataFrame:
    idx = pd.bdate_range("2026-01-01", periods=30)
    rng = np.random.default_rng(seed)
    return pd.DataFrame(rng.uniform(90, 110, (30, 3)), index=idx, columns=["A", "B", "C"])


HIST = {"baseline": {"date": "2026-01-01", "members": ["A", "B", "C"]}, "changes": []}


def test_same_inputs_compute_once_and_return_the_same_frame(counted):
    calls, d, _, _ = counted
    p = _prices()
    f1, r1 = nse_prices.basis_frame(p, HIST, months=6, directory=d)
    f2, r2 = nse_prices.basis_frame(p, HIST, months=6, directory=d)
    assert len(calls) == 1
    pd.testing.assert_frame_equal(f1, f2)
    assert r1 == r2


def test_a_caller_cannot_change_the_memo(counted):
    calls, d, _, _ = counted
    p = _prices()
    f1, r1 = nse_prices.basis_frame(p, HIST, months=6, directory=d)
    f1.iloc[0, 0] = -1.0
    r1["nested"]["n"] = 999
    f2, r2 = nse_prices.basis_frame(p, HIST, months=6, directory=d)
    assert f2.iloc[0, 0] != -1.0 and r2["nested"]["n"] == 1
    assert len(calls) == 1


@pytest.mark.parametrize("change", ["prices", "history", "months", "until"])
def test_any_changed_input_recomputes(counted, change):
    calls, d, _, _ = counted
    p = _prices()
    nse_prices.basis_frame(p, HIST, months=6, directory=d)
    kwargs = dict(other=p, history=HIST, months=6, until=None)
    if change == "prices":
        q = p.copy()
        q.iloc[3, 1] *= 1.01  # an old row restated: the whole-history fingerprint must see it
        kwargs["other"] = q
    elif change == "history":
        kwargs["history"] = {**HIST, "changes": [{"date": "2026-01-10", "added": ["D"], "removed": ["C"]}]}
    elif change == "months":
        kwargs["months"] = 7
    else:
        kwargs["until"] = p.index[-5]
    nse_prices.basis_frame(kwargs["other"], kwargs["history"], months=kwargs["months"],
                           directory=d, until=kwargs["until"])
    assert len(calls) == 2


def test_a_rewritten_nse_file_recomputes(counted):
    calls, d, _, _ = counted
    p = _prices()
    nse_prices.basis_frame(p, HIST, months=6, directory=d)
    target = d / "closes.parquet"
    target.write_text("xy")  # size changes
    st = target.stat()
    os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))
    nse_prices.basis_frame(p, HIST, months=6, directory=d)
    assert len(calls) == 2


def test_a_refreshed_screener_store_recomputes(counted):
    calls, d, _, monkeypatch = counted
    p = _prices()
    nse_prices.basis_frame(p, HIST, months=6, directory=d)
    fresh = pd.DataFrame({"a": [1.0]})  # equal content, new object: the hourly refresh
    monkeypatch.setattr(nse_prices, "screener_store", lambda: fresh)
    nse_prices.basis_frame(p, HIST, months=6, directory=d)
    assert len(calls) == 2 and calls[-1][2] is fresh


def test_the_memo_is_bounded(counted):
    calls, d, _, _ = counted
    for m in range(1, 6):
        nse_prices.basis_frame(_prices(), HIST, months=m, directory=d)
    assert len(nse_prices._BASIS_MEMO) == nse_prices._BASIS_MEMO_SIZE
