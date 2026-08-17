from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_method(text: str, method_name: str, new_method: str) -> str:
    marker = f"    def {method_name}"
    start = text.index(marker)
    next_pos = text.find("\n    def ", start + len(marker))
    if next_pos == -1:
        raise RuntimeError(f"Could not find end of {method_name}")
    return text[:start] + new_method.rstrip() + text[next_pos:]


momentum_path = ROOT / "src/engine/momentum.py"
text = momentum_path.read_text()
if "from src.engine.calendar_momentum import" not in text:
    text = text.replace(
        "from src.core.logger import logger\n",
        "from src.core.logger import logger\nfrom src.engine.calendar_momentum import (\n    _calendar_period_metrics,\n    calendar_start_positions,\n    latest_as_of_date,\n)\n",
        1,
    )

text = replace_method(
    text,
    "calculate_residual_momentum(",
    '''    def calculate_residual_momentum(\n        self,\n        benchmark_returns: pd.Series | None = None,\n        window: int = 126,\n        months: int | None = 6,\n    ) -> pd.Series:\n        """Compute residual alpha over a calendar-defined period by default.\n\n        ``window`` remains available for callers that explicitly request a\n        trading-row window by passing ``months=None``. The production 6M\n        model uses calendar months so weekends/holidays do not change the\n        economic horizon.\n        """\n        daily_ret = self.prices.pct_change(fill_method=None)\n        if benchmark_returns is None:\n            mkt_ret = daily_ret.mean(axis=1)\n        else:\n            mkt_ret = benchmark_returns.reindex(daily_ret.index).ffill()\n\n        if months is None:\n            start = max(0, len(daily_ret) - window)\n        else:\n            as_of = latest_as_of_date(pd.DatetimeIndex(daily_ret.index))\n            starts = calendar_start_positions(\n                pd.DatetimeIndex(daily_ret.index), months, latest_as_of=as_of\n            )\n            start = int(starts[-1])\n\n        ret_w = daily_ret.iloc[start:]\n        mkt_ret_w = mkt_ret.iloc[start:]\n        mkt_var = float(mkt_ret_w.var())\n\n        if mkt_var <= 1e-12 or np.isnan(mkt_var) or len(mkt_ret_w.dropna()) < 30:\n            ranks = pd.Series(np.nan, index=self.prices.columns)\n            self.residual_ranks = ranks\n            return ranks\n\n        covs = ret_w.apply(lambda col: col.cov(mkt_ret_w))\n        betas = covs / mkt_var\n        stock_mean = ret_w.mean()\n        mkt_mean = float(mkt_ret_w.mean())\n        alpha_ann = (stock_mean - betas * mkt_mean) * 252\n\n        if months is None:\n            min_history = min(window, 63)\n        else:\n            min_history = max(2, len(ret_w) // 4)\n        alpha_ann = alpha_ann.where(self._valid_counts >= min_history, np.nan)\n        ranks = alpha_ann.rank(ascending=False, method="min")\n        self.residual_ranks = ranks\n        return ranks\n''',
)

text = replace_method(
    text,
    "calculate_momentum_acceleration(",
    '''    def calculate_momentum_acceleration(self) -> pd.Series:\n        """Rank acceleration using calendar 1M/3M/6M/9M/12M horizons."""\n        zero_s = pd.Series(0.0, index=self.prices.columns)\n        as_of = latest_as_of_date(pd.DatetimeIndex(self.prices.index))\n        scores: dict[int, pd.Series] = {}\n        for months in (1, 3, 6, 9, 12):\n            _, _, sharpe, r2, _ = _calendar_period_metrics(\n                self.prices, self.log_ret, months, latest_as_of=as_of\n            )\n            scores[months] = (sharpe.iloc[-1] * r2.iloc[-1]).replace(\n                [np.inf, -np.inf], np.nan\n            )\n\n        s_1m = scores.get(1, zero_s)\n        s_3m = scores.get(3, zero_s)\n        s_6m = scores.get(6, zero_s)\n        s_9m = scores.get(9, zero_s)\n        s_12m = scores.get(12, zero_s)\n\n        short_term = (\n            0.10 * zscore_series(s_1m)\n            + 0.35 * zscore_series(s_3m)\n            + 0.55 * zscore_series(s_6m)\n        )\n        long_term = 0.45 * zscore_series(s_9m) + 0.55 * zscore_series(s_12m)\n        accel = short_term - long_term\n\n        ranks = accel.rank(ascending=False, na_option="bottom")\n        return ranks\n''',
)

