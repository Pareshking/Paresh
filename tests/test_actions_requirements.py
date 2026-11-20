"""Actions requirements the live book cannot show on a given day (docs/ACTIONS_REQUIREMENTS.md).

Row 12: a holding that cannot be ranked is said so, not hidden.
"""
from __future__ import annotations

import pandas as pd

from src.engine.exit_watch import UNKNOWN, Rules, assess
from src.ui.views.actions_view import rows_html


def test_an_unranked_holding_is_shown_and_named():
    rank_df = pd.DataFrame({"Symbol": ["A"], "Industry": ["Banks"], "Rank": [1], "Qualified": [True]})
    a = assess(rank_df, ["A", "GONE"], Rules())
    gone = a[a["Symbol"] == "GONE"].iloc[0]
    assert gone["status"] == UNKNOWN
    html = rows_html(a[a["Symbol"] == "GONE"], {}, Rules())
    assert "GONE" in html and "Not ranked" in html and "No rule can be checked" in html
