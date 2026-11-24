"""Actions, rebuilt from docs/ACTIONS_REQUIREMENTS.md (S151, owner 20 Nov 2026).

What the record would do at the next rebalance on today's closes: what to sell and
why, what to buy and how much, which holds are close to a line, and what could still
change before the close that counts. The plan is the Dashboard's (`src/ui/model_plan`),
the ranks are the one rank among the qualified on every page, and the model book's
amounts are its value today (`src/ui/book_series`), the figure Portfolio shows.
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import streamlit as st

from src.engine import book_exposure as bx
from src.engine.exit_watch import RANK_SCALE, CLEAR, SELL, STATUS_LABEL, UNKNOWN, WATCH, Rules, assess, nearest_rule, qualified_ranks
from src.engine.track_record import TRACK_RECORD_CONFIG
from src.ui.system_param import stock_href
from src.ui import formats as _fmt
from src.ui import missing_words as mw
from src.ui import page_kit as kit
from src.ui.formats import price as _fmt_price
from src.ui.views.dashboard_home_view import HOME_CSS, emit, html_of, sg
from src.ui.views.portfolio_page import PF_CSS, _head, _kpis, _sec, dshort, inr, pct, short, tone

e = html.escape


@dataclass
class Plan:
    """Everything the page draws, gathered once (for tests and the requirements check)."""
    source: str                       # "Model book" or "My holdings"
    as_of: pd.Timestamp
    check: pd.Timestamp
    fill: pd.Timestamp
    sessions: int
    holiday_note: str
    sells: list
    buys: list
    holds: list
    next_in_line: list
    weights: pd.Series
    assess: pd.DataFrame
    trails: dict
    qrank: pd.Series
    rank_df: pd.DataFrame
    value: float | None               # the book's value today (model book) or the capital box (yours)
    shares: dict = field(default_factory=dict)      # model book: shares held now
    since: dict = field(default_factory=dict)       # return since entry, fraction
    held_since: dict = field(default_factory=dict)
    buy_limit: str = ""               # which of the record's two limits set a buy's size
    rules: Rules = field(default_factory=Rules)
    now_weights: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))   # the book as it stands
    sizes: dict = field(default_factory=dict)        # symbol -> Large / Mid / Small / Micro / Other, NSE lists today
    events: list = field(default_factory=list)       # (date, symbol, role, what) before the fill
    events_note: str = ""                            # how far ahead each source reaches
    swaps: object = None                             # engine.swap_evidence.SwapEvidence
    uninvested: float | None = None                  # model book: rupees not invested today (Portfolio's figure)


def _vs(v, what: str) -> str:
    """"ahead of Nifty Total Market by 1.2 points" / "behind it by 0.5 points" / "level with it"."""
    if v is None:
        return f"not measured against {what}"
    if round(float(v), 1) == 0:
        return f"level with {what}"
    a = abs(float(v))
    return f"{'ahead of' if v > 0 else 'behind'} {what} by {a:.1f} point{'' if a == 1 else 's'}"


def _price(rank_df: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(rank_df.drop_duplicates("Symbol").set_index("Symbol").get("CMP"), errors="coerce")


def buy_rows(p: Plan) -> list[dict]:
    px = _price(p.rank_df)
    out = []
    for s in p.buys:
        w = float(p.weights.get(s, 0.0))
        price = px.get(s)
        amount = None if p.value is None else p.value * w
        qty = None if amount is None or price is None or pd.isna(price) or price <= 0 else int(amount // price)
        out.append({"s": s, "w": w, "price": price, "amount": amount, "qty": qty})
    return out


def sell_rows(p: Plan) -> list[dict]:
    px = _price(p.rank_df)
    out = []
    for s in p.sells:
        qty = p.shares.get(s)
        price = px.get(s)
        out.append({"s": s, "qty": qty, "amount": None if qty is None or price is None or pd.isna(price) else qty * float(price)})
    return out


def basket(p: Plan) -> pd.DataFrame:
    """Kite basket rows: the model book's sells with its share counts, then the buys."""
    rows = []
    for r in sell_rows(p):
        if r["qty"]:
            rows.append({"Instrument": r["s"], "Exchange": "NSE", "Order Type": "MARKET", "Action": "SELL",
                         "Quantity": int(r["qty"]), "Price": 0, "ProductType": "CNC", "TriggerPrice": 0})
    for r in buy_rows(p):
        if r["qty"]:
            rows.append({"Instrument": r["s"], "Exchange": "NSE", "Order Type": "MARKET", "Action": "BUY",
                         "Quantity": int(r["qty"]), "Price": 0, "ProductType": "CNC", "TriggerPrice": 0})
    return pd.DataFrame(rows)


