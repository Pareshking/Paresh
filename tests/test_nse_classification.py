"""NSE's four-level classification from Screener.in, and the Screener's Sector column (S189 item 6 (a))."""

from datetime import date

import pandas as pd

from scripts import nse_classification as nc
from src.engine import extra_universe as xu
from src.loaders import nse_classification as reader

# Saved from https://www.screener.in/company/SANSERA/ on 24 Nov 2026 (the peer-comparison breadcrumb).
SANSERA = """
            <p class="sub">
              <i class="icon-globe"></i>
              <a href="/market/IN02/"
                 target="_blank"
                 title="Broad Sector">Consumer Discretionary</a>
              <i class="icon-right"></i>
              <i class="icon-chart-pie"></i>
              <a href="/market/IN02/IN0201/"
                 target="_blank"
                 title="Sector">Automobile and Auto Components</a>
              <i class="icon-right"></i>
              <i class="icon-industry"></i>
              <a href="/market/IN02/IN0201/IN020102/"
                 target="_blank"
                 title="Broad Industry">Auto Components</a>
              <i class="icon-right"></i>
              <i class="icon-tools-1"></i>
              <a href="/market/IN02/IN0201/IN020102/IN020102001/"
                 target="_blank"
                 title="Industry">Auto Components &amp; Equipments</a>
            </p>
"""


class _Resp:
    def __init__(self, status=200, text="", payload=None):
        self.status_code, self.text, self._p = status, text, payload

    def json(self):
        return self._p


def test_parse_reads_the_four_levels_and_unescapes():
    assert nc.parse(SANSERA) == {
        "Macro": "Consumer Discretionary", "Sector": "Automobile and Auto Components",
        "Industry": "Auto Components", "Basic_Industry": "Auto Components & Equipments"}


def test_parse_without_a_sector_is_none():
    assert nc.parse("<html><a href='/company/X/'>X</a></html>") is None
    assert nc.parse('<a href="/market/IN02/" title="Broad Sector">Energy</a>') is None


def test_due_takes_missing_and_stale_rows_only():
    existing = pd.DataFrame({"Symbol": ["OLD", "NEW", "BAD"], "Checked": ["2026-07-01", "2026-11-20", ""]})
    got = nc.due(existing, ["NEW", "OLD", "BAD", "NONE"], date(2026, 11, 24), max_age_days=90)
    assert got == ["BAD", "NONE", "OLD"]
    assert nc.due(existing, ["NEW", "OLD"], date(2026, 11, 24), everything=True) == ["NEW", "OLD"]
    # A cap takes the missing first, then the oldest.
    older = pd.DataFrame({"Symbol": ["X", "Y"], "Checked": ["2026-05-01", "2026-03-01"]})
    assert nc.due(older, ["X", "Y", "Z"], date(2026, 11, 24), limit=2) == ["Z", "Y"]


def test_merge_overwrites_by_symbol_and_sorts():
    existing = pd.DataFrame([{c: "" for c in nc.COLUMNS} | {"Symbol": s, "Sector": "old"} for s in ("B", "A")])
    out = nc.merge(existing, [{"Symbol": "B", "Sector": "new", "Checked": "2026-11-24"}])
    assert out["Symbol"].tolist() == ["A", "B"]
    assert out.set_index("Symbol").loc["B", "Sector"] == "new"
    assert list(out.columns) == nc.COLUMNS


def test_fetch_falls_back_to_search_by_id_then_to_an_id_twin(monkeypatch):
    monkeypatch.setattr(nc.time, "sleep", lambda s: None)
    pages = {"https://www.screener.in/company/NEWSYM/": _Resp(200, SANSERA),
             "https://www.screener.in/company/NEWSYM/consolidated/": _Resp(200, SANSERA)}

    def get(url, timeout, headers):
        assert headers == nc.UA
        if "/api/company/search/" in url:
            assert "q=Acme%20Gears" in url
            return _Resp(200, payload=[{"id": 9, "name": "Other", "url": "/company/OTHER/"},
                                       {"id": 7, "name": "Acme Gears", "url": "/company/NEWSYM/consolidated/"}])
        return pages.get(url, _Resp(404))

    row = nc.fetch_one("OLDSYM", "Acme Gears Ltd.", {"OLDSYM": "7"}, get=get, today=date(2026, 11, 24))
    assert row["Sector"] == "Automobile and Auto Components"
    assert row["Source"] == "screener.in/company/NEWSYM/"
    # No name and no search hit: the id map's other ticker for the same company.
    row = nc.fetch_one("OLDSYM", "", {"OLDSYM": "7", "NEWSYM": "7"}, get=get)
    assert row["Source"] == "screener.in/company/NEWSYM/"
    assert nc.fetch_one("GONE", "", {}, get=get) is None


