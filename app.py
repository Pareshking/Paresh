"""
NSE Momentum Dashboard — Production Application Entry Point.
Architecture: Modular Package Hierarchy with Pure Paper White Theme & 100% Full Viewport Widescreen Layout.
Flush 0px top padding with Investrack Pill Tab Navigation.
"""

import concurrent.futures
import json
import warnings

import pandas as pd
import streamlit as st

# Suppress runtime noise
warnings.filterwarnings("ignore", category=RuntimeWarning, module="numpy")
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
from src.core.logger import logger
from src.engine import pipeline
from src.engine.corporate_actions import adjust_ohlc, load_events
from src.loaders.indices_loader import fetch_indices_data
# R2-backed production readers are an explicit transport boundary; keep this import adjacent to the loader.
from r2.consumers import r2_streamlit
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
# The engine's memo key AND the precomputed table's validity contract are the
# same fingerprint, so it lives in src/engine/pipeline beside the arithmetic it
# describes -- the nightly job stamps the artifact with it and production
# re-checks it before trusting a single row.
_price_hash = pipeline.price_fingerprint
_symbols_hash = pipeline.symbols_fingerprint


@st.cache_data(show_spinner=False, ttl=3600)
def load_prices_cached(
    sym_key: str, _symbols: list[str], period: str = "2y"
) -> pd.DataFrame:
    # Bumped only when the memo actually misses. If the surrounding stage ran
    # but this stayed at zero, Streamlit served a warm cache and the timing is
    # not a cold one.
    metrics.incr("memo_miss_prices")
    if r2_streamlit.enabled():
        frame, pin = r2_streamlit.read_configured_deep_history()
        metrics.note("deep_price_provider", "r2_yahoo_archive")
        metrics.note("deep_price_as_of", pin.as_of)
        metrics.note("deep_price_revision", pin.revision_sha256)
        logger.info(
            "Deep price history loaded: provider=object_storage dataset=%s as_of=%s revision=%s source=Yahoo-origin archive",
            pin.dataset, pin.as_of, pin.revision_sha256,
        )
        return frame
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


@st.cache_data(show_spinner=False, ttl=3600)
def _adjust_for_corporate_actions(price_hash: str, _frames: dict) -> tuple[dict, list]:
    """Neutralise flagged splits and demergers before the engine reads a price.

    run_backtest has done this since the guard was written; the SCREENER never
    did. The two therefore disagreed about the same stock: the Backtest tab
    priced ABFRL's 1:3 split as the non-event it was, while the ranking on the
    front page scored it through a phantom -67% session and buried it.

    Measured against the published snapshot on 2026-09-15, eight of the 750
    names carried such a session inside a live lookback -- PGIL, HEG,
    INDIAGLYCO and TDPOWERSYS inside ALL FIVE of them, so 100% of each score
    was drawn across a crash that never happened. Every one of the fourteen
    logged events was still sitting in the prices, none had been restated away.

    Cached on the price hash: the adjustment is a handful of column multiplies,
    but it must not re-run on every slider tick.
    """
    metrics.incr("memo_miss_corporate_actions")
    events = load_events()
    adjusted, applied = adjust_ohlc(_frames, events)
    metrics.note("corporate_actions_applied", len(applied))
    if applied:
        logger.info(
            "Neutralised %d flagged corporate action(s) before ranking: %s",
            len(applied),
            ", ".join(sorted({str(e.get("symbol")) for e in applied})),
        )
    return adjusted, applied


# Ten minutes, not an hour, and the reason is NEGATIVE caching.
#
# @st.cache_data stores a failure as readily as a success. The container that
# started at 03:27 UTC on 2026-09-16 asked for an artifact the nightly job had
# not published yet, got a 404, and cached it -- so when the artifact landed
# twenty minutes later the app went on skipping it for the rest of the hour and
# rebuilt the engine on every cold start in between. The probe recorded exactly
# that: ranking_snapshot=http_404 against a file that by then downloaded fine.
#
# The asymmetry decides the number. Re-fetching costs 200 KB and ~0.04s on a
# file that changes once a day; NOT re-fetching costs a full engine build and
# leaves the artifact ignored for up to an hour after it appears.
_RANKING_SNAPSHOT_TTL_S = 600


