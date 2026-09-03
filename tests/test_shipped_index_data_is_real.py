"""The index constituent files the app ships must contain real NSE data.

They are tracked in git and read at startup to build the universe, so anything
that overwrites them locally can be committed by a routine `git add -A` and
shipped. That is not hypothetical: a test fixture whose faked "successful sync"
wrote to the real INDICES_LOCAL paths replaced NIFTY NEXT 50 with 40 rows of
"Co 0,Financial Services,SYM0,EQ,INE000000000", and it reached main.

These assertions are cheap and they fail loudly the moment placeholder data
lands in a shipped list again.
"""
import csv
import re
from pathlib import Path

import pytest

from src.core.config import INDICES_LOCAL

PLACEHOLDER_SYMBOL = re.compile(r"^SYM\d+$")
PLACEHOLDER_ISIN = re.compile(r"^INE0{6,}\d*$")

_SHIPPED = [
    (name, Path(path)) for name, path in sorted(INDICES_LOCAL.items())
    if Path(path).exists()
]


def test_some_index_lists_are_shipped():
    assert _SHIPPED, "no constituent files found; the universe cannot be built"


@pytest.mark.parametrize("name,path", _SHIPPED, ids=[n for n, _ in _SHIPPED])
def test_no_placeholder_rows_in_a_shipped_index(name, path):
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))

    assert rows, f"{name} is empty"

    bad_symbols = [
        r.get("Symbol", "") for r in rows
        if PLACEHOLDER_SYMBOL.match((r.get("Symbol") or "").strip())
    ]
    assert not bad_symbols, (
        f"{name} ({path}) carries fixture symbols {bad_symbols[:5]}. A test "
        "wrote into the real data directory; sandbox it with monkeypatch."
    )

    bad_isins = [
        r.get("ISIN Code", "") for r in rows
        if PLACEHOLDER_ISIN.match((r.get("ISIN Code") or "").strip())
    ]
    assert not bad_isins, f"{name} carries placeholder ISINs {bad_isins[:5]}"


@pytest.mark.parametrize("name,path", _SHIPPED, ids=[n for n, _ in _SHIPPED])
def test_a_shipped_index_is_not_implausibly_small(name, path):
    """A truncated list is the other way this file goes wrong quietly."""
    expected_floor = {
        "NIFTY 50": 45,
        "NIFTY NEXT 50": 45,
        "NIFTY MIDCAP 150": 140,
        "NIFTY SMALLCAP 250": 230,
        "NIFTY MICROCAP 250": 230,
        "NIFTY TOTAL MARKET": 700,
    }.get(name, 1)
    with path.open(newline="", encoding="utf-8-sig") as fh:
        n = sum(1 for _ in csv.DictReader(fh))
    assert n >= expected_floor, (
        f"{name} has {n} rows, below the {expected_floor} a real list carries"
    )
