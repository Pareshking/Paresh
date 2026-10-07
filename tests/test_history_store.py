"""History from 2010, precomputed: stored only for the page's exact settings (src/loaders/history_store.py)."""
from pathlib import Path

import pandas as pd

from src.loaders import history_store as hs

ROOT = Path(__file__).resolve().parents[1]


def _request(**over):
    req = {"index": "nifty_500", "start": "2010-01", "end": "2026-09", "floor": 0.0,
           "settings": {"top_n": 20}, "long_last_session": "2026-10-06", "long_built": "2026-10-07"}
    req.update(over)
    return req


def test_a_stored_run_round_trips_and_is_served_only_for_its_exact_request(tmp_path):
    res = {"equity_curve": pd.Series([1.0, 1.1], index=pd.to_datetime(["2026-01-01", "2026-01-02"])),
           "stats": {"total_return": 0.1}}
    name = hs.run_name("nifty_500", 0)
    meta = {"engine": "abc", "runs": {name: {"request": _request(), "months": ["2010-01", "2026-09"]}}}
    path = tmp_path / hs.ASSET
    path.write_bytes(hs.pack({name: res}, meta))
    got = hs.read_run(path, name)
    assert got["equity_curve"].equals(res["equity_curve"]) and got["stats"] == res["stats"]
    meta = hs.read_meta(path)
    assert hs.lookup(meta, name, _request(), "abc")
    assert not hs.lookup(meta, name, _request(end="2026-06"), "abc")             # other months
    assert not hs.lookup(meta, name, _request(settings={"top_n": 15}), "abc")    # other settings
    assert not hs.lookup(meta, name, _request(long_last_session="2026-10-09"), "abc")   # newer long file
    assert not hs.lookup(meta, name, _request(), "changed")                      # other engine code
    assert hs.read_run(path, hs.run_name("nifty_50", 0)) is None
    assert hs.read_meta(tmp_path / "missing.zip") is None


def test_one_run_per_index_and_floor():
    assert hs.run_name("nifty_500", 0) == "nifty_500__floor0"
    assert hs.run_name("nifty_500", 5.0) == "nifty_500__floor5"


def test_the_engine_fingerprint_ignores_line_endings(tmp_path):
    for rel in hs.ENGINE_FILES:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(b"line one\nline two\n")
    unix = hs.engine_fingerprint(tmp_path)
    for rel in hs.ENGINE_FILES:
        (tmp_path / rel).write_bytes(b"line one\r\nline two\r\n")
    assert hs.engine_fingerprint(tmp_path) == unix
    (tmp_path / hs.ENGINE_FILES[0]).write_bytes(b"changed\n")
    assert hs.engine_fingerprint(tmp_path) != unix


def test_the_precompute_uses_the_pages_defaults():
    # The Backtest page's widgets (backtest_view): 20 holdings (index 2), monthly
    # (21, index 2), equal weight, kept while in the top 2x, the default cost and
    # lookback weights; the floor off by default and the usual floor when on.
    from scripts import precompute_history as ph
    from src.core import config as cfg
    from src.engine.liquidity import DEFAULT_FLOOR_CR

    s = ph.default_settings()
    assert s == {"top_n": 20, "rebal_freq": 21, "weight_method": "Equal Weight",
                 "weights": [round(float(w), 6) for w in cfg.DEFAULT_LOOKBACK_WEIGHTS],
                 "stock_cap": round(cfg.DEFAULT_STOCK_CAP, 6), "sector_cap": round(cfg.DEFAULT_SECTOR_CAP, 6),
                 "cost_bps": round(float(cfg.DEFAULT_TRANSACTION_COST_BPS), 6), "buffer_n": 40}
    assert ph.FLOORS == (0.0, float(DEFAULT_FLOOR_CR))
    view = (ROOT / "src/ui/views/backtest_view.py").read_text(encoding="utf-8")
    assert '[10, 15, 20, 30, 50], index=2' in view and "[5, 10, 21, 42, 63],\n            index=2" in view
    assert '[1.0, 1.5, 2.0],\n            index=2' in view


def test_the_page_asks_the_store_before_reading_the_long_file():
    view = (ROOT / "src/ui/views/backtest_view.py").read_text(encoding="utf-8")
    tab = view[view.index("def _backtest_tab("):]
    assert tab.index("_history_stored(history") < tab.index("_history_frames(history")
    assert "@st.cache_resource(show_spinner=False, ttl=3600)\ndef _long_file():" in view


def test_the_long_file_workflow_precomputes_history_after_publishing():
    import yaml

    steps = yaml.safe_load((ROOT / ".github/workflows/nse_long_prices.yml").read_text(encoding="utf-8"))["jobs"]["build"]["steps"]
    names = [s.get("name", "") for s in steps]
    pre = names.index("Precompute History from 2010")
    assert pre > names.index("Publish to the data-latest release")
    assert steps[pre].get("continue-on-error") is True
    assert "history_backtests.zip" in steps[pre]["run"]
