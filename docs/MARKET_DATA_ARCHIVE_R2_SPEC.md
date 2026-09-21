# Market Data Archive & Cloudflare R2 Architecture Specification

**Status:** Design / pre-implementation  
**Document purpose:** Define the long-term market-data architecture before changing production data flow.  
**Repository:** `Pareshking/Paresh`  
**Target storage:** Cloudflare R2 Standard  
**Last updated:** 2026-09-21

---

## 1. Executive decision

The project is evolving from a Streamlit application that needs market data into a quantitative research system that must preserve historical market data for future:

- backtesting;
- point-in-time universe reconstruction;
- index constituent change analysis;
- survivorship-bias-aware research;
- corporate-action investigation;
- signal and ranking reproducibility;
- long-horizon research;
- future data-source comparisons.

Therefore:

> **Cloudflare R2 will become the canonical long-term market-data archive.**

Git/GitHub remains the canonical home for:

- application source code;
- configuration;
- tests;
- schemas/contracts;
- small reference data;
- reproducible research code.

GitHub Releases may remain as an application snapshot/fallback mechanism during and after migration, but they are not the intended long-term data warehouse.

**Important:** This document records the architecture and migration plan only. It does not authorize changing the live data path yet.

---

## 2. Why we are doing this now

The current repository already publishes a compressed price snapshot as a rolling GitHub Release asset rather than committing market data to Git history.

The current configuration records approximately:

- ~10.5 MB compressed trailing price snapshot;
- ~2.5 GB/year of additional Git history if that snapshot were committed daily.

That is already evidence that Git is the wrong permanent storage layer for a growing market-data archive.

The immediate GitHub storage problem is not urgent. The architectural problem is more important:

> Historical data should accumulate independently of application deployments, Git history, and Streamlit container lifetime.

Moving to R2 before several more years of accumulation gives us a clean boundary while the dataset is still manageable.

---

## 3. Current architecture — verified baseline

### 3.1 Data sources

The current system deliberately keeps price sources separate.

### Screener.in

The Screener pipeline currently collects a separate close/volume history.

The repository documents the Screener source as:

- Close;
- Volume;
- no reliable intraday OHLC history from the current chart endpoint;
- approximately one year of daily resolution, with older data downsampled by the vendor;
- one request per symbol per nightly run;
- paced requests;
- accumulated locally rather than replacing the historical store.

The current Screener sync uses the NIFTY TOTAL MARKET universe and resolves/caches Screener company IDs.

### Yahoo

The existing Yahoo pipeline supplies OHLCV-style price history and remains a separate source.

The repository deliberately does not splice Screener and Yahoo price series together because their adjustment/corporate-action treatment can differ.

This separation is a permanent architectural principle unless explicitly revised by a future data-quality decision.

### NSE / official index data

Official NSE index constituent files are already synchronized into the repository.

The system also has a membership-history mechanism that derives point-in-time membership from the history of those constituent files.

### Other data already collected

The daily sync also handles or produces:

- market-cap snapshots;
- TradingView classification reconciliation;
- trading-day evidence;
- all-time-high snapshots;
- rankings snapshot;
- price snapshots;
- index data.

These datasets must be considered separately when designing the R2 archive. Not every generated artifact belongs in the long-term market-data lake.

---

## 4. Core architectural principle

The archive is **not** a cache.

A cache can be deleted and regenerated.

The R2 archive is intended to be:

> **the durable historical record from which future research datasets can be reconstructed.**

Therefore archive writes must be conservative.

### Never silently:

- overwrite valid history with a smaller dataset;
- replace one vendor's series with another vendor's series;
- infer missing historical observations;
- delete symbols merely because they left today's universe;
- rewrite historical membership without recording why;
- publish an incomplete dataset as complete;
- treat a current universe as a historical universe;
- mix adjusted and unadjusted price bases.

---

# 5. Target architecture

