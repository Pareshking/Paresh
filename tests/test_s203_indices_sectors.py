"""S203: the Indices and Sectors sentences render their approved templates (owner, 24 Nov 2026).

The templates, by id, are in docs/archive/S203_TEMPLATES_OTHER_PAGES.md (sections 4 and 5; rules 11-14 in section
11, the owner's answers in section 12). One test per id, KEEP rows included, on the cases the row lists, with fake
inputs and no network. `_clean` fails a sentence with an empty slot, "None", "nan", a "–" inside it, a doubled word,
or a count spelled out (rule 11).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.engine import indices_page as ip
from src.engine import sectors_page as sp
from src.engine.extra_universe import UNIVERSE_SHORT
from src.ui import missing_words as mw
from src.ui.views import indices_view as iv
from src.ui.views import sector_view as sv
from src.ui.views.dashboard_home_view import Chart, html_of

ROOT = Path(__file__).resolve().parents[1]
NOV = pd.Timestamp("2026-11-20")
UNIS = [UNIVERSE_SHORT[s] for s in ("750", "1000", "nano")]
WORDS = r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b (sectors?|of|indices|styles|completed)"


def _text(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).replace("&#x27;", "'").replace("&amp;", "&").replace("&gt;", ">")


def _clean(html: str, notes: bool = False) -> str:
    """`notes`: a note may end with a column's footnote, "– in 12M: …" (R1)."""
    t = _text(html)
    assert t, "an empty sentence"
    assert not re.search(r"\b(None(?! of)|nan|NaN|NaT)\b", t), t
    for bad in ("{", "}", *(() if notes else (" – ",)), "  ", "..", "the the ", "up −", "down −", "rose −", "fell −", "12-month", "one year"):
        assert bad not in t, (bad, t)
    assert not re.search(WORDS, t, re.I), t
    return t


def _tag(html: str, tag: str) -> str:
    return _clean(re.search(rf"<{tag}[^>]*>(.*?)</{tag.split()[0]}>", html, re.S).group(1))


def _note(parts: list, n: int = 0) -> str:
    return _clean(re.findall(r'<p class="dh-note">(.*?)</p>', html_of(parts), re.S)[n], notes=True)


# ══ Indices (§4) ════════════════════════════════════════════════════════════

def _val(key: str, pct: float, pe: float = 22.0) -> ip.Valuation:
    return ip.Valuation(key=key, name=key, pe_3m=pe, pe_1m=pe, pe_now=pe, pct_3m=pct, pct_1m=pct, pct_now=pct,
                        since=ip.PE_FROM, pb_now=3.0, dy_now=1.2)


def _frames(tm_pe_from: str | None = "2021-10-14", late_tm: bool = False) -> ip.Frames:
    """A small store: weekly-ish sessions from 2012, the six valuation indices with a P/E."""
    idx = pd.bdate_range("2012-01-02", NOV, freq="W-FRI").append(pd.DatetimeIndex([NOV])).unique()
    keys = list(ip.VALUATION_KEYS)
    rng = np.random.default_rng(3)
    close = pd.DataFrame({k: 100 * np.cumprod(1 + rng.normal(0.002, 0.01, len(idx))) for k in keys}, index=idx)
    pe = pd.DataFrame({k: 20 + rng.normal(0, 1, len(idx)) for k in keys}, index=idx)
    if tm_pe_from is None:
        pe = pe.drop(columns="nifty_total_market")
    else:
        pe.loc[pe.index < pd.Timestamp(tm_pe_from), "nifty_total_market"] = np.nan
    if late_tm:
        close.loc[NOV, "nifty_total_market"] = np.nan
    names = {k: k.replace("_", " ").title().replace("Smallcap", "Smallcap") for k in keys}
    return ip.Frames(close, pe, pe * 0 + 3.0, pe * 0 + 1.2, names, {k: "Broad market" for k in keys})


# ── ix.head.1, ix.head.2 ──

@pytest.mark.parametrize("b, s, want", [
    (20, 80, "The Nifty 50's P/E is below its median since Mar 2021; the Nifty Smallcap 250's is above it."),
    (80, 20, "The Nifty 50's P/E is above its median since Mar 2021; the Nifty Smallcap 250's is below it."),
    (20, 30, "The Nifty 50's P/E is at the 20th percentile of its days since Mar 2021; the Nifty Smallcap 250's at the 30th."),
    (50, 70, "The Nifty 50's P/E is at its median since Mar 2021; the Nifty Smallcap 250's at the 70th."),
    (None, None, "NSE's index P/Es are not in yet."),
])
def test_ix_head_1(b, s, want):
    vals = [] if b is None else [_val("nifty_50", b), _val("nifty_smallcap_250", s)]
    assert _tag(iv.head(vals, NOV)[0], "h1") == want


def test_ix_head_2():
    assert _tag(iv.head([], NOV)[0], "p class=\"dh-lede\"") == (
        "NSE's own indices, read at the 20 Nov close: what each index costs against its recent past, which investing "
        "styles beat their parent index, and how deep a median year's max drawdown goes for each size. Price returns; "
        "dividends are not added.")


# ── ix.val.1 to ix.val.4 ──

@pytest.mark.parametrize("b, s, want", [
    (20, 80, "At 22.0 times earnings, the Nifty 50 is cheaper than on 80% of days since 31 Mar 2021. "
             "The Nifty Smallcap 250 is dearer than on 80%."),
    (79.5, 20.5, "At 22.0 times earnings, the Nifty 50 is dearer than on 80% of days since 31 Mar 2021. "
                 "The Nifty Smallcap 250 is cheaper than on 80%."),                 # half up, not to even
    (50, 50, "At 22.0 times earnings, the Nifty 50 is at its median since 31 Mar 2021. "
             "The Nifty Smallcap 250 is at its median."),
])
def test_ix_val_1(b, s, want):
    assert _clean(iv.valuation_headline(_val("nifty_50", b), _val("nifty_smallcap_250", s))) == want


def test_ix_val_1_missing():
    assert iv.valuation_headline(None, None) == "Each index's P/E against its own past since 31 Mar 2021."


