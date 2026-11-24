"""The stock page's words and figures (S182; mock-up v2 approved by the owner, 23 Nov 2026).

Pure functions: each takes what the app already worked out (the ranking row and
the whole ranking, the qualified place from `exit_watch.qualified_ranks`, the
rank trail from `dashboard_insights.rank_trails`, the sell-rule room from
`exit_watch.assess`, the holding from Portfolio's `build_portfolio_tracker`, the
plan's check day from `actions_view.next_rebalance`, Nifty Total Market from
`benchmark_indices`) and turns it into the sentences and table rows the page
draws. No figure is typed here; every number comes from those functions, and
every one is written through the shared formatter (`src/ui/formats.py`, S173).

The view is `src/ui/views/stock_view.py`; the agreed list is
`docs/STOCK_REQUIREMENTS.md`, checked on the built page by
`scripts/check_dashboard_requirements.mjs`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.ui import formats
from src.ui import watchlist_lines as wl

PERIODS = (1, 3, 6, 9, 12)
MARKET = "Nifty Total Market"   # S165: the market the 750 is measured against, named in full (S173 rule 6)
DASH = formats.DASH
_WORDS = ("First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth",
          "Eleventh", "Twelfth", "Thirteenth", "Fourteenth", "Fifteenth", "Sixteenth", "Seventeenth",
          "Eighteenth", "Nineteenth", "Twentieth")
# The 52W high counts only after this many sessions (S3, owner 13 Oct; config.HIGH_52W_MIN_OBSERVATIONS).
HIGH_SESSIONS = 126


# ── Small words ──────────────────────────────────────────────────────────────

def num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None


def tick(v) -> bool:
    return wl._tick(v)


def ordinal_word(n: int) -> str:
    """Twelfth, or 37th past the twentieth (a title starts with a word, not a figure)."""
    n = int(n)
    return _WORDS[n - 1] if 1 <= n <= len(_WORDS) else wl.fmt_ordinal(n)


def short_name(name, symbol: str) -> str:
    """The company without "Limited" / "Ltd." (as Portfolio and the Watchlist write it)."""
    text = str(name or "").strip()
    if not text or text.lower() == "nan":
        return symbol
    for tail in (" Limited", " Ltd.", " Ltd"):
        text = text.removesuffix(tail)
    return text


def market_cap(cr: float | None) -> str:
    """₹29,944 Cr; ₹1.22 lakh Cr above a lakh crore (S173 rule 2)."""
    if cr is None:
        return DASH
    if abs(cr) >= 100000:
        return f"₹{cr / 100000:.2f} lakh Cr"
    return f"{formats.inr(cr)} Cr"


@dataclass(frozen=True)
class Universe:
    """How the page names the ranked list: "Rank of 750", "12th of 750"."""
    short: str          # UNIVERSE_SHORT: "750", "1000", "> ₹2,000 Cr list", "combined universe"
    n: int              # stocks ranked

    @property
    def numeric(self) -> bool:
        return self.short.isdigit()

    @property
    def rank_label(self) -> str:
        return f"Rank of {self.short}" if self.numeric else f"Rank in the {self.short}"

    @property
    def of(self) -> str:
        return f"of {self.short}" if self.numeric else f"of the {self.n:,} in the {self.short}"

    @property
    def the(self) -> str:
        """'the 750', 'the > ₹2,000 Cr list' (the typical stock is the median of ...)."""
        return f"the {self.short}"


def universe(system: str, n: int) -> Universe:
    from src.engine.extra_universe import UNIVERSE_SHORT
    return Universe(UNIVERSE_SHORT.get(system, str(n)), int(n))


def filters_state(row) -> str:
    a, h = tick(row.get("Above 50 EMA")), tick(row.get("Near 52W High"))
    return ("passes both filters" if a and h else "fails both filters" if not a and not h
            else "passes one filter")


def failed_filters(row) -> str:
    a, h = tick(row.get("Above 50 EMA")), tick(row.get("Near 52W High"))
    # A recent listing has no 52W high to be near: say so, not that it is far below one (S193 E).
    young = (not h and num(row.get("% High")) is None and str(row.get("Short History") or "") == "Yes")
    why = f", too new to have a 52W high (none before {HIGH_SESSIONS} sessions)" if young else ""
    return ("both filters" + why if not a and not h else "the 50D EMA filter" if not a
            else "the 52W-high filter" + why if not h else "")


# ── Head ─────────────────────────────────────────────────────────────────────

def kicker(row, index_names: dict) -> list[str]:
    """Stock · SANSERA · Auto · Smallcap 250."""
    from src.ui.industry_names import short_industry
    parts = ["Stock", str(row["Symbol"])]
    ind = short_industry(row.get("Industry"))
    if ind:
        parts.append(ind)
    for t in [t.strip().upper() for t in str(row.get("Indices") or "").split(",") if t.strip()]:
        if t in index_names:
            parts.append(index_names[t])
    return parts


def title(row, uni: Universe, held: bool) -> str:
    """'Sansera Engineering is 12th of 750, passes both filters and is in the model book.'"""
    name = short_name(row.get("Company Name"), str(row["Symbol"]))
    book = "is in the model book" if held else "is not in the model book"
    return f"{name} is {wl.fmt_ordinal(int(row['Rank']))} {uni.of}, {filters_state(row)} and {book}."


def lede(row, as_of: pd.Timestamp, market12: float | None, late: bool = False) -> str:
    """The close and its date, the year against the market, the market cap."""
    close = formats.price(row.get("CMP"))
    high_day = pd.to_datetime(str(row.get("52W High Date") or "")[:10], errors="coerce")
    new_high = pd.notna(high_day) and high_day.normalize() == pd.Timestamp(as_of).normalize()
    parts = [f"{close} at the close on {formats.date(as_of)}" + (", a new 52-week closing high." if new_high else ".")]
    r12 = num(row.get("12M Return"))
    if r12 is not None:
        word = "Up" if round(r12 * 100, 1) >= 0 else "Down"
        line = f"{word} {formats.pct(abs(r12), signed_=False)} in 12 months"
        if late:   # S148, S203 st.ret.3: said, not left out
            line += f"; {MARKET}’s {formats.date(as_of, short=True)} close is not in yet"
        elif market12 is not None:
            line += f", against {formats.pct(market12)} for {MARKET}"
        parts.append(line + ".")
    mc = num(row.get("Market Cap (Cr)"))
    if mc is not None:
        parts.append(f"Market cap {market_cap(mc)}.")
    return " ".join(parts)


@dataclass(frozen=True)
class Tile:
    label: str
    value: str
    sub: str


def tiles(row, uni: Universe, q: int | None, n_qualified: int, as_of: pd.Timestamp, ln: wl.Lines,
          holding: Holding | None) -> list[Tile]:
    """Close, rank, place among the qualified, and (when held) the book's return since entry."""
    r1 = num(row.get("1M Return"))
    out = [Tile(f"Close, {wl.fmt_day(as_of)}", formats.price(row.get("CMP")),
                f"{formats.pct(r1)} in a month" if r1 is not None else "")]
    r3 = num(row.get("Rank (-3M)"))
    out.append(Tile(uni.rank_label, str(int(row["Rank"])),
                    f"{int(r3)} three months ago" if r3 is not None else "not ranked three months ago"))
    if q is not None:
        out.append(Tile("Place among the qualified", f"{wl.fmt_ordinal(q)} of {n_qualified:,}",
                        f"the book buys the top {ln.buy}"))
    else:
        out.append(Tile("Place among the qualified", "Out", f"fails {failed_filters(row)}"))
    if holding is not None and holding.ret is not None:
        sub = f"since {formats.date(holding.entry)}" if holding.entry is not None else "since its first buy"
        if holding.weight is not None:
            sub += f", {holding.weight:.1f}% of the book"
        out.append(Tile("In the model book", formats.pct(holding.ret, fraction=False), sub))
    return out


