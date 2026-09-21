from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]


def _workflow() -> dict:
    return yaml.safe_load(
        (ROOT / ".github/workflows/r2_screener_production_verification.yml").read_text(
            encoding="utf-8"
        )
    )


def test_production_screener_verification_contract():
    spec = _workflow()
    steps = spec["jobs"]["verify"]["steps"]
    names = [str(step.get("name", "")) for step in steps]

    download = names.index("Download production Screener release asset")
    identity = names.index("Verify release artifact identity")
    first_audit = names.index("Live R2 manifest/current/object/HEAD/SHA verification")
    retry = names.index("Actual identical retry against the immutable publication")
    second_audit = names.index("Post-retry live R2 verification")

    assert download < identity < first_audit < retry < second_audit

    retry_step = steps[retry]
    run = str(retry_step["run"])
    assert "scripts/r2_publish.py" in run
    assert "--dataset prices/screener" in run
    assert "--source screener" in run
    assert "--key-root archive/prices/screener" in run

    audit_runs = [str(steps[i]["run"]) for i in (first_audit, second_audit)]
    for audit_run in audit_runs:
        assert "scripts/r2_audit.py" in audit_run
        assert "--dataset prices/screener" in audit_run
        assert '--as-of "$EXPECTED_AS_OF"' in audit_run


def test_production_verification_is_read_only_at_github_level():
    spec = _workflow()
    assert spec["permissions"]["contents"] == "read"
    assert "data-latest" in str(spec)
    assert "screener_prices.parquet" in str(spec)
