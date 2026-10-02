"""Three price sources checking each other, with NSE's own record as the judge.

Owner, 2026-10-02: every adjustment automatic, no manual work. SS is the
primary source (daily OHLCV, splits and bonuses already adjusted); Screener
and NSE's own closes are the other two voices. Pure functions; the nightly
report is scripts/reconcile_report.py.

1. RIGHTS ISSUES. NSE's closes never adjust for a rights issue; SS usually
   does (8 of 10 in 2025-26, measured against NSE), Screener sometimes.
   NSE's corporate-action file states the terms ("RIGHTS 3:25@PRM RS 1799"),
   so the factor is computed, not guessed:

       factor = (held * cum + new * issue) / ((held + new) * cum)

   where cum is the last close before the ex-date and issue is the issue
   price (face value plus the premium). Every price before the ex-date is
   multiplied by it -- in SS only where NSE's raw ex-date move shows SS left
   the issue raw (ss_basis); otherwise SS is kept and NSE brought to SS's basis.
   ADANIENT, ex 2025-11-17: 3 new for 25 held at Rs 1,800
   on a cum close of Rs 2,516.80 gives 0.96948 -- exactly the 3.15% by which
   Screener's history sat below SS's. An issue priced at or above the cum
   close transfers no value and is left alone. A face value the caller does
   not know is inferred from the factor SS or Screener applied (Rs 1, 2, 5
   or 10), else taken as Re 1.

2. THE VOTE. On every (stock, session) the three sources' one-day moves are
   compared. All within VOTE_TOLERANCE: agreed. Two agree and one does not:
   the majority's move is used and the odd source is named. All three
   differ: NSE's move is used (it is the exchange's own record) and the case
   is flagged. Two sources only: agreement or a flag, NSE's move used when it
   is one of them. Two sources without NSE that differ by more than
   GROSS_DISAGREEMENT: the smaller move is used, and the case is flagged.

3. THE RECONCILED SERIES starts from SS and chains, session by session, the
   move the vote settled on, so a bad SS tick is replaced by the majority's
   move and SS's level is kept everywhere else. A session SS lacks is filled
   the same way from the others.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

VOTE_TOLERANCE = 0.005      # one-day moves within half a percentage point agree
DRIFT_TOLERANCE = 0.005     # a level ratio that moves this much is a basis change
DEFAULT_FACE_VALUE = 1.0
STANDARD_FACE_VALUES = (1.0, 2.0, 5.0, 10.0)
JUDGE = "nse"
# Two sources only, no judge, a day's moves this far apart: one of them has
# mishandled a corporate action (SS divided TVSHLTD by 47 for a preference-
# share bonus, Sep 2026). The smaller move is the one without the error.
GROSS_DISAGREEMENT = 0.20

_RIGHTS = re.compile(
    r"RIGHTS?\s*(?P<new>\d+(?:\.\d+)?)\s*:\s*(?P<held>\d+(?:\.\d+)?)"
    r"\s*(?:@|AT)?\s*(?:A\s+)?(?P<prm>PRM|PREM(?:IUM)?)?\.?\s*(?:OF\s+)?"
    r"(?:RS|RE|INR)?\.?\s*(?P<price>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


# ── Rights issues ────────────────────────────────────────────────────────────

def parse_rights(purpose: str) -> dict | None:
    """{"new", "held", "price", "premium"} from NSE's purpose text, or None.

    "premium" is True when the stated price is a premium over face value
    ("@PRM RS 1799"), False when it is the issue price itself ("@ RS 120").
    """
    m = _RIGHTS.search(str(purpose or ""))
    if not m:
        return None
    new, held, price = float(m["new"]), float(m["held"]), float(m["price"])
    if new <= 0 or held <= 0 or price < 0:
        return None
    return {"new": new, "held": held, "price": price, "premium": bool(m["prm"])}


def rights_factor(new: float, held: float, issue_price: float, cum_close: float) -> float:
    """The multiplier for every price before the ex-date (1.0: nothing to adjust)."""
    if cum_close <= 0 or issue_price >= cum_close:
        return 1.0
    return (held * cum_close + new * issue_price) / ((held + new) * cum_close)


# How SS's ex-date move sits against NSE's raw move (log gap), per rights issue.
BASIS_TOLERANCE = 0.003     # SS and NSE closes match to the paisa; this is noise


def _ex_move(closes: pd.DataFrame | None, sym: str, ex: pd.Timestamp) -> float:
    """log(close on the ex-date / last close before it), NaN when not both held."""
    if closes is None or sym not in closes.columns:
        return np.nan
    c = closes[sym].dropna()
    before, on = c.loc[:ex - pd.Timedelta(days=1)], c.loc[ex:ex]
    if before.empty or on.empty or before.iloc[-1] <= 0:
        return np.nan
    return float(np.log(on.iloc[0] / before.iloc[-1]))


def ss_basis(gap: float, factor: float, tolerance: float = BASIS_TOLERANCE) -> str:
    """Whether SS already adjusted a rights issue, from its ex-date gap to NSE raw.

    NSE's closes never adjust rights. SS's ex-date move equal to NSE's (gap 0):
    SS left it raw. Gap equal to -log(factor): SS applied the same factor. Any
    other gap: SS applied a factor of its own. No NSE close: unknown.
    """
    if pd.isna(gap):
        return "unknown"
    if abs(gap) <= tolerance:
        return "raw"
    if abs(gap + np.log(factor)) <= max(tolerance, 0.15 * abs(np.log(factor))):
        return "adjusted"
    return "own_factor"


def _infer_face_value(terms: dict, cum: float, observed: float,
                      tolerance: float = BASIS_TOLERANCE) -> float | None:
    """The standard face value at which the terms give the factor a source applied.

    A premium is quoted over face value, which NSE's file does not state. SS
    (and Screener) adjust with the true one: UTKARSHBNK, TIL and RELTD (2025-26)
    match their factors to four places at Rs 10, not at the Re 1 default.
    """
    if not terms["premium"] or not (0 < observed < 1):
        return None
    best = min(STANDARD_FACE_VALUES, key=lambda fv: abs(np.log(rights_factor(
        terms["new"], terms["held"], terms["price"] + fv, cum)) - np.log(observed)))
    f = rights_factor(terms["new"], terms["held"], terms["price"] + best, cum)
    return best if abs(np.log(f) - np.log(observed)) <= tolerance else None


def rights_events(actions: pd.DataFrame, closes: pd.DataFrame,
                  face_values: dict[str, float] | None = None,
                  check: pd.DataFrame | None = None,
                  raw: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per rights issue in `closes` (SS's), and whether to adjust it.

    `actions` are NSE corporate-action rows (symbol, ex_date, purpose); `raw`
    NSE's closes, which never adjust rights: the cum close is read from them
    when they have the stock, and SS's ex-date move is measured against them
    (ss_basis). SS adjusts most rights issues itself (8 of 10 measured,
    2025-26), so `apply` is True only where NSE shows SS left the issue raw.
    `check` (Screener) reports its own level shift beside the factor.
    """
    cols = ["symbol", "ex_date", "factor", "issue_price", "cum_close", "new", "held",
            "face_value", "face_value_assumed", "ss_basis", "ss_gap", "apply",
            "check_factor", "check_gap", "purpose"]
    if actions is None or actions.empty or closes is None or closes.empty:
        return pd.DataFrame(columns=cols)
    face_values = face_values or {}
    rows = []
    rights = actions[actions["purpose"].astype(str).str.upper().str.contains("RIGHT")]
    for _, act in rights.drop_duplicates(["symbol", "ex_date", "purpose"]).iterrows():
        sym = str(act["symbol"]).upper()
        terms = parse_rights(act["purpose"])
        if terms is None or sym not in closes.columns or pd.isna(act["ex_date"]):
            continue
        ex = pd.Timestamp(act["ex_date"]).normalize()
        before = closes[sym].loc[:ex - pd.Timedelta(days=1)].dropna()
        after = closes[sym].loc[ex:].dropna()
        if before.empty or after.empty:
            continue  # the closes do not straddle the ex-date
        stated = act.get("face_value") if hasattr(act, "get") else None
        if sym in face_values:
            fv, assumed = float(face_values[sym]), False
        elif stated is not None and pd.notna(stated) and float(stated) > 0:
            fv, assumed = float(stated), False        # NSE's list states it
        else:
            fv, assumed = DEFAULT_FACE_VALUE, True
        issue = terms["price"] + fv if terms["premium"] else terms["price"]
        raw_before = raw[sym].loc[:ex - pd.Timedelta(days=1)].dropna() \
            if raw is not None and sym in raw.columns else pd.Series(dtype=float)
        # SS's own cum close is already scaled when SS adjusted; NSE's is not.
        cum = float(raw_before.iloc[-1]) if len(raw_before) else float(before.iloc[-1])
        factor = rights_factor(terms["new"], terms["held"], issue, cum)
        if factor == 1.0:
            continue
        gap = _ex_move(closes, sym, ex) - _ex_move(raw, sym, ex)
        basis = ss_basis(gap, factor)
        check_factor = _level_shift(check, closes, sym, ex) if check is not None else np.nan
        if assumed:
            # The face value the sources used: SS's own factor when it adjusted,
            # else Screener's when it did (its shift against a raw SS).
            observed = np.exp(-gap) if basis == "own_factor" else \
                check_factor if basis == "raw" and pd.notna(check_factor) else np.nan
            fv_seen = _infer_face_value(terms, cum, observed) if pd.notna(observed) else None
            if fv_seen is not None and fv_seen != fv:
                fv, assumed = fv_seen, False
                issue = terms["price"] + fv
                factor = rights_factor(terms["new"], terms["held"], issue, cum)
                basis = ss_basis(gap, factor)
        rows.append({
            "symbol": sym, "ex_date": ex, "factor": round(factor, 6), "issue_price": issue,
            "cum_close": cum, "new": terms["new"], "held": terms["held"], "face_value": fv,
            "face_value_assumed": assumed, "ss_basis": basis,
            "ss_gap": round(gap, 6) if pd.notna(gap) else np.nan, "apply": basis == "raw",
            "check_factor": check_factor,
            "check_gap": abs(factor - check_factor) if pd.notna(check_factor) else np.nan,
            "purpose": str(act["purpose"]),
        })
    return pd.DataFrame(rows, columns=cols)


