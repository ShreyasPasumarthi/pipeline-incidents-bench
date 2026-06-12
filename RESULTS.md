# Baseline results

Run date: 2026-06-12 · 10 scenarios · scoring: fix verified by execution 50%,
root cause 20%, category 15%, culprit commit 15%.

## Standard tier (001–005)

| Agent | 001 rename | 002 format change | 003 bad join | 004 broken import | 005 duplicates | Overall | Fixes |
|---|---|---|---|---|---|---|---|
| oracle (hidden solutions) | 100% | 100% | 100% | 100% | 100% | **100%** | 5/5 |
| Cursor agent (composer-2.5) | 85% | 85% | 100% | 100% | 100% | **94%** | **5/5** |
| Gemini 2.5 Flash-Lite (thin loop) | 35% | 65% | 0%* | — | — | 33%* | 1/3 |
| null (do nothing) | 0% | 15% | 0% | 0% | 0% | **5%** | 0/5 |

\* Flash-Lite's scenario 003 run was starved by free-tier rate limits (1 LLM
call completed); the larger Gemini 2.5 Flash solved 003 at 100% in an earlier
partial run before its daily quota was exhausted. Flash-Lite was run on
scenarios 001–003 only, before 004–005 existed. Rerun pending on fresh quota.

## Hard tier (006–010)

Designed after the frontier agent aced the standard tier. These target
remediation depth, not just diagnosis: incremental state that survives a code
fix, two faults at once, grain violations, and fixes that go green the wrong
way.

| Agent | 006 backfill | 007 compound | 008 fan-out | 009 number format | 010 path drift | Overall | Fixes |
|---|---|---|---|---|---|---|---|
| oracle (hidden solutions) | 100% | 100% | 100% | 100% | 100% | **100%** | 5/5 |
| Cursor agent (composer-2.5) | 100% | 70% | 100% | 100% | 35% | **81%** | 4/5 |
| null (do nothing) | 0% | 0% | 0% | 15% | 0% | **3%** | 0/5 |

Notes on the two hard-tier misses:

- **010 (warehouse path drift) is the most instructive failure.** The agent
  diagnosed the incident perfectly — right culprit commit, right mechanism
  (profiles.yml moved the warehouse to /tmp while ingest still wrote the
  repo-local file). Then it executed the *wrong remediation*: it pointed
  `ingest.py` at /tmp instead of reverting the config drift, abandoning the
  repo's documented warehouse convention. The pipeline went green; the hidden
  assertions (which read the canonical warehouse) failed. A green pipeline is
  not the same as a correct fix — this is exactly the gap between "can patch
  until tests pass" and "understands the system's intent."
- **007 (compound incident)**: the agent fixed *both* simultaneous faults
  (vendor format change + join regression) and the fix verified, but it folded
  the two causes into one "schema_change" narrative and declined to name the
  guilty join commit. Multi-fault attribution is hard.
- **006 (incremental backfill)** is the encouraging result: the agent realized
  a code fix alone leaves corrupted rows in the incremental table and
  full-refreshed it. Remediation depth is not hopeless — it's just not free.

Cross-tier observations:

- Frontier-agent performance: 94% standard tier → 81% hard tier. The benchmark
  now has headroom to measure progress instead of saturating.
- Both misses were judgment failures, not capability failures: the agent could
  read everything and edit anything, and still chose a remediation a senior
  data engineer would reject in review.
- Caveat for all results: the harness hands every agent a curated incident
  context (failing logs, dbt artifacts, git history, data samples). Collecting
  that context automatically in a real production environment is its own hard
  problem — and the next build target.
