"""The screener store has to GROW, because its window slides.

Screener serves daily bars for about a year and weekly beyond that, and there
is no parameter that changes it (measured: 248 points at days=365, 522 across
ten years, 1121 across twenty). So the only way this source ever has more than
a year of daily history is by keeping what it saw last night. A merge that
replaces instead of accumulating turns the store into a rolling window that
never gets any deeper, and the failure is invisible -- the file looks healthy
at 248 rows forever.

The Yahoo cache already made the neighbouring mistake once, taking whole vendor
rows on a duplicated date and losing 572 closes across 337 symbols. Same shape,
so the same cell-level merge, and these tests hold it there.

Nothing here touches the network.
"""

import json

import pandas as pd
import pytest

from src.loaders import screener_loader as sl


class _Resp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def _chart(dates, closes, volumes=None):
    ds = [{"metric": "Price", "values": [[d, str(c)] for d, c in zip(dates, closes)]}]
    if volumes is not None:
        ds.append({"metric": "Volume", "values": [[d, str(v)] for d, v in zip(dates, volumes)]})
    return {"datasets": ds}


class _Session:
    """Serves a canned page and chart per symbol, and can refuse on demand."""

    def __init__(self, charts, ids=None, refuse_after=None, status=429):
        self.charts, self.ids = charts, ids or {}
        self.refuse_after, self.status = refuse_after, status
        self.calls = 0

    def get(self, url, **_):
        self.calls += 1
        if self.refuse_after is not None and self.calls > self.refuse_after:
            return _Resp(status=self.status)
        if "/company/" in url and "/api/" not in url:
            sym = url.rstrip("/").rsplit("/", 1)[-1]
            cid = self.ids.get(sym)
            return _Resp(text=f'<a href="/api/company/{cid}/add/">' if cid else "<html/>")
        cid = url.split("/api/company/")[1].split("/")[0]
        payload = self.charts.get(cid)
        return _Resp(payload=payload) if payload else _Resp(status=404)


# ── Parsing ──────────────────────────────────────────────────────────────────

def test_a_chart_becomes_close_and_volume():
    s = _Session({"7": _chart(["2026-09-16", "2026-09-17"], [100.0, 101.5], [5000, 6000])})
    close, vol = sl.fetch_series("7", s)
    assert close.tolist() == [100.0, 101.5]
    assert vol.tolist() == [5000.0, 6000.0]
    assert list(close.index) == [pd.Timestamp("2026-09-16"), pd.Timestamp("2026-09-17")]


def test_a_chart_without_volume_still_yields_closes():
    """Volume is a separate dataset and may simply not be there."""
    s = _Session({"7": _chart(["2026-09-17"], [101.5])})
    close, vol = sl.fetch_series("7", s)
    assert close.tolist() == [101.5]
    assert len(vol) == 1 and pd.isna(vol.iloc[0])


def test_the_frame_never_pretends_to_have_a_high():
    """The silent-substitution guard.

    The engine falls back to close when high_df is absent (momentum.py sets
    self.high = self.prices), so a frame that quietly offered a close under the
    name 'High' would change the 52-week-high gate with nothing to notice. On
    the live universe that moves the within-5% gate from 22 names to 50. Asking
    this source for a high must fail loudly instead.
    """
    s = _Session({"7": _chart(["2026-09-17"], [101.5], [10])}, ids={"AAA": "7"})
    frame, _ids, _un = sl.fetch_universe(["AAA"], ids={"AAA": "7"}, delay_s=0, session=s)
    assert set(frame.columns.get_level_values(-1)) == {"Close", "Volume"}
    with pytest.raises(KeyError):
        frame.xs("High", axis=1, level=-1)


# ── Being told to stop ───────────────────────────────────────────────────────

def test_a_block_stops_the_walk_and_keeps_what_arrived(caplog):
    """A partial night is worth keeping; retrying into a block is not."""
    charts = {str(i): _chart(["2026-09-17"], [10.0 + i], [100]) for i in range(1, 6)}
    ids = {f"S{i}": str(i) for i in range(1, 6)}
    s = _Session(charts, ids=ids, refuse_after=2, status=429)

    frame, _ids, _un = sl.fetch_universe(list(ids), ids=ids, delay_s=0, session=s)
    kept = list(frame.columns.get_level_values(0).unique())
    assert kept == ["S1", "S2"], "a 429 threw away the symbols already collected"
    assert s.calls == 3, "the walk continued past the refusal"

    from src.core import startup_metrics as m
    assert str(m.snapshot()["facts"].get("screener_run_complete")) == "no"


def test_a_403_is_treated_the_same_as_a_429():
    charts = {"1": _chart(["2026-09-17"], [10.0], [1])}
    ids = {"S1": "1", "S2": "2"}
    s = _Session(charts, ids=ids, refuse_after=1, status=403)
    frame, _i, _u = sl.fetch_universe(list(ids), ids=ids, delay_s=0, session=s)
    assert list(frame.columns.get_level_values(0).unique()) == ["S1"]
    assert s.calls == 2


