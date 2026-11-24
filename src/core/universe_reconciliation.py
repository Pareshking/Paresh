"""Pure symbol-universe reconciliation for ranking diagnostics.

This module deliberately knows nothing about price data or ranking methodology.
It compares canonical NSE symbols only and drops non-tradeable rows (DUMMY and
NaN placeholders) by the universe loader's own rule, is_tradeable_symbol. It is used diagnostically when a published
ranking is rejected so the operator can see the exact missing/extra names.
"""

from collections import Counter
from collections.abc import Iterable

from src.core.tickers import is_tradeable_symbol


def _canonical_symbols(symbols: Iterable[object]) -> list[str]:
    """Normalize symbols without inventing ticker aliases."""
    return [
        value
        for value in (
            str(symbol).strip().upper()
            for symbol in symbols
            if symbol is not None
        )
        if is_tradeable_symbol(value)
    ]


def reconcile_symbols(
    expected: Iterable[object],
    actual: Iterable[object],
    too_new: Iterable[object] = (),
) -> dict[str, object]:
    """Return set/count differences between expected and published symbols.

    No ticker aliasing is performed: HEGAM stays HEGAM, and a suffixed or
    otherwise different symbol remains different. DUMMY symbols are ignored
    before comparison. `too_new` (symbols the caller knows are too new to
    rank, e.g. momentum.too_new_to_rank) moves those out of "missing" into
    "new_listings", so the log does not report a new listing as a loss (S215).
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
    absent = expected_set - actual_set
    new_listings = absent & set(_canonical_symbols(too_new))
    return {
        "expected_count": len(expected_set),
        "published_count": len(actual_set),
        "missing": sorted(absent - new_listings),
        "new_listings": sorted(new_listings),
        "extra": sorted(actual_set - expected_set),
        "duplicates": duplicates,
    }
