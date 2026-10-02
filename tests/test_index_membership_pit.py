"""Guards on data/index_membership_pit.csv (see docs/INDEX_MEMBERSHIP_PIT.md)."""
import csv
import os

PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "index_membership_pit.csv")
ROWS = list(csv.DictReader(open(PATH)))
SIZES = {"NIFTY_50": 50, "NIFTY_NEXT_50": 50, "NIFTY_MIDCAP_150": 150, "NIFTY_SMALLCAP_250": 250,
         "NIFTY_MICROCAP_250": 250, "NIFTY_TOTAL_MARKET": 750, "NIFTY_500": 500}


def members(index, day):
    return {r["symbol"] for r in ROWS if r["index"] == index and r["from_date"] <= day
            and (not r["to_date"] or day <= r["to_date"])}


def test_every_interval_is_well_formed():
    for r in ROWS:
        assert r["from_date"] and (not r["to_date"] or r["from_date"] <= r["to_date"]), r


def test_every_change_date_has_the_right_size():
    # DVR additional securities (symbol ends in DVR) sit above the nominal size.
    for index, size in SIZES.items():
        days = {r["from_date"] for r in ROWS if r["index"] == index}
        for day in days:
            got = members(index, day)
            extra = sum(1 for s in got if s.endswith("DVR"))
            assert len(got) - extra == size, (index, day, len(got))


def test_today_is_current_nse_list_size():
    for index, size in SIZES.items():
        assert len(members(index, "2026-09-30")) == size
