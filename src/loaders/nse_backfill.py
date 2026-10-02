"""NSE history from 2010 without asking NSE for 3,400 daily bundles.

Owner, 2026-10-02: "GitHub data we should check first because waiting 3
days not a good idea". Two sources, both NSE's own record:

PRICES. A public mirror on GitHub (tilak999/NSE-Data-bank, kept current by
its own GitHub Action) holds NSE's full bhavcopy, sec_bhavdata_full_<ddmmyyyy>.csv,
for every session from 10 Jun 2010. Checked against NSE's own Pd file on
2026-10-02: 2 Jan 2012, 1,491 of 1,491 rows and 10 Aug 2026, 2,712 of 2,712
rows equal to the paisa on close and to the share on volume. mirror_prices()
turns one file into the rows NSE's bundle gives (nse_bundle.PRICE_COLUMNS),
so R2's nse/prices_daily holds one shape whatever the day's source.

CORPORATE ACTIONS. The mirror has none. NSE's corporate-action list
answers a whole year in one request (2012: 1,816 rows) with the same
wording the daily Bc file uses -- every 2025-26 split and bonus in the list
is also in the Bc files -- and the face value, which a rights premium is
quoted over. api_actions() turns it into nse_bundle.ACTION_COLUMNS rows plus
face_value.
"""

from __future__ import annotations

import re
import time
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from src.loaders import nse_bundle as nb

MIRROR_REPO = "https://github.com/tilak999/NSE-Data-bank"
MIRROR_START = date(2010, 6, 10)
_MIRROR_NAME = re.compile(r"sec_bhavdata_full_(\d{2})(\d{2})(\d{4})\.csv$")
# NSE's classic bhavcopy (cm02JAN2009bhav.csv): the mirror's historic_data/, and
# NSE's own archive before its daily bundles begin (4 Jan 2010).
_CM_NAME = re.compile(r"cm(\d{2}[A-Z]{3}\d{4})bhav\.csv$")
CM_URL = "https://nsearchives.nseindia.com/content/historical/EQUITIES/{yyyy}/{MON}/cm{DDMONYYYY}bhav.csv.zip"

API_URL = "https://www.nseindia.com/api/corporates-corporateActions"
API_INDICES = ("equities", "sme")
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-actions",
}
API_DELAY_S = 3.0


# ── Prices from the mirror ───────────────────────────────────────────────────

def mirror_days(directory: Path) -> dict[date, Path]:
    """{session: file} for every bhavcopy file in `directory`: the full layout
    (sec_bhavdata_full_DDMMYYYY.csv) or the classic one (cmDDMONYYYYbhav.csv)."""
    out = {}
    for path in Path(directory).glob("cm*bhav.csv"):
        m = _CM_NAME.search(path.name)
        if m:
            try:
                out[datetime.strptime(m.group(1), "%d%b%Y").date()] = path
            except ValueError:
                continue
    for path in Path(directory).glob("sec_bhavdata_full_*.csv"):   # the full file wins a day both hold
        m = _MIRROR_NAME.search(path.name)
        if m:
            dd, mm, yyyy = (int(x) for x in m.groups())
            try:
                out[date(yyyy, mm, dd)] = path
            except ValueError:
                continue
    return out


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.strip().replace({"-": None, "": None}),
                         errors="coerce")