@st.cache_data(show_spinner=False, ttl=_RANKING_SNAPSHOT_TTL_S)
def _fetch_ranking_snapshot() -> tuple:
    """Download the published ranking. Validated separately, and later.

    Split from the check on purpose. The contract cannot be evaluated until the
    price frame is loaded and fingerprinted, but the DOWNLOAD depends on none of
    that -- so it is submitted to the same pool that already overlaps market
    caps and the regime fetch, and by the time there is something to check
    against, the bytes have arrived. A hit then costs nothing on the critical
    path, and a miss costs one request nobody waited for.
    """
    from src.loaders import ranking_store

    return ranking_store.fetch_snapshot()


def _precomputed_ranking(
    fetched: tuple,
    price_hash: str,
    sym_key: str,
    weights: tuple[float, ...],
    universe: list[str],
    applied_actions: list | None = None,
    price_source: str | None = None,
    price_as_of: str | None = None,
) -> pd.DataFrame | None:
    """The nightly job's ranking, but only if it describes exactly this state.

    Thirty of the eighty-nine seconds of a cold start were spent deriving a
    table that is a pure function of inputs this job already had. It ranks the
    same frame it publishes, and stamps the answer with a contract naming every
    input. Production re-checks all of them.

    A miss is normal and cheap: different weights, a universe change, a price
    frame that has moved on since the job ran, or no asset at all. Each returns
    None and the engine runs exactly as it did before. The one outcome worth
    preventing is a HIT that should have been a miss -- a ranking served fast
    against a configuration it does not describe -- which is why every field is
    compared and nothing is inferred.
    """
    from src.loaders import ranking_store

    frame, published = fetched
    if frame is None:
        return None

    expected = ranking_store.contract(
        price_fingerprint=price_hash,
        price_source=price_source,
        # The session the engine would STOP on, which the fingerprint cannot
        # see. It hashes the last row, the shape and the last date; the ranked
        # session is chosen by walking BACK from there over coverage. Two
        # frames can therefore fingerprint identically -- same shape, same
        # final row, right down to its NaNs -- while an earlier session is
        # thin in one and healed in the other, and rank a different day.
        # Verified: publisher 2026-09-09, reader 2026-09-10, one fingerprint.
        # Without this the reader accepts a table for a session it would not
        # have ranked, and every other contract term still matches.
        price_as_of=price_as_of,
        symbols_fingerprint=sym_key,
        weights=weights,
        pipeline_version=pipeline.PIPELINE_VERSION,
        universe=universe,
        # The price fingerprint is blind to these: an adjustment rewrites
        # history BEFORE its own date and leaves the last row alone. See
        # ranking_store.actions_digest.
        applied_actions=applied_actions,
    )
    ok, reason = ranking_store.matches(published, expected)
    if not ok:
        # Logged, not silent: "the precompute did not hit" and "the precompute
        # does not exist" need very different fixes, and only this line tells
        # them apart from outside the container.
        logger.info("Precomputed ranking rejected (%s); computing instead.", reason)
        metrics.note("ranking_precompute", f"miss_{reason.replace(' ', '_')}")
        if reason == "symbols_fingerprint differs" and "Symbol" in frame:
            published_symbols = {
                str(symbol).strip().upper()
                for symbol in frame["Symbol"].dropna().tolist()
            }
            expected_symbols = {
                str(symbol).strip().upper()
                for symbol in universe
            }
            added = sorted(published_symbols - expected_symbols)
            missing = sorted(expected_symbols - published_symbols)
            logger.info(
                "Precomputed universe mismatch: published=%d expected=%d added=%s missing=%s",
                len(published_symbols), len(expected_symbols),
                ",".join(added[:20]) or "-", ",".join(missing[:20]) or "-",
            )
            metrics.note("ranking_precompute_published_symbols", len(published_symbols))
            metrics.note("ranking_precompute_expected_symbols", len(expected_symbols))
            metrics.note("ranking_precompute_universe_added", ",".join(added[:20]) or "none")
            metrics.note("ranking_precompute_universe_missing", ",".join(missing[:20]) or "none")
        return None

    metrics.note("ranking_precompute", "hit")
    metrics.note("ranking_precompute_rows", int(len(frame)))
    logger.info(
        "Precomputed ranking accepted: %d rows, as of %s -- engine skipped.",
        len(frame), str((published or {}).get("price_as_of", "?")),
    )
    return frame


