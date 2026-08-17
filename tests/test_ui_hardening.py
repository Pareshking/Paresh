from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_strategy_overlay_has_no_r2_dependency():
    text = (ROOT / "src/ui/views/strategy_view.py").read_text()
    assert "r2_" not in text
    assert "R2" not in text
    assert "R²" not in text


def test_theme_uses_current_streamlit_iframe_api():
    text = (ROOT / "src/ui/theme.py").read_text()
    assert "streamlit.components.v1" not in text
    assert "components.html" not in text
    assert "st.iframe(" in text
