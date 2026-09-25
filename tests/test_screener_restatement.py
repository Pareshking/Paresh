"""A split/bonus reaches the Screener store, then Screener restates it -- after
a lag nobody can predict (owner, 2026-09-25: "1, 2 or 10 days or it might be
anything"). Replayed night by night against a simulated Screener, with the lag
drawn at random.

The simulated Screener behaves as the real one does:
- the nightly request returns the last WINDOW sessions, daily;
- the deep request returns every 5th session over the whole history (weekly);
- until `event + lag` it serves raw prices (a one-day step at the event);
  from then on every price before the event is multiplied by the factor, and
  volume by its inverse.
"""

from __future__ import annotations

import random

import numpy as np
import pandas as pd
import pytest

from src.engine.corporate_actions import adjust_prices, detect
from src.loaders import screener_loader as sl
from src.loaders.screener_restatement import rebase_store, rebase_symbol

WINDOW = 250          # sessions in the nightly daily window (~one year)
SESSIONS = 700
EVENT = 450           # session index of the ex-date


class FakeScreener:
    def __init__(self, seed: int, factor: float = 0.5, lag: int = 0, event: int = EVENT):
        rng = np.random.default_rng(seed)
        self.dates = pd.bdate_range("2023-01-02", periods=SESSIONS)
        steps = rng.normal(0.0, 0.012, SESSIONS)
        self.raw = 1000.0 * np.exp(np.cumsum(steps))
        self.raw[event:] *= factor                       # the event, unadjusted
        self.vol = rng.integers(50_000, 150_000, SESSIONS).astype(float)
        self.vol[event:] /= factor                       # more shares after a bonus
        self.adjusted = self.raw.copy()
        self.adjusted[:event] *= factor
        self.adj_vol = self.vol.copy()
        self.adj_vol[:event] /= factor
        # A control stock with no event: nothing may ever touch it.
        self.ctrl = 200.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, SESSIONS)))
        self.factor, self.lag, self.event = factor, lag, event

    def _frame(self, night: int, rows: np.ndarray) -> pd.DataFrame:
        restated = night >= self.event + self.lag
        close = self.adjusted if restated else self.raw
        vol = self.adj_vol if restated else self.vol
        idx = self.dates[rows]
        return pd.concat({
            "AAA": pd.DataFrame({"Close": np.round(close[rows], 2), "Volume": vol[rows]}, index=idx),
            "CTRL": pd.DataFrame({"Close": np.round(self.ctrl[rows], 2),
                                  "Volume": np.full(len(rows), 1000.0)}, index=idx),
        }, axis=1)

    def daily(self, night: int) -> pd.DataFrame:
        return self._frame(night, np.arange(max(0, night - WINDOW + 1), night + 1))

    def deep(self, night: int) -> pd.DataFrame:
        return self._frame(night, np.arange(0, night + 1, 5))

    def truth(self, dates: pd.DatetimeIndex) -> pd.Series:
        return pd.Series(self.adjusted, index=self.dates).reindex(dates)


def _replay(fake: FakeScreener, path: str, first: int, last: int,
            deep_every: int | None = None) -> dict[str, dict]:
    """Bootstrap the store at night `first`, then run every night to `last`."""
    sl.merge_into_store(fake.deep(first), path=path)
    sl.merge_into_store(fake.daily(first), path=path)
    rebased: dict[str, dict] = {}
    for night in range(first + 1, last + 1):
        deep = deep_every and (night - first) % deep_every == 0
        sl.merge_into_store(fake.deep(night) if deep else fake.daily(night),
                            path=path, rebased=rebased)
    return rebased


def _closes(path: str) -> pd.DataFrame:
    return sl.closes(pd.read_parquet(path))


def _max_step(series: pd.Series) -> float:
    s = series.dropna()
    return float(np.abs(np.diff(np.log(s.to_numpy()))).max())


def _random_lags(n: int, high: int) -> list[int]:
    rng = random.Random(20260925)
    return [0, 1] + [rng.randint(2, high) for _ in range(n)]


