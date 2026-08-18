"""Market caps committed to the repo by the daily sync.

NSE refuses the production host's IP, so production cannot fetch the PR
archive itself. Without a repo-side source the only fallback is yfinance,
which on a cold start meant 750 individual lookups and the slowest startup
stage measured (45.9s). The sync runs on GitHub Actions, where NSE is
reachable, and leaves its result in the repository.
"""
import importlib

import pandas as pd
import pytest

from src.core.config import REPO_MCAP_FILE


@pytest.fixture
def loader(tmp_path, monkeypatch):
    """mcap_loader with every on-disk cache pointed at an empty tmp dir."""
    import src.loaders.mcap_loader as ml

    importlib.reload(ml)
    monkeypatch.setattr(ml, "MCAP_PR_FILE", str(tmp_path / "pr.parquet"))
    monkeypatch.setattr(ml, "MCAPS_FILE", str(tmp_path / "yf.parquet"))
    # No network in tests: the live PR walk must find nothing.
    monkeypatch.setattr(ml, "_fetch_mcap_from_pr_zip", lambda *a, **k: {})
    monkeypatch.setattr(ml, "_fetch_mcaps_yfinance", lambda syms: {})
    return ml


def _write_snapshot(path, rows):
    pd.DataFrame(rows).to_csv(path, index=False)


def test_repo_snapshot_is_used_when_nse_is_unreachable(loader, tmp_path, monkeypatch):
    snap = tmp_path / "nse_market_caps.csv"
    _write_snapshot(snap, {"Symbol": ["RELIANCE", "TCS"], "MarketCap": [1.9e13, 1.4e13]})
    monkeypatch.setattr(loader, "REPO_MCAP_FILE", str(snap))

    caps = loader.fetch_market_caps(["RELIANCE", "TCS"])
    assert dict(caps) == {"RELIANCE": 1.9e13, "TCS": 1.4e13}


def test_snapshot_symbols_are_normalised(loader, tmp_path, monkeypatch):
    snap = tmp_path / "s.csv"
    _write_snapshot(snap, {"Symbol": [" reliance ", "Tcs"], "MarketCap": [1.0, 2.0]})
    monkeypatch.setattr(loader, "REPO_MCAP_FILE", str(snap))
    assert set(loader.fetch_market_caps(["RELIANCE", "TCS"]).index) == {"RELIANCE", "TCS"}


@pytest.mark.parametrize("bad", [0, -1, None, "not-a-number"])
def test_non_positive_or_unparseable_caps_are_dropped(loader, tmp_path, monkeypatch, bad):
    snap = tmp_path / "s.csv"
    _write_snapshot(snap, {"Symbol": ["GOOD", "BAD"], "MarketCap": [5.0, bad]})
    monkeypatch.setattr(loader, "REPO_MCAP_FILE", str(snap))
    caps = loader.fetch_market_caps(["GOOD", "BAD"])
    assert "BAD" not in caps.index
    assert caps["GOOD"] == 5.0


def test_absent_snapshot_is_not_an_error(loader, tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "REPO_MCAP_FILE", str(tmp_path / "nope.csv"))
    assert len(loader.fetch_market_caps(["RELIANCE"])) == 0


def test_corrupt_snapshot_degrades_rather_than_raising(loader, tmp_path, monkeypatch):
    snap = tmp_path / "bad.csv"
    snap.write_text("this is not,a valid\nmarket cap file\n")
    monkeypatch.setattr(loader, "REPO_MCAP_FILE", str(snap))
    assert len(loader.fetch_market_caps(["RELIANCE"])) == 0


def test_live_nse_still_wins_over_the_snapshot(loader, tmp_path, monkeypatch):
    """The snapshot is a fallback, not a replacement for fresh data."""
    snap = tmp_path / "s.csv"
    _write_snapshot(snap, {"Symbol": ["RELIANCE"], "MarketCap": [1.0]})
    monkeypatch.setattr(loader, "REPO_MCAP_FILE", str(snap))
    monkeypatch.setattr(loader, "_fetch_mcap_from_pr_zip", lambda *a, **k: {"RELIANCE": 999.0})
    assert loader.fetch_market_caps(["RELIANCE"])["RELIANCE"] == 999.0


def test_repo_mcap_path_is_inside_the_committed_data_dir():
    assert REPO_MCAP_FILE.replace("\\", "/").endswith("data/nse_market_caps.csv")