def sg_pts(v: float) -> str:
    return "0.0" if abs(v) < 0.05 else sg(v)


def _lakh(v: float) -> str:
    # In lakh and crore, as written before 22 Nov (owner, 22 Nov 2026: "₹34,05,000" was "completely opposite").
    # "Cr", never "crore" spelled out (glossary 5, owner 23 Nov 2026); half away from zero (glossary 12).
    from src.ui.formats import fixed
    return f"₹{fixed(v / 1e5, 1)} lakh" if v < 1e7 else f"₹{fixed(v / 1e7, 2)} Cr"


def _rk(v) -> str:
    return "Out" if v is None else f"#{v}"


def _ind(p: Plan, s: str) -> str:
    r = p.rank_df.drop_duplicates("Symbol").set_index("Symbol")
    return short(str(r["Industry"].get(s) or "")) if "Industry" in r and s in r.index else ""


def _name(p: Plan, s: str) -> str:
    return (f'<th scope="row"><a class="ac-sym" href="{stock_href(s)}" target="_self">{e(s)}</a>'
            f'<span class="dh-side ac-ind">{e(_ind(p, s))}</span></th>')


# ── Sections ────────────────────────────────────────────────────────────────


def header(p: Plan) -> list:
    a = p.assess.set_index("Symbol") if len(p.assess) else pd.DataFrame()
    n_watch = sum(1 for s in p.holds if s in a.index and a.loc[s, "status"] == WATCH)
    sell_amt = sum(r["amount"] or 0 for r in sell_rows(p))
    buy_amt = sum(r["amount"] or 0 for r in buy_rows(p))
    cells = [("Sell", str(len(p.sells)), "dh-down" if p.sells else "",
              "break a rule at today's close" if p.sells else "nothing breaks a rule", "dh-muted",
              f"{inr(sell_amt)} to sell" if sell_amt else ""),
             ("Buy", str(len(p.buys)), "dh-up" if p.buys else "", "best qualified, not held", "dh-muted",
              f"{inr(buy_amt)} to buy" if buy_amt else ""),
             ("Hold", str(len(p.holds)), "", f"{n_watch} close to a rule" if n_watch else "all clear of the rules",
              "dh-watch" if n_watch else "dh-muted", ""),
             ("Next rebalance", f"{p.check:%a} {dshort(p.check)}", "",
              f"{p.sessions} session{'s' if p.sessions != 1 else ''} away · fills {p.fill:%a} {dshort(p.fill)}", "dh-muted",
              p.holiday_note)]
    who = ("The model book: what the record would trade at the next rebalance."
           if p.source == "Model book" else "Your holdings, under the same rules.")
    when = f"{p.check:%a} {dshort(p.check)}"
    if p.sells or p.buys:
        # Sells in rust, buys in blue: the two verdict phrases (S219 2).
        answer = (kit.verdict(f"{len(p.sells)} sell{'s' if len(p.sells) != 1 else ''}", False if p.sells else None) + " and "
                  + kit.verdict(f"{len(p.buys)} buy{'s' if len(p.buys) != 1 else ''}", True if p.buys else None)
                  + e(f" at the {when} close, filled {p.fill:%a} {dshort(p.fill)}"   # the signal day, then the fill (S193 B)
                      + (f": {_lakh(sell_amt)} out, {_lakh(buy_amt)} in." if sell_amt or buy_amt else ".")))
    else:
        answer = e(f"Nothing to trade on {when}: ") + kit.verdict("every holding is clear of the rules", True) + "."
    return [f'<div class="pf-head"><p class="pf-kick">Actions</p><h1 class="pf-title">{answer}</h1>'
            f'<p class="pf-sub">If today\'s prices hold. {e(who)}</p>',
            _kpis(cells, "pf-four"), "</div>"]


def section_change(p: Plan) -> list:
    """Row 25: what could still change before the close that counts."""
    a = p.assess.set_index("Symbol") if len(p.assess) else pd.DataFrame()
    close = [(s, a.loc[s, "why"]) for s in p.holds if s in a.index and a.loc[s, "status"] == WATCH]
    items = "".join(f'<li><b>{e(s)}</b> {e(str(w))}</li>' for s, w in close) or "<li>No holding is within reach of a line.</li>"
    nxt = " · ".join(e(s) for s in p.next_in_line[:4]) or "–"
    return _sec([_head("ac-change", "What could still change", f"before the {dshort(p.check)} close"),
                 f'<div class="dh-pair"><div><div class="dh-cap ac-cap"><b>Holdings close to a line</b><span>could still change to a sale</span></div>'
                 f'<ul class="ac-list">{items}</ul></div>'
                 f'<div><div class="dh-cap ac-cap"><b>Next in line</b><span>would come in if a buy drops out or another holding breaks a rule</span></div>'
                 f'<p class="ac-next">{nxt}</p></div></div>',
                 f'<div class="dh-cap ac-cap"><b>Results and corporate actions before the fill</b><span>to {dshort(p.fill)}</span></div>',
                 _events_html(p), f'<p class="dh-note">{e(p.events_note)}</p>'])


