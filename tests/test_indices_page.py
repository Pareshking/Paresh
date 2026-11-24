"""The Indices page (S170): its figures on small hand-made stores where the answer is
known, then the page drawn from the committed copy of NSE's files."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
import pytest

from src.engine import indices_page as ip
from src.loaders import nse_indices as ni


def _store(series: dict[str, pd.Series], pe: dict[str, pd.Series] | None = None) -> ip.Frames:
    rows = []
    for k, s in series.items():
        for d, v in s.items():
            rows.append({"date": d, "key": k, "close": v, "pe": (pe or {}).get(k, pd.Series(dtype=float)).get(d, np.nan),
                         "pb": 3.0, "div_yield": 1.0, "derived": False})
    g = pd.DataFrame({"key": list(series), "group": ["Broad market"] * len(series), "name": [k.upper() for k in series]})
    return ip.frames(pd.DataFrame(rows), g)


def test_a_window_starts_on_the_last_session_on_or_before_the_same_date():
    days = pd.bdate_range("2025-01-01", "2026-11-20")
    s = pd.Series(np.arange(len(days), dtype=float) + 100, index=days)
    # 20 Oct 2026 is a Tuesday; one month back from 20 Nov is that day exactly.
    assert ip.ret(s, 1, days[-1]) == pytest.approx((s.iloc[-1] / s[pd.Timestamp("2026-10-20")] - 1) * 100)
    young = s[s.index >= "2026-06-01"]
    assert ip.ret(young, 12, days[-1]) is None and ip.ret(young, 3, days[-1]) is not None


def test_the_pe_percentile_counts_only_from_the_basis_change():
    days = pd.bdate_range("2020-01-01", "2026-11-20")
    close = pd.Series(100.0, index=days)
    pe = pd.Series(np.where(days < ip.PE_FROM, 40.0, 20.0), index=days)   # old basis all dearer
    pe.iloc[-1] = 21.0
    f = _store({"nifty_50": close}, {"nifty_50": pe})
    v = ip.valuation(f, ("nifty_50",))[0]
    # Every day since 31 Mar 2021 reads 20, today 21: dearer than all of them, the
    # old basis's 40s not counted.
    assert v.since == ip.PE_FROM and v.pct_now == pytest.approx(100.0, abs=0.1)


def test_a_style_lead_is_its_return_minus_its_parents():
    days = pd.bdate_range("2024-01-01", "2026-11-20")
    parent = pd.Series(np.linspace(100, 110, len(days)), index=days)
    style = pd.Series(np.linspace(100, 130, len(days)), index=days)
    f = _store({"st": style, "pa": parent})
    s = ip.styles(f, (("Test", "st", "pa"),))[0]
    assert s.lead_now == pytest.approx(ip.ret(style, 12, days[-1]) - ip.ret(parent, 12, days[-1]))
    assert s.rel.iloc[0] == 100 and s.worst == pytest.approx(0, abs=1e-9) and s.recovered is not None


def test_the_worst_relative_fall_and_its_recovery():
    days = pd.bdate_range("2022-01-03", periods=300)
    parent = pd.Series(100.0, index=days)
    path = np.r_[np.linspace(100, 120, 100), np.linspace(120, 90, 100), np.linspace(90, 121, 100)]
    f = _store({"st": pd.Series(path, index=days), "pa": parent})
    s = ip.styles(f, (("Test", "st", "pa"),))[0]
    assert s.worst == pytest.approx(-25.0, abs=0.01)
    assert s.worst_peak == days[99] and s.worst_low == days[199]
    assert s.recovered is not None and s.recovered > days[199]


def test_size_years_give_the_return_and_the_worst_fall_within_each_year():
    days = pd.bdate_range("2016-01-01", "2018-12-31")
    vals = np.full(len(days), 100.0)
    y17 = (days.year == 2017)
    vals[y17] = np.r_[np.linspace(100, 80, y17.sum() // 2), np.linspace(80, 110, y17.sum() - y17.sum() // 2)]
    vals[days.year == 2018] = 110.0
    f = _store({"nifty_100": pd.Series(vals, index=days)})
    z = ip.size_years(f, (("Large", "nifty_100"),))[0]
    ret17, fall17 = z.years[2017]
    assert ret17 == pytest.approx(10.0) and fall17 == pytest.approx(-20.0)
    assert 2016 not in z.years                      # from 2017, the size indices' first full year


def test_every_index_sorts_by_one_year_and_lists_new_indices_last():
    days = pd.bdate_range("2025-01-01", "2026-11-20")
    a = pd.Series(np.linspace(100, 120, len(days)), index=days)
    b = pd.Series(np.linspace(100, 90, len(days)), index=days)
    new = a[a.index >= "2026-09-01"]
    f = _store({"up": a, "down": b, "new": new})
    rows = ip.every_index(f, ("Broad market",))["Broad market"]
    assert [r.key for r in rows] == ["up", "down", "new"]
    assert rows[2].returns[12] is None and rows[2].returns[1] is not None and rows[2].from_high is None


def test_the_compact_copy_round_trips(tmp_path):
    rows = ni.parse_file((
        b"Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,Closing Index Value,"
        b"Points Change,Change(%),Volume,Turnover (Rs. Cr.),P/E,P/B,Div Yield\n"
        b"Nifty 50,20-11-2026,-,-,-,25800.60,1,1,1,1,21.02,3.6,1.3\n"), {"nifty_50": "nifty_50"})
    h, r = tmp_path / "h.parquet", tmp_path / "r.csv"
    ni.write_compact(rows, freeze=True, history=h, recent=r)
    more = ni.parse_file((
        b"Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,Closing Index Value,"
        b"Points Change,Change(%),Volume,Turnover (Rs. Cr.),P/E,P/B,Div Yield\n"
        b"Nifty 50,23-11-2026,-,-,-,25900.10,1,1,1,1,21.10,3.6,1.3\n"), {"nifty_50": "nifty_50"})
    assert ni.write_compact(ni.merge(rows, more), history=h, recent=r) == (1, 1)
    c = ni.read_compact(history=h, recent=r)
    assert list(c["close"]) == [25800.60, 25900.10] and not c["derived"].any()


# ── The page, from the committed copy ────────────────────────────────────────

@pytest.fixture(scope="module")
def real():
    store = ni.read_compact()
    if store.empty:
        pytest.skip("no committed copy of NSE's index files")
    return ip.frames(store, ni.groups())


def test_the_page_draws_every_section_in_the_agreed_order(real):
    from src.ui.views.indices_view import html_of, page_parts
    text = re.sub(r"<[^>]+>", " ", html_of(page_parts(real))).lower()
    order = ["indices", "valuation", "styles", "how long a style can lag", "calendar years", "size, year by year",
             "every index", "data to"]
    pos = 0
    for o in order:
        i = text.find(o, pos)
        assert i >= 0, o
        pos = i + len(o)
    assert "nan" not in text.split() and "none" not in text.split()


def test_the_1000_shows_the_nifty_1000s_pe_and_says_why_the_rest_is_dashed(real):
    """S219-7: NSE publishes the Nifty 1000's P/E and our files carry it (from 16 Nov 2026), so ?sys=1000 adds its
    row: P/E now, and "–" for the percentile and the past readings with one reason; the 750 has no such row."""

    from src.ui.views.indices_view import html_of, page_parts
    y = ip.young_valuation(real, "nifty_1000")
    if y is None:
        pytest.skip("the committed copy has no Nifty 1000 P/E")
    on_1000, on_750 = html_of(page_parts(real, "1000")), html_of(page_parts(real, "750"))
    assert "Nifty 1000" in on_1000 and f"{y.pe_now:.2f}" in on_1000
    assert "the index is too new for a percentile" in on_1000 and "the index is too new for a percentile" not in on_750
    spec = next(p for p in page_parts(real, "1000") if getattr(p, "kind", "") == "trows")
    rows = [r["name"] for r in spec.spec["rows"]]
    assert rows.index("Nifty 1000") == rows.index("Nifty Total Market") + 1


def test_sector_indices_are_not_on_this_page(real):
    rows = ip.every_index(real)
    assert set(rows) == {"Broad market", "Theme", "Strategy"}
    assert "nifty_it" not in {r.key for v in rows.values() for r in v}


def test_the_dashboard_card_reads_the_same_figures(real):
    from src.ui.views.dashboard_home_view import indices_glance_rows
    rows = indices_glance_rows(real)
    v = ip.valuation(real, ("nifty_500",))[0]
    assert rows[0][1].startswith(f"{round(v.pct_now)}")
    best = max((s for s in ip.styles(real) if s.lead_now is not None), key=lambda s: s.lead_now)
    assert best.style.lower() in rows[1][0] and best.name.replace("NIFTY", "Nifty") in rows[1][0]
    assert real.until(pd.Timestamp("2026-10-20")).as_of <= pd.Timestamp("2026-10-20")
