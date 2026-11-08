"""How many stocks qualify, and the next rebalance's churn (TODO S110, items 2 and 5)."""
import numpy as np
import pandas as pd

from src.ui.views import dashboard_panels as dp
from src.ui.views import dashboard_view as dv


def _spreads(n=60, last_share=0.15):
    rng = np.random.default_rng(0)
    share = np.r_[rng.uniform(0.1, 0.9, n - 1), last_share]
    spread = (share - 0.4) * 10 + rng.normal(0, 1, n)     # fewer qualifiers, weaker next month
    dates = pd.date_range("2020-01-31", periods=n, freq="ME")
    return pd.DataFrame({"month": dates.to_period("M").astype(str), "date": dates.strftime("%Y-%m-%d"),
                         "spread": spread, "qualified": share})


def test_a_low_share_reads_few_with_the_evidence():
    out = dp.qualified_html(_spreads(last_share=0.05))
    assert out and "Few</span>" in out and "fewest" in out and "Nifty 500" in out


def test_no_qualified_column_or_too_short_history_draws_nothing():
    assert dp.qualified_html(_spreads().drop(columns="qualified")) is None
    assert dp.qualified_html(_spreads(n=10)) is None
    assert dp.qualified_html(None) is None


def test_the_churn_row_compares_the_plan_with_the_records_months():
    books = {f"2026-{m:02d}": pd.DataFrame({"Action": ["Bought"] * b + ["Held"] * (20 - b)})
             for m, b in ((1, 20), (2, 9), (3, 5))}
    row = dv._churn_row({"month_books": books}, 2, 20)
    assert "2 of 20 would change" in row and "against 7 a month" in row and "(5 to 9)" in row
    assert dv._churn_row({}, 2, 20) == ""
