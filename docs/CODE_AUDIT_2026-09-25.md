# Code, workflow and repository audit — 2026-09-25

Audit only: **no production code was changed.** Every item below was checked
against `main` at `a392539`. Items marked *verify* are strong suspicions
that need one more check before anyone acts on them.

## How it was checked

- Full test suite, locally on Python 3.11: **1328 passed, 1 failed** in 120 s.
- `ruff` (F, B, UP, SIM, S rule sets) and `vulture` for dead code. Every
  "unused" hit was grepped across `src/`, `app.py`, `r2/`, `scripts/`,
  `agent/` and `tests/` before it was listed.
- All 33 workflows: triggers, Python versions, permissions, timeouts,
  concurrency. Recent GitHub Actions run history on `main`.
- All 166 remote branches, after `git fetch --unshallow`.

---

## 1. CRITICAL — fix first

### C1. Two scheduled R2 workflows fail every day on `main`

| Workflow | Status |
|---|---|
| `R2 historical evidence bootstrap` | failed on 2026-09-23 and 2026-09-24 (runs #12, #13) |
| `R2 session continuity audit` | failed on 2026-09-24 (run #4) |

**Root cause of the first failure (reproduced locally):**
`tests/test_r2_historical_evidence.py::test_real_membership_history_has_no_changes_and_covers_acceptance_date`
asserts `data/membership_history.json["changes"] == []`. The 2026-09-23 daily
sync recorded a real NSE symbol change, `{"added": ["HEGAM"], "removed": ["HEG"]}`.
The test asserts a fact about **live, bot-updated data**, so the first real
index change broke it. The data is correct, and `docs/PRODUCTION_STATUS.md`
says HEGAM must not be aliased to HEG. The test is what's wrong.

**Fix:** assert the structure of the history (the schema, sorted dates, no
symbol both added and removed on the same date, `effective_from <=
MEMBERSHIP_AS_OF`), not that it is empty. Don't edit the data file to make
the test pass.

**Session continuity audit:** the root cause hasn't been diagnosed yet. It
needs the run log (it reads R2, so it can't be reproduced here without
credentials).

### C2. Red scheduled workflows are easy to miss

Both failures above have repeated for days with no follow-up, because
scheduled-run failures only go out as email to the actor. Add a failure
notification, such as opening or updating a GitHub issue on failure (see W7).

---

## 2. WARNING — correctness and reliability risks

### W1. The keep-warm ping probably does not keep caches warm (*verify*)
`keep_warm.yml` says one HTTPS GET "keeps the in-process caches warm". A plain
`curl` of `https://paresh.streamlit.app/` gets the static Streamlit shell
only. The Python script runs only when a browser opens the websocket session,
so `@st.cache_data` entries are never filled by the ping. It may not count as
activity for Streamlit Cloud's sleep timer either. It also costs about 34 runs
per weekday.
**Action:** check the app log after a ping. If the script did not run, drive a
real session (the Playwright navigator in `scripts/_streamlit_nav.py` already
exists), or drop the workflow.

### W2. On the legacy HTTPS path, Screener shaping can serve a stale frame for up to an hour
`app.py` `_shape_screener_store(store_revision, _store)` is keyed only on
`store_revision`. On the non-R2 path that value is the constant
`"published_screener_https"`. `_fetch_screener_store` and the shaper have
independent 1-hour TTLs, so a store fetched again can be paired with a shape
cached from the previous store. The R2 path is unaffected because it uses the
immutable SHA.
**Fix:** for the HTTPS path, use a real identity (an ETag, the max date plus
the row count, or a content hash) as the revision.

### W3. `_fetch_screener_store(_k, ...)`: the price hash is silently excluded from the cache key
Streamlit ignores parameters whose names start with `_` when it builds the
cache key, so the `price_hash` passed as `_k` has no effect. That may be
intended (the TTL is the freshness boundary), but the call site reads as if
the hash matters. **Action:** remove the parameter, or rename it and document
it.

### W4. Python version drift
| Place | Version |
|---|---|
| `Dockerfile` | 3.14 |
| `v1-full-validation.yml`, `stage4b-independent-validation.yml` | 3.14 |
| 10 R2/QA workflows | 3.13 |
| 19 other workflows, `.devcontainer` | 3.11 |
| Streamlit Cloud (production) | not pinned in the repo |

Tests pass on 3.11 locally and on 3.14 in CI, but production's interpreter is
not declared anywhere. **Action:** choose one version, pin it for Streamlit
Cloud in the app settings, and use it in the Dockerfile, the devcontainer and
every workflow (for example through a shared `.python-version`).

### W5. Workflows triggered by branches that no longer matter
- `r2-archive-validation.yml` runs on push to `feat/r2-phase1-storage-adapter`
  (223 commits behind `main`, abandoned).
- `stage4b-independent-validation.yml` runs on push to seven `agent/stage4b-*`
  and `claude/stage4b-*` branches, all 230 or more commits behind `main`.
- `v1-full-validation.yml` runs on push to `agent/stage4b-execution` and
  `agent/stage4b-second-archetype`, and repeats them in its `if:` condition.

### W6. Missing guardrails on write-capable workflows
- `weekly_full_sync.yml`: no `permissions:` block (falls back to repository
  defaults), no `timeout-minutes`.
- `daily_sync.yml`, `monthly_track_record.yml`, `r2_archive_audit.yml`,
  `r2_yahoo_raw_build.yml`: no `timeout-minutes` (the default is 6 h).
- `r2_research_consumer.yml`: no `permissions:`, no timeout.
- Only 6 of 33 workflows declare `concurrency`. The R2 publishers
  (`r2_ranking_archive`, `r2_market_cap_history`, `r2_nse_index_prices`,
  `r2-historical-evidence-bootstrap`) can run at the same time as each other,
  whether started by a push, a schedule or a manual dispatch.

### W7. No failure alerting for scheduled jobs
See C2. Suggested: one reusable `notify-on-failure` job that opens or
comments on a pinned "Scheduled job failures" issue.

### W8. The devcontainer is broken and insecure
`.devcontainer/devcontainer.json` opens and runs **`App.py`**, but the file
is `app.py` (Linux is case-sensitive, so it fails). It also starts Streamlit
with `--server.enableCORS false --server.enableXsrfProtection false`, which
contradicts `.streamlit/config.toml` (`enableXsrfProtection = true`). And it
installs an unpinned `streamlit` on top of the pinned 1.63.0.

### W9. Swallowed exceptions in data loaders
`try/except: pass` with no logging: `app.py:95`, `app.py:663`,
`src/loaders/mcap_loader.py` (6 places), `src/loaders/indices_loader.py:38`,
`src/loaders/price_loader.py:36`, `src/engine/parameter_sweep.py:177`.
Each is a spot where a data-quality fault disappears without a trace.
**Fix:** at least `logger.debug(..., exc_info=True)`, or a `metrics.note`
where the UI shows freshness.

---

## 3. REMOVE — unwanted code, files, workflows and branches

### R1. One-off or finished workflows (candidates for deletion)
Each is `workflow_dispatch`-only, or triggers only on edits to its own file,
and served a single investigation:

| Workflow | Why |
|---|---|
| `hegam_screener_probe.yml` | one-off HEGAM probe; the issue is resolved |
| `r2_screener_production_verification.yml` | hard-coded expected SHA and date defaults; push trigger only on its own path |
| `r2-archive-validation.yml` | tied to the abandoned `feat/r2-phase1-storage-adapter` branch |
| `r2_corporate_action_diagnostic.yml` | diagnostic |
| `r2_raw_v1_equivalence.yml` | migration equivalence check, done |
| `r2_yahoo_raw_build.yml`, `r2_yahoo_raw_retry.yml` | one-time raw build; keep only if a rebuild runbook needs them |
| `screener_10y_bootstrap.yml` | one-time bootstrap |
| `v1-recent6m-monthstart.yml` | research run (last touched 2026-08-23) |
| `v1-cold-start-probe.yml` | probe; keep only if it's still used |
| `stage4b-independent-validation.yml` | fires only on stale branches (W5) |

Before deleting any of these, record in a runbook how to recreate it
(`git show <sha>:path`).

### R2. Hard-coded company fixtures inside the `agent/` package
`agent/{anandrathi,lenskart,paytm,sansera,yatharth}_research_packet.py`
(about 3,000 lines) are acceptance-test fixtures for five named companies
with fixed cutoff dates. They are test data, not agent code.
**Move** them to `tests/fixtures/research_packets/`.

### R3. Five near-identical Stage-4B validation scripts
`scripts/stage4b_{anandrathi,lenskart,paytm,yatharth}_live_validation.py`
are 171 lines each and differ only in the company name (an 8-line diff after
normalising names). `stage4b_sansera_…` is a small variant.
**Replace** them with one `scripts/stage4b_live_validation.py --company X`.

### R4. Unused imports and variables (from ruff, confirmed)
- `agent/research_execution.py:20`: unused `build_research_items`; `:31`
  imports `ResearchItem` twice (F811).
- `agent/run.py:14`: unused `pathlib.Path`.
- `src/loaders/screener_loader.py:39`: unused `typing.Iterable`.
- `src/ui/views/ranking_view.py:213`: local `score` assigned and never used.
- 15 F401 hits in total, most of them in `tests/`.

### R5. Dead or near-dead functions (no caller outside tests)
Confirm each before deleting. Some are kept on purpose as public API for the
R2 consumers:
- `src/ui/views/ranking_view.py`: `_fmt_ratio` (no callers anywhere).
- `r2/consumers/r2_historical.py`: `read_membership_as_of` (no callers,
  no tests).
- `src/storage/reader.py`: `read_current_parquet` (no callers, no tests).
- `src/storage/manifest.py`: `canonical_json`, and
  `src/loaders/tv_loader.py`: `reconcile_and_update_tv_classification`
  (no tests; check the single caller).

### R6. Dead warning filters in `app.py`
Lines 16–17 filter `st.components.v1.html` deprecation warnings, but CI now
fails the build if `components.v1` appears anywhere in `app.py` or `src/`.
The filters can never match anything.

### R7. Stale remote branches (166 in total)
- **26** branches have **0 commits** that aren't on `main`. They are fully
  merged and safe to delete.
- The rest are 1–177 commits ahead, mostly squash-merged work. Run the
  branch-by-branch triage described in `docs/REPO_CLEANUP_2026-08-18.md`
  (tag, then delete). The five branches that document already signed off
  (`Sandbox`, `audit/p0-missing-data`, `claude/umiya-*`,
  `feature/6m-backtest`) **still exist**.

### R8. Documentation sprawl
`docs/` holds 15 files (about 5,000 lines), several of them dated snapshots of
finished loops (`V1_AUDIT_CURRENT_LOOP_2026-08-17.md`,
`V1_QA_ROOT_CAUSE_2026-08-18.md`, `REPO_CLEANUP_2026-08-18.md`,
`ADVERSARIAL_AUDIT_2026-09-10.md`). `agent/STAGE_4B_IMPROVEMENT_TRACKER.md`
is 1,439 lines. **Move** closed audits to `docs/archive/`, and keep
`README.md` → `docs/PRODUCTION_STATUS.md` → specs as the reading order.

---

## 4. IMPROVEMENT — quality, tooling, performance

### I1. Add a lint gate to CI
There is no ruff or flake8 step anywhere. Add a `ruff.toml` (start with
`F`, `E9`, `B`) and one step in `v1-full-validation.yml`. The current debt is
121 findings, 47 of them auto-fixable.

### I2. Consolidate test selection
`v1-full-validation.yml` hand-lists `--ignore=` for eight R2 test files, and
`r2-focused-validation.yml` has a separate hand-kept path list. Use pytest
markers (`@pytest.mark.r2`, `@pytest.mark.live_data`) with `-m` instead, so a
new test file cannot fall through both lists.

### I3. Keep live-data assertions out of unit tests
C1 happened because a unit test asserted on bot-updated data. Tag tests that
read `data/*.json` or `data/*.csv` as `live_data` and make sure they check
invariants, not snapshots.

### I4. Dockerfile hygiene
There's no `.dockerignore` (`.git`, `tests/`, `docs/`, `research/` and
`data_cache/` all get copied into the image), the container runs as root, and
there is no layer for the `pyarrow` pin note. Add a `.dockerignore` and a
non-root `USER`.

### I5. Pin GitHub Actions and add Dependabot
The actions are pinned to major tags (`@v4`, `@v5`). Add
`.github/dependabot.yml` for `github-actions` and `pip`. It also brings the
`pyarrow==24.0.0` "bump when arrow#50471 closes" note back up automatically.

### I6. Split the oversized modules
`src/ui/theme.py` (2,320 lines, mostly CSS in Python strings: move it to a
`.css` file loaded once), `src/ui/charts.py` (1,702), `src/loaders/price_loader.py`
(1,430), `src/engine/backtester.py` (1,403). Split them along seams that
already exist; no behaviour change.

### I7. Tests write into the working tree
The test run creates `data_cache/` at the repo root (it's gitignored, so this
is harmless) because `src/core/config.py` falls back to a relative cache
directory. Point tests at `tmp_path` through an env var or a fixture in
`conftest.py`.

### I8. Test runtime
The suite takes about 2 minutes (1,329 tests). Once the tests are marked
(I2), `pytest-xdist -n auto` in CI is a free speed-up.

### I9. Security notes (low risk, recorded)
- No secrets in the repo, and no `eval`, `exec`, `pickle` or `shell=True`.
  Every `requests` call has a timeout.
- 45 `unsafe_allow_html=True` call sites. `tests/test_table_html_escaping.py`
  covers the tables. Do one pass to check that every f-string interpolated
  into those calls goes through `html.escape`.
- `hashlib.md5` is used for cache fingerprints only, not for security. Pass
  `usedforsecurity=False` to document that and to stay FIPS-safe.

---

## 5. LOW PRIORITY
- `zip()` without `strict=` (27 places). Add `strict=True` wherever lengths
  must match.
- `open()` outside a `with` block (21 places, mostly scripts).
- Deprecated `typing` imports (`List`, `Dict`, `Iterable` from `typing`, 18).
- The `app.py` docstring still describes "Investrack Pill Tab Navigation" and
  "Pure Paper White Theme" styling. Refresh it.
- Workflow display names: `v1-production-qa.yml` has no `name:`, so runs show
  up as the file path.

---

## 6. Status (updated 2026-09-25, branch `claude/code-audit-improvements-t8677r`)

Stage-4B paths (`agent/`, `scripts/stage4b_*`, `tests/test_agent_*`,
`stage4b-independent-validation.yml`) were left untouched on purpose because
that work is still in development. R2, R3 and W5's Stage-4B triggers are
deferred for that reason.

### Done
- [x] **C1, historical evidence bootstrap:** the membership test now checks
      invariants instead of expecting no changes. The full bootstrap build
      was re-run locally and succeeds.
- [x] **C1, session continuity audit:** the run log showed argparse exit 2.
      The workflow passed positional paths to `build_trading_sessions.py`,
      which now requires `--prices` and `--output`. After the fix, both steps
      were re-run against the published `data-latest` release: PASS, 720
      sessions.
- [x] Added `tests/test_workflow_script_cli.py`, which checks every
      workflow's `python scripts/X.py` call against that script's argparse
      definition, so this kind of drift fails on the PR.
- [x] **C2/W7:** new `scheduled_failure_alert.yml`. A failed scheduled run
      opens or updates a `scheduled-failure` issue.
- [x] **W6:** timeouts on every job that lacked one; concurrency groups on
      every R2 publisher and audit; `permissions` on `r2_research_consumer`.
      *Correction:* `weekly_full_sync` already scopes its permissions at the
      job level.
- [x] Actions bumped to their first Node 24 majors (GitHub already warns
      that Node 20 is deprecated).
- [x] **R1 (partial):** deleted `r2-archive-validation`,
      `hegam_screener_probe`, `r2_corporate_action_diagnostic`,
      `r2_raw_v1_equivalence` and the two scripts only they called. Kept:
      the Yahoo raw build/retry workflows, the 10-year bootstrap and
      Screener production verification (tests and runbooks refer to them),
      and `v1-recent6m-monthstart` / `v1-cold-start-probe` (research and
      probe tools).
- [x] **W2 + W3:** the HTTPS Screener revision is now derived from the
      data's content; the ignored `_k` argument is gone.
- [x] **W8:** devcontainer fixed. **W9:** cache-write and meta-read
      failures are now logged. (The per-symbol yfinance fallback chain
      deliberately stays quiet.)
- [x] **R4:** unused imports and locals removed. This also removed a test
      that was **defined twice**, so its first copy never ran. **R5:**
      `_fmt_ratio` removed.
- [x] **I1:** `ruff.toml` plus a Lint workflow (pyflakes and syntax errors,
      run on every PR). **I4:** `.dockerignore` and a non-root user.
      **I5:** Dependabot.

### Won't do (with reason)
- **R6:** *Correction:* the `components.v1.html` warning filters in `app.py`
  are not dead. Third-party components (such as
  `streamlit-lightweight-charts`) can still emit that warning. The CI grep
  only covers our own code.
- **I9, md5:** the digests are pipeline and contract fingerprints.
  `usedforsecurity=False` changes nothing functionally and isn't worth
  touching the fingerprint code for.
- The other R5 functions are public R2 consumer API. Keep them.

### Needs the owner
- [ ] **W4:** the Python version Streamlit Cloud runs (Manage app →
      Settings). CI will be aligned to it.
- [ ] **W1:** check whether a keep-warm ping runs the script (see the PR
      description for the steps).
- [ ] **R7:** deleting 23 fully merged branches (command in the PR
      description). Git deletions are blocked from this session.
- [ ] **R8:** whether to move the dated audit docs into `docs/archive/`.

### Later
- [ ] I2 + I3: pytest markers instead of the `--ignore` lists
- [ ] I6: extract the CSS from `theme.py` and split the large modules
- [ ] I7 + I8: isolate the test cache directory; xdist
- [ ] I9: audit the `unsafe_allow_html` interpolations
- [ ] Widen the ruff rules (B, UP, SIM) step by step
- [ ] After Stage-4B lands: R2, R3, W5's Stage-4B triggers
