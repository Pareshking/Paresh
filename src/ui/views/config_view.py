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

from src.core.config import (
    DEFAULT_LOOKBACK_WEIGHTS,
    DEFAULT_SECTOR_CAP,
    DEFAULT_STOCK_CAP,
    DEFAULT_TARGET_VOL,
    INDICES_LOCAL,
    INDICES_URLS,
    MCAPS_FILE,
    PRICES_FILE,
    STORAGE_MODE,
    TV_CLASSIFICATION_FILE,
)
from src.engine.corporate_actions import load_events
from src.loaders.indices_loader import get_sync_metadata, sync_official_nse_indices
from src.ui.components import gap_count, render_data_quality_footer
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


# The page's four sections, in order: anchor id, number, title, what it is
# for, and which pages a change reaches. One list feeds the index and the
# section headers, so the two cannot disagree.
_SECTIONS = [
    ("cfg-universe", "Universe",
     "Which stocks are ranked. The app ranks the constituents of the indices chosen "
     "here, from the official NSE lists.", "every page"),
    ("cfg-score", "Momentum score",
     "How much each lookback window counts in the composite score that sets every rank.",
     "ranks on every page, and the backtest's starting weights"),
    ("cfg-limits", "Portfolio limits",
     "The most the model book may hold in one sector and one stock, and whether it "
     "holds cash to damp volatility.", "Portfolio and Backtest"),
    ("cfg-health", "Data health",
     "What the app corrected in the price history before ranking, and whether its data "
     "files are in place.", "nothing; this section only reports"),
]


def _section_data_sync(sync_meta: dict, tot_stk: int, engine_stocks: int) -> None:
    last_sync = sync_meta.get("last_synced") or "Never synced"
    sync_ok = sync_meta.get("last_attempt_ok")
    last_attempt = sync_meta.get("last_attempt")
    attempt_fetched = sync_meta.get("last_attempt_fetched")
    attempt_errors = sync_meta.get("last_attempt_errors") or {}

    st.html(
        '<div class="cfg-stats">'
        f'<div><span>Last synced</span><b>{html.escape(str(last_sync))}</b></div>'
        f'<div><span>In the index files</span><b>{tot_stk} stocks</b></div>'
        f'<div><span>Ranked now</span><b>{engine_stocks} stocks</b></div></div>'
    )
    if sync_ok is False:
        kit.note(
            f"The last sync ({last_attempt or 'time unknown'}) did not complete.",
            f"It fetched {attempt_fetched if attempt_fetched is not None else '?'} index "
            f"file(s) and {len(attempt_errors)} failed; the figures above are from the "
            "last complete sync.",
        )

    # Which indices feed the ranking. Chosen first, synced second.
    available_indices = list(INDICES_URLS.keys())
    curr_indices = st.session_state.get("cfg_indices", ["NIFTY TOTAL MARKET"])
    new_indices = st.multiselect(
        "Indices to rank",
        available_indices,
        default=curr_indices,
        key="cfg_indices_multiselect",
    )
    if new_indices != curr_indices:
        st.session_state["cfg_indices"] = new_indices
        st.session_state.pop("data_loaded_key", None)
        st.rerun()

    with st.container(horizontal=True, vertical_alignment="center", key="cfg_sync_row"):
        if st.button("Sync from niftyindices.com", type="primary", key="btn_sync_indices"):
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
                st.rerun()

        st.html('<span class="pg-cap">Sync fetches the latest official constituent lists. '
                "One sync at a time, app-wide.</span>")

    with st.expander(f"Index files on disk ({len(INDICES_LOCAL)})", expanded=False):
        for idx_name, path in INDICES_LOCAL.items():
            if os.path.exists(path):
                size = os.path.getsize(path)
                mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime(
                    "%d %b %Y, %H:%M"
                )
                with open(path, "r", encoding="utf-8") as f:
                    lines = sum(1 for _ in f) - 1
                st.caption(
                    f"**{idx_name}**: `{lines}` constituents ({size/1024:.1f} KB) · {mtime}"
                )
            else:
                st.caption(f"**{idx_name}**: File missing at `{path}`")



