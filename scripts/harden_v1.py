from pathlib import Path
import re


def replace_regex(path: str, pattern: str, replacement: str) -> None:
    p = Path(path)
    text = p.read_text()
    out, n = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if n == 0:
        raise SystemExit(f"Expected pattern not found in {path}; refusing blind edit")
    p.write_text(out)


bt = Path("src/engine/backtester.py")
b = bt.read_text().replace("int(round(w_period / 21))", "int(w_period)")
old = '''            ind_map = sec_map
            ind_scores: dict[str, list[float]] = []
            for sym, sc in composite_score.items():
                ind_scores.setdefault(ind_map.get(sym, "Other"), []).append(sc)
            ind_means = {k: np.nanmean(v) for k, v in ind_scores.items()}
            ind_rel = composite_score - composite_score.index.map(
                lambda s: ind_means.get(ind_map.get(s, "Other"), 0)
            )'''
new = '''            ind_map = sec_map
            industry_labels = pd.Series({sym: ind_map.get(sym, "Other") for sym in composite_score.index})
            industry_sum = composite_score.groupby(industry_labels).transform("sum")
            industry_count = composite_score.groupby(industry_labels).transform("count")
            peer_sum = industry_sum - composite_score
            peer_count = industry_count - composite_score.notna().astype(int)
            peer_mean = peer_sum.div(peer_count.replace(0, np.nan))
            ind_rel = composite_score - peer_mean'''
if old in b:
    b = b.replace(old, new, 1)
bt.write_text(b)

cm = Path("src/engine/calendar_momentum.py")
pattern = r"        mean_ = score\.mean\(axis=1\)\n        std_ = score\.std\(axis=1\)\.replace\(0, np\.nan\)\n        z_score = score\.sub\(mean_, axis=0\)\.div\(std_, axis=0\)\.clip\(-3\.0, 3\.0\)"
replacement = '''        z_rows = []
        for _, row in score.iterrows():
            clean = row.dropna()
            if len(clean) < 3 or float(clean.std(ddof=0)) == 0.0:
                z_rows.append(pd.Series(0.0, index=score.columns))
                continue
            raw_mean = float(clean.mean())
            raw_std = float(clean.std(ddof=0))
            clipped = clean.clip(raw_mean - 3.0 * raw_std, raw_mean + 3.0 * raw_std)
            clipped_std = float(clipped.std(ddof=0))
            z = (clipped - float(clipped.mean())) / (clipped_std + 1e-12)
            z_rows.append(z.reindex(score.columns).fillna(0.0))
        z_score = pd.DataFrame(z_rows, index=score.index, columns=score.columns).clip(-3.0, 3.0)'''
replace_regex("src/engine/calendar_momentum.py", pattern, replacement)
# Standardize calendar-period realized dispersion to population variance.
cm_text = cm.read_text()
cm_text = cm_text.replace(
    "sample_var = (rs2 - rn * mean_r * mean_r) / np.where(rn > 1, rn - 1, np.nan)",
    "population_var = (rs2 / np.where(rn > 0, rn, np.nan)) - (mean_r * mean_r)",
)
cm_text = cm_text.replace("daily_sd = np.sqrt(np.maximum(sample_var, 0.0))", "daily_sd = np.sqrt(np.maximum(population_var, 0.0))")
cm.write_text(cm_text)

portfolio = Path("src/engine/portfolio.py")
p = portfolio.read_text()
p = p.replace("self.returns[valid].iloc[-window:].std() * np.sqrt(252)", "self.returns[valid].iloc[-window:].std(ddof=0) * np.sqrt(252)")
p = p.replace("realised = float(port.std() * np.sqrt(252))", "realised = float(port.std(ddof=0) * np.sqrt(252))")
portfolio.write_text(p)

