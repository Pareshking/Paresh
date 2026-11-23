"""How numbers read on the site: one place for signs, rupees and percentages.

House style (pre-launch audit F5/F6, owner 7 Nov 2026):

* A minus is U+2212, never a hyphen, and a value is rounded before it is
  signed, so nothing reads "-0.0%".
* Rupees use Indian grouping (₹28,27,942; ₹1,26,433 Cr), and the sign comes
  before the rupee symbol (−₹954, not ₹-954). Index levels are not rupees and
  keep NSE's own grouping.
* Percentages carry one decimal and, where the sign is the point, a + or −.
* Every displayed figure rounds half away from zero on its decimal value
  (glossary 12, owner 23 Nov 2026): ₹892.50 → ₹893, −2.45% → −2.5%. Python's
  round() rounds half to even and 2.45 is not exact in binary, so rounding goes
  through Decimal(repr(x)); the charts' JavaScript does the same (``rnd`` in
  static/dash_charts.js and lw_chart.py), and a test holds the two together.
* Prices, moving averages and any ₹ level are whole rupees, below ₹100 too (owner,
  22 Nov 2026: "price etc, Moving averages etc should be in round numbers, return
  only with Max one decimal values like 11.1% not 11.11%", and the same day: whole
  rupees "including below ₹100"; S173). Display only: stored data, exports, the
  Kite basket and every calculation keep their exact values.

No streamlit import, so the theme, the page kit and framed tables can all use it.
"""
from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

MINUS = "−"
DASH = "–"


def _finite(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def half_up(v: float, digits: int = 0) -> Decimal:
    """v rounded half away from zero on its decimal value: 892.5 -> 893, -2.45 -> -2.5, 0.05 -> 0.1.

    Decimal(repr(v)) reads the number as it is written (2.45, not 2.4500000000000001776...), and
    ROUND_HALF_UP is half away from zero. Display only: the value itself is never stored rounded."""
    d = v if isinstance(v, Decimal) else Decimal(repr(float(v)))
    return d.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)


def _percent(v: float, fraction: bool):
    """v as a percent, exactly: 0.0245 -> Decimal("2.45"), where 0.0245 * 100 is 2.4499999999999997."""
    return Decimal(repr(float(v))) * 100 if fraction else v


def fixed(v: float, digits: int = 1) -> str:
    """A plain number to ``digits`` places, half away from zero, no sign added: "2.5", "−0.1"."""
    r = half_up(v, digits)
    return f"{MINUS if r < 0 else ''}{abs(r):.{digits}f}"


def signed(v: float | Decimal, digits: int = 1, plus: bool = True) -> str:
    """Rounded first (half away from zero), then signed: "+2.3", "−1.9", "0.0"."""
    r = half_up(v, digits)
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
    r = half_up(v, decimals)
    whole = int(abs(r))
    frac = f"{abs(r) - whole:.{decimals}f}"[1:] if decimals else ""
    sign = MINUS if r < 0 else ("+" if plus and r > 0 else "")
    return f"{sign}₹{indian_group(whole)}{frac}"


def price(x, plus: bool = False) -> str:
    """A price or price level for display: "₹2,906", "₹70" (whole rupees, Indian grouping, at any
    level: S173, owner 22 Nov 2026). Display only."""
    v = _finite(x)
    if v is None:
        return DASH
    return inr(v, 0, plus=plus)


def pts(x, digits: int = 1, fraction: bool = True) -> str:
    """A difference between two returns, in percentage points: 0.083 -> "+8.3 pts".

    Alpha is the strategy's return less the index's, so "+8.3%" would read as
    8.3% OF the index's return (owner, 8 Nov 2026: points, S97 d).
    """
    v = _finite(x)
    if v is None:
        return DASH
    return f"{signed(_percent(v, fraction), digits)} pts"


def pct(x, signed_: bool = True, digits: int = 1, fraction: bool = True) -> str:
    """A return as a percentage: 0.023 -> "+2.3%" (fraction=False takes 2.3)."""
    v = _finite(x)
    if v is None:
        return DASH
    return f"{signed(_percent(v, fraction), digits, plus=signed_)}%"


def date(x, short: bool = False) -> str:
    """A date for display: "20 Nov 2026", or "20 Nov" in a tight column (S173 rule 3). Text that is not a date
    is returned as it is, so a table can pass every cell through."""
    import re
    from datetime import date as _date

    if hasattr(x, "strftime"):
        d = x
    else:
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:[ T]00:00:00)?", str(x).strip())
        if not m:
            return str(x)
        d = _date(int(m[1]), int(m[2]), int(m[3]))
    return f"{d.day} {d.strftime('%b')}" + ("" if short else f" {d.year}")


# A stock's size, as the glossary writes it (glossary 3, owner 23 Nov 2026); the data keeps "Large", "Mid", ...
SIZE_NAMES = {"Large": "Large Cap", "Mid": "Mid Cap", "Small": "Small Cap", "Micro": "Micro Cap"}


def size(key) -> str:
    """A size for display: "Small" -> "Small Cap"; "Nano Cap" and anything else unchanged."""
    return SIZE_NAMES.get(str(key), str(key))


def since(start) -> str:
    """The start of a system's record, as the glossary writes it (glossary 7): "Since 1 Jan 2026"."""
    return f"Since {date(start)}"


PTS_NOTE = "pts = percentage points: 12% − 8% = 4 pts."   # where a reader first meets pts on a page (glossary 4)


PRICES_SOURCE = "NSE"   # the exchange the closes are from; the vendor is not named on a page (owner, 20-21 Nov 2026: "Let's not show source")


def data_to(as_of, source: str = PRICES_SOURCE) -> str:
    """A page's footer line: "Data to 20 Nov 2026 · NSE" (S173 rule 7)."""
    return f"Data to {date(as_of)} · {source}"
