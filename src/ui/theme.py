import hashlib
import re
import time
from html import escape as _esc

import numpy as np
import pandas as pd
import streamlit as st

from src.ui.tokens import FONTS, css_root, resolve
from src.ui import formats as _fmt



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
    "MTD %": "{:+.1%}",
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
    """The page's CSS. Colours and fonts come from src/ui/tokens.py."""
    # The theme's colour variables first, so every rule below can read them,
    # in the same element: a markdown element of its own added an empty
    # block (about 14px) at the top of every page.
    st.markdown(
        # The skip link rides in this element too (audit F27): its own
        # st.html would add another empty block above the header.
        clean_html(f"<style>{css_root()}</style>"
                   '<a class="skip-link" href="#content">Skip to content</a>' + """
        <style>@import url('""" + FONTS["font_css"] + """');</style>

        <style>
        /* ── Design tokens: "Clear Ledger", light only ──────────────────
           The owner asked for a light app, so there is no dark override: a
           reader whose OS is in dark mode still gets the light palette the
           design was checked against (4.5:1 text contrast, 12px minimum). */
        :root {
            --c-bg: var(--c-white);
            --c-bg-subtle: var(--c-subtle);
            --c-border: var(--c-rule);
            --c-border-strong: var(--c-rule_strong);
            --c-text-primary: var(--c-ink);
            --c-text-secondary: var(--c-text_2);
            --c-text-muted: var(--c-muted);
            --c-accent-text: var(--c-ink);
            --c-bull-tint: var(--c-up_tint);
            --c-bear-tint: var(--c-down_tint);
            --font-ui: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            --font-display: var(--font-ui);
            --font-mono: 'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace;

            /* UI kit v2 scale: one set of steps for type, corners, depth and
               spacing, so identical kinds of block read with identical weight. */
            --fs-11: 11px; --fs-12: 12px; --fs-13: 13px; --fs-14: 14px;
            --fs-15: 15px; --fs-17: 17px; --fs-20: 20px; --fs-26: 26px;
            --r-sm: 6px; --r-md: 10px; --r-lg: 12px; --r-xl: 16px;
            --sh-1: 0 1px 2px rgba(14, 23, 38, 0.04);
            --sh-2: 0 4px 12px -2px rgba(14, 23, 38, 0.08);
            --sh-pop: 0 12px 32px -8px rgba(14, 23, 38, 0.18);
            --sp-1: 4px; --sp-2: 8px; --sp-3: 12px; --sp-4: 16px;
            --sp-5: 20px; --sp-6: 24px; --sp-8: 32px;
            --c-caution-tint: var(--c-caution_tint);
            --c-caution-ink: var(--c-caution_ink);
            --c-accent-tint: var(--c-fill);
        }

        /* ── Base Reset & Typography Hierarchy ── */
        html, body, [class*="css"] {
            font-family: var(--font-ui) !important;
            color: var(--c-ink) !important;
            background-color: var(--c-ground) !important;
            -webkit-font-smoothing: antialiased;
        }

        /* ── Typography Classes ── */
        .font-display, h1, h2, h3, h4, [data-testid="stMetricValue"] {
            font-family: var(--font-ui) !important;
            letter-spacing: -0.02em !important;
        }
        .font-mono, [data-testid="stMetricDelta"] {
            font-family: var(--font-mono) !important;
            font-variant-numeric: tabular-nums !important;
        }
        .font-code, code, pre {
            font-family: var(--font-mono) !important;
        }
.font-sans {
            font-family: var(--font-ui) !important;
        }

        /* ── Completely Hide Clunky Grey Native Scrollbars Everywhere (Across All 11 Tabs) ── */
        *, *::before, *::after {
            scrollbar-width: none !important;
            -ms-overflow-style: none !important;
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
            background-color: var(--c-white) !important;
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
            /* Use the full width already granted by Streamlit's native
               layout="wide" setting. All pages share this global container. */
            /* One reading width on wide screens (owner, 7 Nov, audit F38):
               1,240px of content, centred; the Screener table scrolls
               sideways inside it, with a fade at its edge. */
            max-width: calc(1240px + 3rem) !important;
            width: 100% !important;
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
                /* 16px a side (owner, 7 Nov, audit F38): text no longer
                   touches the bezel; it was 8px. */
                padding-left: 1rem !important;
                padding-right: 1rem !important;
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
                font-size: 12px !important;
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
            background-color: var(--c-subtle) !important;
            padding: 4px 5px !important;
            border-radius: 4px !important;
            border: 1px solid var(--c-rule) !important;
            box-shadow: none !important;
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
            border-radius: 4px !important;
            padding: 0 4px !important;
            background-color: transparent !important;
            border: 1px solid transparent !important;
            font-family: var(--font-ui) !important;
            font-size: 12.5px !important;
            font-weight: 600 !important;
            color: var(--c-muted) !important;
            white-space: nowrap !important;
            transition: all 0.15s ease !important;
            cursor: pointer !important;
        }

        .stTabs [data-baseweb="tab"]:hover {
            background-color: var(--c-white) !important;
            color: var(--c-ink) !important;
            border-color: var(--c-rule) !important;
        }

        .stTabs [aria-selected="true"] {
            background-color: var(--c-white) !important;
            color: var(--c-ink) !important;
            font-weight: 700 !important;
            border-color: var(--c-rule_strong) !important;
            box-shadow: none !important;
        }

        /* ── Responsive Header Navigation ──────────────────────────────
           Desktop exposes the full primary navigation directly. The compact
           popover is reserved for narrower viewports where the links no longer fit. */
        .st-key-app_header_shell {
            position: relative !important;
            margin: 6px 0 4px 0 !important;
            min-height: 60px !important;
            padding: 8px 14px !important;
            border: 1px solid var(--c-rule) !important;
            border-radius: 4px !important;
            background: var(--c-white) !important;
            box-shadow: none !important;
            overflow: visible !important;
            gap: 18px !important;
        }

        /* Brand: mark + name. */
        .hdr-title {
            font-family: var(--font-display); font-size: 17px; font-weight: 700;
            letter-spacing: -0.2px; color: var(--c-ink);
        }

        /* Brand: "Paresh Patel", a link home to the Screener. */
        .st-key-app_brand [data-testid="stPageLink"] a {
            padding: 4px 6px !important; background: transparent !important;
            text-decoration: none !important; border-radius: 4px !important;
        }
        .st-key-app_brand [data-testid="stPageLink"] a p,
        .st-key-app_brand [data-testid="stPageLink"] a span {
            font-family: var(--font-display) !important; font-size: 18px !important;
            font-weight: 700 !important; letter-spacing: -0.3px !important;
            color: var(--c-ink) !important; white-space: nowrap !important;
        }
        .st-key-app_brand [data-testid="stPageLink"] a:hover { background: var(--c-subtle) !important; }


        /* Data status pill. Green when every source is current, amber naming
           the stale one otherwise. */
        .hdr-pill {
            display: inline-flex; align-items: center; gap: 8px; white-space: nowrap;
            height: 32px; padding: 0 12px; border-radius: 4px;
            background: var(--c-up_tint); color: var(--c-up_dark); font-size: 13.5px; font-weight: 600;
        }
        .hdr-pill .hdr-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--c-up); }
        .hdr-pill-warn { background: var(--c-caution_tint); color: var(--c-caution_ink); }
        .hdr-pill-warn .hdr-dot { background: var(--c-caution); }
        .stale-notice { margin: 6px 0 2px; padding: 9px 14px; border-radius: 4px; background: var(--c-caution_tint); border: 1px solid var(--c-caution_line); color: var(--c-caution_ink); font-size: 13.5px; font-weight: 600; line-height: 1.4; }
        .stale-notice-info { background: var(--c-subtle); border-color: var(--c-rule); color: var(--c-text_2); font-weight: 500; }

        /* Compact market snapshot: same footprint as the legacy market line,
           but with a stronger visual hierarchy and the same design language as
           the rest of the page. Desktop stays one row; mobile becomes two
           compact rows without adding vertical bulk. */
        .mkt-snapshot {
            display: flex; align-items: stretch; flex-wrap: nowrap;
            min-height: 40px; margin: 4px 0 8px; overflow: hidden;
            border: 1px solid var(--c-rule); border-radius: 4px;
            background: var(--c-white);
        }
        .mkt-item {
            display: flex; align-items: center; gap: 7px;
            min-width: 0; padding: 7px 12px;
            border-right: 1px solid var(--c-rule_soft);
            color: var(--c-text_2); white-space: nowrap;
            font-size: 12.5px; line-height: 1.1;
        }
        .mkt-item:last-child { border-right: 0; }
        .mkt-item strong {
            color: var(--c-ink); font-weight: 600;
            font-variant-numeric: tabular-nums;
        }
        .mkt-label { color: var(--c-muted); font-weight: 500; }
        .mkt-item em {
            color: var(--c-muted); font-style: normal; font-weight: 500;
            margin-left: 2px;
        }
        .mkt-regime {
            display: inline-flex; align-items: center; gap: 5px;
            font-weight: 700;
        }
        .mkt-dot { font-size: 12px; }
        .mkt-up, .mkt-item strong.mkt-up { color: var(--c-up) !important; }
        .mkt-down, .mkt-item strong.mkt-down { color: var(--c-down) !important; }
        .mkt-regime.mkt-down { color: var(--c-down); }
        .mkt-regime.mkt-up { color: var(--c-up); }
        .mkt-regime-item { padding-left: 12px; padding-right: 14px; }
        .mkt-index { gap: 8px; }
        .mkt-index strong { font-family: var(--font-display); font-size: 15px; }
        .mkt-distance { gap: 5px; }
        .mkt-distance strong { font-size: 12.5px; }
        
        /* The menu button is the only navigation on every screen width
           (owner, 7 Nov); it sits at the right of the header. */
        .st-key-app_header_shell { padding-right: 60px !important; }
        @media (max-width: 640px) {
            .st-key-app_header_shell { min-height: 52px !important; padding: 6px 56px 6px 10px !important; gap: 10px !important; flex-wrap: nowrap !important; justify-content: space-between !important; }
            .hdr-pill-lead { display: none; }

            /* Mobile market snapshot — Concept 1: one compact horizontal row.
               Every metric remains intact; the strip scrolls horizontally rather
               than wrapping into a second row or truncating labels. */
            .mkt-snapshot {
                display: flex;
                flex-wrap: nowrap;
                align-items: stretch;
                min-height: 38px;
                margin: 3px 0 8px;
                border-radius: 4px;
                overflow-x: auto;
                overflow-y: hidden;
                scrollbar-width: none !important;
                -ms-overflow-style: none !important;
                -webkit-overflow-scrolling: touch;
            }
            .mkt-snapshot::-webkit-scrollbar { display: none !important; }
            /* The strip scrolls sideways with its scrollbar hidden, so the
               right edge fades to say there is more; the end padding lets the
               last item scroll clear of the fade. */
            .mkt-snapshot {
                -webkit-mask-image: linear-gradient(to right, #000 86%, transparent);
                mask-image: linear-gradient(to right, #000 86%, transparent);
                padding-right: 36px;
            }

            .mkt-item {
                flex: 0 0 auto;
                min-width: max-content;
                min-height: 38px;
                padding: 5px 9px;
                gap: 4px;
                border-right: 1px solid var(--c-rule_soft);
                font-size: 12px;
                line-height: 1.05;
                overflow: visible;
                justify-content: center;
            }

            /* No tint: a fixed red here painted "Bullish" and "3.1% above"
               red on a phone (owner, 7 Nov); the text colour carries the sign. */
            .mkt-regime-item {
                padding-left: 9px;
                padding-right: 10px;
            }
            .mkt-regime {
                gap: 4px;
                font-size: 12px;
            }
            .mkt-dot { font-size: 12px; }

            .mkt-index {
                gap: 5px;
                flex-direction: row;
                align-items: center;
                justify-content: center;
            }
            .mkt-index .mkt-label {
                display: inline;
                font-size: 12px;
                line-height: 1;
                overflow: visible;
                max-width: none;
            }
            .mkt-index strong {
                font-size: 12px;
                line-height: 1;
                overflow: visible;
                max-width: none;
            }

            .mkt-distance {
                gap: 4px;
                flex-direction: row;
                align-items: center;
                justify-content: center;
            }
            .mkt-distance .mkt-label {
                display: inline;
                font-size: 12px;
                line-height: 1;
                overflow: visible;
                max-width: none;
            }
            .mkt-distance strong {
                font-size: 12px;
                line-height: 1;
                overflow: visible;
                max-width: none;
            }

            /* Breadth metrics stay compact chips instead of becoming a second row. */
            .mkt-item:nth-child(n+4) {
                justify-content: center;
            }
            .mkt-item:nth-child(n+4) .mkt-label {
                font-size: 12px;
                line-height: 1;
                overflow: visible;
                max-width: none;
            }
            .mkt-item:nth-child(n+4) strong {
                font-size: 12px;
                line-height: 1;
                overflow: visible;
                max-width: none;
            }
            .mkt-item em { font-size: 12px; }
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
            border: 1px solid var(--c-rule) !important;
            border-radius: 4px !important;
            background: var(--c-subtle) !important;
            color: var(--c-text_2) !important;
            font-size: 18px !important;
            line-height: 1 !important;
        }

        [class*="st-key-app_nav_menu_"] button:hover {
            background: var(--c-white) !important;
            border-color: var(--c-rule_strong) !important;
            color: var(--c-ink) !important;
        }

        /* Page links inside the floating navigation menu. */
        [data-testid="stPopover"] [data-testid="stPageLink"] a,
        [data-testid="stPopoverBody"] [data-testid="stPageLink"] a {
            min-height: 38px !important;
            padding: 7px 10px !important;
            border-radius: 4px !important;
            color: var(--c-text_2) !important;
            text-decoration: none !important;
            font-family: var(--font-ui) !important;
            font-size: 13.5px !important;
            font-weight: 600 !important;
        }

        [data-testid="stPopover"] [data-testid="stPageLink"] a:hover,
        [data-testid="stPopoverBody"] [data-testid="stPageLink"] a:hover {
            background: var(--c-subtle) !important;
            color: var(--c-ink) !important;
        }

        [data-testid="stPopover"] [class*="st-key-navon_"] [data-testid="stPageLink"] a,
        [data-testid="stPopoverBody"] [class*="st-key-navon_"] [data-testid="stPageLink"] a {
            background: var(--c-fill) !important;
            color: var(--c-ink) !important;
            border: 1px solid var(--c-rule_strong) !important;
            font-weight: 700 !important;
        }

        /* ── Screener page (redesign phase 2) ─────────────────────────── */
        .scr-head h1 {
            margin: 0 !important; padding: 0 !important;
            font-family: var(--font-display) !important; font-size: 34px !important;
            font-weight: 700 !important; letter-spacing: -0.6px !important; color: var(--c-ink) !important;
        }
        .scr-head p { margin: 4px 0 0; font-size: 14px; color: var(--c-text_2); }
        .mkt-strip {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            background: var(--c-white); border: 1px solid var(--c-rule); border-radius: 4px; overflow: hidden;
        }
        .ms-tile { display: flex; flex-direction: column; gap: 6px; padding: 16px 20px; border-right: 1px solid var(--c-rule_soft); }
        .ms-tile:last-child { border-right: 0; }
        .ms-k { font-size: 12.5px; font-weight: 600; color: var(--c-muted); }
        .ms-v { font-family: var(--font-display); font-size: 26px; font-weight: 700; line-height: 1.1; color: var(--c-ink); }
        .ms-s { font-size: 13.5px; color: var(--c-text_2); line-height: 1.4; }
        .ms-s b { font-weight: 600; }
        .mkt-strip .up { color: var(--c-up); } .mkt-strip .down { color: var(--c-down); }
        .t50 { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
        .t50-grid { display:flex; flex-direction:column; gap:14px; width:100%; margin-top:4px; }
        .t50-card { width:100%; overflow:hidden; background:var(--c-white); border:1px solid var(--c-rule); border-radius:16px; box-shadow:0 1px 3px rgba(14,23,38,0.04); }
        .t50-card-head { display:flex; align-items:center; justify-content:space-between; gap:16px; min-height:82px; padding:16px 20px; background:var(--c-up_tint_2); border-bottom:1px solid var(--c-up_line); }
        .t50-card-heading { display:flex; align-items:center; gap:14px; min-width:0; }
        .t50-icon { flex:0 0 52px; width:52px; height:52px; display:grid; place-items:center; border-radius:10px; background:var(--c-up); color:var(--c-white); font-size:29px; font-weight:700; line-height:1; }
        .t50-card h2 { margin:0 !important; padding:0 !important; color:var(--c-ink) !important; font-family:var(--font-ui) !important; font-size:23px !important; font-weight: 700 !important; letter-spacing:-0.02em !important; }
        .t50-card p { margin:4px 0 0 !important; color:var(--c-muted) !important; font-size:13.5px !important; line-height:1.35 !important; }
        .t50-table-wrap { width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch; }
        .t50-table { width:100%; min-width:0; display:grid; font-family:var(--font-ui); }
        .t50-col-head, .t50-row { display:grid; grid-template-columns:52px minmax(150px,1.5fr) 1fr 1fr 0.9fr; align-items:center; column-gap:14px; padding:0 20px; }
        .t50-col-head { min-height:42px; background:var(--c-fill_soft); border-bottom:1px solid var(--c-rule); color:var(--c-muted); font-size:12px; font-weight: 600; }
        .t50-row { min-height:55px; border-bottom:1px solid var(--c-rule_soft); color:var(--c-ink); font-size:14px; }
        .t50-row:last-child { border-bottom:0; } .t50-row:hover { background:var(--c-fill_soft); }
        .t50-num { color:var(--c-muted); font-family:var(--font-mono); font-size:12px; } .t50-stock-cell { min-width:0; }
        .t50-stock { color:var(--c-ink) !important; text-decoration:none !important; font-weight:700; letter-spacing:0.01em; }
        .t50-stock:hover { color:var(--c-ink) !important; text-decoration:underline !important; }
        .t50-cell { min-width:0; } .t50-change,.t50-rank,.t50-return { font-family:var(--font-mono); font-variant-numeric:tabular-nums; }
        .t50-delta { font-weight: 700; } .t50-delta.positive { color:var(--c-up); } .t50-delta.negative { color:var(--c-down); } .t50-delta.flat { color:var(--c-muted); }
        .t50-return { font-weight:700; color:var(--c-up); } .t50-return.negative { color:var(--c-down); } .t50-return.flat { color:var(--c-muted); } .t50-trend { display:flex; align-items:center; height:36px; color:var(--c-up); }
        .t50-trend svg { width:132px; height:34px; display:block; } .t50-no-trend { color:var(--c-faint); }
        .t50-entered .t50-card-head { background:var(--c-up_tint_2); border-bottom-color:var(--c-up_line); } .t50-entered .t50-icon { background:var(--c-up); }
        .t50-left .t50-card-head { background:var(--c-down_tint_2); border-bottom-color:var(--c-down_line_2); } .t50-left .t50-icon { background:var(--c-down); }
        .t50-table:has(.t50-extra) .t50-row:last-child { border-bottom:1px solid var(--c-rule_soft); }
        .t50-more { margin:0; border-top:0; cursor:pointer; min-height:46px; padding:0 20px; display:flex; align-items:center; justify-content:center; gap:8px; color:var(--c-ink); font-size:13.5px; font-weight:700; }
        .t50-more:hover { background:var(--c-fill_soft); } .t50-more span span { font-size:17px; }
        .t50-toggle { position:absolute; opacity:0; width:1px; height:1px; pointer-events:none; }
        .t50-extra, .t50-when-open { display:none; }
        .t50-toggle:checked ~ .t50-table-wrap .t50-extra { display:grid; }
        .t50-toggle:checked ~ .t50-more .t50-when-closed { display:none; }
        .t50-toggle:checked ~ .t50-more .t50-when-open { display:inline; }
        .t50-toggle:focus-visible ~ .t50-more { outline:2px solid var(--c-ink); outline-offset:-2px; }
        .t50-note { margin:6px 2px 0; color:var(--c-muted); font-size:12px; line-height:1.4; }
        @media (max-width:640px) {
            .t50-grid { gap:10px; } .t50-card { border-radius:14px; } .t50-card-head { min-height:78px; padding:14px; gap:10px; }
            .t50-card-heading { gap:10px; } .t50-icon { flex-basis:44px; width:44px; height:44px; border-radius:9px; font-size:24px; }
            .t50-card h2 { font-size: 18px !important; } .t50-card p { font-size:12.5px !important; }
            .t50-col-head,.t50-row { padding:0 10px; column-gap:6px; grid-template-columns:28px minmax(120px,1.7fr) 72px 62px 58px; }
            .t50-col-head { min-height:38px; font-size: 12px; } .t50-row { min-height:50px; font-size:12px; } .t50-table { min-width:0; } .t50-change,.t50-rank,.t50-return { font-size: 12px; } .t50-num { font-size: 12px; }
        }
        /* Wide screens: the three movers cards side by side, compact, not
           three full-width tables of five rows each (owner, 13 Oct). */
        @media (min-width: 1100px) {
            .t50-grid { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:14px; align-items:start; }
            .t50-card-head { min-height:0; padding:12px 16px; }
            .t50-icon { flex-basis:34px; width:34px; height:34px; border-radius:8px; font-size: 18px; }
            .t50-card h2 { font-size:17px !important; }
            .t50-card p { font-size:12px !important; margin-top:2px !important; }
            .t50-col-head, .t50-row { grid-template-columns:22px minmax(0,1.5fr) 1fr 0.8fr 0.9fr; column-gap:8px; padding:0 14px; }
            .t50-col-head { min-height:34px; font-size: 12px; }
            .t50-row { min-height:40px; font-size: 13.5px; }
            .t50-more { min-height:38px; font-size: 13.5px; }
        }
        .st-key-scr_toolbar { gap: 10px !important; }
        .st-key-scr_toolbar [data-testid="stPopoverButton"] { height: 40px !important; }
        .sig-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
        .sig-chip {
            display: inline-flex; align-items: center; height: 30px; padding: 0 12px;
            border: 1px solid; border-radius: 4px; font-size: 13.5px; font-weight: 600;
            white-space: nowrap;
        }
        .st-key-scr_head { row-gap: 8px !important; }
        @media (max-width: 640px) {
            .scr-head h1 { font-size: 28px !important; }
            .scr-head p { font-size: 13.5px; }
            .sig-chip { height: 28px; font-size: 12px; white-space: normal; }
            /* One sideways-scrolling row of cards, so the list starts sooner. */
            .mkt-strip { display: flex; overflow-x: auto; background: transparent; border: 0; border-radius: 0; gap: 10px; }
            .ms-tile { flex: 0 0 158px; padding: 12px 14px; background: var(--c-white); border: 1px solid var(--c-rule) !important; border-radius: 4px; gap: 3px; }
            .st-key-dl_rank_csv { display: none !important; }
            /* Page figures read as a 2-wide block, not a sideways scroll. */
            .mkt-strip.pg-strip { display: grid; grid-template-columns: 1fr 1fr; overflow: visible; }
            .mkt-strip.pg-strip .ms-tile { flex: none; min-width: 0; }
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
            /* The preset chips scroll sideways too (stPills below): same fade. */
            .st-key-scr_toolbar [data-testid="stPills"] {
                -webkit-mask-image: linear-gradient(to right, #000 86%, transparent);
                mask-image: linear-gradient(to right, #000 86%, transparent);
                padding-right: 36px !important;
            }
        }

        /* ── Page kit (src/ui/page_kit.py): every other page ───────────── */
        /* Page KPI strip: centered, icon-free. However many tiles a page
           has (4 on Sectors, Actions, Breadth; 6 on Portfolio, Backtest),
           they share the row: a fixed 6-column grid left two empty columns
           beside four tiles, and squeezed long names into 4-line tiles
           (owner, 13 Oct). Narrower screens wrap to as many as fit. */
        .mkt-strip.pg-strip {
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        }
        .mkt-strip.pg-strip .ms-tile {
            align-items: center;
            justify-content: center;
            text-align: center;
            min-width: 0;
            gap: 4px;
            padding: 14px 16px;
        }
        .mkt-strip.pg-strip .ms-k,
        .mkt-strip.pg-strip .ms-v,
        .mkt-strip.pg-strip .ms-s {
            text-align: center;
            width: 100%;
        }
        .mkt-strip.pg-strip .ms-k { font-size: 13.5px; }
        .mkt-strip.pg-strip .ms-v { font-size: 26px; }
        /* A name, not a figure (an industry): smaller, at most two lines. */
        .mkt-strip.pg-strip .ms-v.ms-name {
            font-size: 18px; line-height: 1.2;
            display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
        }
        .mkt-strip.pg-strip .ms-s { font-size: 12.5px; line-height: 1.35; color: var(--c-muted); }
        .mkt-strip.pg-strip .ms-s:empty { display: none; }

        @media (max-width: 640px) {
            .mkt-strip.pg-strip {
                grid-template-columns: 1fr 1fr;
            }
            .mkt-strip.pg-strip .ms-tile { padding: 12px 10px; }
            .mkt-strip.pg-strip .ms-k { font-size: 12px; }
            .mkt-strip.pg-strip .ms-v { font-size: 21px; }
            .mkt-strip.pg-strip .ms-v.ms-name { font-size: 15px; }
            .mkt-strip.pg-strip .ms-s { font-size: 12px; }
        }
        .mkt-strip .warn { color: var(--c-caution); }
        .pg-note {
            padding: 12px 16px; border-radius: 4px; background: var(--c-caution_tint); border: 1px solid var(--c-caution_line);
            font-size: 13.5px; line-height: 1.5; color: var(--c-caution_ink);
        }
        .pg-note b { font-weight: 700; }
        [class*="st-key-pgcard_"] {
            background: var(--c-white); border: 1px solid var(--c-rule); border-radius: 4px;
            padding: 18px 22px !important; gap: 12px !important;
        }
        .pg-card-h { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
        .pg-card-h h2 {
            margin: 0 !important; padding: 0 !important; font-family: var(--font-ui) !important;
            font-size: 17px !important; font-weight: 600 !important; letter-spacing: 0 !important; color: var(--c-ink) !important;
        }
        .pg-card-h span { font-size: 12.5px; color: var(--c-muted); }
        .pg-cap { margin: 0; font-size: 12.5px; line-height: 1.5; color: var(--c-muted); }
        .pg-bars { display: flex; flex-direction: column; gap: 4px; }
        .pg-bar { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr) minmax(56px, auto); align-items: center; gap: 12px; min-height: 30px; }
        /* A long list (Portfolio's industries) runs in two columns on a wide
           card instead of one tall column with a half-empty row each. */
        @media (min-width: 1000px) {
            .pg-bars:has(> .pg-bar:nth-child(7)) { display: block; columns: 2; column-gap: 40px; }
            .pg-bars:has(> .pg-bar:nth-child(7)) .pg-bar { break-inside: avoid; margin-bottom: 4px; }
        }
        .pg-bar-l { font-size: 13.5px; color: var(--c-ink); }
        .pg-bar-t { position: relative; height: 10px; border-radius: 5px; background: var(--c-rule_soft); }
        .pg-bar-t i { position: absolute; left: 0; top: 0; height: 10px; border-radius: 5px; background: var(--c-ink); }
        .pg-bar-t i.warn { background: var(--c-caution); }
        .pg-bar-v { font-family: var(--font-mono); font-size: 13.5px; text-align: right; color: var(--c-ink); }
        @media (min-width: 641px) { .pg-bar-v { white-space: nowrap; } }
        [class*="st-key-pg_actions_"] { gap: 10px !important; }
        /* Exit watch */
        .xw { border: 1px solid var(--c-rule); border-radius: 4px; overflow: hidden; }
        .xw-row { display: grid; grid-template-columns: 150px 150px 1fr 1fr 1fr minmax(0, 1.4fr) 80px;
            gap: 16px; align-items: center; padding: 10px 16px; border-bottom: 1px solid var(--c-rule_soft); background: var(--c-white); }
        .xw-row:last-child { border-bottom: 0; }
        .xw-row:nth-child(odd):not(.xw-head) { background: var(--c-fill_soft); }
        .xw-row.sell { background: var(--c-white) !important; }
        .xw-head { min-height: 40px; padding-top: 6px; padding-bottom: 6px; background: var(--c-subtle) !important;
            font-size: 12px; font-weight: 600; color: var(--c-muted); }
        .xw-s { display: flex; flex-direction: column; min-width: 0; }
        .xw-s a { font-size: 14px; font-weight: 700; color: var(--c-ink) !important; text-decoration: none !important; }
        .xw-s a:hover { color: var(--c-ink) !important; }
        .xw-s small { font-size: 12px; color: var(--c-muted); white-space: normal; line-height: 1.3; }
        .xw-pill { justify-self: start; font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: 4px; white-space: nowrap; }
        .xw-pill.sell { background: var(--c-down_tint); color: var(--c-down); }
        .xw-pill.watch { background: var(--c-caution_tint); color: var(--c-caution_ink); }
        .xw-pill.clear { background: var(--c-up_tint); color: var(--c-up); }
        .xw-pill.unknown { background: var(--c-fill); color: var(--c-muted); }
        .xw-g { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
        .xw-g b { font-family: var(--font-mono); font-size: 13.5px; font-weight: 500; color: var(--c-ink); white-space: nowrap; }
        .xw-g > i { display: block; position: relative; height: 6px; border-radius: 3px; background: var(--c-rule_soft); }
        .xw-g > i > i { display: block; position: absolute; left: 0; top: 0; bottom: 0; border-radius: 3px; background: var(--c-up); }
        .xw-g.tight > i > i { background: var(--c-caution); }
        .xw-g.broken b { color: var(--c-down); }
        .xw-g.broken > i { background: var(--c-down_tint); }
        .xw-g.broken > i > i { background: var(--c-down); }
        .xw-why { font-size: 12.5px; line-height: 1.4; color: var(--c-text_2); }
        .xw-ret { font-family: var(--font-mono); font-size: 13.5px; text-align: right; }
        .xw-head .xw-ret, .xw-ret.hdr { font-family: var(--font-ui); font-size: 12px; }
        .xw-ret.up { color: var(--c-up); } .xw-ret.down { color: var(--c-down); }
        .st-key-xw_editbar { gap: 10px !important; }
        .ac-row { display: grid; align-items: center; gap: 16px; padding: 12px 16px; border-bottom: 1px solid var(--c-rule_soft); }
        .ac-row:last-child { border-bottom: 0; }
        .ac-row.sell { grid-template-columns: 170px minmax(0, 1fr) 130px 80px; background: var(--c-white); }
        .ac-row.buy { grid-template-columns: minmax(170px, 1fr) 80px 110px 80px 80px 110px; background: var(--c-up_tint_3); }
        .ac-row.ac-head { background: var(--c-subtle) !important; padding-top: 9px; padding-bottom: 9px; font-size: 12px; font-weight: 600; color: var(--c-muted); }
        .ac-row .n { font-family: var(--font-mono); font-size: 13.5px; text-align: right; }
        .ac-row .ac-head .n, .ac-head .n { font-family: var(--font-ui); font-size: 12px; }
        .ac-row .up { color: var(--c-up); }
        .ac-why { font-size: 13.5px; color: var(--c-ink); }
        .ac-why b { font-weight: 600; color: var(--c-down); }
        .ac-why b.up { color: var(--c-up); }
        .ac-when { font-size: 12.5px; color: var(--c-text_2); }
        .ac-next { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12.5px; color: var(--c-muted); }
        .t50-chip {
            display: inline-flex; align-items: center; gap: 7px; min-height: 30px;
            padding: 4px 10px 4px 6px; border-radius: 4px;
            background: var(--c-fill); color: var(--c-ink) !important;
            text-decoration: none !important; font-size: 12.5px; font-weight: 700;
            white-space: nowrap; border: 1px solid var(--c-rule);
            transition: background .15s ease, border-color .15s ease, transform .15s ease;
        }
        .t50-chip:hover {
            background: var(--c-rule_soft); border-color: var(--c-rule_strong); transform: translateY(-1px);
        }
        .t50-rank {
            display: inline-flex; align-items: center; justify-content: center;
            width: 22px; height: 22px; border-radius: 50%;
            background: var(--c-ink); color: var(--c-white); font-family: var(--font-mono);
            font-size: 12px; font-weight: 700; line-height: 1;
        }
        @media (max-width: 900px) {
            .ac-row.sell, .ac-row.buy { grid-template-columns: minmax(0, 1fr) auto; gap: 4px 12px; }
            .ac-row.ac-head { display: none; }
            .ac-row .ac-why { grid-column: 1 / -1; order: 3; }
            .ac-row.buy .n:not(:nth-of-type(2)) { display: none; }
            .ac-row.sell .ac-when { display: none; }
        }
        @media (max-width: 900px) {
            .xw-row { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px 10px; padding: 12px 14px; }
            .xw-head { display: none !important; }
            .xw-s { grid-column: 1 / 3; }
            .xw-pill { grid-column: 3; justify-self: end; }
            .xw-why { grid-column: 1 / -1; }
            .xw-ret { display: none; }
            .xw-g b { font-size: 12px; white-space: normal; }
        }
        /* Configuration, Ledger (audit F50): sections are open rows under an
           ink rule, no boxes, no tinted column, no shadow. */
        .cfg-index { display: flex; flex-wrap: wrap; gap: 4px 18px; padding: 2px 0 6px; }
        .cfg-index a {
            font-size: 13.5px; color: var(--c-ink) !important; text-decoration: none !important;
            border-bottom: 1px solid var(--c-rule_strong); padding: 2px 0;
        }
        .cfg-index a:hover, .cfg-index a:focus-visible { border-bottom-color: var(--c-ink); }
        [class*="st-key-cfgsec_"] {
            background: transparent; border: 0; border-top: 1px solid var(--c-ink); border-radius: 0;
            scroll-margin-top: 70px; padding: 0 !important; gap: 0 !important;
        }
        [class*="st-key-cfgsec_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] { gap: 0 !important; align-items: stretch; }
        [class*="st-key-cfgsec_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {
            background: transparent; border-right: 0; padding: 16px 24px 20px 0;
        }
        [class*="st-key-cfgsec_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {
            padding: 16px 0 24px;
        }
        .cfg-intro { display: flex; flex-direction: column; gap: 8px; scroll-margin-top: 80px; }
        .cfg-intro span { font-size: 12px; font-weight: 500; color: var(--c-muted); font-variant-numeric: tabular-nums; }
        .cfg-intro h2 { margin: 0 !important; padding: 0 !important; font-family: var(--font-ui) !important;
            font-size: 18px !important; font-weight: 600 !important; letter-spacing: 0 !important; color: var(--c-ink) !important; }
        .cfg-intro p { margin: 0; font-size: 13.5px; line-height: 1.55; color: var(--c-text_2); }
        .cfg-wbar-h { font-size: 13.5px; color: var(--c-ink); margin-bottom: 8px; }
        .cfg-wbar { display: flex; height: 26px; border-radius: 2px; overflow: hidden; gap: 2px; }
        .cfg-wbar span { display: flex; align-items: center; justify-content: center; font-size: 12px;
            font-weight: 500; white-space: nowrap; overflow: hidden; font-variant-numeric: tabular-nums; }
        [class*="st-key-cfgsec_"] .mkt-strip.pg-strip { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
        [class*="st-key-cfgsec_"] .mkt-strip.pg-strip .ms-tile { min-height: 0; padding: 14px 12px; }
        [class*="st-key-cfgsec_"] .mkt-strip.pg-strip .ms-v { font-size: 20px; }
        [class*="st-key-cfgsec_"] .mkt-strip.pg-strip .ms-s { font-size: 13.5px; }
        .pg-kv {
            display: flex; flex-wrap: wrap; align-items: center; gap: 8px 22px; padding: 10px 0; margin: 0 0 14px;
            background: transparent; border: 0; border-top: 1px solid var(--c-rule); border-bottom: 1px solid var(--c-rule);
            border-radius: 0; font-size: 13.5px; color: var(--c-text_2);
        }
        .pg-kv > b { font-size: 13.5px; font-weight: 600; color: var(--c-muted); }
        .pg-kv span b { color: var(--c-ink); font-weight: 600; }
        .cfg-rule { height: 1px; background: var(--c-rule_soft); margin: 4px 0; }
        .cfg-sub { font-size: 14px; font-weight: 600; color: var(--c-ink); margin-top: 6px; }
        .st-key-cfg_sync_row { gap: 10px !important; flex-wrap: wrap; }
        @media (max-width: 760px) {
            [class*="st-key-cfgsec_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {
                border-right: 0; padding: 14px 0 4px;
            }
            [class*="st-key-cfgsec_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child { padding: 8px 0 20px; }
        }
        .bt-sum {
            display: flex; flex-wrap: wrap; align-items: center; gap: 8px 22px; padding: 10px 0;
            background: transparent; border: 0; border-top: 1px solid var(--c-rule); border-bottom: 1px solid var(--c-rule);
            border-radius: 0; font-size: 13.5px; color: var(--c-text_2);
        }
        .bt-sum > b { font-size: 13.5px; font-weight: 600; color: var(--c-muted); }
        .bt-sum span b { color: var(--c-ink); font-weight: 600; }
        .gc-legend { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13.5px; color: var(--c-text_2); }
        .gc-legend span { display: inline-flex; align-items: center; gap: 6px; }
        .gc-legend i { width: 14px; height: 3px; border-radius: 2px; background: var(--c-faint); }
        .gc-ls i { background: var(--c-ink) !important; }
        .gc-legend b { font-family: var(--font-mono); font-weight: 600; color: var(--c-ink); }
        .mo-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 10px; }
        .mo { padding: 12px 14px; border-radius: 4px; display: flex; flex-direction: column; gap: 3px; background: var(--c-subtle); }
        .mo.up { background: var(--c-up_tint); } .mo.down { background: var(--c-down_tint); }
        .mo.live { background: var(--c-white); border: 1.5px dashed var(--c-rule_strong); }
        .mo-h { display: flex; justify-content: space-between; gap: 8px; font-size: 12.5px; font-weight: 600; color: var(--c-text_2); }
        .mo-h em { font-style: normal; font-size: 12px; font-weight: 600; padding: 1px 6px; border-radius: 4px; background: rgba(255,255,255,0.7); color: var(--c-muted); }
        .mo-v { font-family: var(--font-mono); font-size: 18px; font-weight: 600; }
        .mo-v.up { color: var(--c-up); } .mo-v.down { color: var(--c-down); }
        .mo-s { font-size: 12px; color: var(--c-text_2); }
        /* Sectors: industry leaderboard */
        .ib { border: 1px solid var(--c-rule); border-radius: 4px; overflow: hidden; }
        .ib-row {
            display: grid; align-items: center; gap: 12px; padding: 0 16px; min-height: 46px;
            grid-template-columns: 32px minmax(0, 1.6fr) 56px 190px 76px 96px 104px 76px 72px minmax(0, 1.3fr);
            border-bottom: 1px solid var(--c-rule_soft); font-size: 14px; background: var(--c-white);
        }
        .ib-row:nth-child(odd):not(.ib-head) { background: var(--c-fill_soft); }
        .ib-row:last-child { border-bottom: 0; }
        .ib-head { min-height: 40px; background: var(--c-subtle) !important; font-size: 12px; font-weight: 600; color: var(--c-muted); }
        .ib-head .ib-num { font-family: var(--font-ui); font-size: 12px; }
        .ib-n { font-family: var(--font-mono); font-weight: 600; }
        .ib-name { display: flex; flex-direction: column; min-width: 0; }
        .ib-name b { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .ib-name small { display: none; font-size: 12px; color: var(--c-muted); }
        .ib-num { font-family: var(--font-mono); font-size: 13.5px; text-align: right; }
        .ib-3m { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
        .ib-3m b { font-family: var(--font-mono); font-size: 13.5px; font-weight: 500; width: 62px; text-align: right; }
        .ib-bar { position: relative; width: 96px; height: 8px; border-radius: 4px; background: var(--c-rule_soft); }
        .ib-bar i { position: absolute; top: 0; height: 8px; border-radius: 4px; background: var(--c-faint); }
        .ib-bar i.up { background: var(--c-up); } .ib-bar i.down { background: var(--c-down); }
        .ib-bar em { position: absolute; left: 50%; top: -2px; width: 1px; height: 12px; background: var(--c-faint); }
        .ib .up { color: var(--c-up); } .ib .down { color: var(--c-down); }
        .ib-leads { display: flex; gap: 6px; overflow: hidden; }
        .ib-lead {
            font-size: 12px; font-weight: 600; padding: 2px 7px; border-radius: 4px; background: var(--c-subtle);
            color: var(--c-ink) !important; text-decoration: none !important; white-space: nowrap;
        }
        .ib-lead:hover { background: var(--c-fill); }
        @media (max-width: 1100px) { .ib-leads, .ib-head .ib-d:last-child { display: none; } .ib-row { grid-template-columns: 32px minmax(0, 1.6fr) 56px 190px 76px 96px 104px 76px 72px; } }
        @media (max-width: 760px) {
            .ib-row { grid-template-columns: 24px minmax(0, 1fr) 80px; padding: 8px 12px; }
            .ib-d { display: none !important; }
            .ib-name small { display: block; }
            .ib-bar { display: none; }
            .ib-head .ib-3m { justify-content: flex-end; }
        }
        @media (max-width: 640px) {
            [class*="st-key-pgcard_"] { padding: 14px 14px !important; border-radius: 4px; }
            .pg-bar { grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) 64px; gap: 8px; }
            /* Four figures read as a 2 x 2 block, not four tall tiles. */
            [class*="st-key-mrow_"] { display: grid !important; grid-template-columns: 1fr 1fr; gap: 8px !important; }
            [class*="st-key-mrow_"] > div { width: auto !important; min-width: 0 !important; }
            [class*="st-key-mrow_"] [data-testid="stMetric"] { padding: 10px 12px !important; }
            [class*="st-key-mrow_"] [data-testid="stMetricLabel"] { font-size: 12px; }
        }

        /* The watchlist bridge has no visible output. */
        .st-key-wl_store { display: none !important; }

        /* ── Stock page (redesign phase 3) ────────────────────────────── */
        .st-key-stock_page_back button {
            border: 0 !important; background: transparent !important; padding: 0 !important;
            min-height: 32px !important; color: var(--c-ink) !important; font-weight: 600 !important;
        }
        .st-key-stock_page_back button:hover { color: var(--c-ink) !important; text-decoration: underline; }
        .sp-card { background: var(--c-white); border: 1px solid var(--c-rule); border-radius: 18px; padding: 20px 22px; }
        .sp-card h2, .sp-sec h2 {
            margin: 0 !important; padding: 0 !important; font-family: var(--font-ui) !important;
            font-size: 17px !important; font-weight: 600 !important; letter-spacing: 0 !important; color: var(--c-ink) !important;
        }
        .sp-hero { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 16px; margin-bottom: 14px; }
        .sp-id { display: flex; flex-direction: column; gap: 10px; }
        .sp-chips { display: flex; gap: 8px; flex-wrap: wrap; }
        .sp-sym { font-family: var(--font-mono); font-size: 13.5px; font-weight: 600; padding: 4px 9px; border-radius: 4px; background: var(--c-ink); color: var(--c-white); }
        .sp-tag { font-size: 12.5px; font-weight: 600; padding: 4px 9px; border-radius: 4px; background: var(--c-fill); color: var(--c-text_2); }
        .sp-cls { font-size: 13.5px; color: var(--c-muted); }
        h1.sp-name {
            margin: 0 !important; padding: 0 !important; font-family: var(--font-display) !important;
            font-size: 38px !important; font-weight: 700 !important; letter-spacing: -0.8px !important;
            line-height: 1.1 !important; color: var(--c-ink) !important;
        }
        .sp-price-row { display: flex; align-items: flex-end; gap: 22px; flex-wrap: wrap; }
        .sp-price-col { display: flex; flex-direction: column; gap: 4px; }
        .sp-price { font-family: var(--font-mono); font-size: 36px; font-weight: 600; color: var(--c-ink); line-height: 1.1; }
        .sp-close { font-size: 13.5px; color: var(--c-muted); }
        .sp-changes { display: flex; gap: 8px; flex-wrap: wrap; padding-bottom: 4px; }
        .sp-changes { display: flex; gap: 8px; flex-wrap: wrap; padding-bottom: 2px; }
        .sp-chg { min-width: 82px; display: flex; flex-direction: column; gap: 2px; padding: 7px 11px; border-radius: 4px; }
        .sp-chg i { font-style: normal; font-size: 12px; font-weight: 600; color: var(--c-muted); }
        .sp-chg b { font-family: var(--font-mono); font-size: 13.5px; font-weight: 700; }
        .sp-chg.up { background: var(--c-up_tint); color: var(--c-up); } .sp-chg.down { background: var(--c-down_tint); color: var(--c-down); }
        .sp-chg.flat { background: var(--c-fill); color: var(--c-muted); }
        .sp-rank { display: flex; flex-direction: column; gap: 10px; }
        .sp-k { font-size: 12.5px; font-weight: 600; color: var(--c-muted); }
        .sp-rank-big { display: flex; align-items: baseline; gap: 10px; }
        .sp-rank-big span { font-family: var(--font-display); font-size: 56px; font-weight: 700; line-height: 1; color: var(--c-ink); }
        .sp-rank-big i { font-style: normal; font-size: 15px; color: var(--c-text_2); }
        .sp-path { display: flex; align-items: center; gap: 6px; }
        .sp-step { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 6px 8px; border-radius: 4px; background: var(--c-subtle); min-width: 50px; }
        .sp-step b { font-family: var(--font-mono); font-size: 13.5px; color: var(--c-ink); }
        .sp-step i { font-style: normal; font-size: 12px; color: var(--c-muted); }
        .sp-step.now { background: var(--c-fill); } .sp-step.now b { color: var(--c-ink); }
        .sp-arrow { color: var(--c-faint); font-size: 12px; }
        .sp-facts { display: flex; gap: 16px; flex-wrap: wrap; font-size: 13.5px; color: var(--c-text_2); }
        .sp-facts b { font-family: var(--font-mono); font-weight: 600; color: var(--c-ink); }
        .sp-verdict { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); grid-template-rows: auto 1fr; border-radius: 4px; margin-bottom: 14px; border: 1px solid; overflow: hidden; }
        .sp-verdict.pass { background: var(--c-up_tint_2); border-color: var(--c-up_line_2); }
        .sp-verdict.part { background: var(--c-caution_tint); border-color: var(--c-caution_line); }
        .sp-verdict.fail { background: var(--c-down_tint_2); border-color: var(--c-down_line_3); }
        .sv-head { grid-column: 1 / -1; display: flex; align-items: center; gap: 12px; padding: 16px 20px; border-bottom: 1px solid rgba(14, 23, 38, 0.08); }
        .sv-head-mark { width: 38px; height: 38px; flex-shrink: 0; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: var(--c-white); font-weight: 700; font-size: 18px; background: var(--c-up); }
        .sp-verdict.part .sv-head-mark { background: var(--c-caution); } .sp-verdict.fail .sv-head-mark { background: var(--c-down); }
        .sv-head b { display: block; font-family: var(--font-ui); font-size: 14px; line-height: 1.2; font-weight: 700; color: var(--c-ink); }
        .sv-head i { display: block; margin-top: 2px; font-family: var(--font-ui); font-style: normal; font-size: 12px; line-height: 1.25; color: var(--c-text_2); }
        .sv-state { margin-left: auto; padding: 9px 18px; border-radius: 4px; background: var(--c-up_tint); color: var(--c-up); font-weight: 700; font-size: 13.5px; }
        .sp-verdict.part .sv-state { background: var(--c-caution_tint); color: var(--c-caution); } .sp-verdict.fail .sv-state { background: var(--c-down_line); color: var(--c-down); }
        .sv-card { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 12px; padding: 18px 20px; min-width: 0; }
        .sv-card + .sv-card { border-left: 1px solid rgba(14, 23, 38, 0.08); }
        .sv-main { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
        .sv-k { font-size: 12px; line-height: 1.2; font-weight: 600; color: var(--c-ink); }
        .sv-main strong { font-family: var(--font-display); font-size: 18px; line-height: 1.1; font-weight: 700; color: var(--c-up); white-space: nowrap; }
        .sp-verdict.fail .sv-main strong { color: var(--c-down); }
        .sv-price { font-family: var(--font-mono); font-size: 14px; line-height: 1.2; font-weight: 600; color: var(--c-ink); }
        .sv-side { min-width: 72px; display: flex; flex-direction: column; align-items: flex-end; gap: 3px; padding-left: 14px; border-left: 1px solid rgba(14, 23, 38, 0.08); }
        .sv-side em { font-style: normal; font-size: 13.5px; font-weight: 700; padding: 8px 14px; border-radius: 4px; background: var(--c-up_tint); color: var(--c-up); }
        .sv-side em.fail { background: var(--c-down_line); color: var(--c-down); }
        .sv-side em.bonus { background: var(--c-caution_tint); color: var(--c-caution); }
        .sv-side span { font-size: 12px; color: var(--c-muted); }
        .sv-side b { font-family: var(--font-mono); font-size: 14px; font-weight: 600; color: var(--c-text_2); text-align: right; }
        .sp-notice { background: var(--c-caution_tint); border: 1px solid var(--c-caution_line); border-radius: 4px; padding: 16px 20px; margin-bottom: 14px; color: var(--c-caution_ink); }
        .sp-exit { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; margin: 4px 0 14px; padding: 0 2px; color: var(--c-ink); line-height: 1.45; }
        .sp-exit .lbl { color: var(--c-ink); }
        .sp-exit b { font-weight: 700; }
        .sp-exit span { color: var(--c-ink); }
        .sp-exit a { margin-left: 2px; color: var(--c-ink) !important; text-decoration: none !important; white-space: nowrap; }
        .sp-exit a:hover { text-decoration: underline !important; }
        .sp-notice p { margin: 6px 0 0; font-size: 14px; line-height: 1.5; color: var(--c-text_2); }
        .sp-sec { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin: 6px 2px 6px; }
        .sp-sec span { font-size: 12.5px; color: var(--c-muted); }
        .sp-ladder { margin: 14px 0; }
        .sp-range { margin: 16px 0 6px; }
        .sp-range .track { position: relative; height: 10px; border-radius: 5px; background: var(--c-rule_soft); }
        .sp-range .fill { height: 10px; border-radius: 5px; background: linear-gradient(90deg, var(--c-rule_strong), var(--c-ink)); }
        .sp-range .dot { position: absolute; top: -4px; width: 18px; height: 18px; margin-left: -9px; border-radius: 50%; background: var(--c-ink); border: 3px solid var(--c-white); box-shadow: none; box-sizing: border-box; }
        /* Marks ON the bar only. Unscoped, this also took the legend's two
           swatches out of the legend: they floated above the section as a
           stray "|" under the chart, and the legend lost its colours. */
        .sp-range .track i.m-line, .sp-range .track i.m-ema { position: absolute; top: -5px; width: 3px; height: 20px; margin-left: -1.5px; border-radius: 1px; }
        .sp-range i.m-line { background: var(--c-caution); }
        .sp-range i.m-ema { background: var(--c-ink); }
        .sp-range .ends { display: flex; justify-content: space-between; gap: 10px; margin-top: 8px; font-size: 12.5px; color: var(--c-muted); flex-wrap: wrap; }
        .sp-range .key { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
        .sp-range .key i { display: inline-block; position: static; width: 3px; height: 12px; margin-left: 6px; border-radius: 1px; }
        .sp-ladder .list { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 10px; margin-top: 14px; }
        .sp-ladder .li { display: flex; flex-direction: column; gap: 3px; padding: 12px 14px; border-radius: 4px; background: var(--c-white); }
        .sp-ladder .lk { font-size: 12.5px; font-weight: 600; color: var(--c-text_2); }
        .sp-ladder .lv { font-family: var(--font-mono); font-size: 17px; font-weight: 600; color: var(--c-ink); }
        .sp-ladder .lv.up { color: var(--c-up); } .sp-ladder .lv.down { color: var(--c-down); } .sp-ladder .lv.warn { color: var(--c-caution); }
        .sp-ladder .ls { font-size: 12.5px; color: var(--c-muted); }
        .sp-gp { margin-bottom: 14px; }
        .gp-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
        .gp-legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 12.5px; color: var(--c-muted); }
        .gp-legend span { display: flex; align-items: center; gap: 6px; }
        .gp-legend i { display: inline-block; }
        .gp-legend .k-dd { width: 12px; height: 12px; border-radius: 3px; background: var(--c-down_line_4); }
        .gp-legend .k-ret { width: 12px; height: 12px; border-radius: 3px; background: var(--c-up); }
        .gp-legend .k-nb { width: 14px; height: 4px; border-radius: 2px; background: var(--c-faint); }
        .gp-legend .k-med { width: 0; height: 14px; border-left: 2px dashed var(--c-muted); }
        .gp-row { display: grid; grid-template-columns: 96px minmax(150px, 290px) 1px minmax(0, 1fr) 140px 110px; align-items: center; min-height: 62px; border-bottom: 1px solid var(--c-fill); }
        .gp-row.gp-hdr { min-height: 30px; font-size: 12px; font-weight: 600; color: var(--c-muted); border-bottom: 1px solid var(--c-rule_soft); }
        .gp-row.gp-hdr .r { text-align: right; padding-right: 10px; }
        .gp-row.gp-hdr span:nth-child(4) { padding-left: 10px; }
        .gp-w b { display: block; font-size: 15px; font-weight: 600; }
        .gp-w i { display: block; font-style: normal; font-size: 12px; color: var(--c-muted); }
        .gp-dd { position: relative; height: 28px; margin-right: 10px; }
        .gp-dd .bar { position: absolute; right: 0; top: 4px; height: 20px; border-radius: 4px 0 0 6px; background: var(--c-down_line_4); }
        .gp-dd .lbl { position: absolute; top: 5px; font-family: var(--font-mono); font-size: 12.5px; font-weight: 600; color: var(--c-down); white-space: nowrap; }
        .gp-med { position: absolute; top: -2px; height: 32px; z-index: 1; border-left: 2px dashed var(--c-muted); }
        .gp-axis { height: 44px; background: var(--c-ink); }
        .gp-ret { position: relative; height: 34px; margin: 0 20px 0 10px; }
        .gp-ret .bar { position: absolute; left: 0; top: 2px; height: 18px; border-radius: 0 6px 6px 0; background: linear-gradient(90deg, var(--c-up), var(--c-up)); }
        .gp-ret .bar.neg { background: var(--c-down_line_4); }
        .gp-ret .lbl { position: absolute; top: 2px; font-family: var(--font-mono); font-size: 13.5px; font-weight: 700; color: var(--c-up_dark); white-space: nowrap; }
        .gp-ret .lbl.neg { color: var(--c-down); }
        .gp-ret .nb { position: absolute; left: 0; top: 25px; height: 4px; border-radius: 0 2px 2px 0; background: var(--c-faint); }
        .gp-ret .nl { position: absolute; top: 20px; font-size: 12px; color: var(--c-muted); white-space: nowrap; }
        .gp-sh { display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding-right: 10px; }
        .gp-sh .dots { display: flex; gap: 3px; }
        .gp-sh .dots i { width: 9px; height: 9px; border-radius: 50%; background: var(--c-rule); }
        .gp-sh .dots i.on { background: var(--c-ink); } .gp-sh .dots i.half { background: rgba(79, 70, 229, 0.35); }
        .gp-sh b { font-family: var(--font-mono); font-size: 15px; font-weight: 600; width: 42px; text-align: right; }
        .gp-top { display: flex; justify-content: flex-end; padding-right: 4px; }
        .gp-top em { font-style: normal; font-size: 12px; font-weight: 700; padding: 3px 8px; border-radius: 4px; }
        .gp-top em.good { background: var(--c-up_tint); color: var(--c-up_dark); } .gp-top em.poor { background: var(--c-fill); color: var(--c-text_2); }
        .gp-foot { padding-top: 10px; font-size: 12.5px; color: var(--c-muted); line-height: 1.5; }
        .sp-peers { padding: 0; overflow: hidden; margin-bottom: 14px; }
        .sp-peers .ph { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 16px 20px; }
        .sp-peers .ph span { font-size: 13.5px; color: var(--c-muted); }
        .sp-peers .tw { overflow-x: auto; }
        .sp-peers table { width: 100%; border-collapse: collapse; }
        .sp-peers th { background: var(--c-subtle); font-size: 12px; font-weight: 600; color: var(--c-muted); text-align: right; padding: 10px 16px; border-top: 1px solid var(--c-rule); border-bottom: 1px solid var(--c-rule); white-space: nowrap; }
        .sp-peers td { padding: 12px 16px; text-align: right; font-family: var(--font-mono); font-size: 13.5px; border-bottom: 1px solid var(--c-rule_soft); white-space: nowrap; }
        .sp-peers .l { text-align: left; }
        .sp-peers td.s { font-family: var(--font-ui); font-weight: 600; }
        .sp-peers td.s a { color: var(--c-ink) !important; text-decoration: none !important; }
        .sp-peers td.s a:hover { color: var(--c-ink) !important; }
        .sp-peers td.s em { margin-left: 8px; font-style: normal; font-size: 12px; font-weight: 700; padding: 2px 7px; border-radius: 4px; background: var(--c-fill); color: var(--c-ink); }
        .sp-peers tr.hl td { background: var(--c-subtle); }
        .sp-peers .up { color: var(--c-up); } .sp-peers .down { color: var(--c-down); }
        .sp-checks { display: flex; flex-wrap: wrap; gap: 8px; }
        .sp-checks span { font-size: 13.5px; padding: 8px 12px; border-radius: 4px; background: var(--c-white); color: var(--c-text_2); }
        .sp-checks span.bad { background: var(--c-caution_tint); color: var(--c-caution_ink); font-weight: 600; }
        @media (max-width: 900px) {
            .sp-hero { grid-template-columns: 1fr; }
            .sp-verdict { grid-template-columns: 1fr; }
            .sv-head { grid-column: auto; }
            .sv-card + .sv-card { border-left: 0; border-top: 1px solid rgba(14, 23, 38, 0.08); }
            .sp-path { gap: 4px; }
            .sp-step { min-width: 46px; padding: 6px 5px; }
            .sp-step b { font-size: 12.5px; }
        }
        @media (max-width: 640px) {
            .sp-card { padding: 16px; border-radius: 4px; }
            .sp-exit { gap: 6px; font-size: 14px; line-height: 1.5; }
            .sp-exit .lbl, .sp-exit b, .sp-exit span, .sp-exit a { display: inline; }
            h1.sp-name { font-size: 28px !important; }
            .sp-price { font-size: 30px; }
            .sp-rank-big span { font-size: 44px; }
            .sp-path { width: 100%; justify-content: space-between; }
            .sp-step { flex: 1 1 0; min-width: 0; max-width: 72px; }
            .sp-arrow { flex: 0 0 auto; }
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
            .gp-ret .lbl { left: auto !important; right: -76px; width: 72px; text-align: right; font-size: 13.5px; }
            .gp-ret .nb { top: 21px; }
            .gp-dd { grid-area: dd; margin: 0 78px 0 0; height: 14px; }
            .gp-dd .bar { left: 0; right: auto; top: 2px; height: 10px; border-radius: 0 5px 5px 0; }
            .gp-dd .lbl { right: -76px !important; width: 72px; text-align: right; top: -2px; font-size: 12px; }
            .sp-ladder .list { grid-template-columns: 1fr 1fr; }
        }

        /* ── Stock page in Ledger (audit F49) ─────────────────────────
           Cards open under an ink rule, the verdict a ruled band without a
           tint, figures in Plex Sans tabular (decision 4), labels in words
           and colour rather than filled chips. */
        .sp-card { background: transparent; border: 0; border-top: 1px solid var(--c-ink); border-radius: 0; padding: 14px 0 18px; }
        .sp-hero { gap: 40px; margin-bottom: 8px; }
        .sp-card h2, .sp-sec h2 { font-size: 17px !important; font-weight: 600 !important; }
        h1.sp-name { font-size: 34px !important; font-weight: 600 !important; letter-spacing: -0.4px !important; }
        .sp-sym { font-family: var(--font-ui); font-weight: 600; }
        .sp-price { font-family: var(--font-ui); font-size: 32px; font-weight: 600; font-variant-numeric: tabular-nums; }
        .sp-chg, .sp-chg.up, .sp-chg.down, .sp-chg.flat { background: transparent; padding: 0 16px 0 0; min-width: 0; border-radius: 0; }
        .sp-chg i { font-weight: 500; }
        .sp-chg b { font-family: var(--font-ui); font-size: 15px; font-weight: 600; font-variant-numeric: tabular-nums; }
        .sp-rank-big span { font-size: 48px; font-weight: 600; font-variant-numeric: tabular-nums; }
        .sp-step, .sp-step.now { background: transparent; border: 1px solid var(--c-rule); }
        .sp-step.now { border-color: var(--c-ink); }
        .sp-step b, .sp-facts b, .sv-price, .sv-side b { font-family: var(--font-ui); font-variant-numeric: tabular-nums; }
        .sp-verdict, .sp-verdict.pass, .sp-verdict.part, .sp-verdict.fail {
            background: transparent; border: 0; border-top: 1px solid var(--c-ink); border-bottom: 1px solid var(--c-rule); border-radius: 0;
        }
        .sv-head { padding: 12px 0; border-bottom: 1px solid var(--c-rule); }
        .sv-head-mark { width: 26px; height: 26px; font-size: 14px; font-weight: 600; }
        .sv-state, .sp-verdict.part .sv-state, .sp-verdict.fail .sv-state { background: transparent; padding: 0; font-weight: 600; }
        .sp-verdict.part .sv-state { color: var(--c-caution); }
        .sv-card { padding: 14px 20px 14px 0; }
        .sv-card + .sv-card { border-left: 1px solid var(--c-rule); padding-left: 20px; }
        .sv-main strong { font-family: var(--font-ui); font-weight: 600; font-variant-numeric: tabular-nums; }
        .sv-side { border-left: 0; }
        .sv-side em, .sv-side em.fail, .sv-side em.bonus { background: transparent; padding: 0; font-weight: 600; }
        .sv-side em.bonus { color: var(--c-caution); }
        .sv-k { font-weight: 600; }
        .sp-notice { border-radius: 0; border-width: 0 0 0 2px; }
        .sp-range .fill { background: var(--c-ink); }
        @media (max-width: 760px) {
            .sv-card + .sv-card { border-left: 0; padding-left: 0; border-top: 1px solid var(--c-rule); }
            .sp-hero { gap: 0; }
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
            border-radius: 4px !important;
            font-size: 14px !important;
            font-weight: 500 !important;
            padding: 2px 14px !important;
            height: 40px !important;
            border: 1px solid var(--c-rule) !important;
            background-color: var(--c-subtle) !important;
            color: var(--c-text_2) !important;
            white-space: nowrap !important;
            flex-shrink: 0 !important;
            transition: all 0.15s ease !important;
        }

        [data-testid="stPills"] button:hover {
            background-color: var(--c-white) !important;
            color: var(--c-ink) !important;
            border-color: var(--c-rule_strong) !important;
        }

        [data-testid="stPills"] button[aria-checked="true"] {
            background-color: var(--c-fill) !important;
            color: var(--c-ink) !important;
            border: 1.5px solid var(--c-ink) !important;
            box-shadow: none !important;
            font-weight: 600 !important;
        }

        /* ── Segmented Control (Table / Cards Switcher) ── */
        [data-testid="stSegmentedControl"] {
            height: 36px !important;
            border-radius: 4px !important;
            background-color: var(--c-subtle) !important;
            border: 1px solid var(--c-rule) !important;
            padding: 2px !important;
        }

        [data-testid="stSegmentedControl"] button {
            height: 30px !important;
            border-radius: 4px !important;
            font-size: 0.78rem !important;
            font-weight: 600 !important;
            padding: 0 10px !important;
            color: var(--c-muted) !important;
            border: none !important;
        }

        [data-testid="stSegmentedControl"] button[aria-checked="true"] {
            background-color: var(--c-white) !important;
            color: var(--c-ink) !important;
            box-shadow: none !important;
            font-weight: 700 !important;
        }

        /* ── Harmonized Selectbox Inputs ── */
        div[data-testid="stSelectbox"] > div {
            min-height: 36px !important;
            border-radius: 4px !important;
            border-color: var(--c-rule) !important;
            font-size: 0.82rem !important;
        }

        /* ── RRG Active Selection Buttons: Universal Left Alignment ── */
        /* RRG: the chart's frame, the selection bar, the quadrant lists */
        .st-key-rrg_frame iframe { height: 780px !important; width: 100% !important; }
        .st-key-rrg_selbar { gap: 8px !important; flex-wrap: wrap !important; }
        .st-key-rrg_selbar button { min-height: 32px !important; height: 32px !important; padding: 0 12px !important;
            border-radius: 4px !important; font-size: 12.5px !important; font-weight: 600 !important; }
        .st-key-rrg_selbar button p { font-size: 12.5px !important; font-weight: 600 !important; }
        [class*="st-key-btn_rrg_lead_"] button { background: var(--c-up_tint) !important; border-color: var(--c-up_line_2) !important; color: var(--c-up) !important; border-radius: 4px !important; }
        [class*="st-key-btn_rrg_imp_"] button { background: var(--c-up_tint) !important; border-color: var(--c-up_line_2) !important; color: var(--c-up) !important; border-radius: 4px !important; }
        [class*="st-key-btn_rrg_weak_"] button { background: var(--c-caution_tint) !important; border-color: var(--c-caution_line) !important; color: var(--c-caution) !important; border-radius: 4px !important; }
        [class*="st-key-btn_rrg_lag_"] button { background: var(--c-down_tint) !important; border-color: var(--c-down_line_3) !important; color: var(--c-down) !important; border-radius: 4px !important; }
        [class*="st-key-btn_rrg_lead_"] button p { color: var(--c-up) !important; }
        [class*="st-key-btn_rrg_imp_"] button p { color: var(--c-up) !important; }
        [class*="st-key-btn_rrg_weak_"] button p { color: var(--c-caution) !important; }
        [class*="st-key-btn_rrg_lag_"] button p { color: var(--c-down) !important; }
        [class*="st-key-del_rrg_"] button { background: var(--c-white) !important; border: 1px solid var(--c-rule) !important; }
        /* Phone rules come after the base ones so they win at equal specificity. */
        @media (max-width: 760px) {
            .st-key-rrg_frame iframe { height: 600px !important; }
            .st-key-rrg_frame .stElementContainer { height: auto !important; flex: 0 0 auto !important; }
            /* One row that scrolls sideways, so the chart starts sooner. */
            .st-key-rrg_selbar { flex-wrap: nowrap !important; overflow-x: auto !important; padding-bottom: 4px; }
            .st-key-rrg_selbar > div { flex: none !important; }
            .st-key-rrg_selbar button p { white-space: nowrap !important; }
        }
        .rq-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
        .rq { border: 1px solid var(--c-rule); border-radius: 4px; overflow: hidden; background: var(--c-white); }
        .rq-h { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; padding: 10px 14px; }
        .rq-h b { font-size: 14px; }
        .rq-h span { font-size: 12px; color: var(--c-text_2); }
        .rq.lead .rq-h { background: var(--c-up_tint); } .rq.lead .rq-h b { color: var(--c-up); }
        .rq.imp .rq-h { background: var(--c-up_tint); } .rq.imp .rq-h b { color: var(--c-up); }
        .rq.weak .rq-h { background: var(--c-caution_tint); } .rq.weak .rq-h b { color: var(--c-caution); }
        .rq.lag .rq-h { background: var(--c-down_tint); } .rq.lag .rq-h b { color: var(--c-down); }
        .rq-i { display: flex; justify-content: space-between; gap: 8px; margin: 0 14px; padding: 7px 0;
            border-bottom: 1px solid var(--c-rule_soft); font-size: 13.5px; }
        .rq-i:last-child { border-bottom: 0; }
        .rq-i span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .rq-i a { color: var(--c-ink) !important; text-decoration: none !important; font-weight: 600; }
        .rq-i b { font-family: var(--font-mono); font-size: 12px; font-weight: 500; color: var(--c-text_2); white-space: nowrap; }
        .rq-none { color: var(--c-muted); }
        @media (max-width: 900px) { .rq-grid { grid-template-columns: 1fr; } }



        /* ── Headings & Badges ── */
        h1, h2, h3, h4, h5, h6 {
            color: var(--c-ink) !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em !important;
        }

        p, [data-testid="stMarkdownContainer"] p {
            color: var(--c-text_2) !important;
            font-size: 0.88rem;
        }

        [data-testid="stCaptionContainer"] {
            font-size: 0.78rem !important;
            color: var(--c-muted) !important;
        }

        /* ── Slim Left Sidebar ── */
        [data-testid="stSidebar"] {
            background-color: var(--c-subtle) !important;
            border-right: 1px solid var(--c-rule) !important;
            box-shadow: none !important;
        }

        [data-testid="stSidebarContent"] {
            background-color: var(--c-subtle) !important;
            padding: 1.2rem 1.1rem !important;
        }


        /* ── Sidebar Radio Navigation Items ── */
        [data-testid="stSidebar"] [data-testid="stRadio"] > div {
            gap: 3px !important;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label {
            padding: 7px 10px !important;
            border-radius: 4px !important;
            border: 1px solid transparent !important;
            background-color: transparent !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
            color: var(--c-text_2) !important;
            transition: all 0.15s ease !important;
            cursor: pointer !important;
            width: 100% !important;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
            background-color: var(--c-white) !important;
            border-color: var(--c-rule) !important;
            color: var(--c-ink) !important;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
            background-color: var(--c-white) !important;
            border-color: var(--c-rule_strong) !important;
            color: var(--c-ink) !important;
            box-shadow: none !important;
        }

        [data-testid="stSidebar"] .stButton > button {
            background-color: var(--c-white) !important;
            border: 1px solid var(--c-rule) !important;
            color: var(--c-ink_2) !important;
            font-weight: 600 !important;
            border-radius: 4px !important;
            box-shadow: none !important;
            transition: all 0.15s ease-in-out !important;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            background-color: var(--c-fill) !important;
            border-color: var(--c-rule_strong) !important;
            color: var(--c-ink) !important;
        }

        /* ── UI kit v2 ───────────────────────────────────────────────────
           Shared by the page_kit helpers. st.metric(border=True) draws its own
           1px border; this sets the radius, surface and depth so a figure in a
           card looks the same on every page. Sits after the Command Bar marker,
           outside every block the legibility tests slice. */
        [data-testid="stMetric"] {
            background: var(--c-white) !important;
            border-radius: var(--r-lg) !important;
            box-shadow: none !important;
            min-width: 0;
        }
        [data-testid="stMetric"] [data-testid="stMetricValue"] {
            font-variant-numeric: tabular-nums;
        }
        [class*="st-key-mrow_"] { align-items: stretch; }
        [class*="st-key-mrow_"] > [data-testid="stMetric"],
        [class*="st-key-mrow_"] > div { flex: 1 1 180px; min-width: 0; }
        /* Figures in a card: as tall as their text, not a 90px box (owner, 13 Oct). */
        [class*="st-key-mrow_"] [data-testid="stMetric"] { padding: 10px 14px !important; }
        [class*="st-key-mrow_"] [data-testid="stMetric"] > div { padding: 0 !important; }
        [class*="st-key-mrow_"] [data-testid="stMetricValue"] { font-size: 20px !important; line-height: 1.2 !important; }

        .sr-only { position: absolute !important; width: 1px; height: 1px; overflow: hidden;
            clip: rect(0 0 0 0); white-space: nowrap; padding: 0 !important; border: 0 !important; }
        .pg-onward { color: var(--c-ink) !important; white-space: nowrap;
            text-decoration: underline !important; text-decoration-color: var(--c-rule_strong) !important;
            text-underline-offset: 3px; }
        .pg-onward:hover { text-decoration-color: var(--c-ink) !important; }
        .pg-empty { padding: 18px 0; border-top: 1px solid var(--c-rule); font-size: 15px; color: var(--c-text_2); }
        .pg-empty b { color: var(--c-ink); font-weight: 600; }
        .st-key-br_chart_head { border-top: 1px solid var(--c-ink); padding-top: 12px !important; margin-top: 4px; }
        .br-charts-h { font-size: 20px !important; font-weight: 600 !important; color: var(--c-ink) !important;
            margin: 0 !important; padding: 0 !important; letter-spacing: 0 !important; scroll-margin-top: 72px; }
        .skip-link { position: absolute; left: 16px; top: -60px; z-index: 1000; padding: 8px 14px;
            background: var(--c-ink); color: var(--c-white) !important; font-size: 14px; text-decoration: none !important; }
        .skip-link:focus { top: 8px; }
        .skip-target { display: block; height: 0; outline: 0 !important; }
        /* Actions' exit watch in Ledger (audit F54): open rows, no box, no
           zebra, status as a coloured word, not a filled chip. */
        .xw { border: 0; border-radius: 0; border-top: 1px solid var(--c-rule_strong); }
        .xw-row:nth-child(odd):not(.xw-head) { background: transparent; }
        .xw-head { background: transparent !important; }
        .xw-row { padding-left: 0 !important; padding-right: 0 !important; }
        .xw-pill, .xw-pill.sell, .xw-pill.watch, .xw-pill.clear, .xw-pill.unknown { background: transparent; padding: 0; font-weight: 600; }
        .xw-pill.watch { color: var(--c-caution); }
        .xw-s a { font-weight: 600; }
        .xw-g b { font-family: var(--font-ui); font-variant-numeric: tabular-nums; }
        .xw-ret { font-family: var(--font-ui); font-variant-numeric: tabular-nums; }

        .ac-row.buy, .ac-row.sell { background: transparent; padding-left: 0; padding-right: 0; }
        .ac-row { border-bottom-color: var(--c-rule); }
        .ac-row.ac-head { background: transparent !important; }
        .ac-row .n { font-family: var(--font-ui); font-variant-numeric: tabular-nums; }
        .ac-row .down { color: var(--c-down); }
        .ac-why b { font-weight: 600; }

        /* Phone and tablet: the header (brand, date, menu) stays at the top
           while the page scrolls (audit F32); the market line scrolls away.
           Sticky goes on the header's own box and on a wrapper Streamlit may
           put round it, so the parent that bounds it is the page's block. */
        @media (max-width: 1023px) {
            .st-key-app_header_shell,
            [data-testid="stLayoutWrapper"]:has(> .st-key-app_header_shell),
            [data-testid="stElementContainer"]:has(> .st-key-app_header_shell) {
                position: sticky !important; top: 0 !important; z-index: 60 !important;
            }
            .st-key-app_header_shell { background: var(--c-white) !important; }
            [data-testid="stPopoverBody"]:has([class*="st-key-navoff_"], [class*="st-key-navon_"]) {
                max-height: calc(100vh - 80px) !important; overflow-y: auto !important;
            }
        }

        /* Touch screens (audit F30): stock links and small controls get a hit
           area of at least 40px; padding with an equal negative margin leaves
           the layout as it is. */
        @media (pointer: coarse) {
            .db-sym a, .xw-s a, .t50-stock, .ib-leads a, .pg-onward, .db-kv a {
                display: inline-block; padding: 11px 0; margin: -11px 0;
            }
            [data-baseweb="tag"] [role="presentation"], [data-baseweb="tag"] span[aria-hidden] {
                padding: 10px; margin: -10px -6px -10px 0;
            }
            [data-testid="stTooltipIcon"] { padding: 12px; margin: -12px; }
        }

        /* Sectors' leaderboard in Ledger: no box, a rule above. */
        .ib { border: 0 !important; border-radius: 0 !important; border-top: 1px solid var(--c-rule_strong) !important; background: transparent !important; }
        .ib-head { background: transparent !important; }
        .ib-row { padding-left: 0 !important; padding-right: 0 !important; }

        /* Plex Mono only in dense tables (owner's decision 4, audit F41):
           tiles, legends, bars, lists and the stock page read figures in
           Plex Sans with tabular digits. The Screener, the shared table, the
           leaderboard's numeric columns and the peers table keep Mono. */
        [data-testid="stMetricLabel"], [data-testid="stMetricValue"], [data-testid="stMetricDelta"],
        .t50-num, .t50-change, .t50-rank, .t50-return, .pg-bar-v, .gc-legend b, .mo-v,
        .ib-n, .ib-3m b, .sp-ladder .lv, .gp-dd .lbl, .gp-ret .lbl, .gp-sh b, .rq-i b,
        .db-rule, .db-size td b, .db-size td, .db-sectors td {
            font-family: var(--font-ui) !important; font-variant-numeric: tabular-nums;
        }
        [data-testid="stMetric"] [data-testid="stMetricLabel"],
        [data-testid="stMetric"] [data-testid="stMetricValue"],
        [data-testid="stMetric"] [data-testid="stMetricDelta"] {
            font-family: var(--font-ui) !important; text-transform: none !important; letter-spacing: 0 !important;
        }
        [class*="st-key-mrow_"] [data-testid="stMetricLabel"] { display: flex !important; justify-content: center !important; }

        /* RRG quadrant lists in Ledger (audit F56): open columns under a rule,
           the quadrant's name in its colour, no tinted header or box. */
        .rq { border: 0 !important; border-radius: 0 !important; border-top: 1px solid var(--c-rule_strong) !important; background: transparent !important; }
        .rq.lead .rq-h, .rq.imp .rq-h, .rq.weak .rq-h, .rq.lag .rq-h { background: transparent !important; }
        .rq-h { padding: 10px 0 !important; }
        .rq-h b { font-weight: 600; }
        .rq-i { margin: 0 !important; }
        @media (max-width: 760px) { .rq-grid { grid-template-columns: 1fr 1fr !important; } }

        /* Readers who ask their system for less motion get none (audit F74). */
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after { transition: none !important; animation: none !important; scroll-behavior: auto !important; }
        }

        /* Visible focus everywhere (audit F28): one 2px ink ring for links,
           buttons, tabs, pills, sliders and anything focusable by keyboard. */
        a:focus-visible, button:focus-visible, [role="tab"]:focus-visible,
        [role="button"]:focus-visible, [role="slider"]:focus-visible, summary:focus-visible,
        [tabindex]:not([tabindex="-1"]):focus-visible, input:focus-visible, select:focus-visible {
            outline: 2px solid var(--c-ink) !important; outline-offset: 2px !important;
        }

        /* ── One figure tile (audit F42) ───────────────────────────────
           kit.readings strips and st.metric rows draw the same tile: open,
           between a hairline above and below, cells split by a hairline,
           centred (owner, 13 Oct), the figure in Plex Sans tabular, 600
           (decision 4). No box, no radius, no shadow. */
        .mkt-strip.pg-strip,
        [class*="st-key-mrow_"] {
            background: transparent !important; border: 0 !important; border-radius: 0 !important;
            border-top: 1px solid var(--c-rule) !important; border-bottom: 1px solid var(--c-rule) !important;
            box-shadow: none !important; gap: 0 !important;
        }
        .mkt-strip.pg-strip .ms-tile,
        [class*="st-key-mrow_"] [data-testid="stMetric"] {
            background: transparent !important; border: 0 !important; border-radius: 0 !important;
            border-right: 1px solid var(--c-rule) !important; box-shadow: none !important;
            padding: 12px 14px !important; text-align: center;
        }
        .mkt-strip.pg-strip .ms-tile:last-child,
        [class*="st-key-mrow_"] > :last-child [data-testid="stMetric"],
        [class*="st-key-mrow_"] > [data-testid="stMetric"]:last-child { border-right: 0 !important; }
        [class*="st-key-mrow_"] [data-testid="stMetric"] label,
        [class*="st-key-mrow_"] [data-testid="stMetricLabel"],
        [class*="st-key-mrow_"] [data-testid="stMetricValue"],
        [class*="st-key-mrow_"] [data-testid="stMetricDelta"] { justify-content: center; margin-inline: auto; }
        .mkt-strip.pg-strip .ms-k,
        [class*="st-key-mrow_"] [data-testid="stMetricLabel"] p {
            font-size: 12.5px !important; font-weight: 500 !important; color: var(--c-muted) !important;
        }
        .mkt-strip.pg-strip .ms-v,
        [class*="st-key-mrow_"] [data-testid="stMetricValue"] {
            font-family: var(--font-ui) !important; font-size: 24px !important; font-weight: 600 !important;
            line-height: 1.15 !important; letter-spacing: 0 !important; font-variant-numeric: tabular-nums;
        }
        .mkt-strip.pg-strip .ms-v.ms-name { font-size: 18px !important; }
        @media (max-width: 640px) {
            .mkt-strip.pg-strip, [class*="st-key-mrow_"] {
                display: grid !important; grid-template-columns: 1fr 1fr; gap: 0 !important;
                border-bottom: 0 !important;
            }
            .mkt-strip.pg-strip .ms-tile,
            [class*="st-key-mrow_"] [data-testid="stMetric"] {
                padding: 10px 8px !important; border-bottom: 1px solid var(--c-rule) !important;
            }
            .mkt-strip.pg-strip .ms-tile:nth-child(2n),
            [class*="st-key-mrow_"] > :nth-child(2n) [data-testid="stMetric"] { border-right: 0 !important; }
            .mkt-strip.pg-strip .ms-v, [class*="st-key-mrow_"] [data-testid="stMetricValue"] { font-size: 20px !important; }
            .mkt-strip.pg-strip .ms-v.ms-name { font-size: 15px !important; }
        }

        .pg-callout {
            border-left: 3px solid var(--c-border-strong);
            background: var(--c-bg-subtle);
            border-radius: var(--r-md);
            padding: 10px 14px;
            margin: 0;
            font-size: var(--fs-13);
            line-height: 1.45;
            color: var(--c-text-secondary);
        }
        .pg-callout b { display: block; font-size: var(--fs-13); color: var(--c-text-primary); }
        .pg-callout span { display: block; margin-top: 4px; }
        .pg-callout.up { border-left-color: var(--c-up); background: var(--c-bull-tint); }
        .pg-callout.up b { color: var(--c-up); }
        .pg-callout.down { border-left-color: var(--c-down); background: var(--c-bear-tint); }
        .pg-callout.down b { color: var(--c-down); }
        .pg-callout.warn { border-left-color: var(--c-caution); background: var(--c-caution-tint); }
        .pg-callout.warn b { color: var(--c-caution-ink); }

        a.pg-link {
            display: inline-flex; align-items: center; gap: 6px;
            padding: 8px 14px; border: 1px solid var(--c-border-strong);
            border-radius: var(--r-md); background: var(--c-white);
            color: var(--c-accent-text) !important; font-size: var(--fs-13);
            font-weight: 600; text-decoration: none;
        }
        a.pg-link:hover { border-color: var(--c-ink); background: var(--c-accent-tint); }

        [data-testid="stDialog"] [role="dialog"] {
            border-radius: var(--r-xl) !important;
            box-shadow: var(--sh-pop) !important;
        }

        /* ── Metric Containers ── */
        [data-testid="metric-container"] {
            background-color: var(--c-white) !important;
            border: 1px solid var(--c-rule) !important;
            border-radius: 4px !important;
            padding: 1.1rem 1.3rem !important;
            box-shadow: none !important;
            transition: transform 0.1s ease, box-shadow 0.1s ease;
        }

        [data-testid="metric-container"]:hover {
            border-color: var(--c-rule_strong) !important;
            box-shadow: none !important;
        }

        [data-testid="stMetricLabel"] {
            font-family: var(--font-mono) !important;
            font-size: 0.72rem !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.08em !important;
            color: var(--c-muted) !important;
        }

        [data-testid="stMetricValue"] {
            font-family: var(--font-mono) !important;
            font-size: 1.6rem !important;
            font-weight: 700 !important;
            color: var(--c-ink) !important;
        }

        /* The page-wide paragraph rule reached the <p> inside a metric's label
           and value, leaving every value 14px grey under a 90px box. */
        [data-testid="stMetricLabel"] p,
        [data-testid="stMetricValue"] p {
            font: inherit !important; color: inherit !important; letter-spacing: inherit !important;
            margin: 0 !important;
        }

        [data-testid="stMetricDelta"] {
            font-family: var(--font-mono) !important;
            font-size: 0.78rem !important;
            font-weight: 600 !important;
        }

        /* ── Navigation Tabs ── */
        [data-baseweb="tab-list"] {
            background-color: var(--c-subtle) !important;
            border: 1px solid var(--c-rule) !important;
            border-radius: 4px !important;
            padding: 0.35rem !important;
            gap: 0.25rem !important;
            margin-bottom: 1.4rem !important;
        }

        [data-baseweb="tab"] {
            border-radius: 4px !important;
            padding: 0.45rem 1rem !important;
            font-family: var(--font-mono) !important;
            font-size: 0.8rem !important;
            font-weight: 600 !important;
            color: var(--c-muted) !important;
            border: none !important;
            transition: all 0.15s ease !important;
        }

        [data-baseweb="tab"]:hover {
            color: var(--c-ink) !important;
            background-color: var(--c-fill) !important;
        }

        [aria-selected="true"][data-baseweb="tab"] {
            background-color: var(--c-white) !important;
            color: var(--c-ink) !important;
            border: 1px solid var(--c-rule) !important;
            box-shadow: none !important;
        }

        [data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {
            display: none !important;
        }


        /* ── Financial High-Density DataTables ── */
        [data-testid="stDataFrame"] {
            border: 1px solid var(--c-rule) !important;
            border-radius: 4px !important;
            overflow: hidden !important;
            background-color: var(--c-white) !important;
            box-shadow: none !important;
        }

        /* ── Form Inputs & Buttons ── */
        .stButton > button {
            background-color: var(--c-white) !important;
            border: 1px solid var(--c-rule_strong) !important;
            border-radius: 4px !important;
            color: var(--c-text_2) !important;
            font-size: 0.84rem !important;
            font-weight: 600 !important;
            padding: 0.4rem 0.9rem !important;
            box-shadow: none !important;
            transition: all 0.15s ease !important;
        }

        .stButton > button:hover {
            border-color: var(--c-ink) !important;
            color: var(--c-ink) !important;
            background-color: var(--c-subtle) !important;
        }

        /* The page's one main action: indigo, per the design. */
        .stButton > button[kind="primary"] {
            background-color: var(--c-ink) !important; border-color: var(--c-ink) !important; color: var(--c-white) !important;
        }
        .stButton > button[kind="primary"]:hover {
            background-color: var(--c-ink) !important; border-color: var(--c-ink) !important; color: var(--c-white) !important;
        }

        [data-testid="stDownloadButton"] button {
            background-color: var(--c-white) !important;
            color: var(--c-ink) !important;
            border: 1px solid var(--c-rule_strong) !important;
            font-weight: 600 !important;
            border-radius: 4px !important;
            min-height: 40px !important;
        }

        [data-testid="stDownloadButton"] button:hover {
            background-color: var(--c-subtle) !important;
            border-color: var(--c-ink) !important;
            color: var(--c-ink) !important;
        }

        [data-testid="stDownloadButton"] button[kind="primary"] {
            background-color: var(--c-ink) !important; color: var(--c-white) !important; border-color: var(--c-ink) !important;
        }
        [data-testid="stDownloadButton"] button[kind="primary"]:hover {
            background-color: var(--c-ink) !important; color: var(--c-white) !important;
        }
        /* A page-wide paragraph colour reached into primary buttons and left
           their labels grey on indigo. */
        [data-testid="stBaseButton-primary"] p,
        [data-testid="stBaseButton-primary"] span { color: var(--c-white) !important; }
        /* A form's submit button (the Backtest page's Apply) is its own kind,
           stBaseButton-primaryFormSubmit, and the rules above missed it: its
           label read dark on indigo (owner's phone, 9 Oct 2026). */
        [data-testid="stBaseButton-primaryFormSubmit"] {
            background-color: var(--c-ink) !important; border-color: var(--c-ink) !important; color: var(--c-white) !important;
        }
        [data-testid="stBaseButton-primaryFormSubmit"]:hover {
            background-color: var(--c-ink) !important; border-color: var(--c-ink) !important; color: var(--c-white) !important;
        }
        [data-testid="stBaseButton-primaryFormSubmit"] p,
        [data-testid="stBaseButton-primaryFormSubmit"] span { color: var(--c-white) !important; }
        /* A popover's button carries its own test id, stPopoverButton, so the
           rules above missed it: the Actions page's "Kite basket" read grey on
           indigo (owner's phone, 13 Oct 2026). Every primary kind - button,
           popover, download, form submit, link - carries kind="primary...". */
        [kind^="primary"], [kind^="primary"] p,
        [kind^="primary"] span { color: var(--c-white) !important; }
        [kind^="primary"]:hover { color: var(--c-white) !important; }

        [data-baseweb="select"] > div {
            background-color: var(--c-white) !important;
            border: 1px solid var(--c-rule_strong) !important;
            border-radius: 4px !important;
            color: var(--c-ink) !important;
        }

        [data-baseweb="input"] input, [data-baseweb="textarea"] textarea {
            background-color: var(--c-white) !important;
            border: 1px solid var(--c-rule_strong) !important;
            color: var(--c-ink) !important;
            border-radius: 4px !important;
            font-size: 0.85rem !important;
        }

        [data-baseweb="input"] input:focus, [data-baseweb="textarea"] textarea:focus {
            border-color: var(--c-ink) !important;
            box-shadow: none !important;
        }

        [data-testid="stExpander"] {
            background-color: var(--c-white) !important;
            border: 1px solid var(--c-rule) !important;
            border-radius: 4px !important;
            box-shadow: none !important;
            margin-bottom: 0.8rem !important;
        }

        [data-testid="stExpander"] summary {
            font-size: 0.86rem !important;
            font-weight: 600 !important;
            color: var(--c-ink_2) !important;
        }

        [data-testid="stSlider"] [role="slider"] {
            background-color: var(--c-ink) !important;
            border-color: var(--c-ink) !important;
        }

        hr {
            border-color: var(--c-fill) !important;
            margin: 1.2rem 0 !important;
        }

        /* ── Paper B · Ledger, white ground (owner, 7 Nov 2026) ─────────
           Structure over the palette above: hierarchy from type and white
           space, thin rules instead of boxes, no shadows, small corners.
           Blue is "up", so selection and the active page are ink. */
        :root { --r-sm: 3px; --r-md: 4px; --r-lg: 4px; --r-xl: 4px;
                --sh-1: none; --sh-2: none; }
        [class*="st-key-pgcard_"] {
            background: transparent !important; border: 0 !important;
            border-top: 1px solid var(--c-ink) !important; border-radius: 0 !important;
            padding: 14px 0 6px !important; box-shadow: none !important;
        }
        .st-key-app_header_shell {
            border: 0 !important; border-bottom: 1px solid var(--c-ink) !important;
            border-radius: 0 !important; box-shadow: none !important; background: var(--c-white) !important;
        }
        .st-key-app_brand [data-testid="stPageLink"] a:hover { background: transparent !important; text-decoration: underline !important; }
        .mkt-snapshot { border: 0 !important; border-top: 1px solid var(--c-rule) !important;
            border-bottom: 1px solid var(--c-rule) !important; border-radius: 0 !important; box-shadow: none !important; }
        .mkt-strip, .ms-tile { border-radius: 0 !important; box-shadow: none !important; }
        .t50-card { border: 0 !important; border-top: 1px solid var(--c-ink) !important;
            border-radius: 0 !important; box-shadow: none !important; background: transparent !important; }
        .t50-card-head { background: transparent !important; border-bottom: 1px solid var(--c-rule) !important;
            min-height: 0 !important; padding: 10px 0 !important; }
        .t50-icon { display: none !important; }
        .t50-col-head, .t50-row { padding-left: 0 !important; padding-right: 0 !important; }
        .t50-col-head { background: transparent !important; }
        [data-testid="stMetric"], [class*="st-key-mrow_"] > div {
            border-radius: 0 !important; box-shadow: none !important; }
        [data-testid="stPills"] button { border-radius: 4px !important; background-color: var(--c-white) !important; }
        /* Streamlit 1.65 draws st.pills and st.segmented_control inside
           data-testid="stButtonGroup"; the stPills selector no longer matches. */
        [data-testid="stButtonGroup"] button { border-radius: 4px !important; }
        [data-testid="stPills"] button[aria-checked="true"] { background-color: var(--c-fill) !important;
            border: 1px solid var(--c-ink) !important; }
        .hdr-pill, .sig-chip { border-radius: 4px !important; }
        [data-testid="stExpander"] details { border-radius: 0 !important; border-left: 0 !important; border-right: 0 !important; }

        /* ── One section rhythm (S99, owner, 8 Nov 2026) ─────────────
           A section's top rule sits ~28px below what precedes it on every
           page: the 16px block gap, the previous card's 6px padding and 6px
           here. Measured before: 11px to 44px (question sections kept a 22px
           bottom margin; a block's last paragraph kept its 16px margin). */
        [class*="st-key-pgcard_"] { margin-top: 6px !important; }
        .qp { margin-bottom: 0 !important; margin-top: 6px !important; }
        [data-testid="stExpander"] { margin-bottom: 0 !important; }  /* Streamlit's 12.8px */
        /* A small trend line under a headline figure (S99): kit.spark_img. */
        .ms-spark { display: block; line-height: 0; margin: 6px auto 2px; }
        [data-testid="stMarkdownContainer"] > p:last-child,
        [data-testid="stMarkdownContainer"] > div > p:last-child { margin-bottom: 0 !important; }

        /* "On this page": section links under a page's headline (Breadth, and
           the Dashboard from 8 Nov 2026). */
        .qp-nav { display: flex; flex-wrap: wrap; gap: 4px 18px; font-size: 13.5px; margin: 0 0 14px; }
        .qp-nav a { color: var(--c-ink) !important; text-decoration: underline;
            text-decoration-color: var(--c-rule_strong); text-underline-offset: 3px; }
        .mq h2, .pg-card-h h2 { scroll-margin-top: 72px; }

        /* ── Desktop quick links beside the menu (owner, 7 Nov 2026) ── */
        .st-key-app_quicklinks { gap: 2px !important; margin-left: auto !important; }
        .st-key-app_quicklinks [data-testid="stPageLink"] a {
            padding: 6px 10px !important; border-radius: 0 !important; background: transparent !important;
            border-bottom: 2px solid transparent !important; text-decoration: none !important; }
        .st-key-app_quicklinks [data-testid="stPageLink"] a p { font-size: 14px !important; font-weight: 500 !important;
            color: var(--c-text_2) !important; }
        .st-key-app_quicklinks [class*="st-key-navon_"] [data-testid="stPageLink"] a { border-bottom-color: var(--c-ink) !important; }
        .st-key-app_quicklinks [class*="st-key-navon_"] [data-testid="stPageLink"] a p { color: var(--c-ink) !important; font-weight: 600 !important; }
        .st-key-app_quicklinks [data-testid="stPageLink"] a:hover p { color: var(--c-ink) !important; }
        @media (max-width: 1023px) { .st-key-app_quicklinks { display: none !important; } }

        /* ── Dashboard (src/ui/views/dashboard_view.py) ──────────────
           Two columns on a desktop, one on a phone; tight vertical rhythm
           (owner, 7 Nov: "unnecessary white spaces and large gaps"). */
        .st-key-db_page { gap: 18px !important; }
        .st-key-db_page [data-testid="stHorizontalBlock"] { gap: 36px !important; align-items: flex-start !important; }
        .st-key-db_page [class*="st-key-pgcard_db_"] { padding: 10px 0 0 !important; gap: 6px !important; }
        .st-key-db_page [class*="st-key-pgcard_db_"] .pg-card-h h2 { font-size: 15px !important; }
        .st-key-db_page .pg-cap { font-size: 12px; margin-top: 2px; }
        .db-risk { display: grid; font-size: 13.5px; }
        .db-risk-row { display: grid; grid-template-columns: minmax(120px,1.25fr) 112px minmax(130px,1.25fr) minmax(60px,0.7fr);
            align-items: center; column-gap: 14px; min-height: 34px; padding: 3px 0; border-bottom: 1px solid var(--c-rule_soft); }
        .db-risk-row.db-head { min-height: 26px; font-size: 12px; font-weight: 600; color: var(--c-muted);
            border-bottom: 1px solid var(--c-rule); }
        .db-sym { line-height: 1.2; }
        .db-sym a { font-weight: 600; color: var(--c-ink) !important; text-decoration: none; }
        .db-sym small { display: block; font-size: 12px; color: var(--c-muted); white-space: normal; line-height: 1.3; }
        .db-status { font-size: 12px; font-weight: 600; color: var(--c-text_2); }
        .db-risk-row.watch .db-status { color: var(--c-caution); }
        .db-risk-row.sell .db-status { color: var(--c-down); }
        .db-rule { font-family: var(--font-mono); font-size: 12px; color: var(--c-text_2); }
        .db-bar { display: block; height: 5px; background: var(--c-fill); }
        .db-bar i { display: block; height: 100%; background: var(--c-ink); }
        .db-risk-row.watch .db-bar i { background: var(--c-caution); }
        .db-risk-row.sell .db-bar i { background: var(--c-down); }
        .db-kv { display: grid; grid-template-columns: 92px 1fr; gap: 5px 12px; margin: 0 !important; padding: 0 !important; font-size: 13.5px; line-height: 1.4; }
        .db-kv dt { color: var(--c-muted); font-weight: 600; margin: 0 !important; }
        .db-kv dd { margin: 0 !important; color: var(--c-ink); }
        .db-kv a, .db-sectors a { color: var(--c-ink) !important; }
        .db-lede { margin: 0 0 4px; font-size: 14px; color: var(--c-ink); }
        /* A card's figures as rows: label left, figure right, hairlines (as .mq tables) */
        .db-fig { width: 100%; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; margin: 8px 0 2px; }
        .db-fig th { font-size: 12px; font-weight: 500; color: var(--c-muted); text-align: right; padding: 4px 0 4px 8px; border-bottom: 1px solid var(--c-rule_strong); }
        .db-fig th:first-child, .db-fig td:first-child { text-align: left; padding-left: 0; }
        .db-fig td { padding: 6px 0 6px 8px; border-bottom: 1px solid var(--c-rule); text-align: right; color: var(--c-ink); }
        .db-fig td:first-child { color: var(--c-text_2); }
        .db-fig td.down { color: var(--c-down); } .db-fig td.up { color: var(--c-up); } .db-fig td.mid { color: var(--c-muted); }
        /* S91 panels: momentum health and flows */
        .db-big { font-family: var(--font-serif, Georgia, serif); font-size: 36px; line-height: 1.1; color: var(--c-ink); margin: 0 0 6px; }
        .db-big span { font-family: inherit; font-size: 14px; color: var(--c-muted); margin-left: 6px; }
        .db-big.up, .db-kv b.up { color: var(--c-up); }
        .db-big.down, .db-kv b.down { color: var(--c-down); }
        .db-flag { margin: 4px 0; font-size: 13.5px; font-weight: 600; color: var(--c-down); }
        .db-note { margin: 6px 0 0; font-size: 13px; color: var(--c-muted); }
        .db-mh img { display: block; margin-top: 8px; }
        .db-size, .db-sectors { width: 100%; border-collapse: collapse; font-size: 13.5px; }
        .db-size th, .db-size td, .db-sectors th, .db-sectors td { padding: 6px 8px 6px 0;
            border-bottom: 1px solid var(--c-rule_soft); text-align: right; font-weight: 400; }
        .db-size th:first-child, .db-sectors th { text-align: left; font-weight: 600; color: var(--c-ink); }
        .db-size thead th { font-size: 12px; font-weight: 600; color: var(--c-muted); border-bottom: 1px solid var(--c-rule); }
        .db-size thead th small { display: block; font-size: 12px; font-weight: 400; color: var(--c-muted); }
        .db-size td small { display: inline-block; min-width: 46px; margin-left: 6px; font-size: 12px; font-weight: 400; color: var(--c-muted); }
        .db-size td b, .db-size td, .db-sectors td { font-family: var(--font-mono); }
        .db-size td b { font-weight: 600; }
        .db-size tr.db-base th, .db-size tr.db-base td { color: var(--c-muted); }
        .db-size .up, .db-sectors .up { color: var(--c-up); } .db-size .down, .db-sectors .down { color: var(--c-down); }
        .db-sectors td.db-n { color: var(--c-muted); font-family: var(--font-ui); font-size: 12px; }
        @media (max-width: 640px) {
            .st-key-db_page [data-testid="stHorizontalBlock"] { gap: 18px !important; }
            .db-risk-row { grid-template-columns: 1fr auto; row-gap: 2px; padding: 6px 0; }
            .db-risk-row.db-head { display: none; }
            .db-rule { grid-column: 1 / -1; } .db-bar { grid-column: 1 / -1; }
        }
        </style>
        """),
        unsafe_allow_html=True,
    )


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


