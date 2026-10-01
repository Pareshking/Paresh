"""A sale must say why. "Rebalance Exit" explained nothing.

On 1 Sep 2026 the Backtest's "This month's changes" sold MBAPL, PAISALO,
SHREEJISPG and SIGMAADV under that label. They passed the trend and 52-week
filters; what failed was the index gate. Every earlier rebalance was scored on
today's constituent list (the membership record begins 19 Aug), so the book had
picked them up with hindsight, and the first rebalance scored on the index as it
stood sold them. The sale is right; the label was not.
"""
import pandas as pd

import src.engine.pipeline  # noqa: F401  (pipeline first: it and momentum import each other)
from src.engine.backtester import _exit_reason

SYMS = ["IN", "OUT", "THIN"]
TRUE = pd.Series(True, index=SYMS)


def _reason(symbol, *, ranked=(), index_mask=None, liq_mask=None, above=TRUE, near=TRUE):
    full = pd.Series(range(len(ranked), 0, -1), index=list(ranked), dtype=float)
    return _exit_reason(symbol, full, above, near, 50, 0.8, 40,
                        index_mask=index_mask, liq_mask=liq_mask,
                        signal_date=pd.Timestamp("2026-08-31"))


def test_a_name_outside_the_index_is_sold_for_that_reason():
    mask = pd.Series({"IN": True, "OUT": False, "THIN": True})
    assert _reason("OUT", index_mask=mask) == "Not in the index on 31 Aug 2026"


def test_a_name_below_the_liquidity_floor_says_so():
    liq = pd.Series({"IN": True, "OUT": True, "THIN": False})
    assert _reason("THIN", liq_mask=liq) == "Below the liquidity floor"


def test_the_price_filters_still_bind_first_and_keep_their_wording():
    mask = pd.Series({"IN": True, "OUT": False, "THIN": True})
    below = pd.Series({"IN": True, "OUT": False, "THIN": True})
    assert _reason("OUT", index_mask=mask, above=below).startswith("Trend Breakdown")
    assert _reason("OUT", index_mask=mask, near=below).startswith("Failed 52W High")
    assert _reason("IN", ranked=["IN"]).startswith("Rank Dropped")


def test_with_no_gate_to_blame_the_old_label_stands():
    assert _reason("IN") == "Rebalance Exit"
    # no membership record at all: nothing is claimed about the index
    assert _reason("IN", index_mask=None, liq_mask=None) == "Rebalance Exit"
