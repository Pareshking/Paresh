"""The price frame the backtest and Track Record run on: Screener's closes, with NSE's own
record (then Yahoo) only where Screener has none.

Owner, 2026-10-01: use Screener everywhere, as the live ranking does; NSE or Yahoo only
where Screener has no data. blend_screener() does that; the rest of this module builds the
NSE series that fills the gaps.

Adjusted closes built from NSE's own record, for the fallback.

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

import numpy as np
import pandas as pd

from src.loaders import nse_adjusted as na

DIR = Path(__file__).resolve().parents[2] / "data" / "nse_prices"
BASIS = "nse_as_published"
BASIS_SCREENER = "screener_primary"
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


_STORE_TTL_S = 3600
_store_memo: dict[str, Any] = {"at": 0.0, "frame": None}


def screener_store() -> pd.DataFrame | None:
    """The published Screener history (R2, else the release), memoised for an hour. None if unreachable."""
    import time

    now = time.time()
    if _store_memo["frame"] is not None and now - _store_memo["at"] < _STORE_TTL_S:
        return _store_memo["frame"]
    try:
        from src.loaders import price_source

        frame = price_source.fetch_screener_store()
    except Exception:  # noqa: BLE001  the caller falls back to NSE's own closes
        frame = None
    if frame is not None:
        _store_memo.update(at=now, frame=frame)
    return frame


def blend_screener(base: pd.DataFrame, store: pd.DataFrame | None, extra: Iterable[str] = ()
                   ) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Screener's closes wherever it has one; `base` (NSE's, adjusted) only where it has none.

    Screener's store is daily for the last year or so and sparser before it, and it lacks
    a few stocks outright (ones that merged away). A date or a stock Screener does not
    cover is filled from `base` scaled to Screener's own level at the nearest date it does
    hold for that stock (the ratio is constant between corporate-action restatements), so
    the series is one continuous line on Screener's basis and no step appears at a seam.
    A stock Screener has never held stays on `base`; one `base` lacks that Screener holds
    (`extra`, e.g. a REIT outside NSE's equity series) is taken from Screener whole.
    """
    if store is None or store.empty or not isinstance(store.columns, pd.MultiIndex):
        return base, {"screener": False}
    try:
        close = store.xs("Close", axis=1, level=-1)
    except Exception:  # noqa: BLE001
        return base, {"screener": False}
    close.index = pd.DatetimeIndex(close.index).normalize()
    close = close[~close.index.duplicated(keep="last")]
    cols = [c for c in base.columns if c in close.columns and close[c].notna().any()]
    if not cols:
        return base, {"screener": False}
    shared = close[cols].reindex(base.index)
    n = base[cols].astype(float)
    ratio = (shared / n).where(lambda r: (r > 0) & np.isfinite(r))
    scaled = n * ratio.ffill().bfill()
    out = shared.where(shared.notna(), scaled).combine_first(n)
    result = base.astype(float).copy()
    result[cols] = out
    only = [c for c in dict.fromkeys(extra) if c not in base.columns and c in close.columns
            and close[c].notna().any()]
    if only:
        result = pd.concat([result, close[only].reindex(base.index).astype(float)], axis=1)
    from_screener = float(shared.notna().to_numpy().sum()) / max(int(n.notna().to_numpy().sum()), 1)
    report = {
        "screener": True,
        "screener_names": len(cols),
        "screener_only_names": sorted(only),
        "base_only_names": sorted(set(base.columns) - set(cols)),
        "share_of_cells_from_screener": round(from_screener, 3),
        "screener_last_date": str(close.index[-1].date()),
    }
    return result.astype("float32"), report


def basis_frame(other: pd.DataFrame, history: dict | None, *, months: int,
                directory: Path = DIR, until: pd.Timestamp | None = None,
                screener: pd.DataFrame | str | None = "auto") -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """The record's price frame: NSE as published, for the 750 and the names it dropped.

    `other` is the alternative source's adjusted closes (Yahoo's); it fills the
    few names NSE's equity series does not carry (REITs), extends the frame to
    its last session and supplies a symbol's history from before it joined NSE's
    file. Returns (None, {...}) when no NSE file is committed or it does not
    reach back far enough for a `months`-month study with a 12-month formation
    window, and the caller keeps `other`.

    The frame runs to NSE's last session on file, or `other`'s if that is later.
    Callers count completed months back from the END of the frame they receive, so
    one that fixed `months` against `other` passes `until=other.index[-1]` to keep
    the two ends the same; the record's own runs take the later end, so a month
    closes the day NSE's first session of the next one is on file.
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
    if until is not None:
        frame = frame.loc[: pd.Timestamp(until)]
    # Screener first, as on the live ranking page: NSE's closes only fill what Screener lacks.
    store = screener_store() if isinstance(screener, str) and screener == "auto" else screener
    frame, blend = blend_screener(frame, store if isinstance(store, pd.DataFrame) else None, extra=core)
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
            # float32 column, float64 values: pandas refuses the lossy set.
            frame.loc[early.index, s] = (
                (early * (have.iloc[0] / o.loc[have.index[0]])).astype(frame[s].dtype))
            joined.append(s)
    frame = frame.sort_index().astype("float32")
    report.update(blend)
    report.update(used=True, basis=BASIS_SCREENER if blend.get("screener") else BASIS,
                  last_session_on_file=str(nse.index[-1].date()),
                  other_source_names=sorted(filled), other_source_history=sorted(joined),
                  frame_last_session=str(frame.index[-1].date()))
    return frame, report


def middle_close(symbols: Iterable[str]) -> pd.DataFrame | None:
    """NSE's adjusted closes for `symbols`: the middle price source.

    Screener -> NSE -> Yahoo (owner, 2026-09-27; adopted 2026-10-02). Reads the
    committed data/nse_prices copy. Anything missing or unreadable returns None,
    and the caller falls back to the Screener -> Yahoo order: a middle source
    must never be able to take the app down.
    """
    try:
        data = load()
        if data is None:
            return None
        out, _report = adjusted_close(data["closes"], data["actions"], symbols,
                                      notes=data["notes"])
    except Exception:
        return None
    return out if not out.empty else None
