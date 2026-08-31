"""
NSE Momentum Dashboard — Production Application Entry Point.
Architecture: Modular Package Hierarchy with Pure Paper White Theme & 100% Full Viewport Widescreen Layout.
Flush 0px top padding with Investrack Pill Tab Navigation.
"""

import hashlib
import json
import warnings

import pandas as pd
import streamlit as st

# Suppress runtime noise
warnings.filterwarnings("ignore", category=RuntimeWarning, module="numpy")
warnings.filterwarnings("ignore", message=".*use_container_width.*")
warnings.filterwarnings("ignore", message=".*replace.*st\\.components\\.v1\\.html.*")
warnings.filterwarnings("ignore", message=".*st\\.components\\.v1\\.html.*")

# Core & Loaders
from src.core import startup_metrics as metrics
from src.core.config import (
    MCAP_PR_FILE,
    MCAPS_FILE,
    PRICES_FILE,
)
from src.engine.momentum import MomentumEngine
from src.engine.calendar_momentum import _compute_period_z_scores, _apply_weight_composite
from src.loaders.indices_loader import fetch_indices_data
from src.loaders.mcap_loader import fetch_market_caps
from src.loaders.price_loader import (
    extract_ohlcv,
    fetch_price_history,
    get_market_regime,
)
from src.loaders.tv_loader import load_tv_classification

# UI Design System, Components & Views
from src.ui.ema_utils import count_above_ema
from src.ui.components import (
    compute_signals,
    render_header_kpi_bar,
    render_signal_alerts,
)
from src.ui.theme import inject_custom_css
from src.ui.views.backtest_view import render_backtest_view
from src.ui.views.breadth_view import render_breadth_view
from src.ui.views.config_view import render_config_view
from src.ui.views.guide_view import render_guide_view
from src.ui.views.portfolio_view import render_portfolio_view
from src.ui.views.qualified_view import render_qualified_view
from src.ui.views.ranking_view import render_ranking_view
from src.ui.views.rrg_view import render_rrg_view
from src.ui.views.sector_view import render_sector_view
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
    """Memo key for the quant engine: shape, last session, AND last values.

    The values matter. Within a trading day the frame's last date and shape
    never change -- only the numbers in that final row do, as the session moves
    on. Keyed on shape and date alone, the engine kept returning the ranking it
    computed from the morning's prices while the loader underneath it went on
    refreshing them, so CMP, Score, Rank and every derived column were frozen
    on a page whose header dated them today.

    Hashing the last row is enough: everything before it is settled history,
    and a change there necessarily changes the length or the date too.
    """
    if df is None or df.empty:
        return "empty"
    try:
        last = pd.to_numeric(df.iloc[-1], errors="coerce").to_numpy(dtype="float64")
        digest = hashlib.md5(last.tobytes()).hexdigest()[:12]
        return f"{df.index[-1]}_{df.shape[0]}x{df.shape[1]}_{digest}"
    except Exception:
        return "unknown"


def _symbols_hash(symbols: list[str]) -> str:
    key = ",".join(sorted(s.upper() for s in symbols))
    return hashlib.md5(key.encode()).hexdigest()[:12]


@st.cache_data(show_spinner=False, ttl=3600)
def load_prices_cached(
    sym_key: str, _symbols: list[str], period: str = "2y"
) -> pd.DataFrame:
    # Bumped only when the memo actually misses. If the surrounding stage ran
    # but this stayed at zero, Streamlit served a warm cache and the timing is
    # not a cold one.
    metrics.incr("memo_miss_prices")
    return fetch_price_history(list(_symbols), period=period, force_refresh=False)


@st.cache_data(show_spinner=False, ttl=3600)
def load_mcaps_cached(sym_key: str, _symbols: list[str]) -> pd.Series:
    metrics.incr("memo_miss_market_caps")
    return fetch_market_caps(list(_symbols), force_refresh=False)


@st.cache_data(show_spinner=False, ttl=3600)
def _run_engine_base(
    price_hash: str,
    index_hash: str,
    pipeline_version: str,
    _adj_close: pd.DataFrame,
    _high_prices: pd.DataFrame,
    _low_prices: pd.DataFrame,
    _close_prices: pd.DataFrame,
    _volume_data: pd.DataFrame,
):
    # Expensive: constructs the engine and computes 5×_calendar_period_metrics.
    # Weights are intentionally absent from the cache key so slider adjustments
    # skip this stage entirely.
    metrics.incr("memo_miss_engine_base")
    calc = MomentumEngine(
        _adj_close,
        high_df=_high_prices,
        low_df=_low_prices,
        close_df=_close_prices,
        volume_df=_volume_data,
        weights=[0.2] * 5,
    )
    _compute_period_z_scores(calc)
    return calc


@st.cache_data(show_spinner=False, ttl=3600)
def run_momentum_pipeline(
    base_hash: str,
    weights: tuple[float, ...],
    _calc,
    _index_info: pd.DataFrame,
    _market_caps: pd.Series,
    _close_prices: pd.DataFrame,
    _high_prices: pd.DataFrame,
):
    # Cheap: weighted sum of the pre-computed z-scores + final ranking table.
    # Only re-runs when weights change; price/universe changes invalidate
    # base_hash, which also misses _run_engine_base first.
    metrics.incr("memo_miss_quant_engine")
    _calc.weights = list(weights)
    _apply_weight_composite(_calc, list(weights))
    rank_df = _calc.get_rankings(
        _index_info,
        _market_caps,
        close_prices_df=_close_prices,
        high_prices_df=_high_prices,
    )
    return _calc, rank_df