# ── 1. Rank ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Trail:
    dates: list            # 3M ago, 1M ago, now (sessions)
    ranks: list            # rank of the universe at each (None: not ranked)
    places: list           # place among the qualified at each (None: "Out")


def trail(row, dates: list, past_places: list, q_now: int | None) -> Trail:
    """The ranking's own Rank (-3M) and Rank (-1M), read on the session on or before the date
    (`rank_history_position`, Screener decision A), and the qualified place from the
    Dashboard's rank trail (`rank_trails`, through `ranking_view.qualified_trail`)."""
    ranks = [num(row.get("Rank (-3M)")), num(row.get("Rank (-1M)")), num(row.get("Rank"))]
    places = [num(p) for p in list(past_places)[:2]] + [q_now]
    return Trail(list(dates), [None if r is None else int(r) for r in ranks],
                 [None if p is None else int(p) for p in places])


def place_text(p) -> str:
    return "Out" if p is None else wl.fmt_ordinal(int(p))


def rank_heading(row, uni: Universe, q: int | None, n_qualified: int, ln: wl.Lines) -> tuple[str, str]:
    """(plain, coloured) halves of the heading: 'Twelfth of the 290 that pass both filters, '
    + 'inside the book's buy line'."""
    if q is None:
        return (f"{ordinal_word(int(row['Rank']))} {uni.of}, but out of the {n_qualified:,} the book picks from: ",
                f"it fails {failed_filters(row)}")
    where = ("inside the book’s buy line" if q <= ln.buy else
             "between the book’s buy and keep lines" if q <= ln.keep else "past the book’s keep line")
    return f"{ordinal_word(q)} of the {n_qualified:,} that pass both filters, ", where


