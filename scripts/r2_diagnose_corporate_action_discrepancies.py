"""Diagnose raw-Yahoo vs canonical V1 price-scale discrepancies by corporate action.

This is diagnostic only. It never changes V1 prices, rankings, or the R2 raw archive.
It measures whether a logged corporate action explains a change in the V1/raw
historical scale, and separately reports unexplained scale breaks.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from r2.raw.yahoo import adjusted_from_raw


def close_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if isinstance(frame.columns, pd.MultiIndex):
        levels = [
            {str(v).strip().lower() for v in frame.columns.get_level_values(i)}
            for i in range(frame.columns.nlevels)
        ]
        field_level = next((i for i, vals in enumerate(levels) if "close" in vals), None)
        if field_level is not None:
            key = next(
                v for v in frame.columns.get_level_values(field_level)
                if str(v).strip().lower() == "close"
            )
            frame = frame.xs(key, level=field_level, axis=1)
    elif "Close" in frame.columns:
        frame = frame[["Close"]].rename(columns={"Close": "CLOSE"})
    out = frame.apply(pd.to_numeric, errors="coerce")
    out.index = pd.to_datetime(out.index).tz_localize(None)
    out.columns = [str(c).upper() for c in out.columns]
    return out.sort_index()


def robust_scale(a: pd.Series, b: pd.Series) -> float:
    x = pd.concat([a, b], axis=1).dropna()
    if x.empty:
        return np.nan
    ratio = x.iloc[:, 0] / x.iloc[:, 1]
    ratio = ratio.replace([np.inf, -np.inf], np.nan).dropna()
    if ratio.empty:
        return np.nan
    return float(ratio.median())


def event_attribution(v1: pd.DataFrame, raw_adj: pd.DataFrame, events: list[dict]) -> pd.DataFrame:
    rows = []
    for e in events:
        s = str(e.get("symbol", "")).upper()
        if s not in v1.columns or s not in raw_adj.columns:
            continue
        when = pd.Timestamp(e["date"])
        ratio = float(e["ratio"])
        common = v1[s].index.intersection(raw_adj[s].index)
        if when not in common:
            continue
        # Use a local window, but exclude the action day itself.
        pre_idx = common[(common < when) & (common >= when - pd.Timedelta(days=45))]
        post_idx = common[(common > when) & (common <= when + pd.Timedelta(days=45))]
        pre_scale = robust_scale(v1[s].reindex(pre_idx), raw_adj[s].reindex(pre_idx))
        post_scale = robust_scale(v1[s].reindex(post_idx), raw_adj[s].reindex(post_idx))
        inferred = (post_scale / pre_scale) if np.isfinite(pre_scale) and pre_scale else np.nan
        # If V1 removes a split from the historical side, post/pre should be ~1/ratio.
        expected_scale_step = 1.0 / ratio
        error = (
            abs(np.log(inferred / expected_scale_step))
            if np.isfinite(inferred) and inferred > 0
            else np.nan
        )
        rows.append({
            "symbol": s,
            "date": when.date().isoformat(),
            "logged_ratio": ratio,
            "kind": e.get("kind", ""),
            "looks_like": e.get("looks_like", ""),
            "pre_scale_v1_over_raw": pre_scale,
            "post_scale_v1_over_raw": post_scale,
            "observed_post_over_pre": inferred,
            "expected_post_over_pre": expected_scale_step,
            "log_error": error,
            "pre_obs": len(pre_idx),
            "post_obs": len(post_idx),
            "explains_scale_break": bool(np.isfinite(error) and error <= np.log(1.10)),
        })
    return pd.DataFrame(rows)


def discrepancy(v1: pd.DataFrame, raw_adj: pd.DataFrame) -> pd.DataFrame:
    common_symbols = sorted(set(v1.columns) & set(raw_adj.columns))
    rows = []
    for s in common_symbols:
        x = v1[s].reindex(v1.index.intersection(raw_adj[s].index))
        y = raw_adj[s].reindex(x.index)
        valid = x.notna() & y.notna() & (x != 0)
        if not valid.any():
            continue
        rel = (y[valid] - x[valid]).abs() / x[valid].abs()
        rows.append({
            "symbol": s,
            "observations": int(valid.sum()),
            "material_gt_1pct": int((rel > 0.01).sum()),
            "material_share": float((rel > 0.01).mean()),
            "median_abs_relative_diff": float(rel.median()),
            "p95_abs_relative_diff": float(rel.quantile(0.95)),
        })
    return pd.DataFrame(rows).sort_values("material_share", ascending=False)


def unexplained_scale_breaks(v1: pd.DataFrame, raw_adj: pd.DataFrame, events: list[dict]) -> pd.DataFrame:
    event_days = {(str(e.get("symbol","")).upper(), pd.Timestamp(e["date"])) for e in events}
    rows = []
    for s in sorted(set(v1.columns) & set(raw_adj.columns)):
        idx = v1.index.intersection(raw_adj[s].dropna().index)
        if len(idx) < 30:
            continue
        scale = (v1[s].reindex(idx) / raw_adj[s].reindex(idx)).replace([np.inf, -np.inf], np.nan)
        scale = scale.dropna()
        if len(scale) < 30:
            continue
        step = scale / scale.shift(1)
        for d, value in step.items():
            if not np.isfinite(value) or value <= 0:
                continue
            if abs(np.log(value)) < np.log(1.05):
                continue
            nearby = any(
                sym == s and abs((d - ed).days) <= 3 for sym, ed in event_days
            )
            if nearby:
                continue
            rows.append({
                "symbol": s,
                "date": pd.Timestamp(d).date().isoformat(),
                "scale_step": float(value),
                "abs_log_step": float(abs(np.log(value))),
            })
    out = pd.DataFrame(rows)
    return out.sort_values("abs_log_step", ascending=False) if not out.empty else out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--v1", type=Path, required=True)
    ap.add_argument("--events", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    raw = pd.read_parquet(args.raw)
    raw_adj, *_ = adjusted_from_raw(raw)
    v1 = close_frame(pd.read_parquet(args.v1))
    events_doc = json.loads(args.events.read_text(encoding="utf-8"))
    events = list((events_doc.get("events") or {}).values())

    args.out.mkdir(parents=True, exist_ok=True)
    disc = discrepancy(v1, raw_adj)
    attrib = event_attribution(v1, raw_adj, events)
    unexplained = unexplained_scale_breaks(v1, raw_adj, events)
    disc.to_csv(args.out / "discrepancy_by_symbol.csv", index=False)
    attrib.to_csv(args.out / "event_attribution.csv", index=False)
    unexplained.to_csv(args.out / "unexplained_scale_breaks.csv", index=False)

    matched = attrib[attrib["explains_scale_break"]] if not attrib.empty else attrib
    summary = {
        "common_symbols": int(len(disc)),
        "aggregate_observations": int(disc["observations"].sum()) if not disc.empty else 0,
        "aggregate_material_gt_1pct": int(disc["material_gt_1pct"].sum()) if not disc.empty else 0,
        "events_evaluated": int(len(attrib)),
        "events_explaining_scale_break": int(len(matched)),
        "unexplained_scale_breaks": int(len(unexplained)),
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("R2_CORPORATE_ACTION_DIAGNOSTIC", summary)
    if not attrib.empty:
        print("\nTOP_EVENT_MATCHES")
        print(attrib.sort_values(["explains_scale_break","log_error"], ascending=[False, True]).head(25).to_string(index=False))
    if not unexplained.empty:
        print("\nTOP_UNEXPLAINED_SCALE_BREAKS")
        print(unexplained.head(25).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
