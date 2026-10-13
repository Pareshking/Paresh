"""Limits that fail a job when an audit's findings get worse than the known baseline (S47).

    python scripts/audit_limits.py long --audit audit --report data_cache/nse_long/nse_long_report.json

The audits write what they find to small JSON summaries; until 13 Oct 2026 no
job read them, so a regression (a new fake move, a new level step where ours is
the odd one, a session lost from R2) published green. Each limit below is the
count, or share, the latest run of that audit reported, with the run it comes
from: today's state passes, a worse one fails. A finding that is fixed or
explained lowers the baseline: tighten the constant in the same change.

Counts are maxima (a missing entry in a count table is 0). Shares are minima,
less SHARE_TOLERANCE: a share drifts by about a tenth of a point a week
without anything being wrong (Yahoo 0.8946 on 7 Oct, 0.8938 on 10 Oct).

`nse_history_audit.py --fail-on-limits` checks HISTORY_LIMITS against its own
summary; `nse_long_prices.yml` runs this script after its audits.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

# A share may fall this far below its baseline before the job fails.
SHARE_TOLERANCE = 0.005


@dataclass(frozen=True)
class Limit:
    file: str            # the summary the value is read from
    path: tuple          # keys into it
    bound: float         # the limit
    kind: str = "max"    # "max": a count no higher than bound; "min": a share no lower


def _share(baseline: float) -> float:
    return round(baseline - SHARE_TOLERANCE, 4)


# --- The NSE history audit (scripts/nse_history_audit.py, R2's raw history) ---
# Baseline: run 37047812302 (2 Oct 2026, 2008-01-01 to 2026-10-01), the latest
# full run. It predates #348 (one action counted twice: 500 of its 584 "no
# move"), the 13 weekend sessions collected on 3 Oct and #350's wordings, all
# of which only lower these counts. Tighten after the first scheduled run.
HISTORY_MISSING_WEEKDAYS = 35       # weekdays neither held nor a known closed day (2008 holidays)
HISTORY_GAP_DAYS = 87               # sessions whose previous close says one is missing before them
HISTORY_ACTIONS_NO_MOVE = 584       # splits / bonuses the price does not confirm
HISTORY_UNEXPLAINED_JUMPS = 1401    # one-day moves beyond 1.8x no action explains
HISTORY_RENAMES_REFUSED = 142       # automatic renames the continuity check refused
# Not in the 2 Oct summary: the 73 holiday copies the mirror filed (docs/PRICE_PIPELINE.md,
# "Which days are sessions"), also 73 in run 38043565842's raw audit.
HISTORY_COPIED_SESSIONS = 73

HISTORY_LIMITS = (
    # Weekdays of the last week are left out: a holiday becomes a known closed
    # day only a week later (nse_collect.CLOSED_AFTER_DAYS).
    Limit("summary.json", ("missing_weekdays_settled",), HISTORY_MISSING_WEEKDAYS),
    Limit("summary.json", ("gap_days",), HISTORY_GAP_DAYS),
    Limit("summary.json", ("actions", "no move"), HISTORY_ACTIONS_NO_MOVE),
    Limit("summary.json", ("unexplained_jumps",), HISTORY_UNEXPLAINED_JUMPS),
    Limit("summary.json", ("renames_refused",), HISTORY_RENAMES_REFUSED),
    Limit("summary.json", ("copied_sessions",), HISTORY_COPIED_SESSIONS),
)

# --- The long price file's audits (nse_long_prices.yml) ---
# Baseline: the scheduled build of 10 Oct 2026, run 38043565842 (sessions to
# 9 Oct); the same counts as the 7 Oct build, run 37670495104.

# audit_long_prices.py, summary.json: big moves (beyond 21%) the references call fake or
# split evenly on, and level breaks where ours is the side that moved, per reference.
LONG_FAKE_DOWN = 1
LONG_FAKE_UP = 1
LONG_DISPUTED_DOWN = 2
LONG_DISPUTED_UP = 0
LONG_BREAKS_OURS = {"eod2": 2, "marketlens": 3, "tejhq": 211, "tijori": 446, "yahoo": 421, "ss": 0}
# Share of common days within 2% of each reference (TejHQ and MarketLens adjust
# differently by design: their shares are not limits).
LONG_WITHIN_2PCT = {"yahoo": 0.8938, "eod2": 0.8774, "tijori": 0.9162, "ss": 0.9806}

# audit_against_screener.py, screener_summary.json.
SCREENER_WITHIN_2PCT = 0.9781
SCREENER_STEPS_OURS = 265           # lasting level steps where ours is the side that moved

# audit_raw_bars.py, raw_summary.json: NSE's own rows.
RAW_CLOSE_BELOW_LOW = 137           # all in series T0 (docs/PRICE_PIPELINE.md)
RAW_CLOSE_ABOVE_HIGH = 103
RAW_AVG_OUTSIDE_RANGE = 1372        # rounding on tiny volumes
RAW_ISIN_CHANGED = 0                # a symbol change whose ISIN changed: a different company
RAW_HOLIDAY_COPIES = 73             # sessions the build drops

# verify_bse_fill.py, bse_fill_verify.json: days taken from BSE.
BSE_SHARE_WITHIN_2PCT = 0.9858      # of filled cells a reference covers
BSE_OUTLIER_CELLS = 42              # GRAUWEIL 26 and ten others (docs/DATA_CORRECTNESS.md section 6)

# The build's report, nse_long_report.json.
REPORT_UNPRICED = 1                 # TRIVENIPT
REPORT_RENAMES_NOT_JOINED = 16      # each a real break (S16, S25)

LONG_LIMITS = (
    Limit("summary.json", ("big_moves", "down fake"), LONG_FAKE_DOWN),
    Limit("summary.json", ("big_moves", "up fake"), LONG_FAKE_UP),
    Limit("summary.json", ("big_moves", "down disputed"), LONG_DISPUTED_DOWN),
    Limit("summary.json", ("big_moves", "up disputed"), LONG_DISPUTED_UP),
    *(Limit("summary.json", ("breaks_by", ref, "ours"), n) for ref, n in LONG_BREAKS_OURS.items()),
    *(Limit("summary.json", (f"{ref}_levels", "days_within_2pct"), _share(s), "min")
      for ref, s in LONG_WITHIN_2PCT.items()),
    Limit("screener_summary.json", ("intervals_within_2pct",), _share(SCREENER_WITHIN_2PCT), "min"),
    Limit("screener_summary.json", ("level_shifts_ours_moved",), SCREENER_STEPS_OURS),
    Limit("raw_summary.json", ("bar_exceptions", "close below low"), RAW_CLOSE_BELOW_LOW),
    Limit("raw_summary.json", ("bar_exceptions", "close above high"), RAW_CLOSE_ABOVE_HIGH),
    Limit("raw_summary.json", ("bar_exceptions", "average price outside the range"), RAW_AVG_OUTSIDE_RANGE),
    Limit("raw_summary.json", ("symbol_changes", "ISIN changed"), RAW_ISIN_CHANGED),
    Limit("raw_summary.json", ("calendar", "dropped by the build (a holiday copy?)"), RAW_HOLIDAY_COPIES),
    Limit("bse_fill_verify.json", ("share_of_cells_with_a_reference",), _share(BSE_SHARE_WITHIN_2PCT), "min"),
    Limit("bse_fill_verify.json", ("outlier_cells",), BSE_OUTLIER_CELLS),
    Limit("nse_long_report.json", ("unpriced",), REPORT_UNPRICED),
    Limit("nse_long_report.json", ("renames_not_joined",), REPORT_RENAMES_NOT_JOINED),
)


class Missing(KeyError):
    """A summary, or a section of one, the audit did not write: the audit itself failed."""


def _normalise(doc: dict) -> dict:
    """audit_long_prices' breaks come as a list of {ref, who, n}: index them by ref and side."""
    if isinstance(doc.get("breaks"), list) and "breaks_by" not in doc:
        by: dict = {}
        for b in doc["breaks"]:
            by.setdefault(b["ref"], {})[b["who"]] = b["n"]
        doc = {**doc, "breaks_by": by}
    return doc


