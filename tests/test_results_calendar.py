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


def _meetings(n, day, source, prefix="S"):
    return pd.DataFrame({"symbol": [f"{prefix}{i}" for i in range(n)], "date": day,
                         "purpose": "Financial Results", "results": 1, "detail": "", "source": source})


def test_check_refuses_a_download_with_no_meetings_held():
    today = date(2026, 11, 15)
    assert any("held in 60 days" in b for b in crc.check(_meetings(500, "2026-11-20", "calendar"), None, today))
    assert crc.check(_meetings(500, "2026-11-10", "held"), None, today) == []


def test_the_off_season_and_todays_meetings_moving_to_held_are_not_a_fault():
    # S110, 12-15 Nov 2026: the old guard counted forward meetings, so the Q2
    # deadline (14 Nov) emptying NSE's calendar, and NSE moving the day's meetings
    # from the calendar to the held list, failed the job every night.
    today = date(2026, 11, 15)
    old = pd.concat([_meetings(400, "2026-11-10", "held", "H"), _meetings(430, "2026-11-14", "calendar", "C"),
                     _meetings(5, "2026-12-05", "calendar", "D")])
    new = pd.concat([_meetings(400, "2026-11-10", "held", "H"), _meetings(430, "2026-11-14", "held", "C"),
                     _meetings(5, "2026-12-05", "calendar", "D")])
    assert crc.check(new, old, today) == []
    assert crc.lost_meetings(new, old, today).empty


def test_a_moved_meeting_is_not_lost_but_a_vanished_one_is():
    today = date(2026, 11, 15)
    old = pd.concat([_meetings(300, "2026-11-10", "held", "H"), _meetings(1, "2026-11-20", "calendar", "M")])
    moved = pd.concat([_meetings(300, "2026-11-10", "held", "H"), _meetings(1, "2026-11-27", "calendar", "M")])
    assert crc.lost_meetings(moved, old, today).empty
    gone = _meetings(300, "2026-11-10", "held", "H")
    assert crc.lost_meetings(gone, old, today)["symbol"].tolist() == ["M0"]
    assert crc.check(gone, old, today) == []          # one cancellation is not a broken download


def test_check_refuses_a_download_that_loses_what_the_last_file_knew():
    today = date(2026, 11, 15)
    old = pd.concat([_meetings(400, "2026-11-10", "held", "H"), _meetings(200, "2026-11-25", "calendar", "C")])
    new = pd.concat([_meetings(400, "2026-11-10", "held", "H"), _meetings(100, "2026-11-25", "calendar", "C")])
    bad = crc.check(new, old, today)
    assert len(bad) == 1 and bad[0].startswith("100 of 600 meetings")
    # held meetings about to leave the 60-day window are not required
    edge = _meetings(400, "2026-09-17", "held", "E")
    assert crc.check(_meetings(400, "2026-11-10", "held", "H"),
                     pd.concat([_meetings(400, "2026-11-10", "held", "H"), edge]), today) == []


def test_today_is_nse_date_not_the_runners():
    import inspect
    assert "Asia/Kolkata" in inspect.getsource(crc.ist_today)
    assert "today = ist_today()" in inspect.getsource(crc.main)


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




