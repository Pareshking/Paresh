"""Momentum health for each system: its own members, point in time (S217; owner, 23 Nov 2026).

The Dashboard's momentum tiles read `data/momentum_health.csv`: the Nifty 500's top fifth by our
score against the Nifty 500, from 2010. That file is the same under every system (S193 K3). The owner
chose (23 Nov 2026) "The 750's own stocks from 2021" and "B2": each system's top fifth against the
equal-weighted average of its own members, so the three read alike and none needs an index NSE does
not publish.

Membership per system, each read on the month-end that signals the month:

- 750: NSE's Nifty Total Market (the 500 and the Microcap 250), recorded from 29 Oct 2021.
- 1000: `membership_history.json`'s Nifty 1000, from 30 Oct 2026 (reconstructed until NSE's first
  list, src/engine/nifty1000_backfill.py). No earlier list exists: its record is collected from now.
- nano: the > ₹2,000 Cr list's month-ends in `data/nanocap_membership.json` (from Aug 2026), also
  collected from now.

The tiles read `top` against `bench`, the equal-weighted average (`ew`), points per month.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.engine.extra_universe import SYSTEM_750, SYSTEM_1000, SYSTEM_NANO

ROOT = Path(__file__).resolve().parents[2]
NANO_FILE = ROOT / "data" / "nanocap_membership.json"
INDEX_KEY = {SYSTEM_750: "nifty_total_market", SYSTEM_1000: "nifty_1000"}
SYSTEMS = (SYSTEM_750, SYSTEM_1000, SYSTEM_NANO)
# Fewer months than this and a tile does not name a "deepest fall" or a record: the record is still
# being collected, and the tile says so (a fall in five months is not a fall "since" anything).
MIN_RECORD_MONTHS = 12
BENCH_COLUMN = "ew"


def path(system: str) -> Path:
    return ROOT / "data" / f"momentum_health_{system}.csv"


def nano_history(raw: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """The list's month-ends as a membership timeline (index_universe's form): the first month is the
    baseline, each later month the stocks it adds and drops, effective from its own date."""
    if raw is None:
        try:
            raw = json.loads(NANO_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    months = sorted((raw.get("months") or {}).values(), key=lambda m: m["effective_from"])
    if not months:
        return None
    first = months[0]
    start = pd.Timestamp(first["effective_from"])
    # As index_universe._stored: a list effective on the 1st also answers for the close before it,
    # the close that signals its month.
    base_date = (start - pd.Timedelta(days=1)) if start.day == 1 else start
    changes, prev = [], set(first["symbols"])
    for m in months[1:]:
        cur = set(m["symbols"])
        d = pd.Timestamp(m["effective_from"])
        d = (d - pd.Timedelta(days=1)) if d.day == 1 else d
        changes.append({"date": d.date().isoformat(), "added": sorted(cur - prev), "removed": sorted(prev - cur)})
        prev = cur
    return {"schema_version": 2, "index": "nano", "aliases": {},
            "baseline": {"date": base_date.date().isoformat(), "symbols": sorted(first["symbols"])},
            "changes": changes}


def membership(system: str) -> dict[str, Any] | None:
    if system == SYSTEM_NANO:
        return nano_history()
    from src.engine import index_universe as iu
    return iu.index_history(INDEX_KEY[system])


def build(system: str, close: pd.DataFrame) -> pd.DataFrame:
    """One row per month the record holds: month, date, top, bottom, spread, n, qualified, ew."""
    from src.engine import index_universe as iu
    from src.engine.momentum_health import monthly_spreads

    hist = membership(system)
    if hist is None:
        return pd.DataFrame(columns=["month", "date", "top", "bottom", "spread", "n", "qualified", "ew"])
    cols = sorted(iu.ever_members(hist) & set(close.columns))
    return monthly_spreads(close[cols].astype("float64"), hist, first_month=iu.first_month(hist))


def read(system: str) -> pd.DataFrame | None:
    """The system's record, or None when it has none yet."""
    p = path(system)
    if not p.exists():
        return None
    try:
        frame = pd.read_csv(p)
    except (OSError, ValueError):
        return None
    return frame if len(frame) else None


