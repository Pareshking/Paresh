"""REITs (series RR) get NSE's market cap, and a stale cap is never re-dated.

Production log, 20 Nov 2026: "Loaded NSE PR market cap: 2598 stocks" and no
cap at all for BAGMANE. NSE's mcap20112026.csv does print RR rows (BAGMANE,
BIRET, EMBASSY, ...); the parser kept EQ/BE/BL/BT only, and 2,598 is exactly
EQ 2,407 + BE 191. BIRET and EMBASSY were "rescued" by the committed snapshot,
whose value had not changed since 16 Nov but was re-stamped as today's
pr_live_zip every night.
"""
import importlib.util
import io
import logging
import pathlib
import zipfile
from datetime import date

import pandas as pd
import pytest

from src.core import startup_metrics as metrics
from src.engine import track_record
from src.loaders import mcap_loader

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Rows copied from NSE's PR201126.zip (mcap20112026.csv), plus synthetic rows
# for the series that must stay out and for a duplicate.
HEADER = ("Trade Date,Symbol,Series,Security Name,Category,Last Trade Date,"
          "Face Value(Rs.),Issue Size,Close Price/Paid up value(Rs.),Market Cap(Rs.)              ")
ROWS = [
    "20 NOV 2026,20MICRONS,EQ,20 MICRONS LTD,Listed,20 NOV 2026,5.00,35286502,179.50,     6333574244.00 ",
    "20 NOV 2026,21STCENMGM,BE,21ST CENTURY MGMT SERVICE,Listed,20 NOV 2026,10.00,10500000,46.10,483945000.00",
    "20 NOV 2026,BAGMANE,RR,BAGMANE PRIME OFFICE REIT,Listed,20 NOV 2026,100.00,3400000000,105.80,   359686000000.00   ",
    "20 NOV 2026,BIRET,RR,BROOKFIELD INDIA RET,Listed,20 NOV 2026,275.00,829880869,319.85,   265429097140.95     ",
    "20 NOV 2026,SOMEINVIT,IV,SOME INVIT,Listed,20 NOV 2026,100.00,1000,100.00,100000.00",
    "20 NOV 2026,SMECO,SM,SME CO,Listed,20 NOV 2026,10.00,1000,10.00,10000.00",
    "20 NOV 2026,STCO,ST,ST CO,Listed,20 NOV 2026,10.00,1000,10.00,10000.00",
    "20 NOV 2026,BZCO,BZ,BZ CO,Listed,20 NOV 2026,10.00,1000,10.00,10000.00",
    # One symbol in three series: EQ must win whatever the row order.
    "20 NOV 2026,DUPCO,BL,DUP CO,Listed,20 NOV 2026,10.00,1000,30.00,30000.00",
    "20 NOV 2026,DUPCO,BE,DUP CO,Listed,20 NOV 2026,10.00,1000,20.00,20000.00",
    "20 NOV 2026,DUPCO,EQ,DUP CO,Listed,20 NOV 2026,10.00,1000,10.00,10000.00",
    # BE before BL when there is no EQ.
    "20 NOV 2026,DUP2,BT,DUP2,Listed,20 NOV 2026,10.00,1000,30.00,30000.00",
    "20 NOV 2026,DUP2,BE,DUP2,Listed,20 NOV 2026,10.00,1000,20.00,20000.00",
]


class _Resp:
    status_code = 200

    def __init__(self, content):
        self.content = content


@pytest.fixture
def caps(monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mcap20112026.csv", "\n".join([HEADER, *ROWS]) + "\n")
    monkeypatch.setattr(mcap_loader.requests, "get", lambda *a, **k: _Resp(buf.getvalue()))
    return mcap_loader._fetch_mcap_from_pr_zip(date(2026, 11, 20))


@pytest.mark.parametrize("sym", ["20MICRONS", "21STCENMGM", "BAGMANE", "BIRET", "SOMEINVIT"])
def test_equity_reit_and_invit_series_are_read(caps, sym):
    assert caps[sym] > 0


def test_bagmane_is_nse_printed_cap(caps):
    assert caps["BAGMANE"] == 359_686_000_000.0


@pytest.mark.parametrize("sym", ["SMECO", "STCO", "BZCO"])
def test_sme_and_other_series_stay_out(caps, sym):
    assert sym not in caps


def test_duplicate_series_resolve_deterministically(caps):
    assert caps["DUPCO"] == 10_000.0   # EQ
    assert caps["DUP2"] == 20_000.0    # BE over BT


def _sync_module():
    spec = importlib.util.spec_from_file_location("sync_data_t", ROOT / "scripts/sync_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_gap_filled_caps_keep_their_old_date_and_source(tmp_path):
    prev = tmp_path / "nse_market_caps.csv"
    prev.write_text("Symbol,MarketCap,AsOf,Source\n"
                    "BIRET,218665310172.81,2026-11-16,pr_live_zip\n"
                    "TCS,1.0,2026-11-19,pr_live_zip\n")
    snap = pd.DataFrame({"Symbol": ["BIRET", "NEWCO", "TCS"],
                         "MarketCap": [218665310172.81, 5.0, 2.0],
                         "AsOf": "2026-11-20", "Source": "pr_live_zip"})
    out = _sync_module().carry_forward_gap_fill(snap, str(prev), "BIRET,NEWCO").set_index("Symbol")
    assert out.loc["BIRET", "AsOf"] == "2026-11-16"     # not re-dated to today
    assert out.loc["NEWCO", "AsOf"] == ""               # no prior date: says so
    assert out.loc["TCS", "AsOf"] == "2026-11-20"       # live row untouched


def test_loader_names_the_gap_filled_symbols(tmp_path, monkeypatch):
    snap = tmp_path / "nse_market_caps.csv"
    snap.write_text("Symbol,MarketCap,AsOf,Source\nOLDCO,7.0,2026-11-10,pr_live_zip\n")
    monkeypatch.setattr(mcap_loader, "REPO_MCAP_FILE", str(snap))
    monkeypatch.setattr(mcap_loader, "MCAP_PR_FILE", str(tmp_path / "pr.parquet"))
    monkeypatch.setattr(mcap_loader, "_fetch_mcap_from_pr_zip", lambda d: {"LIVECO": 1.0})
    out = mcap_loader.fetch_market_caps(["LIVECO", "OLDCO"], force_refresh=True)
    assert set(out.index) == {"LIVECO", "OLDCO"}
    assert metrics.snapshot()["facts"]["mcap_repo_gap_fill_list"] == "OLDCO"


def test_not_yet_frozen_ledger_logs_once(tmp_path, caplog, monkeypatch):
    monkeypatch.setattr(track_record, "_NOT_YET_LOGGED", set())
    path = tmp_path / "track_record_shadow_x.json"
    start = track_record._current_month()
    with caplog.at_level(logging.INFO, logger=track_record.logger.name):
        for _ in range(3):
            track_record.load_ledger(path, start)
    assert sum("no frozen month yet" in r.message for r in caplog.records) == 1
