"""The watchlist lives in the reader's browser, and the stock page can add to it.

The list used to live only in the address bar (?wl=...), so any internal link
that did not carry it along -- every ticker in the table, every peer -- would
have emptied it. src/ui/watchlist_store.py keeps it in localStorage instead.
The JavaScript half was checked against a real browser: a star survives a new
visit, and a shared ?wl= link merges into the saved list rather than replacing
it. These tests pin the Python half and the contract between the two.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.ui import watchlist_store

PROBE = str(Path(__file__).parent / "_stock_page_probe_app.py")


class _State(dict):
    def __getattr__(self, k):
        return self[k]


@pytest.fixture
def session(monkeypatch):
    ss = _State()
    monkeypatch.setattr(watchlist_store.st, "session_state", ss)
    return ss


def test_parse_keeps_ticker_characters_order_and_no_repeats():
    assert watchlist_store.parse(" abb, M&M;TCS abb\n<b>x ") == ["ABB", "M&M", "TCS", "BX"]


def test_toggle_adds_then_removes_and_queues_a_browser_write(session):
    assert watchlist_store.toggle("welcorp") is True
    assert watchlist_store.symbols() == ["WELCORP"]
    assert session["_wl_write"] == "WELCORP"
    session.pop("_wl_write")
    session["_wl_seen"] = "WELCORP"
    assert watchlist_store.toggle("WELCORP") is False
    assert watchlist_store.symbols() == []
    assert session["_wl_write"] == ""


def test_saving_what_the_browser_already_holds_writes_nothing(session):
    """Waiting for a report the browser has no reason to send would stall reads."""
    session["_wl_seen"] = "ABB,TCS"
    watchlist_store.save(["abb", "tcs"])
    assert "_wl_write" not in session


def test_a_stale_report_does_not_undo_a_fresh_save(session, monkeypatch):
    """Between a save and the browser's echo, its old value must be ignored."""
    reports = iter(["OLD", "OLD", "NEW"])

    class _Result:
        def __init__(self):
            self.stored = next(reports)

    monkeypatch.setattr(watchlist_store, "_bridge", lambda: (lambda **k: _Result()))
    monkeypatch.setattr(watchlist_store.st, "query_params", {})
    session["_wl_seen"] = "OLD"
    watchlist_store.save(["NEW"])
    watchlist_store.sync()          # sends the write; browser still says OLD
    assert watchlist_store.symbols() == ["NEW"]
    watchlist_store.sync()          # a rerun before the echo: still OLD
    assert watchlist_store.symbols() == ["NEW"]
    watchlist_store.sync()          # the echo arrives
    assert watchlist_store.symbols() == ["NEW"] and "_wl_expect" not in session


def test_a_shared_link_is_merged_by_the_browser_and_leaves_the_address(session, monkeypatch):
    sent = {}

    def bridge(**k):
        sent.update(k["data"])
        return type("R", (), {"stored": None})()

    qp = {"wl": "tcs, infy"}
    monkeypatch.setattr(watchlist_store, "_bridge", lambda: bridge)
    monkeypatch.setattr(watchlist_store.st, "query_params", qp)
    watchlist_store.sync()
    assert sent["merge"] == "TCS,INFY"
    assert "wl" not in qp
    # The union with what the browser saved is taken in the browser.
    assert "stored + ',' + merge" in watchlist_store._JS


def test_the_stock_page_offers_watchlist_and_share():
    at = AppTest.from_file(PROBE, default_timeout=180)
    at.query_params["stock"] = "S3"
    at.run()
    assert not at.exception
    labels = [b.label for b in at.button]
    assert "Add to watchlist" in labels
    at.button(key="sp_watch").click().run()
    assert "In watchlist" in [b.label for b in at.button]
    codes = [c.value for c in at.code]
    assert any(v.endswith("/?stock=S3") for v in codes), codes


def _table_rows(at) -> int:
    frames = [e for e in at.main if getattr(e, "type", "") == "iframe"]
    return max((f.proto.srcdoc.count("<tr data-stock=") for f in frames), default=0)


def test_the_filters_sheet_narrows_the_table():
    at = AppTest.from_file(PROBE, default_timeout=180).run()
    assert not at.exception
    everyone = _table_rows(at)
    at.toggle(key="rank_only_passing").set_value(True).run()
    assert not at.exception
    passing = _table_rows(at)
    assert passing < everyone
    at.button(key="rank_filters_reset").click().run()
    assert not at.exception
    assert _table_rows(at) == everyone
    assert not at.warning, [w.value for w in at.warning]
