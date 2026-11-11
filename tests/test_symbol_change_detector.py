"""The rename detector must fire on a case we know is real.

Its first version grouped twin candidates by their LAST close, which in a
rename differ (the old ticker stops updating), so it reported "0 twins"
against a pair already measured by hand as 716 identical sessions. These
tests exist so that cannot pass quietly again: each one builds a case whose
answer is known and requires the detector to find it.
"""
from __future__ import annotations

import pandas as pd
import pytest

from scripts.check_symbol_changes import _pairs, _twins


def _sessions(n: int) -> pd.DatetimeIndex:
    return pd.bdate_range("2024-01-01", periods=n)


def test_a_handover_is_found_when_one_series_ends_and_another_begins():
    idx = _sessions(10)
    df = pd.DataFrame(index=idx, columns=["OLDCO", "NEWCO"], dtype=float)
    df.loc[idx[:5], "OLDCO"] = 100.0
    df.loc[idx[5:], "NEWCO"] = 99.0
    found = _pairs(df)
    assert [(p[1], p[2]) for p in found] == [("OLDCO", "NEWCO")]
    assert found[0][0] == idx[4]           # the old symbol's last session
    assert found[0][5] == pytest.approx(0.99)


def test_a_handover_at_a_wildly_different_price_is_not_called_a_rename():
    idx = _sessions(10)
    df = pd.DataFrame(index=idx, columns=["OLDCO", "NEWCO"], dtype=float)
    df.loc[idx[:5], "OLDCO"] = 100.0
    df.loc[idx[5:], "NEWCO"] = 40.0       # not a ticker change
    assert _pairs(df) == []


def test_twins_are_found_even_though_their_last_closes_differ():
    """The bug: a renamed company's old ticker stops updating, so grouping
    candidates by last close never compares the very pair that matters."""
    idx = _sessions(120)
    shared = pd.Series(range(120), index=idx, dtype=float) + 400.0
    df = pd.DataFrame(index=idx, dtype=float)
    df["NEWTICK"] = shared                                  # the full history
    df["OLDTICK"] = shared.where(shared.index <= idx[100])  # stops early
    assert df["NEWTICK"].dropna().iloc[-1] != df["OLDTICK"].dropna().iloc[-1]

    twins = _twins(df)
    assert {frozenset((a, b)) for a, b, _ in twins} == {frozenset(("NEWTICK", "OLDTICK"))}
    assert twins[0][2] >= 100


def test_two_different_companies_are_not_twins():
    idx = _sessions(120)
    df = pd.DataFrame(index=idx, dtype=float)
    df["ACO"] = pd.Series(range(120), index=idx, dtype=float) + 400.0
    df["BCO"] = pd.Series(range(120), index=idx, dtype=float) + 400.5
    assert _twins(df) == []
