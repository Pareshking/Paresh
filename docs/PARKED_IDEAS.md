# Parked Ideas

Features and integrations that were researched, discussed, and deliberately
set aside. Recorded here so the reasoning does not have to be reconstructed
from scratch.

---

## 1. `st.navigation()` + `st.Page()` — URL routing

**What it is.** Streamlit 1.36+ supports true multi-page routing with
`st.navigation([st.Page(...), ...])` and sidebar navigation. Each page gets a
distinct URL slug.

**Why parked.** Requires a full app restructure: `app.py` currently loads all
data at the top level and passes it to every tab function as arguments. Moving
to `st.Page()` would require either re-loading data in every page or storing it
in `st.session_state` and re-running all momentum computation if it's absent.
The data-loading + ranking pipeline takes 10–30 seconds; a page that re-loads
from cold on navigation would feel broken.

**When it makes sense.** If the app is split so that the heavy pipeline runs
in exactly one "home" page and all other pages read from session state (with a
redirect to home if state is missing), the restructure becomes tractable. The
Guide tab is a pure-static page that could be extracted immediately with no
data dependency. Leave in mind for when navigation UX becomes the binding
constraint.

---

## 2. `st.column_config` for the main screener table

**Decision: not adopted.**

The main screener table (and all secondary tables — live book, monthly returns,
closed trades, sector breakdown, track record) uses `render_saas_table` in
`src/ui/theme.py`. This is a custom HTML renderer with per-cell conditional
coloring: green/red on every % return cell, sector color coding, JetBrains Mono
numerics, and sticky headers.

`st.dataframe` with `column_config` supports progress bars and type-specific
formatting but cannot do per-cell conditional coloring of individual values.
Switching would lose the visual clarity that makes the live book and closed-
trades tables immediately scannable.

The backtest parameter-sweep table was adopted as the correct home for
`column_config` — it uses `st.dataframe` and has no per-cell coloring need.

---

## 3. External fundamental data

### 3a. `jadeja-rajdeep/nse-momentum-screener`

A GitHub Pages static site that publishes a daily `m.json` with ~2,768 rows
and ~98 columns including Delivery %, EPS/Sales growth, PE, ROE, Promoter
Holding %, and RS metrics. The data is high quality and updated daily.

**Why not used.** The pipeline that generates `m.json` — a MySQL database
exported via PHPMyAdmin — is entirely private. It belongs to an individual, has
no SLA, no API contract, and no guarantee of format stability. Depending on it
would make the app silently break whenever the owner changes schema, pauses
updates, or takes down the site. Not reliable as a production data source.

### 3b. Screener.in

Does not have a public API. What appear to be API calls are undocumented
frontend endpoints that require authenticated session cookies. Using them at
scale (750 stocks) would violate Screener.in's terms of service and would break
whenever their frontend ships changes. Not practical.

---

## 4. Google Sheets integration (issue #14)

**What was proposed.** Pull fundamental data (PE, ROE, EPS growth, Delivery %)
from a Google Sheet that the user populates manually or via a sheet-level
IMPORTFROMWEB or script.

**Why parked.** Requires:
- A service-account JSON credential committed or injected as a secret
- A stable schema agreement between the sheet and the loader
- Handling the Sheet being empty, stale, or inaccessible on app startup

The external-data sources that would feed such a sheet are either private (3a)
or ToS-restricted (3b). Until a reliable, low-maintenance fundamental data
source is identified, building the integration layer first is solving the wrong
problem.

**When it makes sense.** If a clean fundamental data source emerges — a paid
vendor, a licensed feed, or a self-managed scraper with explicit permission —
the Google Sheets transport layer is straightforward to add. The integration
would sit in a new `src/loaders/fundamentals_loader.py` and merge on ISIN or
NSE symbol.

---

## 5. Notes

- **NSE DUMMY placeholders** (e.g. `DUMMYTRVN`) — already filtered in the
  loader, documented in README and audit tracker 2.15. Not a parked idea;
  closed.
- **Survivorship bias** — tracked in `docs/V1_AUDIT_TRACKER.md` §5 under its
  own standing decision. Constituent snapshots accumulate from 2026-08-19
  onwards.
- **Raw-price rebuild (NEXT 9)** — tracked in `docs/V1_AUDIT_TRACKER.md` §4
  and fully designed in `docs/RAW_PRICE_REBUILD.md`. Not started; awaiting user
  approval.