def _events_html(p: Plan) -> str:
    if p.events:
        rows = "".join(f'<li><b>{e(sym)}</b> ({e(role)}) {e(what)}, {dshort(d)}</li>' for d, sym, role, what in p.events)
        return f'<ul class="ac-list">{rows}</ul>'
    return f'<p class="ac-none">{e(mw.no_events("any holding, sell or buy", p.fill))}</p>'


def section_after(p: Plan) -> list:
    """Row 27: the book's sector and size after the trades, against now."""
    if not len(p.weights):
        return []
    ind = lambda s: _ind(p, s) or "Other"   # noqa: E731
    now = p.now_weights.groupby(p.now_weights.index.map(ind)).sum() * 100
    aft = p.weights.groupby(p.weights.index.map(ind)).sum() * 100
    names = sorted(set(now.index) | set(aft.index), key=lambda k: (-max(now.get(k, 0), aft.get(k, 0)), k))
    rows = "".join(f'<tr><th scope="row">{e(k)}</th><td class="dh-num">{now.get(k, 0):.1f}%</td><td class="dh-num dh-b">{aft.get(k, 0):.1f}%</td>'
                   f'<td class="dh-num {tone(aft.get(k, 0) - now.get(k, 0))}">{sg_pts(aft.get(k, 0) - now.get(k, 0))}</td></tr>' for k in names)
    sz = lambda w: w.groupby(w.index.map(lambda s: p.sizes.get(s, "Other"))).sum() * 100   # noqa: E731
    sn, sa = sz(p.now_weights), sz(p.weights)
    srows = "".join(f'<tr><th scope="row">{e(_fmt.size(k))}</th><td class="dh-num">{sn.get(k, 0):.1f}%</td><td class="dh-num dh-b">{sa.get(k, 0):.1f}%</td>'
                    f'<td class="dh-num {tone(sa.get(k, 0) - sn.get(k, 0))}">{sg_pts(sa.get(k, 0) - sn.get(k, 0))}</td></tr>'
                    for k in bx.SIZES if sn.get(k, 0) or sa.get(k, 0))
    # Cash in rupees, the figure Portfolio shows: uninvested now; after, plus the sells and less the buys (whole shares).
    if p.value and p.uninvested is not None:
        after_cash = p.uninvested + sum(r["amount"] or 0 for r in sell_rows(p)) - sum(
            (r["qty"] or 0) * float(r["price"] or 0) for r in buy_rows(p))
        cash_now, cash_after = p.uninvested / p.value * 100, max(0.0, after_cash) / p.value * 100
    else:
        cash_now, cash_after = max(0.0, 100 - float(p.now_weights.sum()) * 100), max(0.0, 100 - float(p.weights.sum()) * 100)
    head = ('<thead><tr><th scope="col">{0}</th><th scope="col" class="dh-num">Now</th><th scope="col" class="dh-num">After</th>'
            '<th scope="col" class="dh-num">Change, pts</th></tr></thead>')
    return _sec([_head("ac-after", "The book after the trades", "sector and size, now and after the trades"),
                 f'<div class="dh-pair"><div class="dh-scroll"><table class="dh-tab dh-tab-s ac-tab">{head.format("Sector")}<tbody>{rows}</tbody></table></div>'
                 f'<div class="dh-scroll"><table class="dh-tab dh-tab-s ac-tab">{head.format("Size")}<tbody>{srows}'
                 f'<tr><th scope="row">Cash</th><td class="dh-num">{cash_now:.1f}%</td><td class="dh-num dh-b">{cash_after:.1f}%</td>'
                 f'<td class="dh-num">{sg_pts(cash_after - cash_now)}</td></tr></tbody></table></div></div>',
                 '<p class="dh-note">Now: each stock at its weight today, after it has moved since the last fill. After: the weights the '
                 'record strikes at the rebalance. Size by NSE’s index lists today: Large Cap is the Nifty 100, Mid Cap the Nifty Midcap 150, '
                 'Small Cap the Nifty Smallcap 250, Micro Cap the Nifty Microcap 250; Nano Cap the Nifty 1000’s other 250 and Ultra Nano Cap '
                 f'anything outside the Nifty 1000 (our own groups, not NSE indices). {_fmt.PTS_NOTE}</p>'])