\`\`\`
                         DATA SOURCES
                              |
             +----------------+----------------+
             |                |                |
         Screener             Yahoo            NSE
         Close/Volume         OHLCV            Index files
             |                |                |
             +----------------+----------------+
                              |
                              v
                    GitHub Actions / Sync
                              |
                 validate / normalize / freeze
                              |
                              v
                 +-------------------------+
                 |      CLOUDFLARE R2      |
                 |                         |
                 |  MASTER DATA ARCHIVE    |
                 |                         |
                 |  prices                 |
                 |  index snapshots        |
                 |  membership history     |
                 |  raw source snapshots   |
                 |  manifests/checksums    |
                 +-----------+-------------+
                             |
                 +-----------+-----------+
                 |                       |
                 v                       v
          Streamlit application     Research / Backtest
          current snapshot          full historical archive
\`\`\`

The application is a **consumer** of the archive, not its owner.

---

# 6. R2 account and storage policy

Use a dedicated private R2 bucket for the research archive.

Suggested logical bucket name:

\`paresh-market-data\`

The actual bucket name may differ if the user's Cloudflare account requires another naming convention.

### Storage class

Use **R2 Standard** initially.

Current Cloudflare pricing documentation states:

- 10 GB-month Standard storage free per month;
- 1 million Class A operations free per month;
- 10 million Class B operations free per month;
- Internet egress is free;
- Standard storage is $0.015/GB-month after the included storage;
- Class A is $4.50/million operations;
- Class B is $0.36/million operations.

Source: Cloudflare R2 pricing documentation:
https://developers.cloudflare.com/r2/pricing/

There is **not** a 500 GB or 1 TB free-storage allowance. The free Standard tier is 10 GB-month.

R2 nevertheless supports unlimited storage per bucket and unlimited objects, with a maximum object size of 5 TiB. Source:
https://developers.cloudflare.com/r2/platform/limits/

At current Standard pricing, approximate storage-only cost is:

| Stored data | Approx. monthly storage cost |
|---:|---:|
| 10 GB | $0 |
| 50 GB | $0.60 |
| 100 GB | $1.35 |
| 500 GB | $7.35 |
| 1 TB / 1000 GB | $14.85 |

These are storage estimates only; operation charges depend on request volume. Egress remains free under current R2 pricing.

---

# 7. Security model

The R2 bucket should remain **private** initially.

Access should be separated by purpose.

### GitHub Actions

Required capability:

- write archive objects;
- read/verify archive objects;
- list relevant objects.

### Streamlit

Required capability:

- read archive objects only.

### Research/backtest jobs

Initially:

- read-only.

Write access should not be given to application processes unless a specific future job requires it.

### Credentials

Credentials must live only in:

- GitHub Actions Secrets;
- Streamlit Secrets;
- an equivalent secure runtime secret store.

Never commit:

- R2 Access Key ID;
- R2 Secret Access Key;
- Cloudflare API tokens;
- bucket credentials.

Cloudflare documents the S3-compatible R2 API and bucket-scoped API-token permissions. R2 can be accessed with standard S3 SDKs such as boto3:
https://developers.cloudflare.com/r2/get-started/s3/

---

# 8. Proposed archive layout

The exact physical partitioning remains an implementation decision, but the logical namespace should be stable.

Suggested layout:

\`\`\`
archive/
  prices/
    screener/
    yahoo/

  indices/
    constituents/
    membership/

  fundamentals/
    <future source-specific datasets>

  market_caps/

  corporate_actions/

  trading_days/

  raw/
    screener/
    yahoo/
    nse/

  manifests/

  schemas/

  snapshots/
    application/
    rankings/
\`\`\`

The archive should avoid millions of tiny files unless there is a demonstrated research/query benefit.

Parquet is the preferred analytical format for tabular historical data.

CSV may be retained for source-faithful raw snapshots where appropriate.

JSON is appropriate for compact metadata/manifests.

---

# 9. Price datasets

## 9.1 Screener price history

Logical dataset:

\`prices/screener/\`

Minimum contract:

| Column | Meaning |
|---|---|
| date | Market session date |
| symbol | NSE symbol |
| close | Screener close |
| volume | Screener volume |
| source | \`screener\` |
| collected_at | Archive ingestion timestamp |

The dataset must preserve the Screener price basis.

It must not be silently combined with Yahoo values.

### Important limitation

The current Screener collection path is daily only for approximately the recent year and is downsampled by Screener beyond that window.

Therefore:

> We cannot assume that a brand-new R2 archive can be populated with many years of daily Screener history from one request.

The archive must grow continuously from nightly collection.

This makes uninterrupted daily collection strategically valuable.

---

## 9.2 Yahoo price history

Logical dataset:

\`prices/yahoo/\`

Expected fields:

- date;
- symbol;
- open;
- high;
- low;
- close;
- adjusted close;
- volume;
- source;
- collection metadata.

The exact adjusted/unadjusted semantics must be documented in the schema before migration.

Yahoo data remains independent of Screener.

---

# 10. No source splicing

This is a hard rule.

Do not do:

\`\`\`
Screener 2024-2026
       +
Yahoo 2020-2024
       =
one "price" series
\`\`\`

unless a future research-specific transformation explicitly declares:

- source boundary;
- adjustment basis;
- transformation;
- validation;
- resulting dataset identity.

The canonical source datasets remain separate.

A derived research series can exist later, but it must never overwrite the raw/canonical source history.

---

# 11. Index constituent history

This is a first-class archive dataset.

The purpose is to answer:

> Who was actually a constituent of an index on a historical date?

It is not sufficient to store only today's constituents.

Target logical dataset:

\`indices/membership/\`

Suggested normalized contract:

| Column | Meaning |
|---|---|
| index | Index name |
| symbol | NSE symbol |
| effective_from | First date membership applies |
| effective_to | Last date membership applies |
| source | Source dataset |
| evidence_date | Date of source snapshot |

The existing repository already has \`build_membership_history.py\`, which derives NIFTY TOTAL MARKET membership history from Git history.

That existing logic is valuable migration input.

The R2 design should eventually make the historical membership dataset independent of Git commit history.

---

# 12. Preserve departed stocks

A symbol leaving NIFTY TOTAL MARKET must **not** cause its historical price data to be deleted.

Example:

\`\`\`
ABC
2018 ----------------------------- 2028
                                      |
                               leaves universe
\`\`\`

The price history remains.

Membership simply changes:

\`\`\`
NIFTY TOTAL MARKET
ABC
effective_to = 2028-...
\`\`\`

This is necessary for survivorship-bias-aware research.

---

# 13. Point-in-time universe reconstruction

Future research must be able to reconstruct:

\`\`\`
Universe(as_of = 2024-06-30)
Universe(as_of = 2025-06-30)
Universe(as_of = 2026-06-30)
\`\`\`

rather than always using:

\`\`\`
Universe(today)
\`\`\`

This is essential for meaningful historical backtests.

The same principle should eventually apply to:

- NIFTY 50;
- NIFTY NEXT 50;
- NIFTY MIDCAP 150;
- NIFTY SMALLCAP 250;
- NIFTY MICROCAP 250;
- NIFTY TOTAL MARKET;
- any future tracked index.

---

# 14. Raw source preservation

Where practical, retain source-faithful snapshots under:

\`raw/<source>/\`

Examples:

\`\`\`
raw/nse/2026-09-18/
raw/screener/2026-09-18/
raw/yahoo/2026-09-18/
\`\`\`

The purpose is auditability.

If a parser or normalization rule is later found to be wrong, the normalized dataset can be rebuilt from the original evidence instead of relying on a transformed copy.

Raw retention policy is still an open implementation decision where source terms or storage growth make indefinite retention inappropriate.

---

# 15. Dataset manifests

Every published canonical dataset should have a manifest.

Minimum metadata:

\`\`\`json
{
  "dataset": "prices/screener",
  "as_of": "YYYY-MM-DD",
  "created_at": "...",
  "source": "screener",
  "schema_version": 1,
  "row_count": 0,
  "symbol_count": 0,
  "min_date": "YYYY-MM-DD",
  "max_date": "YYYY-MM-DD",
  "sha256": "...",
  "pipeline_version": "..."
}
\`\`\`

The manifest is part of the archive contract.

It allows a future research run to state exactly which dataset it consumed.

---

# 16. Immutable versus mutable objects

The archive should distinguish two concepts.

### Historical snapshots

Prefer immutable objects.

Example:

\`\`\`
snapshots/prices/screener/2026-09-18.parquet
\`\`\`

### Current convenience snapshot

May be updated:

\`\`\`
snapshots/application/screener_prices.parquet
\`\`\`

The convenience snapshot can point to the latest validated archive state.

The historical archive should never depend on a mutable \`latest\` object alone.

---

# 17. Checksums and integrity

Every important published object should have a checksum recorded in its manifest.

Migration must verify:

1. source file generated;
2. upload completed;
3. object exists in R2;
4. object size matches;
5. checksum matches;
6. manifest matches object;
7. downstream reader can open the Parquet file.

A successful upload alone is not sufficient.

---

# 18. Daily sync target flow

The desired daily pipeline is:

\`\`\`
1. Determine market/session date
2. Fetch source data
3. Validate source completeness
4. Reject unsettled sessions
5. Normalize without changing source semantics
6. Merge into canonical source history
7. Validate no historical shrinkage
8. Validate coverage
9. Write archive candidate
10. Calculate checksum
11. Upload to R2
12. Read back / verify
13. Publish manifest
14. Publish application snapshot
15. Publish ranking snapshot
16. Only then mark the archive publication successful
\`\`\`

The exact transaction/order mechanics are an implementation task.

---

# 19. Failure philosophy

A failed data collection must fail **closed**, not silently corrupt history.

Examples:

### Source returns partial universe

Do not declare the session complete.

### Source returns zero rows

Do not replace an existing archive.

### New file is smaller unexpectedly

Do not publish automatically.

### Historical dates disappear

Do not overwrite canonical history.

### Duplicate rows

Reject or normalize deterministically before publication.

### Current session still trading

Do not freeze the intraday value as a close.

The current Screener sync already contains some of these safeguards; the R2 layer should preserve and strengthen them.

---

# 20. Application snapshot versus research archive

These are deliberately different products.

## Application snapshot

Optimized for:

- Streamlit cold start;
- current ranking;
- current UI;
- small download;
- fast loading.

It should remain relatively small.

## Research archive

Optimized for:

- completeness;
- historical depth;
- reproducibility;
- backtesting;
- point-in-time reconstruction.

It may grow continuously.

The application must never be forced to download the entire research archive on startup.

---

# 21. Current GitHub Release role

During migration, the current rolling GitHub Release assets remain useful.

Current examples include:

- \`prices.parquet\`;
- \`prices_full.parquet\`;
- \`screener_prices.parquet\`;
- \`rankings.parquet\`.

Target transition:

\`\`\`
BEFORE

GitHub Release
      |
      +--> Streamlit
      |
      +--> archive-ish data


AFTER

R2 canonical archive
      |
      +--> Streamlit snapshot
      |
      +--> Research/backtest
      |
      +--> Historical reconstruction

GitHub Release
      |
      +--> optional fallback / emergency snapshot
\`\`\`

Do not remove the existing release path until R2 has passed the migration gates.

---

# 22. Migration strategy

Migration must be incremental.

## Phase 0 — Documentation

This document.

No production data-path change.

## Phase 1 — R2 connectivity

Create private bucket.

Implement a small storage adapter.

Test:

- put;
- head;
- get;
- list;
- checksum;
- failure handling.

No application dependency.

## Phase 2 — Historical bootstrap

Upload existing validated datasets.

Verify local versus R2:

- row count;
- columns;
- date range;
- symbols;
- file size;
- checksum;
- sample values.

## Phase 3 — Dual publication

Daily sync publishes:

- existing GitHub Release artifacts;
- R2 archive artifacts.

Neither replaces the other yet.

Compare outputs over multiple successful runs.

## Phase 4 — R2 reader

Add R2 read capability behind a configuration flag.

Production still defaults to the proven GitHub path.

## Phase 5 — R2 canonical

After validation:

\`R2 -> primary\`

\`GitHub Release -> fallback\`

## Phase 6 — GitHub data reduction

Only after a stable period:

- stop treating GitHub Release as the permanent archive;
- retain only the application snapshot/fallback required by the deployment;
- keep all canonical historical data in R2.

---

# 23. Migration acceptance gates

R2 migration is not complete because an upload succeeds.

The following gates must pass.

### Gate A — completeness

R2 contains every required historical row from the migration source.

### Gate B — equality

For migrated datasets:

\`local == R2\`

within the defined serialization/checksum contract.

### Gate C — repeatability

Uploading the same dataset twice is idempotent.

### Gate D — failure safety

A failed upload cannot replace the previous known-good dataset.

### Gate E — application

Streamlit can load its required snapshot from R2.

### Gate F — fallback

The application can still recover through the fallback path if R2 is temporarily unavailable, subject to the final deployment design.

### Gate G — research

A backtest can retrieve the full historical dataset without using the application cache.

### Gate H — point-in-time universe

Historical constituent membership can be reconstructed independently of today's universe.

### Gate I — source separation

Screener and Yahoo data remain distinguishable and are never silently spliced.

### Gate J — reproducibility

A research run can record the exact dataset version/manifest it consumed.

---

# 24. Data retention philosophy

The default policy is:

> **Keep historical market data unless there is a documented reason not to.**

Storage is cheap enough that premature deletion creates more research risk than cost.

Potential future retention classes:

| Data | Proposed retention |
|---|---|
| Canonical normalized prices | Indefinite |
| Index membership | Indefinite |
| Corporate-action evidence | Indefinite where practical |
| Manifests | Indefinite |
| Raw source snapshots | Long-term; exact policy TBD |
| Application snapshots | Rolling |
| Temporary CI artifacts | Short-lived |

No deletion policy should be implemented until the dataset dependencies are mapped.

---

# 25. Cost-control principles

R2 is inexpensive, but uncontrolled request patterns are still undesirable.

Rules:

- prefer large analytical objects over huge numbers of tiny objects;
- cache application snapshots;
- avoid repeatedly listing entire buckets;
- use manifests when the exact object is known;
- do not make every Streamlit widget an R2 request;
- download a dataset once per application session where practical;
- keep research jobs explicit about which dataset they consume;
- monitor storage and operation usage.

Current R2 Standard free allowance is 10 GB-month storage, 1M Class A operations and 10M Class B operations monthly. Egress is free.

---

# 26. R2 API technology choice

Use the R2 **S3-compatible API** rather than coupling the application directly to Cloudflare-specific APIs.

Cloudflare documents the endpoint:

\`https://<ACCOUNT_ID>.r2.cloudflarestorage.com\`

and supports existing S3 SDKs such as boto3.

This gives us:

- mature Python tooling;
- straightforward GitHub Actions integration;
- portability;
- easier future migration if another object store becomes preferable.

Source:
https://developers.cloudflare.com/r2/api/

---

# 27. Proposed software boundary

Introduce a small storage abstraction rather than scattering R2 calls through the codebase.

Conceptually:

\`\`\`
src/storage/
    archive.py
    r2.py
    manifest.py
\`\`\`

The rest of the application should ask for:

- publish dataset;
- retrieve dataset;
- check dataset;
- retrieve manifest.

It should not know how S3 signing or R2 authentication works.

This prevents infrastructure details from contaminating the quantitative engine.

---

# 28. What must NOT change

The R2 migration is a storage migration.

It must not silently change:

- System-1 ranking methodology;
- benchmark;
- universe definition;
- momentum formulas;
- ranking weights;
- corporate-action methodology;
- price-source semantics;
- index definitions;
- Stage-4 AI research methodology.

R2 is infrastructure.

It is not a reason to redesign the quantitative engine.

---

# 29. Fundamental data

Fundamentals are intentionally **not included in the first R2 migration contract**.

Current Screener chart collection is a price/volume collection path and does not mean that a full fundamentals dataset is being returned in the same call.

If fundamentals are added later, they should have:

- their own source;
- their own schema;
- their own update cadence;
- publication dates where applicable;
- point-in-time semantics;
- source-specific provenance.

This is especially important because historical fundamentals are not equivalent to today's fundamentals.

A future fundamentals archive must avoid look-ahead bias.

---

# 30. Backtesting requirements

The archive must eventually support queries such as:

### Price

> Give me the price history known for symbol X through date Y.

### Universe

> Give me the NIFTY TOTAL MARKET constituents as of date Y.

### Index change

> Which symbols entered or left NIFTY MIDCAP 150 between dates A and B?

### Survivorship

> Run the strategy using only stocks that were eligible on each historical date.

### Reproducibility

> Re-run the 2026-09-18 ranking using the exact dataset that generated the published ranking.

### Corporate actions

> Explain a discontinuity in symbol X and identify the source/action that caused the normalization.

These requirements drive the archive design.

---

# 31. Future dataset versioning

A dataset version should not mean merely:

\`latest.parquet\`

Instead, research should be able to identify:

- dataset name;
- as-of date;
- schema version;
- source;
- pipeline version;
- checksum.

A future research result should therefore be reproducible from a manifest reference.

---

# 32. Observability

The daily sync should eventually publish measurable facts such as:

- source request count;
- successful symbols;
- unresolved symbols;
- rows added;
- rows preserved;
- missing cells;
- session coverage;
- archive row count;
- archive symbol count;
- archive date range;
- object size;
- checksum;
- upload duration;
- R2 verification status.

A data pipeline should tell us what it actually stored, not merely say "sync completed."

---

# 33. Important current limitation

The phrase "all price history" needs to be interpreted carefully.

We can preserve **all history that we successfully collect**, but we cannot retroactively obtain arbitrary daily Screener history if the source does not expose it at daily resolution.

Therefore:

1. Existing Yahoo history provides a useful longer historical base.
2. Screener history must continue accumulating daily from the present.
3. Future R2 history should preserve both sources independently.
4. We should never pretend that missing historical observations were collected when they were not.

This is one of the main reasons to start the durable archive now.

---

# 34. Open design decisions before implementation

These decisions should be resolved during the implementation design review, not guessed in code.

### A. Physical Parquet partitioning

Options:

- one file per source;
- yearly partitions;
- monthly partitions;
- another analytical layout.

### B. Raw-source retention

How long should raw Screener/Yahoo/NSE snapshots be retained?

### C. R2 object versioning / immutability model

Determine whether immutable date-stamped objects plus manifests are sufficient, or whether additional object protection is warranted.

### D. Application fallback

Determine exact behavior if R2 is unavailable during Streamlit startup.

### E. Research access

Determine whether research jobs read R2 directly or first materialize local working copies.

### F. Historical Yahoo archive depth

Confirm the maximum useful source window and the exact refresh policy.

### G. Screener archive reconstruction

Determine how much existing Screener history can be recovered from the current local/release artifacts before R2 bootstrap.

### H. Fundamentals

Define separately; do not mix into the first migration.

---

# 35. Proposed implementation order

The engineering sequence should be:

1. **Review and approve this architecture.**
2. Inspect every existing data-producing workflow and artifact.
3. Inventory current datasets and their exact schemas.
4. Inventory existing historical depth for every source.
5. Create R2 bucket.
6. Create least-privilege R2 credentials.
7. Implement storage adapter.
8. Implement manifest/checksum layer.
9. Build migration/bootstrap tooling.
10. Migrate existing history.
11. Verify migration independently.
12. Add dual-write to daily sync.
13. Run dual-write for a validation period.
14. Add R2 read path behind a feature flag.
15. Validate Streamlit against R2.
16. Switch R2 to canonical.
17. Retain GitHub snapshot as fallback.
18. Remove unnecessary long-term data publication from GitHub.
19. Add research/backtest readers.
20. Extend archive datasets only after the core archive is stable.

---

# 36. Final architectural principle

The system should eventually have a very clear separation:

\`\`\`
GitHub
  = code + methodology + tests + contracts

R2
  = historical data + evidence + manifests

Streamlit
  = application / visualization / current research interface

Research jobs
  = consumers of the historical archive
\`\`\`

The key principle is:

> **Data survives applications. Applications can be rebuilt from data.**

If Streamlit is redeployed, the archive remains.

If Git history is rewritten, the archive remains.

If the ranking engine changes, the source history remains.

If a new backtest is invented five years from now, the underlying historical evidence remains.

That is the reason for this architecture.


# 37. Phase 3 implementation decision — dual publication

Phase 3 uses the existing validated production artifacts as the single input to
both publication paths.

The daily Yahoo pipeline publishes, when produced:

- `prices_full.parquet` -> `archive/prices/yahoo/<as_of>/prices_full.parquet`;
- `prices.parquet` -> `snapshots/application/<as_of>/prices.parquet`;
- `rankings.parquet` -> `snapshots/rankings/<as_of>/rankings.parquet`.

The independent Screener pipeline publishes:

- `screener_prices.parquet` -> `archive/prices/screener/<as_of>/screener_prices.parquet`.

Each object receives an immutable manifest under:

`archive/manifests/<dataset>/<as_of>.json`

The publication boundary verifies:

1. the exact local artifact exists;
2. the R2 object is uploaded;
3. size and SHA-256 match after read-back;
4. an existing identical object is accepted idempotently;
5. an existing object with different bytes is rejected rather than overwritten;
6. source identity remains explicit in the manifest.

The rolling GitHub Release remains in place during Phase 3.

For same-date corrections caused by later vendor restatements, Phase 3 deliberately
fails closed rather than overwriting an immutable archive object. A future
revision/versioning policy must be introduced explicitly before same-date
replacement is permitted.

This keeps the first dual-publication phase conservative: no historical evidence
can be silently replaced while the R2 archive is being proven against the live
pipeline.


# 38. Same-date source revisions

Phase 3 real-data validation exposed an important property of vendor history:
the same \`as_of\` date can legitimately produce different bytes on a later
collection. This is expected for sources whose historical prices are adjusted
or restated after corporate actions, and must not be treated as a corruption
condition by itself.

The archive therefore uses **content-addressed revisions** for canonical
source datasets:

\`\`\`
archive/prices/yahoo/<as_of>/revisions/<sha256>/prices_full.parquet
archive/prices/screener/<as_of>/revisions/<sha256>/screener_prices.parquet
\`\`\`

Each distinct byte-level snapshot gets its own immutable object and immutable
manifest:

\`\`\`
archive/manifests/<dataset>/<as_of>/revisions/<sha256>.json
\`\`\`

A mutable convenience pointer records the latest accepted revision:

\`\`\`
archive/manifests/<dataset>/<as_of>/current.json
\`\`\`

Rules:

1. identical retry of an existing revision is idempotent and verified;
2. same date + different bytes creates a new revision;
3. an older revision is never overwritten or deleted by publication;
4. \`current.json\` identifies the latest accepted revision only;
5. the revision SHA-256 is the content identity used by the archive;
6. manifests retain source identity and pipeline metadata.

This is particularly important for Yahoo, where corporate-action-adjusted
history can be restated. The archive must preserve what was actually received,
not silently rewrite yesterday's evidence with today's interpretation.

The first observed Yahoo same-date conflict proved that the byte-level
snapshot changed; the semantic cause of each future change should be measured
separately rather than assumed.

# 39. One-time Screener 10-year bootstrap

Screener exposes recent history at daily resolution and older history in
weekly form. A one-time deep-history bootstrap therefore requests approximately
10 years from the same source endpoint and merges it into the existing
source-separated Screener store.

The resulting store deliberately has mixed temporal density:

- recent period: accumulated daily observations;
- older period: Screener-provided weekly observations.

The normal daily Screener job then continues exactly as before. It requests
the recent rolling daily window and merges it into the store, preserving the
older weekly observations. No weekly deep-history request is required on future
daily runs.

The bootstrap is a one-time research-data acquisition step, not a change to the
live ranking methodology.

Acceptance checks for the bootstrap include:

- complete successful universe walk;
- no unsettled session frozen into history;
- historical rows preserved rather than replaced;
- substantial history older than one year;
- final artifact published to both the rolling GitHub Release and R2;
- R2 publication uses the same revision model described above.

This gives the backtest layer a materially deeper Screener source history
without pretending that the older observations are daily bars.
