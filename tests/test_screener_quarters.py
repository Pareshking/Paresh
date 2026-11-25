"""S171 (2): the Screener "Quarters" table parser and the measuring script's arithmetic."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.loaders.screener_quarters import parse_quarters

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "screener_quarters_TCS.html"   # trimmed from screener.in/company/TCS/consolidated/, 25 Nov 2026


def _script():
    spec = importlib.util.spec_from_file_location("screener_earnings_measure", ROOT / "scripts" / "screener_earnings_measure.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _page(header_cells: str, rows: str, sub: str = "Consolidated Figures in Rs. Crores / <a>View Standalone</a>") -> str:
    return (f'<section id="quarters"><h2>Quarterly Results</h2><p class="sub">{sub}</p>'
            f'<table><thead><tr><th></th>{header_cells}</tr></thead><tbody>{rows}</tbody></table></section>')


def test_tcs_fixture_reads_13_quarters_of_sales_and_profit():
    q = parse_quarters(FIXTURE.read_text(encoding="utf-8"))
    assert q is not None and q.basis == "consolidated" and q.sales_label == "Sales"
    assert len(q.rows) == 13
    assert list(q.rows)[0] == "2023-09-30" and list(q.rows)[-1] == "2026-09-30"
    assert q.rows["2023-09-30"] == {"sales": 59692.0, "net_profit": 11380.0, "basis": "consolidated"}
    assert q.rows["2026-09-30"] == {"sales": 73188.0, "net_profit": 13934.0, "basis": "consolidated"}
    assert not q.mixed()


def test_other_sections_are_ignored():
    # The fixture starts with a "peers" table that also has a "Sales +" cell.
    q = parse_quarters(FIXTURE.read_text(encoding="utf-8"))
    assert all(r["sales"] and r["sales"] > 50000 for r in q.rows.values())


def test_bank_revenue_row_indian_commas_and_negatives():
    page = _page('<th data-date-key="2025-06-30">Jun 2025</th><th data-date-key="2026-06-30">Jun 2026</th>',
                 "<tr><td>Revenue&nbsp;<span>+</span></td><td>1,23,456.5</td><td>1,30,000</td></tr>"
                 "<tr><td>YoY Revenue growth</td><td>+5%</td><td>+6%</td></tr>"
                 "<tr><td>Net Profit&nbsp;+</td><td>-96</td><td></td></tr>")
    q = parse_quarters(page)
    assert q.sales_label == "Revenue"
    assert q.rows["2025-06-30"]["sales"] == 123456.5
    assert q.rows["2025-06-30"]["net_profit"] == -96.0
    assert q.rows["2026-06-30"]["net_profit"] is None


def test_standalone_columns_on_a_consolidated_page_are_marked():
    page = _page('<th data-date-key="2025-06-30">Jun 2025 (S)</th><th data-date-key="2026-06-30">Jun 2026</th>',
                 "<tr><td>Sales +</td><td>10</td><td>12</td></tr><tr><td>Net Profit +</td><td>1</td><td>2</td></tr>")
    q = parse_quarters(page)
    assert q.rows["2025-06-30"]["basis"] == "standalone"
    assert q.rows["2026-06-30"]["basis"] == "consolidated"
    assert q.mixed()


def test_all_standalone_page_and_missing_table():
    page = _page('<th data-date-key="2026-06-30">Jun 2026 (S)</th>',
                 "<tr><td>Sales +</td><td>10</td></tr><tr><td>Net Profit +</td><td>1</td></tr>",
                 sub="Figures in Rs. Crores")
    q = parse_quarters(page)
    assert q.rows["2026-06-30"]["basis"] == "standalone" and not q.mixed()
    assert parse_quarters("<html><section id='profit-loss'></section></html>") is None
    assert parse_quarters("") is None


def test_quarter_labels_and_aggregate_arithmetic(monkeypatch):
    m = _script()
    assert m.quarter_label("2026-06-30") == "Q1FY27"
    assert m.quarter_label("2025-12-31") == "Q3FY26"
    assert m.quarter_label("2025-03-31") == "Q4FY25"
    assert m.year_before("2026-06-30") == "2025-06-30"

    def q(base, now):
        page = _page('<th data-date-key="2025-06-30">Jun 2025</th><th data-date-key="2026-06-30">Jun 2026</th>',
                     f"<tr><td>Sales +</td><td>{base}</td><td>{now}</td></tr>"
                     f"<tr><td>Net Profit +</td><td>{base}</td><td>{now}</td></tr>")
        return parse_quarters(page)

    data = {"A": q(100, 150), "B": q(-50, 10), "C": q(200, 180)}
    monkeypatch.setattr(m, "members", lambda key, qe: {"A", "B", "C", "D"})
    r = m.measure(data, "nifty_50", "2026-06-30", "net_profit")
    # (150 + 10 + 180) / (100 - 50 + 200) - 1 = 36%; median of A +50%, C -10% (B's base is negative)
    assert round(r["agg"], 6) == 36.0
    assert round(r["median"], 6) == 20.0
    assert r["members"] == 4 and r["used"] == 3 and r["nonpos_base"] == 1
    assert r["top"][0][0] == "B"          # +60 of 250 = +24 points


def test_tata_motors_left_out_of_q2_and_q3_fy26():
    m = _script()
    assert "TMPV" not in m.members("nifty_50", "2025-12-31")
    assert "TMPV" not in m.members("nifty_50", "2025-09-30")
    assert "TMPV" in m.members("nifty_50", "2026-06-30")
