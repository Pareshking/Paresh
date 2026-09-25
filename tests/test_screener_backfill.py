"""Screener gap-fill: gaps only, never across an adjustment change."""
import numpy as np
import pandas as pd

from scripts import screener_backfill as sb


def _frame(symbols, dates, close=100.0, scale=None):
    idx = pd.DatetimeIndex(dates)
    data = {}
    for s in symbols:
        k = (scale or {}).get(s, 1.0)
        data[(s, "Close")] = np.linspace(close, close + len(idx) - 1, len(idx)) * k
        data[(s, "Volume")] = np.full(len(idx), 1000.0)
    return pd.DataFrame(data, index=idx)


OLD = pd.bdate_range("2025-07-04", "2025-09-17")      # what the store lost
RECENT = pd.bdate_range("2025-09-18", "2026-09-24")   # what both hold


def _source():
    return _frame(["AAA", "BBB", "GONE"], OLD.append(RECENT))


def _store():
    full = _frame(["AAA", "BBB"], OLD.append(RECENT))
    return full.loc[RECENT]


def test_missing_old_dates_are_filled_and_existing_cells_untouched():
    store = _store()
    store.loc[RECENT[-1], ("AAA", "Volume")] = 999.0  # the store's own value
    out, rep = sb.backfill(store, _source())
    assert out.index.min() == OLD[0]
    assert rep["dates_added"] == len(OLD)
    assert out.loc[RECENT[-1], ("AAA", "Volume")] == 999.0
    assert rep["symbols_filled"] == 2 and rep["symbols_skipped"] == 0


def test_a_symbol_whose_basis_changed_is_skipped_not_mixed():
    """A 1:1 bonus since the source was taken halves every stored close."""
    store = _store()
    store[("BBB", "Close")] = store[("BBB", "Close")] / 2
    out, rep = sb.backfill(store, _source())
    assert "BBB" in rep["skipped"] and "disagree" in rep["skipped"]["BBB"]
    assert out.loc[OLD, ("BBB", "Close")].isna().all()      # not filled
    assert out.loc[OLD, ("AAA", "Close")].notna().all()     # the other still is


def test_too_little_overlap_is_unverifiable_and_skipped():
    store = _store().iloc[:3]
    _, rep = sb.backfill(store, _source())
    assert rep["symbols_skipped"] == 2
    assert all("common dates" in why for why in rep["skipped"].values())


def test_a_symbol_the_store_does_not_carry_is_not_added():
    out, _ = sb.backfill(_store(), _source())
    assert "GONE" not in out.columns.get_level_values(0)
    assert list(out.columns) == list(_store().columns)


def test_rounding_noise_within_tolerance_still_fills():
    store = _store()
    store[("AAA", "Close")] = store[("AAA", "Close")] * 1.004
    _, rep = sb.backfill(store, _source())
    assert "AAA" not in rep["skipped"]


def test_the_cli_is_a_dry_run_unless_told(tmp_path, monkeypatch, capsys):
    store_p, src_p = tmp_path / "s.parquet", tmp_path / "r.parquet"
    _store().to_parquet(store_p)
    _source().to_parquet(src_p)
    before = store_p.read_bytes()
    monkeypatch.setattr("sys.argv", ["x", "--store", str(store_p), "--source-file", str(src_p)])
    assert sb.main() == 0
    assert store_p.read_bytes() == before
    monkeypatch.setattr("sys.argv", ["x", "--store", str(store_p), "--source-file", str(src_p), "--apply"])
    assert sb.main() == 0
    assert pd.read_parquet(store_p).index.min() == OLD[0]


def test_a_missing_store_takes_the_source_whole(tmp_path, monkeypatch):
    src_p = tmp_path / "r.parquet"
    _source().to_parquet(src_p)
    target = tmp_path / "cache" / "s.parquet"
    monkeypatch.setattr("sys.argv", ["x", "--store", str(target), "--source-file", str(src_p), "--apply"])
    assert sb.main() == 0
    assert len(pd.read_parquet(target)) == len(_source())


# ── explain: why two copies of one symbol disagree ─────────────────────────

def test_a_bonus_shows_as_one_constant_ratio_before_its_date():
    store, source = _store(), _source()
    bonus = pd.Timestamp("2026-06-01")
    store.loc[store.index < bonus, ("BBB", "Close")] /= 2   # 1:1 bonus re-adjusted history
    got = sb.explain(store, source, "BBB")
    assert got["looks_like_adjustment"] is True
    assert got["ratio_min"] == got["ratio_max"] == 0.5


def test_scattered_corrections_are_not_an_adjustment():
    store, source = _store(), _source()
    for d in (RECENT[10], RECENT[100], RECENT[200]):
        store.loc[d, ("BBB", "Close")] *= 1.03
    got = sb.explain(store, source, "BBB")
    assert got["disagreeing_dates"] == 3
    assert got["looks_like_adjustment"] is False


def test_live_data_says_which_copy_screener_stands_by():
    store, source = _store(), _source()
    d = RECENT[50]
    store.loc[d, ("BBB", "Close")] *= 1.03
    live = store[("BBB", "Close")]            # Screener now serves the store's value
    got = sb.explain(store, source, "BBB", live=live)
    assert (got["live_matches_store"], got["live_matches_source"]) == (1, 0)
