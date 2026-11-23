"""S213: an action NSE listed in words our parser did not read (CCAVENUE, 19 Oct 2026).

NSE's Bc file listed AvenuesAI's 10:1 consolidation as "CNSLDATNRE1 TO RS10" (12 and 13 Oct 2026),
with a record date (13 Oct) and no ex-date. The parser matched only "CONSOLIDAT", and every reader
drops an action with no ex-date, so the long file read +840% on 19 Oct (13.83 to 130.05, trading
halted 13-16 Oct) where Screener read -6%. BSE's bhavcopy: scrip 539807, ISIN INE483S01020 to
INE483S01038, 13.81 on 12 Oct and 130.03 on 19 Oct. NSE's equity list: face value Rs 10.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.loaders import nse_adjusted as na
from src.loaders import nse_bundle as nb

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("purpose,factor", [
    ("CNSLDATNRE1 TO RS10", 10.0),          # CCAVENUE, 12 Oct 2026
    ("CNSLDATN RE 1 TO RS 10", 10.0),       # SHEKHAWATI, 28 Aug 2024
    ("CNSLDATNRS10 TO RS1000", 100.0),      # KAUSHALYA, 12 Jan 2024
    ("Consolidation Of Shares From Rs 2/- To Rs 10/-", 5.0),
    ("FVSPLT FRM RS 10 TO RE 1", 0.1),      # the split wording still reads as before
])
def test_nse_consolidation_wordings(purpose, factor):
    out = nb.classify_purpose(purpose)
    assert out["kind"] in ("consolidation", "split")
    assert out["price_factor"] == pytest.approx(factor)


def test_a_step_with_no_ex_date_takes_its_record_date():
    acts = pd.DataFrame({"symbol": ["CCAVENUE", "X"], "kind": ["consolidation", "dividend"],
                         "ex_date": [pd.NaT, pd.NaT], "record_date": pd.to_datetime(["2026-10-13", "2026-10-13"]),
                         "price_factor": [10.0, np.nan], "purpose": ["CNSLDATNRE1 TO RS10", "DIV RS 5"]})
    out = nb.fill_ex_dates(acts)
    assert out.loc[0, "ex_date"] == pd.Timestamp("2026-10-13")
    assert pd.isna(out.loc[1, "ex_date"])          # only splits, consolidations and bonuses


def test_the_consolidation_is_applied_on_the_first_session_after_the_halt():
    idx = pd.to_datetime(["2026-10-08", "2026-10-09", "2026-10-12", "2026-10-19", "2026-10-20"])
    close = pd.DataFrame({"CCAVENUE": [15.02, 14.90, 13.83, 130.05, 123.66]}, index=idx)
    acts = nb.fill_ex_dates(pd.DataFrame({
        "symbol": ["CCAVENUE"], "series": ["EQ"], "kind": ["consolidation"], "ex_date": [pd.NaT],
        "record_date": [pd.Timestamp("2026-10-13")], "price_factor": [10.0], "purpose": ["CNSLDATNRE1 TO RS10"]}))
    factors, verdicts = na.action_factors(close, acts)
    v = pd.DataFrame(verdicts)
    assert v.iloc[0]["verdict"] == "applied" and v.iloc[0]["session"] == pd.Timestamp("2026-10-19")
    factors.index = close.index
    adjusted = na.adjust(close, factors)["CCAVENUE"]
    assert round(adjusted.loc["2026-10-12"], 2) == 138.3          # Screener's own adjusted close


def test_the_nightly_check_finds_a_step_screener_does_not_have():
    spec = importlib.util.spec_from_file_location("chk", ROOT / "scripts" / "check_long_against_screener.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    idx = pd.to_datetime(["2026-10-12", "2026-10-19", "2026-10-20"])
    long = pd.DataFrame({"CCAVENUE": [13.83, 130.05, 123.66], "FMGOETZE": [613.7, 516.8, 510.0]}, index=idx)
    scr = pd.DataFrame({"CCAVENUE": [138.3, 130.05, 123.66], "FMGOETZE": [613.7, 501.45, 495.0]}, index=idx)
    found = m.disagreements(long, scr)
    assert list(found["symbol"]) == ["CCAVENUE"]   # a 10%+ dividend taken out of one only is not a step
    assert m.disagreements(long.assign(CCAVENUE=scr["CCAVENUE"]), scr).empty
    wf = (ROOT / ".github" / "workflows" / "nse_long_prices.yml").read_text(encoding="utf-8")
    assert "scripts/check_long_against_screener.py --long" in wf
