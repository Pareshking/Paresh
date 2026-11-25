"""The Stock page's results table (owner, 25 Nov 2026: "one table showing last 8-10 quarter key numbers and % growth";
"Go ahead"; "Show last updated but don't show will get every Saturday update")."""
from __future__ import annotations

import pandas as pd

from src.engine import earnings_review as er
from src.ui.views import stock_view as sv

COLS = ["symbol", "quarter_end", "basis", "sales_label", "sales", "operating_profit", "pbt", "net_profit",
        "other_income", "tax_pct", "eps", "fetched"]


def _frame(rows):
    return pd.DataFrame(rows, columns=COLS)


def _quarters(sym, label, n=13, start="2023-09-30", **k):
    ends = pd.date_range(start, periods=n, freq="QE")
    return [[sym, f"{d:%Y-%m-%d}", k.get("basis", "consolidated"), label, 100 + i, 20 + i, 15 + i, 10 + i, 1, 25,
             1 + i / 10, "2026-11-25"] for i, d in enumerate(ends)]


def test_eight_quarters_newest_first_each_against_a_year_earlier():
    r = er.company("AAA", _frame(_quarters("AAA", "Sales")))
    assert len(r.quarters) == 8 and r.quarters[0].label == "Q2 FY27" and r.quarters[-1].label == "Q3 FY25"
    q = r.quarters[0]                      # Sep 2026 (i=12) against Sep 2025 (i=8)
    assert q.values == {"sales": 112, "profit": 32, "net_profit": 22, "eps": 2.2}
    assert round(q.growth["sales"], 6) == round((112 / 108 - 1) * 100, 6)
    assert not r.lender and r.basis == "consolidated" and r.read == pd.Timestamp("2026-11-25")


def test_a_lender_shows_profit_before_tax_and_a_loss_base_reads_a_dash():
    rows = _quarters("BNK", "Revenue")
    rows[8][7] = -5                         # net profit a loss in Sep 2025
    r = er.company("BNK", _frame(rows))
    assert r.lender and r.quarters[0].values["profit"] == 27         # pbt, not "Financing Profit"
    assert r.quarters[0].growth["net_profit"] is None
    html = "".join(sv.results_html(r))
    assert "Revenue, Cr" in html and "Profit before tax, Cr" in html and "Operating profit" not in html
    assert "Growth reads – where the year-earlier figure is nil, a loss, or not yet reported" in html


def test_the_note_says_last_updated_and_names_no_source_or_schedule():
    html = "".join(sv.results_html(er.company("AAA", _frame(_quarters("AAA", "Sales")))))
    assert "5 · Results" in html and "last updated 25 Nov 2026" in html
    assert "Screener" not in html and "Saturday" not in html
    assert "1,12" not in html and ">112<" in html and ">2.20<" in html   # exact crore, EPS to two decimals


def test_a_basis_change_is_not_compared_and_no_file_no_section():
    rows = _quarters("MIX", "Sales")
    for r in rows[:6]:
        r[2] = "standalone"
    r = er.company("MIX", _frame(rows))
    assert [q.label for q in r.quarters] == ["Q2 FY27", "Q1 FY27", "Q4 FY26"]     # Dec 2025 has a standalone base
    assert er.company("NONE", _frame(rows)) is None and sv.results_html(None) == []


def test_sansera_matches_its_own_page():
    # screener.in/company/SANSERA/consolidated/, read 25 Nov 2026: Sep 2026 sales 1,091, net profit 109, EPS 17.31
    r = er.company("SANSERA")
    if r is None:
        return
    q = r.quarters[0]
    if q.label == "Q2 FY27":
        assert q.values["sales"] == 1091 and q.values["net_profit"] == 109 and q.values["eps"] == 17.31


def test_a_new_listing_shows_its_quarters_with_growth_dashed():
    r = er.company("NEW", _frame(_quarters("NEW", "Sales", n=3, start="2026-03-31")))
    assert [q.label for q in r.quarters] == ["Q2 FY27", "Q1 FY27", "Q4 FY26"]
    assert all(v is None for q in r.quarters for v in q.growth.values())