@st.cache_data(show_spinner=False, ttl=3600)
def _fetch_screener_store(_k: str, source_key: str):
    """Read Screener history, optionally from an immutable archive pin."""
    from r2.consumers import r2_streamlit
    from src.loaders import price_source as _ps

    if r2_streamlit.enabled():
        try:
            frame, pin = r2_streamlit.read_configured_screener()
        except Exception as exc:
            logger.error("Configured immutable Screener read failed: %s", type(exc).__name__)
            metrics.note("screener_store_fetch", f"r2_error_{type(exc).__name__}")
            raise RuntimeError("Configured immutable Screener read failed; refusing source fallback") from exc
        metrics.note("screener_store_source", "r2")
        metrics.note("screener_store_as_of", pin.as_of)
        metrics.note("screener_store_revision", pin.revision_sha256)
        logger.info(
            "Screener ranking store: source=object_storage dataset=%s as_of=%s revision=%s",
            pin.dataset,
            pin.as_of,
            pin.revision_sha256,
        )
        return frame

    frame = _ps.fetch_screener_store()
    logger.info("Screener ranking store: source=published_screener_https")
    return frame


def _resolve_price_source(price_hash, sym_key, adj_close, close_p, high_p, low_p, vol_p, symbols):
    """Pick the history the engine scores, falling back rather than failing.

    Screener finishes a session where Yahoo can stall for days, but it carries
    no intraday high, so the 52-week high is measured on closes and the ATR
    columns are dropped rather than computed at half their true width. A
    screener store that cannot reach the 12-month lookback is refused here, so
    the table never ships with an empty 12M column.
    """
    from r2.consumers import r2_streamlit
    from src.loaders import price_source as _ps

    fallback = _ps.from_yahoo(adj_close, close_p, high_p, low_p, vol_p)
    if _ps.preferred() != "screener":
        return fallback
    store = _fetch_screener_store(price_hash, r2_streamlit.configuration_key())
    chosen = _ps.from_screener(store) if store is not None else None
    if chosen is None:
        if r2_streamlit.enabled():
            raise RuntimeError("Configured immutable Screener dataset is not usable")
        return fallback
    keep = [c for c in chosen.close.columns if c in set(symbols)]
    if not keep:
        if r2_streamlit.enabled():
            raise RuntimeError("Configured immutable Screener dataset has no requested symbols")
        return fallback
    chosen.adj_close = chosen.close = chosen.close[keep]
    chosen.volume = chosen.volume.reindex(columns=keep)
    return chosen


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
    _corporate_actions: list | None = None,
):
    # Expensive: constructs the engine, computes 5×_calendar_period_metrics,
    # and pre-computes all weight-independent signal columns (ATR, EMA, 52W
    # high, ATH, drawdowns, persistence) so weight-slider changes in
    # run_momentum_pipeline skip the signal recomputation entirely.
    # _idx_info and _market_caps are underscore-prefixed (excluded from the
    # cache key); price_hash + index_hash already encode data state.
    metrics.incr("memo_miss_engine_base")
    return pipeline.build_engine(
        _adj_close, _high_prices, _low_prices, _close_prices, _volume_data,
        _idx_info, _market_caps, corporate_actions=_corporate_actions,
    )


