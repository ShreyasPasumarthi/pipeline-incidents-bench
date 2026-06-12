# signups-analytics

Daily signups reporting pipeline.

- `ingest.py` loads the growth team's extracts from `data/raw/` into DuckDB
- `dbt/` transforms raw signups into `fct_daily_signups`
- run everything: `bash run_pipeline.sh`
