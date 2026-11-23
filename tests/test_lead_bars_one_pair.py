"""S193 (owner, 23 Nov 2026): every bar of "Momentum's lead, every month" is one pair, the top 100
of the ranking less the Nifty 500. The month so far (Nifty500 Momentum 50 less Nifty Total Market)
was drawn as the last bar."""
import pandas as pd

from src.ui.views.dashboard_home_view import _lead_bars


def test_the_month_so_far_is_not_drawn_as_a_bar():
    spreads = pd.DataFrame({"month": [f"2026-{m:02d}" for m in range(1, 11)],
                            "top": [2.0] * 10, "nifty500": [1.0] * 10})
    lead = [("Month so far", -5.5, "Nifty500 Momentum 50")]
    bars = _lead_bars(spreads, lead)
    assert bars["values"] == [1.0] * 10
    assert bars["full"][-1] == "Oct 2026" and bars["lastNote"] == ""