@pytest.mark.parametrize("lag", _random_lags(8, WINDOW - 10))
def test_restatement_after_any_lag_puts_the_whole_history_on_one_basis(tmp_path, lag):
    fake = FakeScreener(seed=lag, lag=lag)
    path = str(tmp_path / "store.parquet")
    rebased = _replay(fake, path, first=EVENT - 30, last=EVENT + lag + 5)

    c = _closes(path)
    want = fake.truth(c.index)
    np.testing.assert_allclose(c["AAA"].to_numpy(), want.to_numpy(), rtol=2e-4)
    assert _max_step(c["AAA"]) < 0.1                     # no fake -50% anywhere
    assert set(rebased) == {"AAA"}                       # the control is untouched
    assert rebased["AAA"]["factors"][0] == pytest.approx(fake.factor, rel=1e-3)
    vol = sl.volumes(pd.read_parquet(path))["AAA"]
    np.testing.assert_allclose(
        vol.to_numpy(), pd.Series(fake.adj_vol, index=fake.dates).reindex(vol.index).to_numpy(),
        rtol=1e-9)


@pytest.mark.parametrize("lag", _random_lags(3, 60)[1:])
def test_during_the_lag_the_step_is_detected_and_neutralised(tmp_path, lag):
    """Every night before Screener restates, the step is in the store; the
    detector finds it and adjust_prices removes it. The night after, the same
    logged event must change nothing (it would double-adjust otherwise)."""
    fake = FakeScreener(seed=100 + lag, lag=lag)
    path = str(tmp_path / "store.parquet")
    _replay(fake, path, first=EVENT - 30, last=EVENT + lag - 1)

    c = _closes(path)
    found = detect(c, since=c.index[-WINDOW])
    assert list(found["Symbol"]) == ["AAA"]
    assert found.iloc[0]["Date"] == fake.dates[EVENT]
    events = [{"symbol": "AAA", "date": str(fake.dates[EVENT].date()),
               "ratio": float(found.iloc[0]["Ratio"])}]
    adjusted, applied = adjust_prices(c, events)
    assert len(applied) == 1
    assert _max_step(adjusted["AAA"]) < 0.1

    sl.merge_into_store(fake.daily(EVENT + lag), path=path)   # Screener restates
    after = _closes(path)
    unchanged, applied = adjust_prices(after, events)
    assert applied == []
    pd.testing.assert_frame_equal(unchanged, after)
    assert detect(after, since=after.index[-WINDOW]).empty


def test_a_restatement_older_than_the_window_needs_the_deep_check(tmp_path):
    """Screener restates after the event has left the daily window: the nightly
    fetch cannot see it, the weekly deep comparison does."""
    lag = WINDOW + random.Random(3).randint(5, 60)
    fake = FakeScreener(seed=7, lag=lag, event=300)
    nightly = str(tmp_path / "nightly.parquet")
    _replay(fake, nightly, first=280, last=300 + lag + 3)
    assert _max_step(_closes(nightly)["AAA"]) > 0.5      # the stale step remains

    weekly = str(tmp_path / "weekly.parquet")
    rebased = _replay(fake, weekly, first=280, last=300 + lag + 10, deep_every=7)
    c = _closes(weekly)
    np.testing.assert_allclose(c["AAA"].to_numpy(), fake.truth(c.index).to_numpy(), rtol=2e-4)
    assert _max_step(c["AAA"]) < 0.1
    assert set(rebased) == {"AAA"}


def _one(dates, closes, vols=None) -> pd.DataFrame:
    return pd.DataFrame({"Close": closes, "Volume": vols if vols is not None else 1.0},
                        index=pd.DatetimeIndex(dates))


def test_isolated_price_corrections_are_not_restatements():
    dates = pd.bdate_range("2026-01-01", periods=30)
    stored = _one(dates, np.linspace(100, 130, 30))
    ref = stored.iloc[10:].copy()
    ref.iloc[[3, 12], 0] *= 1.08                         # Screener fixed two closes
    out, info = rebase_symbol(stored, ref)
    assert info is None
    pd.testing.assert_frame_equal(out, stored)


def test_rounding_noise_is_never_a_factor():
    dates = pd.bdate_range("2026-01-01", periods=40)
    stored = _one(dates, np.round(np.linspace(10, 12, 40), 2))
    ref = stored.iloc[15:].copy()
    ref["Close"] = ref["Close"] * 1.004                  # inside 1%
    assert rebase_symbol(stored, ref)[1] is None


def test_a_demerger_factor_is_applied_but_volume_left_when_screener_did_not_adjust_it():
    dates = pd.bdate_range("2026-01-01", periods=40)
    stored = _one(dates, np.linspace(200, 240, 40), np.full(40, 500.0))
    ref = stored.iloc[20:].copy()
    ref.iloc[:10, 0] *= 0.87                             # restated before the ex-date
    out, info = rebase_symbol(stored, ref)
    assert info["factors"] == [pytest.approx(0.87), 1.0]
    assert info["volume_rescaled"] is False
    np.testing.assert_allclose(out["Close"].iloc[:20], stored["Close"].iloc[:20] * 0.87)
    pd.testing.assert_series_equal(out["Volume"], stored["Volume"])