def test_an_unknown_symbol_does_not_stop_the_run():
    """A freshly listed name screener has never heard of is ordinary."""
    charts = {"1": _chart(["2026-09-17"], [10.0], [1])}
    s = _Session(charts, ids={"GOOD": "1"})
    frame, _ids, unresolved = sl.fetch_universe(
        ["GOOD", "NEVERHEARDOF"], ids={}, delay_s=0, session=s
    )
    assert "NEVERHEARDOF" in unresolved
    assert "GOOD" in frame.columns.get_level_values(0)


# ── Accumulation, which is the whole point ───────────────────────────────────

def _frame(dates, closes, sym="AAA"):
    idx = pd.to_datetime(dates)
    return pd.concat(
        {sym: pd.DataFrame({"Close": closes, "Volume": [1.0] * len(closes)}, index=idx)},
        axis=1,
    )


def test_the_store_keeps_history_the_window_has_slid_past(tmp_path):
    """The reason this file exists.

    Night one sees Jan and Feb. A year later the window no longer reaches Jan.
    If the merge replaced, January would be gone and the store would sit at one
    year forever, looking perfectly healthy.
    """
    p = str(tmp_path / "s.parquet")
    sl.merge_into_store(_frame(["2026-01-02", "2026-02-02"], [10.0, 11.0]), path=p)
    merged, new_rows, _ = sl.merge_into_store(_frame(["2026-02-02", "2026-03-02"], [11.0, 12.0]), path=p)

    got = sl.closes(merged)["AAA"]
    assert len(got) == 3, "the window slid and took history with it"
    assert got.loc[pd.Timestamp("2026-01-02")] == 10.0
    assert new_rows == 1


def test_a_symbol_missing_tonight_keeps_last_nights_value(tmp_path):
    """Cell level, not row level -- the Yahoo bug, in the new source."""
    p = str(tmp_path / "s.parquet")
    both = pd.concat(
        {"AAA": pd.DataFrame({"Close": [10.0], "Volume": [1.0]}, index=pd.to_datetime(["2026-09-17"])),
         "BBB": pd.DataFrame({"Close": [20.0], "Volume": [2.0]}, index=pd.to_datetime(["2026-09-17"]))},
        axis=1,
    )
    sl.merge_into_store(both, path=p)
    # tonight BBB did not come back at all
    merged, _n, preserved = sl.merge_into_store(_frame(["2026-09-17"], [10.0]), path=p)
    out = sl.closes(merged)
    assert out.loc[pd.Timestamp("2026-09-17"), "BBB"] == 20.0, (
        "a symbol absent for one night erased the value already stored"
    )
    assert preserved >= 1


def test_a_store_that_would_shrink_is_refused(tmp_path):
    """Whatever the cause, fewer cells out than in is never an improvement."""
    p = str(tmp_path / "s.parquet")
    sl.merge_into_store(_frame(["2026-09-15", "2026-09-16", "2026-09-17"], [1.0, 2.0, 3.0]), path=p)
    before = sl.load_store(p)
    blank = _frame(["2026-09-15", "2026-09-16", "2026-09-17"], [float("nan")] * 3)
    after, new_rows, _ = sl.merge_into_store(blank, path=p)
    assert len(after) == len(before)
    assert sl.closes(after)["AAA"].tolist() == [1.0, 2.0, 3.0]


def test_an_empty_night_leaves_the_store_alone(tmp_path):
    p = str(tmp_path / "s.parquet")
    sl.merge_into_store(_frame(["2026-09-17"], [10.0]), path=p)
    merged, new_rows, _ = sl.merge_into_store(pd.DataFrame(), path=p)
    assert new_rows == 0 and len(merged) == 1


def test_the_first_night_creates_the_store(tmp_path):
    p = str(tmp_path / "s.parquet")
    merged, new_rows, _ = sl.merge_into_store(_frame(["2026-09-17"], [10.0]), path=p)
    assert new_rows == 1 and len(merged) == 1


# ── The intraday trap ────────────────────────────────────────────────────────

def test_an_open_session_is_never_accumulated(monkeypatch):
    """Screener serves the RUNNING price during market hours.

    Storing it would freeze an intraday quote into the history as though it
    were a close, and nothing would ever correct it: tomorrow's response no
    longer contains today's intraday value to overwrite it with. Unlike a late
    vendor backfill, this one is permanent.
    """
    from scripts import sync_screener

    monkeypatch.setattr(
        sync_screener, "session_is_complete",
        lambda d, **k: d != pd.Timestamp("2026-09-18").date(),
    )
    frame = _frame(["2026-09-17", "2026-09-18"], [10.0, 11.0])
    kept, dropped = sync_screener._drop_unsettled(frame)
    assert dropped == ["2026-09-18"]
    assert list(pd.DatetimeIndex(kept.index).date) == [pd.Timestamp("2026-09-17").date()]