def rank_note(row, uni: Universe, ln: wl.Lines) -> str:
    score, hz = num(row.get("Score")), num(row.get("Horizons Scored"))
    text = ("A past rank is how today’s rule ranks the stock on that day, read on the last session on or before "
            f"the date. The qualified are the stocks that pass both filters; the book buys the top {ln.buy} of them "
            f"and keeps a holding while it is in the top {ln.keep}.")
    if score is not None:
        scored = ("with all five horizons scored" if hz is not None and hz >= 5 else
                  f"with {int(hz)} of the five horizons scored" if hz is not None else "")
        text += f" Score {formats.signed(score, 3, plus=False)}" + (f", {scored}." if scored else ".")
    return text


def trail_points(places: list, keep: int) -> list[float | None]:
    """y of each point on a 170-px-high drawing: the buy line at 52, the keep line at 110;
    an "Out" sits at the bottom."""
    out = []
    for p in places:
        if p is None:
            out.append(150.0)
        else:
            out.append(round(max(10.0, min(140.0, 52 + (min(int(p), keep + 10) - 20) * 58 / max(keep - 20, 1))), 1))
    return out


# ── 2. Filters and sell rules ────────────────────────────────────────────────

@dataclass(frozen=True)
class Rule:
    name: str
    kind: str
    line: str
    fall: str
    today: str
    ok: bool


@dataclass(frozen=True)
class Ladder:
    low: float | None
    low_date: pd.Timestamp | None
    line: float | None
    ema: float | None
    high: float | None
    high_date: pd.Timestamp | None
    close: float | None

    def x(self, v) -> float:
        if v is None or self.low is None or self.high is None or self.high <= self.low:
            return 0.0
        return round(max(0.0, min(100.0, (v - self.low) / (self.high - self.low) * 100)), 1)


def ema_level(row) -> float | None:
    cmp_v, e = num(row.get("CMP")), num(row.get("% 50 EMA"))
    return None if cmp_v is None or e is None else cmp_v / (1 + e / 100)


def ladder(row, closes: pd.Series | None, high_pct: float) -> Ladder:
    """52W low (the calendar year of closes, as the 52W high is), the −20% line, 50D EMA, 52W high."""
    low = low_date = None
    if closes is not None:
        from src.engine.calendar_momentum import year_window_start
        s = pd.to_numeric(closes, errors="coerce").dropna()
        s = s.iloc[year_window_start(s.index, len(s) - 1):] if len(s) else s
        if not s.empty:
            low, low_date = float(s.min()), pd.Timestamp(s.idxmin())
    hi = num(row.get("52W High"))
    hd = pd.to_datetime(str(row.get("52W High Date") or "")[:10], errors="coerce")
    return Ladder(low, low_date, None if hi is None else hi * high_pct, ema_level(row), hi,
                  None if pd.isna(hd) else hd, num(row.get("CMP")))


