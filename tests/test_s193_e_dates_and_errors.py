"""S193 item E, part 1 (owner, 23 Nov 2026: "Go with your recommendation on I and E"): the date rules and
the error text.

1. Every figure ends on the page's session, or the page says in one sentence where it ends (S148).
2. Header and footers name one session: the ranking's, the date the header pill shows.
3. Foreign flows are cut at the page's session and dated; the chart readout writes ₹ crore in words.
4. The qualify row never shows a month-end under "Now".
5. A missing value is not a failed rule (a stock too new for a 52-week high).
6. No exception text, emoji or internal names to readers; no "None" from the formatters.
"""
from __future__ import annotations

import ast
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.engine import dashboard_insights as di
from src.engine import indices_page as ip
from src.engine.exit_watch import assess
from src.ui import formats

ROOT = Path(__file__).resolve().parents[1]
D20, D19 = pd.Timestamp("2026-11-20"), pd.Timestamp("2026-11-19")


def _closes(end: str, n: int = 400, start: float = 100.0) -> pd.Series:
    idx = pd.bdate_range(end=end, periods=n)
    return pd.Series(start * np.cumprod(np.full(n, 1.001)), index=idx)


# ── 1. Indices: an index without the page's close reads "–" ────────────────

def test_ret_reads_none_without_a_close_for_the_session():
    s = _closes("2026-11-19")
    assert ip.ret(s, 1, D19) is not None
    assert ip.ret(s, 1, D20) is None                       # was the 19 Nov figure under "ends on 20 Nov"
    assert ip.ret(s, 1, D20, on_end=False) == ip.ret(s, 1, D19)   # a date N months back reads on or before


def _frames() -> ip.Frames:
    a, b = _closes("2026-11-20"), _closes("2026-11-19")
    old = _closes("2026-10-01")
    close = pd.concat({"nifty_a": a, "nifty_b": b, "nifty_old": old}, axis=1, sort=True)
    blank = close * np.nan
    names = {"nifty_a": "Nifty A", "nifty_b": "Nifty B", "nifty_old": "Nifty Old"}
    groups = {k: "Theme" for k in names}
    return ip.Frames(close, blank, blank, blank, names, groups)


def test_every_index_keeps_a_late_index_with_dashes_and_drops_a_discontinued_one():
    rows = ip.every_index(_frames())["Theme"]
    by = {r.key: r for r in rows}
    assert "nifty_old" not in by                           # no close for weeks: discontinued
    assert by["nifty_a"].late is None and by["nifty_a"].returns[1] is not None
    b = by["nifty_b"]
    assert b.late == D19 and all(v is None for v in b.returns.values()) and b.from_high is None
    assert rows[-1].key == "nifty_b"                       # late rows last
    assert ip.late_names(rows) == ["Nifty B"]


def test_every_index_reads_on_the_session_it_is_given():
    rows = {r.key: r for r in ip.every_index(_frames(), now=D19)["Theme"]}
    assert rows["nifty_a"].late is None and rows["nifty_b"].late is None


def test_the_sentence_names_the_indices_not_in_yet():
    assert formats.closes_not_in(["Nifty Bank"], D20) == "NSE’s 20 Nov close for Nifty Bank is not in yet."
    assert formats.closes_not_in(["Nifty A", "Nifty B"], D20) == "NSE’s 20 Nov closes for Nifty A and Nifty B are not in yet."
    assert formats.closes_not_in([], D20) == ""
    assert "6 of these indices" in formats.closes_not_in(list("ABCDEF"), D20)


def test_indices_page_says_which_index_is_late():
    from src.ui.views import indices_view as iv
    f = _frames()
    html = "".join(iv.section_every(f, ip.every_index(f), f.as_of))
    assert "NSE’s 20 Nov close for Nifty B is not in yet. Their figures read –." in html
    assert "since" not in html.split("Nifty B")[-1].split("</tr>")[0]   # a late row is not "since <launch>"


def test_sectors_nse_table_follows_the_same_rule():
    from src.engine import sectors_page as sp
    line = sp.IndexLine("k", "Nifty B", True, pd.Timestamp("2020-01-01"), {m: None for m in ip.WINDOWS}, None, None, D19)
    assert not line.young                                  # late, not young: no "since <launch>"
    assert "f.until(ld.when)" in (ROOT / "src/ui/views/sector_view.py").read_text()
    assert "now=ld.when" in (ROOT / "src/engine/sectors_page.py").read_text()


# ── 1. Dashboard and Market ────────────────────────────────────────────────

