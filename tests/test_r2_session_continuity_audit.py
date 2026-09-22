from pathlib import Path

import pandas as pd
import pytest

from scripts.r2_session_continuity_audit import audit_sessions


def _write(tmp_path, rows):
    path = tmp_path / "sessions.parquet"
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


def test_valid_sessions(tmp_path):
    path = _write(
        tmp_path,
        [
            {"date": "2026-01-02", "market": "NSE", "is_session": True},
            {"date": "2026-01-05", "market": "NSE", "is_session": True},
        ],
    )
    result = audit_sessions(path)
    assert result["status"] == "PASS"
    assert result["rows"] == 2


@pytest.mark.parametrize(
    "rows",
    [
        [
            {"date": "2026-01-05", "market": "NSE", "is_session": True},
            {"date": "2026-01-02", "market": "NSE", "is_session": True},
        ],
        [
            {"date": "2026-01-02", "market": "BSE", "is_session": True},
        ],
        [
            {"date": "2026-01-02", "market": "NSE", "is_session": False},
        ],
    ],
)
def test_invalid_session_contracts(tmp_path, rows):
    with pytest.raises(RuntimeError):
        audit_sessions(_write(tmp_path, rows))
