"""Audit limits that fail a job on a regression (S47): scripts/audit_limits.py and its wiring."""
import copy
import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import yaml

from scripts import audit_limits as al
from scripts import nse_history_audit as audit

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

# The long-file audits' summaries as the build of 10 Oct 2026 wrote them
# (run 38043565842), trimmed to what the limits read.
LONG = {
    "summary.json": {
        "yahoo_levels": {"days_within_2pct": 0.8938}, "eod2_levels": {"days_within_2pct": 0.8774},
        "tijori_levels": {"days_within_2pct": 0.9162}, "ss_levels": {"days_within_2pct": 0.9806},
        "marketlens_levels": {"days_within_2pct": 0.8697}, "tejhq_levels": {"days_within_2pct": 0.4073},
        "breaks": [{"ref": "eod2", "who": "eod2", "n": 186}, {"ref": "eod2", "who": "ours", "n": 2},
                   {"ref": "marketlens", "who": "marketlens", "n": 400},
                   {"ref": "marketlens", "who": "ours", "n": 3}, {"ref": "ss", "who": "ss", "n": 45},
                   {"ref": "tejhq", "who": "ours", "n": 211}, {"ref": "tejhq", "who": "tejhq", "n": 207},
                   {"ref": "tijori", "who": "ours", "n": 446}, {"ref": "tijori", "who": "tijori", "n": 786},
                   {"ref": "yahoo", "who": "ours", "n": 421}, {"ref": "yahoo", "who": "yahoo", "n": 183}],
        "big_moves": {"down confirmed": 1211, "down disputed": 2, "down fake": 1, "down unverified": 545,
                      "up confirmed": 245, "up fake": 1, "up unverified": 292},
    },
    "screener_summary.json": {"intervals_within_2pct": 0.9781, "level_shifts": 538,
                              "level_shifts_ours_moved": 265},
    "raw_summary.json": {
        "bar_exceptions": {"average price outside the range": 1372, "close below low": 137,
                           "close above high": 103},
        "symbol_changes": {"no ISIN history": 218, "same ISIN": 95},
        "calendar": {"dropped by the build (a holiday copy?)": 73},
    },
    "bse_fill_verify.json": {"share_of_cells_with_a_reference": 0.9858, "outlier_cells": 42},
    "nse_long_report.json": {"unpriced": ["TRIVENIPT"], "renames_not_joined": ["x"] * 16},
}

# The history audit's summary of run 37047812302 (2 Oct 2026), the baseline.
HISTORY = {"summary.json": {"sessions": 4704, "stocks": 4486, "missing_weekdays": 35,
                            "missing_weekdays_settled": 35, "gap_days": 87, "copied_sessions": 73,
                            "calendar_flags": 80,
                            "actions": {"no move": 584, "applied": 570, "no price": 310, "demerger": 97},
                            "unexplained_jumps": 1401, "renames": 425, "renames_refused": 142}}


def test_todays_long_file_audits_pass():
    assert al.check(LONG, al.LONG_LIMITS) == []


def test_todays_history_audit_passes():
    assert al.check(HISTORY, al.HISTORY_LIMITS) == []


@pytest.mark.parametrize("file, path, worse", [
    ("summary.json", ("big_moves", "up fake"), 2),
    ("summary.json", ("big_moves", "down disputed"), 3),
    ("screener_summary.json", ("level_shifts_ours_moved",), 266),
    ("raw_summary.json", ("calendar", "dropped by the build (a holiday copy?)"), 74),
    ("bse_fill_verify.json", ("outlier_cells",), 43),
    ("nse_long_report.json", ("unpriced",), ["TRIVENIPT", "NEWONE"]),
])
def test_one_more_finding_than_the_baseline_fails(file, path, worse):
    docs = copy.deepcopy(LONG)
    cur = docs[file]
    for key in path[:-1]:
        cur = cur[key]
    cur[path[-1]] = worse
    broken = al.check(docs, al.LONG_LIMITS)
    assert len(broken) == 1 and path[-1] in broken[0]


