"""The Portfolio compares the systems over one window (owner, 20 Nov 2026); a system joins it only after its
first full month (owner, 22 Nov 2026: "first full month", S183). On 22 Nov 2026 the Nifty 1000, started in
November, had a partial month only and moved every other system's window from 1 Oct to 1 Nov."""
from __future__ import annotations

import pandas as pd

from src.ui.views.portfolio_page import common_window

M = lambda s: pd.Period(s, "M")  # noqa: E731


def test_a_system_in_its_first_month_does_not_move_the_window():
    starts = {"750": M("2026-01"), "nano": M("2026-10"), "combined": M("2026-10"), "1000": M("2026-11")}
    common, joined = common_window(starts, M("2026-11"))
    assert common == M("2026-10") and joined == {"750", "nano", "combined"}


def test_it_joins_once_its_first_month_is_complete():
    starts = {"750": M("2026-01"), "nano": M("2026-10"), "combined": M("2026-10"), "1000": M("2026-11")}
    common, joined = common_window(starts, M("2026-12"))
    assert common == M("2026-11") and joined == set(starts)


def test_no_system_with_a_full_month_means_no_window():
    assert common_window({"750": M("2026-11")}, M("2026-11")) == (None, set())


def test_a_system_whose_month_is_not_frozen_waits(  # S194 F5
):
    starts = {"750": M("2026-01"), "nano": M("2026-10"), "1000": M("2026-11")}
    frozen = {"750": {M("2026-01") + k for k in range(11)}, "nano": {M("2026-10"), M("2026-11")}, "1000": set()}
    common, joined = common_window(starts, M("2026-12"), frozen)
    assert joined == {"750", "nano"} and common == M("2026-10")      # November refused: the window keeps 1 Oct
    frozen["1000"] = {M("2026-11")}
    common, joined = common_window(starts, M("2026-12"), frozen)
    assert joined == set(starts) and common == M("2026-11")
