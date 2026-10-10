"""A failed nightly price update must show on the site, and must not hold back every stock.

On 9 Oct 2026 the Screener sync stopped because TRIVENIPT, listed that day, had
no Screener page: no stock got 9 Oct. All Saturday the site showed 8 Oct with a
green pill, because one trading day behind counted as current.
"""
import json
from datetime import date, datetime

import pandas as pd

import src.core.market_time as mt
from src.core import startup_metrics as metrics
from src.core.market_time import INDIA_TZ, last_due_session
from src.ui import components


def setup_function():
    metrics.reset_for_tests()


def _ist(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=INDIA_TZ)


def _pin(monkeypatch, now):
    monkeypatch.setattr(mt, "ist_now", lambda: now)
    monkeypatch.setattr(mt, "ist_today", lambda: now.date())


# ── Which session the prices should hold by now ─────────────────────────────

def test_friday_is_due_on_saturday_morning():
    assert last_due_session(now=_ist(2026, 10, 10, 10)) == date(2026, 10, 9)


def test_a_session_is_not_due_before_nine_the_next_day():
    # Thursday 8 Oct is due at 09:00 on Friday 9 Oct, not at 08:00.
    assert last_due_session(now=_ist(2026, 10, 9, 8)) == date(2026, 10, 7)
    assert last_due_session(now=_ist(2026, 10, 9, 9, 30)) == date(2026, 10, 8)


def test_an_nse_holiday_is_never_due():
    # Dussehra, Tuesday 20 Oct 2026 (NSE's holiday list): Monday is the one due.
    assert last_due_session(now=_ist(2026, 10, 21, 10)) == date(2026, 10, 19)


# ── The 10 Oct case, as the site judges it ──────────────────────────────────

def test_8_oct_prices_on_saturday_10_oct_are_stale(monkeypatch):
    _pin(monkeypatch, _ist(2026, 10, 10, 10))
    metrics.note("price_as_of", "2026-10-08")
    prices = next(i for i in components.data_freshness() if i["label"] == "Prices")
    assert prices["stale"] is True
    assert prices["due"] == date(2026, 10, 9)
    notice = components.stale_prices_notice()
    assert "08 Oct" in notice and "09 Oct" in notice and "10 Oct, 09:00 IST" in notice


def test_9_oct_prices_on_saturday_are_current_and_quiet(monkeypatch):
    _pin(monkeypatch, _ist(2026, 10, 10, 10))
    metrics.note("price_as_of", "2026-10-09")
    prices = next(i for i in components.data_freshness() if i["label"] == "Prices")
    assert prices["stale"] is False
    assert components.stale_prices_notice() == ""


def test_a_session_held_back_while_screener_publishes_is_not_missing(monkeypatch):
    _pin(monkeypatch, _ist(2026, 10, 10, 10))
    metrics.note("price_as_of", "2026-10-08")
    metrics.note("price_deferred_as_of", "2026-10-09")
    metrics.note("price_deferred_coverage", "400/750")
    prices = next(i for i in components.data_freshness() if i["label"] == "Prices")
    assert prices["stale"] is False
    assert components.stale_prices_notice() == ""


# ── New members Screener has not served ─────────────────────────────────────

def test_pending_members_are_named_with_the_day_they_were_first_missed(tmp_path):
    path = tmp_path / "pending.json"
    path.write_text(json.dumps({"symbols": {"TRIVENIPT": "2026-10-10"}}))
    text = components.pending_history_notice(path)
    assert text == "No price history for new index member TRIVENIPT (since 10 Oct)"


def test_no_pending_members_says_nothing(tmp_path):
    path = tmp_path / "pending.json"
    path.write_text(json.dumps({"symbols": {}}))
    assert components.pending_history_notice(path) == ""
    assert components.pending_history_notice(tmp_path / "absent.json") == ""


