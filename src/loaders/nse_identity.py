"""Which old NSE symbol is which current one: renames without a hand-kept ledger.

Owner, 2026-10-02: "Bhavcopy carries an ISIN. If you join on ISIN ... most
renames resolve themselves, and the ledger then only covers securities whose
ISIN changed." Two of NSE's own records, both committed:

  data/reference/nse/symbolchange.csv  NSE's list of ticker changes, 1999 on
                                       (scripts/sync_nse_reference.py)
  data/reference/nse/isin_history.csv  every (symbol, ISIN) the bhavcopy carried,
                                       22 Jun 2011 - 4 Jun 2021, first and last day
                                       (scripts/build_isin_history.py)
  data/reference/nse/equity_l.csv      today's listed symbols and their ISINs

An old symbol (not listed today) maps to a current one when NSE's list
chains it there, or when its last ISIN is a current symbol's ISIN, or -- an
ISIN changes with the face value (20MICRONS: INE144J01019, then
INE144J01027 after Rs 10 -> Rs 5) -- when the first nine characters (the
issuer and security type) match exactly one current ISIN. Measured
2026-10-02: 575 renames, 267 confirmed by both records, none in conflict
once the target must be listed today (the 21 in the ledger all among them).

A matched identity is not always one continuous price: a company restructured
in insolvency keeps its issuer code while the old equity is extinguished
(DHFL -> PIRAMALFIN). nse_prices.chain_symbols therefore joins an automatic
rename only where the two series meet: at most MAX_GAP_DAYS apart, the
price within MAX_JUMP across the join.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REFERENCE = Path(__file__).resolve().parents[2] / "data" / "reference" / "nse"
SYMBOLCHANGE = REFERENCE / "symbolchange.csv"
ISIN_HISTORY = REFERENCE / "isin_history.csv"
EQUITY_L = REFERENCE / "equity_l.csv"

ISSUER_PREFIX = 9          # "INE144J01": country, issuer, security type
MAX_GAP_DAYS = 15          # last old session to first new session
MAX_JUMP = 0.25            # adjusted close across the join


def symbol_changes(path: Path = SYMBOLCHANGE) -> pd.DataFrame:
    """NSE's ticker changes: old, new, date (oldest first)."""
    try:
        raw = pd.read_csv(path, header=None, encoding="latin1",
                          names=["company", "old", "new", "date"], dtype=str)
    except (OSError, ValueError):
        return pd.DataFrame(columns=["old", "new", "date"])
    out = pd.DataFrame({
        "old": raw["old"].str.strip().str.upper(),
        "new": raw["new"].str.strip().str.upper(),
        "date": pd.to_datetime(raw["date"].str.strip(), format="%d-%b-%Y", errors="coerce"),
    })
    return out[(out["old"] != "") & (out["new"] != "")].sort_values("date", kind="stable")


def current_isins(path: Path = EQUITY_L) -> dict[str, str]:
    """{ISIN: symbol} for every equity listed today."""
    try:
        raw = pd.read_csv(path, dtype=str)
    except (OSError, ValueError):
        return {}
    raw.columns = [c.strip().upper() for c in raw.columns]
    return dict(zip(raw["ISIN NUMBER"].str.strip(), raw["SYMBOL"].str.strip().str.upper()))


def isin_history(path: Path = ISIN_HISTORY) -> pd.DataFrame:
    """symbol, isin, first, last: each pair the bhavcopy carried."""
    try:
        return pd.read_csv(path, parse_dates=["first", "last"])
    except (OSError, ValueError):
        return pd.DataFrame(columns=["symbol", "isin", "first", "last"])


def resolve(changes: pd.DataFrame | None = None, history: pd.DataFrame | None = None,
            current: dict[str, str] | None = None) -> pd.DataFrame:
    """old, new, source ("nse_list", "isin", "isin_prefix", or "nse_list+isin..."),
    conflict -- one row per old symbol that leads to a symbol listed today."""
    changes = symbol_changes() if changes is None else changes
    history = isin_history() if history is None else history
    current = current_isins() if current is None else current
    listed = set(current.values())
    by_prefix: dict[str, set[str]] = {}
    for isin, sym in current.items():
        by_prefix.setdefault(isin[:ISSUER_PREFIX], set()).add(sym)

    step = dict(zip(changes["old"], changes["new"]))       # oldest first: the latest wins

    def follow(sym: str) -> str | None:
        seen = set()
        while sym in step and sym not in seen:
            seen.add(sym)
            sym = step[sym]
        return sym if sym in listed and seen else None

    last = history.sort_values("last").groupby("symbol").tail(1).set_index("symbol")["isin"] \
        if len(history) else pd.Series(dtype=str)

    def by_isin(sym: str) -> tuple[str | None, str]:
        isin = last.get(sym)
        if not isinstance(isin, str):
            return None, ""
        if isin in current:
            return current[isin], "isin"
        hits = by_prefix.get(isin[:ISSUER_PREFIX], set())
        return (next(iter(hits)), "isin_prefix") if len(hits) == 1 else (None, "")

    rows = []
    for sym in sorted(set(step) | set(last.index)):
        if sym in listed:
            continue                     # a listed symbol is never re-pointed
        by_list = follow(sym)
        via, how = by_isin(sym)
        if by_list and via and by_list != via:
            rows.append({"old": sym, "new": None, "source": f"nse_list|{how}",
                         "conflict": f"NSE list says {by_list}, {how} says {via}"})
        elif by_list or via:
            src = f"nse_list+{how}" if by_list and via else ("nse_list" if by_list else how)
            rows.append({"old": sym, "new": by_list or via, "source": src, "conflict": ""})
    return pd.DataFrame(rows, columns=["old", "new", "source", "conflict"])


def auto_renames(present: set[str] | None = None, **kwargs) -> dict[str, dict]:
    """{old: {"new_symbol", "evidence", "auto": True}} for the old symbols in
    `present` (all when None), conflicts left out."""
    table = resolve(**kwargs)
    table = table[table["conflict"] == ""]
    if present is not None:
        table = table[table["old"].isin(present)]
    return {r.old: {"new_symbol": r.new, "evidence": r.source, "auto": True}
            for r in table.itertuples()}
