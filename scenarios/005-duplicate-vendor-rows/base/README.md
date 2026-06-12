# orders-revenue

Daily revenue reporting pipeline.

- the fulfillment vendor drops order exports into `data/landing/` (one CSV per day, not in git)
- `ingest.py` loads landing files and `data/raw/` reference data into DuckDB
- `dbt/` builds `fct_revenue` for the finance dashboard
- run everything: `bash run_pipeline.sh`
