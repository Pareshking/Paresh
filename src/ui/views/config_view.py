"""
Configuration & System Settings View Controller.
Windows 11-style left-nav + right-content layout.
"""

import html
import os
import threading
import time
from datetime import datetime

import pandas as pd
import streamlit as st

from src.ui import page_kit as kit
from src.ui import system_param
from src.engine.liquidity import DEFAULT_FLOOR_CR

from src.core.config import (
    DEFAULT_LOOKBACK_WEIGHTS,
    DEFAULT_SECTOR_CAP,
    DEFAULT_STOCK_CAP,
    INDICES_LOCAL,
    INDICES_URLS,
    MCAPS_FILE,
    PRICES_FILE,
    TV_CLASSIFICATION_FILE,
)
from src.engine.corporate_actions import load_events
from src.engine.extra_universe import (
    SYSTEM_750, SYSTEM_COMBINED, SYSTEM_NAMES, SYSTEM_NANO, SYSTEMS,
)
from src.loaders.extra_universe_loader import membership_summary
from src.loaders.indices_loader import get_sync_metadata, sync_official_nse_indices
from src.ui.components import age_phrase, data_freshness, gap_count, render_data_quality_footer
from src.ui.widget_state import forget, remember, resolve
from src.ui.theme import render_saas_table

# Sync and Purge clear st.cache_data for the WHOLE PROCESS, not the clicking
# reader: every other visitor's next rerun then pays the cold engine build
# (~30 s), and Sync also re-downloads every index file from niftyindices.com.
# The app is public, so one reader clicking repeatedly would do that to
# everyone. One clear per window, shared across sessions; module state is
# process-wide in Streamlit.
GLOBAL_REFRESH_COOLDOWN_S = 15 * 60
_refresh_lock = threading.Lock()
_last_global_refresh = [float("-inf")]


def _claim_global_refresh(now: float | None = None) -> float:
    """0.0 when this caller may clear the shared caches, else seconds to wait."""
    now = time.monotonic() if now is None else now
    with _refresh_lock:
        wait = _last_global_refresh[0] + GLOBAL_REFRESH_COOLDOWN_S - now
        if wait > 0:
            return wait
        _last_global_refresh[0] = now
        return 0.0


def _refused_refresh(wait: float) -> None:
    st.toast(
        f"Data was refreshed moments ago. Try again in {max(1, round(wait / 60))} min.",
        icon="⏳",
    )


# The page's four sections, in order: anchor id, title, one short line, and
# which pages a change reaches (the heading's tooltip). One list feeds the
# index and the section headers, so the two cannot disagree.
_SECTIONS = [
    ("cfg-universe", "Universe",
     "Which stocks are ranked, from the official NSE lists.", "every page"),
    ("cfg-score", "Momentum score",
     "How much each lookback window counts.",
     "ranks on every page, and the backtest's starting weights"),
    ("cfg-limits", "Portfolio limits",
     "The Backtest's caps and floor. The track record's own limits: 5% a stock, "
     "40% a sector, no floor.",
     "the Backtest only"),
    ("cfg-health", "Data health",
     "Price corrections and data files.", "nothing; this section only reports"),
]


@st.dialog("Index files on disk", width="medium")
def _index_files_dialog() -> None:
    """Read-only: which constituent lists are on disk, and how fresh."""
    for idx_name, path in INDICES_LOCAL.items():
        if os.path.exists(path):
            size = os.path.getsize(path)
            mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime(
                "%d %b %Y, %H:%M"
            )
            with open(path, "r", encoding="utf-8") as f:
                lines = sum(1 for _ in f) - 1
            st.caption(
                f"**{idx_name.title()}**: `{lines}` constituents ({size/1024:.1f} KB) · {mtime}"
            )
        else:
            st.caption(f"**{idx_name.title()}**: File missing at `{path}`")