def test_ix_val_2():
    f = _frames()
    note = _note(iv.section_valuation(f, ip.valuation(f), NOV, NOV))
    assert note == (
        "P/E is NSE's trailing price to earnings. The percentile counts days from 31 Mar 2021, when NSE changed the "
        "earnings basis (the Nifty 50 went from 40.4 to 33.2 overnight with the price flat), so older readings are a "
        "different measure. Dashed lines mark the middle half; the triangle is a month ago. Each line is 2 percentile "
        "points. Describing is not forecasting: this is not a forecast of returns. P/B gets no percentile: its basis "
        "changed on 29 Sep 2023 and again on 23 Sep 2024.")


def test_ix_val_3():
    f = _frames()
    young = ip.YoungValuation("nifty_1000", "Nifty 1000", pd.Timestamp("2026-11-16"), 23.4, 3.1, 1.1)
    note = _note(iv.section_valuation(f, ip.valuation(f), NOV, NOV, young))
    assert note.endswith("changed on 29 Sep 2023 and again on 23 Sep 2024. – for the Nifty 1000: the index is too new "
                         "for a percentile or a past reading (NSE’s daily files carry its P/E from 16 Nov 2026).")


@pytest.mark.parametrize("tm_from, want", [
    ("2021-10-14", "NSE's P/E for Nifty Total Market starts at its launch, 15 Oct 2021, and this line shows the years "
                   "before the 2021 change of basis."),          # the file's first weekly row after 14 Oct
    (None, "NSE's P/E for Nifty Total Market starts at its launch, and this line shows the years before the 2021 "
           "change of basis."),
])
def test_ix_val_4(tm_from, want):
    f = _frames(tm_from)
    text = _text(html_of(iv.section_valuation(f, ip.valuation(f), NOV, NOV)))
    assert want in text
    assert "A line above the band is dearer than three days in four since 2021; below it, cheaper." in text


# ── ix.sty.1, ix.sty.2 ──

def _style(name: str, lead: float | None, *, now: float = -3.0, worst: float = -10.0, recovered=None,
           parent: str = "Nifty 200", years: dict | None = None) -> ip.Style:
    idx = pd.bdate_range("2020-01-01", NOV)
    from_peak = pd.Series(np.linspace(0, now, len(idx)), index=idx)
    return ip.Style(name, name.lower(), "p", f"Nifty200 {name} 30", parent, pd.Timestamp("2015-04-01"), lead, lead, lead,
                    0.5, years or {}, pd.Series(100.0, index=idx), from_peak, worst, pd.Timestamp("2024-06-28"),
                    pd.Timestamp("2025-03-03"), recovered)


@pytest.mark.parametrize("leads, want", [
    ({"Value": 4.0, "Quality": -6.2, "Momentum": -9.8},
     "Over 12 months, value leads its parent; quality and momentum trail by more than 5 points: 6.2–9.8."),
    ({"Value": 4.0, "Alpha": 2.0, "Quality": -6.0},
     "Over 12 months, value and alpha lead their parents; quality trails by more than 5 points: 6.0."),
    ({"Value": 4.0, "Alpha": 2.0, "Low volatility": 1.0, "Quality": -6.0, "Momentum": -6.04},
     "Over 12 months, 3 styles lead their parents; quality and momentum trail by more than 5 points: 6.0."),
    ({"Value": 4.04, "Quality": -2.0},
     "Over 12 months, value leads its parent by the most, 4.0 points; no style trails by more than 5."),
    ({"Value": -1.0, "Quality": -7.25},
     "No style leads its parent over 12 months; quality trails most, by 7.3 points."),
    ({"Value": None}, "Each style against the index it picks from, over the last 12 months."),
])
def test_ix_sty_1(leads, want):
    assert _clean(iv.styles_headline([_style(k, v) for k, v in leads.items()])) == want


def test_ix_sty_2():
    assert _note(iv.section_styles([_style("Value", 1.0)], NOV, NOV)).startswith(
        "Each style index against the index it picks from: its price return over 12 months minus the parent's, read "
        "3 months ago, a month ago and now. Only live history is used, from the day NSE first published the index.")


# ── ix.lag.1 to ix.lag.3 ──

@pytest.mark.parametrize("now, worst, want", [
    (-8.0, -20.0, "Momentum’s line against the Nifty 200 is 8.0% below its June 2024 peak."),
    (-20.0, -20.0, "Momentum’s line against the Nifty 200 is 20.0% below its June 2024 peak, its deepest since launch in 2015."),
    (-0.04, -20.0, "Momentum’s line against the Nifty 200 is at its peak."),
])
def test_ix_lag_1(now, worst, want):
    assert _clean(iv.lag_headline(_style("Momentum", 1.0, now=now, worst=worst))) == want


def test_ix_lag_2():
    mom = _style("Momentum", 1.0, now=-2.0, worst=-20.0)
    assert iv.lag_extra([mom, _style("Quality", 1.0, now=-3.0, worst=-10.0)], mom) == ""                       # none
    one = _style("Value", 1.0, now=-12.34, worst=-12.34)
    assert _clean(iv.lag_extra([mom, one], mom)) == " Value is at its deepest too, 12.3% below its peak."
    two = [mom, one, _style("Alpha", 1.0, now=-6.05, worst=-6.05)]
    assert _clean(iv.lag_extra(two, mom)) == (" Value is at its deepest too, 12.3% below its peak. Alpha is at its "
                                               "deepest too, 6.1% below its peak.")
    back = _style("Value", 1.0, now=-1.0, worst=-38.75, recovered=pd.Timestamp("2026-07-10"), parent="Nifty 500")
    assert _clean(iv.lag_extra([mom, back], mom)) == (" Value fell 38.8% against the Nifty 500, from Jun 2024 to Mar 2025, "
                                                       "and was back by Jul 2026.")


def test_ix_lag_3():
    assert _note(iv.section_lag([_style("Momentum", 1.0)])) == (
        "The relative line divides the style index by its parent, 100 at launch: rising means the style is ahead. "
        "Below it, how far the line sits under its own best.")


# ── ix.yr.1, ix.yr.2 ──

