"""The volume test's findings must reach the calendar, with their evidence.

The zero-volume test reads something no coverage threshold can: a session where
every priced symbol is flat at zero volume is one on which nothing changed
hands. It found four such sessions in the published frame, and TWO OF THEM SAT
AT 100% VENDOR COVERAGE -- 2026-05-28 and 2026-06-26 -- where no floor of any
value could ever have reached them.

Leaving that knowledge inside the loader means re-deriving it from the whole
frame on every read, and means a human cannot see it at all. Written into the
calendar it becomes a fact with a source attached.

It is recorded as EVIDENCE, not as an assertion that NSE declared a holiday.
The source string says what was observed and at what coverage, so a wrong entry
traces back to the run that made it instead of appearing as an anonymous date
somebody once decided was closed. The exchange still outranks it: record_closed
refuses any date NSE published a bhavcopy for.

The loader-side volume test lived in the Yahoo price cache and was removed with
it (TODO S10, 13 Oct 2026); the calendar's half below is still live.
"""

import json


from src.loaders.trading_days import (
    load_closed, load_confirmed, record_closed, record_confirmed,
)


def test_a_finding_is_recorded_with_what_was_observed(tmp_path):
    """The source must be auditable, not an anonymous assertion."""
    path = str(tmp_path / "days.json")
    added, total = record_closed(
        ["2026-05-28"],
        source="zero-volume evidence (100% priced, all flat at zero volume)",
        path=path,
    )
    assert (added, total) == (1, 1)
    payload = json.loads(open(path).read())
    src = payload["closed_days_source"]["2026-05-28"]
    assert "zero-volume evidence" in src
    assert "100%" in src, "the coverage that decided it was not written down"


def test_the_exchange_still_outranks_the_volume_test(tmp_path):
    """A bhavcopy beats a heuristic, however confident the heuristic is.

    Without this, one bad reading would delete a real session permanently --
    the precise failure the confirmations-only rule exists to prevent, arriving
    through the automated door instead of a human one.
    """
    path = str(tmp_path / "days.json")
    record_confirmed({"2026-05-28"}, path)
    added, _ = record_closed(
        ["2026-05-28"], source="zero-volume evidence (100% priced)", path=path
    )
    assert added == 0
    assert load_closed(path) == set()
    assert load_confirmed(path) == {"2026-05-28"}


def test_learning_the_same_day_twice_rewrites_nothing(tmp_path):
    """The job runs daily over the same 45-day window; it must not churn."""
    path = str(tmp_path / "days.json")
    record_closed(["2026-05-28"], source="zero-volume evidence (100% priced)", path=path)
    before = open(path).read()
    added, _ = record_closed(
        ["2026-05-28"], source="zero-volume evidence (100% priced)", path=path
    )
    assert added == 0
    assert open(path).read() == before


def test_learned_closures_and_human_ones_coexist(tmp_path):
    """Both write the same field, and neither may erase the other's source."""
    path = str(tmp_path / "days.json")
    record_closed(["2026-09-14"], source="user-confirmed NSE holiday", path=path)
    record_closed(["2026-05-28"], source="zero-volume evidence (100% priced)", path=path)
    sources = json.loads(open(path).read())["closed_days_source"]
    assert sources["2026-09-14"] == "user-confirmed NSE holiday"
    assert "zero-volume" in sources["2026-05-28"]
    assert load_closed(path) == {"2026-09-14", "2026-05-28"}


