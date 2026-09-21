from pathlib import Path

import pandas as pd

from scripts.build_trading_sessions import build


def test_build_trading_sessions_is_deterministic(tmp_path: Path):
    src = tmp_path / "prices.parquet"
    out = tmp_path / "sessions.json"
    frame = pd.DataFrame(
        {"AAA": [1, 2, 3]},
        index=pd.to_datetime(["2026-09-18", "2026-09-21", "2026-09-21"]),
    )
    frame.to_parquet(src)
    result = build(src, out)
    assert result["session_count"] == 2
    assert result["first_session"] == "2026-09-18"
    assert result["last_session"] == "2026-09-21"
    assert result["sessions"] == ["2026-09-18", "2026-09-21"]

def test_build_trading_sessions_can_emit_normalized_parquet(tmp_path: Path):
    src = tmp_path / "prices.parquet"
    out = tmp_path / "sessions.parquet"
    frame = pd.DataFrame(
        {"AAA": [1, 2, 3]},
        index=pd.to_datetime(["2026-09-18", "2026-09-21", "2026-09-21"]),
    )
    frame.to_parquet(src)

    result = build(src, out)
    observed = pd.read_parquet(out)

    assert result["session_count"] == len(observed) == 2
    assert list(observed.columns) == [
        "date", "market", "is_session", "source", "evidence_date"
    ]
    assert observed["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-09-18", "2026-09-21"
    ]
    assert observed["market"].eq("NSE").all()
    assert observed["is_session"].all()
    assert observed["evidence_date"].eq("2026-09-21").all()
