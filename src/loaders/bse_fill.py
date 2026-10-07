"""Fill a stretch NSE has no row for with BSE's close, where BSE traded the stock.

Owner, 2026-10-07 (TODO S38): "fill NSE-only gaps from BSE: yes". NSE's files do
not list a security on days NSE did not deal in it (DATA_CORRECTNESS.md section 6):
GOODYEAR, NOVARTIND, KENNAMET, KIRLFER and GRAUWEIL from 26 Oct 2023 to 17 Apr 2026,
77 stocks for a month in 2013, and more. BSE traded them, so a price exists; a
holding or a momentum window across such a stretch should see it, not a hole.

The rules (each has a test in tests/test_bse_fill.py):

  raw space      BSE's closes are as traded, so they go into NSE's RAW closes,
                 before any corporate-action factor is worked out or applied
                 (scripts/build_nse_long_prices.py). Every split, bonus, rights,
                 demerger and dividend factor then reaches a filled day exactly as
                 it reaches NSE's own (DATA_CORRECTNESS.md section 2a).
  a genuine gap  MIN_GAP sessions or more between two NSE closes of one raw NSE
                 symbol (a rename seam is not a gap here: it is two symbols).
  BSE traded     BSE traded the stock on at least MIN_TRADED_SHARE of the gap's
                 sessions BSE has a file for; otherwise it is a suspension, or
                 partly one, and nothing is filled. Only sessions BSE traded
                 (shares > 0) are filled; the rest stay empty.
  same company   the BSE scrip code by ISIN where one is known on both sides
                 (BSE's file carries ISINs from July 2024; NSE's from
                 data/reference/nse/isin_history.csv and equity_l.csv); otherwise
                 by price, the rule scripts/audit_gaps_against_bse.py uses
                 (price_match). An ambiguous price match is refused, and so is a
                 code whose ISIN names another issuer than NSE's.
  junctions      at each end of the gap, BSE's close and NSE's on the nearest
                 JUNCTION_DAYS common days (within JUNCTION_WINDOW sessions):
                 median difference above TOLERANCE refuses the gap.
  never NSE      a day NSE has a close for is never touched.

Every filled cell is recorded (symbol, date, BSE code, BSE close) and every gap
looked at gets a verdict, filled or refused and why.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

MIN_GAP = 5                 # sessions; the gap audit's own threshold
MIN_TRADED_SHARE = 0.5      # the gap audit's "NSE-only gap: BSE traded"
TOLERANCE = 0.02            # price match and junction guard
JUNCTION_DAYS = 3           # common days compared at each end
JUNCTION_WINDOW = 10        # sessions searched at each end for them
MATCH_DAYS = 8              # NSE sessions before the gap the price match uses
ISSUER_PREFIX = 9           # "INE144J01": country, issuer, security type (nse_identity)

CELL_COLUMNS = ["symbol", "date", "bse_code", "bse_close", "bse_shares", "gap_last_nse", "gap_next_nse",
                "mapped_by"]
GAP_COLUMNS = ["symbol", "last_before", "first_after", "missing_sessions", "bse_code", "bse_name", "mapped_by",
               "sessions_with_bse_file", "bse_traded_sessions", "junction_before", "junction_after",
               "filled_sessions", "verdict", "detail"]


def gaps(close: pd.DataFrame, min_gap: int = MIN_GAP) -> list[tuple[str, int, int]]:
    """(symbol, position of the last close before, position of the next close after) per gap."""
    out = []
    for sym in close.columns:
        p = np.flatnonzero(close[sym].notna().to_numpy())
        if len(p) < 2:
            continue
        for i in np.flatnonzero(np.diff(p) - 1 >= min_gap):
            out.append((sym, int(p[i]), int(p[i + 1])))
    return out


def price_match(nse: pd.Series, bse_by_date: dict, tolerance: float = TOLERANCE) -> tuple[int | None, str]:
    """(BSE code, how) whose close is within `tolerance` of NSE's raw closes `nse` (date -> close).

    The rule of scripts/audit_gaps_against_bse.py: the code within 2% on the most
    days, at least 3 and 60% of NSE's; "(ambiguous)" when a second code fits as
    well. bse_by_date maps a date to BSE's rows that day (code, close).
    """
    nse = nse.dropna()
    nse = nse[nse > 0]
    if len(nse) < 3:
        return None, "no NSE close to match"
    parts = [bse_by_date[d][["code", "close"]].assign(nse=float(v)) for d, v in nse.items() if d in bse_by_date]
    if not parts:
        return None, "no BSE file"
    m = pd.concat(parts)
    m["gap"] = (m["close"] / m["nse"] - 1).abs()
    score = (m.groupby("code").agg(hits=("gap", lambda v: (v < tolerance).sum()), med=("gap", "median"))
              .sort_values(["hits", "med"], ascending=[False, True]))
    if score.empty or score.iloc[0].hits < max(3, 0.6 * len(nse)):
        return None, "no BSE price match"
    tie = (len(score) > 1 and score.iloc[1].hits == score.iloc[0].hits
           and score.iloc[1].med < 2 * score.iloc[0].med + 1e-9)
    return int(score.index[0]), "price match" + (" (ambiguous)" if tie else "")


def nse_isins(sym: str, start: pd.Timestamp, end: pd.Timestamp, history: pd.DataFrame | None,
              current: dict[str, str] | None) -> list[str]:
    """NSE's ISINs for `sym` around [start, end]: isin_history's pairs, then today's list.

    Today's ISIN (equity_l.csv, {symbol: isin}) is used only for a gap that ends
    after isin_history does (June 2021): a symbol can be re-used.
    """
    out: list[str] = []
    pad = pd.Timedelta(days=30)
    if history is not None and len(history):
        h = history[(history["symbol"] == sym) & (history["first"] <= end + pad) & (history["last"] >= start - pad)]
        out += list(h["isin"][::-1])
        covered_to = history["last"].max()
    else:
        covered_to = pd.Timestamp.min
    if current and sym in current and end > covered_to:
        out.append(current[sym])
    return list(dict.fromkeys(str(i).strip() for i in out if isinstance(i, str) and i.strip()))


def nse_isins_ever(sym: str, history: pd.DataFrame | None, current: dict[str, str] | None) -> list[str]:
    """Every ISIN NSE's records give `sym`, any period (isin_history.csv, then today's list)."""
    out = list(history.loc[history["symbol"] == sym, "isin"]) if history is not None and len(history) else []
    if current and sym in current:
        out.append(current[sym])
    return list(dict.fromkeys(str(i).strip() for i in out if isinstance(i, str) and i.strip()))


def _prefixes(isins: Iterable[str]) -> set[str]:
    return {i[:ISSUER_PREFIX] for i in isins if isinstance(i, str) and len(i) >= ISSUER_PREFIX}


def _junction(nse: pd.Series, bse: pd.Series, positions: Iterable[int], idx: pd.DatetimeIndex) -> float | None:
    """Median |BSE / NSE - 1| over the first JUNCTION_DAYS positions where both have a close."""
    diffs = []
    for j in positions:
        if not 0 <= j < len(idx):
            continue
        d = idx[j]
        n, b = nse.iloc[j], bse.get(d, np.nan)
        if pd.notna(n) and n > 0 and pd.notna(b) and b > 0:
            diffs.append(abs(b / n - 1))
            if len(diffs) == JUNCTION_DAYS:
                break
    return float(np.median(diffs)) if diffs else None


def prepare(bse: pd.DataFrame) -> dict:
    """BSE's table (scripts/bse_bhavcopy.py build) indexed the ways fill() reads it."""
    b = bse[[c for c in ("date", "code", "close", "shares", "isin", "name") if c in bse.columns]].copy()
    b["date"] = pd.to_datetime(b["date"]).astype("datetime64[ns]")
    b["code"] = b["code"].astype("int64")
    b = b.drop_duplicates(["date", "code"], keep="first")
    b["isin"] = b["isin"].astype("string").str.strip().replace({"nan": pd.NA, "None": pd.NA, "": pd.NA})
    traded = b[(b["shares"] > 0) & (b["close"] > 0)]
    with_isin = b.dropna(subset=["isin"])
    return {
        "days": set(b["date"].unique()),
        "by_date": {d: g for d, g in traded[["date", "code", "close"]].groupby("date")},
        "close": {c: g.set_index("date")["close"] for c, g in traded.groupby("code")},
        "shares": {c: g.set_index("date")["shares"] for c, g in traded.groupby("code")},
        "isin_codes": with_isin.groupby("isin")["code"].agg(lambda c: sorted(set(int(x) for x in c))).to_dict(),
        "code_isins": with_isin.groupby("code")["isin"].agg(lambda i: sorted(set(i))).to_dict(),
        "row_isin": with_isin.set_index(["code", "date"])["isin"].to_dict(),
        "name": (b.drop_duplicates("code", keep="last").set_index("code")["name"].astype(str).to_dict()
                 if "name" in b.columns else {}),
    }


