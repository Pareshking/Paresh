"""Check the long NSE price file against independent price histories, every stock, every day.

    python scripts/audit_long_prices.py --ours nse_long_close.parquet \
        --ref yahoo=yahoo_close.parquet --ref screener=screener_prices.parquet --out audit/

The long file (scripts/build_nse_long_prices.py) is NSE's own closes adjusted
for splits, bonuses and demergers on today's basis. A reference adjusted the
same way should sit on the same level every day, so the log of ours / theirs is
flat. Three checks:

1. LEVELS. For each stock and reference, the share of common days within 2%
   and within 5% (dividends are not in either; a reference that adjusts for
   them drifts slowly, never steps).
2. BREAKS. Days the log ratio steps by more than 5% and stays there (the
   median of the next 10 common days against the previous 10). Whichever
   series moved that day is the one at fault: ours jumping while the
   reference is flat is an action we missed, or applied wrongly.
3. BIG MOVES. Every day our close moved more than 21% either way. Each
   reference covering the day either agrees (moved the same way within 5%,
   or over the two days around it, as references sometimes date a split a
   day apart) or is flat (moved less than 10%). Confirmed when more agree
   than are flat, fake when more are flat, disputed on a tie, unverified
   when no reference covers it.

A reference is wide (dates x symbols), or a (symbol, field) frame with a Close
field. Nothing here reaches the network.

--no-confirm names references that leave some older actions unadjusted (NSE's
MarketLens keeps BHARTIARTL's 2009 and TATACONSUM's 2010 splits as raw falls;
TejHQ adjusts only within an ISIN, and a split changes it). Such a reference
can show a move is fake -- flat on the day ours jumped -- but its own jump
never confirms ours.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BIG = np.log(1.21)       # the owner's line (2026-10-03): a move beyond 21% either way
STEP = np.log(1.05)      # a break in the level against a reference
SAME = np.log(1.05)      # a reference "moved the same way" within 5%
FLAT = np.log(1.10)      # a reference that moved less than 10% did not see the move
WINDOW = 10              # common days either side of a break


def closes(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if isinstance(frame.columns, pd.MultiIndex):
        frame = frame.xs("Close", axis=1, level=1)
    frame.index = pd.DatetimeIndex(frame.index).normalize()
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    return frame.apply(pd.to_numeric, errors="coerce").where(lambda x: x > 0).astype("float64")


def levels(ours: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    """Per stock: common days, and the share within 2% and 5% of the reference."""
    cols = ours.columns.intersection(ref.columns)
    a, b = ours[cols].align(ref[cols], join="inner")
    lr = np.log(a / b)
    n = lr.notna().sum()
    return pd.DataFrame({
        "days": n,
        "within_2pct": (lr.abs() <= np.log(1.02)).sum() / n.replace(0, np.nan),
        "within_5pct": (lr.abs() <= np.log(1.05)).sum() / n.replace(0, np.nan),
        "median_gap": np.exp(lr.median()) - 1,
        "first": lr.apply(lambda s: s.first_valid_index()),
        "last": lr.apply(lambda s: s.last_valid_index()),
    })


def breaks(ours: pd.DataFrame, ref: pd.DataFrame, name: str) -> pd.DataFrame:
    """Days the level against the reference steps and stays stepped, and who moved."""
    rows = []
    for sym in ours.columns.intersection(ref.columns):
        both = pd.concat([ours[sym], ref[sym]], axis=1, keys=["o", "r"]).dropna()
        if len(both) < 2 * WINDOW + 1:
            continue
        lr = np.log(both["o"] / both["r"]).to_numpy()
        step = np.abs(np.diff(lr))
        for i in np.flatnonzero(step > STEP) + 1:
            before = np.median(lr[max(0, i - WINDOW):i])
            after = np.median(lr[i:i + WINDOW])
            if abs(after - before) <= STEP or i < 3 or i + 3 > len(lr):
                continue
            mo = both["o"].iloc[i] / both["o"].iloc[i - 1]
            mr = both["r"].iloc[i] / both["r"].iloc[i - 1]
            rows.append({"symbol": sym, "ref": name, "date": both.index[i].date(),
                         "level_step": float(np.exp(after - before)), "ours_move": float(mo),
                         "ref_move": float(mr),
                         "who": ("ours" if abs(np.log(mo)) > abs(np.log(mr)) else name)})
    return pd.DataFrame(rows, columns=["symbol", "ref", "date", "level_step", "ours_move",
                                       "ref_move", "who"])


def big_moves(ours: pd.DataFrame, refs: dict[str, pd.DataFrame],
              no_confirm: frozenset[str] = frozenset()) -> pd.DataFrame:
    """Every move beyond 21% in ours, with what each reference did that day."""
    prev = ours.ffill().shift(1)
    move = ours / prev
    hit = (np.log(move).abs() > BIG) & ours.notna()
    rows = []
    for (day, sym) in hit.stack()[lambda s: s].index:
        m = float(move.at[day, sym])
        row = {"symbol": sym, "date": day.date(), "move": m}
        seen, agree, flat = 0, 0, 0
        for name, ref in refs.items():
            if sym not in ref.columns:
                continue
            s = ref[sym].dropna()
            if day not in s.index or s.index.get_loc(day) == 0:
                continue
            i = s.index.get_loc(day)
            # A reference may skip days (Screener is every 2-4 days in 2021-2024),
            # so ours is measured over the reference's own span, not one session.
            o = ours[sym].ffill()
            def span(a, b):
                return (s.iloc[b] / s.iloc[a], o.get(s.index[b], np.nan) / o.get(s.index[a], np.nan))
            r1, o1 = span(i - 1, i)
            r2, o2 = span(max(i - 2, 0), min(i + 1, len(s) - 1))
            row[f"{name}_move"] = float(r1)
            seen += 1
            if (np.isfinite(o1) and abs(np.log(r1 / o1)) <= SAME) or (
                    np.isfinite(o2) and abs(np.log(r2 / o2)) <= SAME and abs(np.log(r2)) > BIG / 2):
                if name in no_confirm:
                    seen -= 1          # its jump says nothing either way
                else:
                    agree += 1
            elif abs(np.log(r1)) < FLAT and abs(np.log(r2)) < FLAT:
                flat += 1
        row["refs"] = seen
        # A majority, not any one: a reference missing the same adjustment
        # "confirmed" SHRIRAMFIN's x4.7 jump while Yahoo and eod2 were flat.
        row["agree"], row["flat"] = agree, flat
        row["verdict"] = ("unverified" if not seen else "confirmed" if agree > flat
                          else "fake" if flat > agree else "disputed")
        rows.append(row)
    return pd.DataFrame(rows)


def ratio_name(m: float) -> str:
    """The clean split or bonus a move looks like, if any."""
    from src.engine.corporate_actions import classify_ratio

    label, gap = classify_ratio(m)
    return label if gap is not None and gap <= 0.04 else ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ours", type=Path, required=True)
    ap.add_argument("--ref", action="append", default=[], help="name=path, repeatable")
    ap.add_argument("--no-confirm", action="append", default=[],
                    help="a reference whose own big moves never confirm ours (repeatable)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    ours = closes(args.ours)
    refs = {n: closes(Path(p)) for n, p in (r.split("=", 1) for r in args.ref)}
    summary: dict = {"stocks": int(ours.shape[1]), "sessions": int(ours.shape[0]),
                     "first": str(ours.index[0].date()), "last": str(ours.index[-1].date())}

    lv = []
    for name, ref in refs.items():
        t = levels(ours, ref).assign(ref=name)
        lv.append(t)
        good = t[t["days"] >= 60]
        summary[f"{name}_levels"] = {
            "stocks": int(len(good)), "common_days": int(good["days"].sum()),
            "days_within_2pct": round(float((good["within_2pct"] * good["days"]).sum()
                                            / good["days"].sum()), 4),
            "stocks_99pct_within_2pct": int((good["within_2pct"] >= 0.99).sum()),
        }
    pd.concat(lv).rename_axis("symbol").reset_index().to_csv(args.out / "levels.csv", index=False)

    br = pd.concat([breaks(ours, ref, n) for n, ref in refs.items()], ignore_index=True)
    br.to_csv(args.out / "breaks.csv", index=False)
    summary["breaks"] = br.groupby(["ref", "who"]).size().rename("n").reset_index().to_dict("records")

    bm = big_moves(ours, refs, frozenset(args.no_confirm))
    if not bm.empty:
        bm["looks_like"] = bm["move"].map(ratio_name)
        bm["direction"] = np.where(bm["move"] > 1, "up", "down")
    bm.to_csv(args.out / "big_moves.csv", index=False)
    summary["big_moves"] = ({f"{d} {v}": int(n) for (d, v), n in
                             bm.groupby(["direction", "verdict"]).size().items()} if not bm.empty else {})
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps(summary, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
