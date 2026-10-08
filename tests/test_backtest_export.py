"""The backtest download: the rules a run followed and every trade it made.

The two files must describe the SAME run, so the trades are checked against the
engine's independent records (the tradebook, the price frame) and the rules
against the settings the run was given.
"""

import io
import re
import zipfile

import numpy as np
import pandas as pd
import pytest

from src.engine.backtest_export import (
    COLUMN_NOTES,
    TRADE_COLUMNS,
    RunSpec,
    export_zip,
    rules_table,
    trades_table,
)
from src.engine.backtester import run_backtest

SECTORS = {f"S{i}": ("Banks" if i < 4 else "IT" if i < 8 else "Auto") for i in range(12)}


def _prices(seed: int = 11, n: int = 900, cols: int = 12, end: str = "2026-08-18"):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=end, periods=n)
    return pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0.0006, 0.02, (n, cols)), axis=0)),
        index=idx, columns=[f"S{i}" for i in range(cols)],
    )


def _run(tag="exp", **kw):
    px = _prices()
    args = dict(top_n=4, rebal_freq=21, ema_period=20, high_pct=0.0, stock_cap=0.4,
                sector_cap=0.6, cost_bps=30.0, buffer_n=6, sector_map=SECTORS)
    args.update(kw)
    return px, run_backtest(tag, px, **args)


def _spec(res, **kw):
    eq = res["equity_curve"]
    args = dict(mode="Live system", universe="Test index", benchmark="Nifty 500",
                first_fill=eq.index[0], last_session=eq.index[-1], top_n=4, rebal_freq=21,
                buffer_n=6, weight_method="Equal Weight", cost_bps=30.0, stock_cap=0.4,
                sector_cap=0.6, weights=(0.1, 0.3, 0.3, 0.2, 0.1), liquidity_floor_cr=0.0,
                price_basis="synthetic closes", has_industry_map=True, stats=res["stats"],
                ema_period=20, high_pct=0.0, generated="2026-10-08 12:00")
    args.update(kw)
    return RunSpec(**args)


def test_one_row_per_position_in_entry_order_with_the_agreed_columns():
    px, res = _run()
    t = trades_table(res["closed_trades"])
    assert list(t.columns) == TRADE_COLUMNS
    assert len(t) == len(res["closed_trades"])
    assert t["Trade #"].tolist() == list(range(1, len(t) + 1))
    assert t["Entry date"].is_monotonic_increasing
    assert set(t["Status"]) <= {"Closed", "Open"}


def test_prices_dates_and_returns_agree_with_the_price_frame():
    px, res = _run()
    t = trades_table(res["closed_trades"])
    for _, r in t.iterrows():
        entry = px.loc[r["Entry date"], r["Symbol"]]
        assert r["Entry price"] == pytest.approx(entry, abs=1e-3)
        end_date, end_price = ((r["Mark date"], r["Mark price"]) if r["Status"] == "Open"
                               else (r["Exit date"], r["Exit price"]))
        assert end_price == pytest.approx(px.loc[end_date, r["Symbol"]], abs=1e-3)
        assert r["Price return %"] == pytest.approx((end_price / entry - 1) * 100, abs=0.011)
        assert r["Holding days"] == (pd.Timestamp(end_date) - pd.Timestamp(r["Entry date"])).days


def test_the_fill_is_the_session_after_the_signal_and_open_trades_have_no_exit():
    px, res = _run()
    t = trades_table(res["closed_trades"])
    sessions = list(px.index.strftime("%Y-%m-%d"))
    for _, r in t.iterrows():
        assert sessions.index(r["Entry date"]) == sessions.index(r["Entry signal date"]) + 1
        if r["Status"] == "Closed":
            assert sessions.index(r["Exit date"]) == sessions.index(r["Exit signal date"]) + 1
            assert r["Mark date"] == "" and pd.isna(r["Mark price"])
        else:
            assert r["Exit date"] == "" and pd.isna(r["Exit price"]) and r["Mark date"] != ""
    assert (t["Status"] == "Open").any() and (t["Status"] == "Closed").any()


def test_entry_rank_and_weight_match_the_tradebook_the_engine_kept_separately():
    px, res = _run()
    t = trades_table(res["closed_trades"])
    buys = res["tradebook"][res["tradebook"]["Action"].str.contains("BUY")]
    assert len(buys) == len(t)
    for _, r in t.iterrows():
        b = buys[(buys["Symbol"] == r["Symbol"])
                 & (buys["Period Start"].dt.strftime("%Y-%m-%d") == r["Entry date"])]
        assert len(b) == 1
        rank = int(re.search(r"Rank #(\d+)", b.iloc[0]["Reason / Signal"]).group(1))
        assert int(r["Entry rank"]) == rank
        assert r["Entry weight %"] == pytest.approx(b.iloc[0]["Weight %"], abs=1e-3)
    assert set(t["Sector"]) <= set(SECTORS.values())


