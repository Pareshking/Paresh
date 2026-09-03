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


def _shipped_total_market() -> pd.DataFrame:
    root = os.path.abspath(os.path.join(__file__, "../.."))
    return pd.read_csv(
        os.path.join(root, "data", "indices", "ind_niftytotalmarket_list.csv")
    )


def test_the_shipped_total_market_snapshot_is_complete():
    """The snapshot is whole and free of duplicates.

    This used to assert a raw row count of exactly 752, which failed the moment
    NSE revised the index -- it was 754 by Sep 2026. Worse, it counted rows the
    application never uses: NSE ships DUMMY placeholder rows in this file for
    corporate actions in flight, and the loader discards them.

    So assert what actually matters -- a plausible number of REAL constituents,
    and no duplicates -- rather than a number that drifts with every revision.
    A range still catches the failures worth catching: a truncated download, an
    empty file, or a parse that silently split the universe in half.
    """
    df = _shipped_total_market()
    symbols = df["Symbol"].astype(str).str.strip().str.upper()
    real = symbols[~symbols.str.startswith("DUMMY")]

    assert 700 <= len(real) <= 850, (
        f"{len(real)} real constituents is outside the plausible range for "
        "NIFTY TOTAL MARKET; the file is probably truncated or malformed"
    )
    assert symbols.is_unique


def test_dummy_placeholders_never_reach_the_universe(monkeypatch):
    """DUMMY rows are NSE bookkeeping, not tradeable stocks.

    ind_niftytotalmarket_list.csv genuinely ships rows like
    "Dummy Triveni Ltd.,Capital Goods,DUMMYTRVN,EQ,DUM256C01024". They are
    placeholders for corporate actions and have no price history, so a universe
    carrying them would rank and potentially BUY a ticker that cannot be
    traded. indices_loader discards any symbol starting with DUMMY -- a filter
    that had no test at all until this one, on a file that really does contain
    four of them.
    """
    root = os.path.abspath(os.path.join(__file__, "../.."))
    real_file = os.path.join(root, "data", "indices", "ind_niftytotalmarket_list.csv")

    shipped = _shipped_total_market()["Symbol"].astype(str).str.strip().str.upper()
    dummies = shipped[shipped.str.startswith("DUMMY")]
    assert not dummies.empty, (
        "fixture assumption gone: the shipped file no longer carries DUMMY "
        "rows, so this test would pass without exercising the filter"
    )

    monkeypatch.setattr(
        indices_loader,
        "INDICES_LOCAL",
        {"NIFTY TOTAL MARKET": real_file},
        raising=False,
    )
    monkeypatch.setattr(
        indices_loader,
        "INDICES_URLS",
        {"NIFTY TOTAL MARKET": "https://example.invalid/total-market.csv"},
        raising=False,
    )

    result = indices_loader._fetch_indices_impl(["NIFTY TOTAL MARKET"])
    loaded = result["Symbol"].astype(str).str.upper()

    assert not loaded.str.startswith("DUMMY").any(), (
        f"placeholder tickers reached the universe: "
        f"{sorted(loaded[loaded.str.startswith('DUMMY')])}"
    )
    # Every real constituent survived; only the placeholders were dropped.
    assert len(result) == len(shipped) - len(dummies)


def test_fetch_price_history_empty_symbols_returns_empty_df():
    df = price_loader.fetch_price_history([], period="1d", force_refresh=False)
    assert df.empty


def test_fetch_market_caps_empty_symbols_returns_empty_series():
    series = mcap_loader.fetch_market_caps([], force_refresh=False)
    assert series.empty
