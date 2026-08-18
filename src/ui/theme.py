import re

import numpy as np
import pandas as pd
import streamlit as st


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
    "Trades": "{:,.0f}",
    "Total Trades": "{:,.0f}",
    "Rank": "{:.0f}",
    "Rank (-1M)": "{:.0f}",
    "Rank (-3M)": "{:.0f}",
    "Rank Δ 1M": "{:+.0f}",
    "Rank Δ 3M": "{:+.0f}",
    "Exp Rank": "{:.0f}",
    "Residual Rank": "{:.0f}",
    "Ind-Rel Rank": "{:.0f}",
    "Accel Rank": "{:.0f}",
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
    "Alpha": "{:+.2f}",
    "Beta": "{:.2f}",
    "Score": "{:.2f}",
}

BOOL_ICONS = {True: "🟢", False: "⚪"}
VOL_ICONS = {
    "High": "🟢 High",
    "Surge": "🟢 Surge",
    "Normal": "⚪ Normal",
    "Low": "🔴 Low",
}


def inject_custom_css() -> None:
    """Injects comprehensive Pure Paper White styling with 5-Font institutional typography."""
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=JetBrains+Mono:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&family=Outfit:wght@500;600;700;800;900&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">

        <style>
        /* ── Design Tokens (light default; dark override via media query) ── */
        :root {
            --c-bg: #ffffff;
            --c-bg-subtle: #f8fafc;
            --c-surface: #ffffff;
            --c-border: #e2e8f0;
            --c-text-primary: #0f172a;
            --c-text-secondary: #475569;
            --c-text-muted: #64748b;
            --c-accent: #4f46e5;
            --c-bull: #059669;
            --c-bear: #e11d48;
        }
        @media (prefers-color-scheme: dark) {
            :root:not([data-theme="light"]) {
                --c-bg: #0f172a;
                --c-bg-subtle: #1e293b;
                --c-surface: #1e293b;
                --c-border: #334155;
                --c-text-primary: #f1f5f9;
                --c-text-secondary: #94a3b8;
                --c-text-muted: #64748b;
                --c-accent: #818cf8;
                --c-bull: #34d399;
                --c-bear: #fb7185;
            }
        }
        :root[data-theme="dark"] {
            --c-bg: #0f172a;
            --c-bg-subtle: #1e293b;
            --c-surface: #1e293b;
            --c-border: #334155;
            --c-text-primary: #f1f5f9;
            --c-text-secondary: #94a3b8;
            --c-text-muted: #64748b;
            --c-accent: #818cf8;
            --c-bull: #34d399;
            --c-bear: #fb7185;
        }

        /* ── Base Reset & Typography Hierarchy ── */
        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
            color: #0f172a !important;
            background-color: #ffffff !important;
            -webkit-font-smoothing: antialiased;
        }

        /* ── Typography Classes ── */
        .font-display, h1, h2, h3, h4, [data-testid="stMetricValue"] {
            font-family: 'Outfit', -apple-system, sans-serif !important;
            letter-spacing: -0.02em !important;
        }
        .font-mono, [data-testid="stMetricDelta"] {
            font-family: 'JetBrains Mono', monospace !important;
            font-variant-numeric: tabular-nums !important;
        }
        .font-code, code, pre {
            font-family: 'Fira Code', monospace !important;
        }
        .font-serif {
            font-family: 'Newsreader', Georgia, serif !important;
        }
        .font-sans {
            font-family: 'Plus Jakarta Sans', sans-serif !important;
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
            scrollbar-color: #cbd5e1 transparent !important;
            -ms-overflow-style: auto !important;
        }
        div[role="alert"][aria-label="Market signals"]::-webkit-scrollbar,
        .ticker-ribbon::-webkit-scrollbar {
            height: 4px !important;
            display: block !important;
        }
        div[role="alert"][aria-label="Market signals"]::-webkit-scrollbar-thumb,
        .ticker-ribbon::-webkit-scrollbar-thumb {
            background-color: #cbd5e1 !important;
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
            background-color: #ffffff !important;
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
            max-width: 100% !important;
            padding-top: 0.15rem !important;
            padding-bottom: 2rem !important;
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
            margin-top: 0px !important;
        }

        /* ── Sleek Top Tab Navigation Menu (Equally Spaced Menu Bar) ── */
        .stTabs [data-baseweb="tab-list"] {
            display: flex !important;
            width: 100% !important;
            gap: 4px !important;
            background-color: #f8fafc !important;
            padding: 4px 5px !important;
            border-radius: 9px !important;
            border: 1px solid #e2e8f0 !important;
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
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            font-size: 12.5px !important;
            font-weight: 600 !important;
            color: #64748b !important;
            white-space: nowrap !important;
            transition: all 0.15s ease !important;
            cursor: pointer !important;
        }

        .stTabs [data-baseweb="tab"]:hover {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border-color: #e2e8f0 !important;
        }

        .stTabs [aria-selected="true"] {
            background-color: #ffffff !important;
            color: #4f46e5 !important;
            font-weight: 700 !important;
            border-color: #c7d2fe !important;
            box-shadow: 0 1px 3px rgba(79, 70, 229, 0.08) !important;
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
            border-radius: 20px !important;
            font-size: 0.78rem !important;
            font-weight: 600 !important;
            padding: 2px 10px !important;
            height: 36px !important;
            border: 1px solid #e2e8f0 !important;
            background-color: #f8fafc !important;
            color: #475569 !important;
            white-space: nowrap !important;
            flex-shrink: 0 !important;
            transition: all 0.15s ease !important;
        }

        [data-testid="stPills"] button:hover {
            background-color: #ffffff !important;
            color: #4f46e5 !important;
            border-color: #cbd5e1 !important;
        }

        [data-testid="stPills"] button[aria-checked="true"] {
            background-color: #ffffff !important;
            color: #4f46e5 !important;
            border-color: #4f46e5 !important;
            box-shadow: 0 1px 3px rgba(79, 70, 229, 0.12) !important;
            font-weight: 700 !important;
        }

        /* ── Segmented Control (Table / Cards Switcher) ── */
        [data-testid="stSegmentedControl"] {
            height: 36px !important;
            border-radius: 8px !important;
            background-color: #f8fafc !important;
            border: 1px solid #e2e8f0 !important;
            padding: 2px !important;
        }

        [data-testid="stSegmentedControl"] button {
            height: 30px !important;
            border-radius: 6px !important;
            font-size: 0.78rem !important;
            font-weight: 600 !important;
            padding: 0 10px !important;
            color: #64748b !important;
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
            border-color: #e2e8f0 !important;
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
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
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
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.78rem;
            white-space: nowrap;
            padding: 4px 10px;
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
        }

        /* ── Headings & Badges ── */
        h1, h2, h3, h4, h5, h6 {
            color: #0f172a !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em !important;
        }

        p, [data-testid="stMarkdownContainer"] p {
            color: #334155 !important;
            font-size: 0.88rem;
        }

        [data-testid="stCaptionContainer"] {
            font-size: 0.78rem !important;
            color: #64748b !important;
        }

        /* ── Slim Left Sidebar ── */
        [data-testid="stSidebar"] {
            background-color: #f8fafc !important;
            border-right: 1px solid #e2e8f0 !important;
            box-shadow: 1px 0 3px rgba(0, 0, 0, 0.02) !important;
        }

        [data-testid="stSidebarContent"] {
            background-color: #f8fafc !important;
            padding: 1.2rem 1.1rem !important;
        }

        .sidebar-section-title {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.68rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: #64748b;
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
            color: #334155 !important;
            transition: all 0.15s ease !important;
            cursor: pointer !important;
            width: 100% !important;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
            background-color: #ffffff !important;
            border-color: #e2e8f0 !important;
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
            border: 1px solid #e2e8f0 !important;
            color: #1e293b !important;
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
            border: 1px solid #e2e8f0 !important;
            border-radius: 14px !important;
            padding: 1.1rem 1.3rem !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02) !important;
            transition: transform 0.1s ease, box-shadow 0.1s ease;
        }

        [data-testid="metric-container"]:hover {
            border-color: #cbd5e1 !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.06), 0 2px 4px -1px rgba(0, 0, 0, 0.04) !important;
        }

        [data-testid="stMetricLabel"] {
            font-family: 'IBM Plex Mono', monospace !important;
            font-size: 0.72rem !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.08em !important;
            color: #64748b !important;
        }

        [data-testid="stMetricValue"] {
            font-family: 'IBM Plex Mono', monospace !important;
            font-size: 1.6rem !important;
            font-weight: 700 !important;
            color: #0f172a !important;
        }

        [data-testid="stMetricDelta"] {
            font-family: 'IBM Plex Mono', monospace !important;
            font-size: 0.78rem !important;
            font-weight: 600 !important;
        }

        /* ── Navigation Tabs ── */
        [data-baseweb="tab-list"] {
            background-color: #f8fafc !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 12px !important;
            padding: 0.35rem !important;
            gap: 0.25rem !important;
            margin-bottom: 1.4rem !important;
        }

        [data-baseweb="tab"] {
            border-radius: 8px !important;
            padding: 0.45rem 1rem !important;
            font-family: 'IBM Plex Mono', monospace !important;
            font-size: 0.8rem !important;
            font-weight: 600 !important;
            color: #64748b !important;
            border: none !important;
            transition: all 0.15s ease !important;
        }

        [data-baseweb="tab"]:hover {
            color: #0f172a !important;
            background-color: #f1f5f9 !important;
        }

        [aria-selected="true"][data-baseweb="tab"] {
            background-color: #ffffff !important;
            color: #4f46e5 !important;
            border: 1px solid #e2e8f0 !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
        }

        [data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {
            display: none !important;
        }

        /* ── Stock Screener Card (Tickerboom style) ── */
        .stock-card {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
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
            border-color: #cbd5e1;
            box-shadow: 0 6px 12px -2px rgba(0, 0, 0, 0.08);
        }
        .stock-card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        .stock-card-sym {
            font-family: 'Plus Jakarta Sans', sans-serif;
            font-size: 1.15rem;
            font-weight: 800;
            color: #0f172a;
        }
        .stock-card-rank {
            font-family: 'IBM Plex Mono', monospace;
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
            color: #64748b;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 12px;
        }
        .stock-card-price {
            color: #0f172a !important;
            font-size: 1.35rem !important;
            font-weight: 800 !important;
            font-family: 'IBM Plex Mono', monospace !important;
            letter-spacing: -0.02em !important;
        }

        /* ── Financial High-Density DataTables ── */
        [data-testid="stDataFrame"] {
            border: 1px solid #e2e8f0 !important;
            border-radius: 12px !important;
            overflow: hidden !important;
            background-color: #ffffff !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03) !important;
        }

        /* ── Form Inputs & Buttons ── */
        .stButton > button {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 8px !important;
            color: #334155 !important;
            font-size: 0.84rem !important;
            font-weight: 600 !important;
            padding: 0.4rem 0.9rem !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
            transition: all 0.15s ease !important;
        }

        .stButton > button:hover {
            border-color: #4f46e5 !important;
            color: #4f46e5 !important;
            background-color: #f8fafc !important;
        }

        [data-testid="stDownloadButton"] > button {
            background-color: #ecfdf5 !important;
            color: #059669 !important;
            border: 1px solid #a7f3d0 !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
        }

        [data-testid="stDownloadButton"] > button:hover {
            background-color: #d1fae5 !important;
            border-color: #6ee7b7 !important;
            color: #047857 !important;
        }

        [data-baseweb="select"] > div {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 8px !important;
            color: #0f172a !important;
        }

        [data-baseweb="input"] input, [data-baseweb="textarea"] textarea {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            color: #0f172a !important;
            border-radius: 8px !important;
            font-size: 0.85rem !important;
        }

        [data-baseweb="input"] input:focus, [data-baseweb="textarea"] textarea:focus {
            border-color: #4f46e5 !important;
            box-shadow: 0 0 0 1px #4f46e5 !important;
        }

        [data-testid="stExpander"] {
            background-color: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 12px !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
            margin-bottom: 0.8rem !important;
        }

        [data-testid="stExpander"] summary {
            font-size: 0.86rem !important;
            font-weight: 600 !important;
            color: #1e293b !important;
        }

        [data-testid="stSlider"] [role="slider"] {
            background-color: #4f46e5 !important;
            border-color: #4f46e5 !important;
        }

        hr {
            border-color: #f1f5f9 !important;
            margin: 1.2rem 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Formats boolean and categorical volume indicators for clean display."""
    out = df.copy()
    if "Above 50 EMA" in out.columns:
        out["Above 50 EMA"] = out["Above 50 EMA"].map(BOOL_ICONS)
    if "Near 52W High" in out.columns:
        out["Near 52W High"] = out["Near 52W High"].map(BOOL_ICONS)
    if "Volume" in out.columns:
        out["Volume"] = out["Volume"].map(lambda v: VOL_ICONS.get(v, v))
    return out


def render_styled_table(
    df: pd.DataFrame,
    key: str | None = None,
    gradient_cols: list[str] | None = None,
    height: int | None = None,
    custom_formats: dict[str, str] | None = None,
) -> None:
    """Renders high-density financial table with dynamic tight height, smart auto-formatting, and zero blank rows."""
    active_fmt = {}
    MONTH_NAMES = [
        "jan",
        "feb",
        "mar",
        "apr",
        "may",
        "jun",
        "jul",
        "aug",
        "sep",
        "oct",
        "nov",
        "dec",
    ]
    for col in df.columns:
        if custom_formats and col in custom_formats:
            active_fmt[col] = custom_formats[col]
        elif col in FORMAT_MAP:
            active_fmt[col] = FORMAT_MAP[col]
        elif pd.api.types.is_float_dtype(df[col]):
            col_l = col.lower()
            if (
                any(m in col_l for m in MONTH_NAMES)
                or "return" in col_l
                or "rate" in col_l
                or "yield" in col_l
                or "alpha" in col_l
            ):
                active_fmt[col] = "{:+.1%}"
            elif "%" in col or "pct" in col_l:
                active_fmt[col] = "{:.1f}%"
            elif any(
                w in col_l
                for w in ["sharpe", "sortino", "ratio", "beta", "score", "surge"]
            ):
                active_fmt[col] = "{:.2f}"
            elif any(
                w in col_l
                for w in [
                    "value",
                    "price",
                    "cmp",
                    "cap",
                    "target",
                    "actual",
                    "stop",
                    "exit",
                    "qty",
                    "quantity",
                    "shares",
                    "amount",
                    "volume",
                    "stocks",
                    "count",
                ]
            ):
                active_fmt[col] = "{:,.0f}"
            else:
                valid = df[col].dropna()
                if not valid.empty and (valid % 1 == 0).all():
                    active_fmt[col] = "{:,.0f}"
                else:
                    active_fmt[col] = "{:.2f}"
        elif pd.api.types.is_integer_dtype(df[col]):
            active_fmt[col] = "{:,.0f}"

    # Calculate tight height: exactly fit small tables, scrollable for large datasets
    if height is None:
        n_rows = len(df)
        if n_rows <= 12:
            calc_height = (n_rows * 35) + 40
        else:
            calc_height = 580
    else:
        calc_height = height

    try:
        s = df.style.format(active_fmt, na_rep="—")

        # Clean white styling with soft return color fills
        if "3M Return" in df.columns:
            s = s.map(
                lambda x: (
                    "background-color: #ecfdf5; color: #065f46; font-weight: 600;"
                    if pd.notna(x) and x > 0
                    else (
                        "background-color: #fff1f2; color: #9f1239; font-weight: 600;"
                        if pd.notna(x) and x < 0
                        else ""
                    )
                ),
                subset=["3M Return"],
            )
        if "6M Return" in df.columns:
            s = s.map(
                lambda x: (
                    "background-color: #ecfdf5; color: #065f46; font-weight: 600;"
                    if pd.notna(x) and x > 0
                    else (
                        "background-color: #fff1f2; color: #9f1239; font-weight: 600;"
                        if pd.notna(x) and x < 0
                        else ""
                    )
                ),
                subset=["6M Return"],
            )
        # Rank Delta Color Highlights (Green for advancement, Rose for drops)
        for d_col in ["Rank Δ 1M", "Rank Δ 3M"]:
            if d_col in df.columns:
                s = s.map(
                    lambda x: (
                        "background-color: #d1fae5; color: #065f46; font-weight: 700;"
                        if pd.notna(x) and x >= 30
                        else (
                            "background-color: #ecfdf5; color: #059669; font-weight: 600;"
                            if pd.notna(x) and x > 0
                            else (
                                "background-color: #fee2e2; color: #991b1b; font-weight: 700;"
                                if pd.notna(x) and x <= -30
                                else (
                                    "background-color: #fff1f2; color: #e11d48; font-weight: 600;"
                                    if pd.notna(x) and x < 0
                                    else ""
                                )
                            )
                        )
                    ),
                    subset=[d_col],
                )

        s = s.set_properties(
            **{
                "font-family": "'JetBrains Mono', monospace",
                "font-size": "12px",
                "color": "#0f172a",
                "border-left": "none",
                "border-right": "none",
            }
        )

        s = s.set_table_styles(
            [
                {
                    "selector": "th",
                    "props": [
                        ("background-color", "#f8fafc"),
                        ("color", "#475569"),
                        ("font-size", "11px"),
                        ("font-weight", "700"),
                        ("text-transform", "uppercase"),
                        ("letter-spacing", "0.05em"),
                        ("border-bottom", "1.5px solid #cbd5e1"),
                        ("border-left", "none"),
                        ("border-right", "none"),
                        ("padding", "8px 10px"),
                        ("font-family", "'Plus Jakarta Sans', sans-serif"),
                    ],
                },
                {
                    "selector": "td",
                    "props": [
                        ("padding", "6px 10px"),
                        ("border-bottom", "1px solid #f1f5f9"),
                        ("border-left", "none"),
                        ("border-right", "none"),
                    ],
                },
                {
                    "selector": "tr:hover td",
                    "props": [("background-color", "#f8fafc !important")],
                },
            ]
        )
        st.dataframe(s, width="stretch", height=calc_height, key=key, hide_index=True)
    except Exception:
        st.dataframe(df, width="stretch", height=calc_height, key=key, hide_index=True)


def generate_sparkline_svg(prices_arr, width: int = 74, height: int = 24) -> str:
    """Generates an ultra-lightweight inline SVG sparkline for price trajectories."""
    if prices_arr is None or len(prices_arr) < 2:
        return '<span style="color:#cbd5e1;font-size:0.75rem;">—</span>'
    try:
        p = [float(x) for x in prices_arr if pd.notna(x)]
        if len(p) < 2:
            return '<span style="color:#cbd5e1;font-size:0.75rem;">—</span>'
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
        color = "#059669" if p[-1] >= p[0] else "#e11d48"
        return f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="display:inline-block;vertical-align:middle;"><path d="{path_d}" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    except Exception:
        return '<span style="color:#cbd5e1;font-size:0.75rem;">—</span>'


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


def render_master_screener_table(
    df: pd.DataFrame,
    prices_df: pd.DataFrame | None = None,
    key: str = "master_screener",
    max_height: int = 750,
    density: str = "Full Quant (33)",
) -> None:
    """Renders Institutional SaaS Screener Table with Multi-Tier Column Density, Sticky Headers & Sparklines."""
    if df.empty:
        st.info("No matching stocks found for the active filter criteria.")
        return

    # Determine density tier
    is_exec = str(density).startswith("Executive")
    is_core = str(density).startswith("Core")

    # Pre-extract 60-day price sparklines
    spark_map = {}
    if prices_df is not None and not prices_df.empty:
        spark_window = min(60, len(prices_df))
        sub_prices = prices_df.iloc[-spark_window:]
        for sym in df["Symbol"]:
            if sym in sub_prices.columns:
                spark_map[sym] = generate_sparkline_svg(sub_prices[sym].values)
            else:
                spark_map[sym] = (
                    '<span style="color:#cbd5e1;font-size:0.75rem;">—</span>'
                )

    # Build HTML Rows for All Records (Continuous Scrollable)
    rows_html = []
    for _, row in df.iterrows():
        rk = row.get("Rank", "—")
        sym = row.get("Symbol", "—")

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
            f"<span class='index-tag'>{idx_raw}</span>"
            if idx_raw and idx_raw != "—"
            else "<span class='text-muted'>—</span>"
        )

        ind_raw = str(row.get("Industry", "—"))
        ind_disp = ind_raw[:20] + "…" if len(ind_raw) > 21 else ind_raw

        mcap_val = row.get("Market Cap (Cr)")
        mcap_str = (
            f"₹{float(mcap_val):,.0f}"
            if pd.notna(mcap_val) and isinstance(mcap_val, (int, float))
            else "—"
        )

        # 3M Factor Momentum
        ret_3m = row.get("3M Return")
        ret_3m_str = (
            f"{float(ret_3m):+.1%}"
            if pd.notna(ret_3m) and isinstance(ret_3m, (int, float))
            else "—"
        )
        ret_3m_clr = (
            "ret-pos"
            if (isinstance(ret_3m, (int, float)) and ret_3m > 0)
            else (
                "ret-neg" if (isinstance(ret_3m, (int, float)) and ret_3m < 0) else ""
            )
        )

        sharpe_3m = row.get("3M Sharpe")
        sharpe_3m_str = (
            f"{float(sharpe_3m):.2f}"
            if pd.notna(sharpe_3m) and isinstance(sharpe_3m, (int, float))
            else "—"
        )


        dd_3m = row.get("Max DD 3M")
        dd_3m_str = (
            f"{float(dd_3m):.1f}%"
            if pd.notna(dd_3m) and isinstance(dd_3m, (int, float))
            else "—"
        )

        # 6M Factor Momentum
        ret_6m = row.get("6M Return")
        ret_6m_str = (
            f"{float(ret_6m):+.1%}"
            if pd.notna(ret_6m) and isinstance(ret_6m, (int, float))
            else "—"
        )
        ret_6m_clr = (
            "ret-pos"
            if (isinstance(ret_6m, (int, float)) and ret_6m > 0)
            else (
                "ret-neg" if (isinstance(ret_6m, (int, float)) and ret_6m < 0) else ""
            )
        )

        sharpe_6m = row.get("6M Sharpe")
        sharpe_6m_str = (
            f"{float(sharpe_6m):.2f}"
            if pd.notna(sharpe_6m) and isinstance(sharpe_6m, (int, float))
            else "—"
        )


        dd_6m = row.get("Max DD 6M")
        if (
            pd.isna(dd_6m) or not isinstance(dd_6m, (int, float))
        ) and prices_df is not None:
            p_col = (
                sym
                if sym in prices_df.columns
                else (f"{sym}.NS" if f"{sym}.NS" in prices_df.columns else None)
            )
            if p_col is not None:
                sub_p = prices_df[p_col].dropna()
                if len(sub_p) >= 2:
                    win_6m = min(126, len(sub_p))
                    p_win = sub_p.iloc[-win_6m:]
                    roll_max = p_win.cummax()
                    dd_6m = float(((p_win - roll_max) / roll_max).min() * 100)
        dd_6m_str = (
            f"{float(dd_6m):.1f}%"
            if pd.notna(dd_6m) and isinstance(dd_6m, (int, float))
            else "—"
        )

        # Technicals & Filters
        pct_hi = row.get("% High")
        hi_str = (
            f"{float(pct_hi):.1f}%"
            if pd.notna(pct_hi) and isinstance(pct_hi, (int, float))
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

        # Data Health
        gap_val = str(row.get("Data Gap", "🟢"))
        gap_icon = "🔴" if "🔴" in gap_val else "🟢"

        ffill_val = row.get("FFill %")
        ffill_str = (
            f"{float(ffill_val):.1f}%"
            if pd.notna(ffill_val) and isinstance(ffill_val, (int, float))
            else "0.0%"
        )

        spark_svg = spark_map.get(sym, '<span class="text-muted">—</span>')

        # Every calendar window, formatted once. pc[3]["ret"] is the 3M return
        # cell, and so on; the Full Quant tier below renders all five.
        pc = {m: _period_cells(row, m) for m in PERIOD_WINDOWS}
        period_cells_html = "".join(
            f'<td class="td-num {pc[m]["clr"]}"><strong>{pc[m]["ret"]}</strong></td>'
            f'<td class="td-num td-sharpe">{pc[m]["sharpe"]}</td>'
            f'<td class="td-num td-dd">{pc[m]["dd"]}</td>'
            for m in PERIOD_WINDOWS
        )

        if is_exec:
            row_h = f"""<tr class="screener-row"><td class="sticky-col-rank"><strong>{rk}</strong></td><td class="sticky-col-symbol"><span class="stock-ticker">{sym}</span></td><td class="td-num"><strong>{cmp_str}</strong></td><td class="td-center">{d1m_html}</td><td class="td-center">{idx_html}</td><td class="td-sector" title="{ind_raw}">{ind_disp}</td><td class="td-num {ret_3m_clr}"><strong>{ret_3m_str}</strong></td><td class="td-num td-sharpe">{sharpe_3m_str}</td><td class="td-num">{hi_str}</td><td class="td-num">{ema_str}</td><td class="td-spark">{spark_svg}</td></tr>"""
        elif is_core:
            row_h = f"""<tr class="screener-row"><td class="sticky-col-rank"><strong>{rk}</strong></td><td class="sticky-col-symbol"><span class="stock-ticker">{sym}</span></td><td class="td-num"><strong>{cmp_str}</strong></td><td class="td-center">{d1m_html}</td><td class="td-center">{d3m_html}</td><td class="td-center">{idx_html}</td><td class="td-sector" title="{ind_raw}">{ind_disp}</td><td class="td-num">{mcap_str}</td><td class="td-num {ret_3m_clr}"><strong>{ret_3m_str}</strong></td><td class="td-num td-sharpe">{sharpe_3m_str}</td><td class="td-num {ret_6m_clr}"><strong>{ret_6m_str}</strong></td><td class="td-num td-sharpe">{sharpe_6m_str}</td><td class="td-num">{hi_str}</td><td class="td-num">{ema_str}</td><td class="td-center">{vol_badge}</td><td class="td-num td-sl">{sl_str}</td><td class="td-spark">{spark_svg}</td></tr>"""
        else:
            row_h = f"""<tr class="screener-row"><td class="sticky-col-rank"><strong>{rk}</strong></td><td class="sticky-col-symbol"><span class="stock-ticker">{sym}</span></td><td class="td-num"><strong>{cmp_str}</strong></td><td class="td-center">{d1m_html}</td><td class="td-center">{d3m_html}</td><td class="td-center">{idx_html}</td><td class="td-sector" title="{ind_raw}">{ind_disp}</td><td class="td-num">{mcap_str}</td>{period_cells_html}<td class="td-num">{hi_str}</td><td class="td-num">{ema_str}</td><td class="td-center">{vol_badge}</td><td class="td-center">{above_ema_icon}</td><td class="td-center">{near_hi_icon}</td><td class="td-num td-sl">{sl_str}</td><td class="td-num td-chand">{chand_str}</td><td class="td-center">{gap_icon}</td><td class="td-num">{ffill_str}</td><td class="td-spark">{spark_svg}</td></tr>"""
        rows_html.append(row_h)

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
        headers_block = """
            <tr class="group-header-row">
                <th colspan="3" class="sticky-group-id">IDENTITY</th>
                <th colspan="2">RANK DYNAMICS</th>
                <th colspan="3">CLASSIFICATION</th>
                <th colspan="2">3M MOMENTUM</th>
                <th colspan="2">6M MOMENTUM</th>
                <th colspan="3">FILTERS</th>
                <th>RISK</th>
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
                <th>STOP LOSS</th>
                <th class="th-center">60D SPARK</th>
            </tr>"""
    else:
        headers_block = """
            <tr class="group-header-row">
                <th colspan="3" class="sticky-group-id">IDENTITY</th>
                <th colspan="2">RANK DYNAMICS</th>
                <th colspan="3">CLASSIFICATION</th>
                <th colspan="3">1M FACTOR MOMENTUM</th>
                <th colspan="3">3M FACTOR MOMENTUM</th>
                <th colspan="3">6M FACTOR MOMENTUM</th>
                <th colspan="3">9M FACTOR MOMENTUM</th>
                <th colspan="3">12M FACTOR MOMENTUM</th>
                <th colspan="5">TECHNICALS & FILTERS</th>
                <th colspan="2">RISK & EXITS</th>
                <th colspan="2">DATA HEALTH</th>
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
                <th>% 50 EMA</th>
                <th class="th-center">VOLUME</th>
                <th class="th-center">&gt; 50 EMA</th>
                <th class="th-center">NEAR 52W</th>
                <th>STOP LOSS</th>
                <th>CHAND EXIT</th>
                <th class="th-center">GAP</th>
                <th>FFILL %</th>
                <th class="th-center">60D SPARK</th>
            </tr>"""

    # Master Table Assembly - Rendered via st.iframe with 2D Sticky Freeze
    full_page_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=JetBrains+Mono:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&family=Outfit:wght@500;600;700;800;900&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    background: transparent;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #0f172a;
    -webkit-font-smoothing: antialiased;
    padding: 2px;
}}
.modern-screener-wrapper {{
    width: 100%;
    max-height: {max_height}px;
    overflow: auto;
    border: 1px solid #e2e8f0;
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
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 12.5px;
    color: #0f172a;
    white-space: nowrap;
}}

/* ── Sticky Top Group Headers ── */
.modern-screener-table thead tr.group-header-row th {{
    position: sticky;
    top: 0;
    z-index: 20;
    background: #f8fafc;
    color: #64748b;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 7px 10px;
    border-bottom: 1px solid #e2e8f0;
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
    background: #f1f5f9;
    border-right: 1.5px solid #cbd5e1;
    box-shadow: 3px 0 6px rgba(0,0,0,0.04);
}}

/* ── Sticky Column Sub-Headers ── */
.modern-screener-table thead tr.sub-header-row th {{
    position: sticky;
    top: 28px;
    z-index: 20;
    background: #f8fafc;
    color: #334155;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 8px 10px;
    border-bottom: 2px solid #cbd5e1;
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
    background: #f1f5f9;
    min-width: 48px;
    max-width: 48px;
    width: 48px;
    text-align: center;
    border-right: 1px solid #e2e8f0;
}}
.modern-screener-table thead tr.sub-header-row th.sticky-col-symbol {{
    position: sticky;
    left: 48px;
    top: 28px;
    z-index: 35;
    background: #f1f5f9;
    min-width: 105px;
    max-width: 105px;
    width: 105px;
    text-align: left;
    border-right: 1.5px solid #cbd5e1;
    box-shadow: 3px 0 6px rgba(0,0,0,0.04);
}}

/* ── Table Body Rows ── */
.modern-screener-table tbody tr.screener-row {{
    border-bottom: 1px solid #f1f5f9;
    transition: background-color 0.12s ease;
}}
.modern-screener-table tbody tr.screener-row:hover td {{
    background-color: #f8fafc !important;
}}
.modern-screener-table td {{
    padding: 6px 10px;
    vertical-align: middle;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    border-bottom: 1px solid #f1f5f9;
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
    color: #0f172a;
    border-right: 1px solid #f1f5f9;
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
    border-right: 1.5px solid #e2e8f0;
    box-shadow: 3px 0 6px rgba(0,0,0,0.04);
}}

.stock-ticker {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-weight: 800;
    font-size: 11px;
    color: #0f172a;
    letter-spacing: 0.02em;
}}
.modern-screener-table td.td-center {{ text-align: center; }}
.modern-screener-table td.td-num {{ text-align: right; }}
.modern-screener-table td.td-sector {{
    text-align: left;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 12px;
    color: #475569;
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
    font-family: 'JetBrains Mono', monospace;
    font-size: 10.5px;
    font-weight: 700;
    padding: 1.5px 6px;
    border-radius: 5px;
}}
.badge-green {{
    background: #f0fdf4;
    color: #15803d;
}}
.badge-red {{
    background: #fef2f2;
    color: #b91c1c;
}}
.badge-neutral {{
    color: #64748b;
}}
.index-tag {{
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    background: #f1f5f9;
    color: #475569;
    padding: 1.5px 5px;
    border-radius: 4px;
    border: 1px solid #e2e8f0;
}}
.vol-tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    color: #059669;
}}
.vol-surge {{
    color: #4f46e5;
}}
.ret-pos {{ color: #15803d; font-weight: 700; }}
.ret-neg {{ color: #b91c1c; font-weight: 700; }}
.td-sharpe {{ color: #16a34a; font-weight: 600; }}
.modern-screener-table thead tr.sub-header-row th {{
    cursor: pointer;
    user-select: none;
    transition: background-color 0.15s ease, color 0.15s ease;
}}
.modern-screener-table thead tr.sub-header-row th:hover {{
    background-color: #e2e8f0 !important;
    color: #0f172a !important;
}}
.sort-indicator {{
    display: inline-block;
    margin-left: 4px;
    font-size: 8.5px;
    color: #4f46e5;
    vertical-align: middle;
}}
.td-dd {{ color: #dc2626; }}
.td-sl {{ color: #be123c; }}
.td-chand {{ color: #059669; font-weight: 600; }}
.text-muted {{ color: #94a3b8; font-size: 11px; }}
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

                if (txtA === '—' || txtA === '') return 1;
                if (txtB === '—' || txtB === '') return -1;

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


def render_saas_table(
    df: pd.DataFrame,
    key: str = "saas_table",
    max_height: int | None = None,
) -> None:
    """Renders a beautiful borderless SaaS table with sticky headers, interactive column sorting, and JetBrains Mono numerics."""
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
            headers_html.append(f'<th class="th-center">{col}</th>')
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
            headers_html.append(f'<th class="th-left">{col}</th>')
        else:
            headers_html.append(f'<th class="th-right">{col}</th>')

    rows_html = []
    for _, row in df.iterrows():
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
                    f'<td class="td-left"><span class="stock-ticker">{val}</span></td>'
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
                    f'<td class="td-center"><span class="badge-pill {q_badge}">{q_ico} {q_val}</span></td>'
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
                        f'<td class="td-center"><span class="badge-pill badge-neutral">{val}</span></td>'
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
                    if abs(val) <= 1.0 and val != 0:
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
                    if (
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
                    ):
                        cells_html.append(f'<td class="td-right {clr}">{val:.1%}</td>')
                    else:
                        cells_html.append(f'<td class="td-right {clr}">{val:.1f}%</td>')
                # 3. Currency / Prices (e.g. CMP, Entry Price, Exit Price, Value, Capital)
                elif any(
                    w in c_str
                    for w in [
                        "CMP",
                        "VALUE",
                        "PRICE",
                        "CAPITAL",
                        "MCAP",
                        "STOP LOSS",
                        "CHAND",
                        "ENTRY",
                        "EXIT",
                    ]
                ):
                    if abs(val) < 100 and abs(val) > 0:
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
                cells_html.append(f'<td class="td-left td-sector">{val}</td>')
            elif isinstance(val, bool):
                cells_html.append(
                    f'<td class="td-center">{"🟢 Yes" if val else "⚪ No"}</td>'
                )
            else:
                cells_html.append(f'<td class="td-left">{val}</td>')

        rows_html.append(f'<tr class="screener-row">{"".join(cells_html)}</tr>')

    saas_page_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=JetBrains+Mono:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&family=Outfit:wght@500;600;700;800;900&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    background: transparent;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #0f172a;
    -webkit-font-smoothing: antialiased;
    padding: 2px;
}}
.saas-table-wrapper {{
    width: 100%;
    max-height: {table_h}px;
    overflow: auto;
    border: 1px solid #e2e8f0;
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
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 12px;
    color: #0f172a;
    white-space: nowrap;
}}
.saas-table thead tr th {{
    position: sticky;
    top: 0;
    z-index: 10;
    background: #f8fafc;
    color: #475569;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 8px 10px;
    border-bottom: 1.5px solid #cbd5e1;
    border-left: none;
    border-right: none;
    cursor: pointer;
    user-select: none;
    transition: background-color 0.15s ease, color 0.15s ease;
}}
.saas-table thead tr th:hover {{
    background-color: #e2e8f0 !important;
    color: #0f172a !important;
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
    border-bottom: 1px solid #f1f5f9;
    transition: background-color 0.12s ease;
}}
.saas-table tbody tr.screener-row:hover td {{
    background-color: #f8fafc !important;
}}
.saas-table td {{
    padding: 7px 10px;
    vertical-align: middle;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    border-bottom: 1px solid #f1f5f9;
    border-left: none;
    border-right: none;
    background: #ffffff;
}}
.saas-table td.td-left {{ text-align: left; }}
.saas-table td.td-center {{ text-align: center; }}
.saas-table td.td-right {{ text-align: right; }}
.saas-table td.td-sector {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    color: #475569;
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.stock-ticker {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-weight: 800;
    font-size: 11px;
    color: #0f172a;
    letter-spacing: 0.02em;
}}
.badge-pill {{
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    padding: 1.5px 6px;
    border-radius: 5px;
}}
.badge-green {{ background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; }}
.badge-yellow {{ background: #fefce8; color: #a16207; border: 1px solid #fef08a; }}
.badge-red {{ background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }}
.badge-blue {{ background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }}
.badge-neutral {{ background: #f8fafc; color: #64748b; border: 1px solid #e2e8f0; }}
.ret-pos {{ color: #15803d; font-weight: 700; }}
.ret-neg {{ color: #b91c1c; font-weight: 700; }}
.td-sharpe {{ color: #16a34a; font-weight: 600; }}
.text-muted {{ color: #94a3b8; }}
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

                if (txtA === '—' || txtA === '') return 1;
                if (txtB === '—' || txtB === '') return -1;

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
