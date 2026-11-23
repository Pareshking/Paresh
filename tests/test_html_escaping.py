"""Raw HTML sinks cannot be broken out of (S138, HTML audit 15 Nov 2026)."""
import json
from pathlib import Path

from src.ui import page_kit as kit

ROOT = Path(__file__).resolve().parents[1]


def test_safe_json_cannot_close_its_element_and_stays_valid_json():
    obj = {"col": "</div><script>alert(1)</script>", "amp": "a&b", "n": 3}
    out = kit.safe_json(obj)
    assert "<" not in out and ">" not in out and "&" not in out
    assert json.loads(out) == obj          # the startup-metrics readers parse it unchanged


def test_the_startup_metrics_div_goes_through_safe_json():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    i = src.index('id="umiya-startup-metrics"')
    assert "safe_json(metrics.public_snapshot())" in src[i:i + 600]
    assert "json.dumps(metrics.public_snapshot())" not in src
