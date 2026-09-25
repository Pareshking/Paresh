# V1 repository cleanup — verified findings

Date: 2026-08-18. Everything below was verified against `main` file by file,
after `git fetch --unshallow`.

## Read this first: the clone was shallow

The session clone was shallow. Under a shallow clone every branch reports an
unrelated root commit, so `git merge-base` finds no ancestor and all five
branches looked like independent histories 18–57 commits ahead of `main`.
Deleting on that reading would have destroyed real work. After unshallowing,
`main` had 210 commits and each branch carried only 3–10 genuinely unmerged
ones. **Run `git fetch --unshallow` before judging any branch here.**

## Branch verdicts

| Branch | Head | Verdict |
|---|---|---|
| `audit/p0-missing-data` | `fed0b1b` | Superseded |
| `claude/umiya-codebase-audit-kgr923` | `c621454` | Superseded |
| `claude/umiya-v1-audit-xht45x` | `5e2a4c9` | Superseded; one finding salvaged |
| `feature/6m-backtest` | `586631c` | Superseded by the completed-month window |
| `Sandbox` | `78adafd` | Research only, no production code |

### audit/p0-missing-data
Changed `clean_holidays` to stop forward-filling security-level gaps. `main`
already does this AND guards the case where holiday removal would empty the
dataset, which the branch does not. `main`'s `tests/test_missing_data_integrity.py`
covers the branch's two invariants with four tests. Nothing to salvage.

### claude/umiya-codebase-audit-kgr923
Six items, all verified present on `main`:
IST-aware `_is_fresh` (main uses `ist_today()`); `np.sqrt(lb)` period
annualisation in the backtester; the vectorised ATR true-range rewrite; removal
of the duplicated `indices_loader` cache layer; the `role`/`aria-label`
attributes; and the dead `sy`/`sx` locals. Nothing to salvage.

### claude/umiya-v1-audit-xht45x — one real finding, salvaged
Its benchmark work is superseded: `main` reaches the same single-benchmark
consistency because `fetch_benchmark_history` is `@st.cache_data`-memoised and
all three consumers call it identically.

It also flagged that `MOMENTUM_WINDOWS` (calendar months) was being spent as
trading sessions in the backtest warmup. That was real and still live. Its own
fix — replacing `WINDOWS` wholesale with session counts — would have fed
session counts to the months-based scorer, so the finding was reimplemented
rather than merged. See `SESSIONS_PER_MONTH` in `src/engine/backtester.py` and
`tests/test_backtest_warmup_units.py`.

### feature/6m-backtest
A selectable 6/12-month window measured backwards from the last available date,
so its "6 months" ended mid-month and shifted every session. Superseded by the
fixed last-6-completed-months window, which is reproducible. See
`completed_month_window` and `tests/test_completed_month_backtest_window.py`.

### Sandbox
`research/` scripts and two workflows that fetch NSE directly and run hypothesis
backtests. No production code. Keep only if the research history is wanted.

## Commands

This session's credentials could create and update refs but **not delete refs
or push tags** (403 / dropped connection), so the branch removal below was not
executed. Tag first so the commits stay recoverable, then delete:

```bash
git fetch --unshallow                     # do not skip
git tag -a archive/audit-p0-missing-data   fed0b1b -m "archived 2026-08-18"
git tag -a archive/codebase-audit-kgr923   c621454 -m "archived 2026-08-18"
git tag -a archive/v1-audit-xht45x         5e2a4c9 -m "archived 2026-08-18"
git tag -a archive/feature-6m-backtest     586631c -m "archived 2026-08-18"
git tag -a archive/sandbox-research        78adafd -m "archived 2026-08-18"
git push origin --tags

git push origin --delete Sandbox
git push origin --delete audit/p0-missing-data
git push origin --delete claude/umiya-codebase-audit-kgr923
git push origin --delete claude/umiya-v1-audit-xht45x
git push origin --delete feature/6m-backtest
```

Also delete `archive/probe-test`. It was created while establishing that ref
deletion is refused in this environment, and could not be removed afterwards:

```bash
git push origin --delete archive/probe-test
```

## CI removed from main

`v1-audit-hardening.yml` held `contents: write` and re-ran three one-shot regex
migrations (`harden_v1.py`, `fix_streamlit_html.py`, `fix_strategy_overlay.py`)
against the working source on every push to `main`, committing the result back
over `momentum.py`, `theme.py` and `strategy_view.py`. Spent, and a standing
hazard. Removed with its scripts.

Also removed: five push-triggered workflows that re-ran subsets of the suite
`v1-full-validation.yml` already runs in full; `one-tab-production-probe.yml`
and its script, superseded by `production_qa.py`; and three spent dispatch-only
one-offs.

Kept: `v1-production-qa`, `v1-full-validation`, `daily_sync`,
`weekly_full_sync`, `v1-cold-start-probe`.
