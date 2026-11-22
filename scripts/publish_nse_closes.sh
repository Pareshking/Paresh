#!/usr/bin/env bash
# Publish data/nse_prices/closes.parquet to R2 (nse/closes_2y) and the data-latest
# release (nse_closes.parquet): src/loaders/nse_prices.closes_path() reads them
# (the file is not in git since 21 Nov 2026, TODO S178). Run by
# monthly_track_record.yml after the closes are extended. Seeded once by the
# since-removed nse_closes_publish.yml (run 44945375720: both copies identical
# to the committed file). Needs the R2_* variables, GH_TOKEN and GITHUB_REPOSITORY.
set -euo pipefail
SRC=data/nse_prices/closes.parquet
# sync_nse_prices.py writes the file only when it appends a session; on a run
# that finds the published copy up to date there is nothing new to publish.
if [ ! -f "$SRC" ]; then
  echo "No new NSE closes written this run: the published copy stands."
  exit 0
fi
python scripts/r2_publish.py \
  --path "$SRC" \
  --dataset nse/closes_2y \
  --source sync_nse_prices \
  --key-root archive/nse/closes_2y \
  --pipeline-version "nse-closes-${GITHUB_SHA:-local}" \
  --release-tag data-latest \
  --skip-if-published
tmp="$(mktemp -d)"
cp "$SRC" "$tmp/nse_closes.parquet"
gh release upload data-latest "$tmp/nse_closes.parquet" --repo "$GITHUB_REPOSITORY" --clobber
python scripts/r2_audit.py --dataset nse/closes_2y --as-of \
  "$(python -c 'import pandas as pd; print(pd.read_parquet("data/nse_prices/closes.parquet").index.max().date())')"
