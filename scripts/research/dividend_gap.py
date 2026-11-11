"""How much dividend income the momentum book gives up against the index it is
compared with (audit 11 Nov 2026, TODO S125; read-only research).

Every return on the site is price only, on both sides, so this gap is not in any
figure shown. It measures, from NSE's own corporate-action rows (the long file's
actions pack, release data-latest) and NSE's raw closes (the raw pack):

  book      the record's rules on the Nifty 500 from 2010 (six-monthly reset, the
            15% hold cap, 5% buys, as in cost_and_index_tax.py): each period's
            holdings at their weights, each dividend's amount over the raw close
            before its ex-date
  members   the same yield for an equal-weighted book of the Nifty 500's members
            on each date (point-in-time). Not the index, which is cap-weighted:
            equal weight is the like-for-like baseline for an equal-weight book.

Coverage: the actions pack is NSE's daily Bc files only, complete from 2020; the
summary is 2020-2025. Even there some dividends are missing (INFY shows one a year,
not two), so both yields read low; the gap between them is what this measures.

Dividends of 10% of the price or more are already in the strategy's prices
(nse_adjusted.LARGE_DIVIDEND), so they are counted separately. Weights are each
period's starting weights (drift inside a period is ignored).

Renamed stocks: dividends and raw closes are filed under the ticker of their day;
the book holds the latest ticker. The long file's report maps one to the other
(`renames_landed`), and members are asked for in the same latest-ticker form.

    python scripts/research/dividend_gap.py <nse_long_close.parquet> <nse_actions_pack.parquet> \
        <nse_raw_pack.parquet> <nse_long_report.json>
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import rebalance_rules_after_tax as rr  # noqa: E402
from src.engine import index_universe as iu  # noqa: E402
from src.engine.membership import members_on  # noqa: E402
from src.loaders.nse_adjusted import LARGE_DIVIDEND, _dividends  # noqa: E402

RULE = "4 semi_reset"


def dividend_yields(actions: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw[(raw["mkt"] == "N")].sort_values("date")
    close = raw.pivot_table(index="date", columns="symbol", values="close", aggfunc="last")
    close.index = pd.DatetimeIndex(close.index)
    rows = []
    for r in _dividends(actions).itertuples(index=False):
        if r.symbol not in close.columns or not (r.amount > 0):
            continue
        s = close[r.symbol]
        before = s[s.index < pd.Timestamp(r.date)].dropna()
        if before.empty or (pd.Timestamp(r.date) - before.index[-1]).days > 10:
            continue
        rows.append({"symbol": r.symbol, "date": pd.Timestamp(r.date), "y": float(r.amount) / float(before.iloc[-1])})
    return pd.DataFrame(rows)


def main(long_path: str, actions_path: str, raw_path: str, report_path: str) -> None:
    close = pd.read_parquet(long_path)
    if "date" in close.columns:
        close = close.set_index("date")
    close.index = pd.DatetimeIndex(close.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    res, _ = rr.run(close, bench, "nifty_500", "2010-01-01", RULE)
    tb = res["tradebook"]
    tb = tb[tb["Action"].astype(str).str.contains("BUY|HOLD", regex=True)].copy()
    tb["start"] = pd.to_datetime(tb["Period Start"])
    starts = sorted(tb["start"].unique())
    end_of = dict(zip(starts, starts[1:] + [pd.Timestamp(res["equity_curve"].index[-1])]))

    divs = dividend_yields(pd.read_parquet(actions_path), pd.read_parquet(raw_path,
                           columns=["date", "mkt", "symbol", "close"]))
    divs = divs[(divs["y"] > 0) & (divs["y"] < 1)]
    renames = json.load(open(report_path)).get("renames_landed", {})
    divs["symbol"] = divs["symbol"].map(lambda x: renames.get(x, x))
    membership = iu.index_history("nifty_500")

    book, members = {}, {}
    for st in starts:
        en = end_of[st]
        held = tb[tb["start"] == st].set_index("Symbol")["Weight %"].astype(float) / 100
        d = divs[(divs["date"] > st) & (divs["date"] <= en)]
        yr = st.year
        small = d[d["y"] < LARGE_DIVIDEND]
        large = d[d["y"] >= LARGE_DIVIDEND]
        b = book.setdefault(yr, {"small": 0.0, "large": 0.0})
        b["small"] += float((small.set_index("symbol")["y"] * held.reindex(small["symbol"]).fillna(0).values).sum())
        b["large"] += float((large.set_index("symbol")["y"] * held.reindex(large["symbol"]).fillna(0).values).sum())
        mem = members_on(membership, st, canonical=True) or set()
        if mem:
            w = 1.0 / len(mem)
            m = members.setdefault(yr, {"small": 0.0, "large": 0.0})
            m["small"] += float(small[small["symbol"].isin(mem)]["y"].sum() * w)
            m["large"] += float(large[large["symbol"].isin(mem)]["y"].sum() * w)

    out = pd.DataFrame({
        "book small %": {y: v["small"] * 100 for y, v in book.items()},
        "book large %": {y: v["large"] * 100 for y, v in book.items()},
        "members small %": {y: v["small"] * 100 for y, v in members.items()},
        "members large %": {y: v["large"] * 100 for y, v in members.items()},
    }).sort_index()
    out["gap, small only, pts"] = out["members small %"] - out["book small %"]
    print(out.round(2).to_string())
    # The pack holds NSE's daily Bc files only; they cover every session from 2020
    # (2010 and 2019 in part, 2011-18 hardly at all). The yearly lists that fill
    # 2011-18 are on R2. So the full years are 2020-2025.
    full = out.loc[2020:2025]
    print("\n2020-2025 a year: book", round(full["book small %"].mean(), 2), "% (+", round(full["book large %"].mean(), 2),
          "% large, already in prices); members", round(full["members small %"].mean(), 2), "%; gap",
          round(full["gap, small only, pts"].mean(), 2), "pts")


if __name__ == "__main__":
    main(*sys.argv[1:5])
