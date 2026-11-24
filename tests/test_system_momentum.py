"""S217 (owner, 23 Nov 2026): the momentum tiles for each system, from its own record.

"Build the tiles for each system"; "If each system doesn't have history, we will start collecting it";
"The 750's own stocks from 2021"; "B2": each system's top fifth against its own members, equal weight.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.engine import system_momentum as sm

ROOT = Path(__file__).resolve().parents[1]


def test_the_lists_month_ends_become_a_timeline():
    raw = {"months": {"2026-09-30": {"effective_from": "2026-10-01", "symbols": ["A", "B", "D"]},
                      "2026-08-31": {"effective_from": "2026-09-01", "symbols": ["A", "B", "C"]}}}
    h = sm.nano_history(raw)
    # Effective on the 1st, so it answers for the close that signals the month (as index_universe does).
    assert h["baseline"] == {"date": "2026-08-31", "symbols": ["A", "B", "C"]}
    assert h["changes"] == [{"date": "2026-09-30", "added": ["D"], "removed": ["C"]}]
    assert sm.nano_history({"months": {}}) is None


def test_each_system_reads_its_own_file_against_its_own_members():
    rec = pd.DataFrame({"month": ["2026-09", "2026-10"], "top": [2.0, -1.0], "ew": [1.0, 0.5]})
    tiles = sm.for_tiles(rec)
    assert list(tiles["nifty500"]) == [1.0, 0.5]       # the benchmark is the system's own equal weight
    assert sm.path("nano").name == "momentum_health_nano.csv"


def test_a_short_record_leaves_the_long_windows_empty_and_says_so():
    rec = pd.DataFrame({"month": ["2026-10"], "top": [-9.68], "ew": [-8.96]})
    t = sm.tiles(rec, -3.3)
    assert t[0][1] is None and t[1][1] is None           # no 12 or 3 months from one month
    assert round(t[2][1], 2) == -0.72 and t[2][0] == "October"
    assert t[3] == ("Month so far", -3.3, "Top fifth, at the last month-end")
    assert "collected from October 2026: 1 month so far" in sm.record_note(rec, "nano")
    assert "begins with its first finished month" in sm.record_note(None, "1000")   # not a typed "December 2026" (S193 B)
    long = pd.DataFrame({"month": [str(p) for p in pd.period_range("2025-01", periods=12, freq="M")],
                         "top": [1.0] * 12, "ew": [0.0] * 12})
    assert sm.record_note(long, "750") is None
    assert round(sm.tiles(long, None)[0][1], 4) == round((1.01 ** 12 - 1) * 100, 4)


def test_the_750s_record_is_its_own_members_from_2021():
    rec = pd.read_csv(sm.path("750"))
    assert rec["month"].iloc[0] == "2021-12"             # Nifty Total Market recorded from 29 Oct 2021
    assert rec["n"].min() >= 700                        # the 750, not the Nifty 500
    assert np.isfinite(rec[["top", "ew"]].to_numpy()).all()


def test_month_so_far_ranks_at_the_last_month_end():
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2025-06-02", "2026-11-20")
    drift = np.linspace(-0.001, 0.002, 150)             # a steady order: high drift ranks high and keeps rising
    px = pd.DataFrame(100 * np.exp(np.cumsum(drift + rng.normal(0, 0.002, (len(idx), 150)), axis=0)),
                      index=idx, columns=[f"S{i}" for i in range(150)])
    v = sm.month_so_far(px, list(px.columns), idx[-1])
    assert v is not None and v > 0
    assert sm.month_so_far(px, list(px.columns[:50]), idx[-1]) is None   # fewer than MIN_STOCKS: no reading


def test_dashboard_tiles_read_the_systems_record():
    src = (ROOT / "src" / "ui" / "views" / "dashboard_home_view.py").read_text(encoding="utf-8")
    assert "This system’s top fifth against the {e(uni)}, equal weight" in src
    assert "own = sm.for_tiles(sm.read(system if system in sm.SYSTEMS else SYSTEM_750))" in src
    assert "This system’s record is under 12 months old" in src     # S203 dash.mom.1
    assert "This ranking’s top 100 against the Nifty 500" not in src
    wf = (ROOT / ".github" / "workflows" / "momentum_health.yml").read_text(encoding="utf-8")
    assert "data/momentum_health_*.csv" in wf             # the month-end job collects each system's record


def test_the_nifty_500s_longer_record_is_one_line_beside_every_system():
    # Owner, 23 Nov 2026: "How about we keep N500 for also additionally?" One sentence by B2's rule (top fifth
    # against its members, equal weight), not a second set of tiles; on systems with a short record too.
    from src.ui.views import dashboard_home_view as dv

    sp = pd.read_csv(ROOT / "data" / "momentum_health.csv")
    long = dv._long_record(sp)
    line = dv._long_record_line(long)
    assert line.startswith(" On the Nifty 500’s record since 2010, by the same rule, the deepest fall was")   # S203 dash.mom.7
    assert "of 5% or more took" in line and "to recover" in line
    short = dv._lag_note(None, short="This system’s own record is being collected.", long=long)
    assert "On the Nifty 500’s record since 2010" in short
    assert dv._long_record(sp.drop(columns=["ew"])) is None
