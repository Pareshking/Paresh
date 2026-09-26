"""How close each holding is to the rules that sell it.

The strategy sells a holding at a rebalance when any of three rules breaks
(backtester._exit_reason, in the order they bind):

1. it ranks past the buffer -- counted among the stocks that pass BOTH
   filters, the same `full_ranked` the backtest selects from, not the
   Screener's overall rank;
2. it closes below its 50-day EMA;
3. it closes more than 20% below its 52-week high.

This module reads today's ranking table and says, for each holding, how much
room is left on each rule. It changes nothing and predicts nothing: a rule
broken today sells only if it is still broken at the next rebalance.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# A holding is flagged "watch" inside these margins.
WATCH_RANK_PLACES = 9      # within 9 places of the buffer
WATCH_EMA_CUSHION = 0.03   # price within 3% of its 50-day EMA
WATCH_HIGH_CUSHION = 0.05  # price within 5% of the -20% line

SELL, WATCH, CLEAR, UNKNOWN = "sell", "watch", "clear", "unknown"
STATUS_LABEL = {
    SELL: "Sold if unchanged",
    WATCH: "Watch",
    CLEAR: "Clear",
    UNKNOWN: "Not ranked",
}


@dataclass(frozen=True)
class Rules:
    buffer_n: int = 40
    high_pct: float = 0.80


def _flag(series: pd.Series | None, index) -> pd.Series:
    if series is None:
        return pd.Series(False, index=index)
    return series.map(lambda v: str(v).strip().lower() in ("true", "1", "yes", "✓", "y")
                      if not isinstance(v, (bool, np.bool_)) else bool(v)).astype(bool)


def qualified_ranks(rank_df: pd.DataFrame) -> pd.Series:
    """Position among the stocks that pass both filters, best first (1-based)."""
    ema = _flag(rank_df.get("Above 50 EMA"), rank_df.index)
    near = _flag(rank_df.get("Near 52W High"), rank_df.index)
    passing = rank_df[ema & near].copy()
    passing["_r"] = pd.to_numeric(passing.get("Rank"), errors="coerce")
    passing = passing.sort_values("_r", na_position="last")
    return pd.Series(range(1, len(passing) + 1), index=passing["Symbol"].to_numpy())


def assess(rank_df: pd.DataFrame, symbols: list[str], rules: Rules = Rules()) -> pd.DataFrame:
    """One row per holding with its room on each rule and a status.

    Cushions are fractions of today's price: how far it can fall before it
    crosses that line, with the line held where it is today. A negative
    cushion means the rule is already broken. Symbols not in the ranking come
    back with status "unknown": no rule can be checked for them.
    """
    by_sym = rank_df.drop_duplicates("Symbol").set_index("Symbol")
    qrank = qualified_ranks(rank_df)
    ema_ok = _flag(by_sym.get("Above 50 EMA"), by_sym.index)
    near_ok = _flag(by_sym.get("Near 52W High"), by_sym.index)
    rows = []
    for sym in symbols:
        if sym not in by_sym.index:
            rows.append({"Symbol": sym, "status": UNKNOWN, "why": "not in the ranked universe"})
            continue
        r = by_sym.loc[sym]
        ema_pct = pd.to_numeric(r.get("% 50 EMA"), errors="coerce")
        hi_pct = pd.to_numeric(r.get("% High"), errors="coerce")
        # "% 50 EMA" is price vs EMA in percent (+2.4 = 2.4% above); the fall
        # that reaches the EMA is 1 - EMA/price.
        ema_c = np.nan if pd.isna(ema_pct) else 1 - 1 / (1 + ema_pct / 100)
        # "% High" is price vs the 52-week high in percent (-5 = 5% below);
        # the fall that reaches high_pct of the high is 1 - high_pct*high/price.
        hi_c = np.nan if pd.isna(hi_pct) else 1 - rules.high_pct / (1 + hi_pct / 100)
        q = qrank.get(sym)
        room = None if q is None else rules.buffer_n - int(q)
        e_ok, n_ok = bool(ema_ok.get(sym, False)), bool(near_ok.get(sym, False))

        broken, close = [], []
        if not e_ok:
            broken.append(f"{abs(ema_pct):.1f}% below its 50-day EMA" if pd.notna(ema_pct)
                          else "below its 50-day EMA")
        if not n_ok:
            broken.append(f"more than {(1 - rules.high_pct):.0%} below its 52-week high")
        if e_ok and n_ok and room is not None and room < 0:
            broken.append(f"ranks #{q} of the qualified, past the top {rules.buffer_n}")
        if broken:
            status, why = SELL, "; ".join(broken)
        else:
            if room is not None and room <= WATCH_RANK_PLACES:
                close.append(f"#{q} · {room} places from the buffer")
            if pd.notna(ema_c) and ema_c < WATCH_EMA_CUSHION:
                close.append(f"{ema_pct:.1f}% above its 50-day EMA")
            if pd.notna(hi_c) and hi_c < WATCH_HIGH_CUSHION:
                close.append(f"{hi_c * 100:.1f}% from the −{(1 - rules.high_pct):.0%} line")
            status, why = (WATCH, "; ".join(close)) if close else (CLEAR, "")
        rows.append({
            "Symbol": sym, "Industry": r.get("Industry"), "Rank": r.get("Rank"),
            "Qualified rank": q, "Rank room": room,
            "vs 50 EMA %": ema_pct, "EMA cushion": ema_c, "EMA ok": e_ok,
            "vs 52W high %": hi_pct, "High cushion": hi_c, "High ok": n_ok,
            "status": status, "why": why,
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    order = {SELL: 0, WATCH: 1, CLEAR: 2, UNKNOWN: 3}
    tight = out.apply(_tightness, axis=1, rules=rules)
    return (out.assign(_o=out["status"].map(order), _t=tight)
               .sort_values(["_o", "_t"]).drop(columns=["_o", "_t"]).reset_index(drop=True))


def _tightness(row, rules: Rules) -> float:
    """The smallest room left on any rule, on one scale, for sorting."""
    vals = [row.get("EMA cushion"), row.get("High cushion")]
    room = row.get("Rank room")
    if room is not None and pd.notna(room):
        vals.append(float(room) / rules.buffer_n * 0.2)
    vals = [float(v) for v in vals if v is not None and pd.notna(v)]
    return min(vals) if vals else 9.0


def parse_holdings(text: str) -> list[tuple[str, float | None]]:
    """Symbols with an optional buy price: "HFCL 126.5, QUESS@340, TCS"."""
    import re

    out: list[tuple[str, float | None]] = []
    seen = set()
    for part in re.split(r"[,;\n]+", str(text or "")):
        m = re.match(r"\s*([A-Za-z0-9&._-]{1,20})\s*(?:[@:\s]\s*₹?\s*([0-9]+(?:\.[0-9]+)?))?\s*$", part)
        if not m:
            continue
        sym = m.group(1).upper()
        if sym in seen:
            continue
        seen.add(sym)
        out.append((sym, float(m.group(2)) if m.group(2) else None))
    return out[:200]


def holdings_from_kite_csv(frame: pd.DataFrame) -> list[tuple[str, float | None]]:
    """Kite Console's holdings export: Instrument, Qty., Avg. cost, ..."""
    cols = {c.strip().lower().rstrip("."): c for c in frame.columns}
    sym_col = cols.get("instrument") or cols.get("symbol") or cols.get("tradingsymbol")
    if sym_col is None:
        raise ValueError("no Instrument or Symbol column")
    cost_col = cols.get("avg. cost") or cols.get("avg cost") or cols.get("average price")
    out = []
    for _, r in frame.iterrows():
        sym = str(r[sym_col]).strip().upper().split("-")[0]
        if not sym or sym == "NAN":
            continue
        cost = pd.to_numeric(r[cost_col], errors="coerce") if cost_col else np.nan
        out.append((sym, None if pd.isna(cost) else float(cost)))
    return out
