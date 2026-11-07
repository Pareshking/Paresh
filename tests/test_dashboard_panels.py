"""S91 panels: momentum health and flows read their files and say what they show."""
import numpy as np
import pandas as pd

from src.engine import momentum_health as mh
from src.ui.views import dashboard_panels as dp


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


def test_momentum_panel_text_and_image():
    out = dp.momentum_health_html(_spreads())
    assert "+11.5" in out and "data:image/svg+xml;base64," in out and "<svg" not in out
    assert "percentile since 2010" in out and "October: +0.5 points" in out


def test_flows_panel_reads_the_latest_day_and_the_running_total():
    f = pd.DataFrame([
        {"date": "2026-11-06", "category": "FII/FPI", "buy": 1, "sell": 1, "net": 13749.82},
        {"date": "2026-11-06", "category": "DII", "buy": 1, "sell": 1, "net": -5968.7},
        {"date": "2026-11-09", "category": "FII/FPI", "buy": 1, "sell": 1, "net": -1000.0},
        {"date": "2026-11-09", "category": "DII", "buy": 1, "sell": 1, "net": 2000.0},
    ])
    out = dp.flows_html(f)
    assert "9 Nov 2026 (provisional)" in out and "₹1,000 Cr</b> net sold" in out
    assert "Since 6 Nov (2 sessions): foreign +₹12,750 Cr, domestic −₹3,969 Cr" in out


def test_the_collector_refuses_a_row_that_does_not_add_up():
    import importlib.util
    from datetime import datetime, timezone
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("c", Path(__file__).resolve().parents[1] / "scripts" / "collect_fii_dii.py")
    c = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(c)
    now = datetime(2026, 11, 7, tzinfo=timezone.utc)
    ok = [{"category": "DII", "date": "06-Nov-2026", "buyValue": "10", "sellValue": "4", "netValue": "6"},
          {"category": "FII/FPI", "date": "06-Nov-2026", "buyValue": "1", "sellValue": "3", "netValue": "-2"}]
    assert c.parse(ok, now)[1] == []
    bad = [dict(ok[0], netValue="9"), ok[1]]
    assert any("is not net" in b for b in c.parse(bad, now)[1])
    assert any("missing categories" in b for b in c.parse(ok[:1], now)[1])
