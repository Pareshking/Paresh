"""Short industry names: one map for every page (S154, Screener redesign 21 Nov 2026).

There were two, and they disagreed: the Dashboard, Portfolio and Actions wrote
"Durables", Sectors "Cons. Durables", and the Screener printed NSE's full
names cut at 20 characters ("Fast Moving Consumer…"). A name means one thing
everywhere (PAGE_DESIGN §8); NSE's full name stays in a tooltip where a table
has room for one.
"""
from __future__ import annotations

INDUSTRY_SHORT: dict[str, str] = {
    "Automobile and Auto Components": "Auto",
    "Media Entertainment & Publication": "Media",
    "Fast Moving Consumer Goods": "FMCG",
    "Metals & Mining": "Metals",
    "Consumer Durables": "Durables",
    "Financial Services": "Financials",
    "Consumer Services": "Cons. Services",
    "Capital Goods": "Capital Goods",
    "Oil Gas & Consumable Fuels": "Oil & Gas",
    "Information Technology": "IT",
    "Telecommunication": "Telecom",
}


def short_industry(name) -> str:
    """NSE's industry name in the site's short form; other names unchanged."""
    text = "" if name is None else str(name).strip()
    if text in ("nan", "<NA>", "None"):
        return ""
    return INDUSTRY_SHORT.get(text, text)
