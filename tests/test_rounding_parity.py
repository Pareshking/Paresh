"""Glossary 12 (owner, 23 Nov 2026): every displayed figure rounds half away from zero on its decimal value,
and Python and the charts' JavaScript agree. SONACOMS at ₹892.50 read ₹892 in a table (Python's round(),
half to even) and ₹893 in a chart; JavaScript's Math.round(-24.5) is -24, and 2.45 is not exact in binary.

The same values go through formats.py and through the JavaScript formatters in static/dash_charts.js,
and lw_chart.py (run in node), and must read the same. Display only: nothing here rounds data.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from src.ui import formats

ROOT = Path(__file__).resolve().parents[1]
VALUES = [892.5, -2.45, 0.05, -0.05, 1234.5, 2.45, -24.5, 1.005, 0.25, -0.04, 0.0, 70.49, 1250000.5]

node = shutil.which("node")


def test_python_half_away_from_zero():
    assert formats.price(892.5) == "₹893"
    assert formats.price(1234.5) == "₹1,235"
    assert formats.pct(-2.45, fraction=False) == "−2.5%"
    assert formats.pct(0.05, fraction=False) == "+0.1%"
    assert formats.pct(-0.05, fraction=False) == "−0.1%"
    assert formats.pct(-0.0245) == "−2.5%"          # 0.0245 * 100 is 2.4499999999999997 in binary
    assert formats.pts(-24.5, digits=0, fraction=False) == "−25 pts"
    assert formats.signed(-0.04, 1) == "0.0"         # rounded before it is signed: never "−0.0"
    assert formats.fixed(1.005, 2) == "1.01"


def _python_row(v: float) -> list[str]:
    return [formats.price(v), formats.signed(v, 1), formats.signed(v, 0), formats.fixed(v, 1), formats.fixed(v, 2),
            formats.pct(v, fraction=False)]


def _kit_source() -> str:
    """The formatter lines of static/dash_charts.js, from rnd to sg, runnable on their own."""
    s = (ROOT / "static" / "dash_charts.js").read_text(encoding="utf-8")
    start, end = s.index("const rnd = "), s.index("const sg = ")
    return s[start:s.index("\n", end)]


def _lw_source() -> str:
    """The fmts table of lw_chart.py's script."""
    s = (ROOT / "src" / "ui" / "lw_chart.py").read_text(encoding="utf-8")
    start = s.index("const rnd=")
    return s[start:s.index("};\n", s.index("const fmts=")) + 2]


@pytest.mark.skipif(node is None, reason="node is not installed")
def test_javascript_matches_python():
    script = (
        _kit_source() + "\n"
        + "const lw = (function(){" + _lw_source() + "\nreturn fmts;})();\n"
        + f"const V = {json.dumps(VALUES)};\n"
        + "console.log(JSON.stringify(V.map(v => ({kit: ['₹' + pxf(v), sg(v, 1), sg(v, 0), fx(v, 1), fx(v, 2), sg(v, 1) + '%'],"
        + " lw: [lw.price(v), lw.pct(v), lw.num(v)]}))));\n"
    )
    out = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)
    for v, js in zip(VALUES, out):
        py = _python_row(v)
        # pxf has no sign of its own (prices are positive); compare the magnitude for a negative value.
        kit = [("−₹" + js["kit"][0][2:]) if js["kit"][0].startswith("₹−") else js["kit"][0]] + js["kit"][1:]
        assert kit == py, (v, kit, py)
        assert js["lw"] == [formats.price(v), formats.pct(v, fraction=False), formats.fixed(v, 2)], (v, js["lw"])
