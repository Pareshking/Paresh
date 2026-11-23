"""The price frame the backtest and Track Record run on: Screener's closes, with NSE's own
record (then Yahoo) only where Screener has none.

Owner, 2026-10-01: use Screener everywhere, as the live ranking does; NSE or Yahoo only
where Screener has no data. blend_screener() does that; the rest of this module builds the
NSE series that fills the gaps.

Adjusted closes built from NSE's own record, for the fallback.

Raw NSE closes (src/loaders/nse_history.py) adjusted with NSE's own corporate-
action file (src/loaders/nse_adjusted.py: each split or bonus is applied only
where the price actually moved by its factor). Dividends are not folded back in,
so a close is what traded, the way the published ranking read it.

Why this and not Yahoo for a record that claims to be "as it stood": Yahoo
restates. A dividend paid in September lowers every earlier price, and a vendor
correction rewrites months that have closed. NSE's closes are immutable. Ranking
at a past signal date depends only on ratios within the trailing window, so a
series that is correct up to that date gives the same ranking then and now, and
it gives it from facts that were published that day.

In data/nse_prices/:
    closes.parquet   raw closes as NSE filed them (sessions x symbols, EQ before BE)
    actions.parquet  its split/bonus/consolidation/demerger/rights rows, one per action
    notes.json       ticker renames and one-off corrections, each with its evidence
scripts/sync_nse_prices.py builds and extends them.

The closes are not in git (owner, 21 Nov 2026, TODO S178: each monthly rewrite
added ~1.3 MB to the repository's history). They are published monthly to R2
(CLOSES_DATASET) and the data-latest release (CLOSES_ASSET); closes_path()
reads a local file when a job has just written one, else the published copy.

The published copy is kept on disk for as long as it IS the published copy,
not for a fixed time (TODO S210). Until 23 Nov 2026 a copy under a day old
was used without asking: the nightly job restored a 14-hour-old copy from its
Actions cache, ranked on it after the closes had been republished, and
production, holding the new copy, rejected the precomputed table on every
boot ("price_fingerprint differs") and ranked live instead.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from src.loaders import nse_adjusted as na

DIR = Path(__file__).resolve().parents[2] / "data" / "nse_prices"
CLOSES_FILE = "closes.parquet"
# Where the monthly job publishes the closes (monthly_track_record.yml). Under
# nse/, so r2_retention.py protects every copy (PROTECTED_DATASETS).
CLOSES_DATASET = "nse/closes_2y"
CLOSES_ASSET = "nse_closes.parquet"
CLOSES_CACHE_NAME = "nse_prices_closes.parquet"
# A running process asks which revision is published at most this often. A
# job is a new process and always asks; the app picks a republish up within
# ten minutes. The question is a pointer read (R2) or a one-byte GET (release).
CLOSES_RECHECK_S = 600
# The answer we cannot get (R2 and the release both unreachable): a copy this
# young is used as it is, an older one too, but with a warning (never None).
CLOSES_CACHE_TTL_S = 24 * 3600
_CLOSES_LOCK = threading.Lock()
# cache path -> (time of the last check, the revision found)
_CLOSES_CHECKED: dict[str, tuple[float, str]] = {}
BASIS = "nse_as_published"
BASIS_SCREENER = "screener_primary"
# face_value prices a rights issue (nse_adjusted._rights: issue price = face value
# + premium). A file written before it was kept reads it as missing (S56).
ACTION_COLS = ["symbol", "series", "kind", "ex_date", "purpose", "price_factor", "face_value"]


# ── reading what is committed ────────────────────────────────────────────────

def _readable(path: Path) -> bool:
    try:
        frame = pd.read_parquet(path)
    except Exception:  # noqa: BLE001
        return False
    return not frame.empty


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _revision_file(cache: Path) -> Path:
    return cache.with_name(cache.name + ".revision")


def _held_revision(cache: Path) -> str | None:
    """The revision the copy on disk is: its SHA-256, or the release ETag it was saved with."""
    try:
        return _revision_file(cache).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _save(cache: Path, body: bytes, revision: str) -> bool:
    """Write `body` over the copy, with the revision it is. False if it is not a readable frame."""
    cache.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=cache.parent, suffix=".part")
    with os.fdopen(fd, "wb") as fh:
        fh.write(body)
    if not _readable(Path(tmp)):
        os.unlink(tmp)
        return False
    os.replace(tmp, cache)
    _revision_file(cache).write_text(revision, encoding="utf-8")
    return True


def _r2_reader():
    """The manifest-checked R2 reader, or None when no R2 keys are configured."""
    from src.loaders import app_source

    config = app_source.r2_config()
    return None if config is None else app_source.R2DatasetReader(app_source.R2Archive(config))


def _from_r2(cache: Path) -> tuple[str, Path | None] | None:
    """(current revision, the copy at that revision) from R2, or None when R2 cannot answer.

    The pointer names the revision by its SHA-256, so a copy on disk with that
    SHA-256 is that revision and is kept; anything else is replaced. The
    object is read only when the copy is not it (R2DatasetReader checks size
    and SHA-256 before a byte is returned).
    """
    from src.loaders import app_source

    try:
        reader = _r2_reader()
        if reader is None:
            return None
        ref = reader.resolve_current(CLOSES_DATASET)
        if cache.exists() and _held_revision(cache) == ref.revision_sha256 \
                and _sha256(cache) == ref.revision_sha256:
            return ref.revision_sha256, cache
        body = reader.read_bytes(ref)
    except Exception as exc:  # noqa: BLE001  the release is the fallback
        from src.core.logger import logger

        logger.info("NSE closes not read from R2 (%s); trying the release.", type(exc).__name__)
        return None
    if not _save(cache, body, ref.revision_sha256):
        return None
    app_source.record("nse_closes", "r2")
    _log_revision("r2", ref.revision_sha256, ref.as_of)
    return ref.revision_sha256, cache


def _from_release(cache: Path) -> tuple[str, Path | None] | None:
    """(current revision, the copy at that revision) from the release, or None when it cannot answer.

    The revision is the asset's ETag, asked for with a one-byte ranged GET (the
    signed URL GitHub redirects a release download to refuses HEAD with 401;
    measured 23 Nov 2026, the 206 carries the full download's ETag). The asset
    is downloaded only when the copy on disk was saved under another ETag.
    """
    import requests

    from src.core.config import NSE_LONG_BASE_URL
    from src.loaders import app_source

    url = f"{NSE_LONG_BASE_URL}/{CLOSES_ASSET}"
    try:
        probe = requests.get(url, headers={"Range": "bytes=0-0"}, timeout=30, stream=True)
        try:
            etag = probe.headers.get("ETag", "").strip() if probe.status_code in (200, 206) else ""
        finally:
            probe.close()
        if etag and cache.exists() and _held_revision(cache) == f"release:{etag}":
            return f"release:{etag}", cache
        resp = requests.get(url, timeout=60)
        if resp.status_code != 200:
            return None
        revision = f"release:{resp.headers.get('ETag', '').strip() or etag or _sha_of(resp.content)}"
        if not _save(cache, resp.content, revision):
            return None
    except Exception:  # noqa: BLE001  a held copy beats none
        return None
    app_source.record("nse_closes", "release")
    _log_revision("release", revision, None)
    return revision, cache


def _sha_of(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _log_revision(source: str, revision: str, as_of: str | None) -> None:
    from src.core.logger import logger

    logger.info("NSE closes: revision %s from %s%s", revision[:16], source,
                f" (as of {as_of})" if as_of else "")


def _published_closes(cache_dir: Path | str | None = None, *,
                      now: float | None = None) -> Path | None:
    """The published closes on disk, at the revision published NOW; None if there is none.

    R2's current revision when R2 is configured, else the release's. The copy on
    disk is kept while it is that revision and replaced as soon as it is not,
    whatever its age. A running process asks at most every CLOSES_RECHECK_S.
    When neither can be asked, the copy on disk is used as it is, logged as
    unchecked. Never raises.
    """
    from src.core.config import DATA_DIR

    cache = Path(cache_dir or DATA_DIR) / CLOSES_CACHE_NAME
    now = time.time() if now is None else now
    key = str(cache.resolve())
    with _CLOSES_LOCK:
        checked = _CLOSES_CHECKED.get(key)
        if (checked is not None and cache.exists() and now - checked[0] < CLOSES_RECHECK_S
                and _held_revision(cache) == checked[1]):
            return cache
        found = _from_r2(cache) or _from_release(cache)
        if found is not None:
            _CLOSES_CHECKED[key] = (now, found[0])
            return found[1]
        _CLOSES_CHECKED.pop(key, None)
        if not cache.exists():
            return None
        from src.core.logger import logger

        age_h = (now - cache.stat().st_mtime) / 3600
        (logger.info if age_h * 3600 < CLOSES_CACHE_TTL_S else logger.warning)(
            "NSE closes: neither R2 nor the release answered; using the copy on disk "
            "(%.0f h old, revision %s) unchecked.", age_h, (_held_revision(cache) or "unknown")[:16])
        return cache


def closes_path(directory: Path | str = DIR) -> Path | None:
    """The two-year NSE closes on disk, or None.

    The file in `directory` when there is one (a test's folder, or a job that has
    just written it); otherwise, for the repository's own folder only, the
    published copy (_published_closes). Another folder never fetches.
    """
    local = Path(directory) / CLOSES_FILE
    if local.exists():
        return local
    if Path(directory).resolve() != DIR.resolve():
        return None
    return _published_closes()


def load(directory: Path = DIR) -> dict[str, Any] | None:
    """{"closes", "actions", "notes"} or None when nothing is committed."""
    directory = Path(directory)
    path = closes_path(directory)
    if path is None:
        return None
    try:
        closes = pd.read_parquet(path)
        actions = pd.read_parquet(directory / "actions.parquet")
        notes = json.loads((directory / "notes.json").read_text())
    except (OSError, ValueError):
        return None
    closes.index = pd.DatetimeIndex(closes.index)
    actions = actions.reindex(columns=list(dict.fromkeys([*ACTION_COLS, *actions.columns])))
    return {"closes": closes.astype(float), "actions": actions, "notes": notes}


def _target(a: Any) -> str:
    return a["new_symbol"] if isinstance(a, dict) else str(a)


def chain_symbols(close: pd.DataFrame, renames: dict[str, Any] | None,
                  skipped: list[str] | None = None,
                  landed: dict[str, str] | None = None) -> pd.DataFrame:
    """Join a renamed stock's NSE series into one, under its current symbol.

    NSE files the days before a ticker change under the old symbol and the days
    after under the new one. `renames` is {old: {"new_symbol": new, ...}}, each
    old symbol pointing at the last ticker of its chain. A chain is joined one
    step at a time, each old series onto the one that began where it ended
    (SESAGOA -> SSLT -> VEDL), latest step first, so each step is checked
    against its own successor, not a ticker that began years later. An entry
    marked "auto" (src/loaders/nse_identity.py) is joined only where the two
    series meet -- see continuous(); the others are appended to `skipped`.
    `landed`, when given, receives {old: the column it was joined into}, for
    joining another field the same way (join_landed).
    """
    out = close.copy()
    land: dict[str, str] = {} if landed is None else landed
    groups: dict[str, list[str]] = {}
    for old, a in (renames or {}).items():
        new = _target(a)
        if old in out.columns and old != new:
            groups.setdefault(new, []).append(old)
    for new, olds in groups.items():
        span = {s: (out[s].first_valid_index(), out[s].last_valid_index()) for s in olds}
        olds = [s for s in olds if span[s][0] is not None]
        if not olds:
            continue
        if new not in out.columns:            # no series under the new ticker: the latest old one is it
            last = max(olds, key=lambda s: span[s][0])
            out = out.rename(columns={last: new})
            land[last] = new
            olds.remove(last)
        span[new] = (out[new].first_valid_index(), out[new].last_valid_index())
        members = [*olds, new]
        for old in sorted(olds, key=lambda s: span[s][1], reverse=True):
            # Its successor: the member whose series begins first after this one ends.
            ends = span[old][1] - pd.Timedelta(days=5)
            later = [m for m in members if m != old and span[m][0] is not None and span[m][0] > ends]
            nxt = min(later, key=lambda m: span[m][0]) if later else new
            while nxt in land:
                nxt = land[nxt]
            a = renames[old]
            if isinstance(a, dict) and a.get("auto"):
                why = continuous(out[old], out[nxt])
                if why:
                    if skipped is not None:
                        skipped.append(f"{old}->{nxt}: {why}")
                    continue
            out[nxt] = out[nxt].combine_first(out[old])
            out = out.drop(columns=[old])
            land[old] = nxt
    return out


def landed_in(landed: dict[str, str], sym: str) -> str:
    """The column `sym` ended up in after chain_symbols."""
    seen = set()
    while sym in landed and sym not in seen:
        seen.add(sym)
        sym = landed[sym]
    return sym


def join_landed(frame: pd.DataFrame, landed: dict[str, str], *, product: bool = False) -> pd.DataFrame:
    """Join `frame`'s columns as chain_symbols joined the closes (its `landed` map).

    product=True multiplies (adjustment factors: the new symbol's later splits
    reach back into the old symbol's years); otherwise the old values fill in.
    """
    # Columns in a dict, one frame at the end: inserting and dropping columns
    # one by one fragmented the frame (pandas PerformanceWarning on every
    # production run, 7 Nov). Same columns, same order, same values.
    cols = {c: frame[c] for c in frame.columns}
    for old in landed:
        if old not in cols:
            continue
        to = landed_in(landed, old)
        if to not in cols:
            cols[to] = cols[old]
        elif product:
            cols[to] = cols[to].fillna(1.0) * cols[old].fillna(1.0)
        else:
            cols[to] = cols[to].combine_first(cols[old])
        del cols[old]
    return pd.DataFrame(cols, index=frame.index, columns=list(cols)) if cols else frame.iloc[:, :0].copy()


def chain_raw(close: pd.DataFrame, factors: pd.DataFrame, renames: dict[str, Any] | None,
              skipped: list[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(raw closes joined across renames, their factors joined the same way).

    Joined before any adjustment, so a split or bonus filed under the new
    symbol reaches back into the old symbol's years (INFOSYSTCH -> INFY: three
    later 1:1 bonuses read as an 87% fall and refused the join, so INFY began
    in June 2011).
    """
    landed: dict[str, str] = {}
    raw = chain_symbols(close, renames, skipped, landed)
    return raw, join_landed(factors.reindex(index=close.index), landed, product=True)


def continuous(old: pd.Series, new: pd.Series) -> str:
    """Why `old` does not run on into `new` ("" when it does): the last old
    session and the first new one at most MAX_GAP_DAYS apart, the close
    within MAX_JUMP across the join. A company whose equity was extinguished
    in insolvency keeps its issuer code but not its price."""
    from src.loaders.nse_identity import MAX_GAP_DAYS, MAX_JUMP

    o, n = old.dropna(), new.dropna()
    if o.empty or n.empty:
        return ""
    after = n[n.index > o.index[-1]]
    if after.empty:
        return "the new symbol has no session after the old one's last"
    gap = (after.index[0] - o.index[-1]).days
    if gap > MAX_GAP_DAYS:
        return f"{gap} days between the series"
    jump = after.iloc[0] / o.iloc[-1] - 1
    if abs(jump) > MAX_JUMP:
        return f"price moves {jump:+.0%} across the join"
    return ""


def correct(close: pd.DataFrame, corrections: Iterable[dict[str, Any]] | None) -> pd.DataFrame:
    """Apply recorded one-off factors: every close before `before` times `factor`.

    For an action NSE's file never listed (each entry carries its evidence).
    """
    out = close.copy()
    for c in corrections or []:
        if c["symbol"] in out.columns:
            out.loc[out.index < pd.Timestamp(c["before"]), c["symbol"]] *= float(c["factor"])
    return out


def uncovered(corrections: Iterable[dict[str, Any]] | None, factors: pd.DataFrame,
              renames: dict[str, Any] | None, days: int = 3
              ) -> tuple[list[dict[str, Any]], list[str]]:
    """(the corrections no applied action already covers, those it does).

    A correction stands in for an action NSE's file never listed. Once a list
    does carry it, both applied: SHRIRAMFIN's 1:5 split of 2025-01-10, in
    notes.json and then in NSE's yearly list, left every earlier close at a
    twenty-fifth (audit against Yahoo, 2026-10-03). A correction is skipped
    when the stock (or a symbol it was renamed from) has an applied factor
    within `days` of its date.
    """
    back: dict[str, set[str]] = {}
    for old, a in (renames or {}).items():
        back.setdefault(a["new_symbol"] if isinstance(a, dict) else a, set()).add(old)
    keep, skipped = [], []
    for c in corrections or []:
        names = {c["symbol"]} | back.get(c["symbol"], set())
        day = pd.Timestamp(c["before"])
        window = factors.loc[day - pd.Timedelta(days=days): day + pd.Timedelta(days=days)]
        cols = [n for n in names if n in window.columns]
        if cols and (window[cols].fillna(1.0) != 1.0).to_numpy().any():
            skipped.append(f"{c['symbol']} {c['before']}")
        else:
            keep.append(c)
    return keep, skipped


def on_trading_symbol(actions: pd.DataFrame, closes: pd.DataFrame,
                      renames: dict[str, Any] | None, days: int = 10) -> pd.DataFrame:
    """Each action filed under the symbol that traded on its ex-date.

    NSE's corporate-action list files old actions under today's symbol:
    TATACONSUM's 2010 split, when the stock traded as TATAGLOBAL; ZYDUSLIFE's
    2015 split (CADILAHC); UNITDSPR's 2018 split (MCDOWELL-N). Matched against
    the price of a symbol that did not exist yet, the action found no price
    and was never applied -- the series then joined across the rename with
    the split's fall still in it (audit against Yahoo, 2026-10-03). An action
    whose symbol has no close in the `days` before its ex-date moves to the
    predecessor (following rename chains back) that has one.
    """
    if actions is None or actions.empty or not renames:
        return actions
    back: dict[str, list[str]] = {}
    for old, a in renames.items():
        new = a["new_symbol"] if isinstance(a, dict) else a
        back.setdefault(new, []).append(old)
    have = closes.notna()
    idx = closes.index

    def traded(sym: str, ex: pd.Timestamp) -> bool:
        if sym not in have.columns:
            return False
        lo, hi = idx.searchsorted(ex - pd.Timedelta(days=days)), idx.searchsorted(ex)
        return bool(have[sym].iloc[lo:hi].any())

    out = actions.copy()
    ex_dates = pd.to_datetime(out["ex_date"], errors="coerce")
    for i, (sym, ex) in enumerate(zip(out["symbol"], ex_dates)):
        if pd.isna(ex) or sym not in back or traded(sym, ex):
            continue
        seen, todo = {sym}, list(back[sym])
        while todo:
            old = todo.pop(0)
            if old in seen:
                continue
            seen.add(old)
            if traded(old, ex):
                out.iat[i, out.columns.get_loc("symbol")] = old
                break
            todo += back.get(old, [])
    return out


def adjusted_close(closes: pd.DataFrame, actions: pd.DataFrame, symbols: Iterable[str],
                   *, notes: dict[str, Any] | None = None
                   ) -> tuple[pd.DataFrame, dict[str, Any]]:
    """(adjusted closes for `symbols`, a report of what was and was not found)."""
    notes = notes or {}
    # Renames: NSE's symbol-change list and ISINs (nse_identity), each joined
    # only where the series meet; the ledger in notes.json overrides them.
    from src.loaders.nse_identity import auto_renames

    renames = {**auto_renames(set(closes.columns)), **(notes.get("renames") or {})}
    moved = on_trading_symbol(actions, closes, renames)
    actions_moved = int((moved["symbol"] != actions["symbol"]).sum()) if len(actions) else 0
    factors, verdicts = na.action_factors(closes, moved)
    factors.index = closes.index
    not_joined: list[str] = []
    landed: dict[str, str] = {}
    raw = chain_symbols(closes, renames, not_joined, landed)
    joined = join_landed(factors, landed, product=True)
    close = na.adjust(raw, joined)
    corrections, superseded = uncovered(notes.get("corrections"), joined, renames)
    close = correct(close, corrections)
    wanted = list(dict.fromkeys(symbols))
    # A name asked for by its old symbol gets the joined series of its successor.
    for s in wanted:
        succ = landed_in(landed, s)
        if s not in close.columns and succ in close.columns:
            close[s] = close[succ]
    cols = [s for s in wanted if s in close.columns and close[s].notna().sum() > 0]
    out = close[cols].sort_index().astype("float32")
    report = {
        "symbols_wanted": len(wanted),
        "symbols_priced": len(cols),
        "unpriced": sorted(set(wanted) - set(cols)),
        "sessions": int(len(out)),
        "first_session": str(out.index[0].date()) if len(out) else None,
        "last_session": str(out.index[-1].date()) if len(out) else None,
        "corporate_action_steps": int(len(na.events(factors))),
        "rights_issues": verdicts.loc[verdicts["kind"] == "rights", "verdict"].value_counts().to_dict(),
        "actions_moved_to_old_symbol": actions_moved,
        "corrections_superseded_by_an_action": superseded,
        "renames_joined": len(landed),
        "renames_not_joined": not_joined,
        "renames_landed": dict(sorted(landed.items())),
    }
    return out, report


# ── the frame the engine runs on ─────────────────────────────────────────────

def _carry_forward(base: pd.DataFrame, other: pd.DataFrame) -> pd.DataFrame:
    """Continue `base` past its last session with `other`'s day-to-day moves.

    The committed file is refreshed monthly; between refreshes the sessions it
    lacks are carried forward on the other source's returns, which differ from
    NSE's only by a dividend, if one fell in the gap.
    """
    last = base.index[-1]
    tail = other.index[other.index > last]
    if not len(tail):
        return base
    ref = other.index[other.index <= last]
    if not len(ref):
        return base
    growth = other.loc[tail].div(other.loc[ref[-1]])
    start = base.loc[last].reindex(growth.columns)
    return pd.concat([base, growth.mul(start, axis=1).reindex(columns=base.columns)])


_STORE_TTL_S = 3600
_store_memo: dict[str, Any] = {"at": 0.0, "frame": None}


def screener_store() -> pd.DataFrame | None:
    """The published Screener history, memoised for an hour. None if unreachable.

    The app's own copy first (screener_cache: the configured R2 pin, read once
    per process), so the basis frame prices from the revision the ranking
    uses and the store is not downloaded and held twice (A2, 8 Nov: a cold
    Backtest page read it in both places, ~1 s each; S63 is the same fault in
    the track-record comparison). Outside the app, or when that read fails,
    the release copy as before.
    """
    import time

    now = time.time()
    if _store_memo["frame"] is not None and now - _store_memo["at"] < _STORE_TTL_S:
        return _store_memo["frame"]
    frame = None
    try:
        from src.loaders import screener_cache

        frame, _ = screener_cache.configured()
    except Exception:  # noqa: BLE001  the release copy below
        frame = None
    if frame is None:
        try:
            from src.loaders import price_source

            frame = price_source.fetch_screener_store()
        except Exception:  # noqa: BLE001  the caller falls back to NSE's own closes
            frame = None
    if frame is not None:
        _store_memo.update(at=now, frame=frame)
    return frame


def blend_screener(base: pd.DataFrame, store: pd.DataFrame | None, extra: Iterable[str] = ()
                   ) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Screener's closes wherever it has one; `base` (NSE's, adjusted) only where it has none.

    Screener's store is daily for the last year or so and sparser before it, and it lacks
    a few stocks outright (ones that merged away). A date or a stock Screener does not
    cover is filled from `base` scaled to Screener's own level at the nearest date it does
    hold for that stock (the ratio is constant between corporate-action restatements), so
    the series is one continuous line on Screener's basis and no step appears at a seam.
    A stock Screener has never held stays on `base`; one `base` lacks that Screener holds
    (`extra`, e.g. a REIT outside NSE's equity series) is taken from Screener whole.
    """
    if store is None or store.empty or not isinstance(store.columns, pd.MultiIndex):
        return base, {"screener": False}
    try:
        close = store.xs("Close", axis=1, level=-1)
    except Exception:  # noqa: BLE001
        return base, {"screener": False}
    close.index = pd.DatetimeIndex(close.index).normalize()
    close = close[~close.index.duplicated(keep="last")]
    cols = [c for c in base.columns if c in close.columns and close[c].notna().any()]
    if not cols:
        return base, {"screener": False}
    shared = close[cols].reindex(base.index)
    n = base[cols].astype(float)
    ratio = (shared / n).where(lambda r: (r > 0) & np.isfinite(r))
    scaled = n * ratio.ffill().bfill()
    out = shared.where(shared.notna(), scaled).combine_first(n)
    result = base.astype(float).copy()
    result[cols] = out
    only = [c for c in dict.fromkeys(extra) if c not in base.columns and c in close.columns
            and close[c].notna().any()]
    if only:
        result = pd.concat([result, close[only].reindex(base.index).astype(float)], axis=1)
    from_screener = float(shared.notna().to_numpy().sum()) / max(int(n.notna().to_numpy().sum()), 1)
    report = {
        "screener": True,
        "screener_names": len(cols),
        "screener_only_names": sorted(only),
        "base_only_names": sorted(set(base.columns) - set(cols)),
        "share_of_cells_from_screener": round(from_screener, 3),
        "screener_last_date": str(close.index[-1].date()),
    }
    return result.astype("float32"), report


# basis_frame is called on every Portfolio, Actions and Backtest render (twice on
# Portfolio: the book and the month-to-date) and rebuilt the same frame from the
# committed NSE file each time: ~1.5 s of a warm Portfolio render (audit A1,
# 7 Nov 2026). The memo key holds everything the result depends on, so any change
# -- the NSE files, the price frame, the membership, the window, the Screener
# store -- misses and recomputes. A hit hands back a copy: no caller can alter
# the memo. Two entries: one per live system a reader is likely to switch between.
_BASIS_MEMO: "OrderedDict[tuple, tuple[pd.DataFrame | None, dict[str, Any], Any]]" = OrderedDict()
_BASIS_MEMO_SIZE = 2
_BASIS_LOCK = threading.Lock()


def _file_stamp(directory: Path) -> tuple:
    stamp = []
    for name in (CLOSES_FILE, "actions.parquet", "notes.json"):
        try:
            path = closes_path(directory) if name == CLOSES_FILE else Path(directory) / name
            if path is None:
                raise OSError(name)
            st = path.stat()
            stamp.append((name, st.st_mtime_ns, st.st_size))
        except OSError:
            stamp.append((name, None, None))
    return tuple(stamp)


def _basis_key(other: pd.DataFrame, history: dict | None, months: int, directory: Path,
               until: pd.Timestamp | None) -> tuple:
    from src.engine.pipeline import price_fingerprint

    hist = hashlib.sha256(json.dumps(history, sort_keys=True, default=str).encode()).hexdigest()
    return (str(Path(directory).resolve()), _file_stamp(directory), price_fingerprint(other),
            tuple(map(str, other.columns)), hist, int(months),
            None if until is None else str(pd.Timestamp(until)))


def _copy_result(frame: pd.DataFrame | None, report: dict[str, Any]
                 ) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    return (None if frame is None else frame.copy()), copy.deepcopy(report)


def basis_frame(other: pd.DataFrame, history: dict | None, *, months: int,
                directory: Path = DIR, until: pd.Timestamp | None = None,
                screener: pd.DataFrame | str | None = "auto") -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """basis_frame_uncached, memoised; see _BASIS_MEMO. Same arguments, same result."""
    if other is None or other.empty:
        return _basis_frame_uncached(other, history, months=months, directory=directory,
                                     until=until, screener=screener)
    store = screener_store() if isinstance(screener, str) and screener == "auto" else screener
    try:
        key = _basis_key(other, history, months, directory, until)
    except Exception:  # noqa: BLE001  an unhashable input: compute, never fail on the memo
        return _basis_frame_uncached(other, history, months=months, directory=directory,
                                     until=until, screener=store)
    with _BASIS_LOCK:
        hit = _BASIS_MEMO.get(key)
        # The store is compared by identity: a refreshed store is a new object.
        if hit is not None and hit[2] is store:
            _BASIS_MEMO.move_to_end(key)
            return _copy_result(hit[0], hit[1])
    frame, report = _basis_frame_uncached(other, history, months=months, directory=directory,
                                          until=until, screener=store)
    with _BASIS_LOCK:
        _BASIS_MEMO[key] = (frame, report, store)
        _BASIS_MEMO.move_to_end(key)
        while len(_BASIS_MEMO) > _BASIS_MEMO_SIZE:
            _BASIS_MEMO.popitem(last=False)
    return _copy_result(frame, report)


def _basis_frame_uncached(other: pd.DataFrame, history: dict | None, *, months: int,
                          directory: Path = DIR, until: pd.Timestamp | None = None,
                          screener: pd.DataFrame | str | None = "auto"
                          ) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """The record's price frame: NSE as published, for the 750 and the names it dropped.

    `other` is the alternative source's adjusted closes (Yahoo's); it fills the
    few names NSE's equity series does not carry (REITs), extends the frame to
    its last session and supplies a symbol's history from before it joined NSE's
    file. Returns (None, {...}) when no NSE file is committed or it does not
    reach back far enough for a `months`-month study with a 12-month formation
    window, and the caller keeps `other`.

    The frame runs to NSE's last session on file, or `other`'s if that is later.
    Callers count completed months back from the END of the frame they receive, so
    one that fixed `months` against `other` passes `until=other.index[-1]` to keep
    the two ends the same; the record's own runs take the later end, so a month
    closes the day NSE's first session of the next one is on file.
    """
    from src.loaders import former_members

    data = load(directory)
    if data is None or other is None or other.empty:
        return None, {"used": False, "why": "no NSE price file is committed"}
    core = list(other.columns)
    symbols = core + [s for s in former_members.symbols_needed(history, core) if s not in set(core)]
    nse, report = adjusted_close(data["closes"], data["actions"], symbols, notes=data["notes"])
    if nse.empty:
        return None, {"used": False, "why": "no symbol could be priced from NSE"}
    as_of = pd.Timestamp(other.index[-1])
    need_from = as_of - pd.DateOffset(months=months + 12) - pd.Timedelta(days=10)
    if pd.Timestamp(nse.index[0]) > need_from:
        return None, {"used": False, "why": (
            f"NSE file starts {nse.index[0]:%d %b %Y}; a {months}-month study needs "
            f"{need_from:%d %b %Y}")}

    frame = _carry_forward(nse.astype(float), other.astype(float).reindex(columns=nse.columns))
    if until is not None:
        frame = frame.loc[: pd.Timestamp(until)]
    # Screener first, as on the live ranking page: NSE's closes only fill what Screener lacks.
    store = screener_store() if isinstance(screener, str) and screener == "auto" else screener
    frame, blend = blend_screener(frame, store if isinstance(store, pd.DataFrame) else None, extra=core)
    # Names NSE's equity series lacks, and names that joined its file after the
    # window began: the other source, joined at the first NSE session by level.
    filled, joined = [], []
    first = nse.index[0]
    for s in core:
        o = other[s].dropna() if s in other.columns else pd.Series(dtype=float)
        if s not in frame.columns:
            if len(o):
                frame[s] = o.reindex(frame.index)
                filled.append(s)
            continue
        have = frame[s].dropna()
        early = o[(o.index >= first) & (o.index < have.index[0])] if len(have) else o
        if len(have) and have.index[0] > first + pd.Timedelta(days=10) and len(early) \
                and have.index[0] in o.index:
            early = early.reindex(frame.index).dropna()
            # float32 column, float64 values: pandas refuses the lossy set.
            frame.loc[early.index, s] = (
                (early * (have.iloc[0] / o.loc[have.index[0]])).astype(frame[s].dtype))
            joined.append(s)
    frame = frame.sort_index().astype("float32")
    report.update(blend)
    report.update(used=True, basis=BASIS_SCREENER if blend.get("screener") else BASIS,
                  last_session_on_file=str(nse.index[-1].date()),
                  other_source_names=sorted(filled), other_source_history=sorted(joined),
                  frame_last_session=str(frame.index[-1].date()))
    return frame, report


def middle_close(symbols: Iterable[str]) -> pd.DataFrame | None:
    """NSE's adjusted closes for `symbols`: the middle price source.

    Screener -> NSE -> Yahoo (owner, 2026-09-27; adopted 2026-10-02). Reads the
    committed data/nse_prices copy. Anything missing or unreadable returns None,
    and the caller falls back to the Screener -> Yahoo order: a middle source
    must never be able to take the app down.
    """
    try:
        data = load()
        if data is None:
            return None
        out, _report = adjusted_close(data["closes"], data["actions"], symbols,
                                      notes=data["notes"])
    except Exception:
        return None
    return out if not out.empty else None
