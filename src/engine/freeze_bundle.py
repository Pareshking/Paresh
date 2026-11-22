"""The evidence behind each frozen month (S185, owner 22 Nov 2026).

A frozen month used to be reproducible only while the price data that struck it
was still the data the app reads. October 2026 showed what that costs: the
Screener store carried BSE closes for a fortnight, the 3 Nov freeze struck
October on that store (a SKYGOLD/AKUMS book nobody held), and once the store was
corrected nothing could show which inputs had produced the frozen number
(docs/MONTHS_THAT_DIFFER.md, TODO S89).

At each freeze, for every month it adds, the job now writes one bundle: every
input of the exact `run_backtest` call that struck the month, and its outputs.

    meta.json            system, month, as_of, the run_backtest arguments, the
                         record config and the month's fingerprint, the code's
                         git SHA, the month's results at full precision, the
                         book (every tradebook row of the periods that cover the
                         month), and the sha256 of every other member
    frame.parquet        the price frame passed to run_backtest (the record's
                         basis frame with former members added)
    benchmark.parquet    the benchmark closes passed to it
    membership.json      the point-in-time membership it scored against
    screener_store.parquet  the raw Screener store the frame was built from,
                         byte for byte, so the transformation itself can be
                         checked later, not only its output

The bundle is a zip with fixed timestamps and sorted members, filed on R2 under
`record/freezes/<system>` for its month, as an immutable revision (protected in
scripts/r2_retention.py). Re-running `run_backtest` on a bundle's inputs must
give back the frozen month to the last digit (`replay`,
scripts/replay_frozen_month.py): a later change to the live store can no longer
change what a frozen month was.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd

BUNDLE_VERSION = 1
DATASET_ROOT = "record/freezes"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)  # zip timestamps: the same inputs give the same bytes
MEMBERS = ("frame.parquet", "benchmark.parquet", "membership.json", "screener_store.parquet")
BOOK_COLUMNS = ["Period", "Period Start", "Action", "Symbol", "Price", "Weight %", "Return %"]


def system_key(ledger_file: str | Path) -> str:
    """'750' for data/track_record.json, else the ledger's suffix ('nano', 'shadow_high90')."""
    stem = Path(ledger_file).stem
    rest = stem[len("track_record"):].strip("_") if stem.startswith("track_record") else stem
    return rest or "750"


def dataset(system: str) -> str:
    return f"{DATASET_ROOT}/{system}"