def test_a_new_break_where_ours_moved_fails_even_against_a_clean_reference():
    docs = copy.deepcopy(LONG)
    docs["summary.json"]["breaks"].append({"ref": "ss", "who": "ours", "n": 1})
    assert al.check(docs, al.LONG_LIMITS) == ["summary.json: breaks_by / ss / ours: 1 > 0 allowed"]
    docs["summary.json"]["breaks"][1]["n"] = 3            # eod2, ours: 2 -> 3
    assert len(al.check(docs, al.LONG_LIMITS)) == 2


def test_a_verdict_the_audit_did_not_write_counts_as_none():
    docs = copy.deepcopy(LONG)
    del docs["summary.json"]["big_moves"]["up fake"]
    del docs["raw_summary.json"]["bar_exceptions"]["close above high"]
    assert al.check(docs, al.LONG_LIMITS) == []


def test_shares_may_drift_by_the_tolerance_but_not_beyond():
    docs = copy.deepcopy(LONG)
    docs["summary.json"]["yahoo_levels"]["days_within_2pct"] = 0.8938 - al.SHARE_TOLERANCE + 0.0001
    assert al.check(docs, al.LONG_LIMITS) == []
    docs["summary.json"]["yahoo_levels"]["days_within_2pct"] = 0.8938 - al.SHARE_TOLERANCE - 0.0001
    broken = al.check(docs, al.LONG_LIMITS)
    assert len(broken) == 1 and "yahoo_levels" in broken[0] and "required" in broken[0]
    # TejHQ adjusts within an ISIN only: its share is not a limit.
    docs = copy.deepcopy(LONG)
    docs["summary.json"]["tejhq_levels"]["days_within_2pct"] = 0.1
    assert al.check(docs, al.LONG_LIMITS) == []


def test_a_missing_summary_or_section_fails():
    docs = copy.deepcopy(LONG)
    del docs["raw_summary.json"]
    broken = al.check(docs, al.LONG_LIMITS)
    assert broken and all("no raw_summary.json" in b for b in broken)
    docs = copy.deepcopy(LONG)
    del docs["summary.json"]["yahoo_levels"]
    assert al.check(docs, al.LONG_LIMITS) == ["summary.json: yahoo_levels / days_within_2pct: not in the summary"]
    docs = copy.deepcopy(LONG)
    docs["screener_summary.json"]["intervals_within_2pct"] = None
    assert al.check(docs, al.LONG_LIMITS) == ["screener_summary.json: intervals_within_2pct: no value"]


def test_every_limit_is_a_named_constant_with_its_baseline():
    text = (ROOT / "scripts" / "audit_limits.py").read_text(encoding="utf-8")
    assert "run 38043565842" in text and "run 37047812302" in text
    for lim in (*al.LONG_LIMITS, *al.HISTORY_LIMITS):
        assert lim.kind in ("max", "min")
        assert lim.bound >= 0


def test_the_cli_exits_1_on_a_regression_and_0_otherwise(tmp_path, capsys):
    for name, doc in LONG.items():
        (tmp_path / name).write_text(json.dumps(doc), encoding="utf-8")
    argv = ["long", "--audit", str(tmp_path), "--report", str(tmp_path / "nse_long_report.json")]
    assert al.main(argv) == 0
    worse = copy.deepcopy(LONG["summary.json"])
    worse["big_moves"]["down fake"] = 5
    (tmp_path / "summary.json").write_text(json.dumps(worse), encoding="utf-8")
    assert al.main(argv) == 1
    assert "::error::long price file audit limit: summary.json: big_moves / down fake: 5 > 1 allowed" \
        in capsys.readouterr().out


def test_history_audit_fails_on_limits_only_after_writing_its_report(tmp_path):
    (tmp_path / "summary.json").write_text(json.dumps(HISTORY["summary.json"]), encoding="utf-8")
    assert audit.check_limits(tmp_path, log=lambda *a: None) == 0
    worse = {**HISTORY["summary.json"], "unexplained_jumps": 1402}
    (tmp_path / "summary.json").write_text(json.dumps(worse), encoding="utf-8")
    lines = []
    assert audit.check_limits(tmp_path, log=lines.append) == 1
    assert any("unexplained_jumps: 1402 > 1401" in line for line in lines)
    assert audit.check_limits(tmp_path / "nowhere", log=lambda *a: None) == 1


