"""The gap audit finds a gap's BSE code by the BSE fill's rule (TODO S52).

scripts/audit_gaps_against_bse.py matched BSE codes by price only and picked
another company for 47 of its 147 "NSE-only" gaps on 3 Oct 2026 (MBAPL eleven
codes, BHARATRAS 2008 Indian Card Clothing). It now calls
src/loaders/bse_fill.map_code: ISIN first, the price match only when no ISIN finds
a code, and a code whose ISIN names another issuer is not checked.
"""
import numpy as np
import pandas as pd

from scripts import audit_gaps_against_bse as audit
from src.loaders import bse_fill

DAYS = pd.bdate_range("2023-10-02", "2023-11-24")       # 40 sessions
GAP = DAYS[10:25]                                        # NSE has no row for these 15
HISTORY = pd.DataFrame({"symbol": ["ABC"], "isin": ["INE111A01011"],
                        "first": [pd.Timestamp("2011-06-22")], "last": [pd.Timestamp("2021-06-04")]})


def _nse() -> pd.DataFrame:
    s = pd.Series(100.0 * 1.01 ** np.arange(len(DAYS)), index=DAYS)
    s[GAP] = np.nan
    return pd.DataFrame({"ABC": s})


def _bse(code: int, isin=None, shares: float = 100.0, gap_shares: float | None = None) -> pd.DataFrame:
    """BSE rows for one code at NSE's level every session."""
    full = 100.0 * 1.01 ** np.arange(len(DAYS))
    return pd.DataFrame({"date": DAYS, "code": code, "name": f"CO{code}", "close": full.round(4),
                         "shares": [gap_shares if gap_shares is not None and d in GAP else shares for d in DAYS],
                         "isin": isin})


def _run(bse: pd.DataFrame, history=HISTORY) -> pd.Series:
    close = _nse()
    out = audit.audit(close, close, bse, history=history)
    assert len(out) == 1
    return out.iloc[0]


def test_the_symbols_own_isin_wins_over_a_lookalike_price():
    """BHARATRAS 2008: another company's price fitted; NSE's ISIN (another period) finds the right code."""
    bse = pd.concat([_bse(500009, isin="INE999Z01016"), _bse(590066, isin="INE111A01011")])
    row = _run(bse)
    assert row["bse_code"] == 590066 and row["mapped_by"] == "isin (another period)"
    assert row["verdict"] == "NSE-only gap: BSE traded" and row["bse_traded_sessions"] == len(GAP)


def test_a_price_match_on_another_issuers_code_is_not_checked():
    """MBAPL: the price fitted codes of other companies; BSE's ISIN on the code says so."""
    row = _run(_bse(500009, isin="INE999Z01016"))
    assert row["verdict"] == "not checked: ISIN mismatch"
    assert row["bse_traded_sessions"] == 0


def test_an_ambiguous_price_match_is_not_checked():
    """Before July 2024 BSE's file has no ISIN: two codes at the same price decide nothing."""
    row = _run(pd.concat([_bse(500001), _bse(500002)]), history=None)
    assert row["verdict"] == "not checked: ambiguous BSE match"


def test_an_isin_on_two_bse_codes_is_not_checked():
    row = _run(pd.concat([_bse(500001, isin="INE111A01011"), _bse(500002, isin="INE111A01011")]))
    assert row["verdict"] == "not checked: ISIN maps to more than one BSE code"
    assert pd.isna(row["bse_code"])


def test_a_suspension_on_both_exchanges_and_a_price_only_match_still_classify():
    row = _run(_bse(500001, isin="INE111A01011", gap_shares=0))
    assert row["verdict"] == "no BSE trading either" and row["mapped_by"] == "isin (another period)"
    row = _run(_bse(500001), history=None)                  # no ISIN anywhere: the price match
    assert row["mapped_by"] == "price match" and row["verdict"] == "NSE-only gap: BSE traded"


def test_the_audit_and_the_fill_pick_the_same_code():
    bse = pd.concat([_bse(500009, isin="INE999Z01016"), _bse(590066, isin="INE111A01011")])
    _out, cells, gaps = bse_fill.fill(_nse(), bse, history=HISTORY)
    row = _run(bse)
    assert gaps["bse_code"].iloc[0] == row["bse_code"] == 590066
    assert set(cells["bse_code"]) == {590066}