def load_all_data(indices: list[str]):
    force = st.session_state.pop("force_refresh", False)
    if force:
        st.cache_data.clear()

    # Snapshot cache presence BEFORE any fetch, so "was this container cold?"
    # is answered with evidence rather than inferred from a deploy happening.
    metrics.record_cache_presence({
        "prices": PRICES_FILE,
        "market_caps": MCAPS_FILE,
        "mcap_pr": MCAP_PR_FILE,
    })

    with metrics.stage("universe"):
        idx_info = fetch_indices_data(indices)
    if idx_info.empty:
        return None

    symbols = idx_info["Symbol"].unique().tolist()
    metrics.note("universe_symbols", len(symbols))
    sym_key = _symbols_hash(symbols)

    with metrics.stage("price_history"):
        raw_prices = load_prices_cached(sym_key, symbols, period="2y")
    if raw_prices.empty:
        return None

    with metrics.stage("extract_ohlcv"):
        adj_close, close_p, high_p, low_p, vol_p, open_p = extract_ohlcv(raw_prices, symbols)
    try:
        metrics.note("price_as_of", str(pd.DatetimeIndex(adj_close.index)[-1].date()))
    except Exception:
        pass
    with metrics.stage("market_caps"):
        mcaps = load_mcaps_cached(sym_key, symbols)
    with metrics.stage("market_regime"):
        regime = get_market_regime()

    p_hash = _price_hash(adj_close)
    i_hash = f"{len(idx_info)}_{sym_key}"
    base_hash = f"{p_hash}_{i_hash}_v4_calendar_periods"
    with metrics.stage("engine_base"):
        calc_base = _run_engine_base(
            p_hash,
            i_hash,
            "v4_calendar_periods",
            adj_close,
            high_p,
            low_p,
            close_p,
            vol_p,
        )
    with metrics.stage("quant_engine"):
        calc, rank_df = run_momentum_pipeline(
            base_hash,
            weights,
            calc_base,
            idx_info,
            mcaps,
            close_p,
            high_p,
        )

    return {
        "calc": calc,
        "rank_df": rank_df,
        "adj_close": adj_close,
        "close_prices": close_p,
        "high_prices": high_p,
        "low_prices": low_p,
        "volume_data": vol_p,
        "open_prices": open_p,
        "regime_data": regime,
        "idx_info": idx_info,
    }


# ── Load Market Data ─────────────────────────────────────────────────────────
with st.spinner("Loading market data & executing quantitative momentum engine…"):
    with metrics.stage("data_pipeline_total"):
        data = load_all_data(selected_indices)

def _emit_startup_metrics(outcome: str) -> None:
    """Publish this process's cold-start telemetry as a hidden, inert element.

    Called on the failure path as well as the success path: a cold start that
    fails is precisely when the stage timings and retry counts matter most,
    and st.stop() would otherwise end the script before they were ever
    published.
    """
    metrics.note("script_outcome", outcome)
    metrics.note("script_run_completed_at_s", metrics.since_start())
    st.markdown(
        '<div id="umiya-startup-metrics" style="display:none">'
        + json.dumps(metrics.snapshot())
        + "</div>",
        unsafe_allow_html=True,
    )


if not data:
    st.error(
        "❌ Failed to initialize market data. Please verify your internet connection or reload."
    )
    _emit_startup_metrics("data_init_failed")
    st.stop()

calc = data["calc"]
rank_df = data["rank_df"]
adj_close = data["adj_close"]
high_prices = data["high_prices"]
low_prices = data["low_prices"]
volume_data = data["volume_data"]
regime_data = data["regime_data"]

# An empty ranking is a pipeline failure, not a view to render. Twelve tabs of
# empty frames produced a TypeError in the Qualified tab rather than telling
# anyone what went wrong, so stop here and report what the engine actually saw.
if rank_df.empty:
    diag = getattr(calc, "ranking_diagnostics", {}) or {}
    metrics.note("ranking_diagnostics", diag)
    st.error(
        "❌ The momentum engine ranked 0 stocks, so there is nothing to show.\n\n"
        f"- Universe: **{diag.get('universe', 'unknown')}** symbols\n"
        f"- Price series loaded: **{diag.get('price_columns', 'unknown')}**, "
        f"matching the universe: **{diag.get('symbols_matching_prices', 'unknown')}**\n"
        f"- With any price history: **{diag.get('with_price_history', 'unknown')}**\n"
        f"- Meeting the {diag.get('min_observations', 63)}-observation minimum: "
        f"**{diag.get('meeting_min_observations', 'unknown')}**\n\n"
        "This is almost always upstream price data, not the ranking itself. "
        "Use **Force Refresh** to rebuild the cache, or retry shortly if the "
        "price provider is rate limiting."
    )
    _emit_startup_metrics("empty_ranking")
    st.stop()

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

above_ema = count_above_ema(rank_df)
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
    tab_port,
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
        "Portfolio",
        "Watchlist",
        "Market Breadth",
        "Backtest",
        "Configuration",
        "Guide",
    ]
)

with tab_rank:
    render_ranking_view(
        rank_df, adj_close, high_prices, low_prices, volume_data,
        open_prices=data.get("open_prices"),
    )

with tab_qual:
    render_qualified_view(rank_df, adj_close)

with tab_sec:
    render_sector_view(calc, rank_df, adj_close)

with tab_rrg:
    render_rrg_view(calc, rank_df, adj_close)

with tab_port:
    render_portfolio_view(
        calc=calc,
        rank_df=rank_df,
        sector_cap=sector_cap,
        stock_cap=stock_cap,
        vol_target_on=vol_target_on,
        vol_target_val=vol_target_val,
    )


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


# ── Cold-start telemetry ─────────────────────────────────────────────────────
# Hidden, inert element carrying this process's startup measurements so a
# production probe can read a real cold start from outside the container.
_emit_startup_metrics("ok")
