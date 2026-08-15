"""
Quantitative Multi-System Momentum Engine — Hardened Production Core.

Systems:
  1. Multi-Window Sharpe & Sortino Momentum (Winsorized Z(Sharpe × R²) across 5 lookbacks)
  2. Vectorized Exponential Regression (OLS slope annualized × R² with analytical 1D convolution)
  3. Residual / Idiosyncratic Alpha (Market-beta stripped alpha)
  4. Industry-Relative Momentum (Sector-neutral outperformance)
  5. Momentum Acceleration (Short-term velocity vs long-term baseline)
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
from scipy.ndimage import convolve1d

from src.core.config import DEFAULT_LOOKBACK_WEIGHTS, MOMENTUM_WINDOWS
from src.core.logger import logger


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
    cleaned = df.loc[~holidays]
    return cleaned.ffill()


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
    if len(clean) < 3 or clean.std() == 0:
        return s
    mean, std = float(clean.mean()), float(clean.std())
    lower, upper = mean - std_limit * std, mean + std_limit * std
    return s.clip(lower=lower, upper=upper)


def zscore_series(s: pd.Series, winsorize: bool = True) -> pd.Series:
    """Calculates cross-sectional Z-scores with optional 3-sigma winsorization."""
    if s.empty or s.isna().all():
        return s
    clean = s.dropna()
    if len(clean) < 3 or clean.std() == 0:
        return pd.Series(0.0, index=s.index)
    if winsorize:
        clean = winsorize_series(clean, std_limit=3.0)
    mean_val = float(clean.mean())
    std_val = float(clean.std())
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
        return max(int(window * 0.8), 10)

    def _rolling_r2(self, window: int) -> pd.DataFrame:
        """Vectorized rolling Pearson correlation squared against linear time."""
        log_p = np.log(self.prices.clip(lower=0.01))
        t = pd.Series(np.arange(len(log_p)), index=log_p.index, dtype=float)
        return log_p.rolling(window, min_periods=self._mp(window)).corr(t) ** 2

    def _annualized_sharpe_r2(self, w: int) -> pd.DataFrame:
        """
        Computes annualized Sharpe * R2 using log return consistency:
        Sharpe = ln(P_t / P_{t-w}) / (std(daily_log_returns) * sqrt(w))
        """
        mp = self._mp(w)
        log_ret_w = np.log(
            self.prices / self.prices.shift(w).replace(0, np.nan)
        ).replace([np.inf, -np.inf], np.nan)

        daily_vol_w = (
            self.log_ret.rolling(w, min_periods=mp).std() * np.sqrt(w)
        ).replace(0, np.nan)

        sharpe_w = (log_ret_w / daily_vol_w).replace([np.inf, -np.inf], np.nan)
        r2_w = self._rolling_r2(w)
        return sharpe_w * r2_w

    def _annualized_sortino_r2(self, w: int) -> pd.DataFrame:
        """
        Computes annualized Sortino * R2 using downside deviation:
        Sortino = ln(P_t / P_{t-w}) / (downside_std * sqrt(w))
        """
        mp = self._mp(w)
        log_ret_w = np.log(
            self.prices / self.prices.shift(w).replace(0, np.nan)
        ).replace([np.inf, -np.inf], np.nan)

        downside_log = self.log_ret.clip(upper=0)
        downside_vol_w = (
            np.sqrt((downside_log**2).rolling(w, min_periods=mp).mean()) * np.sqrt(w)
        ).replace(0, np.nan)

        sortino_w = (log_ret_w / downside_vol_w).replace([np.inf, -np.inf], np.nan)
        r2_w = self._rolling_r2(w)
        return sortino_w * r2_w

    # ── System 1: Multi-Window Sharpe Momentum ───────────────────────────────
    def calculate_sharpe_momentum(self) -> pd.DataFrame:
        """Computes weighted Z-scored composite momentum across 5 windows."""
        scores_by_w: dict[int, pd.DataFrame] = {}
        for w in self.WINDOWS:
            raw_score = self._annualized_sharpe_r2(w)
            # Mask short-history tickers
            short_mask = self._valid_counts < w
            if short_mask.any():
                raw_score.loc[:, short_mask] = np.nan

            # Cross-sectional Winsorized Z-score normalization per day
            mean_ = raw_score.mean(axis=1)
            std_ = raw_score.std(axis=1).replace(0, np.nan)
            z_score = raw_score.sub(mean_, axis=0).div(std_, axis=0).clip(-3.0, 3.0)

            scores_by_w[w] = z_score

            # Store latest period diagnostics
            if not self.prices.empty:
                idx_prev = max(0, len(self.prices) - 1 - min(w, len(self.prices) - 1))
                ret_w = (self.prices.iloc[-1] / self.prices.iloc[idx_prev].replace(0, np.nan)) - 1
                daily_vol_latest = (self.log_ret.iloc[-w:].std() * np.sqrt(w)).replace(
                    0, np.nan
                )
                sharpe_latest = np.log((1 + ret_w).clip(lower=0.001)) / daily_vol_latest
                r2_latest = (
                    self._rolling_r2(w).iloc[-1]
                    if len(self.prices) >= w
                    else pd.Series(0.0, index=self.prices.columns)
                )
                self.period_metrics[w] = {
                    "return": ret_w,
                    "sharpe": sharpe_latest,
                    "r2": r2_latest,
                    "score": (
                        z_score.iloc[-1]
                        if not z_score.empty
                        else pd.Series(0.0, index=self.prices.columns)
                    ),
                }

        # Weighted combination
        tot_w = sum(self.weights)
        norm_weights = [w / tot_w for w in self.weights] if tot_w > 0 else [0.2] * 5

        composite = pd.DataFrame(
            0.0, index=self.prices.index, columns=self.prices.columns
        )
        for w, weight in zip(self.WINDOWS, norm_weights):
            if w in scores_by_w:
                composite = composite.add(scores_by_w[w].fillna(0.0) * weight)

        self.momentum_scores = composite
        return self.momentum_scores

    # ── System 2: Vectorized Exponential Regression ──────────────────────────
    def calculate_exp_regression(self, window: int = 126) -> pd.DataFrame:
        """
        Fast analytical rolling exponential regression via 1D convolution:
        Score = (exp(beta * 252) - 1) * R^2
        Calculated in milliseconds with zero Python loop bottlenecks.
        """
        log_p = np.log(self.prices.clip(lower=0.01))
        n = window
        sum_t = (n - 1) * n / 2.0
        sum_t2 = (n - 1) * n * (2 * n - 1) / 6.0
        var_t = sum_t2 - (sum_t**2) / n
        t_weights = np.arange(n) - (sum_t / n)

        # Vectorized 1D convolution along time axis
        conv_vals = convolve1d(
            log_p.fillna(0.0).values,
            t_weights[::-1],
            axis=0,
            mode="constant",
            cval=0.0,
            origin=-(n // 2),
        )
        roll_t_y = pd.DataFrame(conv_vals, index=log_p.index, columns=log_p.columns)

        slope_daily = roll_t_y / max(var_t, 1e-8)
        ann_return = np.exp(slope_daily * 252) - 1
        r2 = self._rolling_r2(window)
        score = ann_return * r2

        short_mask = self._valid_counts < window
        if short_mask.any():
            score.loc[:, short_mask] = np.nan

        self.exp_reg_scores = score
        return score

    # ── System 3: Residual / Idiosyncratic Momentum ──────────────────────────
    def calculate_residual_momentum(
        self,
        benchmark_returns: pd.Series | None = None,
        window: int = 126,
    ) -> pd.Series:
        """
        Computes 6M annualized idiosyncratic residual alpha:
        alpha = (mu_stock - beta * mu_market) * 252
        """
        daily_ret = self.prices.pct_change(fill_method=None)
        if benchmark_returns is None:
            mkt_ret = daily_ret.mean(axis=1)
        else:
            mkt_ret = benchmark_returns.reindex(daily_ret.index).ffill()

        mkt_ret_w = mkt_ret.iloc[-window:]
        mkt_var = float(mkt_ret_w.var())

        if mkt_var <= 1e-12 or np.isnan(mkt_var) or len(mkt_ret_w) < 30:
            ranks = pd.Series(np.nan, index=self.prices.columns)
            self.residual_ranks = ranks
            return ranks

        ret_w = daily_ret.iloc[-window:]
        covs = ret_w.apply(lambda col: col.cov(mkt_ret_w))
        betas = covs / mkt_var

        stock_mean = ret_w.mean()
        mkt_mean = float(mkt_ret_w.mean())
        alpha_ann = (stock_mean - betas * mkt_mean) * 252

        alpha_ann = alpha_ann.where(self._valid_counts >= min(window, 63), np.nan)
        ranks = alpha_ann.rank(ascending=False, method="min")
        self.residual_ranks = ranks
        return ranks

    # ── System 4: Industry-Relative Momentum ─────────────────────────────────
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

        ind_avg = score_df.groupby("Industry")["Score"].transform("mean")
        rel_score = score_df["Score"] - ind_avg

        ranks = pd.Series(rel_score.values, index=score_df["Symbol"]).rank(
            ascending=False, na_option="bottom"
        )
        self.ind_rel_ranks = ranks
        return ranks

    # ── System 5: Momentum Acceleration ──────────────────────────────────────
    def calculate_momentum_acceleration(self) -> pd.Series:
        """
        Measures short-term acceleration vs long-term baseline:
        Accel = (0.10*1M + 0.35*3M + 0.55*6M) - (0.45*9M + 0.55*12M)
        """
        zero_s = pd.Series(0.0, index=self.prices.columns)
        s_1m = (
            self._annualized_sharpe_r2(21).iloc[-1]
            if len(self.prices) >= 21
            else zero_s
        )
        s_3m = (
            self._annualized_sharpe_r2(63).iloc[-1]
            if len(self.prices) >= 63
            else zero_s
        )
        s_6m = (
            self._annualized_sharpe_r2(126).iloc[-1]
            if len(self.prices) >= 126
            else zero_s
        )
        s_9m = (
            self._annualized_sharpe_r2(189).iloc[-1]
            if len(self.prices) >= 189
            else zero_s
        )
        s_12m = (
            self._annualized_sharpe_r2(252).iloc[-1]
            if len(self.prices) >= 252
            else zero_s
        )

        short_term = (
            0.10 * zscore_series(s_1m)
            + 0.35 * zscore_series(s_3m)
            + 0.55 * zscore_series(s_6m)
        )
        long_term = 0.45 * zscore_series(s_9m) + 0.55 * zscore_series(s_12m)
        accel = short_term - long_term

        accel = accel.where(self._valid_counts >= 63, np.nan)
        ranks = accel.rank(ascending=False, na_option="bottom")
        return ranks

    # ── ATR Volatility & Dual Trailing Stops ──────────────────────────────────
    def compute_atr_and_stops(
        self,
        period: int = 14,
        atr_mult: float = 2.0,
        chand_mult: float = 3.0,
    ) -> pd.DataFrame:
        """Vectorized ATR, 2xATR Stop Loss, and 3xATR Chandelier Exits."""
        tr1 = self.high - self.low
        tr2 = (self.high - self.close.shift(1)).abs()
        tr3 = (self.low - self.close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3]).groupby(level=0).max()

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
    def compute_persistence(self, window: int = 126) -> pd.Series:
        """Computes % of trading sessions with positive return in lookback."""
        pos = (self.log_ret.iloc[-window:] > 0).sum()
        total = self.log_ret.iloc[-window:].notna().sum().replace(0, np.nan)
        return (pos / total * 100).round(1)

    # ── Master Rankings Builder ──────────────────────────────────────────────
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
            self.calculate_sharpe_momentum()

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

        # Historical Ranks (-1M: 21D ago, -3M: 63D ago)
        n_rows = len(self.momentum_scores) if self.momentum_scores is not None else 0
        if n_rows > 21 and self.momentum_scores is not None:
            s_1m = self.momentum_scores.iloc[-22].where(valid_mask, np.nan)
            r_1m = s_1m.rank(ascending=False, method="min")
            rank_df["Rank (-1M)"] = rank_df["Symbol"].map(r_1m)
            rank_df["Rank Δ 1M"] = rank_df["Rank (-1M)"] - rank_df["Rank"]
        else:
            rank_df["Rank (-1M)"] = np.nan
            rank_df["Rank Δ 1M"] = np.nan

        if n_rows > 63 and self.momentum_scores is not None:
            s_3m = self.momentum_scores.iloc[-64].where(valid_mask, np.nan)
            r_3m = s_3m.rank(ascending=False, method="min")
            rank_df["Rank (-3M)"] = rank_df["Symbol"].map(r_3m)
            rank_df["Rank Δ 3M"] = rank_df["Rank (-3M)"] - rank_df["Rank"]
        else:
            rank_df["Rank (-3M)"] = np.nan
            rank_df["Rank Δ 3M"] = np.nan

        # CMP & Technical Signals
        close_src = (
            close_prices_df if close_prices_df is not None else self.close
        ).ffill()
        high_src = (high_prices_df if high_prices_df is not None else self.high).ffill()

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

        # 3M & 6M Metrics
        for w, label in [(63, "3M"), (126, "6M")]:
            if w in self.period_metrics:
                m = self.period_metrics[w]
                rank_df[f"{label} Return"] = rank_df["Symbol"].map(m["return"])
                rank_df[f"{label} Sharpe"] = rank_df["Symbol"].map(m["sharpe"])
                rank_df[f"{label} R2"] = rank_df["Symbol"].map(m["r2"])

        # 3M & 6M Drawdowns
        win_3m = min(63, len(close_src))
        roll_max_3m = close_src.iloc[-win_3m:].cummax()
        dd_3m = ((close_src.iloc[-win_3m:] - roll_max_3m) / roll_max_3m.replace(0, np.nan)).min() * 100
        rank_df["Max DD 3M"] = rank_df["Symbol"].map(dd_3m.to_dict())

        win_6m = min(126, len(close_src))
        roll_max_6m = close_src.iloc[-win_6m:].cummax()
        dd_6m = ((close_src.iloc[-win_6m:] - roll_max_6m) / roll_max_6m.replace(0, np.nan)).min() * 100
        rank_df["Max DD 6M"] = rank_df["Symbol"].map(dd_6m.to_dict())

        # ATR & Stops
        atr_df = self.compute_atr_and_stops()
        for c in ["ATR", "ATR %", "Stop Loss", "Chand Exit"]:
            rank_df[c] = rank_df["Symbol"].map(atr_df[c].to_dict())

        # Persistence
        pers = self.compute_persistence(126)
        rank_df["Persistence"] = rank_df["Symbol"].map(pers.to_dict())

        # Volume Signal
        if self.volume is not None and not self.volume.empty:
            vol_df = self.volume.ffill()
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
