#!/usr/bin/env bash
set -euo pipefail
python3 ingest.py
cd dbt
dbt build --profiles-dir . --no-use-colors
