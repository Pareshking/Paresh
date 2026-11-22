"""The Watchlist's answers (S182; mock-up v1 approved by the owner, 22 Nov 2026).

What the Screener cannot say for a set of names the reader chose: where each sits
against the model book's lines, what the book does with it at the next rebalance,
why a name is not ranked, and what is due before the fill. Every figure comes from
the function that owns it on another page, so a stock reads the same everywhere:

  the qualified place      exit_watch.qualified_ranks (Screener, Actions, Dashboard),
                           through ranking_view.with_book_columns (S184)
  the next rebalance       actions_view.next_rebalance (Actions, Dashboard)
  the plan's word          model_plan.model_plan with canonical_book.current_book,
                           the one plan Actions and the Dashboard show (S154)
  results and ex-dates     actions_page._events, the check Actions row 28 runs
  renamed symbols          nse_identity.symbol_changes (NSE's symbolchange.csv)
  another system's rank    the published ranking that system's Screener serves

The lines (the top 20 bought, a holding kept to the 40th) are the record's own
configuration, never written here as numbers.

Formatting: every date, count and word the page writes goes through the `fmt_*`
helpers below, in one place, so they can be swapped for the site's shared formatter
(S173) in one edit. The shared table's own cells are not formatted here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.engine.track_record import TRACK_RECORD_CONFIG
from src.ui import formats

# ── Formatting: the shared formatter (S173, src/ui/formats.py); the words below are this page's own ──

MISSING = formats.DASH              # missing data; the page says why beside it
MINUS = formats.MINUS


def fmt_day(t) -> str:
    """20 Nov (a tight column or a sentence where the year is plain)."""
    return formats.date(pd.Timestamp(t), short=True)


def fmt_date(t) -> str:
    """20 Nov 2026."""
    return formats.date(pd.Timestamp(t))


def fmt_weekday(t) -> str:
    """Mon 30 Nov."""
    t = pd.Timestamp(t)
    return f"{t:%a} {t.day} {t:%b}"


def fmt_ordinal(n: int) -> str:
    """1st, 2nd, 3rd, 11th, 21st, 697th."""
    n = int(n)
    tail = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{tail}"


def fmt_count(n: int, word: str, plural: str | None = None) -> str:
    """1 place, 16 places."""
    n = int(n)
    return f"{n:,} {word if n == 1 else (plural or word + 's')}"


def fmt_system(name: str) -> str:
    """A system's name in a sentence: "the Nifty 750", "> ₹2,000 Cr", "Combined"."""
    return f"the {name}" if str(name).startswith("Nifty") else str(name)


def fmt_names(names) -> str:
    """A, B and C."""
    names = [str(x) for x in names]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


# ── The book's lines ─────────────────────────────────────────────────────────

TOP = "top"
KEEP = "keep"
PAST = "past"
FAILS = "fails"
ORDER = (TOP, KEEP, PAST, FAILS)


@dataclass(frozen=True)
class Lines:
    buy: int        # the book buys the top `buy` qualified
    keep: int       # and keeps a holding while it is in the top `keep`
    high_gap: int   # "near the 52W high": within this many percent


def lines(cfg: dict = TRACK_RECORD_CONFIG) -> Lines:
    return Lines(int(cfg["top_n"]), int(cfg["buffer_n"]), round((1 - float(cfg["high_pct"])) * 100))


def group_of(q, ln: Lines) -> str:
    """Which of the book's lines a qualified place sits within ("Out" is NaN)."""
    if q is None or pd.isna(q):
        return FAILS
    q = int(q)
    return TOP if q <= ln.buy else KEEP if q <= ln.keep else PAST


def group_heading(key: str, ln: Lines) -> tuple[str, str]:
    """(title, what it means) of a heading row."""
    return {
        TOP: (f"Top {ln.buy} qualified", "the book buys from these"),
        KEEP: (f"{fmt_ordinal(ln.buy + 1)} to {fmt_ordinal(ln.keep)} qualified", "kept if held, not bought"),
        PAST: (f"Qualified, past the {fmt_ordinal(ln.keep)}", "a holding here is sold"),
        FAILS: ("Fails a filter", "not bought; a holding is sold"),
    }[key]


