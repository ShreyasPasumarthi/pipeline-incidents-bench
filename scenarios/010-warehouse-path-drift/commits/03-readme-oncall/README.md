# daily-orders

Daily orders pipeline.

- `ingest.py` loads `data/raw/` extracts into the repo-local DuckDB warehouse
  (`warehouse.duckdb`, gitignored)
- `dbt/` builds `fct_daily_orders` from it
- run everything: `bash run_pipeline.sh`

## On-call

The ops dashboard reads `fct_daily_orders` hourly. Failures go to #data-eng.
