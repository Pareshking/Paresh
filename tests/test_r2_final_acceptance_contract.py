"""Contract tests for the R2 final acceptance workflow structure.

Verifies that the workflow preserves its required step ordering and
mandatory arguments without needing real R2 credentials.
"""
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]


def _spec() -> dict:
    return yaml.safe_load(
        (ROOT / ".github/workflows/r2_final_acceptance.yml").read_text(encoding="utf-8")
    )


def _steps() -> list[dict]:
    spec = _spec()
    return spec["jobs"]["final"]["steps"]


def test_final_acceptance_step_ordering():
    steps = _steps()
    names = [str(step.get("name", "")) for step in steps]

    regression = names.index("R2 regression")
    pit = names.index("Live PIT membership acceptance")
    research = names.index("Live immutable research acceptance")
    recovery = names.index("Live recovery audit")
    cost = names.index("Live cost observability")

    assert regression < pit < research < recovery < cost


def test_final_acceptance_pit_membership_script():
    steps = _steps()
    step = next(s for s in steps if s.get("name") == "Live PIT membership acceptance")
    run = str(step["run"])
    assert "scripts/r2_membership_live_validation.py" in run
    assert "--as-of" in run


def test_final_acceptance_research_pin_arguments():
    steps = _steps()
    step = next(s for s in steps if s.get("name") == "Live immutable research acceptance")
    run = str(step["run"])
    assert "scripts/r2_research_live_validation.py" in run
    assert "--dataset" in run
    assert "--as-of" in run
    assert "--revision" in run


def test_final_acceptance_recovery_audit_script():
    steps = _steps()
    step = next(s for s in steps if s.get("name") == "Live recovery audit")
    run = str(step["run"])
    assert "scripts/r2_recovery_audit.py" in run


def test_final_acceptance_cost_audit_script():
    steps = _steps()
    step = next(s for s in steps if s.get("name") == "Live cost observability")
    run = str(step["run"])
    assert "scripts/r2_cost_audit.py" in run


def test_final_acceptance_is_read_only():
    spec = _spec()
    assert spec["permissions"]["contents"] == "read"


def test_final_acceptance_has_r2_credentials_in_env():
    steps = _steps()
    env_keys = set()
    job_env = _spec()["jobs"]["final"].get("env", {})
    env_keys.update(job_env.keys())
    for step in steps:
        env_keys.update((step.get("env") or {}).keys())
    for cred in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT", "R2_BUCKET"):
        assert cred in env_keys, f"R2 credential {cred!r} missing from final acceptance workflow"


def test_final_acceptance_regression_covers_r2_tests():
    steps = _steps()
    step = next(s for s in steps if s.get("name") == "R2 regression")
    run = str(step["run"])
    assert "tests/test_r2_" in run or "test_r2_*.py" in run
