"""The Backtest default page kept as its parts (S233 (1); owner, 26 Nov 2026: "save calculated values")."""

import pandas as pd
import pytest

from src.ui import backtest_snapshot as snap
from src.ui import dash_charts as dc
from src.ui.views.dashboard_home_view import Chart, Cols, html_of


@pytest.fixture(autouse=True)
def _dir(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKTEST_SNAPSHOT_DIR", str(tmp_path / "kept"))


class Store:
    def __init__(self, close, dy, as_of="2026-11-25"):
        self.close, self.dy, self.as_of = close, dy, as_of


def _bench(last=100.0):
    return pd.Series([98.0, 99.5, last], index=pd.date_range("2026-11-21", periods=3), name="n500")


def _inputs(**over):
    h = {"key": "nifty_500", "close_fingerprint": "abc", "membership": {"2026-10": {"A", "B"}},
         "sector_map": {"A": "Banks"}, "start": pd.Period("2010-01", "M"), "built": "2026-11-25"}
    h.update(over)
    return h


def _key(**over):
    args = {"settings": {"top_n": 20, "weights": (0.1, 0.3)}, "inputs": _inputs(), "caps": (0.05, 0.4),
            "bench": _bench(), "store": Store(pd.DataFrame({"x": [1.0, 2.0]}), {"nifty_500": pd.Series([1.2])}),
            "reference_bytes": b'{"built": "2026-11-22"}'}
    args.update(over)
    return snap.key(args["settings"], args["inputs"], args["caps"], args["bench"], args["store"], args["reference_bytes"])


def _sections():
    spec = {"lines": [["2026-11-21", "A", 1.5, None, "Bought", "Rank 3, new"]], "range": {"default": "all", "why": "record"}}
    return {"head": ['<h1 class="dh-h1">Rule beat the Nifty 500 by 4.2 points a year</h1>'],
            "body": ["<p>Falls</p>", Cols(["<p>left</p>"], ["<p>right</p>"], (2, 1))],
            "history": [Chart("history", spec, {"label": "Every trade", "note": "Returns are before costs."})],
            "foot": ['<div class="dh-end"></div>', "<p>Foot</p>"]}


def test_the_key_is_the_same_for_the_same_inputs_and_moves_with_each_one():
    base = _key()
    assert base == _key()
    changed = [
        _key(settings={"top_n": 30, "weights": (0.1, 0.3)}),
        _key(inputs=_inputs(close_fingerprint="abd")),
        _key(inputs=_inputs(membership={"2026-10": {"A", "C"}})),
        _key(inputs=_inputs(sector_map={"A": "Insurance"})),
        _key(inputs=_inputs(built="2026-11-26")),
        _key(caps=(0.05, 0.35)),
        _key(bench=_bench(last=100.5)),          # a value, not only the dates
        _key(store=Store(pd.DataFrame({"x": [1.0, 2.5]}), {"nifty_500": pd.Series([1.2])})),
        _key(store=Store(pd.DataFrame({"x": [1.0, 2.0]}), {"nifty_500": pd.Series([1.3])})),
        _key(reference_bytes=b'{"built": "2026-11-29"}'),
    ]
    assert base not in changed and len(set(changed)) == len(changed)


def test_a_set_is_fingerprinted_in_sorted_order():
    names = [f"S{i}" for i in range(40)]
    assert snap.fingerprint(set(names)) == snap.fingerprint(set(reversed(names)))


def test_a_code_change_moves_the_key(monkeypatch):
    base = _key()
    monkeypatch.setattr(snap, "code_fingerprint", lambda root=snap.ROOT: "other code")
    assert _key() != base


def test_the_stored_parts_draw_exactly_what_the_page_drew():
    k = _key()
    sections = _sections()
    assert snap.save({"key": k, "sections": sections, "meta": {"first": "2010-02-01", "last": "2026-10-30"}})
    kept = snap.load(k)
    assert kept["meta"] == {"first": "2010-02-01", "last": "2026-10-30"}
    for name, parts in sections.items():
        got = kept["sections"][name]
        assert html_of(got) == html_of(parts)
        assert [type(p) for p in got] == [type(p) for p in parts]
    a, b = sections["history"][0], kept["sections"]["history"][0]
    assert dc.frame_html(b.kind, b.spec, **b.fill) == dc.frame_html(a.kind, a.spec, **a.fill)
    cols = kept["sections"]["body"][1]
    assert (cols.left, cols.right, cols.ratio) == (["<p>left</p>"], ["<p>right</p>"], (2, 1))


def test_another_key_or_layout_is_not_served(tmp_path):
    k = _key()
    snap.save({"key": k, "sections": _sections()})
    assert snap.load(_key(caps=(0.05, 0.35))) is None
    raw = snap.dumps({"key": k, "sections": _sections()}).replace(b'"version":1', b'"version":0')
    assert snap.loads(raw, k) is None
    assert snap.loads(b"not json", k) is None


def test_only_the_latest_key_is_kept():
    first, second = _key(), _key(caps=(0.05, 0.35))
    snap.save({"key": first, "sections": _sections()})
    snap.save({"key": second, "sections": _sections()})
    assert snap.load(first) is None and snap.load(second) is not None


def test_a_part_that_is_not_json_is_not_kept_and_does_not_raise():
    k = _key()
    bad = {"head": [Chart("history", {"x": float("nan")}, {})], "body": [], "history": [], "foot": []}
    assert snap.save({"key": k, "sections": bad}) is False
    assert snap.load(k) is None
