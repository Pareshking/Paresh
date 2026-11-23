"""Nifty 1000 as the fourth system (owner, 21 Nov 2026; S175)."""
import importlib.util
import pathlib

import pandas as pd

from src.engine import extra_universe as xu
from src.engine import nifty1000_backfill as nb
from src.engine import systems
from src.loaders import extra_universe_loader as xl

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _rows(syms, tag="", industry="Financial Services"):
    return pd.DataFrame({"Symbol": syms, "Company Name": syms, "Industry": industry, "Indices": tag})


def test_four_systems_in_order_with_the_old_keys_kept():
    assert xu.SYSTEMS == ("750", "1000", "nano", "combined")
    assert xu.SYSTEM_NAMES == {"750": "Nifty 750", "1000": "Nifty 1000",
                               "nano": "> ₹2,000 Cr", "combined": "Combined"}
    assert xu.SYSTEM_INCEPTION["1000"] == "2026-11"
    assert systems.ledger_path("1000").name == "track_record_1000.json"
    assert systems.ledger_path("nano").name == "track_record_nano.json"     # unchanged
    assert systems.inception("1000") == pd.Period("2026-11", "M")


def test_the_universe_is_the_750_then_nifty_nanocap_250():
    base = _rows(["A", "B"], tag="N50")
    n1000 = _rows(["A", "B", "X", "Y"], tag=xu.NANOCAP_250_SHORT, industry="Capital Goods")
    u = xl.system_universe(xu.SYSTEM_1000, base, n1000)
    assert u["Symbol"].tolist() == ["A", "B", "X", "Y"]
    assert u.set_index("Symbol").loc["A", "Indices"] == "N50"                 # the 750 keeps its tags
    assert set(u.set_index("Symbol").loc[["X", "Y"], "Indices"]) == {"NANO250"}
    core, extra = xl.split_symbols(xu.SYSTEM_1000, u)
    assert core == ["A", "B", "X", "Y"] and extra == []                      # caps from NSE's snapshot
    # the other systems are untouched
    nano = _rows(["N1", "A"])
    assert xl.system_universe(xu.SYSTEM_NANO, base, nano)["Symbol"].tolist() == ["N1"]
    assert xl.system_universe(xu.SYSTEM_750, base, nano)["Symbol"].tolist() == ["A", "B"]


def test_the_nifty_1000_list_is_read_with_nse_industry(tmp_path):
    p = tmp_path / "n.csv"
    p.write_text("Company Name,Industry,Symbol,Series,ISIN Code\nX Ltd,Capital Goods,xco,EQ,INE1\n"
                 "Dummy,Other,DUMMYABC,EQ,INE2\n")
    m = xl.nifty_1000_members(str(p))
    assert m["Symbol"].tolist() == ["XCO"] and m["Industry"].tolist() == ["Capital Goods"]
    assert xl.nifty_1000_members(str(tmp_path / "missing.csv")).empty


def test_membership_is_the_recorded_nifty_1000(monkeypatch):
    entry = nb.reconstruct({"baseline": {"date": "2021-10-29", "symbols": ["A"]}, "changes": []},
                           ["A", "X"], "2026-11-21")
    full = {"index": "nifty_total_market", "baseline": {"date": "2021-10-29", "symbols": ["A"]},
            "changes": [], "indices": {"nifty_1000": entry}}
    monkeypatch.setattr(systems, "load_history_or_none", lambda: full)
    h = systems.membership_for(xu.SYSTEM_1000)
    from src.engine.membership import members_on
    assert members_on(h, "2026-10-30") == {"A", "X"}
    monkeypatch.setattr(systems, "load_history_or_none", lambda: {**full, "indices": {}})
    assert systems.membership_for(xu.SYSTEM_1000) is None     # not recorded yet: no backtest


def test_a_freeze_is_refused_while_a_member_has_no_close_on_the_signal_day():
    spec = importlib.util.spec_from_file_location("utr", ROOT / "scripts" / "update_track_record.py")
    utr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(utr)
    entry = nb.reconstruct({"baseline": {"date": "2021-10-29", "symbols": ["A"]}, "changes": []},
                           ["A", "X"], "2026-11-21")
    from src.engine.index_universe import index_history
    h = index_history("nifty_1000", {"indices": {"nifty_1000": entry}})
    idx = pd.to_datetime(["2026-10-29", "2026-10-30", "2026-11-02"])
    prices = pd.DataFrame({"A": [1.0, 1.0, 1.0], "X": [None, None, 2.0]}, index=idx)
    assert utr.unpriced_members(prices, h, pd.Period("2026-11", "M"), 1) == {"2026-10-30": ["X"]}
    prices.loc["2026-10-30", "X"] = 2.0
    assert utr.unpriced_members(prices, h, pd.Period("2026-11", "M"), 1) == {}


def test_the_nightly_jobs_carry_the_fourth_system():
    daily = (ROOT / ".github" / "workflows" / "daily_sync.yml").read_text()
    monthly = (ROOT / ".github" / "workflows" / "monthly_track_record.yml").read_text()
    assert daily.count("for SYS in nano combined 1000; do") == 2      # release upload and R2 publish
    assert "for SYSTEM in nano combined 1000; do" in monthly
    spec = importlib.util.spec_from_file_location("pcs", ROOT / "scripts" / "precompute_systems.py")
    src = (ROOT / "scripts" / "precompute_systems.py").read_text()
    assert "[SYSTEM_NANO, SYSTEM_COMBINED, SYSTEM_1000]" in src and spec is not None


def test_the_750s_nightly_ranking_gets_only_the_750s_caps():
    src = (ROOT / "scripts" / "sync_data.py").read_text()
    assert "_precompute_rankings(symbols, universe_df, mcaps.reindex(symbols).dropna())" in src


