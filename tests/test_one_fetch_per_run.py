"""One run, one download: the NSE PR bundle (C8) and the Screener store (C7).

Measured 10 Nov 2026 (`docs/CALL_AND_STORAGE_AUDIT.md`):

* inside one `daily_sync` run the newest PR bundle was downloaded twice -- by
  `nse_collect --recent 3` and again by `build_benchmarks --update`, which only
  wants the Pd<ddmmyy>.csv rows out of the same zip;
* the 8.79 MB release asset `screener_prices.parquet` was downloaded ~6.2 times
  a day -- twice inside one `screener_sync` run (the backfill source, then the
  row-count guard) and once per `nse_collect` fire, four fires a day, for bytes
  `screener_sync` republishes once a day at ~18:45 UTC.

The bundle tests count requests on the real code path; the two workflow tests
read the YAML, because what changed there is the shape of the job.
"""
from __future__ import annotations

import io
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from scripts import build_benchmarks as bb
from scripts import nse_collect as nc
from src.loaders import nse_bundle as nb

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"

DAY = date(2026, 9, 25)
PD = (
    "MKT,SERIES,SYMBOL,SECURITY,PREV_CL_PR,OPEN_PRICE,HIGH_PRICE,LOW_PRICE,CLOSE_PRICE,"
    "NET_TRDVAL,NET_TRDQTY,IND_SEC,CORP_IND,TRADES,HI_52_WK,LO_52_WK\n"
    "Y, , ,Nifty 50,25000.00,25010,25100,24900,25050.00,0,0,Y, ,0,26000,22000\n"
    "Y, , ,Nifty 500,23000.00,23010,23100,22900,23077.70,0,0,Y, ,0,24000,20000\n"
    "N,EQ,RELIANCE,Reliance Industries,1400,1401,1420,1395,1414.00,1,1,Y, ,1,1600,1200\n"
)
BUNDLE = {"Pd250926.csv": PD.encode(), "Pr250926.txt": b"press release"}


def _zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, body in files.items():
            zf.writestr(name, body)
    return buf.getvalue()


class _Resp:
    def __init__(self, body: bytes):
        self.status_code = 200
        self.content = body


class _CountingNSE:
    """Serves one real zip and counts the requests for it."""

    def __init__(self):
        self.urls: list[str] = []

    def get(self, url, *a, **kw):
        self.urls.append(url)
        return _Resp(_zip(BUNDLE))


# ── C8: the PR bundle ────────────────────────────────────────────────────────

def test_the_benchmark_rows_from_a_kept_bundle_are_the_downloaded_ones(tmp_path):
    """The saving must not change a close: same frame, one download instead of two."""
    nse = _CountingNSE()
    downloaded = bb.nse_rows([DAY], fetch=lambda d, s=None: nb.fetch_bundle(d, session=nse),
                             sleep=lambda *_: None, log=lambda *_: None)
    assert len(nse.urls) == 1, "the control case did not reach NSE at all"
    assert not downloaded.empty and downloaded.iloc[0]["nifty50"] == 25050.0

    # What nse_collect --save-bundles keeps, from the same single download.
    folder = nc.save_bundle(tmp_path, DAY, nb.fetch_bundle(DAY, session=nse))
    assert sorted(p.name for p in folder.iterdir()) == ["Pd250926.csv", "Pr250926.txt"]
    before = len(nse.urls)

    from_disk = bb.nse_rows([DAY], fetch=bb.bundle_reader(tmp_path),
                            sleep=lambda *_: None, log=lambda *_: None)

    assert len(nse.urls) == before, (
        f"build_benchmarks asked NSE again: {nse.urls[before:]}"
    )
    pd.testing.assert_frame_equal(downloaded, from_disk)


def test_a_day_the_collector_did_not_keep_is_still_asked_for(tmp_path):
    """R2 already had it, or NSE had none: the benchmark file must not lose a session."""
    nse = _CountingNSE()
    reader = bb.bundle_reader(tmp_path, fetch=lambda d, s=None: nb.fetch_bundle(d, session=nse))

    frame = bb.nse_rows([DAY], fetch=reader, sleep=lambda *_: None, log=lambda *_: None)

    assert len(nse.urls) == 1
    assert frame.iloc[0]["nifty500"] == 23077.70


