#!/usr/bin/env python3
"""LLM baseline agent for pipeline-incidents-bench.

A deliberately thin agentic loop: the model gets the incident context, then
iterates with four actions (read_file / write_file / run_pipeline / done)
until it has diagnosed the root cause and fixed the pipeline. No framework,
no retrieval — this is the floor, not the ceiling.

Works with any OpenAI-compatible chat completions endpoint. Configure via env
(a .env file in the current directory is also read):

  PIB_LLM_BASE_URL  default: Gemini's OpenAI-compat endpoint
  PIB_LLM_MODEL     default: gemini-2.5-flash
  PIB_LLM_API_KEY   default: falls back to GEMINI_API_KEY / OPENAI_API_KEY

Invoked by the harness as:
  python3 agents/llm/agent.py --workspace <repo> --context <context.json> --output <report.json>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_MODEL = "gemini-2.5-flash"

MAX_TURNS = 18
MAX_FILE_CHARS = 6_000
MAX_RUN_OUTPUT_CHARS = 4_000
SECONDS_BETWEEN_CALLS = 2
# Free tiers bound tokens/minute, and resending the whole conversation each
# turn grows quadratically. Keep the context lean and trim stale observations.
MAX_GIT_LOG_CHARS = 12_000
MAX_PIPE_LOG_CHARS = 4_000
KEEP_RECENT_OBSERVATIONS = 3
TRIMMED_OBS_CHARS = 300

SYSTEM_PROMPT = """\
You are an expert data engineer on call. A scheduled data pipeline run has \
failed. You will diagnose the root cause and FIX the pipeline by editing files \
in the workspace.

