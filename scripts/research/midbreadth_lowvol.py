"""Engine test of the one new state lead from regime_audit.py (S239, 28 Nov 2026): in months whose signal close had
40-60% of the Nifty 500 above its 200D EMA, the less volatile names in the book's pool did better (126-session
volatility, downside volatility and idiosyncratic volatility, t 3.0-3.6 over 61 months).

Fixed before running: at a mid-breadth signal, no NEW buy among the most volatile fifth of that day's names
(126-session volatility); other months unchanged. Tested alone, on top of skip 5, and on top of skip 5 + the Bollinger
entry block. Pass: >= +0.5 pts a year in the run and in both halves against the book it is added to, worst fall no
deeper, above the 90th percentile of a null (the same months, a random fifth blocked, 20 seeds).

    python scripts/research/midbreadth_lowvol.py <nse_long_close.parquet> <regime_dir with states.csv>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from combos_factorial import curve, pct_b  # noqa: E402
from rs_supertrend import run, stats  # noqa: E402
from src.engine import index_universe as iu  # noqa: E402


def main(close_path: str, regime_dir: str, seeds: int = 20) -> None:
    close = pd.read_parquet(close_path)
    close.index = pd.DatetimeIndex(close.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    cols = sorted(iu.ever_members(iu.index_history("nifty_500")) & set(close.columns))
    pf = close.loc[:, cols].astype("float64").ffill()
    st = pd.read_csv(Path(regime_dir) / "states.csv", index_col=0, parse_dates=True)
    mid = st.index[st["breadth"] == "mid"]
    vol = pf.pct_change(fill_method=None).rolling(126, min_periods=100).std(ddof=0)
    calm = vol.rank(axis=1, pct=True) <= 0.80
    gate = pd.DataFrame(True, index=pf.index, columns=pf.columns)
    gate.loc[mid] = calm.loc[mid]
    bb = pct_b(pf) <= 1.0
    print(f"mid-breadth signals: {len(mid)} of {len(st)}")
    for label, base_gate, skip in (("alone", None, 0), ("on skip 5", None, 5), ("on skip 5 + BB", bb, 5)):
        b = stats(curve(run(close, bench, base_gate, "entry", score_skip=skip)))
        g = gate if base_gate is None else (gate & base_gate)
        x = stats(curve(run(close, bench, g, "entry", score_skip=skip)))
        d = {k: x[k] - b[k] for k in ("a year %", "2010-17 %", "2018-26 %")}
        ok = all(v >= 0.5 for v in d.values()) and x["worst fall %"] >= b["worst fall %"]
        print(f"  {label:16s} {b['a year %']:.2f}% -> {x['a year %']:.2f}%  adds {d['a year %']:+.2f} "
              f"(2010-17 {d['2010-17 %']:+.2f}, 2018-26 {d['2018-26 %']:+.2f}); worst {b['worst fall %']:.1f} -> "
              f"{x['worst fall %']:.1f}  {'meets the halves rule' if ok else 'fails'}", flush=True)
        if label == "alone":
            rng = np.random.default_rng(9)
            null = []
            for _ in range(seeds):
                rg = pd.DataFrame(True, index=pf.index, columns=pf.columns)
                rg.loc[mid] = rng.random((len(mid), pf.shape[1])) >= 0.20
                null.append(stats(curve(run(close, bench, rg, "entry")))["a year %"] - b["a year %"])
            null = np.array(null)
            print(f"  NULL (same months, random fifth): mean {null.mean():+.2f}, p90 {np.percentile(null, 90):+.2f}, "
                  f"max {null.max():+.2f} -> real {d['a year %']:+.2f} is "
                  f"{'above' if d['a year %'] > np.percentile(null, 90) else 'inside'} p90", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
