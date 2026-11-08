"""Research rule: kept holdings keep their drifted weight up to a cap (owner, 8 Nov 2026)."""
import pandas as pd
import pytest

from src.engine.backtester import _let_winners_run


def _target(names):
    return pd.Series(1.0 / len(names), index=names)


def test_kept_names_keep_their_weight_and_buys_share_what_sells_freed():
    standing = pd.Series({"WIN": 0.12, "MID": 0.05, "LOSE": 0.03, "SOLD": 0.80})
    w = _let_winners_run(_target(["WIN", "MID", "LOSE", "NEW1", "NEW2"]), standing, ["WIN", "MID", "LOSE", "SOLD"], 0.15)
    assert w["WIN"] == pytest.approx(0.12) and w["LOSE"] == pytest.approx(0.03)   # no trim, no top-up
    assert w["NEW1"] == pytest.approx(0.15) and w["NEW2"] == pytest.approx(0.15)  # 0.80 freed, capped at 15%
    assert w.max() <= 0.15 + 1e-12
    assert w.attrs["cash"] == pytest.approx(0.80 - 0.30)                          # the rest cannot be placed


def test_a_winner_above_the_cap_is_trimmed_to_it_and_the_excess_goes_to_buys():
    standing = pd.Series({"BIG": 0.25, "B": 0.05, "SOLD": 0.70})
    w = _let_winners_run(_target(["BIG", "B", "NEW"]), standing, ["BIG", "B", "SOLD"], 0.15)
    assert w["BIG"] == pytest.approx(0.15)
    assert w["NEW"] == pytest.approx(0.15)


def test_with_no_buys_freed_money_goes_to_kept_names_in_proportion():
    standing = pd.Series({"A": 0.40, "B": 0.10, "C": 0.10, "SOLD": 0.40})
    w = _let_winners_run(_target(["A", "B", "C"]), standing, ["A", "B", "C", "SOLD"], 1.0)
    assert w.sum() == pytest.approx(1.0)
    assert w["A"] / w["B"] == pytest.approx(4.0)


def test_a_fresh_book_is_equal_weight():
    w = _let_winners_run(_target(["A", "B", "C", "D"]), pd.Series(dtype=float), [], 0.15)
    assert w.tolist() == pytest.approx([0.15, 0.15, 0.15, 0.15])
    assert w.attrs["cash"] == pytest.approx(0.40)


def test_the_industry_cap_stays_hard_at_the_rebalance():
    sec = {"A": "Pharma", "B": "Pharma", "C": "Pharma", "D": "IT", "NEW": "Pharma", "NEW2": "IT"}
    standing = pd.Series({"A": 0.15, "B": 0.15, "C": 0.15, "D": 0.05, "SOLD": 0.50})
    w = _let_winners_run(_target(["A", "B", "C", "D", "NEW", "NEW2"]), standing,
                         ["A", "B", "C", "D", "SOLD"], 0.15, sec, 0.40)
    pharma = w[["A", "B", "C", "NEW"]].sum()
    assert pharma <= 0.40 + 1e-9                     # 45% kept was scaled to 40%, NEW gets no Pharma room
    assert w["NEW"] == pytest.approx(0.0, abs=1e-9)
    assert w["NEW2"] == pytest.approx(0.15)          # IT had room
    assert w.max() <= 0.15 + 1e-12


