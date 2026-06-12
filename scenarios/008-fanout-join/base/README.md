# orders-enrichment

Order enrichment pipeline.

- `ingest.py` loads `data/raw/` extracts into DuckDB
- `dbt/` builds `fct_orders` — one row per order, enriched with customer data
- run everything: `bash run_pipeline.sh`