def section_sell(p: Plan) -> list:
    if not p.sells:
        return _sec([_head("ac-sell", "Sell", "none at today's close"), '<p class="dh-note">Nothing breaks a rule.</p>'])
    a = p.assess.set_index("Symbol")
    rows = ""
    for r in sell_rows(p):
        s = r["s"]
        ret = p.since.get(s)
        rows += (f'<tr>{_name(p, s)}<td>{e(str(a.loc[s, "why"] if s in a.index else ""))}</td>'
                 f'<td class="dh-num ac-wide">{e(p.held_since.get(s, "–"))}</td>'
                 f'<td class="dh-num {tone(None if ret is None else ret)}">{pct(None if ret is None else ret * 100)}</td>'
                 f'<td class="dh-num">{"–" if r["qty"] is None else f"{r['qty']:,}"}</td>'
                 f'<td class="dh-num">{"–" if r["amount"] is None else inr(r["amount"])}</td></tr>')
    note = ("Sell in full. The basket carries these sells with the model book's share counts."
            if p.source == "Model book" else "Sell in full; your share counts are not known, so sells are not in the basket.")
    return _sec([_head("ac-sell", "Sell", f"{len(p.sells)} at today's close"),
                 '<div class="dh-scroll"><table class="dh-tab dh-tab-s ac-tab"><thead><tr><th scope="col">Holding</th>'
                 '<th scope="col">The rule it broke</th><th scope="col" class="dh-num ac-wide">Held since</th>'
                 '<th scope="col" class="dh-num">Since entry</th><th scope="col" class="dh-num">Shares</th>'
                 f'<th scope="col" class="dh-num">Amount</th></tr></thead><tbody>{rows}</tbody></table></div>',
                 f'<p class="dh-note">{e(note)} <span class="ac-phone">On a wider screen each row also shows when it was bought.</span></p>'])


def section_buy(p: Plan) -> list:
    if not p.buys:
        return _sec([_head("ac-buy", "Buy", "none"), '<p class="dh-note">No new stock qualifies for a free place.</p>'])
    r = p.rank_df.drop_duplicates("Symbol").set_index("Symbol")
    rows = ""
    for b in buy_rows(p):
        s = b["s"]
        hi = pd.to_numeric(r["% High"].get(s), errors="coerce") if "% High" in r else np.nan
        m3 = pd.to_numeric(r["3M Return"].get(s), errors="coerce") * 100 if "3M Return" in r else np.nan
        m6 = pd.to_numeric(r["6M Return"].get(s), errors="coerce") * 100 if "6M Return" in r else np.nan
        rows += (f'<tr>{_name(p, s)}<td class="dh-num">#{int(p.qrank.get(s, 0))}</td>'
                 f'<td class="dh-num">{"–" if b["price"] is None or pd.isna(b["price"]) else _fmt_price(b['price'])}</td>'
                 f'<td class="dh-num ac-wide {tone(m3)}">{pct(None if pd.isna(m3) else m3)}</td>'
                 f'<td class="dh-num ac-wide {tone(m6)}">{pct(None if pd.isna(m6) else m6)}</td>'
                 f'<td class="dh-num ac-wide">{"–" if pd.isna(hi) else ("at the high" if hi > -0.05 else pct(hi))}</td>'
                 f'<td class="dh-num ac-wide">{b["w"] * 100:.1f}%</td>'
                 f'<td class="dh-num dh-b">{"–" if b["amount"] is None else inr(b["amount"])}</td>'
                 f'<td class="dh-num">{"–" if b["qty"] is None else f"{b['qty']:,}"}</td></tr>')
    nxt = "".join(f'<a class="dh-pill" href="{stock_href(s)}" target="_self">#{int(p.qrank.get(s, 0))} {e(s)}</a>'
                  for s in p.next_in_line[:4])
    base = (f"Amounts are the record's target weight of the model book's value today, {inr(p.value)}."
            if p.source == "Model book" else f"Amounts are each buy's target weight of {inr(p.value)}, the capital in the Kite basket box.")
    ev = p.swaps
    evid = ("" if ev is None else
            # The words carry the sign: "beat … by −0.5 points" had no branch for a loss (S203 ac.buy.4).
            f'<div class="ac-ev"><b>What swaps have added so far.</b> In their first month, the record’s {ev.buys} buys were '
            f'{_vs(ev.buy_1m, "Nifty Total Market")} on average. The {ev.sold} stocks it sold were {_vs(ev.sold_1m, "it")} '
            'in the month after the sale'
            + ("" if ev.buy_3m is None or ev.sold_3m is None else
               f'. Over 3 months: {sg(ev.buy_3m)} against {sg(ev.sold_3m)} points')
            + f'. {ev.rebought} of the {ev.sold} sold were bought back within 2 months. '
            + ("" if not getattr(ev, "unpriced", ()) else
               f'{e(", ".join(ev.unpriced))} {"has" if len(ev.unpriced) == 1 else "have"} no price here and '
               f'{"is" if len(ev.unpriced) == 1 else "are"} left out. ')
            + f'<span class="dh-muted">{ev.first:%b %Y} to {ev.last:%b %Y}: a short record, measured on the record itself, before costs, '
            'with overlapping windows; evidence, not proof.</span></div>')
    return _sec([_head("ac-buy", "Buy", "best qualified, not held"), evid,
                 '<div class="dh-scroll"><table class="dh-tab dh-tab-s ac-tab"><thead><tr><th scope="col">Stock</th>'
                 '<th scope="col" class="dh-num">Qualified</th><th scope="col" class="dh-num">Price</th>'
                 '<th scope="col" class="dh-num ac-wide">3M</th><th scope="col" class="dh-num ac-wide">6M</th>'
                 '<th scope="col" class="dh-num ac-wide">From 52W high</th><th scope="col" class="dh-num ac-wide">Weight</th>'
                 '<th scope="col" class="dh-num">Amount</th><th scope="col" class="dh-num">Shares</th>'
                 f'</tr></thead><tbody>{rows}</tbody></table></div>',
                 f'<p class="dh-note">{e(base)} {e(p.buy_limit)} '
                 '<span class="ac-phone">On a wider screen each row also shows the weight, the 3- and 6-month returns and the distance from the 52-week high.</span></p>',
                 f'<div class="ac-nextrow"><span class="dh-muted">Next in line</span>{nxt}</div>' if nxt else ""])