@pytest.mark.parametrize("led, want", [
    ({"Value": (5, 8), "Quality": (6, 8), "Alpha": (3, 8)},
     "No style led its parent every whole year; quality came closest, 6 of 8."),
    ({"Value": (6, 8), "Quality": (6, 8), "Alpha": (3, 8)},
     "No style led its parent every whole year; value and quality came closest, 6 of 8 each."),
    ({"Value": (8, 8), "Quality": (6, 8)}, "Value led its parent in every whole year since launch."),
])
def test_ix_yr_1(led, want):
    assert _clean(iv.years_headline(led)) == want


def test_ix_yr_2():
    s = _style("Value", 1.0, years={2024: 3.0, 2025: -1.0, 2026: 2.0})
    assert _note(iv.section_years([s], NOV)) == ("Lead over the parent in each calendar year, in points of price return. "
                                                 "Each style starts with its first full year after launch.")


# ── ix.size.1 to ix.size.3 ──

def _size(size: str, name: str, fall: float, years=None) -> ip.SizeYears:
    return ip.SizeYears(size, name.lower().replace(" ", "_"), name, years or {2025: (5.0, fall), 2026: (2.0, -3.0)}, fall)


@pytest.mark.parametrize("small, large, want", [
    (-21.94, -11.1, "In a median year since 2017, the Nifty Smallcap 250's max drawdown was 21.9%, twice the Nifty 100's 11.1%."),
    (-30.0, -10.0, "In a median year since 2017, the Nifty Smallcap 250's max drawdown was 30.0%, 3.0 times the Nifty 100's 10.0%."),
    (-21.0, 0.0, "In a median year since 2017, the Nifty Smallcap 250 had the deepest max drawdown, 21.0%."),
    (-21.0, float("nan"), "In a median year since 2017, the Nifty Smallcap 250 had the deepest max drawdown, 21.0%."),
])
def test_ix_size_1(small, large, want):
    sizes = [_size("Large", "Nifty 100", large), _size("Small", "Nifty Smallcap 250", small)]
    assert _clean(iv.size_headline(sizes)) == want


def test_ix_size_2():
    sizes = [_size("Large", "Nifty 100", -11.1), _size("Small", "Nifty Smallcap 250", -21.9)]
    assert _note(iv.section_size(sizes, NOV)) == ("The bar is the calendar year's return; the dot is the max drawdown "
                                                  "within it. 2026 is year to date. Median of whole years since 2017: "
                                                  "Large Cap −11.1%, Small Cap −21.9%.")
    micro = _size("Micro", "Nifty Microcap 250", -18.9, {2022: (1.0, -20.0), 2025: (2.0, -18.0), 2026: (1.0, -2.0)})
    assert _note(iv.section_size(sizes + [micro], NOV)).endswith("Micro Cap −18.9% (Micro Cap from 2022).")


def test_ix_size_3():
    text = _text(html_of(iv.section_size([_size("Large", "Nifty 100", -11.1)], NOV)))
    assert ("One scale for all four, from 2017 (the Nifty Midcap 150 and Nifty Smallcap 250 start in NSE's file in "
            "Apr 2016; the Nifty Microcap 250 in May 2021).") in text


# ── ix.ev.1 to ix.ev.4 ──

def _row(name: str, r12: float | None, group: str = "Theme", late=None) -> ip.IndexRow:
    return ip.IndexRow(name.lower(), name, group, pd.Timestamp("2015-01-01"), {m: r12 for m in ip.WINDOWS}, None, None, late)


def _tm_frames(r12: float | None, late: bool = False) -> ip.Frames:
    idx = pd.DatetimeIndex([pd.Timestamp("2025-11-20"), NOV - pd.Timedelta(days=1), NOV])
    tm = [100.0, 100.0, np.nan if late else 100.0 * (1 + r12 / 100)]
    close = pd.DataFrame({"nifty_total_market": tm, "nifty_50": [1.0, 1.0, 1.0]}, index=idx)
    return ip.Frames(close, close * np.nan, close * np.nan, close * np.nan)


THEMES = [_row("Nifty IPO", 16.7), _row("Nifty India Defence", 3.0), _row("Nifty India Railways PSU", -24.7)]


@pytest.mark.parametrize("tm, themes, late, want", [
    (5.04, THEMES, False, "Over 12 months, Nifty Total Market is up 5.0%. Among themes, Nifty IPO leads, up 16.7%, and "
                          "Nifty India Railways PSU trails, down 24.7%."),
    (-3.0, THEMES[:1] + THEMES[2:], False, "Over 12 months, Nifty Total Market is down 3.0%. Among themes, Nifty IPO "
                                           "leads, up 16.7%, and Nifty India Railways PSU trails, down 24.7%."),
    (0.04, THEMES[:1], False, "Over 12 months, Nifty Total Market is unchanged. Nifty IPO is the only theme with 12 months."),
    (5.0, THEMES, True, "Nifty Total Market’s 20 Nov close is not in yet. Among themes, Nifty IPO leads, up 16.7%, and "
                        "Nifty India Railways PSU trails, down 24.7%."),
])
def test_ix_ev_1(tm, themes, late, want):
    f = _tm_frames(tm, late)
    assert _clean(iv.every_headline(f, {"Theme": themes}, NOV)) == want


def test_ix_ev_1_no_figures():
    f = ip.Frames(pd.DataFrame({"nifty_50": [1.0]}, index=[NOV]), *(pd.DataFrame(index=[NOV]),) * 3)
    assert iv.every_headline(f, {"Theme": [_row("Nifty New", None)]}, NOV) == \
        "NSE's 1 broad, theme and strategy indices over 12 months."


def test_ix_ev_2():
    f = _tm_frames(5.0)
    late = {"Theme": THEMES + [_row("Nifty B", None, late=NOV - pd.Timedelta(days=1))]}
    assert _note(iv.section_every(f, late, NOV)).endswith(
        "India VIX and the dollar Nifty are left out. NSE’s 20 Nov close for Nifty B is not in yet. Their figures read –.")
    assert _note(iv.section_every(f, {"Theme": THEMES}, NOV)).endswith("India VIX and the dollar Nifty are left out.")


