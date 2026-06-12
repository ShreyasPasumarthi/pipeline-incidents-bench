"""pib — pipeline-incidents-bench command line.

  pib list                                  show scenarios
  pib run --agent <cmd|oracle|null> [--scenario ID]
  pib validate [--scenario ID]              red baseline + oracle must score 100%
"""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
import sys
from pathlib import Path

from . import __version__
from .agents import run_agent
from .context import build_context
from .pipeline import run_pipeline
from .scoring import WEIGHTS, score
from .spec import Scenario, discover
from .workspace import build


def _find_scenarios_root() -> Path:
    here = Path.cwd()
    for candidate in (here, *here.parents):
        if (candidate / "scenarios").is_dir():
            return candidate / "scenarios"
    sys.exit("error: no scenarios/ directory found (run from the bench repo)")


def _runs_root() -> Path:
    root = _find_scenarios_root().parent / ".pib_runs"
    root.mkdir(exist_ok=True)
    return root


def _select(scenarios: list[Scenario], wanted: str | None) -> list[Scenario]:
    if not wanted:
        return scenarios
    hits = [s for s in scenarios if s.id == wanted or s.id.startswith(wanted)]
    if not hits:
        sys.exit(f"error: no scenario matching {wanted!r}")
    return hits


def _run_one(scenario: Scenario, agent_cmd: str, keep: bool) -> dict:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = _runs_root() / f"{ts}_{scenario.id}"
    run_dir.mkdir(parents=True)

    ws = build(scenario, run_dir)

    first_run = run_pipeline(ws.repo, scenario.run_cmd)
    (run_dir / "first_run.log").write_text(first_run.stdout + "\n--- stderr ---\n" + first_run.stderr)
    if first_run.green:
        return {
            "scenario": scenario.id,
            "error": "scenario did not reproduce: first run was green",
            "total": None,
        }

    context = build_context(ws.repo, first_run)
    context_path = run_dir / "context.json"
    context_path.write_text(json.dumps(context, indent=2))

    report_path = run_dir / "report.json"
    report = run_agent(agent_cmd, scenario, ws, context_path, report_path)

    card = score(scenario, ws, report)
    (run_dir / "agent.patch").write_text(card.agent_patch)
    result = {
        "scenario": scenario.id,
        "title": scenario.title,
        "agent": agent_cmd,
        "run_dir": str(run_dir),
        **card.as_dict(),
    }
    (run_dir / "results.json").write_text(json.dumps(result, indent=2))

    if not keep:
        shutil.rmtree(run_dir / "repo", ignore_errors=True)
    return result


def _print_result(result: dict) -> None:
    if result.get("error"):
        print(f"  {result['scenario']}: ERROR — {result['error']}")
        return
    print(f"  {result['scenario']}  ({result['title']})")
    for check, weight in WEIGHTS.items():
        ok = result["checks"].get(check, False)
        mark = "PASS" if ok else "FAIL"
        print(f"    [{mark}] {check:<16} ({weight:.0%})  {result['notes'].get(check, '')}")
    print(f"    score: {result['total']:.0%}")


def cmd_list(args) -> None:
    for s in discover(_find_scenarios_root()):
        print(f"{s.id:<32} {s.difficulty:<8} {', '.join(s.tags)}")
        print(f"  {s.title}")


def cmd_run(args) -> None:
    scenarios = _select(discover(_find_scenarios_root()), args.scenario)
    results = []
    print(f"pib {__version__} — agent: {args.agent}\n")
    for s in scenarios:
        result = _run_one(s, args.agent, args.keep)
        _print_result(result)
        results.append(result)
    scored = [r["total"] for r in results if r.get("total") is not None]
    if scored:
        print(f"\noverall: {sum(scored) / len(scored):.0%} across {len(scored)} scenario(s)")
    if any(r.get("error") for r in results):
        sys.exit(1)


def cmd_validate(args) -> None:
    """Every scenario must (a) reproduce red and (b) be solvable: the oracle
    agent applying the hidden solution must score 100%."""
    scenarios = _select(discover(_find_scenarios_root()), args.scenario)
    failures = 0
    for s in scenarios:
        result = _run_one(s, "oracle", keep=False)
        ok = result.get("total") == 1.0
        status = "OK " if ok else "BAD"
        print(f"[{status}] {s.id}")
        if not ok:
            failures += 1
            _print_result(result)
    print(f"\n{len(scenarios) - failures}/{len(scenarios)} scenarios valid")
    if failures:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(prog="pib")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list scenarios").set_defaults(func=cmd_list)

    p_run = sub.add_parser("run", help="run agent against scenarios")
    p_run.add_argument("--agent", required=True, help='agent command, or built-ins "oracle"/"null"')
    p_run.add_argument("--scenario", help="scenario id (prefix ok); default all")
    p_run.add_argument("--keep", action="store_true", help="keep workspace repos after run")
    p_run.set_defaults(func=cmd_run)

    p_val = sub.add_parser("validate", help="check scenarios reproduce + are solvable")
    p_val.add_argument("--scenario", help="scenario id (prefix ok); default all")
    p_val.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    args.func(args)
