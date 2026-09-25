# Changelog

## 2026-09-25 — Full code audit (merged up to #177)

- Owner decisions shipped:
  - 1B: ranking windows count back from the last price date.
  - 2B: up to five stragglers are ranked on their last print (⏸) instead of holding the ranking back.
  - 3B: the price fingerprint covers the whole history.
- UI read line by line:
  - escaping of every user- or vendor-supplied string;
  - exact index-tag matching;
  - cache keys that change when the history changes;
  - the navigation menu now closes when a page is chosen.
- Production QA:
  - a newer build that contains the triggering commit is no longer a mismatch;
  - the menu-reachability and nav-styling checks now measure what they claim;
  - a Reset that cannot be clicked is now a failure.
- Runtime dependencies pinned to the tested versions. The R2 read gate is skipped on Dependabot PRs and re-runs on main when `requirements.txt` changes.
- The Yahoo index-price fallback only accepts an exact index name.
- R2 storage size report added. Retention is awaiting the owner's decision.

## 2026-09-23 — Production ranking and Streamlit runtime hardening

- Enforced 100% current-universe coverage for canonical ranking sessions, eliminating the 749/750 acceptance path caused by the former 90% coverage floor.
- Added explicit symbol reconciliation diagnostics for precomputed-ranking rejection paths: missing, extra and duplicate symbols.
- Kept NSE DUMMY* placeholder filtering as the canonical tradability rule; no ticker aliases are introduced.
- Confirmed the canonical ranking source remains Screener/R2; Yahoo-origin data remains a separate deep-history/archive/healing feed.
- Reduced repeated Streamlit work by memoizing ranking-contract validation and Screener-frame shaping using correctness-preserving cache identities.
- Suppressed duplicate source-selection and precomputed-acceptance log messages when the logical decision is unchanged.
- Added production documentation covering the R2 path, 750-row completeness contract, Streamlit engine-skipped semantics and verification state.
- Verified the post-merge live deployment: main loaded successfully, the R2 Screener store was read, and a **750-row precomputed ranking was accepted**.

## 2026-09-22 — R2 production publication hardening

- R2 publication uses immutable content-addressed revisions, manifests and current pointers with read-back/hash verification.
- R2-focused CI is isolated from V1 Stage-4B research validation.
- Screener remains the canonical V1 ranking price source; Yahoo is separate archive/deep history.