def value(doc: dict, path: tuple, kind: str = "max"):
    """The value at `path`. A count missing from a count table that exists is 0
    (the audits write only the verdicts they found); anything else missing raises."""
    cur = doc
    for i, key in enumerate(path):
        if not isinstance(cur, dict):
            raise Missing("/".join(path))
        if key not in cur:
            if kind == "max" and i > 0:
                return 0                  # e.g. no "up fake" move, no break against a reference
            raise Missing("/".join(path))
        cur = cur[key]
    if isinstance(cur, (list, tuple, set, dict)):
        return len(cur)
    return cur


def check(docs: dict[str, dict], limits) -> list[str]:
    """One line per limit broken (or summary missing); empty when every limit holds."""
    broken = []
    for lim in limits:
        name = f"{lim.file}: {' / '.join(lim.path)}"
        if lim.file not in docs:
            broken.append(f"{name}: no {lim.file} (the audit did not run to the end)")
            continue
        try:
            v = value(_normalise(docs[lim.file]), lim.path, lim.kind)
        except Missing:
            broken.append(f"{name}: not in the summary")
            continue
        if v is None:
            broken.append(f"{name}: no value")
        elif lim.kind == "max" and v > lim.bound:
            broken.append(f"{name}: {v} > {lim.bound:g} allowed")
        elif lim.kind == "min" and v < lim.bound:
            broken.append(f"{name}: {v} < {lim.bound:g} required")
    return broken


def load(paths) -> dict[str, dict]:
    """{file name: parsed JSON} for those of `paths` that exist."""
    out = {}
    for p in map(Path, paths):
        if p.is_file():
            out[p.name] = json.loads(p.read_text(encoding="utf-8"))
    return out


def report(broken: list[str], what: str, log=print) -> int:
    """Print the outcome (as GitHub annotations) and the exit code: 1 when a limit broke."""
    if not broken:
        log(f"{what}: every audit limit holds")
        return 0
    for line in broken:
        log(f"::error::{what} audit limit: {line}")
    log(f"{what}: {len(broken)} audit limit(s) broken; see scripts/audit_limits.py for each baseline")
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("which", choices=("long", "history"))
    ap.add_argument("--audit", type=Path, required=True, help="the directory the audits wrote to")
    ap.add_argument("--report", type=Path, default=None, help="nse_long_report.json (long only)")
    args = ap.parse_args(argv)
    limits = LONG_LIMITS if args.which == "long" else HISTORY_LIMITS
    files = [args.audit / f for f in {lim.file for lim in limits} if f != "nse_long_report.json"]
    if args.report is not None:
        files.append(args.report)
    broken = check(load(files), limits)
    return report(broken, "long price file" if args.which == "long" else "NSE history")


if __name__ == "__main__":
    sys.exit(main())
