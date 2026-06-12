# orders-mart

Order enrichment pipeline for the analytics mart.

- the payments vendor drops order exports into `data/landing/` (one CSV per day, not in git)
- guest checkouts have no customer record — `fct_orders` must still include them
- `ingest.py` loads landing files and `data/raw/` reference data into DuckDB
- `dbt/` builds `fct_orders`
- run everything: `bash run_pipeline.sh`
