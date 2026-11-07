#!/usr/bin/env python3
"""Rebuild static/fonts.css and static/fonts/*.woff2 from Google Fonts (audit F61).

    python scripts/build_fonts.py

The site serves its three faces itself (IBM Plex Sans 400-700, IBM Plex Mono
400-600, Source Serif 4 400-500; SIL Open Font Licence, static/fonts/OFL.txt)
instead of asking Google from every page and every chart frame. Only the Latin
and Latin Extended files are kept: Latin Extended carries the rupee sign, and
the CSS's unicode-range makes the browser fetch a file only for characters on
the page. Run again only to change a face or weight.
"""
from __future__ import annotations

import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS_URL = ("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700"
           "&family=IBM+Plex+Mono:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500"
           "&display=swap")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
KEEP = ("latin", "latin-ext")


def main() -> None:
    req = urllib.request.Request(CSS_URL, headers={"User-Agent": UA})
    css = urllib.request.urlopen(req, timeout=30).read().decode()
    out_dir = ROOT / "static" / "fonts"
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = ["/* Self-hosted fonts (audit F61, owner 7 Nov 2026): IBM Plex Sans, IBM Plex Mono and",
             "   Source Serif 4, SIL Open Font Licence 1.1 (static/fonts/OFL.txt). Latin and",
             "   Latin Extended only (Latin Extended carries the rupee sign); the browser loads a",
             "   file only for characters on the page. Built from Google Fonts' CSS by",
             "   scripts/build_fonts.py; URLs are relative to this file. */"]
    names: dict[str, str] = {}
    for subset, block in re.findall(r"/\* ([a-z-]+) \*/\s*(@font-face \{.*?\})", css, re.S):
        if subset not in KEEP:
            continue
        family = re.search(r"font-family: '([^']+)'", block).group(1)
        weight = re.search(r"font-weight: ([0-9 ]+);", block).group(1).replace(" ", "-")
        url = re.search(r"url\((https://[^)]+)\)", block).group(1)
        if url not in names:
            name = f"{family.lower().replace(' ', '-')}-{weight}-{subset}.woff2"
            (out_dir / name).write_bytes(urllib.request.urlopen(url, timeout=30).read())
            names[url] = name
        lines.append(f"/* {subset} */\n" + block.replace(url, "fonts/" + names[url]))
    (ROOT / "static" / "fonts.css").write_text("\n".join(lines) + "\n")
    print(f"{len(names)} font files -> {out_dir}")


if __name__ == "__main__":
    main()
