from pathlib import Path

p = Path("src/ui/views/strategy_view.py")
text = p.read_text()
text = text.replace("# 1. Composite Sharpe x R2 — calendar 6M window.", "# 1. Composite Sharpe — calendar 6M window.")
text = text.replace("vol_6m = r_6m.std() * np.sqrt(r_6m.notna().sum()).replace(0, np.nan)", "vol_6m = r_6m.std(ddof=0) * np.sqrt(r_6m.notna().sum()).replace(0, np.nan)")
old = '''        log_p = np.log(p_6m.clip(lower=0.01))
        t_arr = np.arange(len(log_p))
        r2_6m = log_p.corrwith(pd.Series(t_arr, index=log_p.index, dtype=float)) ** 2
        comp_score = sharpe_6m * r2_6m.fillna(0)'''
new = '''        comp_score = sharpe_6m'''
if old in text:
    text = text.replace(old, new, 1)
else:
    raise SystemExit("Expected R2 composite block not found")
text = text.replace(
    '        ind_means = {k: float(np.nanmean(v)) for k, v in ind_scores.items()}',
    '        ind_means = {k: float(np.nanmean(v)) for k, v in ind_scores.items() if np.isfinite(v).any()}',
)
p.write_text(text)
