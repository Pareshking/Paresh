"""Checks on the NSE sample year before the ten-year backfill (owner, 2026-09-27).

Reads everything nse_collect.py has put in R2 since --since and reports, in
Markdown (stdout, the job summary, and --out):

  1. coverage     every trading day in the calendar is held; days NSE had no
                  bundle for are matched against data/nse_trading_days.json
  2. parsing      every held day reads back through the SHA-checked reader;
                  row counts per day, days with far fewer rows, days without
                  a market-cap file
  3. sources      the cross-source check over EVERY day, not just the newest:
                  Screener's close within 1% of NSE's, Screener's and Yahoo's
                  one-day moves within 7% of NSE's
  4. corporate    every split and bonus with its ex-date in the sample: does
     actions      NSE's own previous close on the ex-date carry the factor,
                  did Screener and Yahoo restate the day before by it, and is
                  it in data/corporate_actions_log.json; and the reverse, log
                  events NSE has no split or bonus for
  5. storage      bytes per day per dataset, projected to ten years

Read only: writes nothing to R2.

    python scripts/nse_sample_check.py --since 2025-04-01 \\
        --calendar prices_full.parquet --screener screener_prices.parquet \\
        --yahoo prices.parquet --out nse_sample_report.md --flags-csv flags.csv
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.nse_collect import DATASETS, _closes, load_calendar, present_dates
from src.engine import source_check
from src.loaders import nse_bundle

ROOT = Path(__file__).resolve().parents[1]
TRADING_DAYS = ROOT / "data" / "nse_trading_days.json"
ACTIONS_LOG = ROOT / "data" / "corporate_actions_log.json"
TEN_YEARS_SESSIONS = 2_480          # about 248 NSE sessions a year
FACTOR_TOL = 0.02                   # a restated price within 2% of the factor


# ── Coverage ─────────────────────────────────────────────────────────────────

def coverage(calendar: list[date], have: set[date], since: date,
             closed: set[date]) -> dict:
    """Calendar days missing from R2, and R2 days the calendar lacks."""
    end = max(have) if have else since
    cal = [d for d in calendar if since <= d <= end]
    missing = [d for d in cal if d not in have]
    return {
        "calendar_days": len(cal),
        "held": len([d for d in have if since <= d <= end]),
        "missing_closed": [d for d in missing if d in closed],
        "missing_open": [d for d in missing if d not in closed],
        "not_in_calendar": sorted(d for d in have if since <= d and d not in set(cal)),
    }


# ── Corporate actions ────────────────────────────────────────────────────────

def _prev_session(sessions: pd.DatetimeIndex, day: pd.Timestamp) -> pd.Timestamp | None:
    before = sessions[sessions < day]
    return before[-1] if len(before) else None


def action_steps(actions: pd.DataFrame, nse_close: pd.DataFrame, nse_prev: pd.DataFrame,
                 screener: pd.DataFrame | None, yahoo: pd.DataFrame | None,
                 log_keys: set[tuple[str, str]]) -> pd.DataFrame:
    """One row per split or bonus: the factor against what each source shows.

    nse_step       NSE's previous close on the ex-date / its close the session
                   before. NSE adjusts the previous close for the action, so
                   this should equal the factor.
    raw_move       close on the ex-date / close the session before.
    screener_step  Screener's close the session before / NSE's. Screener
                   restates history, so this should equal the factor too.
    yahoo_step     the same for Yahoo.
    """
    sessions = nse_close.index
    rows = []
    for a in actions.itertuples():
        ex = pd.Timestamp(a.ex_date).normalize()
        prev = _prev_session(sessions, ex)
        sym = a.symbol

        def at(frame, day):
            if frame is None or day is None or day not in frame.index or sym not in frame.columns:
                return np.nan
            return float(frame.at[day, sym])

        c_prev, c_ex, p_ex = at(nse_close, prev), at(nse_close, ex), at(nse_prev, ex)
        s_prev, y_prev = at(screener, prev), at(yahoo, prev)
        row = {
            "symbol": sym, "ex_date": ex.date(), "kind": a.kind, "purpose": a.purpose,
            "factor": a.price_factor,
            "nse_step": p_ex / c_prev if c_prev else np.nan,
            "raw_move": c_ex / c_prev if c_prev else np.nan,
            "screener_step": s_prev / c_prev if c_prev else np.nan,
            "yahoo_step": y_prev / c_prev if c_prev else np.nan,
            "in_log": (ex.date().isoformat(), sym) in log_keys,
        }
        for col in ("nse_step", "screener_step", "yahoo_step"):
            v = row[col]
            row[col + "_ok"] = (bool(abs(v / row["factor"] - 1) <= FACTOR_TOL)
                                if pd.notna(v) and pd.notna(row["factor"]) else None)
        rows.append(row)
    return pd.DataFrame(rows)


def combine_same_day(actions: pd.DataFrame) -> pd.DataFrame:
    """One row per stock and ex-date, the factors multiplied.

    BAJFINANCE went ex a 4:1 bonus and a 2:1 split on 2025-06-16: the price
    fell to a tenth, and each action alone explains only part of it.
    """
    if actions.empty:
        return actions
    grouped = actions.groupby(["symbol", "ex_date"], as_index=False).agg(
        kind=("kind", lambda k: "+".join(sorted(set(k)))),
        purpose=("purpose", lambda p: " / ".join(p)),
        price_factor=("price_factor", "prod"),
    )
    return grouped


# ── Report helpers ───────────────────────────────────────────────────────────

def _dates(ds, limit=30) -> str:
    ds = list(ds)
    if not ds:
        return "none"
    text = ", ".join(d.isoformat() for d in ds[:limit])
    return text + (f" … (+{len(ds) - limit})" if len(ds) > limit else "")


def _table(frame: pd.DataFrame, limit: int = 40) -> str:
    if frame is None or frame.empty:
        return "_none_\n"
    def cell(v):
        return f"{v:.4f}" if isinstance(v, float) else str(v).replace("|", "/")

    head = frame.head(limit)
    lines = ["| " + " | ".join(map(str, head.columns)) + " |",
             "|" + "---|" * len(head.columns)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |"
              for row in head.itertuples(index=False)]
    return "\n".join(lines) + "\n" + (
        f"\n\n_{len(frame) - limit} more rows in the CSV._\n" if len(frame) > limit else "\n")


# ── Main ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default="2025-04-01")
    ap.add_argument("--calendar")
    ap.add_argument("--screener")
    ap.add_argument("--yahoo")
    ap.add_argument("--out", default="nse_sample_report.md")
    ap.add_argument("--flags-csv", default="nse_sample_flags.csv")
    ap.add_argument("--actions-csv", default="nse_sample_actions.csv")
    args = ap.parse_args(argv)
    since = date.fromisoformat(args.since)

    from src.storage.r2 import R2Archive, R2Config
    from src.storage.reader import R2DatasetReader

    archive = R2Archive(R2Config.from_env())
    reader = R2DatasetReader(archive)
    out: list[str] = [f"# NSE sample check — {since} onward\n"]

    # 1. Coverage
    have = {d for d in present_dates(archive) if d >= since}
    closed_info = json.loads(TRADING_DAYS.read_text())
    closed = {date.fromisoformat(d) for d in closed_info.get("closed_days", [])}
    cov = coverage(load_calendar(args.calendar), have, since, closed)
    out += [
        "## 1. Coverage\n",
        f"- Held: **{cov['held']}** of {cov['calendar_days']} calendar sessions "
        f"({min(have) if have else '-'} → {max(have) if have else '-'})",
        f"- Missing, and a known NSE holiday: {_dates(cov['missing_closed'])}",
        f"- **Missing, not a known holiday: {_dates(cov['missing_open'])}**",
        f"- Held but not in the Yahoo calendar: {_dates(cov['not_in_calendar'])}\n",
    ]

    # 2. Parsing: read every day back
    days = sorted(have)
    rows, prices_by_day, actions, unreadable = [], {}, [], []
    mcap_days = present_dates(archive, DATASETS["market_caps"][0])
    ca_days = present_dates(archive, DATASETS["corporate_actions"][0])
    for d in days:
        try:
            p = reader.read_parquet(reader.resolve_current(DATASETS["prices"][0], as_of=d.isoformat()))
        except Exception as exc:                         # report, keep going
            unreadable.append((d, f"{type(exc).__name__}: {exc}"[:120]))
            continue
        prices_by_day[d] = p
        eq = p[p["series"].isin(["EQ", "BE"]) & (p["symbol"] != "")]
        rows.append({"date": d, "rows": len(p), "equities": eq["symbol"].nunique(),
                     "indices": int((p["mkt"] == "Y").sum()), "mcap": d in mcap_days})
        if d in ca_days:
            try:
                actions.append(reader.read_parquet(
                    reader.resolve_current(DATASETS["corporate_actions"][0], as_of=d.isoformat())))
            except Exception as exc:
                unreadable.append((d, f"corporate_actions {type(exc).__name__}"))
    per_day = pd.DataFrame(rows)
    med = per_day["equities"].median() if len(per_day) else 0
    thin = per_day[per_day["equities"] < 0.8 * med] if len(per_day) else per_day
    out += [
        "## 2. Every day reads back\n",
        f"- Read back and SHA-checked: **{len(prices_by_day)}** / {len(days)}",
        f"- Unreadable: {len(unreadable)}" + "".join(f"\n  - {d}: {e}" for d, e in unreadable[:20]),
        f"- Equities per day: min {per_day['equities'].min()}, median {med:.0f}, "
        f"max {per_day['equities'].max()}; index rows median "
        f"{per_day['indices'].median():.0f}" if len(per_day) else "- no rows",
        f"- Days with under 80% of the median equities: {_dates(thin['date']) if len(thin) else 'none'}",
        f"- Days without a market-cap file: {_dates(per_day.loc[~per_day['mcap'], 'date']) if len(per_day) else '-'}",
        f"- Days with a corporate-actions file: {len(ca_days & have)}\n",
    ]

    # Panels of NSE close and previous close, one column per symbol.
    close_rows, prev_rows = {}, {}
    for d, p in prices_by_day.items():
        c = source_check.nse_closes(p)
        eq = p[p["series"].isin(["EQ", "BE"]) & (p["mkt"] != "Y") & (p["symbol"] != "")]
        eq = eq.assign(_r=(eq["series"] != "EQ").astype(int)).sort_values("_r").drop_duplicates("symbol")
        close_rows[pd.Timestamp(d)] = c["close"]
        prev_rows[pd.Timestamp(d)] = eq.set_index("symbol")["prev_close"]
    nse_close = pd.DataFrame(close_rows).T.sort_index()
    nse_prev = pd.DataFrame(prev_rows).T.sort_index()

    # 3. Cross-source check over every day
    screener = _closes(args.screener)
    yahoo = _closes(args.yahoo)
    symbols = sorted(screener.columns) if screener is not None else (
        sorted(yahoo.columns) if yahoo is not None else [])
    flags = [source_check.compare(prices_by_day[d], screener, yahoo, symbols)
             for d in sorted(prices_by_day)]
    flags = pd.concat(flags, ignore_index=True) if flags else pd.DataFrame(
        columns=source_check.CHECK_COLUMNS)
    flags.to_csv(args.flags_csv, index=False)
    counts = flags["check"].value_counts()
    real = flags[~flags["check"].isin(["missing_at_nse", "missing_at_screener"])]
    by_stock = (real.groupby(["symbol", "check"]).size().rename("days").reset_index()
                .sort_values("days", ascending=False))
    by_day = flags.groupby("date").size()
    out += [
        "## 3. Sources against NSE, every day\n",
        f"- Stocks compared: {len(symbols)} (Screener's list); days: {len(prices_by_day)}",
        f"- Checks: {len(symbols) * len(prices_by_day):,} stock-days; "
        f"flags: **{len(flags):,}**",
        "".join(f"\n  - {k}: {v:,}" for k, v in counts.items()),
        "- Worst days: " + ", ".join(f"{pd.Timestamp(d).date()} ({n})"
                                      for d, n in by_day.sort_values(ascending=False).head(8).items()),
        "\nStocks with the most price or move disagreements:\n",
        _table(by_stock, 30),
        "Largest single gaps:\n",
        _table(real.assign(abs_gap=real["gap"].abs()).sort_values("abs_gap", ascending=False)
               .drop(columns="abs_gap"), 25),
    ]

    # 4. Corporate actions
    acts = pd.concat(actions, ignore_index=True) if actions else pd.DataFrame()
    log = json.loads(ACTIONS_LOG.read_text()).get("events", {})
    log_keys = {(e["date"], e["symbol"]) for e in log.values()}
    out.append("## 4. Corporate actions\n")
    if acts.empty:
        out.append("_no corporate-action files held_\n")
    else:
        acts = acts.drop_duplicates(["symbol", "ex_date", "purpose"])
        # Re-read NSE's wording with today's parser: the stored kind is what
        # the parser said on the day it was collected.
        reparsed = pd.DataFrame([nse_bundle.classify_purpose(p) for p in acts["purpose"]],
                                index=acts.index)
        acts[["kind", "price_factor"]] = reparsed[["kind", "price_factor"]]
        out.append("Announced in the sample, by kind: " + ", ".join(
            f"{k} {v}" for k, v in acts["kind"].value_counts().items()) + "\n")
        # NSE's own wording for anything that may move the price, as parsed.
        # The parser learns its phrasing from this list (2026-09-27: no split
        # was recognised at all in the first sample).
        wording = acts[acts["purpose"].str.upper().str.contains(
            "SPLIT|SUB-DIV|SUBDIV|BONUS|DEMERG|CONSOLID|FV|FACE VALUE", regex=True, na=False)]
        common = (wording.groupby(["kind", "purpose"]).size().rename("n").reset_index()
                  .sort_values("n", ascending=False))
        out += ["NSE's wording for splits, bonuses, demergers and consolidations, "
                "with the kind the parser gave it:\n", _table(common, 60)]
        end = max(days)
        steps_in = acts[acts["kind"].isin(["split", "bonus"]) & acts["price_factor"].notna()
                        & (acts["ex_date"] >= pd.Timestamp(since)) & (acts["ex_date"] <= pd.Timestamp(end))]
        steps = action_steps(combine_same_day(steps_in), nse_close, nse_prev, screener,
                             yahoo, log_keys)
        steps.to_csv(args.actions_csv, index=False)
        if not steps.empty:
            def rate(col):
                known = steps[col].dropna()
                return f"{int(known.sum())}/{len(known)}"
            ours = steps[steps["symbol"].isin(symbols)]
            out += [
                f"- Splits and bonuses with ex-date in the sample: **{len(steps)}** "
                f"({len(ours)} in our universe)",
                f"- NSE's previous close carries the factor: {rate('nse_step_ok')}",
                f"- Screener restated the day before by the factor: {rate('screener_step_ok')}",
                f"- Yahoo restated the day before by the factor: {rate('yahoo_step_ok')}",
                f"- In data/corporate_actions_log.json: {int(steps['in_log'].sum())}/{len(steps)}\n",
                "Where a source does not match the factor (our universe first):\n",
                _table(steps[(steps["nse_step_ok"] == False) | (steps["screener_step_ok"] == False)  # noqa: E712
                             | (steps["yahoo_step_ok"] == False)]  # noqa: E712
                       .assign(_ours=lambda f: ~f["symbol"].isin(symbols))
                       .sort_values(["_ours", "ex_date"]).drop(columns=["_ours", "purpose"]), 40),
            ]
        # The reverse: large moves the log recorded that NSE has no split/bonus for.
        known = {(r.ex_date.date().isoformat(), r.symbol) for r in acts.itertuples()
                 if pd.notna(r.ex_date)}
        orphan = [e for e in log.values()
                  if since.isoformat() <= e["date"] <= end.isoformat()
                  and (e["date"], e["symbol"]) not in known]
        out += [f"Log events in the sample with no NSE book closure on that date: {len(orphan)}\n",
                _table(pd.DataFrame(orphan)[["date", "symbol", "ratio", "looks_like"]]
                       if orphan else pd.DataFrame(), 30)]

    # 5. Storage
    out.append("## 5. Storage\n")
    total_day = 0.0
    lines = []
    for key, (dataset, _root) in DATASETS.items():
        sizes = []
        for d in days:
            try:
                ref = reader.resolve_current(dataset, as_of=d.isoformat())
                sizes.append(int(ref.manifest.get("size_bytes", 0)))
            except Exception:
                continue
        if not sizes:
            continue
        avg = float(np.mean(sizes))
        if key != "source_checks":
            total_day += avg
        lines.append(f"| {dataset} | {len(sizes)} | {sum(sizes) / 1e6:.1f} MB | "
                     f"{avg / 1e3:.0f} KB | {avg * TEN_YEARS_SESSIONS / 1e6:.0f} MB |")
    out += ["| dataset | days | held | per day | ten years |", "|---|---|---|---|---|", *lines,
            f"\nTen years of the daily datasets: about **{total_day * TEN_YEARS_SESSIONS / 1e6:.0f} MB** "
            f"(R2 free tier: 10 GB).\n"]

    report = "\n".join(out)
    print(report)
    Path(args.out).write_text(report, encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
