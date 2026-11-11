"""One fetch per constituent CSV per run, and the committed copy read as what it is.

Measured on 10-11 Nov 2026 (`docs/CALL_AND_STORAGE_AUDIT.md`, TODO C5): one
`daily_sync` run made **17 requests for the 6 niftyindices constituent CSVs** --
five downloaded by `sync_official_nse_indices`, all six again by the universe
load seconds later in the same process, all six a third time by
`precompute_systems` -- and the app downloaded all six on every cold start
(4.2 s of a 9.1 s `load_all_data`, TODO A2) and again every hour, even though
`data/indices/*.csv`, which that same job writes and commits, already held the
bytes.

These tests count requests on the real code path with niftyindices answered
locally (the agent proxy blocks the host). They are written so that fetching
NOTHING fails them too: every count is asserted against the number of distinct
URLs, and the universe the committed copy yields is compared with the universe a
live download yields, frame for frame.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timedelta

import pandas as pd
import pytest
import requests

from src.loaders import indices_loader as il

REPO_INDICES = os.path.join(
    os.path.abspath(os.path.join(__file__, "../..")), "data", "indices"
)


class _Resp:
    def __init__(self, body: bytes):
        self.status_code = 200
        self.content = body


@pytest.fixture
def counted(tmp_path, monkeypatch):
    """Serve each constituent URL from the committed CSV; count the requests.

    Every write is redirected into tmp_path: a test must not be able to write
    the data the application ships (see
    tests/test_failed_sync_is_not_reported_as_a_sync.py, which learnt that the
    hard way).
    """
    calls: dict[str, int] = {}

    def fake_request(self, method, url, *a, **kw):  # noqa: ANN001
        assert "niftyindices.com" in url, f"unexpected host: {url}"
        calls[url] = calls.get(url, 0) + 1
        with open(os.path.join(REPO_INDICES, url.rsplit("/", 1)[-1]), "rb") as fh:
            return _Resp(fh.read())

    monkeypatch.setattr(requests.sessions.Session, "request", fake_request)

    idx_dir = tmp_path / "indices"
    shutil.copytree(REPO_INDICES, idx_dir)
    monkeypatch.setattr(
        il,
        "INDICES_LOCAL",
        {name: str(idx_dir / os.path.basename(p)) for name, p in il.INDICES_LOCAL.items()},
    )
    monkeypatch.setattr(il, "SYNC_META_FILE", str(tmp_path / "indices_sync_meta.json"))
    monkeypatch.setattr(il, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(il.time, "sleep", lambda *_: None)
    il.reset_download_memo()
    yield calls, idx_dir, tmp_path
    il.reset_download_memo()


def _seed_meta(tmp_path, hours_old: float | None, indices=None) -> None:
    """The metadata a sync committed `hours_old` hours ago (None: no stamps)."""
    meta: dict = {"last_synced": "earlier", "total_stocks": 754, "indices": {}}
    if hours_old is not None:
        when = (datetime.now() - timedelta(hours=hours_old)).isoformat()
        meta[il.LOCAL_FETCH_KEY] = {k: when for k in (indices or il.INDICES_URLS)}
    (tmp_path / "indices_sync_meta.json").write_text(json.dumps(meta))


def _universe(prefer_local: bool = True) -> pd.DataFrame:
    return il._fetch_indices_impl(["NIFTY TOTAL MARKET"], prefer_local=prefer_local)


# ── one run of the daily sync ────────────────────────────────────────────────

def test_one_daily_sync_run_fetches_each_list_exactly_once(counted):
    """17 requests for 6 files, measured 10 Nov; 6 for 6 now."""
    calls, _idx, tmp_path = counted
    _seed_meta(tmp_path, hours_old=23.5)  # what the PREVIOUS run committed

    # Step 1 and step 2 of scripts/sync_data.run_daily_sync(), in order.
    il.sync_official_nse_indices(force=True)
    after_step1 = sum(calls.values())
    step2 = _universe(prefer_local=False)
    after_step2 = sum(calls.values())

    # scripts/precompute_systems.py: a separate process, so no memo.
    il.reset_download_memo()
    step3 = _universe()

    assert after_step1 == 5, "step 1 still downloads the five lists it maintains"
    assert after_step2 - after_step1 == 1, (
        "step 2 must download only NIFTY TOTAL MARKET, the one list step 1 "
        f"leaves alone; it made {after_step2 - after_step1} requests"
    )
    assert sum(calls.values()) == len(il.INDICES_URLS) == 6
    assert set(calls) == set(il.INDICES_URLS.values())
    assert max(calls.values()) == 1, f"a URL was fetched twice: {calls}"
    # and the universe is the same one at every stage
    assert len(step2) > 700
    pd.testing.assert_frame_equal(step2, step3)


def test_the_universe_from_the_committed_copy_equals_the_downloaded_one(counted):
    """The saving must not change a single row of what is loaded."""
    calls, _idx, tmp_path = counted
    _seed_meta(tmp_path, hours_old=None)
    downloaded = _universe()
    assert sum(calls.values()) == 6, "with no stamp the lists are downloaded"

    calls.clear()
    il.reset_download_memo()
    _seed_meta(tmp_path, hours_old=2)
    from_disk = _universe()

    assert calls == {}, f"the committed copy was not used: {calls}"
    assert not from_disk.empty
    pd.testing.assert_frame_equal(downloaded, from_disk)


# ── when the committed copy is NOT used ──────────────────────────────────────

def test_a_stale_sync_is_downloaded_again(counted):
    """Two days without a successful sync and every reader asks NSE again."""
    calls, _idx, tmp_path = counted
    _seed_meta(tmp_path, hours_old=50)

    assert len(_universe()) > 700
    assert sum(calls.values()) == len(il.INDICES_URLS)


def test_an_unstamped_checkout_downloads_exactly_as_before(counted):
    """Until a sync writes the stamps, nothing changes."""
    calls, _idx, tmp_path = counted
    _seed_meta(tmp_path, hours_old=None)

    assert len(_universe()) > 700
    assert sum(calls.values()) == len(il.INDICES_URLS)


def test_a_missing_committed_file_is_downloaded_even_when_stamped(counted):
    calls, idx_dir, tmp_path = counted
    _seed_meta(tmp_path, hours_old=1)
    os.remove(idx_dir / "ind_nifty50list.csv")

    _universe()

    assert list(calls) == [il.INDICES_URLS["NIFTY 50"]], (
        f"only the absent list should have been downloaded: {calls}"
    )


def test_the_job_that_refreshes_the_lists_never_reads_them(counted):
    """prefer_local=False is what keeps a committed copy from freezing."""
    calls, _idx, tmp_path = counted
    _seed_meta(tmp_path, hours_old=0.1)  # written minutes ago

    _universe(prefer_local=False)

    assert sum(calls.values()) == len(il.INDICES_URLS)


# ── the per-process memo ─────────────────────────────────────────────────────

def test_a_forced_sync_always_really_asks(counted):
    """The Configuration tab's "sync now" must not be served from the memo."""
    calls, _idx, tmp_path = counted
    _seed_meta(tmp_path, hours_old=None)
    _universe()  # fills the memo with all six
    assert sum(calls.values()) == 6
    calls.clear()

    res = il.sync_official_nse_indices(force=True)

    assert sum(calls.values()) == 5, (
        f"a forced sync reused downloaded bytes instead of asking: {calls}"
    )
    assert res["last_attempt_fetched"] == 5 and res["last_attempt_ok"]


