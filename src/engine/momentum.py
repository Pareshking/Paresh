"""
Quantitative Multi-System Momentum Engine — Hardened Production Core.

Systems:
  1. Multi-Window Sharpe & Sortino Momentum (Winsorized Z-score across 5 lookbacks)
  2. Vectorized Exponential Regression (annualized OLS slope with analytical 1D convolution)
  3. Residual / Idiosyncratic Alpha (Market-beta stripped alpha)
  4. Industry-Relative Momentum (Sector-neutral outperformance)
  5. Momentum Acceleration (Short-term velocity vs long-term baseline)
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd
from scipy.ndimage import convolve1d

from src.core.config import DEFAULT_LOOKBACK_WEIGHTS, MOMENTUM_WINDOWS
from src.core.logger import logger
from src.engine.calendar_momentum import (
    _calendar_period_metrics,
    calendar_start_positions,
    latest_as_of_date,
)


def clean_holidays(df: pd.DataFrame | None) -> pd.DataFrame:
    """Drops dates where >70% of the universe has NaN (market holidays)."""
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()
    n_cols = df.shape[1]
    limit = max(int(n_cols * 0.70), 1)
    count = df.isna().sum(axis=1)
    holidays = count > limit
    n_dropped = int(holidays.sum())
    if n_dropped > 0:
        logger.debug(f"Holiday cleanup: dropped {n_dropped} rows")
    # Remove exchange-wide missing dates only; preserve stock-specific NaNs.
    cleaned = df.loc[~holidays]
    return cleaned


def compute_ffill_pct(raw_df: pd.DataFrame | None) -> pd.Series:
    """Computes per-stock % of rows that were gap-filled after dropping holidays."""
    if raw_df is None or raw_df.empty:
        return pd.Series(dtype=float)
    n_cols = raw_df.shape[1]
    limit = max(int(n_cols * 0.70), 1)
    count = raw_df.isna().sum(axis=1)
    cleaned = raw_df.loc[count <= limit]
    if cleaned.empty:
        return pd.Series(dtype=float)
    n_rows = len(cleaned)
    nan_per_col = cleaned.isna().sum()
    return (nan_per_col / max(n_rows, 1) * 100).round(1)


def winsorize_series(s: pd.Series, std_limit: float = 3.0) -> pd.Series:
    """Winsorizes cross-sectional series to +/- std_limit standard deviations."""
    if s.empty or s.isna().all():
        return s
    clean = s.dropna()
    if len(clean) < 3 or clean.std(ddof=0) == 0:
        return s
    mean, std = float(clean.mean()), float(clean.std(ddof=0))
    lower, upper = mean - std_limit * std, mean + std_limit * std
    return s.clip(lower=lower, upper=upper)


def zscore_series(s: pd.Series, winsorize: bool = True) -> pd.Series:
    """Calculates cross-sectional Z-scores with optional 3-sigma winsorization."""
    if s.empty or s.isna().all():
        return s
    clean = s.dropna()
    if len(clean) < 3 or clean.std(ddof=0) == 0:
        return pd.Series(0.0, index=s.index)
    if winsorize:
        clean = winsorize_series(clean, std_limit=3.0)
    mean_val = float(clean.mean())
    std_val = float(clean.std(ddof=0))
    z = (clean - mean_val) / (std_val + 1e-12)
    return z.reindex(s.index)


def _normalize_ticker_cols(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None or df.empty:
        return df
    res = df.copy()
    res.columns = [str(c).replace(".NS", "").strip().upper() for c in res.columns]
    return res


class MomentumEngine:
    """
    Hardened Production Quantitative Momentum Engine.
    Vectorized calculations across 5 lookback windows with zero look-ahead bias.
    """

    WINDOWS: list[int] = MOMENTUM_WINDOWS
    DEFAULT_WEIGHTS: list[float] = DEFAULT_LOOKBACK_WEIGHTS

    def __init__(
        self,
        prices_df: pd.DataFrame,
        *,
        high_df: pd.DataFrame | None = None,
        low_df: pd.DataFrame | None = None,
        close_df: pd.DataFrame | None = None,
        volume_df: pd.DataFrame | None = None,
        weights: Sequence[float] | None = None,
        market_cap_weights: pd.Series | None = None,
    ):
        self.ffill_pct: pd.Series = compute_ffill_pct(prices_df)

        cleaned_p = clean_holidays(prices_df)
        norm_p = _normalize_ticker_cols(cleaned_p)
        self.prices: pd.DataFrame = norm_p if norm_p is not None else pd.DataFrame()
        
        if high_df is not None:
            norm_h = _normalize_ticker_cols(clean_holidays(high_df))
            self.high: pd.DataFrame = norm_h if norm_h is not None else self.prices
        else:
            self.high = self.prices

        if low_df is not None:
            norm_l = _normalize_ticker_cols(clean_holidays(low_df))
            self.low: pd.DataFrame = norm_l if norm_l is not None else self.prices
        else:
            self.low = self.prices

        if close_df is not None:
            norm_c = _normalize_ticker_cols(clean_holidays(close_df))
            self.close: pd.DataFrame = norm_c if norm_c is not None else self.prices
        else:
            self.close = self.prices

        if volume_df is not None:
            self.volume: pd.DataFrame | None = _normalize_ticker_cols(clean_holidays(volume_df))
        else:
            self.volume = None

        self.weights: list[float] = list(weights) if weights is not None else list(self.DEFAULT_WEIGHTS)
        self._mcap_weights: pd.Series | None = market_cap_weights

        # Pre-calculate daily log returns
        self.log_ret: pd.DataFrame = np.log(self.prices / self.prices.shift(1).replace(0, np.nan))
        self._valid_counts: pd.Series = self.prices.notna().sum()

        self.momentum_scores: pd.DataFrame | None = None
        self.exp_reg_scores: pd.DataFrame | None = None
        self.residual_ranks: pd.Series | None = None
        self.ind_rel_ranks: pd.Series | None = None
        self.vol_mgd_ranks: pd.Series | None = None
        self.period_metrics: dict[int, dict[str, pd.Series]] = {}

    @staticmethod
    def _mp(window: int) -> int:
        return window

    def _annualized_sharpe(self, w: int) -> pd.DataFrame:
        """Compute annualized period Sharpe without an  multiplier."""
        log_ret_w = np.log(self.prices / self.prices.shift(w).replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        daily_vol_w = (self.log_ret.rolling(w, min_periods=w).std(ddof=0) * np.sqrt(w)).replace(0, np.nan)
        return (log_ret_w / daily_vol_w).replace([np.inf, -np.inf], np.nan)

    def calculate_sharpe_momentum(self) -> pd.DataFrame:
        """Compatibility entry point for the canonical calendar-month System-1 engine."""
        from src.engine.calendar_momentum import apply_calendar_momentum
        return apply_calendar_momentum(self)

    def calculate_exp_regression(self, window: int = 126) -> pd.DataFrame:
        """Calculate annualized rolling exponential-regression slope without synthetic fills."""
        log_p = np.log(self.prices.clip(lower=0.01))
        n = int(window)
        score = pd.DataFrame(np.nan, index=log_p.index, columns=log_p.columns, dtype=float)
        if n < 2 or len(log_p) < n:
            self.exp_reg_scores = score
            return score

        t = np.arange(n, dtype=float)
        t_rev = t[::-1]
        t2_rev = (t * t)[::-1]
        ones = np.ones(n, dtype=float)

        for col in log_p.columns:
            y = log_p[col].to_numpy(dtype=float)
            mask = np.isfinite(y)
            if int(mask.sum()) < n:
                continue
            y0 = np.where(mask, y, 0.0)
            m = mask.astype(float)
            n_obs = np.convolve(m, ones, mode="valid")
            sum_y = np.convolve(y0, ones, mode="valid")
            sum_t = np.convolve(m, t_rev, mode="valid")
            sum_t2 = np.convolve(m, t2_rev, mode="valid")
            sum_ty = np.convolve(y0, t_rev, mode="valid")
            denom = n_obs * sum_t2 - sum_t * sum_t
            numer = n_obs * sum_ty - sum_t * sum_y
            valid = (n_obs >= n) & (denom > 1e-12)
            slopes = np.full(len(n_obs), np.nan)
            slopes[valid] = numer[valid] / denom[valid]
            out = np.full(len(log_p), np.nan)
            out[n - 1:] = np.exp(np.clip(slopes * 252.0, -700.0, 700.0)) - 1.0
            score[col] = out

        self.exp_reg_scores = score
        return score

    # ── System 3: Residual / Idiosyncratic Momentum ──────────────────────────
    def calculate_residual_momentum(
        self,
        benchmark_returns: pd.Series | None = None,
        window: int = 126,
        months: int | None = 6,
    ) -> pd.Series:
        """Compute residual alpha over a calendar-defined period by default.

        ``window`` remains available for callers that explicitly request a
        trading-row window by passing ``months=None``. The production 6M
        model uses calendar months so weekends/holidays do not change the
        economic horizon.
        """
        daily_ret = self.prices.pct_change(fill_method=None)
        if benchmark_returns is None:
            from src.loaders.price_loader import fetch_benchmark_history
            benchmark_close = fetch_benchmark_history(period="2y")
            mkt_ret = (
                pd.to_numeric(benchmark_close, errors="coerce")
                .reindex(daily_ret.index)
                .pct_change(fill_method=None)
                if not benchmark_close.empty
                else pd.Series(np.nan, index=daily_ret.index, dtype=float)
            )
        else:
            mkt_ret = pd.to_numeric(benchmark_returns, errors="coerce").reindex(daily_ret.index)

        if months is None:
            start = max(0, len(daily_ret) - window)
        else:
            as_of = latest_as_of_date(pd.DatetimeIndex(daily_ret.index))
            starts = calendar_start_positions(
                pd.DatetimeIndex(daily_ret.index), months, latest_as_of=as_of
            )
            start = int(starts[-1])

        mkt_ret_w = mkt_ret.iloc[start:]
        ranks = pd.Series(np.nan, index=self.prices.columns, dtype=float)
        for sym in self.prices.columns:
            pair = pd.concat([daily_ret[sym].iloc[start:], mkt_ret_w], axis=1).dropna()
            if len(pair) < 30:
                continue
            stock_r = pair.iloc[:, 0]
            bench_r = pair.iloc[:, 1]
            mkt_var = float(bench_r.var())
            if mkt_var <= 1e-12 or not np.isfinite(mkt_var):
                continue
            beta = float(stock_r.cov(bench_r)) / mkt_var
            ranks.loc[sym] = (float(stock_r.mean()) - beta * float(bench_r.mean())) * 252
        ranks = ranks.rank(ascending=False, method="min")
        self.residual_ranks = ranks
        return ranks
    def calculate_industry_relative(
        self,
        rank_df: pd.DataFrame,
        industry_col: str = "Industry",
    ) -> pd.Series:
        """Computes stock composite score minus industry peer group average."""
        if self.momentum_scores is None or self.momentum_scores.empty:
            self.calculate_sharpe_momentum()

        latest_scores = self.momentum_scores.iloc[-1] if self.momentum_scores is not None else pd.Series()
        ind_map = rank_df.set_index("Symbol")[industry_col].to_dict() if industry_col in rank_df.columns else {}

        score_df = pd.DataFrame(
            {
                "Symbol": latest_scores.index,
                "Score": latest_scores.values,
                "Industry": [ind_map.get(s, "Other") for s in latest_scores.index],
            }
        )

        # Leave-one-out industry mean: a stock must not contribute to the peer benchmark against which that same stock is measured.
        industry_sum = score_df.groupby("Industry")["Score"].transform("sum", min_count=1)
        industry_count = score_df.groupby("Industry")["Score"].transform("count")
        peer_sum = industry_sum - score_df["Score"]
        peer_count = industry_count - score_df["Score"].notna().astype(int)
        peer_mean = peer_sum.div(peer_count.replace(0, np.nan))
        rel_score = score_df["Score"] - peer_mean

        ranks = pd.Series(rel_score.values, index=score_df["Symbol"]).rank(
            ascending=False, na_option="bottom"
        )
        self.ind_rel_ranks = ranks
        return ranks

    # ── System 5: Momentum Acceleration ──────────────────────────────────────
    def calculate_momentum_acceleration(self) -> pd.Series:
        """Rank acceleration using calendar 1M/3M/6M/9M/12M horizons."""
        zero_s = pd.Series(0.0, index=self.prices.columns)
        as_of = latest_as_of_date(pd.DatetimeIndex(self.prices.index))
        scores: dict[int, pd.Series] = {}
        for months in (1, 3, 6, 9, 12):
            _, _, sharpe, _ = _calendar_period_metrics(
                self.prices, self.log_ret, months, latest_as_of=as_of
            )
            scores[months] = sharpe.iloc[-1].replace(
                [np.inf, -np.inf], np.nan
            )

        s_1m = scores.get(1, zero_s)
        s_3m = scores.get(3, zero_s)
        s_6m = scores.get(6, zero_s)
        s_9m = scores.get(9, zero_s)
        s_12m = scores.get(12, zero_s)

        short_term = (
            0.10 * zscore_series(s_1m)
            + 0.35 * zscore_series(s_3m)
            + 0.55 * zscore_series(s_6m)
        )
        long_term = 0.45 * zscore_series(s_9m) + 0.55 * zscore_series(s_12m)
        accel = short_term - long_term

        ranks = accel.rank(ascending=False, na_option="bottom")
        return ranks
    def compute_atr_and_stops(
        self,
        period: int = 14,
        atr_mult: float = 2.0,
        chand_mult: float = 3.0,
    ) -> pd.DataFrame:
        """Vectorized ATR, 2xATR Stop Loss, and 3xATR Chandelier Exits."""
        prev_close = self.close.shift(1)
        idx = self.high.index.intersection(self.low.index).intersection(prev_close.index)
        h = self.high.reindex(idx)
        lo = self.low.reindex(idx)
        pc = prev_close.reindex(idx)
        tr = np.maximum(np.maximum((h - lo).values, (h - pc).abs().values), (lo - pc).abs().values)
        tr = pd.DataFrame(tr, index=idx, columns=self.high.columns)

        atr = tr.rolling(period, min_periods=max(period - 2, 5)).mean()
        latest_atr = atr.iloc[-1]
        latest_close = self.close.iloc[-1]
        atr_pct = (latest_atr / latest_close.replace(0, np.nan)) * 100

        stop_loss = (latest_close - atr_mult * latest_atr).clip(lower=0)
        hi_22 = self.high.iloc[-22:].max()
        chand_exit = (hi_22 - chand_mult * latest_atr).clip(lower=0)

        return pd.DataFrame(
            {
                "ATR": latest_atr.round(2),
                "ATR %": atr_pct.round(1),
                "Stop Loss": stop_loss.round(2),
                "Chand Exit": chand_exit.round(2),
            }
        )

    # ── Frog-in-the-Pan Persistence ──────────────────────────────────────────
    def compute_persistence(
        self, window: int = 126, months: int | None = 6
    ) -> pd.Series:
        """Compute percentage of sessions with positive return in a 6M calendar window."""
        if months is None:
            ret = self.log_ret.iloc[-window:]
        else:
            as_of = latest_as_of_date(pd.DatetimeIndex(self.log_ret.index))
            starts = calendar_start_positions(
                pd.DatetimeIndex(self.log_ret.index), months, latest_as_of=as_of
            )
            ret = self.log_ret.iloc[int(starts[-1]) :]
        pos = (ret > 0).sum()
        total = ret.notna().sum().replace(0, np.nan)
        return (pos / total * 100).round(1)
    def get_rankings(
        self,
        index_info: pd.DataFrame,
        market_caps: pd.Series,
        *,
        close_prices_df: pd.DataFrame | None = None,
        high_prices_df: pd.DataFrame | None = None,
        compute_exp_reg: bool = True,
    ) -> pd.DataFrame:
        """Constructs comprehensive production master rankings."""
        if self.momentum_scores is None:
            from src.engine.calendar_momentum import apply_calendar_momentum
            apply_calendar_momentum(self)

        latest_scores = (
            self.momentum_scores.iloc[-1]
            if self.momentum_scores is not None
            else pd.Series(dtype=float)
        )
        valid_mask = self._valid_counts >= 63
        latest_scores_valid = latest_scores.where(valid_mask, np.nan)

        rank_df = index_info.copy()
        sym_to_score = latest_scores_valid.to_dict()
        rank_df["Score"] = rank_df["Symbol"].map(sym_to_score)
        rank_df = rank_df.dropna(subset=["Score"]).copy()
        rank_df["Rank"] = (
            rank_df["Score"].rank(ascending=False, method="min").astype(int)
        )
        rank_df["Composite Rank"] = rank_df["Rank"]

        # Historical ranks use calendar 1M/3M snapshots rather than fixed rows.
        n_rows = len(self.momentum_scores) if self.momentum_scores is not None else 0
        if n_rows > 0 and self.momentum_scores is not None:
            as_of = latest_as_of_date(pd.DatetimeIndex(self.momentum_scores.index))
            starts = calendar_start_positions(
                pd.DatetimeIndex(self.momentum_scores.index), 1, latest_as_of=as_of
            )
            idx_1m = int(starts[-1])
            if idx_1m < n_rows:
                s_1m = self.momentum_scores.iloc[idx_1m].where(valid_mask, np.nan)
                r_1m = s_1m.rank(ascending=False, method="min")
                rank_df["Rank (-1M)"] = rank_df["Symbol"].map(r_1m)
                rank_df["Rank Δ 1M"] = rank_df["Rank (-1M)"] - rank_df["Rank"]
            else:
                rank_df["Rank (-1M)"] = np.nan
                rank_df["Rank Δ 1M"] = np.nan

            starts = calendar_start_positions(
                pd.DatetimeIndex(self.momentum_scores.index), 3, latest_as_of=as_of
            )
            idx_3m = int(starts[-1])
            if idx_3m < n_rows:
                s_3m = self.momentum_scores.iloc[idx_3m].where(valid_mask, np.nan)
                r_3m = s_3m.rank(ascending=False, method="min")
                rank_df["Rank (-3M)"] = rank_df["Symbol"].map(r_3m)
                rank_df["Rank Δ 3M"] = rank_df["Rank (-3M)"] - rank_df["Rank"]
            else:
                rank_df["Rank (-3M)"] = np.nan
                rank_df["Rank Δ 3M"] = np.nan
        else:
            rank_df["Rank (-1M)"] = np.nan
            rank_df["Rank Δ 1M"] = np.nan
            rank_df["Rank (-3M)"] = np.nan
            rank_df["Rank Δ 3M"] = np.nan

        # CMP & Technical Signals
        close_src = (
            close_prices_df if close_prices_df is not None else self.close
        ).copy()
        high_src = (high_prices_df if high_prices_df is not None else self.high).copy()

        # Normalize column names to uppercase stripped tickers
        close_src.columns = [
            str(c).replace(".NS", "").strip().upper() for c in close_src.columns
        ]
        high_src.columns = [
            str(c).replace(".NS", "").strip().upper() for c in high_src.columns
        ]

        # Drop any trailing rows that are all NaN
        valid_close_idx = close_src.dropna(how="all").index
        if not valid_close_idx.empty:
            close_src = close_src.loc[: valid_close_idx[-1]]
            high_src = high_src.loc[: valid_close_idx[-1]]

        latest_close = close_src.iloc[-1]
        rank_df["CMP"] = rank_df["Symbol"].map(latest_close.to_dict())

        # 50 EMA
        ema_50 = close_src.ewm(span=50, min_periods=30).mean().iloc[-1]
        rank_df["Above 50 EMA"] = rank_df["Symbol"].map(
            lambda s: (
                (latest_close.get(s, 0) > ema_50.get(s, 0))
                if pd.notna(ema_50.get(s)) and pd.notna(latest_close.get(s))
                else False
            )
        )
        rank_df["% 50 EMA"] = rank_df["Symbol"].map(
            lambda s: (
                ((latest_close.get(s, 0) - ema_50.get(s, 0)) / ema_50.get(s, 1) * 100)
                if pd.notna(ema_50.get(s))
                and pd.notna(latest_close.get(s))
                and ema_50.get(s, 0) > 0
                else np.nan
            )
        )

        # 52W High
        win_52w = min(252, len(high_src))
        high_52w = high_src.iloc[-win_52w:].max()
        pct_high = ((latest_close - high_52w) / high_52w.replace(0, np.nan)) * 100
        rank_df["52W High"] = rank_df["Symbol"].map(high_52w.to_dict())
        rank_df["% High"] = rank_df["Symbol"].map(pct_high.to_dict())
        rank_df["Near 52W High"] = rank_df["% High"].map(
            lambda x: x >= -20.0 if pd.notna(x) else False
        )

        # 3M & 6M Metrics use the canonical calendar-period engine.
        as_of_metrics = latest_as_of_date(pd.DatetimeIndex(self.prices.index))
        for months, label in ((3, "3M"), (6, "6M")):
            _, cal_ret, cal_sharpe, _ = _calendar_period_metrics(
                self.prices, self.log_ret, months, latest_as_of=as_of_metrics
            )
            rank_df[f"{label} Return"] = rank_df["Symbol"].map(cal_ret.iloc[-1].to_dict())
            rank_df[f"{label} Sharpe"] = rank_df["Symbol"].map(cal_sharpe.iloc[-1].to_dict())

        # 3M & 6M drawdowns use calendar-defined windows.
        close_idx = pd.DatetimeIndex(close_src.index)
        as_of = latest_as_of_date(close_idx)
        for months, label in ((3, "3M"), (6, "6M")):
            starts = calendar_start_positions(close_idx, months, latest_as_of=as_of)
            start = int(starts[-1])
            period_close = close_src.iloc[start:]
            roll_max = period_close.cummax()
            dd = ((period_close - roll_max) / roll_max.replace(0, np.nan)).min() * 100
            rank_df[f"Max DD {label}"] = rank_df["Symbol"].map(dd.to_dict())

        # ATR & Stops
        atr_df = self.compute_atr_and_stops()
        for c in ["ATR", "ATR %", "Stop Loss", "Chand Exit"]:
            rank_df[c] = rank_df["Symbol"].map(atr_df[c].to_dict())

        # Persistence
        pers = self.compute_persistence(months=6)
        rank_df["Persistence"] = rank_df["Symbol"].map(pers.to_dict())

        # Volume Signal
        if self.volume is not None and not self.volume.empty:
            vol_df = self.volume.copy()
            vol_df.columns = [
                str(c).replace(".NS", "").strip().upper() for c in vol_df.columns
            ]
            vol_20_avg = vol_df.rolling(20, min_periods=10).mean().iloc[-1]
            vol_latest = vol_df.iloc[-1]
            vol_ratio = vol_latest / vol_20_avg.replace(0, np.nan)
            rank_df["Volume"] = rank_df["Symbol"].map(
                lambda s: (
                    "High"
                    if vol_ratio.get(s, 0) >= 1.5
                    else ("Low" if vol_ratio.get(s, 0) < 0.7 else "Normal")
                )
            )
        else:
            rank_df["Volume"] = "Normal"

        # Market Caps & Flags
        rank_df["Market Cap (Cr)"] = rank_df["Symbol"].map(
            lambda s: (
                (market_caps.get(s, 0) / 1e7)
                if pd.notna(market_caps.get(s))
                else np.nan
            )
        )
        rank_df["Short History"] = rank_df["Symbol"].map(
            lambda s: "Yes" if self._valid_counts.get(s, 0) < 126 else "No"
        )
        rank_df["FFill %"] = rank_df["Symbol"].map(self.ffill_pct.to_dict()).fillna(0.0)
        rank_df["Data Gap"] = rank_df["FFill %"].map(lambda p: "🔴" if p > 10.0 else "")

        # System 2 Exp Regression Rank
        if compute_exp_reg:
            exp_scores = self.calculate_exp_regression(126)
            if not exp_scores.empty:
                exp_latest = exp_scores.iloc[-1]
                exp_rank = exp_latest.rank(ascending=False, method="min")
                rank_df["Exp Rank"] = rank_df["Symbol"].map(exp_rank.to_dict())

        return rank_df.sort_values("Rank").reset_index(drop=True)

    # ── Industry Rankings ────────────────────────────────────────────────────
    def get_industry_rankings(
        self,
        rank_df: pd.DataFrame,
        industry_col: str = "Industry",
    ) -> pd.DataFrame:
        """Aggregates stock ranks into institutional industry rankings."""
        if industry_col not in rank_df.columns:
            return pd.DataFrame()

        groups = rank_df.groupby(industry_col)
        rows: list[dict[str, Any]] = []
        for ind_name, grp in groups:
            if len(grp) < 2 or not ind_name or str(ind_name).strip() in ("", "nan"):
                continue
            sorted_g = grp.sort_values("Rank")
            top_syms = sorted_g["Symbol"].tolist()
            rows.append(
                {
                    "Industry": ind_name,
                    "Stocks": len(grp),
                    "Avg Score": grp["Score"].mean() if "Score" in grp.columns else 0.0,
                    "3M Return": (
                        grp["3M Return"].median() if "3M Return" in grp.columns else 0.0
                    ),
                    "6M Return": (
                        grp["6M Return"].median() if "6M Return" in grp.columns else 0.0
                    ),
                    "Top 1": top_syms[0] if len(top_syms) > 0 else "—",
                    "Top 2": top_syms[1] if len(top_syms) > 1 else "—",
                    "Top 3": top_syms[2] if len(top_syms) > 2 else "—",
                }
            )

        ind_df = pd.DataFrame(rows)
        if ind_df.empty:
            return ind_df
        ind_df["Rank"] = (
            ind_df["Avg Score"].rank(ascending=False, method="min").astype(int)
        )
        return (
            ind_df.sort_values("Rank")
            .drop(columns=["Avg Score"])
            .reset_index(drop=True)
        )

    # ── Multi-Strategy Overlay ───────────────────────────────────────────────
    def get_multi_strategy_overlay(
        self,
        rank_df: pd.DataFrame,
        top_n: int = 50,
    ) -> pd.DataFrame:
        """Finds high-conviction consensus picks across alternative momentum systems."""
        res_ranks = self.calculate_residual_momentum(window=126)
        ind_ranks = self.calculate_industry_relative(rank_df, "Industry")
        acc_ranks = self.calculate_momentum_acceleration()

        cols = [
            "Rank",
            "Symbol",
            "Industry",
            "CMP",
            "3M Return",
            "6M Return",
            "Persistence",
            "ATR %",
        ]
        overlay = rank_df[[c for c in cols if c in rank_df.columns]].copy()
        overlay.rename(columns={"Rank": "Composite Rank"}, inplace=True)
        overlay["Sharpe Rank"] = overlay["Composite Rank"]
        overlay["Residual Rank"] = overlay["Symbol"].map(res_ranks.to_dict())
        overlay["Ind-Rel Rank"] = overlay["Symbol"].map(ind_ranks.to_dict())
        overlay["Accel Rank"] = overlay["Symbol"].map(acc_ranks.to_dict())

        overlay["In All Top"] = (
            (overlay["Residual Rank"] <= top_n)
            & (overlay["Ind-Rel Rank"] <= top_n)
            & (overlay["Accel Rank"] <= top_n)
        )
        return overlay.sort_values("Composite Rank").reset_index(drop=True)