# ── Column headers ──────────────────────────────────────────────────────────
# Module level, and the ONLY place the table's shape is written down. The
# density labels used to carry their own hand-typed column counts -- "Full
# Quant (35)" over a table that emitted 36 -- because a second copy of a
# number is a copy that drifts. `screener_column_count` now reads the count
# back out of these very blocks, so a column added here reaches the label
# with no second edit.
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
# property of the column, so it is declared per column here. Any percentage
# column that is not declared now fails loudly instead of guessing from its
# magnitude.
FRACTION_PERCENT_COLUMNS: frozenset[str] = frozenset({
    # Backtest — trades, periods and stats
    "RETURN %", "MTD %", "STRATEGY NET", "BENCHMARK", "ALPHA VS BENCHMARK",
    "TOTAL RETURN", "GROSS RETURN", "NET RETURN", "ALPHA", "OUTPERFORM",
    "CAGR", "ANN RETURN", "WIN RATE", "MAX DRAWDOWN", "MAX DD",
    "6M NET RETURN", "6M ALPHA",
    "% OF 52W HIGH START", "% OF 52W HIGH END",
    # Shares of a group (sector cards) and a corporate-action move (close / previous - 1).
    "EMA %", "NEAR %", "PASS %", "MOVE %",
})

SCALED_PERCENT_COLUMNS: frozenset[str] = frozenset({
    # Already multiplied by 100 at source
    "TURNOVER", "TURNOVER %", "COST DRAG %", "WEIGHT %",
    "% HIGH", "% ATH", "% 50 EMA", "% 20 EMA", "% 52W HIGH",
    "ATR %", "PERSISTENCE", "FFILL %",
    "DEL %", "DEL% 20D AVG", "DEL% PREV20D",
    "DAY CHG %", "PRICE_CHG_%", "P&L %", "DAY P&L %", "TARGET WEIGHT %", "WEIGHT DRIFT %",
    # The backtest's live book stores the entry weight x 100 (backtester: w * 100);
    # undeclared, it raised on the Backtest page's current book (7 Oct 2026).
    "ENTRY WEIGHT %",
    # The backtest download's trade return, written in percent (src/engine/backtest_export.py).
    "PRICE RETURN %",
    # exit_watch copies "% 50 EMA" and "% High", already x 100.
    "VS 50 EMA %", "VS 52W HIGH %",
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
_AGGREGATE_MONEY_KEYS = ("VALUE", "CAPITAL", "MCAP", "P&L", "DAY P&L")


_PCT_TEXT = re.compile(r"[+−-]?\d[\d,]*(?:\.\d+)?%")


def _is_pct_text_column(col: pd.Series) -> bool:
    """A text column holding only percentages (and dashes): it reads as figures."""
    if pd.api.types.is_numeric_dtype(col):
        return False
    vals = [str(v).strip() for v in col.dropna() if str(v).strip() not in ("", "—", "-")]
    return bool(vals) and all(_PCT_TEXT.fullmatch(v) for v in vals)


def render_saas_table(
    df: pd.DataFrame,
    max_height: int | None = None,
    variant: str = "default",
) -> None:
    """Render a borderless SaaS table with optional page-specific presentation variants."""
    if df.empty:
        st.info("No data available to display.")
        return

    n_rows = len(df)
    if max_height is None:
        table_h = min(600, (n_rows * 44) + 48)
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
                "COMPANY",
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
        elif _is_pct_text_column(df[col]):
            headers_html.append(f'<th class="th-right">{_esc(str(col))}</th>')
        elif not pd.api.types.is_numeric_dtype(df[col]):
            # A text column's cells sit left (the generic cell below), so its
            # heading does too; it sat right over left-aligned text (F44).
            headers_html.append(f'<th class="th-left">{_esc(str(col))}</th>')
        else:
            headers_html.append(f'<th class="th-right">{_esc(str(col))}</th>')

    portfolio_class = "portfolio" if variant == "portfolio" else ""
    rows_html = []
    pct_text_cols = {c for c in df.columns if _is_pct_text_column(df[c])}
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
            portfolio_sign_class = ""
            if variant == "portfolio" and c_str in {"P&L (₹)", "P&L %", "DAY P&L (₹)", "DAY P&L %"}:
                portfolio_sign_class = "portfolio-pos" if val > 0 else ("portfolio-neg" if val < 0 else "portfolio-flat")

            if pd.isna(val) or val is None or str(val).strip() in ("", "nan", "None"):
                cells_html.append('<td class="td-center text-muted">—</td>')
                continue
            if col in pct_text_cols and str(val).strip() in ("—", "-"):
                cells_html.append('<td class="td-right text-muted">—</td>')
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
                cells_html.append(
                    f'<td class="td-center"><span class="badge-pill {q_badge}">{_esc(q_val)}</span></td>'
                )
            elif "STATUS" in c_str:
                status_str = str(val).strip()
                status_class = (
                    "badge-green" if status_str.upper() in {"HELD", "OPEN", "ACTIVE"}
                    else ("badge-red" if status_str.upper() in {"CLOSED", "SOLD"}
                          else "badge-neutral")
                )
                cells_html.append(
                    f'<td class="td-center"><span class="badge-pill {status_class}">{_esc(status_str)}</span></td>'
                )
            elif "ACTION" in c_str:
                # Every Action column is a record of trades, so it says what
                # happened: Bought / Sold / Held (owner, 12 Oct 2026). Plans
                # (the Actions page, filters) say Buy / Sell / Hold. The
                # engine's own codes ("🟢 BUY (Entry)", "⚪ HELD") are unchanged.
                act_str = str(val).upper()
                if "BUY" in act_str or "BOUGHT" in act_str:
                    cells_html.append(
                        '<td class="td-center"><span class="badge-pill badge-green">Bought</span></td>'
                    )
                elif "SELL" in act_str or "SOLD" in act_str:
                    cells_html.append(
                        '<td class="td-center"><span class="badge-pill badge-red">Sold</span></td>'
                    )
                elif any(w in act_str for w in ("HOLD", "HELD", "RETAINED")):
                    cells_html.append(
                        '<td class="td-center"><span class="badge-pill badge-neutral">Held</span></td>'
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
                            "P&L %",
                            "MTD",
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
                    if unit is None:
                        raise ValueError(
                            f"Undeclared percentage unit for column {col!r}; "
                            "add it to FRACTION_PERCENT_COLUMNS or SCALED_PERCENT_COLUMNS."
                        )
                    as_fraction = unit == "fraction"
                    if as_fraction:
                        combined_clr = portfolio_sign_class or clr
                        cells_html.append(
                            f'<td class="td-right {combined_clr}"><strong>{_fmt.pct(val)}</strong></td>'
                        )
                    else:
                        combined_clr = portfolio_sign_class or clr
                        cells_html.append(
                            f'<td class="td-right {combined_clr}"><strong>{_fmt.pct(val, fraction=False)}</strong></td>'
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
                    if unit is None:
                        raise ValueError(
                            f"Undeclared percentage unit for column {col!r}; "
                            "add it to FRACTION_PERCENT_COLUMNS or SCALED_PERCENT_COLUMNS."
                        )
                    as_fraction = unit == "fraction"
                    # A level or a share (weight, turnover, % of the 52W high)
                    # takes no "+"; a change or a distance (drift, vs EMA) does.
                    # A minus always shows (audit F11/F64: "+5.0%" weights).
                    signed_ = any(w in c_str for w in ("DRIFT", "EMA", "VS ", "ALPHA", "CHG", "Δ"))
                    cells_html.append(f'<td class="td-right {clr}">'
                                      f'{_fmt.pct(val, signed_=signed_, fraction=as_fraction)}</td>')
                # 3. Currency / Prices (e.g. CMP, Entry Price, Exit Price, Value, Capital)
                elif any(
                    w in c_str for w in _PER_SHARE_PRICE_KEYS + _AGGREGATE_MONEY_KEYS
                ):
                    if any(w in c_str for w in _PER_SHARE_PRICE_KEYS):
                        cells_html.append(
                            f'<td class="td-right">{_fmt.inr(val, 2)}</td>'
                        )
                    else:
                        cells_html.append(
                            f'<td class="td-right {portfolio_sign_class}">{_fmt.inr(val)}</td>'
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
                    f'<td class="td-center">{"Yes" if val else "No"}</td>'
                )
            elif isinstance(val, str) and _PCT_TEXT.fullmatch(val.strip()):
                # A percentage formatted upstream ("+3.4%", "−1.2%"): a figure,
                # so right-aligned and toned by its sign like any other return.
                t = val.strip()
                tone = "ret-pos" if t.startswith("+") else "ret-neg" if t.startswith(("−", "-")) else ""
                cells_html.append(f'<td class="td-right {tone}">{_esc(t)}</td>')
            else:
                cells_html.append(f'<td class="td-left">{_esc(str(val))}</td>')

        rows_html.append(f'<tr class="screener-row">{"".join(cells_html)}</tr>')

    saas_page_html = f"""<!DOCTYPE html>
<html lang="en"><title>Table</title>
<head>
<meta charset="utf-8">
<link href="{FONTS["font_css"]}" rel="stylesheet">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    background: transparent;
    font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    color: var(--c-ink);
    -webkit-font-smoothing: antialiased;
    padding: 2px;
}}
.saas-table-wrapper {{
    width: 100%;
    max-height: {table_h}px;
    overflow: auto;
    border: 1px solid var(--c-rule);
    border-radius: 4px;
    background: var(--c-white);
    box-shadow: none;
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
    width: max-content;
    min-width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 13.5px;
    color: var(--c-ink);
    white-space: nowrap;
}}
.saas-table thead tr th {{
    position: sticky;
    top: 0;
    z-index: 10;
    background: var(--c-subtle);
    color: var(--c-muted);
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 12px;
    font-weight: 600;
    height: 42px;
    padding: 0 10px;
    border-bottom: 1px solid var(--c-rule);
    border-left: none;
    border-right: none;
    cursor: pointer;
    user-select: none;
    transition: background-color 0.15s ease, color 0.15s ease;
}}
.saas-table thead tr th:hover {{
    background-color: var(--c-rule) !important;
    color: var(--c-ink) !important;
}}
.saas-table thead tr th.th-left {{ text-align: left; }}
.saas-table thead tr th.th-center {{ text-align: center; }}
.saas-table thead tr th.th-right {{ text-align: right; }}
.sort-indicator {{
    display: inline-block;
    margin-left: 4px;
    font-size: 12px;
    color: var(--c-ink);
    vertical-align: middle;
}}

.saas-table-wrapper {{
    -webkit-overflow-scrolling: touch;
    overscroll-behavior-x: contain;
    touch-action: pan-x pan-y;
}}

/* Portfolio: sign colours only; type weight follows the other tables. */
.saas-table-wrapper.portfolio .portfolio-pos {{ color: var(--c-up) !important; }}
.saas-table-wrapper.portfolio .portfolio-neg {{ color: var(--c-down_dark) !important; }}
.saas-table-wrapper.portfolio .portfolio-flat {{ color: var(--c-muted) !important; }}
@media (max-width: 640px) {{
    .saas-table thead tr th {{
        padding: 0 8px;
    }}
    .saas-table td {{
        padding: 0 8px;
    }}
    .saas-table th:first-child,
    .saas-table td:first-child {{
        position: sticky;
        left: 0;
        z-index: 12;
        background: var(--c-white);
        box-shadow: 6px 0 8px -8px rgba(14, 23, 38, 0.35);
    }}
    .saas-table thead th:first-child {{
        background: var(--c-subtle);
    }}
}}
.saas-table tbody tr.screener-row {{
    border-bottom: 1px solid var(--c-fill);
    transition: background-color 0.12s ease;
}}
.saas-table tbody tr.screener-row:hover td {{
    background-color: var(--c-subtle) !important;
}}
.saas-table td {{
    height: 44px;
    padding: 0 10px;
    vertical-align: middle;
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 13.5px;
    border-bottom: 1px solid var(--c-rule_soft);
    border-left: none;
    border-right: none;
    background: var(--c-white);
}}
.saas-table td.td-left {{ text-align: left; }}
.saas-table td.td-center {{ text-align: center; }}
.saas-table td.td-right {{ text-align: right; font-family: 'IBM Plex Mono', ui-monospace, monospace; font-variant-numeric: tabular-nums; }}
.saas-table td.td-sector {{
    font-family: 'IBM Plex Sans', sans-serif;
    color: var(--c-text_2);
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.stock-ticker {{
    font-family: 'IBM Plex Sans', sans-serif;
    font-weight: 600;
    font-size: 14px;
    color: var(--c-ink);
}}
.badge-pill {{
    display: inline-block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    font-weight: 600;
    padding: 2px 7px;
    border-radius: 4px;
}}
.badge-green {{ background: var(--c-up_tint); color: var(--c-up); border: 1px solid var(--c-up_line_2); }}
.badge-yellow {{ background: var(--c-caution_tint); color: var(--c-caution); border: 1px solid var(--c-caution_line); }}
.badge-red {{ background: var(--c-down_tint); color: var(--c-down_dark); border: 1px solid var(--c-down_line_3); }}
.badge-blue {{ background: var(--c-up_tint_2); color: var(--c-up_dark); border: 1px solid var(--c-up_line_2); }}
.badge-neutral {{ background: var(--c-subtle); color: var(--c-muted); border: 1px solid var(--c-rule); }}
.ret-pos {{ color: var(--c-up); font-weight: 700; }}
.ret-neg {{ color: var(--c-down_dark); font-weight: 700; }}
.td-sharpe {{ color: var(--c-up); font-weight: 600; }}
.text-muted {{ color: var(--c-muted); }}
/* One table style (audit F44): as the Screener's. No box: a rule above, the
   header on white under a darker rule, 40px rows on hairlines, status as a
   coloured word rather than a filled pill, weights 500/600. */
.saas-table-wrapper {{ border: 0; border-top: 1px solid var(--c-rule_strong); border-radius: 0; background: transparent; padding: 0; }}
.saas-table thead tr th {{ background: var(--c-white); font-weight: 500; height: 36px; border-bottom: 1px solid var(--c-rule_strong); }}
.saas-table thead tr th:hover {{ background-color: var(--c-white) !important; color: var(--c-ink) !important; }}
@media (max-width: 640px) {{ .saas-table thead th:first-child {{ background: var(--c-white); }} }}
.saas-table td {{ height: 40px; border-bottom: 1px solid var(--c-rule); background: transparent; }}
.saas-table th:first-child, .saas-table td:first-child {{ padding-left: 0; }}
.stock-ticker {{ font-weight: 600; }}
.badge-pill {{ font-family: 'IBM Plex Sans', sans-serif; padding: 0; border: 0 !important; background: transparent !important; font-weight: 600; }}
.badge-yellow {{ color: var(--c-caution); }}
.ret-pos, .ret-neg {{ font-weight: 600; }}
</style>
</head>
<body>
<div class="saas-table-wrapper {portfolio_class}">
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
    st.iframe(resolve(saas_page_html), height=table_h + 10)