def test_dashboard_says_when_index_figures_end_a_session_early():
    from src.ui.views.dashboard_home_view import index_late_note
    assert index_late_note(D20, D20) == ""
    note = index_late_note(D19, D20)
    assert note.startswith("Nifty Total Market to 19 Nov: NSE’s closes for 20 Nov are not in yet")
    assert note.endswith("the book’s are to 20 Nov.") and note.count(".") == 1
    src = (ROOT / "src/ui/views/dashboard_home_view.py").read_text()
    assert "data_to(idx_end)" not in src and "_fmt.data_to_html(as_of)}.</p>" in src   # footer = header's session
    assert "book_month(ledger.get(\"months\", {}), book_mtd, market, momentum, as_of" in src


def test_market_keeps_a_late_size_row_with_dashes():
    from src.ui.views.market_questions_view import size_trend_html
    bench = _closes("2026-11-20")
    html = size_trend_html(bench, {"Nifty Midcap 150": _closes("2026-11-20")}, late=["Nifty Microcap 250"], day=D20)
    row = html.split("Nifty Microcap 250</td>")[1].split("</tr>")[0]
    assert row == "<td>–</td>" * 6
    assert "NSE’s 20 Nov close for Nifty Microcap 250 is not in yet." in html


# ── 2. One session in the header and the footers ───────────────────────────

def _deferred() -> pd.DataFrame:
    idx = pd.bdate_range(end="2026-11-20", periods=30)
    px = pd.DataFrame(100.0, index=idx, columns=[f"S{i}" for i in range(10)])
    px.iloc[-1, 3:] = np.nan            # 20 Nov still publishing: 3 of 10 closes
    return px


def test_session_of_is_the_ranking_session_not_the_last_row():
    from src.engine.pipeline import ranking_as_of
    px = _deferred()
    assert ranking_as_of(px) == "2026-11-19"
    assert formats.session_of(px) == D19
    assert formats.data_to(formats.session_of(px)) == "Data to 19 Nov 2026 · NSE"
    assert formats.session_of(None) is None


@pytest.mark.parametrize("path", ["src/ui/views/ranking_view.py", "src/ui/views/market_view.py",
                                  "src/ui/views/stock_view.py", "src/ui/views/watchlist_view.py",
                                  "src/ui/views/sector_view.py", "src/ui/views/dashboard_home_view.py"])
def test_footers_read_the_session_not_the_frames_last_row(path):
    src = (ROOT / path).read_text()
    assert "data_to(adj_close.index[-1])" not in src
    assert "session_of(" in src


# ── 3. Flows ────────────────────────────────────────────────────────────────

def _nsdl() -> pd.DataFrame:
    days = pd.bdate_range("2026-11-02", "2026-11-23")
    return pd.DataFrame({"date": days.strftime("%Y-%m-%d"), "equity_net": 1000.0})


def test_flows_are_cut_at_the_page_session_and_dated():
    f = di.flows_summary(_nsdl(), D20)
    assert f.as_of == D20 and f.mtd == 1000.0 * len(pd.bdate_range("2026-11-02", D20))
    assert f.month_span == "2 to 20 Nov"
    assert di.flows_summary(_nsdl()).as_of == pd.Timestamp("2026-11-23")   # uncut: the file's own end
    assert pd.to_datetime(di.cut_at(_nsdl(), D20)["date"]).max() == D20
    src = (ROOT / "src/ui/views/dashboard_home_view.py").read_text()
    assert 'f"Foreign, {f.month_span}"' in src and "flows_summary(nsdl, as_of)" in src


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_flow_readout_writes_crore_in_words_as_python_does():
    from src.ui.views.dashboard_home_view import cr
    s = (ROOT / "static" / "dash_charts.js").read_text(encoding="utf-8")
    rnd = s[s.index("const rnd = "):s.index("const fx = ")]
    inr = s[s.index("const inr = "):s.index("Cr'; };", s.index("const inr = ")) + len("Cr'; };")]
    vals = [134230, -122000, 11965, -954, 0, 38000.4, 250000]
    out = subprocess.run([shutil.which("node"), "-e", rnd + inr + f"console.log(JSON.stringify({json.dumps(vals)}.map(inr)))"],
                         capture_output=True, text=True, check=True).stdout
    js = json.loads(out)
    assert js[0] == "+₹1.34 lakh Cr"
    assert js == [cr(v) for v in vals]


# ── 4. The qualify row ──────────────────────────────────────────────────────

def test_qualify_row_reads_dash_under_now_without_todays_reading():
    from src.ui.views.dashboard_home_view import _signals
    me = pd.date_range("2025-01-31", "2026-10-31", freq="BME")
    spreads = pd.DataFrame({"date": me.strftime("%Y-%m-%d"), "qualified": np.linspace(0.6, 0.17, len(me))})
    rows = _signals(spreads, pd.Series(dtype=float), D20, None, {}, {"tests": {}}, qualify_now={})
    q = next(r for r in rows if r["key"] == "qualify")
    assert q["cells"][2] == "–" and q["cells"][0] != "–"
    assert q["now_note"] and "Now reads" not in q["sub"]     # the reason is the Now column's footnote (S203 dash.mom.11)
    live = _signals(spreads, pd.Series(dtype=float), D20, None, {}, {"tests": {}},
                    qualify_now={"2026-08-20": 0.4, "2026-10-20": 0.3, "2026-11-20": 0.2})
    assert next(r for r in live if r["key"] == "qualify")["cells"][2] == "20%"