# ── The id map ───────────────────────────────────────────────────────────────

def test_ids_round_trip(tmp_path):
    p = str(tmp_path / "ids.json")
    sl.save_ids({"ABB": "27", "AAVAS": "1274569"}, path=p)
    assert sl.load_ids(p) == {"ABB": "27", "AAVAS": "1274569"}
    assert "ids" in json.loads(open(p).read())


def test_an_unreadable_id_map_just_means_re_resolving(tmp_path):
    bad = tmp_path / "ids.json"
    bad.write_text("{not json")
    assert sl.load_ids(str(bad)) == {}


# ── The all-time-high snapshot is read three times per engine build ──────────
#
# ath_series once and ath_date_series twice, at each of the two ATH sites in
# momentum.py, and every call re-parsed the same 750-row CSV. Flagged on the
# first day of this work and left open long enough that a later change added
# the third read.

def test_the_snapshot_is_read_from_disk_once(tmp_path, monkeypatch):
    import pandas as pd
    from src.loaders import ath_loader as al

    path = str(tmp_path / "ath.csv")
    pd.DataFrame({"Symbol": ["A", "B"], "ATH": [1.0, 2.0],
                  "ATHDate": ["2026-01-01"] * 2, "AsOf": ["2026-01-01"] * 2}).to_csv(path, index=False)
    al.clear_snapshot_cache()

    reads = []
    real = pd.read_csv
    monkeypatch.setattr(pd, "read_csv", lambda *a, **k: reads.append(1) or real(*a, **k))

    for _ in range(3):
        al.load_ath_snapshot(path)
    assert len(reads) == 1, f"parsed the file {len(reads)} times for three calls"


def test_each_caller_gets_its_own_frame(tmp_path):
    """Callers set_index on the result; handing out the cached object would let
    one caller reshape what every later caller receives."""
    import pandas as pd
    from src.loaders import ath_loader as al

    path = str(tmp_path / "ath.csv")
    pd.DataFrame({"Symbol": ["A"], "ATH": [1.0],
                  "ATHDate": ["2026-01-01"], "AsOf": ["2026-01-01"]}).to_csv(path, index=False)
    al.clear_snapshot_cache()

    first = al.load_ath_snapshot(path)
    first.set_index("Symbol", inplace=True)
    second = al.load_ath_snapshot(path)
    assert "Symbol" in second.columns, "a caller's set_index reshaped the cache"


def test_a_rewritten_snapshot_is_picked_up(tmp_path):
    """The daily sync rewrites this file. Serving yesterday's highs for the
    life of the process would be worse than re-reading it."""
    import time
    import pandas as pd
    from src.loaders import ath_loader as al

    path = str(tmp_path / "ath.csv")
    pd.DataFrame({"Symbol": ["A"], "ATH": [1.0],
                  "ATHDate": ["2026-01-01"], "AsOf": ["2026-01-01"]}).to_csv(path, index=False)
    al.clear_snapshot_cache()
    assert len(al.load_ath_snapshot(path)) == 1

    time.sleep(0.01)
    pd.DataFrame({"Symbol": ["A", "B"], "ATH": [1.0, 2.0],
                  "ATHDate": ["2026-01-01"] * 2, "AsOf": ["2026-01-02"] * 2}).to_csv(path, index=False)
    assert len(al.load_ath_snapshot(path)) == 2, "served a stale snapshot after a rewrite"


def test_stale_generations_do_not_accumulate(tmp_path):
    """A long-running process rewriting the file must not grow the cache."""
    import time
    import pandas as pd
    from src.loaders import ath_loader as al

    path = str(tmp_path / "ath.csv")
    al.clear_snapshot_cache()
    for i in range(4):
        pd.DataFrame({"Symbol": [f"S{i}"], "ATH": [float(i)],
                      "ATHDate": ["2026-01-01"], "AsOf": ["2026-01-01"]}).to_csv(path, index=False)
        al.load_ath_snapshot(path)
        time.sleep(0.01)
    entries = [k for k in al._SNAPSHOT_CACHE if k[0] == path]
    assert len(entries) == 1, f"{len(entries)} generations retained for one path"


def test_a_missing_snapshot_is_not_cached_as_a_success(tmp_path):
    """Absence must not be memoised past the file appearing."""
    import pandas as pd
    from src.loaders import ath_loader as al

    path = str(tmp_path / "later.csv")
    al.clear_snapshot_cache()
    assert al.load_ath_snapshot(path).empty

    pd.DataFrame({"Symbol": ["A"], "ATH": [1.0],
                  "ATHDate": ["2026-01-01"], "AsOf": ["2026-01-01"]}).to_csv(path, index=False)
    assert len(al.load_ath_snapshot(path)) == 1, (
        "the absent-file result was served after the file appeared"
    )