@st.cache_data(show_spinner=False, ttl=3600)
def run_momentum_pipeline(
    base_hash: str,
    weights: tuple[float, ...],
    _calc,
    _index_info: pd.DataFrame,
    _market_caps: pd.Series,
    _close_prices: pd.DataFrame,
    _high_prices: pd.DataFrame,
    intraday: bool = True,
):
    # Cheap: weighted sum of the pre-computed z-scores + final ranking table.
    # Only re-runs when weights change; price/universe changes invalidate
    # base_hash, which also misses _run_engine_base first.
    metrics.incr("memo_miss_quant_engine")
    return pipeline.rank_with_weights(
        _calc, weights, _index_info, _market_caps, _close_prices, _high_prices,
        intraday=intraday,
    )


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
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as _pool:
        _fut_mcaps = _pool.submit(load_mcaps_cached, sym_key, symbols)
        _fut_regime = _pool.submit(get_market_regime)
        # Nothing about the download depends on the prices below, only the
        # CHECK does -- so it overlaps the price work instead of following it.
        _fut_ranking = _pool.submit(_fetch_ranking_snapshot)

        with metrics.stage("price_history"):
            raw_prices = load_prices_cached(sym_key, symbols, period="2y")
            if not r2_streamlit.enabled():
                metrics.note("deep_price_provider", "yahoo")
                logger.info(
                    "Deep price history loaded: provider=Yahoo; this feed is separate "
                    "from the ranking Screener/object-storage source."
                )
        if raw_prices.empty:
            return None

        with metrics.stage("extract_ohlcv"):
            p_hash_raw = _price_hash(raw_prices)
            adj_close, close_p, high_p, low_p, vol_p, open_p = _extract_ohlcv_cached(
                p_hash_raw, sym_key, raw_prices, symbols
            )

        # Every PRICE frame, together. Adjusting the close but not the high
        # would leave a split-adjusted price measured against an unadjusted
        # 52-week high -- a stock permanently "67% below its high" on a split
        # that cost its holders nothing. Volume is left alone on purpose; see
        # adjust_ohlc.
        # Which history to rank. price_source decides for BOTH the app and the
        # nightly precompute, so the two cannot end up scoring different data
        # while the ranking contract still matches -- a wrong answer served
        # fast, which nothing downstream could detect.
        with metrics.stage("price_source"):
            # Keep the Yahoo frame before the switch. The RANKING wants the
            # freshest complete session; the BACKTEST and the track record want
            # DEPTH, and those are different requirements from the same app.
            #
            # Screener serves about a year and grows one session a night, which
            # is ample to rank on and nowhere near the ~18 months a 12-month
            # formation window plus a 6-month reported period needs. Handing
            # them the ranking frame silently emptied both pages.
            _deep_adj_close, _deep_close = adj_close, close_p
            _deep_high, _deep_low = high_p, low_p

            _src = _resolve_price_source(
                p_hash_raw, sym_key, adj_close, close_p, high_p, low_p, vol_p, symbols
            )
            adj_close, close_p = _src.adj_close, _src.close
            high_p, low_p, vol_p = _src.high, _src.low, _src.volume
            if not _src.intraday:
                # OPEN MUST TRAVEL WITH CLOSE. It is extracted once from the
                # Yahoo frame and was never reassigned, so a screener-ranked app
                # drew candles with a Yahoo open against a screener close --
                # different lengths and, worse, different corporate-action
                # bases. On a demerged name that is a fictional body: HEG sits
                # at 728 in one and 267 in the other on the same session.
                #
                # None rather than a substitute. The chart degrades a bar with
                # no open to a flat close, which is exactly the honest picture
                # for a close-only feed.
                open_p = None
            metrics.note("price_source", _src.source)
            metrics.note("price_high_basis", _src.high_basis)
            metrics.note("price_intraday", "yes" if _src.intraday else "no")
            logger.info(
                "Ranking price source selected: source=%s as_of=%s high_basis=%s intraday=%s",
                _src.source,
                str(pipeline.ranking_as_of(adj_close)),
                _src.high_basis,
                "yes" if _src.intraday else "no",
            )

            # AFTER the source is chosen, never before. These describe the
            # frame the engine will actually score, and computing them from the
            # Yahoo frame while the ranking came from screener is exactly the
            # disagreement the ribbon exists to prevent: production showed
            # "16 Sep - 2 trading days behind" over a table dated 18 Sep,
            # because Yahoo's 17th and 18th were too thin to rank while
            # screener had both at 100%.
            try:
                _ranked = pipeline.ranking_as_of(adj_close)
                metrics.note("price_as_of", _ranked)
                _idx = pd.DatetimeIndex(adj_close.index)
                metrics.note("price_frame_last_row", str(_idx[-1].date()))

                _n = int(adj_close.shape[1])
                _cov = adj_close.notna().sum(axis=1)
                _ts = pd.Timestamp(_ranked)
                if _n and _ts in adj_close.index:
                    metrics.note("price_coverage", f"{int(_cov.loc[_ts])}/{_n}")
                # A newer session held back, named so a reader can tell a
                # deliberate wait from a broken pipeline.
                _newer = [d for d in _idx if d > _ts]
                if _newer and _n:
                    _d = _newer[-1]
                    metrics.note("price_deferred_as_of", str(_d.date()))
                    metrics.note("price_deferred_coverage", f"{int(_cov.loc[_d])}/{_n}")
            except Exception:
                pass

        with metrics.stage("corporate_actions"):
            _adj, _ca_applied = _adjust_for_corporate_actions(
                p_hash_raw,
                {"adj_close": adj_close, "close": close_p,
                 "high": high_p if high_p is not None else close_p,
                 "low": low_p if low_p is not None else close_p},
            )
            adj_close, close_p = _adj["adj_close"], _adj["close"]
            if _src.intraday:
                high_p, low_p = _adj["high"], _adj["low"]

        with metrics.stage("market_caps"):
            mcaps = _fut_mcaps.result()
        with metrics.stage("market_regime"):
            regime = _fut_regime.result()
        with metrics.stage("ranking_snapshot_fetch"):
            _fetched_ranking = _fut_ranking.result()

    p_hash = _price_hash(adj_close)
    i_hash = f"{len(idx_info)}_{sym_key}"
    base_hash = f"{p_hash}_{i_hash}_{pipeline.PIPELINE_VERSION}"

    def _build_engine_and_rank():
        """The 30 seconds. Deferred, so a cold start need not pay it at all."""
        with metrics.stage("engine_base"):
            calc_base = _run_engine_base(
                p_hash,
                i_hash,
                pipeline.PIPELINE_VERSION,
                adj_close,
                high_p,
                low_p,
                close_p,
                vol_p,
                idx_info,
                mcaps,
                _ca_applied,
            )
        with metrics.stage("quant_engine"):
            return run_momentum_pipeline(
                base_hash,
                weights,
                calc_base,
                idx_info,
                mcaps,
                close_p,
                high_p if high_p is not None else close_p,
                intraday=_src.intraday,
            )

    # The precomputed table, if the nightly job ranked exactly this frame under
    # exactly these weights. Every input is re-checked; anything unverifiable
    # falls straight through to the computation above. See ranking_store.
    calc = None
    rank_df = None
    with metrics.stage("precomputed_ranking"):
        rank_df = _precomputed_ranking(
            _fetched_ranking, p_hash, _symbols_hash(symbols), weights,
            sorted(idx_info["Symbol"].unique().tolist()) if "Symbol" in idx_info else [],
            _ca_applied,
            price_source=_src.source,
            # Same frame the fingerprint above is taken from, and the same call
            # scripts/sync_data.py makes, so the two sides are comparable.
            price_as_of=pipeline.ranking_as_of(adj_close),
        )

    if rank_df is None:
        calc, rank_df = _build_engine_and_rank()

    return {
        # A CALLABLE, not the engine. Only three of the eleven pages need it
        # (Sectors, RRG, Portfolio); the Screener that every cold start lands on
        # does not, and building it eagerly made every reader pay 30 seconds for
        # an object their first page never touched. Pages that need it call this
        # and get the same memoised engine.
        "get_calc": (lambda: calc) if calc is not None else (
            lambda: _build_engine_and_rank()[0]
        ),
        "calc": calc,
        "rank_df": rank_df,
        "adj_close": adj_close,
        # The longest continuous history available, whatever the ranking is
        # computed from. Only the backtest and the track record read this, and
        # only because they need more history than a ranking does.
        "deep_adj_close": _deep_adj_close,
        "deep_close_prices": _deep_close,
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
        # public_snapshot, not snapshot: this div is hidden, not private, and
        # which upstream feed the prices came from does not belong in HTML
        # anyone can view-source. Timings and counters are untouched.
        + json.dumps(metrics.public_snapshot())
        + "</div>",
        unsafe_allow_html=True,
    )


