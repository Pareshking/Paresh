# Umiya V1 — Current Audit Loop — 2026-08-17

## Baseline

- Repository: `Pareshking/Umiya`
- Scope: V1 only; V2 excluded.
- Baseline main SHA: `df23646c46f040cb8630ae3975a04941d4b33c4e`
- Final code-validation SHA: `02e7440c30bd2a826fa84dc542088714cbd1b04f`
- Current main also contains only the temporary-workflow removal commit after that code-validation SHA; no source change was made by the removal commit.

## Current ledger

| ID | Finding | Severity | Root cause | Fix | Validation | Status |
|---|---|---|---|---|---|---|
| C-01 | Missing calendar factors were converted to synthetic cross-sectional zeros | HIGH | `fillna(0)` before composite aggregation | Preserve NaN and renormalize available factor weights | 45-test suite + 750-stock integration | CLOSED |
| C-02 | Residual-alpha benchmark returns were forward-filled | HIGH | Benchmark reindex used `.ffill()` | Pair stock/benchmark observations without filling | Regression test + full suite | CLOSED |
| C-03 | Portfolio covariance/realized-return paths converted missing returns to zero | HIGH | `fillna(0)` in risk calculations | Use complete paired observations | Regression test + full suite | CLOSED |
| C-04 | Backtester Industry-Relative branch was unreachable and peer mean was self-inclusive | HIGH | Composite predicate included `Industry-Relative` and peer mean included subject stock | Make branch reachable and use leave-one-out peer mean | Regression suite + compile | CLOSED |
| C-05 | Exponential-regression momentum filled missing log prices with zero | HIGH | Vectorized regression used `fillna(0)` | Valid-observation convolution; windows with missing observations remain unavailable | Regression suite + full 750-stock integration | CLOSED |
| C-06 | Historical datasets used today's date as their economic as-of date | MEDIUM | `max(today, last_data_date)` | Use today's date only for fresh data; anchor stale/historical data to last observation | Historical-date regression test + full integration | CLOSED |
| C-07 | Legacy System-1 entry point could bypass calendar-month implementation | HIGH | `calculate_sharpe_momentum()` contained the old row-window path | Delegate compatibility entry point to canonical calendar engine | Full regression + full integration | CLOSED |
| C-08 | Stale R² references remained in UI and guide | HIGH | Legacy labels/text survived prior scoring removal | Remove R² columns/text and update methodology wording | Repository validation + full E2E | CLOSED |
| C-09 | Qualified-stock correlation view forward-filled prices | MEDIUM | `.ffill().pct_change()` | Use `pct_change(fill_method=None)` | Regression/source validation + E2E | CLOSED |
| C-10 | Volume series was forward-filled | MEDIUM | Volume cache used `.ffill()` | Preserve missing volume observations | Full regression + integration | CLOSED |
| C-11 | Cross-sectional normalization had inconsistent sample/population dispersion semantics | MEDIUM | Legacy helper used pandas default sample SD | Use population SD for full cross-sectional population | Full regression + integration | CLOSED |
| C-12 | Small cross-sections returned synthetic zero Z-scores | LOW | Helper used zero fallback for insufficient/constant cross-sections | Preserve NaN | Dedicated regression test | CLOSED |
| C-13 | CI validated Python 3.11 while production runtime was Python 3.14.7 | MEDIUM | CI/deployment parity mismatch | Full validation moved to Python 3.14 | Full 3.14 regression, compile, 750 integration, E2E | CLOSED |

## Validation evidence

- Python: 3.14.7
- Full regression: **45 passed**
- Compileall: **PASS**
- Full 750-stock integration: **PASS**
- Deprecated Streamlit HTML scan: **PASS / NONE**
- Headless Streamlit: **PASS**
- Rendered tabs in headless run: **12**
- Rendered dataframes: **1**
- 750-stock universe: **750 requested / 750 loaded / 750 price series / 750 ranked**
- Latest as-of: **2026-08-17**
- Rank monotonicity: **PASS**
- Score monotonicity by rank: **PASS**

## Quantitative observations

Factor coverage in the final 750-stock run:

- 1M: 750
- 3M: 750
- 6M: 750
- 9M: 737
- 12M: 718

The 9M/12M missingness remains explicit; it is not converted into synthetic zero factor scores. The composite still ranks 750 stocks because available factor weights are renormalized.

Population standard deviations:

- 1M: 0.9702
- 3M: 0.8855
- 6M: 0.8204
- 9M: 0.8331
- 12M: 0.9138

Factor correlation matrix was generated in the validation artifact. Highest off-diagonal correlation was 9M/12M at 0.9078; lowest was 1M/12M at 0.4069.

## Remaining non-blocking observations

1. Streamlit Community Cloud production logs are account-scoped and are not exposed through the connected GitHub interface. Current code is fully validated by GitHub CI/headless Streamlit, but the final Cloud log must be checked in the user's Streamlit workspace after the latest main commit.
2. `requirements.txt` remains range-based rather than fully locked. Current Python 3.14 CI resolved and validated the environment successfully; dependency pinning is a separate reproducibility decision, not required for the current correctness audit.
3. Some strategy/backtester methods intentionally retain explicit row-window parameters for non-System-1 strategy research. System-1 production scoring is canonical calendar-month based. No production System-1 path depends on those legacy parameters.
4. Dynamic HTML rendering uses trusted application-generated data rather than arbitrary user-entered HTML. A future hardening pass could add explicit HTML escaping to all dynamic display values; no CRITICAL/HIGH issue was found from current user-input paths.

## Acceptance state

All objectively resolvable code, mathematical, data-integrity, schema, Streamlit runtime, testing, and 750-stock integration findings from this audit loop are closed. Production Cloud log confirmation is the only external observation not directly accessible from the connected engineering environment.
