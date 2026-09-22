"""Hard guard: R2 infrastructure must remain independent from V1/Stage-4B research."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


FORBIDDEN_IMPORT_PREFIXES = (
    "agent",
    "src.engine",
    "src.ui",
    "streamlit",
    "loaders.ranking_store",
    "loaders.price_loader",
)


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def test_r2_storage_does_not_import_stock_research_runtime():
    storage = ROOT / "src" / "storage"
    violations = []
    for path in sorted(storage.glob("*.py")):
        for module in _imports(path):
            if module == "src.storage" or module.startswith("src.storage."):
                continue
            if any(
                module == prefix or module.startswith(prefix + ".")
                for prefix in FORBIDDEN_IMPORT_PREFIXES
            ):
                violations.append(f"{path.relative_to(ROOT)} -> {module}")
    assert not violations, (
        "R2 storage must not depend on V1/Stage-4B/application runtime: "
        + ", ".join(violations)
    )


def test_r2_focused_workflows_do_not_execute_stage4b():
    workflow_dir = ROOT / ".github" / "workflows"
    violations = []
    for path in sorted(workflow_dir.glob("r2*.yml")):
        text = path.read_text(encoding="utf-8").lower()
        for marker in ("stage4b_", "stage-4b", "sansera", "anandrathi", "paytm", "yatharth", "lenskart"):
            if marker in text:
                violations.append(f"{path.relative_to(ROOT)} contains {marker!r}")
    assert not violations, (
        "R2 workflows must not execute research workloads: "
        + ", ".join(violations)
    )


def test_v1_workflows_explicitly_isolate_r2_only_paths():
    v1 = (workflow_dir := ROOT / ".github" / "workflows" / "v1-full-validation.yml").read_text(
        encoding="utf-8"
    )
    required = ("paths-ignore:", "src/storage/**", "scripts/r2_*.py", "tests/test_r2_*.py")
    missing = [marker for marker in required if marker not in v1]
    assert not missing, f"V1 Full Validation R2 isolation is incomplete: {missing}"
