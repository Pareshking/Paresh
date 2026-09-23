"""Pure symbol-universe reconciliation for ranking diagnostics.

This module deliberately knows nothing about price data or ranking methodology.
It compares canonical NSE symbols only and excludes DUMMY symbols, matching the
universe loader's tradeability rule. It is used diagnostically when a published
ranking is rejected so the operator can see the exact missing/extra names.
"""

from collections import Counter
from typing import Iterable


def _canonical_symbols(symbols: Iterable[object]) -> list[str]:
    """Normalize symbols without inventing ticker aliases."""
    return [
        value
        for value in (
            str(symbol).strip().upper()
            for symbol in symbols
            if symbol is not None
        )
        if value and not value.startswith("DUMMY")
    ]


def reconcile_symbols(
    expected: Iterable[object],
    actual: Iterable[object],
) -> dict[str, object]:
    """Return set/count differences between expected and published symbols.

    No ticker aliasing is performed: HEGAM stays HEGAM, and a suffixed or
    otherwise different symbol remains different. DUMMY symbols are ignored
    before comparison.
    """
    expected_symbols = _canonical_symbols(expected)
    actual_symbols = _canonical_symbols(actual)
    expected_set = set(expected_symbols)
    actual_set = set(actual_symbols)
    duplicates = sorted(
        symbol
        for symbol, count in Counter(actual_symbols).items()
        if count > 1
    )
    return {
        "expected_count": len(expected_set),
        "published_count": len(actual_set),
        "missing": sorted(expected_set - actual_set),
        "extra": sorted(actual_set - expected_set),
        "duplicates": duplicates,
    }
