"""When NSE shuts the door, the caps come from Yahoo rather than staying undated.

NSE refuses the GitHub runner's IP outright, so the PR archive is not merely
late here -- it is unreachable and always will be. That left the committed
market caps permanently undated, and the footer permanently saying so.

Yahoo answers the runner fine; the daily prices already come from there. It is
skipped in the LIVE app only because market cap has no bulk endpoint the way
prices do, so it costs one request per company. The nightly job is the one
place that cost can be paid once for everyone.
"""
import numpy as np
import pytest

from src.loaders import mcap_loader


def test_the_sweep_ignores_every_cache_and_asks_yahoo_directly(monkeypatch):
    asked = {}

    def fake(symbols):
        asked["symbols"] = list(symbols)
        return {s: 1_000.0 for s in symbols}

    monkeypatch.setattr(mcap_loader, "_fetch_mcaps_yfinance", fake)
    out = mcap_loader.fetch_mcaps_from_yfinance(["AAA", "BBB"])

    assert asked["symbols"] == ["AAA", "BBB"]
    assert list(out.index) == ["AAA", "BBB"]
    assert out.dtype == float


@pytest.mark.parametrize("bad", [np.nan, 0.0, -5.0, None])
def test_unusable_values_are_dropped_rather_than_carried(monkeypatch, bad):
    """A cap of zero, NaN or negative is not a small company, it is no answer."""
    monkeypatch.setattr(
        mcap_loader, "_fetch_mcaps_yfinance",
        lambda symbols: {"AAA": 1_000.0, "BBB": bad},
    )
    out = mcap_loader.fetch_mcaps_from_yfinance(["AAA", "BBB"])

    assert list(out.index) == ["AAA"]


def test_an_empty_answer_is_an_empty_series_not_a_crash(monkeypatch):
    monkeypatch.setattr(mcap_loader, "_fetch_mcaps_yfinance", lambda symbols: {})
    out = mcap_loader.fetch_mcaps_from_yfinance(["AAA"])

    assert out.empty
    assert out.dtype == float


# ── The decision the sync makes with that answer ────────────────────────────
# Called, not restated: an earlier version tested its own copy of this rule,
# which would have stayed green with the sync's rule changed or deleted.

def test_a_full_sweep_replaces_the_undated_snapshot():
    from scripts.sync_data import mcap_sweep_is_adoptable as adoptable

    assert adoptable(750, 750) is True
    assert adoptable(700, 750) is True          # 93%
    assert adoptable(675, 750) is True          # exactly 90%


def test_a_thin_sweep_leaves_the_snapshot_alone():
    """Coverage matters more than a date.

    The caps exist to say which size bucket a stock sits in. A stock with no
    cap at all is worse than one whose cap is a day old, so a sparse Yahoo
    answer must not be adopted just because it would carry today's date.
    """
    from scripts.sync_data import mcap_sweep_is_adoptable as adoptable

    assert adoptable(674, 750) is False         # just under 90%
    assert adoptable(400, 750) is False         # 53%
    assert adoptable(0, 750) is False
    assert adoptable(0, 0) is False             # an empty universe adopts nothing


def test_the_sync_applies_that_rule_and_adopts_wholesale():
    import inspect

    import scripts.sync_data as sync

    src = inspect.getsource(sync.run_daily_sync)
    assert "mcap_sweep_is_adoptable(len(_yf_caps), len(symbols))" in src
    assert "fetch_mcaps_from_yfinance" in src
    # Wholesale, never merged -- two days under one AsOf is the thing to avoid.
    assert "mcaps = _yf_caps" in src
    assert sync.MIN_MCAP_COVERAGE == 0.9


def test_the_snapshot_records_which_door_the_number_came_through():
    import inspect

    import scripts.sync_data as sync

    src = inspect.getsource(sync.run_daily_sync)
    assert 'snapshot["Source"] = _mcap_path' in src
