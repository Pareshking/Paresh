"""S193 A12 and A10 (owner, 23 Nov 2026: both approved).

A12: a system's first month has no book before it, so the record measures the book and
the Nifty 500 from its first fill (nano's October from the 1 Oct close: +0.17%, where the
750 read -0.80% from 30 Sep). The market, momentum and lead beside it in that month were
measured from the month-end, so the two sides of one comparison started on different
days. Now every series in the first month starts at the fill, on Portfolio and the
Dashboard alike, and Portfolio's calendar footnotes the cell. The ledgers are unchanged.

A10: Sectors' share above the 200D EMA a month ago counts today's members (37%), the
Dashboard the members of the day (38%). Both rules stay; Sectors' headline names its own.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pandas as pd

from src.engine import dashboard_insights as di
from src.ui.views import portfolio_page as pp

ROOT = Path(__file__).resolve().parents[1]

# Month-end before the first month 100; the first fill (1 Oct) 110; 30 Oct 121; 20 Nov 133.1.
IDX = pd.to_datetime(["2026-09-30", "2026-10-01", "2026-10-30", "2026-11-02", "2026-11-20"])
MARKET = pd.Series([100.0, 110.0, 121.0, 121.0, 133.1], index=IDX)


def test_first_fill_is_the_first_session_of_the_month():
    assert di.first_fill(MARKET, pd.Period("2026-10", "M")) == pd.Timestamp("2026-10-01")
    assert di.first_fill(MARKET, pd.Period("2026-12", "M")) is None
    assert di.first_fill(None, pd.Period("2026-10", "M")) is None


def test_dashboard_first_frozen_month_starts_at_the_fill():
    ledger = {"2026-10": {"strategy": 0.15}}
    first = di.book_month(ledger, None, MARKET, {}, pd.Timestamp("2026-11-20"), first_month=pd.Period("2026-10", "M"))
    old = di.book_month(ledger, None, MARKET, {}, pd.Timestamp("2026-11-20"))
    # Book +15% from the fill: ahead of the market from the fill (+10%), behind it from the month-end (+21%).
    assert (first.months, first.months_ahead) == (1, 1)
    assert (old.months, old.months_ahead) == (1, 0)


def test_dashboard_live_first_month_starts_at_the_fill():
    nov = pd.Period("2026-11", "M")
    mom = {"Momentum": MARKET * 2}
    bm = di.book_month({}, 3.0, MARKET, mom, pd.Timestamp("2026-11-20"), first_month=nov)
    assert round(bm.market_mtd, 6) == round((133.1 / 121.0 - 1) * 100, 6)  # from 2 Nov, the fill
    assert round(bm.momentum_mtd["Momentum"], 6) == round(bm.market_mtd, 6)
    later = di.book_month({}, 3.0, MARKET, mom, pd.Timestamp("2026-11-20"), first_month=pd.Period("2026-10", "M"))
    assert round(later.market_mtd, 6) == round((133.1 / 121.0 - 1) * 100, 6)  # from 30 Oct, the month-end


def _page(system: str, grid: pd.DataFrame) -> pp.Page:
    blank = {f.name: None for f in dataclasses.fields(pp.Page)}
    blank.update(as_of=pd.Timestamp("2026-11-20"), market=MARKET, mom=MARKET, history={"monthly_grid": grid},
                 equity=pd.Series(dtype=float), system=system)
    return pp.Page(**blank)


def test_portfolio_first_month_market_and_lead_start_at_the_fill(monkeypatch):
    import src.engine.systems as systems

    monkeypatch.setattr(systems, "inception", lambda system: pd.Period("2026-10", "M"))
    grid = pd.DataFrame({"Period": ["2026-10", "2026-11"], "Strategy Net": [0.05, 0.02], "Benchmark": [0.10, 0.10]})
    m = pp.months_of(_page("nano", grid))
    oct_, nov = pd.Period("2026-10", "M"), pd.Period("2026-11", "M")
    assert round(m["market"][oct_], 6) == 10.0           # 1 Oct 110 -> 30 Oct 121, not 30 Sep 100 -> 121
    assert round(m["lead"][oct_], 6) == -5.0
    assert round(m["market"][nov], 6) == 10.0            # later months from the month-end, as before
    assert m["n500"][oct_] == 10.0                       # the ledger's recorded value, unchanged


def test_sectors_headline_names_its_members_rule():
    from src.engine import sectors_page as sp
    from src.ui.views import sector_view as sv

    shares = [sp.Share("All ranked stocks", 750, 40.0, 37.0, 47.0), sp.Share("Auto", 49, 30.0, 35.0, 60.0),
              sp.Share("Metals", 20, 50.0, 45.0, 20.0)]
    out = sv.section_inside(None, shares, pd.DataFrame(), pd.DataFrame({"Symbol": ["A"], "3M Return": [1.0], "Industry": ["Auto"]}), lambda s: s, "sector")
    assert "37% a month ago, today’s members;" in out[0]


def test_since_start_market_starts_at_the_fill():
    # Owner, 23 Nov 2026: "2: from the fill". The book starts at the first fill's close; the market beside
    # it started the day before (nano: +8.5% from 30 Sep against +9.6% from 1 Oct, a 1.1 pt gap in the lead).
    from src.engine import portfolio_report as pr

    idx = pd.to_datetime(["2026-09-30", "2026-10-01", "2026-10-05", "2026-11-20"])
    book = pd.Series([100.0, 99.9, 101.0, 110.0], index=idx)
    market = pd.Series([100.0, 110.0, 111.0, 121.0], index=idx)
    rows = {r[0]: r for r in pr.periods(book, market, market, pd.Timestamp("2026-11-20"), pd.Timestamp("2026-10-01"))}
    assert round(rows["Since start"][2], 6) == 10.0           # 110 -> 121, not 100 -> 121
    old = {r[0]: r for r in pr.periods(book, market, market, pd.Timestamp("2026-11-20"))}
    assert round(old["Since start"][2], 6) == 21.0
    g = pr.daily_gaps(book, market, pd.Timestamp("2026-10-01"))
    assert list(g.index) == list(idx[2:])                     # the fill session (cash until the close) is left out
    src = (ROOT / "src" / "ui" / "views" / "dashboard_home_view.py").read_text(encoding="utf-8")
    assert "since_mkt = di.window_return(market, fill0 if fill0 is not None else inc, as_of)" in src   # the book's session; the index reads on or before it (S193 E)
    psrc = (ROOT / "src" / "ui" / "views" / "portfolio_page.py").read_text(encoding="utf-8")
    assert "rows = pr.periods(p.equity, p.market, p.mom, p.as_of, first_fill(p)[1])" in psrc
