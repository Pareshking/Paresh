"""Nightly three-source check: SS, Screener and NSE, with NSE as the judge.

    python scripts/reconcile_report.py --ss data_cache/ss --actions bc.parquet
    python scripts/reconcile_report.py --ss data_cache/ss --start 2025-10-01 --out reports/reconcile

Reads SS's store (src/loaders/ss_prices.py), Screener's published store and
NSE's committed closes (split/bonus/demerger adjusted, nse_prices), takes
NSE's corporate-action rows from --actions (a parquet of
nse_bundle.parse_corporate_actions rows) or else from the committed
data/nse_prices/actions.parquet plus, when R2 is configured, R2's
nse/corporate_actions, and runs src/engine/reconcile.py over them.

Writes to --out: report.md (what a person reads), summary.json, and the
detail as CSV -- rights.csv, votes.csv (every session the sources did not
all agree on, and what was used), drifts.csv (lasting level shifts nobody
explained) and filled.csv (sessions SS lacked, filled from the others).
Never changes a stored price: it reports what the reconciled series would be.
Exit status 1 only when there is nothing to compare.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.engine import reconcile as rc  # noqa: E402
from src.loaders import ss_prices  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def load_ss(directory: Path, start, end) -> pd.DataFrame:
    rows = ss_prices.to_rupees(ss_prices.read_store(directory, start=start, end=end))
    if rows.empty:
        return pd.DataFrame()
    rows["date"] = pd.to_datetime(rows["date"])
    frame = rows.pivot(index="date", columns="symbol", values="close")
    return frame.drop(columns=[c for c in ss_prices.INDEX_SYMBOLS if c in frame.columns])


def load_screener(path: Path | None, start, end) -> pd.DataFrame | None:
    if path is not None:
        store = pd.read_parquet(path)
    else:
        from src.loaders import nse_prices

        store = nse_prices.screener_store()
    if store is None or store.empty or not isinstance(store.columns, pd.MultiIndex):
        return None
    close = store.xs("Close", axis=1, level=-1)
    close.index = pd.to_datetime(close.index).normalize()
    close = close[~close.index.duplicated(keep="last")].sort_index()
    return close.loc[start:end]


def load_nse(symbols, start, end) -> pd.DataFrame | None:
    from src.loaders import nse_prices

    frame = nse_prices.middle_close(symbols)
    if frame is None:
        return None
    frame.index = pd.to_datetime(frame.index)
    return frame.loc[start:end]


def read_r2(start, end) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """(prices, actions) from NSE's daily files on R2 -- every security, raw -- or None."""
    try:
        from src.loaders import nse_history

        prices, actions, _bad = nse_history.read_r2(
            (pd.Timestamp(start) - pd.Timedelta(days=60)).date(), pd.Timestamp(end).date())
        return prices, actions
    except Exception as exc:  # noqa: BLE001  the committed files still serve
        print(f"  NSE files on R2 unavailable ({type(exc).__name__})")
        return None


def load_actions(path: Path | None, r2_actions: pd.DataFrame | None) -> pd.DataFrame | None:
    """NSE's corporate-action rows: --actions, else the committed file plus R2's."""
    if path is not None:
        return pd.read_parquet(path)
    from src.loaders import nse_prices

    committed = nse_prices.load()
    frames = [f for f in (committed["actions"] if committed else None, r2_actions)
              if f is not None and not f.empty]
    if not frames:
        return None
    both = pd.concat(frames, ignore_index=True)
    both["ex_date"] = pd.to_datetime(both["ex_date"])
    return both.drop_duplicates(["symbol", "ex_date", "purpose"])


def complete_nse(nse: pd.DataFrame | None, symbols, r2_prices: pd.DataFrame | None,
                 actions: pd.DataFrame | None, start, end) -> pd.DataFrame | None:
    """NSE's closes for every stock: the committed set, then R2's raw daily files,
    split/bonus adjusted the same way (nse_prices.adjusted_close), for the rest.

    So NSE can judge every stock, and anchor every rights issue -- neither the
    committed set nor this adjusts rights.
    """
    have = set(nse.columns) if nse is not None else set()
    missing = [s for s in symbols if s not in have]
    if not missing or r2_prices is None or r2_prices.empty:
        return nse
    from src.loaders import nse_adjusted, nse_prices

    raw = nse_adjusted.wide(r2_prices)["close"]
    raw.index = pd.DatetimeIndex(raw.index)
    acts = actions if actions is not None else pd.DataFrame(columns=nse_prices.ACTION_COLS)
    extra, _report = nse_prices.adjusted_close(raw, acts, missing)
    extra.index = pd.to_datetime(extra.index)
    extra = extra.loc[start:end].astype(float)
    return extra if nse is None else pd.concat([nse, extra], axis=1)


