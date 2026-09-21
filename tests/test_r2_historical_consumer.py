import pandas as pd
import pytest

from src.consumers.r2_historical import (
    R2HistoricalConsumerError,
    membership_from_frame,
)

def _frame():
    return pd.DataFrame([
        {"index":"nifty_total_market","symbol":"AAA","effective_from":"2026-01-01","effective_to":"2026-06-30","source":"x","evidence_date":"2026-01-01"},
        {"index":"nifty_total_market","symbol":"BBB","effective_from":"2026-01-01","effective_to":None,"source":"x","evidence_date":"2026-01-01"},
        {"index":"nifty_total_market","symbol":"CCC","effective_from":"2026-07-01","effective_to":None,"source":"x","evidence_date":"2026-07-01"},
    ])

def test_reconstructs_membership_as_of_date():
    assert membership_from_frame(_frame(), index="nifty_total_market", as_of="2026-06-30") == {"AAA","BBB"}
    assert membership_from_frame(_frame(), index="nifty_total_market", as_of="2026-07-01") == {"BBB","CCC"}

def test_unknown_index_fails_closed_to_empty_set():
    assert membership_from_frame(_frame(), index="nifty50", as_of="2026-07-01") is None

def test_missing_columns_fail_closed():
    with pytest.raises(R2HistoricalConsumerError, match="missing columns"):
        membership_from_frame(pd.DataFrame({"symbol":["AAA"]}), index="nifty_total_market", as_of="2026-07-01")

def test_duplicate_active_intervals_are_rejected():
    f=pd.concat([_frame(), pd.DataFrame([{"index":"nifty_total_market","symbol":"BBB","effective_from":"2026-01-01","effective_to":None,"source":"x","evidence_date":"2026-01-01"}])], ignore_index=True)
    with pytest.raises(R2HistoricalConsumerError, match="multiple active"):
        membership_from_frame(f, index="nifty_total_market", as_of="2026-07-01")

def test_pre_coverage_is_not_replaced_by_current_members():
    assert membership_from_frame(_frame(), index="nifty_total_market", as_of="2025-12-31") is None
