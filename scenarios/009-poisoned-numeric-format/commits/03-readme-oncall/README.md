# billing-revenue

Daily billing revenue pipeline.

- the billing vendor drops order exports into `data/landing/` (one CSV per day, not in git)
- `ingest.py` loads landing files into DuckDB
- `dbt/` builds `fct_revenue` for the finance dashboard
- run everything: `bash run_pipeline.sh`

## On-call

Finance reads `fct_revenue` at 8am ET. Escalate failures in #data-oncall.
