"""Memory telemetry (ported from #417, bounded) and the S65 guardrails.

Owner, 8 Oct 2026: memory checkpoints so production logs show where memory
goes; one backtest computing at a time across the server; a ceiling on the
parameter sweep a web reader can start.
"""

import threading
import time

import pytest

from src.core import startup_metrics as metrics
from src.engine import compute_gate


# ── Memory checkpoints ───────────────────────────────────────────────────────

def test_a_checkpoint_records_resident_and_peak_memory():
    metrics.reset_for_tests()
    point = metrics.memory_checkpoint("unit")
    assert point["label"] == "unit"
    facts = metrics.snapshot()["facts"]
    assert facts["memory_checkpoints"][-1]["label"] == "unit"
    assert facts["memory_latest"]["unit"] is point
    if "VmHWM" in point:  # Linux
        assert point["VmRSS"] > 0 and point["VmHWM"] >= point["VmRSS"]
        assert facts["memory_peak_bytes"] == point["VmHWM"]


def test_a_stage_records_memory_at_both_ends():
    metrics.reset_for_tests()
    with metrics.stage("unit_stage"):
        pass
    labels = [c["label"] for c in metrics.snapshot()["facts"]["memory_checkpoints"]]
    assert labels == ["unit_stage:start", "unit_stage:end"]


def test_checkpoints_stay_bounded_for_the_life_of_the_process():
    """#417 appended every checkpoint forever; a stage runs on every rerun."""
    metrics.reset_for_tests()
    for i in range(5_000):
        with metrics.stage("price_source"):
            pass
        metrics.memory_checkpoint(f"page:{i % 10}")
    facts = metrics.snapshot()["facts"]
    assert len(facts["memory_checkpoints"]) == metrics.MEMORY_COLD_CHECKPOINTS
    assert facts["memory_checkpoints"][0]["label"] == "price_source:start", "the cold start is kept"
    assert len(facts["memory_latest"]) == 12
    for i in range(500):
        metrics.memory_checkpoint(f"label{i}")
    assert len(metrics.snapshot()["facts"]["memory_latest"]) == metrics.MEMORY_MAX_LABELS


def test_the_peak_is_logged_when_it_climbs_not_on_every_checkpoint(monkeypatch, caplog):
    metrics.reset_for_tests()
    readings = iter([100, 120, 160, 170, 230, 231])
    monkeypatch.setattr(metrics, "_process_memory",
                        lambda: (lambda mb: {"VmRSS": mb * 2**20, "VmHWM": mb * 2**20})(next(readings)))
    import logging
    with caplog.at_level(logging.INFO, logger="nse_momentum"):
        logger = logging.getLogger("nse_momentum")
        logger.addHandler(caplog.handler)
        try:
            for i in range(6):
                metrics.memory_checkpoint(f"page:p{i}")
        finally:
            logger.removeHandler(caplog.handler)
    # The app's logger may not propagate, hence the handler; dedupe in case it does.
    lines = list(dict.fromkeys(r.getMessage() for r in caplog.records if "Memory peak" in r.getMessage()))
    # 100 (first), 160 (+60), 230 (+70); 120, 170, 231 are under the 50 MB step.
    assert [line.split(" at ")[1].split(" ")[0] for line in lines] == ["page:p0", "page:p2", "page:p4"]


def test_memory_facts_reach_the_page_for_the_probe():
    metrics.reset_for_tests()
    metrics.memory_checkpoint("unit")
    assert "memory_checkpoints" in metrics.public_snapshot()["facts"]


# ── One backtest at a time (S65) ─────────────────────────────────────────────

