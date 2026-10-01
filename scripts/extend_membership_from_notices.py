#!/usr/bin/env python3
"""Extend the point-in-time membership history backward using NSE's own notices.

The daily sync only began recording the Nifty Total Market list on 2026-08-19,
so every earlier backtest rebalance was scored on TODAY's list and could hold
names before the index did (the hindsight bias src/engine/membership.py exists
to remove). NSE Indices announces every change to the list in a press release,
so the list on any earlier date is the list we know, with those changes undone.

    ledger  read downloaded press-release PDFs and write data/membership_notices.json
    apply   rewind the history to --start through that ledger and save it
    check   re-verify the committed history against the committed ledger

Nothing is guessed. Rewinding one change requires every symbol it included to be
in the list after it and every symbol it excluded to be absent, and the rewound
list must agree with the independent notices on its own side of --start. Any
disagreement stops the run, except the names the ledger records as unexplained.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import parse_index_notices as pin  # noqa: E402
from src.core.tickers import is_tradeable_symbol  # noqa: E402
from src.engine.membership import members_on  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "membership_history.json"
LEDGER = ROOT / "data" / "membership_notices.json"
INDEX = "NIFTY TOTAL MARKET"
INDEX_KEY = "nifty_total_market"
URL = "https://www.niftyindices.com/Press_Release/{}"
DEFAULT_START = "2025-12-31"
# The semi-annual review of 30 Sep 2025 is the earliest notice the ledger
# holds; facts older than it cannot be cross-checked against a complete record.
ANCHOR_FROM = "2025-09-30"
# A row of a notice's "indices affected" table: "  10      Nifty Total Market".
_TM_ROW = re.compile(r"^\s*\d{1,2}\s+Nifty Total Market\s*$", re.M)


class ReconstructionError(RuntimeError):
    """The notices and the recorded list disagree."""


# ── Ledger: notices -> rows ──────────────────────────────────────────────────

def _pdf_text(path: Path) -> str:
    return subprocess.run(["pdftotext", "-layout", str(path), "-"],
                          capture_output=True, text=True, check=True).stdout


def _tradeable(symbols: list[str]) -> list[str]:
    return sorted({s for s in symbols if is_tradeable_symbol(s)})


def build_ledger(pdf_dir: Path) -> dict[str, Any]:
    """Every Total Market change in the notices under `pdf_dir`."""
    notices: list[dict[str, Any]] = []
    placeholders: list[dict[str, Any]] = []
    for pdf in sorted(pdf_dir.glob("ind_prs*.pdf")):
        text = _pdf_text(pdf)
        effective = pin.effective_dates(text)
        issued = pin.issued_on(text)
        sec = pin.sections(text, "Nifty Total Market")
        if sec and effective:
            notices.append({
                "notice": pdf.name,
                "url": URL.format(pdf.name),
                "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                "issued": issued.isoformat() if issued else None,
                "effective": effective[0].isoformat(),
                "included": _tradeable(sec.get("included", [])),
                "excluded": _tradeable(sec.get("excluded", [])),
            })
        elif _TM_ROW.search(text) and "dummy" in text.lower():
            # A demerged entity held at zero price under a placeholder symbol.
            # is_tradeable_symbol drops these everywhere; listed for the audit.
            placeholders.append({
                "notice": pdf.name,
                "issued": issued.isoformat() if issued else None,
                "effective": [d.isoformat() for d in effective[:2]],
                "kind": "demerger placeholder (DUMMY symbol), not a tradeable name",
            })
    notices.sort(key=lambda n: (n["effective"], n["issued"] or "", n["notice"]))
    return {
        "index": INDEX,
        "source": "NSE Indices press releases, https://www.niftyindices.com/press-release",
        "note": ("Total Market changes read from each notice's own 'Nifty Total Market' "
                 "tables. Placeholder (DUMMY) symbols are dropped by is_tradeable_symbol."),
        "known_unexplained": {},
        "symbol_aliases": {
            "SUNDARMHLD": {
                "new_symbol": "TSFINV",
                "effective": "2025-10-16",
                "company": "Sundaram Finance Holdings Ltd. -> TSF Investments Ltd.",
                "isin": "INE202Z01029",
                "evidence": ("A name and ticker change, so NSE Indices issued no replacement "
                             "notice. Seen in the data: TSFINV is in the list continuously from "
                             "2025-12-31 to 2026-09-29, and ind_prs10082026.pdf lists "
                             "'TSF Investments Ltd. TSFINV' among the 2026-09-30 exclusions. "
                             "NSE approval ref NSE/LIST/362 (2025-10-10) as relayed by the owner."),
            },
            "HEG": {
                "new_symbol": "HEGAM",
                "effective": "2026-09-23",
                "company": "HEG Ltd.",
                "evidence": ("The daily sync recorded HEG out and HEGAM in on 2026-09-23. Yahoo's "
                             "HEG.NS and HEGAM.NS carry identical adjusted closes on every "
                             "overlapping day (24-30 Sep 2026), and the whole earlier history "
                             "is filed under HEGAM."),
            },
        },
        "notices": notices,
        "placeholder_notices": placeholders,
    }


# ── Rewinding ───────────────────────────────────────────────────────────────

def _iso(d: Any) -> date:
    return d if isinstance(d, date) else date.fromisoformat(str(d)[:10])


def reconstruct(history: dict[str, Any], ledger: dict[str, Any],
                start: str = DEFAULT_START) -> tuple[dict[str, Any], dict[str, Any]]:
    """(extended history, report). Raises ReconstructionError on any disagreement."""
    base = history.get("baseline")
    if not base:
        raise ReconstructionError("the history has no baseline to rewind from")
    start_d, base_d = _iso(start), _iso(base["date"])
    if base_d <= start_d:
        return history, {"status": "already covers", "baseline": base_d.isoformat()}

    after = set(base["symbols"])
    notices = [n for n in ledger["notices"] if start_d < _iso(n["effective"]) <= base_d]
    problems: list[str] = []
    state = set(after)
    for n in sorted(notices, key=lambda n: (n["effective"], n["issued"] or "", n["notice"]),
                    reverse=True):
        ins, outs = set(n["included"]), set(n["excluded"])
        if ins & outs:
            problems.append(f"{n['notice']}: {sorted(ins & outs)} both included and excluded")
        if ins - state:
            problems.append(f"{n['notice']} ({n['effective']}): included but not in the list "
                            f"after it: {sorted(ins - state)}")
        if outs & state:
            problems.append(f"{n['notice']} ({n['effective']}): excluded but still in the list "
                            f"after it: {sorted(outs & state)}")
        state = (state - ins) | outs
    if problems:
        raise ReconstructionError("; ".join(problems))

    # Independent notices from the other side of `start`: the last thing each
    # names about a symbol is what the rewound list must say about it.
    known = set(ledger.get("known_unexplained") or {})
    aliases = ledger.get("symbol_aliases") or {}

    def current_symbol(sym: str, on: str) -> str:
        """The symbol a notice's name trades under on `start`: a ticker change
        is not an exit, so an older notice's name is followed to its new ticker."""
        a = aliases.get(sym)
        return a["new_symbol"] if a and _iso(on) < _iso(a["effective"]) <= start_d else sym

    last: dict[str, tuple[bool, str]] = {}
    for n in sorted(ledger["notices"], key=lambda n: (n["effective"], n["issued"] or "")):
        if not (_iso(ANCHOR_FROM) <= _iso(n["effective"]) <= start_d):
            continue
        for s in n["excluded"]:
            last[current_symbol(s, n["effective"])] = (False, n["notice"])
        for s in n["included"]:
            last[current_symbol(s, n["effective"])] = (True, n["notice"])
    contradicted = sorted(s for s, (want, _) in last.items()
                          if (s in state) != want and s not in known)
    if contradicted:
        raise ReconstructionError(
            "the rewound list contradicts notices effective on or before "
            f"{start}: {[(s, last[s][1]) for s in contradicted]}")

    merged: dict[str, dict[str, set[str]]] = {}
    for n in notices:
        m = merged.setdefault(n["effective"], {"added": set(), "removed": set()})
        m["added"] |= set(n["included"])
        m["removed"] |= set(n["excluded"])
    changes = [{"date": d, "added": sorted(m["added"]), "removed": sorted(m["removed"])}
               for d, m in sorted(merged.items())]

    out = dict(history)
    out["baseline"] = {"date": start_d.isoformat(), "symbols": sorted(state)}
    out["changes"] = changes + list(history.get("changes") or [])

    replay = members_on(out, base_d)
    if replay != after:
        raise ReconstructionError("replaying the rewound history does not reproduce the "
                                  f"{base_d} list: {sorted(replay ^ after)[:10]}")
    sizes = {len(members_on(out, d)) for d in [start_d, *(_iso(c["date"]) for c in changes)]}
    report = {
        "status": "extended",
        "from": base_d.isoformat(), "to": start_d.isoformat(),
        "notices_used": [n["notice"] for n in notices],
        "list_sizes_seen": sorted(sizes),
        "anchor_symbols_checked": len(last),
        "aliases_followed": sorted(a for a in aliases if aliases[a]["new_symbol"] in last),
        "known_unexplained_skipped": sorted(s for s in last if s in known),
    }
    return out, report


