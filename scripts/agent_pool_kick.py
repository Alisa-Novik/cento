#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = Path.home() / ".local" / "state" / "cento"
DEFAULT_TARGETS = {"builder": 4, "validator": 3, "small": 3, "coordinator": 1}
DEFAULT_CODEX_MODEL = (
    os.environ.get("CENTO_POOL_CODEX_MODEL")
    or os.environ.get("CENTO_AGENT_MODEL")
    or "gpt-5.3-codex-spark"
)
ACTIVE_STATUSES = {"planned", "launching", "running"}
ENDED_STATUSES = {"dry_run", "succeeded", "failed", "blocked", "stale", "exited_unknown"}


def run_json(command: list[str], timeout: int = 25) -> dict[str, Any]:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"{command} exited {result.returncode}")
    payload = json.loads(result.stdout)
    return payload if isinstance(payload, dict) else {}


def run(command: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)


def active_runs() -> list[dict[str, Any]]:
    payload = run_json(["python3", "scripts/agent_work.py", "runs", "--json", "--active", "--no-untracked"], timeout=15)
    return payload.get("runs") or []


def issues() -> list[dict[str, Any]]:
    payload = run_json(["python3", "scripts/agent_work.py", "list", "--json"], timeout=25)
    return payload.get("issues") or []


def active_issue_ids(runs: list[dict[str, Any]]) -> set[int]:
    ids: set[int] = set()
    for item in runs:
        if str(item.get("status") or "") in ACTIVE_STATUSES and item.get("issue_id") is not None:
            try:
                ids.add(int(item["issue_id"]))
            except (TypeError, ValueError):
                pass
    return ids


def active_pool_counts(runs: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"builder": 0, "validator": 0, "small": 0, "coordinator": 0}
    for item in runs:
        if str(item.get("status") or "") not in ACTIVE_STATUSES:
            continue
        agent = str(item.get("agent") or "")
        role = str(item.get("role") or "")
        if agent.startswith("small-worker"):
            counts["small"] += 1
        elif role in counts:
            counts[role] += 1
    return counts


def issue_priority(issue: dict[str, Any]) -> tuple[int, int]:
    package = str(issue.get("package") or "")
    subject = str(issue.get("subject") or "")
    status = str(issue.get("status") or "")
    score = 50
    if package == "redmine-replacement-v1":
        score -= 30
    if status == "Validating":
        score -= 20
    if any(token in subject.lower() for token in ("cutover", "migration", "backend", "api", "parity")):
        score -= 10
    return score, int(issue.get("id") or 0)


def candidates(all_issues: list[dict[str, Any]], lane: str, blocked: set[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for issue in all_issues:
        issue_id = int(issue.get("id") or 0)
        if issue_id in blocked:
            continue
        status = str(issue.get("status") or "")
        role = str(issue.get("role") or "")
        subject = str(issue.get("subject") or "")
        if lane == "validator":
            if status == "Validating" or (role == "validator" and status == "Queued"):
                rows.append(issue)
        elif lane == "builder":
            if role in {"builder", ""} and status == "Queued":
                rows.append(issue)
        elif lane == "small":
            small_tokens = ("screenshot", "evidence", "strict review", "template", "fixture", "docs", "process", "heartbeat", "stale", "cron", "pool")
            if role in {"builder", ""} and status == "Queued" and any(token in subject.lower() for token in small_tokens):
                rows.append(issue)
        elif lane == "coordinator":
            if role == "coordinator" and status == "Queued":
                rows.append(issue)
    rows.sort(key=issue_priority)
    return rows


def dispatch(issue: dict[str, Any], lane: str, model: str) -> dict[str, Any]:
    issue_id = str(issue["id"])
    if lane == "small":
        role = "builder"
        agent = "small-worker-pool"
        runtime = "codex"
    elif lane == "validator":
        role = "validator"
        agent = "validator-pool"
        runtime = "codex"
    elif lane == "coordinator":
        role = "coordinator"
        agent = "coordinator-pool"
        runtime = "codex"
    else:
        role = "builder"
        agent = "builder-pool"
        runtime = "codex"
    command = [
        "./scripts/cento.sh",
        "agent-work",
        "dispatch",
        issue_id,
        "--node",
        "linux",
        "--agent",
        agent,
        "--role",
        role,
        "--runtime",
        runtime,
    ]
    if runtime == "codex" and model:
        command.extend(["--model", model])
    result = run(command, timeout=90)
    return {
        "issue": int(issue_id),
        "lane": lane,
        "agent": agent,
        "role": role,
        "runtime": runtime,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep tracked Cento builder/validator/small-worker pools moving.")
    parser.add_argument("--builder-target", type=int, default=DEFAULT_TARGETS["builder"])
    parser.add_argument("--validator-target", type=int, default=DEFAULT_TARGETS["validator"])
    parser.add_argument("--small-target", type=int, default=DEFAULT_TARGETS["small"])
    parser.add_argument("--coordinator-target", type=int, default=DEFAULT_TARGETS["coordinator"])
    parser.add_argument("--max-launch", type=int, default=8)
    parser.add_argument("--model", default=DEFAULT_CODEX_MODEL, help="Codex model to use for launched worker runs.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    runs = active_runs()
    all_issues = issues()
    blocked = active_issue_ids(runs)
    counts = active_pool_counts(runs)
    targets = {
        "validator": args.validator_target,
        "builder": args.builder_target,
        "small": args.small_target,
        "coordinator": args.coordinator_target,
    }
    launched: list[dict[str, Any]] = []
    reserved = set(blocked)
    for lane in ("validator", "small", "builder", "coordinator"):
        needed = max(0, targets[lane] - counts.get(lane, 0))
        for issue in candidates(all_issues, lane, reserved)[:needed]:
            if len(launched) >= args.max_launch:
                break
            record = {
                "issue": int(issue["id"]),
                "lane": lane,
                "subject": issue.get("subject"),
                "dry_run": args.dry_run,
            }
            if not args.dry_run:
                record.update(dispatch(issue, lane, args.model))
            launched.append(record)
            reserved.add(int(issue["id"]))
        if len(launched) >= args.max_launch:
            break
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "model": args.model,
        "max_launch": args.max_launch,
        "active_counts": counts,
        "targets": targets,
        "launched_count": len(launched),
        "launched": launched,
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / "agent-pool-kick-latest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if all(item.get("returncode", 0) == 0 for item in launched) else 1


if __name__ == "__main__":
    raise SystemExit(main())
