"""
NSE Momentum Dashboard — Production Application Entry Point.
Architecture: Modular Package Hierarchy with Pure Paper White Theme & 100% Full Viewport Widescreen Layout.
Flush 0px top padding with Investrack Pill Tab Navigation.
"""

import concurrent.futures
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
    DEFAULT_LOOKBACK_WEIGHTS,
    MCAP_PR_FILE,
    MCAPS_FILE,
    PRICES_FILE,
    REPO_MCAP_FILE,
    REPO_ATH_FILE,
)
from src.engine.momentum import MomentumEngine
from src.engine.calendar_momentum import _compute_period_z_scores, _apply_weight_composite
from src.loaders.indices_loader import fetch_indices_data
from src.loaders.mcap_loader import fetch_market_caps
from src.loaders.price_loader import (
    extract_ohlcv,
    fetch_benchmark_history,
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
from src.ui.widget_state import resolve
from src.ui.views.backtest_view import render_backtest_view
from src.ui.views.breadth_view import render_breadth_view
from src.ui.views.config_view import render_config_view
from src.ui.views.guide_view import render_guide_view
from src.ui.views.portfolio_view import render_portfolio_view
from src.ui.views.qualified_view import render_qualified_view
from src.ui.views.ranking_view import render_ranking_view
from src.ui.views.rrg_view import render_rrg_view
from src.ui.views.sector_view import render_sector_view
from src.ui.views.track_record_view import render_track_record_view
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

# Seed freshness dates from committed repo files so the ribbon always has
# something to show even before the loaders run (or on warm-cache reruns
# where cached loader bodies don't re-execute and can't re-note the facts).
# The loaders overwrite these with live dates when they run cold.
try:
    import os as _os
    _snap = pd.read_csv(REPO_MCAP_FILE) if _os.path.exists(REPO_MCAP_FILE) else None
    if _snap is not None and "AsOf" in _snap.columns and len(_snap):
        _d = str(_snap["AsOf"].iloc[0]).strip()
        if _d and "mcap_as_of" not in metrics.snapshot().get("facts", {}):
            metrics.note("mcap_as_of", _d)
            metrics.note("mcap_path", "repo_snapshot")
    _ath = pd.read_csv(REPO_ATH_FILE) if _os.path.exists(REPO_ATH_FILE) else None
    if _ath is not None and "AsOf" in _ath.columns and len(_ath):
        _d = str(_ath["AsOf"].iloc[0]).strip()
        if _d and "ath_as_of" not in metrics.snapshot().get("facts", {}):
            metrics.note("ath_as_of", _d)
            metrics.note("ath_path", "repo_snapshot")
except Exception:
    pass


# ── State Initialization ─────────────────────────────────────────────────────
if "cfg_indices" not in st.session_state:
    st.session_state["cfg_indices"] = ["NIFTY TOTAL MARKET"]
# Every cfg_* setting is read through one resolver: the widget's own value
# while it exists, then a mirror key that Streamlit's widget-state garbage
# collection cannot evict, then the documented default. Seeding session state
# from here is what these lines used to do, and it could not survive the
# Configuration tab's left-nav -- opening another section evicted the weight
# keys, and the absence guard then "restored" the DEFAULTS over a reader's own
# settings, silently, on the next run. See src/ui/widget_state.py.
selected_indices = st.session_state["cfg_indices"]
raw_w = [
    resolve(f"cfg_w{i}", float(DEFAULT_LOOKBACK_WEIGHTS[i - 1]), lo=0.0, hi=1.0)
    for i in range(1, 6)
]
total_w = sum(raw_w)
if total_w <= 0:
    # Every weight at zero is not a configuration, it is a broken one -- and the
    # old fallback quietly ranked the whole universe on EQUAL weights while the
    # Configuration tab still described 10/30/30/20/10. That is a different
    # strategy presented under the configured one's name. Rank on the documented
    # defaults and say so, rather than shipping a silent methodology swap.
    raw_w = list(DEFAULT_LOOKBACK_WEIGHTS)
    total_w = sum(raw_w)
    st.warning(
        "All five momentum lookback weights were zero, which cannot rank "
        "anything. Ranking is using the defaults "
        f"({' · '.join(f'{w:.0%}' for w in DEFAULT_LOOKBACK_WEIGHTS)}). "
        "Set them in **Configuration → Momentum Signal**."
    )
weights = tuple(w / total_w for w in raw_w)

sector_cap = resolve("cfg_sc", 30, lo=15, hi=50) / 100.0
stock_cap = resolve("cfg_stc", 5, lo=2, hi=15) / 100.0
vol_target_on = resolve("cfg_vt", False)
vol_target_val = resolve("cfg_vtv", 25, lo=10, hi=40) / 100.0


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
def _extract_ohlcv_cached(price_hash: str, sym_key: str, _raw_prices: pd.DataFrame, _symbols: list[str]):
    # extract_ohlcv is O(m) over the full MultiIndex on every call. Cache it so
    # reruns triggered by UI interactions (tab switches, slider ticks after the
    # engine cache warms up) skip the decomposition entirely.
    metrics.incr("memo_miss_ohlcv_extract")
    return extract_ohlcv(_raw_prices, _symbols)


@st.cache_data(show_spinner=False, ttl=86400)
def _load_tv_cached() -> dict:
    # load_tv_classification read from disk on every Streamlit rerun with no
    # caching at all. TV sector data changes at most once a day.
    return load_tv_classification()


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
    _idx_info: pd.DataFrame,
    _market_caps: pd.Series,
):
    # Expensive: constructs the engine, computes 5×_calendar_period_metrics,
    # and pre-computes all weight-independent signal columns (ATR, EMA, 52W
    # high, ATH, drawdowns, persistence) so weight-slider changes in
    # run_momentum_pipeline skip the signal recomputation entirely.
    # _idx_info and _market_caps are underscore-prefixed (excluded from the
    # cache key); price_hash + index_hash already encode data state.
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
    calc._precompute_signals(_idx_info, _market_caps, _close_prices, _high_prices)
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

    # mcaps + regime have no dependency on price_history — submit them to
    # background threads so the three fetches overlap on cold start.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as _pool:
        _fut_mcaps = _pool.submit(load_mcaps_cached, sym_key, symbols)
        _fut_regime = _pool.submit(get_market_regime)

        with metrics.stage("price_history"):
            raw_prices = load_prices_cached(sym_key, symbols, period="2y")
        if raw_prices.empty:
            return None

        with metrics.stage("extract_ohlcv"):
            p_hash_raw = _price_hash(raw_prices)
            adj_close, close_p, high_p, low_p, vol_p, open_p = _extract_ohlcv_cached(
                p_hash_raw, sym_key, raw_prices, symbols
            )
        try:
            metrics.note("price_as_of", str(pd.DatetimeIndex(adj_close.index)[-1].date()))
        except Exception:
            pass

        with metrics.stage("market_caps"):
            mcaps = _fut_mcaps.result()
        with metrics.stage("market_regime"):
            regime = _fut_regime.result()

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
            idx_info,
            mcaps,
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
with st.spinner("Loading market data…"):
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
tv_map = _load_tv_cached()
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