def mirror_prices(path: Path, day: date) -> pd.DataFrame:
    """One mirror file as nse_bundle.PRICE_COLUMNS rows (stocks: mkt "N").

    TURNOVER_LACS is in lakhs (value / 1e5, two decimals); fields NSE's Pd
    file has and the mirror does not (security name, 52-week range) are empty.
    """
    raw = pd.read_csv(path, skipinitialspace=True, dtype=str)
    raw.columns = [c.strip().upper() for c in raw.columns]
    if "TOTTRDQTY" in raw.columns:           # the classic layout: value in rupees, no 52-week range
        raw = raw.rename(columns={"OPEN": "OPEN_PRICE", "HIGH": "HIGH_PRICE", "LOW": "LOW_PRICE",
                                  "CLOSE": "CLOSE_PRICE", "PREVCLOSE": "PREV_CLOSE",
                                  "TOTTRDQTY": "TTL_TRD_QNTY", "TOTALTRADES": "NO_OF_TRADES"})
        raw["TURNOVER_LACS"] = (_num(raw["TOTTRDVAL"]) / 1e5).astype(str)
    sym = raw["SYMBOL"].astype(str).str.strip()
    out = pd.DataFrame({
        "date": pd.Timestamp(day),
        "mkt": "N",
        "series": raw["SERIES"].astype(str).str.strip(),
        "symbol": sym,
        "security": "",
        "prev_close": _num(raw["PREV_CLOSE"]),
        "open": _num(raw["OPEN_PRICE"]),
        "high": _num(raw["HIGH_PRICE"]),
        "low": _num(raw["LOW_PRICE"]),
        "close": _num(raw["CLOSE_PRICE"]),
        "value": _num(raw["TURNOVER_LACS"]) * 1e5,
        "volume": _num(raw["TTL_TRD_QNTY"]),
        "trades": _num(raw["NO_OF_TRADES"]) if "NO_OF_TRADES" in raw else np.nan,
        "corp_ind": "",
        "hi_52w": np.nan,
        "lo_52w": np.nan,
        "ind_sec": "",
    })
    out = out[(out["symbol"] != "") & (out["symbol"] != "NAN") & out["close"].notna()]
    return out[nb.PRICE_COLUMNS].reset_index(drop=True)


# ── Corporate actions from NSE's list ────────────────────────────────────────

def _api_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.replace({"-": None}), format="%d-%b-%Y", errors="coerce")


def api_actions(rows: list[dict]) -> pd.DataFrame:
    """NSE's corporate-action list rows as nse_bundle.ACTION_COLUMNS + face_value."""
    if not rows:
        return pd.DataFrame(columns=[*nb.ACTION_COLUMNS, "face_value"])
    raw = pd.DataFrame(rows)
    ex = _api_date(raw["exDate"])
    out = pd.DataFrame({
        "date": ex,                               # the list carries no listing day
        "series": raw.get("series", "").astype(str).str.strip(),
        "symbol": raw["symbol"].astype(str).str.strip().str.upper(),
        "security": raw.get("comp", "").astype(str).str.strip(),
        "record_date": _api_date(raw.get("recDate", pd.Series("-", index=raw.index))),
        "bc_start": _api_date(raw.get("bcStartDate", pd.Series("-", index=raw.index))),
        "bc_end": _api_date(raw.get("bcEndDate", pd.Series("-", index=raw.index))),
        "ex_date": ex,
        "nd_start": _api_date(raw.get("ndStartDate", pd.Series("-", index=raw.index))),
        "nd_end": _api_date(raw.get("ndEndDate", pd.Series("-", index=raw.index))),
        "purpose": raw["subject"].astype(str).str.strip(),
    })
    parsed = pd.DataFrame([nb.classify_purpose(p) for p in out["purpose"]], index=out.index,
                          columns=["kind", "ratio_new", "ratio_held", "face_from",
                                   "face_to", "amount", "price_factor"])
    out = pd.concat([out, parsed], axis=1)
    out["face_value"] = pd.to_numeric(raw.get("faceVal"), errors="coerce")
    out = out[out["ex_date"].notna() & (out["symbol"] != "")]
    return out[[*nb.ACTION_COLUMNS, "face_value"]].drop_duplicates(
        ["symbol", "ex_date", "purpose"]).reset_index(drop=True)


def fetch_actions_year(year: int, session: requests.Session | None = None,
                       sleep=time.sleep) -> pd.DataFrame:
    """Every equity and SME corporate action with an ex-date in `year`."""
    session = session or requests.Session()
    session.headers.update(API_HEADERS)
    rows: list[dict] = []
    for i, index in enumerate(API_INDICES):
        if i:
            sleep(API_DELAY_S)
        r = session.get(API_URL, params={"index": index, "from_date": f"01-01-{year}",
                                         "to_date": f"31-12-{year}"}, timeout=60)
        if r.status_code in (401, 403, 429):
            raise nb.NSEBlocked(f"HTTP {r.status_code}")
        r.raise_for_status()
        got = r.json()
        rows += got if isinstance(got, list) else got.get("data", [])
    return api_actions(rows)


def face_values(actions: pd.DataFrame | None) -> dict[str, float]:
    """{symbol: face value} from the latest action that states one."""
    if actions is None or actions.empty or "face_value" not in actions.columns:
        return {}
    a = actions.dropna(subset=["face_value"]).sort_values("ex_date")
    return {s: float(v) for s, v in zip(a["symbol"], a["face_value"]) if v > 0}
