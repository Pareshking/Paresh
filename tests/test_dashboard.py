"""The dashboard home page (owner, 7 Nov 2026)."""
from __future__ import annotations

import pandas as pd
import pytest

from src.engine import size_leadership as sl


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
    assert r["1M vs 500"] == pytest.approx(r["1M"] - r500)   # points, as on Sectors (audit, 8 Nov 2026)


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










def test_dashboard_is_home_and_the_screener_keeps_an_address():
    src = (__import__("pathlib").Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert 'st.Page(_page_dashboard, title="Dashboard", default=True)' in src
    # /home and /dashboard are redirects to it: the default page is served at "/"
    # only, and /home showed "Page not found" until 8 Nov.
    assert '"home": "Dashboard"' in src and '"dashboard": "Dashboard"' in src
    assert 'st.Page(_page_screener, title="Screener", url_path="screener")' in src


def test_the_on_this_page_line_lists_sections():
    """Owner, 8 Nov 2026: the Breadth page's "On this page" links, on other pages too."""
    from src.ui.page_kit import page_nav_html
    out = page_nav_html([("d-breadth", "Are most stocks taking part?"), ("s-db_risk", "Book at risk")])
    assert out.startswith('<nav class="qp-nav" aria-label="On this page">')
    assert '<a href="#d-breadth">Are most stocks taking part?</a>' in out and 'href="#s-db_risk"' in out
