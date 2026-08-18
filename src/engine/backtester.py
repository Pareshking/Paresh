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
    lookback_ret: int = 126,
    ema_period: int = 50,
    high_pct: float = 0.80,
    ranking_method: str = "Composite (Config Weights)",
    weight_method: str = "Equal Weight",
    config_weights: Sequence[float] = (0.10, 0.30, 0.30, 0.20, 0.10),
    stock_cap: float = 0.05,
    sector_cap: float = 0.30,
    sector_map: dict[str, str] | None = None,
    cost_bps: float = 30.0,
    buffer_n: int | None = None,
    _benchmark_close: pd.Series | None = None,
) -> dict[str, Any] | None:
    """
    Executes a walk-forward momentum backtest with zero look-ahead bias and friction modeling.
    """
    WINDOWS = MOMENTUM_WINDOWS
    prices = _adj_close.dropna(axis=1, how="all").copy()

    is_composite = (
        "Composite" in ranking_method
        or "Multi-Window" in ranking_method
    )
    if is_composite:
        w_total = sum(config_weights)
        norm_w = [cw / w_total for cw in config_weights] if w_total > 0 else [0.2] * 5
        active_windows = [w for w, cw in zip(WINDOWS, norm_w) if cw > 0]
        max_lb = max(active_windows) if active_windows else max(WINDOWS)
    else:
        max_lb = lookback_ret
        norm_w = None

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
    if not rebal_dates:
        return None

    strat_net_daily: list[float] = []
    strat_gross_daily: list[float] = []
    bench_daily: list[float] = []
    period_records: list[dict[str, Any]] = []
    trade_records: list[dict[str, Any]] = []
    closed_trades: list[dict[str, Any]] = []
    open_positions: dict[str, dict[str, Any]] = {}
    sec_map = sector_map or {}

    prev_weights = pd.Series(0.0, index=prices.columns)
    prev_holdings: list[str] = []
    effective_buffer = buffer_n if buffer_n is not None else int(top_n * 1.5)

    for i, start_idx in enumerate(rebal_dates):
        fwd_start = start_idx + 1  # Key: Zero look-ahead - trade on T+1
        fwd_end = rebal_dates[i + 1] + 1 if i + 1 < len(rebal_dates) else len(prices)
        fwd_end = min(fwd_end, len(prices))
        if fwd_end <= fwd_start:
            continue

        _p = prices.iloc[start_idx]
        _ema = ema.iloc[start_idx]
        _hi = high_52w.iloc[start_idx]

        above_ema = _p > _ema
        near_high = _p >= _hi * high_pct
        valid = above_ema & near_high & (_p > 0)

        # ── Compute Causal Signal at Day T ───────────────────────────────────
        if (
            is_composite
            or "Multi-Window" in ranking_method
            or "Composite" in ranking_method
        ):
            composite_score = _composite_z_score(
                prices, log_ret, start_idx, WINDOWS, norm_w if norm_w else [0.2] * 5
            )
            score = composite_score[valid & composite_score.notna()]

        elif "Residual" in ranking_method or "α" in ranking_method:
            # 6M CAPM Market-Beta Regression Alpha
            sl = max(start_idx - 126, 0)
            mkt_ret = benchmark_ret.iloc[sl : start_idx + 1]
            stk_ret = daily_ret.iloc[sl : start_idx + 1]
            # CAPM alpha must use paired valid stock/benchmark observations.
            # Do not let a stock's missing observations enter its mean/beta on a
            # different sample from the benchmark.
            valid_mkt = mkt_ret.notna()
            mkt_ret = mkt_ret.loc[valid_mkt]
            stk_ret = stk_ret.loc[valid_mkt]
            if len(mkt_ret) >= 30 and float(mkt_ret.var()) > 0:
                alpha_res = pd.Series(np.nan, index=prices.columns, dtype=float)
                for sym in stk_ret.columns:
                    pair = pd.concat([stk_ret[sym], mkt_ret], axis=1).dropna()
                    if len(pair) < 30:
                        continue
                    stock_r = pair.iloc[:, 0]
                    bench_r = pair.iloc[:, 1]
                    bench_var = float(bench_r.var())
                    if bench_var <= 0:
                        continue
                    beta_i = float(stock_r.cov(bench_r)) / bench_var
                    alpha_res.loc[sym] = (float(stock_r.mean()) - beta_i * float(bench_r.mean())) * 252
                score = alpha_res[valid & alpha_res.notna()]
            else:
                score = pd.Series(np.nan, index=prices.columns)

        elif "Industry-Relative" in ranking_method:
            # Multi-window Composite minus Industry Peer Mean
            composite_score = _composite_z_score(
                prices, log_ret, start_idx, WINDOWS, norm_w if norm_w else [0.2] * 5
            )

            ind_map = sec_map
            score_df = pd.DataFrame({
                "Symbol": composite_score.index,
                "Score": composite_score.values,
                "Industry": [ind_map.get(s, "Other") for s in composite_score.index],
            })
            peer_sum = score_df.groupby("Industry")["Score"].transform("sum", min_count=1) - score_df["Score"]
            peer_count = score_df.groupby("Industry")["Score"].transform("count") - score_df["Score"].notna().astype(int)
            peer_mean = peer_sum.div(peer_count.replace(0, np.nan))
            ind_rel = score_df["Score"] - peer_mean
            ind_rel.index = score_df["Symbol"]
            score = ind_rel[valid & ind_rel.notna()]

        elif "Acceleration" in ranking_method or "Accel" in ranking_method:
            p_w1 = prices.iloc[max(start_idx - 21, 0) : start_idx + 1]
            p_w3 = prices.iloc[max(start_idx - 63, 0) : start_idx + 1]
            p_w6 = prices.iloc[max(start_idx - 126, 0) : start_idx + 1]
            p_w9 = prices.iloc[max(start_idx - 189, 0) : start_idx + 1]
            p_w12 = prices.iloc[max(start_idx - 252, 0) : start_idx + 1]
            r1 = (p_w1.iloc[-1] / p_w1.iloc[0].clip(lower=0.01)) - 1
            r3 = (p_w3.iloc[-1] / p_w3.iloc[0].clip(lower=0.01)) - 1
            r6 = (p_w6.iloc[-1] / p_w6.iloc[0].clip(lower=0.01)) - 1
            r9 = (p_w9.iloc[-1] / p_w9.iloc[0].clip(lower=0.01)) - 1
            r12 = (p_w12.iloc[-1] / p_w12.iloc[0].clip(lower=0.01)) - 1
            accel = (0.10 * r1 + 0.35 * r3 + 0.55 * r6) - (0.45 * r9 + 0.55 * r12)
            score = accel[valid & accel.notna()]

        else:
            lb = lookback_ret
            sl = max(start_idx - lb, 0)
            p_w = prices.iloc[sl : start_idx + 1]

            if ranking_method == "Sharpe":
                log_ret_period = np.log(
                    p_w.iloc[-1].clip(lower=0.01) / p_w.iloc[0].clip(lower=0.01)
                )
                vol = log_ret.iloc[sl : start_idx + 1].std() * np.sqrt(lb)
                score = log_ret_period / vol.replace(0, np.nan)
            elif ranking_method == "Exp Regression":
                log_p = np.log(p_w.clip(lower=0.01))
                t_s = pd.Series(np.arange(len(log_p)), index=log_p.index, dtype=float)
                # OLS slope of log-price against time, annualized.
                beta = (log_p.sub(log_p.mean()).mul(t_s - t_s.mean(), axis=0).sum() / max(float(((t_s - t_s.mean()) ** 2).sum()), 1e-8))
                score = np.exp(beta * 252) - 1
            else:
                score = p_w.iloc[-1] / p_w.iloc[0] - 1

            score = score[valid & score.notna()]

        full_ranked = score.sort_values(ascending=False)
        if full_ranked.empty:
            for j in range(fwd_start, fwd_end):
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

        elif weight_method == "MVO (Mean-Variance)":
            try:
                _cov_data = (
                    log_ret[holdings]
                    .iloc[max(start_idx - 126, 0) : start_idx + 1]
                    .dropna(how="any")
                )
                if len(_cov_data) < 30:
                    raise ValueError("Insufficient covariance history")
                from sklearn.covariance import ledoit_wolf

                cov_mat, _ = ledoit_wolf(_cov_data)
                eps = 1e-6 * np.trace(cov_mat) / max(len(cov_mat), 1)
                cov_mat = cov_mat * 252 + np.eye(len(cov_mat)) * eps

                _mu = full_ranked[holdings].values.astype(float)
                _mu_range = _mu.max() - _mu.min()
                mu = (
                    (_mu - _mu.min()) / _mu_range * 0.50
                    if _mu_range > 1e-8
                    else np.ones(len(holdings)) * 0.25
                )

                n_h = len(holdings)
                eff_cap = max(stock_cap, 1.0 / n_h + 1e-4)
                from scipy.optimize import minimize

                def _obj(w):
                    return w @ cov_mat @ w - 0.5 * (mu @ w)

                _constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
                if sec_map and sector_cap < 1.0:
                    _sec_idx: dict[str, list[int]] = {}
                    for idx, sym in enumerate(holdings):
                        _sec_idx.setdefault(sec_map.get(sym, "Other"), []).append(idx)
                    for idxs in _sec_idx.values():
                        a = np.zeros(n_h)
                        a[idxs] = 1.0
                        _constraints.append(
                            {
                                "type": "ineq",
                                "fun": lambda w, a=a, c=sector_cap: c - a @ w,
                            }
                        )

                _bounds = [(0, eff_cap)] * n_h
                _opts = {"maxiter": 500}

                res = minimize(
                    _obj,
                    x0=np.ones(n_h) / n_h,
                    method="SLSQP",
                    bounds=_bounds,
                    constraints=_constraints,
                    options=_opts,
                )
                if res.success:
                    wts_arr = np.maximum(res.x, 0)
                    wts = pd.Series(wts_arr / wts_arr.sum(), index=holdings)
                else:
                    _vol_w = (
                        log_ret[holdings]
                        .iloc[max(start_idx - 63, 0) : start_idx + 1]
                        .std()
                    )
                    _inv = (1.0 / _vol_w.replace(0, np.nan)).fillna(0)
                    _inv_sum = _inv.sum()
                    wts = pd.Series(
                        (
                            (_inv / _inv_sum).values
                            if _inv_sum > 0
                            else np.ones(n_h) / n_h
                        ),
                        index=holdings,
                    )
            except Exception:
                wts = pd.Series(1.0 / len(holdings), index=holdings)
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

        p_start_dt = prices.index[fwd_start] if fwd_start < len(prices) else None
        p_end_dt = prices.index[min(fwd_end - 1, len(prices) - 1)]
        period_lbl = (
            f"{p_start_dt:%d %b %Y} → {p_end_dt:%d %b %Y}"
            if p_start_dt
            else f"Period {i+1}"
        )

        # Record Exits & Closed Round-Trip Returns
        for s in exits:
            p_exit = (
                float(prices[s].iloc[fwd_start])
                if (fwd_start < len(prices) and s in prices.columns)
                else float(prices[s].iloc[start_idx])
            )
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
                ret_pct = ((p_exit / p_entry) - 1) if p_entry > 0 else 0.0
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
            p_entry = (
                float(prices[s].iloc[fwd_start])
                if (fwd_start < len(prices) and s in prices.columns)
                else float(prices[s].iloc[start_idx])
            )
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
            p_curr = (
                float(prices[s].iloc[fwd_start])
                if (fwd_start < len(prices) and s in prices.columns)
                else float(prices[s].iloc[start_idx])
            )
            rk = full_ranked.index.get_loc(s) + 1 if s in full_ranked.index else "—"
            w_val = float(wts.get(s, 0.0)) * 100
            pos = open_positions.get(s)
            p_entry = pos["entry_price"] if pos else p_curr
            unrealized_ret = ((p_curr / p_entry) - 1) if p_entry > 0 else 0.0
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

        # ── Measure Forward Daily Returns (T+1 to T') ────────────────────────
        period_strat_rets: list[float] = []
        for d_idx, j in enumerate(range(fwd_start, fwd_end)):
            if j >= len(daily_ret):
                break
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
                for j in range(fwd_start, min(fwd_end, len(benchmark_ret)))
                if j < len(benchmark_ret) and pd.notna(benchmark_ret.iloc[j])
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

    _all_dates = prices.index
    first_fwd = rebal_dates[0] + 1
    dates = _all_dates[first_fwd : first_fwd + len(strat_net_daily)]
    if len(dates) != len(strat_net_daily):
        n = min(len(dates), len(strat_net_daily))
        dates = dates[:n]
        strat_net_daily = strat_net_daily[:n]
        strat_gross_daily = strat_gross_daily[:n]
        bench_daily = bench_daily[:n]

    eq_strat_net = (1 + pd.Series(strat_net_daily, index=dates)).cumprod()
    eq_strat_gross = (1 + pd.Series(strat_gross_daily, index=dates)).cumprod()
    eq_bench = (1 + pd.Series(bench_daily, index=dates)).cumprod()
    monthly_df = pd.DataFrame(period_records).dropna(subset=["Period Start"])
    tradebook_df = pd.DataFrame(trade_records)

    # Append remaining active open positions
    last_dt = prices.index[-1]
    for s, pos in open_positions.items():
        p_curr = (
            float(prices[s].iloc[-1]) if s in prices.columns else pos["entry_price"]
        )
        p_entry = pos["entry_price"]
        entry_dt = pos["entry_date"]
        unrealized_ret = ((p_curr / p_entry) - 1) if p_entry > 0 else 0.0
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

    n_days = len(dates)
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
