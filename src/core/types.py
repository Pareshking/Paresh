"""
Type definitions, enums, and dataclasses for NSE Momentum Dashboard.
Ensures strict type-safety across quant engines, loaders, backtesters, and UI layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, NamedTuple

import pandas as pd


class MarketRegime(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    UNKNOWN = "UNKNOWN"


class WeightMethod(str, Enum):
    EQUAL_WEIGHT = "Equal Weight"
    INVERSE_VOLATILITY = "Inverse Volatility"
    MEAN_VARIANCE = "MVO (Mean-Variance)"


class SurgeMode(str, Enum):
    DAILY_VS_20D = "Daily vs 20D Avg"
    TREND_20D_VS_PREV = "20D Avg vs Prior 20D"


class ColumnDensity(str, Enum):
    EXECUTIVE = "Executive (11)"
    CORE = "Core (17)"
    FULL_QUANT = "Full Quant (35)"


@dataclass(frozen=True)
class SignalAlert:
    """Automated market & momentum signal notification."""
    icon: str
    text: str
    color: str
    category: str = "general"


@dataclass
class BacktestResult:
    """Walk-forward backtest results with performance attribution."""
    equity_curve: pd.Series
    equity_gross: pd.Series
    benchmark: pd.Series
    monthly: pd.DataFrame
    tradebook: pd.DataFrame
    closed_trades: pd.DataFrame
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RegimeData:
    """Market regime telemetry against benchmark 200 DMA."""
    status: MarketRegime
    current_price: float
    dma_200: float
    distance_pct: float


class OHLCVData(NamedTuple):
    """Cleaned 5-tuple OHLCV DataFrame extracted from raw price downloads."""
    adj_close: pd.DataFrame
    close: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    volume: pd.DataFrame
