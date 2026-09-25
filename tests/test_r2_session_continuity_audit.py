
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


_D2 = {"date": "2026-01-02", "market": "NSE", "is_session": True}
_D5 = {"date": "2026-01-05", "market": "NSE", "is_session": True}


# Each case must fail for its own reason: a bare RuntimeError would also be
# satisfied by an earlier check tripping on a malformed fixture.
@pytest.mark.parametrize(
    ("rows", "reason"),
    [
        ([_D5, _D2], "not monotonic"),
        ([_D2, _D2], "duplicated"),
        ([_D2 | {"market": "BSE"}], "non-NSE"),
        ([_D2 | {"is_session": False}], "non-session"),
        ([{"date": "2026-01-02", "market": "NSE"}], "missing required columns"),
    ],
)
def test_invalid_session_contracts(tmp_path, rows, reason):
    with pytest.raises(RuntimeError, match=reason):
        audit_sessions(_write(tmp_path, rows))