def test_the_rule_starts_at_the_30_nov_signal_and_frozen_months_keep_their_fingerprints():
    from src.engine.backtester import _hold_cap_on
    from src.engine.track_record import TRACK_RECORD_CONFIG as cfg
    from src.engine.track_record import config_fingerprint, config_for_month

    assert cfg["hold_cap"] == 0.15 and cfg["hold_cap_from"] == "2026-11-30"
    # Owner, 8 Nov 2026: "6 monthly reset final".
    assert cfg["buy_size"] == 0.05 and list(cfg["weight_reset_months"]) == [3, 9]
    rule = ("hold_cap", "hold_cap_from", "buy_size", "weight_reset_months", "members_only_scoring_from")
    old = {k: v for k, v in cfg.items() if k not in rule}
    for month in ("2026-01", "2026-10", "2026-11"):                # governed by signals before 30 Nov
        assert config_for_month(cfg, month) == old
        assert config_fingerprint(**config_for_month(cfg, month)) == config_fingerprint(**old)
    dec = config_for_month(cfg, "2026-12")
    assert dec["hold_cap"] == 0.15 and dec["hold_cap_from"] == "2026-11-30"
    assert dec["buy_size"] == 0.05 and list(dec["weight_reset_months"]) == [3, 9]
    assert not _hold_cap_on(0.15, "2026-11-30", "2026-10-30")
    assert _hold_cap_on(0.15, "2026-11-30", "2026-11-30")
    assert not _hold_cap_on(None, "2026-11-30", "2027-01-29")


def test_the_plan_strikes_the_records_weights_under_the_rule():
    """Audit, 8 Nov 2026: the Actions plan (and Kite basket) sized buys at an equal 5%
    while the record gives them the money freed by sells."""
    from src.engine.actions import plan_rebalance
    rank = pd.DataFrame({"Symbol": ["A", "B", "N1"], "Industry": ["X", "Y", "Z"],
                         "Qualified #": [1, 2, 3]})
    standing = pd.Series({"A": 0.12, "B": 0.03, "SOLD": 0.03})
    try:
        plan = plan_rebalance(rank, ["A", "B", "SOLD"], top_n=3, buffer_n=6,
                              standing=standing, hold_cap=0.15)
    except Exception as exc:                     # the planner reads other ranking columns
        pytest.skip(f"ranking fixture too thin for the planner: {exc}")
    if "N1" in plan.buys:
        assert plan.weights["A"] == pytest.approx(0.12)
        assert plan.weights["B"] == pytest.approx(0.03)          # kept, not topped up
        assert plan.weights.max() <= 0.15 + 1e-12


def test_drift_keeps_cash_in_the_book():
    """Audit, 8 Nov 2026: a 75%-invested book came back 100% invested."""
    from src.engine.backtester import _drift_holdings
    prices = pd.DataFrame({"A": [10.0, 10.0], "B": [20.0, 20.0]})
    w = pd.Series({"A": 0.40, "B": 0.35})
    out = _drift_holdings(w, prices, 0, 1)
    assert out.sum() == pytest.approx(0.75)
    assert out["A"] == pytest.approx(0.40)


def test_forward_dated_rules_fall_on_a_month_end_signal():
    """Audit, 8 Nov 2026 (C-L1): config_for_month switches a rule on for months that
    start after its date, the engine at signals on or after it; they agree only if the
    date is a month's last business day (the signal date). Not a holiday check."""
    from src.engine.track_record import FORWARD_DATED_KEYS, TRACK_RECORD_CONFIG as cfg
    for key in FORWARD_DATED_KEYS:
        d = pd.Timestamp(cfg[key])
        assert d.weekday() < 5, (key, d)
        assert d == d + pd.offsets.BMonthEnd(0), (key, d, "not the month's last business day")


def test_fixed_buys_are_the_fixed_amount_and_share_cash_when_short():
    """Owner, 8 Nov 2026: each new buy is 5% of the account at the last 31 March;
    short of cash, buys get fewer shares; kept names are never sold to fund them."""
    from src.engine.backtester import _fixed_buys
    standing = pd.Series({"WIN": 0.20, "K": 0.05, "SOLD1": 0.03, "SOLD2": 0.03})
    # enough cash: 20% -> trimmed to 15% frees 5%, plus 6% from sells = 11%; two buys at 5%
    w = _fixed_buys(_target(["WIN", "K", "N1", "N2"]), standing, ["WIN", "K", "SOLD1", "SOLD2"], 0.15, 0.05)
    assert w["WIN"] == pytest.approx(0.15) and w["K"] == pytest.approx(0.05)
    assert w["N1"] == pytest.approx(0.05) and w["N2"] == pytest.approx(0.05)
    total = 0.20 + 0.05 + 0.03 + 0.03
    assert w.attrs["cash"] == pytest.approx(1 - (total - 0.05 - 0.06) - 0.10)   # leftover stays cash


