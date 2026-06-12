#!/usr/bin/env python3
"""Repeated-trials variance study: curated vs collector context.

Runs every scenario N times in each context mode with the same agent, so the
per-scenario deltas and the overall gap can be reported as mean +/- spread
instead of a single noisy sample. Each completed run is appended to an NDJSON
log immediately, so a partial study is still usable if interrupted.

Usage (from the repo root, with the bench venv active):
  python tools/variance_study.py --trials 5 \
      --agent ".venv/bin/python agents/cursor/agent.py"
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pib.cli import _find_scenarios_root, _run_one  # noqa: E402
from pib.scoring import WEIGHTS  # noqa: E402
from pib.spec import discover  # noqa: E402

MODES = ("curated", "collector")
TMP_DRIFT_DB = Path("/tmp/analytics_warehouse.duckdb")


def run_matrix(agent: str, trials: int, log_path: Path) -> list[dict]:
    scenarios = discover(_find_scenarios_root())
    records: list[dict] = []
    total = len(MODES) * trials * len(scenarios)
    done = 0
    t0 = time.monotonic()
    with log_path.open("a") as log:
        for mode in MODES:
            for trial in range(1, trials + 1):
                for s in scenarios:
                    # Scenario 010 writes a shared /tmp warehouse; clear it so
                    # each trial starts from the same drifted state.
                    TMP_DRIFT_DB.unlink(missing_ok=True)
                    res = _run_one(s, agent, keep=False, context_source=mode)
                    rec = {
                        "mode": mode,
                        "trial": trial,
                        "scenario": s.id,
                        "total": res.get("total"),
                        "checks": res.get("checks", {}),
                        "error": res.get("error"),
                    }
                    records.append(rec)
                    log.write(json.dumps(rec) + "\n")
                    log.flush()
                    done += 1
                    elapsed = time.monotonic() - t0
                    eta = (elapsed / done) * (total - done)
                    print(
                        f"[{done}/{total}] {mode}/{s.id} trial {trial}: "
                        f"{_pct(rec['total'])}  (eta {eta/60:.1f}m)",
                        flush=True,
                    )
    return records


def _pct(x) -> str:
    return "ERR" if x is None else f"{x*100:.0f}%"


def aggregate(records: list[dict], trials: int) -> str:
    scenarios = sorted({r["scenario"] for r in records})
    lines: list[str] = []
    lines.append("# Variance study: curated vs collector context\n")
    lines.append(
        f"Agent: Cursor (composer-2.5). Trials: {trials} per (scenario, mode). "
        f"Each cell is mean across trials; range is min-max.\n"
    )

    # Per-scenario mean +/- range, both modes side by side.
    lines.append("## Per-scenario score (mean, [min-max], stdev)\n")
    lines.append("| Scenario | Curated | Collector |")
    lines.append("|---|---|---|")
    for sc in scenarios:
        cells = []
        for mode in MODES:
            vals = [
                r["total"] for r in records
                if r["scenario"] == sc and r["mode"] == mode and r["total"] is not None
            ]
            cells.append(_cell(vals))
        lines.append(f"| {sc} | {cells[0]} | {cells[1]} |")

    # Overall per mode: average each trial across scenarios, then summarize.
    lines.append("\n## Overall (per-trial mean across all scenarios)\n")
    lines.append("| Mode | Mean | [min-max] | stdev | Pipelines fixed (mean) |")
    lines.append("|---|---|---|---|---|")
    for mode in MODES:
        trial_means = []
        fix_rates = []
        for t in range(1, trials + 1):
            vals = [
                r["total"] for r in records
                if r["mode"] == mode and r["trial"] == t and r["total"] is not None
            ]
            if vals:
                trial_means.append(statistics.mean(vals))
            fixes = [
                1 for r in records
                if r["mode"] == mode and r["trial"] == t
                and r.get("checks", {}).get("fix_verified")
            ]
            fix_rates.append(len(fixes))
        if trial_means:
            lo, hi = min(trial_means), max(trial_means)
            sd = statistics.stdev(trial_means) if len(trial_means) > 1 else 0.0
            lines.append(
                f"| {mode} | {statistics.mean(trial_means)*100:.1f}% | "
                f"[{lo*100:.0f}-{hi*100:.0f}%] | {sd*100:.1f} pts | "
                f"{statistics.mean(fix_rates):.1f}/10 |"
            )

    # Per-check pass rate, to show WHERE the modes differ.
    lines.append("\n## Per-check pass rate (fraction of all runs that passed)\n")
    lines.append("| Check | Weight | Curated | Collector |")
    lines.append("|---|---|---|---|")
    for check, weight in WEIGHTS.items():
        cells = []
        for mode in MODES:
            runs = [r for r in records if r["mode"] == mode and r["total"] is not None]
            passed = [r for r in runs if r.get("checks", {}).get(check)]
            cells.append(f"{len(passed)}/{len(runs)} ({len(passed)/len(runs)*100:.0f}%)" if runs else "-")
        lines.append(f"| {check} | {weight:.0%} | {cells[0]} | {cells[1]} |")

    return "\n".join(lines) + "\n"


def _cell(vals: list[float]) -> str:
    if not vals:
        return "—"
    mean = statistics.mean(vals)
    lo, hi = min(vals), max(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    rng = f"{lo*100:.0f}" if lo == hi else f"{lo*100:.0f}-{hi*100:.0f}"
    return f"{mean*100:.0f}% [{rng}] s={sd*100:.0f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--agent", default=".venv/bin/python agents/cursor/agent.py")
    ap.add_argument("--log", default="tools/variance_runs.ndjson")
    ap.add_argument("--out", default="VARIANCE.md")
    ap.add_argument(
        "--aggregate-only", action="store_true",
        help="skip running; just aggregate an existing --log",
    )
    args = ap.parse_args()

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if args.aggregate_only:
        records = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    else:
        records = run_matrix(args.agent, args.trials, log_path)

    report = aggregate(records, args.trials)
    Path(args.out).write_text(report)
    print("\n" + report)


if __name__ == "__main__":
    main()
