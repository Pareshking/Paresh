from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text()
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1))


# 1) Calendar System-1 metrics: keep calendar dates and Sharpe, remove R2 entirely.
p = ROOT / "src/engine/calendar_momentum.py"
s = p.read_text()
s = s.replace(
    "The screener's 1M/3M/6M/9M/12M horizons are calendar periods, not fixed\n21/63/126/189/252-row windows.",
    "The screener's 1M/3M/6M/9M/12M horizons are calendar periods, not fixed\n21/63/126/189/252-row windows.",
)
s = s.replace(
    "Returns score, simple return, period-scale Sharpe, R² and start positions.",
    "Returns score, simple return, period-scale Sharpe and start positions.",
)
s = re.sub(
    r'\n    r2 = np\.full\(\(n_rows, n_cols\), np\.nan\)\n',
    '\n',
    s,
)
old = '''        # R² of log price against observation time. Correlation is invariant to\n        # shifting the time origin, so the global row index is sufficient.\n        ys = cs_y[end + 1] - cs_y[start]\n        ys2 = cs_y2[end + 1] - cs_y2[start]\n        xys = cs_xy[end + 1] - cs_xy[start]\n        yn = cs_yn[end + 1] - cs_yn[start]\n\n        x_sum = (end + start + 1) * (end - start) / 2.0\n        x2_sum = (\n            end * (end + 1) * (2 * end + 1)\n            - (start - 1) * start * (2 * start - 1)\n        ) / 6.0\n\n        cov_num = xys - x_sum * ys / np.where(yn > 0, yn, np.nan)\n        var_x = x2_sum - x_sum * x_sum / np.where(yn > 0, yn, np.nan)\n        var_y = ys2 - ys * ys / np.where(yn > 0, yn, np.nan)\n        corr2 = cov_num * cov_num / np.where(\n            (var_x > 0) & (var_y > 0), var_x * var_y, np.nan\n        )\n        r2[end] = np.clip(corr2, 0.0, 1.0)\n        score[end] = sharpe[end] * r2[end]\n'''
if old not in s:
    raise RuntimeError("calendar R2 block not found")
s = s.replace(old, "        score[end] = sharpe[end]\n", 1)
# Remove now-unused regression prefix sums and x/y validity helpers.
s = re.sub(r'\n    y = np\.log\(prices\.clip\(lower=0\.01\)\)\.to_numpy\(dtype=float\)\n    r = log_returns\.to_numpy\(dtype=float\)\n    valid_y = np\.isfinite\(y\)\n    valid_r = np\.isfinite\(r\)\n', '\n    r = log_returns.to_numpy(dtype=float)\n    valid_r = np.isfinite(r)\n', s)
s = re.sub(r'\n    x = np\.arange\(n_rows, dtype=float\)\n    cs_y = .*?\n    cs_y2 = .*?\n    cs_xy = .*?\n    cs_yn = .*?\n', '\n', s, flags=re.S)
s = re.sub(r'\n        score, returns, sharpe, r2, starts = _calendar_period_metrics\(', '\n        score, returns, sharpe, starts = _calendar_period_metrics(', s)
s = s.replace('            "r2": r2.iloc[end],\n', '')
p.write_text(s)


