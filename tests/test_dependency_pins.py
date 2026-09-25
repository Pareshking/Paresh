"""Runtime dependencies are pinned to the exact versions CI tested.

A floor such as `pandas>=2.0.0` let Streamlit Cloud install whatever was newest
on the day a container booted, while the suite had only ever run against one
version. boto3 is the one deliberate range (see requirements.txt).
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RANGED_ON_PURPOSE = {"boto3"}


def _requirements() -> dict[str, str]:
    reqs = {}
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            name = re.split(r"[=<>!~ ]", line, maxsplit=1)[0].lower()
            reqs[name] = line
    return reqs


def test_every_runtime_dependency_is_pinned_exactly():
    loose = [
        spec for name, spec in _requirements().items()
        if name not in RANGED_ON_PURPOSE
        and not re.fullmatch(r"[A-Za-z0-9_.-]+==\d+(\.\d+)*", spec)
    ]
    assert not loose, f"pin these to an exact version: {loose}"


def test_the_r2_gate_skips_dependabot_prs_and_reruns_on_main():
    wf = yaml.safe_load(
        (ROOT / ".github/workflows/r2-streamlit-production-gate.yml").read_text()
    )
    # PyYAML reads the bare `on:` key as True.
    push_paths = wf[True]["push"]["paths"]
    assert "requirements.txt" in push_paths
    guard = wf["jobs"]["gate"]["if"]
    assert "dependabot[bot]" in guard and "pull_request" in guard
