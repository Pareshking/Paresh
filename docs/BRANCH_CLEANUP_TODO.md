# To do: delete merged remote branches

**Status:** open. **Owner:** repository owner. **Added:** 2026-09-25 (PR #151).

Delete this file once every branch below is gone.

## Why this is a manual step
Every branch below had **0 commits that are not on `main`** when checked on
2026-09-25, so deleting them loses nothing. Claude Code sessions can push
branches but cannot delete them: GitHub returns HTTP 403, as it did in the
August cleanup too. So the owner has to do this.

## Do NOT delete
- Any `agent/*` or `*stage4b*` branch (Stage-4B is in development)
- `audit-backup-*` and `archive/*` (kept as markers on purpose)
- `fix/r2-membership-test-live-change` (another session's branch, PR #152)
- Any branch with an open pull request

## Branches to delete (22)

| # | Branch | Done |
|---|---|---|
| 1 | `claude/multi-agent-audit-framework-upy0zj` | [ ] |
| 2 | `claude/pr-75-4b-interference-8ndpep` | [ ] |
| 3 | `claude/stock-return-calculations-bug-28jrcy` | [ ] |
| 4 | `claude/streamlit-warnings-performance-fn07h8` | [ ] |
| 5 | `claude/umiya-stale-frontend-data-vguzpv` | [ ] |
| 6 | `claude/umiya-v1-qa-hardening-itgv19` | [ ] |
| 7 | `fix/production-universe-and-r2-deep-history` | [ ] |
| 8 | `fix/ranking-universe-reconciliation` | [ ] |
| 9 | `fix/reduce-streamlit-repeat-work` | [ ] |
| 10 | `r2/bootstrap-line-by-line-hardening` | [ ] |
| 11 | `r2/final-acceptance-doc-sync` | [ ] |
| 12 | `r2/fix-bootstrap-pytest` | [ ] |
| 13 | `r2/fix-bootstrap-python-modulepath` | [ ] |
| 14 | `r2/fix-bootstrap-pythonpath` | [ ] |
| 15 | `r2/fix-membership-revision-resolution` | [ ] |
| 16 | `redesign-v3-design` | [ ] |
| 17 | `redesign-v3-doc` | [ ] |
| 18 | `redesign-v3-docs` | [ ] |
| 19 | `redesign-v3-final` | [ ] |
| 20 | `redesign-v3-spec` | [ ] |
| 21 | `redesign-v3-spec2` | [ ] |
| 22 | `redesign-v3-ui` | [ ] |

## Option A: GitHub website (works on a phone)
1. Open <https://github.com/Pareshking/Paresh/branches/all>.
2. Type part of a name into the search box (`redesign-v3`, `r2/`, `fix/`,
   `claude/`).
3. Tap the 🗑️ icon next to each branch in the table above, and only those.
4. A mistake can be undone: GitHub shows **Restore** right after a delete.

## Option B: one command (from any computer with a clone)
Check first that nothing new landed on any of them. The loop prints only
branches that are **not** safe to delete; empty output means go ahead:

```bash
git fetch --prune origin
for b in $(sed -n 's/^| [0-9]* | `\(.*\)` |.*/\1/p' docs/BRANCH_CLEANUP_TODO.md); do
  n=$(git rev-list --count origin/main..origin/$b 2>/dev/null) || continue
  [ "$n" = 0 ] || echo "NOT MERGED: $b ($n commits)"
done
```

Then delete:

```bash
git push origin --delete \
  claude/multi-agent-audit-framework-upy0zj claude/pr-75-4b-interference-8ndpep \
  claude/stock-return-calculations-bug-28jrcy claude/streamlit-warnings-performance-fn07h8 \
  claude/umiya-stale-frontend-data-vguzpv claude/umiya-v1-qa-hardening-itgv19 \
  fix/production-universe-and-r2-deep-history fix/ranking-universe-reconciliation \
  fix/reduce-streamlit-repeat-work r2/bootstrap-line-by-line-hardening \
  r2/final-acceptance-doc-sync r2/fix-bootstrap-pytest r2/fix-bootstrap-python-modulepath \
  r2/fix-bootstrap-pythonpath r2/fix-membership-revision-resolution \
  redesign-v3-design redesign-v3-doc redesign-v3-docs redesign-v3-final \
  redesign-v3-spec redesign-v3-spec2 redesign-v3-ui
```

## Also open: older pull requests to triage

These PRs from 2026-09-22/23 are still open. Each branch carries 1–9 commits
whose exact patches are not on `main`, but later merges (#127, #148, #149 and
others) may have landed the same fixes in different form. Production QA and
every R2 check are green on `main`, so none of them is blocking anything.
Decide for each one: merge, or close with a one-line reason.

| PR | Branch | Size |
|---|---|---|
| #147 | `verify/new-symbol-history` | 1 file, +18 |
| #142 | `fix-production-nav-probe-v6` | 2 files, +37/−11 |
| #137 | `final-qa-popover-fix` | 2 files, +33/−4 |
| #136 | `fix-production-qa-popover-race` | 2 files, +64/−6 |
| #126 | `r2-final-foundation` | 9 files, +181/−213 |
| #120 | `r2-publication-idempotency-and-index-fetch` | 5 files, +70/−23 |
| #116 | `r2-nse-index-final` | 3 files, +82/−10 |
| #115 | `r2-nse-index-fix2` | 2 files, +72/−10 |

Once a PR is closed or merged, its branch can be deleted too.

## When finished
Delete this file in a small PR, or ask a Claude session to remove it. Also
tick R7 in `docs/CODE_AUDIT_2026-09-25.md`.