def place_note(q, held: bool, above_ema: bool, near_high: bool, ln: Lines) -> str:
    """How far a stock is from its line, in words that repeat no column's figure."""
    g = group_of(q, ln)
    if g == FAILS:
        if not above_ema and not near_high:
            return "fails both filters"
        return "fails the 50D EMA filter" if not above_ema else "fails the 52W-high filter"
    q = int(q)
    if g == TOP:
        text = (f"the {fmt_ordinal(q)}, the last place the book buys" if q == ln.buy
                else f"{fmt_count(ln.buy - q, 'place')} inside the top {ln.buy}")
        return text if held else text + "; not held"
    if g == KEEP:
        return (f"the {fmt_ordinal(q)}, the last place a holding is kept" if q == ln.keep
                else f"{fmt_count(q - ln.buy, 'place')} short of the top {ln.buy}")
    return f"{fmt_count(q - ln.keep, 'place')} past the {fmt_ordinal(ln.keep)}"


# ── The plan ─────────────────────────────────────────────────────────────────

BUY, SELL, HOLD, NEXT = "Buy", "Sell", "Hold", "Next in line"


@dataclass
class BookPlan:
    """The model book's plan for the next rebalance, as Actions builds it."""
    as_of: pd.Timestamp
    check: pd.Timestamp
    fill: pd.Timestamp
    sells: list
    buys: list
    holds: list
    next_in_line: list
    book: list = field(default_factory=list)

    def word(self, sym: str) -> str:
        """Buy, Sell, Hold or Next in line; the missing mark when the plan does nothing with it."""
        if sym in self.buys:
            return BUY
        if sym in self.sells:
            return SELL
        if sym in self.holds:
            return HOLD
        if sym in self.next_in_line:
            return NEXT
        return MISSING


def book_plan(rank_df: pd.DataFrame, prices: pd.DataFrame | None, benchmark_close, system: str) -> BookPlan | None:
    """The plan Actions and the Dashboard show: the same book (`current_book`), the
    same check day (`next_rebalance` on the prices' last session) and the same
    function (`model_plan`), on the same prices. None when there is no book."""
    if prices is None or prices.empty:
        return None
    from src.ui.canonical_book import current_book
    from src.ui.model_plan import model_plan
    from src.ui.views.actions_view import next_rebalance

    as_of = pd.Timestamp(prices.index[-1])
    check, fill = next_rebalance(as_of)
    book, record = current_book(prices, benchmark_close, system)
    if book is None or book.empty:
        return None
    plan = model_plan(book, record, rank_df, prices, benchmark_close, system, check)
    return BookPlan(as_of=as_of, check=check, fill=fill, sells=list(plan.sells), buys=list(plan.buys),
                    holds=list(plan.holds), next_in_line=list(plan.next_in_line),
                    book=book["Symbol"].astype(str).tolist())


# ── The grouped table ────────────────────────────────────────────────────────

def _tick(v) -> bool:
    from src.ui.theme import is_tick_true
    return bool(is_tick_true(v))


# Index tags the ranking stores for the systems beyond the 750, in the words the
# page uses for them (PAGE_DESIGN §2: no internal names). The shared table maps
# only the 750's five tags (screener_table.INDEX_NAMES).
SYSTEM_TAGS = {"NANO": "> ₹2,000 Cr", "NANO250": "Nifty 1000"}


