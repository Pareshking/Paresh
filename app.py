"""
NSE Momentum Dashboard — Production Application Entry Point.
Architecture: Modular Package Hierarchy with Pure Paper White Theme & 100% Full Viewport Widescreen Layout.
Flush 0px top padding with Investrack Pill Tab Navigation.
"""

import hashlib
import warnings

import pandas as pd
import streamlit as st

# Suppress runtime noise
warnings.filterwarnings("ignore", category=RuntimeWarning, module="numpy")
warnings.filterwarnings("ignore", message=".*use_container_width.*")
warnings.filterwarnings("ignore", message=".*replace.*st\\.components\\.v1\\.html.*")
warnings.filterwarnings("ignore", message=".*st\\.components\\.v1\\.html.*")

# Core & Loaders
from src.engine.momentum import MomentumEngine
from src.engine.calendar_momentum import apply_calendar_momentum, calendar_start_positions, latest_as_of_date
from src.loaders.indices_loader import fetch_indices_data
from src.loaders.mcap_loader import fetch_market_caps
from src.loaders.price_loader import (
    extract_ohlcv,
    fetch_price_history,
    get_market_regime,
)
from src.loaders.tv_loader import load_tv_classification

# UI Design System, Components & Views
from src.ui.components import (
    compute_signals,
    render_header_kpi_bar,
    render_signal_alerts,
)
from src.ui.theme import inject_custom_css
from src.ui.views.backtest_view import render_backtest_view
from src.ui.views.breadth_view import render_breadth_view
from src.ui.views.config_view import render_config_view
from src.ui.views.delivery_view import render_delivery_view
from src.ui.views.guide_view import render_guide_view
from src.ui.views.portfolio_view import render_portfolio_view
from src.ui.views.qualified_view import render_qualified_view
from src.ui.views.ranking_view import render_ranking_view
from src.ui.views.rrg_view import render_rrg_view
from src.ui.views.sector_view import render_sector_view
from src.ui.views.strategy_view import render_strategy_view
from src.ui.views.watchlist_view import render_watchlist_view

