"""The Guide: how the ranking, the filters, the book and the record work.

One reading column, plain headings, formulas as text (audit F51). Every
statement here is checked against the code it describes:

* windows, Sharpe, winsorising and renormalising: src/engine/calendar_momentum.py
* filters, buffer, costs, weighting: src/engine/backtester.py, track_record.py

No outcome is promised and no allocation is advised: the model has no regime
switch, no stops and no cash target, so the Guide does not suggest any.
What was removed from the engine is in CHANGELOG.md, not here.
"""

import pandas as pd
import streamlit as st

from src.engine.backtester import EMA_MIN_PRINTS
from src.engine.track_record import TRACK_RECORD_CONFIG
from src.ui import page_kit as kit
from src.ui.components import gap_count, render_data_quality_footer

_CSS = """<style>
.gd{max-width:760px;font-family:'IBM Plex Sans',system-ui,sans-serif;color:var(--c-text_2);
    font-size: var(--fs-15);line-height:1.65}
.gd nav{display:flex;flex-wrap:wrap;gap:4px 18px;font-size: var(--fs-13);padding:0 0 4px}
.gd nav a{color:var(--c-ink);text-decoration:none;border-bottom:1px solid var(--c-rule_strong)}
.gd nav a:hover,.gd nav a:focus-visible{border-bottom-color:var(--c-ink)}
.gd h2{font-size: var(--fs-17);font-weight:600;color:var(--c-ink);margin:30px 0 8px;padding-top:12px;
    border-top:1px solid var(--c-ink);scroll-margin-top:72px}
.gd h3{font-size: var(--fs-15);font-weight:600;color:var(--c-ink);margin:18px 0 4px}
.gd p,.gd li,.gd dd{font-size: var(--fs-15);line-height:1.65;color:var(--c-text_2)}
.gd p{margin:0 0 10px}
.gd ol,.gd ul{margin:0 0 10px;padding-left:20px}
.gd li{margin:2px 0}
.gd b{color:var(--c-ink);font-weight:600}
.gd pre{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size: var(--fs-13);line-height:1.6;
    color:var(--c-ink);background:var(--c-subtle);border-left:2px solid var(--c-rule_strong);
    padding:8px 12px;margin:6px 0 12px;white-space:pre-wrap}
.gd dl{margin:0}
.gd dt{font-weight:600;color:var(--c-ink);margin-top:14px}
.gd dd{margin:2px 0 0}
.gd .k{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size: var(--fs-13);color:var(--c-ink)}
</style>"""


