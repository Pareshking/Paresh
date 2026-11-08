"""Results calendar: NSE's board meetings for the book (TODO S110, item 4)."""
import importlib.util
from datetime import date
from pathlib import Path

import pandas as pd

from src.engine import results_calendar as rc

_spec = importlib.util.spec_from_file_location(
    "collect_results_calendar", Path(__file__).resolve().parents[1] / "scripts" / "collect_results_calendar.py")
crc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crc)


def _forward():
    return [{"symbol": "CUPID", "company": "Cupid", "purpose": "Financial Results", "bm_desc": "Q2", "date": "11-Nov-2026"},
            {"symbol": "MBAPL", "company": "MBAPL", "purpose": "Financial Results/Other business matters",
             "bm_desc": "  results   and more ", "date": "14-Nov-2026"},
            {"symbol": "XYZ", "company": "X", "purpose": "Fund Raising", "bm_desc": "", "date": "bad date"}]


def _held():
    return [{"bm_symbol": "DIVISLAB", "bm_date": "07-Nov-2026", "bm_purpose": "Board Meeting Intimation", "bm_desc": "n"},
            {"bm_symbol": "DIVISLAB", "bm_date": "07-Nov-2026", "bm_purpose": "Financial Results", "bm_desc": "Q2"},
            {"bm_symbol": "CUPID", "bm_date": "11-Nov-2026", "bm_purpose": "Financial Results", "bm_desc": "held"}]


def test_normalise_drops_notices_and_bad_dates_and_keeps_one_row_per_company_day():
    d = crc.normalise(_forward(), _held())
    assert list(d.columns) == crc.COLUMNS
    assert "XYZ" not in set(d["symbol"])                              # unreadable date
    assert (d["symbol"] == "DIVISLAB").sum() == 1                      # the intimation row is not a meeting
    cupid = d[d["symbol"] == "CUPID"]
    assert len(cupid) == 1 and cupid["source"].iloc[0] == "held"       # held wins over announced
    assert d.loc[d["symbol"] == "MBAPL", "detail"].iloc[0] == "results and more"
    assert d["results"].tolist() == [1, 1, 1]


def test_a_meeting_listed_only_by_its_notice_is_kept():
    held = [{"bm_symbol": "SCHAND", "bm_date": "05-Nov-2026", "bm_purpose": "Board Meeting Intimation",
             "bm_desc": "To consider and approve the unaudited financial results for Sep 2026"},
            {"bm_symbol": "OTHER", "bm_date": "05-Nov-2026", "bm_purpose": "Board Meeting Intimation", "bm_desc": "AGM"}]
    d = crc.normalise([], held)
    assert d.set_index("symbol").loc["SCHAND", "results"] == 1
    assert d.set_index("symbol").loc["OTHER", "purpose"] == "Board meeting"


def test_check_refuses_an_empty_or_halved_forward_calendar():
    today = date(2026, 11, 8)
    few = crc.normalise(_forward(), [])
    assert any("forward meetings" in b for b in crc.check(few, None, today))
    many = pd.DataFrame({"symbol": [f"S{i}" for i in range(200)], "date": "2026-11-20", "purpose": "Financial Results",
                         "results": 1, "detail": "", "source": "calendar"})
    assert crc.check(many, None, today) == []
    assert any("still ahead" in b for b in crc.check(many.head(80), many, today))


def _cal():
    return pd.DataFrame({
        "symbol": ["DIVISLAB", "GLAND", "CUPID", "MBAPL", "SIGMAADV", "OTHER", "SHREEJISPG"],
        "date": pd.to_datetime(["2026-11-07", "2026-11-06", "2026-11-11", "2026-11-14", "2026-11-20", "2026-11-12",
                                "2026-11-14"]),
        "purpose": ["Financial Results", "Financial Results", "Financial Results",
                    "Financial Results/Other business matters", "Financial Results/Dividend", "Financial Results",
                    "Financial Results/Stock Split"],
        "results": [1, 1, 1, 1, 1, 1, 1]})


def test_the_book_gets_its_meetings_ahead_and_who_has_reported():
    held = ["DIVISLAB", "GLAND", "CUPID", "MBAPL", "SHREEJISPG"]
    bc = rc.for_book(_cal(), held, ["SIGMAADV"], pd.Timestamp("2026-11-08"))
    assert bc.upcoming["symbol"].tolist() == ["CUPID", "MBAPL", "SHREEJISPG", "SIGMAADV"]
    assert bc.upcoming.set_index("symbol")["role"]["SIGMAADV"] == "to buy"
    assert bc.reported["symbol"].tolist() == ["DIVISLAB", "GLAND"]     # latest first; OTHER is not ours
    line = rc.lede(bc, pd.Timestamp("2026-11-30"))
    assert line.startswith("3 holdings report before the 30 Nov check")
    assert "2 of 5 have reported this season, the latest DIVISLAB on 7 Nov" in line


def test_short_purpose_reads_nse_purposes_plainly():
    assert rc.short_purpose("Financial Results/Other business matters") == "Results"
    assert rc.short_purpose("Financial Results/Dividend") == "Results, dividend"
    assert rc.short_purpose("Financial Results/Stock Split") == "Results, stock split"
    assert rc.short_purpose("Other business matters") == "Board meeting"


def test_the_card_lists_days_with_the_check_in_place_and_escapes():
    from src.ui.views import dashboard_view as dv
    cal = _cal()
    cal.loc[len(cal)] = ["A<B", pd.Timestamp("2026-11-30"), "Financial Results", 1]
    bc = rc.for_book(cal, ["CUPID", "MBAPL", "A<B"], [], pd.Timestamp("2026-11-08"))
    out = dv.calendar_html(bc, pd.Timestamp("2026-11-30"))
    assert "Wed, 11 Nov" in out and "Sat, 14 Nov" in out and "Mon, 30 Nov" in out
    assert "Rebalance check" in out and "A&lt;B" in out and "A<B" not in out
    assert out.index("Wed, 11 Nov") < out.index("Mon, 30 Nov")


def test_no_file_means_no_card_and_an_empty_window_says_so(tmp_path):
    from src.ui.views import dashboard_view as dv
    assert rc.load(tmp_path / "missing.csv") is None
    assert rc.for_book(None, ["A"], [], pd.Timestamp("2026-11-08")) is None
    bc = rc.for_book(_cal(), ["NOBODY"], [], pd.Timestamp("2026-11-08"))
    assert "No board meetings announced" in dv.calendar_html(bc, pd.Timestamp("2026-11-30"))
