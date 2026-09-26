import hashlib
import re
import time
from html import escape as _esc
from urllib.parse import quote as _urlq

import numpy as np
import pandas as pd
import streamlit as st

from src.engine.momentum import ATR_DERIVED_COLUMNS, CARRIED_MARK


TICK_TRUE = frozenset({"✅", "TRUE", "1", "YES", "Y"})


def is_tick_true(value) -> bool:
    """Whether a qualification cell means "yes".

    "Above 50 EMA" and "Near 52W High" carry tick marks, not booleans, so every
    consumer has to decode them. Defined once here -- the leaf module both the
    components layer and the row renderers can import -- because the copies
    drifted apart before: one of them omitted .strip(), and the vectorised
    copies used .map(), which preserves the source dtype on an empty frame and
    produced a str-dtype mask that crashed the Qualified tab.
    """
    return value is True or (
        value is not None and str(value).strip().upper() in TICK_TRUE
    )


def clean_html(html_str: str) -> str:
    """Strips leading whitespace from every line to ensure Markdown NEVER interprets HTML as code blocks."""
    return re.sub(r"^[ \t]+", "", html_str, flags=re.MULTILINE).strip()


FORMAT_MAP: dict[str, str] = {
    # Currency & Prices (Integer rounded with commas)
    "CMP": "{:,.0f}",
    "Stop Loss": "{:,.0f}",
    "Chand Exit": "{:,.0f}",
    "52W High": "{:,.0f}",
    "52W Low": "{:,.0f}",
    "Target Value (₹)": "{:,.0f}",
    "Actual Value (₹)": "{:,.0f}",
    "Capital Sized": "{:,.0f}",
    "Allocated Capital": "{:,.0f}",
    "Market Cap (Cr)": "{:,.0f}",
    "Total MCap (Cr)": "{:,.0f}",
    "Total_MCap_Cr": "{:,.0f}",
    # Quantities & Counts (Integer)
    "Shares to Buy": "{:,.0f}",
    "Stocks": "{:,.0f}",
    "Count": "{:,.0f}",
    "Holdings": "{:,.0f}",
    "Horizons Scored": "{:.0f}",
    "Trades": "{:,.0f}",
    "Total Trades": "{:,.0f}",
    "Rank": "{:.0f}",
    "Rank (-1M)": "{:.0f}",
    "Rank (-3M)": "{:.0f}",
    "Rank Δ 1M": "{:+.0f}",
    "Rank Δ 3M": "{:+.0f}",
    "Sharpe Rank": "{:.0f}",
    "Composite Rank": "{:.0f}",
    # Decimal Ratios (1 decimal place with % sign)
    "3M Return": "{:+.1%}",
    "6M Return": "{:+.1%}",
    "1M Return": "{:+.1%}",
    "6M Net Return": "{:+.1%}",
    "6M Alpha": "{:+.1%}",
    "Return %": "{:+.1%}",
    "Strategy Net": "{:+.1%}",
    "Benchmark": "{:+.1%}",
    "Outperform": "{:+.1%}",
    "CAGR": "{:+.1%}",
    "Max Drawdown": "{:.1%}",
    "Win Rate": "{:.0%}",
    # Pre-calculated Percentages (already multiplied by 100)
    "% High": "{:.1f}%",
    "% 50 EMA": "{:+.1f}%",
    "% 20 EMA": "{:.1f}%",
    "% 52W High": "{:.1f}%",
    "ATR %": "{:.1f}%",
    "Persistence": "{:.1f}%",
    "Max DD 3M": "{:.1f}%",
    "FFill %": "{:.1f}%",
    "Weight %": "{:.2f}%",
    "Del %": "{:.1f}%",
    "Del% 20D Avg": "{:.1f}%",
    "Del% Prev20D": "{:.1f}%",
    "Turnover %": "{:.1f}%",
    "Cost Drag %": "{:.2f}%",
    "Day Chg %": "{:+.1f}%",
    "Price_Chg_%": "{:+.1f}%",
    # Ratios & Alpha Scores (2 decimal places)
    "3M Sharpe": "{:.2f}",
    "6M Sharpe": "{:.2f}",
    "Del_Surge_Daily": "{:.2f}×",
    "Del_Surge_20D": "{:.2f}×",
    "Vol_Surge_Daily": "{:.2f}×",
    "Vol_Surge_20D": "{:.2f}×",
    "RS_Ratio": "{:.1f}",
    "RS_Momentum": "{:.1f}",
    "Sharpe": "{:.2f}",
    "Sortino": "{:.2f}",
    "Calmar": "{:.2f}",
    # A fraction, like every other alpha in this codebase: stats["alpha"] is
    # total_s_net - total_b. It sat under "Ratios" as a bare {:+.2f}, left over
    # from the residual-alpha SCORE columns that were removed -- so a 26.3%
    # alpha would have printed as "+0.26" in this renderer while the other one
    # printed "+26.3%".
    "Alpha": "{:+.1%}",
    "Beta": "{:.2f}",
    "Score": "{:.2f}",
}