text = replace_method(
    text,
    "compute_persistence(",
    '''    def compute_persistence(\n        self, window: int = 126, months: int | None = 6\n    ) -> pd.Series:\n        """Compute percentage of sessions with positive return in a 6M calendar window."""\n        if months is None:\n            ret = self.log_ret.iloc[-window:]\n        else:\n            as_of = latest_as_of_date(pd.DatetimeIndex(self.log_ret.index))\n            starts = calendar_start_positions(\n                pd.DatetimeIndex(self.log_ret.index), months, latest_as_of=as_of\n            )\n            ret = self.log_ret.iloc[int(starts[-1]) :]\n        pos = (ret > 0).sum()\n        total = ret.notna().sum().replace(0, np.nan)\n        return (pos / total * 100).round(1)\n''',
)

# Historical rank snapshots must also be calendar-based.
old = '''        # Historical Ranks (-1M: 21D ago, -3M: 63D ago)\n        n_rows = len(self.momentum_scores) if self.momentum_scores is not None else 0\n        if n_rows > 21 and self.momentum_scores is not None:\n            s_1m = self.momentum_scores.iloc[-22].where(valid_mask, np.nan)\n            r_1m = s_1m.rank(ascending=False, method="min")\n            rank_df["Rank (-1M)"] = rank_df["Symbol"].map(r_1m)\n            rank_df["Rank Δ 1M"] = rank_df["Rank (-1M)"] - rank_df["Rank"]\n        else:\n            rank_df["Rank (-1M)"] = np.nan\n            rank_df["Rank Δ 1M"] = np.nan\n\n        if n_rows > 63 and self.momentum_scores is not None:\n            s_3m = self.momentum_scores.iloc[-64].where(valid_mask, np.nan)\n            r_3m = s_3m.rank(ascending=False, method="min")\n            rank_df["Rank (-3M)"] = rank_df["Symbol"].map(r_3m)\n            rank_df["Rank Δ 3M"] = rank_df["Rank (-3M)"] - rank_df["Rank"]\n        else:\n            rank_df["Rank (-3M)"] = np.nan\n            rank_df["Rank Δ 3M"] = np.nan\n'''
new = '''        # Historical ranks use calendar 1M/3M snapshots rather than fixed rows.\n        n_rows = len(self.momentum_scores) if self.momentum_scores is not None else 0\n        if n_rows > 0 and self.momentum_scores is not None:\n            as_of = latest_as_of_date(pd.DatetimeIndex(self.momentum_scores.index))\n            starts = calendar_start_positions(\n                pd.DatetimeIndex(self.momentum_scores.index), 1, latest_as_of=as_of\n            )\n            idx_1m = int(starts[-1])\n            s_1m = self.momentum_scores.iloc[idx_1m].where(valid_mask, np.nan)\n            r_1m = s_1m.rank(ascending=False, method="min")\n            rank_df["Rank (-1M)"] = rank_df["Symbol"].map(r_1m)\n            rank_df["Rank Δ 1M"] = rank_df["Rank (-1M)"] - rank_df["Rank"]\n\n            starts = calendar_start_positions(\n                pd.DatetimeIndex(self.momentum_scores.index), 3, latest_as_of=as_of\n            )\n            idx_3m = int(starts[-1])\n            s_3m = self.momentum_scores.iloc[idx_3m].where(valid_mask, np.nan)\n            r_3m = s_3m.rank(ascending=False, method="min")\n            rank_df["Rank (-3M)"] = rank_df["Symbol"].map(r_3m)\n            rank_df["Rank Δ 3M"] = rank_df["Rank (-3M)"] - rank_df["Rank"]\n        else:\n            rank_df["Rank (-1M)"] = np.nan\n            rank_df["Rank Δ 1M"] = np.nan\n            rank_df["Rank (-3M)"] = np.nan\n            rank_df["Rank Δ 3M"] = np.nan\n'''
if old not in text:
    raise RuntimeError("Historical rank block not found")