# 2) Momentum engine: composite momentum, acceleration and exponential regression no longer use R2.
p = ROOT / "src/engine/momentum.py"
s = p.read_text()
s = s.replace(
    "  1. Multi-Window Sharpe & Sortino Momentum (Winsorized Z(Sharpe × R²) across 5 lookbacks)\n  2. Vectorized Exponential Regression (OLS slope annualized × R² with analytical 1D convolution)",
    "  1. Multi-Window Sharpe & Sortino Momentum (Winsorized Z-score across 5 lookbacks)\n  2. Vectorized Exponential Regression (annualized OLS slope with analytical 1D convolution)",
)
s = re.sub(r'\n    @staticmethod\n    def _mp\(window: int\) -> int:\n        # Require the complete lookback window for each momentum/R² component\.\n        return window\n\n    def _rolling_r2\(.*?\n    def _annualized_sortino_r2\(.*?\n        return sortino_w \* r2_w\n', '\n    @staticmethod\n    def _mp(window: int) -> int:\n        # Require the complete lookback window for each momentum component.\n        return window\n\n    def _annualized_sharpe(self, w: int) -> pd.DataFrame:\n        """Compute annualized period Sharpe from log returns."""\n        mp = self._mp(w)\n        log_ret_w = np.log(\n            self.prices / self.prices.shift(w).replace(0, np.nan)\n        ).replace([np.inf, -np.inf], np.nan)\n        daily_vol_w = (\n            self.log_ret.rolling(w, min_periods=mp).std() * np.sqrt(w)\n        ).replace(0, np.nan)\n        return (log_ret_w / daily_vol_w).replace([np.inf, -np.inf], np.nan)\n\n    def _annualized_sortino(self, w: int) -> pd.DataFrame:\n        """Compute annualized period Sortino from downside log returns."""\n        mp = self._mp(w)\n        log_ret_w = np.log(\n            self.prices / self.prices.shift(w).replace(0, np.nan)\n        ).replace([np.inf, -np.inf], np.nan)\n        downside_log = self.log_ret.clip(upper=0)\n        downside_vol_w = (\n            np.sqrt((downside_log**2).rolling(w, min_periods=mp).mean()) * np.sqrt(w)\n        ).replace(0, np.nan)\n        sortino_w = (log_ret_w / downside_vol_w).replace([np.inf, -np.inf], np.nan)\n        return sortino_w\n', s, flags=re.S)
s = s.replace('raw_score = self._annualized_sharpe_r2(w)', 'raw_score = self._annualized_sharpe(w)')
s = re.sub(r'\n                r2_latest = \(\n                    self\._rolling_r2\(w\)\.iloc\[-1\]\n                    if len\(self\.prices\) >= w\n                    else pd\.Series\(0\.0, index=self\.prices\.columns\)\n                \)', '', s)
s = s.replace('                    "r2": r2_latest,\n', '')
s = s.replace('        Score = (exp(beta * 252) - 1) * R^2\n', '        Score = exp(beta * 252) - 1\n')
s = s.replace('        r2 = self._rolling_r2(window)\n        score = ann_return * r2\n', '        score = ann_return\n')
s = re.sub(r'\n            _, _, sharpe, r2, _ = _calendar_period_metrics\(\n                self\.prices, self\.log_ret, months, latest_as_of=as_of\n            \)\n            scores\[months\] = \(sharpe\.iloc\[-1\] \* r2\.iloc\[-1\]\)\.replace\(', '\n            _, _, sharpe, _ = _calendar_period_metrics(\n                self.prices, self.log_ret, months, latest_as_of=as_of\n            )\n            scores[months] = sharpe.iloc[-1].replace(', s)
s = re.sub(r'\n                rank_df\[f"\{label\} R2"\] = rank_df\["Symbol"\]\.map\(m\["r2"\]\)', '', s)
p.write_text(s)


# 3) Backtester: remove every R2-based ranking model and make Monthly (21D) date-aligned.
p = ROOT / "src/engine/backtester.py"
s = p.read_text()
s = s.replace(
    '    rebal_freq: int = 21,\n',
    '    rebal_freq: int = 21,\n',
)
old = '    start_offset = max_lb + ema_period\n    rebal_dates = list(range(start_offset, len(prices) - 2, rebal_freq))\n'
new = '''    start_offset = max_lb + ema_period\n\n    # Monthly rebalancing is calendar/date aligned: use the first available\n    # trading session of each calendar month after the warm-up period. This\n    # replaces the old fixed 21-row approximation, which drifted across\n    # months and could not reliably start on the first working day. Other\n    # explicit frequencies retain their trading-row cadence.\n    if rebal_freq == 21:\n        dates = pd.DatetimeIndex(prices.index)\n        month_keys = dates.to_period("M")\n        first_by_month = pd.Series(range(len(dates)), index=dates).groupby(month_keys).first()\n        rebal_dates = [\n            int(i)\n            for i in first_by_month.to_numpy()\n            if int(i) >= start_offset and int(i) < len(prices) - 2\n        ]\n    else:\n        rebal_dates = list(range(start_offset, len(prices) - 2, rebal_freq))\n'''
if old not in s:
    raise RuntimeError("backtest rebalancing block not found")
s = s.replace(old, new, 1)
# Composite/industry-relative ranking uses pure Sharpe now.
s = s.replace('            use_r2 = "No R²" not in ranking_method\n', '')
s = s.replace('                if use_r2:\n                    log_p = np.log(p_w.clip(lower=0.01))\n                    t_arr = np.arange(len(log_p))\n                    r2 = log_p.corrwith(pd.Series(t_arr, index=log_p.index, dtype=float)) ** 2\n                    raw_mom = sharpe * r2.fillna(0)\n                else:\n                    raw_mom = sharpe\n', '                raw_mom = sharpe\n')
# Industry-relative duplicate composite calculation.
s = re.sub(r'                log_p = np\.log\(p_w\.clip\(lower=0\.01\)\)\n                t_arr = np\.arange\(len\(log_p\)\)\n                r2 = log_p\.corrwith\(pd\.Series\(t_arr, index=log_p\.index, dtype=float\)\) \*\* 2\n                raw_mom = sharpe \* r2\.fillna\(0\)\n', '                raw_mom = sharpe\n', s)
# Remove the standalone R2 ranking branch.
s = re.sub(r'            elif "R²" in ranking_method:\n                .*?                score = sharpe \* r2\.fillna\(0\)\n', '', s, flags=re.S)
# Exp regression becomes slope-only.
s = re.sub(r'                r = log_p\.corrwith\(t_s\)\n                sy = log_p\.std\(\)\n                sx = float\(t_s\.std\(\)\)\n                beta = r \* \(sy / max\(sx, 1e-8\)\)\n                r2 = r\*\*2\n                score = \(np\.exp\(beta \* 252\) - 1\) \* r2\n', '                sy = log_p.std()\n                sx = float(t_s.std())\n                # OLS slope of log-price against time, annualized.\n                beta = (log_p.sub(log_p.mean()).mul(t_s - t_s.mean(), axis=0).sum() / max(float(((t_s - t_s.mean()) ** 2).sum()), 1e-8))\n                score = np.exp(beta * 252) - 1\n', s)
p.write_text(s)


