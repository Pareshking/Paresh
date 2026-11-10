"""NSE adjusted prices against Screener: the prices, then the rankings.

Owner, 2026-09-27: build NSE adjusted prices and compare the rankings they
give with Screener's; only then make NSE the middle source. Read only: it
changes nothing the app shows. The report goes to the job summary and to
--out; the adjusted closes are written to --adjusted for inspection.

Steps
  1. Read every NSE day held on R2 (nse/prices_daily, nse/corporate_actions,
     the newest nse/market_caps).
  2. Adjust with the Bc file's splits and bonuses, each applied only where
     the price moved by its factor (src/loaders/nse_adjusted.py).
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
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

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


def progress(message: str) -> None:
    """One timestamped line, flushed.

    Run 42486769158's `Compare` step spent 44m41s of a 45m14s job in
    `read_nse` and printed nothing after its first second, so the timeout
    named the job and not the step. Every long phase now says where it is.
    """
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def _new_reader():
    from src.storage.r2 import R2Archive, R2Config
    from src.storage.reader import R2DatasetReader

    return R2DatasetReader(R2Archive(R2Config.from_env()))


def read_nse(
    since: date = SINCE,
    *,
    workers: int | None = None,
    make_reader=None,
):
    """Every NSE day R2 holds since `since`, read `workers` at a time.

    One day costs four R2 round trips (pointer, manifest, HEAD, payload) and a
    parquet parse of the whole market. Read one at a time over ~520 days that
    was ~5 s a day and 45 minutes a run. The reads are independent, so they
    run concurrently; the frames are reassembled in date order, so the
    concatenated result and the `unreadable` list are byte-for-byte what the
    serial loop produced. Each thread builds its own reader (and therefore its
    own boto3 client) rather than sharing one.
    """
    make_reader = make_reader or _new_reader
    workers = workers or int(os.environ.get("NSE_COMPARE_WORKERS", "8"))

    reader = make_reader()
    archive = reader.archive
    days = sorted(d for d in present_dates(archive) if d >= since)
    ca_days = present_dates(archive, DATASETS["corporate_actions"][0])
    progress(
        f"R2 holds {len(days)} NSE sessions since {since} and "
        f"{len(ca_days)} corporate-action days; reading with {workers} workers"
    )

    local = threading.local()

    def _reader() -> object:
        if not hasattr(local, "reader"):
            local.reader = make_reader()
        return local.reader

    def _read(d: date):
        r = _reader()
        p = r.read_parquet(
            r.resolve_current(DATASETS["prices"][0], as_of=d.isoformat())
        )
        price = p[p["series"].isin(na.SERIES)][KEEP]
        action = None
        if d in ca_days:
            action = r.read_parquet(
                r.resolve_current(
                    DATASETS["corporate_actions"][0], as_of=d.isoformat()
                )
            )
        return price, action

    read: dict[date, tuple] = {}
    failed: dict[date, str] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_read, d): d for d in days}
        for future in as_completed(futures):
            d = futures[future]
            try:
                read[d] = future.result()
            except Exception as exc:
                failed[d] = f"{d}: {type(exc).__name__}"
            done += 1
            if done % 50 == 0 or done == len(days):
                progress(f"read {done}/{len(days)} sessions ({len(failed)} unreadable)")

    # Date order, exactly as the serial loop appended them.
    prices = [read[d][0] for d in days if d in read]
    actions = [read[d][1] for d in days if d in read and read[d][1] is not None]
    unreadable = [failed[d] for d in days if d in failed]

    mcap_days = sorted(present_dates(archive, DATASETS["market_caps"][0]))
    progress("reading the newest market-cap snapshot")
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

    progress("step 1: reading the NSE record from R2")
    prices, acts, mcap_frame, unreadable = read_nse()
    if acts.empty:
        acts = pd.DataFrame(columns=["symbol", "ex_date", "kind", "price_factor"])
    progress("step 2: adjusting for splits and bonuses")
    adj, factors, verdicts = na.adjusted_frames(prices, acts)
    adj["close"].astype("float32").to_parquet(args.adjusted, compression="zstd")
    ev = na.events(factors)
    out = [f"# NSE adjusted prices against Screener — {date.today()}\n",
           "## 1. NSE record\n",
           f"- Sessions: **{adj['close'].shape[0]}** ({adj['close'].index.min().date()} → "
           f"{adj['close'].index.max().date()}); stocks: {adj['close'].shape[1]}",
           f"- Unreadable days: {len(unreadable)} {', '.join(unreadable[:10])}",
           f"- Adjustments applied (splits, bonuses, consolidations, demergers): **{len(ev)}**\n"]

    w = na.wide(prices)
    gaps = na.gap_days(w["close"], w["prev_close"])
    sessions = w["close"].index
    out += ["## 1b. Sessions missing from the record\n",
            "A day where most stocks' previous close is not our previous session's "
            "close follows a session we hold no file for (a Budget Sunday, a muhurat "
            "session). Collect it: `nse_collect.yml` → dates.\n"]
    if len(gaps):
        rows = [{"gap before": d.date(),
                 "last held": sessions[sessions.get_loc(d) - 1].date() if sessions.get_loc(d) else "-",
                 "stocks stepping": f"{v:.0%}"} for d, v in gaps.items()]
        out += [_md(pd.DataFrame(rows), 40), ""]
    else:
        out.append("_none_\n")

    w_close = w["close"].copy()
    w_close.index = factors.index
    progress("step 2b: unexplained jumps")
    jumps = na.unexplained_jumps(w_close, factors)
    counts = verdicts["verdict"].value_counts()
    out += ["## 2. The Bc file's splits and bonuses against the price\n",
            f"- Applied (the price moved by the factor): **{int(counts.get('applied', 0))}**",
            f"- Applied on the date with day and month exchanged: "
            f"**{int(counts.get('date swapped', 0))}**",
            f"- Demergers, priced at the ex-date's fall: **{int(counts.get('demerger', 0))}**",
            f"- **Not applied, the price did not move by it: {int(counts.get('no move', 0))}** "
            "(a duplicate date, or a factor the market did not see)",
            _md(verdicts[verdicts["verdict"] == "no move"].drop(columns="verdict")), "",
            f"- No price on or after the ex-date: {int(counts.get('no price', 0))}", "",
            f"- Moves beyond 1.8x in a session with no applied action (demergers, "
            f"specials, genuine moves): {len(jumps)}", _md(jumps), ""]

    progress("step 3: Screener drift")
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
    progress("step 4: rankings, per system")
    base = fetch_indices_data(["NIFTY TOTAL MARKET"])
    extra = xl.members()
    for system in SYSTEMS:
        idx_info = xl.system_universe(system, base if system != SYSTEM_NANO else base.iloc[0:0], extra)
        symbols = idx_info["Symbol"].unique().tolist()
        published, contract = read_snapshot(os.path.join(args.published_dir, asset_name(system)))
        progress(f"ranking {SYSTEM_NAMES[system]} ({len(symbols)} symbols)")
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