# Pure System-1 Sharpe helper: population rolling daily dispersion.
mom = Path("src/engine/momentum.py")
m = mom.read_text()
m = m.replace("self.log_ret.rolling(w, min_periods=w).std() * np.sqrt(w)", "self.log_ret.rolling(w, min_periods=w).std(ddof=0) * np.sqrt(w)")
m = m.replace("self.log_ret.iloc[-w:].std() * np.sqrt(w)", "self.log_ret.iloc[-w:].std(ddof=0) * np.sqrt(w)")
old_metrics = '''        # 3M & 6M Metrics
        for w, label in [(63, "3M"), (126, "6M")]:
            if w in self.period_metrics:
                m = self.period_metrics[w]
                rank_df[f"{label} Return"] = rank_df["Symbol"].map(m["return"])
                rank_df[f"{label} Sharpe"] = rank_df["Symbol"].map(m["sharpe"])
'''
new_metrics = '''        # 3M & 6M Metrics use the canonical calendar-period engine.
        as_of_metrics = latest_as_of_date(pd.DatetimeIndex(self.prices.index))
        for months, label in ((3, "3M"), (6, "6M")):
            _, cal_ret, cal_sharpe, _ = _calendar_period_metrics(
                self.prices, self.log_ret, months, latest_as_of=as_of_metrics
            )
            rank_df[f"{label} Return"] = rank_df["Symbol"].map(cal_ret.iloc[-1].to_dict())
            rank_df[f"{label} Sharpe"] = rank_df["Symbol"].map(cal_sharpe.iloc[-1].to_dict())
'''
if old_metrics not in m:
    raise SystemExit("Expected 3M/6M metric block not found")
m = m.replace(old_metrics, new_metrics, 1)
m = m.replace(
    "        close_src = (\n            close_prices_df if close_prices_df is not None else self.close\n        ).ffill()\n        high_src = (high_prices_df if high_prices_df is not None else self.high).ffill()",
    "        close_src = (\n            close_prices_df if close_prices_df is not None else self.close\n        ).copy()\n        high_src = (high_prices_df if high_prices_df is not None else self.high).copy()",
    1,
)
mom.write_text(m)

for rel in [
    "src/engine/momentum.py",
    "src/engine/calendar_momentum.py",
    "src/engine/backtester.py",
    "src/ui/views/ranking_view.py",
    "src/ui/views/backtest_view.py",
    "README.md",
    "src/ui/views/guide_view.py",
]:
    p = Path(rel)
    text = p.read_text()
    for token in ("R²", "R^2", "R2", "r2"):
        text = text.replace(token, "")
    text = text.replace("Sharpe ×", "Sharpe")
    text = text.replace("R² multiplier", "smoothness multiplier")
    p.write_text(text)

charts = Path("src/ui/charts.py")
c = charts.read_text()
old_drop = '    valid_df = rank_df.dropna(subset=[taxonomy_col, return_col, "Symbol"]).copy()'
new_drop = '''    required = [taxonomy_col, "Symbol"]
    if return_col not in rank_df.columns:
        fallback = "6M Return" if "6M Return" in rank_df.columns else "3M Return" if "3M Return" in rank_df.columns else None
        if fallback is None:
            st.info("Insufficient return data for Treemap.")
            return
        return_col = fallback
    valid_df = rank_df.dropna(subset=required + [return_col]).copy()'''
if old_drop not in c:
    raise SystemExit("Expected Treemap dropna block not found")
c = c.replace(old_drop, new_drop, 1)
c = c.replace('        min_r = valid_df["3M Return"].min()', '        min_r = valid_df[return_col].min()', 1)
c = c.replace('        valid_df["Tile_Weight"] = ((valid_df["3M Return"] + offset) * 1000).clip(', '        valid_df["Tile_Weight"] = ((valid_df[return_col] + offset) * 1000).clip(', 1)
charts.write_text(c)

# Replace deprecated HTML calls with current st.html for ordinary HTML strings.
for path in Path(".").rglob("*.py"):
    if ".git" in path.parts or path.as_posix().startswith(".venv/"):
        continue
    text = path.read_text(errors="ignore")
    if "st.components.v1.html" in text:
        text = text.replace("st.components.v1.html", "st.html")
        path.write_text(text)