@pytest.mark.parametrize("rows, want", [
    (THEMES, "Theme: 2 of 3 are up over 12 months; Nifty IPO leads and Nifty India Railways PSU trails."),
    (THEMES[1:], "Theme: 1 of 2 is up over 12 months; Nifty India Defence leads and Nifty India Railways PSU trails."),
    (THEMES[:2], "Theme: all are up over 12 months; Nifty IPO leads and Nifty India Defence trails."),
    ([_row("Nifty A", -1.0), _row("Nifty B", -2.0)], "Theme: none is up over 12 months; Nifty A leads and Nifty B trails."),
    (THEMES[:1], "Theme: Nifty IPO is up 16.7% over 12 months."),
    ([_row("Nifty New", None)], "Theme"),
])
def test_ix_ev_3(rows, want):
    assert _clean(iv.family_headline("Theme", rows)) == want


def test_ix_ev_4():
    assert iv.GROUP_NOTE == {
        "Broad market": "Size and breadth: Nifty Total Market, the large, mid and small company indices.",
        "Theme": "Ideas that cut across sectors: defence, manufacturing, PSUs, business groups, new listings.",
        "Strategy": "Rules-based selections and weightings: momentum, quality, value, low volatility, equal weight, dividends.",
    }
    assert "Ideas that cut across sectors" in _text(html_of(iv.section_every(_tm_frames(5.0), {"Theme": THEMES}, NOV)))


def test_ix_foot_1():
    f = _frames()
    foot = html_of(iv.page_parts(f))
    n = sum(len(v) for v in ip.every_index(f).values())
    assert f'<p class="dh-foot">Data to 20 Nov 2026 · NSE · {n} broad, theme and strategy indices</p>' in foot


def test_ix_empty_1(monkeypatch):
    seen = {}
    monkeypatch.setattr(iv.indices_data, "frames", lambda: None)
    monkeypatch.setattr(iv.st, "html", lambda *a, **k: None)
    monkeypatch.setattr(iv.kit, "page_empty", lambda title, lede, **k: seen.update(title=title, lede=lede, **k))
    iv.render_indices_view()
    assert seen == {"title": "No index data yet.", "kicker": "Indices",
                    "lede": "The copy of NSE’s daily index files this page reads is not in yet; the page fills once it is."}
    assert (seen["title"], seen["lede"]) == (mw.NO_INDEX_DATA, mw.NO_INDEX_DATA_WHY)


# ══ Sectors (§5) ════════════════════════════════════════════════════════════

def _lead(name, l6, l1, *, l6_3m=-1.0, stocks=12, r6=8.0, l12=2.0):
    return sp.Lead(name, stocks, l6_3m, l6, l6, l1, 0.5, sp.group_of(l6, l1), {1: 1.0, 3: 2.0, 6: r6, 12: 9.0}, -3.0, l12)


def _leads(rows, *, gap=None, mret=None, left=None):
    rows = sorted(rows, key=lambda r: -r.lead6)
    return sp.Leads(NOV, pd.Timestamp("2026-10-20"), pd.Timestamp("2026-08-20"), rows, {}, pd.Series(dtype=float),
                    {r.name: r.stocks for r in rows}, mret or {1: 2.0, 3: 4.0, 6: 3.0, 12: 10.0},
                    {"1": 1.0, "3": 0.5, "6": 2.0, "12": 1.0, "6_1m": 1.5, "6_3m": 1.0} if gap is None else gap, left or {})


SH = staticmethod(lambda n: n)
ALL = [_lead("Healthcare", 5.1, 1.0), _lead("Capital Goods", 4.0, 2.0), _lead("Financials", 3.0, 0.5),
       _lead("Auto", 2.0, 0.1), _lead("Metals", -3.0, 1.0), _lead("IT", -6.4, -1.0), _lead("Chemicals", -8.0, -2.0)]


def _nse(gaps, groups=()):
    return {"as_of": NOV, "gaps": gaps, "groups": list(groups), "pairs": {}}


def _gap(sector, ours3, nse3, gap1=-1.0, index=None):
    return sp.Gap(sector, index or f"Nifty {sector}", pd.Timestamp("2015-01-01"), ours3, nse3, ours3 - nse3, 1.0, 1.0 - gap1, gap1)


# ── se.uni.1 and se.head.1 ──

@pytest.mark.parametrize("uni", UNIS)
@pytest.mark.parametrize("rows, want", [
    (ALL, "Healthcare, Capital Goods, Financials and 1 more lead the {uni} over 6 months and 1 month; Chemicals and IT "
          "trail it by 6 points or more over 6 months."),
    (ALL[:3] + ALL[5:], "Healthcare, Capital Goods and Financials lead the {uni} over 6 months and 1 month; Chemicals and "
                        "IT trail it by 6 points or more over 6 months."),
    (ALL[:1] + ALL[4:], "Healthcare leads the {uni} over 6 months and 1 month; Chemicals and IT trail it by 6 points or "
                        "more over 6 months."),
    (ALL[4:], "No sector leads the {uni} on both 6 months and 1 month; Chemicals and IT trail it by 6 points or more over "
              "6 months."),
    (ALL[:2], "Healthcare and Capital Goods lead the {uni} over 6 months and 1 month."),
])
def test_se_head_1(uni, rows, want):
    assert _clean(sv.head_title(_leads(rows), SH, "sector", uni)) == want.format(uni=uni)


# ── se.head.2 ──

@pytest.mark.parametrize("uni", UNIS)
def test_se_head_2(uni):
    gaps = [_gap("Healthcare", 1.0, 2.0, gap1=-1.0), _gap("IT", 1.0, 0.5, gap1=0.5), _gap("Auto", 1.0, 3.0, gap1=-2.0)]
    ld = _leads(ALL)
    assert _clean(sv.head_lede(ld, "sector", _nse(gaps), uni)) == (
        f"4 of 7 sectors are ahead of the {uni}, equal-weighted, over both windows. Over 1 month, Nifty Total Market "
        f"rose 1.0% and the {uni}, equal-weighted, rose 2.0%. 2 of 3 sector indices beat their sector’s ranked stocks "
        "over the month. Price returns, to the 20 Nov 2026 close.")
    # NSE part missing (a TradingView grouping, the list): the first and last sentences only; 0 and 1 ahead.
    assert sv.head_lede(_leads(ALL[4:]), "sector", None, uni) == (
        f"None of 3 sectors is ahead of the {uni}, equal-weighted, over both windows. Price returns, to the 20 Nov 2026 close.")
    assert sv.head_lede(_leads(ALL[:1] + ALL[4:]), "industry", None, uni).startswith(f"1 of 4 industries is ahead of the {uni}")


