"""The Sectors page (S174, built 21 Nov 2026 from mock-up v2): the sector ↔ NSE index map and the figures."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.engine import indices_page as ip
from src.engine import sectors_page as sp
from src.loaders import nse_indices as ni


def test_every_sector_index_is_placed_exactly_once():
    """Each index in the "Sector" group of nse_index_groups.csv sits under one sector of the approved map, and the
    map names nothing else (owner, 21 Nov 2026: Sectors items 1-6, MQ4 included)."""
    groups = ni.groups()
    sector = set(groups.loc[groups["group"] == "Sector", "key"])
    m = sp.sector_map()
    counts = m["index_key"].value_counts()
    assert set(counts.index) == sector
    assert (counts == 1).all(), counts[counts > 1].to_dict()
    assert set(m["role"]) <= {"headline", "finer"}
    assert (m["reason"].str.len() > 0).all()


def test_one_headline_a_sector_and_the_owners_choices():
    m = sp.sector_map()
    h = m[m["role"] == "headline"]
    assert h["sector"].is_unique and len(h) == 18
    head = sp.headline_of(m)
    assert head["Financial Services"] == "nifty_financial_services"          # MQ2
    assert head["Healthcare"] == "nifty_healthcare_index"                    # MQ3
    assert head["Consumer Services"] == "nifty_consumer_services"            # MQ4
    assert head["Services"] == "nifty_commercial_transport_services"         # MQ4
    finer = dict(zip(m["index_key"], m["sector"]))
    assert finer["nifty_sugar_ethanol"] == "Fast Moving Consumer Goods"     # MQ5
    assert finer["nifty_energy"] == "Oil Gas & Consumable Fuels"             # MQ6


def test_the_two_moved_indices_left_indices_every_index_table():
    g = ni.groups().set_index("key")["group"]
    assert g["nifty_consumer_services"] == "Sector" and g["nifty_commercial_transport_services"] == "Sector"
    assert "Sector" not in ip.PAGE_FAMILIES


def _prices(n=420):
    idx = pd.bdate_range("2025-06-02", periods=n)
    rng = np.random.default_rng(3)
    cols = {}
    for k in range(6):
        cols[f"S{k}"] = 100 * np.cumprod(1 + 0.004 + rng.normal(0, 0.003, n))      # strong
        cols[f"W{k}"] = 100 * np.cumprod(1 - 0.002 + rng.normal(0, 0.003, n))      # weak
    return pd.DataFrame(cols, index=idx)


def test_a_strong_group_leads_and_a_weak_one_trails_with_the_same_construction():
    px = _prices()
    groups = pd.Series({c: ("Strong" if c.startswith("S") else "Weak") for c in px.columns})
    tm = px.mean(axis=1)
    ld = sp.leads(px, groups, tm)
    by = {r.name: r for r in ld.rows}
    assert by["Strong"].group == "ahead on both" and by["Weak"].group == "behind on both"
    # Two equal halves: the leads mirror each other against the 750 of both.
    assert by["Strong"].lead6 > 0 > by["Weak"].lead6
    assert ld.rows[0].name == "Strong"
    assert set(ld.gap) == {"1", "3", "6", "6_1m", "6_3m"}


def test_a_group_under_five_is_left_out_and_named():
    px = _prices()
    groups = pd.Series({c: ("Strong" if c.startswith("S") else "Weak") for c in px.columns})
    groups["W0"] = groups["W1"] = "Tiny"
    ld = sp.leads(px, groups, None)
    assert "Tiny" not in {r.name for r in ld.rows} and ld.left_out == {"Tiny": 2, "Weak": 4}


def test_ema_shares_count_today_members_on_three_dates():
    px = _prices()
    groups = pd.Series({c: ("Strong" if c.startswith("S") else "Weak") for c in px.columns})
    ld = sp.leads(px, groups, None)
    sh = {s.name: s for s in sp.ema_shares(px, groups, ld, span=20)}
    assert sh["Strong"].now == 100.0 and sh["Weak"].now < 50
    assert sh["All ranked stocks"].stocks == 12


def test_the_gap_is_the_sectors_stocks_less_its_index_over_the_same_sessions():
    px = _prices()
    groups = pd.Series({c: ("Financial Services" if c.startswith("S") else "Healthcare") for c in px.columns})
    ld = sp.leads(px, groups, None)
    idx = px.index
    close = pd.DataFrame({"nifty_financial_services": ld.levels["Financial Services"] * 1000 * (1 + 0.1 * (idx >= idx[-10])),
                          "nifty_healthcare_index": ld.levels["Healthcare"] * 500})
    f = ip.Frames(close, close * np.nan, close * np.nan, close * np.nan,
                  {"nifty_financial_services": "Nifty Financial Services", "nifty_healthcare_index": "Nifty Healthcare Index"},
                  {"nifty_financial_services": "Sector", "nifty_healthcare_index": "Sector"})
    m = pd.DataFrame({"sector": ["Financial Services", "Healthcare"], "index_key": list(close.columns),
                      "role": ["headline", "headline"], "reason": ["x", "y"]})
    gaps = {g.sector: g for g in sp.broad_or_narrow(f, ld, m)}
    # Healthcare's index is its own level scaled: no gap. Financials' index jumped 10% in the last month: a gap of about −10 pts.
    assert abs(gaps["Healthcare"].gap3) < 1e-9
    fin = gaps["Financial Services"]
    assert abs(fin.ours3 - fin.nse3 - fin.gap3) < 1e-9 and -13 < fin.gap1 < -9 and fin.gap3 < -9
    assert sp.broad_or_narrow(f, ld, m)[0].sector == "Financial Services"
