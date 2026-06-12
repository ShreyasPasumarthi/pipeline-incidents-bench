"""Builds a scenario workspace: copies the base repo, replays the commit
history with git (fault commit buried among innocent ones), and drops any
landing-zone data files that exist outside version control."""

from __future__ import annotations

import datetime
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .spec import Scenario

GIT_USER = ("Dana Engineer", "dana@example.com")


@dataclass
class Workspace:
    repo: Path
    # overlay dir name -> commit sha, plus "__init__" for the root commit
    commit_map: dict[str, str]
    fault_sha: str | None = None


def _git(repo: Path, *args: str, env: dict | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def _commit(repo: Path, message: str, author: str, when: datetime.datetime) -> str:
    import os

    env = dict(os.environ)
    date = when.strftime("%Y-%m-%dT%H:%M:%S")
    env.update(
        GIT_AUTHOR_DATE=date,
        GIT_COMMITTER_DATE=date,
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "--no-verify", "-m", message, f"--author={author}", env=env)
    return _git(repo, "rev-parse", "HEAD")


def _apply_overlay(overlay: Path, repo: Path) -> None:
    shutil.copytree(overlay, repo, dirs_exist_ok=True)


def build(scenario: Scenario, run_dir: Path) -> Workspace:
    repo = run_dir / "repo"
    repo.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(scenario.base_dir, repo)

    # Landing-zone files arrive outside git (vendor drops, SFTP exports).
    if scenario.landing_dir:
        landing_dest = repo / "data" / "landing"
        landing_dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(scenario.landing_dir, landing_dest, dirs_exist_ok=True)

    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", GIT_USER[0])
    _git(repo, "config", "user.email", GIT_USER[1])

    # Spread commits over the past N+1 days so the history looks lived-in.
    now = datetime.datetime.now()
    n = len(scenario.commits)
    when = now - datetime.timedelta(days=n + 1, hours=3)

    commit_map: dict[str, str] = {}
    commit_map["__init__"] = _commit(
        repo, "init: working pipeline", f"{GIT_USER[0]} <{GIT_USER[1]}>", when
    )

    fault_sha = None
    for i, spec in enumerate(scenario.commits):
        when = now - datetime.timedelta(days=n - i, hours=2, minutes=17 * i)
        _apply_overlay(scenario.path / spec.overlay, repo)
        sha = _commit(repo, spec.message, spec.author, when)
        commit_map[spec.overlay] = sha
        if spec.fault:
            fault_sha = sha

    return Workspace(repo=repo, commit_map=commit_map, fault_sha=fault_sha)


def worktree_diff(repo: Path) -> tuple[list[str], str]:
    """Files the agent touched (vs HEAD) and the unified diff."""
    status = _git(repo, "status", "--porcelain")
    changed = []
    for line in status.splitlines():
        # "XY path" — split off the status code rather than slicing, because
        # surrounding whitespace is not preserved reliably.
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        path = parts[1]
        if " -> " in path:
            path = path.split(" -> ")[1]
        changed.append(path.strip('"'))
    diff = _git(repo, "diff", "HEAD")
    return changed, diff