if not data:
    st.error(
        "❌ Failed to initialize market data. Please verify your internet connection or reload."
    )
    _emit_startup_metrics("data_init_failed")
    st.stop()

# The engine, only when a page actually needs it. `calc` is None whenever the
# precomputed ranking was accepted, which is the common cold start -- see
# _precomputed_ranking. Three pages call get_calc() and pay for it then.
calc = data["calc"]
get_calc = data["get_calc"]
rank_df = data["rank_df"]
adj_close = data["adj_close"]
deep_adj_close = data.get("deep_adj_close")
if deep_adj_close is None or deep_adj_close.empty:
    deep_adj_close = adj_close
high_prices = data["high_prices"]
low_prices = data["low_prices"]
volume_data = data["volume_data"]
regime_data = data["regime_data"]

# An empty ranking is a pipeline failure, not a view to render. Twelve tabs of
# empty frames produced a TypeError in the Qualified tab rather than telling
# anyone what went wrong, so stop here and report what the engine actually saw.
if rank_df.empty:
    # An empty ranking can only come from the live engine -- the precomputed
    # table is never published empty -- so calc is populated here by
    # construction. getattr keeps the diagnostics optional either way.
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


# ── Navigation ───────────────────────────────────────────────────────────────
# Keep the canonical page declarations and st.navigation router unchanged.
# The only experiment here is the user-facing trigger: a compact popover
# replaces the permanent eleven-item navigation row.