def grouped(view: pd.DataFrame, plan: BookPlan | None, ln: Lines) -> tuple[pd.DataFrame, list]:
    """The reader's ranked stocks in the book's lines, each group in rank order,
    with a "Place Note" and a "Plan" word per row, and the heading rows
    [(first symbol, title, count, what it means)] the shared table draws."""
    v = view.copy()

    def col(name, default):
        return v[name] if name in v.columns else pd.Series(default, index=v.index)

    qcol = pd.to_numeric(col("Qualified Rank", float("nan")), errors="coerce")
    v["_g"] = [group_of(q, ln) for q in qcol]
    v["Place Note"] = [place_note(q, bool(h), _tick(a), _tick(n), ln) for q, h, a, n in zip(
        qcol, col("Held", False), col("Above 50 EMA", True), col("Near 52W High", True))]
    v["Plan"] = [plan.word(str(s)) if plan is not None else MISSING for s in v["Symbol"]]
    # The index cell shows the first tag; the systems' own tags get their names here.
    v["Index Name"] = [SYSTEM_TAGS.get(str(x).split(",")[0].strip(), "") for x in col("Indices", "")]
    v["_o"] = v["_g"].map({k: i for i, k in enumerate(ORDER)})
    v = v.sort_values(["_o", "Rank"], kind="stable")
    heads = []
    for key in ORDER:
        part = v[v["_g"] == key]
        if len(part):
            title, meaning = group_heading(key, ln)
            heads.append((str(part["Symbol"].iloc[0]), title, len(part), meaning))
    return v.drop(columns=["_g", "_o"]), heads


# ── The words at the top ─────────────────────────────────────────────────────

def title(table: pd.DataFrame, n_saved: int, plan: BookPlan | None, ln: Lines) -> str:
    """The page's answer: how many of my names the book would buy from, and what it sells."""
    q = table.get("Qualified Rank", pd.Series(dtype=float))
    top = int(sum(group_of(x, ln) == TOP for x in q))
    stocks = "stock" if n_saved == 1 else "stocks"
    head = (f"None of your {n_saved} {stocks} is in the book's top {ln.buy}" if top == 0 else
            f"{top} of your {n_saved} {stocks} {'is' if top == 1 else 'are'} in the book's top {ln.buy}")
    if plan is None:
        return head + "."
    syms = set(table["Symbol"].astype(str))
    held = [s for s in plan.book if s in syms]
    sold = [s for s in plan.sells if s in syms]
    when = fmt_day(plan.check)
    if not held:
        return head + "."
    if not sold:
        return (f"{head}; the one it holds is kept on {when}." if len(held) == 1 else
                f"{head}; none of the {len(held)} it holds is sold on {when}.")
    return f"{head}; {len(sold)} that it holds {'is' if len(sold) == 1 else 'are'} sold on {when}."


def plan_sentence(table: pd.DataFrame, plan: BookPlan | None) -> str:
    """'If today's prices hold, on Mon 30 Nov the model book buys X and sells Y; Z is next in line.'"""
    if plan is None:
        return "The model book's plan for the next rebalance is not available just now."
    syms = list(table["Symbol"].astype(str))
    buys = [s for s in syms if s in plan.buys]
    sells = [s for s in syms if s in plan.sells]
    nxt = [s for s in syms if s in plan.next_in_line]
    lead = f"If today's prices hold, on {fmt_weekday(plan.check)} the model book"
    acts = ([f"buys {fmt_names(buys)}"] if buys else []) + ([f"sells {fmt_names(sells)}"] if sells else [])
    text = f"{lead} {' and '.join(acts)}" if acts else f"{lead} neither buys nor sells any of your stocks"
    if nxt:
        text += f"; {fmt_names(nxt)} {'is' if len(nxt) == 1 else 'are'} next in line"
    return text + "."


def lines_heading(table: pd.DataFrame, plan: BookPlan | None, ln: Lines) -> str:
    """The section's finding: the buys among my names, and the nearest name below the line."""
    syms = list(table["Symbol"].astype(str))
    q = dict(zip(syms, table.get("Qualified Rank", pd.Series([None] * len(syms)))))
    if plan is None:
        first = ""
    else:
        buys = [s for s in syms if s in plan.buys]
        first = ("None of your stocks is a buy" if not buys else
                 f"{buys[0]} is the one buy" if len(buys) == 1 else f"{fmt_names(buys)} are the buys")
    below = sorted(((int(v), s) for s, v in q.items() if v is not None and not pd.isna(v) and int(v) > ln.buy))
    second = ""
    if below:
        v, s = below[0]
        gap = v - ln.buy
        second = f"{s} is {'a place' if gap == 1 else fmt_count(gap, 'place')} short of the top {ln.buy}"
    parts = [p for p in (first, second) if p]
    if not parts:
        return "None of your stocks is qualified: each fails a filter."
    text = "; ".join(parts)
    return text[0].upper() + text[1:] + "."


