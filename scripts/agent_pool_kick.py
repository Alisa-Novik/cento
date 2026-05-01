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
DEFAULT_CODEX_MODEL = os.environ.get("CENTO_POOL_CODEX_MODEL", "gpt-5.4-mini")
ACTIVE_STATUSES = {"planned", "launching", "running"}
ENDED_STATUSES = {"dry_run", "succeeded", "failed", "blocked", "stale", "exited_unknown"}
LANES = ("validator", "small", "builder", "coordinator")
SMALL_TOKENS = ("screenshot", "evidence", "strict review", "template", "fixture", "docs", "process", "heartbeat", "stale", "cron", "pool")


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


def issue_matches_lane(issue: dict[str, Any], lane: str) -> bool:
    status = str(issue.get("status") or "")
    role = str(issue.get("role") or "")
    subject = str(issue.get("subject") or "").lower()
    if lane == "validator":
        return status == "Validating" or role == "validator"
    if lane == "builder":
        return role in {"builder", ""}
    if lane == "small":
        return role in {"builder", ""} and any(token in subject for token in SMALL_TOKENS)
    if lane == "coordinator":
        return role == "coordinator"
    return False


def issue_is_candidate(issue: dict[str, Any], lane: str) -> bool:
    status = str(issue.get("status") or "")
    role = str(issue.get("role") or "")
    subject = str(issue.get("subject") or "").lower()
    if lane == "validator":
        return status == "Validating" or (role == "validator" and status == "Queued")
    if lane == "builder":
        return role in {"builder", ""} and status == "Queued"
    if lane == "small":
        return role in {"builder", ""} and status == "Queued" and any(token in subject for token in SMALL_TOKENS)
    if lane == "coordinator":
        return role == "coordinator" and status == "Queued"
    return False


def lane_stats(all_issues: list[dict[str, Any]], lane: str, blocked: set[int]) -> dict[str, int]:
    stats = {
        "matching": 0,
        "eligible": 0,
        "queued": 0,
        "blocked": 0,
        "review": 0,
        "validating": 0,
        "active_locked": 0,
    }
    for issue in all_issues:
        issue_id = int(issue.get("id") or 0)
        if not issue_matches_lane(issue, lane):
            continue
        stats["matching"] += 1
        status = str(issue.get("status") or "")
        if issue_id in blocked:
            stats["active_locked"] += 1
        if status == "Queued":
            stats["queued"] += 1
        elif status == "Blocked":
            stats["blocked"] += 1
        elif status == "Review":
            stats["review"] += 1
        elif status == "Validating":
            stats["validating"] += 1
        if issue_is_candidate(issue, lane) and issue_id not in blocked:
            stats["eligible"] += 1
    return stats


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
        if issue_is_candidate(issue, lane):
            rows.append(issue)
    rows.sort(key=issue_priority)
    return rows


def classify_dispatch_failure(stderr: str, stdout: str = "") -> str:
    text = f"{stdout}\n{stderr}".lower()
    if any(token in text for token in ("unknown runtime", "agent runtime registry", "no usable runtimes", "runtime registry must")):
        return "runtime_missing"
    if any(token in text for token in ("version skew", "model mismatch", "runtime version mismatch")):
        return "version_skew"
    return "dispatch_failures"


def summarize_lane_reason(snapshot: dict[str, Any]) -> str:
    if snapshot["active"] >= snapshot["target"]:
        return "active_target_already_met"
    if snapshot["eligible"] > 0:
        return "ready"
    if snapshot["matching"] == 0:
        return "no_candidates"
    if snapshot["blocked"] > 0 or snapshot["review"] > 0:
        return "all_candidates_blocked_review"
    return "no_candidates"


