"""S223 (a), read-only research (24 Nov 2026): the record's rules with special dividends of 2% or more taken as return
(NSE's price-index line) against today's 10% line.

    python scripts/research/special_dividend_line.py <nse_long_close.parquet> <nse_actions_pack.parquet> \
        <nse_raw_pack.parquet> [special]

Without "special", every dividend of 2-10% is taken (not NSE's rule; kept for the comparison)."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts" / "research"))
import rebalance_rules_after_tax as rr
from src.loaders import nse_adjusted as na

long_p, act_p, raw_p = sys.argv[1:4]
close = pd.read_parquet(long_p)
if "date" in close.columns:
    close = close.set_index("date")
close.index = pd.DatetimeIndex(close.index)
raw = pd.read_parquet(raw_p, columns=["date", "mkt", "symbol", "close"])
raw = raw[raw["mkt"] == "N"]
rc = raw.pivot_table(index="date", columns="symbol", values="close", aggfunc="last")
rc.index = pd.DatetimeIndex(rc.index).astype("datetime64[ns]")
acts = pd.read_parquet(act_p)
divs = na._dividends(acts)
sp = acts[(acts["kind"] == "dividend") & acts["ex_date"].notna() & acts["purpose"].fillna("").str.upper().str.contains("SPECIAL")]
special = {(r.symbol, pd.Timestamp(r.ex_date).normalize()) for r in sp.itertuples(index=False)}
ONLY_SPECIAL = len(sys.argv) > 4 and sys.argv[4] == "special"
print("special-dividend rows:", len(special), "| mode:", "special only" if ONLY_SPECIAL else "every dividend")
extra = pd.DataFrame(1.0, index=close.index, columns=close.columns)
n = applied = 0
ys = []
for r in divs.itertuples(index=False):
    if r.symbol not in rc.columns or r.symbol not in close.columns or not (r.amount > 0):
        continue
    s = rc[r.symbol]
    day, move = na._move_at(s, r.date)
    if day is None:
        continue
    before = s[s.index < r.date].dropna()
    if before.empty:
        continue
    y = r.amount / float(before.iloc[-1])
    if not (0.02 <= y < na.LARGE_DIVIDEND):
        continue
    if ONLY_SPECIAL and (r.symbol, pd.Timestamp(r.date).normalize()) not in special:
        continue
    n += 1
    if move < 1 - y / 2 and day in extra.index:
        extra.at[day, r.symbol] *= move / (move + y)
        applied += 1; ys.append(y)
print(f"dividends 2%-10%: {n} found, {applied} applied (price fell by half the payout or more); median yield {np.median(ys) if ys else 0:.1%}")
close2 = close * na.factor_after(extra)
bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
out = {}
for name, c in (("10% (today)", close), ("2% (NSE's line)", close2)):
    res, _ = rr.run(c, bench, "nifty_500", "2010-01-01", "4 semi_reset")
    eq = res["equity_curve"]; eq = eq.iloc[:, 0] if isinstance(eq, pd.DataFrame) else eq
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1
    dd = (eq / eq.cummax() - 1).min()
    tb = res["tradebook"]
    last = tb[pd.to_datetime(tb["Period Start"]) == pd.to_datetime(tb["Period Start"]).max()]
    held = set(last[last["Action"].astype(str).str.contains("BUY|HOLD")]["Symbol"])
    out[name] = held
    print(f"{name}: CAGR {cagr:.2%}, max drawdown {dd:.1%}, {eq.index[0]:%d %b %Y} to {eq.index[-1]:%d %b %Y}, last book {len(held)} names")
a, b = out.values()
print(f"last book: {len(a & b)} names in both; only at 10%: {sorted(a - b)}; only at 2%: {sorted(b - a)}")
