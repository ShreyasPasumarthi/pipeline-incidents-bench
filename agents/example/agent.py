#!/usr/bin/env python3
"""Minimal example of the pib agent protocol.

The harness invokes:

    python3 agents/example/agent.py --workspace <repo> --context <context.json> --output <report.json>

A real agent would read context.json (failing run logs, dbt run results, git
history, data samples), investigate the workspace, EDIT files to fix the
pipeline, and write its diagnosis to report.json. This one only demonstrates
the I/O contract — it diagnoses nothing and fixes nothing, so it scores 0%.
"""

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.context) as f:
        context = json.load(f)

    failing = [
        r["unique_id"]
        for r in context.get("dbt_run_results", [])
        if r.get("status") in ("error", "fail")
    ]

    report = {
        "root_cause_category": "other",
        "root_cause": f"pipeline failed (failing nodes: {failing}); cause not investigated",
        "culprit_commit": None,
        "evidence": failing,
        "fix_description": "no fix attempted",
    }
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    main()