# ── Not ranked ───────────────────────────────────────────────────────────────

RENAMED, ELSEWHERE, TOO_NEW, LISTED, UNKNOWN = "renamed", "elsewhere", "too new", "listed", "unknown"


@dataclass(frozen=True)
class Unranked:
    symbol: str
    kind: str
    why: str
    where: str
    replace_with: str = ""          # a renamed symbol's new ticker, when it is ranked here
    system: str = ""                # the other system it is ranked in
    link_label: str = ""


def _ranked_words(sym: str, rank_df: pd.DataFrame, universe: str, ln: Lines) -> str:
    """'TMPV ranks 697th of the 750 and fails both filters.'"""
    from src.engine.exit_watch import qualified_ranks
    row = rank_df[rank_df["Symbol"] == sym].iloc[0]
    q = qualified_ranks(rank_df).get(sym)
    if q is None or pd.isna(q):
        a, n = _tick(row.get("Above 50 EMA")), _tick(row.get("Near 52W High"))
        tail = ("fails both filters" if not a and not n else
                "fails the 50D EMA filter" if not a else "fails the 52W-high filter")
    else:
        tail = f"is {fmt_ordinal(int(q))} among the qualified"
    return f"{sym} ranks {fmt_ordinal(int(row['Rank']))} of the {len(rank_df):,} and {tail}."


def not_ranked(symbols: list, rank_df: pd.DataFrame, *, universe: str, members=(),
               changes: pd.DataFrame | None = None, listed=(), others: dict | None = None,
               ln: Lines | None = None) -> list[Unranked]:
    """Why each of `symbols` missing from the ranking is missing, and where it is.

    In order: NSE renamed it (its chain in `changes`, unless the typed symbol is
    listed today); another system ranks it (`others`: {system name: ranking}, only
    rankings of the same session); this system's list has it but it is too new to
    rank; NSE lists it but no system does; or it is not a known symbol."""
    ln = ln or lines()
    ranked = set(rank_df["Symbol"].astype(str))
    members = {str(m) for m in members}
    listed = {str(s) for s in listed}
    step = {}
    dates = {}
    if changes is not None and len(changes):
        for o, n, d in zip(changes["old"], changes["new"], changes["date"]):
            step[str(o)] = str(n)
            dates[str(o)] = d
    out = []
    for sym in symbols:
        if sym in ranked:
            continue
        new, seen = sym, set()
        while new in step and new not in seen and sym not in listed:
            seen.add(new)
            new = step[new]
        if new != sym:
            when = dates.get(sym)
            name = ""
            if new in ranked and "Company Name" in rank_df.columns:
                nm = str(rank_df.loc[rank_df["Symbol"] == new, "Company Name"].iloc[0] or "").strip()
                for tail in (" Limited", " Ltd.", " Ltd"):
                    nm = nm.removesuffix(tail)
                name = f" ({nm})" if nm and nm != "nan" else ""
            why = (f"NSE changed the symbol to {new}{name}"
                   + (f" on {fmt_date(when)}." if when is not None and not pd.isna(when) else "."))
            there = next(((nm, f) for nm, f in (others or {}).items()
                          if f is not None and new in set(f["Symbol"].astype(str))), None)
            if new in ranked:
                where = _ranked_words(new, rank_df, universe, ln)
            elif there is not None:
                r = int(there[1].loc[there[1]["Symbol"].astype(str) == new, "Rank"].iloc[0])
                where = (f"{new} is not in {fmt_system(universe)}; it ranks {fmt_ordinal(r)} of "
                         f"{len(there[1]):,} in {fmt_system(there[0])}.")
            else:
                where = f"{new} is not ranked in {fmt_system(universe)} either."
            out.append(Unranked(sym, RENAMED, why, where, replace_with=new if new in ranked else ""))
            continue
        hit = next(((name, frame) for name, frame in (others or {}).items()
                    if frame is not None and sym in set(frame["Symbol"].astype(str))), None)
        if hit is not None:
            name, frame = hit
            r = int(frame.loc[frame["Symbol"].astype(str) == sym, "Rank"].iloc[0])
            out.append(Unranked(sym, ELSEWHERE, f"Not a member of {fmt_system(universe)}.",
                                f"Ranks {fmt_ordinal(r)} of {len(frame):,} in {fmt_system(name)}.", system=name,
                                link_label=f"See it in {fmt_system(name)}"))
            continue
        if sym in members:
            out.append(Unranked(sym, TOO_NEW, f"In {fmt_system(universe)}, but too new to rank.",
                                "It needs about three months of prices."))
            continue
        if sym in listed:
            out.append(Unranked(sym, LISTED, "Listed on NSE, but in none of the systems' lists.", MISSING))
            continue
        out.append(Unranked(sym, UNKNOWN, "Not a symbol NSE lists today.", MISSING))
    return out


