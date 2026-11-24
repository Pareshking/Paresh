"""The fixed words for a missing figure, an empty state and a repeated state (S193 E, rules R1, R2, R4, R5).

One module, so one cause reads the same on every page (owner, 23 Nov 2026: "Go with your
recommendation on I and E"; docs/archive/S193_ITEM_E_2026-11-23.md section 5). Pages import
these words instead of writing their own; `tests/test_s193_e2_missing_words.py` fails when a
page writes a cause's words by hand.

* A missing figure is "–" with one reason, worded by its cause. In a table the reason is one
  footnote per column (`column_note`), not one per cell.
* A stock that failed the filters on a day is **"Out"**, never "–".
* A figure that does not apply is a blank cell (`NOT_APPLICABLE`), not "–".
* One form per empty state: a page with no data is h1 + one lede + the footer; a section with
  no data is h2 + one note; a filter with no match is `kit.empty` naming the way out; a failure
  is an amber `kit.note`.
"""
from __future__ import annotations

import pandas as pd

DASH = "–"
OUT = "Out"            # failed the filters that day (rank None in `rank_trails`)
NOT_APPLICABLE = ""    # a blank cell: the figure does not apply to that row

# The four causes of a "–", in fixed words.
SYSTEM_TOO_YOUNG = "the system is too young"
TOO_NEW = "too new"            # a stock or an index
NOT_PUBLISHED = "not published yet"
NO_SUCH_INDEX = "no NSE index"
CAUSES = (SYSTEM_TOO_YOUNG, TOO_NEW, NOT_PUBLISHED, NO_SUCH_INDEX)


def _day(d) -> str:
    return pd.Timestamp(d).strftime("%-d %b %Y")


def _mon(d) -> str:
    return pd.Timestamp(d).strftime("%b %Y")


def system_too_young(first_month=None) -> str:
    """Why a window before a system's record reads "–"."""
    tail = f" (its record starts {_mon(first_month)})" if first_month is not None else ""
    return f"{SYSTEM_TOO_YOUNG}{tail}"


def book_too_short(need: int, have: int) -> str:
    """Why a risk figure that needs more sessions of the book reads "–" (S203 dash.gl.2, pf.eq.11)."""
    return f"{SYSTEM_TOO_YOUNG} (the figure needs {need} sessions; the book has {have})"


def stock_too_new(listed=None, sessions: int | None = None) -> str:
    """Why a stock's long window reads "–"."""
    bits = []
    if listed is not None:
        bits.append(f"listed {_day(listed)}")
    if sessions is not None:
        bits.append(f"{sessions} sessions")
    return f"the stock is {TOO_NEW}" + (f" ({', '.join(bits)})" if bits else "")


def index_too_new(launch=None) -> str:
    """Why an index's window before its launch reads "–"."""
    return f"the index is {TOO_NEW}" + (f" (since {_day(launch)})" if launch is not None else "")


def since(launch) -> str:
    """A young index's own window: "since 28 Jan 2026", one date form, with the year."""
    return f"since {_day(launch)}"


def not_published(what: str = "", until=None) -> str:
    """Why a figure after the source's last date reads "–"."""
    tail = f" ({what} ends {pd.Timestamp(until):%-d %b})" if what and until is not None else ""
    return f"{NOT_PUBLISHED}{tail}"


def not_in_yet(name: str, have, due) -> str:
    """The one sentence for a source a session behind the page (R3): Portfolio's words."""
    return (f"{name} to {pd.Timestamp(have):%-d %b}: NSE’s closes for {pd.Timestamp(due):%-d %b} "
            "are not in yet")


def no_such_index(group: str = "") -> str:
    """Why a group's index row reads "–": NSE publishes none."""
    return f"{NO_SUCH_INDEX} for {group}" if group else NO_SUCH_INDEX


def no_pe() -> str:
    return f"{NOT_PUBLISHED}: NSE publishes no P/E for it"


def too_few_stocks(n: int) -> str:
    """Why a group's own figures read "–": too few of its stocks are ranked today to make a median."""
    return f"fewer than {n} of its stocks are ranked today"


def column_note(column: str, reason: str) -> str:
    """One footnote per table column: "– in 12M: the system is too young (…)." """
    return f"{DASH} in {column}: {reason}."


def column_notes(notes: dict[str, str]) -> str:
    """Several columns' footnotes, one sentence each, in column order."""
    return " ".join(column_note(c, r) for c, r in notes.items() if r)


# ── Repeated states, one sentence each (R5) ──────────────────────────────
NO_MODEL_BOOK = "No model book yet."
NO_MODEL_BOOK_WHY = "It forms once the system has about 18 months of prices."


def no_events(who: str, fill=None) -> str:
    """The board-meeting check, one sentence on Actions and Watchlist (R5)."""
    when = f" before the {pd.Timestamp(fill):%-d %b} fill" if fill is not None else ""
    return f"No board meeting or ex-date is announced for {who}{when}."


# ── Empty states, one form each (R4) ─────────────────────────────────────
NO_MATCH = "No stock matches these filters."
NO_MATCH_WAY_OUT = "Clear the search or pick another preset."
NO_ROWS = "Nothing to show for this choice."
NO_ROWS_WAY_OUT = "Pick another filter above."
NO_PRICES = "No prices yet."
NO_PRICES_WHY = "This page is drawn from the ranked stocks’ daily closes, and none are loaded."


def no_groups(n: int) -> tuple[str, str]:
    """A page of groups with none big enough to compare: its h1 and its lede (R4)."""
    return (f"No group has {n} or more ranked stocks to compare.",
            f"A group needs {n} ranked stocks for its typical stock to mean something; pick another grouping above.")
