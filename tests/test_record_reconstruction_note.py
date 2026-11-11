"""Portfolio is the only page that shows the track record (track-record redirects
there), so it must show the note saying how many months are backfilled
(audit 11 Nov 2026, Q-H1). The since-inception tiles compound backfilled months
with recorded ones; without the note a reader cannot tell a backtest from evidence."""

import inspect

from src.ui.views import portfolio_view, track_record_view


def test_portfolio_keeps_the_reconstruction_note():
    src = inspect.getsource(portfolio_view)
    assert "render_record_sections(" in src
    assert "show_reconstruction_note=False" not in src


def test_note_says_backfilled_months_are_a_backtest():
    src = inspect.getsource(track_record_view.render_record_sections)
    assert "a backtest, not evidence" in src
    assert inspect.signature(track_record_view.render_record_sections).parameters[
        "show_reconstruction_note"].default is True
