"""The price pipeline must stay single-precision from disk to engine.

This is already true, and that is exactly why it needs a guard: the saving is
invisible, so nothing would report its loss. One `.astype(float)` added to a
loader, or one `pd.to_numeric` on a frame rather than a column, silently
doubles the published snapshot, the bytes every cold start downloads, and the
memory the engine holds -- and every test would still pass.

What the measurements actually say, so nobody re-litigates this from intuition:

  * Storage and transfer is where it pays. The published snapshot is 10.5 MB in
    float32 against 18.7 MB in float64, and the frames the engine holds are
    1.4 MB each against 2.9 MB. Prices carry nowhere near seven significant
    figures of meaning, so nothing is lost.

  * Compute is where it does NOT pay, contrary to the obvious guess. pandas
    promotes to float64 inside rolling() and ewm() regardless of input dtype --
    a float64 accumulator is deliberate there, for numerical stability -- so
    those are measured at 0.97-1.03x either way. Only whole-frame reductions
    and rank() benefit, at 1.10-1.15x.

  * The one remaining explicit float64, in _calendar_period_metrics, is left
    alone ON PURPOSE. It computes variance through the
    cumsum(x**2)/n - mean**2 identity, which is the classic
    cancellation-sensitive form; float64 is the correct default there. Measured
    on the shipped snapshot it would have saved 7.4 ms of a 756 ms
    build_engine -- 1% of a function the precomputed ranking means most page
    loads no longer run at all. Not a trade worth making in a variance
    calculation whose error is data-dependent.
"""

import numpy as np
import pandas as pd
import pytest


def _frame(dtype="float32"):
    idx = pd.date_range("2026-01-01", periods=60, freq="B")
    cols = pd.MultiIndex.from_product(
        [["AAA", "BBB"], ["Open", "High", "Low", "Close", "Volume"]],
        names=["Ticker", "Price"],
    )
    data = np.random.default_rng(0).uniform(100, 200, size=(len(idx), len(cols)))
    return pd.DataFrame(data.astype(dtype), index=idx, columns=cols)


def test_extract_ohlcv_does_not_widen_the_frames():
    """The decomposition must hand the engine what it was given."""
    from src.loaders.price_loader import extract_ohlcv

    adj, close_p, high_p, low_p, vol_p, open_p = extract_ohlcv(_frame(), ["AAA", "BBB"])
    # The loop below skips absent frames; the two the engine cannot run without
    # must be here, or it would pass on nothing.
    assert not adj.empty and not close_p.empty
    for name, frame in [
        ("adj_close", adj), ("close", close_p), ("high", high_p),
        ("low", low_p), ("volume", vol_p), ("open", open_p),
    ]:
        if frame is None or frame.empty:
            continue
        assert all(d == np.float32 for d in frame.dtypes), (
            f"{name} came out of extract_ohlcv as {set(map(str, frame.dtypes))}; "
            "something upcast it and doubled the memory the engine holds"
        )


def test_the_engine_holds_single_precision_frames():
    from src.engine.momentum import MomentumEngine

    from src.loaders.price_loader import extract_ohlcv

    adj, close_p, high_p, low_p, vol_p, _ = extract_ohlcv(_frame(), ["AAA", "BBB"])
    e = MomentumEngine(adj, high_df=high_p, low_df=low_p, close_df=close_p,
                       volume_df=vol_p)
    for name in ("prices", "high", "low", "close"):
        frame = getattr(e, name)
        assert all(d == np.float32 for d in frame.dtypes), (
            f"MomentumEngine.{name} is {set(map(str, frame.dtypes))}, not float32"
        )
    # Log returns are a division and a log: both preserve the input dtype.
    assert all(d == np.float32 for d in e.log_ret.dtypes)


def test_corporate_action_adjustment_does_not_widen_the_frames():
    """A column multiply must not be what promotes the whole frame."""
    from src.engine.corporate_actions import adjust_ohlc

    idx = pd.date_range("2026-01-01", periods=60, freq="B")
    prices = np.linspace(300, 330, len(idx), dtype="float32")
    prices[30:] *= 0.5            # the 1:2 split the event describes
    close = pd.DataFrame({"AAA": prices}, index=idx).astype("float32")
    event = {"symbol": "AAA", "date": str(idx[30].date()), "ratio": 0.5}
    frames, applied = adjust_ohlc({"close": close}, [event])
    # A smooth series has no step, so the adjustment would be skipped and no
    # multiply would happen at all -- the test would pass without testing.
    assert applied, "the split was not applied; nothing was multiplied"
    assert all(d == np.float32 for d in frames["close"].dtypes), (
        f"adjust_ohlc returned {set(map(str, frames['close'].dtypes))}"
    )


def test_the_published_snapshot_is_written_single_precision():
    """The line in sync_data that halves what every cold start downloads."""
    import pathlib

    job = (pathlib.Path(__file__).resolve().parents[1] / "scripts/sync_data.py").read_text()
    assert 'astype("float32"' in job, (
        "the daily sync no longer compacts the snapshot to float32; the asset "
        "production downloads on every cold start just doubled"
    )


def test_float32_is_precise_enough_for_a_price():
    """Seven significant figures against a number needing six. No rupee lost."""
    for rupees in (49.05, 1269.84, 7009.75, 89999.5):
        assert np.float32(rupees) == pytest.approx(rupees, rel=1e-6)
