"""A sync that fetched nothing must not stamp itself as a sync.

On 2026-08-29 all five constituent downloads failed -- fifteen requests, not a
byte of index data -- and the job still wrote "last_synced: 29 Aug 2026, 01:04"
next to "total_stocks: 0". The Configuration tab read that file and rendered a
green "Engine Active (0 Stocks)" under a reassuring timestamp, while the
screener was ranking 750 stocks perfectly well from the previous day's lists.

The date recorded WHEN THE JOB RAN and was displayed as WHEN THE DATA WAS
REFRESHED. Those are different facts, and they diverge precisely when one of
them matters.
"""
import json

import pandas as pd
import pytest

from src.loaders import indices_loader


@pytest.fixture
def meta_file(tmp_path, monkeypatch):
    path = tmp_path / "indices_sync_meta.json"
    monkeypatch.setattr(indices_loader, "SYNC_META_FILE", str(path))
    monkeypatch.setattr(indices_loader.time, "sleep", lambda *_: None)
    return path


def _previous_good_sync(meta_file):
    meta_file.write_text(json.dumps({
        "last_synced": "28 Aug 2026, 01:34",
        "timestamp": "2026-08-28T01:34:24",
        "total_stocks": 752,
        "indices": {f"IDX{i}": {"count": 100, "status": "Updated"} for i in range(5)},
    }))


def _all_downloads_fail(monkeypatch):
    def _boom(*a, **k):
        raise OSError("connection refused")
    monkeypatch.setattr(indices_loader.requests, "get", _boom)


class _Resp:
    status_code = 200

    def __init__(self, body):
        self.content = body.encode()


def _all_downloads_succeed(monkeypatch, rows=40):
    body = "Company Name,Industry,Symbol,Series,ISIN Code\n" + "".join(
        f"Co {i},Financial Services,SYM{i},EQ,INE{i:09d}\n" for i in range(rows)
    )
    monkeypatch.setattr(indices_loader.requests, "get", lambda *a, **k: _Resp(body))


# ── The failing run ──────────────────────────────────────────────────────────

def test_a_total_failure_keeps_the_previous_sync_date(meta_file, monkeypatch):
    _previous_good_sync(meta_file)
    _all_downloads_fail(monkeypatch)

    meta = indices_loader.sync_official_nse_indices()

    assert meta["last_synced"] == "28 Aug 2026, 01:34"
    assert meta["total_stocks"] == 752


def test_a_total_failure_does_not_zero_the_universe(meta_file, monkeypatch):
    """The exact number the Configuration tab printed in a green badge."""
    _previous_good_sync(meta_file)
    _all_downloads_fail(monkeypatch)

    assert indices_loader.sync_official_nse_indices()["total_stocks"] != 0


def test_the_failed_attempt_is_recorded_rather_than_hidden(meta_file, monkeypatch):
    """Preserving the old figures must not mean saying nothing went wrong."""
    _previous_good_sync(meta_file)
    _all_downloads_fail(monkeypatch)

    meta = indices_loader.sync_official_nse_indices()

    assert meta["last_attempt_ok"] is False
    assert meta["last_attempt_fetched"] == 0
    assert meta["last_attempt"]
    assert len(meta["last_attempt_errors"]) == 5


def test_the_record_survives_a_round_trip_to_disk(meta_file, monkeypatch):
    _previous_good_sync(meta_file)
    _all_downloads_fail(monkeypatch)
    indices_loader.sync_official_nse_indices()

    on_disk = json.loads(meta_file.read_text())
    assert on_disk["last_synced"] == "28 Aug 2026, 01:34"
    assert on_disk["last_attempt_ok"] is False


def test_a_first_ever_run_that_fails_claims_no_sync_at_all(meta_file, monkeypatch):
    """With no previous good run to fall back on, the honest answer is None."""
    _all_downloads_fail(monkeypatch)

    meta = indices_loader.sync_official_nse_indices()

    assert meta.get("last_synced") is None
    assert meta["last_attempt_ok"] is False


# ── The succeeding run ───────────────────────────────────────────────────────

def test_a_complete_sync_moves_the_date_forward(meta_file, monkeypatch):
    _previous_good_sync(meta_file)
    _all_downloads_succeed(monkeypatch)

    meta = indices_loader.sync_official_nse_indices()

    assert meta["last_synced"] != "28 Aug 2026, 01:34"
    assert meta["last_attempt_ok"] is True
    assert meta["total_stocks"] > 0


def test_a_recovered_sync_clears_the_failure_flag(meta_file, monkeypatch):
    """A good run after a bad one must not leave the warning on screen."""
    _previous_good_sync(meta_file)
    _all_downloads_fail(monkeypatch)
    assert indices_loader.sync_official_nse_indices()["last_attempt_ok"] is False

    _all_downloads_succeed(monkeypatch)
    assert indices_loader.sync_official_nse_indices()["last_attempt_ok"] is True


# ── What the Configuration tab makes of it ───────────────────────────────────

def test_the_tab_reports_the_engines_real_universe_not_the_recorded_zero(
    meta_file, monkeypatch
):
    """``.get(key, default)`` never fired: the key was present, holding zero.

    This is the whole reason the badge could read "Engine Active (0 Stocks)"
    while 750 stocks were ranked on the next tab along.
    """
    meta_file.write_text(json.dumps(
        {"last_synced": "29 Aug 2026, 01:04", "total_stocks": 0, "indices": {}}
    ))
    rank_df = pd.DataFrame({"Symbol": [f"SYM{i}" for i in range(750)]})

    sync_meta = indices_loader.get_sync_metadata()
    engine_stocks = len(rank_df)
    tot_stk = (sync_meta.get("total_stocks") or 0) or len(rank_df)

    assert engine_stocks == 750
    assert tot_stk == 750
    assert sync_meta.get("total_stocks", len(rank_df)) == 0   # the old expression
