"""Executable contracts for Section-C historical evidence bootstrap."""

from pathlib import Path

import pandas as pd

from scripts.r2_historical_evidence_bootstrap import (
    _membership_intervals,
    build_corporate_actions,
    build_market_caps,
    build_trading_sessions,
)

ROOT = Path(__file__).resolve().parents[1]


def test_membership_intervals_close_removed_symbols_and_stamp_open_intervals():
    history = {
        "index": "TEST",
        "baseline": {"date": "2026-08-01", "symbols": ["AAA", "BBB"]},
        "changes": [
            {"date": "2026-08-10", "removed": ["AAA"], "added": ["CCC"]},
            {"date": "2026-08-20", "removed": [], "added": []},
        ],
    }
    frame = _membership_intervals(history)
    aaa = frame.loc[frame["symbol"].eq("AAA")].iloc[0]
    bbb = frame.loc[frame["symbol"].eq("BBB")].iloc[0]
    ccc = frame.loc[frame["symbol"].eq("CCC")].iloc[0]

    assert aaa["effective_from"] == "2026-08-01"
    assert aaa["effective_to"] == "2026-08-09"
    assert pd.isna(bbb["effective_to"])
    assert pd.isna(ccc["effective_to"])
    assert bbb["evidence_date"] == "2026-08-10"
    assert ccc["evidence_date"] == "2026-08-10"


def test_confirmed_trading_sessions_preserve_sparse_source_contract(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    path = build_trading_sessions(out)
    frame = pd.read_parquet(path)

    assert list(frame.columns) == [
        "date", "market", "is_session", "source", "evidence_date"
    ]
    assert frame["is_session"].all()
    assert frame["date"].is_monotonic_increasing
    assert len(frame) == 5


def test_market_cap_dataset_is_explicit_snapshot(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    path = build_market_caps(out)
    frame = pd.read_parquet(path)

    assert set(["symbol", "market_cap", "date", "source", "evidence_date"]) <= set(frame.columns)
    assert frame["date"].nunique() == 1
    assert frame["source"].eq("pr_live_zip").all()


def test_corporate_action_evidence_has_provenance(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    path = build_corporate_actions(out)
    frame = pd.read_parquet(path)

    required = {"event_date", "evidence_date", "source", "evidence_uri", "symbol"}
    assert required <= set(frame.columns)
    assert frame["source"].notna().all()
    assert frame["evidence_uri"].eq(
        "repo://Pareshking/Paresh/data/corporate_actions_log.json"
    ).all()
    assert frame["evidence_date"].notna().all()