# The five lookback windows, their canonical keys, and the documented default
# for each. One list so the pill, the sliders and the reset button cannot drift.
_WINDOWS: list[tuple[str, str, float]] = [
    ("1M", "cfg_w1", DEFAULT_LOOKBACK_WEIGHTS[0]),
    ("3M", "cfg_w2", DEFAULT_LOOKBACK_WEIGHTS[1]),
    ("6M", "cfg_w3", DEFAULT_LOOKBACK_WEIGHTS[2]),
    ("9M", "cfg_w4", DEFAULT_LOOKBACK_WEIGHTS[3]),
    ("12M", "cfg_w5", DEFAULT_LOOKBACK_WEIGHTS[4]),
]


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

    _defaults_txt = " / ".join(f"{w * 100:.0f}" for w in DEFAULT_LOOKBACK_WEIGHTS)
    if st.button(f"Reset to defaults ({_defaults_txt})", key="cfg_w_reset"):
        # Write the mirror and DROP the widget's own state, so the sliders read
        # the restored value on the next run. Writing the widget key instead is
        # legal only above the widget, and was the shape that crashed the tab.
        for _label, key, default in _WINDOWS:
            remember(key, float(default))
            forget(key)
        st.rerun()

    wc = st.columns(5)
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
            value=float(current[key]), step=0.05, key=key,
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

    kit.caption(
        "Weights are normalised to 100%. No window skips the most recent month: "
        "each runs from its calendar start to the latest close."
    )
    st.html(
        '<table class="cfg-guide"><thead><tr><th>Window</th><th>Period</th>'
        '<th class="n">≈ sessions</th><th>What it captures</th></tr></thead><tbody>'
        "<tr><td>1M</td><td>1 calendar month</td><td class='n'>21</td><td>Recent acceleration; noisy on its own</td></tr>"
        "<tr><td>3M</td><td>3 months</td><td class='n'>63</td><td>The main swing of a trend</td></tr>"
        "<tr><td>6M</td><td>6 months</td><td class='n'>126</td><td>An established trend</td></tr>"
        "<tr><td>9M</td><td>9 months</td><td class='n'>189</td><td>Persistence</td></tr>"
        "<tr><td>12M</td><td>12 months</td><td class='n'>252</td><td>The long base; guards against spikes</td></tr>"
        "</tbody></table>"
    )
    kit.caption(
        "More weight on 3M and 6M favours fast breakouts; more on 9M and 12M favours slow, "
        "persistent trends. Session counts are approximate: windows are calendar-anchored."
    )


# Defaults for the on-demand Portfolio Risk widgets. Same reason as the weight
# sliders: the left-nav renders one section per run, Streamlit evicts widget
# state for anything it did not render last time, and a slider with a key but no
# value then falls back to its `min_value`. Here that is silently DESTRUCTIVE
# rather than merely visible -- a 30% sector cap would come back as 15% and a 5%
# stock cap as 2%, both of them plausible numbers that now genuinely bind the
# portfolio and the backtest.
# key -> (default, minimum, maximum). Ranges live here so the resolver rejects
# an out-of-range stored value the same way the widget would.
_RISK_SETTINGS: dict[str, tuple] = {
    "cfg_sc": (round(DEFAULT_SECTOR_CAP * 100), 15, 50),
    "cfg_stc": (round(DEFAULT_STOCK_CAP * 100), 2, 15),
    "cfg_vt": (False, None, None),
    "cfg_vtv": (round(DEFAULT_TARGET_VOL * 100), 10, 40),
}


def _risk(key):
    """The live value of one risk setting, resolved before it is rendered."""
    default, lo, hi = _RISK_SETTINGS[key]
    return resolve(key, default, lo=lo, hi=hi)


