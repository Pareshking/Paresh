"""The data workflows' push-retry must keep THIS run's data on a rebase conflict."""
import pathlib
import re

WORKFLOWS = sorted(pathlib.Path(".github/workflows").glob("*.yml"))


def test_rebase_conflicts_keep_the_replayed_commit():
    """In a rebase, --ours is origin/main. Taking it dropped the sync commit.

    Reproduced: the commit vanished, the next `git push` reported
    "Everything up-to-date" and the step printed "Pushed" with nothing pushed.
    """
    offenders = []
    for path in WORKFLOWS:
        text = path.read_text(encoding="utf-8")
        if "git rebase" in text and re.search(r"git checkout --ours\b", text):
            offenders.append(path.name)
    assert offenders == []


def test_rebase_continue_never_waits_for_an_editor():
    seen = []
    for path in WORKFLOWS:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "git rebase --continue" in line:
                seen.append(path.name)
                assert "GIT_EDITOR=true" in line, path.name
    # Without this, renaming the step (or the glob finding nothing) would pass.
    assert seen, "no workflow runs `git rebase --continue`; is this test stale?"


def test_every_writer_of_the_screener_store_shares_one_queue():
    groups = set()
    for path in WORKFLOWS:
        text = path.read_text(encoding="utf-8")
        if "gh release upload" in text and "screener_prices.parquet" in text:
            groups.add(re.search(r"concurrency:\s*\n(?:\s*#.*\n)*\s*group:\s*(\S+)", text).group(1))
    assert len(groups) == 1, groups
