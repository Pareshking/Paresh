"""Build and dependency diagnostics belong in telemetry, not in front of a reader.

The commit and Streamlit version were briefly rendered as a chip in the
Configuration status bar, to tell "the fix is wrong" from "the fix is not
running" during a live defect. That was plumbing shown to the person using the
app. It is now carried by the hidden startup-metrics element the production QA
probe already reads for deploy correspondence, which is the right place for it:
asserted by machines, invisible to readers.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "src" / "ui" / "views"


def test_no_view_renders_a_build_or_version_chip():
    offenders = []
    for path in sorted(VIEWS.glob("*.py")):
        src = path.read_text()
        for pattern in (r"build \{", r"streamlit \{", r"deployed_revision\("):
            if re.search(pattern, src):
                offenders.append(f"{path.name}: {pattern}")
    assert not offenders, (
        "diagnostics rendered into the UI: " + "; ".join(offenders)
    )


def test_the_telemetry_still_carries_the_revision_and_the_streamlit_version():
    """Removing the chip must not blind the deploy-correspondence check."""
    from src.core import startup_metrics

    snap = startup_metrics.snapshot()
    assert "revision" in snap, "deploy correspondence lost its input"
    assert "streamlit_version" in snap, (
        "the frontend version is no longer observable anywhere"
    )
    version = snap["streamlit_version"]
    assert version is None or re.fullmatch(r"\d+\.\d+\.\d+", version), version


def test_streamlit_is_pinned_not_floated():
    """An unpinned frontend can change under a live app with no commit here.

    That is the most likely reason the weight sliders worked one week and
    rendered at their minimum the next.
    """
    req = (ROOT / "requirements.txt").read_text()
    line = next(l for l in req.splitlines()
                if l.strip().startswith("streamlit") and "lightweight" not in l)
    assert re.fullmatch(r"streamlit==\d+\.\d+\.\d+", line.strip()), (
        f"streamlit must be pinned to an exact version; found {line!r}"
    )