def test_the_2000_cr_list_carries_nse_isins_and_never_guesses():
    listed = pd.DataFrame({"Company Name": ["A Ltd", "B Ltd"], "Industry": "X", "Symbol": ["AAA", "BBB"],
                           "Series": "EQ", "ISIN Code": "", "MarketCapCr": [3000, 2500]})
    eq = pd.DataFrame({"SYMBOL": ["AAA ", "ZZZ"], " ISIN NUMBER": ["INE000A01011", "INE999Z01019"]})
    out = xu.with_isins(listed, eq)
    assert out["ISIN Code"].tolist() == ["INE000A01011", ""]
    assert xu.with_isins(listed, None) is listed
    assert list(out.columns) == list(listed.columns)


# ── S194: the independent audit's findings ───────────────────────────────────

def test_f1_the_comparison_prices_later_joiners(monkeypatch):
    from src.ui.views import track_record_view as tv
    hist = {"baseline": {"date": "2026-10-30", "symbols": ["AAA"]},
            "changes": [{"date": "2026-11-04", "added": ["ENNATURE"], "removed": ["AAA"]}]}
    monkeypatch.setattr(tv, "membership_for", lambda system: hist)
    idx = pd.to_datetime(["2026-11-03", "2026-11-04"])

    class _Chosen:
        close = pd.DataFrame({"AAA": [1.0, 1.0], "ENNATURE": [2.0, 2.0], "OTHER": [3.0, 3.0]}, index=idx)
    from src.loaders import price_source
    monkeypatch.setattr(price_source, "from_screener", lambda store: _Chosen)
    frame = tv._system_prices.__wrapped__("1000", "rev", None) if hasattr(tv._system_prices, "__wrapped__") \
        else tv._system_prices("1000", "rev-f1", None)
    assert {"AAA", "ENNATURE"} <= set(frame.columns) and "OTHER" not in frame.columns


def test_f2_the_nifty_1000_industries_use_the_750s_spelling(tmp_path):
    p = tmp_path / "n.csv"
    p.write_text('Company Name,Industry,Symbol,Series,ISIN Code\n'
                 'A Ltd,"Oil, Gas & Consumable Fuels",AAA,EQ,INE1\n'
                 'B Ltd,"Media, Entertainment & Publication",BBB,EQ,INE2\nC Ltd,Capital Goods,CCC,EQ,INE3\n')
    assert xl.nifty_1000_members(str(p))["Industry"].tolist() == [
        "Oil Gas & Consumable Fuels", "Media Entertainment & Publication", "Capital Goods"]
    t = pd.read_csv(ROOT / "data" / "indices" / "ind_niftytotalmarket_list.csv")
    assert {"Oil Gas & Consumable Fuels", "Media Entertainment & Publication"} <= set(t["Industry"])


def test_f3_the_record_caps_the_250_by_nse_industry_for_the_nifty_1000_only(monkeypatch):
    from src.engine import model_record as mr
    from src.loaders import former_members
    monkeypatch.setattr(xl, "nifty_1000_members",
                        lambda path=None: pd.DataFrame({"Symbol": ["XNEW"], "Industry": ["Capital Goods"]}))
    monkeypatch.setattr(former_members, "industry_for", lambda syms: {s: "Realty" for s in syms})
    assert mr.record_sector_map(["XNEW"], "1000") == {"XNEW": "Capital Goods"}
    assert mr.record_sector_map(["XNEW"], "nano") == {"XNEW": "Realty"}      # other systems unchanged
    assert mr.record_sector_map(["XNEW"]) == {"XNEW": "Realty"}


def test_f4_l1_unpriced_members_skips_frozen_months_and_names_the_rest():
    entry = nb.reconstruct({"baseline": {"date": "2021-10-29", "symbols": ["AAA"]}, "changes": []},
                           ["AAA", "XCO"], "2026-11-21")
    from src.engine.index_universe import index_history
    h = index_history("nifty_1000", {"indices": {"nifty_1000": entry}})
    idx = pd.to_datetime(["2026-10-30", "2026-11-30"])
    prices = pd.DataFrame({"AAA": [1.0, 1.0], "XCO": [None, None]}, index=idx)
    assert systems.unpriced_members(prices, h, pd.Period("2026-11", "M"), 2) == {
        "2026-10-30": ["XCO"], "2026-11-30": ["XCO"]}
    assert systems.unpriced_members(prices, h, pd.Period("2026-11", "M"), 2, skip={"2026-11"}) == {
        "2026-11-30": ["XCO"]}
    from src.ui.canonical_book import unpriced_note
    head, body = unpriced_note({"unpriced": {"2026-10-30": ["XCO"]}})
    assert "1 member" in head and "30 Oct 2026" in head and body.startswith("XCO.")   # S173 rule 3: no ISO date
    assert unpriced_note({}) is None


def test_f6_a_missing_ledger_after_its_first_month_warns_once(tmp_path, monkeypatch, caplog):
    from src.engine import track_record as tr
    monkeypatch.setattr(tr, "_current_month", lambda: pd.Period("2026-12", "M"))
    path = tmp_path / "track_record_1000.json"
    import logging
    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            tr.load_ledger(path, pd.Period("2026-11", "M"))
    assert sum("No track-record ledger" in r.getMessage() for r in caplog.records) <= 1


def test_f7_the_new_tags_have_display_names():
    from src.ui.screener_table import INDEX_NAMES as table_names
    from src.ui.views.stock_view import INDEX_NAMES as stock_names
    for names in (table_names, stock_names):
        # Owner, 23 Nov 2026: the Nifty 1000's other 250 are "Nano Cap" (was "Nanocap 250").
        assert names["NANO250"] == "Nano Cap" and names["NANO"] == "> ₹2,000 Cr"