# 4) Backtest UI: remove R2 model choices and explicitly label monthly as first trading day.
p = ROOT / "src/ui/views/backtest_view.py"
s = p.read_text()
s = s.replace('            21: "Monthly (21 Trading Days)",', '            21: "Monthly (First Trading Day)",')
s = s.replace('            "Composite Sharpe × R² (Config Weights)",', '            "Composite Sharpe (Config Weights)",')
s = s.replace('            "Multi-Window Pure Sharpe (No R²)",', '            "Multi-Window Pure Sharpe",')
s = s.replace('            "Exp Regression (R² Slope)",', '            "Exp Regression",')
s = s.replace('            "Sharpe × R² (Single Window)",\n', '')
s = s.replace('            21: "1M (21 Trading Days)",', '            21: "1M (Calendar Month)",')
s = s.replace('            63: "3M (63 Trading Days)",', '            63: "3M (Calendar Month × 3)",')
s = s.replace('            126: "6M (126 Trading Days)",', '            126: "6M (Calendar Month × 6)",')
s = s.replace('            189: "9M (189 Trading Days)",', '            189: "9M (Calendar Month × 9)",')
s = s.replace('            252: "12M (252 Trading Days)",', '            252: "12M (Calendar Month × 12)",')
s = s.replace('            <span>⏱️ <strong>Interval:</strong> <span style=\'color: #0f172a; font-weight: 600;\'>{bt_rebal} Trading Days</span></span>', "            <span>⏱️ <strong>Interval:</strong> <span style='color: #0f172a; font-weight: 600;'>{'Monthly · First Trading Day' if bt_rebal == 21 else f'{bt_rebal} Trading Days'}</span></span>")
p.write_text(s)


# 5) Screener table/card: remove R2 display columns and fields.
p = ROOT / "src/ui/views/ranking_view.py"
s = p.read_text()
s = s.replace('    "3M R2",\n', '').replace('    "6M R2",\n', '')
s = s.replace('    r2_3m = row.get("3M R2", 0)\n', '')
s = s.replace('            <div>\n                <span style="color: #64748b;">3M R²:</span>\n                <strong>{r2_3m:.2f}</strong>\n            </div>\n', '')
p.write_text(s)


# 6) Add regression-free/calendar-aligned tests.
test = ROOT / "tests/test_calendar_momentum.py"
s = test.read_text()
s = s.replace('    _, returns, _, _, starts = _calendar_period_metrics(', '    _, returns, _, starts = _calendar_period_metrics(')
s = s.replace('    _, _, _, _, starts = _calendar_period_metrics(', '    _, _, _, starts = _calendar_period_metrics(')
if 'def test_calendar_metric_returns_four_values_without_r2()' not in s:
    s += '''\n\ndef test_calendar_metric_returns_four_values_without_r2():\n    prices = _prices()\n    log_returns = np.log(prices / prices.shift(1))\n    result = _calendar_period_metrics(\n        prices, log_returns, 3, latest_as_of=pd.Timestamp("2026-08-17")\n    )\n    assert len(result) == 4\n\n'''
test.write_text(s)

# 7) Update the visible ranking labels in the main guide/config documentation where they are runtime-facing.
for rel in ["src/ui/views/guide_view.py", "src/ui/views/config_view.py", "README.md"]:
    p = ROOT / rel
    if p.exists():
        s = p.read_text()
        s = s.replace("Sharpe × R²", "Sharpe")
        s = s.replace("Sharpe * R²", "Sharpe")
        s = s.replace("R² Slope", "Slope")
        s = s.replace("R²", "")
        p.write_text(s)

# 8) Add a focused invariant test file for source-level removal and date-aligned monthly helper logic.
inv = ROOT / "tests/test_v1_r2_removed.py"
inv.write_text('''from pathlib import Path\n\n\nROOT = Path(__file__).resolve().parents[1]\n\n\ndef test_r2_removed_from_runtime_v1_files():\n    runtime_files = [\n        ROOT / "src/engine/momentum.py",\n        ROOT / "src/engine/calendar_momentum.py",\n        ROOT / "src/engine/backtester.py",\n        ROOT / "src/ui/views/ranking_view.py",\n        ROOT / "src/ui/views/backtest_view.py",\n    ]\n    forbidden = ("R²", "R2", "r2", "Sharpe ×")\n    for path in runtime_files:\n        text = path.read_text()\n        assert not any(token in text for token in forbidden), f"R2 residue in {path}"\n\n''')

print("V1 R2 removal + calendar-aligned monthly backtest edits prepared.")
