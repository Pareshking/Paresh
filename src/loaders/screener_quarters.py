"""Quarterly sales and net profit from a Screener.in company page (S171 part 2, research only).

A company page (https://www.screener.in/company/TCS/consolidated/) carries a "Quarterly Results"
card, ``<section id="quarters">``: one column per quarter (``data-date-key="2026-09-30"``, header
"Sep 2026"), 13 quarters for a visitor not logged in, figures in Rs crore with Indian commas.
The first row is "Sales +" for most companies and "Revenue +" for banks and lenders; "Net
Profit +" is the profit after tax Screener shows (in a consolidated table, before minority
interest is taken out). The sub-heading under the title names the basis, "Consolidated" or
"Standalone". A /consolidated/ page with no consolidated figure for a quarter shows the
standalone one and marks its header "Sep 2024 (S)"; a page with only such columns has no
"Consolidated" in its sub-heading. Each quarter therefore carries its own basis.

"Other Income +" and the tax row (Tax, in %) are read too: the profit measure without other income (S171) takes
other income out after tax at the quarter's own rate.

``parse_quarters`` reads only that section and returns None when the page has none (a company
with no consolidated accounts, a 404 page). Nothing here fetches; the page text is treated as
untrusted input and only numbers and dates come out of it.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

SALES_LABELS = ("sales", "revenue")
PROFIT_LABELS = ("net profit",)
OTHER_INCOME_LABELS = ("other income",)
TAX_PREFIX = "tax"            # the row Tax, in %

_SECTION = re.compile(r'<section[^>]*\bid="quarters"[^>]*>(.*?)</section>', re.S | re.I)
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
_DATE_KEY = re.compile(r'data-date-key="(\d{4}-\d{2}-\d{2})"')
_TAG = re.compile(r"<[^>]+>")
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


@dataclass
class Quarters:
    basis: str                                   # "consolidated" | "standalone" | "" (not stated)
    sales_label: str                             # "Sales" or "Revenue", as the page names the row
    rows: dict[str, dict] = field(default_factory=dict)   # "2026-09-30" -> {sales, net_profit, basis}

    def mixed(self) -> bool:
        """True when a consolidated page fills some quarter with a standalone figure."""
        return len({r["basis"] for r in self.rows.values()}) > 1


def _text(fragment: str) -> str:
    return " ".join(html.unescape(_TAG.sub(" ", fragment)).split())


def _number(text: str) -> float | None:
    """ "1,23,456.7" -> 123456.7; "-96" -> -96.0; "" or "--" -> None."""
    cleaned = text.replace(",", "").replace("−", "-").strip()
    return float(cleaned) if _NUMBER.match(cleaned) else None


def _label(cell: str) -> str:
    return cell.rstrip("+").strip().lower()


def _basis(head: str) -> str:
    """The table's basis from the card's sub-heading: a link to the other basis names it too."""
    if "view standalone" in head:
        return "consolidated"
    if "view consolidated" in head:
        return "standalone"
    if "consolidated" in head:
        return "consolidated"
    return "standalone" if "standalone" in head else ""


def parse_quarters(page: str) -> Quarters | None:
    """quarter end -> {"sales", "net_profit", "other_income", "tax_pct", "basis"} (Rs crore; tax in %), from the page's Quarters table; None without one."""
    found = _SECTION.search(page or "")
    if not found:
        return None
    section = found.group(1)
    basis = _basis(_text(section.split("<table", 1)[0]).lower())
    header = next((r for r in _ROW.findall(section) if _DATE_KEY.search(r)), "")
    dates = _DATE_KEY.findall(header)
    if not dates:
        return None
    marked = {d: "(S)" in _text(c) for d, c in zip(_DATE_KEY.findall(header), _CELL.findall(header)[1:])}
    sales = profit = other = tax = None
    sales_label = ""
    for row in _ROW.findall(section):
        cells = [_text(c) for c in _CELL.findall(row)]
        if len(cells) != len(dates) + 1:
            continue
        name = _label(cells[0])
        if sales is None and name in SALES_LABELS:
            sales, sales_label = cells[1:], cells[0].rstrip("+").strip()
        elif profit is None and name in PROFIT_LABELS:
            profit = cells[1:]
        elif other is None and name in OTHER_INCOME_LABELS:
            other = cells[1:]
        elif tax is None and name.startswith(TAX_PREFIX):
            tax = cells[1:]
    if sales is None and profit is None:
        return None
    out = Quarters(basis=basis, sales_label=sales_label)
    for i, d in enumerate(dates):
        out.rows[d] = {"sales": _number(sales[i]) if sales else None,
                       "net_profit": _number(profit[i]) if profit else None,
                       "other_income": _number(other[i]) if other else None,
                       "tax_pct": _number(tax[i].rstrip("%")) if tax else None,
                       "basis": "standalone" if marked.get(d) else (basis or "standalone")}
    return out