def section_hold(p: Plan) -> list:
    a = p.assess.set_index("Symbol") if len(p.assess) else pd.DataFrame()
    order = [s for s in p.assess["Symbol"] if s in set(p.holds)] if len(p.assess) else list(p.holds)
    order += [s for s in p.assess["Symbol"] if len(p.assess) and a.loc[s, "status"] == UNKNOWN and s not in order]
    rows = ""
    for s in order:
        r = a.loc[s]
        tr = p.trails.get(s, [None, None, None])
        status = r["status"]
        word = {SELL: "dh-down", WATCH: "dh-watch", CLEAR: "dh-up", UNKNOWN: "dh-muted"}.get(status, "")
        if status == UNKNOWN:
            rows += (f'<tr>{_name(p, s)}<td class="{word}">{STATUS_LABEL[UNKNOWN]}</td>'
                     '<td colspan="8" class="dh-muted">No rule can be checked.</td></tr>')
            continue
        q, room = r["Qualified rank"], r["Rank room"]
        buf = "off the list" if pd.isna(q) else (f"{int(room)} to go" if room >= 0 else f"past {p.rules.buffer_n}")
        ema = r["EMA cushion"]
        hi = r["High cushion"]
        ret = p.since.get(s)
        rows += (f'<tr>{_name(p, s)}<td class="{word}">{e(STATUS_LABEL[status])}</td>'
                 f'<td class="dh-num ac-trail">{_rk(tr[0])}</td><td class="dh-num ac-trail">{_rk(tr[1])}</td>'
                 f'<td class="dh-num"><b>{_rk(tr[2])}</b></td>'
                 f'<td class="dh-num">{e(buf)}</td>'
                 f'<td class="dh-num {"dh-watch" if pd.notna(ema) and ema < 0.03 else ""}">{"–" if pd.isna(ema) else f"{ema * 100:.1f}%"}</td>'
                 f'<td class="dh-num {"dh-watch" if pd.notna(hi) and hi < 0.03 else ""}">{"–" if pd.isna(hi) else f"{hi * 100:.1f}%"}</td>'
                 f'<td class="ac-wide">{e(r["why"] or nearest_rule(r, p.rules))}</td>'
                 f'<td class="dh-num {tone(None if ret is None else ret)}">{pct(None if ret is None else ret * 100)}</td></tr>')
    return _sec([_head("ac-hold", "Hold", "closest to a sale first"),
                 '<div class="dh-scroll"><table class="dh-tab dh-tab-s ac-tab"><thead><tr><th scope="col">Holding</th>'
                 '<th scope="col">Status</th><th scope="col" class="dh-num">Rank 3M</th><th scope="col" class="dh-num">1M</th><th scope="col" class="dh-num">Now</th>'
                 f'<th scope="col" class="dh-num">Rank buffer (top {p.rules.buffer_n})</th>'
                 '<th scope="col" class="dh-num">To 50D EMA</th>'
                 f'<th scope="col" class="dh-num">To −{(1 - p.rules.high_pct):.0%} from 52W high</th>'
                 '<th scope="col" class="ac-wide">Closest to</th><th scope="col" class="dh-num">Since entry</th>'
                 f'</tr></thead><tbody>{rows}</tbody></table></div>',
                 '<p class="dh-note">Ordered by the least room on any sell rule; a full rank buffer counts as a '
                 f'{RANK_SCALE:.0%} fall. "To 50D EMA" and "To −{(1 - p.rules.high_pct):.0%} from 52W high" are how far the price can fall from today before it crosses that line. '
                 'Rank 3M · 1M · now: the place among the stocks that pass both filters, 3 months ago, a month ago and now; "Out" means it does not pass them.</p>'])


