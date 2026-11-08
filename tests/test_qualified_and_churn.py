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


def test_the_factor_evidence_is_named_as_the_factors_until_the_portfolio_is_written():
    out = dp.qualified_html(_spreads(last_share=0.05))
    assert "momentum factor" in out and "our strategy" not in out


def _with_portfolio(n=120):
    d = _spreads(n=n)
    d["month"] = pd.period_range("2010-02", periods=n, freq="M").astype(str)
    d["nifty500"] = 1.0
    d["portfolio"] = 1.0 + (d["qualified"] - 0.4) * 5      # fewer qualifiers, smaller lead
    return d


def test_the_portfolio_evidence_replaces_the_factor_and_counts_blocks():
    from src.engine.portfolio_history import excess_by_quarter
    pe = excess_by_quarter(_with_portfolio(), "qualified")
    assert pe["low"] < pe["rest"] and pe["since"] == 2010
    assert [lo for lo, _ in pe["blocks"]] == [2010, 2015] and all(ok for _, ok in pe["blocks"])
    out = dp.qualified_html(_with_portfolio())
    assert "on the Nifty 500 since 2010" in out and "2 of 2 five-year blocks" in out and "trailed the Nifty 500 by" in out
    assert "momentum factor" not in out


def test_portfolio_evidence_needs_its_columns_and_four_years():
    from src.engine.portfolio_history import excess_by_quarter
    assert excess_by_quarter(_spreads(), "qualified") is None
    assert excess_by_quarter(_with_portfolio(n=40), "qualified") is None


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
