"""Focused tests for the Stage-2 quantitative hand-off boundary."""

from datetime import date

import pandas as pd
import pytest

from agent.quant_hand_off import QuantHandoffError, load_quant_snapshot
from src.core import config
from src.engine import pipeline


@pytest.fixture
def ranking_frame():
    return pd.DataFrame(
        {
            "Symbol": ["AAA", "BBB", "CCC"],
            "Rank": [1, 2, 3],
            "Score": [2.5, 1.0, -0.5],
            "1M": [1.2, 0.8, -0.2],
            "3M": [1.1, 0.7, -0.1],
        }
    )


@pytest.fixture
def ranking_contract():
    weights = tuple(float(w) for w in config.DEFAULT_LOOKBACK_WEIGHTS)
    total = sum(weights)
    return {
        "pipeline_version": pipeline.PIPELINE_VERSION,
        "price_source": config.RANKING_PRICE_SOURCE,
        "price_as_of": "2026-09-18",
        "weights": [round(w / total, 6) for w in weights],
        "universe": ["AAA", "BBB", "CCC"],
        "price_fingerprint": "published-price-fingerprint",
        "symbols_fingerprint": "published-symbol-fingerprint",
        "actions_digest": "published-actions",
    }


def _mock_fetch(monkeypatch, frame, contract):
    monkeypatch.setattr(
        "agent.quant_hand_off.ranking_store.fetch_snapshot",
        lambda url=None: (frame, contract),
    )


def test_valid_artifact_becomes_snapshot_without_changing_rows(
    monkeypatch, ranking_frame, ranking_contract
):
    _mock_fetch(monkeypatch, ranking_frame, ranking_contract)

    snapshot = load_quant_snapshot("artifact://rankings.parquet")

    assert snapshot.as_of == date(2026, 9, 18)
    assert snapshot.benchmark == "^CRSLDX"
    assert snapshot.universe == "NIFTY TOTAL MARKET"
    assert snapshot.pipeline_version == pipeline.PIPELINE_VERSION
    assert snapshot.price_source == config.RANKING_PRICE_SOURCE
    assert snapshot.source_artifact == "artifact://rankings.parquet"
    assert [row["Symbol"] for row in snapshot.rows] == ["AAA", "BBB", "CCC"]
    assert [row["Score"] for row in snapshot.rows] == [2.5, 1.0, -0.5]


def test_missing_artifact_fails_closed(monkeypatch):
    monkeypatch.setattr(
        "agent.quant_hand_off.ranking_store.fetch_snapshot",
        lambda url=None: (None, None),
    )
    with pytest.raises(QuantHandoffError, match="unavailable"):
        load_quant_snapshot()


@pytest.mark.parametrize(
    "change, message",
    [
        ({"pipeline_version": "old"}, "pipeline_version"),
        ({"price_source": "yahoo"}, "price_source"),
        ({"price_as_of": ""}, "price_as_of"),
        ({"weights": [0.2] * 5}, "weights"),
        ({"universe": []}, "universe"),
    ],
)
def test_contract_mismatch_fails_closed(
    monkeypatch, ranking_frame, ranking_contract, change, message
):
    published = dict(ranking_contract, **change)
    _mock_fetch(monkeypatch, ranking_frame, published)
    with pytest.raises(QuantHandoffError, match=message):
        load_quant_snapshot()


def test_invalid_as_of_fails_closed(monkeypatch, ranking_frame, ranking_contract):
    published = dict(ranking_contract, price_as_of="not-a-date")
    _mock_fetch(monkeypatch, ranking_frame, published)
    with pytest.raises(QuantHandoffError, match="price_as_of"):
        load_quant_snapshot()


def test_expected_as_of_mismatch_fails_closed(
    monkeypatch, ranking_frame, ranking_contract
):
    _mock_fetch(monkeypatch, ranking_frame, ranking_contract)
    with pytest.raises(QuantHandoffError, match="as-of differs"):
        load_quant_snapshot(expected_as_of=date(2026, 9, 19))


@pytest.mark.parametrize(
    "frame, message",
    [
        (pd.DataFrame(), "no rows"),
        (pd.DataFrame({"Rank": [1], "Score": [1.0]}), "Symbol"),
        (pd.DataFrame({"Symbol": ["AAA"], "Score": [1.0]}), "Rank"),
        (pd.DataFrame({"Symbol": ["AAA"], "Rank": [1]}), "Score"),
        (
            pd.DataFrame(
                {"Symbol": ["AAA", "aaa"], "Rank": [1, 2], "Score": [1.0, 0.5]}
            ),
            "duplicate",
        ),
        (
            pd.DataFrame(
                {"Symbol": ["AAA", ""], "Rank": [1, 2], "Score": [1.0, 0.5]}
            ),
            "empty Symbol",
        ),
        (
            pd.DataFrame({"Symbol": ["AAA"], "Rank": [0], "Score": [1.0]}),
            "invalid Rank",
        ),
    ],
)
def test_bad_rows_fail_closed(monkeypatch, ranking_contract, frame, message):
    _mock_fetch(monkeypatch, frame, ranking_contract)
    with pytest.raises(QuantHandoffError, match=message):
        load_quant_snapshot()


def test_adapter_does_not_call_quant_engine(
    monkeypatch, ranking_frame, ranking_contract
):
    _mock_fetch(monkeypatch, ranking_frame, ranking_contract)

    def forbidden(*args, **kwargs):
        raise AssertionError("Stage-2 hand-off must not recalculate ranking")

    monkeypatch.setattr(pipeline, "build_engine", forbidden)
    monkeypatch.setattr(pipeline, "rank_with_weights", forbidden)

    snapshot = load_quant_snapshot()
    assert len(snapshot.rows) == len(ranking_frame)


def test_expected_as_of_is_an_explicit_audit_constraint(
    monkeypatch, ranking_frame, ranking_contract
):
    _mock_fetch(monkeypatch, ranking_frame, ranking_contract)
    snapshot = load_quant_snapshot(expected_as_of=date(2026, 9, 18))
    assert snapshot.price_as_of == date(2026, 9, 18)

def test_row_outside_contract_universe_fails_closed(
    monkeypatch, ranking_frame, ranking_contract
):
    published = dict(ranking_contract, universe=["AAA", "BBB"])
    _mock_fetch(monkeypatch, ranking_frame, published)
    with pytest.raises(QuantHandoffError, match="outside contract universe"):
        load_quant_snapshot()

