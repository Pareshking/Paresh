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
