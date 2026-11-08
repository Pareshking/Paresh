"""Each index's latest point-in-time membership equals NSE's own list file (audit,
8 Nov 2026: the Nifty 500 history kept ICICIPRULI after NSE renamed it ICICILIFE on
23 Oct; nothing compared the two). DUMMY* placeholders are left out, and a stock in
NSE's file that is a fresh listing above the index count (a demerged company NSE keeps
until its exclusion notice) is allowed, as docs/DATA_CORRECTNESS.md explains."""
from pathlib import Path

import pandas as pd
import pytest

from src.engine import index_universe as iu
from src.engine.membership import members_on

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "nifty_50": "ind_nifty50list.csv",
    "nifty_next_50": "ind_niftynext50list.csv",
    "nifty_midcap_150": "ind_niftymidcap150list.csv",
    "nifty_smallcap_250": "ind_niftysmallcap250list.csv",
    "nifty_microcap_250": "ind_niftymicrocap250_list.csv",
    "nifty_total_market": "ind_niftytotalmarket_list.csv",
}


def _latest(key: str) -> set[str]:
    hist = iu.index_history(key)
    if hist is None:
        pytest.skip(f"no stored history for {key}")
    dates = [c["date"] for c in hist.get("changes", [])] + [hist["baseline"]["date"]]
    return set(members_on(hist, pd.Timestamp(max(dates))))


@pytest.mark.parametrize("key,name", sorted(FILES.items()))
def test_latest_membership_equals_nses_list(key, name):
    path = ROOT / "data" / "indices" / name
    if not path.exists():
        pytest.skip(f"{name} not in the checkout")
    listed = {s for s in pd.read_csv(path)["Symbol"].astype(str).str.strip() if not s.startswith("DUMMY")}
    ours = _latest(key)
    missing = sorted(ours - listed)          # we hold a name NSE no longer lists: a missed exit or rename
    assert not missing, f"{key}: in our history but not NSE's list: {missing}"
    extra = sorted(listed - ours)
    assert len(extra) <= 3, f"{key}: in NSE's list but not our history: {extra}"
