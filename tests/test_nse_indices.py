"""The store of every NSE index (S168): parsing NSE's daily file, joining renames,
and refusing rows that would change history. Cases are NSE's own (21 Nov 2026)."""
from __future__ import annotations

import pandas as pd
import pytest

from src.loaders import nse_indices as ni

HEAD = ("Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,Closing Index Value,"
        "Points Change,Change(%),Volume,Turnover (Rs. Cr.),P/E,P/B,Div Yield\n")


def _file(*rows: str) -> bytes:
    return (HEAD + "\n".join(rows) + "\n").encode()


ALIASES = {"s_p_cnx_nifty": "nifty_50", "cnx_nifty": "nifty_50", "nifty_50": "nifty_50"}


def test_a_session_parses_with_placeholders_and_bare_decimals():
    rows = ni.parse_file(_file(
        "Nifty 50,20-11-2026,25600.1,25810.4,25590.2,25800.60,286.30,1.12,123,4567.8,21.02,3.6,1.3",
        "GSEC10 NSE Index,15-09-2014,-,-,-,1258.1,.47,.04,-,-,-,-,-"), ALIASES)
    n50 = rows[rows["key"] == "nifty_50"].iloc[0]
    assert n50["date"] == pd.Timestamp("2026-11-20") and n50["close"] == 25800.60 and n50["pe"] == 21.02
    g = rows[rows["key"] == "gsec10_nse_index"].iloc[0]
    assert pd.isna(g["open"]) and pd.isna(g["pe"]) and g["points_change"] == 0.47


def test_an_html_answer_is_not_a_session():
    with pytest.raises(ni.NotAnIndexFile):
        ni.parse_file(b"<!DOCTYPE html><html><body>Not found</body></html>")


def test_renamed_indices_join_under_one_key():
    a = ni.parse_file(_file("S&P CNX Nifty,07-02-2013,-,-,-,5959.20,-44.85,-.75,1,1,18.1,3.1,1.5"), ALIASES)
    b = ni.parse_file(_file("CNX Nifty,08-02-2013,-,-,-,5903.50,-55.70,-.93,1,1,18.0,3.1,1.5"), ALIASES)
    store = ni.merge(ni.merge(None, a), b)
    assert set(store["key"]) == {"nifty_50"}
    seam = ni.seams(store).iloc[0]
    assert seam["old"] == "S&P CNX Nifty" and seam["new"] == "CNX Nifty" and bool(seam["continuous"])


def test_a_seam_whose_points_change_does_not_match_is_flagged():
    a = ni.parse_file(_file("CNX Nifty,06-11-2015,-,-,-,7954.30,-1.15,-.01,1,1,21,3,1.3"), ALIASES)
    b = ni.parse_file(_file("Nifty 50,09-11-2015,-,-,-,7915.20,99.00,1.2,1,1,21,3,1.3"), ALIASES)
    assert not bool(ni.seams(ni.merge(ni.merge(None, a), b)).iloc[0]["continuous"])


def test_an_identical_row_printed_twice_is_one_row():
    rows = ni.parse_file(_file("GSEC10 NSE Index,15-09-2014,-,-,-,1258.1,.47,.04,-,-,-,-,-",
                               "GSEC10 NSE Index,15-09-2014,-,-,-,1258.1,.47,.04,-,-,-,-,-"), {})
    assert len(rows) == 1


def test_the_mislabelled_high_beta_row_of_8_feb_2013_is_relabelled():
    rows = ni.parse_file(_file(
        "CNX Alpha Index,08-02-2013,-,-,-,4713.18,-36.65,-0.77,1,1,23.07,3.6,0.65",
        "CNX Alpha Index,08-02-2013,-,-,-,1572.9,-21.94,-1.38,1,1,22.39,0.96,1.18"), {})
    assert sorted(rows["name"]) == ["CNX Alpha Index", "CNX High Beta"]
    assert rows.set_index("name").loc["CNX High Beta", "close"] == 1572.9