def rules(row, a: dict | None, q: int | None, ln: wl.Lines, high_pct: float) -> list[Rule]:
    """Each sell rule's line, the fall that reaches it (`exit_watch.assess`'s cushions) and today."""
    a = a or {}
    ema_pct, hi_pct = num(row.get("% 50 EMA")), num(row.get("% High"))
    ema_ok, hi_ok = tick(row.get("Above 50 EMA")), tick(row.get("Near 52W High"))
    ema_c, hi_c, room = num(a.get("EMA cushion")), num(a.get("High cushion")), num(a.get("Rank room"))
    gap = round((1 - high_pct) * 100)
    hi_level = num(row.get("52W High"))

    def fall(c, ok, have=True, none="Not yet"):
        # A line the stock does not have yet is not a line it is below (S193 E: MILKYMIST, 70 sessions).
        if not ok:
            return "Below it" if have else none
        return DASH if c is None else formats.pct(c, signed_=False)

    short = str(row.get("Short History") or "") == "Yes"
    if ema_pct is None:
        e_today = DASH
    else:
        e_today = f"{formats.pct(ema_pct, fraction=False)} {'above' if ema_pct >= 0 else 'below'}"
    if hi_pct is None:
        h_today = f"None before {HIGH_SESSIONS} sessions" if short else DASH
    elif abs(hi_pct) < 0.05:
        h_today = "At the high"
    else:
        h_today = f"{formats.pct(hi_pct, fraction=False)} from it"
    return [
        Rule("Above its 50D EMA", "filter and sell rule", formats.price(ema_level(row)),
             fall(ema_c, ema_ok, ema_pct is not None, DASH), e_today, ema_ok),
        Rule(f"Within {gap}% of its 52W high", "filter and sell rule",
             formats.price(None if hi_level is None else hi_level * high_pct),
             fall(hi_c, hi_ok, hi_pct is not None, "No 52W high yet" if short else DASH), h_today, hi_ok),
        Rule(f"In the top {ln.keep} of the qualified", "sell rule", wl.fmt_ordinal(ln.keep),
             ("Out" if q is None else wl.fmt_count(int(room), "place") if room is not None and room >= 0 else "Past it"),
             place_text(q), q is not None and q <= ln.keep),
    ]


def rules_heading(a: dict | None, check: pd.Timestamp | None, high_pct: float,
                  held: bool = True) -> tuple[str, str]:
    """(coloured, plain) halves: 'Clear of all three sell rules' + '; a 10.7% fall would reach the nearest, its 50D EMA.'"""
    from src.engine.exit_watch import CLEAR, SELL, WATCH
    a = a or {}
    status = a.get("status")
    when = f"the {wl.fmt_day(check)} check" if check is not None else "the next check"
    if status == SELL:
        # S203 st.rule.1: "A holding would be sold" was said of stocks the book does not hold.
        return ("It would be sold" if held else "It would fail a sell rule",
                f" at {when} if today's price holds: it is {a.get('why') or 'past a rule'}.")
    if status == WATCH:
        return "It is close to a sell rule", f": it {a.get('why')}."
    if status == CLEAR:
        options = [(num(a.get("EMA cushion")), "its 50D EMA"),
                   (num(a.get("High cushion")), f"the −{round((1 - high_pct) * 100)}% line")]
        options = [o for o in options if o[0] is not None]
        if options:
            c, what = min(options)
            return ("Clear of all three sell rules",
                    f"; a {formats.pct(c, signed_=False)} fall would reach the nearest, {what}.")
        return "Clear of all three sell rules", "."
    return "The sell rules cannot be read", " for this stock today."


@dataclass(frozen=True)
class Holding:
    shares: int | None
    weight: float | None          # % of the book, Portfolio's Weight column
    entry: pd.Timestamp | None
    entry_price: float | None
    ret: float | None             # % since entry, Portfolio's Return since Entry %


def holding_from_table(table: pd.DataFrame | None, sym: str) -> Holding | None:
    """The stock's row of Portfolio's own table (`build_portfolio_tracker`, through `book_series`)."""
    if table is None or table.empty or "Symbol" not in table.columns:
        return None
    hit = table[table["Symbol"].astype(str) == sym]
    if hit.empty:
        return None
    r = hit.iloc[0]
    sh = num(r.get("Shares"))
    entry = pd.to_datetime(r.get("Entry Date"), errors="coerce")
    return Holding(None if sh is None else int(sh), num(r.get("Weight %")), None if pd.isna(entry) else entry,
                   num(r.get("Entry Price")), num(r.get("Return since Entry %")))


def holding_sentence(held: bool, h: Holding | None) -> tuple[str, str]:
    """(bold lead, rest): 'The model book holds it:' + ' 165 shares, 5.4% of the book, ...'."""
    if not held:
        return "The model book does not hold it.", ""
    if h is None:
        return "The model book holds it.", ""
    bits = []
    if h.shares is not None:
        bits.append(wl.fmt_count(h.shares, "share"))
    if h.weight is not None:
        bits.append(f"{h.weight:.1f}% of the book")
    if h.entry is not None:
        bits.append(f"first bought on {formats.date(h.entry)}"
                    + (f" at {formats.price(h.entry_price)}" if h.entry_price is not None else ""))
    if h.ret is not None:
        bits.append(f"{formats.pct(h.ret, fraction=False)} since")
    return "The model book holds it:", (" " + ", ".join(bits) + ".") if bits else ""


