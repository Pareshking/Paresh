"""The nightly sync must ask NSE what traded BEFORE it judges the prices.

The confirmation record fixed the right problem in the wrong order. Market caps
were fetched after prices, and the market-cap fetch is what asks NSE for a
bhavcopy -- so on every run the newest session was judged on vendor coverage
alone, and the confirmation that would have saved it was written seconds later.

The 2026-09-16 run, which the record was added to fix:

    20:18:26  Dropping 2 session(s) ... (2026-09-16 at 20%)
    20:18:29  Loaded NSE PR market cap: 2544 stocks for 2026-09-16

The 2026-09-17 run, with the record in place and consulted:

    20:27:22  Dropping 1 session(s) ... (2026-09-17 at 20%)
              Trading days confirmed by NSE: +1 new, 4 on record.

Identical failure, one day apart. The "Keeping ... NSE confirmed" line had
never fired in production, because the newest session -- the only one the
vendor is still publishing, and so the only one that needs rescuing -- can
never be on a record written after it is judged.

These tests read the script structurally rather than running it: the ordering
is the whole fix, and it is invisible to every behavioural test in the suite.
"""

import ast

SCRIPT = "scripts/sync_data.py"


def _daily_sync():
    tree = ast.parse(open(SCRIPT, encoding="utf-8").read())
    return next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "run_daily_sync"
    )


def _call_lines(fn, name):
    """Line numbers where ``name(...)`` is called inside ``fn``."""
    out = []
    for n in ast.walk(fn):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        ident = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
        if ident == name:
            out.append(n.lineno)
    return sorted(out)


def test_nse_is_asked_before_the_price_fetch():
    fn = _daily_sync()
    mcaps = _call_lines(fn, "fetch_market_caps")
    prices = _call_lines(fn, "fetch_price_history")
    assert mcaps and prices, "the sync no longer fetches market caps or prices"
    assert max(mcaps) < min(prices), (
        "market caps are fetched AFTER prices again. The bhavcopy request is "
        "the only thing that confirms a trading day, so the newest session is "
        "back to being judged on coverage alone."
    )


def test_the_confirmation_is_written_down_before_the_price_fetch():
    """Fetching early is not enough -- the record must be WRITTEN first.

    _drop_phantom_sessions reads the file, not the in-memory metrics, so a
    confirmation still sitting in metrics when prices are loaded rescues
    nothing.
    """
    fn = _daily_sync()
    recorded = _call_lines(fn, "record_confirmed")
    prices = _call_lines(fn, "fetch_price_history")
    assert recorded, "the sync no longer records NSE's confirmations at all"
    assert max(recorded) < min(prices), (
        "the trading-day record is written after the price fetch that needs "
        "it; the newest session is judged before the answer exists"
    )


def test_the_price_fetch_still_happens_before_the_rankings_are_precomputed():
    """The reorder must not have pushed prices past what consumes them."""
    fn = _daily_sync()
    prices = _call_lines(fn, "fetch_price_history")
    precompute = _call_lines(fn, "_precompute_rankings")
    if precompute:
        assert min(prices) < min(precompute), (
            "rankings are precomputed before the price cache is updated"
        )


def test_prices_are_never_read_before_they_are_fetched():
    """A cheap guard on the reorder itself: no use-before-assignment."""
    fn = _daily_sync()
    stores, loads = [], []
    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and n.id == "prices_df":
            (stores if isinstance(n.ctx, ast.Store) else loads).append(n.lineno)
    assert stores, "prices_df is no longer assigned in run_daily_sync"
    early = [ln for ln in loads if ln < min(stores)]
    assert not early, f"prices_df is read at {early} before it is assigned"


# ── What gets PUBLISHED must pass the same guards the app reads with ─────────
#
# Everything the publish step writes is consumed by something that does not
# re-check it: the app's cold-start snapshot, the archive the monthly freeze
# reads, and _precompute_rankings, which reads the snapshot file straight back
# off disk and ranks it.
#
# A bare read_parquet here shipped four non-sessions -- 2026-01-15, 2026-05-01,
# 2026-05-28 and 2026-06-26, every priced symbol flat at zero volume, two of
# them at 100% vendor coverage. The app strips them on read and the precompute
# did not, so the two would rank different frames while every field of the
# contract still matched. A wrong answer served fast is worse than no artifact.

def test_the_published_snapshot_is_read_through_the_guards():
    src = open(SCRIPT, encoding="utf-8").read()
    assert "_read_local_price_cache()" in src, (
        "the publish step no longer reads through the price-cache guards, so "
        "non-sessions reach the published snapshot and the precomputed ranking"
    )


def test_the_publish_step_does_not_bypass_them_with_a_bare_read():
    """A fallback is fine; reaching for it first is not."""
    import ast

    tree = ast.parse(open(SCRIPT, encoding="utf-8").read())
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "run_daily_sync"
    )
    guarded, bare = [], []
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            f = n.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            if name == "_read_local_price_cache":
                guarded.append(n.lineno)
            elif name == "read_parquet":
                bare.append(n.lineno)
    assert guarded, "the guarded reader is gone from the publish step"
    for b in bare:
        assert any(g < b for g in guarded), (
            f"a bare read_parquet at line {b} runs before any guarded read; "
            "the published artifact would carry whatever is on disk"
        )
