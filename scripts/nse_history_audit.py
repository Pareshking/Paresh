"""Audit R2's NSE history, 2010 to date: missing days, corporate actions, jumps, renames.

    python scripts/nse_history_audit.py --since 2010-01-01 --out reports/nse_audit

Read only. Reads every session in nse/prices_daily (16 at a time), the
corporate actions (daily Bc files and NSE's yearly list) and nse/closed_days,
then reports:

1. COVERAGE. Sessions held per year; weekdays held neither as a session nor as
   a known closed day (asked of NSE by nse_collect until there are none); and,
   independently of any calendar, sessions whose previous close NSE printed
   does not match our previous session's close for most stocks -- a session
   missing between them (nse_adjusted.gap_days).
2. CORPORATE ACTIONS. Every split, bonus, consolidation and demerger with the
   verdict nse_adjusted.action_factors gives it: applied where the price moved
   by its factor, or "no move" / "no price".
3. UNEXPLAINED JUMPS. One-day moves beyond 1.8x either way that no applied
   action explains (nse_adjusted.unexplained_jumps): a missed action or a bad
   print.
4. RENAMES. Automatic renames (nse_identity) joined, and those the continuity
   check refused.

Writes report.md (also the job summary) and CSV detail to --out.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.loaders import nse_adjusted as na  # noqa: E402
from src.loaders import nse_bundle as nb  # noqa: E402
from src.loaders import nse_history as nh  # noqa: E402

CLOSED = "nse/closed_days"


def weekdays(start: date, end: date) -> list[date]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def missing_weekdays(held: set[date], closed: set[date], start: date, end: date) -> list[date]:
    """Weekdays in [start, end] held neither as a session nor as a known closed day."""
    return [d for d in weekdays(start, end) if d not in held and d not in closed]


def read_history(reader, days: list[date], workers: int = 16, log=print) -> pd.DataFrame:
    """Every session's price rows (stock series only, the columns the audit needs)."""
    def one(d):
        p = reader.read_parquet(reader.resolve_current(nh.R2_PRICES, as_of=d.isoformat()))
        return p[p["series"].isin(na.PRICE_SERIES)][nh.KEEP]

    frames, bad = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, (d, fut) in enumerate(zip(days, [pool.submit(one, d) for d in days])):
            try:
                frames.append(fut.result())
            except Exception as exc:  # noqa: BLE001
                bad.append(f"{d}: {type(exc).__name__}")
            if (i + 1) % 500 == 0:
                log(f"  read {i + 1}/{len(days)} sessions")
    if bad:
        log(f"  unreadable: {len(bad)} {bad[:5]}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=nh.KEEP)


def read_actions(reader, archive, since: date, until: date) -> pd.DataFrame:
    """Daily Bc rows and the yearly list, re-classified, one row per action."""
    frames = []
    for d in sorted(nh.r2_days(archive, nh.R2_ACTIONS)):
        if since <= d <= until:
            frames.append(reader.read_parquet(reader.resolve_current(nh.R2_ACTIONS, as_of=d.isoformat()))
                          .assign(source="bc"))
    for d in sorted(nh.r2_days(archive, nh.R2_ACTIONS_HISTORY)):
        frames.append(reader.read_parquet(reader.resolve_current(nh.R2_ACTIONS_HISTORY,
                                                                 as_of=d.isoformat())).assign(source="list"))
    if not frames:
        return pd.DataFrame()
    # The yearly list first, so a row both carry keeps its "list" tag for drop_swapped_twins.
    acts = pd.concat(frames[::-1], ignore_index=True)
    acts = nb.repair_swapped_dates(acts).drop_duplicates(["symbol", "ex_date", "purpose"])
    parsed = pd.DataFrame([nb.classify_purpose(p) for p in acts["purpose"]], index=acts.index)
    acts[["kind", "price_factor"]] = parsed[["kind", "price_factor"]]
    return nb.drop_swapped_twins(acts)


def audit(prices: pd.DataFrame, actions: pd.DataFrame, held: set[date], closed: set[date],
          since: date, until: date) -> dict:
    from src.loaders import nse_prices as npx
    from src.loaders.nse_identity import auto_renames

    w = na.wide(prices)
    close = w["close"]
    close.index = pd.DatetimeIndex(close.index)
    factors, verdicts = na.action_factors(close, actions)
    factors.index = close.index
    jumps = na.unexplained_jumps(close, factors)
    gaps = na.gap_days(close, w["prev_close"].set_axis(close.index))
    copies = na.copied_sessions(close, w["volume"].set_axis(close.index))
    from src.loaders.nse_calendar import impossible_sessions

    calendar = impossible_sessions(close.index)
    renames = auto_renames(set(close.columns))
    refused: list[str] = []
    npx.chain_raw(close, factors, renames, refused)   # raw closes: the join is checked before adjusting
    return {
        "per_year": pd.Series([d.year for d in held]).value_counts().sort_index(),
        "missing": missing_weekdays(held, closed, since, until),
        "gap_days": gaps,
        "copies": copies,
        "calendar": calendar,
        "verdicts": verdicts,
        "jumps": jumps,
        "renames": len([o for o in renames if o in close.columns]),
        "refused": refused,
        "stocks": close.shape[1],
    }


def write(result: dict, out: Path, since: date, until: date) -> str:
    out.mkdir(parents=True, exist_ok=True)
    v, j = result["verdicts"], result["jumps"]
    v.to_csv(out / "actions.csv", index=False)
    j.to_csv(out / "jumps.csv", index=False)
    pd.DataFrame({"date": result["missing"]}).to_csv(out / "missing_weekdays.csv", index=False)
    result["gap_days"].rename("share").to_csv(out / "gap_days.csv")
    pd.DataFrame({"refused": result["refused"]}).to_csv(out / "renames_refused.csv", index=False)

    lines = [f"# NSE history audit {since} → {until}", "",
             f"{sum(result['per_year'])} sessions, {result['stocks']} stocks.", "",
             "## 1. Coverage", "",
             "| Year | Sessions |", "|---|---|"]
    lines += [f"| {y} | {n} |" for y, n in result["per_year"].items()]
    lines += ["", f"**Weekdays neither held nor a known closed day: {len(result['missing'])}**"
              + (f" — first {', '.join(str(d) for d in result['missing'][:15])}" if result["missing"] else ""),
              "", f"**Sessions whose previous close says a session is missing before them: "
              f"{len(result['gap_days'])}**"]
    for d, share in result["gap_days"].head(20).items():
        lines.append(f"- {pd.Timestamp(d).date()}: {share:.0%} of stocks")
    copies = result.get("copies", pd.Series(dtype=float))
    lines += ["", f"**Sessions that copy the one before (a holiday stored as a trading day): "
              f"{len(copies)}**" + (f" — {', '.join(str(pd.Timestamp(d).date()) for d in copies.index[:40])}"
                                   if len(copies) else "")]
    cal = result.get("calendar", {})
    lines += ["", f"**Sessions on a day NSE cannot trade (weekend not announced, fixed or published "
              f"holiday): {len(cal)}**"]
    lines += [f"- {d}: {why}" for d, why in sorted(cal.items())[:40]]
    lines += ["", "## 2. Corporate actions (split, bonus, consolidation, demerger)", "",
              "| Verdict | Actions |", "|---|---|"]
    lines += [f"| {k} | {n} |" for k, n in v["verdict"].value_counts().items()] if len(v) else ["| — | 0 |"]
    nomove = v[v["verdict"] == "no move"] if len(v) else v
    if len(nomove):
        lines += ["", "Not confirmed by the price (first 25):", ""]
        lines += [f"- {r.symbol} {pd.Timestamp(r.date).date()} {r.kind} ×{r.bc_factor:.4g}"
                  for r in nomove.head(25).itertuples()]
    lines += ["", f"## 3. Unexplained jumps (beyond 1.8× either way): {len(j)}", ""]
    if len(j):
        by_year = j.groupby(pd.to_datetime(j["date"]).dt.year).size()
        lines += ["| Year | Jumps |", "|---|---|"] + [f"| {y} | {n} |" for y, n in by_year.items()]
        lines += ["", "Most recent 30:", ""]
        lines += [f"- {r.symbol} {pd.Timestamp(r.date).date()} ×{r.move:.3f}" for r in j.head(30).itertuples()]
    lines += ["", f"## 4. Renames: {result['renames']} in the data; "
              f"{len(result['refused'])} refused by the continuity check", ""]
    lines += [f"- {r}" for r in result["refused"][:40]]
    text = "\n".join(lines) + "\n"
    (out / "report.md").write_text(text, encoding="utf-8")
    (out / "summary.json").write_text(json.dumps({
        "sessions": int(sum(result["per_year"])), "stocks": int(result["stocks"]),
        "missing_weekdays": len(result["missing"]), "gap_days": int(len(result["gap_days"])),
        "copied_sessions": int(len(result.get("copies", ()))),
        "calendar_flags": int(len(result.get("calendar", {}))),
        "actions": {k: int(n) for k, n in v["verdict"].value_counts().items()} if len(v) else {},
        "unexplained_jumps": int(len(j)), "renames": result["renames"],
        "renames_refused": len(result["refused"])}, indent=1) + "\n")
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", type=date.fromisoformat, default=date(2008, 1, 1))
    ap.add_argument("--until", type=date.fromisoformat, default=None)
    ap.add_argument("--out", type=Path, default=Path("reports/nse_audit"))
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args(argv)

    from src.storage.r2 import R2Archive, R2Config
    from src.storage.reader import R2DatasetReader

    archive = R2Archive(R2Config.from_env())
    reader = R2DatasetReader(archive)
    until = args.until or date.today() - timedelta(days=1)
    held = {d for d in nh.r2_days(archive, nh.R2_PRICES) if args.since <= d <= until}
    closed = nh.r2_days(archive, CLOSED)
    print(f"R2 holds {len(held)} sessions in [{args.since}, {until}], {len(closed)} known closed days")
    prices = read_history(reader, sorted(held), args.workers)
    actions = read_actions(reader, archive, args.since, until)
    print(f"prices {len(prices):,} rows, actions {len(actions):,}")
    result = audit(prices, actions, held, closed, args.since, until)
    text = write(result, args.out, args.since, until)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
