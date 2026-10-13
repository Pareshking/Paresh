#!/usr/bin/env python3
"""Daily closes for the stocks NSE's committed file lacks over Screener's weekly stretch.

    python scripts/build_weekly_fill_extra.py --long nse_long_close.parquet --bse bse_daily.parquet
    python scripts/build_weekly_fill_extra.py --nano --raw-pack nse_raw_pack.parquet \
        --actions-pack nse_actions_pack.parquet --actions-list r2 --bse bse_daily.parquet
    python scripts/build_weekly_fill_extra.py --nano --if-missing ...   # only when a Nano Cap stock is not on file

Owner, 2026-10-07 (TODO S23): fill Screener's weekly stretch with daily
closes for these seven too. data/nse_prices (the app's NSE file) has no REIT
rows and starts JSLL in Aug 2025; four stocks traded only on BSE until they
listed on NSE (SGMART Sep 2025, SHILCTECH Nov 2025, TIMEX Apr 2026, PICCADIL
Jul 2025). The stretch (Oct 2024 - Sep 2025) is history, so the file is built
once and committed; price_source.splice_weekly reads it only where NSE's file
has no close, and the same 2% check against Screener's own weekly moves
applies to every interval.

Sources: the long NSE file (release data-latest; adjusted) for BIRET, EMBASSY
and JSLL; BSE's bhavcopy (scripts/bse_bhavcopy.py; raw, as traded) for the
four, the BSE code found by the ISIN in data/reference/nse/equity_l.csv.
Only NSE sessions are kept (the frame's calendar), and only days BSE traded.

`--nano` (owner, 13 Oct 2026, TODO S57: "do it") writes a second file,
data/reference/weekly_fill_nano.parquet, so Nano Cap and Combined get the same
fill: NSE's own closes for every stock any Nano Cap list has held (the current
list and data/nanocap_membership.json), from 1 Oct 2024, read from the long
file's raw-history pack (every NSE row, SME series included) and adjusted
exactly as the app's NSE file is (nse_prices.adjusted_close with the actions
pack and NSE's yearly list: splits, bonuses, consolidations, demergers and
rights, merged as the long file merges them); before a stock listed on NSE,
BSE's closes (--bse), scaled to NSE's adjustment at the first NSE session. NSE's committed
file holds most of these stocks only from Oct 2026. The daily sync runs it
with `--if-missing`, so a stock that joins the list later is added without a
hand step.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "reference" / "weekly_fill_extra.parquet"
NANO_OUT = ROOT / "data" / "reference" / "weekly_fill_nano.parquet"
NANO_START = pd.Timestamp("2024-10-01")
FROM_LONG = ("BIRET", "EMBASSY", "JSLL")
FROM_BSE = ("SGMART", "SHILCTECH", "TIMEX", "PICCADIL")
START, END = pd.Timestamp("2024-10-01"), pd.Timestamp("2025-10-01")

# BSE's closes are raw. An action inside the stretch, before the stock listed on
# NSE, is in no NSE list, so it is applied here with its evidence: each close
# before the ex-date times the factor (the long file's rule).
ACTIONS = [
    {"symbol": "SHILCTECH", "ex_date": "2025-06-06", "factor": 2 / 3,
     "evidence": "1:2 bonus, record date 6 Jun 2025 (Business Standard 29 May 2025, 'Shilchar "
                 "Technologies fixes record date for bonus issue'); shares 76,26,800 -> 1,14,40,200; "
                 "BSE close 8287.75 -> 6007.75, Screener and Tijori adjusted by 2/3"},
]


def isins(path: Path = ROOT / "data" / "reference" / "nse" / "equity_l.csv") -> dict[str, str]:
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    key = next(k for k in rows[0] if k.strip().upper() == "ISIN NUMBER")
    return {r["SYMBOL"].strip(): r[key].strip() for r in rows}


def build(long_close: pd.DataFrame, bse: pd.DataFrame, isin_of: dict[str, str]) -> tuple[pd.DataFrame, list[dict]]:
    sessions = long_close.index[(long_close.index >= START) & (long_close.index <= END)]
    out = pd.DataFrame(index=sessions, dtype=float)
    notes = []
    for s in FROM_LONG:
        out[s] = long_close[s].reindex(sessions)
        notes.append({"symbol": s, "source": "nse_long_close", "days": int(out[s].notna().sum())})
    b = bse.copy()
    b["date"] = pd.to_datetime(b["date"])
    b = b[(b["date"] >= START) & (b["date"] <= END) & (b["shares"] > 0) & (b["close"] > 0)]
    for s in FROM_BSE:
        codes = sorted(set(b.loc[b["isin"].astype("string").str.strip() == isin_of[s], "code"]))
        if len(codes) != 1:
            raise SystemExit(f"{s}: ISIN {isin_of[s]} maps to BSE codes {codes}, not one")
        rows = b[b["code"] == codes[0]].drop_duplicates("date").set_index("date")["close"]
        out[s] = rows.reindex(sessions)
        for a in (x for x in ACTIONS if x["symbol"] == s):
            out.loc[out.index < pd.Timestamp(a["ex_date"]), s] *= a["factor"]
        notes.append({"symbol": s, "source": f"bse code {codes[0]} (ISIN {isin_of[s]})",
                      "days": int(out[s].notna().sum())})
    out.index.name = "date"
    return out.astype("float64"), notes


def nano_symbols(root: Path = ROOT) -> set[str]:
    """Every stock the Nano Cap list holds now or held at any month-end on file,
    less today's 750: the 750's frame is not this file's to change (S57 was asked
    for Nano Cap and Combined; KMEW, once on the list, would take BSE closes)."""
    from src.loaders import extra_universe_loader as xl

    syms = set(xl.members()["Symbol"].astype(str))
    path = root / "data" / "nanocap_membership.json"
    if path.exists():
        for month in json.loads(path.read_text()).get("months", {}).values():
            syms |= {str(x).strip().upper() for x in month.get("symbols", [])}
    tm = pd.read_csv(root / "data" / "indices" / "ind_niftytotalmarket_list.csv")
    tm.columns = [str(c).strip() for c in tm.columns]
    return syms - set(tm["Symbol"].astype(str).str.strip().str.upper())


def missing(path: Path, symbols: set[str]) -> set[str]:
    """The symbols `path` has no column for (all of them when there is no file)."""
    if not path.exists():
        return set(symbols)
    import pyarrow.parquet as pq

    have = set(pq.ParquetFile(path).schema_arrow.names)
    return set(symbols) - have


def list_actions(source: str) -> pd.DataFrame:
    """NSE's yearly corporate-action list: a folder or zip of the API's y<year>.json
    files (release data-latest, ref_nse_action_list_api_*.zip), or "r2" for the
    copy scripts/import_nse_history.py keeps on R2 (needs the R2 secrets)."""
    from src.loaders import nse_backfill as bf, nse_history as nh

    if source == "r2":
        from src.storage.r2 import R2Archive, R2Config
        from src.storage.reader import R2DatasetReader

        archive = R2Archive(R2Config.from_env())
        reader = R2DatasetReader(archive)
        frames = [reader.read_parquet(reader.resolve_current(nh.R2_ACTIONS_HISTORY, as_of=d.isoformat()))
                  for d in sorted(nh.r2_days(archive, nh.R2_ACTIONS_HISTORY))]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    import zipfile

    path, rows = Path(source), []
    if path.is_dir():
        for f in sorted(path.rglob("y*.json")):
            rows += json.loads(f.read_text(encoding="utf-8"))
    else:
        with zipfile.ZipFile(path) as z:
            for name in sorted(n for n in z.namelist() if Path(n).name.startswith("y") and n.endswith(".json")):
                rows += json.loads(z.read(name))
    return bf.api_actions(rows)


def merged_actions(bc_rows: pd.DataFrame, yearly: pd.DataFrame) -> pd.DataFrame:
    """The daily Bc rows and the yearly list, one row per action, as
    scripts/nse_history_audit.read_actions merges them for the long file."""
    from src.loaders import nse_bundle as nb

    frames = []
    if len(yearly):
        frames.append(yearly.assign(source="list"))
    if len(bc_rows):
        rows = bc_rows.sort_values("r2_day", ascending=False, kind="stable") if "r2_day" in bc_rows else bc_rows
        frames.append(rows.drop(columns="r2_day", errors="ignore").assign(source="bc"))
    if not frames:
        return pd.DataFrame()
    acts = pd.concat(frames, ignore_index=True)
    acts = nb.repair_swapped_dates(acts).drop_duplicates(["symbol", "ex_date", "purpose"])
    parsed = pd.DataFrame([nb.classify_purpose(p) for p in acts["purpose"]], index=acts.index)
    acts[["kind", "price_factor"]] = parsed[["kind", "price_factor"]]
    return nb.drop_swapped_twins(acts)


def before_nse(adjusted: pd.DataFrame, raw_close: pd.DataFrame, bse: pd.DataFrame,
               isin_of: dict[str, str]) -> tuple[pd.DataFrame, list[dict]]:
    """`adjusted` with BSE's closes for the sessions before a stock's first NSE close.

    A stock that traded only on BSE before listing on NSE (ADVAIT, JAYKAY,
    SHUKRAPHAR) has no NSE row then. BSE's closes are raw: each is scaled by the
    stock's adjustment at its first NSE session (adjusted / raw close that day),
    so actions after listing reach them as they reach NSE's own closes. An
    action before listing is in no NSE list; the weekly fill's 2% check refuses
    that week. The BSE code is the one BSE files the stock's current ISIN under
    (its older rows too, whatever ISIN they carry); a stock with no single code
    is left out and listed.
    """
    out, notes = adjusted.copy(), []
    b = bse[(bse["shares"] > 0) & (bse["close"] > 0)].copy()
    b["date"] = pd.to_datetime(b["date"])
    b_isin = b["isin"].astype("string").str.strip()
    for s in adjusted.columns:
        first = adjusted[s].first_valid_index()
        if first is None or first <= adjusted.index[0] or s not in isin_of:
            continue
        codes = sorted(set(b.loc[b_isin == isin_of[s], "code"]))
        if len(codes) != 1:
            notes.append({"symbol": s, "bse": f"ISIN {isin_of[s]} maps to codes {codes}; not filled"})
            continue
        ref = raw_close.at[first, s] if s in raw_close.columns else float("nan")
        if not (pd.notna(ref) and ref > 0):
            continue
        scale = float(adjusted.at[first, s]) / float(ref)
        rows = b[b["code"] == codes[0]].drop_duplicates("date").set_index("date")["close"]
        days = adjusted.index[adjusted.index < first]
        vals = rows.reindex(days) * scale
        if not vals.notna().any():
            continue
        out.loc[days, s] = out.loc[days, s].fillna(vals.astype("float32"))
        notes.append({"symbol": s, "bse": f"code {codes[0]}", "days": int(vals.notna().sum()),
                      "until": str(first.date())})
    return out, notes


def build_nano(raw: pd.DataFrame, actions: pd.DataFrame, symbols: set[str],
               notes: dict | None = None, bse: pd.DataFrame | None = None,
               ) -> tuple[pd.DataFrame, dict]:
    """NSE-adjusted closes from NANO_START for `symbols`, as the app's NSE file adjusts them.

    `raw` is NSE's bhavcopy rows (the long file's raw pack), `actions` NSE's
    corporate-action rows (merged_actions: its actions pack and the yearly
    list, which alone carries many SME splits). A renamed stock's old symbol is
    read too and joined under the current one (nse_identity).
    """
    import src.engine.pipeline  # noqa: F401  (import order: avoids a circular import)
    from scripts.sync_nse_prices import keep_actions
    from src.loaders import nse_adjusted as na, nse_prices as npx
    from src.loaders.nse_identity import auto_renames

    raw = raw[pd.to_datetime(raw["date"]) >= NANO_START]
    wide = na.wide(raw)["close"]
    wide.index = pd.DatetimeIndex(wide.index)
    olds = {o for o, a in auto_renames(set(wide.columns)).items() if a["new_symbol"] in symbols}
    closes = wide[sorted((set(symbols) | olds) & set(wide.columns))]
    adjusted, report = npx.adjusted_close(closes, keep_actions(actions, set(closes.columns)),
                                          sorted(symbols), notes=notes)
    if bse is not None and len(bse):
        adjusted, report["from_bse"] = before_nse(adjusted, closes, bse, isins())
    adjusted.index.name = "date"
    return adjusted.astype("float32"), report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--long", type=Path)
    ap.add_argument("--bse", type=Path)
    ap.add_argument("--nano", action="store_true", help="build weekly_fill_nano.parquet instead")
    ap.add_argument("--raw-pack", type=Path, help="--nano: nse_raw_pack.parquet (release data-latest)")
    ap.add_argument("--actions-pack", type=Path, help="--nano: nse_actions_pack.parquet (release data-latest)")
    ap.add_argument("--actions-list", default=None,
                    help="--nano: NSE's yearly action list, a folder/zip of y<year>.json or 'r2'")
    ap.add_argument("--if-missing", action="store_true",
                    help="--nano: exit 0 when every Nano Cap stock is on file; else, with no packs "
                         "given, name the missing ones and exit 3")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    if args.nano:
        out = args.out or NANO_OUT
        symbols = nano_symbols()
        lacking = missing(out, symbols)
        if args.if_missing and not lacking:
            print(f"{out.name}: all {len(symbols)} Nano Cap stocks on file")
            return 0
        if not (args.raw_pack and args.actions_pack):
            if args.if_missing:
                print(f"{len(lacking)} Nano Cap stocks not on file: {', '.join(sorted(lacking)[:20])}")
                return 3
            ap.error("--nano needs --raw-pack and --actions-pack")
        from src.loaders import nse_prices as npx

        data = npx.load()
        yearly = list_actions(args.actions_list) if args.actions_list else pd.DataFrame()
        actions = merged_actions(pd.read_parquet(args.actions_pack), yearly)
        print(f"actions: {len(actions):,} ({len(yearly):,} from the yearly list)")
        bse = (pd.read_parquet(args.bse, columns=["date", "code", "close", "shares", "isin"])
               if args.bse else None)
        frame, report = build_nano(pd.read_parquet(args.raw_pack), actions,
                                   symbols, notes=data["notes"] if data else None, bse=bse)
        out.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(out, compression="zstd")
        print({k: v for k, v in report.items() if k != "renames_landed"})
        print(f"wrote {out}: {frame.shape[0]} sessions x {frame.shape[1]} stocks "
              f"({len(lacking)} were not on file)")
        return 0
    if not (args.long and args.bse):
        ap.error("--long and --bse are required (or --nano)")
    args.out = args.out or OUT
    frame, notes = build(pd.read_parquet(args.long),
                         pd.read_parquet(args.bse, columns=["date", "code", "close", "shares", "isin"]), isins())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.out)
    for n in notes:
        print(n)
    print(f"wrote {args.out}: {frame.shape[0]} sessions x {frame.shape[1]} stocks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