# ── Navigation ───────────────────────────────────────────────────────────────
# `st.tabs` executed ALL ELEVEN tab bodies on every rerun. That is Streamlit's
# documented behaviour, not a defect, but it made every click cost eleven pages
# of Python (~1.0s measured, charts stubbed) and put every tab's widgets in one
# DOM at once -- fourteen sliders from four different tabs were readable in a
# single production frame.
#
# `st.navigation` runs ONLY the selected page. The trade is that Streamlit now
# discards widget state for every page the reader is not looking at, so each
# keyed widget must carry an explicit value and, where the choice should
# survive, a mirror key. See src/ui/widget_state.py and the README.
#
# Each page is a zero-argument closure over the data loaded above: `st.Page`
# takes a callable with no parameters, and the pipeline is shared by every page
# because the entrypoint runs before the selected page does.


def _page_screener() -> None:
    render_ranking_view(
        rank_df, adj_close, high_prices, low_prices, volume_data,
        open_prices=data.get("open_prices"),
    )


def _page_qualified() -> None:
    render_qualified_view(rank_df, adj_close)


def _page_sectors() -> None:
    render_sector_view(calc, rank_df, adj_close)


def _page_rrg() -> None:
    render_rrg_view(calc, rank_df, adj_close)


def _page_portfolio() -> None:
    render_portfolio_view(
        calc=calc,
        rank_df=rank_df,
        sector_cap=sector_cap,
        stock_cap=stock_cap,
        vol_target_on=vol_target_on,
        vol_target_val=vol_target_val,
    )