def _page_screener() -> None:
    render_ranking_view(
        rank_df, adj_close, high_prices, low_prices, volume_data,
        open_prices=data.get("open_prices"),
    )


def _page_qualified() -> None:
    render_qualified_view(rank_df, adj_close)


def _page_sectors() -> None:
    render_sector_view(get_calc(), rank_df, adj_close)


def _page_rrg() -> None:
    # No get_calc() here. This page never read the engine -- it took it as an
    # argument and ignored it -- so on the common cold start, where the
    # precomputed ranking is accepted and `calc` is still None, opening RRG
    # built the whole engine to satisfy an unused parameter.
    render_rrg_view(rank_df, adj_close)


def _page_portfolio() -> None:
    render_portfolio_view(
        calc=get_calc(),
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
        # Depth, not freshness: a 12-month formation window before a 6-month
        # reported period needs ~18 months of continuous daily data.
        adj_close=deep_adj_close,
        stock_cap=stock_cap,
        sector_cap=sector_cap,
        weights=weights,
    )


def _page_track_record() -> None:
    # The frozen record, plus a live MTD struck under the record's own pinned
    # configuration. fetch_benchmark_history is cached, so this is the same
    # round trip the Backtest page already made.
    render_track_record_view(
        adj_close=deep_adj_close,
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

# position="hidden" keeps Streamlit's own navigation out of the hidden header.
_nav = st.navigation(_PAGES, position="hidden")

# ── Top Header KPI Bar & Alerts ──────────────────────────────────────────────
total_stocks = len(rank_df)

above_ema = count_above_ema(rank_df)
pct_above_ema = (above_ema / total_stocks * 100) if total_stocks > 0 else 0.0

render_header_kpi_bar(
    regime=regime_data,
    total_stocks=total_stocks,
    above_ema=above_ema,
    pct_above_ema=pct_above_ema,
    nav_pages=_PAGES,
    active_page=_nav,
)

signals = compute_signals(
    rank_df=rank_df,
    regime_status=regime_data.status,
    dma_dist=regime_data.distance_pct,
    pct_above_ema=pct_above_ema,
)
render_signal_alerts(signals)


_nav.run()

# ── Cold-start telemetry ─────────────────────────────────────────────────────
# Hidden, inert element carrying this process's startup measurements so a
# production probe can read a real cold start from outside the container.
_emit_startup_metrics("ok")
