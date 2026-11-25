import hashlib
import re
import time
from html import escape as _esc

import numpy as np
import pandas as pd
import streamlit as st

from pathlib import Path

from src.ui.tokens import FONTS, css_root, resolve, serif_face_css
from src.ui import formats as _fmt



TICK_TRUE = frozenset({"✅", "✓", "TRUE", "1", "YES", "Y"})  # the same set as exit_watch._flag (S154)


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
    "Weight %": "{:.1f}%",
    "Del %": "{:.1f}%",
    "Del% 20D Avg": "{:.1f}%",
    "Del% Prev20D": "{:.1f}%",
    "Turnover %": "{:.1f}%",
    "Cost Drag %": "{:.1f}%",
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

# The serif's @font-face rules, read once from static/fonts.css (see
# tokens.serif_face_css for why they are inline rather than imported).
_SERIF_FACES = serif_face_css(
    (Path(__file__).resolve().parents[2] / "static" / "fonts.css").read_text(encoding="utf-8"))


# Never colour alone (S193 J1, owner 23 Nov 2026; GOV.UK warning text, USWDS
# alert): every caution-coloured text or box carries a "!" in a circle. The
# glyph is CSS generated content with empty alternative text ("!" / ""), so a
# screen reader does not read it; notices and boxes also start with a word
# ("Warning:", "Late:"), written by the code that draws them. Framed
# documents (the sortable tables) take the same rule from WARN_ICON_CSS.
WARN_ICON_SELECTORS = (
    ".stale-notice:not(.stale-notice-info)", ".pg-note", ".pg-callout.warn > b", ".bt-warn",
    ".badge-yellow", ".hdr-pill-warn .hdr-dot", ".dh-watch", ".xw-pill.watch", ".dh-qb-watch",
    ".cau", ".mkt-strip .ms-v.warn",
)
WARN_ICON_CSS = (
    ", ".join(f"{sel}::before" for sel in WARN_ICON_SELECTORS)
    + ' { content: "!"; content: "!" / ""; display: inline-flex; align-items: center; justify-content: center;'
    " width: 1.2em; height: 1.2em; margin-right: 0.35em; border-radius: 50%; flex: none;"
    " background: var(--c-caution); color: var(--c-white); font-family: var(--font-ui);"
    " font-size: 0.78em; font-weight: 700; line-height: 1; font-style: normal; vertical-align: 0.12em; }"
    # the pill's dot becomes the icon itself
    " .hdr-pill-warn .hdr-dot { width: auto !important; height: auto !important; background: none !important; }"
    " .hdr-pill-warn .hdr-dot::before { margin-right: 0; font-size: 0.9em; }"
    " .warn-word { font-weight: 700; }"
)


def warn_word(word: str = "Warning") -> str:
    """The leading word of a notice or box in the caution colour ("Warning:")."""
    return f'<span class="warn-word">{_esc(word)}:</span> '


def inject_custom_css() -> None:
    """The page's CSS. Colours and fonts come from src/ui/tokens.py."""
    # st.html, not st.markdown (19 Nov 2026): a markdown element waits for
    # Streamlit's Markdown renderer, about 440 KB of script fetched on first
    # use, so on a slow phone these rules arrived seconds after the st.html
    # headline and the page was drawn twice, unstyled and then styled. A
    # style-only st.html goes to Streamlit's event container, so it adds no
    # block at the top of the page either. The theme's variables come first so
    # every rule below can read them, then the serif's @font-face rules.
    st.html(f"<style>{css_root()}\n{_SERIF_FACES}\n{WARN_ICON_CSS}</style>" + _PAGE_CSS)
    # The skip link (audit F27) is the one visible-on-focus element; it keeps
    # the markdown block it always had.
    st.markdown('<a class="skip-link" href="#content">Skip to content</a>', unsafe_allow_html=True)


# The page stylesheet (S138 I6: moved out of this file, byte for byte). Read once at import;
# colours and sizes in it are var(--…) from src/ui/tokens.py, which css_root() defines.
_PAGE_CSS = (Path(__file__).with_name("page.css")).read_text(encoding="utf-8")


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
    "RETURN SINCE ENTRY %",
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
    vals = [str(v).strip() for v in col.dropna() if str(v).strip() not in ("", "–", "-")]
    return bool(vals) and all(_PCT_TEXT.fullmatch(v) for v in vals)


def render_saas_table(
    df: pd.DataFrame,
    max_height: int | None = None,
    variant: str = "default",
) -> None:
    """Render a borderless SaaS table with optional page-specific presentation variants."""
    if df.empty:
        # A filter with no match reads as a plain line with the way out, never st.info (S193 E, R4).
        from src.ui import page_kit as kit
        from src.ui import missing_words as mw
        kit.empty(mw.NO_ROWS, mw.NO_ROWS_WAY_OUT)
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
            if variant == "portfolio" and c_str in {"P&L (₹)", "P&L %", "DAY P&L (₹)", "DAY P&L %",
                                                    "P&L SINCE REBALANCE (₹)", "RETURN SINCE ENTRY %"}:
                portfolio_sign_class = "portfolio-pos" if val > 0 else ("portfolio-neg" if val < 0 else "portfolio-flat")

            if pd.isna(val) or val is None or str(val).strip() in ("", "nan", "None"):
                cells_html.append('<td class="td-center text-muted">–</td>')
                continue
            if col in pct_text_cols and str(val).strip() in ("–", "-"):
                cells_html.append('<td class="td-right text-muted">–</td>')
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
                    symbol = "▲" if val > 0 else ("▼" if val < 0 else "–")
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
                    symbol = "▲" if val > 0 else ("▼" if val < 0 else "–")
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
                            f'<td class="td-right">{_fmt.price(val)}</td>'
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
    font-size: var(--fs-13);
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
    font-size: var(--fs-12);
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
    font-size: var(--fs-12);
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
    font-size: var(--fs-13);
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
    font-size: var(--fs-13);
    color: var(--c-ink);
}}
.badge-pill {{
    display: inline-block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: var(--fs-12);
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
{WARN_ICON_CSS}
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
                const blankA = (txtA === '–' || txtA === '');
                const blankB = (txtB === '–' || txtB === '');
                if (blankA || blankB) return (blankA === blankB) ? 0 : (blankA ? 1 : -1);

                if (txtA.startsWith('▲') || txtA.startsWith('▼') || txtA.startsWith('–')) {{
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
