"""Scenario specification: loading and validating scenario.yaml files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CATEGORIES = [
    "schema_change",
    "source_data_change",
    "logic_bug",
    "dependency_failure",
    "infra_failure",
    "other",
]


@dataclass
class CommitSpec:
    overlay: str
    message: str
    fault: bool = False
    author: str = "Dana Engineer <dana@example.com>"


@dataclass
class VerifyCheck:
    sql: str
    op: str  # one of: ==, >=, <=, between
    value: float | list[float]

    def passes(self, observed: float | None) -> bool:
        if observed is None:
            return False
        if self.op == "==":
            return observed == self.value
        if self.op == ">=":
            return observed >= self.value
        if self.op == "<=":
            return observed <= self.value
        if self.op == "between":
            lo, hi = self.value
            return lo <= observed <= hi
        raise ValueError(f"unknown verify op: {self.op}")


@dataclass
class Truth:
    # Accepted categories; compound incidents may accept more than one label.
    categories: list[str]
    summary: str
    # Outer list is AND, inner lists are OR: every group must have at least
    # one keyword present in the agent's root-cause text.
    keywords_any: list[list[str]]
    culprit_overlay: str | None
    protected_paths: list[str]
    verify: list[VerifyCheck]


@dataclass
class Scenario:
    id: str
    title: str
    difficulty: str
    tags: list[str]
    run_cmd: str
    database: str
    commits: list[CommitSpec]
    truth: Truth
    path: Path = field(repr=False)

    @property
    def base_dir(self) -> Path:
        return self.path / "base"

    @property
    def solution_dir(self) -> Path:
        return self.path / "solution"

    @property
    def landing_dir(self) -> Path | None:
        d = self.path / "landing"
        return d if d.is_dir() else None


def load_scenario(scenario_dir: Path) -> Scenario:
    raw = yaml.safe_load((scenario_dir / "scenario.yaml").read_text())

    commits = [
        CommitSpec(
            overlay=c["overlay"],
            message=c["message"],
            fault=c.get("fault", False),
            author=c.get("author", CommitSpec.author),
        )
        for c in raw.get("commits", [])
    ]

    t = raw["truth"]
    cats = t["category"] if isinstance(t["category"], list) else [t["category"]]
    for c in cats:
        if c not in CATEGORIES:
            raise ValueError(f"{scenario_dir.name}: unknown category {c!r}")
    truth = Truth(
        categories=cats,
        summary=t["summary"],
        keywords_any=t.get("keywords_any", []),
        culprit_overlay=t.get("culprit_commit_overlay"),
        protected_paths=t.get("protected_paths", []),
        verify=[VerifyCheck(**v) for v in t.get("verify", [])],
    )

    faults = [c for c in commits if c.fault]
    if truth.culprit_overlay and (len(faults) != 1 or faults[0].overlay != truth.culprit_overlay):
        raise ValueError(f"{scenario_dir.name}: culprit_commit_overlay does not match the fault commit")
    if not truth.culprit_overlay and faults:
        raise ValueError(f"{scenario_dir.name}: fault commit present but no culprit_commit_overlay in truth")

    scenario = Scenario(
        id=raw["id"],
        title=raw["title"],
        difficulty=raw.get("difficulty", "medium"),
        tags=raw.get("tags", []),
        run_cmd=raw["pipeline"]["run"],
        database=raw["pipeline"]["database"],
        commits=commits,
        truth=truth,
        path=scenario_dir,
    )
    if not scenario.base_dir.is_dir():
        raise ValueError(f"{scenario_dir.name}: missing base/ directory")
    if not scenario.solution_dir.is_dir():
        raise ValueError(f"{scenario_dir.name}: missing solution/ directory")
    return scenario


def discover(scenarios_root: Path) -> list[Scenario]:
    return [
        load_scenario(p.parent)
        for p in sorted(scenarios_root.glob("*/scenario.yaml"))
    ]
