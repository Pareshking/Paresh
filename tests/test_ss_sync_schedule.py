"""SS is fetched weekly, Fridays 22:02 IST (owner, 17 Nov 2026: "make it weekly only")."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_ss_sync_runs_on_fridays_only():
    wf = yaml.safe_load((ROOT / ".github/workflows/ss_sync.yml").read_text(encoding="utf-8"))
    on = wf.get(True, wf.get("on"))
    assert [s["cron"] for s in on["schedule"]] == ["32 16 * * 5"]   # 16:32 UTC Fri = 22:02 IST
    assert "workflow_dispatch" in on, "a by-hand run must stay possible"


def test_screener_sync_is_scheduled_for_2237_ist():
    """Owner, 19 Nov 2026: the previous day's prices on the site by 06:00 IST."""
    wf = yaml.safe_load((ROOT / ".github/workflows/screener_sync.yml").read_text(encoding="utf-8"))
    on = wf.get(True, wf.get("on"))
    assert [s["cron"] for s in on["schedule"]] == ["7 17 * * *"]   # 17:07 UTC = 22:37 IST
    from datetime import time

    from src.core.market_time import DOWNLOAD_SETTLES
    assert time(22, 37) >= DOWNLOAD_SETTLES, "never before a vendor's close is final"
