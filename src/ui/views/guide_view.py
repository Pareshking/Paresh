"""Guide: what the strategy does, its formulas, and how to trade it.

Every figure here is read from the constants the engine uses
(DEFAULT_LOOKBACK_WEIGHTS, TRACK_RECORD_CONFIG, SHADOW_CONFIG), so the page
cannot drift from the code when a default changes. Each fact is stated once.
The strategy has no regime rule: the header's regime pill is described, and
nothing here suggests acting on it (UI audit 7 Oct 2026, J5).
"""

import pandas as pd
import streamlit as st

from src.core.config import DEFAULT_LOOKBACK_WEIGHTS, MOMENTUM_MONTHS
from src.engine.backtester import sector_slots
from src.engine.track_record import SHADOW_CONFIG, SHADOW_INCEPTION, TRACK_RECORD_CONFIG
from src.ui import page_kit as kit
from src.ui.components import gap_count, render_data_quality_footer

SECTIONS = ["How it works", "Formulas", "Trading it", "FAQ"]

_CFG = TRACK_RECORD_CONFIG
TOP_N = int(_CFG["top_n"])
KEEP_N = int(_CFG["buffer_n"])
EMA = int(_CFG["ema_period"])
OFF_HIGH = 1.0 - float(_CFG["high_pct"])
STOCK_CAP = float(_CFG["stock_cap"])
SECTOR_CAP = float(_CFG["sector_cap"])
COST_BPS = float(_CFG["cost_bps"])
PER_INDUSTRY = sector_slots(TOP_N, STOCK_CAP, SECTOR_CAP)


def weights_table() -> str:
    """The default lookback weights, as a Markdown table read from the constant."""
    rows = "\n".join(
        f"| {m}M | {w:.0%} | {21 * m} |"
        for m, w in zip(MOMENTUM_MONTHS, DEFAULT_LOOKBACK_WEIGHTS, strict=True)
    )
    return "| Window | Default weight | ≈ sessions |\n|---|---:|---:|\n" + rows


def _how_it_works() -> None:
    with kit.card("The strategy", "guide_strategy"):
        st.markdown(f"""
1. **Universe.** The stocks of the system chosen on Configuration. The default, the Nifty 750, is NSE's Nifty Total Market.
2. **Filters.** A stock qualifies when its close is above its {EMA}-day EMA and within {OFF_HIGH:.0%} of its 52-week high.
3. **Score.** A Sharpe ratio over each of five calendar windows, turned into z-scores and blended by weight (Formulas).
4. **Book.** The {TOP_N} best-ranked qualified stocks, equal weight. At a rebalance no stock is above {STOCK_CAP:.0%} and no industry above {SECTOR_CAP:.0%} of the book.
5. **Keep.** A holding stays while it passes both filters and ranks in the top {KEEP_N} qualified stocks.
6. **Rebalance.** Ranked at the close of each month's last session; filled at the next session's close. No stops: a holding leaves only at a rebalance.
7. **Costs.** {COST_BPS:.0f} bps of the position for each sale and the buy that replaces it.
""")

    with kit.card("Lookback weights", "guide_weights"):
        st.markdown(weights_table())
        kit.caption("Windows are calendar months, each from its start to the latest close. "
                    "The Screener ranks on the weights set on Configuration; the track record "
                    "keeps the defaults.")

    with kit.card("Market regime", "guide_regime"):
        st.markdown("""
The header's pill reads **Bullish** when the Nifty 500 closes at or above its 200-day average (the mean of its last 200 closes), and **Bearish** below it.

The strategy does not use it. In either regime the same rules pick the same number of holdings, at the same weights, and no cash is raised for the regime. Cash is held only when the caps cannot place the whole book, for example when fewer stocks pass the filters than the book holds.
""")

    with kit.card("Other pages", "guide_pages"):
        st.markdown(f"""
- **RRG** charts industries against a benchmark. It does not feed the rank.
- **Backtest** settings name a **Recommendation**: {int(SHADOW_CONFIG["top_n"])} holdings, keep while in the top {int(SHADOW_CONFIG["buffer_n"])}, {int(SHADOW_CONFIG["ema_period"])}D EMA. It is recorded beside the live system from {SHADOW_INCEPTION.strftime("%b %Y")} and is not traded.
""")


