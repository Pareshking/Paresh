"""Every "max drawdown" on the site is the same arithmetic.

It was written out seven times -- the backtester's stats, the record's summary_stats, book_risk's panel,
the Portfolio page's record figure and its daily figure, and three research
scripts -- always as `curve / curve.cummax() - 1`. src/engine/metrics.py now
holds it once. These tests pin the formula and check that no module computes
it itself again, so an eighth copy with a different peak basis cannot creep in
unnoticed.

They do NOT claim those figures are equal: the record's is struck on
month-end values and Portfolio's "Max drawdown, daily" on daily closes, which
is why the same book reads -9.9% and -13.5%. The basis belongs to the caller;
only the formula is shared.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.engine import book_risk, metrics, track_record

ROOT = Path(metrics.__file__).resolve().parents[2]


def test_drawdown_is_the_fall_from_the_running_peak():
    eq = pd.Series([100.0, 120.0, 90.0, 150.0, 75.0])
    dd = metrics.drawdown(eq)
    assert dd.tolist() == [0.0, 0.0, -0.25, 0.0, -0.5]
    assert metrics.max_drawdown(eq) == -0.5
    # The peak is this curve's own running maximum: no window, no calendar.
    assert metrics.drawdown(pd.Series([1.0, 2.0, 3.0])).max() == 0.0


def test_nans_keep_their_place_so_a_plotted_line_keeps_its_length():
    eq = pd.Series([100.0, np.nan, 80.0])
    dd = metrics.drawdown(eq)
    assert len(dd) == 3 and pd.isna(dd.iloc[1])
    assert metrics.max_drawdown(eq) == pytest.approx(-0.2)


def test_it_matches_the_expression_the_call_sites_used_to_write():
    rng = np.random.default_rng(11)
    eq = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0004, 0.02, 900))),
                   index=pd.bdate_range("2020-01-01", periods=900))
    before = eq / eq.cummax() - 1
    pd.testing.assert_series_equal(metrics.drawdown(eq), before)
    assert metrics.max_drawdown(eq) == float(before.min())
    # book_risk reports (now, worst) off the same series.
    assert book_risk._drawdown(eq) == (float(before.iloc[-1]), float(before.min()))


def _cummax_lines(path: Path) -> list[str]:
    """Lines dividing a curve by its own cummax: the start of another copy."""
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        code = line.split("#", 1)[0]
        if ".cummax()" in code and "/" in code.split(".cummax()")[0]:
            out.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()}")
    return out


def test_no_module_still_computes_it_itself():
    offenders = []
    for folder in ("src", "scripts", "research", "agent"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            if path == Path(metrics.__file__):
                continue
            offenders += _cummax_lines(path)
    assert offenders == [], "\n".join(offenders)


def test_the_engine_calls_the_helper():
    for func in (track_record.summary_stats, book_risk._drawdown):
        names = {n.func.id for n in ast.walk(ast.parse(inspect.getsource(func).lstrip()))
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert names & {"drawdown", "max_drawdown"}, func.__name__
