"""NSE-only gaps filled from BSE's raw closes (src/loaders/bse_fill.py, TODO S38).

Small made-up frames, one rule each: fill in raw space, every factor reaches a
filled day, NSE's own days never touched, an ISIN that names another company
refused, the junction guard, a suspension left empty.
"""
import numpy as np
import pandas as pd
import pytest

from scripts import build_nse_long_prices as long
from src.loaders import bse_fill

DAYS = pd.bdate_range("2023-10-02", "2023-11-24")       # 40 sessions
GAP = DAYS[10:25]                                        # NSE has no row for these 15


def _nse_close(level: float = 100.0, step: float = 1.01) -> pd.Series:
    s = pd.Series(level * step ** np.arange(len(DAYS)), index=DAYS)
    s[GAP] = np.nan
    return s


def _bse(code: int = 500001, close: pd.Series | None = None, isin=None, offset: float = 1.0,
         shares: float = 100.0, days=DAYS, after_offset: float | None = None) -> pd.DataFrame:
    """BSE rows for one code: NSE's level x offset every session (BSE also trades NSE's days)."""
    full = pd.Series(100.0 * 1.01 ** np.arange(len(DAYS)), index=DAYS) if close is None else close
    rows = []
    for d in days:
        f = offset if after_offset is None or d < GAP[-1] else after_offset
        rows.append({"date": d, "code": code, "name": "X", "close": round(float(full[d]) * f, 4),
                     "shares": shares, "isin": isin})
    return pd.DataFrame(rows)


def test_a_gap_is_filled_with_bses_raw_close_and_every_cell_recorded():
    close = pd.DataFrame({"ABC": _nse_close()})
    out, cells, gaps = bse_fill.fill(close, _bse())
    assert out["ABC"].notna().all()
    assert out.loc[GAP, "ABC"].tolist() == pytest.approx((100.0 * 1.01 ** np.arange(10, 25)).round(4).tolist())
    assert len(cells) == len(GAP) and set(cells["bse_code"]) == {500001}
    assert cells["date"].tolist() == [d.date() for d in GAP]
    assert gaps["verdict"].tolist() == ["filled"] and gaps["filled_sessions"].iloc[0] == 15
    assert bse_fill.summary(cells, gaps)["cells_filled"] == 15


def test_a_day_nse_has_a_close_for_is_never_overwritten():
    nse = _nse_close()
    close = pd.DataFrame({"ABC": nse})
    # BSE 1% off NSE on every day (inside the junction guard): NSE's days must stay NSE's.
    out, cells, _ = bse_fill.fill(close, _bse(offset=1.01))
    have = nse.notna()
    assert (out.loc[have, "ABC"] == nse[have]).all()
    assert set(pd.to_datetime(cells["date"])) == set(GAP)


def test_a_suspension_bse_shows_too_is_not_filled():
    close = pd.DataFrame({"ABC": _nse_close()})
    bse = _bse()
    bse.loc[bse["date"].isin(GAP), "shares"] = 0          # BSE did not trade it either
    out, cells, gaps = bse_fill.fill(close, bse)
    assert out.loc[GAP, "ABC"].isna().all() and cells.empty
    assert gaps["verdict"].iloc[0] == "refused: no BSE trading either (a suspension)"


def test_a_gap_bse_traded_only_partly_is_refused():
    close = pd.DataFrame({"ABC": _nse_close()})
    bse = _bse()
    other = _bse(509999, offset=0.07)                      # BSE's file exists every day
    bse = pd.concat([bse[~bse["date"].isin(GAP[:10])], other])   # ABC traded on 5 of 15 sessions
    out, cells, gaps = bse_fill.fill(close, bse)
    assert out.loc[GAP, "ABC"].isna().all() and cells.empty
    assert gaps["verdict"].iloc[0] == "refused: partly traded on BSE"


def test_only_sessions_bse_traded_are_filled_the_rest_stay_empty():
    close = pd.DataFrame({"ABC": _nse_close()})
    bse = _bse()
    bse = bse[bse["date"] != GAP[3]]                       # one session BSE did not trade
    out, cells, gaps = bse_fill.fill(close, bse)
    assert np.isnan(out.at[GAP[3], "ABC"]) and len(cells) == 14
    assert gaps["verdict"].iloc[0] == "filled"


def test_a_short_gap_is_left_alone():
    nse = pd.Series(100.0 * 1.01 ** np.arange(len(DAYS)), index=DAYS)
    nse[DAYS[10:13]] = np.nan                              # 3 sessions: below MIN_GAP
    out, cells, gaps = bse_fill.fill(pd.DataFrame({"ABC": nse}), _bse())
    assert out["ABC"].isna().sum() == 3 and cells.empty and gaps.empty