def not_ranked_heading(rows: list[Unranked], universe: str) -> str:
    """'2 of your symbols are not in the Nifty 750: one was renamed, one is in > ₹2,000 Cr.'"""
    n = len(rows)
    words = {1: "one", 2: "two", 3: "three"}
    parts = []
    for kind, say in ((RENAMED, "renamed"), (TOO_NEW, "too new to rank"), (LISTED, "in no system's list"),
                      (UNKNOWN, "not a known symbol")):
        k = sum(r.kind == kind for r in rows)
        if k:
            verb = ("was" if k == 1 else "were") if kind == RENAMED else ("is" if k == 1 else "are")
            parts.append(f"{words.get(k, str(k))} {verb} {say}")
    for name in dict.fromkeys(r.system for r in rows if r.kind == ELSEWHERE):
        k = sum(r.system == name for r in rows)
        parts.append(f"{words.get(k, str(k))} {'is' if k == 1 else 'are'} in {fmt_system(name)}")
    head = (f"1 of your symbols is not in {fmt_system(universe)}" if n == 1
            else f"{n} of your symbols are not in {fmt_system(universe)}")
    return head + (": " + ", ".join(parts) if parts else "") + "."


# ── Before the fill ──────────────────────────────────────────────────────────

def fill_heading(events: list, fill: pd.Timestamp) -> str:
    when = f"the {fmt_day(fill)} fill"
    if not events:
        return f"No results meeting or ex-date is announced for your stocks before {when}."
    names = list(dict.fromkeys(str(e[1]) for e in events))
    return (f"{fmt_count(len(events), 'meeting or ex-date', 'meetings or ex-dates')} "
            f"before {when}: {fmt_names(names)}.")


def reported_sentence(reported: pd.DataFrame | None, n_ranked: int) -> str:
    """When the listed stocks last held a results meeting (the last two months)."""
    if reported is None or not len(reported) or not n_ranked:
        return ""
    r = reported.sort_values("date")
    first, last = r.iloc[0], r.iloc[-1]
    span = (f"on {fmt_day(first['date'])} ({first['symbol']})" if len(r) == 1 else
            f"between {fmt_day(first['date'])} ({first['symbol']}) and {fmt_day(last['date'])} ({last['symbol']})")
    if n_ranked == 1:
        return f"{first['symbol']} held its last results meeting on {fmt_day(first['date'])}."
    who = ("Every ranked stock on your list" if len(r) == n_ranked else
           f"{len(r)} of the {n_ranked} ranked stocks on your list")
    return f"{who} held its last results meeting {span}."
