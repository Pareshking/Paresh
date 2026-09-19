"""Stable identity for the canonical System-1 configuration.

The agent records this fingerprint; it does not define or alter the model.
Only configuration values that can change quantitative behaviour belong here.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from src.core import config


def canonical_config_payload() -> dict[str, Any]:
    """Return the quantitative settings that identify the current V1 model."""
    return {
        "benchmark_symbol": config.BENCHMARK_SYMBOL,
        "momentum_months": list(config.MOMENTUM_MONTHS),
        "lookback_weights": list(config.DEFAULT_LOOKBACK_WEIGHTS),
        "sector_cap": config.DEFAULT_SECTOR_CAP,
        "stock_cap": config.DEFAULT_STOCK_CAP,
        "target_vol": config.DEFAULT_TARGET_VOL,
        "transaction_cost_bps": config.DEFAULT_TRANSACTION_COST_BPS,
        "risk_free_rate": config.RISK_FREE_RATE,
        "high_52w_min_observations": config.HIGH_52W_MIN_OBSERVATIONS,
    }


def config_fingerprint() -> str:
    """Hash the canonical payload deterministically for provenance."""
    payload = json.dumps(
        canonical_config_payload(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