@st.dialog("Corporate actions adjusted, by date", width="large")
def _spike_sessions_dialog(rows: list[dict]) -> None:
    """Read-only: every flagged session, newest first, and how each is handled."""
    kit.caption(
        "Each is neutralised in memory before ranking and in the backtest, by rescaling "
        "the history before it. Stored prices are never edited, so a later correction "
        "from the provider is not applied twice."
    )
    kit.caption(
        "A split or bonus should have been adjusted away by the data provider and was not; "
        "re-fetching fixes it. A possible demerger matches no standard ratio; providers "
        "generally don't adjust for these because the parent's price genuinely falls while "
        "shareholders receive stock in the new entity."
    )
    render_saas_table(pd.DataFrame(rows))


def _freshness_table() -> None:
    """Every source's latest date and whether it is current: the one place to check."""
    try:
        items = data_freshness()
    except Exception:
        items = []
    if not items:
        return
    rows = [{
        "Source": str(i["label"]),
        "Latest": str(i["as_of"]) + (f" · {i['coverage']}" if i.get("coverage") else ""),
        "Age": age_phrase(i).strip(" ·()") or "current",
        "Status": "Behind" if i["stale"] else "Current",
    } for i in items]
    render_saas_table(pd.DataFrame(rows))


def _section_data_sync(sync_meta: dict, tot_stk: int, engine_stocks: int) -> None:
    last_sync = sync_meta.get("last_synced") or "Never synced"
    sync_ok = sync_meta.get("last_attempt_ok")
    last_attempt = sync_meta.get("last_attempt")
    attempt_fetched = sync_meta.get("last_attempt_fetched")
    attempt_errors = sync_meta.get("last_attempt_errors") or {}

    sync_day, _, sync_time = str(last_sync).partition(", ")
    tiles = [
        kit.Reading("Last synced", sync_day, f"at {sync_time}" if sync_time else ""),
        kit.Reading("In the index files", f"{tot_stk:,}", "stocks"),
    ]
    if engine_stocks != tot_stk:
        tiles.append(kit.Reading("Ranked now", f"{engine_stocks:,}", "stocks"))
    kit.readings(tiles, "Index sync")
    _freshness_table()
    if sync_ok is False:
        kit.note(
            f"The last sync ({last_attempt or 'time unknown'}) did not complete.",
            f"It fetched {attempt_fetched if attempt_fetched is not None else '?'} index "
            f"file(s) and {len(attempt_errors)} failed; the figures above are from the "
            "last complete sync.",
        )

    # Owner, 2026-09-27: three systems in one app; every page follows this.
    nano = membership_summary()
    options = list(SYSTEMS) if nano else [SYSTEM_750]
    count = f"{nano.get('count', '?')} stocks · " if nano else ""
    captions = {
        SYSTEM_750: "Default · record since Jan 2026",
        SYSTEM_NANO: f"₹2,000 Cr+ outside the 750 · {count}record from Oct 2026",
        SYSTEM_COMBINED: "Both, ranked together · record from Oct 2026",
    }
    current = system_param.current()
    chosen = st.segmented_control(
        "System", options,
        default=current if current in options else options[0],
        required=True,
        format_func=SYSTEM_NAMES.get,
        key="cfg_system_radio",
        help="Every page follows this choice. Nano Cap is every stock of ₹2,000 Cr "
             "or more outside the 750, fixed at each month-end"
             + (f" (list of {nano.get('as_of')})" if nano else "")
             + ", ranked among themselves; Combined ranks both as one list.",
    ) or (current if current in options else options[0])
    st.caption(captions[chosen])
    if chosen != current:
        st.session_state["cfg_system"] = chosen
        st.rerun()

    # Which indices feed the ranking. Chosen first, synced second.
    available_indices = list(INDICES_URLS.keys())
    curr_indices = st.session_state.get("cfg_indices", ["NIFTY TOTAL MARKET"])
    new_indices = st.multiselect(
        "Indices to rank",
        available_indices,
        default=curr_indices,
        format_func=str.title,
        key="cfg_indices_multiselect",
    )
    if new_indices != curr_indices:
        st.session_state["cfg_indices"] = new_indices
        st.session_state.pop("data_loaded_key", None)
        st.rerun()

    with st.container(horizontal=True, vertical_alignment="center", key="cfg_sync_row"):
        if st.button("Sync from niftyindices.com", type="primary", key="btn_sync_indices",
                     help="Fetch the latest official constituent lists. One sync at a time, "
                          "app-wide."):
            _wait = _claim_global_refresh()
            if _wait:
                _refused_refresh(_wait)
            else:
                with st.status("Syncing NSE constituents…", expanded=True) as _sync_status:
                    _sync_status.write("Downloading index CSV files from niftyindices.com…")
                    res = sync_official_nse_indices(force=True)
                    st.session_state["force_refresh"] = True
                    st.session_state.pop("data_loaded_key", None)
                    st.cache_data.clear()
                    st.cache_resource.clear()  # the shared price frames (app.py _shared)
                    if res.get("last_attempt_ok"):
                        n = res["total_stocks"]
                        _sync_status.update(
                            label=f"Synced {n} constituents successfully",
                            state="complete",
                            expanded=False,
                        )
                    else:
                        fetched = res.get("last_attempt_fetched", 0)
                        errors = len(res.get("last_attempt_errors") or {})
                        _sync_status.update(
                            label=f"Sync incomplete — {fetched} downloaded, {errors} failed",
                            state="error",
                            expanded=False,
                        )
                    st.rerun()
        if st.button("Clear cached files", type="secondary", key="btn_purge_cache",
                     help="Drop the cached prices and index lists and load them again."):
            _wait = _claim_global_refresh()
            if _wait:
                _refused_refresh(_wait)
            else:
                st.session_state["force_refresh"] = True
                st.session_state.pop("data_loaded_key", None)
                st.cache_data.clear()
                st.cache_resource.clear()  # the shared price frames (app.py _shared)
                st.rerun()

    if st.button(f"Index files on disk ({len(INDICES_LOCAL)})", type="tertiary",
                 icon=":material/folder_open:", key="dlg_cfg_index_files"):
        _index_files_dialog()


