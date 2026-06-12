# revenue-rollup

Daily revenue rollup pipeline.

- `ingest.py` loads `data/raw/` extracts into DuckDB
- `dbt/` builds `fct_revenue` (incremental — only new days are processed)
- run everything: `bash run_pipeline.sh`

## On-call

Finance reads `fct_revenue` at 7am PT. If the nightly run fails, escalate in
#data-oncall. Note the rollup is incremental — already-processed days are not
recomputed on a normal run.
