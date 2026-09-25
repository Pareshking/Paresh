"""Sync/Purge clear every reader's cache, so one clear per window, process-wide."""
from src.ui.views import config_view as cv


def test_one_global_clear_per_window(monkeypatch):
    monkeypatch.setattr(cv, "_last_global_refresh", [float("-inf")])
    assert cv._claim_global_refresh(now=1000.0) == 0.0
    wait = cv._claim_global_refresh(now=1060.0)
    assert wait == cv.GLOBAL_REFRESH_COOLDOWN_S - 60
    # A refused click does not extend the window.
    assert cv._claim_global_refresh(now=1000.0 + cv.GLOBAL_REFRESH_COOLDOWN_S) == 0.0