def fill(close: pd.DataFrame, bse: pd.DataFrame | dict, *, history: pd.DataFrame | None = None,
         current: dict[str, str] | None = None, min_gap: int = MIN_GAP
         ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(raw closes with NSE-only gaps filled from BSE, one row per filled cell, one row per gap).

    `close` is NSE's RAW closes (sessions x NSE symbols), before any adjustment;
    `bse` BSE's table or prepare()'s result; `history` NSE's symbol-ISIN pairs
    (isin_history.csv) and `current` today's {symbol: isin} (equity_l.csv).
    """
    b = bse if isinstance(bse, dict) else prepare(bse)
    idx = pd.DatetimeIndex(close.index)
    out = close.copy()
    cells, rows = [], []
    for sym, p0, p1 in gaps(close, min_gap):
        last, nxt = idx[p0], idx[p1]
        inside = [idx[j] for j in range(p0 + 1, p1)]
        row = {"symbol": sym, "last_before": last.date(), "first_after": nxt.date(),
               "missing_sessions": len(inside), "bse_code": None, "bse_name": None, "mapped_by": None,
               "sessions_with_bse_file": sum(d in b["days"] for d in inside), "bse_traded_sessions": 0,
               "junction_before": None, "junction_after": None, "filled_sessions": 0}

        def refuse(why: str, detail: str = "") -> None:
            rows.append({**row, "verdict": f"refused: {why}", "detail": detail})

        isins = nse_isins(sym, last, nxt, history, current)
        ever = nse_isins_ever(sym, history, current) or isins
        codes = sorted({c for i in isins for c in b["isin_codes"].get(i, [])})
        how = "isin"
        if not codes:
            # The ISIN NSE gives the symbol in another period: BSE's file has ISINs only
            # from July 2024 and NSE's history only 2011 - 2021 (BHARATRAS 2008 matched
            # INDIAN CARD CLOTHING's price by chance; its own ISIN finds code 590066).
            codes = sorted({c for i in ever for c in b["isin_codes"].get(i, [])})
            how = "isin (another period)"
        if len(codes) == 1:
            code = codes[0]
        elif len(codes) > 1:
            refuse("ISIN maps to more than one BSE code", str(codes))
            continue
        else:
            nse_tail = close[sym].iloc[max(0, p0 - MATCH_DAYS + 1): p0 + 1]
            code, how = price_match(nse_tail, b["by_date"])
        row.update(bse_code=code, mapped_by=how, bse_name=b["name"].get(code))
        if code is None:
            refuse(how)
            continue
        if "ambiguous" in how:
            refuse("ambiguous BSE match")
            continue
        theirs = _prefixes(b["code_isins"].get(code, []))
        # A code whose ISIN names another issuer than any NSE ever gave the symbol is
        # another company whose price happened to fit (24 of the 147 "NSE-only" gaps
        # of 3 Oct 2026: MBAPL matched eleven different codes).
        if ever and theirs and not (_prefixes(ever) & theirs):
            refuse("ISIN mismatch", f"NSE {','.join(ever)}; BSE code {code} {','.join(b['code_isins'][code])}")
            continue
        bclose = b["close"].get(code, pd.Series(dtype=float))
        traded = [d for d in inside if d in bclose.index]
        row["bse_traded_sessions"] = len(traded)
        with_file = row["sessions_with_bse_file"]
        if with_file == 0:
            refuse("no BSE file for any session of the gap")
            continue
        share = len(traded) / with_file
        if share < MIN_TRADED_SHARE:
            refuse("no BSE trading either (a suspension)" if share <= 0.1 else "partly traded on BSE",
                   f"{len(traded)} of {with_file} sessions")
            continue
        nse_s = close[sym]
        jb = _junction(nse_s, bclose, range(p0, p0 - JUNCTION_WINDOW, -1), idx)
        ja = _junction(nse_s, bclose, range(p1, p1 + JUNCTION_WINDOW), idx)
        row.update(junction_before=None if jb is None else round(jb, 4),
                   junction_after=None if ja is None else round(ja, 4))
        if jb is None or ja is None:
            refuse("no common NSE/BSE day at a junction", "start" if jb is None else "end")
            continue
        if jb > TOLERANCE or ja > TOLERANCE:
            side = "start" if jb > TOLERANCE else "end"
            refuse("junction: BSE more than 2% off NSE", f"{side}: {max(jb, ja):.1%}")
            continue
        wrong = [d for d in traded if (code, d) in b["row_isin"] and ever
                 and b["row_isin"][(code, d)][:ISSUER_PREFIX] not in _prefixes(ever)]
        if wrong:
            refuse("ISIN mismatch", f"BSE rows of {len(wrong)} sessions carry another issuer's ISIN")
            continue
        for d in traded:
            assert pd.isna(out.at[d, sym]), "a day NSE has a close for is never filled"
            out.at[d, sym] = float(bclose[d])
            cells.append({"symbol": sym, "date": d.date(), "bse_code": code, "bse_close": float(bclose[d]),
                          "bse_shares": float(b["shares"][code][d]), "gap_last_nse": last.date(),
                          "gap_next_nse": nxt.date(), "mapped_by": how})
        row["filled_sessions"] = len(traded)
        rows.append({**row, "verdict": "filled", "detail": f"{len(inside) - len(traded)} sessions left empty"
                     if len(traded) < len(inside) else ""})
    return (out, pd.DataFrame(cells, columns=CELL_COLUMNS), pd.DataFrame(rows, columns=GAP_COLUMNS))


def summary(cells: pd.DataFrame, gap_rows: pd.DataFrame) -> dict:
    """Counts for nse_long_report.json."""
    filled = gap_rows[gap_rows["verdict"] == "filled"] if len(gap_rows) else gap_rows
    reasons = (gap_rows.loc[gap_rows["verdict"] != "filled", "verdict"].str.removeprefix("refused: ")
               .value_counts().to_dict()) if len(gap_rows) else {}
    return {
        "status": "BSE table read",
        "gaps_checked": int(len(gap_rows)),
        "gaps_filled": int(len(filled)),
        "stocks_filled": int(filled["symbol"].nunique()) if len(filled) else 0,
        "cells_filled": int(len(cells)),
        "gaps_refused": int(len(gap_rows) - len(filled)),
        "refused_by_reason": {k: int(v) for k, v in reasons.items()},
        "min_gap_sessions": MIN_GAP, "tolerance": TOLERANCE,
    }
