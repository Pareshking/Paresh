"""NSE's daily bundle: parsing, the collection loop, and the source check."""
import io
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts import nse_collect as nc
from src.engine import source_check
from src.loaders import nse_bundle as nb

DAY = date(2026, 9, 25)

PD = (
    "MKT,SERIES,SYMBOL,SECURITY,PREV_CL_PR,OPEN_PRICE,HIGH_PRICE,LOW_PRICE,CLOSE_PRICE,"
    "NET_TRDVAL,NET_TRDQTY,IND_SEC,CORP_IND,TRADES,HI_52_WK,LO_52_WK\n"
    "Y, ,Nifty 50,Nifty 50,25000,25010,25100,24900,25050,0,0,Y, ,0,26000,22000\n"
    "N,EQ,IRCTC,Indian Railway Catering,455.00,456,462,450.5,459.00,1234567.5,2690,N, ,5000,920,420\n"
    "N,BE,IRCTC,Indian Railway Catering,455.00,456,462,450.5,458.00,1,1,N, ,1,920,420\n"
    "N,EQ,J&KBANK,Jammu & Kashmir Bank,100,101,103,99,102,1,1,N,XD,1,150,90\n"
)
BC = (
    "SERIES,SYMBOL,SECURITY,RECORD_DT,BC_STRT_DT,BC_END_DT,EX_DT,ND_STRT_DT,ND_END_DT,PURPOSE\n"
    "EQ,ABC,Abc Ltd,26-Sep-2026, , ,26-Sep-2026, , ,BONUS 1:1\n"
    "EQ,DEF,Def Ltd,29-Sep-2026, , ,29-Sep-2026, , ,"
    "FACE VALUE SPLIT (SUB-DIVISION) - FROM RS 10/- PER SHARE TO RS 2/- PER SHARE\n"
    "EQ,GHI,Ghi Ltd,30-Sep-2026, , ,30-Sep-2026, , ,INTERIM DIVIDEND - RS 5.50 PER SHARE\n"
)
MCAP = (
    "Trade Date,Symbol,Series,Security Name,Category,Last Trade Date,Face Value(Rs.),"
    "Issue Size,Close Price/Paid up value(Rs.),Market Cap(Rs.)\n"
    "25 Sep 2026,IRCTC,EQ,Indian Railway Catering,Listed,25 Sep 2026,2,800000000,459,367200000000\n"
    "25 Sep 2026,TINY,SM,Tiny SME,Listed,25 Sep 2026,10,1000000,50,50000000\n"
)


def _zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    return buf.getvalue()


BUNDLE = {"Pd250926.csv": PD.encode(), "Bc250926.csv": BC.encode(),
          "mcap25092026.csv": MCAP.encode(), "Pr250926.txt": b"press"}


def test_prices_keep_every_series_and_the_index_rows_unadjusted():
    p = nb.parse_prices(PD.encode(), DAY)
    assert list(p.columns) == nb.PRICE_COLUMNS
    assert len(p) == 4
    irctc = p[(p.symbol == "IRCTC") & (p.series == "EQ")].iloc[0]
    assert irctc.close == 459.0 and irctc.prev_close == 455.0 and irctc.volume == 2690
    assert irctc.value == pytest.approx(1234567.5)
    assert p[p.ind_sec == "Y"].iloc[0].close == 25050
    assert p[p.symbol == "J&KBANK"].iloc[0].corp_ind == "XD"


def test_purposes_become_kinds_and_price_factors():
    c = nb.classify_purpose
    assert c("BONUS 1:1")["price_factor"] == 0.5
    assert c("BONUS 2:1")["price_factor"] == pytest.approx(1 / 3)
    split = c("FACE VALUE SPLIT (SUB-DIVISION) - FROM RS 10/- PER SHARE TO RS 2/- PER SHARE")
    assert split["kind"] == "split" and split["price_factor"] == pytest.approx(0.2)
    div = c("INTERIM DIVIDEND - RS 5.50 PER SHARE")
    assert div["kind"] == "dividend" and div["amount"] == 5.5 and np.isnan(div["price_factor"])
    # A split and a dividend in one purpose: the split decides the kind.
    assert c("FACE VALUE SPLIT FROM RS 10 TO RS 5 / DIVIDEND RS 2")["kind"] == "split"
    assert c("RIGHTS 1:5 @ PREMIUM RS 100/-")["kind"] == "rights"
    assert np.isnan(c("RIGHTS 1:5 @ PREMIUM RS 100/-")["price_factor"])
    assert c("ANNUAL GENERAL MEETING")["kind"] == "other"


def test_corporate_actions_parse_dates_and_purpose():
    a = nb.parse_corporate_actions(BC.encode(), DAY)
    assert list(a.columns) == nb.ACTION_COLUMNS
    assert list(a["kind"]) == ["bonus", "split", "dividend"]
    assert a.loc[0, "ex_date"] == pd.Timestamp("2026-09-26")
    assert pd.isna(a.loc[0, "bc_start"])


def test_market_caps_keep_every_series_in_rupees():
    m = nb.parse_market_caps(MCAP.encode(), DAY)
    assert list(m["symbol"]) == ["IRCTC", "TINY"]
    assert m.loc[0, "mcap"] == 367_200_000_000 and m.loc[1, "series"] == "SM"
    assert m.loc[0, "last_trade_date"] == pd.Timestamp("2026-09-25")


