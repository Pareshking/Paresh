"""The SS store: exact paise, quality gate, refresh triggers, upsert, filters."""
from datetime import date

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

from src.loaders import ss_prices as ss


@pytest.fixture(autouse=True)
def _endpoint(monkeypatch):
    """The real address is a secret; fetch tests use fake sessions anyway."""
    monkeypatch.setenv(ss.BASE_URL_ENV, "https://example.invalid/api")


def test_no_endpoint_configured_is_a_clear_error(monkeypatch):
    monkeypatch.delenv(ss.BASE_URL_ENV, raising=False)
    with pytest.raises(ss.SSError, match="SS_BASE_URL"):
        ss.base_url()


def test_the_repository_never_names_the_source():
    """Owner, 2026-10-02: the source is "SS" everywhere in this public repository."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    secret = "stock" + "scans"
    hits = [str(p.relative_to(root)) for p in root.rglob("*")
            if p.is_file() and p.suffix in {".py", ".md", ".yml", ".csv", ".json", ".toml"}
            and ".git" not in p.parts and "data_cache" not in p.parts
            and p.name != "sansera_research_packet.py"   # a cited transcript URL (#281)
            and secret in p.read_text(encoding="utf-8", errors="ignore").lower()]
    assert hits == []


def _rows(symbol, closes, start="2026-09-01"):
    days = pd.bdate_range(start, periods=len(closes))
    return pd.DataFrame({
        "date": [d.date() for d in days], "symbol": symbol,
        "open": closes, "high": [c * 1.01 for c in closes], "low": [c * 0.99 for c in closes],
        "close": closes, "volume": [1000.0] * len(closes),
    })[ss.COLUMNS]


def _round2(frame):
    for c in ss.PRICE_COLUMNS:
        frame[c] = frame[c].round(2)
    return frame


# ── Paise ────────────────────────────────────────────────────────────────────

def test_paise_round_trip_is_exact():
    rupees = _round2(_rows("A", [0.05, 1.10, 772.80, 162005.85, 21857.75]))
    back = ss.to_rupees(ss.to_paise(rupees))
    for c in ss.PRICE_COLUMNS:
        assert (back[c].to_numpy() == rupees[c].to_numpy()).all()
    assert ss.to_paise(rupees)["close"].dtype == np.int32


def test_a_price_finer_than_a_paisa_is_refused():
    with pytest.raises(ss.SSError, match="finer than a paisa"):
        ss.to_paise(_rows("A", [100.001]))


def test_volume_beyond_int32_survives():
    rows = _round2(_rows("A", [10.0]))
    rows["volume"] = 2_179_434_800.0          # measured: larger than int32 allows
    assert ss.to_paise(rows)["volume"].iloc[0] == 2_179_434_800


# ── Quality gate ─────────────────────────────────────────────────────────────

def test_a_clean_page_passes():
    assert ss.quality_problems(_round2(_rows("A", [10.0, 11.0, 12.0]))) == []


@pytest.mark.parametrize("mutate,expect", [
    (lambda f: f.assign(close=[-1.0, 11.0]), "non-positive"),
    (lambda f: f.assign(volume=[-5.0, 1.0]), "negative volume"),
    (lambda f: f.assign(high=[1.0, 11.0 * 1.01]), "high/low"),
    (lambda f: pd.concat([f, f.iloc[[0]]]), "duplicate"),
    (lambda f: f.assign(open=[np.nan, 11.0]), "non-finite"),
])
def test_a_bad_page_is_refused(mutate, expect):
    problems = ss.quality_problems(mutate(_round2(_rows("A", [10.0, 11.0]))))
    assert any(expect in p for p in problems)


# ── Full-refresh triggers ────────────────────────────────────────────────────

def test_matching_history_needs_no_refresh():
    rows = _rows("A", [100.0, 101.0, 102.0])
    assert ss.needs_full_refresh(rows, rows) is None


def test_restated_history_triggers_a_refresh():
    stored = _rows("A", [100.0, 101.0, 102.0])
    fresh = _rows("A", [50.0, 50.5, 51.0])          # a 1:2 split, now adjusted back
    assert "restated" in ss.needs_full_refresh(stored, fresh)


def test_a_session_beyond_twenty_percent_triggers_a_refresh():
    fresh = _rows("A", [100.0, 100.0, 50.0])        # not restated yet
    assert "moved -50.0%" in ss.needs_full_refresh(pd.DataFrame(columns=ss.COLUMNS), fresh)


def test_a_move_inside_the_limit_does_not():
    assert ss.needs_full_refresh(pd.DataFrame(columns=ss.COLUMNS), _rows("A", [100.0, 119.0])) is None


# ── Upsert ───────────────────────────────────────────────────────────────────

def test_upsert_is_idempotent():
    rows = ss.to_paise(_round2(_rows("A", [10.0, 11.0])))
    once = ss.upsert(pd.DataFrame(columns=ss.COLUMNS), rows)
    twice = ss.upsert(once, rows)
    assert len(twice) == 2 and not twice.duplicated(["symbol", "date"]).any()


def test_upsert_new_rows_win_and_a_replaced_symbol_drops_its_old_rows():
    old = ss.to_paise(_round2(_rows("A", [10.0, 11.0, 12.0])))
    other = ss.to_paise(_round2(_rows("B", [5.0])))
    store = ss.upsert(old, other)
    new = ss.to_paise(_round2(_rows("A", [20.0], start="2026-09-02")))
    out = ss.upsert(store, new, replace_symbols=["A"])
    assert list(out[out.symbol == "A"]["close"]) == [2000]
    assert list(out[out.symbol == "B"]["close"]) == [500]


# ── Store files ──────────────────────────────────────────────────────────────

def _store(tmp_path):
    a = _round2(_rows("A", [10.0, 11.0, 12.0], start="2025-12-30"))
    b = _round2(_rows("B", [20.0, 21.0], start="2026-01-05"))
    frame = ss.to_paise(pd.concat([a, b], ignore_index=True))
    sizes = ss.write_store(frame, tmp_path)
    return frame, sizes


def test_one_file_per_year_with_the_canonical_schema(tmp_path):
    _, sizes = _store(tmp_path)
    assert set(sizes) == {2025, 2026}
    schema = pq.read_schema(tmp_path / "prices_2026.parquet")
    assert str(schema.field("close").type) == "int32"
    assert str(schema.field("volume").type) == "int64"
    assert "dictionary" in str(schema.field("symbol").type)
    assert not list(tmp_path.glob("*.tmp"))


def test_read_filters_by_symbol_date_and_column(tmp_path):
    _store(tmp_path)
    got = ss.read_store(tmp_path, symbols=["A"], start="2026-01-01", columns=["close"])
    assert set(got.columns) == {"date", "symbol", "close"}
    assert set(got.symbol) == {"A"}
    assert all(d >= date(2026, 1, 1) for d in got["date"])


def test_an_empty_result_is_an_empty_frame(tmp_path):
    _store(tmp_path)
    assert ss.read_store(tmp_path, symbols=["NOPE"]).empty
    assert ss.read_store(tmp_path / "absent").empty


# ── Fetching ─────────────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, status, payload=None):
        self.status_code, self._payload = status, payload

    def json(self):
        return self._payload


class _Session:
    def __init__(self, pages):
        self.pages, self.calls = list(pages), []

    def get(self, url, params=None, **kw):
        self.calls.append(dict(params or {}))
        return self.pages.pop(0)


def _payload(symbol, rows, more):
    return {"companyId": f"NSE:{symbol}", "exchange": "NSE", "tf": "1D",
            "hasMore": more, "prices": rows}


def test_blocked_stops_the_run():
    with pytest.raises(ss.SSBlocked):
        ss.fetch_page("A", session=_Session([_Resp(429)]))


def test_an_answer_for_another_symbol_is_refused():
    with pytest.raises(ss.SSError, match="answer is for"):
        ss.fetch_page("A", session=_Session([_Resp(200, _payload("B", [["2026-09-01", 1, 1, 1, 1, 1]], False))]))


def test_full_history_follows_the_cursor_to_listing():
    page2 = _payload("A", [["2026-09-01", 1, 1, 1, 1, 10], ["2026-09-02", 2, 2, 2, 2, 10]], True)
    page1 = _payload("A", [["2026-08-28", 1, 1, 1, 1, 10], ["2026-08-31", 1, 1, 1, 1, 10]], False)
    session = _Session([_Resp(200, page2), _Resp(200, page1)])
    rows, more = ss.fetch_history("A", None, session=session, sleep=lambda s: None)
    assert len(rows) == 4 and more is False
    assert session.calls[1]["before"] == "2026-09-01"


# ── The batch stops on trouble with the host ─────────────────────────────────

def _run(monkeypatch, tmp_path, answers, symbols):
    import scripts.sync_ss as sync

    calls = []

    def fake_history(symbol, pages, **kw):
        calls.append(symbol)
        answer = answers(symbol, len(calls))
        if isinstance(answer, Exception):
            raise answer
        return answer, False

    monkeypatch.setattr(sync.ss, "fetch_history", fake_history)
    monkeypatch.setattr(sync.time, "sleep", lambda s: None)
    sync.main(["--symbols", *symbols, "--out", str(tmp_path), "--delay", "0"])
    return calls


def test_consecutive_host_failures_stop_the_run(monkeypatch, tmp_path):
    symbols = [f"S{i:02d}" for i in range(30)]
    calls = _run(monkeypatch, tmp_path,
                 lambda s, n: ss.SSError(f"HTTP 503 for {s}"), symbols)
    # five, a pause, five more, then stop -- not thirty requests into a wall
    assert len(calls) == 2 * 5


def test_unknown_tickers_do_not_trip_the_breaker(monkeypatch, tmp_path):
    good = _round2(_rows("X", [10.0, 11.0]))
    symbols = [f"S{i:02d}" for i in range(12)]
    calls = _run(monkeypatch, tmp_path,
                 lambda s, n: (ss.SSError(f"{s}: no prices") if n <= 10
                               else good.assign(symbol=s)), symbols)
    assert len(calls) == 12
    assert set(ss.read_store(tmp_path).symbol) == {"S10", "S11"}


def test_a_block_stops_at_once_and_keeps_what_was_fetched(monkeypatch, tmp_path):
    good = _round2(_rows("X", [10.0, 11.0]))
    calls = _run(monkeypatch, tmp_path,
                 lambda s, n: ss.SSBlocked("HTTP 403") if n == 3 else good.assign(symbol=s),
                 ["A", "B", "C", "D", "E"])
    assert calls == ["A", "B", "C"]
    assert set(ss.read_store(tmp_path).symbol) == {"A", "B"}


def test_the_nightly_round_skips_what_tonight_already_updated():
    from datetime import datetime, timezone

    from scripts.sync_ss import fetched_within

    now = datetime(2026, 10, 2, 20, 0, tzinfo=timezone.utc)
    assert fetched_within({"fetched_at": "2026-10-02T17:30:00+00:00"}, 12, now)
    assert not fetched_within({"fetched_at": "2026-10-01T17:30:00+00:00"}, 12, now)
    assert not fetched_within(None, 12, now) and not fetched_within({}, 12, now)


def test_history_mode_takes_only_stocks_held_without_their_whole_history(monkeypatch, tmp_path):
    import json

    import scripts.sync_ss as sync

    (tmp_path / "manifest.json").write_text(json.dumps({"failed": {}, "symbols": {
        "OLD": {"full_history": False, "more_available": True},
        "NEW": {"full_history": True, "more_available": False},
    }}))
    asked = []

    def fake_history(symbol, pages, **kw):
        asked.append((symbol, pages))
        return _round2(_rows(symbol, [10.0, 11.0])), False

    monkeypatch.setattr(sync.ss, "fetch_history", fake_history)
    monkeypatch.setattr(sync.time, "sleep", lambda s: None)
    sync.main(["--symbols", "OLD", "NEW", "NEVER", "--needs-history",
               "--out", str(tmp_path), "--delay", "0"])
    # back to listing (pages=None), and only the stock held on page 1
    assert asked == [("OLD", None)]
    assert json.loads((tmp_path / "manifest.json").read_text())["symbols"]["OLD"]["full_history"]
