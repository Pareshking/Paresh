"""Highcharts for st.iframe pages, loaded from the app's static folder.

Used where the chart is not a time series (the Relative Rotation Graph, the
correlation heatmap). Time series use TradingView Lightweight Charts
(src/ui/lw_chart.py). Highcharts is under the Highsoft EULA, non-commercial
personal use; see static/HIGHCHARTS_LICENSE.txt.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

_STATIC = Path(__file__).resolve().parents[2] / "static"
HIGHCHARTS_VERSION = "13.1.1"
_CDN = "https://cdn.jsdelivr.net/npm/highcharts@" + HIGHCHARTS_VERSION + "/"
_CDN_NAME = {"highstock.js": "highstock.js", "highcharts-more.js": "highcharts-more.js",
             "highcharts-heatmap.js": "modules/heatmap.js"}


def _js_str(text: str) -> str:
    # A JS string literal that cannot close the <script> block it sits in.
    return json.dumps(text).replace("<", "\\u003c")


def loader_js(files: list[tuple[str, str]], global_name: str) -> str:
    """JavaScript that loads `files` [(static name, CDN url)] in order while the
    frame is parsing, then the CDN copies if the static ones did not define
    `global_name` (audit F60). The library was copied into every chart frame,
    0.2-0.5 MB each and never cached; a script tag is fetched once and cached
    for every frame. Relative "app/static/" resolves against the app page, as
    the frame is a srcdoc document."""
    out = []
    for name, _cdn in files:
        out.append("document.write(" + _js_str(f'<script src="app/static/{name}"></script>') + ");")
    fallback = "".join("document.write(" + _js_str(f'<script src="{cdn}"></script>') + ");" for _n, cdn in files)
    check = f"<script>if(!window.{global_name}){{{fallback}}}</script>"
    out.append("document.write(" + _js_str(check) + ");")
    return "".join(out)


def lib(*modules: str) -> str:
    """The Highcharts Stock core plus the named optional modules, as a loader
    for a <script> block (it used to be the libraries' full source)."""
    names = ["highstock.js", *modules]
    return loader_js([(n, _CDN + _CDN_NAME.get(n, n)) for n in names], "Highcharts")


def script_json(obj) -> str:
    # "</" would close the <script> block that carries the data.
    return json.dumps(obj, separators=(",", ":")).replace("</", "<\\/")


def text_alternative(text: str) -> str:
    """The chart in words for a screen reader, hidden from sight (audit F26).
    The drawing itself is marked aria-hidden by the caller."""
    return ("<p style='position:absolute;width:1px;height:1px;overflow:hidden;"
            "clip:rect(0 0 0 0);white-space:nowrap'>" + html.escape(text) + "</p>")
