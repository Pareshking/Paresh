#!/usr/bin/env python3
"""Build and extend data/nse_prices/ (NSE's own closes and corporate actions).

    python scripts/sync_nse_prices.py --build --cache data_cache/nse_bundles   # from a bundle cache
    python scripts/sync_nse_prices.py --update                                 # fetch the sessions since
    python scripts/sync_nse_prices.py --refresh-actions                        # re-read every action

`--build` keeps the stocks the record needs (the Nifty Total Market, every name the
membership history lists, and the old symbols of the renames in notes.json).
`--update` appends the sessions after the last committed one, read from R2 where
scripts/nse_collect.py stores them (`--source nse` downloads them instead), and then
re-reads every corporate action in the file's span. A source that cannot be read
leaves the committed file as it was.
`--refresh-actions` only re-reads the actions (S56, 12 Oct 2026: the committed file
predated keeping rights rows and their face values, so 14 rights ex-dates since
Sep 2024 moved the NSE closes raw). A refresh never drops an action already on file.
See src/loaders/nse_prices.py.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import src.engine.pipeline  # noqa: E402,F401  (import order: avoids a circular import)
from src.engine.membership import load_history_or_none  # noqa: E402
from src.loaders import former_members, nse_adjusted as na, nse_history as nh  # noqa: E402
from src.loaders import nse_prices as npx  # noqa: E402
from src.loaders.nse_identity import EQUITY_L as EQUITY_LIST  # noqa: E402
from src.loaders.indices_loader import fetch_indices_data  # noqa: E402


def needed(notes: dict) -> list[str]:
    core = fetch_indices_data(["NIFTY TOTAL MARKET"])["Symbol"].unique().tolist()
    syms = set(core) | set(former_members.symbols_needed(load_history_or_none(), core))
    syms |= set(notes.get("renames", {}))
    # The old symbols of renames into anything needed (nse_identity), so the
    # history before a ticker change is kept and joined.
    from src.loaders.nse_identity import auto_renames

    syms |= {old for old, a in auto_renames().items() if a["new_symbol"] in syms}
    return sorted(syms)


def face_values(path: Path = EQUITY_LIST) -> dict[str, float]:
    """Today's face value per symbol, from NSE's equity list (data/reference/nse)."""
    try:
        eq = pd.read_csv(path)
    except (OSError, ValueError):
        return {}
    eq.columns = [str(c).strip().upper() for c in eq.columns]
    if "SYMBOL" not in eq or "FACE VALUE" not in eq:
        return {}
    fv = pd.to_numeric(eq["FACE VALUE"], errors="coerce")
    return {s: float(v) for s, v in zip(eq["SYMBOL"].astype(str).str.strip(), fv) if v > 0}


def keep_actions(actions: pd.DataFrame, symbols: set[str],
                 today_fv: dict[str, float] | None = None) -> pd.DataFrame:
    """The rows that can move a price: splits, bonuses, consolidations, demergers,
    and rights issues with the face value that prices them (nse_adjusted._rights).

    A daily Bc row carries no face value; NSE's yearly list does. A rights row
    without one takes the symbol's face value from another of its rows (the
    nearest in time, as _rights does), else today's from NSE's equity list --
    but only when no split or consolidation since could have changed it.
    """
    if actions.empty:
        return pd.DataFrame(columns=npx.ACTION_COLS)
    a = actions[actions["kind"].isin(na.ACTION_KINDS + ("demerger", "rights")) & actions["symbol"].isin(symbols)]
    a = nh.dedupe_actions(a.assign(record_date=a.get("record_date"), bc_start=a.get("bc_start"),
                                   bc_end=a.get("bc_end")))
    a = a.reindex(columns=list(dict.fromkeys([*npx.ACTION_COLS, *a.columns])))
    a["face_value"] = pd.to_numeric(a["face_value"], errors="coerce")
    all_fv = pd.to_numeric(actions["face_value"], errors="coerce") if "face_value" in actions \
        else pd.Series(float("nan"), index=actions.index)
    all_ex = pd.to_datetime(actions["ex_date"], errors="coerce")
    known = actions.assign(_fv=all_fv, _d=all_ex)[all_fv > 0]
    today_fv = face_values() if today_fv is None else today_fv
    ex = pd.to_datetime(a["ex_date"], errors="coerce")
    for i in a.index[(a["kind"] == "rights") & a["face_value"].isna()]:
        sym = a.at[i, "symbol"]
        k = known[known["symbol"] == sym]
        if len(k):
            a.at[i, "face_value"] = k.loc[(k["_d"] - ex[i]).abs().idxmin(), "_fv"]
            continue
        resplit = (actions["symbol"] == sym) & actions["kind"].isin(["split", "consolidation"]) & (all_ex >= ex[i])
        if sym in today_fv and not resplit.any():
            a.at[i, "face_value"] = today_fv[sym]
    return a[npx.ACTION_COLS].reset_index(drop=True)


def _keys(f: pd.DataFrame) -> pd.Series:
    return (f["symbol"].astype(str) + "|" + f["kind"].astype(str) + "|"
            + pd.to_datetime(f["ex_date"], errors="coerce").dt.strftime("%Y-%m-%d"))


def refreshed(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """The re-read actions, plus any action on file the re-read lacks: never fewer."""
    lost = old[~_keys(old).isin(set(_keys(new)))] if len(old) else old
    out = pd.concat([new, lost.reindex(columns=npx.ACTION_COLS)], ignore_index=True)
    return out.drop_duplicates(subset=["symbol", "series", "kind", "ex_date", "purpose"]).reset_index(drop=True)


def refresh_actions(closes: pd.DataFrame, actions: pd.DataFrame, notes: dict, *,
                    reader=None, archive=None) -> pd.DataFrame:
    """Every corporate action in the committed span, re-read from R2, kept as keep_actions keeps them."""
    from scripts.nse_history_audit import read_actions

    if reader is None:
        from src.storage.r2 import R2Archive, R2Config
        from src.storage.reader import R2DatasetReader

        archive = archive or R2Archive(R2Config.from_env())
        reader = R2DatasetReader(archive)
    since, until = closes.index[0].date(), closes.index[-1].date()
    acts = read_actions(reader, archive or reader.archive, since, until)
    if acts.empty:
        raise RuntimeError("no corporate actions read from R2")
    ex = pd.to_datetime(acts["ex_date"], errors="coerce")
    # A week past the last session: an ex-date on the next one is known before it.
    acts = acts[(ex >= pd.Timestamp(since)) & (ex <= pd.Timestamp(until) + pd.Timedelta(days=7))]
    return refreshed(actions, keep_actions(acts, set(closes.columns) | set(needed(notes))))


def tally(actions: pd.DataFrame) -> str:
    if not len(actions):
        return "none"
    counts = actions["kind"].value_counts()
    fv = pd.to_numeric(actions["face_value"], errors="coerce")
    priced = int(((actions["kind"] == "rights") & (fv > 0)).sum())
    return ", ".join(f"{k} {int(v)}" for k, v in counts.items()) + f" (rights with a face value: {priced})"


def refresh(directory: Path = npx.DIR) -> int:
    data = npx.load(directory)
    if data is None:
        print("nothing committed; run --build first")
        return 1
    try:
        acts = refresh_actions(data["closes"], data["actions"], data["notes"])
    except Exception as exc:  # noqa: BLE001  no credentials, no network: keep the file
        print(f"corporate actions not re-read ({type(exc).__name__}: {exc}); committed file kept")
        return 1
    print(f"actions before: {tally(data['actions'])}")
    print(f"actions after:  {tally(acts)}")
    acts.to_parquet(Path(directory) / "actions.parquet", compression="zstd")
    return 0


def write(closes: pd.DataFrame, actions: pd.DataFrame, directory: Path = npx.DIR) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    closes.sort_index().astype("float32").to_parquet(directory / "closes.parquet", compression="zstd")
    actions.to_parquet(directory / "actions.parquet", compression="zstd")


def special(notes: dict) -> list[date]:
    """Weekend sessions NSE held (notes.json), which no weekday calendar lists."""
    return [date.fromisoformat(d) for d in notes.get("special_sessions", {})]


def build(cache: Path, since: date, until: date) -> int:
    notes = json.loads((npx.DIR / "notes.json").read_text())
    prices, actions, missing = nh.read_cache(cache, since, until, special(notes))
    if prices.empty:
        print("no cached sessions")
        return 1
    wide = na.wide(prices)["close"]
    wide.index = pd.DatetimeIndex(wide.index)
    cols = [s for s in needed(notes) if s in wide.columns]
    write(wide[cols], keep_actions(actions, set(cols)))
    print(f"wrote {len(cols)} symbols x {len(wide)} sessions "
          f"({wide.index[0]:%Y-%m-%d} to {wide.index[-1]:%Y-%m-%d}); {len(missing)} weekdays uncached")
    return 0


def merge_sessions(closes: pd.DataFrame, actions: pd.DataFrame, prices: pd.DataFrame,
                   new_actions: pd.DataFrame, notes: dict) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """(closes, actions, sessions appended): the committed file plus newly read sessions.

    Sessions already on file keep their stored closes; only dates not yet there are added.
    """
    wide = na.wide(prices)["close"]
    wide.index = pd.DatetimeIndex(wide.index)
    cols = [s for s in needed(notes) if s in wide.columns or s in closes.columns]
    merged = pd.concat([closes.reindex(columns=cols), wide.reindex(columns=cols)]).sort_index()
    merged = merged[~merged.index.duplicated(keep="first")]
    acts = pd.concat([actions, keep_actions(new_actions, set(cols))], ignore_index=True)
    acts = acts.drop_duplicates(subset=["symbol", "series", "kind", "ex_date", "purpose"]).reset_index(drop=True)
    return merged, acts, int(len(merged) - len(closes))


def update(pause: float, source: str = "r2") -> int:
    data = npx.load()
    if data is None:
        print("nothing committed to extend; run --build first")
        return 1
    closes, actions, notes = data["closes"], data["actions"], data["notes"]
    last = closes.index[-1].date()
    days = sorted(set(nh.weekdays(last + timedelta(days=1), date.today()))
                  | {d for d in special(notes) if d > last})
    if not days:
        print(f"up to date ({last})")
        return refresh() if source == "r2" else 0
    if source == "r2":
        # The collector keeps every session on R2 (nse_collect.yml); read them there.
        try:
            prices, new_actions, bad = nh.read_r2(days[0], days[-1])
        except Exception as exc:  # noqa: BLE001  no credentials, no network: keep the file
            print(f"R2 unreadable ({type(exc).__name__}: {exc}); committed file kept")
            return 1
        print(f"{len(days)} weekdays since {last}: {prices['date'].nunique() if len(prices) else 0} on R2"
              + (f", unreadable: {bad}" if bad else ""))
        if bad:
            return 1                       # a half-read month would be a silent gap
    else:
        with tempfile.TemporaryDirectory() as tmp:
            tally = nh.fetch_days(days, Path(tmp), pause=pause)
            prices, new_actions, _ = nh.read_cache(Path(tmp), days[0], days[-1], special(notes))
        print(f"{len(days)} weekdays since {last}: {tally}")
        if prices.empty and tally["blocked"]:
            return 1
    if prices.empty:
        print("no new sessions; committed file kept")
        return 0
    merged, acts, added = merge_sessions(closes, actions, prices, new_actions, notes)
    write(merged, acts)
    print(f"appended {added} sessions; file now ends {merged.index[-1]:%Y-%m-%d}")
    if source == "r2":
        refresh()                          # a failure keeps the actions just written
    return 0


def rehearse_append(sessions: int = 5) -> int:
    """Run the real append path on a copy of the file with its last sessions cut off.

    Reads those sessions from R2, merges them back through `merge_sessions` and checks the
    result equals what is committed. Nothing is written. It proves the append works with
    live R2 without waiting for a new trading day. A session R2 does not hold yet (the
    collector runs every four hours) is skipped, not counted as a failure.
    """
    data = npx.load()
    if data is None:
        print("nothing committed to rehearse on")
        return 1
    closes, actions, notes = data["closes"], data["actions"], data["notes"]
    try:
        from src.storage.r2 import R2Archive, R2Config

        r2 = nh.r2_days(R2Archive(R2Config.from_env()))
    except Exception as exc:  # noqa: BLE001
        print(f"R2 unreadable: {type(exc).__name__}: {exc}")
        return 1
    held = [d for d in closes.index if d.date() in r2]
    cut = held[-sessions:]
    if not cut:
        print("no committed session is on R2 to rehearse with")
        return 1
    trimmed = closes.loc[~closes.index.isin(cut)]
    prices, new_actions, bad = nh.read_r2(cut[0].date(), cut[-1].date())
    if bad:
        print(f"unreadable on R2: {bad}")
        return 1
    merged, _acts, added = merge_sessions(trimmed, actions, prices, new_actions, notes)
    back = merged.reindex(index=cut, columns=closes.columns)
    off = int(((back - closes.loc[cut]).abs().stack() > 0.01).sum())
    behind = [str(d.date()) for d in closes.index[-3:] if d.date() not in r2]
    print(f"rehearsal: cut {len(cut)} sessions ({cut[0]:%Y-%m-%d} to {cut[-1]:%Y-%m-%d}), re-read from R2, "
          f"{added} appended, {off} closes differ from the committed file; "
          f"committed but not yet on R2: {behind or 'none'}")
    return 0 if (added == len(cut) and off == 0) else 1


def verify_r2(days: int = 10) -> int:
    """Read the last sessions on file back from R2 and compare their closes.

    Proves the R2 read works with the live credentials (an `--update` with nothing
    new never touches R2) and that R2 and the committed file agree.
    """
    data = npx.load()
    if data is None:
        print("nothing committed to compare")
        return 1
    closes = data["closes"]
    tail = closes.index[-days:]
    try:
        prices, _, bad = nh.read_r2(tail[0].date(), tail[-1].date())
    except Exception as exc:  # noqa: BLE001
        print(f"R2 unreadable: {type(exc).__name__}: {exc}")
        return 1
    wide = na.wide(prices)["close"] if len(prices) else pd.DataFrame()
    wide.index = pd.DatetimeIndex(wide.index)
    cols = [c for c in wide.columns if c in closes.columns]
    both = wide.reindex(index=tail, columns=cols)
    diff = (both - closes.loc[tail, cols]).abs()
    off = int((diff.stack() > 0.01).sum()) if len(cols) else -1
    missing = [str(d.date()) for d in tail if d not in wide.index]
    print(f"R2 read: {len(wide)} of the last {len(tail)} sessions on file, {len(cols)} symbols, "
          f"{off} closes differ by more than 0.01; sessions missing on R2: {missing or 'none'}; "
          f"unreadable: {bad or 'none'}")
    return 0 if (off == 0 and not missing and not bad) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build", action="store_true", help="rebuild from a bundle cache")
    mode.add_argument("--verify-r2", action="store_true",
                      help="read the last sessions back from R2 and compare with the file")
    mode.add_argument("--rehearse-append", action="store_true",
                      help="cut the last committed sessions, re-append them from R2, compare; writes nothing")
    mode.add_argument("--update", action="store_true",
                      help="append the sessions since the last one on file, then re-read the actions")
    mode.add_argument("--refresh-actions", action="store_true",
                      help="re-read every corporate action in the file's span from R2")
    ap.add_argument("--cache", default="data_cache/nse_bundles")
    ap.add_argument("--since", default="2024-09-30")
    ap.add_argument("--until", default=None)
    ap.add_argument("--source", choices=["r2", "nse"], default="r2",
                    help="r2: the days the collector already stored (default); nse: download them")
    ap.add_argument("--pause", type=float, default=1.0)
    args = ap.parse_args()
    if args.verify_r2:
        return verify_r2()
    if args.rehearse_append:
        return rehearse_append()
    if args.refresh_actions:
        return refresh()
    if args.build:
        until = date.fromisoformat(args.until) if args.until else date.today()
        return build(Path(args.cache), date.fromisoformat(args.since), until)
    return update(args.pause, args.source)


if __name__ == "__main__":
    raise SystemExit(main())
