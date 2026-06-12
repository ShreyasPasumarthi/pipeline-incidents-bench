# orders-reporting

Daily orders reporting pipeline.

- `ingest.py` loads `data/raw/` extracts into DuckDB (helpers in `utils/`)
- `dbt/` builds `fct_daily_orders`
- run everything: `bash run_pipeline.sh`
