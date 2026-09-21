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
    assert "marker_price = hi * 0.80" in src
    assert '"_52W Low"' in src
    assert '"_52W High"' in src
    assert '"_52W Position"' in src
    assert '"_52W 20% Marker"' in src
    assert "52W Low ₹" in src
    assert "CMP ₹" in src
    assert "52W High ₹" in src
    assert "canonical_hi = row.get(\"52W High\")" in src


def test_cards_receive_range_data_without_changing_table_path():
    src = _source()
    assert "_render_card_grid(_attach_52w_range(view, high_prices, low_prices, adj_close))" in src
    assert "render_master_screener_table(" in src