def calendar_sentence(check: pd.Timestamp | None, events: list, last_results: pd.Timestamp | None) -> str:
    """The check day, and what is announced before it (the calendar Actions reads, row 28)."""
    if check is None:
        return "The rules are checked at the month-end close."
    text = f"The rules are checked at the month-end close, next on {formats.date(check)}; "
    if events:
        said = [f"{what} on {wl.fmt_day(d)}" for d, _sym, _role, what in events]
        text += f"board meetings and ex-dates announced before then: {wl.fmt_names(said)}."
    else:
        text += "no board meeting is announced before then"
        if last_results is not None:
            text += f" (its last results meeting was on {wl.fmt_day(last_results)})"
        text += "."
    return text


def highs_note(row) -> str:
    text = ("Highs and lows are closing prices over the last 12 months, as the ranking uses them, so they can "
            "differ from an intraday high quoted elsewhere.")
    ath, hi = num(row.get("ATH")), num(row.get("52W High"))
    if ath is None:
        return text
    if hi is not None and round(ath) == round(hi):
        return text + f" The all-time high is the same close, {formats.price(ath)}."
    d = pd.to_datetime(str(row.get("ATH Date") or "")[:10], errors="coerce")
    return text + (f" The all-time closing high is {formats.price(ath)}"
                   + (f", on {formats.date(d)}." if pd.notna(d) else "."))


# ── 3. Returns and falls ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class Window:
    months: int
    start: pd.Timestamp | None
    ret: float | None             # fraction
    market: float | None          # fraction, Nifty Total Market over the same sessions
    typical: float | None         # fraction, median of the universe
    fall: float | None            # percent, negative (Max DD)
    typical_fall: float | None    # percent
    sharpe: float | None
    place: int | None             # rank by return among the universe

    @property
    def lead(self) -> float | None:
        return None if self.ret is None or self.market is None else self.ret - self.market


def window_start(index: pd.DatetimeIndex, months: int) -> pd.Timestamp | None:
    """The first session on or after the same date `months` back (`calendar_start_positions`,
    the rule every return on the site uses)."""
    from src.engine.calendar_momentum import calendar_start_positions
    idx = pd.DatetimeIndex(index)
    if idx.empty:
        return None
    pos = int(calendar_start_positions(idx, months)[-1])
    return idx[pos] if 0 <= pos < len(idx) - 1 else None


def market_return(market: pd.Series | None, start: pd.Timestamp | None, end: pd.Timestamp) -> float | None:
    """The market over the stock's own sessions: its close on the window's first session
    (the last on or before it, when the index has none that day) to the page's session (S182 d)."""
    from src.engine.dashboard_insights import value_at
    if market is None or start is None:
        return None
    a, b = value_at(market, start), value_at(market, end)
    return None if a is None or b is None or a == 0 else b / a - 1


def windows(row, rank_df: pd.DataFrame, index: pd.DatetimeIndex, market: pd.Series | None) -> list[Window]:
    end = pd.DatetimeIndex(index)[-1] if len(index) else None
    out = []
    for m in PERIODS:
        ret = num(row.get(f"{m}M Return"))
        vals = pd.to_numeric(rank_df.get(f"{m}M Return"), errors="coerce").dropna() if f"{m}M Return" in rank_df else pd.Series(dtype=float)
        falls = pd.to_numeric(rank_df.get(f"Max DD {m}M"), errors="coerce").dropna() if f"Max DD {m}M" in rank_df else pd.Series(dtype=float)
        start = window_start(index, m) if end is not None else None
        out.append(Window(
            m, start, ret, market_return(market, start, end) if end is not None else None,
            float(vals.median()) if len(vals) else None, num(row.get(f"Max DD {m}M")),
            float(falls.median()) if len(falls) else None, num(row.get(f"{m}M Sharpe")),
            None if ret is None or not len(vals) else int((vals > ret).sum()) + 1))
    return out


STEPS = (1, 2, 5, 10, 25, 50)   # % of return per line; the smallest that keeps a row within MAX_LINES
MAX_LINES = 60


