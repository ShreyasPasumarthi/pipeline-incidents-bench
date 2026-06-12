# pipeline-incidents-bench

**Can your AI agent actually fix a broken data pipeline? Prove it.**

Reproducible broken-data-pipeline scenarios with *executable* ground truth, for
evaluating AI incident-response agents. Every scenario is a small, realistic
analytics repo (dbt + DuckDB, git history included) with an injected fault. The
agent gets the same evidence a human on-call engineer gets — failing run logs,
dbt artifacts, git log, source data samples — and must diagnose the root cause
and **edit the repo to fix it**.

The headline property: **fixes are graded by execution, not opinion.** After
the agent's edits, the harness reruns the pipeline. It goes green and passes
hidden data assertions, or it doesn't. No LLM judge deciding whether the
diagnosis "sounds right."

## Why

Data pipeline incidents are expensive and constant: upstream schema drift,
vendors silently changing export formats, innocent-looking refactors that
silently drop rows. Existing observability tools detect these. The open
question is whether agents can *fix* them — and there's no objective way to
measure that today. This benchmark is that measuring stick.

Design choices that follow from this:

- **Root-cause attribution is scored, including the null case.** One scenario
  has no code cause at all — agents that reflexively blame the latest commit
  lose points. Real incidents are often data, not code.
- **Decoy commits everywhere.** Innocent commits touch the failing models;
  faulty commits carry innocent messages ("perf: simplify joins").
- **Protected paths.** Agents can't "fix" the pipeline by editing upstream
  data they don't own or deleting the failing test. The alarm is not the fire.
- **Zero infrastructure.** Scenarios run on dbt + DuckDB: `pip install`, no
  Docker, red-to-green in seconds. A heavier tier (Airflow, Postgres, Spark)
  is on the roadmap, but adoption friction matters more than realism points.

## Quickstart

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
# Python 3.14 only: pip install -U mashumaro  (dbt-core pin lags 3.14 support)

.venv/bin/pib list                 # show scenarios
.venv/bin/pib validate             # every scenario: reproduces red + solvable
.venv/bin/pib run --agent null     # do-nothing baseline (~5%)
.venv/bin/pib run --agent oracle   # hidden solutions applied (100%)
.venv/bin/pib run --agent "python3 agents/example/agent.py"   # your agent here
```

### Context source

By default the harness assembles the incident bundle itself (`--context-source
curated`). To instead have it built from raw workspace state by the
[Pipemend](../pipemend) collector — the way it would be in production — pass
`--context-source collector`:

```bash
.venv/bin/pib run --agent "<cmd>" --context-source collector
```

The collector receives only the broken repo and the run command, never the
scenario's ground truth. It must be discoverable as a sibling `pipemend` repo
with a built `.venv`, on `PATH`, or via the `PIPEMEND_CMD` env var. See
[RESULTS.md](RESULTS.md) for the curated-vs-collector comparison.

## Agent protocol

Any executable works. The harness calls:

```
<agent_cmd> --workspace <repo_dir> --context <context.json> --output <report.json>
```

- `workspace` — the broken pipeline repo. Read anything, edit anything
  (your edits ARE the fix). Rerun `bash run_pipeline.sh` as often as you like.
- `context` — the incident bundle: failing run stdout/stderr, parsed dbt
  `run_results`, `git log -p` of recent commits, file tree, and head samples
  of every data file (including landing files that live outside git). Its exact
  shape depends on `--context-source` (curated bundle vs Pipemend collector
  bundle); agents should treat it as opaque incident evidence.
- `report.json` — your diagnosis:

```json
{
  "root_cause_category": "schema_change | source_data_change | logic_bug | dependency_failure | infra_failure | other",
  "root_cause": "free-text diagnosis",
  "culprit_commit": "<sha>, or null if no code change caused this",
  "evidence": ["paths or short descriptions"],
  "fix_description": "what you changed and why"
}
```

See `agents/example/agent.py` for the minimal I/O skeleton.

## Scoring

| Check | Weight | How it's graded |
|---|---|---|
| `fix_verified` | 50% | Pipeline reruns green + hidden SQL assertions pass + no protected files touched |
| `root_cause` | 20% | Diagnosis contains the key concepts (keyword groups, AND of ORs) |
| `category` | 15% | Match against accepted categories (compound incidents accept more than one) |
| `culprit_commit` | 15% | Correct sha — or correctly reporting *no* culprit |

Hidden assertions stop degenerate "fixes": deleting rows, hardcoding values,
or weakening tests won't produce the right row counts and totals.

## Scenario anatomy

```
scenarios/001-upstream-column-rename/
  scenario.yaml      # commits to replay, ground truth, hidden assertions
  base/              # working pipeline repo (initial commit)
  commits/           # overlays replayed as git history; one may be the fault
  landing/           # files dropped outside git (vendor exports), if any
  solution/          # hidden reference fix — proves the scenario is solvable
