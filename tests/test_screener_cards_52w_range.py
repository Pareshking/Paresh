from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RANKING_VIEW = ROOT / "src" / "ui" / "views" / "ranking_view.py"


def _source() -> str:
    return RANKING_VIEW.read_text(encoding="utf-8")


def test_card_indices_use_exact_canonical_short_forms():
    src = _source()
    assert '"N50": "sq-chip-n50"' in src
    assert '"NN50": "sq-chip-nn50"' in src
    assert '"MID150": "sq-chip-mid"' in src
    assert '"SMALL250": "sq-chip-sm"' in src
    assert '"MICRO250": "sq-chip-micro"' in src
    assert 'if "50" in s and "500" not in s' not in src


def test_card_range_uses_252_sessions_and_20_percent_below_high_marker():
    src = _source()
    assert ".sort_index().tail(252)" in src
    assert "marker = 80.0" in src
    assert '"_52W Low"' in src
    assert '"_52W High"' in src
    assert '"_52W Position"' in src
    assert '"_52W 20% Marker"' in src
    assert "52W Low ₹" in src
    assert "CMP ₹" in src
    assert "52W High ₹" in src
    assert "canonical_hi = row.get(\"52W High\")" in src


def test_cards_receive_range_data_without_changing_table_path(monkeypatch):
    """Behaviour, not source text: the drawn cards carry the 52W range."""
    import numpy as np
    import pandas as pd

    from src.ui.views import ranking_view

    syms = ["AAA", "BBB"]
    px = pd.DataFrame(
        np.linspace(100, 200, 300)[:, None].repeat(2, axis=1),
        index=pd.bdate_range(end="2026-09-24", periods=300), columns=syms,
    )
    view = pd.DataFrame({"Symbol": syms, "Rank": [1, 2], "52W High": [200.0, 200.0],
                         "CMP": [190.0, 150.0]})
    drawn = []
    monkeypatch.setattr(ranking_view.st, "markdown", lambda h, **k: drawn.append(h))
    monkeypatch.setattr(ranking_view.st, "caption", lambda *a, **k: None)
    ranking_view._render_card_grid(view, None, None, px)
    assert "52W Low ₹" in drawn[0] and "52W High ₹200" in drawn[0]
    assert "render_master_screener_table(" in _source()
