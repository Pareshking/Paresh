"""Exit watch: the room left on each rule that sells a holding."""
import pandas as pd
import pytest

from src.engine.exit_watch import (
    CLEAR, SELL, UNKNOWN, WATCH, Rules, assess, holdings_from_kite_csv,
    parse_holdings, qualified_ranks,
)
from src.ui.views.exit_watch_view import next_rebalance


def _table():
    # Rank is the Screener's overall rank; D fails the EMA filter, so it is
    # left out of the qualified count and E moves up a place.
    return pd.DataFrame({
        "Symbol": ["A", "B", "C", "D", "E"],
        "Industry": ["X"] * 5,
        "Rank": [1, 2, 3, 4, 5],
        "Above 50 EMA": [True, True, True, False, True],
        "Near 52W High": [True, True, True, True, True],
        "% 50 EMA": [20.0, 2.0, 10.0, -3.0, 10.0],
        "% High": [0.0, -5.0, -18.0, -5.0, -5.0],
    })


def test_the_buffer_counts_only_stocks_that_pass_both_filters():
    q = qualified_ranks(_table())
    assert list(q.index) == ["A", "B", "C", "E"]
    assert q["E"] == 4          # overall #5, qualified #4


def test_statuses_follow_the_three_rules():
    a = assess(_table(), ["A", "B", "C", "D", "E", "ZZZ"], Rules(buffer_n=3)).set_index("Symbol")
    assert a.loc["D", "status"] == SELL and "below its 50-day EMA" in a.loc["D", "why"]
    assert a.loc["E", "status"] == SELL and "past the top 3" in a.loc["E", "why"]
    # B: 2% above its EMA is inside the 3% watch margin.
    assert a.loc["B", "status"] == WATCH
    # C: 18% below its high leaves ~2.4% before the -20% line.
    assert a.loc["C", "status"] == WATCH
    assert a.loc["C", "High cushion"] == pytest.approx(1 - 0.8 / 0.82)
    # A has 2 places of room under a buffer of 3: close, so watched.
    assert a.loc["A", "status"] == WATCH
    assert a.loc["ZZZ", "status"] == UNKNOWN
    # Under the real buffer of 40 it is clear of all three.
    assert assess(_table(), ["A"]).iloc[0]["status"] == CLEAR


def test_cushions_are_the_fall_that_reaches_each_line():
    a = assess(_table(), ["B"]).iloc[0]
    assert a["EMA cushion"] == pytest.approx(1 - 1 / 1.02)
    assert a["High cushion"] == pytest.approx(1 - 0.8 / 0.95)


def test_order_is_closest_to_a_sale_first():
    a = assess(_table(), ["A", "B", "D", "ZZZ"], Rules(buffer_n=40))
    assert list(a["status"]) == [SELL, WATCH, CLEAR, UNKNOWN]


def test_parse_holdings_reads_optional_prices_and_drops_repeats():
    got = parse_holdings("hfcl 126.5, QUESS@340; TCS\nhfcl, J&K-X ₹12, bad entry here")
    assert got == [("HFCL", 126.5), ("QUESS", 340.0), ("TCS", None), ("J&K-X", 12.0)]


def test_kite_holdings_csv():
    frame = pd.DataFrame({"Instrument": ["HFCL", "QUESS-BE"], "Qty.": [10, 5],
                          "Avg. cost": [126.5, "n/a"]})
    assert holdings_from_kite_csv(frame) == [("HFCL", 126.5), ("QUESS", None)]
    with pytest.raises(ValueError):
        holdings_from_kite_csv(pd.DataFrame({"Name": ["x"]}))


def test_next_rebalance_is_the_last_weekday_then_the_next_first_weekday():
    check, fill = next_rebalance(pd.Timestamp("2026-09-25"))
    assert (check, fill) == (pd.Timestamp("2026-09-30"), pd.Timestamp("2026-10-01"))
    # May 2026 ends on a Sunday: checked Friday 29th, filled Monday 1 June.
    check, fill = next_rebalance(pd.Timestamp("2026-05-20"))
    assert (check, fill) == (pd.Timestamp("2026-05-29"), pd.Timestamp("2026-06-01"))