def test_se_head_2_all_none_fell_and_late():
    ld = _leads(ALL, mret={1: -2.0, 3: 1.0, 6: 3.0}, gap={"1": -1.0})
    all_beat = [_gap("Healthcare", 1.0, 2.0), _gap("IT", 1.0, 3.0)]
    late = sp.SectorGroup("Banks", 10, None, [sp.IndexLine("b", "Nifty Bank", True, pd.Timestamp("2010-01-01"),
                                                            {}, None, None, NOV - pd.Timedelta(days=1))])
    t = _clean(sv.head_lede(ld, "sector", _nse(all_beat, [late])))
    assert "Over 1 month, Nifty Total Market fell 1.0% and the 750, equal-weighted, fell 2.0%." in t
    assert "All 2 sector indices beat their sector’s ranked stocks over the month." in t
    assert t.endswith("NSE’s 20 Nov close for Nifty Bank is not in yet. Price returns, to the 20 Nov 2026 close.")
    none_beat = [_gap("Healthcare", 3.0, 2.0, gap1=1.0), _gap("IT", 3.0, 2.0, gap1=1.0)]
    assert "None of 2 sector indices beat their sector’s ranked stocks" in sv.head_lede(ld, "sector", _nse(none_beat))


# ── se.lead.1 to se.lead.6 ──

@pytest.mark.parametrize("rows, want", [
    (ALL, "4 sectors lead on both 6 months and 1 month; 2 trail on both."),
    (ALL[:1] + ALL[5:6], "1 sector leads on both 6 months and 1 month; 1 trails on both."),
    (ALL[4:5], "No sector leads on both 6 months and 1 month; none trails on both."),
    (ALL[:4] + [_lead("IT", -6.4, -1.0, l6_3m=2.34)],
     "4 sectors lead on both 6 months and 1 month; 1 trails on both. IT is among them; its 6-month lead was 2.3 points on 20 Aug."),
])
def test_se_lead_1(rows, want):
    assert _clean(sv.lead_headline(_leads(rows), SH, "sector")) == want


@pytest.mark.parametrize("uni", UNIS)
def test_se_lead_2(uni):
    rows = ALL[:2] + [_lead("New", 1.0, 1.0, l12=None), _lead("Newer", 1.0, -1.0, l12=None)]
    note = _note(sv.section_lead(_leads(rows), SH, "sector", True, uni))
    assert note == (f"Lead: the sector’s return less the {uni}’s over the same sessions, both equal-weighted, in pts. Groups: "
                    "ahead or behind over 6 months and over the last month; the 3M and 12M leads are shown "
                    "beside them and do not move a sector between groups. – in 12M: too new (under 12 months of prices): "
                    "New and Newer.")
    assert _note(sv.section_lead(_leads(ALL[:1]), SH, "sector", True, uni)).endswith("between groups.")       # none short
    one = _note(sv.section_lead(_leads(ALL[:1] + rows[2:3]), SH, "sector", True, uni))
    assert one.endswith("– in 12M: too new (under 12 months of prices): New.")


def test_se_lead_3():
    parts = html_of(sv.section_lead(_leads(ALL), SH, "sector"))
    items = [_clean(x) for x in re.findall(r"<li>(.*?)</li>", parts)]
    assert items == ["Nearest to moving ahead over 6 months: Metals −3.0 points; IT −6.4 points; Chemicals −8.0 points.",
                     "Nearest to falling behind: Auto +2.0 points; Financials +3.0 points; Capital Goods +4.0 points."]
    assert "Which sizes lead, against Nifty Total Market at 1M, 3M and 6M: on the Dashboard, " in _text(parts)
    ahead_only = _text(html_of(sv.section_lead(_leads(ALL[:2]), SH, "sector")))                   # none on one side
    assert "Nearest to moving ahead" not in ahead_only and "Nearest to falling behind: Capital Goods +4.0 points" in ahead_only


@pytest.mark.parametrize("uni", UNIS)
def test_se_lead_4(uni):
    ld = _leads(ALL, left={"Utilities": 4, "Forest": 1})
    assert _clean(sv.lead_example(ld, SH, uni)) == (
        f"Healthcare’s 12 stocks returned +8.0% over 6 months and the {uni} +3.0%, a lead of +5.1 points.")
    assert sv.lead_example(_leads([_lead("Financials", 2.0, 1.0)]), SH, uni).startswith("Financials’ 12 stocks returned")
    text = _text(html_of(sv.section_lead(ld, SH, "sector", True, uni)))
    assert (f"A sector here is the equal-weighted index of its ranked stocks, rebalanced daily, and so is the {uni}. 7 have "
            "five or more ranked stocks and are shown; left out with fewer: Utilities (4), Forest (1). Comparing like "
            "with like keeps a rally of large companies from reading as every one lagging; that gap is the first row, "
            f"the {uni} against Nifty Total Market. Healthcare’s 12 stocks returned") in text
    none_left = _text(html_of(sv.section_lead(_leads(ALL), SH, "sector", True, uni)))
    assert "7 have five or more ranked stocks and are shown. Comparing" in none_left


def test_se_lead_5():
    text = _text(html_of(sv.section_lead(_leads(ALL), SH, "sector")))
    assert ("Each line is 1 point; the bar is the 6M lead now, the triangle the same reading a month ago, and the "
            "numbers the reading 3 months ago, a month ago, now, then the 1M, 3M and 12M leads now. "
            "Describing is not forecasting: a lead on both windows has not been tested here as a signal for the next "
            "month.") in text


@pytest.mark.parametrize("uni", UNIS)
def test_se_lead_6(uni):
    spec = next(p for p in sv.section_lead(_leads(ALL), SH, "sector", True, uni) if isinstance(p, Chart)).spec
    assert spec["rows"][0]["name"] == f"The {uni} against Nifty Total Market"
    gaps = [_gap("Healthcare", 1.0, 2.0)]
    broad = next(p for p in sv.section_broad(_leads(ALL), _nse(gaps), SH, uni) if isinstance(p, Chart)).spec
    assert broad["rows"][0]["name"] == f"The {uni} against Nifty Total Market"


