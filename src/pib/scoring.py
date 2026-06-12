"""Scores an agent's report and fix against the scenario's ground truth.

The headline property of this benchmark: the fix is graded by EXECUTION, not
opinion. We rerun the pipeline after the agent's edits — it goes green and
passes hidden data assertions, or it doesn't.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from .pipeline import PipelineRun, run_pipeline
from .spec import Scenario
from .workspace import Workspace, worktree_diff

WEIGHTS = {
    "category": 0.15,
    "culprit_commit": 0.15,
    "root_cause": 0.20,
    "fix_verified": 0.50,
}


@dataclass
class ScoreCard:
    checks: dict[str, bool] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)
    touched_files: list[str] = field(default_factory=list)
    agent_patch: str = ""
    rerun: PipelineRun | None = None

    @property
    def total(self) -> float:
        return round(sum(WEIGHTS[k] for k, ok in self.checks.items() if ok), 4)

    def as_dict(self) -> dict:
        return {
            "total": self.total,
            "checks": self.checks,
            "notes": self.notes,
            "touched_files": self.touched_files,
        }


def _norm_sha(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("", "null", "none", "n/a", "no commit", "unknown"):
        return None
    return s


def _check_culprit(scenario: Scenario, ws: Workspace, reported) -> tuple[bool, str]:
    truth_sha = (
        ws.commit_map.get(scenario.truth.culprit_overlay)
        if scenario.truth.culprit_overlay
        else None
    )
    rep = _norm_sha(reported)
    if truth_sha is None:
        ok = rep is None
        return ok, "correctly reported no culprit commit" if ok else (
            f"blamed commit {rep} but no code change caused this incident"
        )
    if rep is None:
        return False, f"missed culprit commit {truth_sha[:10]}"
    ok = truth_sha.startswith(rep) and len(rep) >= 7 or rep == truth_sha
    return ok, f"expected {truth_sha[:10]}, got {rep[:10]}"


def _check_keywords(scenario: Scenario, report: dict) -> tuple[bool, str]:
    text = " ".join(
        str(report.get(k, "")) for k in ("root_cause", "fix_description")
    ).lower()
    missing = []
    for group in scenario.truth.keywords_any:
        if not any(kw.lower() in text for kw in group):
            missing.append(group)
    if missing:
        return False, f"diagnosis missing concepts: {missing}"
    return True, "all root-cause concepts present"


def _check_protected(scenario: Scenario, touched: list[str]) -> tuple[bool, str]:
    violations = [
        f
        for f in touched
        for pattern in scenario.truth.protected_paths
        if fnmatch.fnmatch(f, pattern)
    ]
    if violations:
        return False, f"modified protected files (upstream data / tests): {sorted(set(violations))}"
    return True, "no protected files touched"


def _run_verify_checks(scenario: Scenario, repo: Path) -> tuple[bool, str]:
    db = repo / scenario.database
    if not db.exists():
        return False, f"database {scenario.database} not found after rerun"
    con = duckdb.connect(str(db), read_only=True)
    try:
        for check in scenario.truth.verify:
            try:
                row = con.execute(check.sql).fetchone()
            except duckdb.Error as exc:
                return False, f"assertion errored: {check.sql!r} -> {exc}"
            observed = row[0] if row else None
            observed = float(observed) if observed is not None else None
            if not check.passes(observed):
                return False, (
                    f"assertion failed: {check.sql!r} -> {observed} "
                    f"(want {check.op} {check.value})"
                )
    finally:
        con.close()
    return True, "pipeline green and all hidden data assertions pass"


def score(scenario: Scenario, ws: Workspace, report: dict) -> ScoreCard:
    card = ScoreCard()

    ok = report.get("root_cause_category") in scenario.truth.categories
    card.checks["category"] = ok
    card.notes["category"] = (
        "correct" if ok
        else f"expected one of {scenario.truth.categories}, got {report.get('root_cause_category')!r}"
    )

    ok, note = _check_culprit(scenario, ws, report.get("culprit_commit"))
    card.checks["culprit_commit"] = ok
    card.notes["culprit_commit"] = note

    ok, note = _check_keywords(scenario, report)
    card.checks["root_cause"] = ok
    card.notes["root_cause"] = note

    card.touched_files, card.agent_patch = worktree_diff(ws.repo)
    protected_ok, protected_note = _check_protected(scenario, card.touched_files)

    if not protected_ok:
        card.checks["fix_verified"] = False
        card.notes["fix_verified"] = protected_note
        return card

    rerun = run_pipeline(ws.repo, scenario.run_cmd)
    card.rerun = rerun
    if not rerun.green:
        card.checks["fix_verified"] = False
        card.notes["fix_verified"] = "pipeline still red after agent's fix"
        return card

    ok, note = _run_verify_checks(scenario, ws.repo)
    card.checks["fix_verified"] = ok
    card.notes["fix_verified"] = note
    return card