def inject_custom_css() -> None:
    """Injects comprehensive Pure Paper White styling with 5-Font institutional typography."""
    st.markdown(
        clean_html("""
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500..800&family=Geist:wght@400..700&family=Geist+Mono:wght@400..700&display=swap" rel="stylesheet">

        <style>
        /* ── Design tokens: "Clear Ledger", light only ──────────────────
           The owner asked for a light app, so there is no dark override: a
           reader whose OS is in dark mode still gets the light palette the
           design was checked against (4.5:1 text contrast, 12px minimum). */
        :root {
            --c-bg: #F6F7F9;
            --c-bg-subtle: #F4F5F8;
            --c-surface: #FFFFFF;
            --c-border: #E3E6EB;
            --c-border-strong: #D0D5DD;
            --c-text-primary: #0E1726;
            --c-text-secondary: #3C4657;
            --c-text-muted: #5E6878;
            --c-accent: #4F46E5;
            --c-accent-text: #4338CA;
            --c-bull: #067647;
            --c-bull-tint: #E8F5EE;
            --c-bear: #B42318;
            --c-bear-tint: #FDEDEB;
            --c-caution: #B54708;
            --font-ui: 'Geist', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            --font-display: 'Bricolage Grotesque', 'Geist', sans-serif;
            --font-mono: 'Geist Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
        }

        /* ── Base Reset & Typography Hierarchy ── */
        html, body, [class*="css"] {
            font-family: 'Geist', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
            color: #0E1726 !important;
            background-color: #F6F7F9 !important;
            -webkit-font-smoothing: antialiased;
        }

        /* ── Typography Classes ── */
        .font-display, h1, h2, h3, h4, [data-testid="stMetricValue"] {
            font-family: 'Bricolage Grotesque', -apple-system, sans-serif !important;
            letter-spacing: -0.02em !important;
        }
        .font-mono, [data-testid="stMetricDelta"] {
            font-family: 'Geist Mono', monospace !important;
            font-variant-numeric: tabular-nums !important;
        }
        .font-code, code, pre {
            font-family: 'Geist Mono', monospace !important;
        }
.font-sans {
            font-family: 'Geist', sans-serif !important;
        }

        /* ── Completely Hide Clunky Grey Native Scrollbars Everywhere (Across All 11 Tabs) ── */
        *, *::before, *::after {
            scrollbar-width: none !important;
            -ms-overflow-style: none !important;
        }
        /* Restore visible thin scrollbar for horizontal overflow containers (accessibility) */
        div[role="alert"][aria-label="Market signals"],
        .ticker-ribbon {
            scrollbar-width: thin !important;
            scrollbar-color: #D0D5DD transparent !important;
            -ms-overflow-style: auto !important;
        }
        div[role="alert"][aria-label="Market signals"]::-webkit-scrollbar,
        .ticker-ribbon::-webkit-scrollbar {
            height: 4px !important;
            display: block !important;
        }
        div[role="alert"][aria-label="Market signals"]::-webkit-scrollbar-thumb,
        .ticker-ribbon::-webkit-scrollbar-thumb {
            background-color: #D0D5DD !important;
            border-radius: 99px !important;
        }
        *::-webkit-scrollbar, 
        ::-webkit-scrollbar,
        [data-testid="stDataFrame"] *::-webkit-scrollbar,
        [data-testid="stTable"] *::-webkit-scrollbar,
        [data-testid="stHorizontalBlock"] *::-webkit-scrollbar,
        .stDataFrame *::-webkit-scrollbar,
        div[data-testid="stTable"] *::-webkit-scrollbar,
        div[role="grid"] *::-webkit-scrollbar,
        div[class*="glideDataGrid"] *::-webkit-scrollbar,
        div[class*="dvn-scroller"] *::-webkit-scrollbar,
        .element-container *::-webkit-scrollbar,
        iframe *::-webkit-scrollbar {
            width: 0px !important;
            height: 0px !important;
            display: none !important;
            background: transparent !important;
        }

        .stApp {
            background-color: #F6F7F9 !important;
        }

        /* ── Completely Eliminate Top Space & Streamlit Header ── */
        header, [data-testid="stHeader"], .stApp > header {
            display: none !important;
            height: 0px !important;
            min-height: 0px !important;
            max-height: 0px !important;
            padding: 0px !important;
            margin: 0px !important;
            visibility: hidden !important;
            overflow: hidden !important;
        }

        #MainMenu, footer {
            display: none !important;
            visibility: hidden !important;
        }

        /* ── Remove Left Sidebar (100% Full Viewport Width) ── */
        [data-testid="stSidebar"], [data-testid="stSidebarNav"], section[data-testid="stSidebar"] {
            display: none !important;
        }

        /* ── Flush 0px Top Padding on Main Container ── */
        .main, .stMain, [data-testid="stMain"] {
            padding-top: 0px !important;
            margin-top: 0px !important;
        }

        .main .block-container, [data-testid="stMainBlockContainer"], [data-testid="block-container"] {
            /* 1360px keeps a 13-column table readable without the lines
               getting so long on a wide monitor that the eye loses the row. */
            max-width: 1360px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            padding-top: 0.15rem !important;
            padding-bottom: 2rem !important;
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
            margin-top: 0px !important;
        }

        /* ── Phones get their screen back ──────────────────────────────────
           1.5rem a side is 48px, and on a 412px phone that is 12% of the
           display spent on empty margin -- measured, not estimated. The
           screener table is the widest thing in the app and scrolls
           horizontally inside its frame, so every pixel returned here is one
           more pixel of columns visible before the reader has to scroll.
           8px still reads as a gutter rather than content touching the bezel.

           This has been the layout since the first commit; nothing recent
           narrowed it. Verified by rendering both revisions at 412px, which
           came out identical at 364px usable. */
        @media (max-width: 640px) {
            .main .block-container,
            [data-testid="stMainBlockContainer"],
            [data-testid="block-container"] {
                padding-left: 0.5rem !important;
                padding-right: 0.5rem !important;
            }

            /* Tab bar: scroll horizontally instead of squishing 10 tabs into 375px. */
            .stTabs [data-baseweb="tab-list"] {
                padding: 3px 3px !important;
                overflow-x: auto !important;
                overflow-y: hidden !important;
                flex-wrap: nowrap !important;
                scrollbar-width: none !important;
                -ms-overflow-style: none !important;
            }
            .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar {
                display: none !important;
            }
            /* Each tab holds its natural width instead of flex-shrinking to zero. */
            .stTabs [data-baseweb="tab"] {
                flex: 0 0 auto !important;
                font-size: 11px !important;
                padding: 0 6px !important;
                height: 32px !important;
            }

            /* Stack all st.columns() vertically on mobile.
               260px min-width means no two columns fit in a 375px viewport,
               so every column wraps to its own full-width row.
               Content is never cramped; users scroll vertically instead. */
            [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
            }
            [data-testid="column"] {
                min-width: 260px !important;
            }
        }

        /* ── Sleek Top Tab Navigation Menu (Equally Spaced Menu Bar) ── */
        .stTabs [data-baseweb="tab-list"] {
            display: flex !important;
            width: 100% !important;
            gap: 4px !important;
            background-color: #F4F5F8 !important;
            padding: 4px 5px !important;
            border-radius: 9px !important;
            border: 1px solid #E3E6EB !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
            margin-bottom: 0.85rem !important;
        }

        .stTabs [data-baseweb="tab-border"],
        .stTabs [data-baseweb="tab-highlight"] {
            display: none !important;
        }

        .stTabs [data-baseweb="tab"] {
            flex: 1 1 0px !important;
            min-width: 0 !important;
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            text-align: center !important;
            height: 36px !important;
            border-radius: 7px !important;
            padding: 0 4px !important;
            background-color: transparent !important;
            border: 1px solid transparent !important;
            font-family: 'Geist', sans-serif !important;
            font-size: 12.5px !important;
            font-weight: 600 !important;
            color: #5E6878 !important;
            white-space: nowrap !important;
            transition: all 0.15s ease !important;
            cursor: pointer !important;
        }

        .stTabs [data-baseweb="tab"]:hover {
            background-color: #ffffff !important;
            color: #0E1726 !important;
            border-color: #E3E6EB !important;
        }

        .stTabs [aria-selected="true"] {
            background-color: #ffffff !important;
            color: #4f46e5 !important;
            font-weight: 700 !important;
            border-color: #c7d2fe !important;
            box-shadow: 0 1px 3px rgba(79, 70, 229, 0.08) !important;
        }

        /* ── Compact Hamburger Navigation ───────────────────────────────
           The page router remains st.navigation(position="hidden"), while the
           custom header exposes a single st.popover trigger. The old eleven-item pill
           row consumed ~180px on a phone before the screener even started.
           Keep the trigger intentionally small; the full navigation only
           exists in the floating popover when the reader asks for it. */
        .st-key-app_header_shell {
            position: relative !important;
            margin: 6px 0 4px 0 !important;
            min-height: 60px !important;
            padding: 8px 60px 8px 14px !important;
            border: 1px solid #E3E6EB !important;
            border-radius: 14px !important;
            background: #FFFFFF !important;
            box-shadow: 0 1px 2px rgba(14, 23, 38, 0.04) !important;
            overflow: visible !important;
            gap: 18px !important;
        }

        /* Brand: mark + name. */
        .hdr-title {
            font-family: var(--font-display); font-size: 17px; font-weight: 700;
            letter-spacing: -0.2px; color: #0E1726;
        }

        /* Brand: "Paresh Patel", a link home to the Screener. */
        .st-key-app_brand [data-testid="stPageLink"] a {
            padding: 4px 6px !important; background: transparent !important;
            text-decoration: none !important; border-radius: 8px !important;
        }
        .st-key-app_brand [data-testid="stPageLink"] a p,
        .st-key-app_brand [data-testid="stPageLink"] a span {
            font-family: var(--font-display) !important; font-size: 19px !important;
            font-weight: 700 !important; letter-spacing: -0.3px !important;
            color: #0E1726 !important; white-space: nowrap !important;
        }
        .st-key-app_brand [data-testid="stPageLink"] a:hover { background: #F4F5F8 !important; }

        /* Desktop link row. Underlined, not boxed: it is a menu, not buttons. */
        .st-key-app_toplinks { gap: 2px !important; flex-wrap: nowrap !important; overflow: hidden !important; }
        .st-key-app_toplinks [data-testid="stPageLink"] a {
            padding: 8px 10px !important;
            border-radius: 8px !important;
            border-bottom: 2px solid transparent !important;
            color: #3C4657 !important;
            text-decoration: none !important;
            white-space: nowrap !important;
            background: transparent !important;
        }
        .st-key-app_toplinks [data-testid="stPageLink"] a p,
        .st-key-app_toplinks [data-testid="stPageLink"] a span {
            font-family: var(--font-ui) !important;
            font-size: 14px !important;
            font-weight: 500 !important;
            color: inherit !important;
        }
        .st-key-app_toplinks [data-testid="stPageLink"] a:hover {
            background: #F4F5F8 !important;
            color: #0E1726 !important;
        }
        .st-key-app_toplinks [class*="st-key-navon_"] [data-testid="stPageLink"] a {
            color: #0E1726 !important;
            border-bottom-color: #4F46E5 !important;
            border-radius: 8px 8px 0 0 !important;
        }
        .st-key-app_toplinks [class*="st-key-navon_"] [data-testid="stPageLink"] a p {
            font-weight: 650 !important;
        }

        /* Data status pill. Green when every source is current, amber naming
           the stale one otherwise. */
        .hdr-pill {
            display: inline-flex; align-items: center; gap: 8px; white-space: nowrap;
            height: 32px; padding: 0 12px; border-radius: 999px;
            background: #E8F5EE; color: #054F31; font-size: 13px; font-weight: 600;
        }
        .hdr-pill .hdr-dot { width: 8px; height: 8px; border-radius: 50%; background: #067647; }
        .hdr-pill-warn { background: #FEF6EA; color: #7A2E0E; }
        .hdr-pill-warn .hdr-dot { background: #B54708; }

        /* Market line under the bar. Keeps "NIFTY" and "Universe:" visible:
           the production QA probe reads them as its readiness signal. */
        .mkt-line {
            display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px;
            padding: 4px 4px 10px; font-size: 13px; color: #3C4657;
        }
        .mkt-line strong { color: #0E1726; font-weight: 600; font-variant-numeric: tabular-nums; }
        .mkt-line .mkt-sep { color: #A5ACB8; }
        .mkt-line .mkt-regime { font-weight: 700; }
        .mkt-line .mkt-up, .mkt-line strong.mkt-up { color: #067647; }
        .mkt-line .mkt-down, .mkt-line strong.mkt-down { color: #B42318; }

        @media (max-width: 900px) {
            .st-key-app_toplinks { display: none !important; }
        }
        @media (max-width: 640px) {
            .st-key-app_header_shell { min-height: 52px !important; padding: 6px 56px 6px 10px !important; gap: 10px !important; flex-wrap: nowrap !important; justify-content: space-between !important; }
            .hdr-pill-lead { display: none; }
            .mkt-line .mkt-sep { display: none; }
            .hdr-title { font-size: 16px; }
            .hdr-pill { height: 28px; padding: 0 10px; font-size: 12px; }
            .mkt-line { font-size: 12px; padding: 2px 2px 8px; }
        }

        /* Keep the Streamlit popover out of normal flow so mobile flex
           stacking cannot move it underneath the header. */
        .st-key-app_header_shell [class*="st-key-app_nav_menu_"] {
            position: absolute !important;
            top: 50% !important;
            transform: translateY(-50%) !important;
            right: 7px !important;
            z-index: 20 !important;
            width: 40px !important;
            min-width: 40px !important;
            margin: 0 !important;
        }

        [class*="st-key-app_nav_menu_"] button {
            min-height: 40px !important;
            width: 40px !important;
            padding: 0 !important;
            border: 1px solid #E3E6EB !important;
            border-radius: 8px !important;
            background: #F4F5F8 !important;
            color: #3C4657 !important;
            font-size: 18px !important;
            line-height: 1 !important;
        }

        [class*="st-key-app_nav_menu_"] button:hover {
            background: #ffffff !important;
            border-color: #c7d2fe !important;
            color: #4f46e5 !important;
        }

        /* Page links inside the floating navigation menu. */
        [data-testid="stPopover"] [data-testid="stPageLink"] a,
        [data-testid="stPopoverBody"] [data-testid="stPageLink"] a {
            min-height: 38px !important;
            padding: 7px 10px !important;
            border-radius: 7px !important;
            color: #3C4657 !important;
            text-decoration: none !important;
            font-family: 'Geist', sans-serif !important;
            font-size: 13px !important;
            font-weight: 600 !important;
        }

        [data-testid="stPopover"] [data-testid="stPageLink"] a:hover,
        [data-testid="stPopoverBody"] [data-testid="stPageLink"] a:hover {
            background: #F4F5F8 !important;
            color: #0E1726 !important;
        }

        [data-testid="stPopover"] [class*="st-key-navon_"] [data-testid="stPageLink"] a,
        [data-testid="stPopoverBody"] [class*="st-key-navon_"] [data-testid="stPageLink"] a {
            background: #eef2ff !important;
            color: #4f46e5 !important;
            border: 1px solid #c7d2fe !important;
            font-weight: 700 !important;
        }

        /* ── Screener page (redesign phase 2) ─────────────────────────── */
        .scr-head h1 {
            margin: 0 !important; padding: 0 !important;
            font-family: var(--font-display) !important; font-size: 34px !important;
            font-weight: 700 !important; letter-spacing: -0.6px !important; color: #0E1726 !important;
        }
        .scr-head p { margin: 4px 0 0; font-size: 14.5px; color: #3C4657; }
        .mkt-strip {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            background: #FFFFFF; border: 1px solid #E3E6EB; border-radius: 16px; overflow: hidden;
        }
        .ms-tile { display: flex; flex-direction: column; gap: 6px; padding: 16px 20px; border-right: 1px solid #EDEFF3; }
        .ms-tile:last-child { border-right: 0; }
        .ms-k { font-size: 12.5px; font-weight: 600; color: #5E6878; }
        .ms-v { font-family: var(--font-display); font-size: 26px; font-weight: 700; line-height: 1.1; color: #0E1726; }
        .ms-s { font-size: 13px; color: #3C4657; line-height: 1.4; }
        .ms-s b { font-weight: 600; }
        .ms-dot { color: #A5ACB8; font-weight: 500; }
        .mkt-strip .up { color: #067647; } .mkt-strip .down { color: #B42318; }
        .ms-bar { display: block; height: 6px; border-radius: 3px; background: #EDEFF3; }
        .ms-bar i { display: block; height: 6px; border-radius: 3px; background: #0E1726; }
        .scr-count { font-size: 13.5px; color: #3C4657; padding: 2px 2px 0; }
        .scr-count strong { color: #0E1726; }
        .t50 { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
        .t50-card { background: #FFFFFF; border: 1px solid #E3E6EB; border-radius: 16px; padding: 18px 20px; display: flex; flex-direction: column; gap: 12px; }
        .t50-h { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
        .t50-h h2 { margin: 0 !important; padding: 0 !important; font-family: var(--font-ui) !important; font-size: 16px !important; font-weight: 650 !important; letter-spacing: 0 !important; }
        .t50-h span { font-size: 13px; font-weight: 600; }
        .t50 .up { color: #067647; } .t50 .down { color: #B42318; }
        .t50-chips { display: flex; flex-wrap: wrap; gap: 8px; }
        .t50-chip {
            display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 10px;
            border-radius: 8px; background: #F4F5F8; color: #0E1726 !important; text-decoration: none !important;
            font-size: 13px; font-weight: 650;
        }
        .t50-chip:hover { background: #EEF0FF; }
        .t50-chip span { font-family: var(--font-mono); font-size: 12px; font-weight: 500; color: #5E6878; }
        .t50-none { font-size: 13px; color: #5E6878; }
        .st-key-scr_toolbar { gap: 10px !important; }
        .st-key-scr_toolbar [data-testid="stPopoverButton"] { height: 40px !important; }
        .sig-label { font-size: 12.5px; font-weight: 600; color: #5E6878; margin-right: 2px; white-space: nowrap; }
        @media (max-width: 640px) {
            .scr-head h1 { font-size: 28px !important; }
            .scr-head p { font-size: 13.5px; }
            /* One sideways-scrolling row of cards, so the list starts sooner. */
            .mkt-strip { display: flex; overflow-x: auto; background: transparent; border: 0; border-radius: 0; gap: 10px; }
            .ms-tile { flex: 0 0 158px; padding: 12px 14px; background: #FFFFFF; border: 1px solid #E3E6EB !important; border-radius: 14px; gap: 3px; }
            .ms-tile .ms-bar { display: none; }
            .st-key-dl_rank_csv { display: none !important; }
            /* Filters & sort opens as a bottom sheet on a phone. The panel is
               portalled outside the page, so it is found by what it holds. */
            [data-testid="stPopoverBody"]:has(.st-key-scr_filters) {
                position: fixed !important; left: 0 !important; right: 0 !important;
                bottom: 0 !important; top: auto !important; transform: none !important;
                width: 100vw !important; max-width: 100vw !important;
                max-height: 82vh !important; overflow-y: auto !important;
                border-radius: 18px 18px 0 0 !important;
                box-shadow: 0 -8px 30px rgba(14, 23, 38, 0.18) !important;
                padding: 18px 16px 24px !important;
            }
            .ms-v { font-size: 20px; }
            .ms-s { font-size: 12px; }
            .st-key-scr_toolbar [data-testid="stSelectbox"] { width: 100% !important; }
        }

        /* ── Page kit (src/ui/page_kit.py): every other page ───────────── */
        .mkt-strip .warn { color: #B54708; }
        .pg-note {
            padding: 12px 16px; border-radius: 12px; background: #FEF6EA; border: 1px solid #F5D7A8;
            font-size: 13.5px; line-height: 1.5; color: #7A2E0E;
        }
        .pg-note b { font-weight: 700; }
        [class*="st-key-pgcard_"] {
            background: #FFFFFF; border: 1px solid #E3E6EB; border-radius: 16px;
            padding: 18px 22px !important; gap: 12px !important;
        }
        .pg-card-h { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
        .pg-card-h h2 {
            margin: 0 !important; padding: 0 !important; font-family: var(--font-ui) !important;
            font-size: 17px !important; font-weight: 650 !important; letter-spacing: 0 !important; color: #0E1726 !important;
        }
        .pg-card-h span { font-size: 12.5px; color: #5E6878; }
        .pg-cap { margin: 0; font-size: 12.5px; line-height: 1.5; color: #5E6878; }
        .pg-bars { display: flex; flex-direction: column; gap: 4px; }
        .pg-bar { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr) 76px; align-items: center; gap: 12px; min-height: 30px; }
        .pg-bar-l { font-size: 13.5px; color: #0E1726; }
        .pg-bar-t { position: relative; height: 10px; border-radius: 5px; background: #EDEFF3; }
        .pg-bar-t i { position: absolute; left: 0; top: 0; height: 10px; border-radius: 5px; background: #4F46E5; }
        .pg-bar-t i.warn { background: #B54708; }
        .pg-bar-v { font-family: var(--font-mono); font-size: 13px; text-align: right; color: #0E1726; }
        [class*="st-key-pg_actions_"] { gap: 10px !important; }
        .hm-wrap { overflow-x: auto; }
        .cfg-top { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
        .cfg-pills { display: flex; gap: 8px; flex-wrap: wrap; }
        .cfg-pill { display: inline-flex; align-items: center; gap: 7px; height: 30px; padding: 0 12px; border-radius: 999px; background: #F1F3F6; color: #3C4657; font-size: 12.5px; font-weight: 600; }
        .cfg-pill.ok { background: #E8F5EE; color: #054F31; }
        .cfg-pill i { width: 7px; height: 7px; border-radius: 50%; background: #067647; }
        .cfg-h { font-size: 15px; font-weight: 650; color: #0E1726; margin: 6px 0 2px; }
        .cfg-s { font-size: 13px; color: #5E6878; margin-bottom: 10px; }
        .st-key-cfg_tabs [role="radiogroup"] { gap: 4px !important; padding: 4px; border-radius: 12px; background: #ECEEF2; display: inline-flex !important; flex-wrap: wrap; }
        .st-key-cfg_tabs [role="radiogroup"] label { margin: 0 !important; padding: 7px 14px !important; border-radius: 9px; cursor: pointer; }
        .st-key-cfg_tabs [role="radiogroup"] label > div:has(input) { display: none !important; }
        .st-key-cfg_tabs [role="radiogroup"] label input { position: absolute; opacity: 0; }
        .st-key-cfg_tabs [role="radiogroup"] label:has(input:checked) { background: #FFFFFF; box-shadow: 0 1px 2px rgba(14,23,38,0.08); }
        .st-key-cfg_tabs [role="radiogroup"] label p { font-size: 14px !important; font-weight: 600 !important; color: #3C4657 !important; }
        .st-key-cfg_tabs [role="radiogroup"] label:has(input:checked) p { color: #0E1726 !important; }
        .bt-sum {
            display: flex; flex-wrap: wrap; align-items: center; gap: 8px 22px; padding: 14px 20px;
            background: #FFFFFF; border: 1px solid #E3E6EB; border-radius: 16px; font-size: 13.5px; color: #3C4657;
        }
        .bt-sum > b { font-size: 13px; font-weight: 600; color: #5E6878; }
        .bt-sum span b { color: #0E1726; font-weight: 650; }
        .gc-legend { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13px; color: #3C4657; }
        .gc-legend span { display: inline-flex; align-items: center; gap: 6px; }
        .gc-legend i { width: 14px; height: 3px; border-radius: 2px; background: #98A1AE; }
        .gc-ls i { background: #4F46E5 !important; }
        .gc-legend b { font-family: var(--font-mono); font-weight: 600; color: #0E1726; }
        .mo-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 10px; }
        .mo { padding: 12px 14px; border-radius: 12px; display: flex; flex-direction: column; gap: 3px; background: #F4F5F8; }
        .mo.up { background: #E8F5EE; } .mo.down { background: #FDEDEB; }
        .mo.live { background: #FFFFFF; border: 1.5px dashed #C7D2FE; }
        .mo-h { display: flex; justify-content: space-between; gap: 8px; font-size: 12.5px; font-weight: 600; color: #3C4657; }
        .mo-h em { font-style: normal; font-size: 11px; font-weight: 600; padding: 1px 6px; border-radius: 6px; background: rgba(255,255,255,0.7); color: #5E6878; }
        .mo-v { font-family: var(--font-mono); font-size: 18px; font-weight: 600; }
        .mo-v.up { color: #067647; } .mo-v.down { color: #B42318; }
        .mo-s { font-size: 12px; color: #3C4657; }
        /* Sectors: industry leaderboard */
        .ib { border: 1px solid #E3E6EB; border-radius: 12px; overflow: hidden; }
        .ib-row {
            display: grid; align-items: center; gap: 12px; padding: 0 16px; min-height: 46px;
            grid-template-columns: 32px minmax(0, 1.6fr) 56px 190px 76px 96px 104px 76px 72px minmax(0, 1.3fr);
            border-bottom: 1px solid #EDEFF3; font-size: 14px; background: #FFFFFF;
        }
        .ib-row:nth-child(odd):not(.ib-head) { background: #FAFBFC; }
        .ib-row:last-child { border-bottom: 0; }
        .ib-head { min-height: 40px; background: #F4F5F8 !important; font-size: 12px; font-weight: 600; color: #5E6878; }
        .ib-n { font-family: var(--font-mono); font-weight: 600; }
        .ib-name { display: flex; flex-direction: column; min-width: 0; }
        .ib-name b { font-weight: 650; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .ib-name small { display: none; font-size: 12px; color: #5E6878; }
        .ib-num { font-family: var(--font-mono); font-size: 13.5px; text-align: right; }
        .ib-3m { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
        .ib-3m b { font-family: var(--font-mono); font-size: 13.5px; font-weight: 500; width: 62px; text-align: right; }
        .ib-bar { position: relative; width: 96px; height: 8px; border-radius: 4px; background: #EDEFF3; }
        .ib-bar i { position: absolute; top: 0; height: 8px; border-radius: 4px; background: #98A1AE; }
        .ib-bar i.up { background: #067647; } .ib-bar i.down { background: #B42318; }
        .ib-bar em { position: absolute; left: 50%; top: -2px; width: 1px; height: 12px; background: #98A1AE; }
        .ib .up { color: #067647; } .ib .down { color: #B42318; }
        .ib-leads { display: flex; gap: 6px; overflow: hidden; }
        .ib-lead {
            font-size: 12px; font-weight: 650; padding: 2px 7px; border-radius: 6px; background: #F4F5F8;
            color: #0E1726 !important; text-decoration: none !important; white-space: nowrap;
        }
        .ib-lead:hover { background: #EEF0FF; }
        @media (max-width: 1100px) { .ib-leads, .ib-head .ib-d:last-child { display: none; } .ib-row { grid-template-columns: 32px minmax(0, 1.6fr) 56px 190px 76px 96px 104px 76px 72px; } }
        @media (max-width: 760px) {
            .ib-row { grid-template-columns: 24px minmax(0, 1fr) 80px; padding: 8px 12px; }
            .ib-d { display: none !important; }
            .ib-name small { display: block; }
            .ib-bar { display: none; }
            .ib-head .ib-3m { justify-content: flex-end; }
        }
        .hm { display: grid; gap: 3px; min-width: 520px; }
        .hm-x, .hm-y { font-family: var(--font-mono); font-size: 11px; color: #3C4657; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .hm-x { writing-mode: vertical-rl; transform: rotate(180deg); height: 76px; text-align: left; justify-self: center; }
        .hm-y { display: flex; align-items: center; }
        .hm-c { height: 28px; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-family: var(--font-mono); font-size: 11px; background: #F4F5F8; color: #0E1726; }
        @media (max-width: 640px) {
            [class*="st-key-pgcard_"] { padding: 14px 14px !important; border-radius: 14px; }
            .pg-bar { grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) 64px; gap: 8px; }
        }

        /* The watchlist bridge has no visible output. */
        .st-key-wl_store { display: none !important; }

        /* ── Stock page (redesign phase 3) ────────────────────────────── */
        .st-key-stock_page_back button {
            border: 0 !important; background: transparent !important; padding: 0 !important;
            min-height: 32px !important; color: #4338CA !important; font-weight: 600 !important;
        }
        .st-key-stock_page_back button:hover { color: #312E81 !important; text-decoration: underline; }
        .sp-card { background: #FFFFFF; border: 1px solid #E3E6EB; border-radius: 18px; padding: 20px 22px; }
        .sp-card h2, .sp-sec h2 {
            margin: 0 !important; padding: 0 !important; font-family: var(--font-ui) !important;
            font-size: 17px !important; font-weight: 650 !important; letter-spacing: 0 !important; color: #0E1726 !important;
        }
        .sp-hero { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 16px; margin-bottom: 14px; }
        .sp-id { display: flex; flex-direction: column; gap: 10px; }
        .sp-chips { display: flex; gap: 8px; flex-wrap: wrap; }
        .sp-sym { font-family: var(--font-mono); font-size: 13px; font-weight: 600; padding: 4px 9px; border-radius: 7px; background: #0E1726; color: #FFFFFF; }
        .sp-tag { font-size: 12.5px; font-weight: 600; padding: 4px 9px; border-radius: 7px; background: #F1F3F6; color: #3C4657; }
        .sp-cls { font-size: 13.5px; color: #5E6878; }
        h1.sp-name {
            margin: 0 !important; padding: 0 !important; font-family: var(--font-display) !important;
            font-size: 38px !important; font-weight: 700 !important; letter-spacing: -0.8px !important;
            line-height: 1.1 !important; color: #0E1726 !important;
        }
        .sp-price-row { display: flex; align-items: flex-end; gap: 22px; flex-wrap: wrap; }
        .sp-price-col { display: flex; flex-direction: column; gap: 4px; }
        .sp-price { font-family: var(--font-mono); font-size: 36px; font-weight: 600; color: #0E1726; line-height: 1.1; }
        .sp-close { font-size: 13px; color: #5E6878; }
        .sp-changes { display: flex; gap: 8px; flex-wrap: wrap; padding-bottom: 4px; }
        .sp-chg { font-family: var(--font-mono); font-size: 13.5px; font-weight: 600; padding: 6px 10px; border-radius: 8px; }
        .sp-chg.up { background: #E8F5EE; color: #067647; } .sp-chg.down { background: #FDEDEB; color: #B42318; }
        .sp-chg.flat { background: #F1F3F6; color: #5E6878; }
        .sp-rank { display: flex; flex-direction: column; gap: 10px; }
        .sp-k { font-size: 12.5px; font-weight: 600; color: #5E6878; }
        .sp-rank-big { display: flex; align-items: baseline; gap: 10px; }
        .sp-rank-big span { font-family: var(--font-display); font-size: 56px; font-weight: 800; line-height: 1; color: #0E1726; }
        .sp-rank-big i { font-style: normal; font-size: 15px; color: #3C4657; }
        .sp-path { display: flex; align-items: center; gap: 8px; }
        .sp-step { display: flex; flex-direction: column; align-items: center; padding: 6px 10px; border-radius: 10px; background: #F4F5F8; min-width: 56px; }
        .sp-step b { font-family: var(--font-mono); font-size: 14px; color: #0E1726; }
        .sp-step i { font-style: normal; font-size: 11.5px; color: #5E6878; }
        .sp-step.now { background: #EEF0FF; } .sp-step.now b { color: #3730A3; }
        .sp-arrow { color: #98A1AE; }
        .sp-facts { display: flex; gap: 16px; flex-wrap: wrap; font-size: 13px; color: #3C4657; }
        .sp-facts b { font-family: var(--font-mono); font-weight: 600; color: #0E1726; }
        .sp-verdict { display: grid; grid-template-columns: 250px repeat(3, minmax(0, 1fr)); border-radius: 16px; margin-bottom: 14px; border: 1px solid; }
        .sp-verdict.pass { background: #F1FAF5; border-color: #BFE3CD; }
        .sp-verdict.part { background: #FEF8EE; border-color: #F5D7A8; }
        .sp-verdict.fail { background: #FDF3F2; border-color: #F3C7C1; }
        .sp-verdict .vh { display: flex; align-items: center; gap: 12px; padding: 16px 20px; }
        .sp-verdict .vm { width: 34px; height: 34px; flex-shrink: 0; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #FFFFFF; font-weight: 800; }
        .sp-verdict.pass .vm { background: #067647; } .sp-verdict.part .vm { background: #B54708; } .sp-verdict.fail .vm { background: #B42318; }
        .sp-verdict .vh b { display: block; font-size: 16px; font-weight: 700; color: #0E1726; }
        .sp-verdict .vh i { display: block; font-style: normal; font-size: 12.5px; color: #3C4657; }
        .sp-verdict .vc { display: flex; flex-direction: column; gap: 3px; padding: 14px 18px; border-left: 1px solid rgba(14, 23, 38, 0.08); }
        .sp-verdict .k { font-size: 12.5px; font-weight: 600; color: #3C4657; }
        .sp-verdict .k em { font-style: normal; font-weight: 500; }
        .sp-verdict .v { font-family: var(--font-mono); font-size: 17px; font-weight: 600; color: #0E1726; }
        .sp-verdict .v.up { color: #067647; } .sp-verdict .v.down { color: #B42318; }
        .sp-verdict .s { font-size: 12.5px; color: #3C4657; }
        .sp-notice { background: #FEF6EA; border: 1px solid #F5D7A8; border-radius: 16px; padding: 16px 20px; margin-bottom: 14px; color: #7A2E0E; }
        .sp-notice p { margin: 6px 0 0; font-size: 14px; line-height: 1.5; color: #3C4657; }
        .sp-sec { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin: 6px 2px 6px; }
        .sp-sec span { font-size: 12.5px; color: #5E6878; }
        .sp-ladder { margin: 14px 0; }
        .sp-range { margin: 16px 0 6px; }
        .sp-range .track { position: relative; height: 10px; border-radius: 5px; background: #EDEFF3; }
        .sp-range .fill { height: 10px; border-radius: 5px; background: linear-gradient(90deg, #C7D2FE, #4F46E5); }
        .sp-range .dot { position: absolute; top: -4px; width: 18px; height: 18px; margin-left: -9px; border-radius: 50%; background: #4F46E5; border: 3px solid #FFFFFF; box-shadow: 0 0 0 1px #4F46E5; box-sizing: border-box; }
        /* Marks ON the bar only. Unscoped, this also took the legend's two
           swatches out of the legend: they floated above the section as a
           stray "|" under the chart, and the legend lost its colours. */
        .sp-range .track i.m-line, .sp-range .track i.m-ema { position: absolute; top: -5px; width: 3px; height: 20px; margin-left: -1.5px; border-radius: 1px; }
        .sp-range i.m-line { background: #B54708; }
        .sp-range i.m-ema { background: #0E1726; }
        .sp-range .ends { display: flex; justify-content: space-between; gap: 10px; margin-top: 8px; font-size: 12.5px; color: #5E6878; flex-wrap: wrap; }
        .sp-range .key { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
        .sp-range .key i { display: inline-block; position: static; width: 3px; height: 12px; margin-left: 6px; border-radius: 1px; }
        .sp-ladder .list { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 10px; margin-top: 14px; }
        .sp-ladder .li { display: flex; flex-direction: column; gap: 3px; padding: 12px 14px; border-radius: 12px; background: #F6F7F9; }
        .sp-ladder .lk { font-size: 12.5px; font-weight: 600; color: #3C4657; }
        .sp-ladder .lv { font-family: var(--font-mono); font-size: 17px; font-weight: 600; color: #0E1726; }
        .sp-ladder .lv.up { color: #067647; } .sp-ladder .lv.down { color: #B42318; } .sp-ladder .lv.warn { color: #B54708; }
        .sp-ladder .ls { font-size: 12.5px; color: #5E6878; }
        .sp-gp { margin-bottom: 14px; }
        .gp-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
        .gp-legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 12.5px; color: #5E6878; }
        .gp-legend span { display: flex; align-items: center; gap: 6px; }
        .gp-legend i { display: inline-block; }
        .gp-legend .k-dd { width: 12px; height: 12px; border-radius: 3px; background: #F2B8B0; }
        .gp-legend .k-ret { width: 12px; height: 12px; border-radius: 3px; background: #067647; }
        .gp-legend .k-nb { width: 14px; height: 4px; border-radius: 2px; background: #98A1AE; }
        .gp-legend .k-med { width: 0; height: 14px; border-left: 2px dashed #5E6878; }
        .gp-row { display: grid; grid-template-columns: 96px minmax(150px, 290px) 1px minmax(0, 1fr) 140px 110px; align-items: center; min-height: 62px; border-bottom: 1px solid #F1F3F6; }
        .gp-row.gp-hdr { min-height: 30px; font-size: 12px; font-weight: 600; color: #5E6878; border-bottom: 1px solid #EDEFF3; }
        .gp-row.gp-hdr .r { text-align: right; padding-right: 10px; }
        .gp-row.gp-hdr span:nth-child(4) { padding-left: 10px; }
        .gp-w b { display: block; font-size: 15px; font-weight: 650; }
        .gp-w i { display: block; font-style: normal; font-size: 11.5px; color: #5E6878; }
        .gp-dd { position: relative; height: 28px; margin-right: 10px; }
        .gp-dd .bar { position: absolute; right: 0; top: 4px; height: 20px; border-radius: 6px 0 0 6px; background: #F2B8B0; }
        .gp-dd .lbl { position: absolute; top: 5px; font-family: var(--font-mono); font-size: 12.5px; font-weight: 600; color: #B42318; white-space: nowrap; }
        .gp-med { position: absolute; top: -2px; height: 32px; z-index: 1; border-left: 2px dashed #5E6878; }
        .gp-axis { height: 44px; background: #0E1726; }
        .gp-ret { position: relative; height: 34px; margin: 0 20px 0 10px; }
        .gp-ret .bar { position: absolute; left: 0; top: 2px; height: 18px; border-radius: 0 6px 6px 0; background: linear-gradient(90deg, #0B8A55, #067647); }
        .gp-ret .bar.neg { background: #F2B8B0; }
        .gp-ret .lbl { position: absolute; top: 2px; font-family: var(--font-mono); font-size: 13.5px; font-weight: 700; color: #054F31; white-space: nowrap; }
        .gp-ret .lbl.neg { color: #B42318; }
        .gp-ret .nb { position: absolute; left: 0; top: 25px; height: 4px; border-radius: 0 2px 2px 0; background: #98A1AE; }
        .gp-ret .nl { position: absolute; top: 20px; font-size: 11px; color: #5E6878; white-space: nowrap; }
        .gp-sh { display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding-right: 10px; }
        .gp-sh .dots { display: flex; gap: 3px; }
        .gp-sh .dots i { width: 9px; height: 9px; border-radius: 50%; background: #E3E6EB; }
        .gp-sh .dots i.on { background: #4F46E5; } .gp-sh .dots i.half { background: rgba(79, 70, 229, 0.35); }
        .gp-sh b { font-family: var(--font-mono); font-size: 15px; font-weight: 600; width: 42px; text-align: right; }
        .gp-top { display: flex; justify-content: flex-end; padding-right: 4px; }
        .gp-top em { font-style: normal; font-size: 11.5px; font-weight: 700; padding: 3px 8px; border-radius: 999px; }
        .gp-top em.good { background: #E8F5EE; color: #054F31; } .gp-top em.poor { background: #F1F3F6; color: #3C4657; }
        .gp-foot { padding-top: 10px; font-size: 12.5px; color: #5E6878; line-height: 1.5; }
        .sp-peers { padding: 0; overflow: hidden; margin-bottom: 14px; }
        .sp-peers .ph { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 16px 20px; }
        .sp-peers .ph span { font-size: 13px; color: #5E6878; }
        .sp-peers .tw { overflow-x: auto; }
        .sp-peers table { width: 100%; border-collapse: collapse; }
        .sp-peers th { background: #F4F5F8; font-size: 12px; font-weight: 600; color: #5E6878; text-align: right; padding: 10px 16px; border-top: 1px solid #E3E6EB; border-bottom: 1px solid #E3E6EB; white-space: nowrap; }
        .sp-peers td { padding: 12px 16px; text-align: right; font-family: var(--font-mono); font-size: 13.5px; border-bottom: 1px solid #EDEFF3; white-space: nowrap; }
        .sp-peers .l { text-align: left; }
        .sp-peers td.s { font-family: var(--font-ui); font-weight: 650; }
        .sp-peers td.s a { color: #0E1726 !important; text-decoration: none !important; }
        .sp-peers td.s a:hover { color: #4338CA !important; }
        .sp-peers td.s em { margin-left: 8px; font-style: normal; font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 6px; background: #EEF0FF; color: #3730A3; }
        .sp-peers tr.hl td { background: #F4F3FF; }
        .sp-peers .up { color: #067647; } .sp-peers .down { color: #B42318; }
        .sp-checks { display: flex; flex-wrap: wrap; gap: 8px; }
        .sp-checks span { font-size: 13.5px; padding: 8px 12px; border-radius: 10px; background: #F6F7F9; color: #3C4657; }
        .sp-checks span.bad { background: #FEF6EA; color: #7A2E0E; font-weight: 600; }
        @media (max-width: 900px) {
            .sp-hero { grid-template-columns: 1fr; }
            .sp-verdict { grid-template-columns: 1fr; }
            .sp-verdict .vc { border-left: 0; border-top: 1px solid rgba(14, 23, 38, 0.08); }
        }
        @media (max-width: 640px) {
            .sp-card { padding: 16px; border-radius: 16px; }
            h1.sp-name { font-size: 28px !important; }
            .sp-price { font-size: 30px; }
            .sp-rank-big span { font-size: 44px; }
            /* Phone: each window stacks -- label and Sharpe, the return bar,
               the drawdown bar -- with the values in a right-hand column. */
            .gp-row {
                grid-template-columns: minmax(0, 1fr) auto;
                grid-template-areas: "w sh" "ret ret" "dd dd";
                row-gap: 6px; padding: 10px 0; min-height: 0;
            }
            .gp-row.gp-hdr, .gp-axis, .gp-top, .gp-med, .gp-ret .nl { display: none !important; }
            .gp-w { grid-area: w; } .gp-w b { display: inline; } .gp-w i { display: inline; margin-left: 6px; }
            .gp-sh { grid-area: sh; padding-right: 0; }
            .gp-sh b { width: auto; font-size: 14px; }
            .gp-ret { grid-area: ret; margin: 0 78px 0 0; height: 26px; }
            .gp-ret .lbl { left: auto !important; right: -76px; width: 72px; text-align: right; font-size: 13px; }
            .gp-ret .nb { top: 21px; }
            .gp-dd { grid-area: dd; margin: 0 78px 0 0; height: 14px; }
            .gp-dd .bar { left: 0; right: auto; top: 2px; height: 10px; border-radius: 0 5px 5px 0; }
            .gp-dd .lbl { right: -76px !important; width: 72px; text-align: right; top: -2px; font-size: 12px; }
            .sp-ladder .list { grid-template-columns: 1fr 1fr; }
        }

        /* ── Command Bar & Quick Filter Pills Styling ── */
        [data-testid="stPills"] {
            display: flex !important;
            gap: 6px !important;
            align-items: center !important;
            flex-wrap: nowrap !important;
            white-space: nowrap !important;
            overflow-x: auto !important;
            scrollbar-width: none !important;
        }

        [data-testid="stPills"] button {
            border-radius: 999px !important;
            font-size: 14px !important;
            font-weight: 500 !important;
            padding: 2px 14px !important;
            height: 40px !important;
            border: 1px solid #E3E6EB !important;
            background-color: #F4F5F8 !important;
            color: #3C4657 !important;
            white-space: nowrap !important;
            flex-shrink: 0 !important;
            transition: all 0.15s ease !important;
        }

        [data-testid="stPills"] button:hover {
            background-color: #ffffff !important;
            color: #4f46e5 !important;
            border-color: #D0D5DD !important;
        }

        [data-testid="stPills"] button[aria-checked="true"] {
            background-color: #EEEDFD !important;
            color: #0E1726 !important;
            border: 1.5px solid #4F46E5 !important;
            box-shadow: none !important;
            font-weight: 600 !important;
        }

        /* ── Segmented Control (Table / Cards Switcher) ── */
        [data-testid="stSegmentedControl"] {
            height: 36px !important;
            border-radius: 8px !important;
            background-color: #F4F5F8 !important;
            border: 1px solid #E3E6EB !important;
            padding: 2px !important;
        }

        [data-testid="stSegmentedControl"] button {
            height: 30px !important;
            border-radius: 6px !important;
            font-size: 0.78rem !important;
            font-weight: 600 !important;
            padding: 0 10px !important;
            color: #5E6878 !important;
            border: none !important;
        }

        [data-testid="stSegmentedControl"] button[aria-checked="true"] {
            background-color: #ffffff !important;
            color: #4f46e5 !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05) !important;
            font-weight: 700 !important;
        }

        /* ── Harmonized Selectbox Inputs ── */
        div[data-testid="stSelectbox"] > div {
            min-height: 36px !important;
            border-radius: 8px !important;
            border-color: #E3E6EB !important;
            font-size: 0.82rem !important;
        }

        /* ── RRG Active Selection Buttons: Universal Left Alignment ── */
        div[class*="st-key-del_rrg_"] {
            display: flex !important;
            justify-content: flex-start !important;
            width: 100% !important;
        }
        div[class*="st-key-del_rrg_"] button {
            justify-content: flex-start !important;
            text-align: left !important;
            display: flex !important;
            align-items: center !important;
            width: 100% !important;
        }
        div[class*="st-key-del_rrg_"] button *,
        div[class*="st-key-del_rrg_"] button div,
        div[class*="st-key-del_rrg_"] button p,
        div[class*="st-key-del_rrg_"] button span,
        div[class*="st-key-del_rrg_"] button [data-testid="stMarkdownContainer"] {
            justify-content: flex-start !important;
            text-align: left !important;
            display: flex !important;
            align-items: center !important;
            width: 100% !important;
            margin: 0 !important;
        }

        /* ── Mac-Style Window Dots Bar ── */
        .mac-dots-container {
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 0px;
        }
        .mac-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
        }
        .mac-dot-red { background-color: #ff5f56; }
        .mac-dot-yellow { background-color: #ffbd2e; }
        .mac-dot-green { background-color: #27c93f; }

        /* ── Ticker Ribbon Bar ── */
        .ticker-ribbon {
            display: flex;
            align-items: center;
            gap: 16px;
            overflow-x: auto;
            padding: 8px 16px;
            background-color: #F4F5F8;
            border: 1px solid #E3E6EB;
            border-radius: 12px;
            margin-bottom: 16px;
            scrollbar-width: none;
        }
        .ticker-ribbon::-webkit-scrollbar {
            display: none;
        }
        .ticker-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-family: 'Geist Mono', monospace;
            font-size: 0.78rem;
            white-space: nowrap;
            padding: 4px 10px;
            background-color: #ffffff;
            border: 1px solid #E3E6EB;
            border-radius: 8px;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
        }

        /* ── Headings & Badges ── */
        h1, h2, h3, h4, h5, h6 {
            color: #0E1726 !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em !important;
        }

        p, [data-testid="stMarkdownContainer"] p {
            color: #3C4657 !important;
            font-size: 0.88rem;
        }

        [data-testid="stCaptionContainer"] {
            font-size: 0.78rem !important;
            color: #5E6878 !important;
        }

        /* ── Slim Left Sidebar ── */
        [data-testid="stSidebar"] {
            background-color: #F4F5F8 !important;
            border-right: 1px solid #E3E6EB !important;
            box-shadow: 1px 0 3px rgba(0, 0, 0, 0.02) !important;
        }

        [data-testid="stSidebarContent"] {
            background-color: #F4F5F8 !important;
            padding: 1.2rem 1.1rem !important;
        }

        .sidebar-section-title {
            font-family: 'Geist Mono', monospace;
            font-size: 0.68rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: #5E6878;
            margin-top: 14px;
            margin-bottom: 6px;
        }

        /* ── Sidebar Radio Navigation Items ── */
        [data-testid="stSidebar"] [data-testid="stRadio"] > div {
            gap: 3px !important;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label {
            padding: 7px 10px !important;
            border-radius: 8px !important;
            border: 1px solid transparent !important;
            background-color: transparent !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
            color: #3C4657 !important;
            transition: all 0.15s ease !important;
            cursor: pointer !important;
            width: 100% !important;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
            background-color: #ffffff !important;
            border-color: #E3E6EB !important;
            color: #4f46e5 !important;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
            background-color: #ffffff !important;
            border-color: #c7d2fe !important;
            color: #4f46e5 !important;
            box-shadow: 0 1px 3px rgba(79, 70, 229, 0.08) !important;
        }

        [data-testid="stSidebar"] .stButton > button {
            background-color: #ffffff !important;
            border: 1px solid #E3E6EB !important;
            color: #1F2A3A !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
            transition: all 0.15s ease-in-out !important;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            background-color: #eef2ff !important;
            border-color: #c7d2fe !important;
            color: #4f46e5 !important;
        }

        /* ── Metric Containers ── */
        [data-testid="metric-container"] {
            background-color: #ffffff !important;
            border: 1px solid #E3E6EB !important;
            border-radius: 14px !important;
            padding: 1.1rem 1.3rem !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02) !important;
            transition: transform 0.1s ease, box-shadow 0.1s ease;
        }

        [data-testid="metric-container"]:hover {
            border-color: #D0D5DD !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.06), 0 2px 4px -1px rgba(0, 0, 0, 0.04) !important;
        }

        [data-testid="stMetricLabel"] {
            font-family: 'Geist Mono', monospace !important;
            font-size: 0.72rem !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.08em !important;
            color: #5E6878 !important;
        }

        [data-testid="stMetricValue"] {
            font-family: 'Geist Mono', monospace !important;
            font-size: 1.6rem !important;
            font-weight: 700 !important;
            color: #0E1726 !important;
        }

        [data-testid="stMetricDelta"] {
            font-family: 'Geist Mono', monospace !important;
            font-size: 0.78rem !important;
            font-weight: 600 !important;
        }

        /* ── Navigation Tabs ── */
        [data-baseweb="tab-list"] {
            background-color: #F4F5F8 !important;
            border: 1px solid #E3E6EB !important;
            border-radius: 12px !important;
            padding: 0.35rem !important;
            gap: 0.25rem !important;
            margin-bottom: 1.4rem !important;
        }

        [data-baseweb="tab"] {
            border-radius: 8px !important;
            padding: 0.45rem 1rem !important;
            font-family: 'Geist Mono', monospace !important;
            font-size: 0.8rem !important;
            font-weight: 600 !important;
            color: #5E6878 !important;
            border: none !important;
            transition: all 0.15s ease !important;
        }

        [data-baseweb="tab"]:hover {
            color: #0E1726 !important;
            background-color: #F1F3F6 !important;
        }

        [aria-selected="true"][data-baseweb="tab"] {
            background-color: #ffffff !important;
            color: #4f46e5 !important;
            border: 1px solid #E3E6EB !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
        }

        [data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {
            display: none !important;
        }

        /* ── Stock Screener Card (Tickerboom style) ── */
        .stock-card {
            background-color: #ffffff;
            border: 1px solid #E3E6EB;
            border-radius: 14px;
            padding: 16px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
            transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            height: 100%;
        }
        .stock-card:hover {
            transform: translateY(-2px);
            border-color: #D0D5DD;
            box-shadow: 0 6px 12px -2px rgba(0, 0, 0, 0.08);
        }
        .stock-card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        .stock-card-sym {
            font-family: 'Geist', sans-serif;
            font-size: 1.15rem;
            font-weight: 800;
            color: #0E1726;
        }
        .stock-card-rank {
            font-family: 'Geist Mono', monospace;
            font-size: 0.72rem;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 20px;
            background-color: #eef2ff;
            color: #4f46e5;
            border: 1px solid #c7d2fe;
        }
        .stock-card-company {
            font-size: 0.76rem;
            color: #5E6878;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 12px;
        }
        .stock-card-price {
            color: #0E1726 !important;
            font-size: 1.35rem !important;
            font-weight: 800 !important;
            font-family: 'Geist Mono', monospace !important;
            letter-spacing: -0.02em !important;
        }

        /* ── Financial High-Density DataTables ── */
        [data-testid="stDataFrame"] {
            border: 1px solid #E3E6EB !important;
            border-radius: 12px !important;
            overflow: hidden !important;
            background-color: #ffffff !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03) !important;
        }

        /* ── Form Inputs & Buttons ── */
        .stButton > button {
            background-color: #ffffff !important;
            border: 1px solid #D0D5DD !important;
            border-radius: 8px !important;
            color: #3C4657 !important;
            font-size: 0.84rem !important;
            font-weight: 600 !important;
            padding: 0.4rem 0.9rem !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
            transition: all 0.15s ease !important;
        }

        .stButton > button:hover {
            border-color: #4f46e5 !important;
            color: #4f46e5 !important;
            background-color: #F4F5F8 !important;
        }

        /* The page's one main action: indigo, per the design. */
        .stButton > button[kind="primary"] {
            background-color: #4F46E5 !important; border-color: #4F46E5 !important; color: #FFFFFF !important;
        }
        .stButton > button[kind="primary"]:hover {
            background-color: #4338CA !important; border-color: #4338CA !important; color: #FFFFFF !important;
        }

        [data-testid="stDownloadButton"] button {
            background-color: #FFFFFF !important;
            color: #0E1726 !important;
            border: 1px solid #D0D5DD !important;
            font-weight: 600 !important;
            border-radius: 10px !important;
            min-height: 40px !important;
        }

        [data-testid="stDownloadButton"] button:hover {
            background-color: #F4F5F8 !important;
            border-color: #4F46E5 !important;
            color: #4338CA !important;
        }

        [data-testid="stDownloadButton"] button[kind="primary"] {
            background-color: #4F46E5 !important; color: #FFFFFF !important; border-color: #4F46E5 !important;
        }
        [data-testid="stDownloadButton"] button[kind="primary"]:hover {
            background-color: #4338CA !important; color: #FFFFFF !important;
        }
        /* A page-wide paragraph colour reached into primary buttons and left
           their labels grey on indigo. */
        [data-testid="stBaseButton-primary"] p,
        [data-testid="stBaseButton-primary"] span { color: #FFFFFF !important; }

        [data-baseweb="select"] > div {
            background-color: #ffffff !important;
            border: 1px solid #D0D5DD !important;
            border-radius: 8px !important;
            color: #0E1726 !important;
        }

        [data-baseweb="input"] input, [data-baseweb="textarea"] textarea {
            background-color: #ffffff !important;
            border: 1px solid #D0D5DD !important;
            color: #0E1726 !important;
            border-radius: 8px !important;
            font-size: 0.85rem !important;
        }

        [data-baseweb="input"] input:focus, [data-baseweb="textarea"] textarea:focus {
            border-color: #4f46e5 !important;
            box-shadow: 0 0 0 1px #4f46e5 !important;
        }

        [data-testid="stExpander"] {
            background-color: #ffffff !important;
            border: 1px solid #E3E6EB !important;
            border-radius: 12px !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
            margin-bottom: 0.8rem !important;
        }

        [data-testid="stExpander"] summary {
            font-size: 0.86rem !important;
            font-weight: 600 !important;
            color: #1F2A3A !important;
        }

        [data-testid="stSlider"] [role="slider"] {
            background-color: #4f46e5 !important;
            border-color: #4f46e5 !important;
        }

        hr {
            border-color: #F1F3F6 !important;
            margin: 1.2rem 0 !important;
        }
        </style>
        """),
        unsafe_allow_html=True,
    )


