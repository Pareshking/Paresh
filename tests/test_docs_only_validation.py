"""S199: a Markdown-only PR runs the Markdown-reading tests, not the full validation.

Owner, 22-23 Nov 2026: docs-only PRs must not skip every check, because tests read
the docs; they run those tests (seconds) instead of the ~14-min suite and app checks.
A page requirements doc is read row by row against the running app, so a PR touching
one keeps the full run.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows" / "v1-full-validation.yml"
GATE = "steps.scope.outputs.light != 'true'"


def _steps():
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(WF.read_text(encoding="utf-8"))["jobs"]["validate"]["steps"]


def _docs_step(steps):
    return next(s for s in steps if s.get("name", "").startswith("Markdown-reading tests"))


def test_every_heavy_step_is_skipped_on_a_markdown_only_pr():
    steps = _steps()
    names = [s.get("name") or s.get("uses") or s.get("run") for s in steps]
    first = names.index(_docs_step(steps)["name"])
    for step in steps[first + 1:]:
        assert GATE in str(step.get("if", "")), step.get("name") or step.get("uses")


def test_the_scope_keeps_requirements_docs_and_code_on_the_full_run():
    scope = next(s for s in _steps() if s.get("id") == "scope")["run"]
    assert "pull_request" in scope            # pushes, schedules, dispatches run everything
    assert r"'\.md$'" in scope                # any non-Markdown file -> full run
    assert r"_REQUIREMENTS\.md$" in scope     # a page requirements doc -> full run


def test_every_test_that_reads_markdown_runs_on_a_markdown_only_pr():
    listed = set(re.findall(r"tests/\S+\.py", _docs_step(_steps())["run"]))
    readers = set()
    pattern = re.compile(r'/ "docs" /|"\.md"\}|suffix in \{[^}]*"\.md"')
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        if path.name != Path(__file__).name and pattern.search(path.read_text(encoding="utf-8")):
            readers.add(f"tests/{path.name}")
    assert readers <= listed, f"add to the Markdown-only step: {sorted(readers - listed)}"
    for name in listed:
        assert (ROOT / name).exists(), name
