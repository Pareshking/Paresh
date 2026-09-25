import pandas as pd
import pytest

from src.loaders import price_loader


def _raw_frame(symbol: str, dates: list[str]) -> pd.DataFrame:
    index = pd.DatetimeIndex(dates)
    columns = pd.MultiIndex.from_product(
        [[f"{symbol}.NS"], ["Close", "Volume"]],
        names=["Ticker", "Price"],
    )
    return pd.DataFrame(
        [[100.0, 1000.0] for _ in index],
        index=index,
        columns=columns,
    )


def test_new_cache_symbols_excludes_dummy_and_preserves_canonical_symbol():
    cached = _raw_frame("OLDSTOCK", ["2026-09-17"])
    assert price_loader._new_cache_symbols(
        ["OLDSTOCK", "HEGAM", "DUMMYHEG"], cached
    ) == ["HEGAM"]


def test_new_symbol_full_history_uses_requested_period_and_only_new_symbols(monkeypatch):
    calls = []

    def fake_download(tickers, **kwargs):
        calls.append((tickers, kwargs))
        return _raw_frame("HEGAM", ["2025-09-18", "2026-09-17"])

    monkeypatch.setattr(price_loader.yf, "download", fake_download)

    out = price_loader._download_full_symbol_history(["HEGAM"], "10y")

    assert calls == [
        (
            ["HEGAM.NS"],
            {
                "period": "10y",
                "progress": False,
                "group_by": "ticker",
                "threads": True,
                "auto_adjust": True,
            },
        )
    ]
    assert set(out.columns.get_level_values(0)) == {"HEGAM"}
    assert len(out.index) == 2


def test_fetch_price_history_full_backfills_new_symbol_before_fresh_cache_return(
    monkeypatch, tmp_path
):
    cache_path = tmp_path / "prices.parquet"
    cached = _raw_frame("OLDSTOCK", ["2026-09-17"])
    cached.to_parquet(cache_path)

    calls = []

    def fake_download(tickers, **kwargs):
        calls.append(tickers)
        return _raw_frame("HEGAM", ["2025-09-18", "2026-09-17"])

    monkeypatch.setattr(price_loader, "PRICES_FILE", str(cache_path))
    monkeypatch.setattr(price_loader.yf, "download", fake_download)
    monkeypatch.setattr(price_loader, "_cache_is_current", lambda _: True)

    def should_not_increment(*args, **kwargs):
        pytest.fail("existing-symbol incremental download was used for a new symbol")

    monkeypatch.setattr(price_loader, "_fetch_incremental_updates", should_not_increment)

    out = price_loader.fetch_price_history(
        ["OLDSTOCK", "HEGAM", "DUMMYHEG"],
        period="10y",
        force_refresh=False,
        heal_days=0,
    )

    assert set(price_loader._cached_symbols(out)) == {"OLDSTOCK", "HEGAM"}
    assert calls == [["HEGAM.NS"]]
    assert pd.Timestamp("2025-09-18") in out.index
    assert pd.Timestamp("2026-09-17") in out.index

def test_new_symbol_batch_gap_is_retried_individually(monkeypatch):
    calls = []

    def fake_download(tickers, **kwargs):
        calls.append((tickers, kwargs))
        if isinstance(tickers, list):
            # Simulate a batch response that silently omits HEGAM.
            return _raw_frame("OTHER", ["2026-09-17"])
        return _raw_frame("HEGAM", ["2025-09-18", "2026-09-17"])

    monkeypatch.setattr(price_loader.yf, "download", fake_download)

    out = price_loader._download_full_symbol_history(["HEGAM"], "10y")

    assert calls[0][0] == ["HEGAM.NS"]
    assert calls[1][0] == "HEGAM.NS"
    assert set(out.columns.get_level_values(0)) == {"OTHER", "HEGAM"}