# ── se.broad.1, se.broad.2 ──

@pytest.mark.parametrize("uni", UNIS)
@pytest.mark.parametrize("gaps, want", [
    ([_gap("Financials", 2.0, 5.04, index="Nifty Financial Services"), _gap("Healthcare", 3.0, 1.0)],
     "Nifty Financial Services rose 5.0% over 3 months, while the sector’s 12 ranked stocks rose 2.0%. "
     "Only Financials is narrower than the {uni} against Nifty Total Market."),
    ([_gap("Financials", -2.0, -1.0), _gap("IT", -1.0, 0.0), _gap("Auto", 3.0, 1.0)],
     "Nifty Financials fell 1.0% over 3 months, while the sector’s 12 ranked stocks fell 2.0%. "
     "2 sectors are narrower than the {uni} against Nifty Total Market: Financials and IT."),
    ([_gap("Auto", 3.0, 1.0)],
     "Nifty Auto rose 1.0% over 3 months, while the sector’s 12 ranked stocks rose 3.0%. "
     "No sector is narrower than the {uni} against Nifty Total Market."),
])
def test_se_broad_1(uni, gaps, want):
    assert _clean(sv.broad_headline(_leads(ALL), gaps, SH, uni)) == want.format(uni=uni)


def test_se_broad_1_colour_on_the_verdict_only():
    h2 = sv.broad_headline(_leads(ALL), [_gap("Financials", 2.0, 5.0), _gap("Healthcare", 3.0, 1.0)], SH)
    assert h2.startswith("Nifty Financials rose 5.0%") and '<span class="dh-down">Only Financials' in h2


def test_se_broad_2():
    gaps = [_gap("Healthcare", 3.0, 1.0)]
    late = sp.SectorGroup("Banks", 10, None, [sp.IndexLine("b", "Nifty Bank", True, pd.Timestamp("2010-01-01"),
                                                            {}, None, None, NOV - pd.Timedelta(days=1))])
    assert _note(sv.section_broad(_leads(ALL), _nse(gaps, [late]), SH)).endswith(
        "pts = percentage points: 12% − 8% = 4 pts. NSE’s 20 Nov close for Nifty Bank is not in yet. Its sector is left out here.")
    assert _note(sv.section_broad(_leads(ALL), _nse(gaps), SH)).endswith("pts = percentage points: 12% − 8% = 4 pts.")


# ── se.ix.1, se.ix.2, se.only.1 ──

def _ix(name, r12, young=False, late=None):
    return sp.IndexLine(name.lower(), name, False, pd.Timestamp("2026-06-15" if young else "2010-01-01"),
                        {m: (None if young or late else r12) for m in ip.WINDOWS}, None, 20.0, late)


@pytest.mark.parametrize("lines, want", [
    ([_ix("Nifty IT", 12.0), _ix("Nifty Bank", 4.0), _ix("Nifty Pharma", -3.04), _ix("Nifty New", None, young=True)],
     "Over 12 months, Nifty IT leads NSE’s sector indices, up 12.0%, and Nifty Pharma trails, down 3.0%. 1 of the 4 is "
     "younger than 12 months."),
    ([_ix("Nifty IT", -1.0), _ix("Nifty Bank", -4.0)],
     "Over 12 months, Nifty IT leads NSE’s sector indices, down 1.0%, and Nifty Bank trails, down 4.0%. None of the 2 is "
     "younger than 12 months."),
    ([_ix("Nifty IT", 1.0), _ix("Nifty Bank", -4.0), _ix("Nifty A", None, young=True), _ix("Nifty B", None, young=True)],
     "Over 12 months, Nifty IT leads NSE’s sector indices, up 1.0%, and Nifty Bank trails, down 4.0%. 2 of the 4 are "
     "younger than 12 months."),
    ([_ix("Nifty A", None, young=True)], "NSE’s 1 sector indices, each beside its sector."),
])
def test_se_ix_1(lines, want):
    assert _clean(sv.indices_headline(lines)) == want


def test_se_ix_2():
    grp = sp.SectorGroup("IT", 10, None, [_ix("Nifty IT", 5.0), _ix("Nifty B", None, late=NOV - pd.Timedelta(days=1))])
    note = _note(sv.section_indices(_leads(ALL), _nse([], [grp]), SH))
    assert note.startswith("All 2 of NSE’s sector indices, each under the sector it belongs to;")
    assert note.endswith("Themes, strategies and broad indices are on Indices. NSE’s 20 Nov close for Nifty B is not in yet. "
                         "Their figures read –.")
    on_time = sp.SectorGroup("IT", 10, None, [_ix("Nifty IT", 5.0)])
    assert _note(sv.section_indices(_leads(ALL), _nse([], [on_time]), SH)).endswith("broad indices are on Indices.")


def test_se_only_1():
    assert sv.NSE_ONLY == "NSE’s indices match NSE’s sectors; switch to NSE sectors to see them."
    assert sv.TV_ONLY == ("This list’s stocks carry TradingView’s sectors, so NSE’s sector indices, built on NSE’s sectors, "
                          "are not set beside them.")
    assert _clean(sv.section_only_nse(True)[0]) == "NSE’s sector indices" + sv.NSE_ONLY


# ── se.mo.1 to se.mo.3 ──

def _months(runs: dict[str, list[float]]) -> pd.DataFrame:
    labels = ["Jul 2026", "Aug 2026", "Sep 2026", "Oct 2026", "Nov so far"]
    out = pd.DataFrame.from_dict(runs, orient="index", columns=labels)

    def run(vals):
        n, sign = 0, 0
        for v in reversed(vals[:-1]):
            s = 1 if v > 0 else -1 if v < 0 else 0
            if not s or (sign and s != sign):
                break
            sign, n = s, n + 1
        return sign * n
    out["run"] = [run(v) for v in runs.values()]
    out["total"] = [sum(v[:-1]) for v in runs.values()]
    return out


