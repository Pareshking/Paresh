"""NSE's Corporate Earnings Review table (S171 part 1): the committed CSV pinned to figures read in the PDFs,
and the parser on text copied from them (pdftotext -layout). The PDFs are not in the repository; set
NSE_EARNINGS_PDFS to a folder holding them (scripts/nse_earnings_review.py --mode download) to rebuild the
CSV from them and compare."""
import csv
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "reference" / "nse_earnings_review.csv"
_spec = importlib.util.spec_from_file_location("nse_earnings_review", ROOT / "scripts" / "nse_earnings_review.py")
ner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ner)


def _rows():
    with open(CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _value(quarter, index, measure):
    hits = [r for r in _rows() if (r["quarter"], r["index"], r["measure"]) == (quarter, index, measure)]
    assert len(hits) == 1, (quarter, index, measure, hits)
    return float(hits[0]["value_pct"]), hits[0]


# Figures read in the PDFs by eye on 25 Nov 2026 (issue, PDF page).
KNOWN = [
    # Q1 FY27, p34 Table 26 Median (%) column
    ("Q1FY27", "Nifty 50", "pat_median_yoy", 19.2),
    ("Q1FY27", "Nifty Next 50", "pat_median_yoy", 16.3),
    ("Q1FY27", "Nifty Midcap 150", "pat_median_yoy", 20.1),
    ("Q1FY27", "Nifty Smallcap 250", "pat_median_yoy", 18.6),
    ("Q1FY27", "Nifty 500", "pat_median_yoy", 18.8),
    # Q1 FY27, p23 Table 13 Median column
    ("Q1FY27", "Nifty Smallcap 250", "sales_median_yoy", 17.2),
    ("Q1FY27", "Nifty 50", "sales_median_yoy", 16.8),
    # Q1 FY27 aggregates: tables 6 and 20, and the prose for the three middle indices
    ("Q1FY27", "Nifty 50", "pat_agg_yoy", 11.8),
    ("Q1FY27", "Nifty Next 50", "pat_agg_yoy", 4.5),
    ("Q1FY27", "Nifty Midcap 150", "pat_agg_yoy", 6.1),
    ("Q1FY27", "Nifty Smallcap 250", "pat_agg_yoy", 33.9),
    ("Q1FY27", "Nifty 500", "pat_agg_yoy", 11.1),
    ("Q1FY27", "Nifty 50", "sales_agg_yoy", 18.4),
    ("Q1FY27", "Nifty 500", "sales_agg_yoy", 18.9),
    # older issues, tables 1/6/9/14
    ("Q1FY22", "Nifty 50", "pat_agg_yoy", 104.3),
    ("Q1FY22", "Nifty 500", "sales_agg_yoy", 41.8),
    ("Q2FY23", "Nifty 500", "pat_agg_yoy", -8.4),
    ("Q4FY23", "Nifty 50", "pat_agg_yoy", 11.3),
    ("Q2FY24", "Nifty 500", "pat_median_yoy", 16.9),
    ("Q3FY26", "Nifty 50", "sales_agg_yoy", 12.5),   # ex-Tata Motors (owner, 25 Nov 2026)
    # gap quarters, read from the next issue's previous-quarter column
    ("Q4FY26", "Nifty 50", "sales_agg_yoy", 11.2),
    ("Q4FY26", "Nifty 500", "pat_agg_yoy", 15.3),
    ("Q2FY22", "Nifty 500", "pat_median_yoy", 16.7),
]


@pytest.mark.parametrize("quarter,index,measure,value", KNOWN)
def test_known_figures(quarter, index, measure, value):
    got, _ = _value(quarter, index, measure)
    assert got == pytest.approx(value)


def test_every_row_carries_its_evidence():
    rows = _rows()
    assert rows and list(rows[0]) == ner.COLUMNS
    keys = [(r["quarter"], r["index"], r["measure"]) for r in rows]
    assert len(keys) == len(set(keys))
    for r in rows:
        assert r["index"] in ner.INDICES and r["measure"] in ner.MEASURES
        assert r["quarter"] in ner.ISSUES or r["quarter"] in ner.GAPS
        assert r["issue"] in ner.ISSUES and r["pdf_url"] == ner.ISSUES[r["issue"]][0]
        assert r["pdf_url"].startswith("https://nsearchives.nseindia.com/") and r["pdf_url"].endswith(".pdf")
        assert int(r["page"]) >= 1 and r["published"]
        v = float(r["value_pct"])
        # the value is printed in the quoted row or sentence: 14 as "14%", -2.3 as "(2.3)"
        printed = {f"{v:g}", f"{v:.1f}", f"({abs(v):g})", f"({abs(v):.1f})"}
        assert any(re.search(r"(?<![\d.])" + re.escape(p) + r"(?!\d|\.\d)", r["quote"]) for p in printed), r
        assert r["source"] in ("table", "prose", "table, later issue")
        assert (r["source"] == "table, later issue") == (r["quarter"] != r["issue"])


def test_every_quarter_since_fy22_is_covered_or_named_a_gap():
    have = {r["quarter"] for r in _rows()}
    for fy in range(22, 28):
        for q in range(1, 5):
            quarter = f"Q{q}FY{fy}"
            if (fy, q) > (27, 2):
                continue
            assert quarter in have or quarter in ner.GAPS, quarter
    # every quarter with an issue has the two headline aggregates for both broad indices
    for quarter in list(ner.ISSUES) + [g for g in ner.GAPS if g != "Q2FY27"]:
        for index in ("Nifty 50", "Nifty 500"):
            for measure in ("sales_agg_yoy", "pat_agg_yoy"):
                _value(quarter, index, measure)


def test_the_known_disagreements_inside_an_issue_are_recorded():
    _, r = _value("Q4FY23", "Nifty 50", "pat_agg_yoy")
    assert "p1 prose says 11.1" in r["cross_check"]
    _, r = _value("Q4FY22", "Nifty 500", "pat_agg_yoy")
    assert "p1 prose says 24.6" in r["cross_check"] and "p2 prose agrees" in r["cross_check"]


def test_q3_fy26_aggregates_exclude_tata_motors_as_the_owner_decided():
    """Owner, 25 Nov 2026: Q3 FY26 reads the 'ex-Tata Motors' rows (Tata Motors demerged 1 Oct 2025), as Q2 FY26's
    index row and NSE's own summary do. Pinned against the Q3 FY26 PDF, Dec-25 YoY column: Tables 1, 7, 11, 24."""
    for index, measure, value, with_tata in (("Nifty 50", "sales_agg_yoy", 12.5, 9.2), ("Nifty 50", "pat_agg_yoy", 12.8, 8.9),
                                             ("Nifty 500", "sales_agg_yoy", 11.1, 9.6), ("Nifty 500", "pat_agg_yoy", 18.2, 15.9)):
        _, r = _value("Q3FY26", index, measure)
        assert float(r["value_pct"]) == value
        assert f"{index} ex-Tata Motors" in r["quote"] and f"with Tata Motors gives {with_tata:g}" in r["quote"]
    assert "Q3FY26" in ner.EX_TATA_QUARTERS


def test_month_labels_and_numbers():
    assert ner.month_quarter("Jun-26") == "Q1FY27"
    assert ner.month_quarter("Sep-21") == "Q2FY22"
    assert ner.month_quarter("Dec-25") == "Q3FY26"
    assert ner.month_quarter("Mar-26") == "Q4FY26"
    assert ner.number("(2.3)") == -2.3 and ner.number("1,234.5") == 1234.5 and ner.number("-0.6") == -0.6


# Text as pdftotext -layout prints it (Q1 FY27 issue, shortened).
_TABLE = """Table {n}: Sector-wise {what} growth of {index} companies
                                                                   QoQ growth                                                     YoY growth
 Sector
                                                     Jun-25               Mar-26               Jun-26                  Jun-25          Mar-26       Jun-26
 Energy                                                  -6.5                  8.3                    9.0                 1.0               8.7       26.7
 {index}                                                {a}
 {index} ex-Energy                                      -3.5                  8.2                   -0.6                 6.4              12.1       15.7
Source: CMIE Prowess, LSEG workspace, NSE EPR.
Note: 1. The above table provides data for companies in the {index} index as of end of respective quarters.
"""
_MEDIAN = """Table 26: Segment-wise distribution of companies based on YoY aggregate and median PAT growth across Nifty
500 constituents
 Index                             <=0%         0% - 10%         10% -20%         20% - 30%       30% - 40%     40% - 50%     > 50%    Median (%)

 Nifty 50                                9                 8                9                9             6           2          7        19.2%
 Nifty Smallcap 250                    61                24               36                23            11          14         59        18.6%
Source: CMIE Prowess, LSEG Workspace, NSE
Note: The above chart provides data for companies in the Nifty 500 index as of June 30th, 2026.
"""


def _pages():
    t = [_TABLE.format(n=1, what="net sales", index="Nifty 50", a="-4.2    8.2    1.8    5.0    11.2    18.4"),
         _TABLE.format(n=6, what="PAT", index="Nifty 50", a="(1.0)   2.0   3.0   (4.0)   8.2   11.8"),
         _TABLE.format(n=9, what="net sales", index="Nifty 500", a="1.0   2.0   3.0   4.0   11.2   18.9"),
         _TABLE.format(n=20, what="PAT", index="Nifty 500", a="1.0   2.0   3.0   4.0   15.3   11.1"),
         _MEDIAN]
    return t


def test_the_index_row_of_each_sector_table_is_read():
    rows = ner.aggregate_rows("Q1FY27", _pages())
    got = {(r["quarter"], r["index"], r["measure"]): r["value_pct"] for r in rows}
    assert got[("Q1FY27", "Nifty 50", "sales_agg_yoy")] == 18.4          # not the ex-Energy row's 15.7
    assert got[("Q1FY27", "Nifty 50", "pat_agg_yoy")] == 11.8
    assert got[("Q1FY27", "Nifty 500", "pat_agg_yoy")] == 11.1
    assert got[("Q4FY26", "Nifty 500", "pat_agg_yoy")] == 15.3           # Q4 FY26 has no issue: kept
    page = {r["measure"] + r["index"]: r["page"] for r in rows if r["quarter"] == "Q1FY27"}
    assert page["pat_agg_yoyNifty 500"] == 4


def test_a_table_whose_last_column_is_not_the_issues_quarter_is_refused():
    with pytest.raises(ValueError, match="last YoY column"):
        ner.aggregate_rows("Q2FY27", _pages())


def test_the_median_column_is_read_and_the_contents_page_skipped():
    toc = ("Table 26: Segment-wise distribution of companies based on YoY aggregate and median PAT growth across"
           " Nifty 500\nconstituents ......................................34\n")
    rows = ner.median_rows("Q1FY27", [toc, _MEDIAN])
    got = {r["index"]: (r["value_pct"], r["page"]) for r in rows if r["measure"] == "pat_median_yoy"}
    assert got == {"Nifty 50": (19.2, 2), "Nifty Smallcap 250": (18.6, 2)}


def test_a_prose_sentence_must_be_on_its_page():
    pages = ["x"] * 41 + ["Aggregate PAT of Nifty Smallcap 250 companies grew by a strong 33.9% YoY\n in Q1 FY27."]
    saved = ner.PROSE
    try:
        ner.PROSE = [e for e in saved if e[0] == "Q1FY27" and e[4] == 42]
        assert [r["value_pct"] for r in ner.prose_rows("Q1FY27", pages)] == [33.9]
        with pytest.raises(ValueError, match="not found"):
            ner.prose_rows("Q1FY27", ["x"] * 42)
    finally:
        ner.PROSE = saved


def test_a_second_statement_that_differs_is_a_conflict():
    base = {"index": "Nifty 50", "measure": "pat_agg_yoy", "issue": "Q4FY23", "quarter": "Q4FY23"}
    rows, conflicts = ner.assemble({"Q4FY23": [
        {**base, "value_pct": 11.3, "source": "table", "page": 12, "quote": "row: Nifty 50 ... 11.3"},
        {**base, "value_pct": 11.1, "source": "prose", "page": 1, "quote": "11.1%/10.3%", "role": "check"},
    ]})
    assert len(rows) == 1 and rows[0]["value_pct"] == 11.3 and len(conflicts) == 1


@pytest.mark.skipif(not os.environ.get("NSE_EARNINGS_PDFS"), reason="the PDFs are not in the repository")
def test_the_csv_is_what_the_pdfs_give(tmp_path):
    # in a child process with -I: the PDFs are downloaded files
    out = tmp_path / "rebuilt.csv"
    subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "nse_earnings_review.py"), "--mode", "build",
                    "--raw", os.environ["NSE_EARNINGS_PDFS"], "--out", str(out)], check=True, capture_output=True)
    assert out.read_text(encoding="utf-8") == CSV.read_text(encoding="utf-8")
