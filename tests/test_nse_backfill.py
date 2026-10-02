"""NSE history from the GitHub bhavcopy mirror and NSE's corporate-action list."""
from datetime import date

import pandas as pd

from scripts import import_nse_history as imp
from src.loaders import nse_backfill as bf
from src.loaders import nse_bundle as nb

# The mirror's own layout, including the space after each comma it uses from 2020.
MIRROR = """SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER
TIL, EQ, 10-Aug-2026, 232.10, 233.00, 236.00, 231.00, 232.40, 232.50, 233.10, 51234, 119.43, 1500, 30000, 58.55
DEEDEV, BE, 10-Aug-2026, 629.70, 630.00, 631.00, 620.00, 626.00, 626.20, 625.00, 1000, 6.25, 40, 1000, 100.00
"""


def _mirror(tmp_path, days):
    for d in days:
        (tmp_path / f"sec_bhavdata_full_{d.strftime('%d%m%Y')}.csv").write_text(MIRROR)
    return tmp_path


def test_a_mirror_file_becomes_the_rows_nses_bundle_gives(tmp_path):
    _mirror(tmp_path, [date(2026, 8, 10)])
    rows = bf.mirror_prices(tmp_path / "sec_bhavdata_full_10082026.csv", date(2026, 8, 10))
    assert list(rows.columns) == nb.PRICE_COLUMNS
    til = rows[rows["symbol"] == "TIL"].iloc[0]
    assert (til["series"], til["close"], til["prev_close"], til["volume"]) == ("EQ", 232.5, 232.1, 51234)
    assert til["value"] == 119.43 * 1e5 and til["mkt"] == "N"
    assert rows[rows["symbol"] == "DEEDEV"].iloc[0]["series"] == "BE"


def test_mirror_days_reads_the_date_from_the_file_name(tmp_path):
    _mirror(tmp_path, [date(2010, 6, 10), date(2026, 8, 10)])
    (tmp_path / "README.md").write_text("x")
    assert sorted(bf.mirror_days(tmp_path)) == [date(2010, 6, 10), date(2026, 8, 10)]


API_ROWS = [
    {"symbol": "UTKARSHBNK", "series": "EQ", "subject": "Rights 8:13 @ Premium Rs 4/-",
     "exDate": "14-Oct-2025", "recDate": "14-Oct-2025", "bcStartDate": "-", "bcEndDate": "-",
     "ndStartDate": "-", "ndEndDate": "-", "faceVal": "10", "comp": "Utkarsh Small Finance Bank"},
    {"symbol": "ABC", "series": "EQ", "subject": "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share",
     "exDate": "02-Jan-2012", "recDate": "03-Jan-2012", "bcStartDate": "-", "bcEndDate": "-",
     "ndStartDate": "-", "ndEndDate": "-", "faceVal": "10", "comp": "Abc Ltd"},
    {"symbol": "XYZ", "series": "EQ", "subject": "Bonus 1:1", "exDate": "-", "recDate": "-",
     "bcStartDate": "-", "bcEndDate": "-", "ndStartDate": "-", "ndEndDate": "-",
     "faceVal": "1", "comp": "no ex-date: dropped"},
]


def test_nses_list_becomes_action_rows_with_face_values():
    acts = bf.api_actions(API_ROWS)
    assert list(acts.columns) == [*nb.ACTION_COLUMNS, "face_value"]
    assert set(acts["symbol"]) == {"UTKARSHBNK", "ABC"}
    split = acts[acts["symbol"] == "ABC"].iloc[0]
    assert split["kind"] == "split" and split["price_factor"] == 0.2
    assert acts[acts["symbol"] == "UTKARSHBNK"].iloc[0]["kind"] == "rights"
    assert bf.face_values(acts) == {"UTKARSHBNK": 10.0, "ABC": 10.0}


def test_a_stated_face_value_is_used_for_the_rights_factor():
    from src.engine import reconcile as rc

    days = pd.bdate_range("2025-10-08", periods=10)
    raw = pd.DataFrame({"UTKARSHBNK": [23.2] * 4 + [18.66] * 6}, index=days)
    acts = bf.api_actions(API_ROWS[:1])
    row = rc.rights_events(acts, raw, raw=raw).iloc[0]
    assert row["face_value"] == 10 and not row["face_value_assumed"] and row["issue_price"] == 14


def test_import_prices_publishes_what_r2_lacks_oldest_first(tmp_path):
    (tmp_path / "m").mkdir()
    mirror = _mirror(tmp_path / "m", [date(2010, 6, 10), date(2010, 6, 11), date(2010, 6, 14)])
    sent = []
    stats = imp.import_prices(mirror, lambda: {date(2010, 6, 11)}, tmp_path / "w",
                              since=date(2010, 1, 1), until=date(2026, 10, 1),
                              publish=lambda path, ds, src: sent.append((path.parent.name, ds, src)))
    assert [d for d, _, _ in sent] == ["2010-06-10", "2010-06-14"]
    assert {ds for _, ds, _ in sent} == {"nse/prices_daily"}
    assert stats["published"] == 2 and not stats["failed"]


def test_import_prices_skips_a_day_the_collector_published_meanwhile(tmp_path):
    (tmp_path / "m").mkdir()
    mirror = _mirror(tmp_path / "m", [date(2010, 6, 10), date(2010, 6, 11), date(2010, 6, 14)])
    reads = iter([set(), {date(2010, 6, 14)}])
    sent = []
    stats = imp.import_prices(mirror, lambda: next(reads), tmp_path / "w", since=date(2010, 1, 1),
                              until=date(2026, 10, 1), refresh=2,
                              publish=lambda path, ds, src: sent.append(path.parent.name))
    assert sent == ["2010-06-10", "2010-06-11"] and stats["skipped"] == 1


def test_import_prices_stops_when_its_time_is_spent(tmp_path):
    (tmp_path / "m").mkdir()
    mirror = _mirror(tmp_path / "m", [date(2010, 6, 10), date(2010, 6, 11)])
    ticks = iter([0, 0, 61])
    stats = imp.import_prices(mirror, set, tmp_path / "w", since=date(2010, 1, 1),
                              until=date(2026, 10, 1), max_minutes=1, clock=lambda: next(ticks),
                              publish=lambda *a: None)
    assert stats["published"] == 1 and stats["left"] == 1


def test_import_actions_publishes_one_file_a_year_and_stops_on_a_refusal(tmp_path):
    def fetch(year, session):
        if year == 2012:
            raise nb.NSEBlocked("HTTP 403")
        return bf.api_actions(API_ROWS[:2])

    sent = []
    n = imp.import_actions(2010, 2014, tmp_path, publish=lambda path, ds, src: sent.append(ds),
                           fetch=fetch, sleep=lambda s: None, log=lambda *a: None)
    assert n == 2 and sent == ["nse/corporate_actions_history"] * 2
