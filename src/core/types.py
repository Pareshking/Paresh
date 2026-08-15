"""
Type definitions and dataclasses for NSE Momentum Dashboard.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict
import pandas as pd


class MarketRegime(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    UNKNOWN = "UNKNOWN"


class WeightMethod(str, Enum):
    EQUAL_WEIGHT = "Equal Weight"
    INVERSE_VOLATILITY = "Inverse Volatility"
    MEAN_VARIANCE = "Mean-Variance (MVO)"


class SurgeMode(str, Enum):
    DAILY_VS_20D = "Daily vs 20D Avg"
    TREND_20D_VS_PREV = "20D Avg vs Prior 20D"


@dataclass
class SignalAlert:
    icon: str
    text: str
    color: str
    category: str = "general"


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    benchmark: pd.Series
    monthly: pd.DataFrame
    stats: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RegimeData:
    status: MarketRegime
    current_price: float
    dma_200: float
    distance_pct: float
