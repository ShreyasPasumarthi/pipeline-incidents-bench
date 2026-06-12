"""Runs a scenario's pipeline command and captures the outcome."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PipelineRun:
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float

    @property
    def green(self) -> bool:
        return self.exit_code == 0


def run_pipeline(repo: Path, run_cmd: str, timeout: int = 600) -> PipelineRun:
    env = dict(os.environ)
    # Make the harness's interpreter environment (dbt, duckdb) visible to
    # scenario scripts even when pib is invoked without venv activation.
    venv_bin = str(Path(sys.executable).parent)
    env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
    env.setdefault("DBT_SEND_ANONYMOUS_USAGE_STATS", "false")

    start = time.monotonic()
    result = subprocess.run(
        ["bash", run_cmd],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    return PipelineRun(
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_s=time.monotonic() - start,
    )
