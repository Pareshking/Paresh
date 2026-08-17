# Umiya V1 — Current Audit Loop — 2026-08-17

## Baseline

- Repository: `Pareshking/Umiya`
- Scope: V1 only; V2 excluded.
- Baseline main SHA: `df23646c46f040cb8630ae3975a04941d4b33c4e`
- Current universe correction is based on the repository's NSE index snapshot synchronized on **15 Aug 2026**, which records **752 Nifty Total Market constituents**.

## Current ledger

| ID | Finding | Severity | Root cause | Fix | Validation | Status |
|---|---|---|---|---|---|---|
| C-01 | Missing calendar factors were converted to synthetic cross-sectional zeros | HIGH | `fillna(0)` before composite aggregation | Preserve NaN and renormalize available factor weights | Regression suite + full-universe integration | CLOSED |
| C-02 | Residual-alpha benchmark returns were forward-filled | HIGH | Benchmark reindex used `.ffill()` | Pair stock/benchmark observations without filling | Regression test + full suite | CLOSED |
| C-03 | Portfolio covariance/realized-return paths converted missing returns to zero | HIGH | `fillna(0)` in risk calculations | Use complete paired observations | Regression test + full suite | CLOSED |
| C-04 | Backtester Industry-Relative branch was unreachable and peer mean was self-inclusive | HIGH | Composite predicate included `Industry-Relative` and peer mean included subject stock | Make branch reachable and use leave-one-out peer mean | Regression suite + compile | CLOSED |
| C-05 | Exponential-regression momentum filled missing log prices with zero | HIGH | Vectorized regression used `fillna(0)` | Valid-observation convolution; windows with missing observations remain unavailable | Regression suite + full-universe integration | CLOSED |
| C-06 | Historical datasets used today's date as their economic as-of date | MEDIUM | `max(today, last_data_date)` | Use today's date only for fresh data; anchor stale/historical data to last observation | Historical-date regression test + integration | CLOSED |
| C-07 | Legacy System-1 entry point could bypass calendar-month implementation | HIGH | `calculate_sharpe_momentum()` contained the old row-window path | Delegate compatibility entry point to canonical calendar engine | Regression + integration | CLOSED |
| C-08 | Stale R² references remained in UI and guide | HIGH | Legacy labels/text survived scoring removal | Remove R² columns/text and update methodology wording | Repository validation + E2E | CLOSED |
| C-09 | Qualified-stock correlation view forward-filled prices | MEDIUM | `.ffill().pct_change()` | Use `pct_change(fill_method=None)` | Regression/source validation + E2E | CLOSED |
| C-10 | Volume series was forward-filled | MEDIUM | Volume cache used `.ffill()` | Preserve missing volume observations | Regression + integration | CLOSED |
| C-11 | Cross-sectional normalization had inconsistent sample/population dispersion semantics | MEDIUM | Legacy helper used pandas default sample SD | Use population SD for full cross-sectional population | Regression + integration | CLOSED |
| C-12 | Small cross-sections returned synthetic zero Z-scores | LOW | Helper used zero fallback for insufficient/constant cross-sections | Preserve NaN | Dedicated regression test | CLOSED |
| C-13 | CI validated Python 3.11 while production runtime was Python 3.14.7 | MEDIUM | CI/deployment parity mismatch | Full validation moved to Python 3.14 | 3.14 regression/compile/integration/E2E | CLOSED |
| C-14 | Production V1 selected Nifty Total Market but loader explicitly skipped the Total Market master CSV | HIGH | `_fetch_indices_impl()` skipped `NIFTY TOTAL MARKET`; application default selection is exactly `NIFTY TOTAL MARKET` | Load the canonical Total Market CSV and honor the selected-index filter | New loader regression + 752-stock full integration | VALIDATING |
| C-15 | Validation pipeline and audit report hard-coded the historical 750-stock universe | MEDIUM | Integration script/workflow expected 750 despite current synchronized snapshot containing 752 | Update production validation to current 752 constituent snapshot | Full 752-stock integration | VALIDATING |

## Current universe evidence

The repository's synchronized index metadata dated **15 Aug 2026** records:

- NIFTY 50: 50
- NIFTY NEXT 50: 50
- NIFTY MIDCAP 150: 150
- NIFTY SMALLCAP 250: 250
- NIFTY MICROCAP 250: 252
- NIFTY TOTAL MARKET master snapshot: **752 constituents**

The Nifty Total Market methodology describes the index as targeting 750 stocks, but the actual constituent count can temporarily differ because NSE permits ad-hoc reconstitution/rebalancing. Therefore V1's production universe must use the **current official constituent snapshot**, not a hard-coded 750 assumption.

## Validation state

- Loader correction committed: `a71b14d1985017bf92ad0330fb030b4280b0c222`
- Validation script correction committed: `3bbe7c71ebc811a9a005d66acd1f73a83cdc013b`
- Validation workflow correction committed: `dacdd1e54b074a2c8de0d95040041659ceacbb9e`
- Regression coverage committed: `dc622ac059da89e4e4779da9b1a7d0064fb9b431`
- Full validation run #34 is currently executing against commit `dc622ac059da89e4e4779da9b1a7d0064fb9b431`.

The final PASS/FAIL for the 752-stock production pipeline will be recorded only after that run completes.

## Acceptance state

The universe discrepancy is identified and the code/validation paths have been corrected. It is not yet marked CLOSED until the full 752-stock regression, quantitative integration, and headless Streamlit validation complete successfully.