def test_the_junction_guard_refuses_a_gap_whose_bse_level_does_not_meet_nses():
    close = pd.DataFrame({"ABC": _nse_close()})
    # Fine at the start, 5% off NSE from the gap's last session on: not the same price line.
    out, cells, gaps = bse_fill.fill(close, _bse(after_offset=1.05))
    assert out.loc[GAP, "ABC"].isna().all() and cells.empty
    assert gaps["verdict"].iloc[0] == "refused: junction: BSE more than 2% off NSE"
    assert gaps["detail"].iloc[0].startswith("end")
    assert gaps["junction_before"].iloc[0] == pytest.approx(0.0)


def test_an_isin_naming_another_company_is_refused():
    close = pd.DataFrame({"ABC": _nse_close()})
    history = pd.DataFrame({"symbol": ["ABC"], "isin": ["INE111A01011"],
                            "first": [pd.Timestamp("2011-06-22")], "last": [pd.Timestamp("2025-06-04")]})
    # The price fits, but BSE's file says the code is another issuer's.
    bse = _bse(isin="INE999Z01016")
    out, cells, gaps = bse_fill.fill(close, bse, history=history)
    assert out.loc[GAP, "ABC"].isna().all() and cells.empty
    assert gaps["verdict"].iloc[0] == "refused: ISIN mismatch"


def test_the_code_is_found_by_isin_when_both_sides_carry_one():
    close = pd.DataFrame({"ABC": _nse_close()})
    history = pd.DataFrame({"symbol": ["ABC"], "isin": ["INE111A01011"],
                            "first": [pd.Timestamp("2011-06-22")], "last": [pd.Timestamp("2025-06-04")]})
    # Two codes with the same prices: by price this is ambiguous, by ISIN it is not.
    bse = pd.concat([_bse(500001, isin="INE111A01011"), _bse(500002, isin="INE222B01012")])
    out, cells, gaps = bse_fill.fill(close, bse, history=history)
    assert gaps["mapped_by"].iloc[0] == "isin" and set(cells["bse_code"]) == {500001}
    assert out["ABC"].notna().all()


def test_an_isin_from_another_period_finds_the_code_and_refuses_a_lookalike():
    """BHARATRAS 2008: NSE's ISIN is known only for 2011 - 2021 and BSE's only from 2024,
    and another company's BSE price fitted; the symbol's own ISIN, any period, decides."""
    close = pd.DataFrame({"ABC": _nse_close()})
    history = pd.DataFrame({"symbol": ["ABC"], "isin": ["INE111A01011"],
                            "first": [pd.Timestamp("2011-06-22")], "last": [pd.Timestamp("2021-06-04")]})
    lookalike = _bse(500009, isin="INE999Z01016")
    _out, cells, gaps = bse_fill.fill(close, lookalike, history=history)
    assert cells.empty and gaps["verdict"].iloc[0] == "refused: ISIN mismatch"
    own = pd.concat([lookalike, _bse(590066, isin="INE111A01011")])
    _out, cells, gaps = bse_fill.fill(close, own, history=history)
    assert gaps["mapped_by"].iloc[0] == "isin (another period)" and set(cells["bse_code"]) == {590066}


def test_an_ambiguous_price_match_is_refused():
    close = pd.DataFrame({"ABC": _nse_close()})
    bse = pd.concat([_bse(500001), _bse(500002)])          # no ISIN (BSE's old format)
    out, cells, gaps = bse_fill.fill(close, bse)
    assert out.loc[GAP, "ABC"].isna().all() and cells.empty
    assert gaps["verdict"].iloc[0] == "refused: ambiguous BSE match"


def test_todays_isin_is_used_only_after_the_isin_history_ends():
    history = pd.DataFrame({"symbol": ["ZZZ"], "isin": ["INE000Z01010"],
                            "first": [pd.Timestamp("2011-06-22")], "last": [pd.Timestamp("2021-06-04")]})
    current = {"ABC": "INE111A01011"}
    assert bse_fill.nse_isins("ABC", pd.Timestamp("2023-10-25"), pd.Timestamp("2026-04-20"),
                              history, current) == ["INE111A01011"]
    assert bse_fill.nse_isins("ABC", pd.Timestamp("2013-08-01"), pd.Timestamp("2013-09-01"),
                              history, current) == []


# ── through the long-file build: the fill is raw, the factors reach it ───────

def _prices(split_on: pd.Timestamp | None = None) -> pd.DataFrame:
    """NSE's raw rows for ABC with the gap; a 1:5 split on `split_on` (raw price / 5 from then)."""
    rows = []
    for i, d in enumerate(DAYS):
        for sym in ("ABC", "ZZZ"):                          # ZZZ trades every day: NSE's calendar
            if sym == "ABC" and d in GAP:
                continue
            c = 100.0 * 1.01 ** i / (5 if sym == "ABC" and split_on is not None and d >= split_on else 1)
            rows.append({"date": d, "mkt": "N", "series": "EQ", "symbol": sym, "close": c, "prev_close": c,
                         "high": c, "low": c, "volume": 1000.0, "value": c * 1000.0})
    return pd.DataFrame(rows)


