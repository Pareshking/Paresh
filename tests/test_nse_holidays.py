"""NSE's holiday list refreshes itself, and a year it does not cover is "cannot tell" (owner, 15 Nov 2026)."""
import importlib.util
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from src.core import market_time
from src.core.market_time import INDIA_TZ
from src.loaders import nse_calendar

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("sync_nse_holidays", ROOT / "scripts" / "sync_nse_holidays.py")
sh = importlib.util.module_from_spec(_spec)
sys.modules["sync_nse_holidays"] = sh
_spec.loader.exec_module(sh)

TODAY = date(2026, 11, 15)


def _api(*items):
    return {"CM": [{"tradingDate": d, "weekDay": "", "description": desc, "morning_session": None,
                    "evening_session": None, "Sr_no": i} for i, (d, desc) in enumerate(items, 1)]}


def _row(d, desc="Holiday", special=""):
    return {"date": d, "description": desc, "special_session": special, "source": "x"}


def test_parse_reads_nse_dates_and_its_muhurat_star():
    rows = sh.parse(_api(("26-Jan-2027", "Republic Day"), ("29-Oct-2027", "Diwali Laxmi Pujan*"),
                         ("bad", "skip me")), TODAY)
    assert [r["date"] for r in rows] == ["2027-01-26", "2027-10-29"]
    assert rows[1]["description"] == "Diwali Laxmi Pujan" and rows[1]["special_session"] == "muhurat"
    assert rows[0]["special_session"] == "" and "fetched 2026-11-15" in rows[0]["source"]


def test_the_committed_file_is_exactly_what_the_parser_writes_from_nse():
    # The 3 Oct file was made by hand; NSE's live list matched it on 15 Nov, date for
    # date, with the "*" on 8 Nov. Rebuilt through the parser, nothing may change.
    old = sh.read()
    as_api = _api(*[(pd.Timestamp(r["date"]).strftime("%d-%b-%Y"),
                     r["description"] + ("*" if r["special_session"] else "")) for r in old])
    merged, changes = sh.merge(old, sh.parse(as_api, TODAY), TODAY)
    assert changes == [] and merged == old


def test_merge_adds_a_new_year_and_never_rewrites_the_past():
    old = [_row("2026-10-20", "Dussehra"), _row("2026-12-25", "Christmas")]
    new = [_row("2026-10-20", "Dasara (renamed)"), _row("2026-12-25", "Christmas"), _row("2027-01-26", "Republic Day")]
    rows, changes = sh.merge(old, new, TODAY)
    assert [r["date"] for r in rows] == ["2026-10-20", "2026-12-25", "2027-01-26"]
    assert rows[0]["description"] == "Dussehra"                      # past: untouched
    assert changes == ["added 2027-01-26 Republic Day"]


def test_a_cancelled_future_holiday_goes_only_when_nse_gave_a_full_year():
    old = [_row("2027-03-04", "Holi"), _row("2027-01-26")]
    full = [_row(f"2027-{m:02d}-15") for m in range(1, 12) if m != 3]           # 10 days of 2027, no Holi
    rows, changes = sh.merge(old, full, TODAY)
    assert "2027-03-04" not in {r["date"] for r in rows} and any("removed 2027-03-04" in c for c in changes)
    half = [_row("2027-01-26")]                                              # a thin reply strips nothing
    rows, changes = sh.merge(old, half, TODAY)
    assert "2027-03-04" in {r["date"] for r in rows} and changes == []


def test_an_empty_reply_changes_nothing():
    try:
        sh.merge([_row("2026-12-25")], [], TODAY)
    except ValueError:
        return
    raise AssertionError("an empty NSE reply must be refused")


def test_coverage_warns_for_the_current_year_and_next_year_from_mid_december():
    only_2026 = [_row("2026-12-25")]
    assert sh.coverage_warnings(only_2026, date(2026, 11, 15)) == []
    assert any("2027" in w for w in sh.coverage_warnings(only_2026, date(2026, 12, 15)))
    assert any("does not cover 2027" in w for w in sh.coverage_warnings(only_2026, date(2027, 1, 4)))


def _lists_for(years):
    hol = {date(y, 1, 26): "Republic Day" for y in years}
    return lambda: (hol, set(), set())


def test_an_uncovered_year_is_cannot_tell_not_a_stale_chip(monkeypatch):
    monkeypatch.setattr(nse_calendar, "_lists", _lists_for([2026]))
    # Mon 4 Jan 2027, mid-morning: Fri 1 Jan would be "due", but 2027 is not on NSE's list.
    now = datetime(2027, 1, 4, 11, 0, tzinfo=INDIA_TZ)
    assert market_time.last_due_session(now=now) is None
    monkeypatch.setattr(nse_calendar, "_lists", _lists_for([2026, 2027]))
    assert market_time.last_due_session(now=now) == date(2027, 1, 1)


def test_the_rebalance_caveat_appears_only_for_an_uncovered_year(monkeypatch):
    monkeypatch.setattr(nse_calendar, "_lists", _lists_for([2026]))
    assert nse_calendar.holiday_caveat(pd.Timestamp("2026-11-30"), pd.Timestamp("2026-12-01")) == ""
    note = nse_calendar.holiday_caveat(pd.Timestamp("2026-12-31"), pd.Timestamp("2027-01-01"))
    assert "2027" in note and "assumes none" in note
    assert nse_calendar.covers(2026) and not nse_calendar.covers(2027)


def test_the_nightly_reference_sync_fetches_the_list_without_going_red():
    wf = (ROOT / ".github" / "workflows" / "nse_reference_sync.yml").read_text(encoding="utf-8")
    assert "python scripts/sync_nse_holidays.py || echo" in wf
    assert wf.index("sync_nse_holidays.py") < wf.index("git add -A data/reference/nse/")