def generate_sparkline_svg(prices_arr, width: int = 74, height: int = 24) -> str:
    """Generates an ultra-lightweight inline SVG sparkline for price trajectories."""
    if prices_arr is None or len(prices_arr) < 2:
        return '<span style="color:#D0D5DD;font-size:0.75rem;">—</span>'
    try:
        p = [float(x) for x in prices_arr if pd.notna(x)]
        if len(p) < 2:
            return '<span style="color:#D0D5DD;font-size:0.75rem;">—</span>'
        p_min, p_max = min(p), max(p)
        rng = p_max - p_min
        if rng <= 0:
            rng = 1.0
        n = len(p)
        pts = []
        for i, val in enumerate(p):
            x = round((i / (n - 1)) * (width - 8) + 4, 1)
            y = round(height - 4 - ((val - p_min) / rng) * (height - 8), 1)
            pts.append(f"{x},{y}")
        path_d = "M " + " L ".join(pts)
        color = "#067647" if p[-1] >= p[0] else "#B42318"
        return f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="display:inline-block;vertical-align:middle;"><path d="{path_d}" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    except Exception:
        return '<span style="color:#D0D5DD;font-size:0.75rem;">—</span>'


PERIOD_WINDOWS: tuple[int, ...] = (1, 3, 6, 9, 12)


