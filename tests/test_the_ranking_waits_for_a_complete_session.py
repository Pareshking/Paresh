"""The ranking must land on a session the vendor has finished publishing.

The engine reads each symbol's CLOSING price as a real observation -- p1 comes
straight from the frame and is never forward-filled (calendar_momentum says so
deliberately). So a symbol with no print on the final session scores NaN across
every horizon and leaves the table.

Correct per symbol, wrong for the universe. Yahoo publishes an Indian session
over roughly two days, measured on the live snapshot for 2026-09-17:

    23:30 IST that night     150/750   20%
    next morning             378/750   50%
    a day later              750/750  100%

Ranking on that session is not a fresher table, it is a table of whichever half
the vendor published first -- selected by vendor latency, not by momentum.

This never showed until 2026-09-18 because the coverage floor deleted the thin
session outright, so the ranking landed on the previous one by accident. Fixing
the floor to KEEP real sessions took that accident away: the published run of
2026-09-18 ranked 378 names instead of 750, and the next scheduled run would
have ranked about 150.

History and ranking date are separate questions, and these tests pin the
separation: every real session stays in the frame, the engine stops at the
newest complete one.
"""

import numpy as np
import pandas as pd
import pytest

from src.engine.pipeline import (
    MAX_UNRANKED_TAIL,
    RANKING_COVERAGE_FLOOR,
    _trim_to_ranked_session,
    last_ranked_session,
    ranking_as_of,
)


def _frame(coverages, start="2026-01-01", n_cols=750):
    """One row per coverage fraction, NaN-padded to that fraction."""
    idx = pd.bdate_range(start, periods=len(coverages))
    rows = []
    for c in coverages:
        have = int(round(c * n_cols))
        rows.append([100.0] * have + [np.nan] * (n_cols - have))
    return pd.DataFrame(rows, index=idx, columns=[f"S{i}" for i in range(n_cols)])


def test_the_engine_stops_before_a_half_published_session():
    """The exact shape of the 2026-09-18 published run: 500 rows, 50% tail."""
    df = _frame([1.0] * 499 + [0.504])
    pos = last_ranked_session(df)
    assert pos == len(df.index) - 2, "the ranking landed on the unfinished session"


@pytest.mark.parametrize("tail", [0.20, 0.50, 0.63, 0.82])
def test_every_coverage_the_vendor_actually_showed_is_deferred(tail):
    """20% and 50% were measured on 2026-09-17; 63% and 82% on other dates."""
    df = _frame([1.0] * 30 + [tail])
    assert last_ranked_session(df) == len(df.index) - 2


def test_a_complete_session_is_ranked_immediately():
    """Nothing is deferred once the vendor has finished -- no built-in lag."""
    df = _frame([1.0] * 30)
    assert last_ranked_session(df) == len(df.index) - 1
    frames, cutoff = _trim_to_ranked_session(df)
    assert cutoff is None, "a complete session was held back for no reason"


def test_a_session_missing_any_current_symbol_is_deferred():
    """The floor is a real boundary, not a demand for a perfect 100%.

    A handful of the universe can legitimately have no print -- suspended,
    halted, newly delisted -- and that must not defer the whole table.
    """
    df = _frame([1.0] * 30 + [RANKING_COVERAGE_FLOOR + 0.02])
    assert last_ranked_session(df) == len(df.index) - 1


def test_history_that_thins_out_with_age_is_not_mistaken_for_incompleteness():
    """Older rows are legitimately sparse, and an absolute floor would misread it.

    A stock that listed in 2025 is NaN for every session before it, so a 2024
    row can sit at 60% coverage while being perfectly complete. Coverage is
    judged against the RECENT norm for exactly this reason.
    """
    df = _frame([0.55] * 200 + [0.75] * 200 + [1.0] * 30)
    assert last_ranked_session(df) == len(df.index) - 1, (
        "an old, legitimately sparse history pushed the ranking date backwards"
    )


def test_nothing_moves_when_the_whole_tail_is_thin():
    """Beyond max_back the rule gives up rather than hide real sessions.

    Walking back indefinitely to chase a threshold is the failure this area
    already had once, in the other direction.
    """
    df = _frame([1.0] * 30 + [0.2] * (MAX_UNRANKED_TAIL + 2))
    assert last_ranked_session(df) is None
    frames, cutoff = _trim_to_ranked_session(df)
    assert cutoff is None and frames[0] is df


def test_the_frame_keeps_every_real_session():
    """Deferring the ranking date must never delete history.

    The archive, the charts and every return calculation need the session; only
    the engine stops short of it.
    """
    df = _frame([1.0] * 30 + [0.5])
    trimmed, cutoff = _trim_to_ranked_session(df)
    assert len(df) == 31, "the source frame was mutated"
    assert len(trimmed[0]) == 30
    assert cutoff == df.index[-2]


def test_the_label_always_matches_the_table():
    """as-of comes from the same rule the engine uses, or they disagree.

    Stamping the snapshot with the frame's last row would label the table with
    a session it never scored -- and nothing downstream could tell.
    """
    df = _frame([1.0] * 30 + [0.5])
    trimmed, _ = _trim_to_ranked_session(df)
    assert ranking_as_of(df) == str(trimmed[0].index[-1].date())
    assert ranking_as_of(df) == str(df.index[-2].date())


def test_every_frame_is_cut_to_the_same_session():
    """A frame left one row long reads its prices past everything scored."""
    df = _frame([1.0] * 30 + [0.5])
    others = [df.copy() for _ in range(4)]
    trimmed, cutoff = _trim_to_ranked_session(df, *others)
    assert cutoff is not None
    assert {len(f) for f in trimmed} == {30}


def test_trimming_twice_changes_nothing():
    """build_engine and rank_with_weights both apply it to the same frames."""
    df = _frame([1.0] * 30 + [0.5])
    once, c1 = _trim_to_ranked_session(df)
    twice, c2 = _trim_to_ranked_session(once[0])
    assert len(once[0]) == len(twice[0]) == 30
    assert c2 is None, "a second pass moved the date again"


def test_an_empty_or_degenerate_frame_is_left_alone():
    for df in (pd.DataFrame(), None, _frame([])):
        frames, cutoff = _trim_to_ranked_session(df)
        assert cutoff is None
    assert last_ranked_session(pd.DataFrame()) is None
    assert last_ranked_session(None) is None
    assert ranking_as_of(pd.DataFrame()) == ""
