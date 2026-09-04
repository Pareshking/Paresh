"""Data runtime for the v2 verification app.

This deliberately reuses the existing loaders and MomentumEngine. It does not
introduce a second quantitative model or change the production calculations.
"""

from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from src.core import startup_metrics as metrics
from src.core.config import MCAPS_FILE, MCAP_PR_FILE, PRICES_FILE
from src.engine.calendar_momentum import _apply_weight_composite, _compute_period_z_scores
from src.engine.momentum import MomentumEngine
from src.loaders.indices_loader import fetch_indices_data
from src.loaders.mcap_loader import fetch_market_caps
from src.loaders.price_loader import extract_ohlcv, fetch_price_history, get_market_regime


def _symbols_hash(symbols: list[str]) -> str:
    return hashlib.md5(",".join(sorted(s.upper() for s in symbols)).encode()).hexdigest()[:12]


def _price_hash(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "empty"
    try:
        last = pd.to_numeric(df.iloc[-1], errors="coerce").to_numpy(dtype="float64")
        digest = hashlib.md5(last.tobytes()).hexdigest()[:12]
        return f"{df.index[-1]}_{df.shape[0]}x{df.shape[1]}_{digest}"
    except Exception:
        return "unknown"


@st.cache_data(show_spinner=False, ttl=3600)
def _prices(sym_key: str, _symbols: list[str]) -> pd.DataFrame:
    return fetch_price_history(list(_symbols), period="2y", force_refresh=False)


@st.cache_data(show_spinner=False, ttl=3600)
def _mcaps(sym_key: str, _symbols: list[str]) -> pd.Series:
    return fetch_market_caps(list(_symbols), force_refresh=False)


@st.cache_data(show_spinner=False, ttl=3600)
def _ohlcv(price_hash: str, sym_key: str, _raw: pd.DataFrame, _symbols: list[str]):
    return extract_ohlcv(_raw, _symbols)


@st.cache_data(show_spinner=False, ttl=3600)
def _base_engine(
    price_hash: str,
    universe_hash: str,
    _adj: pd.DataFrame,
    _high: pd.DataFrame,
    _low: pd.DataFrame,
    _close: pd.DataFrame,
    _volume: pd.DataFrame,
    _idx: pd.DataFrame,
    _mcaps: pd.Series,
):
    calc = MomentumEngine(
        _adj,
        high_df=_high,
        low_df=_low,
        close_df=_close,
        volume_df=_volume,
        weights=[0.2] * 5,
    )
    _compute_period_z_scores(calc)
    calc._precompute_signals(_idx, _mcaps, _close, _high)
    return calc


@st.cache_data(show_spinner=False, ttl=3600)
def _ranked(
    base_hash: str,
    weights: tuple[float, ...],
    _calc,
    _idx: pd.DataFrame,
    _mcaps: pd.Series,
    _close: pd.DataFrame,
    _high: pd.DataFrame,
):
    _calc.weights = list(weights)
    _apply_weight_composite(_calc, list(weights))
    rank_df = _calc.get_rankings(
        _idx,
        _mcaps,
        close_prices_df=_close,
        high_prices_df=_high,
    )
    return _calc, rank_df


def load_runtime() -> dict | None:
    if st.session_state.pop("v2_force_refresh", False):
        st.cache_data.clear()

    indices = st.session_state.get("v2_indices", ["NIFTY TOTAL MARKET"])
    raw_weights = [float(st.session_state.get(f"v2_w{i}", x)) for i, x in enumerate((.10,.30,.30,.20,.10), 1)]
    total = sum(raw_weights)
    weights = tuple(w / total for w in raw_weights) if total > 0 else (.2,) * 5

    idx = fetch_indices_data(indices)
    if idx is None or idx.empty or "Symbol" not in idx.columns:
        return None
    symbols = idx["Symbol"].dropna().astype(str).unique().tolist()
    sym_key = _symbols_hash(symbols)

    raw = _prices(sym_key, symbols)
    if raw is None or raw.empty:
        return None
    raw_hash = _price_hash(raw)
    adj, close, high, low, volume, open_ = _ohlcv(raw_hash, sym_key, raw, symbols)
    if adj is None or adj.empty:
        return None

    mcaps = _mcaps(sym_key, symbols)
    p_hash = _price_hash(adj)
    u_hash = f"{len(idx)}_{sym_key}"
    base_hash = f"{p_hash}_{u_hash}_v2"
    calc_base = _base_engine(p_hash, u_hash, adj, high, low, close, volume, idx, mcaps)
    calc, rank_df = _ranked(base_hash, weights, calc_base, idx, mcaps, close, high)
    if rank_df is None or rank_df.empty:
        return None

    try:
        regime = get_market_regime()
    except Exception:
        regime = None

    return {
        "calc": calc,
        "rank_df": rank_df,
        "adj_close": adj,
        "close_prices": close,
        "high_prices": high,
        "low_prices": low,
        "volume_data": volume,
        "open_prices": open_,
        "idx_info": idx,
        "regime": regime,
        "weights": weights,
    }
