#!/usr/bin/env bash
set -euo pipefail
python3 ingest.py
cd dbt
# Backfill: rows written while the cents bug was live are stale; the
# incremental rollup must be rebuilt, not just resumed.
dbt build --full-refresh --profiles-dir . --no-use-colors
