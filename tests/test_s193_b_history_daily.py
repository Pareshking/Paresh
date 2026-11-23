"""S193 B: readings a year or more back come from a daily frame, windows in sessions or days.

Owner, 23 Nov 2026 ("Fix, I am with your recommendation"). Each test is a small
synthetic version of a case the audit found (docs/archive/S193_ITEM_B_2026-11-23.md
section 3): on a store that is weekly before mid-2025, the 200D EMA share a year
ago, "five sessions" of new highs, a stock's all-time high and its 50D EMA, and
the swap evidence read wrong; on the daily frame they read what NSE's daily
closes say.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.engine import market_questions as mq
from src.engine import swap_evidence as sw
from src.loaders import price_source as ps
from src.loaders.ath_loader import build_ath_snapshot

ROOT = Path(__file__).resolve().parents[1]


def _truth(n_stocks: int = 120, sessions: int = 700, seed: int = 7) -> pd.DataFrame:
    """Daily closes: a random walk per stock, the NSE long file's stand-in."""
    idx = pd.bdate_range("2023-01-06", periods=sessions)   # a Friday: the store starts with the file
    rng = np.random.default_rng(seed)
    steps = rng.normal(0.0004, 0.02, size=(sessions, n_stocks))
    return pd.DataFrame(100 * np.exp(np.cumsum(steps, axis=0)), index=idx,
                        columns=[f"S{i:03d}" for i in range(n_stocks)])


def _sparse(truth: pd.DataFrame, daily_from: int) -> pd.DataFrame:
    """Screener's shape: Fridays only before `daily_from`, every session after."""
    idx = truth.index
    keep = (np.arange(len(idx)) >= daily_from) | (idx.day_of_week == 4)
    return truth[keep]


# ── The daily frame ─────────────────────────────────────────────────────────

def test_the_weekly_stretch_is_filled_from_the_long_file_and_every_own_close_kept():
    truth = _truth(5, 400)
    store = _sparse(truth, 300)
    out, report = ps.daily_history(store, truth)
    assert report["cells"] > 0
    pd.testing.assert_index_equal(out.index, truth.index)
    # Same levels on both sides here, so the ratio fill gives NSE's closes exactly.
    np.testing.assert_allclose(out.to_numpy(), truth.to_numpy(), rtol=1e-12)
    # Every close the store had is the store's own.
    assert (out.loc[store.index, store.columns] == store).all().all()


def test_no_long_file_leaves_the_frame_as_it_is():
    store = _sparse(_truth(3, 300), 200)
    out, report = ps.daily_history(store, None)
    assert out is store and report["cells"] == 0


def test_the_200d_ema_share_a_year_ago_is_read_on_daily_closes():
    # The Market page's "the share above the 200D EMA went from 54% to 45%": on the
    # sparse store a 200-row EMA a year back spans about four years of Fridays.
    truth = _truth()
    store = _sparse(truth, 560)
    when = truth.index[480]          # in the weekly stretch, as a year ago is
    on_truth = mq._share_above_ema(truth, 200).loc[when]
    on_store = mq._share_above_ema(store, 200).loc[when]
    daily, _ = ps.daily_history(store, truth)
    assert mq._share_above_ema(daily, 200).loc[when] == pytest.approx(on_truth)
    assert on_store != pytest.approx(on_truth)          # the case the audit found


def test_net_new_highs_count_seven_days_not_five_rows():
    # "A new 52-week high in the last five sessions": five rows of a weekly
    # stretch are five weeks. A high three Fridays back is not this week's.
    idx = pd.date_range("2023-01-06", periods=80, freq="W-FRI")
    rising = np.linspace(100, 200, 80)
    prices = pd.DataFrame({f"S{i}": rising.copy() for i in range(10)}, index=idx)
    prices.iloc[-3:, :] = prices.iloc[-4, 0] * 0.95      # the high was the fourth-last Friday
    nnh = mq._net_new_highs(prices)
    assert nnh.iloc[-4] == pytest.approx(100.0)
    assert nnh.iloc[-1] == pytest.approx(0.0)               # five rows would still count it: +100


def test_net_new_highs_on_a_daily_frame_cover_the_week():
    idx = pd.bdate_range("2024-01-01", periods=400)
    base = pd.Series(np.linspace(100, 200, 400), index=idx)
    prices = pd.DataFrame({f"S{i}": base for i in range(10)})
    prices.iloc[-4:, :] = 150.0                              # last high on the fifth-last session (a Monday)
    nnh = mq._net_new_highs(prices)
    assert nnh.iloc[-1] == pytest.approx(100.0)               # within seven days of the last session
    prices.iloc[-6:, :] = 150.0                              # last high eight days back
    assert mq._net_new_highs(prices).iloc[-1] == pytest.approx(0.0)


# ── The stock page ──────────────────────────────────────────────────────────

def _store_of(close: pd.DataFrame) -> pd.DataFrame:
    frame = close.copy()
    frame.columns = pd.MultiIndex.from_tuples([(c, "Close") for c in close.columns])
    return frame


