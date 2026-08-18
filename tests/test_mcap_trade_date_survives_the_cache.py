"""The market-cap trade date must survive the disk cache.

Only the live-zip path recorded mcap_pr_date. When the PR parquet was already
on disk -- which is the normal case on GitHub Actions, where the workflow
restores data_cache/ -- the loader took the disk path, knew the caps but not
their date, and the daily sync stamped the committed snapshot with an empty
AsOf. "Market caps" then dropped out of the freshness ribbon entirely, because
a source with no date was not rendered.

The date belongs to the bhavcopy, not to how the bhavcopy was obtained.
"""
from datetime import date, datetime

import pandas as pd
import pytest


@pytest.fixture
def cached_pr_file(tmp_path, monkeypatch):
    from src.loaders import mcap_loader

    path = tmp_path / "mcap_nse.parquet"
    monkeypatch.setattr(mcap_loader, "MCAP_PR_FILE", str(path))
    return mcap_loader, path


def _write_cache(path, trade_date: str | None):
    rows = []
    for sym, cap in (("RELIANCE", 1.5e13), ("TCS", 1.2e13)):
        row = {"Symbol": sym, "MarketCap": cap, "LastUpdated": datetime.now()}
        if trade_date is not None:
            row["TradeDate"] = trade_date
        rows.append(row)
    pd.DataFrame(rows).to_parquet(path, compression="snappy")


def test_disk_cache_reports_the_trade_date(cached_pr_file, monkeypatch):
    mcap_loader, path = cached_pr_file
    _write_cache(path, "2026-08-18")
    monkeypatch.setattr(mcap_loader, "_is_mcap_cache_fresh", lambda: True)

    from src.core import startup_metrics as metrics

    caps = mcap_loader.fetch_market_caps(["RELIANCE", "TCS"])
    facts = metrics.snapshot()["facts"]

    assert len(caps) >= 2
    assert facts["mcap_path"] == "pr_disk_cache"
    assert facts["mcap_pr_date"] == "2026-08-18"
    assert facts["mcap_as_of"] == "2026-08-18"


def test_a_legacy_cache_without_the_column_still_loads(cached_pr_file, monkeypatch):
    """Caches written before this change must not break the loader."""
    mcap_loader, path = cached_pr_file
    _write_cache(path, None)
    monkeypatch.setattr(mcap_loader, "_is_mcap_cache_fresh", lambda: True)

    caps = mcap_loader.fetch_market_caps(["RELIANCE", "TCS"])
    assert len(caps) >= 2          # degrades to undated, does not raise


def test_the_dated_cache_feeds_the_freshness_ribbon(cached_pr_file, monkeypatch):
    """End to end: a dated disk cache produces a dated Market caps chip."""
    mcap_loader, path = cached_pr_file
    _write_cache(path, "2026-08-18")
    monkeypatch.setattr(mcap_loader, "_is_mcap_cache_fresh", lambda: True)
    mcap_loader.fetch_market_caps(["RELIANCE", "TCS"])

    from src.ui.components import data_freshness

    items = {i["label"]: i for i in data_freshness()}
    assert "Market caps" in items
    assert items["Market caps"]["as_of"] == "18 Aug"
    assert items["Market caps"]["as_of"] != "date unknown"


def test_trade_date_is_written_when_the_live_zip_succeeds(tmp_path, monkeypatch):
    """The write side of the same property."""
    from src.loaders import mcap_loader

    path = tmp_path / "mcap_nse.parquet"
    monkeypatch.setattr(mcap_loader, "MCAP_PR_FILE", str(path))
    monkeypatch.setattr(mcap_loader, "_is_mcap_cache_fresh", lambda: False)
    monkeypatch.setattr(mcap_loader, "recent_trading_days", lambda n: [date(2026, 8, 18)])
    monkeypatch.setattr(
        mcap_loader, "_fetch_mcap_from_pr_zip",
        lambda td: {"RELIANCE": 1.5e13, "TCS": 1.2e13},
    )

    mcap_loader.fetch_market_caps(["RELIANCE", "TCS"])

    assert path.exists(), "the PR cache should have been written"
    written = pd.read_parquet(path)
    assert "TradeDate" in written.columns
    assert set(written["TradeDate"]) == {"2026-08-18"}
