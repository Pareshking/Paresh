"""S91 panels: momentum health and flows read their files and say what they show."""
import numpy as np
import pandas as pd
import pytest

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
    assert "percentile since 2010" in out and "October: +0.5 pts" in out


def _long(n=36, ew=True):
    d = _spreads(n)
    d["top"] = 2.0                       # winners +2 a month
    d["nifty500"] = 0.5                  # the index +0.5
    if ew:
        d["ew"] = 1.0                    # the average member +1
    return d


def _c(monthly_pct: float) -> float:
    """12 months of that return, compounded, in %."""
    return ((1 + monthly_pct / 100) ** 12 - 1) * 100


def test_long_only_leads_with_winners_against_the_index_and_splits_it():
    """Each leg is a 12-month return, compounded, and the legs are then
    subtracted: 2% a month is 26.8% over a year, not 24."""
    lo = mh.long_only(_long())
    top, ew, idx = _c(2.0), _c(1.0), _c(0.5)
    assert lo["top_12m"] == pytest.approx(top) and lo["index_12m"] == pytest.approx(idx)
    assert lo["lead_12m"] == pytest.approx(top - idx)           # 20.66, not 18.0 summed
    assert lo["momentum_12m"] == pytest.approx(top - ew)
    assert lo["breadth_12m"] == pytest.approx(ew - idx)
    assert lo["momentum_12m"] + lo["breadth_12m"] == pytest.approx(lo["lead_12m"])
    out = dp.long_only_html(_long())
    assert "+20.7" in out and "returned +26.8% against the Nifty 500" in out and "+6.2%" in out
    assert "20.7 pts ahead" in out
    assert "(momentum)" in out and "(breadth)" in out and "for reference" in out


def test_long_only_without_the_average_member_shows_the_total_and_the_factor_only():
    out = dp.long_only_html(_long(ew=False))
    assert "+20.7" in out and "(momentum)" not in out and "for reference" in out
    assert mh.long_only(_spreads()) is None                  # no index column: the old card draws
    assert mh.long_only(_long(n=12)) is None


def _flows(n):
    days = pd.bdate_range("2026-11-06", periods=n)
    rows = []
    for k, d in enumerate(days):
        rows += [{"date": d.date().isoformat(), "category": "FII/FPI", "buy": 1, "sell": 1, "net": 1000.0 * (k + 1)},
                 {"date": d.date().isoformat(), "category": "DII", "buy": 1, "sell": 1, "net": -500.0}]
    return pd.DataFrame(rows)


def test_flows_never_lead_with_one_day():
    out = dp.flows_html(_flows(1))
    assert "Collecting: 1 session since 6 Nov 2026" in out and "net bought" not in out


def test_flows_lead_with_the_total_from_five_sessions():
    out = dp.flows_html(_flows(5))
    assert "last 5 sessions to 12 Nov 2026" in out
    assert "₹15,000 Cr</b> net bought" in out and "₹2,500 Cr</b> net sold" in out     # 1+2+3+4+5 thousand; 5 x 500
    assert "data:image/svg+xml;base64," in out and "Since" not in out
    out = dp.flows_html(_flows(25))
    assert "last 20 sessions" in out and "Since 6 Nov 2026 (25 sessions)" in out


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


def test_percentiles_read_as_ordinals():
    assert [dp.ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 42, 100)] == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "42nd", "100th"]


def test_nsdl_flows_lead_with_twenty_days_and_twelve_months():
    days = pd.bdate_range("2025-11-03", "2026-11-06")
    nsdl = pd.DataFrame({"date": days.strftime("%Y-%m-%d"), "equity_net": 100.0})
    out = dp.nsdl_flows_html(nsdl, _flows(1))
    assert "last 20 reporting days" in out and "₹2,000 Cr</b> net bought" in out
    assert "12 months" in out and "DII: 1 session collected from NSE" in out
    assert "data:image/svg+xml;base64," in out
    assert dp.nsdl_flows_html(nsdl.head(3), None) is None
