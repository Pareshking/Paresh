"""Screener's weekly stretch filled with NSE's daily moves (TODO S23, owner 2026-10-07).

The splice is by ratio, interval by interval: every Screener close stays as
Screener has it, the sessions between two of them follow NSE's daily path from
the left one, and an interval where NSE's move disagrees with Screener's by
more than the tolerance is not filled.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from src.loaders import price_source as ps

ROOT = Path(__file__).resolve().parents[1]

# NSE's calendar: 120 sessions. Screener: every 5th session for the first 80
# (weekly), then every session (daily).
SESSIONS = pd.bdate_range("2025-01-06", periods=120)
WEEKLY = SESSIONS[:80:5]
DAILY = SESSIONS[80:]


def _nse(seed=1, cols=("A",)):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({c: 100 * np.exp(np.cumsum(rng.normal(0, 0.015, len(SESSIONS))))
                         for c in cols}, index=SESSIONS)


def _screener(nse, factor=1.0):
    """Screener's points: NSE's closes times a constant (another adjustment basis)."""
    idx = WEEKLY.append(DAILY)
    return (nse.reindex(idx) * factor).astype(float)


def test_every_screener_close_stays_and_the_gaps_follow_nses_daily_path():
    nse = _nse()
    scr = _screener(nse, factor=0.9)          # Screener's level 10% under NSE's
    out, rep = ps.fill_weekly_from_nse(scr, nse)
    # Screener's own closes, exactly
    assert (out.loc[scr.index, "A"] == scr["A"]).all()
    # the weekly stretch is now daily: every NSE session up to the daily stretch
    assert out.index.equals(SESSIONS)
    # on Screener's level, not NSE's ...
    a, t = WEEKLY[3], SESSIONS[17]
    assert np.isclose(out.at[t, "A"], scr.at[a, "A"] * nse.at[t, "A"] / nse.at[a, "A"])
    assert np.isclose(out.at[t, "A"] / nse.at[t, "A"], 0.9)
    # ... and with NSE's daily moves
    moves = (out["A"] / out["A"].shift(1)).iloc[1:80]
    assert np.allclose(moves, (nse["A"] / nse["A"].shift(1)).iloc[1:80])
    assert rep["intervals_refused"] == 0 and rep["sessions_added"] == 64 and rep["symbols"] == 1


def test_a_stretch_where_nse_and_screener_disagree_is_kept_weekly_and_listed():
    nse = _nse()
    scr = _screener(nse)
    # An action NSE adjusted and Screener did not, between Screener's 4th and
    # 5th weekly closes: every NSE close before session 17 scaled by 0.8.
    nse_adj = nse.copy()
    nse_adj.iloc[:17] *= 0.8
    out, rep = ps.fill_weekly_from_nse(scr, nse_adj)
    a, b = WEEKLY[3], WEEKLY[4]
    inside = out.loc[(out.index > a) & (out.index < b), "A"]
    assert inside.isna().all()                               # not filled
    assert out.at[a, "A"] == scr.at[a, "A"] and out.at[b, "A"] == scr.at[b, "A"]
    assert rep["refused"] == [{"symbol": "A", "from": str(a.date()), "to": str(b.date()),
                               "nse_vs_screener": round(1 / 0.8 - 1, 4)}]
    # the other intervals are filled, on Screener's level on both sides of the action
    assert out.loc[(out.index > WEEKLY[1]) & (out.index < WEEKLY[2]), "A"].notna().all()
    t = SESSIONS[7]
    assert np.isclose(out.at[t, "A"], nse.at[t, "A"])        # 0.8 does not leak in


def test_a_disagreement_inside_the_tolerance_is_filled():
    nse = _nse()
    scr = _screener(nse)
    scr.loc[WEEKLY[5], "A"] *= 1.015                         # 1.5% off: within 2%
    out, rep = ps.fill_weekly_from_nse(scr, nse)
    assert rep["intervals_refused"] == 0
    assert out.loc[(out.index > WEEKLY[4]) & (out.index < WEEKLY[5]), "A"].notna().all()
    assert out.at[WEEKLY[5], "A"] == scr.at[WEEKLY[5], "A"]


def test_nothing_is_filled_where_screener_is_daily():
    nse = _nse()
    scr = _screener(nse)
    hole = DAILY[25]
    scr.loc[hole, "A"] = np.nan                              # a hole in the daily stretch
    out, rep = ps.fill_weekly_from_nse(scr, nse)
    assert np.isnan(out.at[hole, "A"])
    assert (out.loc[DAILY].dropna().index == scr.loc[DAILY, "A"].dropna().index).all()
    added = out.index.difference(scr.index)
    assert added.max() < DAILY[0]


def test_a_series_that_is_never_daily_is_left_alone():
    nse = _nse()
    scr = nse.reindex(SESSIONS[::5])
    out, rep = ps.fill_weekly_from_nse(scr, nse)
    assert out is scr and rep["cells"] == 0


def test_nothing_before_the_first_screener_close_or_nses_first_session():
    nse = _nse()
    scr = _screener(nse)
    scr.loc[WEEKLY[:3], "A"] = np.nan                        # Screener starts at WEEKLY[3]
    out, _ = ps.fill_weekly_from_nse(scr, nse.iloc[30:])     # NSE starts at session 30
    assert out.loc[: SESSIONS[29], "A"].dropna().index.isin(scr.index).all()
    assert out.loc[SESSIONS[31]:SESSIONS[34], "A"].notna().all()


def test_too_few_stocks_covered_means_no_sessions_are_added():
    """An added session where a stock has no price would delete its weekly return."""
    nse = _nse(cols=("A", "B", "C"))
    scr = _screener(nse)
    out, rep = ps.fill_weekly_from_nse(scr, nse[["A"]])      # NSE has 1 of 3
    assert out is scr and rep["skipped"] and rep["coverage"] == round(1 / 3, 4)
    out, rep = ps.fill_weekly_from_nse(scr, nse)
    assert rep["coverage"] == 1.0 and len(out) == len(SESSIONS)


def _frames(close):
    return ps.PriceFrames(adj_close=close, close=close, high=None, low=None,
                          volume=close * 0 + 1, source="screener", intraday=False, notes=[])


def _old_keep_and_fill(close, middle):
    """keep_and_fill as it was before the weekly fill."""
    mid = ps.eligible_middle(close, middle)
    if mid is not None:
        close, _, _ = ps.fill_from_backup(close, mid)
    return close


def test_flag_off_is_the_old_frame_exactly():
    end = pd.Timestamp.today().normalize()
    sessions = pd.bdate_range(end=end, periods=300)
    rng = np.random.default_rng(7)
    nse = pd.DataFrame({c: 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 300)))
                        for c in ("A", "B")}, index=sessions)
    scr = nse.reindex(sessions[:200:5].append(sessions[200:]))
    scr.loc[sessions[250], "A"] = np.nan                     # a daily hole for the old fill
    off = ps.keep_and_fill(_frames(scr.copy()), ["A", "B"], None, nse, weekly_fill=False)
    expected = _old_keep_and_fill(scr.copy(), nse)
    assert off.close.equals(expected) and off.weekly_fill is None
    on = ps.keep_and_fill(_frames(scr.copy()), ["A", "B"], None, nse, weekly_fill=True)
    assert len(on.close) > len(off.close)
    assert on.weekly_fill["cells"] > 0
    assert on.volume.index.equals(on.close.index)
    # Screener's closes are untouched with the fill on
    pts = scr.stack().dropna()
    assert np.allclose(on.close.stack().reindex(pts.index), pts)


def test_the_flag_defaults_to_the_config(monkeypatch):
    import src.core.config as cfg

    sessions = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=300)
    nse = pd.DataFrame({"A": np.linspace(100, 130, 300)}, index=sessions)
    scr = nse.reindex(sessions[:200:5].append(sessions[200:]))
    monkeypatch.setattr(cfg, "SCREENER_WEEKLY_NSE_FILL", False)
    off = ps.keep_and_fill(_frames(scr.copy()), ["A"], None, nse)
    assert off.weekly_fill is None and len(off.close) == len(scr)
    monkeypatch.setattr(cfg, "SCREENER_WEEKLY_NSE_FILL", True)
    on = ps.keep_and_fill(_frames(scr.copy()), ["A"], None, nse)
    assert on.weekly_fill["cells"] > 0


def test_the_setting_is_in_the_ranking_contract(monkeypatch):
    """A table precomputed with the fill on must not be served to an app with it off."""
    import src.core.config as cfg
    from src.engine import pipeline

    monkeypatch.setattr(cfg, "SCREENER_WEEKLY_NSE_FILL", True)
    on = pipeline.pipeline_version()
    monkeypatch.setattr(ps, "WEEKLY_FILL_TOLERANCE", 0.05)
    assert pipeline.pipeline_version() != on
    monkeypatch.setattr(cfg, "SCREENER_WEEKLY_NSE_FILL", False)
    assert pipeline.pipeline_version() != on


def test_the_app_and_the_precompute_take_the_setting_from_one_place():
    """Neither caller passes weekly_fill: both read config.SCREENER_WEEKLY_NSE_FILL."""
    for rel in ("app.py", "scripts/sync_data.py", "scripts/precompute_systems.py"):
        assert "weekly_fill=" not in (ROOT / rel).read_text(encoding="utf-8"), rel
    body = (ROOT / "src/loaders/price_source.py").read_text(encoding="utf-8")
    fn = body[body.index("def frames_from("):body.index("# ── Backup source")]
    assert "keep_and_fill(chosen, symbols, None, middle_close)" in fn


def test_the_committed_extra_closes_fill_only_what_nse_lacks(tmp_path):
    # Owner, 7 Oct: seven stocks NSE's file lacks (REITs, BSE-only before listing)
    # take the committed daily closes; NSE's own closes are never replaced.
    from src.loaders import price_source as ps

    days = pd.bdate_range("2025-01-01", periods=4)
    nse = pd.DataFrame({"AAA": [1.0, np.nan, 3.0, 4.0]}, index=days)
    extra = pd.DataFrame({"AAA": [9.0, 2.0, 9.0, 9.0], "REIT": [5.0, 5.5, 6.0, 6.5]}, index=days)
    path = tmp_path / "extra.parquet"
    extra.to_parquet(path)
    got = ps.with_weekly_extra(nse, path)
    assert list(got["AAA"]) == [1.0, 2.0, 3.0, 4.0]
    assert list(got["REIT"]) == [5.0, 5.5, 6.0, 6.5]
    assert ps.with_weekly_extra(nse, tmp_path / "missing.parquet") is nse


def test_the_committed_extra_file_holds_the_seven_stocks():
    from src.loaders import price_source as ps

    extra = pd.read_parquet(ps.WEEKLY_FILL_EXTRA)
    assert set(extra.columns) == {"BIRET", "EMBASSY", "JSLL", "SGMART", "SHILCTECH", "TIMEX", "PICCADIL"}
    assert extra.notna().sum().min() >= 240
