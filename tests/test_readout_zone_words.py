"""The flows readout keeps one line per series on a phone in any fallback font (S222).

"+₹1.34 lakh Cr foreign · a heavy-buying month" filled the whole 360 px readout in DejaVu Sans (an
Ubuntu runner's fallback; Inter on the dev container): it wrapped on CI only and kept main's
validation red from #666 (layout audit: readout 91 of 347 px). Measured 24 Nov 2026 at 412 px, the
longest new line is 323 px in DejaVu Sans, 293 in Inter, 269 in FreeSans.
"""
import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "ui" / "views" / "dashboard_home_view.py"
LIMIT = 15   # "moderate buying"; "a heavy-buying month" (20) is what wrapped


def _zone_words() -> dict[str, str]:
    for node in ast.walk(ast.parse(SRC.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Dict):
            keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
            if {"above", "between", "belowZero"} <= set(keys):
                return {k.value: v.value for k, v in zip(node.keys, node.values, strict=False)
                        if isinstance(k, ast.Constant) and k.value in ("above", "between", "belowZero")}
    raise AssertionError("the flows bar spec has no zone words")


def test_the_zone_words_are_short_enough_for_one_line_at_412px():
    words = _zone_words()
    assert words == {"above": "heavy buying", "between": "moderate buying", "belowZero": "net selling"}
    assert all(len(w) <= LIMIT for w in words.values())


def test_both_readout_holders_measure_again_once_the_web_fonts_load():
    """A first fit in the fallback font must not hold its height after IBM Plex arrives (S222)."""
    js = (SRC.parents[3] / "static" / "dash_charts.js").read_text(encoding="utf-8")
    assert js.count("addEventListener('loadingdone'") == 2      # interact() and rowsInteract()
