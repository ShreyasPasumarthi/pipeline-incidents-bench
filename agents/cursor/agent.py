#!/usr/bin/env python3
"""Cursor-agent baseline for pipeline-incidents-bench.

Drives a local Cursor agent (via the Cursor SDK) against the broken pipeline
workspace. The agent edits files in place; its diagnosis is collected through
a pib_report.json file it writes in the workspace, which this adapter moves
to the harness's --output path.

Auth: CURSOR_API_KEY (Cursor Dashboard -> Integrations). A .env file in the
bench root is also read. Model: PIB_CURSOR_MODEL (default composer-2.5).

Invoked by the harness as:
  python3 agents/cursor/agent.py --workspace <repo> --context <context.json> --output <report.json>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from cursor_sdk import Agent, AgentOptions, CursorAgentError, LocalAgentOptions

REPORT_BASENAME = "pib_report.json"

PROMPT_TEMPLATE = """\
You are on call for this data pipeline repository. A scheduled run has failed.

Diagnose the root cause and FIX the pipeline by editing files in this repo.
Rules:
- Do NOT edit raw or landing data files under data/ (you don't own upstream
  systems) and do NOT delete or weaken tests.
- The failure may or may not be caused by a recent code change. Commit
  messages can be misleading; verify against actual diffs and data. If no code
  change caused it, say so — do not blame an innocent commit.
- Verify your fix by rerunning `bash run_pipeline.sh` until it exits 0.

When done, write a file named {report_basename} in the repo root containing
ONLY this JSON:
{{
  "root_cause_category": "schema_change | source_data_change | logic_bug | dependency_failure | infra_failure | other",
  "root_cause": "<specific free-text diagnosis>",
  "culprit_commit": "<full sha of the offending commit, or null if no code change caused this>",
  "evidence": ["<paths or short descriptions>"],
  "fix_description": "<what you changed and why>"
}}

INCIDENT CONTEXT (collected at failure time):
{context}
"""


def load_dotenv() -> None:
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            return


def fallback_report(note: str) -> dict:
    return {
        "root_cause_category": "other",
        "root_cause": f"cursor agent did not complete: {note}",
        "culprit_commit": None,
        "evidence": [],
        "fix_description": "incomplete",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    load_dotenv()
    api_key = os.environ.get("CURSOR_API_KEY")
    if not api_key:
        sys.exit("agent: CURSOR_API_KEY not set (Cursor Dashboard -> Integrations)")
    model = os.environ.get("PIB_CURSOR_MODEL", "composer-2.5")

    workspace = Path(args.workspace).resolve()
    context = json.loads(Path(args.context).read_text())
    prompt = PROMPT_TEMPLATE.format(
        report_basename=REPORT_BASENAME,
        context=json.dumps(context, indent=1),
    )

    # The SDK bridge occasionally fails to spawn (e.g. a transient empty
    # --tool-callback-auth-token). That is harness infrastructure, not agent
    # ability, so retry before letting it contaminate the score.
    report = fallback_report("unknown")
    attempts = 3
    for attempt in range(1, attempts + 1):
        try:
            result = Agent.prompt(
                prompt,
                AgentOptions(
                    api_key=api_key,
                    model=model,
                    local=LocalAgentOptions(cwd=str(workspace)),
                ),
            )
            print(f"agent: cursor run status={result.status}", file=sys.stderr)
            if result.status != "finished":
                report = fallback_report(f"run status {result.status}")
            break
        except CursorAgentError as err:
            print(
                f"agent: startup failed (attempt {attempt}/{attempts}): {err}",
                file=sys.stderr,
            )
            report = fallback_report(f"startup failed after {attempt} attempts: {err}")
            if attempt < attempts:
                time.sleep(5 * attempt)

    # Collect the report the agent left in the workspace (and remove it so it
    # doesn't pollute the worktree diff the harness scores).
    report_file = workspace / REPORT_BASENAME
    if report_file.exists():
        try:
            report = json.loads(report_file.read_text())
        except json.JSONDecodeError:
            report = fallback_report("wrote invalid JSON report")
        report_file.unlink()
    elif report["root_cause"].endswith("unknown"):
        report = fallback_report("no report file written")

    Path(args.output).write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
