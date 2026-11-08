"""Which sectors lead, and is leadership changing? From NSE's sector indices.

Owner, 8 Nov 2026 (TODO S109): the Dashboard answers both from NSE's own
sector indices with plain returns against the Nifty 500, which anyone can
check on a price chart. An RRG was tried first and dropped: against
StockCharts' weekly India RRG it agreed on the quadrant for 64% of indices on
a held-out week, below the owner's 80% bar.

Leading is the 3-month return against the Nifty 500; changing compares the
1-month figure with the 3-month one. Windows are calendar months on the
sessions both series hold, as in size_leadership, and a figure "against the
Nifty 500" is (1 + r) / (1 + r500) - 1, the same as the size table's.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.engine.calendar_momentum import calendar_start_positions
from src.engine.size_leadership import closes

# Key in the index-level file (scripts/build_nse_index_prices.SECTOR_NAMES) -> name shown.
SECTORS = (
    ("sector_bank", "Bank"), ("sector_it", "IT"), ("sector_pharma", "Pharma"),
    ("sector_auto", "Auto"), ("sector_fmcg", "FMCG"), ("sector_metal", "Metal"),
    ("sector_realty", "Realty"), ("sector_media", "Media"), ("sector_psu_bank", "PSU Bank"),
    ("sector_fin_services", "Financial Services"), ("sector_pse", "PSE"),
    ("sector_energy", "Energy"), ("sector_infra", "Infrastructure"),
)
LONG, SHORT = 3, 1          # months
MIN_SECTORS = 8             # fewer than this and the answer is left out
GROUPS = ("ahead on both", "gaining", "fading", "behind on both")


@dataclass(frozen=True)
class SectorRotation:
    table: pd.DataFrame      # index: sector name; "3M vs 500", "1M vs 500", "3M", "1M", "group"
    starts: dict[int, pd.Timestamp]
    end: pd.Timestamp
    missing: tuple[str, ...]


def _group(long_rel: float, short_rel: float) -> str:
    if long_rel > 0 and short_rel > 0:
        return "ahead on both"
    if long_rel <= 0 and short_rel > 0:
        return "gaining"
    if long_rel > 0:
        return "fading"
    return "behind on both"


def sector_rotation(levels: pd.DataFrame | None, nifty500: pd.Series | None) -> SectorRotation | None:
    if levels is None or levels.empty or nifty500 is None:
        return None
    wide = closes(levels)
    keys = [k for k, _ in SECTORS if k in wide]
    if len(keys) < MIN_SECTORS:
        return None
    n500 = pd.to_numeric(nifty500, errors="coerce").dropna()
    n500.index = pd.to_datetime(n500.index).normalize()
    joined = wide[keys].join(n500.rename("nifty500"), how="inner")
    joined = joined[joined["nifty500"].notna()]
    if len(joined) < 30:
        return None
    idx = pd.DatetimeIndex(joined.index)
    end = idx[-1]
    starts: dict[int, pd.Timestamp] = {}
    for w in (SHORT, LONG):
        pos = int(calendar_start_positions(idx, w)[-1])
        if pos >= len(idx) - 1:
            return None
        starts[w] = idx[pos]
    rows = {}
    for key, name in SECTORS:
        if key not in joined:
            continue
        row = {}
        for w, start in starts.items():
            a, b = joined.at[start, key], joined.at[end, key]
            if pd.isna(a) or pd.isna(b) or a <= 0:
                row = {}
                break
            r = b / a - 1
            r500 = joined.at[end, "nifty500"] / joined.at[start, "nifty500"] - 1
            row[f"{w}M"] = r
            row[f"{w}M vs 500"] = (1 + r) / (1 + r500) - 1
        if row:
            rows[name] = row
    if len(rows) < MIN_SECTORS:
        return None
    table = pd.DataFrame(rows).T.sort_values(f"{LONG}M vs 500", ascending=False)
    table["group"] = [_group(lr, sr) for lr, sr in zip(table[f"{LONG}M vs 500"], table[f"{SHORT}M vs 500"])]
    missing = tuple(name for _, name in SECTORS if name not in table.index)
    return SectorRotation(table, starts, end, missing)


def leaders_sentence(res: SectorRotation) -> tuple[str, str]:
    """(verdict, sentence) for "Which sectors lead?"."""
    t, col = res.table, f"{LONG}M vs 500"
    ahead = t[t[col] > 0]
    top, bottom = t.index[0], t.index[-1]
    verdict = ", ".join(ahead.index[:3]) if len(ahead) else "None ahead"
    sentence = (f"{len(ahead)} of {len(t)} sector indices beat the Nifty 500 over {LONG} months; "
                f"{top} leads by {t.at[top, col] * 100:+.1f} pts and {bottom} trails by "
                f"{t.at[bottom, col] * 100:+.1f} pts.").replace("+-", "−").replace("-", "−")
    return verdict, sentence


def changing_sentence(res: SectorRotation) -> tuple[str, str]:
    """(verdict, sentence) for "Is leadership changing?"."""
    g = res.table["group"]
    gaining, fading = list(g[g == "gaining"].index), list(g[g == "fading"].index)
    moved = len(gaining) + len(fading)
    if moved == 0:
        verdict = "No"
    elif moved >= len(g) / 3:
        verdict = "Yes"
    else:
        verdict = "A little"
    parts = []
    if gaining:
        parts.append(f"gaining: {', '.join(gaining)}")
    if fading:
        parts.append(f"fading: {', '.join(fading)}")
    sentence = (f"{moved} of {len(g)} sector indices are on the other side of the Nifty 500 over the last month "
                f"than over {LONG} months" + (f" ({'; '.join(parts)})" if parts else "") + ".")
    return verdict, sentence
