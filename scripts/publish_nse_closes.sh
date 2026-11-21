#!/usr/bin/env bash
# Publish data/nse_prices/closes.parquet to R2 (nse/closes_2y) and the data-latest
# release (nse_closes.parquet): src/loaders/nse_prices.closes_path() reads them
# when the repository holds no copy. Run by monthly_track_record.yml after the
# closes are extended, and once by nse_closes_publish.yml to seed both copies.
# Needs the R2_* variables, GH_TOKEN and GITHUB_REPOSITORY.
set -euo pipefail
SRC=data/nse_prices/closes.parquet
[ -f "$SRC" ] || { echo "::error::$SRC is missing: nothing to publish"; exit 1; }
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
