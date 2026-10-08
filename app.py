    """(frames the engine scores, the deep close history) -- Screener, then NSE.

    No Yahoo (owner, 2026-10-02). Screener carries no intraday high, so the
    52-week high is measured on closes and the ATR columns are dropped. A
    store that cannot reach the 12-month lookback is refused, and NSE's own
    closes rank instead; (None, None) when neither can serve.

    The deep history is Screener's whole store for these symbols (about ten
    years): the backtest and the track record want depth, not the ranking's
    400-day fill window.
    """
    from r2.consumers import r2_streamlit
    from src.loaders import nse_prices as _nse
    from src.loaders import price_source as _ps

    _ps.preferred()  # reports a stale UMIYA_PRICE_SOURCE setting
    metrics.memory_checkpoint("resolve_price_source:before_screener")
    store_result = _fetch_screener_store(r2_streamlit.configuration_key())
    metrics.memory_checkpoint("resolve_price_source:after_screener_fetch")
    chosen = None
    if store_result is not None:
        store, store_revision = store_result
        if store is not None:
            chosen = _shape_screener_store(store_revision, store)
    if chosen is not None:
        metrics.note("screener_shaped_shape", [int(chosen.close.shape[0]), int(chosen.close.shape[1])])
        metrics.note("screener_shaped_memory_bytes", int(chosen.close.memory_usage(deep=True).sum()))
    metrics.memory_checkpoint("resolve_price_source:after_screener_shape")
    if chosen is None and r2_streamlit.enabled():
        raise RuntimeError("Configured immutable Screener dataset is not usable")
    deep = None
    if chosen is not None:
        keep = [c for c in chosen.close.columns if c in set(symbols)]
        deep = chosen.close[keep].copy() if keep else None
    if deep is not None:
        metrics.note("deep_history_shape", [int(deep.shape[0]), int(deep.shape[1])])
        metrics.note("deep_history_memory_bytes", int(deep.memory_usage(deep=True).sum()))
    metrics.memory_checkpoint("resolve_price_source:after_deep_copy")
    _nse_close = _nse.middle_close(symbols)
    if _nse_close is not None:
        metrics.note("nse_middle_close_shape", [int(_nse_close.shape[0]), int(_nse_close.shape[1])])
        metrics.note("nse_middle_close_memory_bytes", int(_nse_close.memory_usage(deep=True).sum()))
    metrics.memory_checkpoint("resolve_price_source:after_nse_middle_close")
    src = _ps.frames_from(chosen, symbols, _nse_close)
    if src is not None and deep is None:
        deep = src.close
    return src, deep


@st.cache_data(show_spinner=False, ttl=86400)
def _load_tv_cached() -> dict:
    # load_tv_classification read from disk on every Streamlit rerun with no
    # caching at all. TV sector data changes at most once a day.
    return load_tv_classification()