def _period_cells(row, months: int) -> dict[str, str]:
    """Return/Sharpe/drawdown cells for one calendar window.

    Five windows are shown, so the per-period formatting is written once here
    rather than copied five times; the 3M and 6M blocks were already duplicates
    of each other and adding 1M, 9M and 12M by hand would have made five.
    """
    label = f"{months}M"
    ret = row.get(f"{label} Return")
    ret_num = isinstance(ret, (int, float)) and pd.notna(ret)
    sharpe = row.get(f"{label} Sharpe")
    dd = row.get(f"Max DD {label}")
    return {
        "ret": f"{float(ret):+.1%}" if ret_num else "—",
        "clr": "ret-pos" if (ret_num and ret > 0) else ("ret-neg" if (ret_num and ret < 0) else ""),
        "sharpe": (
            f"{float(sharpe):.2f}"
            if pd.notna(sharpe) and isinstance(sharpe, (int, float))
            else "—"
        ),
        "dd": (
            f"{float(dd):.1f}%"
            if pd.notna(dd) and isinstance(dd, (int, float))
            else "—"
        ),
    }


_SPARK_MISSING = '<span style="color:#D0D5DD;font-size:0.75rem;">—</span>'


def _spark_window_key(sub_prices: pd.DataFrame) -> str:
    """Fingerprint the 60-session window the sparklines are drawn from.

    Same shape as src/engine/pipeline.frame_memo_key and for the same
    reason: within a trading day the window's last date and shape do not
    change, only the numbers in the final row do, so hashing that row is what
    makes an intraday refresh miss the cache instead of serving this morning's
    lines under this afternoon's prices. Everything before the last row is
    settled history, and a change there moves the shape or the date anyway.
    """
    try:
        last = pd.to_numeric(sub_prices.iloc[-1], errors="coerce").to_numpy(dtype="float64")
        digest = hashlib.md5(last.tobytes()).hexdigest()[:12]
        return f"{sub_prices.index[-1]}_{sub_prices.shape[0]}x{sub_prices.shape[1]}_{digest}"
    except Exception:
        # Un-fingerprintable means un-cacheable: return a value that never
        # repeats, so the map is recomputed rather than wrongly reused.
        return f"nokey_{id(sub_prices)}_{time.time()}"


