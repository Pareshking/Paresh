from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Fix the remaining calendar-metrics API residue left by the first pass.
p = ROOT / "src/engine/calendar_momentum.py"
s = p.read_text()
s = s.replace("Returns score, simple return, period-scale Sharpe, R² and start positions.", "Returns score, simple return, period-scale Sharpe and start positions.")
s = s.replace(") -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, np.ndarray]:", ") -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, np.ndarray]:", 1)
s = s.replace("    r2 = np.full((n_rows, n_cols), np.nan)\n", "")
start = s.find("        # R² of log price against observation time.")
if start >= 0:
    end = s.find("        score[end] = sharpe[end]", start)
    if end >= 0:
        s = s[:start] + s[end:]
s = s.replace("        pd.DataFrame(r2, index=frame_index, columns=prices.columns),\n", "")
s = s.replace("        score, returns, sharpe, r2, starts = _calendar_period_metrics(", "        score, returns, sharpe, starts = _calendar_period_metrics(")
s = s.replace('                "r2": r2.iloc[end],\n', "")
p.write_text(s)

# Replace Momentum System 1/2 completely so no R2 implementation remains.
p = ROOT / "src/engine/momentum.py"
s = p.read_text()
s = s.replace("Winsorized Z(Sharpe × R²)", "Winsorized Z-score")
s = s.replace("OLS slope annualized × R²", "annualized OLS slope")
start = s.find("    @staticmethod\n    def _mp(window: int)")
end = s.find("    # ── System 3:", start)
if start < 0 or end < 0:
    raise RuntimeError("Momentum System-1/System-2 block not found")
block = '''    @staticmethod
    def _mp(window: int) -> int:
        return window

    def _annualized_sharpe(self, w: int) -> pd.DataFrame:
        """Compute annualized period Sharpe without an R2 multiplier."""
        log_ret_w = np.log(self.prices / self.prices.shift(w).replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        daily_vol_w = (self.log_ret.rolling(w, min_periods=w).std() * np.sqrt(w)).replace(0, np.nan)
        return (log_ret_w / daily_vol_w).replace([np.inf, -np.inf], np.nan)

    def calculate_sharpe_momentum(self) -> pd.DataFrame:
        """Compute weighted cross-sectional Z-scored pure Sharpe momentum."""
        scores_by_w = {}
        for w in self.WINDOWS:
            raw_score = self._annualized_sharpe(w)
            short_mask = self._valid_counts < w
            if short_mask.any():
                raw_score.loc[:, short_mask] = np.nan
            mean_ = raw_score.mean(axis=1)
            std_ = raw_score.std(axis=1).replace(0, np.nan)
            scores_by_w[w] = raw_score.sub(mean_, axis=0).div(std_, axis=0).clip(-3.0, 3.0)
            if not self.prices.empty:
                idx_prev = max(0, len(self.prices) - 1 - min(w, len(self.prices) - 1))
                ret_w = self.prices.iloc[-1] / self.prices.iloc[idx_prev].replace(0, np.nan) - 1
                daily_vol = (self.log_ret.iloc[-w:].std() * np.sqrt(w)).replace(0, np.nan)
                self.period_metrics[w] = {"return": ret_w, "sharpe": np.log((1 + ret_w).clip(lower=0.001)) / daily_vol, "score": scores_by_w[w].iloc[-1]}
        total_weight = sum(self.weights)
        weights = [w / total_weight for w in self.weights] if total_weight > 0 else [0.2] * 5
        composite = pd.DataFrame(0.0, index=self.prices.index, columns=self.prices.columns)
        available = pd.DataFrame(0.0, index=self.prices.index, columns=self.prices.columns)
        for w, weight in zip(self.WINDOWS, weights):
            scores = scores_by_w[w]
            composite = composite.add(scores.fillna(0.0) * weight)
            available = available.add(scores.notna().astype(float) * weight)
        self.momentum_scores = composite.div(available.replace(0.0, np.nan))
        return self.momentum_scores

    def calculate_exp_regression(self, window: int = 126) -> pd.DataFrame:
        """Calculate annualized rolling exponential-regression slope."""
        log_p = np.log(self.prices.clip(lower=0.01))
        n = window
        sum_t = (n - 1) * n / 2.0
        sum_t2 = (n - 1) * n * (2 * n - 1) / 6.0
        var_t = sum_t2 - (sum_t ** 2) / n
        t_weights = np.arange(n) - sum_t / n
        conv_vals = convolve1d(log_p.fillna(0.0).values, t_weights[::-1], axis=0, mode="constant", cval=0.0, origin=-(n // 2))
        roll_t_y = pd.DataFrame(conv_vals, index=log_p.index, columns=log_p.columns)
        score = np.exp((roll_t_y / max(var_t, 1e-8)) * 252) - 1
        short_mask = self._valid_counts < window
        if short_mask.any():
            score.loc[:, short_mask] = np.nan
        self.exp_reg_scores = score
        return score

'''
s = s[:start] + block + s[end:]
p.write_text(s)

print("Remaining V1 R2 residue repaired.")
