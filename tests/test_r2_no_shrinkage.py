from __future__ import annotations

import pandas as pd
import pytest

from scripts.audit_no_shrinkage import audit_no_shrinkage


def _write(path, frame):
    frame.to_parquet(path)


def test_no_shrinkage_accepts_new_history_and_preserved_cells(tmp_path):
    dates = pd.to_datetime(["2026-01-01", "2026-01-02"])
    before = pd.DataFrame({"AAA": [1.0, 2.0], "BBB": [3.0, None]}, index=dates)
    after = pd.DataFrame(
        {"AAA": [1.0, 2.0, 4.0], "BBB": [3.0, None, 5.0], "CCC": [7.0, 8.0, 9.0]},
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
    )
    old_path, new_path = tmp_path / "before.parquet", tmp_path / "after.parquet"
    _write(old_path, before)
    _write(new_path, after)

    result = audit_no_shrinkage(old_path, new_path)

    assert result["status"] == "PASS"
    assert result["before_sessions"] == 2
    assert result["after_sessions"] == 3


@pytest.mark.parametrize(
    "after",
    [
        pd.DataFrame({"AAA": [1.0]}, index=pd.to_datetime(["2026-01-01"])),
        pd.DataFrame({"AAA": [None, 2.0], "BBB": [3.0, 4.0]}, index=pd.to_datetime(["2026-01-01", "2026-01-02"])),
    ],
)
def test_no_shrinkage_rejects_removed_session_or_cell(tmp_path, after):
    before = pd.DataFrame(
        {"AAA": [1.0, 2.0], "BBB": [3.0, 4.0]},
        index=pd.to_datetime(["2026-01-01", "2026-01-02"]),
    )
    old_path, new_path = tmp_path / "before.parquet", tmp_path / "after.parquet"
    _write(old_path, before)
    _write(new_path, after)

    with pytest.raises(RuntimeError, match='"status": "FAIL"'):
        audit_no_shrinkage(old_path, new_path)