def _body() -> str:
    cfg = TRACK_RECORD_CONFIG
    top_n, buffer_n, cost = int(cfg["top_n"]), int(cfg["buffer_n"]), float(cfg["cost_bps"])
    w = dict(zip(("1M", "3M", "6M", "9M", "12M"), cfg["config_weights"]))
    stock_cap, sector_cap = float(cfg["stock_cap"]), float(cfg["sector_cap"])
    per_industry = int(sector_cap * top_n)
    ema_period, high_pct = int(cfg["ema_period"]), float(cfg["high_pct"])
    # Dates and counts for the two forward-dated rules and the warm-up come
    # from the pinned config and the code, never typed here: the Guide once
    # quoted a hardcoded "2.9% above its 200D EMA" against the 3.4% the header
    # was showing on the same render (slot 10, 10 Nov 2026).
    warmup_from = pd.Timestamp(cfg["ema_warmup_from"]).strftime("%-d %b %Y")
    members_from = pd.Timestamp(cfg["members_only_scoring_from"]).strftime("%-d %b %Y")
    min_prints = int(EMA_MIN_PRINTS)
    # A new listing's wait (S193 B, G1: the Guide said "about six weeks", the 30-close EMA; ranking
    # needs 63 sessions and the 52-week high 126).
    from src.core.config import HIGH_52W_MIN_OBSERVATIONS
    from src.engine.momentum import MIN_OBSERVATIONS
    min_ranked, min_high = int(MIN_OBSERVATIONS), int(HIGH_52W_MIN_OBSERVATIONS)
    # How the 52-week high was actually measured in this run, as the freshness
    # ribbon publishes it (app.py records PriceFrames.high_basis).
    from src.core import startup_metrics as _metrics

    high_basis = str(_metrics.snapshot().get("facts", {}).get("price_high_basis") or "").strip()
    basis_note = f" Today's tables measured it on {high_basis}." if high_basis else ""
    weights = " · ".join(f"{k} {float(v) * 100:.0f}%" for k, v in w.items())
    # The steps describe the Nifty 750; the other systems run them on their own lists (S193 C).
    from src.engine.extra_universe import SYSTEM_1000, SYSTEM_NAMES, SYSTEM_NANO
    import html as _html
    others = _html.escape(f"{SYSTEM_NAMES[SYSTEM_1000]} and the {SYSTEM_NAMES[SYSTEM_NANO]} list")
    score = " + ".join(f"{float(v):.2f}·z({k})" for k, v in w.items())
    return f"""
<div class="gd">
<nav aria-label="On this page">
<a href="#steps">The five steps</a><a href="#score">The score</a><a href="#filters">Filters</a>
<a href="#book">The book</a><a href="#weights">Weighting</a>
<a href="#acting">Acting on it</a><a href="#faq">Questions</a>
</nav>

<h2 id="steps">The five steps</h2>
<ol>
<li><b>Universe.</b> About 750 stocks: the Nifty Total Market as NSE published it on each date,
so a stock counts only while it was a member. Prices are daily closes, adjusted for splits, bonuses,
consolidations, rights issues and demergers; the history from 2010 also takes out dividends of 10% or more.
The {others} follow the same steps on their own lists.</li>
<li><b>Score.</b> Each stock's return over 1, 3, 6, 9 and 12 months, divided by its volatility over
the same window; each window ranked against the other stocks; the five blended ({weights}).</li>
<li><b>Filters.</b> Above its 50D EMA and within 20% of its 52-week high.</li>
<li><b>Book.</b> The top {top_n} stocks that pass both filters, at most {per_industry} from one sector.
A holding stays while it ranks within the top {buffer_n} and passes both filters. From the 30 Nov 2026
rebalance every holding goes back to 5% twice a year (March and September); in between, winners run
(see Weighting).</li>
<li><b>Trades.</b> Once a month: the ranking at the month's last close, the trades at the next
session's close. Nothing is sold in between.</li>
</ol>
<p>The figures these steps produce are on Portfolio and Backtest; the one test quoted here, under Weighting, is dated.</p>

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
<p>A stock without, say, 12 months of history is scored on the windows it has, with their weights
rescaled; it is not given an average value for the missing window. These are the record's weights. The
Configuration page can change them for the Screener and the Backtest; the record and the model book
on Portfolio and Actions keep these.</p>
<h3>How it differs from NSE's and MSCI's momentum indices</h3>
<p>The same family: each is a return divided by volatility, turned into a z-score and capped at ±3. NSE's Nifty200
Momentum 30 and MSCI's momentum indices use only 6 and 12 months, weighted half and half, and leave out the latest
month; NSE divides by the volatility of 12 months of daily returns, MSCI by that of 3 years of weekly returns. This score adds 1, 3 and
9 months, runs to the latest close, and divides each window by the volatility inside it. A version that leaves out the
latest five sessions runs beside the record as a shadow book (Portfolio).</p>
<p>From the {members_from} ranking the score is worked out over the index members of that day only, as the
Screener has always done, so the same stock gets the same score on every page; earlier months were
scored over a wider set of stocks and are left exactly as they were recorded.</p>

<h2 id="filters">Filters</h2>
<ul>
<li><b>Trend:</b> the close above its {ema_period}D EMA. An EMA (exponential moving average) is an average of past
closes that gives the latest days the most weight, so it turns sooner than a simple average (SMA), which weights
every day alike. The site writes them 50D EMA and 200D EMA: the average over 50 or 200 sessions.</li>
<li><b>Near the high:</b> the close at or above {high_pct:.0%} of its 52-week high.</li>
</ul>
<p>A stock that fails either is not bought; a holding that fails either at a rebalance is sold.
No liquidity filter is applied, in the record or by default in the Backtest.</p>
<h3>A stock needs {min_prints} closes before it has a {ema_period}D EMA</h3>
<p>From the {warmup_from} ranking a stock with fewer than {min_prints} daily closes has no
{ema_period}D EMA at all, so it cannot be above one and cannot pass the trend filter. It is
not ranked low; it is simply not among the stocks that qualify, and it cannot be bought. This is the
rule the Screener has always used, and the months already recorded replay as they were.</p>
<h3>A new listing waits about six months</h3>
<p>No stock is ranked before {min_ranked} sessions of prices, and the 52-week high needs {min_high} closes
before the near-the-high filter can pass. A recent listing therefore waits about six months of trading
before it can be bought.</p>
<h3>The 52-week high is read from closes</h3>
<p>The high the filter measures against is the highest <i>close</i> of the last year, not the highest
price touched during a day. The price history the record is struck on carries closes only.{basis_note}
A spike above the closing price is not counted. The high is therefore a little lower, and every stock
reads as a little nearer to it than a chart drawn from intraday prices would show. Every count of
stocks near their high on this site, the one in the header included, is counted on that basis. Such a
figure only lines up with another measured the same way.</p>

<h2 id="book">The book</h2>
<ul>
<li><b>Size:</b> {top_n} stocks, each 1/{top_n} of the account at a reset (the March and September
rebalances); in between, a holding that stays is held as it moves, and a new buy is 1/{top_n} of the
account as it stood at the last reset (see Weighting).</li>
<li><b>Caps:</b> a new buy is {stock_cap:.0%} of the account as it stood at the last reset (a little more
than {stock_cap:.0%} of today's if the book has fallen since) and no NSE sector is above
{sector_cap:.0%} of the book at a rebalance, so at most {per_industry} of the {top_n} from one sector; the
next-ranked stock from another sector takes the place. From the 30 Nov 2026 rebalance a holding that
is kept is trimmed only above 15%, not back to {stock_cap:.0%} (see Weighting), so a holding whose price
has risen sits above the buy size until a reset. Between rebalances prices can carry a sector past
its cap until the next rebalance trims it.</li>
<li><b>Buffer:</b> a holding is kept while its rank among stocks passing both filters stays within
{buffer_n}, so a move from 18th to 24th does not trigger a sale and a repurchase.</li>
<li><b>Costs:</b> {cost:.0f} basis points for a round trip (buying and later selling), charged on what
is traded. Returns are before tax, except the after-tax rows in the Backtest's section 4 and the
test quoted under Weighting.</li>
<li><b>No stops:</b> a holding leaves only at a monthly rebalance.</li>
</ul>

<h2 id="weights">Weighting</h2>
<p><b>Equal weight</b> sets each new book's targets: 1/{top_n} of the account a holding.</p>
<p><b>Six-monthly reset</b> (from the 30 Nov 2026 rebalance). Until then every rebalance put each
holding back to 1/{top_n}, selling some of a winner and topping up a laggard. From then that happens
twice a year, at the March and September rebalances. In between, a holding that stays is left as its
price moved it unless it is above 15%, when it is cut to 15%, and each new buy is 5% of the account
as it stood at the last reset, paid from cash; when cash is short the new names get fewer shares, and
no holding is sold to pay for them. No sector is above 40% after a rebalance. In the test behind
the decision (8 Nov 2026, with an estimate of tax) the monthly reset earned
15.4% a year after tax and the six-monthly 15.3%, with far fewer trades between resets. That test ran
on the Nifty 500 from 2010, as the Backtest does, because Nifty Total Market starts only on
14 Oct 2021. The Backtest
re-runs the record's rules every week, so its after-tax figure can differ by a little.
Against the alternative of simply holding the index, both price only, both sold at the end and taxed:
the Backtest page shows the figures for the record's rules from 2010, re-run every week (section 4).
Months before the change keep the old rule.</p>
<p><b>Inverse volatility</b> can be tried in the Backtest: each holding's weight is proportional to
one over its volatility over the last 63 sessions.</p>
<pre>w_i = (1 / σ_i) / Σ_j (1 / σ_j)</pre>
<p>It gives calmer stocks more weight. Whether that lowers the book's volatility or drawdown depends
on the period; run the Backtest with each weighting to compare them.</p>

<h2 id="acting">Acting on it</h2>
<ol>
<li>After the month's last close, open <b>Actions</b>: it lists what to sell and what to buy.</li>
<li>Sell in full, then buy. The Kite basket there carries the buys, each at its target weight of the
capital you enter, and, for the model book, its sells at the model book's share counts (check them
against your own holdings). Import it in Zerodha Kite under Orders, Baskets, Import.</li>
<li>Place the orders on the next session. The record fills at that session's close, so orders near
the close follow it most closely.</li>
<li>Hold until the next month-end. <b>Actions</b> shows during the month how close each holding is to
a rule; nothing is sold before the rebalance.</li>
</ol>

<h2 id="faq">Questions</h2>
<dl>
<dt>Are the returns after tax?</dt>
<dd>No, except the after-tax rows in the Backtest's section 4. "Net" means after the modelled trading
costs only. A monthly rebalance realises most gains within twelve months, which in India are short-term
capital gains, so after tax the outcome is lower than every before-tax figure shown.</dd>
<dt>Why is a stock ranked 14th not in the book?</dt>
<dd>Either it fails a filter (the rank counts every stock; the book takes only those passing both), or
the book is full of holdings still inside the buffer of {buffer_n}. New stocks enter only as holdings
leave.</dd>
<dt>Why does a stock's rank differ from its qualified rank?</dt>
<dd>The rank places it among all stocks in the universe; the qualified rank, among those passing both
filters. The book and the buffer use the qualified rank.</dd>
<dt>Does Nifty Total Market's trend change the model?</dt>
<dd>No. The header's "... % above its 200D EMA" (or below) compares the index it names with its 200D EMA, for context.
The model holds {top_n} stocks whatever the index does and keeps no cash target.</dd>
<dt>What does "pts" mean?</dt>
<dd>pts = percentage points: 12% − 8% = 4 pts. A gap between two returns is written in points, by subtraction:
+20.0% against +5.0% is 15.0 pts. Written as a percentage it could be read as a relative return (14.3%).
"bps" (basis points, hundredths of a point) is kept for costs.</dd>
<dt>What is a max drawdown?</dt>
<dd>The worst fall from a peak to a later low over a window: "6M max drawdown" is the deepest such fall in the
last six months. Plain "drawdown" is how far a price or the book is below its peak today.</dd>
<dt>What do the costs cover?</dt>
<dd>{cost:.0f} basis points a round trip, meant to cover brokerage, exchange and SEBI fees, GST on them,
stamp duty, STT and the bid-ask spread. STT (0.1% on the buy and on the sell) and stamp duty (0.015% on
the buy) take about 22 bps of it; what is left pays the spread, which has not been measured. The
Backtest page re-runs the record's rules from 2010 at 60 and 100 bps every week (section 4). Capital-gains
tax is not included.</dd>
</dl>
</div>
"""


def render_guide_view(rank_df: pd.DataFrame) -> None:
    # A title that answers the reader's question, the page's name as the kicker (S203 Q1, owner 24 Nov 2026).
    kit.page_head(
        "How the ranking picks the book, and how to act on it.",
        "The ranking, the filters, the book and the record, step by step",
        kicker="Guide",
    )
    st.html(_CSS + _body())
    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