text = text.replace(old, new, 1)

# Calendar 3M/6M drawdowns.
old = '''        # 3M & 6M Drawdowns\n        win_3m = min(63, len(close_src))\n        roll_max_3m = close_src.iloc[-win_3m:].cummax()\n        dd_3m = ((close_src.iloc[-win_3m:] - roll_max_3m) / roll_max_3m.replace(0, np.nan)).min() * 100\n        rank_df["Max DD 3M"] = rank_df["Symbol"].map(dd_3m.to_dict())\n\n        win_6m = min(126, len(close_src))\n        roll_max_6m = close_src.iloc[-win_6m:].cummax()\n        dd_6m = ((close_src.iloc[-win_6m:] - roll_max_6m) / roll_max_6m.replace(0, np.nan)).min() * 100\n        rank_df["Max DD 6M"] = rank_df["Symbol"].map(dd_6m.to_dict())\n'''
new = '''        # 3M & 6M drawdowns use calendar-defined windows.\n        close_idx = pd.DatetimeIndex(close_src.index)\n        as_of = latest_as_of_date(close_idx)\n        for months, label in ((3, "3M"), (6, "6M")):\n            starts = calendar_start_positions(close_idx, months, latest_as_of=as_of)\n            start = int(starts[-1])\n            period_close = close_src.iloc[start:]\n            roll_max = period_close.cummax()\n            dd = ((period_close - roll_max) / roll_max.replace(0, np.nan)).min() * 100\n            rank_df[f"Max DD {label}"] = rank_df["Symbol"].map(dd.to_dict())\n'''
if old not in text:
    raise RuntimeError("Drawdown block not found")
text = text.replace(old, new, 1)

text = text.replace(
    '        pers = self.compute_persistence(126)\n',
    '        pers = self.compute_persistence(months=6)\n',
    1,
)

momentum_path.write_text(text)

# The app fallback must use the same calendar start rule, not 126 rows.
app_path = ROOT / "app.py"
app = app_path.read_text()
app = app.replace(
    'from src.engine.calendar_momentum import apply_calendar_momentum\n',
    'from src.engine.calendar_momentum import apply_calendar_momentum, calendar_start_positions, latest_as_of_date\n',
    1,
)
old = '''        win_6m = min(126, len(close_p))\n        roll_max_6m = close_p.iloc[-win_6m:].cummax()\n        dd_6m = ((close_p.iloc[-win_6m:] - roll_max_6m) / roll_max_6m).min() * 100\n'''
new = '''        as_of = latest_as_of_date(pd.DatetimeIndex(close_p.index))\n        starts = calendar_start_positions(\n            pd.DatetimeIndex(close_p.index), 6, latest_as_of=as_of\n        )\n        period_close = close_p.iloc[int(starts[-1]) :]\n        roll_max_6m = period_close.cummax()\n        dd_6m = ((period_close - roll_max_6m) / roll_max_6m).min() * 100\n'''
if old not in app:
    raise RuntimeError("App 6M fallback block not found")
app = app.replace(old, new, 1)
app_path.write_text(app)