Rules of the incident:
- You may edit pipeline code (ingestion scripts, dbt models). You must NOT \
edit raw/landing data files (you don't own upstream systems) and must NOT \
delete or weaken tests — fixing the alarm is not fixing the fire.
- The failure may or may not be caused by a recent code change. Commit \
messages can be misleading; verify against the actual diffs and data. If no \
code change caused the incident, say so — do not blame an innocent commit.
- Verify your fix by rerunning the pipeline until it is green.

Respond with EXACTLY ONE JSON object per turn (no prose, no markdown fences). \
Available actions:

{"action": "read_file", "path": "<relative path>"}
{"action": "write_file", "path": "<relative path>", "content": "<full new file content>"}
{"action": "run_pipeline"}
{"action": "done", "report": {
    "root_cause_category": "schema_change | source_data_change | logic_bug | dependency_failure | infra_failure | other",
    "root_cause": "<specific free-text diagnosis>",
    "culprit_commit": "<full sha of the offending commit, or null if no code change caused this>",
    "evidence": ["<paths or short descriptions>"],
    "fix_description": "<what you changed and why>"
}}

Only call done after run_pipeline has succeeded (exit code 0), or when you \
are certain you cannot fix it.
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


class LLM:
    def __init__(self) -> None:
        self.base_url = os.environ.get("PIB_LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        self.model = os.environ.get("PIB_LLM_MODEL", DEFAULT_MODEL)
        self.api_key = (
            os.environ.get("PIB_LLM_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )
        if not self.api_key:
            sys.exit("agent: no API key (set PIB_LLM_API_KEY or GEMINI_API_KEY)")
        self.calls = 0

    def chat(self, messages: list[dict]) -> str:
        self.calls += 1
        backoff = 15
        for attempt in range(10):
            time.sleep(SECONDS_BETWEEN_CALLS)
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.2,
                },
                timeout=180,
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                # Free-tier token quotas reset each minute; waiting always
                # recovers, so be patient rather than give up.
                wait = backoff
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait = max(int(retry_after), 5)
                print(f"agent: HTTP {resp.status_code}, retrying in {wait}s", file=sys.stderr)
                time.sleep(wait)
                backoff = min(int(backoff * 1.5), 65)
                continue
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        raise RuntimeError("LLM endpoint kept failing after retries")


def parse_action(text: str) -> dict | None:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    if start == -1:
        return None
    # Take the largest balanced JSON object starting at the first brace.
    depth = 0
    in_str = False
    escape = False
    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_str:
            escape = True
        elif ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        return None
    return None


def safe_path(workspace: Path, rel: str) -> Path | None:
    p = (workspace / rel).resolve()
    return p if p.is_relative_to(workspace.resolve()) else None


def do_read(workspace: Path, rel: str) -> str:
    p = safe_path(workspace, rel)
    if p is None:
        return f"ERROR: path {rel!r} escapes the workspace"
    if not p.exists():
        return f"ERROR: {rel} does not exist"
    if p.is_dir():
        entries = sorted(x.name + ("/" if x.is_dir() else "") for x in p.iterdir())
        return f"{rel} is a directory:\n" + "\n".join(entries)
    content = p.read_text(errors="replace")
    if len(content) > MAX_FILE_CHARS:
        content = content[:MAX_FILE_CHARS] + "\n...[truncated]..."
    return content


def do_write(workspace: Path, rel: str, content: str) -> str:
    p = safe_path(workspace, rel)
    if p is None:
        return f"ERROR: path {rel!r} escapes the workspace"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"wrote {len(content)} chars to {rel}"


def do_run(workspace: Path) -> str:
    result = subprocess.run(
        ["bash", "run_pipeline.sh"],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=600,
    )
    out = (result.stdout + "\n" + result.stderr)[-MAX_RUN_OUTPUT_CHARS:]
    return f"exit_code: {result.returncode}\n{out}"


def compact_context(context: dict) -> dict:
    """Shrink the incident bundle to fit comfortably in free-tier token budgets."""
    c = dict(context)
    if len(c.get("git_log", "")) > MAX_GIT_LOG_CHARS:
        c["git_log"] = c["git_log"][:MAX_GIT_LOG_CHARS] + "\n...[truncated]..."
    run = dict(c.get("pipeline_run", {}))
    for k in ("stdout", "stderr"):
        v = run.get(k, "")
        if len(v) > MAX_PIPE_LOG_CHARS:
            run[k] = "...[truncated]...\n" + v[-MAX_PIPE_LOG_CHARS:]
    c["pipeline_run"] = run
    return c


def trim_history(messages: list[dict]) -> None:
    """Collapse old observations in place; the model can re-read files."""
    obs_indexes = [
        i
        for i, m in enumerate(messages)
        if m["role"] == "user" and m["content"].startswith("OBSERVATION:")
    ]
    for i in obs_indexes[:-KEEP_RECENT_OBSERVATIONS]:
        if len(messages[i]["content"]) > TRIMMED_OBS_CHARS:
            messages[i]["content"] = (
                messages[i]["content"][:TRIMMED_OBS_CHARS]
                + "\n...[older observation trimmed — re-read the file if needed]..."
            )


def fallback_report(note: str) -> dict:
    return {
        "root_cause_category": "other",
        "root_cause": f"agent failed to complete: {note}",
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
    llm = LLM()
    workspace = Path(args.workspace)
    context = json.loads(Path(args.context).read_text())

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "INCIDENT CONTEXT:\n" + json.dumps(compact_context(context), indent=1),
        },
    ]

    report = fallback_report("ran out of turns")
    for turn in range(MAX_TURNS):
        trim_history(messages)
        try:
            reply = llm.chat(messages)
        except Exception as e:  # endpoint failure — file what we have
            report = fallback_report(str(e))
            break
        messages.append({"role": "assistant", "content": reply})

        action = parse_action(reply)
        if action is None:
            messages.append({"role": "user", "content": "Could not parse JSON. Respond with exactly one valid JSON action object."})
            continue

        kind = action.get("action")
        print(f"agent turn {turn + 1}: {kind} {action.get('path', '')}", file=sys.stderr)

        if kind == "done":
            report = action.get("report") or fallback_report("done without report")
            break
        elif kind == "read_file":
            obs = do_read(workspace, str(action.get("path", "")))
        elif kind == "write_file":
            obs = do_write(workspace, str(action.get("path", "")), str(action.get("content", "")))
        elif kind == "run_pipeline":
            obs = do_run(workspace)
        else:
            obs = f"ERROR: unknown action {kind!r}"
        messages.append({"role": "user", "content": f"OBSERVATION:\n{obs}"})

    Path(args.output).write_text(json.dumps(report, indent=2))
    print(f"agent: finished after {llm.calls} LLM calls", file=sys.stderr)


if __name__ == "__main__":
    main()
