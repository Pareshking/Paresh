"""Shared statistics of an equity curve.

Drawdown was written out six times -- the record's summary, the book risk
panel, the Portfolio page twice and three research scripts -- always as the
same expression, `curve / curve.cummax() - 1`. One helper, so a reader can see
that every "max drawdown" on the site is the same arithmetic.

What differs between those six is the CURVE, not the formula, and that stays
with the caller: the record's figure is struck on month-end values and
Portfolio's "Max drawdown, daily" on daily closes, which is why the same book
reads -9.9% in one place and -13.5% in the other (both correct; each names its
basis). Nothing here resamples, re-bases or windows a curve.

Volatility is deliberately NOT here: the engine's position sizing uses the
population standard deviation (ddof=0) and the reported statistics use the
sample one (ddof=1), and unifying them would change a printed number. See
docs/TODO.md S118.
"""
from __future__ import annotations

import pandas as pd


def drawdown(curve: pd.Series) -> pd.Series:
    """Fall from the running peak, as a fraction (-0.12 is 12% below the peak).

    The peak is the highest value of this curve so far -- no window, no
    calendar -- so the first point is always 0 and the series is never
    positive. NaNs are kept where they are: a caller plotting the line needs it
    to stay the same length as the curve, and `.min()` ignores them anyway.
    """
    return curve / curve.cummax() - 1.0


def max_drawdown(curve: pd.Series) -> float:
    """The deepest point of `drawdown(curve)`; NaN for an empty curve."""
    return float(drawdown(curve).min())