def _section_portfolio_risk() -> None:
    # Same exposure as the weight sliders, and worse in consequence: an evicted
    # weight comes back as an obvious 0.00, but an evicted cap comes back as a
    # PLAUSIBLE number -- a 30% sector cap as 15%, a 5% stock cap as 2% -- and
    # both genuinely bind the portfolio and the backtest. Every widget below is
    # handed an explicit resolved value and mirrored afterwards.
    lc, rc = st.columns(2, gap="large")
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
        # The Portfolio page's holdings count (20 unless the reader changed it).
        # A cap at or below 1/n admits exactly one fully invested book.
        n_hold = int(st.session_state.get("port_top_n", 20) or 20)
        if new_stc * n_hold <= 100:
            kit.note(
                f"At {new_stc}% per stock and {n_hold} holdings, every stock sits at the cap.",
                "Equal weight and inverse volatility then give the same book. Raise it to "
                f"{100 // n_hold + 2}% or more for the weighting to matter.",
            )

    st.html('<div class="cfg-rule"></div>')
    new_vt = st.toggle(
        "Volatility targeting",
        value=_risk("cfg_vt"), key="cfg_vt",
        help="When on, the Portfolio page holds cash to keep the book near a target yearly volatility.",
    )
    remember("cfg_vt", bool(new_vt))
    kit.caption("On: the Portfolio page holds cash to keep the book near the target below. "
                "Off: fully invested.")
    new_vtv = st.slider(
        "Target yearly volatility (%)", min_value=10, max_value=40, step=5,
        value=_risk("cfg_vtv"), key="cfg_vtv", disabled=not new_vt,
    )
    remember("cfg_vtv", int(new_vtv))


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
        st.html(
            '<div class="cfg-stats">'
            f'<div><span>Price jumps neutralised</span><b>{len(_events)}</b><em>sessions, before ranking</em></div>'
            f'<div><span>Splits the provider missed</span><b>{_split}</b><em>a re-fetch fixes these</em></div>'
            f'<div class="warn"><span>Possible demergers</span><b>{_other}</b><em>no standard ratio</em></div></div>'
        )
        kit.caption(
            "Each is neutralised in memory before ranking and in the backtest, by rescaling "
            "the history before it. Stored prices are never edited, so a later correction "
            "from the provider is not applied twice."
        )
        _rows = []
        for e in sorted(_events, key=lambda x: x.get("date", ""), reverse=True):
            _move = e.get("move")
            _rows.append(
                {
                    "Date": e.get("date", "—"),
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
        with st.expander(f"All {len(_events)} sessions, by date", expanded=False):
            render_saas_table(pd.DataFrame(_rows))
        kit.caption(
            "A split or bonus should have been adjusted away by the data provider and was not; "
            "re-fetching fixes it. A possible demerger matches no standard ratio; providers "
            "generally don't adjust for these because the parent's price genuinely falls while "
            "shareholders receive stock in the new entity."
        )

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
        f'<div class="cfg-intro" id="{anchor}"><span>{i + 1}</span><h2>{html.escape(title)}</h2>'
        f"<p>{html.escape(what)}</p><small>Changes: {html.escape(reaches)}</small></div>"
    )
    return right


def render_config_view(rank_df: pd.DataFrame) -> None:
    """Everything that decides the ranking and the book, on one page."""
    sync_meta = get_sync_metadata()
    synced_stocks = sync_meta.get("total_stocks") or 0
    tot_stk = synced_stocks or len(rank_df)
    engine_stocks = len(rank_df)
    mode_label = (
        "Streamlit Cloud" if STORAGE_MODE == "streamlit-cloud" else "Local Production"
    )

    st.html(
        '<div class="cfg-top"><div class="scr-head"><h1>Configuration</h1>'
        "<p>Everything that decides the ranking and the book, on one page. "
        "Changes apply as you make them.</p></div>"
        '<div class="cfg-pills">'
        f'<span class="cfg-pill ok"><i></i>Ranking {engine_stocks} stocks</span>'
        f'<span class="cfg-pill">{html.escape(mode_label)}</span></div></div>'
    )

    # What is in effect, read the same way the rest of the app reads it.
    raw_w = [resolve(key, d, lo=0.0, hi=1.0) for _l, key, d in _WINDOWS]
    tot = sum(raw_w)
    norm = [w / tot for w in raw_w] if tot > 0 else list(DEFAULT_LOOKBACK_WEIGHTS)
    is_default = all(abs(a - b) < 1e-6 for a, b in zip(norm, DEFAULT_LOOKBACK_WEIGHTS))
    indices = st.session_state.get("cfg_indices", ["NIFTY TOTAL MARKET"])
    vt_on = bool(_risk("cfg_vt"))
    n_events = len(load_events() or [])
    kit.readings([
        kit.Reading("Universe", " + ".join(i.title() for i in indices) or "—",
                    f"{engine_stocks} stocks ranked"),
        kit.Reading("Score weights", "·".join(f"{w * 100:.0f}" for w in norm),
                    "1M·3M·6M·9M·12M" + (", the default" if is_default else ", your own")),
        kit.Reading("Portfolio limits", f"{_risk('cfg_stc')}% · {_risk('cfg_sc')}%",
                    "per stock · per sector"),
        kit.Reading("Volatility target", f"{_risk('cfg_vtv')}%" if vt_on else "Off",
                    "holds cash to stay near it" if vt_on else "fully invested"),
        kit.Reading("Data health", f"{n_events} fixed" if n_events else "Clean",
                    "price jumps neutralised" if n_events else "no corporate actions flagged"),
    ], "Settings in effect")

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
