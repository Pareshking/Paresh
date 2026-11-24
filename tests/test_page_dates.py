"""S164 (owner, 21 Nov 2026: "market breadth page must be having live data till yesterday atleast ... must be strict
audit"): every chart, table and sentence ends on the page's session, or says why, by rule.

The check itself is `scripts/_page_dates.mjs`. CI runs it on the running app, reading R2 as the live site does, inside
the layout audit step of `.github/workflows/v1-full-validation.yml`: `number_format_audit.mjs` (rule 9) on the pages it
reads and `glossary_audit.mjs` on the ones only it opens (Configuration, the Nano Cap pages). The live site is checked
with `node scripts/page_dates_audit.mjs <url> ...`. This file tests the rules on fixtures (the 20 Nov 2026 cases of
docs/STALENESS_AUDIT_2026-11-21.md), that every allowed end names its reason and a TODO id, the wiring, and
Configuration's table of files (extends S154 (c), S148: a series a page reads ends on the page's data date or the
page names its date).

Open items the text check cannot see, because the figure carries no date, are strict xfails here: each fails the
suite once it is fixed, so its marker comes out with the fix.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

HEADER = "Dashboard\nPrices · closes of 20 Nov\nNifty 500\n"
FOOTER = "\nData to 20 Nov 2026 · NSE."


def _judge(pages: list[dict]) -> list[dict]:
    """pageDateFindings for each {url, raw?, frames?}."""
    js = ("import('./scripts/_page_dates.mjs').then(m => { const pages = JSON.parse(process.argv[1]); "
          "console.log(JSON.stringify(pages.map(p => m.pageDateFindings(p.url, p)))); });")
    out = subprocess.run([NODE, "--input-type=module", "-e", js, json.dumps(pages)], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def _page(main: str, *charts: tuple[str, str | None], url: str = "http://x/") -> dict:
    return {"url": url, "frames": [{"text": HEADER + main + FOOTER, "specEnd": None}]
            + [{"text": t, "specEnd": s} for t, s in charts]}


# ── The rules ───────────────────────────────────────────────────────────────

@needs_node
def test_the_session_is_the_header_pill_with_the_footers_year():
    r = _judge([_page("Nothing dated.")])[0]
    assert r["session"] == "2026-11-20" and r["findings"] == []


@needs_node
def test_a_page_with_data_and_no_session_is_a_finding_but_the_guide_is_not():
    r = _judge([{"url": "http://x/", "raw": "No dates at all."}, {"url": "http://x/guide", "raw": "Method."}])
    assert r[0]["findings"][0]["shown"] == "no session"
    assert r[1]["findings"] == []


@needs_node
def test_the_triggering_case_fails_a_chart_ending_on_the_last_month_end_with_no_rule():
    # 21 Nov 2026: Breadth's "Behind the answer" chart read "Latest · 30 Oct 2026" on a 20 Nov page.
    chart = ("Nifty 500 against its 10-month average\nLatest · 30 Oct 2026\n−3.1%\n", "2026-10-30")
    r = _judge([_page("Behind the answer", chart)])[0]
    shown = {f["shown"] for f in r["findings"]}
    assert "Latest · 30 Oct 2026" in shown and "chart data to 30 Oct 2026" in shown


@needs_node
def test_a_chart_whose_spec_stops_early_fails_even_without_a_dated_readout():
    r = _judge([_page("", ("Latest · the broadest 65% now\n", "2026-11-13"))])[0]
    assert [f["shown"] for f in r["findings"]] == ["chart data to 13 Nov 2026"]


@needs_node
def test_a_stated_rule_passes_and_names_its_rule():
    pages = [
        _page("The test reads month-ends: Nifty 500 to 30 Oct 2026, −3.1%."),
        _page("Domestic institutions, provisional, to 18 Nov."),
        _page("", ("Monthly closes, each finished month\nLatest · Oct 2026\n", "2026-10-31")),
        _page("Net new highs, week to 13 Nov 2026."),
    ]
    rules = [[x["rule"] for x in r["ruled"]] for r in _judge(pages)]
    assert all(not r["findings"] for r in _judge(pages))
    assert rules[0] == ["month_end"] and rules[1] == ["source_lag"] and "month_end" in rules[2] and rules[3] == ["weekly"]


@needs_node
def test_a_rule_in_another_sentence_does_not_count():
    r = _judge([_page("Each line is a month-end reading. Domestic flows, 2 to 18 Nov 2026, −₹50,000 Cr.")])[0]
    assert [f["shown"] for f in r["findings"]] == ["to 18 Nov 2026"]


@needs_node
def test_a_footer_that_states_its_rule_rules_its_month_and_no_other():
    # Backtest: "Data to 30 Oct 2026 · NSE’s long price file, the last completed month" on a 20 Nov session.
    main = ("Tested 4 Jan 2010 to 30 Oct 2026.\nThe book from 1 Oct to 15 Sep 2026.\n"
            "Data to 30 Oct 2026 · NSE’s long price file, the last completed month · prices to 20 Nov 2026.")
    r = _judge([{"url": "http://x/backtest", "frames": [{"text": HEADER + main, "specEnd": None},
                                                         {"text": "Latest · 30 Oct 2026", "specEnd": "2026-10-30"}]}])[0]
    by = {x["shown"]: x["rule"] for x in r["ruled"]}
    assert by["to 30 Oct 2026"] == "month_end"                               # the footer's own sentence
    assert by["Latest · 30 Oct 2026"] == by["chart data to 30 Oct 2026"] == "month_end (the footer)"
    assert [f["shown"] for f in r["findings"]] == ["to 15 Sep 2026"]         # September is not the footer's month


@needs_node
def test_a_footer_before_the_session_without_a_rule_fails():
    r = _judge([{"url": "http://x/", "raw": "Prices · closes of 20 Nov\nData to 18 Nov 2026 · NSE."}])[0]
    assert r["session"] == "2026-11-20"
    assert [f["shown"] for f in r["findings"]] == ["to 18 Nov 2026"]


@needs_node
def test_history_and_ends_ahead_pass():
    main = ("Its deepest fall, December 2024 to September 2025, made back by March 2026.\n"
            "Board meetings to 5 Dec.\nNovember so far, to 20 Nov 2026.\nLatest · Nov 2026, to 20 Nov")
    r = _judge([_page(main, ("Latest · Nov 2026\n", "2026-11-30"))])[0]
    assert r["findings"] == []


@needs_node
def test_a_new_early_end_on_the_dashboard_is_not_swallowed_by_the_allow_list():
    main = "Domestic institutions, 2 to 18 Nov, on NSE\nNifty 500 against its 10-month average to 30 Oct 2026"
    r = _judge([_page(main)])[0]
    assert [a["shown"] for a in r["allowed"]] == ["to 18 Nov"]
    assert [f["shown"] for f in r["findings"]] == ["to 30 Oct 2026"]


# ── The allow-list ──────────────────────────────────────────────────────────

def _allow() -> list[dict]:
    js = ("import('./scripts/_page_dates.mjs').then(m => console.log(JSON.stringify(m.ALLOW.map(a => "
          "({re: a.re.source, where: a.where && a.where.source, todo: a.todo, why: a.why})))));")
    return json.loads(subprocess.run([NODE, "--input-type=module", "-e", js], cwd=ROOT, capture_output=True,
                                     text=True, check=True).stdout)


@needs_node
def test_every_allowed_end_names_its_reason_and_a_todo_id():
    # The TODO row itself is not read here: a test that reads docs/ must also run on a Markdown-only PR
    # (tests/test_docs_only_validation.py), and that step is in the workflow, outside this change.
    for a in _allow():
        assert re.fullmatch(r"S\d+", a["todo"]), a
        assert len(a["why"]) > 40 and re.match(r"(open|rule shown|not a figure): ", a["why"]), a


# ── Wiring: the check runs in CI on the running app ─────────────────────────

def test_the_audits_ci_runs_call_the_date_check():
    for name in ("number_format_audit.mjs", "glossary_audit.mjs", "page_dates_audit.mjs"):
        src = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "from './_page_dates.mjs'" in src and "reportPageDates(" in src, name
    wf = (ROOT / ".github" / "workflows" / "v1-full-validation.yml").read_text(encoding="utf-8")
    assert "node scripts/number_format_audit.mjs --save" in wf
    assert "node scripts/glossary_audit.mjs --cache" in wf and "http://localhost:8501/configuration" in wf
    text = (ROOT / "scripts" / "_page_text.mjs").read_text(encoding="utf-8")
    assert "frames.push({ text: r[0], specEnd: r[3] })" in text


# ── Configuration: every file a page reads, its date and its rule ───────────

def _files(tmp: Path, **last: str) -> Path:
    (tmp / "nse_prices").mkdir()
    for name in ("benchmarks.csv", "benchmark_indices.csv", "nse_total_market.csv", "nsdl_fpi_daily.csv",
                 "fii_dii_flows.csv", "breadth_history.csv"):
        pd.DataFrame({"date": ["2026-11-02", last.get(name, "2026-11-20")]}).to_csv(tmp / name, index=False)
    pd.DataFrame({"kind": ["month", "day", "day"], "period": ["2026-10", "2026-11-17", "2026-11-18"]}).to_csv(
        tmp / "nse_dii.csv", index=False)
    pd.DataFrame({"month": ["2026-09", last.get("momentum_health.csv", "2026-10")]}).to_csv(
        tmp / "momentum_health.csv", index=False)
    (tmp / "momentum_health_latest.json").write_text(json.dumps({"date": "2026-10-30", "qualified": 0.17}))
    return tmp


def test_configuration_lists_each_file_with_its_date_rule_and_status(tmp_path):
    from src.ui.views.config_view import FILE_RULES, file_dates
    rows = {r["File"]: r for r in file_dates(pd.Timestamp("2026-11-20"), str(_files(tmp_path, **{
        "breadth_history.csv": "2026-11-16"})))}
    assert len(rows) == len(FILE_RULES)
    assert rows["Nifty 500 and Nifty 50"]["Status"] == "On the session"
    assert rows["Domestic institutions, on NSE"]["Latest"] == "18 Nov 2026"
    assert rows["Domestic institutions, on NSE"]["Status"] == "2 sessions late, within its rule"
    # The audit's case: breadth_history.csv ended 16 Nov on a 20 Nov page, four sessions, against a daily rule.
    assert rows["Breadth history"]["Status"] == "4 sessions late, behind its rule"
    assert rows["Momentum’s record"]["Latest"] == "Oct 2026" and rows["Momentum’s record"]["Status"] == "Within its rule"
    assert rows["Stocks that qualify, today"]["Latest"] == "Not on this server"
    assert all(r["Its rule"].endswith(".") for r in rows.values())


def test_a_monthly_file_two_months_old_is_behind_after_the_sixth():
    from src.ui.views.config_view import file_dates
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = str(_files(Path(d), **{"momentum_health.csv": "2026-09"}))
        late = {r["File"]: r["Status"] for r in file_dates(pd.Timestamp("2026-11-20"), root)}
        early = {r["File"]: r["Status"] for r in file_dates(pd.Timestamp("2026-11-04"), root)}
    assert late["Momentum’s record"] == "Behind its rule"
    assert early["Momentum’s record"] == "Within its rule"          # the month's job runs on the 2nd to 6th


def test_configuration_without_a_session_shows_no_file_table():
    from src.ui.views.config_view import file_dates
    assert file_dates(None) == [] and file_dates(pd.NaT) == []


def test_every_file_in_the_table_is_read_by_a_page():
    # Nothing is listed that nothing reads (S195 §4).
    from src.ui.views.config_view import FILE_RULES
    src = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src").rglob("*.py")
                    if p.name != "config_view.py")
    for _, file, *_ in FILE_RULES:
        assert Path(file).name in src, file


# ── Open items the text check cannot see (strict: each fails once fixed) ────

@pytest.mark.xfail(strict=True, reason="S164 open (staleness audit #7): the Dashboard's '12 months' momentum tile ends "
                   "at the last finished month and does not name it (src/engine/system_momentum.py:152, "
                   "dashboard_insights.py:181); fix: its note names the window, e.g. 'Nov 2025 to Oct 2026'")
def test_the_12_month_tile_names_the_month_it_ends():
    from src.engine import system_momentum as sm
    months = pd.period_range("2025-08", "2026-10", freq="M").astype(str)
    record = pd.DataFrame({"month": months, "top": 1.0, sm.BENCH_COLUMN: 0.5})
    when, value, note = sm.tiles(record, 0.3)[0]
    assert when == "12 months" and value is not None
    assert "Oct" in when + note
