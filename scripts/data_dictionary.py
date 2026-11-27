"""Write docs/DATA_DICTIONARY.md: each committed data file's columns, rows, dates and writer (S163 §3).

Read from the files and the workflows, so it can be run again when they change:
    python scripts/data_dictionary.py
Units are not inferred; DATA_CATALOGUE.md says what each dataset is.
"""
from __future__ import annotations

import fnmatch
import json
import re
import subprocess
import warnings
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "DATA_DICTIONARY.md"
DATE_HINT = re.compile(r"date|as_of|quarter_end|day|month", re.I)


def writers() -> dict[str, list[str]]:
    """data path -> workflows whose `git add` names it (or its folder)."""
    found: dict[str, list[str]] = {}
    for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        text = wf.read_text()
        for m in re.finditer(r"git add ([^\n;&|]+)", text):
            for token in m.group(1).split():
                if token.startswith("data"):
                    found.setdefault(token.rstrip("/"), []).append(wf.stem)
    return found


# The bots' commit subjects, by the workflow that makes them (each workflow's `git commit -m`).
BOT_SUBJECTS = {
    "automated daily NSE index & classification sync": "daily_sync",
    "weekly full sync findings": "weekly_full_sync",
    "freeze closed month(s)": "monthly_track_record",
}
HISTORY_SINCE = "60 days ago"


def history_writer(path: str, log: str | None = None) -> str | None:
    """Who committed `path` in the last 60 days, from git: the bot workflows named by their commit
    subject, or "pull requests only" for a file no job touched. None when git has no history for it
    (a shallow clone), so the caller keeps the workflow-level answer."""
    if log is None:
        try:
            log = subprocess.run(["git", "log", f"--since={HISTORY_SINCE}", "--format=%an|%s", "--", path],
                                 cwd=ROOT, capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            return None
    jobs, prs = {}, 0
    for line in filter(None, log.splitlines()):
        author, _, subject = line.partition("|")
        if author.startswith("github-actions"):
            job = next((j for k, j in BOT_SUBJECTS.items() if k in subject), "a job (" + subject[:40] + ")")
            jobs[job] = jobs.get(job, 0) + 1
        else:
            prs += 1
    if not jobs and not prs:
        return None
    if not jobs:
        return f"pull requests only ({prs} in 60 days; kept by hand)"
    named = ", ".join(f"{j} ({n} commits)" for j, n in sorted(jobs.items(), key=lambda kv: -kv[1]))
    return named + (f"; also {prs} by pull request" if prs else "")


def writer_of(path: str, table: dict[str, list[str]]) -> str:
    best = ""
    for key in table:
        # A token may be a folder, a file or a glob (`data/momentum_health_*.csv`).
        hit = path == key or path.startswith(key + "/") or ("*" in key and fnmatch.fnmatchcase(path, key))
        if hit and len(key) > len(best):
            best = key
    if not best:
        return "not written by a job"
    jobs = ", ".join(sorted(set(table[best])))
    # `git add -A data/` stages anything under data/ and names no file: ask git who committed it.
    if best == "data":
        return history_writer(path) or f"{jobs} (stages all of `data/`; writer not named)"
    return jobs


def span_of(df: pd.DataFrame, cols: list[str]) -> str:
    """The first date-like column's first and last date, or the index's when it holds dates."""
    candidates = [(c, df[c]) for c in cols if DATE_HINT.search(c)]
    if isinstance(df.index, pd.DatetimeIndex):
        candidates.insert(0, ("index", df.index.to_series()))
    for name, values in candidates:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            d = pd.to_datetime(values, errors="coerce").dropna()
        if len(d):
            return f"`{name}` {d.min():%Y-%m-%d} to {d.max():%Y-%m-%d}"
    return ""


def describe(path: Path) -> tuple[str, str, str]:
    """(rows, columns, date range) for one file."""
    try:
        if path.suffix == ".csv":
            df = pd.read_csv(path, low_memory=False)
        elif path.suffix == ".parquet":
            df = pd.read_parquet(path)
        elif path.suffix == ".jsonl":
            df = pd.read_json(path, lines=True)
        else:
            obj = json.loads(path.read_text())
            if isinstance(obj, dict):
                return (f"{len(obj)} keys", ", ".join(list(obj)[:12]) + (" ..." if len(obj) > 12 else ""), "")
            if isinstance(obj, list):
                return (f"{len(obj)} items", "", "")
            return ("", "", "")
    except Exception as exc:  # a dictionary, never a reason to stop
        return ("unreadable", type(exc).__name__, "")
    cols = [str(c) for c in df.columns]
    if len(cols) > 40:
        return (f"{len(df):,}", f"wide: {len(cols)} columns ({', '.join(cols[:3])}, ...)", span_of(df, cols))
    span = span_of(df, cols)
    shown = ", ".join(cols[:14]) + (f" ... (+{len(cols) - 14})" if len(cols) > 14 else "")
    return (f"{len(df):,}", shown, span)


def main() -> None:
    table = writers()
    files = sorted(p for p in (ROOT / "data").rglob("*")
                   if p.is_file() and p.suffix in {".csv", ".parquet", ".json", ".jsonl"}
                   and "__pycache__" not in p.parts)
    lines = [
        "# Data dictionary (S163, generated by `scripts/data_dictionary.py`)",
        "",
        "Each committed data file: rows, columns, the first date column's range, and the workflow whose",
        "`git add` writes it. Where that workflow stages all of `data/`, the writer is read from git instead:",
        "the jobs that committed the file in the last 60 days (by their commit subject), or \"pull requests",
        "only\" for a file kept by hand. Run the script again after a data change, from a clone with that",
        "history; do not edit by hand. What each dataset means, its R2 copy and its readers are in",
        "`docs/DATA_CATALOGUE.md`. Units are not inferred.",
        "",
        "| File | Rows | Columns | Dates | Written by |",
        "|---|---|---|---|---|",
    ]
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        rows, cols, span = describe(p)
        lines.append(f"| `{rel}` | {rows} | {cols.replace('|', '/')} | {span} | {writer_of(rel, table)} |")
    OUT.write_text("\n".join(lines) + "\n")
    print(f"{OUT.relative_to(ROOT)}: {len(files)} files")


if __name__ == "__main__":
    main()