def test_a_weekday_of_the_last_week_is_not_yet_a_missing_day(tmp_path):
    """A holiday is a known closed day only a week later (nse_collect): not a fault before."""
    result = {"per_year": pd.Series({2026: 3}), "missing": [date(2026, 9, 1), date(2026, 10, 9)],
              "gap_days": pd.Series(dtype=float), "copies": pd.Series(dtype=float), "calendar": {},
              "verdicts": pd.DataFrame(columns=["verdict"]), "jumps": pd.DataFrame(columns=["date"]),
              "renames": 0, "refused": [], "stocks": 1}
    audit.write(result, tmp_path, date(2026, 9, 1), date(2026, 10, 12))
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["missing_weekdays"] == 2 and summary["missing_weekdays_settled"] == 1


# --- the workflows -------------------------------------------------------------------------

def _wf(name):
    doc = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    return doc, doc.get(True) or doc.get("on")


def _cron_day(cron):
    """The day of month a 'm h D * *' cron fires on."""
    return int(cron.split()[2])


def test_the_yearly_list_is_imported_monthly_before_the_full_rebuild_and_the_audit():
    imp, imp_on = _wf("nse_history_import.yml")
    aud, aud_on = _wf("nse_history_audit.yml")
    imp_cron, aud_cron = imp_on["schedule"][0]["cron"], aud_on["schedule"][0]["cron"]
    assert imp_cron.split()[0] != "0" and aud_cron.split()[0] != "0"
    # Import on day 2, then the audit on day 3; the long file re-reads everything every Saturday.
    assert _cron_day(imp_cron) < _cron_day(aud_cron)
    steps = {s.get("name", ""): s for s in imp["jobs"]["import"]["steps"]}
    actions = next(s for n, s in steps.items() if n.startswith("Corporate actions"))
    assert "date -u +%Y) - 1" in actions["run"]          # last year and this year when scheduled
    for name in ("Fetch the bhavcopy mirror (data/ only)", "Prices R2 lacks, oldest first"):
        assert "github.event_name != 'schedule'" in steps[name]["if"]


def test_the_long_file_rereads_everything_on_every_scheduled_saturday():
    # Owner, 13 Oct 2026: a full rebuild every Saturday, not only the second.
    doc, on = _wf("nse_long_prices.yml")
    assert on["schedule"][0]["cron"] == "30 3 * * 6"
    steps = doc["jobs"]["build"]["steps"]
    first = steps[0]
    assert first["if"] == "github.event_name == 'schedule'"
    assert "FULL=yes" in first["run"] and "-ge" not in first["run"]
    pack = next(s for s in steps if s.get("name") == "The raw-history pack from the last build")
    assert pack["if"] == "env.FULL != 'yes'"
    assert "inputs.full == 'yes'" in doc["jobs"]["build"]["env"]["FULL"]


def test_the_long_file_audit_limits_fail_the_job_after_publish_and_before_the_upload():
    doc, _ = _wf("nse_long_prices.yml")
    steps = doc["jobs"]["build"]["steps"]
    names = [s.get("name", s.get("uses", "")) for s in steps]
    publish = names.index("Publish to the data-latest release")
    audit_i = names.index("Audit the new file")
    limits = names.index("Audit limits")
    upload = next(i for i, s in enumerate(steps) if str(s.get("uses", "")).startswith("actions/upload-artifact"))
    assert publish < audit_i < limits < upload
    assert "audit_limits.py long" in steps[limits]["run"]
    assert "continue-on-error" not in steps[limits]
    assert steps[upload]["if"] == "always()"


def test_the_history_audit_fails_on_limits_but_still_writes_its_summary_and_artifact():
    doc, _ = _wf("nse_history_audit.yml")
    steps = doc["jobs"]["audit"]["steps"]
    names = [s.get("name", s.get("uses", "")) for s in steps]
    run, limits = names.index("Audit"), names.index("Audit limits")
    upload = next(i for i, s in enumerate(steps) if str(s.get("uses", "")).startswith("actions/upload-artifact"))
    assert "GITHUB_STEP_SUMMARY" in steps[run]["run"]
    assert run < limits < upload
    assert "audit_limits.py history --audit reports/nse_audit" in steps[limits]["run"]
    assert steps[limits]["if"] == "inputs.fail_on_limits != 'no'"     # on for every scheduled run
    assert steps[upload]["if"] == "always()"
