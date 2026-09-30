from __future__ import annotations

import pandas as pd
import pytest

from src.ui import canonical_book
from src.ui.views.portfolio_view import build_portfolio_history, build_portfolio_tracker


def _book() -> pd.DataFrame:
    frame = pd.DataFrame(
        [
            {
                "Symbol": "AAA",
                "Industry": "Alpha",
                "Entry Date": pd.Timestamp("2026-08-03"),
                "Entry Price": 100.0,
                "Price Now": 120.0,
                "Return %": 0.20,
                "MTD %": 0.10,
                "Holding (Days)": 55,
                "Weight %": 0.50,
                "Rank at Entry": 3,
                "Rank at Rebalance": 2,
            },
            {
                "Symbol": "BBB",
                "Industry": "Beta",
                "Entry Date": pd.Timestamp("2026-09-01"),
                "Entry Price": 200.0,
                "Price Now": 180.0,
                "Return %": -0.10,
                "MTD %": -0.05,
                "Holding (Days)": 26,
                "Weight %": 0.50,
                "Rank at Entry": 5,
                "Rank at Rebalance": 4,
            },
        ]
    )
    frame.attrs["as_of"] = pd.Timestamp("2026-09-30")
    return frame


def _ranking() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Symbol": "AAA",
                "Company Name": "Alpha Ltd",
                "Industry": "Alpha",
                "TV_Sector": "Industrials",
                "Rank": 7,
                "Market Cap (Cr)": 1200,
                "1M Return": 4.0,
                "3M Return": 8.0,
                "6M Return": 15.0,
                "12M Return": 30.0,
            },
            {
                "Symbol": "BBB",
                "Company Name": "Beta Ltd",
                "Industry": "Beta",
                "TV_Sector": "Financials",
                "Rank": 11,
                "Market Cap (Cr)": 900,
                "1M Return": -2.0,
                "3M Return": 3.0,
                "6M Return": 7.0,
                "12M Return": 12.0,
            },
            {
                "Symbol": "CCC",
                "Company Name": "Not Held",
                "Industry": "Other",
                "TV_Sector": "Other",
                "Rank": 1,
                "Market Cap (Cr)": 2000,
                "1M Return": 5.0,
                "3M Return": 9.0,
                "6M Return": 20.0,
                "12M Return": 40.0,
            },
        ]
    )


def test_canonical_current_book_is_the_track_record_live_book(monkeypatch):
    expected = _book()
    calls = []

    def fake_record_run(adj_close, benchmark_close, system):
        calls.append((adj_close, benchmark_close, system))
        return {"live_book": expected, "live_meta": {"as_of": pd.Timestamp("2026-09-30")}}

    monkeypatch.setattr(
        "src.ui.views.track_record_view.record_run",
        fake_record_run,
    )

    got, result = canonical_book.current_book(
        pd.DataFrame({"AAA": [100.0]}),
        pd.Series([100.0]),
        "750",
    )

    assert calls and calls[0][2] == "750"
    assert result["live_meta"]["as_of"] == pd.Timestamp("2026-09-30")
    assert got["Symbol"].tolist() == ["AAA", "BBB"]
    assert got["Entry Date"].tolist() == expected.sort_values("Symbol")["Entry Date"].tolist()


def test_canonical_current_book_rejects_duplicate_positions(monkeypatch):
    duplicate = pd.concat([_book(), _book().iloc[[0]]], ignore_index=True)

    monkeypatch.setattr(
        "src.ui.views.track_record_view.record_run",
        lambda *_args: {"live_book": duplicate},
    )

    with pytest.raises(ValueError, match="duplicate symbols"):
        canonical_book.current_book(pd.DataFrame(), None, "750")


def test_portfolio_tracker_cannot_add_or_select_symbols():
    book = _book()
    out = build_portfolio_tracker(book, _ranking(), 1_000_000)

    assert out["Symbol"].tolist() == ["AAA", "BBB"]
    assert "CCC" not in set(out["Symbol"])
    assert len(out) == len(book)


def test_portfolio_tracker_uses_recorded_entry_data_and_target_weights():
    out = build_portfolio_tracker(_book(), _ranking(), 1_000_000)

    aaa = out.set_index("Symbol").loc["AAA"]
    bbb = out.set_index("Symbol").loc["BBB"]

    assert aaa["Entry Date"] == pd.Timestamp("2026-08-03")
    assert aaa["Entry Price"] == 100.0
    assert aaa["Target Weight %"] == pytest.approx(0.50)
    assert bbb["Entry Date"] == pd.Timestamp("2026-09-01")
    assert bbb["Entry Price"] == 200.0


def test_portfolio_tracker_capital_changes_sizing_not_membership():
    book = _book()
    a = build_portfolio_tracker(book, _ranking(), 1_000_000)
    b = build_portfolio_tracker(book, _ranking(), 2_000_000)

    assert a["Symbol"].tolist() == b["Symbol"].tolist()
    assert (b["Shares"] >= a["Shares"]).all()
    assert b["Target Weight %"].tolist() == a["Target Weight %"].tolist()


def test_portfolio_tracker_current_weight_and_pnl_are_accounting_fields():
    out = build_portfolio_tracker(_book(), _ranking(), 1_000_000)

    assert out["P&L (₹)"].sum() == pytest.approx(
        out["Current Value (₹)"].sum() - out["Invested Value (₹)"].sum()
    )
    assert out["Weight %"].sum() <= 100.0 + 1e-9
    assert set(out["Status"]) == {"Held"}


def test_portfolio_history_scales_canonical_equity_and_preserves_trades():
    record = {
        "equity_curve": pd.Series([1.0, 1.05, 1.02], index=pd.date_range("2026-01-02", periods=3)),
        "benchmark": pd.Series([1.0, 1.03, 1.01], index=pd.date_range("2026-01-02", periods=3)),
        "monthly": pd.DataFrame([{"Strategy Net": 0.05}]),
        "closed_trades": pd.DataFrame([{"Symbol": "AAA", "Status": "Closed", "Return %": 5.0}]),
        "tradebook": pd.DataFrame([{"Action": "BUY", "Symbol": "AAA"}]),
    }
    out = build_portfolio_history(record, 2_000_000)

    assert out["equity"].iloc[0] == pytest.approx(2_000_000)
    assert out["equity"].iloc[1] == pytest.approx(2_100_000)
    assert out["benchmark"].iloc[-1] == pytest.approx(2_020_000)
    assert out["max_drawdown"] == pytest.approx(1.02 / 1.05 - 1.0)
    assert out["trades"]["Symbol"].tolist() == ["AAA"]
    assert out["tradebook"]["Action"].tolist() == ["BUY"]
