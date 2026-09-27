"""NSE adjusted prices against Screener: the prices, then the rankings.

Owner, 2026-09-27: build NSE adjusted prices and compare the rankings they
give with Screener's; only then make NSE the middle source. Read only: it
changes nothing the app shows. The report goes to the job summary and to
--out; the adjusted closes are written to --adjusted for inspection.

Steps
  1. Read every NSE day held on R2 (nse/prices_daily, nse/corporate_actions,
     the newest nse/market_caps).
  2. Adjust with NSE's own previous-close steps (src/loaders/nse_adjusted.py);
     cross-check the steps against the Bc file's parsed splits and bonuses.
  3. Prices: per stock, how far NSE-adjusted / Screener wanders over the last
     400 sessions. Two correctly adjusted series differ by a constant at most.
  4. Rankings, for each system: the published table (Screener, Yahoo for
     gaps -- what users see) against the same pipeline run on NSE's prices.

    python scripts/nse_compare.py --screener screener_prices.parquet \\
        --published-dir . --extra prices_extra.parquet
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.nse_collect import DATASETS, present_dates  # noqa: E402
from src.loaders import nse_adjusted as na  # noqa: E402
from src.loaders import nse_bundle  # noqa: E402

SINCE = date(2023, 10, 1)
KEEP = ["date", "mkt", "series", "symbol", "close", "prev_close", "high", "low",
        "volume", "value"]


def read_nse(since: date = SINCE):
    from src.storage.r2 import R2Archive, R2Config
    from src.storage.reader import R2DatasetReader

    archive = R2Archive(R2Config.from_env())
    reader = R2DatasetReader(archive)
    prices, actions, unreadable = [], [], []
    days = sorted(d for d in present_dates(archive) if d >= since)
    ca_days = present_dates(archive, DATASETS["corporate_actions"][0])
    for d in days:
        try:
            p = reader.read_parquet(reader.resolve_current(DATASETS["prices"][0], as_of=d.isoformat()))
            prices.append(p[p["series"].isin(na.SERIES)][KEEP])
            if d in ca_days:
                actions.append(reader.read_parquet(
                    reader.resolve_current(DATASETS["corporate_actions"][0], as_of=d.isoformat())))
        except Exception as exc:
            unreadable.append(f"{d}: {type(exc).__name__}")
    mcap_days = sorted(present_dates(archive, DATASETS["market_caps"][0]))
    mcaps = reader.read_parquet(reader.resolve_current(
        DATASETS["market_caps"][0], as_of=mcap_days[-1].isoformat())) if mcap_days else None
    acts = pd.concat(actions, ignore_index=True) if actions else pd.DataFrame()
    if not acts.empty:
        acts = nse_bundle.repair_swapped_dates(acts).drop_duplicates(["symbol", "ex_date", "purpose"])
        parsed = pd.DataFrame([nse_bundle.classify_purpose(p) for p in acts["purpose"]], index=acts.index)
        acts[["kind", "price_factor"]] = parsed[["kind", "price_factor"]]
    return pd.concat(prices, ignore_index=True), acts, mcaps, unreadable


def rank(src, symbols, idx_info, mcaps):
    """The ranking pipeline exactly as the nightly precompute runs it."""
    from src.core.config import DEFAULT_LOOKBACK_WEIGHTS
    from src.engine import pipeline
    from src.engine.corporate_actions import adjust_ohlc, load_events

    frames, applied = adjust_ohlc({"adj_close": src.adj_close, "close": src.close,
                                   "high": src.close, "low": src.close}, load_events())
    w = tuple(float(x) for x in DEFAULT_LOOKBACK_WEIGHTS)
    w = tuple(x / sum(w) for x in w)
    calc = pipeline.build_engine(frames["adj_close"], None, None, frames["close"], src.volume,
                                 idx_info, mcaps, corporate_actions=applied)
    _c, table = pipeline.rank_with_weights(calc, w, idx_info, mcaps, frames["close"],
                                           frames["close"], intraday=False)
    return table, pipeline.ranking_as_of(frames["adj_close"])


def _md(frame: pd.DataFrame, n: int = 20) -> str:
    """A markdown table without the optional tabulate dependency."""
    if not len(frame):
        return "_none_"
    f = frame.head(n)
    cell = lambda v: f"{v:.4g}" if isinstance(v, float) else (str(v.date()) if isinstance(v, pd.Timestamp) else str(v))  # noqa: E731
    rows = ["| " + " | ".join(map(str, f.columns)) + " |", "|" + "---|" * len(f.columns)]
    rows += ["| " + " | ".join(cell(v) for v in r) + " |" for r in f.itertuples(index=False)]
    more = f"\n_…and {len(frame) - n} more_" if len(frame) > n else ""
    return "\n".join(rows) + more


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--screener", default="screener_prices.parquet")
    ap.add_argument("--published-dir", default=".")
    ap.add_argument("--out", default="nse_compare_report.md")
    ap.add_argument("--adjusted", default="nse_adjusted_close.parquet")
    args = ap.parse_args(argv)

    from src.engine.extra_universe import SYSTEMS, SYSTEM_NAMES, SYSTEM_NANO
    from src.loaders import extra_universe_loader as xl
    from src.loaders.indices_loader import fetch_indices_data
    from src.loaders.ranking_store import asset_name, read_snapshot

    prices, acts, mcap_frame, unreadable = read_nse()
    adj, factors = na.adjusted_frames(prices)
    adj["close"].astype("float32").to_parquet(args.adjusted, compression="zstd")
    ev = na.events(factors)
    out = [f"# NSE adjusted prices against Screener — {date.today()}\n",
           "## 1. NSE record\n",
           f"- Sessions: **{adj['close'].shape[0]}** ({adj['close'].index.min().date()} → "
           f"{adj['close'].index.max().date()}); stocks: {adj['close'].shape[1]}",
           f"- Unreadable days: {len(unreadable)} {', '.join(unreadable[:10])}",
           f"- Adjustments NSE made (previous-close steps): **{len(ev)}**\n"]

    cc = na.crosscheck_actions(factors, acts) if not acts.empty else None
    out.append("## 2. Steps against the Bc file's splits and bonuses\n")
    if cc is None:
        out.append("_no corporate-action files_\n")
    else:
        out += [f"- Agreeing within 2%: {len(ev) - len(cc['unparsed']) - len(cc['mismatched'])}",
                f"- **Disagreeing: {len(cc['mismatched'])}**", _md(cc["mismatched"]), "",
                f"- Parsed split/bonus with no NSE step: {len(cc['missing'])}", _md(cc["missing"]), "",
                f"- NSE step with no parsed split/bonus (demergers, specials): {len(cc['unparsed'])}",
                _md(cc["unparsed"].sort_values("date", ascending=False)), ""]

    store = pd.read_parquet(args.screener)
    scr_close = store.xs("Close", axis=1, level=-1)
    drift = na.level_drift(adj["close"], scr_close)
    bad = drift[drift["max_drift"] > 0.01]
    out += ["## 3. Prices: NSE adjusted / Screener, last 400 sessions\n",
            f"- Stocks compared: {len(drift)}; median of the per-stock ratio: "
            f"{drift['median_ratio'].median():.4f}",
            f"- Within 1% throughout: **{int((drift['max_drift'] <= 0.01).sum())}**; "
            f"beyond 1% at some point: **{len(bad)}**",
            _md(bad.reset_index(names="symbol").round(4), 30), ""]

    caps = (mcap_frame.drop_duplicates("symbol").set_index("symbol")["mcap"]
            if mcap_frame is not None else pd.Series(dtype=float))
    out.append("## 4. Rankings: published (Screener) against NSE\n")
    base = fetch_indices_data(["NIFTY TOTAL MARKET"])
    extra = xl.members()
    for system in SYSTEMS:
        idx_info = xl.system_universe(system, base if system != SYSTEM_NANO else base.iloc[0:0], extra)
        symbols = idx_info["Symbol"].unique().tolist()
        published, contract = read_snapshot(os.path.join(args.published_dir, asset_name(system)))
        src = na.as_price_frames(adj, symbols)
        try:
            nse_table, as_of = rank(src, symbols, idx_info, caps.reindex(symbols).dropna())
        except Exception as exc:
            out.append(f"### {SYSTEM_NAMES[system]}\n\n_NSE ranking failed: {type(exc).__name__}: {exc}_\n")
            continue
        if published is None:
            out.append(f"### {SYSTEM_NAMES[system]}\n\n_no published table_\n")
            continue
        r = na.compare_rankings(published, nse_table)
        out += [f"### {SYSTEM_NAMES[system]}\n",
                f"- As of: published {contract.get('price_as_of') if contract else '?'}, NSE {as_of}",
                f"- Ranked: published {r['a_rows']}, NSE {r['b_rows']}, both {r['common']}",
                f"- Rank correlation (Spearman): **{r['spearman']:.4f}**",
                f"- Top 20 in common: **{r['top20_overlap']}/20** "
                f"(only published: {', '.join(r['top20_only_a']) or '-'}; only NSE: {', '.join(r['top20_only_b']) or '-'})",
                f"- Top 50 in common: **{r['top50_overlap']}/50**",
                f"- Ranked by only one side: published {len(r['only_a'])} "
                f"({', '.join(r['only_a'][:15])}), NSE {len(r['only_b'])} ({', '.join(r['only_b'][:15])})",
                "", "Largest rank moves:", "",
                _md(r["largest_moves"].rename(columns={"Rank_a": "published", "Rank_b": "nse"}), 15), ""]

    text = "\n".join(out)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