@pytest.mark.parametrize("uni", UNIS)
@pytest.mark.parametrize("runs, h2, ex", [
    ({"Auto": [-0.4, 0.5, 0.8, 1.2, 0.1], "IT": [1.0, -1.0, 1.0, -1.0, 0.0]},
     "Auto has beaten the {uni} in each of the last 3 completed months, the longest run.",
     "For example, Auto: Oct +1.2, Sep +0.8 and Aug +0.5 points, all ahead of the {uni}; Jul was −0.4, so the count stops "
     "there and Run reads 3 ahead. Its 12 months, +2.1 points, is the 12 completed months added up."),
    ({"Auto": [0.4, -0.5, 0.8, 1.2, 0.1], "IT": [1.0, -1.0, 1.0, -1.0, 0.0]},
     "Auto has beaten the {uni} in September and October, the longest run.",
     "For example, Auto: Oct +1.2 and Sep +0.8 points, all ahead of the {uni}; Aug was −0.5, so the count stops there and "
     "Run reads 2 ahead. Its 12 months, +1.9 points, is the 12 completed months added up."),
    ({"Auto": [0.4, 0.5, -0.8, -1.2, 0.1], "IT": [0.5, 0.2, -1.0, -1.0, 0.0]},
     "Auto and IT have trailed the {uni} in September and October, the longest runs.",
     "For example, Auto: Oct −1.2 and Sep −0.8 points, all behind the {uni}; Aug was +0.5"),
    ({"Auto": [0.4, -0.5, -0.8, 1.2, 0.1], "IT": [1.0, 1.0, -1.0, 1.0, 0.0]},
     "Auto and IT beat the {uni} in October, and no sector has a longer run.",
     "For example, Auto: Oct +1.2 points, ahead of the {uni}; Sep was −0.8"),
    ({"Auto": [0.4, 0.002, 0.8, 1.2, 0.1]},
     "Auto has beaten the {uni} in each of the last 4 completed months, the longest run.",
     "Jul +0.4 points, all ahead of the {uni}. Its 12 months"),
    ({"Auto": [0.4, 0.5, -0.004, 1.2, 0.1]},
     "Auto beat the {uni} in October, and no sector has a longer run.",
     "Sep was behind by less than 0.05, so the count stops there and Run reads 1 ahead."),
    ({"Auto": [0.0, 0.0, 0.0, 0.0, 0.1]}, "No sector has beaten or trailed the {uni} two months running.", ""),
])
def test_se_mo_1_and_2(uni, runs, h2, ex):
    got_h2, got_ex = sv.months_headline(_months(runs), SH, "sector", uni)
    assert _clean(got_h2) == h2.format(uni=uni)
    assert ex.format(uni=uni) in got_ex
    if got_ex:
        _clean(got_ex)


def test_se_mo_3():
    # Rule 11: counts are figures, "the 12 completed months" as in se.mo.2.
    parts = sv.section_months(_months({"Auto": [0.4, 0.5, 0.8, 1.2, 0.1]}), SH, "sector", "1000")
    assert _text(re.findall(r'<p class="dh-note">(.*?)</p>', html_of(parts), re.S)[0]) == ("Each cell is the sector’s lead over the 1000 in that calendar month, both equal-weighted, in "
                            "pts; the last month column is the month so far. Run counts completed months in a row on the "
                            "same side; the last column adds the 12 completed months. Today’s members throughout.")


# ── se.map.1 to se.map.3 ──

def _pt(name, x1, y0, y1):
    return {"name": name, "x1": x1, "x0": 0.0, "y0": y0, "y1": y1, "then": "20 Oct", "now": "20 Nov"}


@pytest.mark.parametrize("uni", UNIS)
@pytest.mark.parametrize("rows, want", [
    ([_pt("Auto", 3.0, 40, 50), _pt("IT", -2.0, 50, 40), _pt("Metals", 1.0, 30, 30)],
     "Breadth rose in 1 of 3 sectors from 20 Oct to 20 Nov. Auto gained most on the {uni}, IT lost most."),
    ([_pt("Auto", 3.0, 50, 40), _pt("IT", 3.04, 50, 40), _pt("Metals", 1.0, 30, 30)],
     "Breadth rose in none of 3 sectors from 20 Oct to 20 Nov. Auto and IT gained most on the {uni}, Metals lost most."),
    ([_pt("Auto", 3.0, 40, 50), _pt("IT", -2.0, 30, 40)],
     "Breadth rose in all 2 sectors from 20 Oct to 20 Nov. Auto gained most on the {uni}, IT lost most."),
])
def test_se_map_1(uni, rows, want):
    assert _clean(sv.map_headline(rows, SH, "sector", uni)) == want.format(uni=uni)


def test_se_map_2():
    views = {"200-1": [_pt("Auto", 3.0, 40, 50), _pt("IT", -2.0, 50, 40)]}
    assert _note(sv.section_map(views, SH, "sector", "1000")) == (
        "Across: the sector’s lead over the 1000 over the period, both equal-weighted, in pts (for 1M, the one-month lead "
        "above). Up: the share of its stocks above the EMA. The hollow dot is the reading a period ago, the filled dot "
        "today. The leader is blue, the laggard rust, the rest grey; click one, or choose it in the list, to fade the rest, "
        "and click it again to show all. Today’s members, five or more stocks each.")


@pytest.mark.parametrize("uni", UNIS)
def test_se_map_3(uni):
    t = sv.map_text(uni)
    assert t["q_across"] == f"Across: did it beat the {uni} over the {{p}}?"
    assert t["a_market"] == f"The {uni}, built the same way over the same closes:"
    assert t["r_ru"] == f"it beat the {uni} by more and more of its stocks are in an uptrend: broad strength building."
    assert t["fell"] == "breadth fell in {n} of {of}." and not any("750" in v for v in t.values() if uni != "750")
    js = (ROOT / "static" / "dash_charts.js").read_text(encoding="utf-8")
    assert "T.fell.replace('{n}', fell === 0 ? 'none' : fell)" in js                      # n = 0: "fell in none of 19"
    views = {"200-1": [_pt("Auto", 3.0, 40, 50)]}
    chart = next(p for p in sv.section_map(views, SH, "sector", uni) if isinstance(p, Chart))
    assert chart.spec["text"]["x_axis"] == f"lead over the {uni}, pts →"


# ── se.in.1, se.in.2 ──

def _share(name, now, b1=40.0):
    return sp.Share(name, 10, 30.0, b1, now)


