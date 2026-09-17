"""Which dates NSE itself says were trading days.

Counting how much of the universe has a price cannot tell a holiday from a
vendor that has not finished publishing, and the two dates that proved it were
measured a day apart:

                         2026-09-16 (traded)   2026-09-14 (holiday)
    during the sync              20%                   61%
    a day later                  63%                   86%

A single coverage threshold gets one of them wrong whichever value it takes. On
2026-09-16 a 70% floor dropped the real session and kept nothing; by 2026-09-17
the same floor would have kept the holiday and dropped the real session again.
Yahoo backfills a closed day as readily as an open one, so no amount of tuning
rescues the heuristic.

The exchange settles it, and the nightly sync ALREADY ASKS. It downloads
archives.nseindia.com/.../PR{ddmmyy}.zip every morning for market caps and
walks back until one answers; a 200 means NSE published a bhavcopy, which means
the market traded. On 2026-09-16 the job logged both facts three seconds apart:

    20:18:26  Dropping 2 session(s) ... (2026-09-16 at 20%)
    20:18:29  Loaded NSE PR market cap: 2544 stocks for 2026-09-16

It had the confirmation in hand and discarded the session anyway. This module
is where that answer gets written down instead.

ONLY A 200 IS EVIDENCE, AND ONLY OF PRESENCE. NSE answers 403 when it is rate
limiting — six retries on 2026-09-14 never got past it — and a 403 is
indistinguishable from a refusal for any other reason. Reading "no answer" as
"no session" would delete real trading days on a bad network day, which is far
worse than the bug this fixes. So the record holds confirmations only, an
unknown date is simply unknown, and the caller keeps its existing behaviour
there.
"""

from __future__ import annotations

import json
import os
from datetime import date

from src.core.config import REPO_TRADING_DAYS_FILE
from src.core.logger import logger

SCHEMA_VERSION: int = 1


def load_confirmed(path: str | None = None) -> set[str]:
    """ISO dates NSE has confirmed as trading days. Never raises."""
    target = path or REPO_TRADING_DAYS_FILE
    if not os.path.exists(target):
        return set()
    try:
        with open(target, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (ValueError, OSError) as exc:
        logger.warning(
            "Trading-day record unreadable (%s); treating every date as unknown.",
            type(exc).__name__,
        )
        return set()
    days = payload.get("trading_days")
    if not isinstance(days, list):
        return set()
    return {str(d) for d in days if isinstance(d, str) and d}


def record_confirmed(
    days: set[str] | list[str], path: str | None = None
) -> tuple[int, int]:
    """Add confirmed dates to the record. Returns (newly added, total).

    Append-only by construction: a date NSE confirmed once stays confirmed, and
    a run that learns nothing new rewrites nothing. Nothing here ever removes a
    date — an absent date means "not established", never "closed", so forgetting
    one only costs a fallback, while inventing a closure would delete real
    history.
    """
    target = path or REPO_TRADING_DAYS_FILE
    existing = load_confirmed(target)
    incoming = {str(d) for d in days if d}
    added = incoming - existing
    if not added:
        return 0, len(existing)

    merged = sorted(existing | incoming)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "source": "NSE PR bhavcopy (archives.nseindia.com) — HTTP 200 only",
        "note": (
            "Confirmations only. An absent date is UNKNOWN, never closed: NSE "
            "answers 403 when rate limiting and that is indistinguishable from "
            "any other refusal, so absence is never evidence of a holiday."
        ),
        "trading_days": merged,
    }
    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        tmp = target + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1)
            fh.write("\n")
        os.replace(tmp, target)
    except OSError as exc:
        logger.warning("Could not write the trading-day record (%s).", exc)
        return 0, len(existing)

    logger.info(
        "Trading-day record: +%d confirmed by NSE (%s), %d on file.",
        len(added), ", ".join(sorted(added)[:4]), len(merged),
    )
    return len(added), len(merged)


def is_confirmed(day: date | str, confirmed: set[str] | None = None) -> bool:
    """Did NSE publish a bhavcopy for this date?

    False covers BOTH "NSE says no" and "nobody has asked yet" — deliberately
    indistinguishable, because the record cannot express a closure. Callers must
    treat False as "no information", never as "the market was shut".
    """
    days = load_confirmed() if confirmed is None else confirmed
    key = day if isinstance(day, str) else day.isoformat()
    return key in days
