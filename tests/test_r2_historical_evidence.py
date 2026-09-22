"""Executable contracts for Section-C historical evidence bootstrap."""

import json
from pathlib import Path

import pandas as pd

from scripts.r2_publish import describe_parquet
from scripts.r2_historical_evidence_bootstrap import (
    INDEX_FILES,
    MEMBERSHIP_AS_OF,
    _membership_intervals,
    build_corporate_actions,
    build_market_caps,
    build_membership,
    build_trading_sessions,
)


ROOT = Path(__file__).resolve().parents[1]


def test_all_index_source_files_exist():
    assert all(path.is_file() for path in INDEX_FILES.values())


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

    assert set(frame["index"]) == {"nifty_total_market"}
    assert set(frame["as_of"]) == {MEMBERSHIP_AS_OF}
    assert aaa["effective_from"] == "2026-08-01"
    assert aaa["effective_to"] == "2026-08-09"
    assert pd.isna(bbb["effective_to"])
    assert pd.isna(ccc["effective_to"])
    assert bbb["evidence_date"] == "2026-08-20"
    assert ccc["evidence_date"] == "2026-08-20"


def test_real_membership_history_has_no_changes_and_covers_acceptance_date(tmp_path):
    history = json.loads((ROOT / "data/membership_history.json").read_text())
    assert history["changes"] == []
    build_membership(tmp_path)
    frame = tmp_path / "membership_nifty_total_market.parquet"
    generated = pd.read_parquet(frame)
    assert generated["index"].eq("nifty_total_market").all()
    assert generated["as_of"].eq(MEMBERSHIP_AS_OF).all()
    assert (pd.to_datetime(generated["effective_from"]) <= pd.Timestamp(MEMBERSHIP_AS_OF)).all()
    assert describe_parquet(frame)["as_of"] == MEMBERSHIP_AS_OF


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
    payload = json.loads((ROOT / "data/nse_trading_days.json").read_text())
    expected_dates = sorted(set(payload.get("trading_days", [])))
    assert len(frame) == len(expected_dates)
    assert frame["date"].dt.strftime("%Y-%m-%d").tolist() == expected_dates


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


def test_build_membership_produces_all_five_research_index_histories(tmp_path):
    paths = build_membership(tmp_path)
    names = {path.name for path in paths}
    expected = {
        "membership_nifty50.parquet",
        "membership_nifty_next50.parquet",
        "membership_nifty_midcap150.parquet",
        "membership_nifty_smallcap250.parquet",
        "membership_nifty_microcap250.parquet",
        "membership_nifty_total_market.parquet",
    }
    assert expected <= names
    for name in expected:
        frame = pd.read_parquet(tmp_path / name)
        assert not frame.empty
        assert frame["symbol"].notna().all()
        assert frame["effective_from"].notna().all()
        assert frame["as_of"].eq(MEMBERSHIP_AS_OF).all()

