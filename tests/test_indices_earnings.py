"""S171 (3): the Indices page shows NSE's latest earnings review figures beside the P/E."""
from __future__ import annotations

import pandas as pd

from src.engine import earnings_review as er
from src.ui.views import indices_view as iv


def test_latest_is_the_newest_quarter_with_its_own_issue():
    lt = er.latest()
    assert lt is not None
    assert lt.quarter == "Q1FY27" and lt.published == pd.Timestamp("2026-09-16")
    v = lt.values
    # Pinned against NSE's Q1 FY27 PDF (p15, p29, p30, p34, p42), checked by hand 25 Nov 2026.
    assert v["Nifty 50"]["pat_agg_yoy"] == 11.8 and v["Nifty 500"]["pat_agg_yoy"] == 11.1
    assert v["Nifty Smallcap 250"]["pat_agg_yoy"] == 33.9 and v["Nifty Midcap 150"]["pat_median_yoy"] == 20.1
    assert v["Nifty Next 50"]["sales_agg_yoy"] is None          # NSE gave no Next 50 revenue total this quarter


def test_a_quarter_filled_from_a_later_issue_is_not_the_latest():
    df = pd.DataFrame([
        {"quarter": "Q1FY27", "index": "Nifty 500", "measure": "pat_agg_yoy", "value_pct": 11.1, "issue": "Q1FY27",
         "published": "2026-09-16", "pdf_url": "u1"},
        {"quarter": "Q2FY27", "index": "Nifty 500", "measure": "pat_agg_yoy", "value_pct": 9.0, "issue": "Q3FY27",
         "published": "2027-03-01", "pdf_url": "u2"},
    ])
    assert er.latest(df).quarter == "Q1FY27"


def test_the_section_names_the_quarter_source_and_shows_a_dash_for_a_figure_nse_did_not_publish():
    html = iv.section_earnings(er.latest())[0]
    assert "Q1 FY27" in html and "16 Sep 2026" in html and "nsearchives.nseindia.com" in html
    assert "+33.9%" in html and "–" in html and "did not publish" in html
    assert iv.earnings_headline(er.latest()) == (
        "In Q1 FY27 the Nifty 500's profit rose 11.1% from a year earlier; the median company's profit rose 18.8%.")


def test_no_file_no_section():
    assert iv.section_earnings(None) == []
