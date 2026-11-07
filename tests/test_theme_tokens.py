"""The theme lives in src/ui/tokens.py (owner, 7 Nov 2026: change it in one place)."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from src.ui.tokens import PALETTE, C, css_root, resolve

ROOT = Path(__file__).resolve().parents[1]
UI = [p for p in (ROOT / "src" / "ui").rglob("*.py") if p.name != "tokens.py"] + [ROOT / "app.py"]


def test_every_colour_name_the_ui_uses_is_in_the_palette():
    names = set()
    for p in UI:
        names |= set(re.findall(r"var\(--c-([a-z0-9_]+)\)", p.read_text(encoding="utf-8")))
    # --c-bg, --c-text-primary and the like are aliases defined in theme.py's own :root.
    unknown = {n for n in names - set(PALETTE) if "-" not in n}
    assert not unknown, unknown
    for p in UI:
        for n in re.findall(r"\bC\.([a-z0-9_]+)\b", p.read_text(encoding="utf-8")):
            assert n in PALETTE, (p.name, n)


def test_no_theme_variable_is_defined_as_itself():
    # theme.py once had "--c-caution: var(--c-caution);" after the move to tokens:
    # a self-reference is invalid CSS, so every caution colour on the site was
    # transparent (the dashboard's Watch bar showed it, 7 Nov).
    for p in UI:
        src = p.read_text(encoding="utf-8")
        assert not re.search(r"--c-([a-z0-9_-]+):\s*var\(--c-\1\)", src), p.name


def test_no_palette_colour_is_written_out_by_hand_in_the_ui():
    by_hex = {v.upper() for v in PALETTE.values()}
    for p in UI:
        found = {h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}\b", p.read_text(encoding="utf-8"))}
        assert not (found & by_hex), (p.name, sorted(found & by_hex))


def test_resolve_writes_colours_in_and_refuses_an_unknown_name():
    assert resolve("a{color:var(--c-up)} b{x:var(--font-mono)}") == f"a{{color:{C.up}}} b{{x:var(--font-mono)}}"
    with pytest.raises(KeyError):
        resolve("var(--c-not_a_colour)")
    assert css_root().startswith(":root {") and f"--c-ink: {C.ink};" in css_root()


def test_streamlit_config_repeats_the_tokens_exactly():
    theme = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))["theme"]
    assert theme["primaryColor"] == C.ink
    assert theme["textColor"] == C.ink
    assert theme["backgroundColor"] == C.ground
    assert theme["secondaryBackgroundColor"] == C.subtle
    assert theme["borderColor"] == C.rule_strong
    assert theme["greenColor"] == C.up and theme["redColor"] == C.down
    assert theme["orangeColor"] == C.caution


@pytest.mark.parametrize("module", ["screener_table", "lw_chart", "charts"])
def test_framed_documents_are_sent_resolved(module):
    src = (ROOT / "src" / "ui" / f"{module}.py").read_text(encoding="utf-8")
    calls = re.findall(r"st\.iframe\((.*)", src)
    assert calls and all(c.startswith("resolve(") for c in calls), calls
