# orders-analytics

Order reporting pipeline.

- `ingest.py` loads `data/raw/` extracts into DuckDB
- `dbt/` builds `fct_orders` (every order, enriched with customer region;
  guest checkouts have no customer record)
- run everything: `bash run_pipeline.sh`
