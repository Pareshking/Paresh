"""SS is fetched weekly, Fridays 22:02 IST (owner, 17 Nov 2026: "make it weekly only")."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_ss_sync_runs_on_fridays_only():
    wf = yaml.safe_load((ROOT / ".github/workflows/ss_sync.yml").read_text(encoding="utf-8"))
    on = wf.get(True, wf.get("on"))
    assert [s["cron"] for s in on["schedule"]] == ["32 16 * * 5"]   # 16:32 UTC Fri = 22:02 IST
    assert "workflow_dispatch" in on, "a by-hand run must stay possible"
