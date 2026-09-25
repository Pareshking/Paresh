"""F&O stocks have no circuit limit, so a one-day move beyond 35% can be real.

Owner, 2026-09-25: treat an F&O move that matches no split/bonus ratio as a
real price move until Screener restates the history (a demerger is restated
within days, a crash never is).
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

import scripts.check_corporate_actions as cca
from scripts.sync_fo_symbols import parse
from src.engine.corporate_actions import (
    CORPORATE_ACTION,
    PRICE_MOVE,
    load_events,
    load_fo_symbols,
    needs_confirmation,
)

FO = {"YESBANK", "VEDL"}
CRASH = {"date": "2026-03-10", "symbol": "YESBANK", "ratio": 0.44, "kind": "unclassified"}
DEMERGER = {"date": "2026-03-10", "symbol": "VEDL", "ratio": 0.35, "kind": "unclassified"}
FO_SPLIT = {"date": "2026-03-10", "symbol": "VEDL", "ratio": 0.5, "kind": "split/bonus"}
CASH_DEMERGER = {"date": "2026-03-10", "symbol": "HEG", "ratio": 0.37, "kind": "unclassified"}


def _log(tmp_path, *events):
    p = tmp_path / "log.json"
    p.write_text(json.dumps({"events": {f"k{i}": e for i, e in enumerate(events)}}))
    return p


def test_unconfirmed_fo_moves_are_not_neutralised_everything_else_is(tmp_path):
    p = _log(tmp_path, CRASH, DEMERGER, FO_SPLIT, CASH_DEMERGER)
    got = load_events(p, fo_symbols=FO)
    assert got == [FO_SPLIT, CASH_DEMERGER]   # a clean ratio, or no F&O: an action


def test_a_confirmed_fo_demerger_is_neutralised_and_a_price_move_never(tmp_path):
    confirmed = {**DEMERGER, "verdict": CORPORATE_ACTION}
    real = {**CASH_DEMERGER, "verdict": PRICE_MOVE}
    assert load_events(_log(tmp_path, confirmed, real), fo_symbols=FO) == [confirmed]


def test_needs_confirmation_only_for_fo_and_no_clean_ratio():
    assert needs_confirmation(CRASH, FO)
    assert not needs_confirmation(FO_SPLIT, FO)
    assert not needs_confirmation(CASH_DEMERGER, FO)
    assert not needs_confirmation({**CRASH, "verdict": CORPORATE_ACTION}, FO)


def _closes(restated_symbols: set[str]) -> pd.DataFrame:
    idx = pd.bdate_range("2026-01-05", periods=60)
    when = idx.get_loc(pd.Timestamp("2026-03-10"))
    out = {}
    for sym, ratio in (("YESBANK", 0.44), ("VEDL", 0.35)):
        s = np.full(len(idx), 100.0)
        if sym in restated_symbols:
            s[:when] *= ratio          # Screener rescaled the history: no step
        else:
            s[when:] *= ratio          # the step is still there
        out[sym] = s
    return pd.DataFrame(out, index=idx)


def test_screener_restating_the_history_confirms_a_corporate_action():
    events = {"crash": dict(CRASH), "demerger": dict(DEMERGER)}
    closes = _closes(restated_symbols={"VEDL"})
    got = cca.confirm_restated(events, closes, closes.index[0], fo_symbols=FO)
    assert got == ["demerger"]
    assert events["demerger"]["verdict"] == CORPORATE_ACTION
    assert "verdict" not in events["crash"]     # still a real move


def test_weekly_history_never_confirms_anything():
    """Across weekly points a crash and its rebound look like no step."""
    events = {"demerger": dict(DEMERGER)}
    closes = _closes(restated_symbols={"VEDL"})
    daily_from = pd.Timestamp("2026-03-20")     # the event is before the daily tail
    assert cca.confirm_restated(events, closes, daily_from, fo_symbols=FO) == []


def test_an_owner_verdict_is_never_overwritten():
    events = {"real": {**DEMERGER, "verdict": PRICE_MOVE}}
    closes = _closes(restated_symbols={"VEDL"})
    assert cca.confirm_restated(events, closes, closes.index[0], fo_symbols=FO) == []
    assert events["real"]["verdict"] == PRICE_MOVE


def test_the_market_lot_file_parses_to_stock_symbols_only():
    text = ("UNDERLYING ,SYMBOL ,SEP-26\n"
            "NIFTY 50 ,NIFTY ,65\n"
            "NIFTY BANK ,BANKNIFTY ,30\n"
            "YES BANK LIMITED ,YESBANK ,31100\n"
            "PB FINTECH LIMITED ,POLICYBZR ,350\n")
    assert parse(text) == ["POLICYBZR", "YESBANK"]


def test_the_committed_list_carries_the_stocks_that_prompted_the_rule():
    fo = load_fo_symbols()
    assert len(fo) >= 100
    assert {"POLICYBZR", "YESBANK"} <= fo
