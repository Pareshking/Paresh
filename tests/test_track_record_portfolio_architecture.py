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
    ledger = {
        "months": {
            "2026-01": {"strategy": 0.05, "benchmark": 0.03, "origin": "recorded", "universe": "point_in_time"},
            "2026-02": {"strategy": -0.0285714286, "benchmark": -0.0194174757, "origin": "recorded", "universe": "point_in_time"},
        }
    }
    out = build_portfolio_history(record, 2_000_000, ledger)

    assert out["equity"].iloc[0] == pytest.approx(2_000_000)
    assert out["equity"].iloc[1] == pytest.approx(2_100_000)
    assert out["equity"].iloc[2] == pytest.approx(2_040_000)
    assert out["benchmark"].iloc[-1] == pytest.approx(2_020_000)
    assert out["max_drawdown"] == pytest.approx(2.04 / 2.10 - 1.0)
    assert out["trades"]["Symbol"].tolist() == ["AAA"]
    assert out["tradebook"]["Action"].tolist() == ["BUY"]

def test_portfolio_tracker_uses_canonical_nse_industry_for_750():
    out = build_portfolio_tracker(_book(), _ranking(), 1_000_000)

    by_symbol = out.set_index("Symbol")
    assert by_symbol.loc["AAA", "Sector / Industry"] == "Alpha"
    assert by_symbol.loc["BBB", "Sector / Industry"] == "Beta"
    assert by_symbol.loc["AAA", "Sector / Industry"] != "Industrials"
    assert by_symbol.loc["BBB", "Sector / Industry"] != "Financials"


def test_portfolio_history_uses_fractional_ledger_returns():
    record = {
        "closed_trades": pd.DataFrame(),
        "tradebook": pd.DataFrame(),
    }
    ledger = {
        "months": {
            "2026-01": {"strategy": -0.026879, "benchmark": -0.03318},
            "2026-02": {"strategy": 0.036104, "benchmark": 0.003785},
            "2026-03": {"strategy": -0.122179, "benchmark": -0.113904},
            "2026-04": {"strategy": 0.184092, "benchmark": 0.105003},
            "2026-05": {"strategy": 0.10194, "benchmark": -0.00117},
            "2026-06": {"strategy": 0.090069, "benchmark": 0.014947},
            "2026-07": {"strategy": -0.021666, "benchmark": 0.020223},
            "2026-08": {"strategy": 0.126149, "benchmark": -0.000441},
        }
    }

    out = build_portfolio_history(record, 2_000_000, ledger)

    assert out["equity"].iloc[-1] == pytest.approx(2_773_872.8091234444, rel=1e-6)
    assert out["benchmark"].iloc[-1] == pytest.approx(1_964_712.7, rel=1e-6)

def test_record_run_passes_canonical_inception_to_stateful_backtest(monkeypatch):
    from src.ui.views import track_record_view

    captured = {}

    monkeypatch.setattr(track_record_view, "load_events", lambda: [])
    monkeypatch.setattr(track_record_view, "price_fingerprint", lambda _prices: "fp")
    monkeypatch.setattr(track_record_view, "membership_for", lambda _system: None)

    def fake_run_backtest(*args, **kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(track_record_view, "run_backtest", fake_run_backtest)

    dates = pd.bdate_range("2025-01-01", "2026-09-30")
    prices = pd.DataFrame({"AAA": range(len(dates))}, index=dates)

    track_record_view.record_run(prices, None, "750")

    assert captured["stateful_history"] is True
    assert captured["history_start"] == pd.Timestamp("2026-01-01")




def test_record_run_defensively_filters_pre_inception_history(monkeypatch):
    from src.ui.views import track_record_view

    monkeypatch.setattr(track_record_view, "load_events", lambda: [])
    monkeypatch.setattr(track_record_view, "price_fingerprint", lambda _prices: "fp")
    monkeypatch.setattr(track_record_view, "membership_for", lambda _system: None)

    pre_start = pd.DataFrame(
        [
            {"Period Start": pd.Timestamp("2022-08-05"), "Action": "BUY", "Symbol": "OLD"},
            {"Period Start": pd.Timestamp("2026-08-03"), "Action": "BUY", "Symbol": "NEW"},
        ]
    )
    closed = pd.DataFrame(
        [
            {"Exit Date": "02 Sep 2022", "Symbol": "OLD", "Status": "Closed"},
            {"Exit Date": "02 Sep 2026", "Symbol": "NEW", "Status": "Closed"},
        ]
    )

    def fake_run_backtest(*args, **kwargs):
        return {"tradebook": pre_start, "closed_trades": closed}

    monkeypatch.setattr(track_record_view, "run_backtest", fake_run_backtest)

    dates = pd.bdate_range("2025-01-01", "2026-09-30")
    prices = pd.DataFrame({"AAA": range(len(dates))}, index=dates)

    result = track_record_view.record_run(prices, None, "750")

    assert result["tradebook"]["Symbol"].tolist() == ["NEW"]
    assert result["closed_trades"]["Symbol"].tolist() == ["NEW"]


def test_portfolio_history_includes_live_month_to_date_without_rewriting_frozen_months():
    record = {
        "closed_trades": pd.DataFrame(),
        "tradebook": pd.DataFrame(),
    }
    ledger = {
        "months": {
            "2026-08": {"strategy": 0.126149, "benchmark": -0.000441},
        }
    }
    out = build_portfolio_history(
        record,
        2_000_000,
        ledger,
        {
            "strategy_mtd": 0.09493520755905593,
            "benchmark_mtd": -0.01,
            "mtd_period": "2026-09",
        },
    )

    assert out["equity"].iloc[-2] == pytest.approx(2_252_298.0, rel=1e-6)
    assert out["equity"].iloc[-1] == pytest.approx(
        2_252_298.0 * (1.0 + 0.09493520755905593), rel=1e-6
    )
    assert out["equity"].index[-1].to_period("M") == pd.Period("2026-09", freq="M")
    assert out["benchmark"].iloc[-1] == pytest.approx(
        out["benchmark"].iloc[-2] * 0.99, rel=1e-6
    )

def test_portfolio_tracker_calculates_day_pnl_percentage_from_previous_value():
    prices = pd.DataFrame(
        {"AAA": [100.0, 105.0], "BBB": [200.0, 198.0]},
        index=pd.date_range("2026-09-29", periods=2),
    )
    out = build_portfolio_tracker(_book(), _ranking(), 1_000_000, prices)
    by_symbol = out.set_index("Symbol")
    assert by_symbol.loc["AAA", "Previous Value (₹)"] == pytest.approx(5000.0)
    assert by_symbol.loc["AAA", "Day P&L (₹)"] == pytest.approx(250.0)
    assert by_symbol.loc["AAA", "Day P&L %"] == pytest.approx(5.0)