@st.cache_data(show_spinner=False, ttl=3600)
def _sparkline_svgs(window_key: str, _sub_prices: pd.DataFrame) -> dict[str, str]:
    """Every symbol's sparkline for one price window, built once.

    Keyed on the WINDOW, not on the symbols being displayed, so the screener's
    filters and presets all read the same cached map instead of each rebuilding
    the subset they happen to show. Measured at ~118ms for 750 symbols, paid on
    every Table-mode render before this.
    """
    return {
        str(col): generate_sparkline_svg(_sub_prices[col].values)
        for col in _sub_prices.columns
    }


# ── Column headers ──────────────────────────────────────────────────────────
# Module level, and the ONLY place the table's shape is written down. The
# density labels used to carry their own hand-typed column counts -- "Full
# Quant (35)" over a table that emitted 36 -- because a second copy of a
# number is a copy that drifts. `screener_column_count` now reads the count
# back out of these very blocks, so a column added here reaches the label
# with no second edit.
def _headers_block(is_exec: bool, is_core: bool, has_risk: bool) -> str:
    # Dropped together: a group label spanning no columns leaves a stray cell
    # in the top header row, which shifts every column after it by one.
    risk_group_core = "<th>RISK</th>" if has_risk else ""
    risk_sub_core = "<th>STOP LOSS</th>" if has_risk else ""
    risk_group_full = '<th colspan="2">RISK & EXITS</th>' if has_risk else ""
    risk_sub_full = (
        "<th>STOP LOSS</th>\n                <th>CHAND EXIT</th>" if has_risk else ""
    )

    # Assemble headers based on density
    if is_exec:
        headers_block = """
            <tr class="group-header-row">
                <th colspan="3" class="sticky-group-id">IDENTITY</th>
                <th>DYNAMICS</th>
                <th colspan="2">CLASSIFICATION</th>
                <th colspan="2">3M MOMENTUM</th>
                <th colspan="2">FILTERS</th>
                <th>TREND</th>
            </tr>
            <tr class="sub-header-row">
                <th class="sticky-col-rank">RANK</th>
                <th class="sticky-col-symbol">SYMBOL</th>
                <th>CMP</th>
                <th class="th-center">1M Δ</th>
                <th class="th-center">INDEX</th>
                <th class="th-left">INDUSTRY</th>
                <th>3M RET</th>
                <th>3M SHARPE</th>
                <th>% 52W HI</th>
                <th>% 50 EMA</th>
                <th class="th-center">60D SPARK</th>
            </tr>"""
    elif is_core:
        headers_block = f"""
            <tr class="group-header-row">
                <th colspan="3" class="sticky-group-id">IDENTITY</th>
                <th colspan="2">RANK DYNAMICS</th>
                <th colspan="3">CLASSIFICATION</th>
                <th colspan="2">3M MOMENTUM</th>
                <th colspan="2">6M MOMENTUM</th>
                <th colspan="3">FILTERS</th>
                {risk_group_core}
                <th>TREND</th>
            </tr>
            <tr class="sub-header-row">
                <th class="sticky-col-rank">RANK</th>
                <th class="sticky-col-symbol">SYMBOL</th>
                <th>CMP</th>
                <th class="th-center">1M Δ</th>
                <th class="th-center">3M Δ</th>
                <th class="th-center">INDEX</th>
                <th class="th-left">INDUSTRY</th>
                <th>MCAP (CR)</th>
                <th>3M RET</th>
                <th>3M SHARPE</th>
                
                <th>6M RET</th>
                <th>6M SHARPE</th>
                <th>% 52W HI</th>
                <th>% 50 EMA</th>
                <th class="th-center">VOLUME</th>
                {risk_sub_core}
                <th class="th-center">60D SPARK</th>
            </tr>"""
    else:
        headers_block = f"""
            <tr class="group-header-row">
                <th colspan="3" class="sticky-group-id">IDENTITY</th>
                <th colspan="2">RANK DYNAMICS</th>
                <th colspan="3">CLASSIFICATION</th>
                <th colspan="3">1M FACTOR MOMENTUM</th>
                <th colspan="3">3M FACTOR MOMENTUM</th>
                <th colspan="3">6M FACTOR MOMENTUM</th>
                <th colspan="3">9M FACTOR MOMENTUM</th>
                <th colspan="3">12M FACTOR MOMENTUM</th>
                <th colspan="7">TECHNICALS & FILTERS</th>
                {risk_group_full}
                <th colspan="3">DATA HEALTH</th>
                <th>TREND</th>
            </tr>
            <tr class="sub-header-row">
                <th class="sticky-col-rank">RANK</th>
                <th class="sticky-col-symbol">SYMBOL</th>
                <th>CMP</th>
                <th class="th-center">1M Δ</th>
                <th class="th-center">3M Δ</th>
                <th class="th-center">INDEX</th>
                <th class="th-left">INDUSTRY</th>
                <th>MCAP (CR)</th>
                <th>1M RET</th>
                <th>1M SHARPE</th>
                <th>MAX DD 1M</th>
                <th>3M RET</th>
                <th>3M SHARPE</th>
                <th>MAX DD 3M</th>
                <th>6M RET</th>
                <th>6M SHARPE</th>
                <th>MAX DD 6M</th>
                <th>9M RET</th>
                <th>9M SHARPE</th>
                <th>MAX DD 9M</th>
                <th>12M RET</th>
                <th>12M SHARPE</th>
                <th>MAX DD 12M</th>
                <th>% 52W HI</th>
                <th>% ATH</th>
                <th>% 50 EMA</th>
                <th class="th-center">VOLUME</th>
                <th class="th-center">&gt; 50 EMA</th>
                <th class="th-center">NEAR 52W</th>
                <th class="th-center">AT ATH</th>
                {risk_sub_full}
                <th class="th-center">GAP</th>
                <th>FFILL %</th>
                <th class="th-center">HORIZONS</th>
                <th class="th-center">60D SPARK</th>
            </tr>"""
    return headers_block


def screener_column_count(density: str, columns) -> int:
    """How many columns the table will actually draw at this density."""
    return len(
        re.findall(
            r"<th",
            re.search(
                r'<tr class="sub-header-row">(.*?)</tr>',
                _headers_block(
                    str(density).startswith("Executive"),
                    str(density).startswith("Core"),
                    any(c in columns for c in ATR_DERIVED_COLUMNS),
                ),
                re.S,
            ).group(1),
        )
    )