def footer(p: Plan) -> list:
    from src.ui.components import gap_count
    rd = p.rank_df
    short_n = int((rd.get("Short History", pd.Series(dtype=str)) == "Yes").sum())
    return [f'<p class="dh-foot">{_fmt.data_to(p.as_of)}. {len(rd)} stocks ranked; {gap_count(rd)} with a price gap, '
            f'{short_n} with a short history.</p>']


def page_parts(p: Plan) -> list:
    return header(p) + section_change(p) + section_sell(p) + section_buy(p) + section_after(p) + section_hold(p) + footer(p)


AC_CSS = """
.ac-sym{font-family:var(--font-mono);font-weight:600;color:var(--c-ink);text-decoration:none}
.ac-ind{font-weight:400;color:var(--c-muted)}
.ac-tab th[scope=row]{white-space:nowrap}.ac-tab thead th{vertical-align:bottom}
.ac-trail{color:var(--c-muted)}.ac-trail b{color:var(--c-ink)}
.ac-list{margin:0;padding-left:18px;font-size:var(--fs-13)}.ac-list li{margin:2px 0}
.ac-next{margin:0;font-family:var(--font-mono);font-size:var(--fs-13)}
.ac-nextrow{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:var(--fs-13)}
.ac-phone{display:none}
.ac-ev{border-left:3px solid var(--c-up);padding:6px 0 6px 12px;font-size:var(--fs-13);max-width:80ch}
.ac-none{margin:0;font-size:var(--fs-13);color:var(--c-text_2)}
.dh-cap.ac-cap{justify-content:flex-start;column-gap:var(--sp-2)}
@media (max-width:640px){.ac-wide{display:none}.ac-phone{display:inline}}
"""


# ── Gather and render ───────────────────────────────────────────────────────