def test_every_exit_reason_is_one_the_rules_file_explains():
    _px, res = _run(high_pct=0.8, ema_period=20)
    t = trades_table(res["closed_trades"])
    rules = rules_table(_spec(res, high_pct=0.8), t)
    explained = [r.split(": ", 1)[1] for r in rules.loc[rules.Section == "Exit rules", "Item"]
                 if r.startswith("Reason: ")]
    reasons = t.loc[t.Status == "Closed", "Reason for exit"]
    assert len(reasons)
    for text in reasons:
        assert any(text.startswith(k) for k in explained), (text, explained)
    # an exit reason the engine gains tomorrow must be added to the rules file
    open_reason = t.loc[t.Status == "Open", "Reason for exit"].iloc[0]
    assert open_reason == "Still held at window close"


def test_rules_state_the_settings_the_run_was_given_not_defaults():
    _px, res = _run()
    t = trades_table(res["closed_trades"])
    r = rules_table(_spec(res, top_n=4, buffer_n=6, cost_bps=30.0, ema_period=20, high_pct=0.0), t)
    flat = {(a, b): c for a, b, c, _ in r.itertuples(index=False)}
    assert flat[("Entry rules", "2. Trend filter")] == "Close above its 20-session EMA"
    assert "0%" in flat[("Entry rules", "3. 52-week-high filter")]
    assert flat[("Entry rules", "6. Select")] == "Top 4 by rank"
    assert flat[("Entry rules", "Buffer zone")].startswith("Top 6")
    assert flat[("Costs", "Trading cost")] == "30 bps per unit of turnover"
    assert flat[("Run", "Trades in trades file")] == str(len(t))
    assert flat[("Run", "First fill date")] == t["Entry date"].min()
    assert "1M 10%" in r.loc[r.Item == "5. Rank", "Note"].iloc[0]


def test_membership_is_described_as_the_run_actually_used_it():
    _px, res = _run()
    t = trades_table(res["closed_trades"])
    for pit, cur, expect in ((12, 0, "point in time"), (5, 7, "where on record"), (0, 12, "today's list")):
        spec = _spec(res, stats={**res["stats"], "pit_periods": pit, "current_universe_periods": cur})
        rule = rules_table(spec, t)
        value = rule.loc[rule.Item == "1. In the index on T", "Value"].iloc[0]
        assert expect in value, (pit, cur, value)


def test_a_run_with_no_industry_map_and_a_liquidity_floor_says_so():
    _px, res = _run(sector_map=None)
    t = trades_table(res["closed_trades"])
    r = rules_table(_spec(res, has_industry_map=False, liquidity_floor_cr=5.0), t)
    items = r["Item"].tolist()
    assert "Industry cap on names" not in items
    assert r.loc[r.Item == "Industry cap", "Value"].iloc[0] == "Not applied"
    assert "Rs 5 Cr" in r.loc[r.Item == "4. Liquidity floor", "Value"].iloc[0]


def test_the_zip_holds_two_csv_files_that_read_back_in_excel_encoding():
    _px, res = _run()
    t = trades_table(res["closed_trades"])
    r = rules_table(_spec(res), t)
    z = zipfile.ZipFile(io.BytesIO(export_zip(r, t)))
    assert sorted(z.namelist()) == ["backtest_rules.csv", "backtest_trades.csv"]
    raw = z.read("backtest_trades.csv")
    assert raw.startswith(b"\xef\xbb\xbf")
    back = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
    assert list(back.columns) == TRADE_COLUMNS and len(back) == len(t)
    rules_back = pd.read_csv(io.BytesIO(z.read("backtest_rules.csv")), encoding="utf-8-sig")
    assert list(rules_back.columns) == ["Section", "Item", "Value", "Note"]
    documented = rules_back.loc[rules_back.Section == "Columns in the trades file", "Item"].tolist()
    assert documented == TRADE_COLUMNS == list(COLUMN_NOTES)


def test_no_trades_still_gives_the_rules_and_an_empty_trades_file():
    _px, res = _run()
    empty = trades_table(pd.DataFrame())
    assert list(empty.columns) == TRADE_COLUMNS and empty.empty
    r = rules_table(_spec(res), empty)
    assert r.loc[r.Item == "Trades in trades file", "Value"].iloc[0] == "0"
    z = zipfile.ZipFile(io.BytesIO(export_zip(r, empty)))
    assert len(pd.read_csv(io.BytesIO(z.read("backtest_trades.csv")), encoding="utf-8-sig")) == 0
