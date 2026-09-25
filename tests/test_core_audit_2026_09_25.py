"""Regressions from the 2026-09-25 line-by-line audit of app.py and src/core."""

from src.core import config
from src.core.universe_reconciliation import reconcile_symbols


def test_reconciliation_drops_the_same_placeholders_the_universe_loader_does():
    out = reconcile_symbols(["ABB", "DUMMYX", "nan"], ["ABB", "NAN", "X"])
    assert out["missing"] == []
    assert out["extra"] == []  # "X" is one character: not a ticker either
    assert out["expected_count"] == out["published_count"] == 1


def test_risk_defaults_come_from_config():
    from src.ui.views import config_view

    risk = config_view._RISK_SETTINGS
    assert risk["cfg_sc"][0] == round(config.DEFAULT_SECTOR_CAP * 100)
    assert risk["cfg_stc"][0] == round(config.DEFAULT_STOCK_CAP * 100)
    assert risk["cfg_vtv"][0] == round(config.DEFAULT_TARGET_VOL * 100)


def test_engine_memo_is_keyed_on_the_applied_corporate_actions():
    """Adjustments rewrite history before their date, so price_hash cannot see them."""
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path("app.py").read_text(encoding="utf-8"))
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_run_engine_base"
    )
    hashed = [a.arg for a in fn.args.args if not a.arg.startswith("_")]
    assert "actions_key" in hashed
