"""A session R2 fails to serve under parallel reads is read again before the build gives up."""
import importlib.util
from datetime import date
from pathlib import Path

import pandas as pd

_spec = importlib.util.spec_from_file_location(
    "audit", Path(__file__).resolve().parents[1] / "scripts" / "nse_history_audit.py")
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


class _Reader:
    def __init__(self, flaky: dict):
        self.flaky = flaky                        # day -> failures left

    def resolve_current(self, dataset, as_of):
        return as_of

    def read_parquet(self, key):
        if self.flaky.get(key, 0) > 0:
            self.flaky[key] -= 1
            raise RuntimeError("ClientError")
        return pd.DataFrame({"date": [key], "mkt": ["N"], "series": ["EQ"], "symbol": ["A"],
                             **{c: [1.0] for c in audit.nh.KEEP if c not in ("date", "mkt", "series", "symbol")}})


def test_a_flaky_session_is_read_on_retry(monkeypatch):
    monkeypatch.setattr(audit, "RETRY_PAUSE_S", 0)
    days = [date(2026, 11, d) for d in (2, 3, 4)]
    reader = _Reader({"2026-11-03": 2})
    out = audit.read_history(reader, days, workers=2, log=lambda *_: None)
    assert sorted(out["date"]) == ["2026-11-02", "2026-11-03", "2026-11-04"]


def test_a_session_that_never_reads_is_still_missing(monkeypatch):
    monkeypatch.setattr(audit, "RETRY_PAUSE_S", 0)
    reader = _Reader({"2026-11-03": 99})
    out = audit.read_history(reader, [date(2026, 11, 2), date(2026, 11, 3)], workers=2, log=lambda *_: None)
    assert list(out["date"]) == ["2026-11-02"]