def gather(source: str, rank_df: pd.DataFrame, adj_close: pd.DataFrame, benchmark_close, system: str,
           my_symbols: list | None = None, my_since: dict | None = None, capital: float | None = None) -> Plan | None:
    from src.core.market_time import ist_now
    from src.engine import dashboard_insights as di
    from src.engine.actions import plan_rebalance
    from src.loaders.nse_calendar import holiday_caveat
    from src.ui.views.actions_view import _sessions_between, next_rebalance

    cfg = TRACK_RECORD_CONFIG
    rules = Rules(buffer_n=int(cfg["buffer_n"]), high_pct=float(cfg["high_pct"]))
    as_of = pd.Timestamp(adj_close.index[-1]) if adj_close is not None and len(adj_close) else pd.Timestamp(ist_now().date())
    check, fill = next_rebalance(as_of)
    shares, since, held, value, limit = {}, {}, {}, capital, ""
    if source == "Model book":
        from src.core.config import MODEL_BOOK_CAPITAL
        from src.engine.systems import inception, ledger_path
        from src.engine.track_record import load_ledger
        from src.ui.book_series import book_series
        from src.ui.canonical_book import current_book
        from src.ui.model_plan import model_plan
        book, record = current_book(adj_close, benchmark_close, system)
        if book is None or book.empty:
            return None
        symbols = book["Symbol"].tolist()
        plan = model_plan(book, record, rank_df, adj_close, benchmark_close, system, check)
        ledger = load_ledger(ledger_path(system), inception(system))
        series = book_series(book, record, ledger, rank_df, adj_close, benchmark_close, MODEL_BOOK_CAPITAL)
        uninv = None
        if series is not None:
            value = float(series.value)
            uninv = float(series.uninvested)
            shares = dict(zip(series.table["Symbol"].astype(str), pd.to_numeric(series.table["Shares"], errors="coerce").astype(int)))
        since = dict(zip(book["Symbol"], pd.to_numeric(book["Return %"], errors="coerce")))
        held = {s: dshort(d) + f" ’{pd.Timestamp(d):%y}" for s, d in zip(book["Symbol"], pd.to_datetime(book["Entry Date"], errors="coerce"))
                if pd.notna(d)}
        # The book now: each holding's value over the book's value today, Portfolio's Weight column (S154; it read
        # Healthcare 29.5% from the drifted struck weights against Portfolio's 29.4%, found 21 Nov 2026).
        if series is not None and "Weight %" in series.table:
            now_w = pd.to_numeric(series.table.set_index("Symbol")["Weight %"], errors="coerce").fillna(0) / 100
        else:
            now_w = pd.to_numeric(book.set_index("Symbol")["Weight %"], errors="coerce").fillna(0) / 100
        try:
            from src.engine import swap_evidence as sw
            from src.loaders import benchmark_indices as bi
            from src.ui.views.portfolio_view import build_portfolio_history
            hist = build_portfolio_history(record, MODEL_BOOK_CAPITAL, ledger, (record or {}).get("live_meta") or {})
            from src.loaders import former_members
            # A name that has since left the list is valued by the record from the former members' file:
            # measured from it too, not dropped (JBCHEPHARM, S193 B).
            swaps = sw.from_record(hist, adj_close, bi.series(bi.TOTAL_MARKET), former_members.load())
        except (KeyError, ValueError, OSError):
            swaps = None
        if plan.buys:
            w = float(plan.weights.get(plan.buys[0], 0.0))
            cash = w * len(plan.buys)
            # The comparison is each buy against the buy size, not the total (S193 B: "13.3% ... less than the 5%").
            # Three sentences, the rule's start read from the record's config, not typed (S203 ac.buy.3, rule 9).
            rule_from = pd.Timestamp(cfg.get("hold_cap_from") or "2026-11-30")
            limit = (f"Each buy gets {w * 100:.1f}%, less than the {cfg.get('buy_size', 0.05) * 100:.0f}% buy size. The record "
                     f"does not trim a kept stock to make room, so the buys share the {cash * 100:.1f}% the sells free up. "
                     f"This is the six-monthly rule, in force from the {rule_from:%-d %b %Y} rebalance."
                     if w < float(cfg.get("buy_size") or 0.05) - 1e-9 else "")
    else:
        symbols = list(my_symbols or [])
        if not symbols:
            return None
        plan = plan_rebalance(rank_df, symbols, top_n=len(symbols), buffer_n=rules.buffer_n,
                              stock_cap=float(cfg["stock_cap"]), sector_cap=float(cfg["sector_cap"]))
        since = dict(my_since or {})
        now_w = pd.Series(1.0 / len(symbols), index=symbols)     # your own weights are not known
        uninv = None
        swaps = None
    q = qualified_ranks(rank_df)
    every = sorted(set(symbols) | set(plan.buys))
    sizes, events, events_note = _sizes(every, as_of), *_events(every, set(plan.sells), set(plan.buys), as_of, fill)
    px = adj_close if adj_close is not None else pd.DataFrame()
    _, trails = di.rank_trails(px, [s for s in symbols if s in px.columns], now=q) if len(px) else ({}, {})
    caveat = " · NSE holidays not yet published" if holiday_caveat(check, fill) else ""
    return Plan(source=source, as_of=as_of, check=check, fill=fill, sessions=_sessions_between(as_of, check),
                holiday_note=caveat.strip(" ·"), sells=list(plan.sells), buys=list(plan.buys), holds=list(plan.holds),
                next_in_line=list(plan.next_in_line), weights=plan.weights, assess=assess(rank_df, symbols, rules),
                trails=trails, qrank=q, rank_df=rank_df, value=value, shares=shares, since=since, held_since=held,
                buy_limit=limit, rules=rules, now_weights=now_w, sizes=sizes, events=events, events_note=events_note, swaps=swaps, uninvested=uninv)


def _sizes(symbols: list, on: pd.Timestamp) -> dict:
    import json
    from pathlib import Path
    from src.engine import book_exposure as bx
    path = Path(__file__).resolve().parents[3] / "data" / "membership_history.json"
    try:
        return bx.size_of(symbols, on, json.loads(path.read_text()))
    except (OSError, ValueError):
        return {}