# The five lookback windows, their canonical keys, and the documented default
# for each. One list so the pill, the sliders and the reset button cannot drift.
_WINDOWS: list[tuple[str, str, float]] = [
    ("1M", "cfg_w1", DEFAULT_LOOKBACK_WEIGHTS[0]),
    ("3M", "cfg_w2", DEFAULT_LOOKBACK_WEIGHTS[1]),
    ("6M", "cfg_w3", DEFAULT_LOOKBACK_WEIGHTS[2]),
    ("9M", "cfg_w4", DEFAULT_LOOKBACK_WEIGHTS[3]),
    ("12M", "cfg_w5", DEFAULT_LOOKBACK_WEIGHTS[4]),
]

# What each window measures, shown as its slider's tooltip. Every window runs
# from its calendar start to the latest close; none skips the latest month.
# Session counts are approximate because the windows are calendar-anchored.
_WINDOW_HELP = {
    "1M": "1 calendar month to the latest close, about 21 sessions. "
          "Recent acceleration; noisy on its own.",
    "3M": "3 months to the latest close, about 63 sessions. The main swing of a "
          "trend; more weight favours fast breakouts.",
    "6M": "6 months to the latest close, about 126 sessions. An established trend.",
    "9M": "9 months to the latest close, about 189 sessions. Persistence; more "
          "weight favours slow, persistent trends.",
    "12M": "12 months to the latest close, about 252 sessions. The long base; "
           "guards against spikes.",
}


