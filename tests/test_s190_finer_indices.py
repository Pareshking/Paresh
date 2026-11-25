"""S190: each finer NSE index is paired with the ranked stocks of its NSE industry or basic industry."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.engine import sectors_page as sp


def _prices(n_syms: int, days: int = 400) -> pd.DataFrame:
    idx = pd.bdate_range("2025-01-01", periods=days)
    rng = np.random.default_rng(0)
    return pd.DataFrame(100 * np.cumprod(1 + rng.normal(0, 0.01, (days, n_syms)), axis=0), index=idx,
                        columns=[f"S{i}" for i in range(n_syms)])


def _fmap() -> pd.DataFrame:
    return pd.DataFrame([
        {"index_key": "nifty_bank", "level": "NSE_Industry", "labels": "Banks", "noun": "banks", "reason": ""},
        {"index_key": "nifty_psu_bank", "level": "NSE_Basic_Industry", "labels": "Public Sector Bank", "noun": "public-sector banks", "reason": ""},
        {"index_key": "nifty_sfb", "level": "NSE_Basic_Industry", "labels": "Other Bank;Microfinance", "noun": "x", "reason": ""},
        {"index_key": "nifty_missing", "level": "NSE_Macro", "labels": "Anything", "noun": "y", "reason": ""},
    ])


def test_each_finer_index_gets_the_ranked_stocks_of_its_industry():
    px = _prices(12)
    rank = pd.DataFrame({"Symbol": px.columns,
                         "NSE_Industry": ["Banks"] * 8 + ["Finance"] * 4,
                         "NSE_Basic_Industry": ["Public Sector Bank"] * 5 + ["Other Bank"] * 3 + ["Microfinance"] * 3 + ["NBFC"]})
    out = sp.finer_stocks(px, rank, px.index[-1], _fmap())
    assert out["nifty_bank"].stocks == 8 and out["nifty_bank"].noun == "banks"
    assert out["nifty_psu_bank"].stocks == 5
    assert out["nifty_sfb"].stocks == 6                    # two labels, joined by ";"
    assert "nifty_missing" not in out                       # a level the ranking does not carry pairs nothing
    # The same equal-weighted, daily-rebalanced level the sector rows use, read with the Indices date rule.
    level = sp.pi.equal_weight_level(px[list(px.columns[:5])])
    assert out["nifty_psu_bank"].returns == {m: sp.ew_return(level, m, px.index[-1]) for m in sp.WINDOWS}


def test_fewer_than_five_stocks_pair_nothing():
    px = _prices(8)
    rank = pd.DataFrame({"Symbol": px.columns, "NSE_Industry": ["Banks"] * 4 + ["Finance"] * 4,
                         "NSE_Basic_Industry": ["Public Sector Bank"] * 4 + ["NBFC"] * 4})
    assert sp.finer_stocks(px, rank, px.index[-1], _fmap()) == {}


def test_the_committed_pairing_names_finer_indices_of_the_sector_map_only():
    fmap, smap = sp.finer_map(), sp.sector_map()
    finer = set(smap.loc[smap["role"] == "finer", "index_key"])
    assert len(fmap) and set(fmap["index_key"]) <= finer
    assert set(fmap["level"]) <= {"NSE_Industry", "NSE_Basic_Industry"}
    assert (fmap["noun"].str.len() > 0).all() and (fmap["reason"].str.len() > 0).all()


def test_the_pairing_labels_exist_in_the_classification_file():
    cls = pd.read_csv("data/reference/nse_classification.csv", dtype=str)
    col = {"NSE_Industry": "Industry", "NSE_Basic_Industry": "Basic_Industry"}
    for r in sp.finer_map().itertuples():
        for lab in r.labels.split(";"):
            assert lab in set(cls[col[r.level]]), (r.index_key, lab)


def test_the_sector_indices_table_shows_the_paired_stocks_under_their_index():
    from src.ui.views import sector_view as sv
    from src.ui.views.dashboard_home_view import html_of
    ret = {m: 1.0 for m in sp.WINDOWS}
    fin = sp.Finer("public-sector banks", 11, ret, -2.0)
    line = sp.IndexLine("nifty_psu_bank", "Nifty PSU Bank", False, pd.Timestamp("2012-01-01"), ret, -1.0, 8.2, None, fin)
    nse = {"as_of": pd.Timestamp("2026-11-23"), "groups": [sp.SectorGroup("Financial Services", 117, None, [line])]}
    out = html_of(sv.section_indices(None, nse, lambda s: s))
    assert "The 750’s 11 public-sector banks" in out
    assert out.index("Nifty PSU Bank") < out.index("public-sector banks")