# Strategy walk-forward calculations: 1M/3M/6M/12M are calendar horizons.
strategy_path = ROOT / "src/ui/views/strategy_view.py"
strategy = strategy_path.read_text()
strategy = strategy.replace(
    'from src.engine.momentum import MomentumEngine\n',
    'from src.engine.momentum import MomentumEngine\nfrom src.engine.calendar_momentum import calendar_start_positions\n',
    1,
)
old = '''        # 1. Composite Sharpe x R2\n        log_ret_s = np.log(p_slice / p_slice.shift(1).replace(0, np.nan))\n        p_6m = p_slice.iloc[-126:] if len(p_slice) >= 126 else p_slice\n        ret_6m = (p_slice.iloc[-1] / p_slice.iloc[0].clip(lower=0.01)) - 1\n        vol_6m = (\n            log_ret_s.iloc[-126:].std() * np.sqrt(126)\n            if len(log_ret_s) >= 126\n            else log_ret_s.std() * np.sqrt(len(log_ret_s))\n        )\n        sharpe_6m = ret_6m / vol_6m.replace(0, np.nan)\n        log_p = np.log(p_6m.clip(lower=0.01))\n        t_arr = np.arange(len(log_p))\n        r2_6m = log_p.corrwith(pd.Series(t_arr, index=log_p.index, dtype=float)) ** 2\n        comp_score = sharpe_6m * r2_6m.fillna(0)\n\n        # 2. Residual Alpha\n        mkt_ret = daily_ret.loc[:t_start].mean(axis=1).iloc[-126:]\n        stk_ret = daily_ret.loc[:t_start].iloc[-126:]\n'''
new = '''        # 1. Composite Sharpe x R2 — calendar 6M window.\n        log_ret_s = np.log(p_slice / p_slice.shift(1).replace(0, np.nan))\n        idx_slice = pd.DatetimeIndex(p_slice.index)\n        start_6m = int(calendar_start_positions(idx_slice, 6, latest_as_of=t_start)[-1])\n        p_6m = p_slice.iloc[start_6m:]\n        ret_6m = (p_slice.iloc[-1] / p_slice.iloc[start_6m].clip(lower=0.01)) - 1\n        r_6m = log_ret_s.iloc[start_6m + 1 :]\n        vol_6m = r_6m.std() * np.sqrt(r_6m.notna().sum()).replace(0, np.nan)\n        sharpe_6m = ret_6m / vol_6m.replace(0, np.nan)\n        log_p = np.log(p_6m.clip(lower=0.01))\n        t_arr = np.arange(len(log_p))\n        r2_6m = log_p.corrwith(pd.Series(t_arr, index=log_p.index, dtype=float)) ** 2\n        comp_score = sharpe_6m * r2_6m.fillna(0)\n\n        # 2. Residual Alpha — same calendar 6M window.\n        mkt_ret = daily_ret.loc[:t_start].mean(axis=1).iloc[start_6m:]\n        stk_ret = daily_ret.loc[:t_start].iloc[start_6m:]\n'''
if old not in strategy:
    raise RuntimeError("Strategy 6M block not found")
strategy = strategy.replace(old, new, 1)
old = '''        # 4. Momentum Acceleration (Short vs Long)\n        ret_1m = (p_slice.iloc[-1] / p_slice.iloc[-min(21, len(p_slice))].clip(lower=0.01)) - 1\n        ret_3m = (p_slice.iloc[-1] / p_slice.iloc[-min(63, len(p_slice))].clip(lower=0.01)) - 1\n        ret_12m = (p_slice.iloc[-1] / p_slice.iloc[-min(252, len(p_slice))].clip(lower=0.01)) - 1\n        accel_score = (ret_1m + ret_3m) - ret_12m\n'''
new = '''        # 4. Momentum Acceleration — calendar 1M/3M/12M windows.\n        start_1m = int(calendar_start_positions(idx_slice, 1, latest_as_of=t_start)[-1])\n        start_3m = int(calendar_start_positions(idx_slice, 3, latest_as_of=t_start)[-1])\n        start_12m = int(calendar_start_positions(idx_slice, 12, latest_as_of=t_start)[-1])\n        ret_1m = (p_slice.iloc[-1] / p_slice.iloc[start_1m].clip(lower=0.01)) - 1\n        ret_3m = (p_slice.iloc[-1] / p_slice.iloc[start_3m].clip(lower=0.01)) - 1\n        ret_12m = (p_slice.iloc[-1] / p_slice.iloc[start_12m].clip(lower=0.01)) - 1\n        accel_score = (ret_1m + ret_3m) - ret_12m\n'''
if old not in strategy:
    raise RuntimeError("Strategy acceleration block not found")
strategy = strategy.replace(old, new, 1)
strategy_path.write_text(strategy)

print("Calendar-period consistency migration applied.")
