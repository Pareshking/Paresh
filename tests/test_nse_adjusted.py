"""NSE adjusted prices: the Bc file's splits and bonuses, applied where the price confirms them."""

import numpy as np
import pandas as pd

from src.loaders import nse_adjusted as na


def _rows(sym, closes, prevs, series="EQ", vol=100.0):
    days = pd.bdate_range("2026-01-05", periods=len(closes))
    return pd.DataFrame({
        "date": days, "series": series, "symbol": sym, "mkt": "N",
        "close": closes, "prev_close": prevs, "high": closes, "low": closes,
        "volume": vol, "value": 1.0,
    })


def _split_frame():
    # 1:5 split on day 3. NSE's previous close is NOT adjusted (as in its
    # real files: ADANIPOWER, 22 Sep 2025), so the Bc file carries the action.
    a = _rows("ABC", [100.0, 102.0, 21.0, 22.0], [99.0, 100.0, 102.0, 21.0])
    b = _rows("XYZ", [50.0, 51.0, 52.0, 53.0], [49.0, 50.0, 51.0, 52.0])
    idx = _rows("", [1.0, 1.0, 1.0, 1.0], [1.0, 1.0, 1.0, 1.0]).assign(mkt="Y", security="NIFTY 50")
    return pd.concat([a, b, idx], ignore_index=True)


def _actions(*rows):
    return pd.DataFrame(rows, columns=["symbol", "kind", "ex_date", "price_factor"])


SPLIT = ("ABC", "split", pd.Timestamp("2026-01-07"), 0.2)


def test_a_split_from_the_bc_file_is_applied_backwards():
    adj, f, v = na.adjusted_frames(_split_frame(), _actions(SPLIT))
    assert np.isclose(f.at[pd.Timestamp("2026-01-07"), "ABC"], 0.2)
    assert np.allclose(adj["close"]["ABC"].tolist(), [20.0, 20.4, 21.0, 22.0])
    assert np.allclose(adj["volume"]["ABC"].tolist(), [500.0, 500.0, 100.0, 100.0])
    assert np.allclose(adj["close"]["XYZ"].tolist(), [50.0, 51.0, 52.0, 53.0])
    assert v["verdict"].tolist() == ["applied"]
    assert "" not in adj["close"].columns                 # index rows dropped


def test_an_action_the_price_does_not_confirm_is_not_applied():
    # Bc lists the split twice (a revised date) and a bonus XYZ's price never saw.
    adj, f, v = na.adjusted_frames(_split_frame(), _actions(
        SPLIT, ("ABC", "split", pd.Timestamp("2026-01-08"), 0.2),
        ("XYZ", "bonus", pd.Timestamp("2026-01-08"), 0.5)))
    assert (f != 1.0).sum().sum() == 1                    # only the real ex-date
    assert v.set_index(["symbol", "date"])["verdict"].to_dict() == {
        ("ABC", pd.Timestamp("2026-01-07")): "applied",
        ("ABC", pd.Timestamp("2026-01-08")): "no move",
        ("XYZ", pd.Timestamp("2026-01-08")): "no move",
    }
    assert np.allclose(adj["close"]["XYZ"].tolist(), [50.0, 51.0, 52.0, 53.0])


def test_without_the_action_the_drop_is_listed_as_unexplained():
    w = na.wide(_split_frame())
    f, _v = na.action_factors(w["close"], _actions())
    j = na.unexplained_jumps(w["close"], f)
    assert j["symbol"].tolist() == ["ABC"] and np.isclose(j["move"].iat[0], 21 / 102)
    f2, _v = na.action_factors(w["close"], _actions(SPLIT))
    assert na.unexplained_jumps(w["close"], f2).empty


def test_eq_is_preferred_when_a_stock_trades_in_both_series():
    both = pd.concat([_rows("ABC", [10.0], [10.0], "BE"), _rows("ABC", [11.0], [11.0], "EQ")])
    assert na.wide(both)["close"].iat[0, 0] == 11.0


