"""The publish gate refuses a Screener store the app cannot shape cleanly."""
import importlib.util
from pathlib import Path

import pandas as pd

from src.loaders import price_source as ps
from src.loaders import screener_loader

_spec = importlib.util.spec_from_file_location(
    "check_ranking_frames", Path(__file__).resolve().parents[1] / "scripts" / "check_ranking_frames.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

IDX = pd.bdate_range("2026-10-05", periods=3)


def _frames(errors=()):
    c = pd.DataFrame({"A": [1.0, 2.0, 3.0]}, index=IDX)
    return ps.PriceFrames(adj_close=c, close=c, high=None, low=None, volume=c, source="screener",
                          intraday=False, middle_errors=list(errors))


def _store(monkeypatch):
    monkeypatch.setattr(screener_loader, "load_store", lambda _p: pd.DataFrame({("A", "Close"): [1.0]}))
    monkeypatch.setattr(screener_loader, "closes", lambda s: pd.DataFrame({"A": [1.0]}))


def test_a_clean_frame_passes(monkeypatch):
    _store(monkeypatch)
    monkeypatch.setattr(ps, "ranking_frames", lambda *a: _frames())
    assert gate.check("x.parquet") == []


def test_a_raising_frame_is_refused(monkeypatch):
    _store(monkeypatch)

    def boom(*_a):
        raise ValueError("Encountered all NA values")

    monkeypatch.setattr(ps, "ranking_frames", boom)
    problems = gate.check("x.parquet")
    assert len(problems) == 1 and "Encountered all NA values" in problems[0]


def test_a_skipped_nse_step_is_refused(monkeypatch):
    _store(monkeypatch)
    monkeypatch.setattr(ps, "ranking_frames", lambda *a: _frames(["NSE gap fill: ValueError: x"]))
    assert gate.check("x.parquet") == ["NSE gap fill: ValueError: x"]


def test_a_missing_store_is_refused(monkeypatch):
    monkeypatch.setattr(screener_loader, "load_store", lambda _p: pd.DataFrame())
    assert gate.check("missing.parquet")