def test_a_search_hit_needs_the_same_id_or_the_same_name():
    hits = [{"id": 1, "name": "Acme Gears Ltd", "url": "/company/A/"}]
    assert nc.pick_hit(hits, "2", "Acme Gears Ltd.") is None
    assert nc.pick_hit(hits, None, "ACME GEARS LIMITED") == "/company/A/"
    assert nc.pick_hit(hits, None, "Acme") is None


def test_retries_on_429_and_stops_on_403(monkeypatch):
    monkeypatch.setattr(nc.time, "sleep", lambda s: None)
    answers = iter([_Resp(429), _Resp(503), _Resp(200, SANSERA)])
    assert nc._get("u", lambda url, timeout, headers: next(answers), pause=0).status_code == 200
    try:
        nc._get("u", lambda url, timeout, headers: _Resp(403), pause=0)
    except nc.Blocked:
        pass
    else:
        raise AssertionError("403 must stop the run")


def test_compare_counts_agreement_with_nse_lists(tmp_path):
    lst = tmp_path / "list.csv"
    lst.write_text("Company Name,Industry,Symbol\nA,\"Oil Gas & Consumable Fuels\",A\nB,Power,B\nC,Realty,C\n")
    cls = pd.DataFrame({"Symbol": ["A", "B"], "Sector": ["Oil, Gas & Consumable Fuels", "Utilities"]})
    r = nc.compare(cls, {"x": str(lst)})["x"]
    assert (r["checked"], r["agree"], r["missing"]) == (2, 1, 1)
    assert r["mismatches"] == [("B", "Power", "Utilities")]


def test_the_committed_file_has_its_columns_sorted():
    frame = nc.load()
    assert list(frame.columns) == nc.COLUMNS
    assert frame["Symbol"].tolist() == sorted(frame["Symbol"])
    assert frame["Symbol"].is_unique


# ── The reader ──────────────────────────────────────────────────────────────


def _files(tmp_path):
    cls = tmp_path / "cls.csv"
    cls.write_text("Symbol,Macro,Sector,Industry,Basic_Industry,Source,Checked\n"
                   "NANO1,Healthcare,Healthcare,Pharma,Pharmaceuticals,s,2026-11-24\n"
                   "BIG,Energy,\"Oil, Gas & Consumable Fuels\",x,y,s,2026-11-24\n")
    tm = tmp_path / "tm.csv"
    tm.write_text("Company Name,Industry,Symbol\nBig Ltd,Oil Gas & Consumable Fuels,BIG\n")
    n1000 = tmp_path / "n1000.csv"
    n1000.write_text("Company Name,Industry,Symbol\nMid Ltd,\"Media, Entertainment & Publication\",MID\n")
    return reader.sector_map(str(cls), str(tm), str(n1000))


def test_sector_map_prefers_nse_lists_and_uses_the_750_spelling(tmp_path):
    m = _files(tmp_path)
    assert m["BIG"] == "Oil Gas & Consumable Fuels"
    assert m["MID"] == "Media Entertainment & Publication"
    assert m["NANO1"] == "Healthcare"


def test_screener_copy_shows_nse_sector_and_falls_back(tmp_path):
    m = _files(tmp_path)
    rank = pd.DataFrame({"Symbol": ["NANO1", "UNKNOWN", "BIG"], "Rank": [1, 2, 3],
                         "Industry": ["Health Technology", "Process Industries", "Energy Minerals"]})
    before = rank.copy()
    out = reader.with_nse_sectors(rank, xu.SYSTEM_NANO, m, min_coverage=0.5)
    assert out["Industry"].tolist() == ["Healthcare", "Unclassified", "Oil Gas & Consumable Fuels"]   # not in the file: "Unclassified" (S226)
    # The ranking's own frame (the model plan's sector cap) is not touched.
    pd.testing.assert_frame_equal(rank, before)
    assert reader.with_nse_sectors(rank, xu.SYSTEM_750, m) is rank


def test_too_few_nse_sectors_leave_the_column_as_it_was():
    rank = pd.DataFrame({"Symbol": ["A", "B", "C"], "Industry": ["Finance", "Finance", "Finance"]})
    assert reader.with_nse_sectors(rank, xu.SYSTEM_NANO, {"A": "Financial Services"}) is rank
    out = reader.with_nse_sectors(rank, xu.SYSTEM_NANO, {"A": "Financial Services", "B": "Realty", "C": "Power"})
    assert out["Industry"].tolist() == ["Financial Services", "Realty", "Power"]