def render_master_screener_table(
    df: pd.DataFrame,
    prices_df: pd.DataFrame | None = None,
    max_height: int = 750,
    density: str = "Full Quant (35)",
) -> None:
    """Renders Institutional SaaS Screener Table with Multi-Tier Column Density, Sticky Headers & Sparklines."""
    if df.empty:
        st.info("No matching stocks found for the active filter criteria.")
        return

    # Determine density tier
    is_exec = str(density).startswith("Executive")
    is_core = str(density).startswith("Core")

    # A ranking built from CLOSING prices carries no ATR, so the Core and Full
    # densities were printing a STOP LOSS column -- and, at Full, a CHAND EXIT
    # column beside it -- in which every one of 750 rows was an em dash. The
    # columns are dropped with their headers and their group label instead.
    # The card grid already did this (it emits an empty footer span), which is
    # why only the table showed it.
    has_risk = any(col in df.columns for col in ATR_DERIVED_COLUMNS)

    # Pre-extract 60-day price sparklines
    spark_map = {}
    if prices_df is not None and not prices_df.empty:
        spark_window = min(60, len(prices_df))
        sub_prices = prices_df.iloc[-spark_window:]
        all_svgs = _sparkline_svgs(_spark_window_key(sub_prices), sub_prices)
        spark_map = {sym: all_svgs.get(sym, _SPARK_MISSING) for sym in df["Symbol"]}

    # Build HTML Rows for All Records (Continuous Scrollable)
    #
    # to_dict("records") rather than iterrows(): iterrows() rebuilds a pandas
    # Series per row, which measured ~3.4x the cost of plain dicts over 750
    # rows. Every read below is row.get(...), which a dict answers identically.
    # The frame here always carries Symbol and Industry as text, so it is
    # mixed-dtype and iterrows() was already boxing values to native Python --
    # the isinstance(x, (int, float)) checks throughout see exactly what they
    # saw before.
    rows_html = []
    for row in df.to_dict("records"):
        rk = row.get("Rank", "—")
        sym = row.get("Symbol", "—")
        # Every value below originates in a third-party feed (the
        # niftyindices.com constituent CSVs, the NSE PR bhavcopy, Yahoo) and
        # lands in an st.iframe srcdoc, which Streamlit renders with
        # allow-scripts AND allow-same-origin -- markup in a cell would
        # execute on the app's own origin. Escape at the sink, once, where
        # it cannot be forgotten by a new column.
        rk_s = _esc(str(rk))
        sym_s = _esc(str(sym))

        cmp_val = row.get("CMP")
        cmp_str = (
            f"₹{float(cmp_val):,.0f}"
            if pd.notna(cmp_val) and isinstance(cmp_val, (int, float))
            else "—"
        )

        # Rank moves
        d1m = row.get("Rank Δ 1M")
        if pd.notna(d1m) and isinstance(d1m, (int, float)):
            if d1m > 0:
                d1m_html = f"<span class='badge-pill badge-green'>▲ {int(d1m)}</span>"
            elif d1m < 0:
                d1m_html = (
                    f"<span class='badge-pill badge-red'>▼ {abs(int(d1m))}</span>"
                )
            else:
                d1m_html = "<span class='badge-pill badge-neutral'>— 0</span>"
        else:
            d1m_html = "<span class='text-muted'>—</span>"

        d3m = row.get("Rank Δ 3M")
        if pd.notna(d3m) and isinstance(d3m, (int, float)):
            if d3m > 0:
                d3m_html = f"<span class='badge-pill badge-green'>▲ {int(d3m)}</span>"
            elif d3m < 0:
                d3m_html = (
                    f"<span class='badge-pill badge-red'>▼ {abs(int(d3m))}</span>"
                )
            else:
                d3m_html = "<span class='badge-pill badge-neutral'>— 0</span>"
        else:
            d3m_html = "<span class='text-muted'>—</span>"

        # Classification
        idx_raw = str(row.get("Indices", "—")).split(",")[0].strip()
        idx_html = (
            f"<span class='index-tag'>{_esc(idx_raw)}</span>"
            if idx_raw and idx_raw != "—"
            else "<span class='text-muted'>—</span>"
        )

        ind_raw = str(row.get("Industry", "—"))
        ind_disp = ind_raw[:20] + "…" if len(ind_raw) > 21 else ind_raw
        ind_raw_s = _esc(ind_raw)
        ind_disp_s = _esc(ind_disp)

        mcap_val = row.get("Market Cap (Cr)")
        mcap_str = (
            f"₹{float(mcap_val):,.0f}"
            if pd.notna(mcap_val) and isinstance(mcap_val, (int, float))
            else "—"
        )

        # 3M and 6M are read from `pc` below, like every other window. They used
        # to be formatted by hand here, twice, because the Executive and Core
        # tiers predate _period_cells and only Full Quant was migrated to it --
        # which is how the dead dd_3m_str/dd_6m_str pair survived in this block
        # long after nothing rendered them.

        # Technicals & Filters
        pct_hi = row.get("% High")
        hi_str = (
            f"{float(pct_hi):.1f}%"
            if pd.notna(pct_hi) and isinstance(pct_hi, (int, float))
            else "—"
        )

        pct_ath = row.get("% ATH")
        ath_peak = str(row.get("ATH Date") or "").strip()
        ath_title = f' title="Peak printed {_esc(ath_peak)}"' if ath_peak else ""
        ath_str = (
            f"{float(pct_ath):.1f}%"
            if pd.notna(pct_ath) and isinstance(pct_ath, (int, float))
            else "—"
        )

        pct_ema = row.get("% 50 EMA")
        ema_str = (
            f"{float(pct_ema):+.1f}%"
            if pd.notna(pct_ema) and isinstance(pct_ema, (int, float))
            else "—"
        )

        vol_val = str(row.get("Volume", "Normal"))
        vol_badge = (
            "<span class='vol-tag'>🔥 High</span>"
            if vol_val == "High"
            else (
                "<span class='vol-tag vol-surge'>⚡ Surge</span>"
                if vol_val == "Surge"
                else "<span class='text-muted'>• Normal</span>"
            )
        )

        above_ema_icon = "🟢" if is_tick_true(row.get("Above 50 EMA")) else "⚪"
        near_hi_icon = "🟢" if is_tick_true(row.get("Near 52W High")) else "⚪"
        at_ath_icon = "🟢" if is_tick_true(row.get("At ATH")) else "⚪"

        # Risk & Exits
        sl_val = row.get("Stop Loss")
        sl_str = (
            f"₹{float(sl_val):,.0f}"
            if pd.notna(sl_val) and isinstance(sl_val, (int, float))
            else "—"
        )

        chand_val = row.get("Chand Exit")
        chand_str = (
            f"₹{float(chand_val):,.0f}"
            if pd.notna(chand_val) and isinstance(chand_val, (int, float))
            else "—"
        )

        sl_cell = f'<td class="td-num td-sl">{sl_str}</td>' if has_risk else ""
        chand_cell = (
            f'<td class="td-num td-chand">{chand_str}</td>' if has_risk else ""
        )

        # Data Health
        gap_val = str(row.get("Data Gap", "🟢"))
        gap_icon = "🔴" if "🔴" in gap_val else "🟢"
        if CARRIED_MARK in gap_val:
            # Ranked on its last print: no price on the ranking session.
            gap_icon = f'<span title="No price on the ranking date; ranked on its last print">{gap_icon}{CARRIED_MARK}</span>'

        ffill_val = row.get("FFill %")
        ffill_str = (
            f"{float(ffill_val):.1f}%"
            if pd.notna(ffill_val) and isinstance(ffill_val, (int, float))
            else "0.0%"
        )

        # How many of the five calendar horizons actually scored this stock.
        # The composite renormalises over the ones that did, so a 2-of-5 name
        # sits on the same scale as a 5-of-5 name while averaging fewer, noisier
        # terms -- its rank moves more between sessions for reasons that are
        # about its listing date, not its momentum. Anything short of the full
        # five is worth seeing, so only the full count renders unmarked.
        hz_val = row.get("Horizons Scored")
        if pd.notna(hz_val) and isinstance(hz_val, (int, float)):
            hz_n = int(hz_val)
            hz_cls = "" if hz_n >= len(PERIOD_WINDOWS) else " td-short-hz"
            hz_str = (
                f'<span class="hz-count{hz_cls}" title="Scored on {hz_n} of '
                f'{len(PERIOD_WINDOWS)} calendar horizons'
                f'{"" if hz_n >= len(PERIOD_WINDOWS) else "; the composite is an average over fewer, noisier terms"}'
                f'">{hz_n}/{len(PERIOD_WINDOWS)}</span>'
            )
        else:
            hz_str = "<span class='text-muted'>—</span>"

        spark_svg = spark_map.get(sym, '<span class="text-muted">—</span>')

        # Every calendar window, formatted once. pc[3]["ret"] is the 3M return
        # cell, and so on; the Full Quant tier below renders all five.
        #
        # The symbol opens the stock page. Getting there is not as simple as an
        # href: this table lives in a Streamlit iframe sandboxed with
        #   allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox
        #   allow-same-origin allow-scripts allow-downloads
        # and NO allow-top-navigation, so the browser refuses any attempt by
        # this frame to navigate the page around it -- a plain link, target
        #="_parent", and assigning parent.location alike. Chrome rejects the
        # last one out loud: "The current window does not have permission to
        # navigate the target frame."
        #
        # The href stays a real URL so middle-click and "copy link address"
        # behave; the click itself is handled by the delegated listener in the
        # page script below, which is where the workaround lives.
        sym_link = (
            f'<a href="?stock={_urlq(str(sym), safe="")}" '
            f'class="stock-ticker" data-stock="{sym_s}" '
            f'style="text-decoration:none;border-bottom:1px dotted #667080;'
            f'cursor:pointer;" title="Open {sym_s}">{sym_s}</a>'
        )

        pc = {m: _period_cells(row, m) for m in PERIOD_WINDOWS}
        period_cells_html = "".join(
            f'<td class="td-num {pc[m]["clr"]}"><strong>{pc[m]["ret"]}</strong></td>'
            f'<td class="td-num td-sharpe">{pc[m]["sharpe"]}</td>'
            f'<td class="td-num td-dd">{pc[m]["dd"]}</td>'
            for m in PERIOD_WINDOWS
        )

        if is_exec:
            row_h = f"""<tr class="screener-row"><td class="sticky-col-rank"><strong>{rk_s}</strong></td><td class="sticky-col-symbol">{sym_link}</td><td class="td-num"><strong>{cmp_str}</strong></td><td class="td-center">{d1m_html}</td><td class="td-center">{idx_html}</td><td class="td-sector" title="{ind_raw_s}">{ind_disp_s}</td><td class="td-num {pc[3]['clr']}"><strong>{pc[3]['ret']}</strong></td><td class="td-num td-sharpe">{pc[3]['sharpe']}</td><td class="td-num">{hi_str}</td><td class="td-num">{ema_str}</td><td class="td-spark">{spark_svg}</td></tr>"""
        elif is_core:
            row_h = f"""<tr class="screener-row"><td class="sticky-col-rank"><strong>{rk_s}</strong></td><td class="sticky-col-symbol">{sym_link}</td><td class="td-num"><strong>{cmp_str}</strong></td><td class="td-center">{d1m_html}</td><td class="td-center">{d3m_html}</td><td class="td-center">{idx_html}</td><td class="td-sector" title="{ind_raw_s}">{ind_disp_s}</td><td class="td-num">{mcap_str}</td><td class="td-num {pc[3]['clr']}"><strong>{pc[3]['ret']}</strong></td><td class="td-num td-sharpe">{pc[3]['sharpe']}</td><td class="td-num {pc[6]['clr']}"><strong>{pc[6]['ret']}</strong></td><td class="td-num td-sharpe">{pc[6]['sharpe']}</td><td class="td-num">{hi_str}</td><td class="td-num">{ema_str}</td><td class="td-center">{vol_badge}</td>{sl_cell}<td class="td-spark">{spark_svg}</td></tr>"""
        else:
            row_h = f"""<tr class="screener-row"><td class="sticky-col-rank"><strong>{rk_s}</strong></td><td class="sticky-col-symbol">{sym_link}</td><td class="td-num"><strong>{cmp_str}</strong></td><td class="td-center">{d1m_html}</td><td class="td-center">{d3m_html}</td><td class="td-center">{idx_html}</td><td class="td-sector" title="{ind_raw_s}">{ind_disp_s}</td><td class="td-num">{mcap_str}</td>{period_cells_html}<td class="td-num">{hi_str}</td><td class="td-num"{ath_title}>{ath_str}</td><td class="td-num">{ema_str}</td><td class="td-center">{vol_badge}</td><td class="td-center">{above_ema_icon}</td><td class="td-center">{near_hi_icon}</td><td class="td-center">{at_ath_icon}</td>{sl_cell}{chand_cell}<td class="td-center">{gap_icon}</td><td class="td-num">{ffill_str}</td><td class="td-center">{hz_str}</td><td class="td-spark">{spark_svg}</td></tr>"""
        rows_html.append(row_h)

    headers_block = _headers_block(is_exec, is_core, has_risk)

    # Master Table Assembly - Rendered via st.iframe with 2D Sticky Freeze
    full_page_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500..800&family=Geist:wght@400..700&family=Geist+Mono:wght@400..700&display=swap" rel="stylesheet">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    background: transparent;
    font-family: 'Geist', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #0E1726;
    -webkit-font-smoothing: antialiased;
    padding: 2px;
}}
.modern-screener-wrapper {{
    width: 100%;
    max-height: {max_height}px;
    overflow: auto;
    border: 1px solid #E3E6EB;
    border-radius: 12px;
    background: #ffffff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    position: relative;
    scrollbar-width: none !important;
    -ms-overflow-style: none !important;
}}
.modern-screener-wrapper::-webkit-scrollbar,
body::-webkit-scrollbar,
*::-webkit-scrollbar {{
    width: 0px !important;
    height: 0px !important;
    display: none !important;
    background: transparent !important;
}}
.modern-screener-table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-family: 'Geist', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 12.5px;
    color: #0E1726;
    white-space: nowrap;
}}

/* ── Sticky Top Group Headers ── */
.modern-screener-table thead tr.group-header-row th {{
    position: sticky;
    top: 0;
    z-index: 20;
    background: #F4F5F8;
    color: #5E6878;
    font-family: 'Geist Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 7px 10px;
    border-bottom: 1px solid #E3E6EB;
    border-left: none;
    border-right: none;
    text-align: center;
}}

/* ── 2D Frozen Top-Left Header Group (Identity) ── */
.modern-screener-table thead tr.group-header-row th.sticky-group-id {{
    position: sticky;
    left: 0;
    top: 0;
    z-index: 40;
    background: #F1F3F6;
    border-right: 1.5px solid #D0D5DD;
    box-shadow: 3px 0 6px rgba(0,0,0,0.04);
}}

/* ── Sticky Column Sub-Headers ── */
.modern-screener-table thead tr.sub-header-row th {{
    position: sticky;
    top: 28px;
    z-index: 20;
    background: #F4F5F8;
    color: #3C4657;
    font-family: 'Geist Mono', monospace;
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 8px 10px;
    border-bottom: 2px solid #D0D5DD;
    border-left: none;
    border-right: none;
    text-align: right;
}}
.modern-screener-table thead tr.sub-header-row th.th-center {{ text-align: center; }}
.modern-screener-table thead tr.sub-header-row th.th-left {{ text-align: left; }}