def _section_momentum_signal() -> None:
    # Resolve once, and hand the SAME numbers to the pill and to the sliders.
    # Reading them separately is what let the two disagree on screen.
    current = {key: resolve(key, default, lo=0.0, hi=1.0)
               for _label, key, default in _WINDOWS}
    raw_w = [current[key] for _label, key, _d in _WINDOWS]
    tot_w = sum(raw_w)
    # All-zero falls back to what app.py actually ranks on -- the documented
    # defaults -- not an equal split the ranking never uses.
    _fallback = [float(w) for w in DEFAULT_LOOKBACK_WEIGHTS]
    norm_w = (
        [w / tot_w for w in raw_w] if tot_w > 0
        else [w / sum(_fallback) for w in _fallback]
    )

    # The split as a bar, labelled. "Weight vector:" is also what the
    # production QA probe reads back off the page, so the wording stays.
    shades = ("#C7D2FE", "#818CF8", "#4F46E5", "#3730A3", "#1E1B4B")
    segs = "".join(
        f'<span style="width:{w * 100:.2f}%;background:{c};color:{"#0E1726" if i < 2 else "#FFFFFF"}">'
        f"{html.escape(lbl)} {w:.0%}</span>"
        for i, ((lbl, _k, _d), w, c) in enumerate(zip(_WINDOWS, norm_w, shades)) if w > 0
    )
    st.html(
        '<div class="cfg-wbar-h">How the score weighs each window · Weight vector: '
        + " · ".join(f"{w:.0%}" for w in norm_w)
        + f'</div><div class="cfg-wbar">{segs}</div>'
    )

    if st.button("Reset to defaults", key="cfg_w_reset"):
        # Write the mirror and DROP the widget's own state, so the sliders read
        # the restored value on the next run. Writing the widget key instead is
        # legal only above the widget, and was the shape that crashed the tab.
        for _label, key, default in _WINDOWS:
            remember(key, float(default))
            forget(key)
        st.rerun()

    wc = st.columns(5, vertical_alignment="top")
    for col, (label, key, default) in zip(wc, _WINDOWS):
        # Hand the widget an EXPLICIT value. Relying on session state alone is
        # what produced the reported defect: measured against the live app on
        # 2026-09-11, these five were the only sliders in the whole DOM without
        # one, and the only five rendering at their minimum -- 0.00 beside a
        # pill reading the correct weights from the same state. The Backtest
        # tab's five, identical in range and step but given a value, were
        # correct in the same frame.
        shown = col.slider(
            label, min_value=0.0, max_value=1.0,
            value=float(current[key]), step=0.05, key=key, help=_WINDOW_HELP[label],
        )
        # Record it where eviction cannot reach it, so navigating to another
        # section no longer reverts a reader's own weights to the defaults.
        remember(key, float(shown))
        current[key] = float(shown)

    # A vector that sums to zero cannot rank anything. Say so and leave the
    # controls alone: the previous repair wrote `st.session_state[key]` AFTER
    # the slider existed, which raises StreamlitWidgetAlreadyInstantiatedError
    # and took the entire Configuration tab down for anyone who dragged all
    # five to zero. `app.py` ranks on the documented defaults meanwhile, and
    # says so there too.
    if sum(current.values()) <= 0:
        st.warning(
            "All five lookback weights are zero, which cannot rank anything. "
            "Ranking is using the documented defaults "
            f"({' · '.join(f'{w:.0%}' for w in DEFAULT_LOOKBACK_WEIGHTS)}) "
            "until you set one — press **Reset to defaults** above."
        )

    kit.caption("Weights are normalised to 100%.")


# Defaults for the on-demand Portfolio limits widgets. Same reason as the weight
# sliders: the left-nav renders one section per run, Streamlit evicts widget
# state for anything it did not render last time, and a slider with a key but no
# value then falls back to its `min_value`. Here that is silently DESTRUCTIVE
# rather than merely visible -- a 30% sector cap would come back as 15% and a 5%
# stock cap as 2%, both of them plausible numbers that now genuinely bind the
# backtest. (The model book on Portfolio and Actions is pinned to the record's
# limits and reads none of these.)
# key -> (default, minimum, maximum). Ranges live here so the resolver rejects
# an out-of-range stored value the same way the widget would.
# Volatility targeting was removed (owner, 12 Oct 2026): no page used it.
_RISK_SETTINGS: dict[str, tuple] = {
    "cfg_sc": (round(DEFAULT_SECTOR_CAP * 100), 15, 50),
    "cfg_stc": (round(DEFAULT_STOCK_CAP * 100), 2, 15),
    "cfg_lf": (False, None, None),
    "cfg_lfv": (DEFAULT_FLOOR_CR, 1, 500),
}