def test_the_all_time_high_between_two_weekly_closes_is_found():
    # RELIANCE: Rs 1,597 on Fri 12 Jul 2024 from the weekly closes; NSE's daily
    # high is Rs 1,600.90 on Mon 8 Jul.
    idx = pd.bdate_range("2024-06-03", "2025-09-30")
    nse = pd.DataFrame({"RELIANCE": np.linspace(1300.0, 1400.0, len(idx))}, index=idx)
    nse.loc["2024-07-08", "RELIANCE"] = 1600.90
    nse.loc["2024-07-12", "RELIANCE"] = 1596.73
    store = _store_of(_sparse(nse, len(idx) - 60))
    weekly = build_ath_snapshot(["RELIANCE"], store).set_index("Symbol")
    daily = build_ath_snapshot(["RELIANCE"], store, nse).set_index("Symbol")
    assert weekly.loc["RELIANCE", "ATHDate"] == "2024-07-12"
    assert daily.loc["RELIANCE", "ATH"] == pytest.approx(1600.90)
    assert daily.loc["RELIANCE", "ATHDate"] == "2024-07-08"


def test_the_chart_ema_reads_daily_closes(monkeypatch):
    from src.ui import daily_history

    truth = _truth(1, 500)
    sym = truth.columns[0]
    ranking = _sparse(truth, 400)
    monkeypatch.setattr(daily_history, "_long_column", lambda s: truth[[s]].astype("float32"))
    close = daily_history.stock_close(sym, ranking)
    when = truth.index[350]
    want = truth[sym].ewm(span=50, min_periods=30).mean().loc[when]
    got = close.ewm(span=50, min_periods=30).mean().loc[when]
    assert got == pytest.approx(want, rel=1e-6)
    weekly = ranking[sym].ewm(span=50, min_periods=30).mean().loc[when]
    assert weekly != pytest.approx(want, rel=1e-3)


def test_the_chart_falls_back_to_the_ranking_frame_without_the_long_file(monkeypatch):
    from src.ui import daily_history

    ranking = _sparse(_truth(1, 300), 200)
    monkeypatch.setattr(daily_history, "_long_column", lambda s: None)
    close = daily_history.stock_close(ranking.columns[0], ranking)
    pd.testing.assert_series_equal(close, ranking[ranking.columns[0]].dropna())


# ── Actions: the swap evidence ──────────────────────────────────────────────

def test_a_traded_name_without_a_price_is_named_not_dropped():
    idx = pd.bdate_range("2026-01-01", periods=120)
    px = pd.DataFrame({"A": 100 * 1.002 ** np.arange(120)}, index=idx)
    market = pd.Series(100.0, index=idx)
    ev = sw.evidence([("A", idx[0]), ("JBCHEPHARM", idx[5])], [("A", idx[30]), ("JBCHEPHARM", idx[40])], px, market)
    assert ev.buys == 1 and ev.sold == 1
    assert ev.unpriced == ("JBCHEPHARM",)


def test_a_name_that_left_the_list_is_measured_from_the_fallback_prices():
    idx = pd.bdate_range("2026-01-01", periods=120)
    px = pd.DataFrame({"A": 100 * 1.002 ** np.arange(120)}, index=idx)
    former = pd.DataFrame({"JBCHEPHARM": 100 * 1.001 ** np.arange(120)}, index=idx)
    market = pd.Series(100.0, index=idx)
    ev = sw.evidence([("A", idx[0]), ("JBCHEPHARM", idx[5])], [("A", idx[30]), ("JBCHEPHARM", idx[40])],
                     px, market, former)
    assert ev.buys == 2 and ev.sold == 2 and ev.unpriced == ()
    assert ev.buy_1m == pytest.approx(((1.002 ** 21 - 1) + (1.001 ** 21 - 1)) / 2 * 100)


def test_the_market_is_read_on_the_stocks_own_window_dates():
    # The index file lacks a session the stock has (1 Feb 2026, a Sunday budget
    # session): counted on each side's own sessions the two windows ended on
    # different dates, here a day apart.
    idx = pd.bdate_range("2026-01-05", periods=80).union([pd.Timestamp("2026-02-01")])
    stock = pd.Series(100.0, index=idx)
    stock[stock.index >= "2026-02-01"] = 110.0
    mkt_idx = idx.drop(pd.Timestamp("2026-02-01"))
    market = pd.Series(np.arange(len(mkt_idx), dtype=float) + 100, index=mkt_idx)
    start = idx[0]
    end = stock.index[21]                                    # the stock's 21st session after the start
    want = (110 / 100 - 1) - (market.loc[:end].iloc[-1] / market.loc[start] - 1)
    assert sw._ahead(stock, market, start, 21) == pytest.approx(want)


# ── Which page reads which frame ────────────────────────────────────────────

def test_market_and_sectors_read_the_daily_history():
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    for page in ("_page_market", "_page_sectors"):
        body = text.split(f"def {page}() -> None:")[1].split("\ndef ")[0]
        assert "history_prices=_daily_history()" in body, page
        assert "deep_adj_close" not in body, page
