"""How numbers read on the site: one place for signs, rupees and percentages.

House style (pre-launch audit F5/F6, owner 7 Nov 2026):

* A minus is U+2212, never a hyphen, and a value is rounded before it is
  signed, so nothing reads "-0.0%".
* Rupees use Indian grouping (₹28,27,942; ₹1,26,433 Cr), and the sign comes
  before the rupee symbol (−₹954, not ₹-954). Index levels are not rupees and
  keep NSE's own grouping.
* Percentages carry one decimal and, where the sign is the point, a + or −.

No streamlit import, so the theme, the page kit and framed tables can all use it.
"""
from __future__ import annotations

import math

MINUS = "−"
DASH = "—"


def _finite(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def signed(v: float, digits: int = 1, plus: bool = True) -> str:
    """Rounded first, then signed: "+2.3", "−1.9", "0.0"."""
    r = round(v, digits)
    sign = ("+" if plus else "") if r > 0 else MINUS if r < 0 else ""
    return f"{sign}{abs(r):.{digits}f}"


def indian_group(whole: int) -> str:
    """Digits in Indian grouping: 2827942 -> "28,27,942"."""
    s = str(abs(int(whole)))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    pairs = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    if head:
        pairs.insert(0, head)
    return ",".join(pairs) + "," + tail


def inr(x, decimals: int = 0, plus: bool = False) -> str:
    """₹ amount in Indian grouping: "₹28,27,942", "−₹954", "₹2,340.00"."""
    v = _finite(x)
    if v is None:
        return DASH
    r = round(v, decimals)
    whole = int(abs(r))
    frac = f"{abs(r) - whole:.{decimals}f}"[1:] if decimals else ""
    sign = MINUS if r < 0 else ("+" if plus and r > 0 else "")
    return f"{sign}₹{indian_group(whole)}{frac}"


def pct(x, signed_: bool = True, digits: int = 1, fraction: bool = True) -> str:
    """A return as a percentage: 0.023 -> "+2.3%" (fraction=False takes 2.3)."""
    v = _finite(x)
    if v is None:
        return DASH
    return f"{signed(v * 100 if fraction else v, digits, plus=signed_)}%"
