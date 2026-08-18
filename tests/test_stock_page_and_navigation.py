"""The stock detail page, and getting to it from the screener.

Two defects motivated this. The card grid rendered view.head(48) and stopped
SILENTLY -- ranks 49 to 750 did not exist in card view and nothing on screen
said so. And there was no way to open a stock at all except by typing it into
the search box; clicking a symbol did nothing.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parent / "_stock_page_probe_app.py")


def _app(**query):
    at = AppTest.from_file(APP, default_timeout=180)
    for k, v in query.items():
        at.query_params[k] = v
    at.run()
    return at


# ── Routing ─────────────────────────────────────────────────────────────────

def test_screener_renders_without_a_stock_param():
    at = _app()
    assert not at.exception


def test_stock_param_opens_the_detail_page():
    at = _app(stock="S3")
    assert not at.exception
    body = " ".join(m.value for m in at.markdown)
    assert "S3" in body


@pytest.mark.parametrize("section", [
    "Key levels", "Performance across every window", "Rank dynamics",
    "Data health", "Price action",
])
def test_every_section_of_the_page_renders(section):
    at = _app(stock="S3")
    body = " ".join(m.value for m in at.markdown)
    assert section in body


def test_the_page_offers_a_way_back():
    at = _app(stock="S3")
    assert any("Back to screener" in b.label for b in at.button)


def test_symbol_lookup_is_case_insensitive():
    at = _app(stock="s3")
    assert not at.exception
    assert "S3" in " ".join(m.value for m in at.markdown)


def test_an_unknown_symbol_warns_rather_than_crashing():
    at = _app(stock="NOSUCHTICKER")
    assert not at.exception
    assert any("not in the current ranking" in w.value for w in at.warning)


def test_key_levels_show_the_all_time_high_and_its_date():
    at = _app(stock="S3")
    body = " ".join(m.value for m in at.markdown)
    assert "All-Time High" in body
    assert "% from ATH" in body


def test_performance_matrix_covers_every_window():
    at = _app(stock="S3")
    body = " ".join(m.value for m in at.markdown)
    for months in (1, 3, 6, 9, 12):
        assert f"{months}M" in body
    for band in ("Return", "Sharpe", "Max Drawdown"):
        assert band in body


# ── Navigation links ────────────────────────────────────────────────────────

def _rank_df(cols: int = 8):
    from src.engine.momentum import MomentumEngine

    n = 400
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    rng = np.random.default_rng(4)
    px = pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, (n, cols)), axis=0)),
        index=idx, columns=[f"S{i}" for i in range(cols)],
    )
    info = pd.DataFrame({
        "Symbol": [f"S{i}" for i in range(cols)],
        "Industry": ["IT", "Bank"] * (cols // 2),
        "Indices": ["NIFTY 50"] * cols,
    })
    calc = MomentumEngine(px, high_df=px * 1.01, low_df=px * 0.99, close_df=px,
                          volume_df=pd.DataFrame(1e5, index=idx, columns=px.columns))
    return calc.get_rankings(info, pd.Series(1e4, index=px.columns),
                             close_prices_df=px, high_prices_df=px * 1.01), px


def test_card_symbol_links_to_the_stock_page(monkeypatch):
    from src.ui.views import ranking_view

    rank_df, _ = _rank_df()
    captured = []
    monkeypatch.setattr(ranking_view.st, "html",
                        lambda *a, **k: captured.append(a[0] if a else ""))
    ranking_view.render_stock_card(rank_df.iloc[0])

    html = " ".join(str(c) for c in captured)
    sym = rank_df.iloc[0]["Symbol"]
    assert f'href="?stock={sym}"' in html
    assert 'target="_self"' in html


def test_table_symbol_links_out_of_the_iframe():
    """The table lives in st.iframe, so _self would navigate the frame itself."""
    from src.ui import theme

    rank_df, px = _rank_df()
    captured = {}
    orig_iframe, orig_info = theme.st.iframe, theme.st.info
    theme.st.iframe = lambda h, **k: captured.setdefault("html", h)
    theme.st.info = lambda *a, **k: None
    try:
        theme.render_master_screener_table(rank_df, prices_df=px, key="t",
                                           density="Full Quant (35)")
    finally:
        theme.st.iframe, theme.st.info = orig_iframe, orig_info

    html = captured["html"]
    assert 'href="?stock=' in html
    assert 'target="_parent"' in html
    assert 'target="_self"' not in html


# ── Card grid reaches every stock ───────────────────────────────────────────

def test_card_grid_reports_how_many_of_how_many(monkeypatch):
    from src.ui.views import ranking_view

    rank_df, _ = _rank_df(cols=8)
    captions = []
    monkeypatch.setattr(ranking_view.st, "caption", lambda t, **k: captions.append(t))
    monkeypatch.setattr(ranking_view.st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(ranking_view.st, "columns",
                        lambda n, **k: [ranking_view.st.container() for _ in range(n)])
    monkeypatch.setattr(ranking_view.st, "button", lambda *a, **k: False)
    monkeypatch.setattr(ranking_view, "render_stock_card", lambda row: None)

    ranking_view._render_card_grid(rank_df)
    assert any(f"of {len(rank_df)}" in c for c in captions)


def test_card_grid_batch_size_is_not_a_hard_cap():
    """48 is a page size, not a ceiling -- the old code silently truncated."""
    from src.ui.views.ranking_view import CARD_BATCH

    assert CARD_BATCH == 48


def test_empty_result_says_so(monkeypatch):
    from src.ui.views import ranking_view

    infos = []
    monkeypatch.setattr(ranking_view.st, "info", lambda t, **k: infos.append(t))
    ranking_view._render_card_grid(pd.DataFrame(columns=["Symbol", "Rank"]))
    assert infos and "No stocks match" in infos[0]
