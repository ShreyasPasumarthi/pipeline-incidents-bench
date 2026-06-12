"""Agent invocation.

External agents are any executable honoring the protocol:

    <agent_cmd> --workspace <repo_dir> --context <context.json> --output <report.json>

The agent may freely read and EDIT files inside the workspace (that's the
fix). It must write report.json:

    {
      "root_cause_category": "schema_change | source_data_change | logic_bug |
                              dependency_failure | infra_failure | other",
      "root_cause": "free-text diagnosis",
      "culprit_commit": "<sha>" | null,
      "evidence": ["paths or short descriptions"],
      "fix_description": "free text"
    }

Two built-ins exist for harness development:
  - "oracle": applies the scenario's hidden solution; proves the scenario is
    solvable and that a perfect run scores 100%.
  - "null": does nothing; proves a do-nothing agent scores 0%.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from .spec import Scenario
from .workspace import Workspace

BUILTIN_AGENTS = ("oracle", "null")


def run_agent(
    agent_cmd: str,
    scenario: Scenario,
    workspace: Workspace,
    context_path: Path,
    report_path: Path,
    timeout: int = 1800,
) -> dict:
    if agent_cmd == "oracle":
        report = _oracle(scenario, workspace)
        report_path.write_text(json.dumps(report, indent=2))
        return report
    if agent_cmd == "null":
        report = {
            "root_cause_category": "other",
            "root_cause": "unknown",
            "culprit_commit": None,
            "evidence": [],
            "fix_description": "no action taken",
        }
        report_path.write_text(json.dumps(report, indent=2))
        return report

    cmd = shlex.split(agent_cmd) + [
        "--workspace", str(workspace.repo),
        "--context", str(context_path),
        "--output", str(report_path),
    ]
    # The agent must be able to rerun the pipeline itself, so it needs the
    # harness's interpreter environment (dbt, duckdb) on PATH.
    env = dict(os.environ)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    subprocess.run(cmd, timeout=timeout, check=False, env=env)
    if not report_path.exists():
        raise RuntimeError(f"agent did not write a report to {report_path}")
    return json.loads(report_path.read_text())


def _oracle(scenario: Scenario, workspace: Workspace) -> dict:
    shutil.copytree(scenario.solution_dir, workspace.repo, dirs_exist_ok=True)
    truth = scenario.truth
    culprit_sha = (
        workspace.commit_map.get(truth.culprit_overlay)
        if truth.culprit_overlay
        else None
    )
    return {
        "root_cause_category": truth.categories[0],
        "root_cause": truth.summary,
        "culprit_commit": culprit_sha,
        "evidence": truth.protected_paths[:2],
        "fix_description": truth.summary,
    }
