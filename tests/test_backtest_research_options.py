"""Backtest-page research options (owner, 9 Oct 2026).

Score each window by Sharpe (the live system) or by its plain return; an
optional all-time-high gate beside the 52-week-high one; EMA period and
52-week distance from the page. The defaults must remain the live system to
the last trade (checked on the real 2010 history before merge: equity curve
and all 5,800 trades identical).
"""

import numpy as np
import pandas as pd
import pytest

from src.engine.backtester import _exit_reason, run_backtest
from src.engine.calendar_momentum import anchor_frame, period_sharpe_at

_RUN = run_backtest
while hasattr(_RUN, "__wrapped__"):
    _RUN = _RUN.__wrapped__


def _prices(n_days=700, n=40, seed=5):
    idx = pd.bdate_range("2022-01-03", periods=n_days)
    rng = np.random.default_rng(seed)
    drift = rng.normal(0.0004, 0.0006, n)
    vol = rng.uniform(0.008, 0.03, n)
    lr = rng.normal(drift, vol, (n_days, n))
    return pd.DataFrame(100 * np.exp(np.cumsum(lr, axis=0)), index=idx,
                        columns=[f"S{i:02d}" for i in range(n)])


def test_plain_return_is_the_same_window_without_the_volatility_division():
    prices = _prices()
    lr = np.log(prices / prices.shift(1))
    end = len(prices) - 30
    sharpe, s0 = period_sharpe_at(prices, lr, end, 6, prices_anchor=anchor_frame(prices))
    plain, s1 = period_sharpe_at(prices, lr, end, 6, prices_anchor=anchor_frame(prices), metric="return")
    assert s0 == s1
    expected = np.log(prices.iloc[end] / prices.iloc[s0])
    pd.testing.assert_series_equal(plain, expected, check_names=False)
    window = lr.iloc[s0 + 1 : end + 1]
    vol = window.std(ddof=0) * np.sqrt(window.notna().sum())
    pd.testing.assert_series_equal(sharpe, plain / vol, check_names=False)


def test_an_unknown_metric_is_refused():
    prices = _prices()
    with pytest.raises(ValueError):
        period_sharpe_at(prices, np.log(prices / prices.shift(1)), 400, 3, metric="sortino")


def _bt(**kw):
    return _RUN("t", _prices(), backtest_months=12, stateful_history=True, **kw)


def test_the_defaults_are_the_live_system():
    base = _bt()
    explicit = _bt(score_method="sharpe", ath_pct=None, ema_period=50, high_pct=0.80)
    pd.testing.assert_series_equal(base["equity_curve"], explicit["equity_curve"])
    pd.testing.assert_frame_equal(base["tradebook"], explicit["tradebook"])


def test_each_option_reaches_the_simulation():
    base = _bt()["equity_curve"]
    for kw in ({"score_method": "return"}, {"ath_pct": 0.97, "ath_min_years": 0},
               {"ema_period": 10}, {"high_pct": 0.97}):
        assert not _bt(**kw)["equity_curve"].equals(base), kw


@pytest.mark.parametrize("kw", [{"score_method": "momentum"}, {"ath_pct": 0.0}, {"ath_pct": 1.5}])
def test_invalid_options_are_refused(kw):
    with pytest.raises(ValueError):
        _bt(**kw)


def test_a_sale_on_the_ath_gate_says_so():
    s = pd.Series({"AAA": True})
    reason = _exit_reason("AAA", pd.Series(dtype=float), s, s, 50, 0.8, 30,
                          near_ath=pd.Series({"AAA": False}), ath_pct=0.8)
    assert reason == "Failed ATH Filter (< 80% of all-time high)"


# ── The page ─────────────────────────────────────────────────────────────────

def _view():
    return open("src/ui/views/backtest_view.py", encoding="utf-8").read()


def test_every_setting_sits_inside_the_apply_form():
    src = _view()
    form = src[src.index("def _settings_form("):src.index("def _backtest_body(")]
    body = form[form.index('with st.form("bt_settings"'):form.index("st.form_submit_button(")]
    for key in ("bt_top_n", "bt_keep_rank", "bt_rebal_days", "bt_weight_scheme", "bt_cost",
                "bt_ema_period", "bt_exit_ema", "bt_52w_off", "bt_exit_52w", "bt_ath_off",
                "bt_exit_ath", "bt_score", "btw_", "bt_hist_index", "bt_hist_months", "bt_hist_floor"):
        assert key in body, key
    tab = src[src.index("def _backtest_tab("):]
    assert "st.popover(" not in tab[:tab.index("run_backtest(")], "a setting outside the form reruns on every change"