```

Every scenario must pass `pib validate`: the fault reproduces red, and the
reference solution scores exactly 100%. Scenarios that can't be solved or
can't be reproduced don't ship.

### Current scenarios

| id | fault | cause in git? |
|---|---|---|
| `001-upstream-column-rename` | upstream export renames `user_id` → `customer_id`; staging view breaks | yes, disguised as a chore |
| `002-vendor-export-format-change` | vendor switches `amount` to `amount_minor` (cents); not_null fails | **no** — data only |
| `003-bad-join-refactor` | "perf" commit turns left join into inner join; guest orders silently dropped | yes, disguised as perf |
| `004-broken-import-refactor` | ingestion refactor ships a broken import; pipeline dies before dbt | yes |
| `005-duplicate-vendor-rows` | vendor re-delivers overlapping rows; unique test fails | **no** — data only |

Hard tier — these punish shallow "patch until green" strategies:

| id | fault | what makes it hard |
|---|---|---|
| `006-incremental-backfill` | cents bug corrupts an *incremental* model | fixing the code isn't enough — stale rows persist; a backfill (full-refresh) is required |
| `007-compound-incident` | vendor format change **and** a join regression strike together | fixing one fault still leaves the pipeline red; attribution must untangle two causes |
| `008-fanout-join` | address enrichment joins without filtering type; orders fan out | error is a grain violation two models downstream of the cause |
| `009-poisoned-numeric-format` | vendor adds thousands separators (`"1,234.56"`); cast explodes | failure surfaces in the mart, cause is in a landing file; no git cause |
| `010-warehouse-path-drift` | "standardize warehouse location" chore points dbt at an empty database | the *tempting* fix (align ingest to the new path) goes green but violates the repo's documented convention — hidden assertions catch it |

## Related work & positioning

The "AI agents for incident response" space is active, but it splits cleanly by
*layer* and by *which part of the loop* a tool actually owns:

- **General software/infra observability** — e.g. [Superlog](https://superlog.sh/)
  (open-source agentic telemetry: ingests OpenTelemetry traces/logs/metrics,
  groups noisy signals into incidents). These operate on running-service
  telemetry and are strongest at *detection and triage*; autonomous *fixing* is
  early (the open default agent records an incident summary).
- **Data observability** — Monte Carlo, Anomalo, Metaplane: detect data-quality
  and freshness anomalies in the warehouse. Strong at alerting; remediation is
  left to humans.

This benchmark is deliberately orthogonal to both. It does not detect incidents
— it assumes one already fired — and it measures the step everyone else stops
short of: **can an agent actually fix it, verified by execution?** The scope is
the *data layer* (dbt/warehouse/git), and the grading is reproducible ground
truth rather than an LLM judge or a human's opinion. To our knowledge no public
benchmark measures verified remediation for data-pipeline incidents; that gap is
the reason this exists.

## Roadmap

- 30–50 scenarios across schema drift, data anomalies, logic bugs, dependency
  and infra failures
- Heavy tier: dockerized Airflow + Postgres + Spark scenarios
- LLM-agent baselines (Claude, GPT) with published scorecards
- LLM judge for root-cause free text (keyword groups are v0)
- Noisy multi-signal incidents: scenarios where the failing run is one of many
  correlated alerts, to test triage/grouping, not just single-fault repair

## License

MIT

---

Built and maintained by **Pipemend** — AI incident response for data pipelines.
