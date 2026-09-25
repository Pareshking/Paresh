"""The classification history is built from the repository's own snapshots.

This used to build a frame by hand and assert on that frame, never running the
builder. It now runs scripts/build_classification_history.py against this
repository's git history (a shallow CI checkout still has one commit).
"""
import pandas as pd

from scripts.build_classification_history import build


def test_the_builder_produces_the_classification_contract(tmp_path):
    out = tmp_path / "classification.parquet"
    summary = build(out)
    frame = pd.read_parquet(out)

    assert {"symbol", "sector", "industry", "effective_from", "evidence_date",
            "evidence_commit", "source", "as_of"} <= set(frame.columns)
    assert summary["snapshot_count"] >= 1 and summary["row_count"] == len(frame)
    # One row per symbol within each snapshot, never a blank classification.
    assert not frame.duplicated(["effective_from", "symbol"]).any()
    assert frame["sector"].notna().all() and frame["industry"].notna().all()
    assert frame["evidence_commit"].str.fullmatch(r"[0-9a-f]{40}").all()
    assert not frame["symbol"].str.startswith("DUMMY").any()