/* ── 2D Frozen Column Headers ── */
.modern-screener-table thead tr.sub-header-row th.sticky-col-rank {{
    position: sticky;
    left: 0;
    top: 28px;
    z-index: 35;
    background: #F1F3F6;
    min-width: 48px;
    max-width: 48px;
    width: 48px;
    text-align: center;
    border-right: 1px solid #E3E6EB;
}}
.modern-screener-table thead tr.sub-header-row th.sticky-col-symbol {{
    position: sticky;
    left: 48px;
    top: 28px;
    z-index: 35;
    background: #F1F3F6;
    min-width: 105px;
    max-width: 105px;
    width: 105px;
    text-align: left;
    border-right: 1.5px solid #D0D5DD;
    box-shadow: 3px 0 6px rgba(0,0,0,0.04);
}}

/* ── Table Body Rows ── */
.modern-screener-table tbody tr.screener-row {{
    border-bottom: 1px solid #F1F3F6;
    transition: background-color 0.12s ease;
}}
.modern-screener-table tbody tr.screener-row:hover td {{
    background-color: #F4F5F8 !important;
}}
.modern-screener-table td {{
    padding: 6px 10px;
    vertical-align: middle;
    font-family: 'Geist Mono', monospace;
    font-size: 12px;
    border-bottom: 1px solid #F1F3F6;
    border-left: none;
    border-right: none;
    background: #ffffff;
}}

/* ── 2D Frozen Columns (Body Data) ── */
.modern-screener-table td.sticky-col-rank {{
    position: sticky;
    left: 0;
    z-index: 10;
    background: #ffffff;
    min-width: 48px;
    max-width: 48px;
    width: 48px;
    text-align: center;
    font-weight: 800;
    color: #0E1726;
    border-right: 1px solid #F1F3F6;
}}
.modern-screener-table td.sticky-col-symbol {{
    position: sticky;
    left: 48px;
    z-index: 10;
    background: #ffffff;
    min-width: 105px;
    max-width: 105px;
    width: 105px;
    text-align: left;
    padding-left: 10px;
    border-right: 1.5px solid #E3E6EB;
    box-shadow: 3px 0 6px rgba(0,0,0,0.04);
}}

