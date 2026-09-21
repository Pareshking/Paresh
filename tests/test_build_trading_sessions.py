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
