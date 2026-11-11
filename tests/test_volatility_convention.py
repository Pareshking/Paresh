"""Every standard deviation on the site is the POPULATION one, ddof=0.

Owner, 11 Nov 2026: "OK, match everything". Before that the engine's sizing
path spelled out ``std(ddof=0)`` while every figure the site reported took
pandas' default sample SD, and the difference was a printed number (TODO S119,
docs/TRACK_RECORD.md).

This reads the call sites with ``ast`` rather than grepping for the string
``ddof=0``: a refactor that renames a variable, reflows a line or moves the
call to another module leaves a string match passing while the convention has
quietly reverted. It also asserts a FLOOR on how many call sites it found, so
the test cannot pass by scanning nothing -- a scan whose glob stopped matching
is the failure this repository has been bitten by before.

The two exempt files are listed by name with their reason and are still
scanned: if one loses its standard deviations the test says so, rather than
letting the exemption rot into a blanket.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Directories whose standard deviations are the site's own arithmetic. Tests
# are excluded on purpose: a test may legitimately compute the sample SD to
# assert that the code does NOT.
SCANNED_DIRS = ("src", "scripts", "research")

# A standard deviation is one of these, called as a method.
STD_ATTRS = ("std", "nanstd")

# How many call sites the scan must find. There are 28 on 11 Nov 2026; a floor
# well under that still fails loudly if the walk stops finding files, while
# leaving room to delete a research script.
MIN_SITES = 22
MIN_UNIFIED_SITES = 15

# Files allowed to keep another convention, each with the reason it is not the
# site's own volatility. Both must still contain standard deviations.
EXEMPT = {
    "scripts/research_lookback_sweep.py":
        "replicates a published paper's Sharpe ratios, which are defined there "
        "on the sample SD; a research sweep, not a figure the site prints",
    "scripts/research/rrg_vs_stockcharts.py":
        "searches for the formula that reproduces an EXTERNAL vendor's RRG, so "
        "it must follow the vendor and not us; its verdict is `ratio >= 100`, "
        "which turns on the sign of the numerator and cannot move with ddof",
}

# Reader-visible or sizing sites that must not silently disappear: if the
# volatility of one of these moves house, this test should be the thing that
# notices, not a reader.
REQUIRED_FILES = (
    "src/engine/backtester.py",
    "src/engine/book_risk.py",
    "src/engine/momentum_crash.py",
    "src/engine/portfolio.py",
    "src/engine/calendar_momentum.py",
    "src/ui/views/rrg_view.py",
)


def _std_call_sites() -> list[tuple[str, int, str | None]]:
    """(relative path, line, the ddof argument as source) for every ``.std()``."""
    sites: list[tuple[str, int, str | None]] = []
    for folder in SCANNED_DIRS:
        for path in sorted((ROOT / folder).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not isinstance(func, ast.Attribute) or func.attr not in STD_ATTRS:
                    continue
                ddof = next((ast.unparse(k.value) for k in node.keywords
                             if k.arg == "ddof"), None)
                sites.append((path.relative_to(ROOT).as_posix(), node.lineno, ddof))
    return sites


@pytest.fixture(scope="module")
def sites() -> list[tuple[str, int, str | None]]:
    return _std_call_sites()


def test_the_scan_actually_found_the_call_sites(sites):
    """A test that matches nothing passes everything."""
    assert len(sites) >= MIN_SITES, (
        f"only {len(sites)} standard-deviation call sites found under "
        f"{SCANNED_DIRS}; the scan has stopped seeing the code, so its verdict "
        "below means nothing"
    )
    unified = [s for s in sites if s[0] not in EXEMPT]
    assert len(unified) >= MIN_UNIFIED_SITES, (
        f"only {len(unified)} non-exempt call sites found; see above"
    )
    found = {s[0] for s in sites}
    missing = [f for f in REQUIRED_FILES if f not in found]
    assert not missing, (
        f"no standard deviation left in {missing}: if the calculation moved, "
        "move its entry in REQUIRED_FILES with it and check the new home passes "
        "ddof=0"
    )


def test_every_standard_deviation_is_the_population_one(sites):
    """ddof=0, spelled out, at every site that is not listed as exempt."""
    offenders = [
        f"{path}:{line} passes ddof=" + (ddof if ddof else
                                          "<nothing: pandas' default sample SD>")
        for path, line, ddof in sites
        if path not in EXEMPT and ddof != "0"
    ]
    assert not offenders, (
        "every volatility, dispersion and z-score on the site is the POPULATION "
        "standard deviation, ddof=0, spelled out (owner, 11 Nov 2026: \"OK, "
        "match everything\"; docs/TRACK_RECORD.md, TODO S119). Pandas' default "
        "is the SAMPLE SD, so leaving ddof off reverts the convention and moves "
        "a published figure. Offending sites:\n  " + "\n  ".join(offenders)
    )


def test_the_exemptions_still_describe_real_files(sites):
    """An exemption whose file or whose standard deviations are gone is a lie."""
    for rel, reason in EXEMPT.items():
        assert (ROOT / rel).exists(), f"exempt file {rel} no longer exists"
        assert reason.strip(), f"exempt file {rel} has no reason"
        assert any(s[0] == rel for s in sites), (
            f"{rel} is exempt from the ddof=0 rule but no longer computes a "
            "standard deviation: delete the exemption"
        )
