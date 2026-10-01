#!/usr/bin/env python3
"""Read NSE Indices press-release text and pull out membership changes.

NSE announces every change to a Nifty index in a press release on
niftyindices.com (https://www.niftyindices.com/press-release). This module
turns the text of those notices (the output of ``pdftotext -layout``) into the
lists of symbols included in and excluded from an index, so point-in-time
membership can be rebuilt from primary documents instead of guessed.

Only parsing lives here. It reads text and never touches the network, and it
invents nothing: a table whose serial numbers do not run 1..n is an error,
because that is what a dropped row looks like.
"""

from __future__ import annotations

import re
from datetime import date

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], start=1)}

_DATE = (r"(January|February|March|April|May|June|July|August|September|"
         r"October|November|December)\s+(\d{1,2}),?\s+(\d{4})")
_EFFECTIVE = re.compile(
    r"(?:effective\s+from|w\.e\.f\.?|with\s+effect\s+from)\s+" + _DATE, re.I)
_ISSUED = re.compile(r"Mumbai,\s+" + _DATE, re.I)

# A table row: serial number, company name, symbol. The name can wrap onto the
# line above, so only the serial and the trailing symbol are relied on.
_ROW = re.compile(r"^\s*(\d{1,3})\s+(.*?)\s{2,}([A-Z0-9][A-Z0-9&\-]*)\s*$")
# "16) Nifty Total Market", or a bare "Nifty Total Market" line. Index-name
# tables in corporate-action notices ("  1   Nifty Next 50") have no bracket
# after the number, so they are not headings.
_HEADING = re.compile(r"^\s*(?:\d{1,2}\)\s+)?(Nifty[^.:,]{1,70}?)\s*$")
_ACTION = re.compile(
    r"following\s+compan(?:y|ies)\s+(?:is|are)\s+being\s+(excluded|included)", re.I)


class NoticeParseError(ValueError):
    """A table in a notice did not parse cleanly."""


def _to_date(m: re.Match) -> date:
    return date(int(m.group(3)), MONTHS[m.group(1).title()], int(m.group(2)))


def effective_dates(text: str) -> list[date]:
    """Every effective date a notice names, in order of appearance."""
    return [_to_date(m) for m in _EFFECTIVE.finditer(text)]


def issued_on(text: str) -> date | None:
    m = _ISSUED.search(text)
    return _to_date(m) if m else None


def sections(text: str, index_name: str) -> dict[str, list[str]]:
    """{"excluded": [symbols], "included": [symbols]} under the heading
    `index_name`, or an empty dict when the notice has no such section.

    Raises NoticeParseError if a table's serial numbers are not 1..n.
    """
    want = index_name.strip().lower()
    in_section = False
    action: str | None = None
    rows: list[tuple[int, str]] = []
    out: dict[str, list[str]] = {}

    def flush() -> None:
        nonlocal action, rows
        if action and rows:
            serials = [s for s, _ in rows]
            if serials != list(range(1, len(rows) + 1)):
                raise NoticeParseError(
                    f"{index_name} / {action}: serial numbers {serials[:3]}..."
                    f"{serials[-3:]} are not 1..{len(rows)}; a row was dropped or "
                    "mis-read")
            out.setdefault(action, []).extend(sym for _, sym in rows)
        action, rows = None, []

    for line in text.splitlines():
        a = _ACTION.search(line)
        if a and in_section:
            flush()
            action = a.group(1).lower()
            continue
        h = _HEADING.match(line)
        if h and not _ROW.match(line) and "following" not in line.lower():
            flush()
            in_section = h.group(1).strip().lower() == want
            continue
        if in_section and action:
            r = _ROW.match(line)
            if r:
                rows.append((int(r.group(1)), r.group(3)))
    flush()
    return out
