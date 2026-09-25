"""Every `python scripts/X.py ...` call in a workflow must match X's argparse CLI.

The R2 session continuity audit went red on 2026-09-24 because its workflow
still passed positional paths after build_trading_sessions.py had moved to
required --prices/--output flags. Unit tests of the script passed; only the
scheduled run noticed. This test catches that drift at PR time.
"""

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
CALL = re.compile(r"python3? (scripts/\w+\.py)([^\n;&|]*)")


def _cli(script: Path) -> tuple[set[str], bool] | None:
    source = script.read_text(encoding="utf-8")
    if "argparse" not in source:
        return None
    flags = set(re.findall(r'add_argument\(\s*"(--[\w-]+)"', source))
    takes_positional = bool(re.search(r'add_argument\(\s*"[A-Za-z_]', source))
    return flags, takes_positional


def _calls():
    for workflow in WORKFLOWS:
        data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        for job in (data.get("jobs") or {}).values():
            for step in job.get("steps") or []:
                run = step.get("run") or ""
                run = re.sub(r"\\\n\s*", " ", run)
                run = re.sub(r"\$\{\{.*?\}\}", "EXPR", run)
                run = re.sub(r'"\$\(.*?\)"', "EXPR", run, flags=re.S)
                for match in CALL.finditer(run):
                    yield workflow.name, match.group(1), match.group(2)


@pytest.mark.parametrize("workflow,script,args", list(_calls()))
def test_workflow_script_arguments_match_argparse(workflow, script, args):
    path = ROOT / script
    assert path.is_file(), f"{workflow} calls missing {script}"
    cli = _cli(path)
    if cli is None:
        return
    flags, takes_positional = cli
    tokens = [t.strip("'\"") for t in args.split()]
    used = {t.split("=", 1)[0] for t in tokens if t.startswith("--")}
    unknown = used - flags - {"--help"}
    assert not unknown, f"{workflow}: {script} has no option(s) {sorted(unknown)}"
    if not takes_positional:
        # A bare token is only legal as the value of the flag before it.
        for prev, token in zip([""] + tokens, tokens):
            if not token.startswith("--"):
                assert prev.startswith("--") and "=" not in prev, (
                    f"{workflow}: {script} takes no positional argument, got {token!r}"
                )
