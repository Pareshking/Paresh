from src.core import startup_metrics as metrics


def test_note_if_changed_reports_only_new_value():
    metrics.reset_for_tests()

    assert metrics.note_if_changed("x", "first") is True
    assert metrics.note_if_changed("x", "first") is False
    assert metrics.note_if_changed("x", "second") is True
    # Dedupe state, not a fact: it must never reach the page-embedded snapshot.
    assert "x" not in metrics.snapshot()["facts"]


def test_note_if_changed_distinguishes_equal_values_after_other_facts():
    metrics.reset_for_tests()

    assert metrics.note_if_changed("price_source_selection_key", "screener|2026-09-22") is True
    metrics.note("unrelated", 123)
    assert metrics.note_if_changed("price_source_selection_key", "screener|2026-09-22") is False


def test_dedupe_keys_never_reach_the_served_snapshot():
    metrics.reset_for_tests()
    metrics.note_if_changed("price_source_selection_key", "screener|2026-09-22")
    metrics.note_if_changed("ranking_precompute_rejection_key", "x" * 20_000)
    facts = metrics.public_snapshot()["facts"]
    assert "price_source_selection_key" not in facts
    assert "ranking_precompute_rejection_key" not in facts
