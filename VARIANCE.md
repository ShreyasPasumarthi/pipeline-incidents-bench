# Variance study: curated vs collector context

Agent: Cursor (composer-2.5). Trials: 5 per (scenario, mode). Each cell is mean across trials; range is min-max.

## Per-scenario score (mean, [min-max], stdev)

| Scenario | Curated | Collector |
|---|---|---|
| 001-upstream-column-rename | 91% [85-100] s=8 | 97% [85-100] s=7 |
| 002-vendor-export-format-change | 85% [85] s=0 | 85% [85] s=0 |
| 003-bad-join-refactor | 100% [100] s=0 | 100% [100] s=0 |
| 004-broken-import-refactor | 100% [100] s=0 | 100% [100] s=0 |
| 005-duplicate-vendor-rows | 100% [100] s=0 | 100% [100] s=0 |
| 006-incremental-backfill | 100% [100] s=0 | 100% [100] s=0 |
| 007-compound-incident | 82% [70-100] s=13 | 79% [70-85] s=8 |
| 008-fanout-join | 100% [100] s=0 | 100% [100] s=0 |
| 009-poisoned-numeric-format | 100% [100] s=0 | 100% [100] s=0 |
| 010-warehouse-path-drift | 35% [35] s=0 | 97% [85-100] s=7 |

## Overall (per-trial mean across all scenarios)

| Mode | Mean | [min-max] | stdev | Pipelines fixed (mean) |
|---|---|---|---|---|
| curated | 89.3% | [88-90%] | 1.3 pts | 9.0/10 |
| collector | 95.8% | [92-97%] | 2.0 pts | 10.0/10 |

## Per-check pass rate (fraction of all runs that passed)

| Check | Weight | Curated | Collector |
|---|---|---|---|
| category | 15% | 38/50 (76%) | 41/50 (82%) |
| culprit_commit | 15% | 43/50 (86%) | 45/50 (90%) |
| root_cause | 20% | 50/50 (100%) | 50/50 (100%) |
| fix_verified | 50% | 45/50 (90%) | 50/50 (100%) |

## Methods note: two cells rerun after a harness crash

In the original 100-run sweep, two collector-mode runs (004 and 008, trial 2)
scored 0% because the Cursor SDK's bridge process failed to spawn
(`Missing value for --tool-callback-auth-token`) — the agent never started,
and the adapter scored the untouched repo. That is harness infrastructure
failing, not the agent, so the adapter now retries bridge startup (3 attempts,
backoff) and those two cells were rerun under identical conditions; both
scored 100%. The raw log (`tools/variance_runs.ndjson`) marks the two replaced
rows with a `rerun` field. No other cell was rerun, and no run was discarded
for scoring low.