# ── 5. A missing value is not a failed rule ─────────────────────────────────

def _young_row() -> pd.DataFrame:
    return pd.DataFrame([{"Symbol": "MILKYMIST", "Rank": 40, "Above 50 EMA": True, "Near 52W High": False,
                          "% 50 EMA": 4.0, "% High": np.nan, "52W High": np.nan, "Short History": "Yes",
                          "CMP": 500.0, "Industry": "Food"}])


def test_a_stock_too_new_for_a_52_week_high_is_told_so():
    a = assess(_young_row(), ["MILKYMIST"], sessions={"MILKYMIST": 70}).iloc[0]
    assert a["why"] == "too new to have a 52-week high: 70 of 126 sessions"
    assert "below its 52-week high" not in a["why"]
    old = _young_row().assign(**{"% High": -25.0, "Short History": "No"})
    assert "more than 20% below its 52-week high" in assess(old, ["MILKYMIST"]).iloc[0]["why"]


def test_stock_lines_do_not_read_a_missing_high_as_below_it():
    from src.ui import stock_lines as sl
    from src.ui import watchlist_lines as wl
    row = _young_row().iloc[0]
    a = assess(_young_row(), ["MILKYMIST"], sessions={"MILKYMIST": 70}).iloc[0].to_dict()
    rules = sl.rules(row, a, None, wl.Lines(buy=20, keep=40, high_gap=20), 0.8)
    assert rules[1].fall == "No 52W high yet" and rules[1].today == "None before 126 sessions"
    assert "too new to have a 52W high" in sl.failed_filters(row)
    head, rest = sl.rules_heading(a, D20, 0.8)
    assert "more than 20%" not in rest and "too new to have a 52-week high: 70 of 126 sessions" in rest


# ── 6. Errors and formatters ────────────────────────────────────────────────

@pytest.mark.parametrize("v", [None, float("nan"), pd.NaT, np.nan, float("inf")])
def test_date_of_a_missing_value_is_a_dash(v):
    assert formats.date(v) == "–"


def test_data_to_without_a_date_leaves_the_date_out():
    assert formats.data_to(None) == "Data from NSE"
    assert formats.data_to(pd.NaT) == "Data from NSE"
    assert formats.data_to(D20) == "Data to 20 Nov 2026 · NSE"
    assert formats.date("abc") == "abc"


def test_stale_sources_are_written_in_words():
    from src.ui.views.ranking_view import behind_phrase
    assert behind_phrase({"label": "Prices", "as_of": "18 Nov", "date": pd.Timestamp("2026-11-18").date()}) == "Prices are to 18 Nov"
    assert behind_phrase({"label": "Market caps", "as_of": "date unknown", "date": None}) == "Market caps carry no date, so they may be old"
    t = behind_phrase({"label": "All-time highs", "as_of": "2y window, not all-time", "date": None})
    assert "2y window" not in t and "are to" not in t


READER_CALLS = {"error", "warning", "caption", "info", "success", "toast", "markdown", "write", "html", "note", "empty"}


def _sources():
    return [ROOT / "app.py", *sorted((ROOT / "src").rglob("*.py"))]


def test_no_exception_object_is_formatted_into_reader_text():
    bad = []
    for p in _sources():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for h in ast.walk(tree):
            if not (isinstance(h, ast.ExceptHandler) and h.name):
                continue
            for n in ast.walk(ast.Module(body=h.body, type_ignores=[])):
                if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                        and n.func.value.id in ("st", "kit") and n.func.attr in READER_CALLS):
                    args = n.args + [k.value for k in n.keywords]
                    if any(isinstance(x, ast.Name) and x.id == h.name for a in args for x in ast.walk(a)):
                        bad.append(f"{p.relative_to(ROOT)}:{n.lineno}")
    assert not bad, bad


def test_no_cross_mark_emoji_or_missing_control_in_reader_text():
    for p in _sources():
        s = p.read_text(encoding="utf-8")
        assert "❌" not in s, p
        assert "Force Refresh" not in s, p          # the control is "Clear cached files" on Configuration


def test_k_f1_a_table_row_opens_the_screener_address_not_the_host_path():
    # S193 K crawl, 23 Nov: rows on Actions, Sectors and Watchlist set window.location.search, so the host kept
    # its own path (/sectors?stock=X), app.py redirected it and Back looped on the stock.
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "src" / "ui" / "screener_table.py").read_text(encoding="utf-8")
    assert "window.location.search=" not in src
    assert "'screener'+search" in src