def write_report(result: rc.Reconciled, out: Path, start, end, notes: list[str]) -> str:
    out.mkdir(parents=True, exist_ok=True)
    s = result.summary()
    for name in ("rights", "votes", "drifts", "filled"):
        getattr(result, name).to_csv(out / f"{name}.csv", index=False)
    (out / "summary.json").write_text(json.dumps(
        {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "window": [str(start), str(end)], **s, "notes": notes}, indent=1) + "\n", encoding="utf-8")

    v = result.votes
    lines = [
        f"# Price check {start} → {end}",
        "",
        f"{s['stocks']} stocks, {s['sessions']} sessions. SS is the primary source; "
        "Screener and NSE vote; NSE (the exchange's own record) settles anything else.",
        "",
        "| | |",
        "|---|---|",
        f"| Rights issues (SS already adjusted / we adjusted / check) | {s['rights_issues']} "
        f"({s['rights_issues'] - s['rights_applied'] - s['rights_to_check']} / {s['rights_applied']} / "
        f"{s['rights_to_check']}) |",
        f"| Sessions where SS was outvoted (2 of 3 used) | {s['ss_outvoted']} |",
        f"| Sessions where another source was outvoted | {s['majority_corrections'] - s['ss_outvoted']} |",
        f"| Two sources disagreed, NSE used | {s['judge_used']} |",
        f"| **Unresolved — look at these** (NSE's move used; SS's where NSE has none) | **{s['unresolved']}** |",
        f"| **Lasting level shifts nobody explained — look at these** | **{s['level_drifts']}** |",
        f"| Level shifts on a known corporate action (sources chose different factors) | "
        f"{s['action_drifts']} |",
        f"| Sessions SS lacked, filled from the others | {s['sessions_filled']} |",
        "",
    ]
    if len(result.rights):
        basis_text = {"raw": "not adjusted → factor applied",
                      "adjusted": "already adjusted",
                      "own_factor": "adjusted with its own factor — check",
                      "unknown": "no NSE price to tell — check"}
        lines += ["## Rights issues", "",
                  "| Stock | Ex-date | Terms | Factor | SS | Screener's own |",
                  "|---|---|---|---|---|---|"]
        for r in result.rights.itertuples():
            chk = f"{r.check_factor:.4f}" if pd.notna(r.check_factor) else "—"
            fv = " (face value assumed Re 1)" if r.face_value_assumed else \
                f" (face value ₹{r.face_value:g})" if r.face_value != 1 else ""
            own = f" ({np.exp(-r.ss_gap):.4f})" if r.ss_basis == "own_factor" else ""
            lines.append(f"| {r.symbol} | {pd.Timestamp(r.ex_date).date()} | {r.new:g}:{r.held:g} at "
                         f"₹{r.issue_price:,.2f}{fv} | {r.factor:.4f} | "
                         f"{basis_text.get(r.ss_basis, r.ss_basis)}{own} | {chk} |")
        lines.append("")
    flagged = v[v["verdict"] == "unresolved"] if len(v) else v
    if len(flagged):
        lines += ["## Unresolved sessions (NSE's move used; SS's where NSE has none)", "",
                  "| Stock | Date | SS | Screener | NSE |", "|---|---|---|---|---|"]
        for r in flagged.head(50).itertuples():
            cells = [getattr(r, f"move_{n}", float("nan")) for n in ("ss", "screener", "nse")]
            lines.append(f"| {r.symbol} | {r.date.date()} | " + " | ".join(
                f"{c:+.2%}" if pd.notna(c) else "—" for c in cells) + " |")
        lines.append("")
    if len(result.drifts):
        lines += ["## Lasting level shifts (SS vs Screener)", "",
                  "| Stock | From | Shift | Corporate action |", "|---|---|---|---|"]
        for r in result.drifts.sort_values("action").itertuples():
            act = r.action or "**none — look at this**"
            lines.append(f"| {r.symbol} | {pd.Timestamp(r.date).date()} | {r.shift:+.2%} | {act} |")
        lines.append("")
    outvoted = v[(v["verdict"] == "majority")] if len(v) else v
    if len(outvoted):
        lines += ["## Outvoted sources (top stocks)", ""]
        top = outvoted.groupby(["odd", "symbol"]).size().sort_values(ascending=False).head(15)
        for (odd, sym), n in top.items():
            lines.append(f"- {sym}: {odd} outvoted on {n} session(s)")
        lines.append("")
    for note in notes:
        lines.append(f"> {note}")
    text = "\n".join(lines) + "\n"
    (out / "report.md").write_text(text, encoding="utf-8")
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ss", type=Path, default=ROOT / "data_cache" / "ss")
    ap.add_argument("--screener", type=Path, default=None, help="a Screener store file (default: published)")
    ap.add_argument("--actions", type=Path, default=None, help="NSE corporate-action rows (default: committed + R2)")
    ap.add_argument("--r2", action="store_true", help="read NSE's daily files on R2 even with --actions")
    ap.add_argument("--start", type=date.fromisoformat, default=None, help="default: one year back")
    ap.add_argument("--end", type=date.fromisoformat, default=None)
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "reconcile")
    args = ap.parse_args(argv)

    end = pd.Timestamp(args.end or date.today())
    start = pd.Timestamp(args.start or (end - pd.DateOffset(years=1)).date())
    notes: list[str] = []
    ss = load_ss(args.ss, start, end)
    if ss.empty:
        print("No SS prices in the window; nothing to compare.")
        return 1
    screener = load_screener(args.screener, start, end)
    if screener is None:
        notes.append("Screener's store was unavailable: only SS and NSE voted.")
    nse = load_nse(list(ss.columns), start, end)
    r2 = read_r2(start, end) if args.actions is None or args.r2 else None
    actions = load_actions(args.actions, r2[1] if r2 else None)
    if actions is None:
        notes.append("NSE's corporate actions were unavailable: rights issues were not adjusted.")
    nse = complete_nse(nse, list(ss.columns), r2[0] if r2 else None, actions, start, end)
    if nse is None:
        notes.append("NSE's closes were unavailable: only SS and Screener voted.")
    elif nse.shape[1] < ss.shape[1]:
        notes.append(f"NSE had no closes for {ss.shape[1] - nse.shape[1]} of {ss.shape[1]} stocks: "
                     "there SS and Screener vote alone.")
    result = rc.reconcile(ss, screener, nse, actions)
    text = write_report(result, args.out, start.date(), end.date(), notes)
    print(text)
    print(f"RECONCILE {json.dumps(result.summary())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
