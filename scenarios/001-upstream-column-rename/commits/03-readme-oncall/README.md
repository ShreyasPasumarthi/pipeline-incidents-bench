# signups-analytics

Daily signups reporting pipeline.

- `ingest.py` loads the growth team's extracts from `data/raw/` into DuckDB
- `dbt/` transforms raw signups into `fct_daily_signups`
- run everything: `bash run_pipeline.sh`

## On-call

If the nightly run fails, check the dbt logs first, then ping #growth-data.
The exec dashboard reads `fct_daily_signups` at 8am PT — fix before then.
