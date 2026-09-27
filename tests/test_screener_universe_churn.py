"""Regression coverage for current-universe-driven Screener acquisition."""

from scripts.sync_screener import current_universe_delta


def test_new_symbols_are_forced_into_acquisition_set():
    current = ["AAA", "BBB", "HEGAM", *[f"NEW{i:02d}" for i in range(10)]]
    stored = ["AAA", "BBB", "HEG", *[f"OLD{i:02d}" for i in range(10)]]

    new_current, exited = current_universe_delta(current, stored)

    assert new_current == ["HEGAM", *[f"NEW{i:02d}" for i in range(10)]]
    assert exited == ["HEG", *[f"OLD{i:02d}" for i in range(10)]]


def test_index_reclassification_does_not_look_like_a_new_security():
    # The index bucket is not part of identity. A SMALL250 -> MID150 move keeps
    # the same symbol and therefore must not trigger another history download.
    current = ["AAA", "MOVED"]
    stored = ["AAA", "MOVED"]

    new_current, exited = current_universe_delta(current, stored)

    assert new_current == []
    assert exited == []


def test_exited_symbols_are_not_current_acquisition_targets():
    current = ["AAA"]
    stored = ["AAA", "EXIT1", "EXIT2"]

    new_current, exited = current_universe_delta(current, stored)

    assert new_current == []
    assert exited == ["EXIT1", "EXIT2"]


def test_dummy_symbols_are_not_added_by_the_delta_when_loader_has_filtered_them():
    # sync_screener consumes the already filtered authoritative universe. This
    # fixture mirrors that contract: DUMMY placeholders must never be present
    # in current_symbols, even when an old store still contains one.
    current = ["AAA", "BBB"]
    stored = ["AAA", "BBB", "DUMMYHEG"]

    new_current, exited = current_universe_delta(current, stored)

    assert new_current == []
    assert exited == ["DUMMYHEG"]


def _frame(symbols):
    import pandas as pd

    idx = pd.DatetimeIndex(["2026-09-21"])
    columns = pd.MultiIndex.from_tuples(
        [(symbol, field) for symbol in symbols for field in ("Close", "Volume")],
        names=["Symbol", "Field"],
    )
    values = []
    for _ in idx:
        row = []
        for symbol in symbols:
            row.extend([100.0, 1000.0])
        values.append(row)
    return pd.DataFrame(values, index=idx, columns=columns)


def test_run_forces_new_symbols_before_regular_sweep(monkeypatch):
    import scripts.sync_screener as sync

    calls = []
    monkeypatch.setattr(
        sync,
        "fetch_indices_data",
        lambda selected: __import__("pandas").DataFrame({"Symbol": ["AAA", "HEGAM"]}),
    )
    monkeypatch.setattr(sync.sl, "load_store", lambda: _frame(["AAA"]))
    monkeypatch.setattr(sync.sl, "load_ids", lambda: {})
    monkeypatch.setattr(sync.sl, "save_ids", lambda ids: None)
    monkeypatch.setattr(sync, "_drop_unsettled", lambda frame: (frame, []))
    monkeypatch.setattr(sync, "session_is_complete", lambda date: True)
    monkeypatch.setattr(sync, "_deep_check_due", lambda: False)
    monkeypatch.setattr(sync, "EXTRA_LIST", "/nonexistent/ind_nanocap_list.csv")

    def fake_fetch(symbols, **kwargs):
        calls.append((list(symbols), kwargs.get("days")))
        return _frame(symbols), kwargs["ids"], []

    monkeypatch.setattr(sync.sl, "fetch_universe", fake_fetch)
    captured = {}

    def fake_merge(frame, **kwargs):
        captured["symbols"] = sorted(sync.sl.closes(frame).columns.tolist())
        return frame, 1, 0

    monkeypatch.setattr(sync.sl, "merge_into_store", fake_merge)

    assert sync.run() == 0
    assert calls == [(["HEGAM"], 3650), (["AAA"], 365)]
    assert captured["symbols"] == ["AAA", "HEGAM"]


def test_extra_universe_is_fetched_after_the_750_and_never_gates_the_night(monkeypatch, tmp_path):
    import pandas as pd

    import scripts.sync_screener as sync

    extra = tmp_path / "ind_nanocap_list.csv"
    pd.DataFrame({"Symbol": ["AAA", "XOLD", "XNEW", "XGONE", "DUMMYX"]}).to_csv(extra, index=False)
    monkeypatch.setattr(sync, "EXTRA_LIST", str(extra))
    monkeypatch.setattr(sync, "fetch_indices_data",
                        lambda selected: pd.DataFrame({"Symbol": ["AAA"]}))
    monkeypatch.setattr(sync.sl, "load_store", lambda: _frame(["AAA", "XOLD", "XGONE"]))
    monkeypatch.setattr(sync.sl, "load_ids", lambda: {})
    monkeypatch.setattr(sync.sl, "save_ids", lambda ids: None)
    monkeypatch.setattr(sync, "_drop_unsettled", lambda frame: (frame, []))
    monkeypatch.setattr(sync, "_deep_check_due", lambda: False)
    calls = []

    def fake_fetch(symbols, **kwargs):
        calls.append((list(symbols), kwargs.get("days")))
        served = [s for s in symbols if s != "XGONE"]      # Screener lacks one
        return _frame(served), kwargs["ids"], [s for s in symbols if s == "XGONE"]

    monkeypatch.setattr(sync.sl, "fetch_universe", fake_fetch)
    captured = {}

    def fake_merge(frame, **kwargs):
        captured["symbols"] = sorted(sync.sl.closes(frame).columns.tolist())
        return _frame(["AAA", "XOLD", "XNEW", "XGONE"]), 1, 0

    monkeypatch.setattr(sync.sl, "merge_into_store", fake_merge)

    assert sync.run() == 0                   # XGONE unserved: the night still succeeds
    # The 750 first; then new extras with full history, then the rest.
    assert calls == [(["AAA"], 365), (["XNEW"], 3650), (["XGONE", "XOLD"], 365)]
    assert captured["symbols"] == ["AAA", "XNEW", "XOLD"]
    assert sync.extra_symbols(["AAA"], str(extra)) == ["XGONE", "XNEW", "XOLD"]


def test_the_pause_adds_jitter_only_when_pacing(monkeypatch):
    from src.loaders import screener_loader as sl

    slept = []
    sl._pause(0, sleep=slept.append)
    sl._pause(1.2, sleep=slept.append)
    assert slept[0] == 0 and 1.2 <= slept[1] <= 1.2 + sl.SCREENER_JITTER_S
