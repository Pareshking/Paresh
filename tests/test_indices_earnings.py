"""S171: NSE's earnings review file (kept for the weekly check), and the Indices page, which shows our calculation
from Screener's company results (owner, 25 Nov 2026: "We will use Screener data only")."""
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


def test_the_section_shows_our_calculation_for_six_indices_and_names_its_source():
    lt = er.ours()
    assert lt is not None and set(lt.values) == set(er.OUR_INDICES)
    html = iv.section_earnings(lt)[0]
    q = er.quarter_label(lt.quarter)
    assert q in html and "Our calculation from companies&#x27; reported results" in html and "last updated" in html
    assert "Screener" not in html and "Saturday" not in html          # owner, 25 Nov 2026: no source, no schedule
    assert "Rajesh Exports" in html and "fraud" not in html            # left out, named; the page states no charge
    assert "Microcap 250" in html and "NSE" not in html and "PDF" not in html
    assert iv.earnings_headline(lt).startswith(f"In {q} the Nifty 500's profit ")


def test_the_page_profit_is_the_chosen_measure():
    df = pd.DataFrame([
        {"quarter": "Q2FY27", "index": "Nifty 500", "measure": m, "value_pct": v, "as_of": "2026-11-28"}
        for m, v in (("pat_agg_yoy", 7.3), ("pat_xoi_agg_yoy", 30.3), ("sales_agg_yoy", 22.3))])
    lt = er.ours(df)
    want = {"pat": 7.3, "pat_xoi": 30.3}[er.PROFIT]
    assert lt.values["Nifty 500"]["pat_agg_yoy"] == want and lt.values["Nifty 500"]["sales_agg_yoy"] == 22.3
    assert lt.published == pd.Timestamp("2026-11-28")


def test_no_file_no_section():
    assert iv.section_earnings(None) == []


def test_history_runs_every_quarter_from_q1_fy22_with_q3_fy26_ex_tata_motors():
    h = er.history("Nifty 500", "pat_agg_yoy")
    assert len(h) == 21 and h.index[0] == pd.Timestamp("2021-06-30") and h.index[-1] == pd.Timestamp("2026-06-30")
    assert h[pd.Timestamp("2025-12-31")] == 18.2                     # ex-Tata Motors (owner, 25 Nov 2026); 15.9 with it
    assert er.history("Nifty 50", "pat_agg_yoy")[pd.Timestamp("2025-12-31")] == 12.8
    assert er.quarter_end("Q4FY26") == pd.Timestamp("2026-03-31") and er.quarter_end("Q3FY26") == pd.Timestamp("2025-12-31")


def test_the_history_chart_reads_our_quarters():
    parts = iv.earnings_history()
    assert len(parts) == 2
    h = er.ours_history("Nifty 500", "pat_agg_yoy")
    first, last = er.quarter_label(iv._quarters([h.index[0]])[0]), er.quarter_label(iv._quarters([h.index[-1]])[0])
    how = str(parts[1])
    assert f"{first} to {last}" in how and "Tata Motors" in how and "Screener" not in how and "Saturday" not in how


def test_the_heading_rounds_as_the_table_does():
    # Live, 25 Nov 2026: 30.25 read "30.2%" in the heading and "+30.3%" in the table.
    df = pd.DataFrame([{"quarter": "Q2FY27", "index": "Nifty 500", "measure": m, "value_pct": v, "as_of": "2026-11-25"}
                       for m, v in ((f"{er.PROFIT}_agg_yoy", 30.25), (f"{er.PROFIT}_median_yoy", 20.95))])
    assert iv.earnings_headline(er.ours(df)) == ("In Q2 FY27 the Nifty 500's profit rose 30.3% from a year earlier; "
                                                 "the median company's profit rose 21.0%.")
