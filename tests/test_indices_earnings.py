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


def test_the_latest_table_counts_companies_reported_against_the_index_size():
    # Owner, 25 Nov 2026: "we can show how many companies out of universe reported".
    lt = er.ours()
    assert set(lt.reported) == set(er.OUR_INDICES)
    used, size = lt.reported["Nifty 50"]
    assert size == 50 and 0 < used <= 50                              # the index's size, before Tata Motors is left out
    html = iv.section_earnings(lt)[0]
    assert "Companies reported" in html and f"{used} of 50" in html


def test_the_quarter_coming_in_has_its_own_block_and_stays_out_of_the_finished_tables():
    df = pd.DataFrame([{"quarter": q, "quarter_end": qe, "index": "Nifty 500", "measure": m, "value_pct": v,
                        "members": 500, "size": 500, "used": u, "complete": c, "as_of": "2027-01-23"}
                       for q, qe, u, c in (("Q2FY27", "2026-09-30", 495, True), ("Q3FY27", "2026-12-31", 212, False))
                       for m, v in ((f"{er.PROFIT}_agg_yoy", 12.0), ("sales_agg_yoy", 9.0))])
    assert er.ours(df).quarter == "Q2FY27" and er.partial(df).quarter == "Q3FY27"
    html = iv.section_partial(er.partial(df))
    assert "Q3 FY27 so far: 212 of 500 Nifty 500 companies have reported." in html and "move as the rest report" in html
    assert er.partial(df[df["complete"]]) is None and iv.section_partial(None) == ""
    assert list(er.ours_history("Nifty 500", "pat_agg_yoy", df).index) == [pd.Timestamp("2026-09-30")]


def test_an_index_with_too_few_reported_reads_a_dash_so_far():
    pt = er.Latest(quarter="Q3FY27", published=pd.Timestamp("2027-01-23"), pdf_url="",
                   values={"Nifty 50": {"pat_agg_yoy": 40.0, "sales_agg_yoy": 20.0}}, reported={"Nifty 50": (3, 50)})
    html = iv.section_partial(pt)
    assert "+40.0%" not in html and "3 of 50" in html


def test_the_quarter_coming_in_is_the_top_row_of_the_quarterly_tables(monkeypatch):
    pt = er.Latest(quarter="Q3FY27", published=pd.Timestamp("2027-01-23"), pdf_url="",
                   values={i: {"pat_agg_yoy": 12.0, "sales_agg_yoy": 9.0} for i in er.OUR_INDICES},
                   reported={**{i: (40, 50) for i in er.OUR_INDICES}, "Nifty 500": (212, 500), "Nifty 50": (3, 50)})
    monkeypatch.setattr(er, "partial", lambda df=None: pt)
    html = iv.earnings_quarters()[0]
    first = html.split("<tbody>")[1].split("</tr>")[0]
    assert "Q3 FY27 so far" in first and "212 of 500 reported" in first and "+12.0%" in first
    assert first.count("–") == 1                                       # the Nifty 50, 3 of 50: too few yet