def test_the_memo_does_not_outlive_its_window(counted, monkeypatch):
    """A warm app asking again an hour later must really ask."""
    calls, _idx, tmp_path = counted
    _seed_meta(tmp_path, hours_old=None)
    monkeypatch.setenv("INDICES_DOWNLOAD_MEMO_S", "0")

    _universe(prefer_local=False)
    assert sum(calls.values()) == 6
    _universe(prefer_local=False)

    assert sum(calls.values()) == 12, (
        f"the second load was served from an expired memo: {calls}"
    )


def test_the_memo_is_used_within_its_window(counted):
    calls, _idx, tmp_path = counted
    _seed_meta(tmp_path, hours_old=None)

    first = _universe(prefer_local=False)
    assert sum(calls.values()) == 6
    second = _universe(prefer_local=False)

    assert sum(calls.values()) == 6, f"the same bytes were downloaded again: {calls}"
    pd.testing.assert_frame_equal(first, second)


# ── the stamp itself ─────────────────────────────────────────────────────────

def test_a_sync_stamps_the_lists_it_wrote(counted):
    calls, _idx, tmp_path = counted
    _seed_meta(tmp_path, hours_old=None)

    il.sync_official_nse_indices(force=True)

    meta = json.loads((tmp_path / "indices_sync_meta.json").read_text())
    stamped = set(meta[il.LOCAL_FETCH_KEY])
    assert stamped == set(il.INDICES_URLS) - {"NIFTY TOTAL MARKET"}
    for name in stamped:
        assert il.committed_copy_age_s(name, meta) < 60


def test_a_download_in_a_reader_stamps_the_copy_it_persisted(counted):
    """So precompute_systems, minutes later, reads the file instead of NSE."""
    calls, _idx, tmp_path = counted
    _seed_meta(tmp_path, hours_old=None)

    _universe()

    meta = json.loads((tmp_path / "indices_sync_meta.json").read_text())
    assert set(meta[il.LOCAL_FETCH_KEY]) == set(il.INDICES_URLS)


def test_stamping_keeps_the_figures_the_configuration_tab_shows(counted, tmp_path):
    """The stamp is additive: it must not disturb last_synced or total_stocks."""
    calls, _idx, tmp_path = counted
    (tmp_path / "indices_sync_meta.json").write_text(json.dumps({
        "last_synced": "28 Aug 2026, 01:34",
        "timestamp": "2026-08-28T01:34:24",
        "total_stocks": 752,
        "indices": {"NIFTY 50": {"count": 50, "status": "Updated"}},
    }))

    _universe()

    meta = json.loads((tmp_path / "indices_sync_meta.json").read_text())
    assert meta["last_synced"] == "28 Aug 2026, 01:34"
    assert meta["total_stocks"] == 752
    assert meta["indices"] == {"NIFTY 50": {"count": 50, "status": "Updated"}}
    assert meta[il.LOCAL_FETCH_KEY]
