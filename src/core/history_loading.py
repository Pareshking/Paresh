from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def materialize_deep_history(
    source: pd.DataFrame | None,
    symbols: Iterable[str],
) -> pd.DataFrame | None:
    """Copy only requested symbols from the long source when history is needed."""
    if source is None:
        return None
    wanted = set(symbols)
    keep = [column for column in source.columns if column in wanted]
    return source[keep].copy() if keep else None