def _risk(key):
    """The live value of one risk setting, resolved before it is rendered."""
    default, lo, hi = _RISK_SETTINGS[key]
    return resolve(key, default, lo=lo, hi=hi)


def _section_portfolio_risk() -> None:
    # Same exposure as the weight sliders, and worse in consequence: an evicted
    # weight comes back as an obvious 0.00, but an evicted cap comes back as a
    # PLAUSIBLE number -- a 30% sector cap as 15%, a 5% stock cap as 2% -- and
    # both genuinely bind the backtest. Every widget below is handed an
    # explicit resolved value and mirrored afterwards.
    lc, rc = st.columns(2, gap="large", vertical_alignment="top")
    new_sc = lc.slider(
        "Most in one sector (%)", min_value=15, max_value=50, step=5,
        value=_risk("cfg_sc"), key="cfg_sc",
    )
    remember("cfg_sc", int(new_sc))
    new_stc = rc.slider(
        "Most in one stock (%)", min_value=2, max_value=15, step=1,
        value=_risk("cfg_stc"), key="cfg_stc",
    )
    remember("cfg_stc", int(new_stc))
    if new_stc > new_sc:
        kit.note(f"The stock cap ({new_stc}%) is above the sector cap ({new_sc}%).",
                 "No book can satisfy both; lower the stock cap.")
    else:
        # The Backtest's holdings count (20 unless the reader changed it): the
        # caps act there. A cap at or below 1/n admits one fully invested book.
        n_hold = int(st.session_state.get("bt_top_n", 20) or 20)
        if new_stc * n_hold <= 100:
            kit.note(
                f"At {new_stc}% per stock and {n_hold} backtest holdings, every stock sits at the cap.",
                "Equal weight and inverse volatility then give the same book. Raise it to "
                f"{100 // n_hold + 2}% or more for the weighting to matter.",
            )

    # Owner, 2026-09-27: off by default; every system; the track record's
    # pinned configuration never uses it (src/engine/liquidity.py).
    st.html('<div class="cfg-rule"></div>')
    new_lf = st.toggle(
        "Liquidity floor",
        value=_risk("cfg_lf"), key="cfg_lf",
        help="A stock whose 20-day average traded value (close × volume) is below "
             "the floor is not bought at a Backtest rebalance.",
    )
    remember("cfg_lf", bool(new_lf))
    new_lfv = st.number_input(
        "Floor (₹ Cr a day)", min_value=1, max_value=500, step=1,
        value=int(_risk("cfg_lfv")), key="cfg_lfv", disabled=not new_lf, width=220,
    )
    remember("cfg_lfv", int(new_lfv))


def _day(value) -> str:
    """The log's ISO date as 01 Oct 2026; a dash when it is missing or unreadable."""
    try:
        return pd.Timestamp(value).strftime("%d %b %Y")
    except (TypeError, ValueError):
        return "—"


def _section_data_health(rank_df: pd.DataFrame) -> None:
    _events = load_events()
    if not _events:
        st.success(
            "No corporate actions flagged. Every session in the price history "
            "moves within a plausible range."
        )
    else:
        _split = sum(1 for e in _events if e.get("kind") == "split/bonus")
        _other = len(_events) - _split
        kit.readings([
            kit.Reading("Corporate actions adjusted", f"{len(_events)}", "sessions, before ranking"),
            kit.Reading("Splits the provider missed", f"{_split}", "a re-fetch fixes these"),
            kit.Reading("Possible demergers", f"{_other}", "no standard ratio", tone="warn"),
        ], "Corporate actions")
        _rows = []
        for e in sorted(_events, key=lambda x: x.get("date", ""), reverse=True):
            _move = e.get("move")
            _rows.append(
                {
                    "Date": _day(e.get("date")),
                    "Symbol": e.get("symbol", "—"),
                    "Move": f"{_move * 100:+.1f}%" if _move is not None else "—",
                    # A null ratio in the log raised TypeError on the format
                    # and took the Configuration page down.
                    "Ratio": (
                        f"{float(e['ratio']):.4f}"
                        if isinstance(e.get("ratio"), (int, float)) else "—"
                    ),
                    "Looks Like": e.get("looks_like", "—"),
                    "Kind": (
                        "Split / bonus"
                        if e.get("kind") == "split/bonus"
                        else "Possible demerger"
                    ),
                }
            )
        if st.button("All sessions, by date", type="tertiary",
                     icon=":material/table_rows:", key="dlg_cfg_sessions"):
            _spike_sessions_dialog(_rows)

    st.html('<div class="cfg-sub">Data files</div>')
    cache_data = [
        ("Price History", PRICES_FILE),
        ("Market Caps", MCAPS_FILE),
        ("TV Classification", TV_CLASSIFICATION_FILE),
    ]
    cache_rows = []
    for label, path in cache_data:
        exists = os.path.exists(path)
        size_mb = os.path.getsize(path) / (1024 * 1024) if exists else 0
        cache_rows.append(
            {
                "Dataset": label,
                "Status": "Present" if exists else "Missing",
                "Size": f"{size_mb:.1f} MB" if exists else "—",
                "Path": path,
            }
        )
    render_saas_table(pd.DataFrame(cache_rows))



