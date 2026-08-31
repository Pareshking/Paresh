"""
Momentum Engine — single-system production core.

One system, the one that always drove every rank on screen: multi-window
Sharpe momentum, winsorized and z-scored across five calendar lookbacks.

Four alternative systems used to live here -- exponential regression, residual
alpha, industry-relative and momentum acceleration. None of them fed the
composite Rank; they produced extra columns and a Multi-Strategy tab. They were
removed deliberately: each carried its own failure modes (residual alpha reached
out to Yahoo mid-calculation), and none paid for the surface area it cost.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from src.core.config import DEFAULT_LOOKBACK_WEIGHTS, MOMENTUM_WINDOWS
from src.core.tickers import normalise_symbol
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
    if n_dropped == len(df):
        logger.warning(
            "Holiday cleanup would remove the entire dataset; preserving rows "
            "to avoid converting an upstream sparse/malformed cache into an empty "
            "production price history."
        )
        return df.copy()
    # Remove exchange-wide missing dates only; preserve stock-specific NaNs.
    return df.loc[~holidays]


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



def _normalize_ticker_cols(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None or df.empty:
        return df
    res = df.copy()
    res.columns = [normalise_symbol(c) for c in res.columns]
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

        # Clean holidays once from prices_df and share the resulting index across
        # all four frames. clean_holidays() performs an O(n×m) NaN scan; calling
        # it separately for each frame wastes 3 redundant full-matrix passes.
        # Exchange-wide holidays show as >70% NaN density in all frames equally,
        # so the prices_df mask is the correct and complete holiday mask.
        cleaned_p = clean_holidays(prices_df)
        norm_p = _normalize_ticker_cols(cleaned_p)
        self.prices: pd.DataFrame = norm_p if norm_p is not None else pd.DataFrame()
        _keep_idx = cleaned_p.index if cleaned_p is not None and not cleaned_p.empty else (
            prices_df.index if prices_df is not None else pd.Index([])
        )

        def _apply_mask(df: pd.DataFrame | None) -> pd.DataFrame | None:
            if df is None or df.empty:
                return df
            return df.loc[df.index.intersection(_keep_idx)]

        if high_df is not None:
            norm_h = _normalize_ticker_cols(_apply_mask(high_df))
            self.high: pd.DataFrame = norm_h if norm_h is not None else self.prices
        else:
            self.high = self.prices

        if low_df is not None:
            norm_l = _normalize_ticker_cols(_apply_mask(low_df))
            self.low: pd.DataFrame = norm_l if norm_l is not None else self.prices
        else:
            self.low = self.prices

        if close_df is not None:
            norm_c = _normalize_ticker_cols(_apply_mask(close_df))
            self.close: pd.DataFrame = norm_c if norm_c is not None else self.prices
        else:
            self.close = self.prices

        if volume_df is not None:
            self.volume: pd.DataFrame | None = _normalize_ticker_cols(_apply_mask(volume_df))
        else:
            self.volume = None

        self.weights: list[float] = list(weights) if weights is not None else list(self.DEFAULT_WEIGHTS)
        self._mcap_weights: pd.Series | None = market_cap_weights

        # Pre-calculate daily log returns
        self.log_ret: pd.DataFrame = np.log(self.prices / self.prices.shift(1).replace(0, np.nan))
        self._valid_counts: pd.Series = self.prices.notna().sum()

        self.momentum_scores: pd.DataFrame | None = None
        self.ranking_diagnostics: dict[str, int] = {}
        self.vol_mgd_ranks: pd.Series | None = None
        self.period_metrics: dict[int, dict[str, pd.Series]] = {}
        self.period_dates: dict[int, dict] = {}

    def calculate_sharpe_momentum(self) -> pd.DataFrame:
        """Compatibility entry point for the canonical calendar-month System-1 engine."""
        from src.engine.calendar_momentum import apply_calendar_momentum
        return apply_calendar_momentum(self)


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
        # Use the last row that has at least one real close. On a partial trading
        # day self.close.iloc[-1] may be all-NaN (data pulled before the close),
        # which turns ATR%, Stop Loss, and Chandelier Exit all NaN even though
        # the prior day's data is complete and usable.
        latest_close = self.close.dropna(how="all").iloc[-1]
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
            # Reuse the calendar start date already computed by apply_calendar_momentum
            # rather than re-running calendar_start_positions (another searchsorted pass).
            pd_entry = getattr(self, "period_dates", {}).get(months, {})
            actual_start = pd_entry.get("actual_start")
            if actual_start is not None and pd.notna(actual_start):
                ret = self.log_ret.loc[actual_start:]
            else:
                as_of = latest_as_of_date(pd.DatetimeIndex(self.log_ret.index))
                starts = calendar_start_positions(
                    pd.DatetimeIndex(self.log_ret.index), months, latest_as_of=as_of
                )
                ret = self.log_ret.iloc[int(starts[-1]):]
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

        # Why a ranking can come back empty. dropna below removes every symbol
        # without a score, so if no symbol cleared the 63-observation minimum
        # the result is zero rows -- which used to reach the views as an empty
        # frame and crash the Qualified tab instead of saying anything. Record
        # the counts so the failure is diagnosable rather than silent.
        universe_symbols = set(rank_df["Symbol"].astype(str))
        price_symbols = set(str(c) for c in self.prices.columns)
        self.ranking_diagnostics = {
            "universe": int(len(rank_df)),
            # Distinguishes a symbol-namespace mismatch from thin history. If
            # this is 0 while price columns exist, the price frame is keyed
            # differently from the universe (e.g. "RELIANCE.NS" vs "RELIANCE")
            # and every Score maps to NaN no matter how good the data is.
            "price_columns": int(len(price_symbols)),
            "symbols_matching_prices": int(len(universe_symbols & price_symbols)),
            "with_price_history": int((self._valid_counts > 0).sum()),
            "meeting_min_observations": int(valid_mask.sum()),
            "min_observations": 63,
            "scored": int(rank_df["Score"].notna().sum()),
        }

        rank_df = rank_df.dropna(subset=["Score"]).copy()
        rank_df["Rank"] = (
            rank_df["Score"].rank(ascending=False, method="min").astype(int)
        )
        rank_df["Composite Rank"] = rank_df["Rank"]

        # Historical ranks use calendar 1M/3M snapshots rather than fixed rows.
        # Precompute both windows in one pass to avoid two separate searchsorted calls.
        n_rows = len(self.momentum_scores) if self.momentum_scores is not None else 0
        if n_rows > 0 and self.momentum_scores is not None:
            score_idx = pd.DatetimeIndex(self.momentum_scores.index)
            as_of = latest_as_of_date(score_idx)
            hist_starts = {
                m: calendar_start_positions(score_idx, m, latest_as_of=as_of)
                for m in (1, 3)
            }
            idx_1m = int(hist_starts[1][-1])
            if idx_1m < n_rows:
                s_1m = self.momentum_scores.iloc[idx_1m].where(valid_mask, np.nan)
                r_1m = s_1m.rank(ascending=False, method="min")
                rank_df["Rank (-1M)"] = rank_df["Symbol"].map(r_1m)
                rank_df["Rank Δ 1M"] = rank_df["Rank (-1M)"] - rank_df["Rank"]
            else:
                rank_df["Rank (-1M)"] = np.nan
                rank_df["Rank Δ 1M"] = np.nan

            idx_3m = int(hist_starts[3][-1])
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
            normalise_symbol(c) for c in close_src.columns
        ]
        high_src.columns = [
            normalise_symbol(c) for c in high_src.columns
        ]

        # Drop any trailing rows that are all NaN
        valid_close_idx = close_src.dropna(how="all").index
        if not valid_close_idx.empty:
            close_src = close_src.loc[: valid_close_idx[-1]]
            high_src = high_src.loc[: valid_close_idx[-1]]

        latest_close = close_src.iloc[-1]
        rank_df["CMP"] = rank_df["Symbol"].map(latest_close.to_dict())

        # 50 EMA — vectorized: convert to dicts once, single lookup per symbol
        ema_50 = close_src.ewm(span=50, min_periods=30).mean().iloc[-1]
        _ema_d = ema_50.to_dict()
        _cls_d = latest_close.to_dict()

        def _above_ema(s: str) -> bool:
            e, c = _ema_d.get(s), _cls_d.get(s)
            return bool(c > e) if (e is not None and c is not None and pd.notna(e) and pd.notna(c)) else False

        def _pct_ema(s: str) -> float:
            e, c = _ema_d.get(s), _cls_d.get(s)
            if e is not None and c is not None and pd.notna(e) and pd.notna(c) and e > 0:
                return (c - e) / e * 100
            return np.nan

        rank_df["Above 50 EMA"] = rank_df["Symbol"].map(_above_ema)
        rank_df["% 50 EMA"] = rank_df["Symbol"].map(_pct_ema)

        # 52W High
        win_52w = min(252, len(high_src))
        _win = high_src.iloc[-win_52w:]
        high_52w = _win.max()
        # When the 52-week high was printed. The all-time high already carries
        # its date; a 52-week high without one is the same assertion in a
        # shorter window -- "12% off the high" reads very differently if that
        # high was last week rather than eleven months ago.
        # idxmax() raises "Encountered all NA values" on a column that is
        # entirely NaN -- which is exactly what a rate-limited ticker looks
        # like. Ask only the columns that have something to report.
        _has_any = _win.notna().any()
        high_52w_date = (
            _win.loc[:, _has_any[_has_any].index].idxmax()
            if bool(_has_any.any())
            else pd.Series(dtype="datetime64[ns]")
        )
        pct_high = ((latest_close - high_52w) / high_52w.replace(0, np.nan)) * 100
        rank_df["52W High"] = rank_df["Symbol"].map(high_52w.to_dict())
        rank_df["52W High Date"] = rank_df["Symbol"].map(
            {
                sym: (str(pd.Timestamp(d).date()) if pd.notna(d) else "")
                for sym, d in high_52w_date.items()
            }
        )
        rank_df["% High"] = rank_df["Symbol"].map(pct_high.to_dict())
        rank_df["Near 52W High"] = rank_df["% High"].map(
            lambda x: x >= -20.0 if pd.notna(x) else False
        )

        # ── All-time high ────────────────────────────────────────────────────
        # Same shape as % 52W High, over a far longer window. The snapshot is
        # built from ATH_HISTORY_PERIOD by the daily sync job; when it is
        # absent we fall back to the high water mark of the history in memory,
        # which is a TWO-YEAR high, not an all-time one. "ATH Source" records
        # which of the two produced the number so the column is never silently
        # mislabelled.
        from src.loaders.ath_loader import ath_series

        snapshot_ath = ath_series()
        window_ath = high_src.max()
        if not snapshot_ath.empty:
            # Row-wise max of the two. The snapshot is a day behind by
            # construction, so a stock printing a new high today must not read
            # as below its all-time high; and a symbol missing from the
            # snapshot still gets its in-window high rather than a NaN.
            ath = pd.concat(
                [snapshot_ath.reindex(window_ath.index), window_ath], axis=1
            ).max(axis=1)
            ath_source = "snapshot"
        else:
            ath = window_ath
            ath_source = "in_memory_window"

        pct_ath = ((latest_close - ath) / ath.replace(0, np.nan)) * 100
        rank_df["ATH"] = rank_df["Symbol"].map(ath.to_dict())
        rank_df["% ATH"] = rank_df["Symbol"].map(pct_ath.to_dict())
        rank_df["At ATH"] = rank_df["% ATH"].map(
            lambda x: x >= -5.0 if pd.notna(x) else False
        )
        rank_df["ATH Source"] = ath_source

        # When the peak was printed. Over a long window a single bad tick can
        # set a permanent phantom high, so the date travels with the number.
        from src.loaders.ath_loader import ath_date_series

        peak_dates = ath_date_series()
        if not peak_dates.empty:
            rank_df["ATH Date"] = rank_df["Symbol"].map(peak_dates.to_dict())
        else:
            rank_df["ATH Date"] = ""

        # Every canonical window, not just 3M and 6M. apply_calendar_momentum
        # has already computed all five and stored each period-end return and
        # Sharpe in self.period_metrics, so publishing the other three costs
        # nothing -- and reading them back is strictly better than recomputing
        # two of them here, which duplicated the work and gave the two paths a
        # chance to disagree. The fallback covers a caller that reached
        # get_rankings without going through apply_calendar_momentum.
        as_of_metrics = latest_as_of_date(pd.DatetimeIndex(self.prices.index))
        for months in MOMENTUM_WINDOWS:
            label = f"{months}M"
            cached = (self.period_metrics or {}).get(months) or {}
            cal_ret_last = cached.get("return")
            cal_sharpe_last = cached.get("sharpe")
            if not isinstance(cal_ret_last, pd.Series) or not isinstance(
                cal_sharpe_last, pd.Series
            ):
                _, cal_ret_last, cal_sharpe, _ = _calendar_period_metrics(
                    self.prices, self.log_ret, months, latest_as_of=as_of_metrics
                )
                cal_sharpe_last = cal_sharpe.iloc[-1]
            rank_df[f"{label} Return"] = rank_df["Symbol"].map(cal_ret_last.to_dict())
            rank_df[f"{label} Sharpe"] = rank_df["Symbol"].map(cal_sharpe_last.to_dict())

        # Drawdowns over the same calendar windows.
        # Precompute all start positions once; avoids one np.searchsorted pass per window.
        close_idx = pd.DatetimeIndex(close_src.index)
        as_of = latest_as_of_date(close_idx)
        starts_by_month = {
            m: calendar_start_positions(close_idx, m, latest_as_of=as_of)
            for m in MOMENTUM_WINDOWS
        }
        for months in MOMENTUM_WINDOWS:
            label = f"{months}M"
            start = int(starts_by_month[months][-1])
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
                normalise_symbol(c) for c in vol_df.columns
            ]
            vol_20_avg = vol_df.rolling(20, min_periods=10).mean().iloc[-1]
            vol_latest = vol_df.iloc[-1]
            vol_ratio = vol_latest / vol_20_avg.replace(0, np.nan)
            _vr_d = vol_ratio.to_dict()
            rank_df["Volume"] = rank_df["Symbol"].map(
                lambda s: (
                    # Default np.nan so stocks absent from vol_df get "Normal"
                    # (no data) rather than "Low" (thin volume). Python NaN
                    # comparisons evaluate to False on both branches.
                    "High" if _vr_d.get(s, np.nan) >= 1.5
                    else ("Low" if _vr_d.get(s, np.nan) < 0.7 else "Normal")
                )
            )
        else:
            rank_df["Volume"] = "Normal"

        # Market Caps & Flags
        #
        # Taken as published by NSE, from the daily snapshot. A market cap is
        # read here to place a stock in a size band, and a band is far wider
        # than a session's price move -- so re-scaling the figure to the
        # current price would add plumbing and a second failure mode without
        # changing any answer it is actually used for.
        _mc_d = market_caps.to_dict()
        rank_df["Market Cap (Cr)"] = rank_df["Symbol"].map(
            lambda s: (_mc_d[s] / 1e7) if pd.notna(_mc_d.get(s)) else np.nan
        )
        _vc_d = self._valid_counts.to_dict()
        rank_df["Short History"] = rank_df["Symbol"].map(
            lambda s: "Yes" if _vc_d.get(s, 0) < 126 else "No"
        )
        rank_df["FFill %"] = rank_df["Symbol"].map(self.ffill_pct.to_dict()).fillna(0.0)
        rank_df["Data Gap"] = rank_df["FFill %"].map(lambda p: "🔴" if p > 10.0 else "")


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