.stock-ticker {{
    font-family: 'Geist', sans-serif;
    font-weight: 800;
    font-size: 11px;
    color: #0E1726;
    letter-spacing: 0.02em;
}}
.modern-screener-table td.td-center {{ text-align: center; }}
.modern-screener-table td.td-num {{ text-align: right; }}
.modern-screener-table td.td-sector {{
    text-align: left;
    font-family: 'Geist', sans-serif;
    font-size: 12px;
    color: #3C4657;
    max-width: 160px;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.modern-screener-table td.td-spark {{
    text-align: center;
    padding: 2px 8px;
    width: 80px;
}}

/* Badges & Pills */
.badge-pill {{
    display: inline-block;
    font-family: 'Geist Mono', monospace;
    font-size: 10.5px;
    font-weight: 700;
    padding: 1.5px 6px;
    border-radius: 5px;
}}
.badge-green {{
    background: #E8F5EE;
    color: #067647;
}}
.badge-red {{
    background: #FDEDEB;
    color: #912018;
}}
.badge-neutral {{
    color: #5E6878;
}}
.index-tag {{
    display: inline-block;
    font-family: 'Geist Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    background: #F1F3F6;
    color: #3C4657;
    padding: 1.5px 5px;
    border-radius: 4px;
    border: 1px solid #E3E6EB;
}}
.vol-tag {{
    font-family: 'Geist Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    color: #067647;
}}
.vol-surge {{
    color: #4f46e5;
}}
.ret-pos {{ color: #067647; font-weight: 700; }}
.ret-neg {{ color: #912018; font-weight: 700; }}
.td-sharpe {{ color: #067647; font-weight: 600; }}
.modern-screener-table thead tr.sub-header-row th {{
    cursor: pointer;
    user-select: none;
    transition: background-color 0.15s ease, color 0.15s ease;
}}
.modern-screener-table thead tr.sub-header-row th:hover {{
    background-color: #E3E6EB !important;
    color: #0E1726 !important;
}}
.sort-indicator {{
    display: inline-block;
    margin-left: 4px;
    font-size: 8.5px;
    color: #4f46e5;
    vertical-align: middle;
}}
.td-dd {{ color: #B42318; }}
.td-sl {{ color: #912018; }}
.td-chand {{ color: #067647; font-weight: 600; }}
.hz-count {{
    font-family: 'Geist Mono', monospace;
    font-size: 11px;
    font-weight: 600;
    color: #5E6878;
}}
/* Amber, not red: a partial composite is a caveat on how much history is
   behind the rank, not a data fault like a price gap. */
.td-short-hz {{
    color: #93370D;
    font-weight: 800;
    background: #FEF6EA;
    border-radius: 5px;
    padding: 1px 5px;
}}
.text-muted {{ color: #667080; font-size: 11px; }}
</style>
</head>
<body>
<div class="modern-screener-wrapper">
    <table class="modern-screener-table">
        <thead>
            {headers_block}
        </thead>
        <tbody>
            {''.join(rows_html)}
        </tbody>
    </table>
</div>
<script>
document.addEventListener('DOMContentLoaded', function() {{
    // Symbol -> stock page. This frame may not navigate the page around it
    // (no allow-top-navigation), but it DOES have allow-same-origin, so it can
    // reach into the parent document -- which is not sandboxed -- and add a
    // script there. That script runs as the parent and navigating yourself is
    // always allowed, so the route opens in the same tab like the card view.
    //
    // If the parent is ever cross-origin (the injection throws), allow-popups
    // is granted, so the page opens in a new tab instead. Losing the tab is a
    // worse experience than keeping it; having no way in at all is worse than
    // both.
    document.addEventListener('click', function(ev) {{
        const link = ev.target.closest ? ev.target.closest('a[data-stock]') : null;
        if (!link) return;
        ev.preventDefault();
        const sym = link.getAttribute('data-stock');
        const search = '?stock=' + encodeURIComponent(sym);
        try {{
            const host = window.parent;
            const s = host.document.createElement('script');
            s.textContent = 'window.location.search=' + JSON.stringify(search) + ';';
            host.document.body.appendChild(s);
            s.remove();
        }} catch (e) {{
            window.open(search, '_blank');
        }}
    }});

    const table = document.querySelector('.modern-screener-table');
    if (!table) return;
    const thList = table.querySelectorAll('thead tr.sub-header-row th');
    const tbody = table.querySelector('tbody');

    thList.forEach((th, colIdx) => {{
        if (th.classList.contains('th-spark') || th.innerText.includes('SPARK')) return;
        let currentDir = 'none';

        th.addEventListener('click', function() {{
            currentDir = (currentDir === 'asc') ? 'desc' : 'asc';

            thList.forEach(otherTh => {{
                const icon = otherTh.querySelector('.sort-indicator');
                if (icon) icon.remove();
                if (otherTh !== th) otherTh.removeAttribute('data-sort-dir');
            }});

            th.setAttribute('data-sort-dir', currentDir);
            const ind = document.createElement('span');
            ind.className = 'sort-indicator';
            ind.textContent = currentDir === 'asc' ? ' ▲' : ' ▼';
            th.appendChild(ind);

            const rows = Array.from(tbody.querySelectorAll('tr.screener-row'));
            rows.sort((rowA, rowB) => {{
                const cellA = rowA.children[colIdx];
                const cellB = rowB.children[colIdx];
                if (!cellA || !cellB) return 0;

                let txtA = cellA.innerText.trim();
                let txtB = cellB.innerText.trim();

                // Blanks sink to the bottom in both directions. Two blanks
                // compare EQUAL: returning 1 for both orders made the
                // comparator inconsistent, and the browser's sort may then
                // scramble the rows.
                const blankA = (txtA === '—' || txtA === '');
                const blankB = (txtB === '—' || txtB === '');
                if (blankA || blankB) return (blankA === blankB) ? 0 : (blankA ? 1 : -1);

                if (txtA.startsWith('▲') || txtA.startsWith('▼') || txtA.startsWith('—')) {{
                    let numA = parseFloat(txtA.replace(/[▲▼—\\s]/g, '')) * (txtA.startsWith('▼') ? -1 : 1);
                    let numB = parseFloat(txtB.replace(/[▲▼—\\s]/g, '')) * (txtB.startsWith('▼') ? -1 : 1);
                    if (!isNaN(numA) && !isNaN(numB)) {{
                        return currentDir === 'asc' ? (numA - numB) : (numB - numA);
                    }}
                }}

                let cleanA = txtA.replace(/[₹,×%+#]/g, '').trim();
                let cleanB = txtB.replace(/[₹,×%+#]/g, '').trim();
                let valA = parseFloat(cleanA);
                let valB = parseFloat(cleanB);

                if (!isNaN(valA) && !isNaN(valB) && cleanA !== '' && cleanB !== '') {{
                    return currentDir === 'asc' ? (valA - valB) : (valB - valA);
                }}

                return currentDir === 'asc' ? txtA.localeCompare(txtB) : txtB.localeCompare(txtA);
            }});

            rows.forEach(r => tbody.appendChild(r));
        }});
    }});
}});
</script>
</body>
</html>"""
    st.iframe(full_page_html, height=max_height)


# ── Percentage units ────────────────────────────────────────────────────────
# Two conventions meet in these tables. Some columns carry a FRACTION (0.0734
# means +7.34%); others carry a value already multiplied by 100 (7.34 means
# +7.34%). The renderer used to tell them apart by magnitude -- "<= 1.0, so it
# must be a fraction" -- and magnitude cannot recover a unit. It failed on
# precisely the rows that matter most:
#
#   Return % = 1.31 on a stock that gained 131%  ->  printed "+1.3%"
#   Max DD 3M = -0.8, an 0.8% drawdown           ->  printed "-80.0%"
#
# so a multibagger read as a rounding error, and the blotter's entry and exit
# prices refused to reconcile with the return beside them. The unit is a
# property of the column, so it is declared per column here. Anything not
# listed falls back to the magnitude guess, which is right for the ordinary
# case of a return between -100% and +100%.
FRACTION_PERCENT_COLUMNS: frozenset[str] = frozenset({
    # Backtest — trades, periods and stats
    "RETURN %", "STRATEGY NET", "BENCHMARK", "ALPHA VS BENCHMARK",
    "TOTAL RETURN", "GROSS RETURN", "NET RETURN", "ALPHA", "OUTPERFORM",
    "CAGR", "ANN RETURN", "WIN RATE", "MAX DRAWDOWN", "MAX DD",
    "6M NET RETURN", "6M ALPHA",
})

SCALED_PERCENT_COLUMNS: frozenset[str] = frozenset({
    # Already multiplied by 100 at source
    "TURNOVER", "TURNOVER %", "COST DRAG %", "WEIGHT %",
    "% HIGH", "% ATH", "% 50 EMA", "% 20 EMA", "% 52W HIGH",
    "ATR %", "PERSISTENCE", "FFILL %",
    "DEL %", "DEL% 20D AVG", "DEL% PREV20D",
    "DAY CHG %", "PRICE_CHG_%",
})

# Window-parameterised families, so adding a horizon to MOMENTUM_WINDOWS does
# not silently reintroduce the guess for that column.
_FRACTION_PATTERNS = (re.compile(r"^\d+M RETURN$"),)
_SCALED_PATTERNS = (re.compile(r"^MAX DD \d+M$"),)


def percent_unit(column: object) -> str | None:
    """"fraction", "scaled", or None when the column has not declared a unit."""
    name = str(column).strip().upper()
    if name in FRACTION_PERCENT_COLUMNS or any(
        p.match(name) for p in _FRACTION_PATTERNS
    ):
        return "fraction"
    if name in SCALED_PERCENT_COLUMNS or any(p.match(name) for p in _SCALED_PATTERNS):
        return "scaled"
    return None


# Per-share prices are quoted to the paisa. Rounding them to the rupee -- which
# is what "two decimals only below 100" did to every stock above 100 rupees --
# means an entry of 157.65 and an exit of 168.40 print as 158 and 168, and the
# +6.8% beside them looks wrong because, at the precision shown, it is.
_PER_SHARE_PRICE_KEYS = ("CMP", "PRICE", "STOP LOSS", "CHAND", "ENTRY", "EXIT")
_AGGREGATE_MONEY_KEYS = ("VALUE", "CAPITAL", "MCAP")


def render_saas_table(
    df: pd.DataFrame,
    max_height: int | None = None,
) -> None:
    """Renders a beautiful borderless SaaS table with sticky headers, interactive column sorting, and Geist Mono numerics."""
    if df.empty:
        st.info("No data available to display.")
        return

    n_rows = len(df)
    if max_height is None:
        table_h = min(600, (n_rows * 36) + 48)
    else:
        table_h = max_height

    headers_html = []
    for col in df.columns:
        c_str = str(col).upper()
        if any(
            w in c_str
            for w in [
                "RANK",
                "DELTA",
                "Δ",
                "GAP",
                "STATUS",
                "STOCKS",
                "COUNT",
                "HOLDINGS",
                "TRADES",
                "IN ALL TOP",
                "QUADRANT",
                "ACTION",
            ]
        ):
            headers_html.append(f'<th class="th-center">{_esc(str(col))}</th>')
        elif any(
            w in c_str
            for w in [
                "SYMBOL",
                "INDUSTRY",
                "SECTOR",
                "STRATEGY",
                "TAXONOMY",
                "DESCRIPTION",
                "NAME",
                "PERIOD",
                "MODEL",
                "OBJECTIVE",
                "REGIME",
                "WINDOW",
                "REASON",
                "MONTH",
            ]
        ):
            headers_html.append(f'<th class="th-left">{_esc(str(col))}</th>')
        else:
            headers_html.append(f'<th class="th-right">{_esc(str(col))}</th>')

    rows_html = []
    # Plain dicts rather than iterrows(): a Series per row is ~3.4x the cost
    # over a large frame and nothing here needs one. Unlike the screener table
    # this renderer takes arbitrary frames, some of which are homogeneously
    # numeric -- where iterrows() hands back numpy scalars rather than boxing
    # to native Python. That is safe here only because the value branches below
    # test (int, np.integer) and (float, np.floating), so a native int and a
    # numpy int64 land in the same branch either way. Keep those numpy arms if
    # this loop is ever rewritten.
    for row in df.to_dict("records"):
        cells_html = []
        for col in df.columns:
            val = row[col]
            c_str = str(col).upper()

            if pd.isna(val) or val is None or str(val).strip() in ("", "nan", "None"):
                cells_html.append('<td class="td-center text-muted">—</td>')
                continue

            # Special column formatting
            if "SYMBOL" in c_str:
                cells_html.append(
                    f'<td class="td-left"><span class="stock-ticker">{_esc(str(val))}</span></td>'
                )
            elif "QUADRANT" in c_str:
                q_val = str(val).capitalize()
                q_badge = {
                    "Leading": "badge-green",
                    "Weakening": "badge-yellow",
                    "Lagging": "badge-red",
                    "Improving": "badge-blue",
                }.get(q_val, "badge-neutral")
                q_ico = {
                    "Leading": "🟢",
                    "Weakening": "🟡",
                    "Lagging": "🔴",
                    "Improving": "🔵",
                }.get(q_val, "⚪")
                cells_html.append(
                    f'<td class="td-center"><span class="badge-pill {q_badge}">{q_ico} {_esc(q_val)}</span></td>'
                )
            elif "ACTION" in c_str:
                act_str = str(val).upper()
                if "BUY" in act_str:
                    cells_html.append(
                        '<td class="td-center"><span class="badge-pill badge-green">🟢 BUY</span></td>'
                    )
                elif "SELL" in act_str:
                    cells_html.append(
                        '<td class="td-center"><span class="badge-pill badge-red">🔴 SELL</span></td>'
                    )
                else:
                    cells_html.append(
                        f'<td class="td-center"><span class="badge-pill badge-neutral">{_esc(str(val))}</span></td>'
                    )
            elif isinstance(val, (int, np.integer)) and not isinstance(val, bool):
                if any(w in c_str for w in ["DELTA", "Δ"]):
                    clr = (
                        "badge-green"
                        if val > 0
                        else ("badge-red" if val < 0 else "badge-neutral")
                    )
                    symbol = "▲" if val > 0 else ("▼" if val < 0 else "—")
                    cells_html.append(
                        f'<td class="td-center"><span class="badge-pill {clr}">{symbol} {abs(int(val))}</span></td>'
                    )
                elif any(
                    w in c_str
                    for w in ["RANK", "STOCKS", "COUNT", "HOLDINGS", "TRADES"]
                ):
                    cells_html.append(
                        f'<td class="td-center"><strong>{int(val)}</strong></td>'
                    )
                else:
                    cells_html.append(f'<td class="td-right">{int(val):,}</td>')
            elif isinstance(val, (float, np.floating)):
                if any(w in c_str for w in ["DELTA", "Δ"]):
                    clr = (
                        "badge-green"
                        if val > 0
                        else ("badge-red" if val < 0 else "badge-neutral")
                    )
                    symbol = "▲" if val > 0 else ("▼" if val < 0 else "—")
                    cells_html.append(
                        f'<td class="td-center"><span class="badge-pill {clr}">{symbol} {abs(round(val))}</span></td>'
                    )
                elif any(
                    w in c_str
                    for w in ["RANK", "STOCKS", "COUNT", "HOLDINGS", "TRADES"]
                ):
                    cells_html.append(
                        f'<td class="td-center"><strong>{round(val)}</strong></td>'
                    )
                # Whole-number counts that arrive as float (a NaN anywhere in
                # the column makes pandas store it that way): "3.00 buys" and
                # "42.00 days" read as measurements, not counts.
                elif any(w in c_str for w in ["BUYS", "SELLS", "(DAYS)", "SHARES"]) and float(val).is_integer():
                    cells_html.append(f'<td class="td-right">{int(val):,}</td>')
                # 1. Returns & Alphas & Monthly returns (e.g. M-1, M-2, Strategy Net, Benchmark)
                elif (
                    any(
                        w in c_str
                        for w in [
                            "RETURN",
                            "RET",
                            "ALPHA",
                            "CAGR",
                            "DAY CHG",
                            "NET",
                            "BENCHMARK",
                        ]
                    )
                    or c_str.startswith("M-")
                    or "MONTH" in c_str
                ):
                    clr = (
                        "ret-pos"
                        if val > 0
                        else ("ret-neg" if val < 0 else "text-muted")
                    )
                    unit = percent_unit(col)
                    as_fraction = (
                        unit == "fraction"
                        if unit is not None
                        else (abs(val) <= 1.0 and val != 0)
                    )
                    if as_fraction:
                        cells_html.append(
                            f'<td class="td-right {clr}"><strong>{val:+.1%}</strong></td>'
                        )
                    else:
                        cells_html.append(
                            f'<td class="td-right {clr}"><strong>{val:+.1f}%</strong></td>'
                        )
                # 2. Percentages (e.g. Del %, Win Rate, Turnover %, Cost Drag %, ATR %, Weight %)
                elif any(
                    w in c_str
                    for w in [
                        "%",
                        "DD",
                        "DRAWDOWN",
                        "WIN RATE",
                        "TURNOVER",
                        "DEL",
                        "DRAG",
                        "FFILL",
                        "HIGH",
                        "EMA",
                        "WEIGHT",
                    ]
                ):
                    clr = (
                        "ret-neg"
                        if any(w in c_str for w in ["DD", "DRAWDOWN", "DRAG"])
                        else ""
                    )
                    unit = percent_unit(col)
                    as_fraction = (
                        unit == "fraction"
                        if unit is not None
                        else (
                            abs(val) <= 1.0
                            and val != 0
                            and not any(
                                k in c_str
                                for k in [
                                    "DEL",
                                    "TURNOVER",
                                    "DRAG",
                                    "FFILL",
                                    "EMA",
                                    "HIGH",
                                    "%",
                                ]
                            )
                        )
                    )
                    if as_fraction:
                        cells_html.append(f'<td class="td-right {clr}">{val:.1%}</td>')
                    else:
                        cells_html.append(f'<td class="td-right {clr}">{val:.1f}%</td>')
                # 3. Currency / Prices (e.g. CMP, Entry Price, Exit Price, Value, Capital)
                elif any(
                    w in c_str for w in _PER_SHARE_PRICE_KEYS + _AGGREGATE_MONEY_KEYS
                ):
                    if any(w in c_str for w in _PER_SHARE_PRICE_KEYS):
                        cells_html.append(
                            f'<td class="td-right">₹{float(val):,.2f}</td>'
                        )
                    else:
                        cells_html.append(
                            f'<td class="td-right">₹{float(val):,.0f}</td>'
                        )
                # 4. Multipliers & Ratios (e.g. Sharpe, Sortino, Calmar, Beta, Surge, Multiplier, Profit Factor, RS_Ratio, RS_Momentum)
                elif any(
                    w in c_str
                    for w in [
                        "SHARPE",
                        "SORTINO",
                        "CALMAR",
                                                "RATIO",
                        "BETA",
                        "SURGE",
                        "MULTIPLIER",
                        "FACTOR",
                        "PERSISTENCE",
                        "RS_RATIO",
                        "RS_MOMENTUM",
                    ]
                ):
                    if any(w in c_str for w in ["SURGE", "MULTIPLIER", "FACTOR"]):
                        cells_html.append(
                            f'<td class="td-right td-sharpe">{float(val):.2f}×</td>'
                        )
                    else:
                        cells_html.append(
                            f'<td class="td-right td-sharpe">{float(val):.2f}</td>'
                        )
                # 5. Generic Float Fallback (Guarantees clean 2 decimals max!)
                else:
                    cells_html.append(f'<td class="td-right">{val:.2f}</td>')
            elif any(w in c_str for w in ["INDUSTRY", "SECTOR"]):
                cells_html.append(f'<td class="td-left td-sector">{_esc(str(val))}</td>')
            elif isinstance(val, bool):
                cells_html.append(
                    f'<td class="td-center">{"🟢 Yes" if val else "⚪ No"}</td>'
                )
            else:
                cells_html.append(f'<td class="td-left">{_esc(str(val))}</td>')

        rows_html.append(f'<tr class="screener-row">{"".join(cells_html)}</tr>')

    saas_page_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500..800&family=Geist:wght@400..700&family=Geist+Mono:wght@400..700&display=swap" rel="stylesheet">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    background: transparent;
    font-family: 'Geist', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #0E1726;
    -webkit-font-smoothing: antialiased;
    padding: 2px;
}}
.saas-table-wrapper {{
    width: 100%;
    max-height: {table_h}px;
    overflow: auto;
    border: 1px solid #E3E6EB;
    border-radius: 10px;
    background: #ffffff;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    scrollbar-width: none !important;
    -ms-overflow-style: none !important;
}}
.saas-table-wrapper::-webkit-scrollbar,
body::-webkit-scrollbar,
*::-webkit-scrollbar {{
    width: 0px !important;
    height: 0px !important;
    display: none !important;
    background: transparent !important;
}}
.saas-table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-family: 'Geist', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 12px;
    color: #0E1726;
    white-space: nowrap;
}}
.saas-table thead tr th {{
    position: sticky;
    top: 0;
    z-index: 10;
    background: #F4F5F8;
    color: #3C4657;
    font-family: 'Geist Mono', monospace;
    font-size: 10.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 8px 10px;
    border-bottom: 1.5px solid #D0D5DD;
    border-left: none;
    border-right: none;
    cursor: pointer;
    user-select: none;
    transition: background-color 0.15s ease, color 0.15s ease;
}}
.saas-table thead tr th:hover {{
    background-color: #E3E6EB !important;
    color: #0E1726 !important;
}}
.saas-table thead tr th.th-left {{ text-align: left; }}
.saas-table thead tr th.th-center {{ text-align: center; }}
.saas-table thead tr th.th-right {{ text-align: right; }}
.sort-indicator {{
    display: inline-block;
    margin-left: 4px;
    font-size: 8.5px;
    color: #4f46e5;
    vertical-align: middle;
}}

.saas-table tbody tr.screener-row {{
    border-bottom: 1px solid #F1F3F6;
    transition: background-color 0.12s ease;
}}
.saas-table tbody tr.screener-row:hover td {{
    background-color: #F4F5F8 !important;
}}
.saas-table td {{
    padding: 7px 10px;
    vertical-align: middle;
    font-family: 'Geist Mono', monospace;
    font-size: 12px;
    border-bottom: 1px solid #F1F3F6;
    border-left: none;
    border-right: none;
    background: #ffffff;
}}
.saas-table td.td-left {{ text-align: left; }}
.saas-table td.td-center {{ text-align: center; }}
.saas-table td.td-right {{ text-align: right; }}
.saas-table td.td-sector {{
    font-family: 'Geist', sans-serif;
    color: #3C4657;
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.stock-ticker {{
    font-family: 'Geist', sans-serif;
    font-weight: 800;
    font-size: 11px;
    color: #0E1726;
    letter-spacing: 0.02em;
}}
.badge-pill {{
    display: inline-block;
    font-family: 'Geist Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    padding: 1.5px 6px;
    border-radius: 5px;
}}
.badge-green {{ background: #E8F5EE; color: #067647; border: 1px solid #bbf7d0; }}
.badge-yellow {{ background: #fefce8; color: #a16207; border: 1px solid #fef08a; }}
.badge-red {{ background: #FDEDEB; color: #912018; border: 1px solid #F3C7C1; }}
.badge-blue {{ background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }}
.badge-neutral {{ background: #F4F5F8; color: #5E6878; border: 1px solid #E3E6EB; }}
.ret-pos {{ color: #067647; font-weight: 700; }}
.ret-neg {{ color: #912018; font-weight: 700; }}
.td-sharpe {{ color: #067647; font-weight: 600; }}
.text-muted {{ color: #667080; }}
</style>
</head>
<body>
<div class="saas-table-wrapper">
    <table class="saas-table">
        <thead>
            <tr>{"".join(headers_html)}</tr>
        </thead>
        <tbody>
            {"".join(rows_html)}
        </tbody>
    </table>
</div>
<script>
document.addEventListener('DOMContentLoaded', function() {{
    const table = document.querySelector('.saas-table');
    if (!table) return;
    const thList = table.querySelectorAll('thead tr th');
    const tbody = table.querySelector('tbody');

    thList.forEach((th, colIdx) => {{
        let currentDir = 'none';

        th.addEventListener('click', function() {{
            currentDir = (currentDir === 'asc') ? 'desc' : 'asc';

            thList.forEach(otherTh => {{
                const icon = otherTh.querySelector('.sort-indicator');
                if (icon) icon.remove();
                if (otherTh !== th) otherTh.removeAttribute('data-sort-dir');
            }});

            th.setAttribute('data-sort-dir', currentDir);
            const ind = document.createElement('span');
            ind.className = 'sort-indicator';
            ind.textContent = currentDir === 'asc' ? ' ▲' : ' ▼';
            th.appendChild(ind);

            const rows = Array.from(tbody.querySelectorAll('tr.screener-row'));
            rows.sort((rowA, rowB) => {{
                const cellA = rowA.children[colIdx];
                const cellB = rowB.children[colIdx];
                if (!cellA || !cellB) return 0;

                let txtA = cellA.innerText.trim();
                let txtB = cellB.innerText.trim();

                // Blanks sink to the bottom in both directions. Two blanks
                // compare EQUAL: returning 1 for both orders made the
                // comparator inconsistent, and the browser's sort may then
                // scramble the rows.
                const blankA = (txtA === '—' || txtA === '');
                const blankB = (txtB === '—' || txtB === '');
                if (blankA || blankB) return (blankA === blankB) ? 0 : (blankA ? 1 : -1);

                if (txtA.startsWith('▲') || txtA.startsWith('▼') || txtA.startsWith('—')) {{
                    let numA = parseFloat(txtA.replace(/[▲▼—\\s]/g, '')) * (txtA.startsWith('▼') ? -1 : 1);
                    let numB = parseFloat(txtB.replace(/[▲▼—\\s]/g, '')) * (txtB.startsWith('▼') ? -1 : 1);
                    if (!isNaN(numA) && !isNaN(numB)) {{
                        return currentDir === 'asc' ? (numA - numB) : (numB - numA);
                    }}
                }}

                let cleanA = txtA.replace(/[₹,×%+#]/g, '').trim();
                let cleanB = txtB.replace(/[₹,×%+#]/g, '').trim();
                let valA = parseFloat(cleanA);
                let valB = parseFloat(cleanB);

                if (!isNaN(valA) && !isNaN(valB) && cleanA !== '' && cleanB !== '') {{
                    return currentDir === 'asc' ? (valA - valB) : (valB - valA);
                }}

                return currentDir === 'asc' ? txtA.localeCompare(txtB) : txtB.localeCompare(txtA);
            }});

            rows.forEach(r => tbody.appendChild(r));
        }});
    }});
}});
</script>
</body>
</html>"""
    st.iframe(saas_page_html, height=table_h + 10)
