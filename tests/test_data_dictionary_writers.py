"""S163: a file staged by a whole-`data/` `git add` gets its writer from git, not a guess."""
from pathlib import Path

from scripts import data_dictionary as dd

ROOT = Path(__file__).resolve().parents[1]


def test_bot_commits_name_their_workflow_and_prs_are_counted():
    log = ("github-actions[bot]|chore(data): automated daily NSE index & classification sync [skip ci]\n"
           "github-actions[bot]|chore(data): automated daily NSE index & classification sync [skip ci]\n"
           "Someone|S99: a fix (#700)\n")
    assert dd.history_writer("x", log) == "daily_sync (2 commits); also 1 by pull request"


def test_a_file_no_job_touched_is_kept_by_hand():
    assert dd.history_writer("x", "Someone|S1 (#1)\nSomeone|S2 (#2)\n").startswith("pull requests only (2")


def test_no_history_keeps_the_workflow_answer():
    assert dd.history_writer("x", "") is None


def test_the_subjects_are_read_from_the_workflows():
    assert dd.BOT_SUBJECTS["automated daily NSE index & classification sync"] == "daily_sync"
    assert dd.BOT_SUBJECTS["Screener earnings, weekly"] == "screener_earnings"
    assert dd.BOT_SUBJECTS["freeze closed month(s)"] == "monthly_track_record"
    assert len(dd.BOT_SUBJECTS) >= 15


def test_every_bot_subject_is_one_a_workflow_commits():
    texts = {p.stem: p.read_text() for p in (ROOT / ".github" / "workflows").glob("*.yml")}
    for subject, wf in dd.BOT_SUBJECTS.items():
        assert subject in texts[wf], (subject, wf)


def test_a_glob_in_git_add_names_its_workflow():
    table = {"data": ["daily_sync"], "data/momentum_health_*.csv": ["momentum_health"]}
    assert dd.writer_of("data/momentum_health_750.csv", table) == "momentum_health"
