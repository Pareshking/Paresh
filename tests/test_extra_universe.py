"""The extra universe: who is in it, and which month-end sets it."""
from datetime import date

import pandas as pd

from src.engine import extra_universe as xu

CR = 10_000_000


def _caps(rows):
    return pd.DataFrame(rows, columns=["symbol", "series", "security", "category", "mcap"])


def test_members_keep_main_board_stocks_over_the_floor_outside_the_750():
    caps = _caps([
        ("BIGIN750", "EQ", "Big In 750 Ltd", "Listed", 90_000 * CR),
        ("ABOVE", "EQ", "Above Floor Ltd", "Listed", 2_500 * CR),
        ("ATFLOOR", "BE", "At Floor Ltd", "Listed", 2_000 * CR),
        ("BELOW", "EQ", "Below Floor Ltd", "Listed", 1_999 * CR),
        ("SMEBIG", "SM", "Big SME Ltd", "Listed", 5_000 * CR),
        ("NIFTYBEES", "EQ", "Nippon India ETF Nifty BeES", "Listed", 40_000 * CR),
        ("GOLDFUND", "EQ", "Some Gold Exchange Traded Fund", "Listed", 9_000 * CR),
        ("SUSP", "EQ", "Suspended Ltd", "Suspended", 3_000 * CR),
        ("DUMMYX", "EQ", "Dummy", "Listed", 3_000 * CR),
    ])
    out = xu.members(caps, exclude={"BIGIN750"},
                     classification={"ABOVE": {"TV_Sector": "Finance"}})
    assert list(out["Symbol"]) == ["ABOVE", "ATFLOOR"]
    assert list(out["Industry"]) == ["Finance", xu.UNCLASSIFIED]
    assert list(out.columns[:5]) == xu.LIST_COLUMNS
    assert out["MarketCapCr"].tolist() == [2500, 2000]


def test_eq_is_kept_over_be_for_the_same_symbol():
    caps = _caps([("TWICE", "BE", "Twice Ltd", "Listed", 3_000 * CR),
                  ("TWICE", "EQ", "Twice Ltd", "Listed", 3_000 * CR)])
    assert xu.members(caps, set())["Series"].tolist() == ["EQ"]


def test_the_month_end_session_sets_the_list():
    aug31, sep25 = date(2026, 8, 31), date(2026, 9, 25)
    held = {date(2026, 8, 28), aug31, sep25}
    # Mid-September: August's last session.
    assert xu.membership_day(held, date(2026, 9, 27)) == aug31
    # September 30 (a Wednesday) arrives: built that evening, for 1 October.
    sep30 = date(2026, 9, 30)
    assert xu.membership_day(held | {sep30}, sep30) == sep30
    assert xu.effective_from(sep30) == date(2026, 10, 1)
    # A holiday on the last weekday: the newest session, once the month is over.
    assert xu.membership_day(held | {date(2026, 9, 29)}, date(2026, 10, 1)) == date(2026, 9, 29)
    assert xu.membership_day(set(), date(2026, 9, 27)) is None
    assert xu.effective_from(date(2026, 12, 31)) == date(2027, 1, 1)


def test_effective_nano_always_excludes_current_750():
    from src.loaders.extra_universe_loader import effective_nano

    base = pd.DataFrame({"Symbol": ["SIGMAADV", "IN750"]})
    extra = pd.DataFrame({
        "Symbol": ["SIGMAADV", "NANO1", "NANO2"],
        "Company Name": ["Sigma", "Nano 1", "Nano 2"],
        "Industry": ["Technology", "Technology", "Finance"],
        "Indices": ["NANO", "NANO", "NANO"],
    })
    out = effective_nano(base, extra)
    assert out["Symbol"].tolist() == ["NANO1", "NANO2"]
    assert set(out["Symbol"]).isdisjoint(set(base["Symbol"]))


def test_effective_nano_handles_stock_leaving_750():
    from src.loaders.extra_universe_loader import effective_nano

    base = pd.DataFrame({"Symbol": ["STAYS750"]})
    extra = pd.DataFrame({
        "Symbol": ["STAYS750", "LEAVES750"],
        "Company Name": ["Current", "Former"],
        "Industry": ["Technology", "Finance"],
        "Indices": ["NANO", "NANO"],
    })
    out = effective_nano(base, extra)
    assert out["Symbol"].tolist() == ["LEAVES750"]
