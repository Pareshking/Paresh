"""One plan for the next rebalance, read with the record's held weights (S154, 20 Nov 2026).

Found while starting the Actions redesign: the model book reached Actions without its
fill date, so `standing_weights` returned None and the 30 Nov plan fell back to equal
weight; and the Dashboard built the same plan without the held weights at all.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.ui import canonical_book as cb

ROOT = Path(__file__).resolve().parents[1]


def _book():
    return pd.DataFrame({"Symbol": ["B", "A"], **{c: [1.0, 1.0] for c in cb.REQUIRED_BOOK_COLUMNS if c != "Symbol"}})


def test_current_book_carries_the_fill_date(monkeypatch):
    import src.engine.model_record as mr
    monkeypatch.setattr(mr, "record_run", lambda *a, **k: {
        "live_book": _book(), "live_meta": {"as_of": pd.Timestamp("2026-11-19"), "fill_date": pd.Timestamp("2026-11-02")}})
    book, _ = cb.current_book(pd.DataFrame(), None)
    assert list(book["Symbol"]) == ["A", "B"]
    assert book.attrs["fill_date"] == pd.Timestamp("2026-11-02")
    assert book.attrs["as_of"] == pd.Timestamp("2026-11-19")


def test_a_book_without_its_fill_date_is_refused_not_planned_at_equal_weight(monkeypatch):
    from src.ui import model_plan as mp
    import src.engine.backtester as bt
    monkeypatch.setattr(bt, "_hold_cap_on", lambda *a: True)
    book = pd.DataFrame({"Symbol": ["A"], "Weight %": [5.0]})          # no attrs
    with pytest.raises(ValueError, match="fill date"):
        mp.model_plan(book, {}, pd.DataFrame(), pd.DataFrame({"A": [1.0]}), None, "750", pd.Timestamp("2026-11-30"))


def test_the_dashboard_and_actions_build_the_model_plan_in_one_place():
    home = (ROOT / "src/ui/views/dashboard_home_view.py").read_text(encoding="utf-8")
    actions = (ROOT / "src/ui/views/actions_page.py").read_text(encoding="utf-8")   # the page since the 20 Nov rebuild
    assert "plan_rebalance(" not in home and "model_plan(" in home
    assert "model_plan(" in actions
    # Actions may read today's weights to show the book now; only model_plan plans with them.
    assert "standing=" not in actions
