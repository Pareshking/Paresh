"""R2 Section-D raw Yahoo acquisition and adjustment contracts."""

import numpy as np
import pandas as pd

from r2.raw.yahoo import adjusted_from_raw, download_raw_ohlcv, read_raw_ohlcv


def _raw_frame() -> pd.DataFrame:
    idx = pd.to_datetime(["2026-09-01", "2026-09-02", "2026-09-03"])
    cols = pd.MultiIndex.from_product(
        [["AAA", "BBB"], ["Open", "High", "Low", "Close", "Volume"]],
        names=["Ticker", "Price"],
    )
    values = np.array([
        [100, 101, 99, 100, 1000, 200, 202, 198, 200, 2000],
        [50, 51, 49, 50, 1000, 100, 101, 99, 100, 2000],
        [51, 52, 50, 51, 1100, 101, 102, 100, 101, 2100],
    ], dtype=float)
    return pd.DataFrame(values, index=idx, columns=cols)


def test_download_pins_unadjusted_and_raw_fields(monkeypatch):
    seen = {}

    def fake_download(tickers, **kwargs):
        seen["tickers"] = tickers
        seen.update(kwargs)
        return _raw_frame()

    monkeypatch.setattr("r2.raw.yahoo.yf.download", fake_download)
    frame = download_raw_ohlcv(["AAA", "BBB"], period="10y")
    assert seen["auto_adjust"] is False
    assert set(frame.columns.get_level_values(1)) == {"Open", "High", "Low", "Close", "Volume"}


def test_read_raw_round_trip(tmp_path):
    path = tmp_path / "raw.parquet"
    expected = _raw_frame()
    expected.to_parquet(path)
    pd.testing.assert_frame_equal(read_raw_ohlcv(path), expected)


def test_adjustment_is_read_time_only(tmp_path, monkeypatch):
    raw = _raw_frame()
    path = tmp_path / "raw.parquet"
    raw.to_parquet(path)

    import r2.raw.yahoo as raw_loader
    monkeypatch.setattr(raw_loader, "load_events", lambda: [{
        "date": "2026-09-03", "symbol": "AAA", "ratio": 0.5,
    }])

    before = read_raw_ohlcv(path)
    adj_close, _close, high, _low, volume, applied = adjusted_from_raw(before)

    assert applied and applied[0]["symbol"] == "AAA"
    assert float(adj_close.loc["2026-09-01", "AAA"]) == 50.0
    assert float(high.loc["2026-09-01", "AAA"]) == 50.5
    assert float(volume.loc["2026-09-01", "AAA"]) == 1000.0
    pd.testing.assert_frame_equal(read_raw_ohlcv(path), before)


def test_raw_build_workflow_is_manual_and_r2_is_explicit():
    import yaml

    with open(".github/workflows/r2_yahoo_raw_build.yml", encoding="utf-8") as fh:
        spec = yaml.safe_load(fh)
    trigger = spec.get("on") or spec.get(True)
    assert "workflow_dispatch" in trigger
    assert "push" not in trigger
    run = "\n".join(str(step.get("run", "")) for step in spec["jobs"]["build"]["steps"])
    assert "r2_build_yahoo_raw.py" in run
    assert "--dataset prices/yahoo/raw" in run
    assert "--key-root archive/prices/yahoo/raw" in run