def test_an_index_printed_twice_with_different_values_is_refused():
    rows = ni.parse_file(_file("Nifty Bank,10-01-2020,-,-,-,32000,1,0.1,1,1,20,3,1",
                               "Nifty Bank,10-01-2020,-,-,-,15000,1,0.1,1,1,20,3,1"), {})
    with pytest.raises(ValueError, match="printed twice"):
        ni.merge(None, rows)


def test_a_stored_close_is_never_changed():
    first = ni.parse_file(_file("Nifty 50,20-11-2026,-,-,-,25800.60,1,1,1,1,21,3,1"), ALIASES)
    store = ni.merge(None, first)
    same = ni.parse_file(_file("Nifty 50,20-11-2026,-,-,-,25800.61,1,1,1,1,21,3,1"), ALIASES)
    assert len(ni.merge(store, same)) == 1                  # a paisa of rounding: kept as stored
    moved = ni.parse_file(_file("Nifty 50,20-11-2026,-,-,-,25700.00,1,1,1,1,21,3,1"), ALIASES)
    with pytest.raises(ValueError, match="stored close would change"):
        ni.merge(store, moved)


def test_new_sessions_are_added_in_order():
    a = ni.parse_file(_file("Nifty 50,19-11-2026,-,-,-,25514.30,1,1,1,1,21,3,1"), ALIASES)
    b = ni.parse_file(_file("Nifty 50,20-11-2026,-,-,-,25800.60,1,1,1,1,21,3,1"), ALIASES)
    store = ni.merge(ni.merge(None, b), a)
    s = ni.series(store, "nifty_50")
    assert list(s.index) == [pd.Timestamp("2026-11-19"), pd.Timestamp("2026-11-20")]
    assert s.iloc[-1] == 25800.60


def test_the_committed_tables_load():
    al = ni.load_aliases()
    assert al["cnx_nifty"] == "nifty_50" and al["cnx_finance"] == "nifty_financial_services"
    assert ni.CORRECTIONS.exists()


def test_a_slash_date_is_the_session_not_a_dropped_file():
    # 59 files, Jun 2014 - Jun 2015, print 09/06/2014; they were once dropped silently.
    rows = ni.parse_file(_file("CNX Nifty,09/06/2014,-,-,-,7654.60,1,1,1,1,21,3,1"), ALIASES,
                         pd.Timestamp("2014-06-09"))
    assert list(rows["date"]) == [pd.Timestamp("2014-06-09")]


def test_a_month_first_date_is_read_as_the_session_asked_for():
    # NSE's file for 10 Apr 2023 says 04-10-2023; read day-first it would be 4 Oct.
    rows = ni.parse_file(_file("Nifty 50,04-10-2023,-,-,-,17624.05,24.9,.14,1,1,20.75,4.13,1.41"), ALIASES,
                         pd.Timestamp("2023-04-10"))
    assert list(rows["date"]) == [pd.Timestamp("2023-04-10")]


def test_a_file_dated_another_day_is_refused():
    with pytest.raises(ni.NotAnIndexFile, match="asked for 21 Nov 2026"):
        ni.parse_file(_file("Nifty 50,20-11-2026,-,-,-,25800.60,1,1,1,1,21,3,1"), ALIASES,
                      pd.Timestamp("2026-11-21"))


def test_an_unreadable_date_refuses_the_file():
    with pytest.raises(ni.NotAnIndexFile, match="unreadable Index Date"):
        ni.parse_file(_file("Nifty 50,2026.11.20,-,-,-,25800.60,1,1,1,1,21,3,1"), ALIASES)


def test_a_saved_file_names_its_session():
    assert ni.session_from_name("ind_close_all_10042023") == pd.Timestamp("2023-04-10")
    assert ni.session_from_name("20140609") == pd.Timestamp("2014-06-09")
    assert ni.session_from_name("notes") is None


def _rows(name, dates, start=100.0):
    lines = [f"{name},{d:%d-%m-%Y},-,-,-,{start + i},1,1,1,1,20,3,1" for i, d in enumerate(dates)]
    return ni.parse_file(_file(*lines), {})