def _events(symbols: list, sells: set, buys: set, as_of: pd.Timestamp, fill: pd.Timestamp) -> tuple[list, str]:
    """Board meetings (NSE's calendar) and ex-dates (NSE's corporate actions) from tomorrow to the fill."""
    import json
    from pathlib import Path
    from src.engine import results_calendar as rc
    root = Path(__file__).resolve().parents[3]
    role = lambda s: "to sell" if s in sells else "to buy" if s in buys else "held"   # noqa: E731
    lo, hi = pd.Timestamp(as_of).normalize() + pd.Timedelta(days=1), pd.Timestamp(fill).normalize()
    out, notes = [], []
    cal = rc.load()
    if cal is not None and len(cal):
        hit = cal[cal["symbol"].isin(symbols) & (cal["date"] >= lo) & (cal["date"] <= hi)]
        out += [(d, sym, role(sym), rc.short_purpose(str(pur))) for sym, d, pur in zip(hit["symbol"], hit["date"], hit["purpose"])]
        notes.append(f"Board meetings: NSE's calendar, announced to {cal['date'].max():%-d %b}")
    try:
        ca = pd.DataFrame(json.loads((root / "data" / "reference" / "nse" / "corporate_actions_recent.json").read_text()))
        ca["ex"] = pd.to_datetime(ca["exDate"], format="%d-%b-%Y", errors="coerce")
        hit = ca[ca["symbol"].isin(symbols) & (ca["ex"] >= lo) & (ca["ex"] <= hi)]
        out += [(d, sym, role(sym), str(sub)) for sym, d, sub in zip(hit["symbol"], hit["ex"], hit["subject"])]
        last = ca["ex"].max()
        notes.append(f"ex-dates: NSE's corporate actions, collected to {last:%-d %b}"
                     + ("; dates after that are not yet in the file" if pd.notna(last) and last < hi else ""))
    except (OSError, ValueError, KeyError):
        notes.append("ex-dates: not available")
    return sorted(out), "; ".join(notes) + ". Dates are as companies announced them and can move."


def render(rank_df: pd.DataFrame, adj_close: pd.DataFrame, benchmark_close, system: str = "750",
           model_book_note: str | None = None) -> None:
    from src.core.market_time import ist_now
    from src.ui import holdings_store
    from src.ui import page_kit as kit
    from src.ui.views import actions_view as av
    from src.ui.views.qualified_view import render_qualified_view
    from src.ui.widget_state import remember

    holdings_store.sync()
    st.html(f"<style>{HOME_CSS}{PF_CSS}{AC_CSS}</style>")
    sources = av.SOURCES if model_book_note is None else ["My holdings"]
    top = st.container()        # the title and counts, filled once the plan is known, drawn above the switch
    bar = st.container(horizontal=True, vertical_alignment="center", key="ac_bar")
    with bar:
        source = st.segmented_control("Holdings", sources, default=sources[0], key="xw_source",
                                      label_visibility="collapsed") or sources[0]
    if model_book_note is not None:
        kit.note(mw.NO_MODEL_BOOK, model_book_note, kind="info")   # when the record starts: explains, not a fault
    my_syms, my_since, capital = None, None, None
    if source == "My holdings":
        av._edit_holdings()
        my_syms, my_since, _ = av._my_holdings(rank_df)
        capital = float(av.kite_capital())
    with st.spinner("Loading the plan…"):
        p = gather(source, rank_df, adj_close, benchmark_close, system, my_syms, my_since, capital)
    if p is None:
        if source == "My holdings":
            kit.empty("Add your holdings above,", "or upload the holdings CSV from Kite, to see what to do with them.")
        else:
            kit.empty(mw.NO_MODEL_BOOK, mw.NO_MODEL_BOOK_WHY)   # the sentence Dashboard and Portfolio use (S193 E, R5)
        return
    if source != "My holdings":
        from src.ui.canonical_book import current_book, unpriced_note
        if (note := unpriced_note(current_book(adj_close, benchmark_close, system)[1])) is not None:
            kit.note(*note, kind="warning")
    with bar, st.popover("Kite basket", icon=":material/download:", type="primary"):
        if source == "My holdings":
            cap = float(st.number_input("Capital (₹)", min_value=av.KITE_MIN_CAPITAL, max_value=av.KITE_MAX_CAPITAL,
                                        step=100_000, value=av.kite_capital(), key=av.KITE_CAPITAL_KEY,
                                        help="Your account's size; each buy is its target weight of it."))
            remember(av.KITE_CAPITAL_KEY, int(cap))
            if cap != p.value:
                p.value = cap
            kit.caption("Buy orders only, each at its target weight of the capital above; your share counts are not known.")
        else:
            kit.caption(f"The model book's sell orders, with its share counts, and its buy orders, each at the record's "
                        f"target weight of the book's value today, {inr(p.value)}.")
        orders = basket(p)
        st.download_button("Download basket CSV", orders.to_csv(index=False).encode(), f"kite_actions_{ist_now():%Y%m%d}.csv",
                           "text/csv", type="primary", key="dl_actions_basket", icon=":material/download:", disabled=orders.empty)
    with top:
        emit(header(p))
    emit(section_change(p) + section_sell(p) + section_buy(p) + section_after(p) + section_hold(p))
    with st.expander("Buy candidates · the qualified list", expanded=False):
        render_qualified_view(rank_df, adj_close)
    emit(footer(p))


__all__ = ["render", "gather", "page_parts", "basket", "Plan", "html_of"]
