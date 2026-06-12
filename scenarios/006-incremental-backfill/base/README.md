# revenue-rollup

Daily revenue rollup pipeline.

- `ingest.py` loads `data/raw/` extracts into DuckDB
- `dbt/` builds `fct_revenue` (incremental — only new days are processed)
- run everything: `bash run_pipeline.sh`
