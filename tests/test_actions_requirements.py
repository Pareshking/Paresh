"""Actions requirements the live book cannot show on a given day (docs/ACTIONS_REQUIREMENTS.md).

Row 12: a holding that cannot be ranked is said so, not hidden. Tested on the live page's Hold
section (actions_page.section_hold); it was tested on actions_view.rows_html, which no page called (S203).
"""
from __future__ import annotations

import pandas as pd

from src.engine.exit_watch import UNKNOWN, Rules, assess
from src.ui.views import actions_page as ap


def test_an_unranked_holding_is_shown_and_named():
    rank_df = pd.DataFrame({"Symbol": ["A"], "Industry": ["Banks"], "Rank": [1], "Qualified": [True]})
    a = assess(rank_df, ["A", "GONE"], Rules())
    gone = a[a["Symbol"] == "GONE"].iloc[0]
    assert gone["status"] == UNKNOWN
    day = pd.Timestamp("2026-11-20")
    plan = ap.Plan(source="Model book", as_of=day, check=pd.Timestamp("2026-11-30"), fill=pd.Timestamp("2026-12-01"),
                   sessions=6, holiday_note="", sells=[], buys=[], holds=["A", "GONE"], next_in_line=[],
                   weights=pd.Series({"A": 0.5, "GONE": 0.5}), assess=a, trails={}, qrank=pd.Series({"A": 1}),
                   rank_df=rank_df, value=None)
    html = "".join(ap.section_hold(plan))
    assert "GONE" in html and "No rule can be checked" in html
