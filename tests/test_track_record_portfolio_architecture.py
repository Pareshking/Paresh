from __future__ import annotations

import numpy as np
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
        "src.engine.model_record.record_run",
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
        "src.engine.model_record.record_run",
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


def test_portfolio_tracker_sizes_shares_from_original_entry_weight_after_rebalance():
    book = _book()
    # AAA entered at 10% of account equity; a later rebalance cut its target to
    # 5%. The held share count must not be retroactively cut in half.
    book.loc[book["Symbol"] == "AAA", "Entry Weight %"] = 10.0
    book.loc[book["Symbol"] == "AAA", "Weight %"] = 5.0

    out = build_portfolio_tracker(book, _ranking(), 1_000_000)
    aaa = out.set_index("Symbol").loc["AAA"]

    assert aaa["Entry Weight %"] == pytest.approx(10.0)
    assert aaa["Target Weight %"] == pytest.approx(5.0)
    assert aaa["Shares"] == 1000
    assert aaa["Invested Value (₹)"] == pytest.approx(100_000.0)
    assert aaa["Current Value (₹)"] == pytest.approx(120_000.0)
    assert aaa["P&L (₹)"] == pytest.approx(20_000.0)


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
    from src.engine import model_record

    captured = {}

    monkeypatch.setattr(model_record, "load_events", lambda: [])
    monkeypatch.setattr(model_record, "price_fingerprint", lambda _prices: "fp")
    monkeypatch.setattr(model_record, "membership_for", lambda _system: None)

    def fake_run_backtest(*args, **kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(model_record, "run_backtest", fake_run_backtest)

    dates = pd.bdate_range("2025-01-01", "2026-09-30")
    prices = pd.DataFrame({"AAA": range(len(dates))}, index=dates)

    model_record.record_run(prices, None, "750")

    assert captured["stateful_history"] is True
    assert captured["history_start"] == pd.Timestamp("2026-01-01")




def test_record_run_defensively_filters_pre_inception_history(monkeypatch):
    from src.engine import model_record

    monkeypatch.setattr(model_record, "load_events", lambda: [])
    monkeypatch.setattr(model_record, "price_fingerprint", lambda _prices: "fp")
    monkeypatch.setattr(model_record, "membership_for", lambda _system: None)

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

    monkeypatch.setattr(model_record, "run_backtest", fake_run_backtest)

    dates = pd.bdate_range("2025-01-01", "2026-09-30")
    prices = pd.DataFrame({"AAA": range(len(dates))}, index=dates)

    result = model_record.record_run(prices, None, "750")

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


def test_live_month_reaches_rebalances_and_trades():
    from src.engine.model_record import with_live_month

    fill, as_of = pd.Timestamp("2026-09-01"), pd.Timestamp("2026-09-30")
    res = {
        "tradebook": pd.DataFrame([{"Period": "p", "Period Start": pd.Timestamp("2026-08-03"),
                                    "Action": "x", "Symbol": "OLD"}]),
        "closed_trades": pd.DataFrame([
            {"Symbol": "A", "Exit Date": "03 Aug 2026", "Status": "Closed"},
            {"Symbol": "B", "Exit Date": "Not exited (mark 31 Aug 2026)", "Status": "Open"},
        ]),
        "month_changes": pd.DataFrame([
            {"Action": "🔴 SOLD", "Symbol": "A2", "Entry Date": pd.Timestamp("2026-03-02"),
             "Entry Price": 10.0, "Exit Price": 12.0, "Return %": 0.2, "Weight %": 0.0, "Reason": "r"},
            {"Action": "🟢 BOUGHT", "Symbol": "N", "Entry Date": fill, "Entry Price": 5.0,
             "Exit Price": 6.0, "Return %": 0.2, "Weight %": 5.0, "Reason": "new"},
        ]),
        "live_book": pd.DataFrame([{"Symbol": "N", "Entry Date": fill, "Entry Price": 5.0,
                                    "Price Now": 6.0, "Return %": 0.2, "Holding (Days)": 29}]),
        "live_meta": {"fill_date": fill, "as_of": as_of},
    }
    out = with_live_month(res)
    assert set(out["tradebook"]["Symbol"]) == {"OLD", "A2", "N"}
    assert out["tradebook"]["Period Start"].max() == fill
    ct = out["closed_trades"]
    assert ct.loc[ct["Status"] == "Open", "Symbol"].tolist() == ["N"]
    assert "A2" in ct.loc[ct["Status"] == "Closed", "Symbol"].tolist()


def test_open_trades_survive_the_stateful_window_filter():
    import numpy as np

    from src.engine.backtester import run_backtest

    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2023-06-01", periods=800)
    px = pd.DataFrame(
        {f"S{i}": 100 * np.exp(np.cumsum(rng.normal(0.001, 0.018, 800))) for i in range(60)},
        index=dates,
    )
    res = run_backtest(
        "open_trades_regression", px, top_n=20, backtest_months=6,
        stateful_history=True, history_start=dates[-1].replace(day=1) - pd.DateOffset(months=6),
    )
    closed = res["closed_trades"]
    assert not closed.empty
    assert (closed["Status"] == "Open").any()


def test_portfolio_performance_overview_uses_canonical_account_return_series():
    record = {"closed_trades": pd.DataFrame(), "tradebook": pd.DataFrame()}
    ledger = {
        "months": {
            "2026-01": {"strategy": 0.10, "benchmark": 0.02, "origin": "recorded"},
        }
    }
    live_meta = {
        "mtd_period": "2026-02",
        "strategy_mtd": 0.05,
        "benchmark_mtd": 0.01,
        "as_of": pd.Timestamp("2026-02-27"),
    }

    out = build_portfolio_history(
        record, 1_000_000, ledger, live_meta, today=pd.Timestamp("2026-03-01")
    )

    # Same frozen month + live month series used by Track Record; no 100x
    # fraction/percentage conversion and no substitution of current-book P&L.
    assert out["equity"].iloc[-1] == pytest.approx(1_155_000)
    assert out["benchmark"].iloc[-1] == pytest.approx(1_030_200)
    assert out["strategy_total_return"] == pytest.approx(0.155)
    assert out["benchmark_total_return"] == pytest.approx(0.0302)
    assert out["mtd_period"] == "2026-02"
    assert out["mtd_state"] == "closed"
    feb = out["monthly_grid"].set_index("Period").loc["2026-02"]
    assert feb["Strategy Net"] == pytest.approx(0.05)
    assert feb["Benchmark"] == pytest.approx(0.01)
    assert feb["Origin"] == "Closed, awaiting freeze"


def test_portfolio_total_return_matches_track_record_summary_with_same_mtd():
    from src.engine.track_record import summary_stats

    record = {"closed_trades": pd.DataFrame(), "tradebook": pd.DataFrame()}
    ledger = {
        "months": {
            "2026-01": {"strategy": -0.02, "benchmark": 0.01, "origin": "recorded"},
            "2026-02": {"strategy": 0.04, "benchmark": -0.03, "origin": "recorded"},
        }
    }
    live_meta = {
        "mtd_period": "2026-03",
        "strategy_mtd": 0.03,
        "benchmark_mtd": 0.02,
        "as_of": pd.Timestamp("2026-03-31"),
    }
    out = build_portfolio_history(
        record, 2_000_000, ledger, live_meta, today=pd.Timestamp("2026-03-31")
    )
    stats = summary_stats(
        ledger,
        mtd={
            "period": pd.Period("2026-03", freq="M"),
            "strategy": 0.03,
            "benchmark": 0.02,
            "as_of": pd.Timestamp("2026-03-31"),
        },
    )

    assert out["strategy_total_return"] == pytest.approx(stats["total_return"])
    assert out["benchmark_total_return"] == pytest.approx(stats["bench_return"])


def test_portfolio_positions_size_from_equity_before_each_fill():
    book = pd.DataFrame([
        {
            "Symbol": "AAA", "Industry": "Alpha",
            "Entry Date": pd.Timestamp("2026-02-02"), "Entry Price": 100.0,
            "Price Now": 120.0, "Return %": 0.20, "MTD %": 0.10,
            "Holding (Days)": 26, "Weight %": 10.0,
            "Rank at Entry": 1, "Rank at Rebalance": 1,
        },
        {
            "Symbol": "BBB", "Industry": "Beta",
            "Entry Date": pd.Timestamp("2026-03-02"), "Entry Price": 200.0,
            "Price Now": 220.0, "Return %": 0.10, "MTD %": 0.05,
            "Holding (Days)": 1, "Weight %": 10.0,
            "Rank at Entry": 2, "Rank at Rebalance": 2,
        },
    ])
    book.attrs["as_of"] = pd.Timestamp("2026-03-02")
    equity = pd.Series(
        [2_000_000.0, 2_100_000.0],
        index=pd.to_datetime(["2026-01-31", "2026-02-28"]),
    )

    out = build_portfolio_tracker(
        book, pd.DataFrame(), 2_000_000.0, equity_curve=equity
    ).set_index("Symbol")

    # February's buy uses January-end account equity; March's buy uses
    # February-end equity, rather than reusing the original ₹20 lakh base.
    assert out.loc["AAA", "Capital at Entry (₹)"] == pytest.approx(2_000_000)
    assert out.loc["AAA", "Shares"] == 2_000
    assert out.loc["BBB", "Capital at Entry (₹)"] == pytest.approx(2_100_000)
    assert out.loc["BBB", "Shares"] == 1_050
    assert out.loc["AAA", "Weight %"] == pytest.approx(240_000 / 2_100_000 * 100)
    assert out.loc["BBB", "Weight %"] == pytest.approx(231_000 / 2_100_000 * 100)


def test_portfolio_shares_follow_the_latest_rebalance_so_holdings_never_exceed_the_account():
    book = _book()
    book.attrs["fill_date"] = "2026-03-02"
    syms = book["Symbol"].tolist()
    idx = pd.to_datetime(["2026-03-02", "2026-03-03"])
    prices = pd.DataFrame({s: [100.0, 300.0] for s in syms}, index=idx)
    equity = pd.Series([1_000_000.0], index=[pd.Timestamp("2026-02-28")])
    out = build_portfolio_tracker(book, _ranking(), 1_000_000, prices, equity_curve=equity)
    expect = (1_000_000 * out["Target Weight %"] / 100.0 / 100.0).apply(np.floor)
    assert out["Shares"].tolist() == expect.astype(int).tolist()