@dataclass(frozen=True)
class Bar:
    n: int                 # lines in the track
    zero: int              # lines left of the zero line
    start: int             # first filled line
    filled: int            # filled lines
    part: float            # height of the partly filled line (0-1)
    part_at: int | None    # where the partly filled line sits
    market: float | None   # the market's mark, in lines from the left


def line_step(ws: list[Window]) -> int:
    """One scale for every row: the smallest step that keeps the longest bar within MAX_LINES."""
    hi = max([abs(w.ret) * 100 for w in ws if w.ret is not None]
             + [abs(w.market) * 100 for w in ws if w.market is not None] + [1.0])
    neg = max([-w.ret * 100 for w in ws if w.ret is not None and w.ret < 0]
              + [-w.market * 100 for w in ws if w.market is not None and w.market < 0] + [0.0])
    pos = max([w.ret * 100 for w in ws if w.ret is not None and w.ret > 0]
              + [w.market * 100 for w in ws if w.market is not None and w.market > 0] + [0.0])
    for s in STEPS:
        if (np.ceil(neg / s) + np.ceil(pos / s)) <= MAX_LINES:
            return s
    return int(np.ceil(hi / MAX_LINES / 50) * 50)


def bars(ws: list[Window], step: int) -> list[Bar]:
    """Line bars on one scale (PAGE_DESIGN §4.2): a gain fills right of the zero line, a fall left;
    the last line fills part of its height; the market is a small triangle."""
    neg = max([-w.ret * 100 for w in ws if w.ret is not None and w.ret < 0]
              + [-w.market * 100 for w in ws if w.market is not None and w.market < 0] + [0.0])
    pos = max([w.ret * 100 for w in ws if w.ret is not None and w.ret > 0]
              + [w.market * 100 for w in ws if w.market is not None and w.market > 0] + [0.0])
    zero = int(np.ceil(neg / step))
    n = max(zero + int(np.ceil(pos / step)) + 1, 2)
    out = []
    for w in ws:
        v = 0.0 if w.ret is None else w.ret * 100 / step
        whole, part = int(abs(v)), abs(v) - int(abs(v))
        if v >= 0:
            start, part_at = zero, zero + whole
        else:
            start, part_at = zero - whole, zero - whole - 1
        mk = None if w.market is None else round(zero + w.market * 100 / step, 2)
        out.append(Bar(n, zero, start, whole, round(part, 2), part_at if part > 0.005 else None, mk))
    return out


def returns_heading(ws: list[Window]) -> tuple[str, str, str]:
    """('', 'Ahead of Nifty Total Market on 3 of 5 windows', '; its max drawdown over 12 months was 17.0%.').

    The lede states the 12-month return; the heading leads with what the table shows beside it (S203 Q5,
    owner 24 Nov 2026: no figure twice, the lede keeps the 12M return)."""
    both = [x for x in ws if x.ret is not None and x.market is not None]
    w = next((x for x in ws if x.months == 12 and x.fall is not None), None) or next(
        (x for x in reversed(ws) if x.fall is not None), None)
    dd = (f"its max drawdown over {w.months} months was {formats.pct(abs(w.fall), signed_=False, fraction=False)}."
          if w is not None else "")
    if not both:
        return ((dd[0].upper() + dd[1:]) if dd else "No return to show for this stock yet."), "", ""
    k = sum(x.ret > x.market for x in both)
    return "", f"Ahead of {MARKET} on {k} of {len(both)} window{'s' if len(both) != 1 else ''}", ("; " + dd if dd else ".")


def returns_tone(ws: list[Window]) -> str:
    """Up when the stock is ahead on most windows it can be compared on."""
    both = [x for x in ws if x.ret is not None and x.market is not None]
    return "up" if both and 2 * sum(x.ret > x.market for x in both) > len(both) else "down"


def returns_note(as_of: pd.Timestamp, uni: Universe) -> str:
    return ("Price returns, without dividends. Each window runs from its first session on or after the same date "
            f"back to {wl.fmt_day(as_of)}; {MARKET} over the same sessions. Lead is the stock’s return "
            f"less {MARKET}’s, in points ({formats.PTS_NOTE[:-1]}). The typical stock is the median of {uni.the}. Max drawdown "
            "is the deepest fall from a peak inside the window. Sharpe is the window’s return over its volatility, as the ranking "
            f"scores it, not annualised. Rank by return is its place among {uni.the} on that window’s return alone.")


# ── 4. Price ─────────────────────────────────────────────────────────────────

