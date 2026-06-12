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

## Curated vs collector context (the real test)

The scores above hand the agent a context bundle the harness assembled with
full knowledge of the repo layout. The open question for a real product is
whether that bundle can be reconstructed automatically from raw workspace
state. So we ran the same Cursor agent again, but replaced the curated bundle
with the output of `pipemend collect` — a read-only collector that sees only
the broken repo and the run command, never the scenario's ground truth
(`pib run --context-source collector`).

| Scenario | Curated | Collector | Δ |
|---|---|---|---|
| 001 rename | 85% | **100%** | +15 |
| 002 format change | 85% | 85% | 0 |
| 003 bad join | 100% | 100% | 0 |
| 004 broken import | 100% | 100% | 0 |
| 005 duplicates | 100% | 100% | 0 |
| 006 backfill | 100% | 100% | 0 |
| 007 compound | 70% | **85%** | +15 |
| 008 fan-out | 100% | 100% | 0 |
| 009 number format | 100% | 100% | 0 |
| 010 path drift | 35% | **85%** | +50 |
| **Overall** | **88%** | **96%** | **+8** |
| **Pipelines fixed** | **9/10** | **10/10** | **+1** |

Collector context **matched or beat** curated context on every scenario. The
reason is the product thesis in miniature: the curated bundle is raw evidence
and leaves all inference to the agent, whereas `pipemend collect` pre-digests
that evidence into *leads* — a score-ranked suspect commit (with confidence and
reasons) and cross-signal detections like config drift and vendor header drift.

Where that pre-digestion moved the needle:

- **010 path drift: 35% → 85%, and it's the durable result.** This is the only
  scenario where the curated agent failed to *fix* the pipeline — it pointed
  `ingest.py` at the drifted `/tmp` path, going green the wrong way. The
  collector emitted an explicit signal: *"dbt profiles.yml points at
  /tmp/analytics_warehouse.duckdb, but the most recently written warehouse file
  is the repo-local warehouse.duckdb — ingestion and dbt may disagree about
  where the warehouse lives."* With that lead, the agent reverted profiles.yml —
  the correct fix — and `fix_verified` (execution-graded against hidden
  assertions, not opinion) passed. Same model, same repo, different context:
  the collector's cross-signal detection steered the agent off the
  green-but-wrong remediation.
- **001 rename: 85% → 100%** and **007 compound: 70% → 85%** are attribution
  gains — the collector named the culprit sha and got the category right where
  the curated agent had hedged or mislabeled. These are real but smaller, and a
  single LLM run carries enough variance that a ±one-check swing on an
  individual scenario is within noise. The robust, mechanistically-explained
  win is 010.

Honest caveats:

- An *opinionated* bundle that names a top suspect can mislead as well as guide.
  On 002 the collector correctly hedged ("low confidence — a data fault with no
  code cause is also plausible") and the agent made the same category miss it
  made under curated context: the collector neither helped nor hurt. The risk
  that a confidently-wrong verdict drags an agent to a worse answer is real, and
  measuring it across more scenarios is exactly what this benchmark exists for.

## Variance study (5 trials per scenario per mode, 100 scored runs)

The table above is a single run of a non-deterministic agent, so we repeated
the full matrix 5 times per mode ([VARIANCE.md](VARIANCE.md) has per-scenario
spreads and a methods note):

| Mode | Overall (mean of trial means) | Spread | Verified fixes |
|---|---|---|---|
| curated | 89.3% | [88–90%], s=1.3 pts | 45/50 (90%) — 010 failed in all 5 trials |
| collector | 95.8% | [92–97%], s=2.0 pts | **50/50 (100%)** — every pipeline, every trial |

The single-run conclusions held up:

- **010 (path drift) is a systematic flip, not a lucky roll**: 35% in all five
  curated trials (the agent always goes green the wrong way), 97% mean with the
  collector's config-drift signal.
- The remaining per-scenario noise lives in attribution checks (category,
  culprit commit) on 001/007, not in fix correctness.

The takeaway for the thesis: the agent's raw fixing ability was already high;
the lever that turned a 90% verified-fix rate into 100% and made 10/10 fixes
reproducible across every trial was **the quality of the assembled context,
not the model.** That is the layer the collector owns — and it is now real
code, not a roadmap item.
