"""The grouping switch on Sectors (owner, 21 Nov 2026, item 12): NSE sectors give the full page; with a TradingView
grouping every section built from the ranked stocks regroups, and the NSE index sections give way to one line.
No section silently keeps NSE's sectors."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engine import indices_page as ip
from src.ui.views import sector_view as sv
from src.ui.views.dashboard_home_view import Chart, html_of

NSE = {"Financial Services": "F", "Healthcare": "H"}
TV = {"Finance": "F", "Health Technology": "H"}


def _rank_and_prices():
    n = 420
    idx = pd.bdate_range("2025-06-02", periods=n)
    rng = np.random.default_rng(5)
    px, rows = {}, []
    for k in range(12):
        sym = f"S{k:02d}"
        drift = 0.003 if k % 2 else -0.001
        px[sym] = 100 * np.cumprod(1 + drift + rng.normal(0, 0.004, n))
        nse = "Financial Services" if k % 2 else "Healthcare"
        tv = "Health Technology" if k < 6 else "Finance"          # a different split from NSE's
        rows.append({"Symbol": sym, "Industry": nse, "TV_Sector": tv, "TV_Industry": tv + " sub", "Rank": k + 1,
                     "3M Return": 0.01 * k, "6M Return": 0.02 * k, "Above 50 EMA": k % 2 == 1, "Near 52W High": True,
                     "Short History": "No", "Data Gap": ""})
    return pd.DataFrame(rows), pd.DataFrame(px, index=idx)


@pytest.fixture
def frames(monkeypatch):
    rank, px = _rank_and_prices()
    idx = px.index
    close = pd.DataFrame({"nifty_financial_services": px.iloc[:, 1::2].mean(axis=1) * 300,
                          "nifty_healthcare_index": px.iloc[:, ::2].mean(axis=1) * 200}, index=idx)
    f = ip.Frames(close, close * 0 + 20.0, close * 0 + 3.0, close * 0 + 1.0,
                  {"nifty_financial_services": "Nifty Financial Services", "nifty_healthcare_index": "Nifty Healthcare Index"},
                  {"nifty_financial_services": "Sector", "nifty_healthcare_index": "Sector"})
    from src.ui import indices_data
    monkeypatch.setattr(indices_data, "frames", lambda: f)
    smap = pd.DataFrame({"sector": ["Financial Services", "Healthcare"], "index_key": list(close.columns),
                         "role": ["headline", "headline"], "reason": ["x", "y"]})
    monkeypatch.setattr(sv.sp, "sector_map", lambda path=None: smap)
    return rank, px, px.mean(axis=1)


def _page(rank, px, tm, col):
    model = sv._model.__wrapped__(f"t|{col}", rank, px, col, tm)
    parts = sv.page_parts(model, rank, col)
    text = html_of(parts) + " ".join(str(p.spec) for p in parts if isinstance(p, Chart))
    return model, parts, text


def test_nse_sectors_give_the_full_page(frames):
    model, parts, text = _page(*frames, "Industry")
    assert "Broad or narrow" in text and "NSE’s sector indices" in text and "for the sector" in text
    assert sv.NSE_ONLY not in text
    assert {r.name for r in model["ld"].rows} == set(NSE)
    assert "pairs" in {p.kind for p in parts if isinstance(p, Chart)}


@pytest.mark.parametrize("col", ["TV_Sector", "TV_Industry"])
def test_a_tradingview_grouping_regroups_every_section_and_hides_the_nse_indices(frames, col):
    rank, px, tm = frames
    model, parts, text = _page(rank, px, tm, col)
    want = set(rank[col])
    # Every section built from the ranked stocks reads the chosen grouping, none keeps NSE's sectors.
    assert {r.name for r in model["ld"].rows} == want
    assert set(model["months"].index) == want
    assert {s.name for s in model["shares"]} - {"All ranked stocks"} == want
    assert {r["name"] for v in model["map"].values() for r in v} == want
    for nse in NSE:
        assert nse not in text, f"{nse} shown under a TradingView grouping"
    # The NSE index sections give way to one line, said once; no index figure is drawn.
    assert model["nse"] is None
    assert text.count(sv.NSE_ONLY) == 1
    assert "Nifty Financial Services" not in text and "for the sector" not in text
    assert "pairs" not in {p.kind for p in parts if isinstance(p, Chart)}
