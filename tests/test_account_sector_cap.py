"""The canonical account carries the 5% stock / 30% industry caps (owner, 2026-10-02).

Before this, record_run passed no sector map, so run_backtest's 30% default
never bound and the account held 40-60% in one industry while Actions and the
research backtest applied 30%.
"""
import ast
import inspect
import pathlib
import textwrap

import pandas as pd

from src.engine import backtester as bt
from src.engine import model_record
from src.engine.model_record import record_sector_map
from src.engine.track_record import TRACK_RECORD_CONFIG, run_backtest_kwargs
from src.loaders import former_members


def test_pinned_config_carries_the_caps():
    assert TRACK_RECORD_CONFIG["stock_cap"] == 0.05
    assert TRACK_RECORD_CONFIG["sector_cap"] == 0.40


def test_current_members_keep_their_nse_index_industry():
    # industry_for re-labels current members from TradingView; for these three
    # it disagreed with the index file the ranking and Actions read.
    idx = pd.read_csv(former_members.INDEX_FILE)
    nse = dict(zip(idx["Symbol"], idx["Industry"]))
    names = [s for s in ("CPPLUS", "SIGMAADV", "STLTECH") if s in nse]
    assert names, "fixture names left the index; pick current members"
    got = record_sector_map(names)
    assert all(got[s] == nse[s] for s in names)
    every = record_sector_map(list(nse))
    assert every == {s: str(nse[s]) for s in nse}


def test_former_members_still_get_a_label():
    idx = pd.read_csv(former_members.INDEX_FILE)
    gone = "CIGNITITEC"
    if gone in set(idx["Symbol"]):
        return
    assert record_sector_map([gone])[gone]


def _run_backtest_call(func):
    """The run_backtest call inside `func`, as syntax rather than as text.

    Still a source check -- running record_run_uncached needs the whole price
    and membership stack -- but it reads the call, so it survives the
    arguments being passed through track_record.run_backtest_kwargs instead of
    being spelled out at the call site, and still fails if one goes missing.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "run_backtest"):
            return node
    raise AssertionError(f"{func.__name__} does not call run_backtest")


def test_record_run_passes_the_caps_and_a_sector_map():
    call = _run_backtest_call(model_record.record_run_uncached)
    starred = [ast.unparse(k.value) for k in call.keywords if k.arg is None]
    named = {k.arg for k in call.keywords if k.arg}
    assert "run_backtest_kwargs(cfg)" in starred
    assert any(k.arg == "sector_map" and ast.unparse(k.value).startswith("record_sector_map(")
               for k in call.keywords), named
    # And the shared block really carries the caps through to the engine.
    kw = run_backtest_kwargs(TRACK_RECORD_CONFIG)
    assert kw["stock_cap"] == TRACK_RECORD_CONFIG["stock_cap"] == 0.05
    assert kw["sector_cap"] == TRACK_RECORD_CONFIG["sector_cap"] == 0.40
    # Every key it supplies is an argument run_backtest accepts, so a renamed
    # setting cannot be swallowed by **kwargs or raise only in production.
    params = inspect.signature(bt.run_backtest.__wrapped__).parameters
    assert set(kw) <= set(params), set(kw) - set(params)


def test_the_freeze_script_and_the_live_replay_run_one_configuration():
    """The monthly freeze and the app's replay must agree argument for argument.

    They each used to spell the sixteen settings out, so a new rule could be
    added to one and not the other and a frozen month would replay under
    different rules than it was struck under.
    """
    freeze = pathlib.Path(inspect.getsourcefile(model_record)).parents[2] / "scripts" / "update_track_record.py"
    tree = ast.parse(freeze.read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "run_backtest"]
    assert len(calls) == 1
    assert "run_backtest_kwargs(cfg)" in [ast.unparse(k.value) for k in calls[0].keywords if k.arg is None]


def test_ledger_months_are_struck_under_the_capped_config():
    import json
    from src.engine.track_record import LEDGER_PATH
    ledger = json.loads(open(LEDGER_PATH, encoding="utf-8").read())
    # The latest STRATEGY rebuild; a benchmark-only correction re-strikes no month.
    last = [r for r in ledger["rebuilds"] if r.get("kind") != "benchmark_correction"][-1]
    assert {m["config"] for m in ledger["months"].values()} == {last["config"]}
    assert "40%" in last["note"]
