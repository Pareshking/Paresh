"""No source line under a chart (owner, 20 Nov 2026: "Let's not show source"; 22 Nov: the footer may name NSE).
S237 G4 added one under every chart on 28 Nov against that rule; the owner chose "Revert to my rule" the same day."""
import ast
from pathlib import Path

from src.ui.views.dashboard_home_view import how

VIEWS = Path(__file__).resolve().parents[1] / "src" / "ui" / "views"


def test_the_footer_prints_no_source():
    html = how("What.", "Read.", ["A"], [["1"]])
    assert "Source:" not in html and "dh-src" not in html


def test_no_view_passes_or_prints_a_source_line():
    found = []
    for f in VIEWS.glob("*.py"):
        text = f.read_text(encoding="utf-8")
        for n in ast.walk(ast.parse(text)):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "how":
                if any(k.arg == "source" for k in n.keywords):
                    found.append(f"{f.name}:{n.lineno}")
        if "Source: " in text or "dh-src" in text:
            found.append(f"{f.name}: a literal source line")
    assert not found, found