def test_a_missing_column_comes_back_empty_not_as_an_error():
    p = nb.parse_prices(b"SERIES,SYMBOL,CLOSE_PRICE\nEQ,ABC,10\n", DAY)
    assert p.loc[0, "close"] == 10 and np.isnan(p.loc[0, "high"])


class _Resp:
    def __init__(self, status, content=b""):
        self.status_code, self.content = status, content


class _Session:
    def __init__(self, resp):
        self.resp, self.urls = resp, []

    def get(self, url, **kw):
        self.urls.append(url)
        return self.resp


def test_fetch_reads_the_zip_and_names_the_right_file():
    s = _Session(_Resp(200, _zip({k: v.decode("latin-1") for k, v in BUNDLE.items()})))
    files = nb.fetch_bundle(DAY, session=s)
    assert s.urls == ["https://archives.nseindia.com/archives/equities/bhavcopy/pr/PR250926.zip"]
    assert set(nb.parse_bundle(files, DAY)) == {"prices", "corporate_actions", "market_caps"}


def test_fetch_returns_none_for_a_missing_day_and_raises_on_a_refusal():
    assert nb.fetch_bundle(DAY, session=_Session(_Resp(404))) is None
    with pytest.raises(nb.NSEBlocked):
        nb.fetch_bundle(DAY, session=_Session(_Resp(403)))


# ── The collection loop ──────────────────────────────────────────────────────

def test_collect_publishes_each_table_and_stops_at_a_refusal(tmp_path):
    published = []

    def publish(path, **kw):
        published.append((Path(path).name, kw["dataset"], kw["key_root"]))
        assert pd.read_parquet(path)["date"].nunique() == 1

    d1, d2, d3, d4 = date(2026, 9, 25), date(2026, 9, 24), date(2026, 9, 23), date(2026, 9, 22)

    def fetch(day):
        if day == d2:
            return None                        # holiday
        if day == d3:
            raise nb.NSEBlocked("HTTP 403")
        return BUNDLE

    sleeps = []
    stats = nc.collect([d1, d2, d3, d4], fetch=fetch, publish=publish, workdir=tmp_path,
                       sleep=sleeps.append, log=lambda *_: None)
    assert stats["published"] == [d1] and stats["absent"] == [d2] and stats["blocked"]
    assert d4 not in stats["published"]       # nothing after the refusal
    assert {p[1] for p in published} == {"nse/prices_daily", "nse/corporate_actions",
                                         "nse/market_caps"}
    assert all(p[2].startswith("archive/nse/") for p in published)
    assert len(sleeps) == 2                   # a pause between requests, none before the first


def test_backfill_takes_missing_sessions_newest_first():
    cal = [date(2016, 1, 4), date(2020, 5, 5), date(2026, 9, 24), date(2026, 9, 25)]
    have = {date(2026, 9, 25)}
    assert nc.backfill_dates(cal, have, 2) == [date(2026, 9, 24), date(2020, 5, 5)]
    assert nc.backfill_dates(cal, have, 9, start=date(2017, 1, 1)) == [
        date(2026, 9, 24), date(2020, 5, 5)]


def test_present_dates_reads_only_this_datasets_pointers():
    class A:
        def list_keys(self, prefix):
            return iter([prefix + "2026-09-25/current.json",
                         prefix + "2026-09-25/revisions/abc.json",
                         prefix + "2026-09-24/current.json"])
    assert nc.present_dates(A()) == {date(2026, 9, 25), date(2026, 9, 24)}


def test_recent_weekdays_skip_weekends():
    assert nc.recent_weekdays(3, date(2026, 9, 27)) == [
        date(2026, 9, 25), date(2026, 9, 24), date(2026, 9, 23)]


# ── Source check ─────────────────────────────────────────────────────────────

def _frame(day_prev, day, values: dict[str, tuple[float, float]]):
    return pd.DataFrame({s: [a, b] for s, (a, b) in values.items()},
                        index=pd.DatetimeIndex([day_prev, day]))


def test_source_check_flags_level_and_return_gaps_only():
    nse = nb.parse_prices(PD.encode(), DAY)
    prev, day = pd.Timestamp("2026-09-24"), pd.Timestamp("2026-09-25")
    # IRCTC: NSE 455 -> 459 (+0.9%). J&KBANK: 100 -> 102 (+2%).
    screener = _frame(prev, day, {"IRCTC": (455, 459), "J&KBANK": (100, 112)})
    # Yahoo's level is dividend-shifted (it drifts), but its move matches: no flag.
    yahoo = _frame(prev, day, {"IRCTC": (400, 403.5), "J&KBANK": (90, 91.8)})
    flags = source_check.compare(nse, screener, yahoo, ["IRCTC", "J&KBANK", "GONE"])
    got = {(r.symbol, r.check) for r in flags.itertuples()}
    assert got == {("J&KBANK", "screener_level"), ("J&KBANK", "screener_return"),
                   ("GONE", "missing_at_nse")}


def test_source_check_uses_eq_before_be():
    closes = source_check.nse_closes(nb.parse_prices(PD.encode(), DAY))
    assert closes.at["IRCTC", "close"] == 459.0
    assert "Nifty 50".upper() not in closes.index
