"""NSDL's FPI daily trends page parses to equity rows per reporting date (S106)."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("nsdl", Path(__file__).resolve().parents[1] / "scripts" / "nsdl_fpi.py")
nsdl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nsdl)


def _row(*cells):
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


PAGE = "<table>" + "".join([
    _row("Reporting Date", "Debt/Equity", "Investment Route", "Gross Purchases", "Gross Sales", "Net", "US$", "FX"),
    # The 1 Oct 2026 block as NSDL's archive printed it (probe on PR #479).
    _row("01-Oct-2026", "Equity", "Stock Exchange", "17667.90", "27237.47", "(9569.57)", "(997.00)", "Rs.95.9832"),
    _row("Primary market &amp; others", "337.70", "0.01", "337.69", "35.18"),
    _row("Sub-total", "18005.60", "27237.48", "(9231.88)", "(961.82)"),
    _row("Debt-General Limit", "Stock Exchange", "310.70", "983.38", "(672.68)", "(70.08)"),
    _row("Primary market &amp; others", "192.55", "188.99", "3.56", "0.37"),
    _row("Sub-total", "503.25", "1172.37", "(669.12)", "(69.71)"),
    _row("05-Oct-2026", "Equity", "Stock Exchange", "12794.16", "22429.12", "(9634.96)", "(1003.72)", "Rs.95.9927"),
    _row("Primary market &amp; others", "353.61", "0.17", "353.44", "36.82"),
    _row("Sub-total", "13147.77", "22429.29", "(9281.52)", "(966.90)"),
]) + "</table>"


def test_equity_rows_per_reporting_date():
    rows = nsdl.parse_daily(PAGE, "archive 2026-10")
    assert [r["date"] for r in rows] == ["2026-10-01", "2026-10-05"]
    first = rows[0]
    assert first["exchange_net"] == -9569.57 and first["primary_net"] == 337.69
    assert first["equity_net"] == -9231.88 and first["equity_net_usd_mn"] == -961.82
    assert nsdl.problems(rows) == []


def test_bad_rows_are_refused():
    rows = nsdl.parse_daily(PAGE, "x")
    rows[0]["exchange_net"] = 1.0
    assert any("purchases - sales" in b for b in nsdl.problems(rows))
    assert nsdl.problems([]) == ["nothing parsed"]


def test_month_ends_stop_at_today():
    from datetime import date
    assert nsdl.month_ends("2026-09", date(2026, 11, 7)) == [date(2026, 9, 30), date(2026, 10, 31), date(2026, 11, 7)]
