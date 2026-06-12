"""Assembles the IncidentContext bundle handed to the agent.

This is deliberately the same shape of evidence a production collector would
gather: failing run output, orchestrator/dbt artifacts, recent git history,
and samples of the source data files. Nothing scenario-identifying leaks in.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .pipeline import PipelineRun

MAX_LOG_CHARS = 20_000
MAX_GIT_CHARS = 40_000
MAX_DATA_FILES = 12
DATA_SAMPLE_LINES = 6


def _tail(text: str, limit: int) -> str:
    return text if len(text) <= limit else "...[truncated]...\n" + text[-limit:]


def _git_log(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "-p", "--stat", "-n", "12", "--no-color"],
        capture_output=True,
        text=True,
    )
    out = result.stdout
    return out if len(out) <= MAX_GIT_CHARS else out[:MAX_GIT_CHARS] + "\n...[truncated]..."


def _file_tree(repo: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-files"], capture_output=True, text=True
    )
    return result.stdout.splitlines()


def _dbt_run_results(repo: Path) -> list[dict]:
    rr = repo / "dbt" / "target" / "run_results.json"
    if not rr.exists():
        return []
    try:
        data = json.loads(rr.read_text())
    except json.JSONDecodeError:
        return []
    nodes = []
    for r in data.get("results", []):
        nodes.append(
            {
                "unique_id": r.get("unique_id"),
                "status": r.get("status"),
                "message": r.get("message"),
                "failures": r.get("failures"),
            }
        )
    return nodes


def _data_samples(repo: Path) -> list[dict]:
    """Head of every data file, including landing files that live outside git."""
    samples = []
    data_dir = repo / "data"
    if not data_dir.is_dir():
        return samples
    for f in sorted(data_dir.rglob("*.csv"))[:MAX_DATA_FILES]:
        lines = f.read_text(errors="replace").splitlines()
        samples.append(
            {
                "path": str(f.relative_to(repo)),
                "rows": max(len(lines) - 1, 0),
                "head": lines[:DATA_SAMPLE_LINES],
            }
        )
    return samples


def build_context(repo: Path, run: PipelineRun) -> dict:
    return {
        "incident": "Scheduled pipeline run failed. Diagnose the root cause and fix it.",
        "pipeline_run": {
            "command": "bash run_pipeline.sh",
            "exit_code": run.exit_code,
            "stdout": _tail(run.stdout, MAX_LOG_CHARS),
            "stderr": _tail(run.stderr, MAX_LOG_CHARS),
        },
        "dbt_run_results": _dbt_run_results(repo),
        "git_log": _git_log(repo),
        "file_tree": _file_tree(repo),
        "data_samples": _data_samples(repo),
    }