def sessions_above(close: pd.Series, ema: pd.Series, last: int = 60) -> tuple[int, int]:
    """(sessions closed above the 50D EMA, sessions with an EMA) over the last `last`."""
    both = pd.DataFrame({"c": close, "e": ema}).dropna().tail(last)
    return int((both["c"] > both["e"]).sum()), len(both)


def rs_words(rs_end: float | None) -> str:
    """The stock against Nifty Total Market over 12 months, from RS (100 at the start): 'has almost tripled'."""
    if rs_end is None:
        return ""
    r = rs_end / 100
    if r >= 1.9:
        n = int(round(r))
        verb = {2: "doubled", 3: "tripled", 4: "quadrupled"}.get(n)
        if verb is None:
            return f"has grown {r:.1f} times"
        return f"has {'almost ' if r < n else 'more than ' if r > n + 0.05 else ''}{verb}"
    pct = (r - 1) * 100
    # A ratio, not a gap in points (glossary 4): "its relative strength fell 11.8%", not "11.8% behind" (S193 B).
    return f"its relative strength {'rose' if pct >= 0 else 'fell'} {formats.pct(abs(pct), signed_=False, fraction=False)}"


def price_heading(above: int, of: int, rs_end: float | None) -> tuple[str, str, str]:
    """('Above its 50D EMA on 57 of the last 60 sessions; ', 'against Nifty Total Market it has almost tripled', ' in 12 months.')"""
    a = f"Above its 50D EMA on {above} of the last {of} sessions" if of else "Too few sessions for a 50D EMA yet"
    words = rs_words(rs_end)
    if not words:
        return a + ".", "", ""
    return a + "; ", f"against {MARKET} it {words}" if words.startswith("has") else f"against {MARKET} {words}", " in 12 months."


PRICE_NOTE = ("Three panes: price with its 50D EMA, the one the ranking reads (none before 30 sessions); volume, the "
              "shares traded each session (taller bars on busier days, blue when the close rose); and RS, the stock’s "
              f"price over {MARKET}’s, set to 100 at the start of the range: above 100 it has gained more than {MARKET} "
              "since then. Prices are adjusted for corporate actions.")


# ── 5. Industry ──────────────────────────────────────────────────────────────

PEERS_SHOWN = 8


def peers(full: pd.DataFrame, row) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The sector's eight best-ranked, this stock always among them, and the whole sector."""
    ind = row.get("Industry")
    if not ind or "Industry" not in full.columns:
        return full.iloc[0:0], full.iloc[0:0]
    in_ind = full[full["Industry"] == ind].sort_values("Rank")
    shown = in_ind.head(PEERS_SHOWN)
    sym = str(row["Symbol"])
    if sym not in set(shown["Symbol"].astype(str)):
        shown = pd.concat([shown.head(PEERS_SHOWN - 1), in_ind[in_ind["Symbol"].astype(str) == sym]])
    return shown, in_ind


def industry_heading(row, in_ind: pd.DataFrame) -> str:
    from src.ui.industry_names import short_industry
    sym = str(row["Symbol"])
    order = list(in_ind["Symbol"].astype(str))
    pos = order.index(sym) + 1 if sym in order else None
    q = pd.to_numeric(in_ind.get("Qualified Rank"), errors="coerce").notna().sum() if "Qualified Rank" in in_ind else 0
    ind = short_industry(row.get("Industry"))
    head = (f"{ordinal_word(pos)} of {len(in_ind)} {ind} stocks" if pos else f"{len(in_ind)} {ind} stocks")
    return f"{head}; {int(q)} of them pass{'es' if q == 1 else ''} both filters."


def from_high(r, as_of: pd.Timestamp) -> str:
    hd = pd.to_datetime(str(r.get("52W High Date") or "")[:10], errors="coerce")
    if pd.notna(hd) and hd.normalize() == pd.Timestamp(as_of).normalize():
        return "New high"
    v = num(r.get("% High"))
    return DASH if v is None else formats.pct(v, fraction=False)


# ── 6. Data ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Action:
    kind: str
    terms: str
    ex: pd.Timestamp
    factor: float | None