def _level_shift(adjusted: pd.DataFrame, raw: pd.DataFrame, sym: str, ex: pd.Timestamp,
                 sessions: int = 10) -> float:
    """How an adjusted source's history sits against the raw one before an ex-date.

    The median of adjusted/raw over the sessions just before, over the same
    ratio just after: the factor the adjusted source applied (1.0 if none).
    """
    if adjusted is None or sym not in adjusted.columns or sym not in raw.columns:
        return np.nan
    ratio = (adjusted[sym] / raw[sym]).replace([np.inf, -np.inf], np.nan).dropna()
    pre = ratio.loc[:ex - pd.Timedelta(days=1)].tail(sessions)
    post = ratio.loc[ex:].head(sessions)
    if pre.empty or post.empty:
        return np.nan
    return round(float(pre.median() / post.median()), 6)


def apply_factors(closes: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Every close before each event's ex-date multiplied by its factor."""
    out = closes.copy()
    for _, ev in (events if events is not None else pd.DataFrame()).iterrows():
        if ev["symbol"] in out.columns:
            mask = out.index < pd.Timestamp(ev["ex_date"])
            out.loc[mask, ev["symbol"]] = out.loc[mask, ev["symbol"]] * float(ev["factor"])
    return out


# ── The vote ─────────────────────────────────────────────────────────────────

def _calendar(sources: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    """Every session any source holds a price for."""
    days = set()
    for frame in sources.values():
        days |= set(frame.dropna(how="all").index)
    return pd.DatetimeIndex(sorted(days))


def _moves(closes: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """One-day moves on the shared calendar: NaN where the source lacks the day
    or the session before it, so a move never silently spans a gap."""
    return closes.reindex(calendar).pct_change(fill_method=None)


def vote(sources: dict[str, pd.DataFrame], tolerance: float = VOTE_TOLERANCE) -> pd.DataFrame:
    """Every (date, symbol) where the sources' one-day moves do not all agree.

    Columns: date, symbol, verdict ("majority" | "judge" | "unresolved"),
    used (the move adopted), odd (the source outvoted, if any), and each
    source's own move. Agreed sessions are not listed.
    """
    names = list(sources)
    calendar = _calendar(sources)
    moves = {n: _moves(f, calendar) for n, f in sources.items()}
    symbols = sorted(set().union(*(set(m.columns) for m in moves.values())))
    stacked = {n: m.reindex(columns=symbols).stack(future_stack=True) for n, m in moves.items()}
    frame = pd.DataFrame(stacked)
    frame = frame[frame.notna().sum(axis=1) >= 2]
    frame = frame[(frame.max(axis=1) - frame.min(axis=1)) > tolerance]  # only disagreements
    rows = []
    for (day, sym), r in zip(frame.index, frame.to_dict("records")):
        have = {n: float(r[n]) for n in names if pd.notna(r[n])}
        verdict, used, odd = "unresolved", have.get(JUDGE, np.nan), ""
        if len(have) >= 3:
            for n in have:
                rest = [v for k, v in have.items() if k != n]
                if max(rest) - min(rest) <= tolerance:
                    verdict, used, odd = "majority", float(np.median(rest)), n
                    break
        if verdict == "unresolved" and JUDGE in have:
            verdict = "judge" if len(have) == 2 else "unresolved"
        elif verdict == "unresolved" and max(have.values()) - min(have.values()) > GROSS_DISAGREEMENT:
            used = min(have.values(), key=abs)              # flagged, never a wild jump
        rows.append({"date": pd.Timestamp(day), "symbol": sym, "verdict": verdict,
                     "used": used, "odd": odd, **{f"move_{n}": have.get(n, np.nan) for n in names}})
    cols = ["date", "symbol", "verdict", "used", "odd", *[f"move_{n}" for n in names]]
    return pd.DataFrame(rows, columns=cols)


def _action_label(row) -> str:
    kind = str(row.get("kind") or "").strip()
    purpose = str(row.get("purpose") or "").upper()
    if "RIGHT" in purpose:
        return "rights"
    if kind and kind not in ("other", "dividend"):
        return kind
    return "demerger" if "DEMERGER" in purpose else ""


def level_drifts(a: pd.DataFrame, b: pd.DataFrame, actions: pd.DataFrame | None = None,
                 tolerance: float = DRIFT_TOLERANCE, window: int = 10) -> pd.DataFrame:
    """Lasting shifts in a/b, each tagged with the corporate action it sits on.

    A one-day disagreement is the vote's business; a ratio that steps and
    stays (one source restated history, or adjusted an action the other did
    not) is reported here. `action` names a known corporate action (NSE's
    rows: symbol, ex_date, purpose[, kind]) within five days -- a demerger,
    where sources legitimately pick different factors -- or is "" when
    nothing explains the shift: those are the ones to look at.
    """
    known: dict[str, list[tuple[pd.Timestamp, str]]] = {}
    if actions is not None and not actions.empty:
        for row in actions.to_dict("records"):
            label = _action_label(row)
            if label and pd.notna(row.get("ex_date")):
                known.setdefault(str(row["symbol"]).upper(), []).append(
                    (pd.Timestamp(row["ex_date"]).normalize(), label))
    rows = []
    for sym in sorted(set(a.columns) & set(b.columns)):
        ratio = (a[sym] / b[sym]).replace([np.inf, -np.inf], np.nan).dropna()
        if len(ratio) < 2 * window:
            continue
        pre = ratio.rolling(window).median().shift(1)            # the `window` sessions before
        post = ratio[::-1].rolling(window).median()[::-1]         # this session and after
        shift = (post / pre - 1).dropna()
        if shift.empty:
            continue
        # Medians tie across the days next to a step: of the days within a
        # tenth of the largest shift, the step is the one the ratio jumps on.
        near = shift[shift.abs() >= 0.9 * shift.abs().max()]
        jump = ratio.pct_change().abs().reindex(near.index).fillna(0)
        best_day = jump.idxmax()
        best = float(shift[best_day])
        if abs(best) <= tolerance:
            continue
        hits = [lbl for d, lbl in known.get(sym, []) if abs((best_day - d).days) <= 5]
        rows.append({"symbol": sym, "date": best_day, "shift": best,
                     "action": hits[0] if hits else ""})
    return pd.DataFrame(rows, columns=["symbol", "date", "shift", "action"])


# ── The reconciled series ────────────────────────────────────────────────────

@dataclass
class Reconciled:
    close: pd.DataFrame
    votes: pd.DataFrame
    rights: pd.DataFrame
    drifts: pd.DataFrame
    filled: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=["date", "symbol", "source"]))

    def summary(self) -> dict:
        v = self.votes
        return {
            "stocks": int(self.close.shape[1]),
            "sessions": int(self.close.shape[0]),
            "rights_issues": int(len(self.rights)),
            "rights_applied": int(self.rights["apply"].astype(bool).sum()) if len(self.rights) else 0,
            "rights_to_check": int(self.rights["ss_basis"].isin(["own_factor", "unknown"]).sum())
            if len(self.rights) else 0,
            "majority_corrections": int((v["verdict"] == "majority").sum()) if len(v) else 0,
            "ss_outvoted": int(((v["verdict"] == "majority") & (v["odd"] == "ss")).sum()) if len(v) else 0,
            "judge_used": int((v["verdict"] == "judge").sum()) if len(v) else 0,
            "unresolved": int((v["verdict"] == "unresolved").sum()) if len(v) else 0,
            "level_drifts": int((self.drifts["action"] == "").sum()) if len(self.drifts) else 0,
            "action_drifts": int((self.drifts["action"] != "").sum()) if len(self.drifts) else 0,
            "sessions_filled": int(len(self.filled)),
        }


def reconcile(ss: pd.DataFrame, screener: pd.DataFrame | None, nse: pd.DataFrame | None,
              actions: pd.DataFrame | None = None, face_values: dict | None = None,
              tolerance: float = VOTE_TOLERANCE,
              nse_raw: pd.DataFrame | None = None) -> Reconciled:
    """SS's closes, rights-adjusted and corrected by the vote, gaps filled.

    `nse` (committed, split/bonus adjusted) never adjusts rights; `nse_raw`
    (NSE's raw daily closes) stands in for it as the rights anchor where the
    committed set lacks a stock. Screener is the rights check and a voter.
    """
    # The rights anchor: NSE's committed closes, else its raw daily file
    # (`nse_raw`: every security, unadjusted) for stocks the committed set lacks.
    anchor = nse
    if nse_raw is not None:
        extra = nse_raw.drop(columns=[c for c in (nse.columns if nse is not None else [])
                                      if c in nse_raw.columns])
        anchor = extra if nse is None else pd.concat([nse, extra], axis=1)
    rights = rights_events(actions, ss, face_values, check=screener, raw=anchor)
    ss_adj = apply_factors(ss, rights[rights["apply"].astype(bool)])
    # NSE never adjusts rights: bring it to SS's basis -- our factor where SS
    # was raw or matched it, SS's own where SS used another (exp(-gap)).
    to_nse = rights.assign(factor=np.where(rights["ss_basis"] == "own_factor",
                                           np.exp(-rights["ss_gap"].astype(float)),
                                           rights["factor"]))
    to_nse = to_nse[to_nse["ss_basis"] != "unknown"]
    nse_adj = apply_factors(nse, to_nse) if nse is not None else None
    sources = {"ss": ss_adj}
    if screener is not None:
        sources["screener"] = screener.reindex(columns=ss.columns)
    if nse_adj is not None:
        sources["nse"] = nse_adj.reindex(columns=ss.columns)
    votes = vote(sources, tolerance)

    index = _calendar(sources)
    moves = {n: _moves(f, index) for n, f in sources.items()}
    chosen = moves["ss"].copy()
    # strictly after SS's first close: the chain starts from that close
    started = ss_adj.reindex(index).notna().cummax().shift(1, fill_value=False)
    fill_src = pd.DataFrame("", index=index, columns=chosen.columns)
    for name in ("screener", "nse"):                    # sessions SS cannot give a move for
        if name in moves:
            gap = chosen.isna() & moves[name].notna() & started
            chosen = chosen.mask(gap, moves[name])
            fill_src = fill_src.mask(gap, name)
    for r in votes.itertuples():                        # the vote's settled moves win
        if pd.notna(r.used) and r.symbol in chosen.columns:
            chosen.at[r.date, r.symbol] = r.used
            fill_src.at[r.date, r.symbol] = ""
    out = {}
    for sym in ss_adj.columns:
        own = ss_adj[sym].dropna()
        if own.empty:
            continue
        start = own.index[0]
        m = chosen[sym].loc[chosen.index > start].dropna()
        out[sym] = pd.concat([pd.Series({start: float(own.iloc[0])}),
                              float(own.iloc[0]) * (1 + m).cumprod()])
    stacked = fill_src.stack()
    stacked = stacked[stacked != ""]
    filled = [{"date": d, "symbol": s_, "source": src} for (d, s_), src in stacked.items()]
    close = pd.DataFrame(out).sort_index()
    drifts = level_drifts(ss_adj, sources["screener"], actions) if "screener" in sources else \
        pd.DataFrame(columns=["symbol", "date", "shift", "action"])
    return Reconciled(close=close, votes=votes, rights=rights, drifts=drifts,
                      filled=pd.DataFrame(filled, columns=["date", "symbol", "source"]))