def key_root(system: str) -> str:
    return f"archive/{DATASET_ROOT}/{system}"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parquet_bytes(frame: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    frame.to_parquet(buf, compression="zstd")
    return buf.getvalue()


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return value.item()  # numpy scalar
        except (AttributeError, ValueError):
            pass
    return value


def month_book(tradebook: pd.DataFrame | None, month: str) -> list[dict[str, Any]]:
    """Every tradebook row of the periods that cover `month`.

    A calendar month runs from the last month-end close on the book held then,
    to the fill, and on the new book after it (docs/TRACK_RECORD.md): so the
    rows of the period in force on the month's first day, and of each period
    that starts inside the month, buys, holds and exits, with prices and weights.
    """
    if tradebook is None or len(tradebook) == 0:
        return []
    tb = tradebook.copy()
    tb["Period Start"] = pd.to_datetime(tb["Period Start"])
    first = pd.Period(month, freq="M").start_time
    last = pd.Period(month, freq="M").end_time
    starts = sorted(tb["Period Start"].dropna().unique())
    # The period in force when the month opened (it ran from before the first day),
    # and every period that starts within the month, a fill on its first day included.
    before = [s for s in starts if s < first]
    keep = set(s for s in starts if first <= s <= last)
    if before:
        keep.add(before[-1])
    rows = tb[tb["Period Start"].isin(keep)]
    cols = [c for c in BOOK_COLUMNS if c in rows.columns]
    out = rows[cols].sort_values(["Period Start", "Symbol", "Action"]).reset_index(drop=True)
    out["Period Start"] = out["Period Start"].dt.strftime("%Y-%m-%d")
    return [_jsonable(r) for r in out.to_dict(orient="records")]


def holdings(book: list[dict[str, Any]]) -> dict[str, list[str]]:
    """{period start: sorted symbols bought or held}: the names a month owned."""
    out: dict[str, set[str]] = {}
    for row in book:
        action = str(row.get("Action", ""))
        if "BUY" in action or "HOLD" in action:
            out.setdefault(str(row["Period Start"]), set()).add(str(row["Symbol"]))
    return {k: sorted(v) for k, v in sorted(out.items())}


def build(*, system: str, month: str, as_of: pd.Timestamp, frame: pd.DataFrame,
          benchmark: pd.Series, membership: dict | None, screener_store: bytes,
          screener_source: str, kwargs: dict[str, Any], sector_map: dict[str, str],
          actions: list, backtest_months: int, cfg: dict[str, Any], fingerprint: str,
          results: dict[str, float | None], book: list[dict[str, Any]],
          code_sha: str) -> bytes:
    """The bundle's bytes. Deterministic: the same inputs give the same sha256."""
    members = {
        "frame.parquet": _parquet_bytes(frame),
        "benchmark.parquet": _parquet_bytes(benchmark.rename("close").to_frame()),
        "membership.json": json.dumps(membership, sort_keys=True, default=str).encode(),
        "screener_store.parquet": bytes(screener_store),
    }
    meta = {
        "bundle_version": BUNDLE_VERSION,
        "system": system,
        "month": month,
        "as_of": pd.Timestamp(as_of).strftime("%Y-%m-%d"),
        "code_sha": code_sha,
        "run_backtest": {
            "kwargs": _jsonable(kwargs),
            # JSON has only lists: the arguments passed as tuples, so replay restores them.
            "tuple_kwargs": sorted(k for k, v in kwargs.items() if isinstance(v, tuple)),
            "sector_map": _jsonable(sector_map),
            "actions": _jsonable(actions),
            "backtest_months": int(backtest_months),
        },
        "config": _jsonable(cfg),
        "fingerprint": fingerprint,
        "results": _jsonable(results),
        "book": book,
        "screener_store": {"source": screener_source, "sha256": _sha(members["screener_store.parquet"]),
                           "bytes": len(members["screener_store.parquet"])},
        "members": {name: _sha(body) for name, body in members.items()},
    }
    members["meta.json"] = json.dumps(meta, sort_keys=True, indent=1, default=str).encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, members[name])
    return buf.getvalue()


