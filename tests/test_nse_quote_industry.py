"""The one-off NSE classification read (S189's four stocks, owner 26 Nov 2026)."""

from scripts import nse_quote_industry as q


def test_the_four_levels_are_read_from_nse_answer():
    payload = {"industryInfo": {"macro": "Industrials", "sector": "Construction", "industry": "Construction",
                                "basicIndustry": "Civil Construction"}}
    assert q.levels(payload) == {"Macro-economic sector": "Industrials", "Sector": "Construction",
                                 "Industry": "Construction", "Basic industry": "Civil Construction"}


def test_a_level_nse_leaves_out_says_so():
    assert q.levels({"industryInfo": {"macro": "Services"}})["Basic industry"] == "not shown"
    assert set(q.levels({}).values()) == {"not shown"}
