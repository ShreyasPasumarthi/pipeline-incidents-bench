# orders-reporting

Daily orders reporting pipeline.

- `ingest.py` loads `data/raw/` extracts into DuckDB (helpers in `utils/`)
- `dbt/` builds `fct_daily_orders`
- run everything: `bash run_pipeline.sh`

## On-call

The ops dashboard reads `fct_daily_orders` hourly. If the run fails,
check ingest logs first, then #data-eng.