def read(data: bytes) -> dict[str, Any]:
    """The bundle's contents; raises if a member's sha256 disagrees with meta.json."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        raw = {name: zf.read(name) for name in zf.namelist()}
    meta = json.loads(raw["meta.json"])
    for name, digest in meta["members"].items():
        if _sha(raw[name]) != digest:
            raise ValueError(f"bundle member {name} does not match its sha256 in meta.json")
    bench = pd.read_parquet(io.BytesIO(raw["benchmark.parquet"]))["close"]
    return {
        "meta": meta,
        "frame": pd.read_parquet(io.BytesIO(raw["frame.parquet"])),
        "benchmark": bench,
        "membership": json.loads(raw["membership.json"]),
        "screener_store": raw["screener_store.parquet"],
    }


def run_kwargs(meta: dict[str, Any]) -> dict[str, Any]:
    """The stored run_backtest keyword arguments, with the tuples restored as passed."""
    kw = dict(meta["run_backtest"]["kwargs"])
    for name in meta["run_backtest"].get("tuple_kwargs", []):
        if isinstance(kw.get(name), list):
            kw[name] = tuple(kw[name])
    return kw


def replay(bundle: dict[str, Any]) -> dict[str, Any]:
    """Re-run the month's run_backtest on the bundle's own inputs.

    Returns the month's strategy and benchmark returns at full precision, the
    ledger's rounded values, and the book, for comparison with what was frozen.
    """
    from src.engine.backtester import run_backtest
    from src.engine.track_record import calendar_month_returns

    meta = bundle["meta"]
    rb = meta["run_backtest"]
    frame_sha = meta["members"]["frame.parquet"][:16]
    result = run_backtest(
        f"freeze_replay_{meta['system']}_{meta['month']}_{frame_sha}",
        bundle["frame"],
        **run_kwargs(meta),
        sector_map=rb["sector_map"],
        _benchmark_close=bundle["benchmark"],
        backtest_months=rb["backtest_months"],
        _membership=bundle["membership"],
        _actions=rb["actions"],
    )
    if result is None:
        raise RuntimeError("the bundle's backtest produced no result")
    period = pd.Period(meta["month"], freq="M")
    strat = calendar_month_returns(result["equity_curve"])
    bench = calendar_month_returns(result["benchmark"])
    s = float(strat.loc[period]) if period in strat.index else None
    b = float(bench.loc[period]) if period in bench.index else None
    return {
        "strategy": s,
        "benchmark": b,
        "ledger": {"strategy": None if s is None else round(s, 6),
                   "benchmark": None if b is None else round(b, 6),
                   "alpha": None if s is None or b is None else round(s - b, 6)},
        "book": month_book(result.get("tradebook"), meta["month"]),
    }


def publish(data: bytes, *, system: str, month: str, code_sha: str, workdir: Path) -> str:
    """Publish the bundle to R2 as an immutable revision; returns its sha256. Raises on failure."""
    from scripts.r2_publish import publish as r2_publish

    path = Path(workdir) / f"freeze_{system}_{month}.zip"
    path.write_bytes(data)
    return r2_publish(path, dataset=dataset(system), source="monthly_track_record",
                      key_root=key_root(system), pipeline_version=f"s185-{code_sha[:12]}",
                      release_tag="none", as_of=month)


def fetch(system: str, month: str) -> bytes:
    """The current bundle of `system`'s `month` from R2. Raises when there is none."""
    from src.storage.r2 import R2Archive, R2Config
    from src.storage.reader import R2DatasetReader

    reader = R2DatasetReader(R2Archive(R2Config.from_env()))
    return reader.read_bytes(reader.resolve_current(dataset(system), as_of=month))


# ── The frozen books in git ─────────────────────────────────────────────────
# data/record_books.json: {system: {month: {as_of, freeze_revision,
# screener_store_sha256, book: [tradebook rows]}}}. Written by the monthly
# freeze beside the ledger, append-only like it: pages and the parity check read
# a month's book here, without R2; the bundle on R2 is the evidence behind it.
BOOKS_PATH = Path(__file__).resolve().parents[2] / "data" / "record_books.json"


def load_books(path: Path = BOOKS_PATH) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def add_book(books: dict[str, Any], *, system: str, month: str, as_of: str,
             freeze_revision: str | None, screener_store_sha256: str,
             book: list[dict[str, Any]], force: bool = False) -> dict[str, Any]:
    """Record one frozen month's book. An existing month is kept unless `force` (a rebuild)."""
    months = books.setdefault(system, {})
    if month in months and not force:
        return books
    months[month] = {"as_of": as_of, "freeze_revision": freeze_revision,
                     "screener_store_sha256": screener_store_sha256, "book": book}
    books[system] = dict(sorted(months.items()))
    return books


def save_books(books: dict[str, Any], path: Path = BOOKS_PATH) -> None:
    Path(path).write_text(json.dumps(dict(sorted(books.items())), indent=1, sort_keys=True,
                                     default=str) + "\n", encoding="utf-8")


def book_differences(stored: list[dict[str, Any]], replayed: list[dict[str, Any]]) -> dict[str, Any]:
    """Names held in one book and not the other, per period start ({} when the same)."""
    a, b = holdings(stored), holdings(replayed)
    out = {}
    for start in sorted(set(a) | set(b)):
        sa, sb = set(a.get(start, [])), set(b.get(start, []))
        if sa != sb:
            out[start] = {"stored_only": sorted(sa - sb), "replay_only": sorted(sb - sa)}
    return out