def for_tiles(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    """The record in the columns the tiles read (`top`, `nifty500`), the benchmark being the system's
    own equal-weighted members (B2)."""
    if frame is None or not len(frame) or BENCH_COLUMN not in frame.columns:
        return None
    return frame.assign(nifty500=frame[BENCH_COLUMN])


def month_so_far(close: pd.DataFrame, members: list[str], as_of: pd.Timestamp) -> float | None:
    """This month to `as_of`: the top fifth by score at the last month-end, equal weight, less all the
    system's members, equal weight (points). The record's rule, run on the month in progress, on
    today's members (the record reads each month-end's)."""
    from src.engine.momentum_health import MIN_STOCKS, TOP_FRACTION
    from src.engine.rank_history import snapshots

    px = close[[c for c in members if c in close.columns]].sort_index()
    px = px.loc[:as_of]
    if px.empty:
        return None
    first = pd.Timestamp(as_of).to_period("M").to_timestamp()
    before = px.index[px.index < first]
    if not len(before) or px.index[-1] < first:
        return None
    t0 = before[-1]
    snap = snapshots(px.loc[:t0], [t0])
    day = snap[snap["score"].notna()]
    ret = (px.iloc[-1] / px.loc[t0] - 1.0).reindex(day["symbol"].to_numpy())
    scored = pd.Series(day["score"].to_numpy(), index=day["symbol"].to_numpy())[ret.notna()]
    if len(scored) < MIN_STOCKS:
        return None
    k = max(int(len(scored) * TOP_FRACTION), 1)
    top = scored.sort_values(ascending=False).index[:k]
    return float(ret[top].mean() - ret[scored.index].mean()) * 100


def tiles(record: pd.DataFrame | None, mtd: float | None) -> list[tuple[str, float | None, str]]:
    """The momentum tiles from the system's own record: 12 months, the last 3, the last month, then
    the month so far. A window the record does not yet cover reads None ("–"), not a shorter window."""
    import numpy as np

    d = record.dropna(subset=["top", BENCH_COLUMN]).sort_values("month") if record is not None else pd.DataFrame()

    def lead(rows: pd.DataFrame, need: int) -> float | None:
        if len(rows) < need:
            return None
        top = float(np.prod(1 + rows["top"].astype(float) / 100) - 1)
        bench = float(np.prod(1 + rows[BENCH_COLUMN].astype(float) / 100) - 1)
        return (top - bench) * 100

    last = d.iloc[-1]["month"] if len(d) else None
    # The note names the window: the tile ends at the last finished month, not today (S164, staleness audit #7).
    out = [("12 months", lead(d.tail(12), 12),
            "Top fifth of the ranking" + (f", {_span(d.tail(12))}" if len(d) >= 12 else "")),
           ("Last 3 months", lead(d.tail(3), 3), _span(d.tail(3)) if len(d) >= 3 else ""),
           (pd.Period(last, freq="M").strftime("%B") if last else "Last month", lead(d.tail(1), 1), "")]
    out.append(("Month so far", mtd, "Top fifth, at the last month-end"))
    return out


def _span(rows: pd.DataFrame) -> str:
    first, last = pd.Period(rows.iloc[0]["month"], freq="M"), pd.Period(rows.iloc[-1]["month"], freq="M")
    if first.year != last.year:   # "Nov 2025 to Oct 2026"; within one year "Aug to Oct"
        return f"{first.strftime('%b %Y')} to {last.strftime('%b %Y')}"
    return f"{first.strftime('%b')} to {last.strftime('%b')}"


def record_note(record: pd.DataFrame | None, system: str) -> str | None:
    """What a short record says instead of a deepest fall: None once the record is long enough."""
    n = 0 if record is None else len(record)
    if n >= MIN_RECORD_MONTHS:
        return None
    if n == 0:
        # Not a typed date: the 1000's list starts 30 Oct 2026, so its first row is November, not the
        # "December 2026" this said (S193 B).
        first = "its first finished month"
        return (f"This system’s own record begins with {first}. Its deepest fall and recovery are shown "
                f"from {MIN_RECORD_MONTHS} months.")
    since = pd.Period(record["month"].iloc[0], "M").strftime("%B %Y")
    return (f"This system’s own record is being collected from {since}: {n} month{'s' if n != 1 else ''} so far. "
            f"Its deepest fall and recovery are shown from {MIN_RECORD_MONTHS} months.")