# Page Config: 100% Widescreen, Sidebar Collapsed
st.set_page_config(
    page_title="Paresh Patel | Momentum Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Inject Pure Paper White Design System
inject_custom_css()


# ── State Initialization ─────────────────────────────────────────────────────
if "cfg_indices" not in st.session_state:
    st.session_state["cfg_indices"] = ["NIFTY TOTAL MARKET"]
if "cfg_w1" not in st.session_state:
    st.session_state.update(
        {
            "cfg_w1": 0.10,
            "cfg_w2": 0.30,
            "cfg_w3": 0.30,
            "cfg_w4": 0.20,
            "cfg_w5": 0.10,
        }
    )
if "cfg_sc" not in st.session_state:
    st.session_state.update(
        {"cfg_sc": 30, "cfg_stc": 5, "cfg_vt": False, "cfg_vtv": 25}
    )

selected_indices = st.session_state["cfg_indices"]
raw_w = [st.session_state[f"cfg_w{i}"] for i in range(1, 6)]
total_w = sum(raw_w)
weights = tuple([w / total_w for w in raw_w] if total_w > 0 else [0.2] * 5)

sector_cap = st.session_state["cfg_sc"] / 100.0
stock_cap = st.session_state["cfg_stc"] / 100.0
vol_target_on = st.session_state["cfg_vt"]
vol_target_val = st.session_state["cfg_vtv"] / 100.0


# ── Cached Data Pipeline ─────────────────────────────────────────────────────
def _price_hash(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "empty"
    try:
        return f"{df.index[-1]}_{df.shape[0]}x{df.shape[1]}"
    except Exception:
        return "unknown"


def _symbols_hash(symbols: list[str]) -> str:
    key = ",".join(sorted(s.upper() for s in symbols))
    return hashlib.md5(key.encode()).hexdigest()[:12]


@st.cache_data(show_spinner=False, ttl=3600)
def load_prices_cached(
    sym_key: str, _symbols: list[str], period: str = "2y"
) -> pd.DataFrame:
    return fetch_price_history(list(_symbols), period=period, force_refresh=False)


@st.cache_data(show_spinner=False, ttl=3600)
def load_mcaps_cached(sym_key: str, _symbols: list[str]) -> pd.Series:
    return fetch_market_caps(list(_symbols), force_refresh=False)


@st.cache_data(show_spinner=False, ttl=3600)
def run_momentum_pipeline(
    price_hash: str,
    index_hash: str,
    pipeline_version: str,
    _adj_close: pd.DataFrame,
    _high_prices: pd.DataFrame,
    _low_prices: pd.DataFrame,
    _close_prices: pd.DataFrame,
    _volume_data: pd.DataFrame,
    _index_info: pd.DataFrame,
    _market_caps: pd.Series,
    weights: tuple[float, ...],
):
    calc = MomentumEngine(
        _adj_close,
        high_df=_high_prices,
        low_df=_low_prices,
        close_df=_close_prices,
        volume_df=_volume_data,
        weights=list(weights),
    )
    apply_calendar_momentum(calc)
    rank_df = calc.get_rankings(
        _index_info,
        _market_caps,
        close_prices_df=_close_prices,
        high_prices_df=_high_prices,
        compute_exp_reg=True,
    )
    return calc, rank_df


def load_all_data(indices: list[str]):
    force = st.session_state.pop("force_refresh", False)
    if force:
        st.cache_data.clear()

    idx_info = fetch_indices_data(indices)
    if idx_info.empty:
        return None

    symbols = idx_info["Symbol"].unique().tolist()
    sym_key = _symbols_hash(symbols)

    raw_prices = load_prices_cached(sym_key, symbols, period="2y")
    if raw_prices.empty:
        return None

    adj_close, close_p, high_p, low_p, vol_p = extract_ohlcv(raw_prices, symbols)
    mcaps = load_mcaps_cached(sym_key, symbols)
    regime = get_market_regime()

    p_hash = _price_hash(adj_close)
    i_hash = f"{len(idx_info)}_{sym_key}"
    calc, rank_df = run_momentum_pipeline(
        p_hash,
        i_hash,
        "v4_calendar_periods",
        adj_close,
        high_p,
        low_p,
        close_p,
        vol_p,
        idx_info,
        mcaps,
        weights,
    )

    # Ensure Max DD 6M is populated
    if "Max DD 6M" not in rank_df.columns or rank_df["Max DD 6M"].isna().all():
        as_of = latest_as_of_date(pd.DatetimeIndex(close_p.index))
        starts = calendar_start_positions(
            pd.DatetimeIndex(close_p.index), 6, latest_as_of=as_of
        )
        period_close = close_p.iloc[int(starts[-1]) :]
        roll_max_6m = period_close.cummax()
        dd_6m = ((period_close - roll_max_6m) / roll_max_6m).min() * 100
        dd_6m_dict = {
            str(k).replace(".NS", "").strip().upper(): v
            for k, v in dd_6m.to_dict().items()
        }
        rank_df["Max DD 6M"] = rank_df["Symbol"].map(dd_6m_dict)

    return {
        "calc": calc,
        "rank_df": rank_df,
        "adj_close": adj_close,
        "close_prices": close_p,
        "high_prices": high_p,
        "low_prices": low_p,
        "volume_data": vol_p,
        "regime_data": regime,
        "idx_info": idx_info,
    }


# ── Load Market Data ─────────────────────────────────────────────────────────
with st.spinner("Loading market data & executing quantitative momentum engine…"):
    data = load_all_data(selected_indices)

if not data:
    st.error(
        "❌ Failed to initialize market data. Please verify your internet connection or reload."
    )
    st.stop()

calc = data["calc"]
rank_df = data["rank_df"]
adj_close = data["adj_close"]
high_prices = data["high_prices"]
low_prices = data["low_prices"]
volume_data = data["volume_data"]
regime_data = data["regime_data"]

# Merge TradingView granular classification
tv_map = load_tv_classification()
if tv_map:
    rank_df["TV_Sector"] = rank_df["Symbol"].map(
        lambda s: tv_map.get(s, {}).get("TV_Sector", "")
    )
    rank_df["TV_Industry"] = rank_df["Symbol"].map(
        lambda s: tv_map.get(s, {}).get("TV_Industry", "")
    )
else:
    rank_df["TV_Sector"] = ""
    rank_df["TV_Industry"] = rank_df.get("Industry", "")


# ── Top Header KPI Bar & Alerts ──────────────────────────────────────────────
total_stocks = len(rank_df)

# Defensive handling for duplicate column names.  A duplicate "Above 50 EMA"
# can turn rank_df["Above 50 EMA"] into a DataFrame; map() on a DataFrame in
# pandas 2.1+ returns a DataFrame, so .sum() returns a Series, and int(Series)
# raises ValueError.  Force to a 1-D bool Series before summing.
ema_col = rank_df.get("Above 50 EMA")
if isinstance(ema_col, pd.DataFrame):
    ema_col = ema_col.iloc[:, -1]

is_above_ema = (
    ema_col.map(
        lambda x: x is True or str(x).strip() in ["✅", "True", "1"]
    )
    if ema_col is not None
    else pd.Series(dtype=bool)
)
if isinstance(is_above_ema, pd.DataFrame):
    is_above_ema = is_above_ema.iloc[:, -1]
above_ema = int(is_above_ema.astype(float).sum())
pct_above_ema = (above_ema / total_stocks * 100) if total_stocks > 0 else 0.0
gap_count = int((rank_df.get("Data Gap", pd.Series()) == "🔴").sum())

render_header_kpi_bar(
    regime=regime_data,
    total_stocks=total_stocks,
    above_ema=above_ema,
    pct_above_ema=pct_above_ema,
    gap_count=gap_count,
)

signals = compute_signals(
    rank_df=rank_df,
    regime_status=regime_data.status,
    dma_dist=regime_data.distance_pct,
    pct_above_ema=pct_above_ema,
)
render_signal_alerts(signals)


# ── Top Horizontal Pill Tabs (100% Viewport Width) ───────────────────────────
(
    tab_rank,
    tab_qual,
    tab_sec,
    tab_rrg,
    tab_strat,
    tab_port,
    tab_deliv,
    tab_watch,
    tab_breadth,
    tab_backtest,
    tab_config,
    tab_guide,
) = st.tabs(
    [
        "Screener",
        "Qualified",
        "Sectors",
        "RRG",
        "Multi-Strategy",
        "Portfolio",
        "Delivery",
        "Watchlist",
        "Market Breadth",
        "Backtest",
        "Configuration",
        "Guide",
    ]
)

with tab_rank:
    render_ranking_view(rank_df, adj_close, high_prices, low_prices, volume_data)

with tab_qual:
    render_qualified_view(rank_df, adj_close)

with tab_sec:
    render_sector_view(calc, rank_df, adj_close)

with tab_rrg:
    render_rrg_view(calc, rank_df, adj_close)

with tab_strat:
    render_strategy_view(calc, rank_df, adj_close, weights)

with tab_port:
    render_portfolio_view(
        calc=calc,
        rank_df=rank_df,
        sector_cap=sector_cap,
        stock_cap=stock_cap,
        vol_target_on=vol_target_on,
        vol_target_val=vol_target_val,
    )

with tab_deliv:
    render_delivery_view(rank_df)

with tab_watch:
    render_watchlist_view(rank_df)

with tab_breadth:
    render_breadth_view(rank_df, adj_close)

with tab_backtest:
    render_backtest_view(
        rank_df=rank_df,
        adj_close=adj_close,
        stock_cap=stock_cap,
        sector_cap=sector_cap,
        weights=weights,
    )

with tab_config:
    render_config_view(rank_df)

with tab_guide:
    render_guide_view(rank_df)