def nse_actions(actions: pd.DataFrame | None, sym: str) -> list[Action]:
    """The stock's splits, bonuses, rights issues and demergers in NSE's own action list
    (`data/nse_prices/actions.parquet`), one per action (the EQ row before the BE one)."""
    if actions is None or actions.empty or "symbol" not in actions.columns:
        return []
    a = actions[actions["symbol"].astype(str) == sym].copy()
    if a.empty:
        return []
    a["_s"] = (a.get("series", pd.Series("EQ", index=a.index)).astype(str) != "EQ").astype(int)
    a = a.sort_values(["ex_date", "_s"]).drop_duplicates(["kind", "ex_date"], keep="first")
    out = []
    for _, r in a.iterrows():
        terms = " ".join(str(r.get("purpose") or "").split())
        out.append(Action(str(r.get("kind") or "action"), terms, pd.Timestamp(r["ex_date"]),
                          num(r.get("price_factor"))))
    return out


def action_line(a: Action) -> str:
    """'Split, ex 3 Jul 2026: Face Value Split (Sub-Division) - From Rs 10/- To Rs 2/-; prices before it × 0.2.'"""
    kind = {"split": "Split", "bonus": "Bonus", "rights": "Rights issue", "demerger": "Demerger"}.get(a.kind, a.kind.title())
    text = f"{kind}, ex {formats.date(a.ex)}"
    if a.terms:
        text += f": {a.terms}"
    if a.factor is not None:
        text += f"; prices before it are scaled by {a.factor:g}"
    return text


@dataclass
class DataChecks:
    items: list = field(default_factory=list)   # (ok, text)
    actions: list = field(default_factory=list)
    since: str = ""                              # " since October 2024": where NSE's lists start

    @property
    def to_read(self) -> int:
        return sum(1 for ok, _ in self.items if not ok)


def data_checks(row, as_of: pd.Timestamp, actions: list[Action], actions_from: pd.Timestamp | None) -> DataChecks:
    from src.engine.momentum import CARRIED_MARK
    gap = str(row.get("Data Gap") or "")
    ffill = num(row.get("FFill %")) or 0.0
    short = str(row.get("Short History") or "No") == "Yes"
    hz = num(row.get("Horizons Scored"))
    items = []
    if ffill <= 0 and "🔴" not in gap:
        items.append((True, "A close on every session of the last 12 months; none carried forward"))
    else:
        if ffill > 0:
            items.append((ffill <= 10, f"{formats.pct(ffill, signed_=False, fraction=False)} of the last 12 months’ "
                                       "sessions carry the previous close"))
        if "🔴" in gap:
            items.append((False, "A data gap in the last 12 months"))
    items.append((not short, f"More than {HIGH_SESSIONS} sessions of prices, so the 52-week high counts" if not short else
                  f"Fewer than {HIGH_SESSIONS} sessions of prices, so the 52W-high filter cannot pass yet"))
    if hz is not None and hz >= 5:
        items.append((True, "Ranked on all five horizons (1, 3, 6, 9 and 12 months)"))
    elif hz is not None:
        items.append((False, f"Ranked on {int(hz)} of the five horizons; the score is spread over those it has"))
    carried = CARRIED_MARK in gap
    items.append((not carried, f"The price is the last print, not the {wl.fmt_day(as_of)} close" if carried else
                  f"The price is the {wl.fmt_day(as_of)} close, the ranking’s own day"))
    since = f" since {actions_from:%B %Y}" if actions_from is not None else ""
    if not actions:
        items.append((True, f"No split, bonus, rights issue or demerger in NSE’s lists{since}"))
    src = str(row.get("ATH Source") or "")
    items.append((src == "snapshot", "All-time closing high over the full price history we hold, its weekly years filled with NSE’s daily closes"
                  if src == "snapshot"
                  else "High from a two-year window, not all-time"))
    return DataChecks(items, actions, since)


def data_heading(dc: DataChecks) -> str:
    if dc.to_read == 0 and not dc.actions:
        return ("Nothing to correct: a full year of prices with no gaps, and no split, bonus or rights issue to "
                "adjust for.")
    parts = []
    if dc.actions:
        last = dc.actions[-1]
        kind = {"rights": "rights issue"}.get(last.kind, last.kind)
        # The lists start in Oct 2024; an older action (RELIANCE's 2023 demerger) is in the history but not counted here (S193 B).
        parts.append(f"{wl.fmt_count(len(dc.actions), 'corporate action')} in NSE’s lists{dc.since}, the latest a {kind} "
                     f"ex {formats.date(last.ex)}; the prices before it are rescaled")
    if dc.to_read:
        parts.append(f"{wl.fmt_count(dc.to_read, 'check')} to read")
    text = "; ".join(parts) + "."
    return text[0].upper() + text[1:]


def foot(as_of) -> str:
    return f"{formats.data_to(as_of)}."