def test_a_back_calculated_row_years_before_launch_is_not_live_history():
    # NSE's regenerated 7 Jul 2016 file lists Nifty Total Market (launched 2021):
    # one row, then nothing for many sessions, then its live run.
    days = pd.bdate_range("2016-07-07", periods=70)
    store = ni.merge(_rows("Nifty Total Market", [days[0]], 3914.55),
                     _rows("Nifty Total Market", days[40:], 7000))
    store = ni.merge(store, _rows("Nifty 50", days))
    s = ni.series(store, "nifty_total_market")
    assert s.index[0] == days[40] and len(s) == 30
    assert ni.series(store, "nifty_total_market", live_only=False).index[0] == days[0]
    assert len(ni.series(store, "nifty_50")) == 70


def test_a_back_calculated_row_two_sessions_before_launch_is_not_live():
    # Nifty100 Low Volatility 30: in the regenerated 7 Jul 2016 file, absent on 8 Jul,
    # live from 11 Jul.
    days = pd.bdate_range("2016-07-07", periods=40)
    store = ni.merge(_rows("Nifty100 Low Volatility 30", [days[0], *days[2:]], 6635.95),
                     _rows("Nifty 50", days))
    assert ni.series(store, "nifty100_low_volatility_30").index[0] == days[2]


def test_a_missing_day_is_derived_from_the_next_sessions_points_change():
    # 9 Oct 2013: NSE has no file; 10 Oct's close minus its points change is 9 Oct's
    # close (6007.45, which Kaggle's collector also holds).
    a = ni.parse_file(_file("CNX Nifty,08-10-2013,-,-,-,5928.40,1,1,1,1,18,3,1"), ALIASES)
    c = ni.parse_file(_file("CNX Nifty,10-10-2013,-,-,-,6020.95,13.50,.22,1,1,18,3,1"), ALIASES)
    store = ni.derive_missing(ni.merge(ni.merge(None, a), c), [pd.Timestamp("2013-10-09")])
    row = store[store["date"] == pd.Timestamp("2013-10-09")].iloc[0]
    assert row["close"] == 6007.45 and bool(row["derived"]) and pd.isna(row["pe"])
    assert len(ni.derive_missing(store, [pd.Timestamp("2013-10-09")])) == len(store)   # once only
    assert not ni.merge(None, a)["derived"].any()


def test_a_derived_close_that_jumps_is_refused():
    a = ni.parse_file(_file("CNX Nifty,08-10-2013,-,-,-,5928.40,1,1,1,1,18,3,1"), ALIASES)
    c = ni.parse_file(_file("CNX Nifty,10-10-2013,-,-,-,6020.95,3000,1,1,1,18,3,1"), ALIASES)
    store = ni.derive_missing(ni.merge(ni.merge(None, a), c), [pd.Timestamp("2013-10-09")])
    assert pd.Timestamp("2013-10-09") not in set(store["date"])


def test_the_missing_sessions_table_lists_eleven_derivable_days():
    assert len(ni.missing_sessions()) == 11


def test_parallel_fetch_reads_days_in_date_order_whoever_answers_first(monkeypatch):
    """Four requests at a time (21 Nov 2026): the store must not depend on which answer came back first."""
    import importlib.util
    import random
    import time as _time
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "collect_nse_indices", Path(__file__).resolve().parents[1] / "scripts" / "collect_nse_indices.py")
    c = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(c)
    head = ("Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,Closing Index Value,"
            "Points Change,Change(%),Volume,Turnover (Rs. Cr.),P/E,P/B,Div Yield\n")

    def fake(day):
        _time.sleep(random.random() / 50)            # answers arrive out of order
        if day.dayofweek >= 5:
            return None
        return (head + f"Nifty 50,{day:%d-%m-%Y},-,-,-,{1000 + day.day},1,1,1,1,21,3,1\n").encode()

    monkeypatch.setattr(c, "_fetch", fake)
    rows, skipped = c.fetch_since(pd.Timestamp("2026-10-31"), {"nifty_50": "nifty_50"},
                                  pd.Timestamp("2026-11-20"), workers=4)
    assert not skipped
    assert list(rows["date"]) == sorted(rows["date"]) and len(rows) == 15
    assert list(rows["close"]) == [1000.0 + d.day for d in rows["date"]]
