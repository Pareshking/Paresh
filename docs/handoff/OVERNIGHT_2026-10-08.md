# Overnight engineering loop (owner logged off 2026-10-08 ~01:00 IST; wants everything live by morning)

Repo: C:\Users\Quali\Paresh (GitHub Pareshking/Paresh). Read CLAUDE.md, docs/TODO.md first.
Test venv (pandas 3.0.6, streamlit 1.65): C:\Users\Quali\AppData\Local\Temp\claude\C--Users-Quali-Paresh\a5241b96-4bda-4b2a-8dc3-0ed4402cfc7d\scratchpad\p3\Scripts\python.exe
(PYTHONUTF8=1; known flaky on Windows only: tests/test_ss_prices.py file lock; tests/test_build_info.py in worktrees).
GitHub DNS drops sometimes: retry git/gh in a loop.

## Rules (owner-approved, keep them)
- Branch from origin/main per item; small PRs; title says what changed; commit ends
  "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"; PR body ends
  "🤖 Generated with [Claude Code](https://claude.com/claude-code)".
- Owner approved merging each item after CI is green ON THE PR'S CURRENT HEAD (check headRefOid).
- Batch merges where possible: every merge redeploys the live app (#412 now reloads in place, so less harmful).
- Data: never hand-change prices; evidence for every data fix; run the audits.
- After merging, check main CI (Lint, V1 Full Validation, V1 Production QA). A Production QA
  "Unexpected served revision X for Y" failure is a race with a newer data commit, not a defect.
- Update docs/TODO.md rows (with run/PR proof) as items finish; one docs PR at the end.
- Write progress below (Status log) after each item.

## Queue (in order)
1. [ ] S56 (high): committed data/nse_prices/actions.parquet has NO rights rows (52 bonus, 39 split, 18 demerger).
   Find why scripts/sync_nse_prices.py (or nse_bundle classify/filters) drops kind=="rights"; add them so
   nse_adjusted.rights_factor applies (needs face value + ratio + premium, see nse_adjusted._rights).
   Then: replay the 750 record (model_record.record_run / track_record months Jan-Sep 2026) with rights
   applied vs today, report any month that changes (do NOT rewrite frozen months; record it in TODO for the owner).
   Evidence: reports/followups_s52_s53_2026-10-07.md (merged in #408) lists 14 rights ex-dates since Sep 2024 (HCC 5 Dec 2025 -23% raw).
2. [ ] Bug: Kite basket sized on Rs 10 lakh (actions_view.py ~292 reads a capital nothing sets) while Portfolio uses Rs 20 lakh -> use the Portfolio capital. Test.
3. [ ] Bug: Configuration "Volatility targeting" changes nothing (config_view.py ~402-406; portfolio_view ~493 discards it; backtest never receives it) -> remove the control (owner chose "fix both": remove it). Keep tests green.
4. [ ] UI audit, all 15 PRs (owner: "Do all 15 PRs"). Full audit: scratchpad\ui_audit.md. Order:
   1 Actions text pass; 2 kit.breakdown (Portfolio "Industry exposure" style) used by Qualified "Where they come from";
   3 Portfolio each figure once (update scripts/portfolio_production_qa.py in the same PR);
   4 one calendar grid; 5 Backtest as research only (owner OK given by "do all"); 6 one trades/rebalances renderer;
   7 footer + as-of once; 8 captions/notes/empty states; 9 one number formatter; 10 Configuration (vol targeting already removed);
   11 Sectors/RRG/Breadth/Watchlist text; 12 stock page incl. peers renderer; 13 Screener movers; 14 Guide rewrite; 15 dead kit code.
   Each: run full tests + headless smoke (scripts/headless_smoke.py) and look at the page locally
   (.claude/launch.json "streamlit-local", port 8599) before merging.
5. [ ] Storage clean-up: release data-latest leftovers (e.g. tmp_session_2026-10-03.zip, prices.parquet / prices_extra.parquet /
   prices_full.parquet if nothing reads them -- grep first; ref_long_price_audit_2026-10-03.zip keep?). Only delete assets
   nothing in the repo or workflows reads; list them in the PR/TODO. Deleting release assets is destructive: if unsure, record, don't delete.
6. [ ] S24: SS history run 37666859753 (started 7 Oct ~23:40 IST). When it completes, read ss_manifest.json
   (full_history count); if stocks still lack history, dispatch another: gh workflow run ss_sync.yml -f mode=history -f rounds=17 -f per_round=40
7. [ ] Final: docs/TODO.md updated, one docs PR merged; summary for the owner in the chat (what merged, PR links, CI, anything left).

## Done tonight (for reference)
#394 sweep, #395 first-month crash, #396 data safety, #397 wording, #400 BSE gap fill, #401 weekly fill (+7 stocks, SHILCTECH bonus),
#402 QA live-month, #403 Alpha difference, #404 Entry Weight crash, #405 Streamlit 1.65, #406/#409 docs, #407 build 35->2.5 min,
#408 gap audit ISIN, #410 History precompute (867 MB -> stored, app peak 578 MB), #411 startup warnings, #412 reload in place.

## Status log
- 2026-10-08 01:05 IST: loop set up; #412 and #408 merged.