def _bse_raw(split_on: pd.Timestamp | None = None) -> pd.DataFrame:
    raw = pd.Series([100.0 * 1.01 ** i / (5 if split_on is not None and d >= split_on else 1)
                     for i, d in enumerate(DAYS)], index=DAYS)
    return _bse(close=raw)


def _split(on: pd.Timestamp) -> pd.DataFrame:
    return pd.DataFrame([{"symbol": "ABC", "ex_date": on, "kind": "split", "price_factor": 0.2,
                          "purpose": "FACE VALUE SPLIT FROM RS 10 TO RS 2"}])


@pytest.mark.parametrize("split_on", [DAYS[30], GAP[7]], ids=["split after the gap", "split inside the gap"])
def test_a_split_reaches_the_filled_days_as_it_reaches_nses(split_on):
    log: dict = {}
    close, value, report = long.build(_prices(split_on), _split(split_on), {}, {}, ["ABC"],
                                      bse=_bse_raw(split_on), fill_log=log)
    s = close["ABC"].astype(float)
    assert s.notna().all()
    # Adjusted: one smooth 1% line, the split folded back over NSE's days and BSE's alike.
    assert (s / s.shift(1)).dropna().to_numpy() == pytest.approx(1.01, rel=1e-4)
    assert s.iloc[-1] == pytest.approx(100.0 * 1.01 ** (len(DAYS) - 1) / 5, rel=1e-5)
    # Raw BSE closes recorded, before the factor (the split inside the gap is BSE's own move).
    cells = log["cells"].set_index("date")
    assert cells.loc[GAP[0].date(), "bse_close"] == pytest.approx(100.0 * 1.01 ** 10, rel=1e-4)
    assert report["bse_fill"]["cells_filled"] == len(GAP)
    # Traded value is NSE's own: nothing filled.
    assert value.loc[GAP, "ABC"].isna().all()


def test_without_a_bse_table_the_build_fills_nothing_and_says_so():
    close, _value, report = long.build(_prices(), pd.DataFrame(columns=_split(DAYS[0]).columns), {}, {}, ["ABC"])
    assert close.loc[GAP, "ABC"].isna().all()
    assert report["bse_fill"]["cells_filled"] == 0 and "no BSE table" in report["bse_fill"]["status"]


# ── the BSE table's weekly refresh, its protection, and the verification ─────

def test_extending_the_bse_table_adds_new_sessions_and_never_loses_one():
    from scripts.bse_bhavcopy import extend

    base = _bse(days=DAYS[:20]).assign(group="A")
    new = _bse(days=DAYS[19:], offset=1.001, isin="INE111A01011").assign(group="A")
    out = extend(base, new)
    assert sorted(out["date"].unique()) == list(DAYS)
    # A session in both takes the new download's rows, once.
    assert (out["date"] == DAYS[19]).sum() == 1
    assert out.loc[out["date"] == DAYS[19], "isin"].iloc[0] == "INE111A01011"
    assert extend(base, base.iloc[0:0]).shape == base.shape


def test_the_bse_dataset_on_r2_is_protected_from_clean_up():
    from scripts import r2_retention as rr

    assert rr._protected("bse/daily")
    with pytest.raises(ValueError, match="protected"):
        rr.check_protected({"bse/daily": "archive/bse/daily"}, {})


def test_the_verification_compares_filled_days_with_each_reference():
    from scripts.verify_bse_fill import verify

    close = pd.DataFrame({"ABC": _nse_close()})
    out, cells, _ = bse_fill.fill(close, _bse())
    ref_good = pd.DataFrame({"ABC": out["ABC"] * 0.97})          # another basis: 3% lower throughout
    ref_bad = pd.DataFrame({"ABC": out["ABC"].where(~out.index.isin(GAP), out["ABC"] * 1.10)})
    frame, summary = verify(out, cells, {"good": ref_good, "bad": ref_bad})
    assert summary["cells_filled"] == 15
    # Level differs by 3%, but anchored on the NSE days around the gap it agrees.
    assert summary["by_reference"]["good"]["level_within_2pct"] == 0.0
    assert summary["by_reference"]["good"]["anchored_within_2pct"] == 1.0
    assert summary["by_reference"]["bad"]["anchored_within_2pct"] == 0.0
    assert summary["share_of_cells_with_a_reference"] == 1.0
    _frame, summary2 = verify(out, cells, {"bad": ref_bad})
    assert summary2["within_2pct_of_at_least_one_reference"] == 0
