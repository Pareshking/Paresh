import numpy as np
import pandas as pd
import pytest

from src.engine.backtester import run_backtest


def test_benchmark_symbol_is_nifty_500():
    # Single source-of-truth benchmark required by the V1 research framework.
    from src.core.config import BENCHMARK_SYMBOL
    assert BENCHMARK_SYMBOL == "^CRSLDX"


def _prices(n=700, cols=10, seed=3):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    return pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, (n, cols)), axis=0)),
        index=idx, columns=[f"S{i}" for i in range(cols)],
    )


def test_the_benchmark_is_the_supplied_index_not_the_universe_mean():
    """Two different index series, same stocks: only the benchmark may move.

    This used to compare two hand-typed series with each other and never ran
    the backtester, so it could not fail.
    """
    px = _prices()
    kw = dict(top_n=4, rebal_freq=21, ema_period=20, high_pct=0.0,
              cost_bps=0.0, buffer_n=6)
    rising = pd.Series(np.linspace(100, 160, len(px)), index=px.index)
    falling = pd.Series(np.linspace(100, 70, len(px)), index=px.index)
    a = run_backtest("bench-rising", px, _benchmark_close=rising, **kw)
    b = run_backtest("bench-falling", px, _benchmark_close=falling, **kw)

    assert a["stats"]["total_return"] == pytest.approx(b["stats"]["total_return"])
    assert a["stats"]["bench_return"] > 0 > b["stats"]["bench_return"]


def test_the_symbol_is_typed_once_in_the_shipped_code():
    """The literal belongs in config.py; everywhere else reads the constant.

    It used to be retyped at every call site -- the record's config, the
    ledger, the benchmark store's column map, the RRG selector, the Backtest
    tab, the sweep and the agent CLI -- so nothing could tell a deliberate
    benchmark from a typo, and a change of index would have had to be made in
    nine places.

    Read as code, not as text: every string the module would actually evaluate,
    docstrings excluded, so prose may still name the index. Tests and docs are
    not scanned. The first version of this test resolved the repository root
    one directory too high, found no files at all and passed on nothing; the
    assertion below therefore also checks that it read something.
    """
    import ast
    from pathlib import Path

    from src.core import config

    root = Path(config.__file__).resolve().parents[2]
    this_file = Path(config.__file__).resolve()
    offenders, scanned = [], 0
    for folder in ("src", "scripts", "agent", "research"):
        for path in sorted((root / folder).rglob("*.py")):
            if path == this_file:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            docstrings = {
                id(n.body[0].value)
                for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and n.body and isinstance(n.body[0], ast.Expr)
                and isinstance(n.body[0].value, ast.Constant)
                and isinstance(n.body[0].value.value, str)
            }
            scanned += 1
            for node in ast.walk(tree):
                if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                        and config.BENCHMARK_SYMBOL in node.value
                        and id(node) not in docstrings):
                    offenders.append(f"{path.relative_to(root)}:{node.lineno}")
    assert scanned > 100 and not offenders, f"scanned {scanned}: " + "\n".join(offenders)
