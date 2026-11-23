"""S218: a new listing's first sessions before Screener's first price (owner, 23 Nov 2026).

TRIVENIPT listed on 12 Oct 2026 (NSE 684.00, BSE 683.85; 13 Oct NSE 649.80, BSE 649.70). Screener
starts on 14 Oct (617.35), and the ranking frame filled only after a stock's first Screener price,
so its highest close so far was lost. Owner: "From now on: TRIVENIPT and every new listing after it.
No frozen month changes." Earlier listings are left as they are.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.loaders import price_source as ps

IDX = pd.to_datetime(["2026-10-09", "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"])


def _frames(sym="TRIVENIPT", nse_start=1, scr_start=3, idx=IDX):
    n = len(idx)
    nse = pd.Series([np.nan] * nse_start + [684.0, 649.8, 617.35, 586.5, 590.0][: n - nse_start], index=idx)
    scr = pd.Series(np.nan, index=idx)
    scr.iloc[scr_start:] = nse.iloc[scr_start:]
    other = pd.Series(100.0, index=idx)
    return pd.DataFrame({sym: scr, "OTHER": other}), pd.DataFrame({sym: nse, "OTHER": other})


def test_trivenipt_starts_on_its_listing_day():
    close, middle = _frames()
    out, done = ps.extend_new_listings(close, middle)
    assert done == {"TRIVENIPT": 2}
    assert out.loc["2026-10-12", "TRIVENIPT"] == 684.0
    assert round(out.loc["2026-10-13", "TRIVENIPT"], 2) == 649.8
    assert out["TRIVENIPT"].loc["2026-10-14":].equals(close["TRIVENIPT"].loc["2026-10-14":])   # Screener's own, kept
    assert out["OTHER"].equals(close["OTHER"])


def test_chained_by_ratio_on_screeners_level():
    close, middle = _frames()
    close["TRIVENIPT"] *= 2          # Screener on another basis: the chain takes Screener's level
    out, _ = ps.extend_new_listings(close, middle)
    assert out.loc["2026-10-12", "TRIVENIPT"] == 1368.0


def test_listings_before_the_owners_date_are_left_alone():
    idx = IDX - pd.Timedelta(days=400)
    close, middle = _frames(idx=idx)
    out, done = ps.extend_new_listings(close, middle)
    assert done == {} and out.equals(close)


def test_a_long_lead_or_a_different_basis_is_not_chained():
    close, middle = _frames(scr_start=6 + 0)          # Screener never starts: nothing to chain from
    assert ps.extend_new_listings(close, middle)[1] == {}
    close, middle = _frames()
    close.loc["2026-10-16", "TRIVENIPT"] = 650.0      # first common closes disagree by over 1%
    assert ps.extend_new_listings(close, middle)[1] == {}
    big = pd.date_range("2026-10-12", periods=12, freq="B")
    nse = pd.Series(np.linspace(600, 650, 12), index=big)
    scr = nse.where(nse.index >= big[7])              # 7 sessions of lead: over the limit
    assert ps.extend_new_listings(pd.DataFrame({"X": scr}), pd.DataFrame({"X": nse}))[1] == {}


def test_the_app_frame_carries_it_and_says_so():
    close, middle = _frames()
    chosen = ps.PriceFrames(adj_close=close, close=close, high=None, low=None,
                            volume=pd.DataFrame(1.0, index=close.index, columns=close.columns),
                            source="screener", intraday=False)
    out = ps.keep_and_fill(chosen, ["TRIVENIPT", "OTHER"], None, middle, weekly_fill=False)
    assert out.close.loc["2026-10-12", "TRIVENIPT"] == 684.0
    assert any("TRIVENIPT 2" in n for n in out.notes)
