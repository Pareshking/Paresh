"""The nightly sync must ask NSE what traded BEFORE it judges the prices.

The confirmation record fixed the right problem in the wrong order. Market caps
were fetched after prices, and the market-cap fetch is what asks NSE for a
bhavcopy -- so on every run the newest session was judged on vendor coverage
alone, and the confirmation that would have saved it was written seconds later.

The 2026-09-16 run, which the record was added to fix:

    20:18:26  Dropping 2 session(s) ... (2026-09-16 at 20%)
    20:18:29  Loaded NSE PR market cap: 2544 stocks for 2026-09-16

The 2026-09-17 run, with the record in place and consulted:

    20:27:22  Dropping 1 session(s) ... (2026-09-17 at 20%)
              Trading days confirmed by NSE: +1 new, 4 on record.

Identical failure, one day apart. The "Keeping ... NSE confirmed" line had
never fired in production, because the newest session -- the only one the
vendor is still publishing, and so the only one that needs rescuing -- can
never be on a record written after it is judged.

These tests read the script structurally rather than running it: the ordering
is the whole fix, and it is invisible to every behavioural test in the suite.
"""

import ast

SCRIPT = "scripts/sync_data.py"


def _daily_sync():
    tree = ast.parse(open(SCRIPT, encoding="utf-8").read())
    return next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "run_daily_sync"
    )


def _call_lines(fn, name):
    """Line numbers where ``name(...)`` is called inside ``fn``."""
    out = []
    for n in ast.walk(fn):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        ident = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
        if ident == name:
            out.append(n.lineno)
    return sorted(out)


# ── What gets PUBLISHED must pass the same guards the app reads with ─────────
#
# Everything the publish step writes is consumed by something that does not
# re-check it: the app's cold-start snapshot, the archive the monthly freeze
# reads, and _precompute_rankings, which reads the snapshot file straight back
# off disk and ranks it.
#
# A bare read_parquet here shipped four non-sessions -- 2026-01-15, 2026-05-01,
# 2026-05-28 and 2026-06-26, every priced symbol flat at zero volume, two of
# them at 100% vendor coverage. The app strips them on read and the precompute
# did not, so the two would rank different frames while every field of the
# contract still matched. A wrong answer served fast is worse than no artifact.


