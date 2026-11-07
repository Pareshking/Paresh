"""The Guide: how the ranking, the filters, the book and the record work.

One reading column, plain headings, formulas as text (audit F51). Every
statement here is checked against the code it describes:

* windows, Sharpe, winsorising and renormalising: src/engine/calendar_momentum.py
* filters, buffer, costs, weighting: src/engine/backtester.py, track_record.py
* the rotation graph: src/ui/views/rrg_view.py

No outcome is promised and no allocation is advised: the model has no regime
switch, no stops and no cash target, so the Guide does not suggest any.
What was removed from the engine is in CHANGELOG.md, not here.
"""

import pandas as pd
import streamlit as st

from src.engine.track_record import TRACK_RECORD_CONFIG
from src.ui import page_kit as kit
from src.ui.components import gap_count, render_data_quality_footer

_CSS = """<style>
.gd{max-width:760px;font-family:'IBM Plex Sans',system-ui,sans-serif;color:var(--c-text_2);
    font-size:15px;line-height:1.65}
.gd nav{display:flex;flex-wrap:wrap;gap:4px 18px;font-size:13.5px;padding:0 0 4px}
.gd nav a{color:var(--c-ink);text-decoration:none;border-bottom:1px solid var(--c-rule_strong)}
.gd nav a:hover,.gd nav a:focus-visible{border-bottom-color:var(--c-ink)}
.gd h2{font-size:18px;font-weight:600;color:var(--c-ink);margin:30px 0 8px;padding-top:12px;
    border-top:1px solid var(--c-ink);scroll-margin-top:72px}
.gd h3{font-size:15px;font-weight:600;color:var(--c-ink);margin:18px 0 4px}
.gd p,.gd li,.gd dd{font-size:15px;line-height:1.65;color:var(--c-text_2)}
.gd p{margin:0 0 10px}
.gd ol,.gd ul{margin:0 0 10px;padding-left:20px}
.gd li{margin:2px 0}
.gd b{color:var(--c-ink);font-weight:600}
.gd pre{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size: 13.5px;line-height:1.6;
    color:var(--c-ink);background:var(--c-subtle);border-left:2px solid var(--c-rule_strong);
    padding:8px 12px;margin:6px 0 12px;white-space:pre-wrap}
.gd dl{margin:0}
.gd dt{font-weight:600;color:var(--c-ink);margin-top:14px}
.gd dd{margin:2px 0 0}
.gd .k{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:13.5px;color:var(--c-ink)}
</style>"""