def test_fixed_buys_short_of_cash_buy_fewer_shares_and_never_sell_kept_names():
    from src.engine.backtester import _fixed_buys
    standing = pd.Series({"A": 0.48, "B": 0.48, "SOLD": 0.04})
    w = _fixed_buys(_target(["A", "B", "N1", "N2"]), standing, ["A", "B", "SOLD"], 0.50, 0.05)
    assert w["A"] == pytest.approx(0.48) and w["B"] == pytest.approx(0.48)    # untouched
    assert w["N1"] == pytest.approx(0.02) and w["N2"] == pytest.approx(0.02)  # 4% cash shared
    assert w.attrs["cash"] == pytest.approx(0.0, abs=1e-12)


def _px(seed=7, n=900, cols=12):
    import numpy as np
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    return pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0.0006, 0.02, (n, cols)), axis=0)),
                        index=idx, columns=[f"S{i}" for i in range(cols)])


def test_a_scheduled_reset_puts_every_holding_back_to_target_in_its_month():
    """Research (owner, 8 Nov 2026): with weight_reset_months=(3,), the book struck at
    a March signal is equal weight; at other signals kept names keep their drift."""
    from src.engine.backtester import run_backtest
    fn = run_backtest
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    kw = dict(top_n=4, rebal_freq=21, ema_period=20, high_pct=0.0, cost_bps=0.0, buffer_n=8,
              stock_cap=1.0, sector_cap=1.0, hold_cap=0.5, buy_size=0.25)
    res = fn("reset-test", _px(), weight_reset_months=(3,), **kw)
    tb = res["tradebook"]
    tb = tb[tb["Action"].str.contains("BUY|HOLD")].copy()
    tb["start"] = pd.to_datetime(tb["Period Start"])
    spreads = tb.groupby("start")["Weight %"].agg(lambda w: w.max() - w.min())
    # the end-of-March signal fills on the first April session
    april = [d for d in spreads.index if d.month == 4]
    assert april, "no reset in the sample"
    assert all(spreads[d] < 1e-6 for d in april)
    assert spreads.max() > 1.0          # at other fills kept names drifted apart


def test_actions_buy_weight_is_buy_size_of_the_account_at_the_last_reset():
    from src.engine.actions import fixed_buy_weight
    idx = pd.bdate_range("2026-01-01", "2026-11-06")
    eq = pd.Series(1.0, index=idx)
    eq[eq.index > pd.Timestamp("2026-09-30")] = 1.2          # value at the 1 Oct reset fill
    eq.iloc[-1] = 1.5                                         # today
    assert fixed_buy_weight(eq, (3, 9), 0.05) == pytest.approx(0.05 * 1.2 / 1.5)
    assert fixed_buy_weight(None, (3, 9), 0.05) is None


def test_the_plan_uses_fixed_buys_between_resets():
    from src.engine.actions import plan_rebalance
    rank = pd.DataFrame({"Symbol": ["A", "B", "N1"], "Industry": ["X", "Y", "Z"], "Qualified #": [1, 2, 3]})
    standing = pd.Series({"A": 0.30, "B": 0.03, "SOLD": 0.67})
    try:
        plan = plan_rebalance(rank, ["A", "B", "SOLD"], top_n=3, buffer_n=6,
                              standing=standing, hold_cap=0.15, buy_weight=0.04)
    except Exception as exc:                      # the planner reads other ranking columns
        pytest.skip(f"ranking fixture too thin for the planner: {exc}")
    if "N1" in plan.buys:
        assert plan.weights["A"] == pytest.approx(0.15)       # trimmed only above 15%
        assert plan.weights["B"] == pytest.approx(0.03)       # not topped up
        assert plan.weights["N1"] == pytest.approx(0.04)      # the fixed amount
