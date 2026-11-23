"""S193 A6 (23 Nov 2026): the Nano Cap Dashboard's "Stocks that qualify" read the 30 Oct month-end
under "Now": its prices hold no Nifty 500 stock. The nightly breadth job writes the Nifty 500 share on
the Dashboard's three dates, and every system reads it first."""
import json
from pathlib import Path

import pandas as pd

from src.ui.views import dashboard_home_view as dh

ROOT = Path(__file__).resolve().parents[1]


def _file(tmp_path, as_of, n=3):
    days = ["2026-08-20", "2026-10-19", "2026-11-20"][:n]
    p = tmp_path / "q.json"
    p.write_text(json.dumps({"as_of": as_of, "nifty500": {d: v for d, v in zip(days, (0.46, 0.15, 0.44))}}))
    return p


def test_the_saved_reading_is_used_for_its_own_session(tmp_path):
    got = dh._qualify_saved(pd.Timestamp("2026-11-20"), _file(tmp_path, "2026-11-20"))
    assert got[pd.Timestamp("2026-11-20")] == 0.44 and len(got) == 3


def test_an_older_or_partial_file_is_not_used(tmp_path):
    assert dh._qualify_saved(pd.Timestamp("2026-11-23"), _file(tmp_path, "2026-11-20")) == {}
    assert dh._qualify_saved(pd.Timestamp("2026-11-20"), _file(tmp_path, "2026-11-20", n=2)) == {}
    assert dh._qualify_saved(pd.Timestamp("2026-11-20"), tmp_path / "missing.json") == {}


def test_the_nightly_job_writes_and_commits_it():
    script = (ROOT / "scripts" / "build_breadth_history.py").read_text()
    wf = (ROOT / ".github" / "workflows" / "nse_long_prices.yml").read_text()
    assert "write_qualified(close" in script
    assert "git add data/qualified_now.json" in wf