def _page_watchlist() -> None:
    render_watchlist_view(rank_df)


def _page_breadth() -> None:
    render_breadth_view(rank_df, adj_close)


def _page_backtest() -> None:
    render_backtest_view(
        rank_df=rank_df,
        adj_close=adj_close,
        stock_cap=stock_cap,
        sector_cap=sector_cap,
        weights=weights,
    )


def _page_track_record() -> None:
    # The frozen record, plus a live MTD struck under the record's own pinned
    # configuration. fetch_benchmark_history is cached, so this is the same
    # round trip the Backtest page already made.
    render_track_record_view(
        adj_close=adj_close,
        benchmark_close=fetch_benchmark_history(period="5y"),
    )


def _page_configuration() -> None:
    render_config_view(rank_df)


def _page_guide() -> None:
    render_guide_view(rank_df)


# Titles and order are the app's public surface: the production QA probe walks
# them by name and tests/test_qa_tab_list_matches_the_app.py pins them, so a
# rename here without one there is a failing build, not a silent drift.
_PAGES = [
    st.Page(_page_screener, title="Screener", url_path="screener", default=True),
    st.Page(_page_qualified, title="Qualified", url_path="qualified"),
    st.Page(_page_sectors, title="Sectors", url_path="sectors"),
    st.Page(_page_rrg, title="RRG", url_path="rrg"),
    st.Page(_page_portfolio, title="Portfolio", url_path="portfolio"),
    st.Page(_page_watchlist, title="Watchlist", url_path="watchlist"),
    st.Page(_page_breadth, title="Market Breadth", url_path="breadth"),
    st.Page(_page_backtest, title="Backtest", url_path="backtest"),
    st.Page(_page_track_record, title="Track Record", url_path="track-record"),
    st.Page(_page_configuration, title="Configuration", url_path="configuration"),
    st.Page(_page_guide, title="Guide", url_path="guide"),
]

# position="hidden": Streamlit draws NO navigation of its own, and the app
# draws its own row below. This is not a preference.
#
# `position="top"` renders the nav INSIDE Streamlit's header, and
# src/ui/theme.py:240 hides that header outright:
#
#     header, [data-testid="stHeader"], .stApp > header { display: none !important; }
#
# so the nav shipped in the DOM with display:none. The app was left with no way
# to reach ten of its eleven pages, and because hidden elements contribute no
# text, the QA probe saw a healthy shell with no navigation and no page names --
# which is exactly what it reported. Test:
# tests/test_navigation_is_visible.py.
#
# Drawing it here also puts it back where the tab strip was, under the header
# KPI bar, instead of above it in the chrome.
_nav = st.navigation(_PAGES, position="hidden")

with st.container(horizontal=True, wrap=True, gap="small", key="app_nav"):
    for _i, _p in enumerate(_PAGES):
        # The ACTIVE item is marked here, in Python, not in CSS. Streamlit
        # styles the current page link through an emotion prop with no stable
        # attribute -- no aria-current, no class worth targeting -- so the only
        # selector available would be a generated class hash that changes
        # between versions. `st.navigation` returns one of the very objects it
        # was passed (navigation.py resolves `matching_pages[0]` from the list),
        # so identity is exact and needs no attribute access; reading `.title`
        # here raised AttributeError whenever app.py was imported outside a
        # script run.
        _state = "navon" if _p is _nav else "navoff"
        # width="content" is load-bearing, not decoration. st.container defaults
        # to width="stretch", so each of these per-item wrappers claimed the
        # full column width and only two pills fitted per row -- eleven items
        # became a six-row, ~500px block above the content on a phone. Hugging
        # the label lets them pack.
        with st.container(key=f"{_state}_{_i}", width="content"):
            # No explicit label: st.page_link takes the page's own title.
            st.page_link(_p)

_nav.run()


# ── Cold-start telemetry ─────────────────────────────────────────────────────
# Hidden, inert element carrying this process's startup measurements so a
# production probe can read a real cold start from outside the container.
_emit_startup_metrics("ok")
