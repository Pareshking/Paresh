"""NSE's own end-of-day bundle: prices, corporate actions and market caps.

NSE publishes one zip per trading day at
archives.nseindia.com/archives/equities/bhavcopy/pr/PR<ddmmyy>.zip. The
nightly sync has fetched it for years, but only read the market-cap file out
of it. The same zip carries the exchange's own record of the day:

  Pd<ddmmyy>.csv   every security's open, high, low, close, previous close,
                   traded value and quantity -- UNADJUSTED, as they traded
  Bc<ddmmyy>.csv   book closures and record dates, with the purpose in words
                   ("BONUS 1:1", "FACE VALUE SPLIT ... FROM RS 10/- ... TO
                   RS 2/-", "DIVIDEND - RS 5 PER SHARE")
  mcap<ddmmyyyy>.csv  market capitalisation of every listed security

This module fetches a bundle and turns those three files into tidy tables.
It never adjusts a price: the record is what NSE published that day, and
corporate actions are kept as their own rows so an adjusted series can be
rebuilt from the two at any time. The parsers match columns by name and
tolerate a missing column (it comes back empty) rather than failing, so a
format change shows up as blanks in the record, not as a lost day.
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import date

import numpy as np
import pandas as pd
import requests

from src.core.config import HTTP_HEADERS

BUNDLE_URL = "https://archives.nseindia.com/archives/equities/bhavcopy/pr/PR{ddmmyy}.zip"


class NSEBlocked(RuntimeError):
    """NSE refused the client (401/403/429). Every other date will be refused
    too, so the caller stops for this run instead of retrying into a block."""


def bundle_url(day: date) -> str:
    return BUNDLE_URL.format(ddmmyy=day.strftime("%d%m%y"))


def fetch_bundle(day: date, session: requests.Session | None = None,
                 timeout: float = 20.0) -> dict[str, bytes] | None:
    """The bundle's files for `day`, by name, or None when NSE has none.

    A 404 means no bundle (a holiday, or not published yet). A refusal raises
    NSEBlocked. Anything else unexpected also returns None and is the
    caller's to report: one bad day must not end a run.
    """
    get = (session or requests).get
    resp = get(bundle_url(day), headers=HTTP_HEADERS, timeout=timeout)
    if resp.status_code in (401, 403, 429):
        raise NSEBlocked(f"HTTP {resp.status_code} for {day.isoformat()}")
    if resp.status_code != 200:
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            return {info.filename: zf.read(info) for info in zf.infolist()
                    if not info.is_dir()}
    except zipfile.BadZipFile:
        return None


def member(files: dict[str, bytes], prefix: str) -> bytes | None:
    """The CSV whose base name starts with `prefix` (case-insensitive)."""
    for name, body in files.items():
        base = name.rsplit("/", 1)[-1].lower()
        if base.startswith(prefix.lower()) and base.endswith(".csv"):
            return body
    return None


def read_csv(body: bytes) -> pd.DataFrame:
    """Every value as stripped text, headers upper-cased and trimmed.

    A row with more fields than the header keeps them, joined back into its
    last column: NSE writes some purposes with an unquoted comma ("INTERIM
    DIVIDEND - RS 2, SPECIAL DIVIDEND - RS 1"), and the Bc file of 2024-08-22
    stopped the whole backfill on one ("Expected 10 fields, saw 11").
    """
    header = body.split(b"\n", 1)[0].decode("utf-8", "replace")
    width = len(header.split(","))

    def _rejoin(fields: list[str]) -> list[str]:
        return fields[:width - 1] + [",".join(fields[width - 1:])]

    frame = pd.read_csv(io.BytesIO(body), dtype=str, keep_default_na=False,
                        skipinitialspace=True, encoding_errors="replace",
                        engine="python", on_bad_lines=_rejoin)
    frame.columns = [str(c).strip().upper() for c in frame.columns]
    return frame.apply(lambda s: s.str.strip())


def _col(frame: pd.DataFrame, *names: str, contains: str | None = None) -> pd.Series:
    for n in names:
        if n in frame.columns:
            return frame[n]
    if contains:
        for c in frame.columns:
            if contains in c:
                return frame[c]
    return pd.Series("", index=frame.index, dtype=object)


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False).str.strip(),
                         errors="coerce")


_ISO_DAY = r"^\s*\d{4}-\d{1,2}-\d{1,2}"


def _day(s: pd.Series) -> pd.Series:
    """NSE's dates, whichever way a file writes them.

    Most files write day first ("05-Dec-2025", "05-12-2025"), but the Bc file
    also writes ISO ("2025-12-05"), and pandas applies dayfirst to ISO too:
    "2025-12-05" became 12 May. CAMS's split (record date 5 Dec 2025) was
    stored as 2025-05-12 until 2026-09-27. ISO is read as ISO; the rest day
    first.
    """
    s = s.replace({"": None, "-": None})
    iso = s.fillna("").astype(str).str.match(_ISO_DAY)
    out = pd.to_datetime(s.where(~iso), errors="coerce", dayfirst=True, format="mixed")
    if iso.any():
        out[iso] = pd.to_datetime(s[iso].str.strip().str[:10], errors="coerce", format="%Y-%m-%d")
    return out


ACTION_DATE_COLUMNS = ["record_date", "bc_start", "bc_end", "ex_date", "nd_start", "nd_end"]


def repair_swapped_dates(actions: pd.DataFrame, before_days: int = 45,
                         after_days: int = 120) -> pd.DataFrame:
    """Undo the day/month swap in corporate actions stored before 2026-09-27.

    A Bc file lists closures around the day it was published. A stored date
    far outside that window whose day and month, swapped, land inside it was
    an ISO date read day-first; swap it back. Dates past the 12th could never
    be swapped and are left alone, as is anything the swap does not explain.
    """
    out = actions.copy()
    listed = pd.to_datetime(out["date"])
    lo, hi = listed - pd.Timedelta(days=before_days), listed + pd.Timedelta(days=after_days)
    for col in [c for c in ACTION_DATE_COLUMNS if c in out.columns]:
        d = pd.to_datetime(out[col])
        ok = d.notna() & (d.dt.day <= 12)
        swapped = pd.to_datetime(
            {"year": d.dt.year.where(ok, 2000), "month": d.dt.day.where(ok, 1),
             "day": d.dt.month.where(ok, 1)}, errors="coerce")
        fix = ok & ~d.between(lo, hi) & swapped.between(lo, hi)
        out.loc[fix, col] = swapped[fix]
    return out


# ── Prices ───────────────────────────────────────────────────────────────────

PRICE_COLUMNS = ["date", "mkt", "series", "symbol", "security", "prev_close",
                 "open", "high", "low", "close", "value", "volume", "trades",
                 "corp_ind", "hi_52w", "lo_52w", "ind_sec"]


def parse_prices(body: bytes, day: date) -> pd.DataFrame:
    """Pd<date>.csv: one row per traded security, as NSE printed it.

    Index rows (MKT = Y, no symbol, the index name in SECURITY) stay in: they
    carry the day's index closes. IND_SEC = Y is not an index row; it marks a
    stock that is an index member.
    """
    raw = read_csv(body)
    out = pd.DataFrame({
        "date": pd.Timestamp(day),
        "mkt": _col(raw, "MKT"),
        "series": _col(raw, "SERIES").str.upper(),
        "symbol": _col(raw, "SYMBOL").str.upper(),
        "security": _col(raw, "SECURITY"),
        "prev_close": _num(_col(raw, "PREV_CL_PR", "PREV_CLOSE", "PREVCLOSE")),
        "open": _num(_col(raw, "OPEN_PRICE", "OPEN")),
        "high": _num(_col(raw, "HIGH_PRICE", "HIGH")),
        "low": _num(_col(raw, "LOW_PRICE", "LOW")),
        "close": _num(_col(raw, "CLOSE_PRICE", "CLOSE")),
        "value": _num(_col(raw, "NET_TRDVAL", "TURNOVER")),
        "volume": _num(_col(raw, "NET_TRDQTY", "TOTTRDQTY")),
        "trades": _num(_col(raw, "TRADES", "TOTALTRADES")),
        "corp_ind": _col(raw, "CORP_IND"),
        "hi_52w": _num(_col(raw, "HI_52_WK")),
        "lo_52w": _num(_col(raw, "LO_52_WK")),
        "ind_sec": _col(raw, "IND_SEC").str.upper(),
    }, index=raw.index)
    out = out[(out["symbol"] != "") | (out["security"] != "")]
    return out[PRICE_COLUMNS].reset_index(drop=True)


# ── Corporate actions ────────────────────────────────────────────────────────

ACTION_COLUMNS = ["date", "series", "symbol", "security", "record_date",
                  "bc_start", "bc_end", "ex_date", "nd_start", "nd_end",
                  "purpose", "kind", "ratio_new", "ratio_held", "face_from",
                  "face_to", "amount", "price_factor"]

# Most price-changing first: a purpose naming several takes the first match.
# NSE's Bc file abbreviates: a split reads "FVSPLT FRM RS 10 TO RE 1" (also
# "FV SPLT", "FRMRS 100", "TO 1", "RE1"), and a bonus of preference shares
# "SCH AGMT-BONUS NCRPS 4:1". The first sample year (2026-09-27) recognised
# no split at all and counted NCRPS bonuses as equity bonuses; both are
# pinned in tests/test_nse_bundle.py with NSE's own wording.
_KINDS = [
    ("split", re.compile(r"SPLIT|SPLT|SUB[- ]?DIVISION|SUBDIVISION")),
    ("consolidation", re.compile(r"CONSOLIDAT")),
    # Preference shares issued as bonus: equity holders keep every share, so
    # the equity price has no bonus step (TVSMOTOR 2025-08-25 moved -0.3%).
    ("bonus_preference", re.compile(r"BONUS\s*(?:NCRPS|PREF|RPS|NCPS|DEBENTURE)")),
    ("bonus", re.compile(r"BONUS")),
    ("demerger", re.compile(r"DEMERGER|SPIN[- ]?OFF")),
    ("rights", re.compile(r"RIGHTS")),
    ("buyback", re.compile(r"BUY[- ]?BACK")),
    ("dividend", re.compile(r"DIVIDEND|\bDIV\b|DISTRIBUTION")),
]
_RATIO = re.compile(r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)")
_FACE = re.compile(r"(?:FROM|FRM)\s*R[SE]?\.?\s*([\d.]+).*?\bTO\s*(?:R[SE]?\.?)?\s*([\d.]+)")
_AMOUNT = re.compile(r"(?:RS|RE|INR)\.?\s*([\d]+(?:\.\d+)?)")


def classify_purpose(purpose: str) -> dict:
    """What an action is and, where the words say it, the price factor.

    price_factor is what every price before the ex-date is multiplied by to
    sit on the same basis as prices after it:
      split / consolidation  face value to / face value from  (10 -> 2: 0.2)
      bonus a:b              b / (a + b)   (a new shares for every b held)
    Dividends, rights and demergers have none here: their factor depends on
    prices or on terms the purpose text does not carry.
    """
    text = (purpose or "").upper()
    kind = next((k for k, rx in _KINDS if rx.search(text)), "other")
    info = {"kind": kind, "ratio_new": np.nan, "ratio_held": np.nan,
            "face_from": np.nan, "face_to": np.nan, "amount": np.nan,
            "price_factor": np.nan}
    if kind in ("split", "consolidation"):
        m = _FACE.search(text)
        if m:
            f_from, f_to = float(m.group(1)), float(m.group(2))
            info.update(face_from=f_from, face_to=f_to)
            if f_from > 0 and f_to > 0:
                info["price_factor"] = f_to / f_from
    elif kind in ("bonus", "rights"):
        m = _RATIO.search(text)
        if m:
            new, held = float(m.group(1)), float(m.group(2))
            info.update(ratio_new=new, ratio_held=held)
            if kind == "bonus" and new > 0 and held > 0:
                info["price_factor"] = held / (new + held)
    elif kind == "dividend":
        m = _AMOUNT.search(text)
        if m:
            info["amount"] = float(m.group(1))
    return info


def parse_corporate_actions(body: bytes, day: date) -> pd.DataFrame:
    """Bc<date>.csv: the book closures and record dates NSE listed that day."""
    raw = read_csv(body)
    out = pd.DataFrame({
        "date": pd.Timestamp(day),
        "series": _col(raw, "SERIES").str.upper(),
        "symbol": _col(raw, "SYMBOL").str.upper(),
        "security": _col(raw, "SECURITY"),
        "record_date": _day(_col(raw, "RECORD_DT", "RECORD_DATE")),
        "bc_start": _day(_col(raw, "BC_STRT_DT", "BC_START_DT")),
        "bc_end": _day(_col(raw, "BC_END_DT")),
        "ex_date": _day(_col(raw, "EX_DT", "EX_DATE")),
        "nd_start": _day(_col(raw, "ND_STRT_DT", "ND_START_DT")),
        "nd_end": _day(_col(raw, "ND_END_DT")),
        "purpose": _col(raw, "PURPOSE"),
    }, index=raw.index)
    out = out[out["symbol"] != ""].reset_index(drop=True)
    parsed = pd.DataFrame([classify_purpose(p) for p in out["purpose"]],
                          index=out.index,
                          columns=["kind", "ratio_new", "ratio_held", "face_from",
                                   "face_to", "amount", "price_factor"])
    return pd.concat([out, parsed], axis=1)[ACTION_COLUMNS]


# ── Market caps ──────────────────────────────────────────────────────────────

MCAP_COLUMNS = ["date", "symbol", "series", "security", "category",
                "last_trade_date", "face_value", "issue_size", "close", "mcap"]


def parse_market_caps(body: bytes, day: date) -> pd.DataFrame:
    """mcap<date>.csv: every listed security's market capitalisation (rupees)."""
    raw = read_csv(body)
    out = pd.DataFrame({
        "date": pd.Timestamp(day),
        "symbol": _col(raw, "SYMBOL", contains="SYMBOL").str.upper(),
        "series": _col(raw, "SERIES").str.upper(),
        "security": _col(raw, "SECURITY NAME", "SECURITY", contains="SECURITY"),
        "category": _col(raw, "CATEGORY", contains="CATEGORY"),
        "last_trade_date": _day(_col(raw, "LAST TRADE DATE", contains="TRADE DATE")),
        "face_value": _num(_col(raw, contains="FACE VALUE")),
        "issue_size": _num(_col(raw, contains="ISSUE SIZE")),
        "close": _num(_col(raw, contains="CLOSE PRICE")),
        "mcap": _num(_col(raw, contains="MARKET CAP")),
    }, index=raw.index)
    out = out[out["symbol"] != ""].reset_index(drop=True)
    return out[MCAP_COLUMNS]


def parse_bundle(files: dict[str, bytes], day: date) -> dict[str, pd.DataFrame]:
    """The three tables a bundle yields; a file the zip lacks is left out."""
    tables: dict[str, pd.DataFrame] = {}
    for key, prefix, parser in (("prices", "pd", parse_prices),
                                ("corporate_actions", "bc", parse_corporate_actions),
                                ("market_caps", "mcap", parse_market_caps)):
        body = member(files, prefix)
        if body is not None:
            tables[key] = parser(body, day)
    return tables