def test_the_pending_list_keeps_the_first_day_and_drops_served_members(tmp_path):
    import scripts.sync_screener as sync

    path = tmp_path / "pending.json"
    sync.write_pending_history(["TRIVENIPT"], path, today="2026-10-10")
    sync.write_pending_history(["TRIVENIPT", "NEWCO"], path, today="2026-10-12")
    assert json.loads(path.read_text())["symbols"] == {"NEWCO": "2026-10-12", "TRIVENIPT": "2026-10-10"}
    sync.write_pending_history([], path, today="2026-10-13")
    assert json.loads(path.read_text())["symbols"] == {}


def _frame(symbols):
    idx = pd.DatetimeIndex(["2026-10-09"])
    columns = pd.MultiIndex.from_tuples(
        [(s, f) for s in symbols for f in ("Close", "Volume")], names=["Symbol", "Field"]
    )
    return pd.DataFrame([[100.0, 1000.0] * len(symbols)], index=idx, columns=columns)


def test_an_unserved_new_member_no_longer_holds_back_every_stock(monkeypatch, tmp_path):
    import scripts.sync_screener as sync

    monkeypatch.setattr(sync, "PENDING_FILE", tmp_path / "pending.json")
    monkeypatch.setattr(sync, "fetch_indices_data",
                        lambda selected: pd.DataFrame({"Symbol": ["AAA", "TRIVENIPT"]}))
    monkeypatch.setattr(sync.sl, "load_store", lambda: _frame(["AAA"]))
    monkeypatch.setattr(sync.sl, "load_ids", lambda: {})
    monkeypatch.setattr(sync.sl, "save_ids", lambda ids: None)
    monkeypatch.setattr(sync, "_drop_unsettled", lambda frame: (frame, []))
    monkeypatch.setattr(sync, "_deep_check_due", lambda: False)
    monkeypatch.setattr(sync, "EXTRA_LIST", "/nonexistent/ind_nanocap_list.csv")

    def fake_fetch(symbols, **kwargs):
        served = [s for s in symbols if s != "TRIVENIPT"]      # no Screener page yet
        return _frame(served), kwargs["ids"], [s for s in symbols if s == "TRIVENIPT"]

    monkeypatch.setattr(sync.sl, "fetch_universe", fake_fetch)
    merged = {}

    def fake_merge(frame, **kwargs):
        merged["symbols"] = sorted(sync.sl.closes(frame).columns.tolist())
        return frame, 1, 0

    monkeypatch.setattr(sync.sl, "merge_into_store", fake_merge)

    assert sync.run() == 0
    assert merged["symbols"] == ["AAA"]                     # everyone else still gets the night
    pending = json.loads((tmp_path / "pending.json").read_text())["symbols"]
    assert list(pending) == ["TRIVENIPT"]                   # and the workflow fails on this


def test_an_existing_member_losing_its_history_still_stops_the_night(monkeypatch, tmp_path):
    import scripts.sync_screener as sync

    monkeypatch.setattr(sync, "PENDING_FILE", tmp_path / "pending.json")
    monkeypatch.setattr(sync, "fetch_indices_data",
                        lambda selected: pd.DataFrame({"Symbol": ["AAA", "BBB"]}))
    monkeypatch.setattr(sync.sl, "load_store", lambda: _frame(["AAA", "BBB"]))
    monkeypatch.setattr(sync.sl, "load_ids", lambda: {})
    monkeypatch.setattr(sync.sl, "save_ids", lambda ids: None)
    monkeypatch.setattr(sync, "_drop_unsettled", lambda frame: (frame, []))
    monkeypatch.setattr(sync, "_deep_check_due", lambda: False)
    monkeypatch.setattr(sync, "EXTRA_LIST", "/nonexistent/ind_nanocap_list.csv")
    monkeypatch.setattr(sync.sl, "fetch_universe", lambda symbols, **kw: (_frame(["AAA"]), kw["ids"], []))
    monkeypatch.setattr(sync.sl, "merge_into_store", lambda frame, **kw: (_frame(["AAA"]), 1, 0))

    assert sync.run() == 3