def test_level_drift_flags_an_adjustment_one_side_missed():
    adj, _f, _v = na.adjusted_frames(_split_frame(), _actions(SPLIT))
    screener = adj["close"].copy()
    screener.loc[:"2026-01-06", "ABC"] *= 5                    # never adjusted the split
    d = na.level_drift(adj["close"], screener)
    assert d.index[0] == "ABC" and d.loc["ABC", "max_drift"] > 0.5
    assert d.loc["XYZ", "max_drift"] == 0


def test_compare_rankings_reports_overlap_and_order():
    a = pd.DataFrame({"Symbol": list("ABCD"), "Rank": [1, 2, 3, 4]})
    b = pd.DataFrame({"Symbol": list("BACE"), "Rank": [1, 2, 3, 4]})
    r = na.compare_rankings(a, b, top=(2,))
    assert r["common"] == 3 and r["top2_overlap"] == 2
    assert r["only_a"] == ["D"] and r["only_b"] == ["E"]


def test_a_missing_session_is_found_from_the_previous_close():
    # Day 3's previous close is a session we never collected (a Budget
    # Sunday): most stocks' previous close is not our last close.
    days = pd.bdate_range("2026-01-05", periods=4)
    rows = []
    for sym in ["A", "B", "C", "D"]:
        closes = [100.0, 100.0, 103.0, 104.0]
        prevs = [100.0, 100.0, 102.0 if sym != "D" else 100.0, 103.0]  # 102: the missing session
        rows.append(pd.DataFrame({"date": days, "series": "EQ", "symbol": sym, "mkt": "N",
                                  "close": closes, "prev_close": prevs, "high": closes,
                                  "low": closes, "volume": 1.0, "value": 1.0}))
    w = na.wide(pd.concat(rows))
    g = na.gap_days(w["close"], w["prev_close"])
    assert list(g.index) == [days[2]] and np.isclose(g.iat[0], 0.75)


def test_the_ex_date_matches_whatever_type_it_was_stored_as():
    for ex in (pd.Timestamp("2026-01-07").date(), "2026-01-07",
               pd.Timestamp("2026-01-07").as_unit("ms")):
        _adj, f, v = na.adjusted_frames(_split_frame(), _actions(("ABC", "split", ex, 0.2)))
        assert v["verdict"].tolist() == ["applied"], ex
        assert np.isclose(f.at[pd.Timestamp("2026-01-07"), "ABC"], 0.2), ex


def test_an_ex_date_printed_month_first_is_found_on_the_swapped_date():
    # E2E's 1:10 split went ex on 6 Mar 2026; Bc printed it as 2026-06-03.
    days = pd.bdate_range("2026-02-26", "2026-06-10")
    close = pd.DataFrame({"E2E": np.where(days < pd.Timestamp("2026-03-06"), 100.0, 10.2)}, index=days)
    f, v = na.action_factors(close, _actions(("E2E", "split", pd.Timestamp("2026-06-03"), 0.1)))
    assert v["verdict"].tolist() == ["date swapped"]
    assert v["session"].iat[0] == pd.Timestamp("2026-03-06")
    assert np.isclose(f.at[pd.Timestamp("2026-03-06"), "E2E"], 0.1) and (f != 1.0).sum().sum() == 1
    # A day past the 12th cannot be a swap: nothing is applied.
    f, v = na.action_factors(close, _actions(("E2E", "split", pd.Timestamp("2026-05-20"), 0.1)))
    assert v["verdict"].tolist() == ["no move"] and (f == 1.0).all().all()