def _section(i: int):
    """One section: what it is on the left, its controls on the right."""
    anchor, title, what, reaches = _SECTIONS[i]
    box = st.container(key=f"cfgsec_{anchor.split('-')[1]}")
    left, right = box.columns([1, 2.4], gap="large")
    left.html(
        f'<div class="cfg-intro" id="{anchor}"><span>{i + 1}</span>'
        f'<h2 title="Changes: {html.escape(reaches)}">{html.escape(title)}</h2>'
        f"<p>{html.escape(what)}</p></div>"
    )
    return right


def render_config_view(rank_df: pd.DataFrame) -> None:
    """Everything that decides the ranking and the backtest, on one page."""
    sync_meta = get_sync_metadata()
    synced_stocks = sync_meta.get("total_stocks") or 0
    tot_stk = synced_stocks or len(rank_df)
    engine_stocks = len(rank_df)
    kit.page_head(
        "Configuration",
        "Changes apply as you make them. The model book on Portfolio and Actions keeps "
        "the track record's own settings.",
    )

    # What is in effect, read the same way the rest of the app reads it.
    raw_w = [resolve(key, d, lo=0.0, hi=1.0) for _l, key, d in _WINDOWS]
    tot = sum(raw_w)
    norm = [w / tot for w in raw_w] if tot > 0 else list(DEFAULT_LOOKBACK_WEIGHTS)
    is_default = all(abs(a - b) < 1e-6 for a, b in zip(norm, DEFAULT_LOOKBACK_WEIGHTS))
    indices = st.session_state.get("cfg_indices", ["NIFTY TOTAL MARKET"])
    system_note = (f" · {SYSTEM_NAMES.get(st.session_state.get('cfg_system'), '')}"
                   if st.session_state.get("cfg_system", SYSTEM_750) != SYSTEM_750 else "")
    # The weights are shown once, by the bar in Momentum score; the count of
    # corporate actions once, in Data health.
    kit.kv_line([
        ("Universe", (" + ".join(i.title() for i in indices) or "—") + system_note),
        ("Score weights", "Default" if is_default else "Yours"),
        ("Backtest max per stock · per sector", f"{_risk('cfg_stc')}% · {_risk('cfg_sc')}%"),
        ("Backtest liquidity floor", f"₹{_risk('cfg_lfv')} Cr" if _risk("cfg_lf") else "Off"),
    ], lead="In effect")

    st.html(
        '<nav class="cfg-index" aria-label="Sections">'
        + "".join(f'<a href="#{a}">{i + 1} · {html.escape(t)}</a>'
                  for i, (a, t, _w, _r) in enumerate(_SECTIONS))
        + "</nav>"
    )

    with _section(0):
        _section_data_sync(sync_meta, tot_stk, engine_stocks)
    with _section(1):
        _section_momentum_signal()
    with _section(2):
        _section_portfolio_risk()
    with _section(3):
        _section_data_health(rank_df)

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