def test_gated_work_runs_one_at_a_time():
    active, peak = [0], [0]
    lock = threading.Lock()

    @compute_gate.serialised
    def work():
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.05)
        with lock:
            active[0] -= 1

    threads = [threading.Thread(target=work) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert peak[0] == 1
    assert not compute_gate.busy()


def test_busy_is_true_only_while_work_runs():
    started, release = threading.Event(), threading.Event()

    @compute_gate.serialised
    def work():
        started.set()
        release.wait(2)

    t = threading.Thread(target=work)
    t.start()
    started.wait(2)
    assert compute_gate.busy()
    release.set()
    t.join()
    assert not compute_gate.busy()


def test_the_gate_is_reentrant():
    @compute_gate.serialised
    def inner():
        return 1

    @compute_gate.serialised
    def outer():
        return inner() + 1

    assert outer() == 2


def test_a_cache_hit_is_not_queued_behind_a_running_backtest():
    """The gate sits UNDER st.cache_data, so it is taken only on a miss."""
    import streamlit as st

    calls = []

    @st.cache_data(max_entries=4)
    @compute_gate.serialised
    def work(key: str):
        calls.append(key)
        return key

    assert work("a") == "a"
    started, release = threading.Event(), threading.Event()

    @compute_gate.serialised
    def long_run():
        started.set()
        release.wait(2)

    t = threading.Thread(target=long_run)
    t.start()
    started.wait(2)
    t0 = time.perf_counter()
    assert work("a") == "a"
    waited = time.perf_counter() - t0
    release.set()
    t.join()
    assert waited < 0.5 and calls == ["a"]


def test_run_backtest_is_gated_under_its_cache():
    src = open("src/engine/backtester.py", encoding="utf-8").read()
    at = src.index("def run_backtest(")
    decorators = src[src.rindex("@st.cache_data", 0, at):at]
    assert decorators.index("@st.cache_data") < decorators.index("@compute_gate.serialised")


def test_the_cache_key_still_follows_run_backtests_own_code():
    """st.cache_data hashes the function's source; through functools.wraps it
    must still be run_backtest's body, or a code change would serve old results."""
    import inspect

    from src.engine.backtester import run_backtest

    assert "Executes a walk-forward momentum backtest" in inspect.getsource(run_backtest.__wrapped__)
    assert run_backtest.__wrapped__.__name__ == "run_backtest"


# ── The sweep ceiling (S65) ──────────────────────────────────────────────────

def test_the_web_sweep_ceiling_is_enforced_by_the_engine_too():
    import numpy as np
    import pandas as pd

    from src.engine.parameter_sweep import MAX_WEB_COMBINATIONS, run_parameter_sweep

    prices = pd.DataFrame(np.ones((10, 2)), columns=["A", "B"],
                          index=pd.bdate_range("2026-01-01", periods=10))
    space = {"Holdings": list(range(5, 5 + MAX_WEB_COMBINATIONS + 1))}
    with pytest.raises(ValueError, match="exceeds max_combinations"):
        run_parameter_sweep(prices, space, max_combinations=MAX_WEB_COMBINATIONS)


def test_the_backtest_page_refuses_a_sweep_over_the_ceiling():
    src = open("src/ui/views/backtest_view.py", encoding="utf-8").read()
    refuse = src.index("if n_combos > MAX_WEB_COMBINATIONS:")
    button = src.index('st.button("Run sweep"')
    assert refuse < button and "return" in src[refuse:button]
    assert "max_combinations=MAX_WEB_COMBINATIONS" in src


# ── The backtest's 52-week high (production OOM, 8 Oct 2026) ─────────────────

def test_the_rolling_high_does_not_pin_its_window():
    """run_backtest keeps one of these per signal date for the whole run."""
    import tracemalloc

    import numpy as np
    import pandas as pd

    from src.engine.backtester import _rolling_high_at

    prices = pd.DataFrame(np.random.default_rng(0).random((600, 400)),
                          index=pd.bdate_range("2020-01-01", periods=600))
    tracemalloc.start()
    kept = {i: _rolling_high_at(prices, i) for i in range(300, 600, 10)}
    retained, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    window_bytes = 252 * 400 * 8
    assert retained < 3 * window_bytes, (
        f"{len(kept)} kept highs retain {retained / 1e6:.1f} MB: each is pinning its "
        "252-row rolling frame again"
    )


def test_the_rolling_high_values_are_unchanged():
    import numpy as np
    import pandas as pd

    from src.engine.backtester import _rolling_high_at

    prices = pd.DataFrame(np.random.default_rng(1).random((400, 30)),
                          index=pd.bdate_range("2020-01-01", periods=400))
    prices.iloc[50:80, 3] = np.nan
    full = prices.rolling(252, min_periods=126).max()
    for idx in (130, 251, 252, 399):
        pd.testing.assert_series_equal(_rolling_high_at(prices, idx), full.iloc[idx], check_names=False)


# ── Freed memory goes back to the system (src/core/memory.py) ────────────────

def test_release_freed_memory_never_raises_and_is_fast():
    import platform

    from src.core import memory

    took = memory.release_freed_memory()
    if platform.system() == "Linux" and platform.libc_ver()[0] == "glibc":
        assert took is not None and took < 1.0
    else:
        assert took is None


def test_release_freed_memory_returns_what_a_thread_freed():
    """The production pattern: work on a short-lived thread, freed into its arena."""
    import platform
    import threading

    import numpy as np

    from src.core import memory

    if not (platform.system() == "Linux" and platform.libc_ver()[0] == "glibc"):
        pytest.skip("glibc only")

    def rss_mb():
        with open("/proc/self/status") as fh:
            return next(int(line.split()[1]) // 1024 for line in fh if line.startswith("VmRSS"))

    def small_work():
        blocks = [np.ones(8_000) for _ in range(4_000)]  # 4k x 64 KB = ~256 MB
        del blocks

    t = threading.Thread(target=small_work)
    t.start()
    t.join()
    before = rss_mb()
    memory.release_freed_memory()
    after = rss_mb()
    assert after <= before


def test_every_page_run_ends_with_a_release():
    src = open("app.py", encoding="utf-8").read()
    page = src.index('metrics.memory_checkpoint(f"page:')
    assert src.index("release_freed_memory()", page) > page


def test_the_gate_knows_whose_computation_holds_it(monkeypatch):
    """With one reader the gate is usually held by that reader's own abandoned
    rerun; the page must not call it 'another reader's'."""
    started, release = threading.Event(), threading.Event()
    sessions = iter(["session-A", "session-B"])
    monkeypatch.setattr(compute_gate, "current_session", lambda: next(sessions))

    @compute_gate.serialised
    def work():
        started.set()
        release.wait(2)

    t = threading.Thread(target=work)
    t.start()
    started.wait(2)
    assert compute_gate.holder() == "session-A"
    release.set()
    t.join()
    assert compute_gate.holder() is None


def test_the_queued_message_is_amber_and_names_whose_run_it_is():
    src = open("src/ui/views/backtest_view.py", encoding="utf-8").read()
    block = src[src.index("if compute_gate.busy():"):src.index("with st.spinner(\"Running walk-forward")]
    assert "queued.warning(" in block and "queued.info(" not in block
    assert "Your previous settings are still computing" in block
    assert "Another reader's backtest is computing" in block