@pytest.mark.parametrize("uni", UNIS)
@pytest.mark.parametrize("allr, rest, want", [
    (_share("All", 47.0, 37.0), [_share("Auto", 60.0), _share("IT", 40.0), _share("Metals", 20.0)],
     "47% of the {uni}’s stocks are above their 200D EMA, up from 37% a month ago. Auto has the most, 60%, and Metals "
     "the fewest, 20%."),
    (_share("All", 37.0, 47.0), [_share("Auto", 60.0), _share("IT", 60.4), _share("Metals", 20.0)],
     "37% of the {uni}’s stocks are above their 200D EMA, down from 47% a month ago. Auto and IT have the most, 60%, "
     "and Metals the fewest, 20%."),
    (_share("All", 47.2, 46.8), [_share("Auto", 60.0), _share("IT", 20.0), _share("Metals", 19.6)],
     "47% of the {uni}’s stocks are above their 200D EMA, the same as 47% a month ago. Auto has the most, 60%, and IT "
     "and Metals the fewest, 20%."),
    (_share("All", 47.0, None), [_share("Auto", 60.0), _share("IT", 20.0)],
     "47% of the {uni}’s stocks are above their 200D EMA. Auto has the most, 60%, and IT the fewest, 20%."),
])
def test_se_in_1(uni, allr, rest, want):
    assert _clean(sv.inside_headline(allr, rest, SH, uni)) == want.format(uni=uni)


def test_se_in_2(monkeypatch):
    from src.engine.track_record import TRACK_RECORD_CONFIG as cfg
    shares = [sp.Share("All ranked stocks", 750, 40.0, 37.0, 47.0), _share("Auto", 60.0), _share("Metals", 20.0)]
    rank = pd.DataFrame({"Symbol": ["A"], "3M Return": [1.0], "Industry": ["Auto"]})
    note = _note(sv.section_inside(None, shares, pd.DataFrame(), rank, SH, "sector", "1000"))
    assert "Then the ranking table’s own flags: above the 50D EMA, within 20% of the 52-week high, passing both" in note
    assert "stocks that have since left the 1000. Sort by any heading." in note
    assert note.endswith("– in the filter columns and Leaders: fewer than 5 of its stocks are ranked today (Auto, Metals).")
    monkeypatch.setitem(cfg, "high_pct", 0.75)
    assert "within 25% of the 52-week high" in _note(sv.section_inside(None, shares, pd.DataFrame(), rank, SH, "sector"))


# ── se.stk.1, se.group.1, se.dead.1 ──

def test_se_stk_1():
    assert sv.stocks_heading("Healthcare", 12) == "Healthcare’s 12 ranked stocks, best rank first."
    assert sv.stocks_heading("Capital Goods", 1) == "Capital Goods’ 1 ranked stocks, best rank first."
    src = (ROOT / "src" / "ui" / "views" / "sector_view.py").read_text(encoding="utf-8")
    assert src.index("slot = st.empty()") < src.index('st.selectbox(f"Pick a {noun}"') < src.index("stocks_heading(sh(pick_name)")


def test_se_group_1():
    assert sv.GROUP_WORDS == {
        "ahead on both": ("Ahead on both", "ahead over 6 months and over 1 month"),
        "gaining": ("Gaining", "behind over 6 months, ahead over 1 month"),
        "fading": ("Fading", "ahead over 6 months, behind over 1 month"),
        "behind on both": ("Behind on both", "behind over 6 months and over 1 month")}


def test_se_dead_1():
    for gone in ("leadership_explainer", "_reading", "_words", "_of", "for_universe"):
        assert not hasattr(sv, gone), gone


# ── se.uni.1: every sentence on the page, on the three systems ──

@pytest.mark.parametrize("uni", UNIS)
def test_se_uni_1_the_whole_page_names_the_systems_list(uni):
    ld = _leads(ALL)
    months = _months({"Auto": [0.4, 0.5, 0.8, 1.2, 0.1]})
    views = {"200-1": [_pt("Auto", 3.0, 40, 50), _pt("IT", -2.0, 50, 40)]}
    shares = [sp.Share("All ranked stocks", 750, 40.0, 37.0, 47.0), _share("Auto", 60.0), _share("IT", 20.0)]
    model = {"ld": ld, "months": months, "shares": shares, "map": views,
             "nse": _nse([_gap("Healthcare", 3.0, 1.0)], [sp.SectorGroup("Healthcare", 12, ALL[0], [_ix("Nifty Pharma", 4.0)])])}
    rank = pd.DataFrame({"Symbol": ["A", "B"], "3M Return": [1.0, 2.0], "Industry": ["Auto", "IT"], "Rank": [1, 2]})
    parts = sv.page_parts(model, rank, "Industry", True, uni)
    text = _text(html_of(parts)) + " ".join(str(p.spec) for p in parts if isinstance(p, Chart))
    if uni != "750":
        assert "750" not in text.replace("750 stocks", "")
    assert f"the {uni}" in text and f"The {uni} against Nifty Total Market" in text
    for h in re.findall(r"<h[12][^>]*>(.*?)</h[12]>", html_of(parts), re.S):
        _clean(h)


def test_s229_a_click_on_the_map_picks_a_sector_out():
    """S229 (owner, 25 Nov 2026): a click faded the others before the 22 Nov rebuild; the rebuild kept only the list."""
    js = (Path(__file__).resolve().parents[1] / "static" / "dash_charts.js").read_text(encoding="utf-8")
    lmap = js[js.index("R.lmap ="):js.index("R.stable =")]
    assert "el.addEventListener('pointerup'" in lmap and "pick.value = focus" in lmap
    assert "opacity: on(r) ? 1 : .22" in lmap


def test_configuration_carries_the_foot_line_its_text_points_to():
    """Data health says the prices' date "is in the line at the foot of the page"; the page had no such line, so with a
    late source (the pill then drops "closes of") it named no session (found 25 Nov 2026)."""
    src = (Path(__file__).resolve().parents[1] / "src" / "ui" / "views" / "config_view.py").read_text(encoding="utf-8")
    assert "in the line at the foot of the page" in src
    assert 'as_of=prices.get("date") if prices else None' in src