def _body() -> str:
    cfg = TRACK_RECORD_CONFIG
    top_n, buffer_n, cost = int(cfg["top_n"]), int(cfg["buffer_n"]), float(cfg["cost_bps"])
    w = dict(zip(("1M", "3M", "6M", "9M", "12M"), cfg["config_weights"]))
    stock_cap, sector_cap = float(cfg["stock_cap"]), float(cfg["sector_cap"])
    per_industry = int(sector_cap * top_n)
    weights = " · ".join(f"{k} {float(v) * 100:.0f}%" for k, v in w.items())
    score = " + ".join(f"{float(v):.2f}·z({k})" for k, v in w.items())
    return f"""
<div class="gd">
<nav aria-label="On this page">
<a href="#steps">The five steps</a><a href="#score">The score</a><a href="#filters">Filters</a>
<a href="#book">The book</a><a href="#weights">Weighting</a><a href="#rrg">Rotation graph</a>
<a href="#acting">Acting on it</a><a href="#faq">Questions</a>
</nav>

<h2 id="steps">The five steps</h2>
<ol>
<li><b>Universe.</b> About 750 stocks: the Nifty Total Market as NSE published it on each date,
so a stock counts only while it was a member. Prices are daily closes, adjusted for splits and bonuses.</li>
<li><b>Score.</b> Each stock's return over 1, 3, 6, 9 and 12 months, divided by its volatility over
the same window; each window ranked against the other stocks; the five blended ({weights}).</li>
<li><b>Filters.</b> Above its 50-day EMA and within 20% of its 52-week high.</li>
<li><b>Book.</b> The top {top_n} stocks that pass both filters, equal weight, at most {per_industry} from
one industry. A holding stays while it ranks within the top {buffer_n} and passes both filters.</li>
<li><b>Trades.</b> Once a month: the ranking at the month's last close, the trades at the next
session's close. Nothing is sold in between.</li>
</ol>
<p>The figures these steps produce are on Portfolio and Backtest; none is quoted here.</p>

<h2 id="score">The score</h2>
<h3>Windows are calendar months</h3>
<p>A window of <i>m</i> months opens on the first session on or after the same date <i>m</i> months
earlier. If a stock did not trade that day, its last close up to five sessions before stands in;
older than that, the window has no value for that stock.</p>
<h3>Return over volatility, per window</h3>
<pre>return_m     = ln(P_today / P_open)
volatility_m = SD of daily log returns in the window × √n     (population SD, n = sessions)
sharpe_m     = return_m / volatility_m</pre>
<p>This is a statistic for the window, not an annualised Sharpe ratio, and is not comparable with one.</p>
<h3>Ranked against the other stocks</h3>
<p>For each window, across the stocks that day: values beyond three standard deviations are pulled in
to that limit, the result is turned into a z-score, and the z-score is capped at ±3, in that order.</p>
<pre>score = ({score}) / (sum of the weights of the windows the stock has)</pre>
<p>A stock without, say, a 12-month history is scored on the windows it has, with their weights
rescaled; it is not given an average 12-month value. These are the record's weights. The
Configuration page can change them for the Screener and the Backtest; the record and the model book
on Portfolio and Actions keep these.</p>

<h2 id="filters">Filters</h2>
<ul>
<li><b>Trend:</b> the close above its 50-day exponential moving average.</li>
<li><b>Near the high:</b> the close at or above 80% of its 52-week high.</li>
</ul>
<p>A stock that fails either is not bought; a holding that fails either at a rebalance is sold.
No liquidity filter is applied, in the record or by default in the Backtest.</p>

<h2 id="book">The book</h2>
<ul>
<li><b>Size:</b> {top_n} stocks, each 1/{top_n} of the account at the rebalance, then held as they
move until the next one.</li>
<li><b>Caps:</b> no stock above {stock_cap:.0%} and no NSE industry above {sector_cap:.0%} of the book at a
rebalance, so at most {per_industry} of the {top_n} from one industry; the next-ranked stock from another
industry takes the place. Between rebalances prices can carry an industry past the cap until the next
rebalance trims it.</li>
<li><b>Buffer:</b> a holding is kept while its rank among stocks passing both filters stays within
{buffer_n}, so a move from 18th to 24th does not trigger a sale and a repurchase.</li>
<li><b>Costs:</b> {cost:.0f} basis points for a round trip (buying and later selling), charged on what
is traded. Tax on gains is not modelled anywhere: every return on the site is before tax.</li>
<li><b>No stops:</b> a holding leaves only at a monthly rebalance.</li>
</ul>

<h2 id="weights">Weighting</h2>
<p><b>Equal weight</b> is what the record uses: each holding 1/{top_n} of the account.</p>
<p><b>Inverse volatility</b> can be tried in the Backtest: each holding's weight is proportional to
one over its volatility over the last 63 sessions.</p>
<pre>w_i = (1 / σ_i) / Σ_j (1 / σ_j)</pre>
<p>It gives calmer stocks more weight. Whether that lowers the book's volatility or drawdown depends
on the period; the Backtest shows both side by side.</p>

<h2 id="rrg">Rotation graph</h2>
<p>For each industry, the average daily return of its stocks is compounded and divided by the
benchmark's compounded return: its relative-strength line.</p>
<ul>
<li><b>RS-Ratio</b> (across): the line, smoothed with an exponential average over about six weeks,
divided by its own twelve-week average.</li>
<li><b>RS-Momentum</b> (up): RS-Ratio divided by its value one week earlier.</li>
</ul>
<p>Both are then expressed across industries as 100 + 6.5 × z-score, so 100 is the average industry.
The four quarters: <b>Leading</b> (both above 100), <b>Weakening</b> (ratio above, momentum below),
<b>Lagging</b> (both below), <b>Improving</b> (ratio below, momentum above). Industries often move
through them clockwise. The graph is a picture of rotation; it does not feed the ranking.</p>

<h2 id="acting">Acting on it</h2>
<ol>
<li>After the month's last close, open <b>Actions</b>: it lists what to sell and what to buy.</li>
<li>Place the sells by hand, in full. Then download the Kite basket there (buy orders only, each at its
target weight of the capital you enter) and import it in Zerodha Kite under Orders, Baskets, Import.</li>
<li>Place the orders on the next session. The record fills at that session's close, so orders near
the close follow it most closely.</li>
<li>Hold until the next month-end. <b>Actions</b> shows during the month how close each holding is to
a rule; nothing is sold before the rebalance.</li>
</ol>

<h2 id="faq">Questions</h2>
<dl>
<dt>Are the returns after tax?</dt>
<dd>No. "Net" means after the modelled trading costs only. A monthly rebalance realises most gains
within twelve months, which in India are short-term capital gains, so after tax the outcome is lower
than every figure shown.</dd>
<dt>Why is a stock ranked 14th not in the book?</dt>
<dd>Either it fails a filter (the rank counts every stock; the book takes only those passing both), or
the book is full of holdings still inside the buffer of {buffer_n}. New stocks enter only as holdings
leave.</dd>
<dt>Why does a stock's rank differ from its qualified rank?</dt>
<dd>The rank places it among all stocks in the universe; the qualified rank, among those passing both
filters. The book and the buffer use the qualified rank.</dd>
<dt>Does the market trend change the model?</dt>
<dd>No. "Trend: up" or "down" in the header compares the Nifty 500 with its 200-day EMA for context.
The model holds {top_n} stocks in every market and keeps no cash target.</dd>
<dt>What do the costs cover?</dt>
<dd>{cost:.0f} basis points a round trip, meant to cover brokerage, exchange and SEBI fees, GST on them,
stamp duty, STT and the bid-ask spread. Capital-gains tax is not included.</dd>
</dl>
</div>
"""


def render_guide_view(rank_df: pd.DataFrame) -> None:
    kit.page_head(
        "Guide",
        "How the ranking, the filters, the book and the record work, and how to act on them",
    )
    st.html(_CSS + _body())
    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