def test_the_options_reach_the_backtest():
    src = _view()
    call = src[src.index("bt_res = run_backtest("):]
    call = call[:call.index("queued.empty()")]
    for arg in ("ema_period=ema_period", "high_pct=high_pct", "score_method=score_method", "ath_pct=ath_pct"):
        assert arg in call


# ── Separate rules for keeping a holding ─────────────────────────────────────

def test_keep_rules_equal_to_the_buy_rules_change_nothing():
    base = _bt()
    same = _bt(exit_ema_period=50, exit_high_pct=0.80)
    pd.testing.assert_series_equal(base["equity_curve"], same["equity_curve"])
    pd.testing.assert_frame_equal(base["tradebook"], same["tradebook"])


def test_looser_keep_rules_hold_names_longer():
    base = _bt(high_pct=0.95)
    loose = _bt(high_pct=0.95, exit_high_pct=0.70)
    assert not loose["equity_curve"].equals(base["equity_curve"])

    def count(res, word):
        return int(res["tradebook"]["Action"].str.contains(word).sum())

    # Fewer buys and sells, more holds: names are kept through dips the buy rule rejects.
    assert count(loose, "BUY") < count(base, "BUY")
    assert count(loose, "SELL") < count(base, "SELL")
    assert count(loose, "HOLD") > count(base, "HOLD")


@pytest.mark.parametrize("kw", [{"exit_high_pct": 0.0}, {"exit_ath_pct": 1.2}, {"exit_ema_period": 1}])
def test_invalid_keep_rules_are_refused(kw):
    with pytest.raises(ValueError):
        _bt(**kw)


def test_any_number_of_holdings_and_any_keep_rank():
    """Owner, 9 Oct: e.g. 23 holdings kept while ranked within 77."""
    res = _bt(top_n=23, buffer_n=77)
    assert res is not None and not res["equity_curve"].empty


def test_the_page_passes_the_keep_rules_and_rank_to_the_backtest():
    src = _view()
    call = src[src.index("bt_res = run_backtest("):src.index("queued.empty()")]
    assert "**exit_rules," in call and "buffer_n=keep_rank" in call


# ── The ATH rule waits for enough history on file (owner, 9 Oct 2026) ───────

def test_an_unreachable_minimum_history_is_the_same_as_no_ath_rule():
    """Every fixture stock trades from the file's first day, so with a 30-year
    minimum none of them is ever held to the rule."""
    none = _bt()
    waiting = _bt(ath_pct=0.99, ath_min_years=30)
    pd.testing.assert_series_equal(none["equity_curve"], waiting["equity_curve"])
    pd.testing.assert_frame_equal(none["tradebook"], waiting["tradebook"])


def test_with_no_minimum_the_ath_rule_applies():
    assert not _bt(ath_pct=0.99, ath_min_years=0)["equity_curve"].equals(_bt()["equity_curve"])


def test_which_stocks_the_ath_rule_applies_to():
    from src.engine.backtester import ath_history, ath_trusted

    idx = pd.bdate_range("2008-01-01", "2014-12-31")
    prices = pd.DataFrame(1.0, index=idx, columns=["OLD", "NEW"])
    prices.loc[:"2011-06-30", "NEW"] = np.nan          # lists mid-2011: whole history on file
    hist = ath_history(prices)
    early = ath_trusted(hist, "2010-06-30", 3)
    assert not early["OLD"], "priced from the file's first day: its real peak may be earlier"
    assert ath_trusted(hist, "2011-07-01", 3)["NEW"], "listed inside the file: trusted at once"
    assert ath_trusted(hist, "2011-01-03", 3)["OLD"], "three years on file"
    assert ath_trusted(hist, "2008-01-02", 0)["OLD"], "no minimum"


def test_the_minimum_history_is_validated():
    with pytest.raises(ValueError):
        _bt(ath_pct=0.8, ath_min_years=-1)


def test_the_page_labels_the_ath_with_where_the_history_starts():
    src = _view()
    assert "ATH since <b>{pd.Timestamp(adj_close.index[0]):%b %Y}</b>" in src
    assert 'key="bt_ath_years"' in src and "ath_min_years=ath_min_years" in src
