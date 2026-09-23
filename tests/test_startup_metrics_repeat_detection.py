from src.core import startup_metrics as metrics


def test_note_if_changed_reports_only_new_value():
    metrics.reset_for_tests()

    assert metrics.note_if_changed("x", "first") is True
    assert metrics.note_if_changed("x", "first") is False
    assert metrics.note_if_changed("x", "second") is True
    assert metrics.snapshot()["facts"]["x"] == "second"


def test_note_if_changed_distinguishes_equal_values_after_other_facts():
    metrics.reset_for_tests()

    assert metrics.note_if_changed("price_source_selection_key", "screener|2026-09-22") is True
    metrics.note("unrelated", 123)
    assert metrics.note_if_changed("price_source_selection_key", "screener|2026-09-22") is False