def relevant_aliases(history: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    """The ledger's ticker changes whose OLD symbol appears in the history, in the
    shape members_on(canonical=True) reads. A change whose old symbol the history
    never names (SUNDARMHLD: already listed as TSFINV) needs no entry."""
    named = set(history["baseline"]["symbols"])
    for c in history.get("changes") or []:
        named |= set(c.get("added") or []) | set(c.get("removed") or [])
    return {old: {"new_symbol": a["new_symbol"], "effective": a["effective"]}
            for old, a in (ledger.get("symbol_aliases") or {}).items() if old in named}


def _apply_to_file(history: dict[str, Any], extended: dict[str, Any]) -> dict[str, Any]:
    """Write the new baseline and changes to the flat keys and, when present, the
    per-index copy (the two are kept identical by the daily sync)."""
    out = dict(extended)
    entry = (history.get("indices") or {}).get(INDEX_KEY)
    if entry is not None:
        if entry.get("baseline") != history.get("baseline") or entry.get("changes") != history.get("changes"):
            raise ReconstructionError(
                f"indices.{INDEX_KEY} differs from the flat history; refusing to guess which is right")
        out["indices"] = dict(history["indices"])
        out["indices"][INDEX_KEY] = {**entry, "baseline": extended["baseline"],
                                     "changes": extended["changes"]}
    return out


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def check(history: dict[str, Any], ledger: dict[str, Any], start: str = DEFAULT_START) -> list[str]:
    """Problems with the committed history, as strings (empty when it is sound)."""
    problems: list[str] = []
    base = history.get("baseline") or {}
    if _iso(base.get("date", "9999-01-01")) > _iso(start):
        problems.append(f"baseline {base.get('date')} is later than {start}: not extended")
        return problems
    for n in ledger["notices"]:
        eff = _iso(n["effective"])
        if eff <= _iso(start):
            continue
        before = members_on(history, date.fromordinal(eff.toordinal() - 1))
        after = members_on(history, eff)
        if before is None or after is None:
            problems.append(f"{n['notice']}: no coverage around {eff}")
            continue
        if set(n["included"]) & before or set(n["included"]) - after:
            problems.append(f"{n['notice']}: included names do not enter on {eff}")
        if set(n["excluded"]) - before or set(n["excluded"]) & after:
            problems.append(f"{n['notice']}: excluded names do not leave on {eff}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_l = sub.add_parser("ledger", help="build the ledger from downloaded PDFs")
    p_l.add_argument("--pdf-dir", required=True, type=Path)
    p_l.add_argument("--out", type=Path, default=LEDGER)
    p_a = sub.add_parser("apply", help="rewind the history through the ledger")
    p_a.add_argument("--start", default=DEFAULT_START)
    p_a.add_argument("--history", type=Path, default=HISTORY)
    p_a.add_argument("--ledger", type=Path, default=LEDGER)
    p_a.add_argument("--dry-run", action="store_true")
    p_c = sub.add_parser("check", help="verify the committed history against the ledger")
    p_c.add_argument("--start", default=DEFAULT_START)
    p_c.add_argument("--history", type=Path, default=HISTORY)
    p_c.add_argument("--ledger", type=Path, default=LEDGER)
    args = ap.parse_args()

    if args.cmd == "ledger":
        ledger = build_ledger(args.pdf_dir)
        _save(args.out, ledger)
        print(f"{len(ledger['notices'])} notices with a Total Market table, "
              f"{len(ledger['placeholder_notices'])} placeholder notices -> {args.out}")
        return 0

    history, ledger = _load(args.history), _load(args.ledger)
    if args.cmd == "check":
        problems = check(history, ledger, args.start)
        for p in problems:
            print("PROBLEM:", p)
        print("sound" if not problems else f"{len(problems)} problem(s)")
        return 1 if problems else 0

    extended, report = reconstruct(history, ledger, args.start)
    aliases = relevant_aliases(extended, ledger)
    report["aliases_written"] = sorted(aliases)
    print(json.dumps(report, indent=2))
    if args.dry_run:
        return 0
    if report["status"] == "extended":
        _save(args.history, {**_apply_to_file(history, extended), "aliases": aliases})
        print(f"wrote {args.history}")
    elif (history.get("aliases") or {}) != aliases:
        _save(args.history, {**history, "aliases": aliases})
        print(f"wrote {args.history} (aliases only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
