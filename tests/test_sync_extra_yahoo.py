"""Yahoo for the extra universe: its own file, suffix stripped, batched."""
import pandas as pd

from scripts import sync_extra_yahoo as sx


def _yf(batch):
    idx = pd.DatetimeIndex(["2026-09-24", "2026-09-25"], tz="Asia/Kolkata")
    cols = pd.MultiIndex.from_tuples([(t, f) for t in batch for f in ("Close", "High")])
    frame = pd.DataFrame(1.0, index=idx, columns=cols)
    if "GONE.NS" in batch:
        frame[("GONE.NS", "Close")] = float("nan")
        frame[("GONE.NS", "High")] = float("nan")
    return frame


def test_download_batches_and_strips_the_suffix(monkeypatch):
    monkeypatch.setattr(sx, "BATCH", 2)
    calls = []

    def fetch(batch):
        calls.append(batch)
        return _yf(batch)

    out = sx.download(["AAA", "BBB", "GONE"], fetch=fetch)
    assert calls == [["AAA.NS", "BBB.NS"], ["GONE.NS"]]
    # A batch Yahoo returned nothing for adds nothing.
    assert set(out.columns.get_level_values(0)) == {"AAA", "BBB"}
    assert out.index.tz is None and list(out.index.day) == [24, 25]


def test_tickers_skip_placeholders(tmp_path):
    p = tmp_path / "list.csv"
    pd.DataFrame({"Symbol": ["xyz", "DUMMY1", "ABC", "ABC"]}).to_csv(p, index=False)
    assert sx.tickers(p) == ["ABC", "XYZ"]
    assert sx.tickers(tmp_path / "none.csv") == []
