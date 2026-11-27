"""The one-off S189 read matches BSE's row by ISIN."""

from scripts import nse_quote_industry as q


def test_isins_come_from_nses_nifty_1000_list():
    assert q.isins(["CMPDI"]) == {"CMPDI": "INE05HV01027"}


def test_a_row_is_matched_by_isin_whatever_the_column_is_called():
    rows = [{"SCRIP_CD": "1", "ISIN_NUMBER": "INE000000001"}, {"SCRIP_CD": "2", "ISIN_NUMBER": "INE05HV01027"}]
    assert q.match(rows, "ine05hv01027")["SCRIP_CD"] == "2"
    assert q.match(rows, "INE999999999") is None
