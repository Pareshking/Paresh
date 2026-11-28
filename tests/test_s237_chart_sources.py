"""S237 G4 (28 Nov 2026): every chart's footer names where its figures come from, as tipsheet's do."""
import ast
from pathlib import Path

from src.ui.views.dashboard_home_view import how

VIEWS = Path(__file__).resolve().parents[1] / "src" / "ui" / "views"


def test_the_footer_prints_its_source():
    html = how("What.", "Read.", ["A"], [["1"]], source="NSE Indices' daily closes")
    assert '<p class="dh-src">Source: NSE Indices&#x27; daily closes.</p>' in html or "Source: NSE Indices" in html


def test_every_chart_footer_names_a_source():
    # The Indices earnings chart names no source (owner, 25 Nov 2026: "no source, no schedule").
    missing = []
    for f in VIEWS.glob("*.py"):
        for n in ast.walk(ast.parse(f.read_text())):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "how":
                if not any(k.arg == "source" and not (isinstance(k.value, ast.Constant) and not k.value.value) for k in n.keywords):
                    missing.append(f"{f.name}:{n.lineno}")
    src = (VIEWS / "indices_view.py").read_text()
    earnings = [m for m in missing if m.startswith("indices_view.py:")
                and "companies added together" in src.split("\n")[int(m.split(":")[1]) - 1]]
    missing = [m for m in missing if m not in earnings]
    assert len(earnings) == 1, earnings
    assert not missing, missing
