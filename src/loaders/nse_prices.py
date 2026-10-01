"""Adjusted closes built from NSE's own record, for the backtest and Track Record.

Raw NSE closes (src/loaders/nse_history.py) adjusted with NSE's own corporate-
action file (src/loaders/nse_adjusted.py: each split or bonus is applied only
where the price actually moved by its factor). Dividends are not folded back in,
so a close is what traded, the way the published ranking read it.

Why this and not Yahoo for a record that claims to be "as it stood": Yahoo
restates. A dividend paid in September lowers every earlier price, and a vendor
correction rewrites months that have closed. NSE's closes are immutable. Ranking
at a past signal date depends only on ratios within the trailing window, so a
series that is correct up to that date gives the same ranking then and now, and
it gives it from facts that were published that day.

Committed in data/nse_prices/:
    closes.parquet   raw closes as NSE filed them (sessions x symbols, EQ before BE)
    actions.parquet  its split/bonus/consolidation/demerger rows, one per action
    notes.json       ticker renames and one-off corrections, each with its evidence
scripts/sync_nse_prices.py builds and extends them.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from src.loaders import nse_adjusted as na

DIR = Path(__file__).resolve().parents[2] / "data" / "nse_prices"
BASIS = "nse_as_published"
ACTION_COLS = ["symbol", "series", "kind", "ex_date", "purpose", "price_factor"]


# ── reading what is committed ────────────────────────────────────────────────

def load(directory: Path = DIR) -> dict[str, Any] | None:
    """{"closes", "actions", "notes"} or None when nothing is committed."""
    directory = Path(directory)
    try:
        closes = pd.read_parquet(directory / "closes.parquet")
        actions = pd.read_parquet(directory / "actions.parquet")
        notes = json.loads((directory / "notes.json").read_text())
    except (OSError, ValueError):
        return None
    closes.index = pd.DatetimeIndex(closes.index)
    return {"closes": closes.astype(float), "actions": actions, "notes": notes}


def chain_symbols(close: pd.DataFrame, renames: dict[str, Any] | None) -> pd.DataFrame:
    """Join a renamed stock's two NSE series into one, under its current symbol.

    NSE files the days before a ticker change under the old symbol and the days
    after under the new one. `renames` is {old: {"new_symbol": new, ...}}.
    """
    out = close.copy()
    for old, a in (renames or {}).items():
        new = a["new_symbol"] if isinstance(a, dict) else str(a)
        if old not in out.columns:
            continue
        out[new] = out[new].combine_first(out[old]) if new in out.columns else out[old]
        out = out.drop(columns=[old])
    return out


def correct(close: pd.DataFrame, corrections: Iterable[dict[str, Any]] | None) -> pd.DataFrame:
    """Apply recorded one-off factors: every close before `before` times `factor`.

    For an action NSE's file never listed (each entry carries its evidence).
    """
    out = close.copy()
    for c in corrections or []:
        if c["symbol"] in out.columns:
            out.loc[out.index < pd.Timestamp(c["before"]), c["symbol"]] *= float(c["factor"])
    return out


def adjusted_close(closes: pd.DataFrame, actions: pd.DataFrame, symbols: Iterable[str],
                   *, notes: dict[str, Any] | None = None
                   ) -> tuple[pd.DataFrame, dict[str, Any]]:
    """(adjusted closes for `symbols`, a report of what was and was not found)."""
    notes = notes or {}
    factors, _ = na.action_factors(closes, actions)
    factors.index = closes.index
    close = chain_symbols(na.adjust(closes, factors), notes.get("renames"))
    close = correct(close, notes.get("corrections"))
    wanted = list(dict.fromkeys(symbols))
    cols = [s for s in wanted if s in close.columns and close[s].notna().sum() > 0]
    out = close[cols].sort_index().astype("float32")
    report = {
        "symbols_wanted": len(wanted),
        "symbols_priced": len(cols),
        "unpriced": sorted(set(wanted) - set(cols)),
        "sessions": int(len(out)),
        "first_session": str(out.index[0].date()) if len(out) else None,
        "last_session": str(out.index[-1].date()) if len(out) else None,
        "corporate_action_steps": int(len(na.events(factors))),
    }
    return out, report


# ── the frame the engine runs on ─────────────────────────────────────────────

def _carry_forward(base: pd.DataFrame, other: pd.DataFrame) -> pd.DataFrame:
    """Continue `base` past its last session with `other`'s day-to-day moves.

    The committed file is refreshed monthly; between refreshes the sessions it
    lacks are carried forward on the other source's returns, which differ from
    NSE's only by a dividend, if one fell in the gap.
    """
    last = base.index[-1]
    tail = other.index[other.index > last]
    if not len(tail):
        return base
    ref = other.index[other.index <= last]
    if not len(ref):
        return base
    growth = other.loc[tail].div(other.loc[ref[-1]])
    start = base.loc[last].reindex(growth.columns)
    return pd.concat([base, growth.mul(start, axis=1).reindex(columns=base.columns)])


def basis_frame(other: pd.DataFrame, history: dict | None, *, months: int,
                directory: Path = DIR) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """The record's price frame: NSE as published, for the 750 and the names it dropped.

    `other` is the alternative source's adjusted closes (Yahoo's); it fills the
    few names NSE's equity series does not carry (REITs), extends the frame to
    its last session and supplies a symbol's history from before it joined NSE's
    file. Returns (None, {...}) when no NSE file is committed or it does not
    reach back far enough for a `months`-month study with a 12-month formation
    window, and the caller keeps `other`.
    """
    from src.loaders import former_members

    data = load(directory)
    if data is None or other is None or other.empty:
        return None, {"used": False, "why": "no NSE price file is committed"}
    core = list(other.columns)
    symbols = core + [s for s in former_members.symbols_needed(history, core) if s not in set(core)]
    nse, report = adjusted_close(data["closes"], data["actions"], symbols, notes=data["notes"])
    if nse.empty:
        return None, {"used": False, "why": "no symbol could be priced from NSE"}
    as_of = pd.Timestamp(other.index[-1])
    need_from = as_of - pd.DateOffset(months=months + 12) - pd.Timedelta(days=10)
    if pd.Timestamp(nse.index[0]) > need_from:
        return None, {"used": False, "why": (
            f"NSE file starts {nse.index[0]:%d %b %Y}; a {months}-month study needs "
            f"{need_from:%d %b %Y}")}

    frame = _carry_forward(nse.astype(float), other.astype(float).reindex(columns=nse.columns))
    # Never later than `other`: callers count completed months back from the end
    # of the frame they hand over, and the two must agree on where that is.
    frame = frame.loc[: pd.Timestamp(other.index[-1])]
    # Names NSE's equity series lacks, and names that joined its file after the
    # window began: the other source, joined at the first NSE session by level.
    filled, joined = [], []
    first = nse.index[0]
    for s in core:
        o = other[s].dropna() if s in other.columns else pd.Series(dtype=float)
        if s not in frame.columns:
            if len(o):
                frame[s] = o.reindex(frame.index)
                filled.append(s)
            continue
        have = frame[s].dropna()
        early = o[(o.index >= first) & (o.index < have.index[0])] if len(have) else o
        if len(have) and have.index[0] > first + pd.Timedelta(days=10) and len(early) \
                and have.index[0] in o.index:
            early = early.reindex(frame.index).dropna()
            frame.loc[early.index, s] = early * (have.iloc[0] / o.loc[have.index[0]])
            joined.append(s)
    frame = frame.sort_index().astype("float32")
    report.update(used=True, basis=BASIS, last_session_on_file=str(nse.index[-1].date()),
                  other_source_names=sorted(filled), other_source_history=sorted(joined),
                  frame_last_session=str(frame.index[-1].date()))
    return frame, report
