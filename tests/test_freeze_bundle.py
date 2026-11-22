"""S185: each frozen month's evidence bundle replays the month exactly, whatever
later happens to the live prices (owner, 22 Nov 2026)."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.engine import freeze_bundle as fb
from src.engine.backtester import run_backtest
from src.engine.track_record import TRACK_RECORD_CONFIG, calendar_month_returns, run_backtest_kwargs

ROOT = Path(__file__).resolve().parents[1]


def _prices(n_days=700, n=40, seed=5):
    idx = pd.bdate_range("2022-01-03", periods=n_days)
    rng = np.random.default_rng(seed)
    drift = rng.normal(0.0004, 0.0006, n)
    vol = rng.uniform(0.008, 0.03, n)
    lr = rng.normal(drift, vol, (n_days, n))
    return pd.DataFrame(100 * np.exp(np.cumsum(lr, axis=0)), index=idx,
                        columns=[f"S{i:02d}" for i in range(n)])


def _bench(idx):
    return pd.Series(100 * np.exp(np.linspace(0, 0.2, len(idx))), index=idx, name="NIFTY500")


KWARGS = run_backtest_kwargs(TRACK_RECORD_CONFIG)


def _run(key, frame, bench):
    return run_backtest(key, frame, **KWARGS, sector_map={}, _benchmark_close=bench,
                        backtest_months=12, _membership=None, _actions=[])


@pytest.fixture(scope="module")
def frozen():
    """A month struck by the real engine, and its bundle."""
    frame = _prices()
    bench = _bench(frame.index)
    result = _run("s185_original", frame, bench)
    strat = calendar_month_returns(result["equity_curve"])
    bmk = calendar_month_returns(result["benchmark"])
    month = str(strat.index[-2])  # the last closed month
    period = pd.Period(month, freq="M")
    s, b = float(strat.loc[period]), float(bmk.loc[period])
    store = io.BytesIO()
    frame.to_parquet(store)
    data = fb.build(
        system="750", month=month, as_of=frame.index[-1], frame=frame, benchmark=bench,
        membership=None, screener_store=store.getvalue(), screener_source="test",
        kwargs=KWARGS, sector_map={}, actions=[], backtest_months=12,
        cfg=TRACK_RECORD_CONFIG, fingerprint="abc123",
        results={"strategy": s, "benchmark": b, "ledger_strategy": round(s, 6),
                 "ledger_benchmark": round(b, 6), "ledger_alpha": round(s - b, 6)},
        book=fb.month_book(result["tradebook"], month), code_sha="testsha",
    )
    return {"frame": frame, "bench": bench, "result": result, "month": month, "data": data,
            "strategy": s, "benchmark": b}


# (a) the key test: the bundle replays the frozen month exactly, even after the
# live prices change the way October 2026's did.
def test_the_bundle_replays_the_frozen_month_to_the_last_digit(frozen):
    got = fb.replay(fb.read(frozen["data"]))
    assert got["strategy"] == frozen["strategy"] and got["benchmark"] == frozen["benchmark"]
    assert fb.book_differences(fb.read(frozen["data"])["meta"]["book"], got["book"]) == {}
    assert fb.holdings(got["book"])  # a real book, not an empty one


def test_a_changed_live_store_changes_a_fresh_replay_but_not_the_frozen_month(frozen):
    month, frame = frozen["month"], frozen["frame"]
    book = fb.holdings(fb.read(frozen["data"])["meta"]["book"])
    start = max(book)                      # the period that formed the month's book
    held = book[start][0]
    # October's failure mode: a held name's closes before the signal are restated
    # (here: halved over the 90 days before it, so it falls below its EMA and out
    # of the top), and a replay on the live data forms a different book.
    mutated = frame.copy()
    window = (mutated.index >= pd.Timestamp(start) - pd.Timedelta(days=90)) & (
        mutated.index < pd.Timestamp(start))
    mutated.loc[window, held] *= 0.5
    fresh = _run("s185_mutated", mutated, frozen["bench"])
    fresh_book = fb.month_book(fresh["tradebook"], month)
    assert fb.book_differences(fb.read(frozen["data"])["meta"]["book"], fresh_book) != {}
    # ... and the bundle still gives the frozen month, untouched.
    again = fb.replay(fb.read(frozen["data"]))
    assert again["strategy"] == frozen["strategy"]
    assert fb.book_differences(fb.read(frozen["data"])["meta"]["book"], again["book"]) == {}


def test_the_replay_script_passes_on_the_bundle_and_its_ledger_row(frozen):
    mod = _load_script("replay_frozen_month")
    revision = hashlib.sha256(frozen["data"]).hexdigest()
    s, b = frozen["strategy"], frozen["benchmark"]
    ledger = {"months": {frozen["month"]: {"strategy": round(s, 6), "benchmark": round(b, 6),
                                           "alpha": round(s - b, 6), "freeze_revision": revision}}}
    assert mod.check(frozen["data"], ledger=ledger, books={}) == []
    ledger["months"][frozen["month"]]["strategy"] = round(s, 6) + 0.001
    assert any("ledger strategy" in f for f in mod.check(frozen["data"], ledger=ledger, books={}))


# (b) no month is frozen without its evidence.
def test_a_failed_publish_raises_before_anything_is_recorded(frozen, tmp_path):
    mod = _load_script("update_track_record")
    month = frozen["month"]
    ledger = {"months": {month: {"strategy": 0.01, "benchmark": 0.0, "alpha": 0.01}}}
    before = json.dumps(ledger, sort_keys=True)

    def broken(*_a, **_k):
        raise RuntimeError("R2 unreachable")

    with pytest.raises(RuntimeError, match="R2 unreachable"):
        _archive(mod, frozen, ledger, publisher=broken, books_path=tmp_path / "record_books.json")
    assert json.dumps(ledger, sort_keys=True) == before
    assert not (tmp_path / "record_books.json").exists()


def test_a_published_month_names_its_revision_and_keeps_its_book(frozen, tmp_path):
    mod = _load_script("update_track_record")
    month = frozen["month"]
    ledger = {"months": {month: {"strategy": 0.01, "benchmark": 0.0, "alpha": 0.01}}}
    sent = {}

    def fake(data, **kw):
        sent["data"] = data
        return hashlib.sha256(data).hexdigest()

    books = _archive(mod, frozen, ledger, publisher=fake, books_path=tmp_path / "record_books.json")
    row = ledger["months"][month]
    assert row["freeze_revision"] == hashlib.sha256(sent["data"]).hexdigest()
    assert row["screener_store_sha256"] == fb.read(sent["data"])["meta"]["screener_store"]["sha256"]
    assert books["750"][month]["freeze_revision"] == row["freeze_revision"]
    assert fb.holdings(books["750"][month]["book"])


def test_the_freeze_publishes_before_it_writes_the_ledger():
    src = (ROOT / "scripts" / "update_track_record.py").read_text()
    main = src[src.index("def main()"):]
    assert main.index("_archive_months(") < main.index("save_books(") < main.index("save_ledger(")
    assert "R2Config.from_env()" in src            # no R2: the freeze refuses


# (c) the bundle itself.
def test_the_same_inputs_give_the_same_bytes_and_a_tampered_member_is_refused(frozen):
    meta = fb.read(frozen["data"])["meta"]
    assert set(meta["members"]) == set(fb.MEMBERS)
    assert meta["run_backtest"]["tuple_kwargs"] == ["weight_reset_months"]
    assert fb.run_kwargs(meta)["weight_reset_months"] == KWARGS["weight_reset_months"]
    assert fb.run_kwargs(meta)["config_weights"] == list(KWARGS["config_weights"])
    zin = zipfile.ZipFile(io.BytesIO(frozen["data"]))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zout:
        for name in zin.namelist():
            body = zin.read(name)
            zout.writestr(name, body + b"x" if name == "benchmark.parquet" else body)
    with pytest.raises(ValueError, match="benchmark.parquet"):
        fb.read(out.getvalue())


def test_the_raw_screener_store_is_archived_byte_for_byte(frozen):
    bundle = fb.read(frozen["data"])
    raw = io.BytesIO()
    frozen["frame"].to_parquet(raw)
    assert bundle["screener_store"] == raw.getvalue()
    assert bundle["meta"]["screener_store"]["sha256"] == hashlib.sha256(raw.getvalue()).hexdigest()


def test_system_keys_follow_the_ledger_file():
    assert fb.system_key("data/track_record.json") == "750"
    assert fb.system_key("data/track_record_nano.json") == "nano"
    assert fb.system_key("data/track_record_shadow_high90.json") == "shadow_high90"
    assert fb.dataset("nano") == "record/freezes/nano"


# (d) R2 keeps every bundle.
def test_retention_protects_every_freeze_bundle():
    mod = _load_script("r2_retention")
    assert "record/freezes/" in mod.PROTECTED_DATASETS


# (e) every freeze step can publish, and the book is committed with the ledger.
def test_every_freeze_step_has_r2_and_the_books_are_committed():
    yaml = pytest.importorskip("yaml")
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "monthly_track_record.yml").read_text())
    steps = wf["jobs"]["freeze"]["steps"]
    freezes = [s for s in steps if "update_track_record.py" in str(s.get("run", ""))]
    assert len(freezes) >= 5
    for step in freezes:
        env = step.get("env") or {}
        assert {"R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT",
                "R2_BUCKET"} <= set(env), step["name"]
        assert "--no-archive" not in step["run"], step["name"]
    commit = next(s for s in steps if s.get("name") == "Commit the ledger")
    assert "data/record_books.json" in commit["run"]


def _archive(mod, frozen, ledger, *, publisher, books_path):
    return mod._archive_months(
        [frozen["month"]], ledger, system_key="750", as_of=frozen["frame"].index[-1],
        frame=frozen["frame"], benchmark=frozen["bench"], membership=None,
        store_bytes=b"raw store", store_source="test", kwargs=KWARGS, sector_map={},
        actions=[], backtest_months=12, cfg=TRACK_RECORD_CONFIG, fingerprint=lambda _p: "abc",
        result=frozen["result"], force=False, publish=True, publisher=publisher,
        books_path=books_path,
    )


def test_the_monthly_workflow_replays_what_it_froze_after_the_commit():
    yaml = pytest.importorskip("yaml")
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "monthly_track_record.yml").read_text())
    steps = wf["jobs"]["freeze"]["steps"]
    names = [s.get("name", "") for s in steps]
    replay = [i for i, s in enumerate(steps) if "replay_frozen_month.py" in str(s.get("run", ""))]
    assert len(replay) == 1
    step = steps[replay[0]]
    assert "--frozen-since" in step["run"]
    assert replay[0] > names.index("Commit the ledger")
    assert "github.sha" in step["env"]["REPLAY_SINCE"]
    assert {"R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT",
            "R2_BUCKET"} <= set(step["env"])
    replay_line = next(ln for ln in step["run"].splitlines() if "replay_frozen_month.py" in ln)
    assert "||" not in replay_line  # a failed replay fails the job


def test_frozen_since_names_only_months_given_a_bundle_after_the_ref(tmp_path):
    import subprocess

    mod = _load_script("replay_frozen_month")
    (tmp_path / "data").mkdir()

    def write(name, months):
        (tmp_path / "data" / name).write_text(json.dumps({"months": months}))

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    write("track_record.json", {"2026-10": {"strategy": 0.01}})
    write("track_record_nano.json", {"2026-10": {"strategy": 0.02}})
    git("init", "-q")
    git("add", ".")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    assert mod.frozen_since("HEAD", root=tmp_path) == []
    write("track_record.json", {"2026-10": {"strategy": 0.01},
                                "2026-11": {"strategy": 0.03, "freeze_revision": "a" * 64}})
    write("track_record_1000.json", {"2026-11": {"strategy": 0.04, "freeze_revision": "b" * 64}})
    write("track_record_nano.json", {"2026-10": {"strategy": 0.02}, "2026-11": {"strategy": 0.0}})
    assert mod.frozen_since("HEAD", root=tmp_path) == [("750", "2026-11"), ("1000", "2026-11")]
    with pytest.raises(SystemExit, match="Unknown commit"):
        mod.frozen_since("0" * 40, root=tmp_path)


def _load_script(name):
    spec = importlib.util.spec_from_file_location(f"s185_{name}", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, mod)
    spec.loader.exec_module(mod)
    return mod


def test_a_month_whose_fill_is_its_first_day_keeps_the_book_held_into_it():
    # October 2026: the fill was on 1 Oct, so 30 Sep -> 1 Oct ran on September's book.
    tb = pd.DataFrame({
        "Period": ["Sep", "Sep", "Oct", "Oct", "Nov"],
        "Period Start": ["2026-09-01", "2026-09-01", "2026-10-01", "2026-10-01", "2026-11-02"],
        "Action": ["🟢 BUY (Entry)", "⚪ HOLD (Retained)", "🟢 BUY (Entry)", "🔴 SELL (Exit)",
                   "🟢 BUY (Entry)"],
        "Symbol": ["AETHER", "SKYGOLD", "AKUMS", "AETHER", "ZZZ"],
        "Price": [1.0] * 5, "Weight %": [5.0] * 5, "Return %": [0.0] * 5,
    })
    assert fb.holdings(fb.month_book(tb, "2026-10")) == {
        "2026-09-01": ["AETHER", "SKYGOLD"], "2026-10-01": ["AKUMS"]}
    assert fb.holdings(fb.month_book(tb, "2026-11")) == {
        "2026-10-01": ["AKUMS"], "2026-11-02": ["ZZZ"]}


def test_the_same_inputs_build_the_same_bundle_bytes():
    idx = pd.bdate_range("2026-01-01", periods=5)
    args = dict(system="750", month="2026-01", as_of=idx[-1],
                frame=pd.DataFrame({"A": [1.0, 2, 3, 4, 5]}, index=idx),
                benchmark=pd.Series([1.0, 1, 1, 1, 1], index=idx), membership={"m": 1},
                screener_store=b"store", screener_source="t", kwargs={"w": (1, 2)},
                sector_map={}, actions=[], backtest_months=1, cfg={}, fingerprint="f",
                results={"strategy": 0.1, "benchmark": 0.0}, book=[], code_sha="c")
    assert fb.build(**args) == fb.build(**args)
