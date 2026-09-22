"""Regression coverage for current-universe-driven Screener acquisition."""

from scripts.sync_screener import current_universe_delta


def test_new_symbols_are_forced_into_acquisition_set():
    current = ["AAA", "BBB", "HEGAM", *[f"NEW{i:02d}" for i in range(10)]]
    stored = ["AAA", "BBB", "HEG", *[f"OLD{i:02d}" for i in range(10)]]

    new_current, exited = current_universe_delta(current, stored)

    assert new_current == ["HEGAM", *[f"NEW{i:02d}" for i in range(10)]]
    assert exited == ["HEG", *[f"OLD{i:02d}" for i in range(10)]]


def test_index_reclassification_does_not_look_like_a_new_security():
    # The index bucket is not part of identity. A SMALL250 -> MID150 move keeps
    # the same symbol and therefore must not trigger another history download.
    current = ["AAA", "MOVED"]
    stored = ["AAA", "MOVED"]

    new_current, exited = current_universe_delta(current, stored)

    assert new_current == []
    assert exited == []


def test_exited_symbols_are_not_current_acquisition_targets():
    current = ["AAA"]
    stored = ["AAA", "EXIT1", "EXIT2"]

    new_current, exited = current_universe_delta(current, stored)

    assert new_current == []
    assert exited == ["EXIT1", "EXIT2"]


def test_dummy_symbols_are_not_added_by_the_delta_when_loader_has_filtered_them():
    # sync_screener consumes the already filtered authoritative universe. This
    # fixture mirrors that contract: DUMMY placeholders must never be present
    # in current_symbols, even when an old store still contains one.
    current = ["AAA", "BBB"]
    stored = ["AAA", "BBB", "DUMMYHEG"]

    new_current, exited = current_universe_delta(current, stored)

    assert new_current == []
    assert exited == ["DUMMYHEG"]