def reason_text(reason: str) -> tuple[str, str]:
    if reason == "dry_run":
        return (
            "Dry run planned launch work but did not start any workers.",
            "Rerun without --dry-run to actually launch the selected workers.",
        )
    if reason == "launched":
        return (
            "At least one worker launched successfully.",
            "Monitor the active runs and rerun only if the queue changes.",
        )
    if reason == "active_target_already_met":
        return (
            "No workers launched because every lane is already at or above its active target.",
            "Wait for active workers to finish or raise the targets before rerunning the pool.",
        )
    if reason == "all_candidates_blocked_review":
        return (
            "No workers launched because the remaining lane-matching issues are blocked or in Review.",
            "Unblock or finish the candidate issues, then rerun the pool.",
        )
    if reason == "version_skew":
        return (
            "No workers launched because the dispatch attempt hit a runtime/model version skew.",
            "Requeue the stale model work or align the runtime/model mapping, then rerun the pool.",
        )
    if reason == "runtime_missing":
        return (
            "No workers launched because the requested runtime or runtime registry could not be resolved.",
            "Fix the runtime registry or install the missing runtime binary, then rerun the pool.",
        )
    if reason == "dispatch_failures":
        return (
            "No workers launched because every dispatch attempt failed.",
            "Inspect the failure list, fix the underlying dispatch error, then rerun the pool.",
        )
    return (
        "No workers launched.",
        "Inspect the pool diagnostics and rerun once the blocker is cleared.",
    )


def build_reason_summary(
    *,
    dry_run: bool,
    launched: list[dict[str, Any]],
    all_issues: list[dict[str, Any]],
    blocked: set[int],
    counts: dict[str, int],
    targets: dict[str, int],
) -> dict[str, Any]:
    successful_launches = [item for item in launched if item.get("returncode", 0) == 0 and not dry_run]
    failed_launches = [item for item in launched if item.get("returncode", 0) not in (0, None)]
    lane_snapshots: list[dict[str, Any]] = []
    for lane in LANES:
        snapshot = {
            "lane": lane,
            "active": counts.get(lane, 0),
            "target": targets.get(lane, 0),
            "needed": max(0, targets.get(lane, 0) - counts.get(lane, 0)),
        }
        snapshot.update(lane_stats(all_issues, lane, blocked))
        snapshot["reason"] = summarize_lane_reason(snapshot)
        lane_snapshots.append(snapshot)
    if dry_run and launched:
        reason = "dry_run"
    elif successful_launches:
        reason = "launched"
    else:
        failure_reasons = [classify_dispatch_failure(str(item.get("stderr") or ""), str(item.get("stdout") or "")) for item in failed_launches]
        if "runtime_missing" in failure_reasons:
            reason = "runtime_missing"
        elif "version_skew" in failure_reasons:
            reason = "version_skew"
        elif failed_launches:
            reason = "dispatch_failures"
        elif lane_snapshots and all(snapshot["reason"] == "active_target_already_met" for snapshot in lane_snapshots):
            reason = "active_target_already_met"
        elif any(snapshot["reason"] == "all_candidates_blocked_review" for snapshot in lane_snapshots):
            reason = "all_candidates_blocked_review"
        else:
            reason = "no_candidates"
    summary, next_action = reason_text(reason)
    dispatch_failures = [
        {
            "issue": int(item.get("issue") or 0),
            "lane": item.get("lane"),
            "returncode": int(item.get("returncode") or 0),
            "reason": classify_dispatch_failure(str(item.get("stderr") or ""), str(item.get("stdout") or "")),
            "stderr": str(item.get("stderr") or ""),
        }
        for item in failed_launches
    ]
    return {
        "primary_reason": reason,
        "summary": summary,
        "next_action": next_action,
        "dry_run": dry_run,
        "attempt_count": len(launched),
        "success_count": len(successful_launches),
        "failure_count": len(failed_launches),
        "lanes": lane_snapshots,
        "dispatch_failures": dispatch_failures,
    }


def dispatch(issue: dict[str, Any], lane: str) -> dict[str, Any]:
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
    if runtime == "codex" and DEFAULT_CODEX_MODEL:
        command.extend(["--model", DEFAULT_CODEX_MODEL])
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
                record.update(dispatch(issue, lane))
            launched.append(record)
            reserved.add(int(issue["id"]))
        if len(launched) >= args.max_launch:
            break
    successful_launches = [item for item in launched if item.get("returncode", 0) == 0 and not args.dry_run]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "active_counts": counts,
        "targets": targets,
        "launched": launched,
        "successful_launches": successful_launches,
        "failed_launches": [item for item in launched if item.get("returncode", 0) not in (0, None)],
        "reason_summary": build_reason_summary(
            dry_run=args.dry_run,
            launched=launched,
            all_issues=all_issues,
            blocked=blocked,
            counts=counts,
            targets=targets,
        ),
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / "agent-pool-kick-latest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if all(item.get("returncode", 0) == 0 for item in launched) else 1


if __name__ == "__main__":
    raise SystemExit(main())
