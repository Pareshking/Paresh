"""S193 L: Production QA records each page's load time and fails when a page is over its budget on
two runs in a row (owner, 23 Nov 2026). Budgets: docs/archive/S193_ITEM_L_2026-11-24.md."""
import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "production_qa", pathlib.Path(__file__).resolve().parents[1] / "scripts" / "production_qa.py")
qa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qa)

# The report's "Budgets as built": the larger of the local bench and the first live reading, x 1.5.
BUDGETS = {"Dashboard": 8, "Portfolio": 9, "Actions": 8, "Sectors": 9, "Watchlist": 6.5, "Market": 10.5,
           "Indices": 7.5, "Backtest": 31, "Guide": 6, "Stock": 7}


def _all(v):
    return {k: v for k in BUDGETS}


def test_the_budgets_are_the_reports():
    assert {k: b for k, (_p, b) in qa.PAGE_BUDGETS_S.items()} == BUDGETS


def test_once_over_is_a_warning_twice_fails():
    within = {k: b - 0.5 for k, b in BUDGETS.items()}
    slow = {**within, "Sectors": 12.0}
    fails, rows = qa.judge_page_times(slow, {"run_id": "1", "seconds": within})
    assert not fails and rows["Sectors"]["over"] and not rows["Sectors"]["previous_over"]
    fails, rows = qa.judge_page_times(slow, {"run_id": "2", "seconds": slow})
    assert len(fails) == 1 and "Sectors" in fails[0]["detail"] and "run 2" in fails[0]["detail"]
    assert fails[0]["kind"] == "APPLICATION"


def test_no_previous_run_records_without_failing():
    fails, rows = qa.judge_page_times(_all(99.0), None)
    assert not fails and all(r["over"] for r in rows.values())


def test_no_reading_counts_as_over():
    fails, _ = qa.judge_page_times({**_all(1.0), "Backtest": None}, {"seconds": {**_all(1.0), "Backtest": None}})
    assert len(fails) == 1 and "Backtest" in fails[0]["detail"]


def test_the_times_round_trip_through_the_cached_file(tmp_path):
    path = tmp_path / "t" / "page_times.json"
    qa.write_page_times(_all(1.5), path)
    assert qa.read_previous_times(path)["seconds"] == _all(1.5)
    assert qa.read_previous_times(tmp_path / "missing.json") is None


def test_the_workflow_restores_and_saves_the_times_around_the_run():
    wf = (pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows" / "v1-production-qa.yml").read_text()
    restore, run, save = (wf.index("actions/cache/restore"), wf.index("python scripts/production_qa.py"),
                          wf.index("actions/cache/save"))
    assert restore < run < save and "path: .qa_page_times" in wf and "restore-keys: qa-page-times-" in wf
