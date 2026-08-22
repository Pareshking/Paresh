"""
Walk-forward historical backtesting engine with zero look-ahead bias and transaction cost drag.

Features:
  1. Zero Look-Ahead Execution (Rank at T close -> Trade at T+1)
  2. Transaction Cost & Slippage Drag Matrix (STT, Stamp Duty, Brokerage, Slippage)
  3. Rank Persistence Buffer Zones (Minimize turnover and transaction friction)
  4. Full Performance Attribution (CAGR, Sharpe, Sortino, Calmar, Max DD, Turnover)
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd
import streamlit as st

from src.core.config import MOMENTUM_WINDOWS

# MOMENTUM_WINDOWS are calendar months; warmup arithmetic needs trading sessions.
SESSIONS_PER_MONTH: int = 21


DEFAULT_BACKTEST_MONTHS: int = 6


def completed_month_window(
    dates: pd.DatetimeIndex, months: int = DEFAULT_BACKTEST_MONTHS
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """First and last day of the most recent `months` COMPLETED calendar months.

    The month in progress is excluded. Reporting a partial month beside full
    ones invites comparing a half-month return against six whole ones, and the
    partial month moves every day the market is open. On 18 Aug 2026 this spans
    1 Feb 2026 to 31 Jul 2026 -- August is still running.
    """
    if len(dates) == 0:
        raise ValueError("completed_month_window requires at least one date")
    if months <= 0:
        raise ValueError("months must be positive")
    current_month_start = pd.Timestamp(dates[-1]).normalize().replace(day=1)
    window_end = current_month_start - pd.Timedelta(days=1)
    window_start = current_month_start - pd.DateOffset(months=months)
    return window_start, window_end


def _calendar_period_sharpe(
    prices: pd.DataFrame,
    log_returns: pd.DataFrame,
    end_idx: int,
    months: int,
) -> tuple[pd.Series, int]:
    """V1 period-scale Sharpe using the same calendar-window rule as the screener."""
    dates = pd.DatetimeIndex(prices.index)
    target = pd.Timestamp(dates[end_idx]).normalize() - pd.DateOffset(months=months)
    start_idx = int(dates.searchsorted(target, side="left"))
    if start_idx >= end_idx:
        return pd.Series(np.nan, index=prices.columns), start_idx
    if target < pd.Timestamp(dates[0]).normalize():
        # The data does not reach back far enough to cover this window.
        # searchsorted clamps to 0, which would score a "12-month" return over
        # however few sessions exist. Report it unavailable instead; the
        # composite renormalises over the windows it actually has.
        return pd.Series(np.nan, index=prices.columns), start_idx

    p0 = prices.iloc[start_idx].clip(lower=0.01)
    p1 = prices.iloc[end_idx].clip(lower=0.01)
    log_return = np.log(p1 / p0)

    window_lr = log_returns.iloc[start_idx + 1 : end_idx + 1]
    n = window_lr.notna().sum()
    # Population SD (ddof=0), matching the canonical screener engine in
    # src/engine/calendar_momentum._calendar_period_metrics. Sample SD would
    # rescale each stock by sqrt(n/(n-1)), and because n differs per stock
    # that is not a uniform rescaling -- it makes the backtest fail to
    # reproduce the screener's Sharpe.
    daily_sd = window_lr.std(ddof=0)
    period_vol = daily_sd * np.sqrt(n.astype(float))
    sharpe = log_return / period_vol.replace(0, np.nan)
    sharpe[n <= 1] = np.nan
    return sharpe, start_idx


def _fill_price(prices: pd.DataFrame, symbol: str, idx: int) -> float:
    """The price a fill is struck at, or NaN when the tape has nothing to fill on.

    Yahoo holes sessions routinely, and `float(prices[s].iloc[idx])` on a holed
    session returned NaN, which the callers then fed into `if p_entry > 0` --
    False for NaN -- and logged the trade as a flat 0.00% round trip. A
    fabricated zero in a blotter is worse than a gap: it lands in the win rate,
    the profit factor and the average-loss figure as a real, uneventful trade.
    So carry the last real print forward (a stock that has not traded is filled
    at the last price it traded at), and if there is no earlier print at all,
    return NaN and let the trade report NaN.
    """
    if symbol not in prices.columns or idx >= len(prices):
        return float("nan")
    col = prices[symbol]
    value = col.iloc[idx]
    if pd.isna(value):
        prior = col.iloc[: idx + 1].dropna()
        if prior.empty:
            return float("nan")
        value = prior.iloc[-1]
    return float(value)


def _round_trip_return(entry: float, exit_: float) -> float:
    """Realised return, or NaN when either leg has no price. Never a fake 0%."""
    if not np.isfinite(entry) or not np.isfinite(exit_) or entry <= 0:
        return float("nan")
    return (exit_ / entry) - 1.0


def _composite_z_score(
    prices: pd.DataFrame,
    log_returns: pd.DataFrame,
    start_idx: int,
    windows: Sequence[int],
    weights: Sequence[float],
) -> pd.Series:
    """Canonical multi-window composite z-score used by every ranking method.

    A window that is unavailable for a stock must NOT become a synthetic zero
    z-score. A zero is the cross-sectional average, so filling it silently
    shrinks that stock's score toward the mean in proportion to the weight it
    is missing. Each stock is therefore renormalised by the weight actually
    available to it, matching apply_calendar_momentum() in
    src/engine/calendar_momentum.py.
    """
    composite = pd.Series(0.0, index=prices.columns)
    available_weight = pd.Series(0.0, index=prices.columns)
    for w_period, cw in zip(windows, weights):
        if cw <= 0:
            continue
        raw_mom, _ = _calendar_period_sharpe(
            prices, log_returns, start_idx, int(w_period)
        )
        sig_cs = float(raw_mom.std(ddof=0))
        if not np.isfinite(sig_cs) or sig_cs <= 0:
            # Degenerate or empty cross-section carries no information; it
            # contributes no score and no available weight.
            continue
        mu_cs = float(raw_mom.mean())
        z = ((raw_mom - mu_cs) / sig_cs).clip(-3.0, 3.0)
        composite += z.fillna(0.0) * cw
        available_weight += z.notna().astype(float) * cw
    return composite.div(available_weight.replace(0.0, np.nan))


@st.cache_data(show_spinner=False, ttl=3600)
def run_backtest(
    prices_hash: str,
    _adj_close: pd.DataFrame,
    top_n: int = 20,
    rebal_freq: int = 21,
    ema_period: int = 50,
    high_pct: float = 0.80,
    weight_method: str = "Equal Weight",
    config_weights: Sequence[float] = (0.10, 0.30, 0.30, 0.20, 0.10),
    stock_cap: float = 0.05,
    sector_cap: float = 0.30,
    sector_map: dict[str, str] | None = None,
    cost_bps: float = 30.0,
    buffer_n: int | None = None,
    _benchmark_close: pd.Series | None = None,
    backtest_months: int = DEFAULT_BACKTEST_MONTHS,
) -> dict[str, Any] | None:
    """
    Executes a walk-forward momentum backtest with zero look-ahead bias and friction modeling.
    """
    WINDOWS = MOMENTUM_WINDOWS
    prices = _adj_close.dropna(axis=1, how="all").copy()

    w_total = sum(config_weights)
    norm_w = [cw / w_total for cw in config_weights] if w_total > 0 else [0.2] * 5
    active_windows = [w for w, cw in zip(WINDOWS, norm_w) if cw > 0]
    # WINDOWS are calendar MONTHS (the scoring path passes them straight to
    # _calendar_period_sharpe). The warmup below is measured in SESSIONS, so
    # using the months verbatim gave max_lb = 12 -- a 12-month formation
    # window warmed up over 12 trading days. The first rebalance then landed
    # at session 32 and _calendar_period_sharpe, whose searchsorted clamps to
    # 0, silently scored "12-month momentum" from whatever little history
    # existed. Convert to sessions for the warmup; keep months for scoring.
    max_lb = (
        max(active_windows) if active_windows else max(WINDOWS)
    ) * SESSIONS_PER_MONTH

    min_needed = max_lb + ema_period + rebal_freq + 10
    if len(prices) < min_needed:
        return None

    daily_ret = prices.pct_change(fill_method=None)
    log_ret = np.log(prices / prices.shift(1).replace(0, np.nan))

    if _benchmark_close is None or _benchmark_close.empty:
        benchmark_ret = pd.Series(np.nan, index=prices.index, dtype=float)
    else:
        benchmark_series = pd.to_numeric(_benchmark_close, errors="coerce").reindex(prices.index)
        benchmark_ret = benchmark_series.pct_change(fill_method=None)

    ema = prices.ewm(span=ema_period).mean()
    high_52w = prices.rolling(252, min_periods=126).max()

    start_offset = max_lb + ema_period
    dates = pd.DatetimeIndex(prices.index)
    if rebal_freq == 21:
        # Monthly convention: signal/rebalance at the last available trading
        # session of each calendar month, then execute on the next session.
        eligible = dates[start_offset:]
        month_keys = eligible.to_period("M")
        idx_values = np.arange(start_offset, len(prices))
        last_by_month = pd.Series(idx_values, index=eligible).groupby(month_keys).last()
        rebal_dates = [int(i) for i in last_by_month.to_numpy() if int(i) < len(prices) - 2]
    else:
        rebal_dates = list(range(start_offset, len(prices) - 2, rebal_freq))

    # Restrict the REPORTED window to the last N completed calendar months. The
    # formation history before it is untouched -- a rebalance still scores on a
    # full 12-month lookback; we simply do not report periods outside the
    # window. Filter on the EXECUTION date (T+1), because a rebalance signalled
    # on the last session of January is the trade that holds through February.
    window_start, window_end = completed_month_window(dates, backtest_months)
    rebal_dates = [
        i for i in rebal_dates if window_start <= dates[i + 1] <= window_end
    ]
    if not rebal_dates:
        return None

    # The final holding period must stop at the window, not run into the month
    # in progress. searchsorted(..., "right") is an EXCLUSIVE bound, so the last
    # session the simulation may touch is one before it.
    hard_end_idx = int(dates.searchsorted(window_end, side="right"))
    last_sim_idx = min(hard_end_idx - 1, len(prices) - 1)

    strat_net_daily: list[float] = []
    strat_gross_daily: list[float] = []
    bench_daily: list[float] = []
    equity_dates: list[pd.Timestamp] = []
    period_records: list[dict[str, Any]] = []
    trade_records: list[dict[str, Any]] = []
    closed_trades: list[dict[str, Any]] = []
    open_positions: dict[str, dict[str, Any]] = {}
    sec_map = sector_map or {}

    prev_weights = pd.Series(0.0, index=prices.columns)
    prev_holdings: list[str] = []
    effective_buffer = buffer_n if buffer_n is not None else int(top_n * 1.5)

    for i, start_idx in enumerate(rebal_dates):
        # Three distinct indices, previously collapsed into two:
        #   start_idx  T    -- the signal date; every filter and score reads it
        #   fwd_start  T+1  -- the FILL. Entry and exit prices are struck here.
        #   exit_idx        -- the fill that closes this holding (the next
        #                      rebalance's T+1, or the end of the window).
        # The position is bought at the T+1 CLOSE, so the first day it can earn
        # anything is T+2. Accruing from T+1 -- which is what a single
        # fwd_start did -- credited the portfolio the T -> T+1 move, i.e. it
        # bought at the close of the very session it ranked on. That is the
        # look-ahead this engine claims not to have, and it also made the
        # equity curve disagree with the tradebook: a stock logged as bought at
        # T+1 and sold at T'+1 contributed P[T']/P[T] to the return series.
        fwd_start = start_idx + 1  # Key: Zero look-ahead - fill on T+1
        exit_idx = rebal_dates[i + 1] + 1 if i + 1 < len(rebal_dates) else last_sim_idx
        exit_idx = min(exit_idx, last_sim_idx)
        if exit_idx <= fwd_start:
            continue

        _p = prices.iloc[start_idx]
        _ema = ema.iloc[start_idx]
        _hi = high_52w.iloc[start_idx]

        above_ema = _p > _ema
        near_high = _p >= _hi * high_pct
        valid = above_ema & near_high & (_p > 0)

        # ── Compute Causal Signal at Day T ───────────────────────────────────
        # One signal, the composite that drives every rank on screen. The
        # alternatives that used to branch here -- residual alpha, industry
        # relative, acceleration, exp regression, raw return -- were removed:
        # backtesting a ranking the screener never shows answers a question
        # nobody asked, and each branch was its own untested scoring path.
        composite_score = _composite_z_score(
            prices, log_ret, start_idx, WINDOWS, norm_w if norm_w else [0.2] * 5
        )
        score = composite_score[valid & composite_score.notna()]

        full_ranked = score.sort_values(ascending=False)
        if full_ranked.empty:
            for j in range(fwd_start + 1, exit_idx + 1):
                equity_dates.append(prices.index[j])
                strat_net_daily.append(0.0)
                strat_gross_daily.append(0.0)
                bench_daily.append(
                    float(benchmark_ret.iloc[j]) if j < len(benchmark_ret) and pd.notna(benchmark_ret.iloc[j]) else 0.0
                )
            continue

        # ── Buffer Zone Selection (Turnover Reduction) ───────────────────────
        selected_holdings: list[str] = []
        if prev_holdings:
            # Retain previous holdings if still within buffer rank and valid
            for s in prev_holdings:
                if s in full_ranked.index:
                    rk = full_ranked.index.get_loc(s) + 1
                    if rk <= effective_buffer:
                        selected_holdings.append(s)
                if len(selected_holdings) >= top_n:
                    break

        # Fill remaining slots with top candidates
        for s in full_ranked.index:
            if s not in selected_holdings:
                selected_holdings.append(s)
            if len(selected_holdings) >= top_n:
                break

        holdings = selected_holdings[:top_n]

        # ── Portfolio Weighting ──────────────────────────────────────────────
        if weight_method == "Inverse Volatility":
            vol_w = log_ret[holdings].iloc[max(start_idx - 63, 0) : start_idx + 1].std()
            inv = (1.0 / vol_w.replace(0, np.nan)).fillna(0)
            t_w = inv.sum()
            wts = (
                (inv / t_w)
                if t_w > 0
                else pd.Series(1.0 / len(holdings), index=holdings)
            )

        else:
            wts = pd.Series(1.0 / len(holdings), index=holdings)

        # ── Turnover & Transaction Drag ──────────────────────────────────────
        full_w = pd.Series(0.0, index=prices.columns)
        full_w[wts.index] = wts.values

        if prev_weights.sum() > 0:
            turnover_period = float((full_w - prev_weights).abs().sum() / 2.0)
        else:
            turnover_period = 1.0  # Initial portfolio establishment

        prev_weights = full_w
        friction_drag = turnover_period * (cost_bps / 10000.0)

        # ── Record Rebalance Tradebook (Entries, Exits & Holds) ───────────────
        entries = [s for s in holdings if s not in prev_holdings]
        exits = [s for s in prev_holdings if s not in holdings]
        holds = [s for s in holdings if s in prev_holdings]

        # Both endpoints are fills: bought at the close of p_start_dt, sold at
        # the close of p_end_dt. The period return is exactly what a position
        # held between those two prints earned.
        p_start_dt = prices.index[fwd_start]
        p_end_dt = prices.index[exit_idx]
        period_lbl = (
            f"{p_start_dt:%d %b %Y} → {p_end_dt:%d %b %Y}"
            if p_start_dt
            else f"Period {i+1}"
        )

        # Record Exits & Closed Round-Trip Returns
        for s in exits:
            p_exit = _fill_price(prices, s, fwd_start)
            if s in full_ranked.index:
                rk = full_ranked.index.get_loc(s) + 1
                reason = f"Rank Dropped (#{rk} > Buffer {effective_buffer})"
            elif not above_ema.get(s, False):
                reason = f"Trend Breakdown (< {ema_period} EMA)"
            elif not near_high.get(s, False):
                reason = f"Failed 52W High Filter (< {high_pct*100:.0f}%)"
            else:
                reason = "Rebalance Exit"

            pos = open_positions.pop(s, None)
            if pos:
                p_entry = pos["entry_price"]
                entry_dt = pos["entry_date"]
                ret_pct = _round_trip_return(p_entry, p_exit)
                h_days = (
                    (p_start_dt - entry_dt).days
                    if (p_start_dt and entry_dt)
                    else rebal_freq
                )
            else:
                p_entry = p_exit
                entry_dt = p_start_dt
                ret_pct = 0.0
                h_days = rebal_freq

            closed_trades.append(
                {
                    "Month": f"{p_start_dt:%b-%Y}" if p_start_dt else "—",
                    "Symbol": s,
                    "Entry Date": f"{entry_dt:%d %b %Y}" if entry_dt else "—",
                    "Entry Price": p_entry,
                    "Exit Date": f"{p_start_dt:%d %b %Y}" if p_start_dt else "—",
                    "Exit Price": p_exit,
                    "Return %": ret_pct,
                    "Holding (Days)": h_days,
                    "Reason for Exit": reason,
                    "Status": "Closed",
                }
            )

            trade_records.append(
                {
                    "Period": period_lbl,
                    "Period Start": p_start_dt,
                    "Action": "🔴 SELL (Exit)",
                    "Symbol": s,
                    "Price": p_exit,
                    "Return %": ret_pct,
                    "Weight %": 0.0,
                    "Reason / Signal": reason,
                }
            )

        # Record Entries
        for s in entries:
            p_entry = _fill_price(prices, s, fwd_start)
            rk = full_ranked.index.get_loc(s) + 1 if s in full_ranked.index else 1
            w_val = float(wts.get(s, 0.0)) * 100

            open_positions[s] = {
                "entry_date": p_start_dt,
                "entry_price": p_entry,
                "entry_idx": fwd_start,
                "entry_weight": w_val,
                "entry_rank": rk,
            }

            trade_records.append(
                {
                    "Period": period_lbl,
                    "Period Start": p_start_dt,
                    "Action": "🟢 BUY (Entry)",
                    "Symbol": s,
                    "Price": p_entry,
                    "Return %": 0.0,
                    "Weight %": w_val,
                    "Reason / Signal": f"New Momentum Leader (Rank #{rk})",
                }
            )

        # Record Holds
        for s in holds:
            p_curr = _fill_price(prices, s, fwd_start)
            rk = full_ranked.index.get_loc(s) + 1 if s in full_ranked.index else "—"
            w_val = float(wts.get(s, 0.0)) * 100
            pos = open_positions.get(s)
            p_entry = pos["entry_price"] if pos else p_curr
            unrealized_ret = _round_trip_return(p_entry, p_curr)
            trade_records.append(
                {
                    "Period": period_lbl,
                    "Period Start": p_start_dt,
                    "Action": "⚪ HOLD (Retained)",
                    "Symbol": s,
                    "Price": p_curr,
                    "Return %": unrealized_ret,
                    "Weight %": w_val,
                    "Reason / Signal": f"Buffer Zone Retention (Rank #{rk})",
                }
            )

        prev_holdings = holdings

        # ── Measure Held Returns (fill at T+1 through the closing fill) ──────
        # The first accrual day is T+2: the position was bought at the T+1
        # close, so the T+1 bar itself belongs to whoever held it before.
        period_strat_rets: list[float] = []
        for d_idx, j in enumerate(range(fwd_start + 1, exit_idx + 1)):
            if j >= len(daily_ret):
                break
            equity_dates.append(prices.index[j])
            _dr = daily_ret.iloc[j]
            avail = [s for s in holdings if s in _dr.index and pd.notna(_dr[s])]
            gross_r = float((_dr[avail] * wts[avail]).sum()) if avail else 0.0

            # Deduct friction on the first rebalance day
            net_r = gross_r - (friction_drag if d_idx == 0 else 0.0)
            bench_r = float(benchmark_ret.iloc[j]) if pd.notna(benchmark_ret.iloc[j]) else 0.0

            strat_gross_daily.append(gross_r)
            strat_net_daily.append(net_r)
            bench_daily.append(bench_r)
            period_strat_rets.append(net_r)

        if period_strat_rets:
            s_ret_c = float(np.prod([1 + r for r in period_strat_rets]) - 1)
            b_rets = [
                float(benchmark_ret.iloc[j])
                for j in range(fwd_start + 1, min(exit_idx + 1, len(benchmark_ret)))
                if pd.notna(benchmark_ret.iloc[j])
            ]
            b_ret_c = float(np.prod([1 + r for r in b_rets]) - 1) if b_rets else 0.0
            period_records.append(
                {
                    "Period": period_lbl,
                    "Period Start": p_start_dt,
                    "Period End": p_end_dt,
                    "Strategy Net": s_ret_c,
                    "Benchmark": b_ret_c,
                    "Alpha vs Benchmark": s_ret_c - b_ret_c,
                    "Turnover %": turnover_period * 100,
                    "Cost Drag %": friction_drag * 100,
                    "Holdings": len(holdings),
                    "Buys": len(entries),
                    "Sells": len(exits),
                }
            )

    if not strat_net_daily:
        return None

    # The accrual dates are recorded as the loop runs. Rebuilding them from
    # rebal_dates[0] assumed every rebalance contributed an unbroken run of
    # sessions from the first fill onward -- false whenever a period is skipped
    # -- and silently shifted the whole equity curve by the number of missing
    # days rather than failing.
    dates = pd.DatetimeIndex(equity_dates)

    # Index every curve at 1.0 on the FILL date -- the session the first
    # positions were bought on, one before the first day they could earn
    # anything. Without that base point the curve's first value is already
    # 1 + r0, and `iloc[-1] / iloc[0]` then divides that first day back out:
    # the reported total return silently omitted one day of P&L and, with it,
    # the entire cost of establishing the portfolio, which is charged on
    # exactly that day (100% turnover -- the largest single drag in the run).
    base_pos = int(prices.index.get_loc(dates[0])) - 1

    def _curve(daily: list[float]) -> pd.Series:
        series = pd.Series(daily, index=dates, dtype=float)
        if base_pos >= 0:
            base = pd.Series([0.0], index=[prices.index[base_pos]])
            series = pd.concat([base, series])
        return (1 + series).cumprod()

    eq_strat_net = _curve(strat_net_daily)
    eq_strat_gross = _curve(strat_gross_daily)
    eq_bench = _curve(bench_daily)
    if not period_records:
        # Every rebalance was skipped (typically insufficient formation history).
        # Building a frame from [] and calling dropna(subset=...) raised
        # KeyError: ['Period Start'] rather than reporting no result.
        return None
    monthly_df = pd.DataFrame(period_records).dropna(subset=["Period Start"])
    tradebook_df = pd.DataFrame(trade_records)

    # Append remaining active open positions, marked at the LAST SIMULATED
    # session. Marking them at prices.index[-1] priced them in the month still
    # in progress -- outside the reported window and outside the equity curve --
    # so the blotter showed a return the strategy is not credited with, on a
    # date the header says the backtest does not cover.
    last_dt = prices.index[last_sim_idx]
    for s, pos in open_positions.items():
        p_curr = _fill_price(prices, s, last_sim_idx)
        p_entry = pos["entry_price"]
        entry_dt = pos["entry_date"]
        unrealized_ret = _round_trip_return(p_entry, p_curr)
        h_days = (last_dt - entry_dt).days if (last_dt and entry_dt) else 0
        closed_trades.append(
            {
                "Month": f"🟢 Active ({last_dt:%b-%Y})",
                "Symbol": s,
                "Entry Date": f"{entry_dt:%d %b %Y}" if entry_dt else "—",
                "Entry Price": p_entry,
                "Exit Date": f"Active ({last_dt:%d %b %Y})",
                "Exit Price": p_curr,
                "Return %": unrealized_ret,
                "Holding (Days)": h_days,
                "Reason for Exit": "🟢 Currently Held (Open Position)",
                "Status": "Open",
            }
        )

    closed_trades_df = pd.DataFrame(closed_trades)

    total_s_net = float(eq_strat_net.iloc[-1] / eq_strat_net.iloc[0] - 1)
    total_s_gross = float(eq_strat_gross.iloc[-1] / eq_strat_gross.iloc[0] - 1)
    total_b = float(eq_bench.iloc[-1] / eq_bench.iloc[0] - 1)

    n_days = len(dates)  # accrual sessions; the base point is not one of them
    ann_factor = 252.0 / max(n_days, 1)
    cagr_net = float((1 + total_s_net) ** ann_factor - 1) if (1 + total_s_net) > 0 else -1.0
    cagr_gross = (
        float((1 + total_s_gross) ** ann_factor - 1) if (1 + total_s_gross) > 0 else -1.0
    )
    cagr_bench = float((1 + total_b) ** ann_factor - 1) if (1 + total_b) > 0 else -1.0

    strat_daily_s = pd.Series(strat_net_daily)
    strat_vol = float(strat_daily_s.std() * np.sqrt(252))
    strat_sharpe = float(((cagr_net - 0.065) / strat_vol)) if strat_vol > 0 else 0.0

    dd_series = eq_strat_net / eq_strat_net.cummax() - 1
    max_dd = float(dd_series.min())

    n_periods = len(monthly_df)
    win_rate = (
        float((monthly_df["Alpha vs Benchmark"] > 0).mean())
        if not monthly_df.empty and "Alpha vs Benchmark" in monthly_df.columns
        else 0.0
    )

    downside_rets = strat_daily_s[strat_daily_s < 0]
    downside_vol = (
        float(downside_rets.std() * np.sqrt(252)) if len(downside_rets) > 5 else strat_vol
    )
    strat_sortino = float(((cagr_net - 0.065) / downside_vol)) if downside_vol > 0 else 0.0

    calmar_ratio = float((cagr_net / abs(max_dd))) if abs(max_dd) > 0 else 0.0
    avg_turnover = float(monthly_df["Turnover %"].mean()) if not monthly_df.empty else 0.0
    tot_cost_drag = total_s_gross - total_s_net

    return {
        "equity_curve": eq_strat_net,
        "equity_gross": eq_strat_gross,
        "benchmark": eq_bench,
        "monthly": monthly_df,
        "tradebook": tradebook_df,
        "closed_trades": closed_trades_df,
        "stats": {
            "total_return": total_s_net,
            "gross_return": total_s_gross,
            "bench_return": total_b,
            "alpha": total_s_net - total_b,
            "ann_return": cagr_net,
            "cagr_gross": cagr_gross,
            "ann_bench": cagr_bench,
            "max_drawdown": max_dd,
            "win_rate": win_rate,
            "sharpe": strat_sharpe,
            "sortino": strat_sortino,
            "calmar": calmar_ratio,
            "volatility": strat_vol,
            "avg_turnover": avg_turnover,
            "cost_drag_total": tot_cost_drag,
            "n_periods": n_periods,
            "n_days": n_days,
        },
    }
