"""The hand-built HTML tables must escape every third-party string they render.

`render_saas_table` and `render_master_screener_table` assemble raw markup and
hand it to `st.iframe`, whose srcdoc Streamlit renders with `allow-scripts`
AND `allow-same-origin` -- script in a cell runs on the app's own origin, with
the parent app's DOM and storage in reach.

Every string those tables interpolate arrives from a third party: `Symbol`,
`Industry` and `Indices` come from the niftyindices.com constituent CSVs (the
loader writes the response body straight to disk and reads it back with no
character validation), `ATH Date` and `Market Cap` from the NSE PR bhavcopy,
prices from Yahoo. "NSE symbols are alphanumeric today" is an observation
about the feed, not a property the app enforces -- so the escaping lives here.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

import pandas as pd
import pytest

from src.ui import theme


class _Markup(HTMLParser):
    """Collects the tags and attributes a browser would actually build."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.attrs: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(name.lower() for name, _ in attrs)

    handle_startendtag = handle_starttag


def _parsed(html: str) -> _Markup:
    """Parse only the generated rows/headers, never the static page chrome."""
    body = "".join(re.findall(r"<t[rh][ >].*?</t[rh]>", html, re.S)) or html
    m = _Markup()
    m.feed(body)
    return m


def _assert_inert(html: str, payload: str) -> None:
    """The payload may appear as text; it may never become markup."""
    assert payload not in html, "payload reached the iframe srcdoc unescaped"
    parsed = _parsed(html)
    assert not {"img", "script", "svg", "iframe", "object"} & set(parsed.tags), parsed.tags
    assert not [a for a in parsed.attrs if a.startswith("on")], parsed.attrs

# Text context, attribute-breakout, and a quote-delimiter escape.
PAYLOADS = [
    "<img src=x onerror=alert(1)>",
    '" onmouseover="alert(1)',
    "</span><script>alert(1)</script>",
    "' onfocus='alert(1)",
]


@pytest.fixture()
def captured(monkeypatch):
    """Capture the markup the table hands to st.iframe."""
    box: dict[str, str] = {}
    monkeypatch.setattr(theme.st, "iframe", lambda html, **kw: box.setdefault("html", html))
    monkeypatch.setattr(theme.st, "info", lambda *a, **kw: None)
    return box


def _screener_row(**overrides) -> pd.DataFrame:
    row = {
        "Rank": 1,
        "Symbol": "RELIANCE",
        "CMP": 100.0,
        "Rank Δ 1M": 2,
        "Rank Δ 3M": 1,
        "Indices": "N50",
        "Industry": "Oil & Gas",
        "Market Cap (Cr)": 1000.0,
        "3M Return": 0.1,
        "3M Sharpe": 1.0,
        "6M Return": 0.2,
        "6M Sharpe": 1.2,
        "% High": 1.0,
        "% ATH": 2.0,
        "ATH Date": "2024-01-01",
        "% 50 EMA": 3.0,
        "Volume": "Normal",
        "Above 50 EMA": True,
        "Near 52W High": True,
        "At ATH": False,
        "Stop Loss": 90.0,
        "Chand Exit": 88.0,
        "Data Gap": "🟢",
        "FFill %": 0.0,
    }
    row.update(overrides)
    return pd.DataFrame([row])


@pytest.mark.parametrize("payload", PAYLOADS)
@pytest.mark.parametrize("column", ["Symbol", "Industry", "Indices", "ATH Date"])
def test_master_screener_escapes_third_party_cells(captured, column, payload):
    theme.render_master_screener_table(_screener_row(**{column: payload}))
    _assert_inert(captured["html"], payload)


@pytest.mark.parametrize("payload", PAYLOADS)
@pytest.mark.parametrize("column", ["Symbol", "Industry", "Quadrant", "Action", "Reason"])
def test_saas_table_escapes_third_party_cells(captured, column, payload):
    df = pd.DataFrame([{"Symbol": "TCS", "Industry": "IT", "Quadrant": "Leading",
                        "Action": "HOLD", "Reason": "n/a", **{column: payload}}])
    theme.render_saas_table(df)
    _assert_inert(captured["html"], payload)


