"""When the book's companies report (TODO S110, item 4; owner, 8 Nov 2026: "let's build").

Reads data/results_calendar.csv, written nightly by scripts/collect_results_calendar.py
from NSE's board-meeting calendar (meetings announced ahead) and its list of meetings
already held. Dates are as companies announced them; they can move.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CALENDAR_FILE = ROOT / "data" / "results_calendar.csv"
META_FILE = ROOT / "data" / "results_calendar_meta.json"
AHEAD_DAYS = 35           # about four weeks: past the next monthly check
SEASON_DAYS = 60          # a holding that met within this window has "reported this season"


@dataclass(frozen=True)
class BookCalendar:
    upcoming: pd.DataFrame          # symbol, date, purpose, results, detail, role; soonest first
    reported: pd.DataFrame          # holdings whose results meeting is past, latest first
    holdings: int
    fetched_on: pd.Timestamp | None


def load(path: Path = CALENDAR_FILE) -> pd.DataFrame | None:
    if not Path(path).exists():
        return None
    d = pd.read_csv(path)
    if d.empty or not {"symbol", "date", "purpose", "results"} <= set(d.columns):
        return None
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    return d.dropna(subset=["date"])


def fetched_on(path: Path = META_FILE) -> pd.Timestamp | None:
    try:
        return pd.Timestamp(json.loads(Path(path).read_text())["fetched_on"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def short_purpose(purpose: str) -> str:
    """NSE's 'Financial Results/Dividend/Other business matters' read as 'Results, dividend'."""
    words = {"financial results": "Results", "dividend": "dividend", "fund raising": "fund raising",
             "buyback": "buyback", "bonus": "bonus", "stock split": "stock split",
             "other business matters": ""}
    parts = [p.strip() for p in str(purpose).split("/") if p.strip()]
    out = [words.get(p.lower(), p.lower()) for p in parts]
    out = [p for p in out if p]
    if not out:
        return "Board meeting"
    text = ", ".join(out)
    return text[0].upper() + text[1:]


def for_book(cal: pd.DataFrame | None, holdings: list[str], buys: list[str], as_of: pd.Timestamp,
             ahead_days: int = AHEAD_DAYS, fetched: pd.Timestamp | None = None) -> BookCalendar | None:
    """The book's meetings from `as_of` (inclusive) to `ahead_days` on, and the
    holdings that have already held a results meeting this season."""
    if cal is None:
        return None
    as_of = pd.Timestamp(as_of).normalize()
    role = {s: "held" for s in holdings} | {s: "to buy" for s in buys if s not in holdings}
    mine = cal[cal["symbol"].isin(role)].copy()
    mine["role"] = mine["symbol"].map(role)
    ahead = mine[(mine["date"] >= as_of) & (mine["date"] <= as_of + pd.Timedelta(days=ahead_days))]
    ahead = ahead.sort_values(["date", "role", "symbol"]).reset_index(drop=True)
    past = mine[(mine["date"] < as_of) & (mine["date"] >= as_of - pd.Timedelta(days=SEASON_DAYS))
                & (mine["results"] == 1) & (mine["role"] == "held")]
    past = past.sort_values("date", ascending=False).drop_duplicates("symbol").reset_index(drop=True)
    return BookCalendar(ahead, past, len(holdings), fetched)


def lede(bc: BookCalendar, check: pd.Timestamp) -> str:
    held = bc.upcoming[bc.upcoming["role"] == "held"]
    before = held[(held["date"] <= pd.Timestamp(check)) & (held["results"] == 1)]
    n = before["symbol"].nunique()
    who = "No holding reports" if n == 0 else ("1 holding reports" if n == 1 else f"{n} holdings report")
    parts = [f"{who} before the {pd.Timestamp(check):%-d %b} check"]
    if len(bc.reported):
        parts.append(f"{len(bc.reported)} of {bc.holdings} have reported this season, "
                     f"the latest {bc.reported['symbol'].iloc[0]} on {bc.reported['date'].iloc[0]:%-d %b}")
    return "; ".join(parts) + "."
