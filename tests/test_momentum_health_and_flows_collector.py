"""S91: momentum health reads its spreads file; the FII/DII collector refuses a row that does not add up.

The Dashboard cards that drew these (dashboard_panels.py) went with the old Dashboard, 21 Nov 2026."""
import numpy as np
import pandas as pd

from src.engine import momentum_health as mh
from datetime import UTC


def _spreads(n=36, last=0.5):
    months = pd.period_range("2023-11", periods=n, freq="M").astype(str)
    vals = np.r_[np.full(n - 1, 1.0), last]
    return pd.DataFrame({"month": months, "date": "", "top": 0.0, "bottom": 0.0, "spread": vals, "n": 500})


def test_health_reads_the_trailing_year_its_percentile_and_a_crash():
    h = mh.health(_spreads())
    assert h["trailing_12m"] == 11.5 and h["month"] == "2026-10"
    assert h["percentile"] < 10 and not h["crash"]           # 11.5 is the lowest 12-month sum
    assert mh.health(_spreads(last=-9.0))["crash"]
    assert mh.health(_spreads(n=12)) is None


def test_an_unfinished_month_and_months_before_the_membership_are_left_out():
    assert not mh._complete(pd.Timestamp("2026-11-06")) and mh._complete(pd.Timestamp("2026-10-30"))
    idx = pd.bdate_range("2009-06-01", "2026-11-06")
    ends = mh.month_ends(pd.DataFrame({"A": 1.0}, index=idx))
    assert ends[-1] == pd.Timestamp("2026-11-06")


def test_the_collector_refuses_a_row_that_does_not_add_up():
    import importlib.util
    from datetime import datetime
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("c", Path(__file__).resolve().parents[1] / "scripts" / "collect_fii_dii.py")
    c = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(c)
    now = datetime(2026, 11, 7, tzinfo=UTC)
    ok = [{"category": "DII", "date": "06-Nov-2026", "buyValue": "10", "sellValue": "4", "netValue": "6"},
          {"category": "FII/FPI", "date": "06-Nov-2026", "buyValue": "1", "sellValue": "3", "netValue": "-2"}]
    assert c.parse(ok, now)[1] == []
    bad = [dict(ok[0], netValue="9"), ok[1]]
    assert any("is not net" in b for b in c.parse(bad, now)[1])
    assert any("missing categories" in b for b in c.parse(ok[:1], now)[1])