def test_an_incomplete_kept_bundle_is_downloaded_again(tmp_path):
    """A directory without the Pd member cannot answer the question asked of it."""
    (tmp_path / DAY.isoformat()).mkdir()
    (tmp_path / DAY.isoformat() / "Pr250926.txt").write_bytes(b"press release")
    nse = _CountingNSE()
    reader = bb.bundle_reader(tmp_path, fetch=lambda d, s=None: nb.fetch_bundle(d, session=nse))

    frame = bb.nse_rows([DAY], fetch=reader, sleep=lambda *_: None, log=lambda *_: None)

    assert len(nse.urls) == 1
    assert not frame.empty


def test_the_collector_keeps_every_bundle_it_fetched_and_only_when_asked(tmp_path, monkeypatch):
    """--save-bundles is opt-in, and writes the members under their own names."""
    monkeypatch.setattr(nb, "fetch_bundle", lambda day, session=None: dict(BUNDLE))
    kept, bare = tmp_path / "kept", tmp_path / "bare"
    bare.mkdir()

    assert nc.main(["--probe", DAY.isoformat(), "--delay", "0",
                    "--save-bundles", str(kept)]) == 0
    assert nc.main(["--probe", DAY.isoformat(), "--delay", "0"]) == 0

    assert sorted(p.name for p in (kept / DAY.isoformat()).iterdir()) == [
        "Pd250926.csv", "Pr250926.txt"]
    assert list(bare.iterdir()) == []


def test_the_daily_sync_hands_the_bundles_from_the_collector_to_the_benchmarks():
    """The two steps must point at the same directory, or neither change bites."""
    doc = yaml.safe_load((WORKFLOWS / "daily_sync.yml").read_text(encoding="utf-8"))
    steps = {s.get("name"): s for s in doc["jobs"]["sync"]["steps"]}
    collect = steps["Collect the last NSE sessions"]["run"]
    bench = steps["Extend the benchmark closes"]["run"]

    assert "--save-bundles /tmp/nse-bundles" in collect
    assert "--bundles /tmp/nse-bundles" in bench
    assert "--recent 3" in collect and "--update" in bench


# ── C7: the Screener store ───────────────────────────────────────────────────

def _steps(workflow: str, job: str) -> list[dict]:
    doc = yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8"))
    return doc["jobs"][job]["steps"]


def test_the_row_guard_reads_the_copy_the_fold_step_downloaded():
    steps = {s.get("name"): s for s in _steps("screener_sync.yml", "screener")}
    fold = steps["Fold the published store into the working copy"]["run"]
    publish = steps["Publish screener history"]["run"]

    assert "--dir /tmp/screener-release" in fold
    assert 'PUBLISHED=/tmp/screener-release/screener_prices.parquet' in publish
    assert 'if [ ! -f "$PUBLISHED" ]' in publish, (
        "the guard must still download when the fold step could not"
    )
    # The guard itself is unchanged: it still compares row counts and fails.
    assert "metadata.num_rows" in publish
    assert "fewer rows than the published one" in publish


def test_nse_collect_downloads_the_store_only_when_the_release_has_new_bytes():
    steps = {s.get("name"): s for s in _steps("nse_collect.yml", "collect")}
    ident = steps["Identify the published Screener store"]
    restore = steps["Restore the Screener store"]
    fetch = steps["Fetch Screener's store to check against"]
    collect = steps["Collect and check"]

    # The cache key is the published asset's own size and upload time, so a
    # restored file can only be the file the release is serving.
    assert ".size" in ident["run"] and ".updatedAt" in ident["run"]
    assert "screener_prices.parquet" in ident["run"]
    assert restore["with"]["key"] == "${{ steps.screener_asset.outputs.key }}"
    assert restore["with"]["path"] == "screener_prices.parquet"
    assert "steps.restore_screener.outputs.cache-hit != 'true'" in fetch["if"]
    # and the check still runs on every fire, against that file
    assert "--check --screener screener_prices.parquet" in collect["run"]
    assert "cache-hit" not in str(collect.get("if", ""))
