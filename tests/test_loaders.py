"""
Unit tests for data loaders and caching mechanisms.
"""

import os
import shutil
import sys
import tempfile

import pandas as pd
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(__file__, "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.loaders import indices_loader, price_loader, mcap_loader


@pytest.fixture(autouse=True)
def patch_constants(monkeypatch):
    monkeypatch.setattr(indices_loader, "INDICES_URLS", {}, raising=False)
    tmp_dir = tempfile.mkdtemp(prefix="nse_test_")
    monkeypatch.setattr(indices_loader, "DATA_DIR", tmp_dir, raising=False)
    monkeypatch.setattr(indices_loader, "REPO_DATA_DIR", tmp_dir, raising=False)
    monkeypatch.setattr(indices_loader, "INDICES_LOCAL", {}, raising=False)
    monkeypatch.setattr(
        indices_loader,
        "SYNC_META_FILE",
        os.path.join(tmp_dir, "sync_meta.json"),
        raising=False,
    )
    monkeypatch.setattr(
        price_loader, "PRICES_FILE", os.path.join(tmp_dir, "prices.parquet"), raising=False
    )
    monkeypatch.setattr(
        mcap_loader, "MCAP_PR_FILE", os.path.join(tmp_dir, "mcap_pr.parquet"), raising=False
    )
    monkeypatch.setattr(
        mcap_loader, "MCAPS_FILE", os.path.join(tmp_dir, "mcap.parquet"), raising=False
    )
    yield
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_sync_official_nse_indices_returns_meta():
    meta = indices_loader.sync_official_nse_indices(force=False)
    assert isinstance(meta, dict)
    for key in ["last_synced", "timestamp", "total_stocks", "indices"]:
        assert key in meta


def test_fetch_indices_data_honors_total_market_selection(monkeypatch, tmp_path):
    csv = "Company Name,Industry,Symbol,Series,ISIN Code\n"
    csv += "Alpha Ltd.,Capital Goods,ALPHA,EQ,INE000A00001\n"
    csv += "Beta Ltd.,Healthcare,BETA,EQ,INE000A00002\n"
    local = tmp_path / "ind_niftytotalmarket_list.csv"
    local.write_text(csv, encoding="utf-8")

    monkeypatch.setattr(
        indices_loader,
        "INDICES_URLS",
        {"NIFTY TOTAL MARKET": "https://example.invalid/total-market.csv"},
        raising=False,
    )
    monkeypatch.setattr(
        indices_loader,
        "INDICES_LOCAL",
        {"NIFTY TOTAL MARKET": str(local)},
        raising=False,
    )

    result = indices_loader._fetch_indices_impl(["NIFTY TOTAL MARKET"])
    assert result["Symbol"].tolist() == ["ALPHA", "BETA"]
    assert len(result) == 2


def test_current_nifty_total_market_snapshot_has_752_constituents():
    root = os.path.abspath(os.path.join(__file__, "../.."))
    path = os.path.join(root, "data", "indices", "ind_niftytotalmarket_list.csv")
    df = pd.read_csv(path)
    assert len(df) == 752
    assert df["Symbol"].astype(str).str.upper().is_unique


def test_fetch_price_history_empty_symbols_returns_empty_df():
    df = price_loader.fetch_price_history([], period="1d", force_refresh=False)
    assert df.empty


def test_fetch_market_caps_empty_symbols_returns_empty_series():
    series = mcap_loader.fetch_market_caps([], force_refresh=False)
    assert series.empty
