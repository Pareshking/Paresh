"""NSE adjusted prices: NSE's own previous-close steps, applied backwards."""

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
    # 1:5 split on day 3: NSE prints the previous close as 100/5 = 20.
    a = _rows("ABC", [100.0, 102.0, 21.0, 22.0], [99.0, 100.0, 20.4, 21.0])
    b = _rows("XYZ", [50.0, 51.0, 52.0, 53.0], [49.0, 50.0, 51.0, 52.0])
    idx = _rows("", [1.0, 1.0, 1.0, 1.0], [1.0, 1.0, 1.0, 1.0]).assign(mkt="Y", security="NIFTY 50")
    return pd.concat([a, b, idx], ignore_index=True)


def test_a_split_is_read_from_nses_previous_close_and_applied_backwards():
    adj, f = na.adjusted_frames(_split_frame())
    assert np.isclose(f.at[pd.Timestamp("2026-01-07"), "ABC"], 0.2)
    assert np.allclose(adj["close"]["ABC"].tolist(), [20.0, 20.4, 21.0, 22.0])
    assert np.allclose(adj["volume"]["ABC"].tolist(), [500.0, 500.0, 100.0, 100.0])
    assert np.allclose(adj["close"]["XYZ"].tolist(), [50.0, 51.0, 52.0, 53.0])
    assert "" not in adj["close"].columns                 # index rows dropped


def test_eq_is_preferred_when_a_stock_trades_in_both_series():
    both = pd.concat([_rows("ABC", [10.0], [10.0], "BE"), _rows("ABC", [11.0], [11.0], "EQ")])
    assert na.wide(both)["close"].iat[0, 0] == 11.0


def test_crosscheck_names_disagreements_and_unparsed_steps():
    _adj, f = na.adjusted_frames(_split_frame())
    actions = pd.DataFrame({
        "symbol": ["ABC", "XYZ"], "kind": ["split", "bonus"],
        "ex_date": [pd.Timestamp("2026-01-07"), pd.Timestamp("2026-01-08")],
        "price_factor": [0.5, 0.5],
    })
    c = na.crosscheck_actions(f, actions)
    assert c["mismatched"]["symbol"].tolist() == ["ABC"]       # Bc says 0.5, NSE stepped 0.2
    assert c["missing"]["symbol"].tolist() == ["XYZ"]          # a bonus with no step
    assert c["unparsed"].empty


def test_level_drift_flags_an_adjustment_one_side_missed():
    adj, _f = na.adjusted_frames(_split_frame())
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
