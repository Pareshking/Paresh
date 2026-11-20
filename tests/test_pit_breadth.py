"""Breadth on the members of each date (S150)."""

import numpy as np
import pandas as pd

from src.engine import market_questions as mq
from src.engine.pit_breadth import member_mask, splice


def _history():
    return {"baseline": {"date": "2024-01-01", "symbols": ["A", "B"]},
            "changes": [{"date": "2024-07-01", "added": ["C"], "removed": ["B"]}]}


def test_member_mask_follows_the_changes():
    idx = pd.bdate_range("2023-12-01", "2024-12-31")
    m = member_mask(_history(), idx, ["A", "B", "C", "D"])
    assert not m.loc["2023-12-15"].any()                      # before the record: unknown, not today's list
    assert m.loc["2024-03-01"].tolist() == [True, True, False, False]
    assert m.loc["2024-08-01"].tolist() == [True, False, True, False]


def test_a_leaver_counts_while_it_was_a_member():
    """B falls and leaves on 1 Jul: counting today's members (A, C) hides its fall."""
    idx = pd.bdate_range("2023-01-02", "2024-12-31")
    up = pd.Series(np.linspace(100, 200, len(idx)), index=idx)
    down = pd.Series(np.linspace(200, 50, len(idx)), index=idx)
    px = pd.DataFrame({"A": up, "B": down, "C": up})
    mask = member_mask(_history(), idx, px.columns)
    pit = mq._share_above_ema(px, 50, mask)
    today = mq._share_above_ema(px[["A", "C"]], 50)
    with_leaver = pit.loc["2024-03-01"]
    assert round(with_leaver) == 50                           # A up, B down
    assert round(today.loc["2024-03-01"]) == 100              # survivors only: looks broader than it was


def test_beat_counts_members_on_that_date():
    idx = pd.bdate_range("2023-01-02", "2024-12-31")
    px = pd.DataFrame({"A": np.linspace(100, 200, len(idx)), "B": np.linspace(200, 50, len(idx)),
                       "C": np.linspace(100, 300, len(idx))}, index=idx)
    bench = pd.Series(np.linspace(100, 120, len(idx)), index=idx)
    mask = member_mask(_history(), idx, px.columns)
    share, _ = mq._beat_index_12m(px, bench, pd.Timestamp("2024-03-01"), mask)
    assert share == 50.0                                      # A beat, B did not; C was not yet a member


def test_splice_uses_the_file_up_to_its_end_and_live_after():
    live = pd.Series([1.0, 2.0, 3.0, 4.0], index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]))
    past = pd.DataFrame({"x": [10.0, 20.0]}, index=pd.to_datetime(["2024-01-01", "2024-01-02"]))
    out = splice(live, past, "x")
    assert out.tolist() == [10.0, 20.0, 3.0, 4.0]
    assert splice(live, None, "x").equals(live)
    assert splice(pd.Series(dtype=float), past, "x").tolist() == [10.0, 20.0]
