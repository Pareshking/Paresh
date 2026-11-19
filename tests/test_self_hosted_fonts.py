"""Fonts are served by the app, not Google (audit F61)."""
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_font_file_in_the_stylesheet_exists_and_is_latin():
    css = (ROOT / "static" / "fonts.css").read_text()
    urls = re.findall(r"url\(([^)]+)\)", css)
    assert urls and all(u.startswith("fonts/") for u in urls)
    for u in set(urls):
        assert (ROOT / "static" / u).stat().st_size > 5_000, u
    for family in ("IBM Plex Sans", "IBM Plex Mono", "Source Serif 4"):
        assert f"font-family: '{family}'" in css
    assert "U+20AD-20C4" in css          # Latin Extended: the rupee sign, U+20B9
    assert (ROOT / "static" / "fonts" / "OFL.txt").exists()


def test_no_page_or_frame_asks_google_for_fonts():
    hits = []
    for path in list((ROOT / "src").rglob("*.py")) + [ROOT / "app.py", ROOT / ".streamlit" / "config.toml"]:
        text = path.read_text(encoding="utf-8")
        if "fonts.googleapis" in text or "fonts.gstatic" in text:
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []
    theme = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())["theme"]
    assert theme["font"] == "'IBM Plex Sans', sans-serif"


# ── Loading order (19 Nov 2026: the serif headline flashed on a phone) ──────

def _faces(css: str) -> set[tuple[str, str, str]]:
    out = set()
    for block in re.findall(r"@font-face \{(.*?)\}", css, re.S):
        family = re.search(r"font-family: '([^']+)'", block).group(1)
        url = re.search(r"url\(([^)]+)\)", block).group(1)
        rng = re.search(r"unicode-range: ([^;]+);", block).group(1)
        out.add((family, url, rng))
    return out


def test_config_declares_the_theme_faces_that_fonts_css_holds():
    # Streamlit writes these rules when the page opens, before the script runs.
    css = (ROOT / "static" / "fonts.css").read_text()
    theme = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())["theme"]
    declared = {(f["family"], f["url"].removeprefix("app/static/"), f["unicodeRange"])
                for f in theme["fontFaces"]}
    wanted = {f for f in _faces(css) if f[0] in ("IBM Plex Sans", "IBM Plex Mono")}
    assert wanted and declared == wanted
    for f in theme["fontFaces"]:
        assert (ROOT / "static" / f["url"].removeprefix("app/static/")).exists(), f["url"]
    sans = [f for f in theme["fontFaces"] if f["family"] == "IBM Plex Sans"]
    assert all(f["weight"] == "400 700" for f in sans)   # one variable file covers 400-700


def test_serif_rules_ride_in_the_first_style_element():
    from src.ui import theme as th
    from src.ui.tokens import FONTS, serif_face_css
    from streamlit.elements.html import _html_only_style_tags
    css = serif_face_css((ROOT / "static" / "fonts.css").read_text())
    urls = re.findall(r"url\(([^)]+)\)", css)
    assert urls and all(u.startswith("app/static/fonts/source-serif-4-") for u in urls)
    assert all((ROOT / "static" / u.removeprefix("app/static/")).exists() for u in urls)
    for name in ("SS4 fallback Noto", "SS4 fallback Times"):
        assert f"font-family: '{name}'" in css and f"'{name}'" in FONTS["serif"]
    assert FONTS["serif"].startswith("'Source Serif 4', 'SS4 fallback")
    # st.html with style tags only goes to the event container: no block, and
    # no wait for the Markdown renderer.
    assert _html_only_style_tags("<style>x</style>" + th._PAGE_CSS)
    src = (ROOT / "src" / "ui" / "theme.py").read_text() + (ROOT / "src" / "ui" / "page_kit.py").read_text()
    assert "@import url('\"\"\" + FONTS" not in src and "EDITORIAL_FONT" not in src


def test_fallback_overrides_keep_the_target_line_box():
    from src.ui.tokens import fallback_overrides
    o = fallback_overrides({"ascent": 1036, "descent": 335, "lineGap": 0, "upm": 1000}, 0.902)
    scale = float(o["size-adjust"].rstrip("%")) / 100
    assert scale == 0.902
    # After the browser scales the overrides by size-adjust, they are the target's metrics.
    assert abs(float(o["ascent-override"].rstrip("%")) / 100 * scale - 1.036) < 1e-4
    assert abs(float(o["descent-override"].rstrip("%")) / 100 * scale - 0.335) < 1e-4


def test_the_page_css_survives_streamlits_html_sanitiser():
    # st.html runs DOMPurify, which drops a whole <style> element whose text
    # holds anything tag-shaped ("<p>" in a comment did it on 19 Nov 2026:
    # 119 KB of rules vanished and the page rendered unstyled).
    from src.ui import theme as th
    from src.ui.tokens import css_root
    from src.ui.page_kit import _EDITORIAL_CSS
    for css in (th._PAGE_CSS, _EDITORIAL_CSS, css_root(), th._SERIF_FACES):
        inner = re.sub(r"</?style>", "", css)
        assert not re.search(r"<[/\w]", inner), re.search(r"<[/\w].{0,30}", inner).group(0)
