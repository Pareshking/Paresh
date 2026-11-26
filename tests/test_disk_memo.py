"""Results kept on disk across cache clears (S233 (2))."""

import pandas as pd

from src.core import disk_memo


def test_a_result_is_built_once_per_key_and_served_after():
    calls = []

    def build():
        calls.append(1)
        return pd.DataFrame({"A": [1.0, 2.0]})

    k = disk_memo.digest("x", "fp1")
    first = disk_memo.get("t", k, build)
    again = disk_memo.get("t", k, build)
    assert len(calls) == 1
    pd.testing.assert_frame_equal(first, again)
    disk_memo.get("t", disk_memo.digest("x", "fp2"), build)
    assert len(calls) == 2


def test_only_the_latest_keys_are_kept(tmp_path, monkeypatch):
    for i in range(4):
        disk_memo.get("t", disk_memo.digest(i), lambda i=i: i)
    assert len(list(disk_memo._dir("t").glob("*.pkl"))) == disk_memo.KEEP


def test_an_unreadable_memo_is_rebuilt():
    k = disk_memo.digest("broken")
    disk_memo.get("t", k, lambda: 1)
    (disk_memo._dir("t") / f"{k[:40]}.pkl").write_bytes(b"not a pickle")
    assert disk_memo.get("t", k, lambda: 2) == 2


def test_the_code_fingerprint_moves_with_a_file(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n")
    one = disk_memo.code_fingerprint(tmp_path)
    disk_memo._CODE.clear()
    (tmp_path / "src" / "a.py").write_text("x = 2\n")
    assert disk_memo.code_fingerprint(tmp_path) != one


def test_the_daily_history_is_rebuilt_when_the_long_file_changes(monkeypatch):
    """The ranking frame alone does not key it: the long file's values do too."""
    from src.loaders import nse_long, price_source
    from src.ui import daily_history as dh

    prices = pd.DataFrame({"A": [1.0, 2.0, 3.0]}, index=pd.date_range("2026-11-02", periods=3))
    longs = iter([pd.DataFrame({"A": [1.0, 2.0, 3.0]}, index=prices.index),
                  pd.DataFrame({"A": [1.0, 2.5, 3.0]}, index=prices.index)])
    built = []
    monkeypatch.setattr(nse_long, "load_columns", lambda cols, start=None: next(longs))

    def fill(frame, long):
        built.append(float(long.iloc[1, 0]))
        return frame * 1.0, {"cells": 1}
    monkeypatch.setattr(price_source, "daily_history", fill)
    dh._built.__wrapped__("fp", prices)
    dh._built.__wrapped__("fp", prices)
    assert built == [2.0, 2.5]