@pytest.mark.parametrize("payload", PAYLOADS)
def test_saas_table_escapes_column_headers(captured, payload):
    theme.render_saas_table(pd.DataFrame([{payload: 1}]))
    assert payload not in captured["html"]


def test_symbol_link_target_is_url_encoded(captured):
    """The href carries the symbol, so it must not be able to grow attributes."""
    theme.render_master_screener_table(_screener_row(Symbol='A" onclick="alert(1)'))
    html = captured["html"]
    assert "onclick" not in [a for a in _parsed(html).attrs]
    assert '<a href="?stock=A%22%20onclick%3D%22alert%281%29"' in html


def test_ordinary_symbols_still_render_and_link(captured):
    """Escaping must be invisible to the alphanumeric tickers that exist today."""
    theme.render_master_screener_table(_screener_row(Symbol="RELIANCE"))
    html = captured["html"]
    assert 'href="?stock=RELIANCE"' in html
    assert 'data-stock="RELIANCE"' in html
    assert ">RELIANCE</a>" in html


def test_ampersand_industry_survives_as_text(captured):
    """An escaped "&" is still the right character once the browser parses it."""
    theme.render_master_screener_table(_screener_row(Industry="Oil & Gas"))
    assert "Oil &amp; Gas" in captured["html"]


# ── Chart pages: JSON inside a <script> block ────────────────────────────────
#
# The chart components take the same route -- a full HTML page handed to
# st.iframe -- but reach it through json.dumps into a <script> body. json.dumps
# escapes quotes and backslashes and NOT "<", and the HTML parser looks for the
# literal "</script" before JavaScript ever sees the string, so an Industry
# name or ticker carrying "</script>" closes the block and everything after it
# is markup.

BREAKOUT = "</script><img src=x onerror=alert(1)>"


def _script_tags_balance(html: str) -> bool:
    return len(re.findall(r"<script\b", html)) == len(re.findall(r"</script\s*>", html))


def test_rrg_chart_payload_cannot_close_its_script_block(monkeypatch):
    from src.ui import charts

    box: dict[str, str] = {}
    monkeypatch.setattr(charts.st, "iframe", lambda html, **kw: box.setdefault("html", html))
    monkeypatch.setattr(charts.st, "info", lambda *a, **kw: None)

    charts.render_rrg_chart(pd.DataFrame([{
        "Industry": BREAKOUT, "RS_Ratio": 100.0, "RS_Momentum": 100.0,
        "Quadrant": "Leading", "Stocks": 3, "Trail_R": [100.0], "Trail_M": [100.0],
    }]))

    html = box["html"]
    assert BREAKOUT not in html
    assert _script_tags_balance(html)


def test_sector_treemap_payload_cannot_close_its_script_block(monkeypatch):
    from src.ui import charts

    box: dict[str, str] = {}
    monkeypatch.setattr(charts.st, "iframe", lambda html, **kw: box.setdefault("html", html))
    monkeypatch.setattr(charts.st, "info", lambda *a, **kw: None)
    monkeypatch.setattr(charts.st, "warning", lambda *a, **kw: None)

    charts.render_sector_treemap(pd.DataFrame({
        "Symbol": ["AAA", "BBB"],
        "Industry": [BREAKOUT, BREAKOUT],
        "Rank": [1, 2],
        "CMP": [10.0, 20.0],
        "Market Cap (Cr)": [100.0, 200.0],
        "3M Return": [0.1, 0.2],
        "3M Sharpe": [1.0, 1.1],
    }))

    html = box["html"]
    assert BREAKOUT not in html
    assert _script_tags_balance(html)


def test_script_json_preserves_the_value_it_escapes():
    """The escape must be invisible to JavaScript -- "<\\/" is just "/"."""
    import json

    from src.ui.charts import _script_json

    encoded = _script_json({"industry": BREAKOUT})
    assert "</script" not in encoded
    assert json.loads(encoded.replace("<\\/", "</"))["industry"] == BREAKOUT