def test_a_demerger_is_priced_at_the_ex_dates_fall():
    closes = [100.0, 101.0, 64.0, 65.0]                  # 36.6% left with the new company
    w = na.wide(_rows("VEDL", closes, closes))
    f, v = na.action_factors(w["close"], _actions(("VEDL", "demerger", pd.Timestamp("2026-01-07"), np.nan)))
    assert v["verdict"].tolist() == ["demerger"]
    assert np.isclose(f.at[pd.Timestamp("2026-01-07"), "VEDL"], 64 / 101)
    rising = na.wide(_rows("X", [100.0, 101.0, 103.0, 104.0], [100.0] * 4))
    f, v = na.action_factors(rising["close"], _actions(("X", "demerger", pd.Timestamp("2026-01-07"), np.nan)))
    assert v["verdict"].tolist() == ["no move"] and (f == 1.0).all().all()


def test_one_action_listed_twice_is_applied_once():
    """NSE's daily Bc file and its yearly list carry the same split, worded
    differently. Multiplied, a 1:5 split became x0.04 and went unapplied
    (HDFCBANK 2019, ADANIPOWER 2025 in the 2008-2026 audit)."""
    twice = pd.DataFrame([
        {"symbol": "ABC", "kind": "split", "ex_date": pd.Timestamp("2026-01-07"),
         "price_factor": 0.2, "purpose": "FACE VALUE SPLIT (SUB-DIVISION) - FROM RS 10/- PER SHARE TO RS 2/- PER SHARE"},
        {"symbol": "ABC", "kind": "split", "ex_date": "2026-01-07",
         "price_factor": 0.2, "purpose": "FVSPLT FRM RS 10 TO RS 2"},
    ])
    adj, f, v = na.adjusted_frames(_split_frame(), twice)
    assert np.isclose(f.at[pd.Timestamp("2026-01-07"), "ABC"], 0.2)
    assert v["verdict"].tolist() == ["applied"]
    assert np.allclose(adj["close"]["ABC"].tolist(), [20.0, 20.4, 21.0, 22.0])


def test_the_same_split_under_a_month_first_date_is_not_applied_again():
    """MCX 2026: the Bc file said 2 Jan, the yearly list 1 Feb (month-first).
    Both found the 2 Jan fall; applied twice, the long file showed a x5 jump."""
    days = pd.DatetimeIndex(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08",
                             "2026-06-30", "2026-07-01", "2026-07-02"])
    close = pd.DataFrame({"ABC": [100.0, 102.0, 21.0, 22.0, 23.0, 23.1, 23.2]}, index=days)
    rows = _actions(("ABC", "split", pd.Timestamp("2026-01-07"), 0.2),
                    ("ABC", "split", pd.Timestamp("2026-07-01"), 0.2))
    f, v = na.action_factors(close, rows)
    assert np.isclose(f.at[pd.Timestamp("2026-01-07"), "ABC"], 0.2) and (f != 1.0).sum().sum() == 1
    assert sorted(v["verdict"]) == ["applied", "duplicate"]


def test_two_different_actions_on_one_day_still_multiply():
    both = _actions(("ABC", "bonus", pd.Timestamp("2026-01-07"), 0.5),
                    ("ABC", "split", pd.Timestamp("2026-01-07"), 0.4))
    _adj, f, v = na.adjusted_frames(_split_frame(), both)
    assert np.isclose(f.at[pd.Timestamp("2026-01-07"), "ABC"], 0.2)
    assert v["verdict"].tolist() == ["applied"]


def test_a_holiday_stored_as_a_copy_of_the_session_before_is_found():
    days = pd.bdate_range("2024-01-22", periods=5)
    rng = np.random.default_rng(3)
    close = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.01, (5, 40)), axis=0)), index=days)
    vol = pd.DataFrame(rng.integers(1_000, 9_000, (5, 40)).astype(float), index=days)
    close.iloc[2], vol.iloc[2] = close.iloc[1], vol.iloc[1]      # 24 Jan repeats 23 Jan
    close.iloc[4, :3] = close.iloc[3, :3]                      # a few unchanged stocks: normal
    out = na.copied_sessions(close, vol)
    assert list(out.index) == [days[2]]