def test_two_events_rescale_each_stretch_by_its_own_factor():
    dates = pd.bdate_range("2026-01-01", periods=60)
    base = np.linspace(100, 160, 60)
    stored = _one(dates, base)
    ref = stored.iloc[10:].copy()
    ref.iloc[:20, 0] *= 0.25                             # before both events
    ref.iloc[20:35, 0] *= 0.5                            # between them
    out, info = rebase_symbol(stored, ref)
    assert info["factors"] == [pytest.approx(0.25), pytest.approx(0.5), 1.0]
    np.testing.assert_allclose(out["Close"].iloc[:10], base[:10] * 0.25)


def test_a_gap_around_the_event_is_split_where_the_step_is():
    """The reference lacks the dates either side of the event; the stored step
    tells where the old basis ends."""
    dates = pd.bdate_range("2026-01-01", periods=40)
    raw = np.full(40, 100.0)
    raw[20:] = 50.0                                      # 1:1 bonus on day 20
    stored = _one(dates, raw)
    adjusted = np.full(40, 50.0)
    keep = [i for i in range(40) if not 16 <= i <= 23]
    ref = _one(dates[keep], adjusted[keep])
    out, info = rebase_symbol(stored, ref)
    assert info is not None
    merged = ref.combine_first(out)                      # as merge_into_store does
    np.testing.assert_allclose(merged["Close"].to_numpy(), adjusted)


def test_rebase_store_leaves_symbols_the_reference_does_not_carry():
    dates = pd.bdate_range("2026-01-01", periods=20)
    stored = pd.concat({"AAA": _one(dates, np.full(20, 10.0)),
                        "BBB": _one(dates, np.full(20, 30.0))}, axis=1)
    ref = pd.concat({"AAA": _one(dates[5:], np.full(15, 5.0))}, axis=1)
    out, report = rebase_store(stored, ref)
    assert set(report) == {"AAA"}
    np.testing.assert_allclose(out[("AAA", "Close")].iloc[:5], 5.0)
    pd.testing.assert_frame_equal(out["BBB"], stored["BBB"])
    assert list(out.columns) == list(stored.columns)


def test_deep_check_is_due_a_week_after_the_last_one_and_when_never_run(tmp_path, monkeypatch):
    from datetime import date

    import scripts.sync_screener as sync

    monkeypatch.delenv("SCREENER_DEEP_CHECK", raising=False)
    state = str(tmp_path / "deep.json")
    assert sync._deep_check_due(date(2026, 9, 25), state) is True     # never run
    sync._record_deep_check(date(2026, 9, 25), state)
    assert sync._deep_check_due(date(2026, 10, 1), state) is False    # 6 days
    assert sync._deep_check_due(date(2026, 10, 2), state) is True     # 7 days
    assert sync._deep_check_due(date(2026, 10, 9), state) is True     # a late run still checks
    monkeypatch.setenv("SCREENER_DEEP_CHECK", "1")
    assert sync._deep_check_due(date(2026, 9, 26), state) is True


def test_the_screener_check_scans_only_the_daily_tail_and_logs_the_source(tmp_path, monkeypatch):
    import json
    import sys

    import scripts.check_corporate_actions as cca

    fake = FakeScreener(seed=5, lag=10)
    store = str(tmp_path / "store.parquet")
    _replay(fake, store, first=EVENT - 30, last=EVENT + 3)       # inside the lag
    monkeypatch.setattr("src.core.config.SCREENER_PRICES_FILE", store)
    log = tmp_path / "log.json"
    monkeypatch.setattr(sys, "argv", ["x", "--source", "screener", "--log", str(log)])
    assert cca.main() == 0
    events = json.loads(log.read_text())["events"]
    assert list(events) == [f"{fake.dates[EVENT].date()}:AAA"]
    assert events[f"{fake.dates[EVENT].date()}:AAA"]["source"] == "screener"


def test_daily_start_skips_the_weekly_history():
    import scripts.check_corporate_actions as cca

    weekly = pd.date_range("2024-01-05", periods=20, freq="W-FRI")
    daily = pd.bdate_range("2024-06-03", periods=30)
    assert cca.daily_start(weekly.append(daily)) == daily[0]
