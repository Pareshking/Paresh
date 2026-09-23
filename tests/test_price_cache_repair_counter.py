import pandas as pd

from src.loaders import price_loader


def test_count_true_cells_handles_nullable_boolean_masks():
    mask = pd.DataFrame(
        {
            "present": pd.array([True, pd.NA, False], dtype="boolean"),
            "missing": pd.array([False, True, pd.NA], dtype="boolean"),
        }
    )

    assert price_loader._count_true_cells(mask) == 2


def test_merge_cache_repair_counter_preserves_vendor_values_and_cached_gaps(monkeypatch, tmp_path):
    cached = pd.DataFrame(
        {
            ("AAA", "Close"): [100.0, float("nan")],
            ("BBB", "Close"): [200.0, 201.0],
        }, index=pd.to_datetime(["2026-09-21", "2026-09-22"])
    )
    cached.columns = pd.MultiIndex.from_tuples(cached.columns, names=["Ticker", "Price"])

    new_data = pd.DataFrame(
        {
            ("AAA.NS", "Close"): [101.0, 102.0],
            ("BBB.NS", "Close"): [float("nan"), 202.0],
        }, index=pd.to_datetime(["2026-09-21", "2026-09-22"])
    )
    new_data.columns = pd.MultiIndex.from_tuples(new_data.columns, names=["Ticker", "Price"])

    target = tmp_path / "prices.parquet"
    monkeypatch.setattr(price_loader, "PRICES_FILE", str(target))
    monkeypatch.setattr(price_loader, "_drop_phantom_sessions", lambda frame: frame)
    monkeypatch.setattr(price_loader, "_drop_unsettled_rows", lambda frame: frame)

    result = price_loader._merge_and_save_cache(cached, new_data)

    assert result.loc[pd.Timestamp("2026-09-21"), ("AAA", "Close")] == 101.0
    assert result.loc[pd.Timestamp("2026-09-21"), ("BBB", "Close")] == 200.0
    assert result.loc[pd.Timestamp("2026-09-22"), ("AAA", "Close")] == 102.0
    assert result.loc[pd.Timestamp("2026-09-22"), ("BBB", "Close")] == 202.0
    assert target.exists()
