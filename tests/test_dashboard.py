"""The dashboard home page (owner, 7 Nov 2026)."""
from __future__ import annotations

import pandas as pd
import pytest

from src.engine import size_leadership as sl
from src.ui.views import dashboard_view as dv


def _levels(dates, factor=1.0, weekly_from=None):
    rows = []
    for k, start in (("nifty50", 100), ("nifty_midcap150", 200), ("nifty_smallcap250", 300),
                     ("nifty_microcap250", 400)):
        for i, d in enumerate(dates):
            if weekly_from is not None and d < weekly_from and d.weekday() != 4:
                continue
            rows.append({"date": d, "index": k, "close": start * (1 + 0.001 * i) * factor,
                         "source": "test"})
    return pd.DataFrame(rows)


def test_every_window_opens_on_one_shared_session_and_relative_is_against_the_500():
    dates = pd.bdate_range("2026-04-01", "2026-11-06")
    lv = _levels(dates, weekly_from=pd.Timestamp("2026-06-01"))   # sparse before June, like Screener's chart
    n500 = pd.Series([1000 * (1 + 0.002 * i) for i in range(len(dates))], index=dates)
    res = sl.size_leadership(lv, n500)
    assert res is not None and res.end == pd.Timestamp("2026-11-06")
    assert res.starts[1] == pd.Timestamp("2026-10-06")
    assert res.starts[6].weekday() == 4          # weekly stretch: the first Friday on/after 6 May
    r = res.table.loc["Nifty 50"]
    r500 = res.table.loc["Nifty 500", "1M"]
    assert r["1M vs 500"] == pytest.approx((1 + r["1M"]) / (1 + r500) - 1)


def test_the_table_is_shown_only_when_the_files_nifty_50_matches_nse():
    dates = pd.bdate_range("2026-09-01", "2026-11-06")
    lv = _levels(dates)
    nse = lv[lv["index"] == "nifty50"].set_index("date")["close"]
    assert sl.cross_check(lv, nse)[0]
    assert not sl.cross_check(lv, nse * 1.01)[0]
    assert not sl.cross_check(lv[lv["index"] != "nifty50"], nse)[0]


def test_missing_an_index_leaves_the_table_out():
    dates = pd.bdate_range("2026-09-01", "2026-11-06")
    lv = _levels(dates)
    assert sl.size_leadership(lv[lv["index"] != "nifty_microcap250"], pd.Series(1.0, index=dates)) is None


def test_the_answer_line_uses_the_figures_below_it():
    line = dv.answer_line(0.023, 0.071, 1, 2, pd.Timestamp("2026-11-30"))
    assert line == ("The book is +2.3% this month against +7.1% for the Nifty 500; 2 would be sold "
                    "if the month ended today; 1 is close to a rule; next rebalance Mon 30 Nov.")
    assert "no holding is close to a rule" in dv.answer_line(float("nan"), float("nan"), 0, 0,
                                                             pd.Timestamp("2026-11-30"))


def test_book_at_risk_lists_least_room_first_with_its_rule():
    from src.engine.exit_watch import Rules, assess
    rows = [{"Symbol": f"S{i}", "Rank": i, "Above 50 EMA": True, "Near 52W High": True,
             "% 50 EMA": 30.0, "% High": 0.0, "Industry": "X"} for i in range(1, 41)]
    rows[0].update(Symbol="LAURUSLABS", **{"% 50 EMA": 100 * (1 / (1 - 0.126) - 1)})
    rows[15].update(Symbol="PVRINOX", **{"% 50 EMA": 100 * (1 / (1 - 0.138) - 1)})
    rows[2].update(Symbol="SHILPAMED", **{"% 50 EMA": 100 * (1 / (1 - 0.028) - 1)})
    a = assess(pd.DataFrame(rows), ["LAURUSLABS", "PVRINOX", "SHILPAMED"], Rules())
    out = dv._at_risk_html(a, Rules())
    order = [out.index(s) for s in ("SHILPAMED", "PVRINOX", "LAURUSLABS")]
    assert order == sorted(order)
    assert "rank buffer · 24 places" in out and "50D EMA · 2.8%" in out


def test_dashboard_is_home_and_the_screener_keeps_an_address():
    src = (dv.__file__ and open(__import__("pathlib").Path(dv.__file__).parents[3] / "app.py",
                                encoding="utf-8").read())
    assert 'st.Page(_page_dashboard, title="Dashboard", default=True)' in src
    # /home and /dashboard are redirects to it: the default page is served at "/"
    # only, and /home showed "Page not found" until 8 Nov.
    assert '"home": "Dashboard"' in src and '"dashboard": "Dashboard"' in src
    assert 'st.Page(_page_screener, title="Screener", url_path="screener")' in src
