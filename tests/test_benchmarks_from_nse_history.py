"""benchmarks.csv takes NSE's own closes from its index history (S168, owner 24 Nov 2026)."""
import importlib.util
from pathlib import Path

import pandas as pd

from src.loaders import benchmark_store as bs

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("build_benchmarks", ROOT / "scripts" / "build_benchmarks.py")
bb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bb)


def _history(tmp_path):
    rows = [("2013-04-12", "nifty_500", 4352.70, False), ("2013-04-12", "nifty_50", 5528.55, False),
            ("2013-04-15", "nifty_500", 4400.00, False),                      # Nifty 50 missing
            ("2013-04-16", "nifty_500", 4457.50, True), ("2013-04-16", "nifty_50", 5688.95, False)]
    h = pd.DataFrame(rows, columns=["date", "key", "close", "derived"])
    h["date"] = pd.to_datetime(h["date"])
    path = tmp_path / "h.parquet"
    h.to_parquet(path)
    return path


def test_a_date_is_taken_only_with_both_closes_from_nse_itself(tmp_path):
    rows = bb.nse_history_rows(_history(tmp_path))
    assert list(rows.index) == [pd.Timestamp("2013-04-12")]
    assert rows.iloc[0]["nifty500"] == 4352.70 and rows.iloc[0]["source"] == "nse"


def test_nse_replaces_another_source_on_the_same_date_and_keeps_the_rest(tmp_path):
    old = pd.DataFrame({"nifty500": [4352.75, 4457.55], "nifty50": [5528.55, 5688.95],
                        "source": ["kaggle", "kaggle"]},
                       index=pd.DatetimeIndex(["2013-04-12", "2013-04-16"], name="date"))
    out = bs.merge(old, bb.nse_history_rows(_history(tmp_path)))
    assert out.loc["2013-04-12", "source"] == "nse" and out.loc["2013-04-12", "nifty500"] == 4352.70
    assert out.loc["2013-04-16", "source"] == "kaggle"            # NSE's row there is derived


def test_the_committed_file_serves_nse_from_2012():
    b = bs.read().reset_index()
    since = b[b["date"] >= "2012-02-21"]
    assert (since["source"] == "nse").mean() > 0.99
