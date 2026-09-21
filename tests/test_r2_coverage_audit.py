from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.r2_coverage_audit import audit_no_shrinkage


def _write(path: Path, dates: list[str], values: list[list[float]]) -> None:
    columns = pd.MultiIndex.from_product([["AAA", "BBB"], ["Close"]])
    pd.DataFrame(values, index=pd.to_datetime(dates), columns=columns).to_parquet(path)


def test_rejects_missing_interior_session(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.parquet"
    candidate = tmp_path / "candidate.parquet"
    _write(baseline, ["2026-09-17", "2026-09-18", "2026-09-21"], [[10, 20], [11, 21], [12, 22]])
    _write(candidate, ["2026-09-17", "2026-09-21"], [[10, 20], [12, 22]])
    with pytest.raises(RuntimeError, match="historical sessions disappeared"):
        audit_no_shrinkage(baseline, candidate)


def test_accepts_appended_history(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.parquet"
    candidate = tmp_path / "candidate.parquet"
    _write(baseline, ["2026-09-18", "2026-09-21"], [[10, 20], [11, 21]])
    _write(candidate, ["2026-09-17", "2026-09-18", "2026-09-21", "2026-09-22"], [[9, 19], [10, 20], [11, 21], [12, 22]])
    result = audit_no_shrinkage(baseline, candidate)
    assert result["status"] == "PASS"
    assert result["missing_sessions"] == 0
