"""The corporate-actions check must actually have prices to check.

Found on 11 Nov 2026 by reading a step log nobody had opened. `daily_sync` had
been printing

    ✗ no screener closes to check

and exiting 1 in under a second, on every run -- and the step's
`|| echo "::warning::... (new find or failure)"` turned that into a warning
whose wording reads like a find. Seven consecutive green runs carried it.

The cause: the check read `data_cache/screener_prices.parquet` and NOTHING
writes that file on a runner. `price_source.fetch_screener_store` streams the
release asset to a temp file, reads it and deletes it, so the store a sync run
downloads is never on disk for the next process.

These tests pin the two halves of the fix: the published store is used when
the local file is absent, and a run with neither cannot be mistaken for a clean
one.
"""
import importlib.util
from pathlib import Path

import pandas as pd

_spec = importlib.util.spec_from_file_location(
    "check_corporate_actions",
    Path(__file__).resolve().parents[1] / "scripts" / "check_corporate_actions.py")
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


def _store() -> pd.DataFrame:
    """A two-symbol store shaped as the Screener store is: (symbol, field)."""
    idx = pd.bdate_range("2026-09-01", periods=40)
    cols = pd.MultiIndex.from_product([["AAA", "BBB"], ["Close", "Volume"]])
    frame = pd.DataFrame(100.0, index=idx, columns=cols)
    frame.loc[:, (slice(None), "Volume")] = 1000.0
    return frame


def test_the_published_store_is_used_when_the_local_file_is_absent(monkeypatch):
    from src.loaders import price_source, screener_loader

    monkeypatch.setattr(screener_loader, "load_store", lambda *_a, **_k: pd.DataFrame())
    called = []

    def _fetch(*_a, **_k):
        called.append(True)
        return _store()

    monkeypatch.setattr(price_source, "fetch_screener_store", _fetch)

    closes, since, where = m._closes("screener")
    assert called, "the check skipped instead of fetching the store it is meant to scan"
    assert not closes.empty and list(closes.columns) == ["AAA", "BBB"]
    assert since is not None
    assert "published" in where


def test_a_run_with_no_prices_at_all_says_it_did_not_run(monkeypatch, capsys):
    from src.loaders import price_source, screener_loader

    monkeypatch.setattr(screener_loader, "load_store", lambda *_a, **_k: pd.DataFrame())
    monkeypatch.setattr(price_source, "fetch_screener_store", lambda *_a, **_k: None)
    monkeypatch.setattr("sys.argv", ["check_corporate_actions.py", "--fail-on-new"])

    assert m.main() == 2, "a check that could not run must not share an exit code with a find"
    out = capsys.readouterr().out
    assert "did NOT run" in out, "a skipped check must not read like a clean one"
    assert "neither the local file nor the published store" in out


def test_a_scan_names_where_its_prices_came_from(monkeypatch, capsys):
    """A green run should show the check ran, not merely that it exited 0."""
    from src.loaders import price_source, screener_loader

    monkeypatch.setattr(screener_loader, "load_store", lambda *_a, **_k: pd.DataFrame())
    monkeypatch.setattr(price_source, "fetch_screener_store", lambda *_a, **_k: _store())
    monkeypatch.setattr(m, "_load", lambda *_a, **_k: {"schema_version": 1, "events": {}})
    monkeypatch.setattr("sys.argv", ["check_corporate_actions.py", "--dry-run"])

    assert m.main() == 0
    out = capsys.readouterr().out
    assert "scanned screener from" in out and "40 sessions x 2 symbols" in out
