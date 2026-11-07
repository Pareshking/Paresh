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