def _formulas() -> None:
    with kit.card("Score", "guide_score"):
        st.markdown(r"""
Each window $m \in \{1, 3, 6, 9, 12\}$ months opens on the first session on or after the as-of date less $m$ months. The opening price may be carried forward up to five sessions; beyond that the window has no score.

With $s$ the opening session, $t$ the as-of session and $n$ the number of daily returns between them:

$$\text{Sharpe}_m = \frac{\ln(P_t / P_s)}{\sigma_{\text{pop}}\big(\ln(P/P_{-1})\big) \times \sqrt{n}}$$

The $\sqrt{n}$ scales volatility to the window, so this is a period Sharpe, not an annualised one.

Each window's cross-section is winsorised at $\pm 3\sigma$, z-scored on the winsorised values, then clamped to $\pm 3$, in that order.

$$\text{Score} = \frac{\sum_m w_m \, z_m}{\sum_{m \,:\, z_m \text{ available}} w_m}$$

A window a stock cannot supply adds neither score nor weight.
""")

    with kit.card("Weighting", "guide_weighting"):
        st.markdown(rf"""
- **Equal weight**, the live system: $w_i = 1/N$.
- **Inverse volatility**, a Backtest setting (Weighting): $w_i = (1/\sigma_i) \,/\, \sum_j (1/\sigma_j)$, with $\sigma$ the population standard deviation of daily log returns over the last 63 sessions.

Both are then held to the {STOCK_CAP:.0%} stock and {SECTOR_CAP:.0%} industry caps. A cap is never raised; weight it cannot place is held as cash. With {TOP_N} holdings and a {STOCK_CAP:.0%} cap every name is already at {STOCK_CAP:.0%}, so inverse volatility changes nothing.
""")

    with kit.card("Costs", "guide_costs"):
        st.markdown(rf"""
$$\text{{Turnover}} = \tfrac{{1}}{{2}} \sum_i |\Delta w_i| \qquad \text{{Cost}} = \text{{Turnover}} \times {COST_BPS:.0f}\text{{ bps}}$$

Charged at each fill. Selling one holding and buying its replacement costs {COST_BPS:.0f} bps of that position.
""")

    with kit.card("Relative Rotation Graph", "guide_rrg"):
        st.markdown(r"""
Each line is an industry (the average daily return of its stocks, at least two) or one stock. With $L$ the lookback in sessions (12 weeks = 60 by default):

$$\text{RS} = \frac{\text{line growth}}{\text{benchmark growth}} \qquad \text{RS-Ratio} = \frac{\text{EMA}(\text{RS}, L/2)}{\text{SMA}\big(\text{EMA}(\text{RS}, L/2), L\big)}$$

RS-Momentum is RS-Ratio divided by its value a week earlier (a session earlier on the daily chart). Both are z-scored across the lines on the chosen date and drawn as $100 + 6.5z$, so 100 is the average line that day, not the benchmark.

| Quadrant | RS-Ratio | RS-Momentum |
|---|---|---|
| Leading | 100 or more | 100 or more |
| Weakening | 100 or more | below 100 |
| Lagging | below 100 | below 100 |
| Improving | below 100 | 100 or more |

The usual path is clockwise: Improving, Leading, Weakening, Lagging.
""")


def _trading_it() -> None:
    with kit.card("Each month", "guide_trading"):
        st.markdown("""
1. On **Actions**, read the Sell, Buy and Hold lists. Until the month's last close they are a preview at today's close.
2. Press **Kite basket**, set your capital and download the basket CSV. It holds buy orders only, each at its target weight.
3. Sell each listed sale in full yourself: the app does not know how many shares you hold.
4. Import the CSV into a Kite basket and place it on the first session of the month. The model fills at that day's close, so orders near the close follow it most closely.
5. Hold to the next rebalance. Place no stop orders.
""")


def _faq() -> None:
    with kit.card("Are the returns after tax?", "guide_faq_tax"):
        st.markdown(
            "No. Every return in the app is before tax; \"net\" means net of trading costs "
            "only. Gains on shares sold within 12 months of purchase are short-term capital "
            "gains in India.")
    with kit.card("Can I trade between rebalances?", "guide_faq_when"):
        st.markdown("The model does not. It trades once a month, on the first session, "
                    "and has no stops.")
    with kit.card(f"Why is a top-{TOP_N} stock not in the book?", "guide_faq_buffer"):
        st.markdown(
            "The book counts only stocks that pass both filters; the Screener's Rank counts "
            f"every scored stock. Holdings keep their place while they rank in the top {KEEP_N} "
            "qualified stocks, so they can hold slots a newer name would take. An industry already at "
            f"{PER_INDUSTRY} of {TOP_N} names is skipped for the next-ranked stock.")


def render_guide_view(rank_df: pd.DataFrame) -> None:
    """The Guide page: four sections, one shown at a time."""
    kit.page_head("Guide", "What the strategy does, its formulas, and how to trade it")

    section = st.segmented_control(
        "Section", SECTIONS, default=SECTIONS[0], required=True,
        key="guide_main_nav", label_visibility="collapsed",
    ) or SECTIONS[0]

    {"How it works": _how_it_works, "Formulas": _formulas,
     "Trading it": _trading_it, "FAQ": _faq}[section]()

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
