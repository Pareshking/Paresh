"""Dashboard sentences on a month's first session and in a selling month (S203 draft, 24 Nov 2026).

With no Nifty Total Market figure for the month yet, the headline called abs(None) and the page crashed;
a momentum range crossing zero read "up −1.2 to 3.4%"; a selling month read "have bought −₹5,000 Cr".
"""
from __future__ import annotations

import pandas as pd

from src.engine import dashboard_insights as di
from src.ui.views import dashboard_home_view as dv


def _bm(book, market, mom):
    return di.BookMonth(book_mtd=book, market_mtd=market, book_ytd=None, market_ytd=None, months_ahead=0, months=0,
                        behind_months=[], momentum_mtd=mom, momentum_ytd={}, ahead_of_momentum=0, level_with_momentum=0)


def test_no_market_figure_yet_does_not_crash():
    html = "".join(x for x in dv.section_book(_bm(0.4, None, {}), None, None, pd.Timestamp("2026-12-01")) if isinstance(x, str))
    assert "Nifty Total Market has no December figure yet" in html


def test_a_range_crossing_zero_reads_from_to():
    # S203 dash.book.3: the approved template ("range from −1.2% to +3.4%") replaced "between ... and ...".
    two = lambda a, b: {"nifty200_mom30": a, "nifty500_mom50": b}  # noqa: E731
    assert dv._momentum_range(two(-1.2, 3.4)) == "NSE’s 2 momentum indices range from −1.2% to +3.4%."
    assert dv._momentum_range(two(0.5, 2.0)) == "NSE’s 2 momentum indices are up 0.5% to 2.0%."
    assert dv._momentum_range(two(-2.1, -0.5)) == "NSE’s 2 momentum indices are down 0.5% to 2.1%."


def test_a_selling_month_says_sold():
    f = di.Flows(as_of=pd.Timestamp("2026-12-05"), mtd=-5000.0, month_rank=9, months_in_record=60, prior_record=None,
                 last20=-5000.0, last20_is_record=False, streak=0, before=12000.0, before_selling_months=3,
                 monthly=[], trail20=[])
    html = dv.flows_head(f)
    assert "have sold" in html and "bought −" not in html and "bought -" not in html


def test_book_too_short_reads_one_colon_in_a_note():
    from src.ui import missing_words as mw
    note = "No risk figures yet: " + mw.book_too_short(63, 20) + "."
    assert note.count(":") == 1 and "63 sessions" in note and "the book has 20" in note


def test_flow_evidence_counts_only_months_with_a_next_month():
    import numpy as np
    import pandas as pd
    from src.engine.dashboard_insights import flow_evidence
    months = pd.period_range("2015-01", "2018-12", freq="M")
    rng = np.random.default_rng(0)
    nsdl = pd.DataFrame({"date": [m.to_timestamp(how="end").normalize() for m in months]
                         + [pd.Timestamp("2019-01-15")],
                         "equity_net": list(rng.normal(0, 1000, len(months))) + [5.0]})
    spreads = pd.DataFrame({"month": [str(m) for m in months], "top": rng.normal(1, 2, len(months)),
                            "nifty500": rng.normal(0, 2, len(months))})
    days = pd.date_range("2015-01-01", "2018-12-31", freq="B")
    bench = pd.DataFrame({"nifty500": np.linspace(100, 150, len(days)), "nifty50": np.linspace(100, 140, len(days))},
                         index=days)
    ev = flow_evidence(nsdl, spreads, bench)
    assert ev.tested == ev.months - 1          # the last month has no next month to test
    assert ev.tested_heavy <= ev.heavy_months
