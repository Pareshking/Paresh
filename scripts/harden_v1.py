from pathlib import Path
import re


def replace_regex(path: str, pattern: str, replacement: str) -> None:
    p = Path(path)
    text = p.read_text()
    out, n = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if n == 0 and replacement not in text:
        return
    p.write_text(out)


# Calendar-month horizons are [1, 3, 6, 9, 12]. The backtester passes
# these values directly to the canonical calendar-period helper.
bt = Path("src/engine/backtester.py")
b = bt.read_text().replace("int(round(w_period / 21))", "int(w_period)")
old = '''            ind_map = sec_map
            ind_scores: dict[str, list[float]] = {}
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

# Winsorize raw cross-sectional scores before Z-score normalization.
cm = Path("src/engine/calendar_momentum.py")
pattern = r"        mean_ = score\.mean\(axis=1\)\n        std_ = score\.std\(axis=1\)\.replace\(0, np\.nan\)\n        z_score = score\.sub\(mean_, axis=0\)\.div\(std_, axis=0\)\.clip\(-3\.0, 3\.0\)"
replacement = '''        z_rows = []
        for _, row in score.iterrows():
            clean = row.dropna()
            if len(clean) < 3 or float(clean.std()) == 0.0:
                z_rows.append(pd.Series(0.0, index=score.columns))
                continue
            raw_mean = float(clean.mean())
            raw_std = float(clean.std())
            clipped = clean.clip(raw_mean - 3.0 * raw_std, raw_mean + 3.0 * raw_std)
            clipped_std = float(clipped.std())
            z = (clipped - float(clipped.mean())) / (clipped_std + 1e-12)
            z_rows.append(z.reindex(score.columns).fillna(0.0))
        z_score = pd.DataFrame(z_rows, index=score.index, columns=score.columns).clip(-3.0, 3.0)'''
replace_regex("src/engine/calendar_momentum.py", pattern, replacement)

# Population daily dispersion for realized annualized portfolio volatility.
portfolio = Path("src/engine/portfolio.py")
p = portfolio.read_text().replace("realised = float(port.std() * np.sqrt(252))", "realised = float(port.std(ddof=0) * np.sqrt(252))")
portfolio.write_text(p)

# Remove only explicit stale R² methodology terminology. Do not touch ordinary
# implementation identifiers such as cs_r2, which are not methodology claims.
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
    for token in ("R²", "R^2", "R2"):
        text = text.replace(token, "")
    text = text.replace("Sharpe ×", "Sharpe")
    text = text.replace("R² multiplier", "smoothness multiplier")
    p.write_text(text)
