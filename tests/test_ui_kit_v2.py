"""The UI kit v2 helpers render, and the pickers that moved to segmented
controls keep their keys, defaults and a value that can never be None."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.ui import page_kit as kit

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "src" / "ui" / "views"


def test_pct_formats_fractions_and_dashes_non_finite():
    assert kit.pct(0.123) == "+12.3%"
    assert kit.pct(-0.05) == "-5.0%"
    assert kit.pct(-0.05, signed=False) == "-5.0%"
    assert kit.pct(0.05, signed=False) == "5.0%"
    for bad in (None, float("nan"), float("inf"), "x"):
        assert kit.pct(bad) == "—"


def _kit_app():
    import pandas as pd
    import streamlit as st

    from src.ui import page_kit as k

    k.metric_row([k.Metric("Strategy", k.pct(0.1), delta="+2.0% vs Nifty", tone="normal"),
                  k.Metric("Alpha", k.pct(float("nan")))], key="t")
    k.callout("Holdout check", "<b>escaped</b>", "warn")
    k.badge("LIVE", "up")
    k.df_card("Table", "t", pd.DataFrame({"a": [0.1, 0.2], "r": [1, 2]}),
              column_config={"a": k.col_pct("A"), "r": k.col_rank("R")})
    with k.toolbar("t"):
        st.write("in the bar")


def test_kit_helpers_render_without_error():
    at = AppTest.from_function(_kit_app).run()
    assert not at.exception, [e.value for e in at.exception]
    assert [m.label for m in at.metric] == ["Strategy", "Alpha"]
    assert [m.value for m in at.metric] == ["+10.0%", "—"]
    assert len(at.dataframe) == 1


def test_callout_escapes_its_text():
    import streamlit as st  # noqa: F401

    def app():
        from src.ui import page_kit as k
        k.callout("<i>t</i>", "<script>x</script>", "bogus")

    at = AppTest.from_function(app).run()
    assert not at.exception
    html = at.get("html")[0].value
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert 'class="pg-callout muted"' in html


# key -> (view file, default). Each must be a segmented_control with
# required=True, an explicit default and an `or` fallback on the read.
MIGRATED = {
    "br_lb_days": "breadth_view.py",
    "hl_win_sel": "breadth_view.py",
    "rrg_tf_choice": "rrg_view.py",
    "qual_top_n": "qualified_view.py",
    "sector_rank_by": "sector_view.py",
}


@pytest.mark.parametrize("key", MIGRATED)
def test_migrated_pickers_are_required_segmented_controls_with_a_default(key):
    tree = ast.parse((VIEWS / MIGRATED[key]).read_text(encoding="utf-8"))
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and any(k.arg == "key" and isinstance(k.value, ast.Constant) and k.value.value == key
                for k in n.keywords)
    ]
    assert len(calls) == 1, f"{key} should be drawn exactly once"
    call = calls[0]
    kw = {k.arg: k.value for k in call.keywords}
    assert call.func.attr == "segmented_control"
    assert isinstance(kw.get("required"), ast.Constant) and kw["required"].value is True
    assert "default" in kw


def test_dialog_openers_are_buttons_and_the_dialogs_are_module_level():
    tree = ast.parse((VIEWS / "config_view.py").read_text(encoding="utf-8"))
    top = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)
           and any("dialog" in ast.unparse(d) for d in n.decorator_list)}
    assert top == {"_index_files_dialog", "_spike_sessions_dialog"}


def test_every_page_kit_helper_the_views_call_exists():
    """The Backtest and Track Record pages called kit.growth_chart for a day
    after a commit renamed it; both raised AttributeError on every load and no
    test noticed, because none of them renders those pages' charts."""
    used: set[tuple[str, str]] = set()
    for path in [*VIEWS.glob("*.py"), *(ROOT / "src" / "ui").glob("*.py"), ROOT / "app.py"]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases = {
            a.asname or a.name.rsplit(".", 1)[-1]
            for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == "src.ui"
            for a in n.names if a.name == "page_kit"
        }
        for n in ast.walk(tree):
            if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                    and n.value.id in aliases):
                used.add((path.name, n.attr))
    assert used, "the guard lost its target"
    missing = sorted(f"{f}: kit.{a}" for f, a in used if not hasattr(kit, a))
    assert not missing, missing


def test_growth_chart_rebases_growth_factors_to_100():
    def app():
        from src.ui import page_kit as k
        k.growth_chart(["a", "b", "c"], [1.0, 1.1, 1.2], [1.0, 1.0, 1.05], key="t")

    at = AppTest.from_function(app).run()
    assert not at.exception, [e.value for e in at.exception]
    legend = at.get("html")[0].value
    assert "₹120" in legend and "₹105" in legend
