#!/usr/bin/env python3
"""Run the append-only Walk Autopilot follow-up loop."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
import shlex
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import spend_ledger


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "workspace" / "runs" / "walk-autopilot"
ROUTING_RUN_ROOT = RUN_ROOT / "routing-native"
ROUTING_LATEST_DIR = ROUTING_RUN_ROOT / "latest"
REVIEW_UNBLOCK_RUN_ROOT = RUN_ROOT / "review-unblock"
REVIEW_UNBLOCK_LATEST_DIR = REVIEW_UNBLOCK_RUN_ROOT / "latest"
PATCH_SWARM_AUTOPILOT_ROOT = RUN_ROOT / "patch-swarm"
PATCH_SWARM_AUTOPILOT_LATEST_DIR = PATCH_SWARM_AUTOPILOT_ROOT / "latest"
STATE_DIR = Path.home() / ".local" / "state" / "cento"
FACTORY_SCALE_CRON_BEGIN = "# BEGIN CENTO FACTORY SCALE FINAL TEST"
FACTORY_SCALE_CRON_END = "# END CENTO FACTORY SCALE FINAL TEST"
FACTORY_SCALE_LOG_PATH = ROOT / "workspace" / "logs" / "factory-scale-final-test.log"
FACTORY_SCALE_ROADMAP_DOC = ROOT / "docs" / "factory-1000-patch-swarm-roadmap.md"
FACTORY_SCALE_ADVANCE_DIRNAME = "advance"
FACTORY_SCALE_ACTIVE_STATUSES = {"planned", "running"}
LIVE_API_LOCK_NAME = "openai-live-api.lock"
ROUTING_CRON_BEGIN = "# BEGIN CENTO ROUTING NATIVE LOOP"
ROUTING_CRON_END = "# END CENTO ROUTING NATIVE LOOP"
ROUTING_LOG_PATH = ROOT / "workspace" / "logs" / "routing-native-loop.log"
ROUTING_AGENT_WORK_PACKAGE = "cento-routing-nativeness"
REVIEW_UNBLOCK_ACTION_CAPS = {
    "close_done": 20,
    "validate_local": 4,
    "dispatch_validator": 3,
    "requeue_stale_dispatch": 6,
    "repair_task": 3,
    "close_demo_test": 10,
    "archive_stale_historical": 6,
}
REVIEW_UNBLOCK_ACTIVE_RUN_STATUSES = {"planned", "launching", "running"}
REVIEW_UNBLOCK_MUTATING_TYPES = {
    "close_done",
    "validate_local",
    "dispatch_validator",
    "requeue_stale_dispatch",
    "repair_task",
    "close_demo_test",
    "archive_stale_historical",
}
SKILL_TERMS = [
    "cento-native",
    "ui-verify-and-report",
    "cento-requirements-manifest",
    "navigate-skills",
    "openai-docs",
    "imagegen",
    "plugin-creator",
    "skill-creator",
    "skill-installer",
]
REQUIRED_LOOP_SECTIONS = [
    "Findings",
    "Breakthroughs",
    "Copied-Forward Notes",
    "Next Steps",
    "Next Big Things",
    "Spend",
    "Validation",
    "Changed Files",
    "Blockers",
    "Recommended Next Loop",
]
DASHBOARD_TOTAL_ENV = "CENTO_OPENAI_DASHBOARD_TOTAL_SPEND_USD"
OPENAI_HARD_CAP_ENV = "CENTO_OPENAI_HARD_CAP_USD"
REQUIRE_DASHBOARD_BUDGET_ENV = "CENTO_REQUIRE_DASHBOARD_TOTAL_BUDGET"
FACTORY_SCALE_PROREQ_COMMANDS = [
    ("intake", ["./scripts/cento.sh", "proreq-light", "intake"]),
    ("context", ["./scripts/cento.sh", "proreq-light", "context"]),
    ("screenshot", ["./scripts/cento.sh", "proreq-light", "screenshot"]),
    ("pro-request", ["./scripts/cento.sh", "proreq-light", "pro-request"]),
    ("codex-plan", ["./scripts/cento.sh", "proreq-light", "codex-plan"]),
    ("backend-work", ["./scripts/cento.sh", "proreq-light", "backend-work"]),
    ("integration-plan", ["./scripts/cento.sh", "proreq-light", "integration-plan"]),
    ("validation-plan", ["./scripts/cento.sh", "proreq-light", "validation-plan"]),
    ("deliver", ["./scripts/cento.sh", "proreq-light", "deliver", "--no-full-check", "--json"]),
    ("evidence", ["./scripts/cento.sh", "proreq-light", "evidence"]),
]
FACTORY_SCALE_MILESTONE_SPECS = [
    {
        "id": "milestone-01",
        "title": "Coordinator kernel, cron, append-only ledgers",
        "executions": [
            ("coordinator-kernel", "Define the factory-scale coordinator kernel and run contract."),
            ("cron-deadline-lock", "Install deadline-aware cron with flock overlap prevention."),
            ("append-only-ledgers", "Prove events, calls, metrics, and spend ledgers are append-only."),
        ],
    },
    {
        "id": "milestone-02",
        "title": "ProReq-light batch runner and isolated run roots",
        "executions": [
            ("batch-runner", "Select exactly one pending ProReq-light execution per tick."),
            ("isolated-run-roots", "Keep each ProReq-light pipeline root away from the active Dev Pipeline Studio root."),
            ("call-ledger-contract", "Record ten explicit ProReq-light command calls per execution."),
        ],
    },
    {
        "id": "milestone-03",
        "title": "Patch Swarm ingestion from ProReq-light outputs",
        "executions": [
            ("proreq-output-ingestion", "Normalize ProReq-light outputs into Patch Swarm milestone handoffs."),
            ("milestone-grouping", "Bind every three ProReq-light executions to one Patch Swarm run."),
            ("candidate-receipt-linking", "Link generated candidate receipts back to their ProReq-light inputs."),
        ],
    },
    {
        "id": "milestone-04",
        "title": "Provider adapters for Codex/Claude/API candidate receipts",
        "executions": [
            ("codex-candidate-adapter", "Shape Codex Exec patch proposals into candidate_patch.v1 receipts."),
            ("claude-candidate-adapter", "Shape Claude Code proposals into the same provider-neutral receipt."),
            ("api-candidate-adapter", "Keep OpenAI API candidates behind explicit budget gates."),
        ],
    },
    {
        "id": "milestone-05",
        "title": "Deterministic validation fanout and failure taxonomy",
        "executions": [
            ("validator-fanout", "Run deterministic validation across candidate receipts."),
            ("failure-taxonomy", "Classify schema, ownership, patch-shape, duplicate, and test failures."),
            ("quarantine-ledger", "Append rejected candidates and reasons without mutating accepted evidence."),
        ],
    },
    {
        "id": "milestone-06",
        "title": "Manifest-driven Safe Integrator queue",
        "executions": [
            ("integrator-queue", "Queue selected winners for the Factory Safe Integrator."),
            ("worktree-apply-plan", "Require apply through Factory/Safe Integrator worktrees only."),
            ("rollback-receipts", "Attach rollback and validation receipts to every integration plan."),
        ],
    },
    {
        "id": "milestone-07",
        "title": "Cost/latency admission controller",
        "executions": [
            ("cost-admission", "Reject live provider fanout without explicit budget and hard cap."),
            ("latency-budget", "Track seconds per candidate, selected patch, and validation tier."),
            ("duplicate-saturation", "Stop candidate generation when duplicate clusters saturate."),
        ],
    },
    {
        "id": "milestone-08",
        "title": "Dev Pipeline / Factory operator observability",
        "executions": [
            ("operator-status", "Render log-derived status for the six-hour run."),
            ("factory-ui-state", "Expose candidate counts, provider mix, and handoffs to Dev Pipeline state."),
            ("handoff-evidence", "Keep operator handoff markdown current as a derived artifact."),
        ],
    },
    {
        "id": "milestone-09",
        "title": "Self-improvement task generator",
        "executions": [
            ("improvement-miner", "Mine failure taxonomy and metrics for self-improvement tasks."),
            ("task-generator", "Draft bounded Agent Work follow-ups for repeated blockers."),
            ("promotion-gates", "Promote only improvements with passing deterministic validation."),
        ],
    },
    {
        "id": "milestone-10",
        "title": "1,000-patch Factory pilot and scale report",
        "executions": [
            ("thousand-candidate-pilot", "Complete ten fixture Patch Swarm runs for 1,000 candidates."),
            ("scale-report", "Summarize cost, latency, validation, and integration readiness."),
            ("repeat-loop", "Feed the next self-improvement loop from the scale report."),
        ],
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def timestamp_id(prefix: str = "walk-autopilot") -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_cento_path(value: str | Path) -> Path:
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else ROOT / path


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, IsADirectoryError, OSError):
        return {}
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def dashboard_total_spend_usd(args: argparse.Namespace) -> float | None:
    explicit = optional_float(getattr(args, "dashboard_total_spend_usd", None))
    if explicit is not None:
        return explicit
    return optional_float(os.environ.get(DASHBOARD_TOTAL_ENV))


def live_api_budget_gate(args: argparse.Namespace, summary: dict[str, Any] | None = None) -> dict[str, Any]:
    dashboard_total = dashboard_total_spend_usd(args)
    hard_cap = float(getattr(args, "hard_cap_usd", 20.0))
    local_total = float((summary or {}).get("total_cost_usd") or 0.0)
    effective_total = max(local_total, dashboard_total or 0.0)
    if not bool(getattr(args, "allow_live_api", False)):
        return {
            "allowed": True,
            "status": "not-required",
            "dashboard_total_spend_usd": dashboard_total,
            "local_total_cost_usd": round(local_total, 8),
            "effective_total_cost_usd": round(effective_total, 8),
            "hard_cap_usd": hard_cap,
        }
    if dashboard_total is None:
        return {
            "allowed": False,
            "status": "blocked",
            "reason": f"--allow-live-api requires --dashboard-total-spend-usd or {DASHBOARD_TOTAL_ENV}; dashboard total is the hard-cap source of truth.",
            "dashboard_total_spend_usd": None,
            "local_total_cost_usd": round(local_total, 8),
            "effective_total_cost_usd": round(effective_total, 8),
            "hard_cap_usd": hard_cap,
        }
    if dashboard_total >= hard_cap:
        return {
            "allowed": False,
            "status": "blocked",
            "reason": f"dashboard total ${dashboard_total:.2f} is already >= hard cap ${hard_cap:.2f}",
            "dashboard_total_spend_usd": round(dashboard_total, 8),
            "local_total_cost_usd": round(local_total, 8),
            "effective_total_cost_usd": round(effective_total, 8),
            "hard_cap_usd": hard_cap,
        }
    if effective_total >= hard_cap:
        return {
            "allowed": False,
            "status": "blocked",
            "reason": f"effective spend ${effective_total:.2f} is already >= hard cap ${hard_cap:.2f}",
            "dashboard_total_spend_usd": round(dashboard_total, 8),
            "local_total_cost_usd": round(local_total, 8),
            "effective_total_cost_usd": round(effective_total, 8),
            "hard_cap_usd": hard_cap,
        }
    return {
        "allowed": True,
        "status": "allowed",
        "dashboard_total_spend_usd": round(dashboard_total, 8),
        "local_total_cost_usd": round(local_total, 8),
        "effective_total_cost_usd": round(effective_total, 8),
        "hard_cap_usd": hard_cap,
    }


def run_command(command: list[str], *, timeout: int, env: dict[str, str] | None = None) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "command": command,
            "command_text": shlex.join(command),
            "exit_code": result.returncode,
            "stdout_tail": (result.stdout or "")[-6000:],
            "stderr_tail": (result.stderr or "")[-6000:],
            "duration_seconds": round(time.monotonic() - started, 3),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "command": command,
            "command_text": shlex.join(command),
            "exit_code": 124,
            "stdout_tail": stdout[-6000:],
            "stderr_tail": (stderr + f"\ntimeout after {timeout}s")[-6000:],
            "duration_seconds": round(time.monotonic() - started, 3),
            "timed_out": True,
        }


def init_run(run_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "loops").mkdir(exist_ok=True)
    notes = run_dir / "notes.md"
    if not notes.exists():
        notes.write_text(
            "# Walk Autopilot Notes\n\n"
            "- Factory dry-run cost must remain separated from explicit Pro/image/API cost.\n"
            "- Dispatch preflight remains enabled; missing canonical story manifests should be repaired before launch attempts.\n",
            encoding="utf-8",
        )
    for filename in ("metrics.jsonl", "spend-ledger.jsonl"):
        (run_dir / filename).touch(exist_ok=True)
    config = {
        "schema_version": "cento.walk_autopilot.config.v1",
        "run_id": run_dir.name,
        "created_at": now_iso(),
        "loops": args.loops,
        "cadence_seconds": args.cadence_seconds,
        "soft_cap_usd": args.soft_cap_usd,
        "hard_cap_usd": args.hard_cap_usd,
        "live_workers": bool(args.live_workers),
        "allow_live_api": bool(args.allow_live_api),
        "max_worker_launch": args.max_worker_launch,
        "review_unblock_mode": review_unblock_mode_for_args(args),
        "patch_swarm_enabled": bool(getattr(args, "patch_swarm", False)),
        "patch_swarm_candidate_target": int(getattr(args, "patch_swarm_candidate_target", 100)),
        "budget_scope": "openai_dashboard_total_for_live_api",
        "dashboard_total_spend_usd": dashboard_total_spend_usd(args),
        "compute_policy": {"codex": 85, "claude": 15, "openai_api": 0},
    }
    write_json(run_dir / "config.json", config)
    dashboard_total = dashboard_total_spend_usd(args)
    if dashboard_total is not None:
        spend_ledger.append_record(
            run_dir / "spend-ledger.jsonl",
            spend_ledger.build_dashboard_total_record(
                run_id=run_dir.name,
                total_usd=dashboard_total,
                note="Operator-supplied OpenAI dashboard total spend snapshot for live API hard-cap gating.",
            ),
        )
    if args.dashboard_delta_usd:
        spend_ledger.append_record(
            run_dir / "spend-ledger.jsonl",
            spend_ledger.build_dashboard_delta_record(
                run_id=run_dir.name,
                delta_usd=args.dashboard_delta_usd,
                note="Operator-supplied dashboard delta for reconciliation.",
            ),
        )
    return config


def previous_loop_path(run_dir: Path, loop_number: int) -> Path | None:
    if loop_number <= 1:
        return None
    path = run_dir / "loops" / f"loop-{loop_number - 1:04d}.md"
    return path if path.exists() else None


def copied_forward_notes(run_dir: Path, loop_number: int) -> str:
    previous = previous_loop_path(run_dir, loop_number)
    notes = (run_dir / "notes.md").read_text(encoding="utf-8") if (run_dir / "notes.md").exists() else ""
    copied = ["Current notes.md:", notes.strip() or "- No prior notes."]
    if previous:
        text = previous.read_text(encoding="utf-8")
        marker = "## Recommended Next Loop"
        if marker in text:
            copied.append("Previous recommended next loop:\n" + text.split(marker, 1)[1].strip()[:2000])
    return "\n\n".join(copied)


def spend_summary(run_dir: Path) -> dict[str, Any]:
    return spend_ledger.summarize_paths([run_dir / "spend-ledger.jsonl"])


def hard_cap_reached(summary: dict[str, Any], hard_cap: float) -> bool:
    return float(summary.get("total_cost_usd") or 0.0) >= hard_cap


def validation_green(commands: list[dict[str, Any]]) -> bool:
    required = ["tools-json", "compute-policy", "factory-status", "factory-autopilot", "parallel-delivery-validate", "agent-pool-dry-run"]
    by_name = {str(item.get("name") or ""): item for item in commands}
    for name in required:
        if name not in by_name:
            return False
        exit_code = by_name[name].get("exit_code")
        if exit_code is None or int(exit_code) != 0:
            return False
    return True


def count_dirty_files() -> int:
    result = run_command(["git", "status", "--short"], timeout=20)
    if result["exit_code"] != 0:
        return -1
    return len([line for line in str(result.get("stdout_tail") or "").splitlines() if line.strip()])


def command_record(name: str, result: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, **result}


def command_json_payload(record: dict[str, Any]) -> dict[str, Any]:
    text = str(record.get("stdout_tail") or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def file_fingerprint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": rel(path)}
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = path.stat()
    return {
        "exists": True,
        "path": rel(path),
        "bytes": stat.st_size,
        "sha256": digest.hexdigest(),
        "mtime": int(stat.st_mtime),
    }


def read_crontab(crontab_file: str = "") -> str:
    if crontab_file:
        try:
            return Path(crontab_file).read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""
    try:
        result = subprocess.run(["crontab", "-l"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout


def write_crontab(text: str, crontab_file: str = "") -> None:
    if crontab_file:
        path = Path(crontab_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return
    result = subprocess.run(["crontab", "-"], input=text, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "crontab install failed")


def strip_routing_cron_block(text: str) -> str:
    if ROUTING_CRON_BEGIN not in text:
        return text
    before, rest = text.split(ROUTING_CRON_BEGIN, 1)
    if ROUTING_CRON_END not in rest:
        return before.rstrip() + "\n"
    _block, after = rest.split(ROUTING_CRON_END, 1)
    return (before.rstrip() + "\n" + after.lstrip()).strip() + ("\n" if before.strip() or after.strip() else "")


def routing_cron_block(every_hours: int) -> str:
    if every_hours < 1 or every_hours > 24:
        raise ValueError("--every-hours must be between 1 and 24")
    schedule = f"0 */{every_hours} * * *"
    inner = f"cd {shlex.quote(str(ROOT))} && ./scripts/cento.sh walk-autopilot routing run --json"
    command = (
        f"mkdir -p {shlex.quote(str(STATE_DIR))} {shlex.quote(str(ROUTING_LOG_PATH.parent))} "
        f"&& flock -n {shlex.quote(str(STATE_DIR / 'routing-native-loop.lock'))} "
        f"bash -lc {shlex.quote(inner)} >> {shlex.quote(str(ROUTING_LOG_PATH))} 2>&1"
    )
    return "\n".join([ROUTING_CRON_BEGIN, f"{schedule} {command}", ROUTING_CRON_END, ""])


def routing_cron_status(crontab_file: str = "") -> dict[str, Any]:
    text = read_crontab(crontab_file)
    installed = ROUTING_CRON_BEGIN in text and ROUTING_CRON_END in text
    schedule = ""
    if installed:
        block = text.split(ROUTING_CRON_BEGIN, 1)[1].split(ROUTING_CRON_END, 1)[0]
        for line in block.splitlines():
            line = line.strip()
            if line:
                schedule = " ".join(line.split()[:5])
                break
    return {
        "installed": installed,
        "marker_begin_count": text.count(ROUTING_CRON_BEGIN),
        "marker_end_count": text.count(ROUTING_CRON_END),
        "schedule": schedule,
        "log_path": rel(ROUTING_LOG_PATH),
        "crontab_file": crontab_file,
    }


def strip_factory_scale_cron_block(text: str) -> str:
    if FACTORY_SCALE_CRON_BEGIN not in text:
        return text
    before, rest = text.split(FACTORY_SCALE_CRON_BEGIN, 1)
    if FACTORY_SCALE_CRON_END not in rest:
        return before.rstrip() + "\n"
    _block, after = rest.split(FACTORY_SCALE_CRON_END, 1)
    return (before.rstrip() + "\n" + after.lstrip()).strip() + ("\n" if before.strip() or after.strip() else "")


def factory_scale_run_dir(run_id: str) -> Path:
    return RUN_ROOT / run_id


def resolve_artifact_path(value: Any) -> Path:
    text = str(value or "").strip()
    if not text:
        return ROOT
    path = Path(text)
    return path if path.is_absolute() else ROOT / path


def latest_factory_scale_run_dir() -> Path | None:
    if not RUN_ROOT.exists():
        return None
    runs = [path for path in RUN_ROOT.glob("factory-scale-*") if path.is_dir()]
    return max(runs, key=lambda path: (path.stat().st_mtime, path.name)) if runs else None


def factory_scale_slug(index: int) -> tuple[str, str]:
    flat: list[tuple[str, str]] = []
    for milestone in FACTORY_SCALE_MILESTONE_SPECS:
        flat.extend([(str(slug), str(title)) for slug, title in milestone["executions"]])
    if not flat:
        return f"exec-{index:03d}", "Factory scale ProReq-light execution"
    slug, title = flat[(index - 1) % len(flat)]
    if index > len(flat):
        cycle = ((index - 1) // len(flat)) + 1
        slug = f"{slug}-cycle-{cycle}"
        title = f"{title} (cycle {cycle})"
    return slug, title


def ceil_div(value: int, divisor: int) -> int:
    return (max(0, int(value)) + max(1, int(divisor)) - 1) // max(1, int(divisor))


def factory_scale_executions_for_call_target(target_proreq_calls: int) -> int:
    return max(1, ceil_div(int(target_proreq_calls), len(FACTORY_SCALE_PROREQ_COMMANDS)))


def factory_scale_call_target_for_executions(proreq_executions: int) -> int:
    return max(1, int(proreq_executions)) * len(FACTORY_SCALE_PROREQ_COMMANDS)


def factory_scale_manifest(
    proreq_executions: int,
    *,
    patch_swarm: bool = True,
    candidate_target: int = 100,
    max_parallel_agents: int = 5,
) -> dict[str, Any]:
    total = max(1, int(proreq_executions))
    candidate_target = max(1, int(candidate_target))
    max_parallel_agents = max(1, int(max_parallel_agents))
    executions: list[dict[str, Any]] = []
    for index in range(1, total + 1):
        slug, title = factory_scale_slug(index)
        milestone_index = ((index - 1) // 3) + 1
        milestone_spec = FACTORY_SCALE_MILESTONE_SPECS[(milestone_index - 1) % len(FACTORY_SCALE_MILESTONE_SPECS)]
        executions.append(
            {
                "id": f"exec-{index:03d}",
                "index": index,
                "slug": slug,
                "title": title,
                "milestone_id": f"milestone-{milestone_index:02d}",
                "milestone_title": str(milestone_spec["title"]),
                "expected_command_count": len(FACTORY_SCALE_PROREQ_COMMANDS),
            }
        )
    milestones: list[dict[str, Any]] = []
    for start in range(0, len(executions), 3):
        group = executions[start : start + 3]
        if not group:
            continue
        milestone_index = (start // 3) + 1
        spec = FACTORY_SCALE_MILESTONE_SPECS[(milestone_index - 1) % len(FACTORY_SCALE_MILESTONE_SPECS)]
        milestones.append(
            {
                "id": f"milestone-{milestone_index:02d}",
                "index": milestone_index,
                "title": str(spec["title"]),
                "proreq_execution_ids": [str(item["id"]) for item in group],
                "patch_swarm_enabled": bool(patch_swarm),
                "patch_swarm_trigger_after": str(group[-1]["id"]) if len(group) == 3 else "",
                "candidate_target": candidate_target,
                "max_parallel_agents": max_parallel_agents,
            }
        )
    return {
        "schema_version": "cento.walk_autopilot.factory_scale.manifest.v1",
        "proreq_execution_count": len(executions),
        "expected_proreq_call_count": len(executions) * len(FACTORY_SCALE_PROREQ_COMMANDS),
        "patch_swarm_milestone_count": len([item for item in milestones if item.get("patch_swarm_trigger_after")]),
        "expected_candidate_receipts": len([item for item in milestones if item.get("patch_swarm_trigger_after") and patch_swarm]) * candidate_target,
        "executions": executions,
        "milestones": milestones,
    }


def factory_scale_roadmap_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        "# Factory 1,000 Patch Swarm Roadmap",
        "",
        "This roadmap scales Cento Factory toward `1,000 parallel candidate patches -> manifest-driven integration -> mostly deterministic validation -> task done in seconds for $1-2 -> self-improve and repeat`.",
        "",
        "The six-hour final test uses local, API-safe defaults: ProReq-light command calls are ledgered in isolated run roots, Patch Swarm runs fixture/candidate-receipt e2e, and any real apply remains behind Factory/Safe Integrator worktrees.",
        "",
        "## Milestones",
        "",
    ]
    executions_by_milestone: dict[str, list[dict[str, Any]]] = {}
    for execution in as_list(manifest.get("executions")):
        if isinstance(execution, dict):
            executions_by_milestone.setdefault(str(execution.get("milestone_id") or ""), []).append(execution)
    for milestone in as_list(manifest.get("milestones")):
        if not isinstance(milestone, dict):
            continue
        lines.extend(
            [
                f"### {milestone.get('index')}. {milestone.get('title')}",
                "",
            ]
        )
        for execution in executions_by_milestone.get(str(milestone.get("id") or ""), []):
            lines.append(f"- `{execution.get('id')}` `{execution.get('slug')}`: {execution.get('title')}")
        lines.extend(
            [
                "",
                f"Patch Swarm: `{'enabled' if milestone.get('patch_swarm_enabled') else 'disabled'}` after `{milestone.get('patch_swarm_trigger_after') or 'not enough executions'}` with `100` candidate receipts.",
                "",
            ]
        )
    lines.extend(
        [
            "## Final Test Contract",
            "",
            "- Duration: six hours by default, scheduled every 12 minutes for 30 ticks.",
            "- ProReq-light: 30 executions, 10 command-call records each, 300 command-call ledger records total.",
            "- Patch Swarm: 10 fixture e2e sub-executions, 100 candidate receipts each, 1,000 candidate receipts total.",
            "- Mutation policy: no direct main-worktree apply; selected candidates hand off to Factory/Safe Integrator.",
            "- Hard stops: deadline reached, repeated cron lock conflict, two consecutive infrastructure failures, unexpected live API request, or untracked dirty growth without a matching ledger event.",
            "",
        ]
    )
    return "\n".join(lines)


def factory_scale_execution_prompt(execution: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Factory scale final test ProReq-light execution `{execution.get('id')}`.",
            f"Milestone: {execution.get('milestone_title')}",
            f"Task: {execution.get('title')}",
            "",
            "Generate planning artifacts only. Keep live OpenAI API and image dispatch disabled. Any patch apply must go through Factory/Safe Integrator worktrees.",
        ]
    )


def factory_scale_seed_proreq_root(run_dir: Path, execution: dict[str, Any]) -> Path:
    execution_dir = run_dir / "proreq-executions" / str(execution["id"])
    pipeline_root = execution_dir / "pipeline-root"
    payload = {
        "schema_version": "cento.pipeline.execution_run.v1",
        "run_id": str(execution["id"]),
        "project_id": "proreq-light-project",
        "template_id": "proreq-light-task",
        "pipeline": "proreq-light-task-proreq-light-project",
        "source": "cento-walk-autopilot-factory-scale",
        "status": "running",
        "prompt": factory_scale_execution_prompt(execution),
        "issue_subject": str(execution.get("title") or execution.get("slug") or execution["id"]),
        "triggered_by": "walk-autopilot-factory-scale",
        "inputs": [
            {"id": "operator-thoughts", "kind": "questionnaire", "source": "user", "answer": factory_scale_execution_prompt(execution)},
            {"id": "generated-cento-context", "kind": "path", "source": "auto"},
            {"id": "ui-screenshot-request", "kind": "image", "source": "auto", "automation": "request-only"},
            {"id": "pro-backend-schema", "kind": "details", "source": "auto"},
            {"id": "backend-work-handoff", "kind": "evidence", "source": "auto"},
        ],
    }
    execution_run_path = pipeline_root / "execution" / "execution_run.json"
    execution_manifest_path = execution_dir / "execution.json"
    if not execution_run_path.exists():
        write_json(execution_run_path, payload)
    if not execution_manifest_path.exists():
        write_json(execution_manifest_path, {"schema_version": "cento.factory_scale.proreq_execution.v1", **execution, "pipeline_root": rel(pipeline_root)})
    return pipeline_root


def factory_scale_append_event(run_dir: Path, event: str, payload: dict[str, Any] | None = None) -> None:
    append_jsonl(
        run_dir / "events.jsonl",
        {
            "schema_version": "cento.walk_autopilot.factory_scale.event.v1",
            "written_at": now_iso(),
            "run_id": run_dir.name,
            "event": event,
            **(payload or {}),
        },
    )


def factory_scale_append_thought(run_dir: Path, thought: str, payload: dict[str, Any] | None = None) -> None:
    append_jsonl(
        run_dir / "thoughts.jsonl",
        {
            "schema_version": "cento.walk_autopilot.factory_scale.thought.v1",
            "written_at": now_iso(),
            "run_id": run_dir.name,
            "thought": thought,
            **(payload or {}),
        },
    )


def factory_scale_init_run(run_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    patch_swarm_candidate_target = int(getattr(args, "patch_swarm_candidate_target", 100))
    patch_swarm_max_parallel_agents = int(getattr(args, "patch_swarm_max_parallel_agents", 5))
    manifest = factory_scale_manifest(
        args.proreq_executions,
        patch_swarm=bool(args.patch_swarm),
        candidate_target=patch_swarm_candidate_target,
        max_parallel_agents=patch_swarm_max_parallel_agents,
    )
    started = datetime.now(timezone.utc).replace(microsecond=0)
    deadline = started + timedelta(hours=float(args.duration_hours))
    tick_schedule = str(getattr(args, "tick_schedule", "*/12 * * * *") or "*/12 * * * *")
    batch_size = max(1, int(getattr(args, "batch_size", 1)))
    target_proreq_calls = int(getattr(args, "target_proreq_calls", manifest["expected_proreq_call_count"]) or manifest["expected_proreq_call_count"])
    max_proreq_calls = int(getattr(args, "max_proreq_calls", manifest["expected_proreq_call_count"]) or manifest["expected_proreq_call_count"])
    config = {
        "schema_version": "cento.walk_autopilot.factory_scale.config.v1",
        "run_id": run_dir.name,
        "created_at": started.isoformat().replace("+00:00", "Z"),
        "deadline_at": deadline.isoformat().replace("+00:00", "Z"),
        "duration_hours": float(args.duration_hours),
        "tick_schedule": tick_schedule,
        "batch_size": batch_size,
        "run_mode": str(getattr(args, "run_mode", "final-test") or "final-test"),
        "lock_name": str(getattr(args, "lock_name", "factory-scale-final-test.lock") or "factory-scale-final-test.lock"),
        "target_proreq_calls": target_proreq_calls,
        "max_proreq_calls": max_proreq_calls,
        "proreq_executions": int(args.proreq_executions),
        "min_proreq_calls": int(args.min_proreq_calls),
        "expected_proreq_calls": manifest["expected_proreq_call_count"],
        "patch_swarm_enabled": bool(args.patch_swarm),
        "patch_swarm_candidate_target": patch_swarm_candidate_target,
        "patch_swarm_max_parallel_agents": patch_swarm_max_parallel_agents,
        "patch_swarm_expected_runs": manifest["patch_swarm_milestone_count"] if bool(args.patch_swarm) else 0,
        "patch_swarm_expected_candidate_receipts": manifest["expected_candidate_receipts"] if bool(args.patch_swarm) else 0,
        "execute_proreq": bool(getattr(args, "execute_proreq", False)),
        "proreq_command_timeout": int(getattr(args, "proreq_command_timeout", 900)),
        "proreq_light_mode": "local-codex-exec" if bool(getattr(args, "execute_proreq", False)) else "ledger-only-api-safe",
        "hard_stop_conditions": [
            "deadline reached",
            "cron lock conflict lasting more than one tick",
            "two consecutive infrastructure failures",
            "unexpected live API request",
            "untracked dirty growth without a matching ledger event",
        ],
        "roadmap_doc": rel(FACTORY_SCALE_ROADMAP_DOC),
    }
    write_json(run_dir / "config.json", config)
    write_json(run_dir / "execution-manifest.json", manifest)
    (run_dir / "roadmap.md").write_text(factory_scale_roadmap_markdown(manifest), encoding="utf-8")
    for filename in ("events.jsonl", "thoughts.jsonl", "proreq-light-calls.jsonl", "metrics.jsonl", "spend-ledger.jsonl"):
        (run_dir / filename).touch(exist_ok=True)
    for execution in as_list(manifest.get("executions")):
        if isinstance(execution, dict):
            factory_scale_seed_proreq_root(run_dir, execution)
    for milestone in as_list(manifest.get("milestones")):
        if isinstance(milestone, dict):
            milestone_dir = run_dir / "patch-swarm" / str(milestone["id"])
            milestone_dir.mkdir(parents=True, exist_ok=True)
            write_json(milestone_dir / "milestone.json", {"schema_version": "cento.factory_scale.patch_swarm_milestone.v1", **milestone})
    factory_scale_append_event(run_dir, "run_started", {"config": rel(run_dir / "config.json"), "manifest": rel(run_dir / "execution-manifest.json")})
    factory_scale_append_thought(
        run_dir,
        "Factory scale final test initialized with log-derived status and isolated ProReq-light roots.",
        {"expected_proreq_calls": config["expected_proreq_calls"], "expected_candidate_receipts": config["patch_swarm_expected_candidate_receipts"]},
    )
    factory_scale_write_handoff(run_dir)
    return config


def factory_scale_completed_execution_ids(run_dir: Path) -> set[str]:
    calls = spend_ledger.read_jsonl(run_dir / "proreq-light-calls.jsonl")
    completed = {
        str(item.get("execution_id") or "")
        for item in calls
        if str(item.get("command_name") or "") == "evidence" and str(item.get("status") or "") in {"logged", "completed"}
    }
    return {item for item in completed if item}


def factory_scale_next_execution(run_dir: Path) -> dict[str, Any] | None:
    manifest = read_json(run_dir / "execution-manifest.json")
    completed = factory_scale_completed_execution_ids(run_dir)
    for execution in as_list(manifest.get("executions")):
        if isinstance(execution, dict) and str(execution.get("id") or "") not in completed:
            return execution
    return None


def factory_scale_consecutive_infra_failures(events: list[dict[str, Any]]) -> int:
    count = 0
    for item in reversed(events):
        event = str(item.get("event") or "")
        if event in {"proreq_execution_failed", "patch_swarm_failed", "cron_lock_conflict"}:
            count += 1
            continue
        if event in {"proreq_execution_completed", "patch_swarm_completed", "run_started", "hard_stop"}:
            break
    return count


def factory_scale_record_proreq_call(
    run_dir: Path,
    execution: dict[str, Any],
    *,
    command_index: int,
    command_name: str,
    command: list[str],
    pipeline_root: Path,
    result: dict[str, Any] | None = None,
) -> None:
    result = result or {}
    status = str(result.get("status") or "logged")
    append_jsonl(
        run_dir / "proreq-light-calls.jsonl",
        {
            "schema_version": "cento.walk_autopilot.factory_scale.proreq_light_call.v1",
            "written_at": now_iso(),
            "run_id": run_dir.name,
            "execution_id": str(execution["id"]),
            "execution_index": int(execution.get("index") or 0),
            "milestone_id": str(execution.get("milestone_id") or ""),
            "command_index": command_index,
            "command_name": command_name,
            "command": command,
            "command_text": shlex.join(command),
            "pipeline_root": rel(pipeline_root),
            "status": status,
            "exit_code": result.get("exit_code", 0),
            "duration_seconds": result.get("duration_seconds", 0),
            "stdout_tail": str(result.get("stdout_tail") or "")[-1000:],
            "stderr_tail": str(result.get("stderr_tail") or "")[-1000:],
            "mode": result.get("mode", "ledger-only"),
        },
    )


def factory_scale_run_proreq_execution(run_dir: Path, execution: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    pipeline_root = factory_scale_seed_proreq_root(run_dir, execution)
    execute = bool(config.get("execute_proreq"))
    failures: list[str] = []
    for command_index, (command_name, command) in enumerate(FACTORY_SCALE_PROREQ_COMMANDS, start=1):
        if execute:
            env = os.environ.copy()
            env["CENTO_DEV_PIPELINE_STUDIO_ROOT"] = str(pipeline_root)
            env["CENTO_WALK_AUTOPILOT_RUN_DIR"] = str(run_dir)
            env.setdefault("CENTO_HARD_PROREQ_DISABLE_GPT_IMAGE_2", "1")
            result = run_command(command, timeout=int(config.get("proreq_command_timeout") or 900), env=env)
            result["status"] = "completed" if int(result.get("exit_code") or 0) == 0 else "failed"
            result["mode"] = "local-codex-exec"
        else:
            result = {
                "status": "logged",
                "exit_code": 0,
                "duration_seconds": 0,
                "stdout_tail": "",
                "stderr_tail": "",
                "mode": "ledger-only",
            }
            receipt_path = run_dir / "proreq-executions" / str(execution["id"]) / f"call-{command_index:02d}-{command_name}.json"
            write_json(
                receipt_path,
                {
                    "schema_version": "cento.factory_scale.proreq_light_call_receipt.v1",
                    "run_id": run_dir.name,
                    "execution_id": str(execution["id"]),
                    "command_index": command_index,
                    "command_name": command_name,
                    "command": command,
                    "status": "logged",
                    "pipeline_root": rel(pipeline_root),
                    "api_safe": True,
                },
            )
        factory_scale_record_proreq_call(
            run_dir,
            execution,
            command_index=command_index,
            command_name=command_name,
            command=command,
            pipeline_root=pipeline_root,
            result=result,
        )
        if int(result.get("exit_code") or 0) != 0:
            failures.append(f"{command_name}: exit {result.get('exit_code')}")
            break
    status = "completed" if not failures else "failed"
    event = "proreq_execution_completed" if status == "completed" else "proreq_execution_failed"
    factory_scale_append_event(
        run_dir,
        event,
        {
            "execution_id": str(execution["id"]),
            "execution_index": int(execution.get("index") or 0),
            "milestone_id": str(execution.get("milestone_id") or ""),
            "status": status,
            "call_count": len(FACTORY_SCALE_PROREQ_COMMANDS) if not failures else len(spend_ledger.read_jsonl(run_dir / "proreq-light-calls.jsonl")),
            "failures": failures,
            "pipeline_root": rel(pipeline_root),
        },
    )
    return {"status": status, "failures": failures, "pipeline_root": rel(pipeline_root)}


def factory_scale_milestone_for_execution(run_dir: Path, execution: dict[str, Any]) -> dict[str, Any]:
    manifest = read_json(run_dir / "execution-manifest.json")
    milestone_id = str(execution.get("milestone_id") or "")
    for milestone in as_list(manifest.get("milestones")):
        if isinstance(milestone, dict) and str(milestone.get("id") or "") == milestone_id:
            return milestone
    return {}


def factory_scale_patch_swarm_already_ran(run_dir: Path, milestone_id: str) -> bool:
    for item in spend_ledger.read_jsonl(run_dir / "events.jsonl"):
        if str(item.get("event") or "") == "patch_swarm_completed" and str(item.get("milestone_id") or "") == milestone_id:
            return True
    return False


def factory_scale_run_patch_swarm_milestone(run_dir: Path, milestone: dict[str, Any]) -> dict[str, Any]:
    milestone_id = str(milestone.get("id") or "")
    milestone_dir = run_dir / "patch-swarm" / milestone_id
    milestone_dir.mkdir(parents=True, exist_ok=True)
    swarm_run_id = f"{run_dir.name}-{milestone_id}"
    command = [
        "./scripts/cento.sh",
        "parallel-delivery",
        "patch-swarm",
        "e2e",
        "--run-id",
        swarm_run_id,
        "--candidate-target",
        str(int(milestone.get("candidate_target") or 100)),
        "--max-parallel-agents",
        str(int(milestone.get("max_parallel_agents") or 5)),
        "--fixture",
        "--json",
    ]
    result = run_command(command, timeout=360)
    record = command_record("factory-scale-patch-swarm", result)
    write_json(milestone_dir / "command_result.json", record)
    try:
        payload = json.loads(str(result.get("stdout_tail") or "{}"))
    except json.JSONDecodeError:
        payload = {}
    status = "completed" if int(result.get("exit_code") or 0) == 0 and payload.get("status") == "completed" else "failed"
    summary = {
        "schema_version": "cento.factory_scale.patch_swarm_milestone_summary.v1",
        "run_id": run_dir.name,
        "milestone_id": milestone_id,
        "status": status,
        "parallel_delivery_run_id": swarm_run_id,
        "parallel_delivery_run": payload.get("run_dir") or f"workspace/runs/parallel-delivery/patch-swarm/{swarm_run_id}",
        "proreq_execution_ids": milestone.get("proreq_execution_ids", []),
        "candidate_count": int(payload.get("candidate_count") or 0),
        "selected_count": int(payload.get("selected_count") or 0),
        "estimated_cost_usd": float(payload.get("estimated_cost_usd") or 0.0),
        "safe_integrator_handoff": payload.get("safe_integrator_handoff", ""),
        "validation": payload.get("validation", "unknown"),
        "decision_report": payload.get("decision_report", ""),
    }
    write_json(milestone_dir / "summary.json", summary)
    (milestone_dir / "handoff.md").write_text(
        "\n".join(
            [
                f"# Factory Scale {milestone_id} Patch Swarm Handoff",
                "",
                f"- Status: `{summary['status']}`",
                f"- ProReq-light inputs: `{', '.join([str(item) for item in summary['proreq_execution_ids']])}`",
                f"- Candidate receipts: `{summary['candidate_count']}`",
                f"- Selected candidates: `{summary['selected_count']}`",
                f"- Parallel delivery run: `{summary['parallel_delivery_run']}`",
                f"- Safe Integrator handoff: `{summary['safe_integrator_handoff'] or '-'}`",
                "",
                "Mutation policy: selected patches remain candidate receipts until Factory/Safe Integrator worktrees validate and apply them.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    factory_scale_append_event(
        run_dir,
        "patch_swarm_completed" if status == "completed" else "patch_swarm_failed",
        {
            "milestone_id": milestone_id,
            "status": status,
            "candidate_count": summary["candidate_count"],
            "selected_count": summary["selected_count"],
            "parallel_delivery_run": summary["parallel_delivery_run"],
            "safe_integrator_handoff": summary["safe_integrator_handoff"],
        },
    )
    append_jsonl(
        run_dir / "spend-ledger.jsonl",
        {
            "schema_version": "cento.factory_scale.spend_ledger.v1",
            "written_at": now_iso(),
            "run_id": run_dir.name,
            "lane": "patch-swarm",
            "category": "fixture-estimate",
            "provider": "local-fixture",
            "billable": False,
            "cost_usd": 0.0,
            "estimated_cost_usd": summary["estimated_cost_usd"],
            "candidate_count": summary["candidate_count"],
            "milestone_id": milestone_id,
            "artifact": rel(milestone_dir / "summary.json"),
            "note": "Patch Swarm fixture e2e writes candidate receipts and Safe Integrator handoff; no live API spend.",
        },
    )
    return summary


def factory_scale_status_payload(run_id: str = "", crontab_file: str = "") -> dict[str, Any]:
    run_dir = factory_scale_run_dir(run_id) if run_id else latest_factory_scale_run_dir()
    if not run_dir or not run_dir.exists():
        return {"schema_version": "cento.walk_autopilot.factory_scale.status.v1", "status": "unknown", "run_id": run_id, "run_dir": ""}
    config = read_json(run_dir / "config.json")
    manifest = read_json(run_dir / "execution-manifest.json")
    events = spend_ledger.read_jsonl(run_dir / "events.jsonl")
    calls = spend_ledger.read_jsonl(run_dir / "proreq-light-calls.jsonl")
    metrics_records = spend_ledger.read_jsonl(run_dir / "metrics.jsonl")
    completed = factory_scale_completed_execution_ids(run_dir)
    patch_events = [item for item in events if str(item.get("event") or "") == "patch_swarm_completed"]
    hard_stops = [item for item in events if str(item.get("event") or "") == "hard_stop"]
    deadline = parse_iso_datetime(config.get("deadline_at"))
    deadline_reached = bool(deadline and datetime.now(timezone.utc) >= deadline)
    expected_execs = int(config.get("proreq_executions") or manifest.get("proreq_execution_count") or 0)
    expected_calls = int(config.get("expected_proreq_calls") or manifest.get("expected_proreq_call_count") or 0)
    expected_patch_runs = int(config.get("patch_swarm_expected_runs") or 0)
    candidate_receipts = sum(int(item.get("candidate_count") or 0) for item in patch_events)
    if hard_stops:
        status = "stopped"
    elif expected_execs and len(completed) >= expected_execs and len(patch_events) >= expected_patch_runs:
        status = "completed"
    elif deadline_reached:
        status = "deadline_reached"
    elif events:
        status = "running"
    else:
        status = "planned"
    next_execution = factory_scale_next_execution(run_dir)
    cron = factory_scale_cron_status(crontab_file)
    return {
        "schema_version": "cento.walk_autopilot.factory_scale.status.v1",
        "checked_at": now_iso(),
        "status": status,
        "run_id": run_dir.name,
        "run_dir": rel(run_dir),
        "run_mode": str(config.get("run_mode") or "final-test"),
        "deadline_at": config.get("deadline_at"),
        "deadline_reached": deadline_reached,
        "cron": cron,
        "batch_size": int(config.get("batch_size") or 1),
        "target_proreq_calls": int(config.get("target_proreq_calls") or expected_calls),
        "max_proreq_calls": int(config.get("max_proreq_calls") or expected_calls),
        "proreq_execution_count": expected_execs,
        "completed_proreq_executions": len(completed),
        "pending_proreq_executions": max(0, expected_execs - len(completed)),
        "remaining_proreq_calls": max(0, expected_calls - len(calls)),
        "next_execution_id": str(next_execution.get("id") or "") if next_execution else "",
        "proreq_call_count": len(calls),
        "expected_proreq_call_count": expected_calls,
        "min_proreq_calls": int(config.get("min_proreq_calls") or 0),
        "min_proreq_calls_met": len(calls) >= int(config.get("min_proreq_calls") or 0),
        "patch_swarm_runs": len(patch_events),
        "expected_patch_swarm_runs": expected_patch_runs,
        "candidate_patch_receipts": candidate_receipts,
        "expected_candidate_patch_receipts": int(config.get("patch_swarm_expected_candidate_receipts") or 0),
        "hard_stop_count": len(hard_stops),
        "metrics_records": len(metrics_records),
        "handoff": rel(run_dir / "handoff.md"),
    }


def factory_scale_write_handoff(run_dir: Path) -> None:
    status = factory_scale_status_payload(run_dir.name)
    lines = [
        "# Factory Scale Final Test Handoff",
        "",
        f"- Run: `{run_dir.name}`",
        f"- Mode: `{status.get('run_mode')}`",
        f"- Status: `{status.get('status')}`",
        f"- Deadline: `{status.get('deadline_at')}`",
        f"- Batch size: `{status.get('batch_size')}`",
        f"- ProReq-light executions: `{status.get('completed_proreq_executions')}/{status.get('proreq_execution_count')}`",
        f"- ProReq-light command calls: `{status.get('proreq_call_count')}/{status.get('expected_proreq_call_count')}`",
        f"- Remaining ProReq-light command calls: `{status.get('remaining_proreq_calls')}`",
        f"- Patch Swarm runs: `{status.get('patch_swarm_runs')}/{status.get('expected_patch_swarm_runs')}`",
        f"- Candidate patch receipts: `{status.get('candidate_patch_receipts')}/{status.get('expected_candidate_patch_receipts')}`",
        f"- Next execution: `{status.get('next_execution_id') or '-'}`",
        "",
        "## Resume",
        "",
        f"`./scripts/cento.sh walk-autopilot factory-scale tick --run-id {run_dir.name} --batch-size {status.get('batch_size') or 1} --json`",
        "",
        "## Status",
        "",
        f"`./scripts/cento.sh walk-autopilot factory-scale status --run-id {run_dir.name} --json`",
        "",
        "## Mutation Policy",
        "",
        "Patch candidates remain receipts until Factory/Safe Integrator worktrees validate and apply them. The factory-scale coordinator does not apply patches to the main worktree.",
        "",
    ]
    (run_dir / "handoff.md").write_text("\n".join(lines), encoding="utf-8")


def factory_scale_append_metrics(run_dir: Path, payload: dict[str, Any]) -> None:
    status = factory_scale_status_payload(run_dir.name)
    append_jsonl(
        run_dir / "metrics.jsonl",
        {
            "schema_version": "cento.walk_autopilot.factory_scale.metrics.v1",
            "written_at": now_iso(),
            "run_id": run_dir.name,
            "status": status.get("status"),
            "completed_proreq_executions": status.get("completed_proreq_executions"),
            "proreq_call_count": status.get("proreq_call_count"),
            "patch_swarm_runs": status.get("patch_swarm_runs"),
            "candidate_patch_receipts": status.get("candidate_patch_receipts"),
            **payload,
        },
    )


def factory_scale_candidate_matrix(run_dir: Path, *, promotion_limit: int = 25) -> dict[str, Any]:
    status = factory_scale_status_payload(run_dir.name)
    manifest = read_json(run_dir / "execution-manifest.json")
    candidates: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    milestones: list[dict[str, Any]] = []
    provider_counts: Counter[str] = Counter()
    selected_provider_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    touched_path_counts: Counter[str] = Counter()
    error_counts: Counter[str] = Counter()
    missing_artifacts: list[str] = []
    total_estimated_cost = 0.0

    for milestone in as_list(manifest.get("milestones")):
        if not isinstance(milestone, dict):
            continue
        milestone_id = str(milestone.get("id") or "")
        summary = read_json(run_dir / "patch-swarm" / milestone_id / "summary.json")
        parallel_run = resolve_artifact_path(summary.get("parallel_delivery_run")) if summary else Path("")
        candidate_index = read_json(parallel_run / "candidate_index.json") if summary else {}
        ranking = read_json(parallel_run / "ranking.json") if summary else {}
        handoff_path = resolve_artifact_path(summary.get("safe_integrator_handoff")) if summary else Path("")
        handoff = read_json(handoff_path) if summary else {}
        milestone_candidates = [item for item in as_list(candidate_index.get("candidates")) if isinstance(item, dict)]
        handoff_selected = [item for item in as_list(handoff.get("selected_candidates")) if isinstance(item, dict)]
        selected_ids = {str(item.get("candidate_id") or "") for item in handoff_selected}
        candidate_lookup: dict[str, dict[str, Any]] = {}
        if not summary:
            missing_artifacts.append(rel(run_dir / "patch-swarm" / milestone_id / "summary.json"))
        if summary and not candidate_index:
            missing_artifacts.append(rel(parallel_run / "candidate_index.json"))
        if summary and not handoff:
            missing_artifacts.append(rel(handoff_path))
        for item in milestone_candidates:
            candidate_id = str(item.get("id") or "")
            provider = str(item.get("provider") or "unknown")
            state = str(item.get("status") or "unknown")
            patch = as_dict(item.get("patch"))
            touched = [str(path) for path in as_list(item.get("touched_paths"))]
            row = {
                "milestone_id": milestone_id,
                "milestone_title": str(milestone.get("title") or ""),
                "parallel_delivery_run": rel(parallel_run),
                "candidate_id": candidate_id,
                "execution_id": str(item.get("execution_id") or ""),
                "task_id": str(item.get("task_id") or ""),
                "provider": provider,
                "status": state,
                "score": float(item.get("score") or 0.0),
                "cost_usd_estimate": float(item.get("cost_usd_estimate") or 0.0),
                "duration_ms_estimate": int(item.get("duration_ms_estimate") or 0),
                "touched_paths": touched,
                "patch_file": str(patch.get("patch_file") or ""),
                "patch_sha256": str(patch.get("sha256") or ""),
                "candidate_receipt": str(item.get("candidate_receipt") or ""),
                "validation_receipt": str(item.get("validation_receipt") or ""),
                "selected": candidate_id in selected_ids,
                "errors": [str(error) for error in as_list(item.get("errors"))],
            }
            candidates.append(row)
            candidate_lookup[candidate_id] = row
            provider_counts[provider] += 1
            status_counts[state] += 1
            total_estimated_cost += row["cost_usd_estimate"]
            for path in touched:
                touched_path_counts[path] += 1
            for error in row["errors"]:
                error_counts[error or "unknown"] += 1
        for item in handoff_selected:
            provider = str(item.get("provider") or "unknown")
            candidate_id = str(item.get("candidate_id") or "")
            detail = candidate_lookup.get(candidate_id, {})
            selected_row = {
                "milestone_id": milestone_id,
                "milestone_title": str(milestone.get("title") or ""),
                "parallel_delivery_run": rel(parallel_run),
                "handoff": rel(handoff_path),
                "candidate_id": candidate_id,
                "execution_id": str(item.get("execution_id") or ""),
                "provider": provider,
                "score": float(item.get("score") or 0.0),
                "cost_usd_estimate": float(detail.get("cost_usd_estimate") or 0.0),
                "duration_ms_estimate": int(detail.get("duration_ms_estimate") or 0),
                "patch_file": str(item.get("patch_file") or ""),
                "candidate_receipt": str(detail.get("candidate_receipt") or ""),
                "validation_receipt": str(detail.get("validation_receipt") or ""),
                "touched_paths": [str(path) for path in as_list(item.get("touched_paths"))],
            }
            selected.append(selected_row)
            selected_provider_counts[provider] += 1
        milestones.append(
            {
                "milestone_id": milestone_id,
                "title": str(milestone.get("title") or ""),
                "status": str(summary.get("status") or "missing"),
                "parallel_delivery_run": rel(parallel_run) if summary else "",
                "candidate_count": len(milestone_candidates),
                "selected_count": len(handoff_selected),
                "top_candidate_count": len(as_list(ranking.get("top_candidates"))),
                "safe_integrator_handoff": rel(handoff_path) if summary else "",
                "proreq_execution_ids": [str(item) for item in as_list(milestone.get("proreq_execution_ids"))],
            }
        )

    selected.sort(key=lambda item: (-float(item.get("score") or 0.0), float(item.get("cost_usd_estimate") or 0.0), str(item.get("milestone_id") or ""), str(item.get("candidate_id") or "")))
    promotion_candidates = selected[: max(0, int(promotion_limit))]
    return {
        "schema_version": "cento.walk_autopilot.factory_scale.candidate_matrix.v1",
        "written_at": now_iso(),
        "run_id": run_dir.name,
        "run_dir": rel(run_dir),
        "source_status": status,
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "promotion_limit": int(promotion_limit),
        "promotion_candidate_count": len(promotion_candidates),
        "estimated_provider_cost_usd": round(total_estimated_cost, 6),
        "provider_counts": dict(sorted(provider_counts.items())),
        "selected_provider_counts": dict(sorted(selected_provider_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "top_touched_paths": [{"path": path, "count": count} for path, count in touched_path_counts.most_common(20)],
        "validation_taxonomy": {
            "status_counts": dict(sorted(status_counts.items())),
            "error_counts": dict(sorted(error_counts.items())),
            "missing_artifacts": missing_artifacts,
        },
        "milestones": milestones,
        "selected_candidates": selected,
        "promotion_candidates": promotion_candidates,
        "candidates": candidates,
    }


def factory_scale_promotion_plan(matrix: dict[str, Any], live_api_guard: dict[str, Any]) -> dict[str, Any]:
    plans: list[dict[str, Any]] = []
    for index, candidate in enumerate(as_list(matrix.get("promotion_candidates")), start=1):
        if not isinstance(candidate, dict):
            continue
        parallel_run = str(candidate.get("parallel_delivery_run") or "")
        plans.append(
            {
                "sequence": index,
                "milestone_id": str(candidate.get("milestone_id") or ""),
                "candidate_id": str(candidate.get("candidate_id") or ""),
                "execution_id": str(candidate.get("execution_id") or ""),
                "provider": str(candidate.get("provider") or ""),
                "score": float(candidate.get("score") or 0.0),
                "cost_usd_estimate": float(candidate.get("cost_usd_estimate") or 0.0),
                "duration_ms_estimate": int(candidate.get("duration_ms_estimate") or 0),
                "patch_file": str(candidate.get("patch_file") or ""),
                "candidate_receipt": str(candidate.get("candidate_receipt") or ""),
                "validation_receipt": str(candidate.get("validation_receipt") or ""),
                "touched_paths": [str(path) for path in as_list(candidate.get("touched_paths"))],
                "safe_integrator_handoff": str(candidate.get("handoff") or ""),
                "dry_run_command": f"./scripts/cento.sh parallel-delivery patch-swarm integrate {Path(parallel_run).name} --dry-run --json" if parallel_run else "",
                "validation_command": f"./scripts/cento.sh parallel-delivery patch-swarm validate {Path(parallel_run).name} --json" if parallel_run else "",
            }
        )
    return {
        "schema_version": "cento.walk_autopilot.factory_scale.safe_integrator_promotion_plan.v1",
        "written_at": now_iso(),
        "run_id": str(matrix.get("run_id") or ""),
        "status": "ready" if plans else "blocked",
        "apply": False,
        "dry_run": True,
        "factory_safe_integrator_required": True,
        "promotion_limit": int(matrix.get("promotion_limit") or 0),
        "candidate_receipts_considered": int(matrix.get("candidate_count") or 0),
        "selected_candidates_available": int(matrix.get("selected_count") or 0),
        "promotion_plan_count": len(plans),
        "live_api_guard": {
            "live_api_requested": bool(live_api_guard.get("live_api_requested")),
            "live_api_enabled": bool(live_api_guard.get("live_api_enabled")),
            "fail_closed": bool(live_api_guard.get("fail_closed")),
            "blocked_reasons": as_list(live_api_guard.get("blocked_reasons")),
        },
        "plans": plans,
        "next_gate": "Factory/Safe Integrator worktree apply plan and deterministic validation; no direct main-worktree mutation.",
    }


def factory_scale_safe_id(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value)).strip("-") or "factory-scale"


def factory_scale_normalize_promotion_candidate(run_dir: Path, item: dict[str, Any], sequence: int) -> dict[str, Any]:
    import parallel_delivery

    milestone_id = str(item.get("milestone_id") or "milestone")
    source_execution_id = str(item.get("execution_id") or f"exec-{sequence:03d}")
    candidate_id = str(item.get("candidate_id") or f"factory-scale-candidate-{sequence:04d}")
    task_id = factory_scale_safe_id(f"{milestone_id}-{source_execution_id}-{sequence:04d}")
    touched_paths = [str(path) for path in as_list(item.get("touched_paths")) if str(path)]
    patch_file = str(item.get("patch_file") or "")
    patch_path = resolve_cento_path(patch_file) if patch_file else Path("")
    patch_sha = file_fingerprint(patch_path).get("sha256", "") if patch_file else ""
    return {
        "schema_version": parallel_delivery.SCHEMA_PATCH_SWARM_CANDIDATE,
        "id": candidate_id,
        "run_id": run_dir.name,
        "execution_id": task_id,
        "source_execution_id": source_execution_id,
        "task_id": task_id,
        "provider": str(item.get("provider") or "codex-exec"),
        "status": "validated",
        "score": float(item.get("score") or 0.0),
        "cost_usd_estimate": float(item.get("cost_usd_estimate") or 0.0),
        "duration_ms_estimate": int(item.get("duration_ms_estimate") or 0),
        "touched_paths": touched_paths,
        "owned_paths": touched_paths,
        "patch": {
            "format": "unified_diff",
            "patch_file": patch_file,
            "sha256": str(item.get("patch_sha256") or patch_sha or ""),
        },
        "candidate_receipt": str(item.get("candidate_receipt") or ""),
        "validation_receipt": str(item.get("validation_receipt") or ""),
        "errors": [],
        "promotion_source": {
            "schema_version": "cento.walk_autopilot.factory_scale.promotion_source.v1",
            "run_id": run_dir.name,
            "milestone_id": milestone_id,
            "source_execution_id": source_execution_id,
            "sequence": sequence,
            "safe_integrator_handoff": str(item.get("safe_integrator_handoff") or ""),
        },
    }


def factory_scale_select_promotion_candidates(
    run_dir: Path,
    promotion_plan: dict[str, Any],
    *,
    limit: int = 0,
    exclusive_paths: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for sequence, item in enumerate(as_list(promotion_plan.get("plans")), start=1):
        if not isinstance(item, dict):
            skipped.append({"sequence": sequence, "reason": "plan item is not an object"})
            continue
        candidate = factory_scale_normalize_promotion_candidate(run_dir, item, sequence)
        touched_paths = set(candidate.get("touched_paths") or [])
        if exclusive_paths and seen_paths.intersection(touched_paths):
            skipped.append(
                {
                    "sequence": sequence,
                    "candidate_id": candidate.get("id"),
                    "reason": "overlaps previously selected touched path",
                    "overlap": sorted(seen_paths.intersection(touched_paths)),
                }
            )
            continue
        selected.append(candidate)
        seen_paths.update(touched_paths)
        if limit and len(selected) >= limit:
            break
    return selected, skipped


def factory_scale_promote_to_factory(
    run_dir: Path,
    *,
    promotion_plan_path: Path | None = None,
    factory_run: str = "",
    apply: bool = False,
    validate_each: bool = False,
    branch: str = "",
    worktree: str = "",
    limit: int = 0,
    exclusive_paths: bool = True,
) -> dict[str, Any]:
    import parallel_delivery

    plan_path = promotion_plan_path or run_dir / FACTORY_SCALE_ADVANCE_DIRNAME / "safe-integrator-promotion-plan.json"
    promotion_plan = read_json(plan_path)
    if not promotion_plan:
        return {
            "schema_version": "cento.walk_autopilot.factory_scale.factory_promotion.v1",
            "status": "blocked",
            "run_id": run_dir.name,
            "reason": "promotion plan not found",
            "promotion_plan": rel(plan_path),
        }
    selected, skipped = factory_scale_select_promotion_candidates(
        run_dir,
        promotion_plan,
        limit=limit,
        exclusive_paths=exclusive_paths,
    )
    if not selected:
        return {
            "schema_version": "cento.walk_autopilot.factory_scale.factory_promotion.v1",
            "status": "blocked",
            "run_id": run_dir.name,
            "reason": "no promotion candidates selected",
            "promotion_plan": rel(plan_path),
            "skipped": skipped,
        }
    factory_run_value = factory_run or f"workspace/runs/factory/factory-scale-promotion-{run_dir.name}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    promotion = parallel_delivery.promote_patch_swarm_to_factory(
        run_dir,
        selected,
        factory_run=factory_run_value,
        apply=apply,
        validate_each=validate_each,
        branch=branch,
        worktree=worktree,
        limit=limit,
    )
    payload = {
        "schema_version": "cento.walk_autopilot.factory_scale.factory_promotion.v1",
        "status": promotion.get("status", "unknown"),
        "run_id": run_dir.name,
        "run_dir": rel(run_dir),
        "promotion_plan": rel(plan_path),
        "factory_promotion": promotion,
        "factory_run_dir": promotion.get("factory_run_dir", ""),
        "selected_count": len(selected),
        "skipped_count": len(skipped),
        "exclusive_paths": bool(exclusive_paths),
        "apply": bool(apply),
        "selected_candidate_ids": [str(item.get("id") or "") for item in selected],
        "skipped": skipped[:50],
        "written_at": now_iso(),
    }
    promotion_receipt = run_dir / FACTORY_SCALE_ADVANCE_DIRNAME / f"factory-promotion-{factory_scale_safe_id(str(Path(factory_run_value).name))}.json"
    write_json(promotion_receipt, payload)
    factory_scale_append_event(
        run_dir,
        "factory_promotion_completed",
        {
            "status": payload.get("status"),
            "factory_run_dir": payload.get("factory_run_dir"),
            "selected_count": len(selected),
            "skipped_count": len(skipped),
            "apply": bool(apply),
        },
    )
    factory_scale_append_metrics(
        run_dir,
        {
            "tick_result": "factory_promotion_completed",
            "factory_promotion_status": payload.get("status"),
            "factory_promotion_selected_count": len(selected),
            "factory_promotion_skipped_count": len(skipped),
            "factory_promotion_apply": bool(apply),
        },
    )
    payload["receipt"] = rel(promotion_receipt)
    return payload


def write_factory_scale_advance_markdown(
    report_path: Path,
    *,
    run_dir: Path,
    preflight: dict[str, Any],
    live_api_guard: dict[str, Any],
    matrix: dict[str, Any],
    promotion_plan: dict[str, Any],
) -> None:
    lines = [
        "# Factory Scale Advance Report",
        "",
        f"- Source run: `{run_dir.name}`",
        f"- Source status: `{as_dict(matrix.get('source_status')).get('status', 'unknown')}`",
        f"- No-overlap decision: `{preflight.get('decision')}`",
        f"- Active overlap detected: `{bool(preflight.get('active'))}`",
        f"- Live OpenAI/API enabled: `{bool(live_api_guard.get('live_api_enabled'))}`",
        f"- Candidate receipts indexed: `{matrix.get('candidate_count')}`",
        f"- Selected candidates: `{matrix.get('selected_count')}`",
        f"- Promotion plan count: `{promotion_plan.get('promotion_plan_count')}`",
        f"- Estimated provider cost from fixture receipts: `${float(matrix.get('estimated_provider_cost_usd') or 0.0):.6f}`",
        "",
        "## Artifacts",
        "",
        f"- Candidate matrix: `{rel(report_path.parent / 'candidate-matrix.json')}`",
        f"- Promotion plan: `{rel(report_path.parent / 'safe-integrator-promotion-plan.json')}`",
        f"- Live API guard: `{rel(report_path.parent / 'live-api-guard.json')}`",
        f"- No-overlap preflight: `{rel(report_path.parent / 'no-overlap-preflight.json')}`",
        "",
        "## Provider Counts",
        "",
        markdown_list([f"{provider}: {count}" for provider, count in as_dict(matrix.get("provider_counts")).items()]),
        "",
        "## Selected Provider Counts",
        "",
        markdown_list([f"{provider}: {count}" for provider, count in as_dict(matrix.get("selected_provider_counts")).items()]),
        "",
        "## Validation Taxonomy",
        "",
        "```json",
        json.dumps(matrix.get("validation_taxonomy", {}), indent=2, sort_keys=True),
        "```",
        "",
        "## Promotion Gate",
        "",
        "Selected candidates remain receipts until Factory/Safe Integrator worktrees validate and apply them. This report does not mutate the main worktree.",
        "",
        "## Next Commands",
        "",
        f"`./scripts/cento.sh walk-autopilot factory-scale advance --run-id {run_dir.name} --json`",
        "",
        "`make check`",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def factory_scale_write_advance_artifacts(
    run_dir: Path,
    *,
    preflight: dict[str, Any],
    live_api_guard: dict[str, Any],
    promotion_limit: int,
) -> dict[str, Any]:
    advance_dir = run_dir / FACTORY_SCALE_ADVANCE_DIRNAME
    advance_dir.mkdir(parents=True, exist_ok=True)
    matrix = factory_scale_candidate_matrix(run_dir, promotion_limit=promotion_limit)
    promotion_plan = factory_scale_promotion_plan(matrix, live_api_guard)
    preflight_path = advance_dir / "no-overlap-preflight.json"
    live_guard_path = advance_dir / "live-api-guard.json"
    matrix_path = advance_dir / "candidate-matrix.json"
    promotion_path = advance_dir / "safe-integrator-promotion-plan.json"
    report_path = advance_dir / "morning-report.md"
    write_json(preflight_path, preflight)
    write_json(live_guard_path, live_api_guard)
    write_json(matrix_path, matrix)
    write_json(promotion_path, promotion_plan)
    write_factory_scale_advance_markdown(
        report_path,
        run_dir=run_dir,
        preflight=preflight,
        live_api_guard=live_api_guard,
        matrix=matrix,
        promotion_plan=promotion_plan,
    )
    spend_ledger.append_record(
        run_dir / "spend-ledger.jsonl",
        spend_ledger.build_factory_record(
            run_id=run_dir.name,
            status="completed",
            cost_usd=0.0,
            artifact=rel(report_path),
            note="Factory scale advance indexed completed Patch Swarm receipts and wrote Safe Integrator promotion plans without live API spend.",
        ),
        dedupe=False,
    )
    factory_scale_append_event(
        run_dir,
        "advance_completed",
        {
            "advance_dir": rel(advance_dir),
            "candidate_count": matrix.get("candidate_count"),
            "selected_count": matrix.get("selected_count"),
            "promotion_plan_count": promotion_plan.get("promotion_plan_count"),
            "live_api_enabled": bool(live_api_guard.get("live_api_enabled")),
        },
    )
    factory_scale_append_metrics(
        run_dir,
        {
            "tick_result": "advance_completed",
            "advance_candidate_count": matrix.get("candidate_count"),
            "advance_selected_count": matrix.get("selected_count"),
            "advance_promotion_plan_count": promotion_plan.get("promotion_plan_count"),
            "live_api_enabled": bool(live_api_guard.get("live_api_enabled")),
        },
    )
    return {
        "schema_version": "cento.walk_autopilot.factory_scale.advance.v1",
        "status": "completed",
        "run_id": run_dir.name,
        "run_dir": rel(run_dir),
        "advance_dir": rel(advance_dir),
        "candidate_matrix": rel(matrix_path),
        "promotion_plan": rel(promotion_path),
        "morning_report": rel(report_path),
        "no_overlap_preflight": rel(preflight_path),
        "live_api_guard": rel(live_guard_path),
        "candidate_count": matrix.get("candidate_count"),
        "selected_count": matrix.get("selected_count"),
        "promotion_plan_count": promotion_plan.get("promotion_plan_count"),
        "live_api_enabled": bool(live_api_guard.get("live_api_enabled")),
        "live_api_blocked_reasons": live_api_guard.get("blocked_reasons", []),
    }


def factory_scale_cron_block(run_id: str, duration_hours: float | None = None) -> str:
    run_dir = factory_scale_run_dir(run_id)
    config = read_json(run_dir / "config.json")
    deadline = parse_iso_datetime(config.get("deadline_at"))
    if deadline is None:
        hours = float(duration_hours if duration_hours is not None else config.get("duration_hours") or 6.0)
        deadline = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=hours)
    deadline_epoch = int(deadline.timestamp())
    schedule = str(config.get("tick_schedule") or "*/12 * * * *")
    batch_size = max(1, int(config.get("batch_size") or 1))
    lock = STATE_DIR / str(config.get("lock_name") or "factory-scale-final-test.lock")
    tick_args = f"--run-id {shlex.quote(run_id)} --batch-size {batch_size} --json"
    inner = (
        f"if [ \"$(date -u +%s)\" -le {deadline_epoch} ]; then "
        f"cd {shlex.quote(str(ROOT))} && ./scripts/cento.sh walk-autopilot factory-scale tick {tick_args}; "
        f"else echo 'factory-scale deadline reached for {run_id}'; fi"
    )
    conflict = (
        f"cd {shlex.quote(str(ROOT))} && ./scripts/cento.sh walk-autopilot factory-scale tick "
        f"--run-id {shlex.quote(run_id)} --cron-lock-conflict --json"
    )
    command = (
        f"mkdir -p {shlex.quote(str(STATE_DIR))} {shlex.quote(str(FACTORY_SCALE_LOG_PATH.parent))} "
        f"&& flock -n {shlex.quote(str(lock))} bash -lc {shlex.quote(inner)} "
        f"|| bash -lc {shlex.quote(conflict)}"
    ).replace("%", r"\%")
    return "\n".join([FACTORY_SCALE_CRON_BEGIN, f"{schedule} {command} >> {shlex.quote(str(FACTORY_SCALE_LOG_PATH))} 2>&1", FACTORY_SCALE_CRON_END, ""])


def factory_scale_cron_status(crontab_file: str = "") -> dict[str, Any]:
    text = read_crontab(crontab_file)
    installed = FACTORY_SCALE_CRON_BEGIN in text and FACTORY_SCALE_CRON_END in text
    schedule = ""
    run_id = ""
    if installed:
        block = text.split(FACTORY_SCALE_CRON_BEGIN, 1)[1].split(FACTORY_SCALE_CRON_END, 1)[0]
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            schedule = " ".join(line.split()[:5])
            if "--run-id" in line:
                parts = line.split()
                for index, part in enumerate(parts):
                    if part == "--run-id" and index + 1 < len(parts):
                        run_id = parts[index + 1].strip("'\"")
                        break
            break
    return {
        "installed": installed,
        "marker_begin_count": text.count(FACTORY_SCALE_CRON_BEGIN),
        "marker_end_count": text.count(FACTORY_SCALE_CRON_END),
        "schedule": schedule,
        "run_id": run_id,
        "log_path": rel(FACTORY_SCALE_LOG_PATH),
        "crontab_file": crontab_file,
    }


def factory_scale_process_rows(process_lines: list[str] | None = None) -> list[dict[str, Any]]:
    if process_lines is None:
        try:
            result = subprocess.run(["ps", "-eo", "pid=,etime=,cmd="], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return []
        if result.returncode != 0:
            return []
        process_lines = result.stdout.splitlines()
    rows: list[dict[str, Any]] = []
    current_pid = os.getpid()
    for line in process_lines:
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        if pid == current_pid:
            continue
        cmd = parts[2]
        lower = cmd.lower()
        if " rg " in f" {lower} " or "ps -eo" in lower:
            continue
        if "factory-scale status" in lower or "factory-scale preflight" in lower or "factory-scale advance" in lower or "factory-scale start" in lower:
            continue
        patterns = (
            "walk-autopilot factory-scale",
            "walk_autopilot.py factory-scale",
            "parallel-delivery patch-swarm",
            "parallel_delivery.py patch-swarm",
            "proreq-light",
            "proreq_light.py",
        )
        if any(pattern in lower for pattern in patterns):
            rows.append({"pid": pid, "etime": parts[1], "command": cmd})
    return rows


def factory_scale_status_is_active(payload: dict[str, Any]) -> bool:
    status = str(payload.get("status") or "")
    pending = int(payload.get("pending_proreq_executions") or 0)
    cron = as_dict(payload.get("cron"))
    if bool(cron.get("installed")):
        return True
    return status in FACTORY_SCALE_ACTIVE_STATUSES and pending > 0


def factory_scale_no_overlap_preflight(
    run_id: str = "",
    crontab_file: str = "",
    *,
    process_lines: list[str] | None = None,
) -> dict[str, Any]:
    target = factory_scale_status_payload(run_id, crontab_file)
    latest = target if not run_id else factory_scale_status_payload("", crontab_file)
    cron = factory_scale_cron_status(crontab_file)
    processes = factory_scale_process_rows(process_lines)
    target_active = factory_scale_status_is_active(target)
    latest_active = factory_scale_status_is_active(latest) and str(latest.get("run_id") or "") != str(target.get("run_id") or "")
    cron_active = bool(cron.get("installed"))
    process_active = bool(processes)
    active = bool(target_active or latest_active or cron_active or process_active)
    if active:
        decision = "attach_existing"
    elif str(target.get("status") or "") == "completed":
        decision = "reuse_completed_run"
    elif str(target.get("status") or "") == "unknown":
        decision = "safe_to_start"
    else:
        decision = "safe_to_advance"
    return {
        "schema_version": "cento.walk_autopilot.factory_scale.no_overlap_preflight.v1",
        "checked_at": now_iso(),
        "run_id": str(target.get("run_id") or run_id),
        "active": active,
        "decision": decision,
        "target_status": target,
        "latest_status": latest,
        "cron": cron,
        "active_processes": processes,
        "process_active": process_active,
        "cron_active": cron_active,
        "target_active": target_active,
        "latest_active": latest_active,
    }


def parse_factory_scale_live_api_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    live_categories = {"api", "pro", "image"}
    rows: list[dict[str, Any]] = []
    for record in records:
        if record.get("duplicate_of"):
            continue
        if str(record.get("provider") or "") != "openai":
            continue
        if str(record.get("category") or "") not in live_categories:
            continue
        if str(record.get("status") or "") not in {"started", "completed", "failed", "timeout"}:
            continue
        written = parse_iso_datetime(record.get("written_at"))
        if written is None:
            continue
        rows.append({"written_at": written, "record": record})
    rows.sort(key=lambda item: item["written_at"])
    return rows


def factory_scale_live_api_rate_limit(
    records: list[dict[str, Any]],
    *,
    max_calls_per_hour: int = 4,
    min_spacing_seconds: int = 900,
    checked_at: datetime | None = None,
) -> dict[str, Any]:
    checked_at = checked_at or datetime.now(timezone.utc).replace(microsecond=0)
    live_rows = parse_factory_scale_live_api_records(records)
    last = live_rows[-1] if live_rows else None
    window_started = checked_at - timedelta(hours=1)
    recent = [item for item in live_rows if item["written_at"] >= window_started]
    seconds_since_last: int | None = None
    last_call_at = ""
    if last:
        seconds_since_last = max(0, int((checked_at - last["written_at"]).total_seconds()))
        last_call_at = last["written_at"].isoformat().replace("+00:00", "Z")
    blocked_reasons: list[str] = []
    if max_calls_per_hour <= 0:
        blocked_reasons.append("max live OpenAI calls per hour is zero")
    elif len(recent) >= max_calls_per_hour:
        blocked_reasons.append(f"live OpenAI call count in the last hour is {len(recent)} >= {max_calls_per_hour}")
    if seconds_since_last is not None and seconds_since_last < min_spacing_seconds:
        blocked_reasons.append(f"last live OpenAI call was {seconds_since_last}s ago < {min_spacing_seconds}s minimum spacing")
    return {
        "schema_version": "cento.walk_autopilot.factory_scale.live_api_rate_limit.v1",
        "checked_at": checked_at.isoformat().replace("+00:00", "Z"),
        "allowed": not blocked_reasons,
        "blocked_reasons": blocked_reasons,
        "max_live_calls_per_hour": max_calls_per_hour,
        "min_live_call_spacing_seconds": min_spacing_seconds,
        "recent_live_call_count": len(recent),
        "live_call_record_count": len(live_rows),
        "last_live_call_at": last_call_at,
        "seconds_since_last_live_call": seconds_since_last,
    }


def factory_scale_live_api_guard(args: argparse.Namespace, run_dir: Path) -> dict[str, Any]:
    records = spend_ledger.read_jsonl(run_dir / "spend-ledger.jsonl")
    summary = spend_ledger.summarize_records(records)
    budget_gate = live_api_budget_gate(args, summary)
    rate_limit = factory_scale_live_api_rate_limit(
        records,
        max_calls_per_hour=int(getattr(args, "max_live_calls_per_hour", 4)),
        min_spacing_seconds=int(getattr(args, "min_live_call_spacing_seconds", 900)),
    )
    requested = bool(getattr(args, "allow_live_api", False))
    enabled = bool(requested and budget_gate.get("allowed") and rate_limit.get("allowed"))
    blocked_reasons: list[str] = []
    if requested and not bool(budget_gate.get("allowed")):
        blocked_reasons.append(str(budget_gate.get("reason") or "live OpenAI budget gate blocked"))
    if requested and not bool(rate_limit.get("allowed")):
        blocked_reasons.extend([str(item) for item in as_list(rate_limit.get("blocked_reasons"))])
    if not requested:
        blocked_reasons.append("live OpenAI/API lane not requested")
    return {
        "schema_version": "cento.walk_autopilot.factory_scale.live_api_guard.v1",
        "checked_at": now_iso(),
        "run_id": run_dir.name,
        "live_api_requested": requested,
        "live_api_enabled": enabled,
        "fail_closed": not enabled,
        "blocked_reasons": blocked_reasons,
        "budget_gate": budget_gate,
        "rate_limit": rate_limit,
        "lock_path": str(STATE_DIR / LIVE_API_LOCK_NAME),
        "policy": {
            "default_overnight_target_usd": 10.0,
            "default_overnight_hard_cap_usd": float(getattr(args, "hard_cap_usd", 25.0)),
            "no_cron_live_api_without_lock_budget_and_rate_limit": True,
            "dashboard_total_required_for_live_api": True,
        },
    }


def run_json_command(command: list[str], *, timeout: int) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        meta: dict[str, Any] = {
            "command": command,
            "command_text": shlex.join(command),
            "exit_code": result.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "timed_out": False,
            "stdout_bytes": len(stdout.encode("utf-8", errors="ignore")),
            "stderr_bytes": len(stderr.encode("utf-8", errors="ignore")),
        }
        if stderr:
            meta["stderr_sha256"] = sha256_text(stderr)
        if stdout.strip():
            try:
                payload = json.loads(stdout)
                meta["json_ok"] = isinstance(payload, dict)
            except json.JSONDecodeError:
                payload = {}
                meta["json_ok"] = False
                meta["stdout_sha256"] = sha256_text(stdout)
        else:
            payload = {}
            meta["json_ok"] = result.returncode == 0
        return (payload if isinstance(payload, dict) else {}, meta)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        meta = {
            "command": command,
            "command_text": shlex.join(command),
            "exit_code": 124,
            "duration_seconds": round(time.monotonic() - started, 3),
            "timed_out": True,
            "stdout_bytes": len(stdout.encode("utf-8", errors="ignore")),
            "stderr_bytes": len(stderr.encode("utf-8", errors="ignore")),
            "json_ok": False,
        }
        if stderr:
            meta["stderr_sha256"] = sha256_text(stderr)
        if stdout:
            meta["stdout_sha256"] = sha256_text(stdout)
        return {}, meta


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def int_or_none(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def issue_status_key(issue: dict[str, Any]) -> str:
    return str(issue.get("status") or "").strip().lower()


def issue_by_id(issues_payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
    items: dict[int, dict[str, Any]] = {}
    for item in as_list(issues_payload.get("issues")):
        if not isinstance(item, dict):
            continue
        issue_id = int_or_none(item.get("id"))
        if issue_id:
            items[issue_id] = item
    return items


def active_issue_ids_from_runs(runs_payload: dict[str, Any]) -> set[int]:
    active: set[int] = set()
    for item in as_list(runs_payload.get("runs")):
        if not isinstance(item, dict):
            continue
        issue_id = int_or_none(item.get("issue_id"))
        if not issue_id:
            continue
        status = str(item.get("status") or "").strip().lower()
        pid_alive = bool(item.get("pid_alive")) or bool(item.get("pid"))
        tmux_alive = bool(item.get("tmux_alive"))
        if status in REVIEW_UNBLOCK_ACTIVE_RUN_STATUSES and (pid_alive or tmux_alive):
            active.add(issue_id)
    return active


def canonical_agent_work_dir(issue_id: int) -> Path:
    return ROOT / "workspace" / "runs" / "agent-work" / str(issue_id)


def canonical_story_path(issue_id: int) -> Path:
    return canonical_agent_work_dir(issue_id) / "story.json"


def canonical_validation_path(issue_id: int) -> Path:
    return canonical_agent_work_dir(issue_id) / "validation.json"


def validation_run_note(issue_id: int, validation_path: Path) -> str:
    return "\n\n".join(
        [
            "## Delivered\n- Review/Unblock Autopilot ran the deterministic local validator path.",
            f"## Validation\n- Executed `agent-work validate-run {issue_id}` using `{rel(validation_path)}`.",
            "## Evidence\n- `validate-run` writes validation-report markdown, JSON, and review summary artifacts in the canonical issue run directory.",
            "## Residual risk\n- Automated checks may miss subjective review ambiguity; escalate if the generated report fails the strict review gate.",
        ]
    )


def review_unblock_mode_for_args(args: argparse.Namespace) -> str:
    if bool(getattr(args, "no_review_unblock", False)):
        return "off"
    explicit = str(getattr(args, "review_unblock_mode", "") or "").strip().lower()
    if explicit:
        return explicit
    return "aggressive" if bool(getattr(args, "live_workers", False)) else "report"


def review_unblock_action(
    action_type: str,
    *,
    issue_id: int | None = None,
    package: str = "",
    reason: str = "",
    command: list[str] | None = None,
    apply: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    seed = json.dumps(
        {"type": action_type, "issue_id": issue_id, "package": package, "reason": reason, "command": command or []},
        sort_keys=True,
    )
    payload: dict[str, Any] = {
        "id": f"{action_type}-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:10]}",
        "type": action_type,
        "issue_id": issue_id,
        "package": package,
        "reason": reason,
        "command": command or [],
        "apply": bool(apply),
        "status": "planned",
    }
    if extra:
        payload.update(extra)
    return payload


def collect_review_unblock_snapshot(stage_dir: Path) -> dict[str, Any]:
    snapshot_dir = stage_dir / "snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    recovery_payload, recovery_meta = run_json_command(
        [
            "./scripts/cento.sh",
            "agent-work",
            "recovery-plan",
            "--json",
            "--run-dir",
            rel(stage_dir / "recovery-plan"),
        ],
        timeout=180,
    )
    issues_payload, issues_meta = run_json_command(["./scripts/cento.sh", "agent-work", "list", "--all", "--json"], timeout=180)
    runs_payload, runs_meta = run_json_command(["./scripts/cento.sh", "agent-work", "runs", "--json"], timeout=180)

    write_json(snapshot_dir / "recovery-plan.json", recovery_payload)
    write_json(snapshot_dir / "agent-work-list.json", issues_payload)
    write_json(snapshot_dir / "agent-work-runs.json", runs_payload)
    command_meta = {"recovery_plan": recovery_meta, "agent_work_list": issues_meta, "agent_work_runs": runs_meta}
    write_json(snapshot_dir / "commands.json", command_meta)

    return {
        "schema_version": "cento.review_unblock.snapshot.v1",
        "collected_at": now_iso(),
        "stage_dir": rel(stage_dir),
        "recovery": recovery_payload,
        "issues": issues_payload,
        "runs": runs_payload,
        "commands": command_meta,
    }


def repair_story_payload(candidate: dict[str, Any], stage_dir: Path) -> dict[str, Any]:
    source_issue = int_or_none(candidate.get("source_issue_id")) or 0
    package = str(candidate.get("package") or "agent-ops")
    title = str(candidate.get("title") or f"Repair blocked Agent Work issue {source_issue}").strip()
    description = " ".join(str(candidate.get("description") or "").split())
    if len(description) > 900:
        description = description[:897].rstrip() + "..."
    repair_run_dir = f"workspace/runs/agent-work/review-unblock/{source_issue or 'unknown'}"
    return {
        "schema_version": "1.0",
        "issue": {"id": 0, "title": title, "package": package},
        "lane": {"owner": "walk-autopilot", "node": "linux", "agent": "", "role": "builder"},
        "paths": {"run_dir": repair_run_dir},
        "scope": {
            "goal": (
                f"Resolve the bounded recovery blocker for Agent Work issue #{source_issue}. "
                f"Recovery reason: {candidate.get('reason') or 'follow-up candidate'}."
            ),
            "acceptance": [
                "Inspect the source issue, recovery-plan note, canonical story/validation artifacts, and run evidence before changing status.",
                "Either repair the missing artifact/evidence, requeue with a precise note, or leave a closure recommendation with evidence.",
                "Do not broaden ownership beyond the source issue's run artifacts unless the issue text explicitly requires it.",
            ],
        },
        "expected_outputs": [
            {
                "path": f"{repair_run_dir}/worker-handoff.md",
                "description": "Concise handoff describing the blocker, repair performed, validation, evidence, and residual risk.",
                "owner": "builder",
                "required": True,
            },
            {
                "path": f"{repair_run_dir}/review-unblock-report.json",
                "description": "Machine-readable summary of the reviewed blocker and recommended next state.",
                "owner": "builder",
                "required": True,
            },
        ],
        "validation": {
            "manifest": f"{repair_run_dir}/validation.json",
            "mode": "no-model",
            "no_model_eligible": True,
            "risk": "medium",
            "escalation_triggers": ["missing_manifest", "failed_deterministic_command", "ambiguity"],
            "commands": [
                f"./scripts/cento.sh agent-work show {source_issue} --json",
                "python3 -m py_compile scripts/walk_autopilot.py",
            ],
        },
        "deliverables": {
            "manifest": f"{repair_run_dir}/deliverables.json",
            "hub": f"{repair_run_dir}/start-here.html",
        },
        "review_gate": {
            "required_sections": ["Delivered", "Validation", "Evidence", "Residual risk"],
            "residual_risk_required": True,
        },
        "metadata": {
            "drafted_at": now_iso(),
            "source": "walk-autopilot-review-unblock",
            "source_issue_id": source_issue,
            "recovery_reason": candidate.get("reason") or "",
            "description_excerpt": description,
            "stage_dir": rel(stage_dir),
        },
    }


def choose_review_unblock_candidates(snapshot: dict[str, Any], *, apply_allowed: bool, dirty_blocked: bool) -> list[dict[str, Any]]:
    recovery = as_dict(snapshot.get("recovery"))
    review = as_dict(recovery.get("review"))
    runs = as_dict(recovery.get("runs"))
    issues_payload = as_dict(snapshot.get("issues"))
    runs_payload = as_dict(snapshot.get("runs"))
    issues = issue_by_id(issues_payload)
    active_issue_ids = active_issue_ids_from_runs(runs_payload)
    actions: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int | str]] = set()

    def add(action: dict[str, Any], key: tuple[str, int | str] | None = None) -> None:
        action_key = key or (str(action.get("type") or ""), int_or_none(action.get("issue_id")) or str(action.get("package") or action.get("id") or ""))
        if action_key in seen_keys:
            return
        seen_keys.add(action_key)
        if dirty_blocked and str(action.get("type") or "") in REVIEW_UNBLOCK_MUTATING_TYPES:
            action["apply"] = False
            action["blocked_reason"] = "git dirty count changed during Review/Unblock snapshot collection"
        elif str(action.get("type") or "") in REVIEW_UNBLOCK_MUTATING_TYPES:
            action["apply"] = bool(apply_allowed)
        actions.append(action)

    close_budget = REVIEW_UNBLOCK_ACTION_CAPS["close_done"]
    for package_item in as_list(review.get("packages_ready")):
        if not isinstance(package_item, dict):
            continue
        package = str(package_item.get("package") or "").strip()
        count = int_or_none(package_item.get("count")) or len(as_list(package_item.get("issue_ids")))
        if not package:
            continue
        if count <= 0:
            continue
        if count > close_budget:
            add(
                review_unblock_action(
                    "operator_needed",
                    package=package,
                    reason=f"Review package `{package}` has {count} ready issue(s), exceeding remaining close cap {close_budget}.",
                    apply=False,
                    extra={"issue_ids": as_list(package_item.get("issue_ids"))},
                ),
                ("operator_needed", f"close_cap_{package}"),
            )
            continue
        close_budget -= count
        add(
            review_unblock_action(
                "close_done",
                package=package,
                reason=f"{count} Review issue(s) have passing validation and evidence.",
                command=[
                    "./scripts/cento.sh",
                    "agent-work",
                    "review-drain",
                    "--package",
                    package,
                    "--run-dir",
                    "__STAGE_ACTION_DIR__",
                    "--json",
                    "--apply",
                ],
                apply=apply_allowed,
                extra={"issue_ids": as_list(package_item.get("issue_ids"))},
            ),
            ("close_done", package),
        )

    local_validations = 0
    dispatches = 0
    for issue in as_list(issues_payload.get("issues")):
        if not isinstance(issue, dict):
            continue
        issue_id = int_or_none(issue.get("id"))
        if not issue_id or issue_id in active_issue_ids:
            continue
        status = issue_status_key(issue)
        if status != "validating":
            continue
        story_path = canonical_story_path(issue_id)
        validation_path = canonical_validation_path(issue_id)
        if story_path.exists() and validation_path.exists() and local_validations < REVIEW_UNBLOCK_ACTION_CAPS["validate_local"]:
            local_validations += 1
            add(
                review_unblock_action(
                    "validate_local",
                    issue_id=issue_id,
                    package=str(issue.get("package") or ""),
                    reason="Validating issue has canonical story and validation manifests and no active run.",
                    command=[
                        "./scripts/cento.sh",
                        "agent-work",
                        "validate-run",
                        str(issue_id),
                        "--manifest",
                        rel(validation_path),
                        "--story-manifest",
                        rel(story_path),
                        "--note",
                        validation_run_note(issue_id, validation_path),
                        "--json",
                    ],
                    apply=apply_allowed,
                ),
                ("validate_local", issue_id),
            )
        elif story_path.exists() and validation_path.exists() and dispatches < REVIEW_UNBLOCK_ACTION_CAPS["dispatch_validator"]:
            dispatches += 1
            add(
                review_unblock_action(
                    "dispatch_validator",
                    issue_id=issue_id,
                    package=str(issue.get("package") or ""),
                    reason="Validating issue has manifests but exceeded the local validation cap; launch a bounded validator.",
                    command=[
                        "./scripts/cento.sh",
                        "agent-work",
                        "dispatch",
                        str(issue_id),
                        "--role",
                        "validator",
                        "--runtime",
                        "auto",
                        "--validation-manifest",
                        rel(validation_path),
                    ],
                    apply=apply_allowed,
                ),
                ("dispatch_validator", issue_id),
            )
        else:
            add(
                review_unblock_action(
                    "operator_needed",
                    issue_id=issue_id,
                    package=str(issue.get("package") or ""),
                    reason="Validating issue has no active run but is missing a canonical story or validation manifest.",
                    apply=False,
                    extra={"story_manifest": rel(story_path), "validation_manifest": rel(validation_path)},
                ),
                ("operator_needed", issue_id),
            )

    requeue_count = 0
    for item in as_list(recovery.get("blocked_requeue")):
        if requeue_count >= REVIEW_UNBLOCK_ACTION_CAPS["requeue_stale_dispatch"]:
            break
        if not isinstance(item, dict):
            continue
        issue_id = int_or_none(item.get("id"))
        if not issue_id or issue_id in active_issue_ids:
            continue
        requeue_count += 1
        role = str(item.get("role") or "builder")
        add(
            review_unblock_action(
                "requeue_stale_dispatch",
                issue_id=issue_id,
                package=str(item.get("package") or ""),
                reason=str(item.get("reason") or "stale dispatch can be requeued"),
                command=[
                    "./scripts/cento.sh",
                    "agent-work",
                    "update",
                    str(issue_id),
                    "--status",
                    "queued",
                    "--role",
                    role,
                    "--note",
                    "Review/Unblock Autopilot requeued this issue because the prior dispatch is stale and no active run is attached.",
                    "--json",
                ],
                apply=apply_allowed,
            ),
            ("requeue_stale_dispatch", issue_id),
        )

    for item in as_list(runs.get("stale_items")):
        if not isinstance(item, dict):
            continue
        issue_id = int_or_none(item.get("issue_id"))
        run_id = str(item.get("run_id") or "").strip()
        if not issue_id or not run_id:
            continue
        issue = issues.get(issue_id, {})
        status = issue_status_key(issue)
        if status in {"done", "closed"} or bool(issue.get("is_closed")):
            if len([action for action in actions if action.get("type") == "archive_stale_historical"]) >= REVIEW_UNBLOCK_ACTION_CAPS["archive_stale_historical"]:
                continue
            add(
                review_unblock_action(
                    "archive_stale_historical",
                    issue_id=issue_id,
                    package=str(issue.get("package") or item.get("package") or ""),
                    reason="Stale run ledger belongs to a Done or closed issue.",
                    command=["python3", "scripts/agent_manager.py", "reconcile-ledger", run_id, "--apply"],
                    apply=apply_allowed,
                    extra={"run_id": run_id},
                ),
                ("archive_stale_historical", run_id),
            )
        elif status in {"running", "validating", "blocked"} and issue_id not in active_issue_ids:
            if requeue_count >= REVIEW_UNBLOCK_ACTION_CAPS["requeue_stale_dispatch"]:
                continue
            requeue_count += 1
            role = str(issue.get("role") or item.get("role") or "builder")
            add(
                review_unblock_action(
                    "requeue_stale_dispatch",
                    issue_id=issue_id,
                    package=str(issue.get("package") or item.get("package") or ""),
                    reason=f"Stale {item.get('role') or 'worker'} ledger has no live pid or tmux session.",
                    command=[
                        "./scripts/cento.sh",
                        "agent-work",
                        "update",
                        str(issue_id),
                        "--status",
                        "queued",
                        "--role",
                        role,
                        "--note",
                        f"Review/Unblock Autopilot requeued this issue because run `{run_id}` is stale and no active process is attached.",
                        "--json",
                    ],
                    apply=apply_allowed,
                    extra={"run_id": run_id},
                ),
                ("requeue_stale_dispatch", issue_id),
            )

    for item in as_list(recovery.get("follow_up_candidates"))[: REVIEW_UNBLOCK_ACTION_CAPS["repair_task"]]:
        if not isinstance(item, dict):
            continue
        source_issue_id = int_or_none(item.get("source_issue_id"))
        if not source_issue_id:
            continue
        story_manifest = f"__STAGE_DRAFT_DIR__/repair-{source_issue_id}.story.json"
        add(
            review_unblock_action(
                "repair_task",
                issue_id=source_issue_id,
                package=str(item.get("package") or "agent-ops"),
                reason=str(item.get("reason") or "bounded follow-up candidate"),
                command=[
                    "./scripts/cento.sh",
                    "agent-work",
                    "create",
                    "--title",
                    str(item.get("title") or f"Repair blocked Agent Work issue {source_issue_id}"),
                    "--description",
                    str(item.get("description") or f"Repair blocked Agent Work issue {source_issue_id}"),
                    "--node",
                    "linux",
                    "--role",
                    "builder",
                    "--package",
                    str(item.get("package") or "agent-ops"),
                    "--manifest",
                    story_manifest,
                    "--owns",
                    f"workspace/runs/agent-work/{source_issue_id}/",
                    "--json",
                ],
                apply=apply_allowed,
                extra={"source_candidate": item, "story_manifest": story_manifest},
            ),
            ("repair_task", source_issue_id),
        )

    demo_closed = 0
    for issue in as_list(issues_payload.get("issues")):
        if not isinstance(issue, dict) or not bool(issue.get("test_artifact")):
            continue
        issue_id = int_or_none(issue.get("id"))
        if not issue_id or issue_id in active_issue_ids:
            continue
        status = issue_status_key(issue)
        if status in {"done", "closed", "running", "validating", "review"}:
            continue
        if demo_closed >= REVIEW_UNBLOCK_ACTION_CAPS["close_demo_test"]:
            continue
        demo_closed += 1
        role = str(issue.get("role") or "coordinator")
        add(
            review_unblock_action(
                "close_demo_test",
                issue_id=issue_id,
                package=str(issue.get("package") or ""),
                reason="Issue is tagged by Agent Work as demo/test/stale inventory and has no active run.",
                command=[
                    "./scripts/cento.sh",
                    "agent-work",
                    "update",
                    str(issue_id),
                    "--status",
                    "done",
                    "--role",
                    role,
                    "--note",
                    "Review/Unblock Autopilot closed this demo/test inventory item; no active run was attached.",
                    "--json",
                ],
                apply=apply_allowed,
            ),
            ("close_demo_test", issue_id),
        )

    if dirty_blocked:
        add(
            review_unblock_action(
                "operator_needed",
                reason="Git dirty count changed during snapshot collection, so mutating Review/Unblock actions were blocked.",
                apply=False,
            ),
            ("operator_needed", "dirty_changed"),
        )

    command_failures = [
        name
        for name, meta in as_dict(snapshot.get("commands")).items()
        if isinstance(meta, dict) and int(meta.get("exit_code") or 0) != 0
    ]
    if command_failures:
        add(
            review_unblock_action(
                "operator_needed",
                reason=f"Review/Unblock snapshot command(s) failed: {', '.join(command_failures)}.",
                apply=False,
                extra={"command_failures": command_failures},
            ),
            ("operator_needed", "command_failures"),
        )

    return actions


def decide_review_unblock(snapshot: dict[str, Any], *, mode: str, dirty_before: int, dirty_after: int) -> dict[str, Any]:
    apply_allowed = mode == "aggressive" and dirty_before == dirty_after
    dirty_blocked = dirty_before != dirty_after
    actions = choose_review_unblock_candidates(snapshot, apply_allowed=apply_allowed, dirty_blocked=dirty_blocked)
    type_counts = Counter(str(item.get("type") or "unknown") for item in actions)
    applicable = [item for item in actions if bool(item.get("apply"))]
    return {
        "schema_version": "cento.review_unblock.decision.v1",
        "decided_at": now_iso(),
        "mode": mode,
        "authority": "report" if mode == "report" else "bounded_apply",
        "apply_allowed": apply_allowed,
        "dirty_count_before": dirty_before,
        "dirty_count_after": dirty_after,
        "action_caps": REVIEW_UNBLOCK_ACTION_CAPS,
        "summary": {
            "action_count": len(actions),
            "applicable_count": len(applicable),
            "operator_needed_count": type_counts.get("operator_needed", 0),
            "type_counts": dict(sorted(type_counts.items())),
        },
        "actions": actions,
        "next_iteration": [
            "Compare action type counts across two loops before raising caps.",
            "Keep review-drain closure evidence-first; never close Review without validation pass plus evidence.",
            "Convert repeated operator_needed reasons into narrower deterministic repair rules only after two samples.",
        ],
    }


def materialize_review_unblock_action(action: dict[str, Any], action_dir: Path) -> list[str]:
    command = [str(item) for item in as_list(action.get("command"))]
    replacements = {
        "__STAGE_ACTION_DIR__": rel(action_dir),
        "__STAGE_DRAFT_DIR__": rel(action_dir / "drafts"),
    }
    materialized: list[str] = []
    for item in command:
        for source, replacement in replacements.items():
            item = item.replace(source, replacement)
        materialized.append(item)
    if action.get("type") == "repair_task":
        source_candidate = as_dict(action.get("source_candidate"))
        source_issue = int_or_none(action.get("issue_id")) or 0
        draft_path = action_dir / "drafts" / f"repair-{source_issue}.story.json"
        write_json(draft_path, repair_story_payload(source_candidate, action_dir))
        action["story_manifest_materialized"] = rel(draft_path)
    return materialized


def apply_review_unblock_actions(actions: list[dict[str, Any]], stage_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, original in enumerate(actions, start=1):
        action = dict(original)
        action_dir = stage_dir / "actions" / f"{index:03d}-{action.get('type')}"
        action_dir.mkdir(parents=True, exist_ok=True)
        if not bool(action.get("apply")):
            action["status"] = "skipped_report"
            write_json(action_dir / "action.json", action)
            append_jsonl(stage_dir / "actions.jsonl", action)
            results.append(action)
            continue
        command = materialize_review_unblock_action(action, action_dir)
        action["command"] = command
        timeout = 240 if action.get("type") in {"validate_local", "dispatch_validator"} else 120
        result = run_command(command, timeout=timeout)
        action["result"] = result
        action["status"] = "applied" if int(result.get("exit_code") or 0) == 0 else "failed"
        write_json(action_dir / "action.json", action)
        append_jsonl(stage_dir / "actions.jsonl", action)
        results.append(action)
    return results


def write_review_unblock_report(path: Path, snapshot: dict[str, Any], decision: dict[str, Any], results: list[dict[str, Any]]) -> None:
    summary = as_dict(decision.get("summary"))
    applied = [item for item in results if item.get("status") == "applied"]
    failed = [item for item in results if item.get("status") == "failed"]
    skipped = [item for item in results if item.get("status") == "skipped_report"]
    lines = [
        "# Review/Unblock Autopilot",
        "",
        f"- Mode: `{decision.get('mode')}`",
        f"- Authority: `{decision.get('authority')}`",
        f"- Actions: `{summary.get('action_count', 0)}`",
        f"- Applicable: `{summary.get('applicable_count', 0)}`",
        f"- Applied: `{len(applied)}`",
        f"- Failed: `{len(failed)}`",
        f"- Skipped/report-only: `{len(skipped)}`",
        f"- Operator-needed: `{summary.get('operator_needed_count', 0)}`",
        "",
        "## Type Counts",
        "",
        markdown_list([f"`{key}`: {value}" for key, value in as_dict(summary.get("type_counts")).items()]),
        "",
        "## Actions",
        "",
    ]
    for item in results:
        issue = f"#{item.get('issue_id')}" if item.get("issue_id") else "-"
        lines.append(
            f"- `{item.get('status')}` `{item.get('type')}` issue={issue} package=`{item.get('package') or '-'}` reason={item.get('reason')}"
        )
    if not results:
        lines.append("- No action candidates.")
    command_meta = as_dict(snapshot.get("commands"))
    lines.extend(
        [
            "",
            "## Snapshot Commands",
            "",
            markdown_list(
                [
                    f"`{name}` exit={as_dict(meta).get('exit_code')} json_ok={as_dict(meta).get('json_ok')}"
                    for name, meta in command_meta.items()
                ]
            ),
            "",
            "## Next Iteration",
            "",
            markdown_list([str(item) for item in as_list(decision.get("next_iteration"))]),
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def latest_review_unblock_run_dir() -> Path | None:
    if not REVIEW_UNBLOCK_RUN_ROOT.exists():
        return None
    runs = [path for path in REVIEW_UNBLOCK_RUN_ROOT.glob("review-unblock-*") if path.is_dir()]
    return sorted(runs)[-1] if runs else None


def mirror_review_unblock_latest(run_dir: Path) -> None:
    REVIEW_UNBLOCK_LATEST_DIR.parent.mkdir(parents=True, exist_ok=True)
    if REVIEW_UNBLOCK_LATEST_DIR.exists() or REVIEW_UNBLOCK_LATEST_DIR.is_symlink():
        if REVIEW_UNBLOCK_LATEST_DIR.is_dir() and not REVIEW_UNBLOCK_LATEST_DIR.is_symlink():
            shutil.rmtree(REVIEW_UNBLOCK_LATEST_DIR)
        else:
            REVIEW_UNBLOCK_LATEST_DIR.unlink()
    shutil.copytree(run_dir, REVIEW_UNBLOCK_LATEST_DIR)


def run_review_unblock_stage(stage_dir: Path, *, mode: str) -> dict[str, Any]:
    stage_dir.mkdir(parents=True, exist_ok=True)
    dirty_before = count_dirty_files()
    snapshot = collect_review_unblock_snapshot(stage_dir)
    dirty_after = count_dirty_files()
    decision = decide_review_unblock(snapshot, mode=mode, dirty_before=dirty_before, dirty_after=dirty_after)
    write_json(stage_dir / "snapshot.json", snapshot)
    write_json(stage_dir / "decision.json", decision)
    results = apply_review_unblock_actions(as_list(decision.get("actions")), stage_dir)
    write_json(stage_dir / "results.json", {"schema_version": "cento.review_unblock.results.v1", "results": results})
    write_review_unblock_report(stage_dir / "decision_report.md", snapshot, decision, results)
    type_counts = Counter(str(item.get("type") or "unknown") for item in results)
    status_counts = Counter(str(item.get("status") or "unknown") for item in results)
    failed_count = status_counts.get("failed", 0)
    return {
        "schema_version": "cento.review_unblock.stage.v1",
        "status": "completed" if failed_count == 0 else "failed",
        "exit_code": 0 if failed_count == 0 else 1,
        "mode": mode,
        "stage_dir": rel(stage_dir),
        "decision_report": rel(stage_dir / "decision_report.md"),
        "summary": as_dict(decision.get("summary")),
        "type_counts": dict(sorted(type_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "failed_count": failed_count,
        "applied_count": status_counts.get("applied", 0),
        "skipped_count": status_counts.get("skipped_report", 0),
        "operator_needed_count": type_counts.get("operator_needed", 0),
    }


def review_unblock_command_record(stage: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": "review-unblock",
        "exit_code": int(stage.get("exit_code") or 0),
        "command": ["internal", "review-unblock-stage"],
        "command_text": f"internal review-unblock stage mode={stage.get('mode')}",
        "stdout_tail": json.dumps({"summary": stage.get("summary"), "decision_report": stage.get("decision_report")}, sort_keys=True),
        "stderr_tail": "",
        "duration_seconds": 0,
        "timed_out": False,
        "review_unblock": stage,
    }


def collect_git_counts() -> dict[str, Any]:
    result = run_command(["git", "status", "--short"], timeout=20)
    lines = [line for line in str(result.get("stdout_tail") or "").splitlines() if line.strip()]
    status_counts = Counter((line[:2] or "??").strip() or line[:2] for line in lines)
    return {
        "exit_code": result.get("exit_code"),
        "dirty_count": len(lines) if int(result.get("exit_code") or 0) == 0 else -1,
        "status_counts": dict(sorted(status_counts.items())),
    }


def collect_tool_registry_counts() -> dict[str, Any]:
    payload = read_json(ROOT / "data" / "tools.json")
    tools = payload.get("tools") if isinstance(payload.get("tools"), list) else []
    walk = next((item for item in tools if isinstance(item, dict) and item.get("id") == "walk-autopilot"), {})
    commands = walk.get("commands") if isinstance(walk, dict) and isinstance(walk.get("commands"), list) else []
    docs = walk.get("docs") if isinstance(walk, dict) and isinstance(walk.get("docs"), list) else []
    return {
        "tool_count": len(tools),
        "walk_autopilot_registered": bool(walk),
        "walk_autopilot_command_count": len(commands),
        "walk_autopilot_routing_command_count": len([item for item in commands if " routing " in str(item)]),
        "walk_autopilot_docs_count": len(docs),
    }


def collect_cli_docs_counts() -> dict[str, Any]:
    payload = read_json(ROOT / "data" / "cento-cli.json")
    commands = payload.get("commands") if isinstance(payload.get("commands"), list) else []
    routing = payload.get("routing") if isinstance(payload.get("routing"), list) else []
    notes = payload.get("notes") if isinstance(payload.get("notes"), list) else []
    doc_path = ROOT / "docs" / "ai-routing-nativeness-loop.md"
    return {
        "builtin_command_count": len(commands),
        "routing_entry_count": len(routing),
        "notes_count": len(notes),
        "human_routing_doc_exists": doc_path.exists(),
        "human_routing_doc_bytes": doc_path.stat().st_size if doc_path.exists() else 0,
    }


def summarize_walk_status(payload: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics_records")
    loops = payload.get("loops") if isinstance(payload.get("loops"), list) else []
    incidents = payload.get("incidents") if isinstance(payload.get("incidents"), list) else []
    spend = payload.get("spend") if isinstance(payload.get("spend"), dict) else {}
    return {
        "command": meta,
        "run_id": payload.get("run_id") or "",
        "metrics_records": metrics if isinstance(metrics, int) else 0,
        "loop_count": len(loops),
        "incident_count": len(incidents),
        "spend_total_usd": spend.get("total_cost_usd"),
    }


def collect_walk_autopilot_status() -> dict[str, Any]:
    payload, meta = run_json_command(["./scripts/cento.sh", "walk-autopilot", "status"], timeout=90)
    return summarize_walk_status(payload, meta)


def collect_self_improve_status() -> dict[str, Any]:
    payload, meta = run_json_command(["./scripts/cento.sh", "parallel-delivery", "self-improve", "status", "--json"], timeout=120)
    validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    promotion = payload.get("promotion") if isinstance(payload.get("promotion"), dict) else {}
    return {
        "command": meta,
        "run_dir": payload.get("run_dir") or "",
        "latest_dir": payload.get("latest_dir") or "",
        "cron_installed": bool(payload.get("cron_installed")),
        "status": payload.get("status") or "unknown",
        "validation_status": validation.get("status") or payload.get("validation_status") or "unknown",
        "promotion_recommendation": promotion.get("recommendation") or payload.get("promotion_recommendation") or "unknown",
    }


def aggregate_agent_runs(payload: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    runs = payload.get("runs") if isinstance(payload.get("runs"), list) else []
    status_counts: Counter[str] = Counter()
    health_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    runtime_counts: Counter[str] = Counter()
    demo_test_run_count = 0
    stale_count = 0
    failed_count = 0
    running_count = 0
    for item in runs:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "unknown")
        health = str(item.get("health") or "unknown")
        role = str(item.get("role") or "unknown")
        runtime = str(item.get("runtime") or "unknown")
        status_counts[status] += 1
        health_counts[health] += 1
        role_counts[role] += 1
        runtime_counts[runtime] += 1
        if "stale" in status or "stale" in health:
            stale_count += 1
        if status == "failed" or health == "failed":
            failed_count += 1
        if status == "running" or health == "running":
            running_count += 1
        haystack = " ".join(
            [
                str(item.get("issue_subject") or ""),
                str(item.get("package") or ""),
                str(item.get("run_id") or ""),
            ]
        ).lower()
        if any(term in haystack for term in ("demo", "test", "fixture")):
            demo_test_run_count += 1
    return {
        "command": meta,
        "count": len(runs),
        "status_counts": dict(sorted(status_counts.items())),
        "health_counts": dict(sorted(health_counts.items())),
        "role_counts": dict(sorted(role_counts.items())),
        "runtime_counts": dict(sorted(runtime_counts.items())),
        "stale_count": stale_count,
        "failed_count": failed_count,
        "running_count": running_count,
        "demo_test_run_count": demo_test_run_count,
    }


def collect_agent_work_counts() -> dict[str, Any]:
    payload, meta = run_json_command(["./scripts/cento.sh", "agent-work", "runs", "--json"], timeout=180)
    return aggregate_agent_runs(payload, meta)


def collect_codex_sqlite_counts(path: Path | None = None) -> dict[str, Any]:
    db_path = path or (Path.home() / ".codex" / "logs_2.sqlite")
    if not db_path.exists():
        return {"exists": False, "path": str(db_path)}
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2)
        try:
            columns = [str(row[1]) for row in conn.execute("pragma table_info(logs)").fetchall()]
            row_count = int(conn.execute("select count(*) from logs").fetchone()[0])
            level_counts = {
                str(level): int(count)
                for level, count in conn.execute("select level, count(*) from logs group by level order by count(*) desc").fetchall()
            }
            target_counts = {
                str(target): int(count)
                for target, count in conn.execute(
                    "select target, count(*) from logs group by target order by count(*) desc limit 20"
                ).fetchall()
            }
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return {"exists": True, "path": str(db_path), "error": type(exc).__name__}
    return {
        "exists": True,
        "path": str(db_path),
        "bytes": db_path.stat().st_size,
        "columns": columns,
        "row_count": row_count,
        "level_counts": level_counts,
        "error_count": int(level_counts.get("ERROR", 0) + level_counts.get("error", 0)),
        "top_targets": target_counts,
    }


def count_skill_mentions_in_file(path: Path, terms: list[str]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    if not path.exists():
        return {"exists": False, "path": str(path), "bytes": 0, "counts": dict(counts)}
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                for term in terms:
                    if term in line:
                        counts[term] += line.count(term)
    except OSError as exc:
        return {"exists": True, "path": str(path), "bytes": path.stat().st_size, "error": type(exc).__name__, "counts": dict(counts)}
    return {"exists": True, "path": str(path), "bytes": path.stat().st_size, "counts": dict(sorted(counts.items()))}


def collect_skill_usage_counts() -> dict[str, Any]:
    sources = [
        Path.home() / ".codex" / "history.jsonl",
        Path.home() / ".codex" / "log" / "codex-tui.log",
    ]
    source_counts = [count_skill_mentions_in_file(path, SKILL_TERMS) for path in sources]
    totals: Counter[str] = Counter()
    for source in source_counts:
        for term, count in (source.get("counts") or {}).items():
            totals[str(term)] += int(count)
    return {
        "terms": SKILL_TERMS,
        "sources": source_counts,
        "total_counts": dict(sorted(totals.items())),
    }


def collect_cento_native_skill_drift() -> dict[str, Any]:
    installed_root = Path.home() / ".codex" / "skills" / "cento-native"
    repo_root = ROOT / "skills" / "codex" / "cento-native"
    rows: list[dict[str, Any]] = []
    for relative in ("SKILL.md", "references/routing.md"):
        installed = file_fingerprint(installed_root / relative)
        repo = file_fingerprint(repo_root / relative)
        rows.append(
            {
                "relative_path": relative,
                "installed": installed,
                "repo": repo,
                "in_sync": bool(installed.get("exists") and repo.get("exists") and installed.get("sha256") == repo.get("sha256")),
            }
        )
    return {
        "installed_root": str(installed_root),
        "repo_root": rel(repo_root),
        "files": rows,
        "drift_count": len([item for item in rows if not item["in_sync"]]),
    }


def collect_routing_raw_counts(crontab_file: str = "") -> dict[str, Any]:
    return {
        "schema_version": "cento.routing_nativeness.raw_counts.v1",
        "collected_at": now_iso(),
        "privacy": {
            "mode": "counts-only",
            "raw_prompt_or_log_excerpts": False,
            "notes": "Collectors persist aggregate counts, command metadata, hashes, and status fields only.",
        },
        "git": collect_git_counts(),
        "cron": routing_cron_status(crontab_file),
        "tools": collect_tool_registry_counts(),
        "cli_docs": collect_cli_docs_counts(),
        "walk_autopilot": collect_walk_autopilot_status(),
        "self_improve": collect_self_improve_status(),
        "agent_work": collect_agent_work_counts(),
        "codex_observability": collect_codex_sqlite_counts(),
        "skill_usage": collect_skill_usage_counts(),
        "cento_native_skill_drift": collect_cento_native_skill_drift(),
    }


def routing_action(action_id: str, severity: str, reason: str, change: str, *, agent_work: bool = True) -> dict[str, Any]:
    return {
        "id": action_id,
        "severity": severity,
        "reason": reason,
        "recommended_change": change,
        "agent_work": agent_work,
    }


def decide_routing_changes(raw: dict[str, Any], *, dirty_before: int, dirty_after: int) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    cron = raw.get("cron") if isinstance(raw.get("cron"), dict) else {}
    if not bool(cron.get("installed")):
        actions.append(
            routing_action(
                "install_routing_cron",
                "medium",
                "The lightweight routing nativeness loop is not installed in crontab.",
                "Install the marked cron block at a four-hour cadence after deterministic validation passes.",
            )
        )

    self_improve = raw.get("self_improve") if isinstance(raw.get("self_improve"), dict) else {}
    self_status = str(self_improve.get("status") or "unknown").lower()
    validation_status = str(self_improve.get("validation_status") or "unknown").lower()
    promotion = str(self_improve.get("promotion_recommendation") or "unknown").lower()
    if self_status in {"unknown", "failed", "degraded", "partial", "incomplete"} or validation_status in {"unknown", "failed"} or promotion in {"unknown", "repair_pipeline_first"}:
        actions.append(
            routing_action(
                "repair_self_improve_before_heavy_cron",
                "high",
                f"Self-improvement status={self_status}, validation={validation_status}, promotion={promotion}.",
                "Repair the nightly self-improvement artifacts and gates before installing or relying on the heavier ProReq cron path.",
            )
        )

    drift = raw.get("cento_native_skill_drift") if isinstance(raw.get("cento_native_skill_drift"), dict) else {}
    drift_count = int(drift.get("drift_count") or 0)
    if drift_count:
        actions.append(
            routing_action(
                "sync_cento_native_skill",
                "high",
                f"{drift_count} installed/repo cento-native skill file(s) differ or are missing.",
                "Sync installed and repo skill copies, then validate routing intent examples for Docs, command docs, analysis, implementation, and tasking.",
            )
        )

    tools = raw.get("tools") if isinstance(raw.get("tools"), dict) else {}
    if int(tools.get("walk_autopilot_routing_command_count") or 0) < 4:
        actions.append(
            routing_action(
                "register_routing_commands",
                "high",
                "The tool registry does not expose the routing run/status/cron command surface.",
                "Register the walk-autopilot routing commands and artifact locations in data/tools.json and the human tool index.",
            )
        )

    cli_docs = raw.get("cli_docs") if isinstance(raw.get("cli_docs"), dict) else {}
    if not bool(cli_docs.get("human_routing_doc_exists")):
        actions.append(
            routing_action(
                "write_human_routing_docs",
                "medium",
                "No human-facing routing nativeness loop document exists under docs/.",
                "Add a readable operator page that explains cadence, authority, artifacts, privacy boundaries, and next iteration rules.",
            )
        )

    agent_work = raw.get("agent_work") if isinstance(raw.get("agent_work"), dict) else {}
    stale_count = int(agent_work.get("stale_count") or 0)
    demo_test_count = int(agent_work.get("demo_test_run_count") or 0)
    if stale_count or demo_test_count:
        actions.append(
            routing_action(
                "agent_work_hygiene_cleanup",
                "medium",
                f"Agent run inventory has stale_count={stale_count} and demo_test_run_count={demo_test_count}.",
                "Queue a bounded hygiene cleanup to archive stale historical runs, identify active blockers, and keep demo/test inventory from hiding live work.",
            )
        )

    codex = raw.get("codex_observability") if isinstance(raw.get("codex_observability"), dict) else {}
    error_count = int(codex.get("error_count") or 0)
    if error_count > 50:
        actions.append(
            routing_action(
                "codex_error_observability",
                "medium",
                f"Codex local observability database contains {error_count} ERROR rows.",
                "Summarize error targets by count, map repeated targets to Cento skills or routing gaps, and avoid storing raw log bodies.",
            )
        )
    elif error_count:
        actions.append(
            routing_action(
                "codex_error_observability",
                "low",
                f"Codex local observability database contains {error_count} ERROR rows.",
                "Track ERROR trend across the next two routing iterations before creating a repair task.",
                agent_work=False,
            )
        )

    agent_work_allowed = True
    if dirty_before != dirty_after:
        agent_work_allowed = False
        actions.append(
            routing_action(
                "dirty_worktree_changed_during_loop",
                "high",
                f"Git dirty count changed from {dirty_before} to {dirty_after} while collecting routing stats.",
                "Do not create or update Agent Work from this run; inspect concurrent local edits first.",
                agent_work=False,
            )
        )

    severity_counts = Counter(str(item.get("severity") or "unknown") for item in actions)
    actionable_count = len([item for item in actions if bool(item.get("agent_work"))])
    return {
        "schema_version": "cento.routing_nativeness.decision.v1",
        "decided_at": now_iso(),
        "authority": "report_then_task",
        "cron_may_plan": True,
        "cron_may_implement": False,
        "agent_work_allowed": agent_work_allowed,
        "dirty_count_before": dirty_before,
        "dirty_count_after": dirty_after,
        "summary": {
            "action_count": len(actions),
            "actionable_count": actionable_count,
            "severity_counts": dict(sorted(severity_counts.items())),
        },
        "actions": actions,
        "next_iteration": routing_next_iteration(actions),
    }


def routing_next_iteration(actions: list[dict[str, Any]]) -> list[str]:
    ids = {str(item.get("id") or "") for item in actions}
    steps = [
        "Let the four-hour loop collect at least two samples, then compare action id stability and severity movement.",
        "Keep collectors counts-only; add a new counter only when it changes a routing decision.",
        "Create implementation work through Agent Work, not directly from cron.",
    ]
    if "repair_self_improve_before_heavy_cron" in ids:
        steps.append("Repair the nightly self-improvement gate before enabling any heavier live ProReq automation.")
    if "sync_cento_native_skill" in ids:
        steps.append("Make the installed cento-native skill and repo copy byte-identical, then re-run routing stats.")
    if "agent_work_hygiene_cleanup" in ids:
        steps.append("Run a bounded Agent Work hygiene cleanup and measure stale/demo/test counts in the next sample.")
    if "codex_error_observability" in ids:
        steps.append("Track Codex ERROR count and top targets without storing log bodies or prompt text.")
    return steps


def write_routing_report(path: Path, raw: dict[str, Any], decision: dict[str, Any], agent_request: dict[str, Any]) -> None:
    tools = raw.get("tools") if isinstance(raw.get("tools"), dict) else {}
    agent_work = raw.get("agent_work") if isinstance(raw.get("agent_work"), dict) else {}
    codex = raw.get("codex_observability") if isinstance(raw.get("codex_observability"), dict) else {}
    skill_usage = raw.get("skill_usage") if isinstance(raw.get("skill_usage"), dict) else {}
    actions = decision.get("actions") if isinstance(decision.get("actions"), list) else []
    lines = [
        "# Routing Nativeness Loop Decision Report",
        "",
        "## Summary",
        "",
        f"- Collected at: `{raw.get('collected_at')}`",
        f"- Authority: `{decision.get('authority')}`",
        f"- Cron may implement: `{decision.get('cron_may_implement')}`",
        f"- Actions: `{decision.get('summary', {}).get('action_count', 0)}`",
        f"- Actionable through Agent Work: `{decision.get('summary', {}).get('actionable_count', 0)}`",
        "",
        "## Counts",
        "",
        f"- Git dirty count: `{raw.get('git', {}).get('dirty_count')}`",
        f"- Routing cron installed: `{raw.get('cron', {}).get('installed')}`",
        f"- Registered tools: `{tools.get('tool_count')}`",
        f"- Walk Autopilot routing commands registered: `{tools.get('walk_autopilot_routing_command_count')}`",
        f"- Agent runs observed: `{agent_work.get('count')}`",
        f"- Agent stale count: `{agent_work.get('stale_count')}`",
        f"- Agent demo/test run count: `{agent_work.get('demo_test_run_count')}`",
        f"- Codex log rows: `{codex.get('row_count')}`",
        f"- Codex ERROR rows: `{codex.get('error_count')}`",
        f"- Skill usage terms tracked: `{len(skill_usage.get('terms') or [])}`",
        "",
        "## Decisions",
        "",
    ]
    if actions:
        for item in actions:
            lines.extend(
                [
                    f"### {item.get('id')}",
                    "",
                    f"- Severity: `{item.get('severity')}`",
                    f"- Agent Work: `{item.get('agent_work')}`",
                    f"- Reason: {item.get('reason')}",
                    f"- Recommended change: {item.get('recommended_change')}",
                    "",
                ]
            )
    else:
        lines.extend(["- No routing changes recommended by this sample.", ""])
    lines.extend(
        [
            "## Agent Work Handoff",
            "",
            f"- Status: `{agent_request.get('status')}`",
            f"- Issue: `{agent_request.get('issue_id') or ''}`",
            f"- Story manifest: `{agent_request.get('story_manifest') or ''}`",
            "",
            "## Next Iteration",
            "",
            markdown_list([str(item) for item in decision.get("next_iteration") or []]),
            "",
            "## Privacy Boundary",
            "",
            "This report is counts-only. It does not persist prompt text, log bodies, command stdout payloads, or raw Agent Work issue subjects.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_next_iteration(path: Path, decision: dict[str, Any]) -> None:
    lines = [
        "# Routing Nativeness Next Iteration",
        "",
        "## Operating Rule",
        "",
        "The scheduled loop gathers counts, writes a decision report, and creates or updates one bounded Agent Work task when an actionable change is detected. It does not implement changes from cron.",
        "",
        "## Next Steps",
        "",
        markdown_list([str(item) for item in decision.get("next_iteration") or []]),
        "",
        "## Promotion Check",
        "",
        "- Two consecutive runs should agree on top action ids before increasing automation.",
        "- Any new collector must prove it changes a routing decision and remains counts-only.",
        "- Heavy ProReq or live worker automation remains gated behind explicit operator action.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def routing_story_payload(decision: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    actions = [item for item in decision.get("actions") or [] if isinstance(item, dict) and bool(item.get("agent_work"))]
    acceptance = [
        f"{item.get('id')}: {item.get('recommended_change')}"
        for item in actions
    ] or ["No implementation action is required; keep the routing report as evidence."]
    return {
        "schema_version": "1.0",
        "issue": {"id": 0, "title": "Cento routing nativeness loop follow-up", "package": ROUTING_AGENT_WORK_PACKAGE},
        "lane": {"owner": "walk-autopilot", "node": "linux", "agent": "", "role": "coordinator"},
        "paths": {"run_dir": rel(run_dir)},
        "scope": {
            "goal": "Resolve the bounded routing and Cento-native follow-up actions identified by the lightweight scheduled routing loop.",
            "acceptance": acceptance,
        },
        "expected_outputs": [
            {
                "path": rel(run_dir / "decision_report.md"),
                "description": "Counts-only routing decision report that explains the selected follow-up actions.",
                "owner": "coordinator",
                "required": True,
            },
            {
                "path": rel(run_dir / "next_iteration.md"),
                "description": "Next iteration plan for the scheduled routing nativeness loop.",
                "owner": "coordinator",
                "required": True,
            },
        ],
        "validation": {
            "manifest": rel(run_dir / "validation.json"),
            "mode": "no-model",
            "no_model_eligible": True,
            "risk": "medium",
            "escalation_triggers": ["missing_manifest", "failed_deterministic_command", "ambiguity"],
            "commands": [
                "python3 -m pytest tests/test_routing_nativeness_loop.py tests/test_walk_autopilot.py tests/test_self_improvement_loop.py -q",
                "python3 -m py_compile scripts/walk_autopilot.py",
                "python3 -m json.tool data/tools.json",
                "python3 -m json.tool data/cento-cli.json",
            ],
        },
        "deliverables": {
            "manifest": rel(run_dir / "deliverables.json"),
            "hub": rel(run_dir / "start-here.html"),
        },
        "review_gate": {
            "required_sections": ["Delivered", "Validation", "Evidence", "Residual risk"],
            "residual_risk_required": True,
        },
        "metadata": {
            "drafted_at": now_iso(),
            "source": "walk-autopilot-routing-nativeness",
            "decision_report": rel(run_dir / "decision_report.md"),
            "action_ids": [str(item.get("id") or "") for item in actions],
        },
    }


def extract_issue_id(payload: dict[str, Any]) -> int | None:
    candidates = [payload.get("id"), payload.get("issue_id")]
    issue = payload.get("issue")
    if isinstance(issue, dict):
        candidates.extend([issue.get("id"), issue.get("issue_id")])
    for value in candidates:
        try:
            issue_id = int(value)
        except (TypeError, ValueError):
            continue
        if issue_id > 0:
            return issue_id
    return None


def routing_agent_note(run_dir: Path, decision: dict[str, Any]) -> str:
    summary = decision.get("summary") if isinstance(decision.get("summary"), dict) else {}
    return (
        "Routing nativeness loop wrote a new counts-only decision report. "
        f"Report: {rel(run_dir / 'decision_report.md')}. "
        f"Actions={summary.get('action_count', 0)} actionable={summary.get('actionable_count', 0)} "
        f"severity_counts={summary.get('severity_counts', {})}."
    )


def upsert_routing_agent_work(run_dir: Path, decision: dict[str, Any], *, no_agent_work: bool) -> dict[str, Any]:
    actionable = [item for item in decision.get("actions") or [] if isinstance(item, dict) and bool(item.get("agent_work"))]
    story_path = run_dir / "agent-work-story.json"
    write_json(story_path, routing_story_payload(decision, run_dir))
    if not actionable:
        return {"status": "not_needed", "issue_id": None, "story_manifest": rel(story_path)}
    if no_agent_work:
        return {"status": "skipped_no_agent_work", "issue_id": None, "story_manifest": rel(story_path)}
    if not bool(decision.get("agent_work_allowed")):
        return {"status": "blocked_dirty_worktree_changed", "issue_id": None, "story_manifest": rel(story_path)}

    previous = read_json(ROUTING_LATEST_DIR / "agent_work_request.json")
    previous_issue_id = extract_issue_id(previous)
    note = routing_agent_note(run_dir, decision)
    if previous_issue_id:
        show_payload, show_meta = run_json_command(["./scripts/cento.sh", "agent-work", "show", str(previous_issue_id), "--json"], timeout=60)
        issue_status = str(show_payload.get("status") or "").lower()
        if int(show_meta.get("exit_code") or 0) == 0 and issue_status not in {"done", "closed"}:
            update_payload, update_meta = run_json_command(
                ["./scripts/cento.sh", "agent-work", "update", str(previous_issue_id), "--note", note, "--json"],
                timeout=90,
            )
            if int(update_meta.get("exit_code") or 0) == 0:
                return {
                    "status": "updated",
                    "issue_id": extract_issue_id(update_payload) or previous_issue_id,
                    "story_manifest": rel(story_path),
                    "command": update_meta,
                }

    title = "Cento routing nativeness loop follow-up"
    description = (
        "Counts-only scheduled routing loop identified actionable Cento-native follow-up work. "
        f"Decision report: {rel(run_dir / 'decision_report.md')}"
    )
    create_payload, create_meta = run_json_command(
        [
            "./scripts/cento.sh",
            "agent-work",
            "create",
            "--title",
            title,
            "--description",
            description,
            "--node",
            "linux",
            "--role",
            "coordinator",
            "--package",
            ROUTING_AGENT_WORK_PACKAGE,
            "--manifest",
            rel(story_path),
            "--owns",
            "scripts/walk_autopilot.py",
            "--owns",
            "data/tools.json",
            "--owns",
            "docs/ai-routing-nativeness-loop.md",
            "--json",
        ],
        timeout=120,
    )
    issue_id = extract_issue_id(create_payload)
    return {
        "status": "created" if int(create_meta.get("exit_code") or 0) == 0 and issue_id else "create_failed",
        "issue_id": issue_id,
        "story_manifest": rel(story_path),
        "command": create_meta,
    }


def latest_routing_run_dir() -> Path | None:
    if not ROUTING_RUN_ROOT.exists():
        return None
    runs = [path for path in ROUTING_RUN_ROOT.glob("routing-native-*") if path.is_dir()]
    return sorted(runs)[-1] if runs else None


def mirror_routing_latest(run_dir: Path) -> None:
    ROUTING_LATEST_DIR.parent.mkdir(parents=True, exist_ok=True)
    if ROUTING_LATEST_DIR.exists() or ROUTING_LATEST_DIR.is_symlink():
        if ROUTING_LATEST_DIR.is_dir() and not ROUTING_LATEST_DIR.is_symlink():
            shutil.rmtree(ROUTING_LATEST_DIR)
        else:
            ROUTING_LATEST_DIR.unlink()
    shutil.copytree(run_dir, ROUTING_LATEST_DIR)


def latest_agent_pool_payload() -> dict[str, Any]:
    return read_json(STATE_DIR / "agent-pool-kick-latest.json")


def live_failure_issue_ids(payload: dict[str, Any]) -> list[int]:
    rows = payload.get("failed_launches") or payload.get("launched") or []
    ids: list[int] = []
    if not isinstance(rows, list):
        return ids
    for item in rows:
        if not isinstance(item, dict):
            continue
        try:
            issue_id = int(item.get("issue") or 0)
        except (TypeError, ValueError):
            continue
        if issue_id > 0 and issue_id not in ids:
            ids.append(issue_id)
    return ids


def manifest_gaps_for_agent_pool_payload(payload: dict[str, Any], issue_ids: list[int] | None = None) -> list[dict[str, Any]]:
    rows = payload.get("launched") or []
    requested = set(issue_ids or [])
    gaps: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return gaps
    for item in rows:
        if not isinstance(item, dict):
            continue
        try:
            issue_id = int(item.get("issue") or 0)
        except (TypeError, ValueError):
            continue
        if issue_id <= 0 or (requested and issue_id not in requested):
            continue
        story = ROOT / "workspace" / "runs" / "agent-work" / str(issue_id) / "story.json"
        validation = ROOT / "workspace" / "runs" / "agent-work" / str(issue_id) / "validation.json"
        story_missing = not story.exists()
        validation_missing = not validation.exists()
        if story_missing or validation_missing:
            gaps.append(
                {
                    "issue": issue_id,
                    "lane": item.get("lane"),
                    "subject": item.get("subject"),
                    "story_manifest": rel(story),
                    "validation_manifest": rel(validation),
                    "story_missing": story_missing,
                    "validation_missing": validation_missing,
                }
            )
    return gaps


def classify_agent_pool_live_failure(live_result: dict[str, Any], payload: dict[str, Any], gaps: list[dict[str, Any]]) -> str:
    text = "\n".join(
        [
            str(live_result.get("stdout_tail") or ""),
            str(live_result.get("stderr_tail") or ""),
            json.dumps(payload, sort_keys=True) if payload else "",
        ]
    ).lower()
    if bool(live_result.get("timed_out")):
        return "agent_pool_live_timeout"
    if "canonical story manifest is missing" in text or "story manifest is missing" in text or gaps:
        return "missing_canonical_manifest"
    if "dispatch preflight blocked" in text or "preflight" in text:
        return "dispatch_preflight_blocked"
    reason = payload.get("reason_summary", {}).get("primary_reason") if isinstance(payload.get("reason_summary"), dict) else ""
    if reason:
        return f"agent_pool_{str(reason).replace('-', '_')}"
    return "agent_pool_live_launch_failed"


def incident_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Agent Pool Live Dispatch Incident",
        "",
        f"- Class: `{payload.get('incident_class')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Loop: `{payload.get('loop')}`",
        f"- Opened: `{payload.get('opened_at')}`",
        "",
        "## Summary",
        "",
        str(payload.get("summary") or "Live worker dispatch failed and was handled by the walk autopilot incident path."),
        "",
        "## Candidate Issues",
        "",
    ]
    issues = payload.get("issue_ids") or []
    if issues:
        lines.extend(f"- `{issue}`" for issue in issues)
    else:
        lines.append("- None captured.")
    lines.extend(["", "## Manifest Gaps", ""])
    gaps = payload.get("manifest_gaps") or []
    if gaps:
        for item in gaps:
            lines.append(
                f"- #{item.get('issue')} `{item.get('lane') or '-'}` story_missing={item.get('story_missing')} validation_missing={item.get('validation_missing')}"
            )
    else:
        lines.append("- None detected.")
    lines.extend(["", "## Attempts", ""])
    for item in payload.get("attempts") or []:
        lines.append(f"- `{item.get('name')}` exit={item.get('exit_code')} timed_out={bool(item.get('timed_out'))}")
    lines.extend(["", "## Resolution", "", str(payload.get("resolution") or "Pending.")])
    return "\n".join(lines).rstrip() + "\n"


def write_agent_pool_incident(run_dir: Path, payload: dict[str, Any]) -> None:
    incident_dir = Path(str(payload["incident_dir"]))
    if not incident_dir.is_absolute():
        incident_dir = ROOT / incident_dir
    write_json(incident_dir / "incident.json", payload)
    (incident_dir / "notes.md").write_text(incident_markdown(payload), encoding="utf-8")
    attempts = payload.get("attempts") or []
    with (incident_dir / "attempts.jsonl").open("w", encoding="utf-8") as handle:
        for item in attempts:
            handle.write(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n")


def append_incident_history(run_dir: Path, payload: dict[str, Any]) -> None:
    append_jsonl(
        run_dir / "incident-history.jsonl",
        {
            "schema_version": "cento.walk_autopilot.incident_history.v1",
            "written_at": now_iso(),
            "run_id": run_dir.name,
            "loop": payload.get("loop"),
            "incident_class": payload.get("incident_class"),
            "status": payload.get("status"),
            "issue_ids": payload.get("issue_ids") or [],
            "incident_dir": rel(Path(str(payload.get("incident_dir") or ""))),
        },
    )


def consecutive_unresolved_incident_count(run_dir: Path, incident_class: str) -> int:
    records = spend_ledger.read_jsonl(run_dir / "incident-history.jsonl")
    count = 0
    for item in reversed(records):
        if str(item.get("incident_class") or "") != incident_class:
            break
        if str(item.get("status") or "") == "recovered":
            break
        count += 1
    return count


def self_improvement_story_payload(incident_payload: dict[str, Any], story_run_dir: str) -> dict[str, Any]:
    incident_class = str(incident_payload.get("incident_class") or "agent_pool_live_launch_failed")
    title = f"Repair recurring walk autopilot incident: {incident_class}"
    issue_ids = ", ".join(str(item) for item in incident_payload.get("issue_ids") or []) or "none captured"
    return {
        "schema_version": "1.0",
        "issue": {"id": 0, "title": title, "package": "agent-ops"},
        "lane": {"owner": "walk-autopilot", "node": "linux", "agent": "", "role": "builder"},
        "paths": {"run_dir": story_run_dir},
        "scope": {
            "goal": f"Eliminate recurring live worker dispatch incident class `{incident_class}` observed during Walk Autopilot. Candidate issues: {issue_ids}.",
            "acceptance": [
                "Incident classification, repair, retry, and documentation remain deterministic and covered by focused tests.",
                "Live worker dispatch keeps trying bounded repairs instead of falling back to proof-only loops.",
            ],
        },
        "expected_outputs": [
            {
                "path": "docs/agent-work-live-dispatch-incident.md",
                "description": "Operator runbook for recurring live worker dispatch incidents.",
                "owner": "builder",
                "required": True,
            },
            {
                "path": "tests/test_walk_autopilot.py",
                "description": "Focused regression coverage for incident handling behavior.",
                "owner": "builder",
                "required": True,
            },
        ],
        "validation": {
            "manifest": f"{story_run_dir}/validation.json",
            "mode": "no-model",
            "no_model_eligible": True,
            "risk": "medium",
            "escalation_triggers": ["missing_manifest", "failed_deterministic_command", "ambiguity"],
            "commands": [
                "python3 -m pytest tests/test_walk_autopilot.py tests/test_agent_pool_kick.py",
                "python3 -m json.tool data/tools.json",
            ],
        },
        "deliverables": {
            "manifest": f"{story_run_dir}/deliverables.json",
            "hub": f"{story_run_dir}/start-here.html",
        },
        "review_gate": {
            "required_sections": ["Delivered", "Validation", "Evidence", "Residual risk"],
            "residual_risk_required": True,
        },
        "metadata": {
            "drafted_at": now_iso(),
            "source": "walk-autopilot-incident-followup",
            "incident_class": incident_class,
        },
    }


def maybe_create_self_improvement_followup(run_dir: Path, incident_payload: dict[str, Any]) -> dict[str, Any]:
    incident_class = str(incident_payload.get("incident_class") or "")
    followups_path = run_dir / "incidents" / "self-improvement-followups.json"
    followups = read_json(followups_path)
    existing = followups.get(incident_class) if isinstance(followups, dict) else None
    if existing:
        return {"status": "existing", "followup": existing}

    incident_dir = Path(str(incident_payload["incident_dir"]))
    if not incident_dir.is_absolute():
        incident_dir = ROOT / incident_dir
    story_run_dir = rel(incident_dir / "self-improvement")
    story_path = incident_dir / "self-improvement-story.json"
    story_path.write_text(json.dumps(self_improvement_story_payload(incident_payload, story_run_dir), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    title = f"Repair recurring walk autopilot incident: {incident_class}"
    description = (
        f"Walk Autopilot observed the `{incident_class}` live worker dispatch incident in consecutive loops. "
        f"Incident bundle: {rel(incident_dir)}"
    )
    result = run_command(
        [
            "./scripts/cento.sh",
            "agent-work",
            "create",
            "--title",
            title,
            "--description",
            description,
            "--node",
            "linux",
            "--role",
            "builder",
            "--package",
            "agent-ops",
            "--manifest",
            rel(story_path),
            "--json",
        ],
        timeout=120,
    )
    record = {
        "status": "created" if int(result.get("exit_code") or 0) == 0 else "create_failed",
        "story_manifest": rel(story_path),
        "command": result.get("command_text"),
        "exit_code": result.get("exit_code"),
        "stdout_tail": result.get("stdout_tail"),
        "stderr_tail": result.get("stderr_tail"),
    }
    if not isinstance(followups, dict):
        followups = {}
    followups[incident_class] = record
    write_json(followups_path, followups)
    return record


def live_worker_blockers(commands: list[dict[str, Any]]) -> list[str]:
    recovered_live_launch = any(
        item.get("name") == "agent-pool-live-retry-after-incident" and int(item.get("exit_code") or 0) == 0
        for item in commands
    )
    blockers: list[str] = []
    for item in commands:
        if int(item.get("exit_code") or 0) == 0:
            continue
        if recovered_live_launch and item.get("name") == "agent-pool-live-launch":
            continue
        blockers.append(f"{item.get('name')}: exit {item.get('exit_code')}")
    return blockers


def handle_agent_pool_live_incident(
    *,
    run_dir: Path,
    loop_number: int,
    args: argparse.Namespace,
    live_result: dict[str, Any],
    run_named: Any,
) -> dict[str, Any]:
    payload = command_json_payload(live_result) or latest_agent_pool_payload()
    issue_ids = live_failure_issue_ids(payload)
    gaps = manifest_gaps_for_agent_pool_payload(payload, issue_ids)
    incident_class = classify_agent_pool_live_failure(live_result, payload, gaps)
    incident_dir = run_dir / "incidents" / f"loop-{loop_number:04d}-{incident_class}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    attempts = [live_result]
    incident_payload: dict[str, Any] = {
        "schema_version": "cento.walk_autopilot.agent_pool_incident.v1",
        "run_id": run_dir.name,
        "loop": loop_number,
        "opened_at": now_iso(),
        "updated_at": now_iso(),
        "incident_class": incident_class,
        "status": "open",
        "incident_dir": rel(incident_dir),
        "summary": "Live worker dispatch failed; Walk Autopilot is applying bounded repair and retry instead of switching to proof-only loops.",
        "issue_ids": issue_ids,
        "manifest_gaps": gaps,
        "agent_pool_payload": payload,
        "attempts": attempts,
        "resolution": "Repair and retry pending.",
    }
    write_agent_pool_incident(run_dir, incident_payload)
    notify(args.notify_target, f"Walk incident loop {loop_number}: {incident_class}; repairing and retrying live workers.")

    repair_command = [
        "./scripts/cento.sh",
        "agent-pool-kick",
        "--repair-missing-manifests",
        "--repair-apply",
        "--repair-lanes",
        "all",
        "--repair-limit",
        str(max(args.max_worker_launch, len(issue_ids), 1)),
        "--max-launch",
        "0",
        "--dry-run",
    ]
    for issue_id in issue_ids:
        repair_command.extend(["--repair-issue", str(issue_id)])
    repair = run_named("agent-pool-incident-repair-manifests", repair_command, 120)
    attempts.append(repair)

    post_repair = run_named(
        "agent-pool-incident-post-repair-dry-run",
        ["./scripts/cento.sh", "agent-pool-kick", "--max-launch", str(args.max_worker_launch), "--dry-run"],
        90,
    )
    attempts.append(post_repair)

    retry = run_named(
        "agent-pool-live-retry-after-incident",
        ["./scripts/cento.sh", "agent-pool-kick", "--max-launch", str(args.max_worker_launch)],
        240,
    )
    attempts.append(retry)

    if int(retry.get("exit_code") or 0) == 0:
        incident_payload["status"] = "recovered"
        incident_payload["resolution"] = "Manifest repair and bounded retry succeeded in the same loop."
    else:
        recovery = run_named(
            "agent-work-recovery-plan",
            [
                "./scripts/cento.sh",
                "agent-work",
                "recovery-plan",
                "--json",
                "--run-dir",
                rel(incident_dir / "recovery-plan"),
            ],
            180,
        )
        attempts.append(recovery)
        incident_payload["status"] = "unresolved"
        incident_payload["resolution"] = "Retry failed; recovery-plan artifacts were attached for the next loop."

    incident_payload["attempts"] = attempts
    incident_payload["updated_at"] = now_iso()
    write_agent_pool_incident(run_dir, incident_payload)
    append_incident_history(run_dir, incident_payload)

    if incident_payload["status"] != "recovered" and consecutive_unresolved_incident_count(run_dir, incident_class) >= 2:
        followup = maybe_create_self_improvement_followup(run_dir, incident_payload)
        incident_payload["self_improvement_followup"] = followup
        incident_payload["updated_at"] = now_iso()
        write_agent_pool_incident(run_dir, incident_payload)

    notify(
        args.notify_target,
        f"Walk incident loop {loop_number}: {incident_class} status={incident_payload['status']} bundle={rel(incident_dir / 'notes.md')}",
    )
    return incident_payload


def run_loop(run_dir: Path, loop_number: int, args: argparse.Namespace, previous_green: bool) -> dict[str, Any]:
    loop_started = now_iso()
    env = os.environ.copy()
    env["CENTO_WALK_AUTOPILOT_RUN_DIR"] = str(run_dir)
    env.setdefault("CENTO_AGENT_RUNTIME", "auto")
    env.setdefault("CENTO_HARD_PROREQ_DISABLE_GPT_IMAGE_2", "1")

    before_spend = spend_summary(run_dir)
    before_dirty = count_dirty_files()
    commands: list[dict[str, Any]] = []

    def run_named(name: str, command: list[str], timeout: int | None = None, extra_env: dict[str, str] | None = None) -> dict[str, Any]:
        merged_env = dict(env)
        if extra_env:
            merged_env.update(extra_env)
        result = run_command(command, timeout=timeout or args.command_timeout, env=merged_env)
        record = command_record(name, result)
        commands.append(record)
        return record

    run_named("tools-json", ["python3", "-m", "json.tool", "data/tools.json"], timeout=30)
    run_named("compute-policy", ["./scripts/cento.sh", "compute-policy", "show", "--json"], timeout=30)
    run_named("factory-status", ["./scripts/cento.sh", "factory", "status", args.factory_run_id, "--json"], timeout=60)
    run_named("factory-autopilot", ["./scripts/cento.sh", "factory", "autopilot", args.factory_run_id, "--dry-run", "--cycles", "1"], timeout=180)
    run_named("parallel-delivery-validate", ["./scripts/cento.sh", "parallel-delivery", "validate", "--json"], timeout=180)
    if getattr(args, "patch_swarm", False):
        run_named(
            "parallel-delivery-patch-swarm",
            [
                "./scripts/cento.sh",
                "parallel-delivery",
                "patch-swarm",
                "e2e",
                "--run-id",
                f"{run_dir.name}-loop-{loop_number:04d}",
                "--candidate-target",
                str(int(getattr(args, "patch_swarm_candidate_target", 100))),
                "--max-parallel-agents",
                str(int(getattr(args, "patch_swarm_max_parallel_agents", 5))),
                "--providers",
                str(getattr(args, "patch_swarm_providers", "codex-exec,claude-code,api-openai")),
                "--fixture",
                "--json",
            ],
            timeout=360,
        )
    else:
        commands.append({"name": "parallel-delivery-patch-swarm", "exit_code": 0, "skipped": True, "reason": "patch swarm autopilot disabled"})
    run_named(
        "agent-work-hygiene",
        ["./scripts/cento.sh", "agent-work-hygiene", "--out-dir", rel(run_dir / "agent-work-hygiene")],
        timeout=120,
    )
    review_unblock_mode = review_unblock_mode_for_args(args)
    if review_unblock_mode == "off":
        review_unblock_stage = {
            "status": "skipped",
            "exit_code": 0,
            "mode": "off",
            "summary": {},
            "applied_count": 0,
            "failed_count": 0,
            "operator_needed_count": 0,
        }
        commands.append({"name": "review-unblock", "exit_code": 0, "skipped": True, "reason": "review unblock disabled", "review_unblock": review_unblock_stage})
    else:
        try:
            review_unblock_stage = run_review_unblock_stage(
                run_dir / "review-unblock" / f"loop-{loop_number:04d}",
                mode=review_unblock_mode,
            )
            commands.append(review_unblock_command_record(review_unblock_stage))
        except Exception as exc:  # pragma: no cover - defensive loop containment
            review_unblock_stage = {
                "status": "failed",
                "exit_code": 1,
                "mode": review_unblock_mode,
                "error": str(exc),
                "summary": {},
                "applied_count": 0,
                "failed_count": 1,
                "operator_needed_count": 1,
            }
            commands.append(
                {
                    "name": "review-unblock",
                    "exit_code": 1,
                    "command": ["internal", "review-unblock-stage"],
                    "command_text": f"internal review-unblock stage mode={review_unblock_mode}",
                    "stdout_tail": "",
                    "stderr_tail": str(exc),
                    "duration_seconds": 0,
                    "timed_out": False,
                    "review_unblock": review_unblock_stage,
                }
            )
    run_named("agent-pool-dry-run", ["./scripts/cento.sh", "agent-pool-kick", "--max-launch", str(args.max_worker_launch), "--dry-run"], timeout=90)
    repair = run_named(
        "agent-pool-repair-manifests",
        [
            "./scripts/cento.sh",
            "agent-pool-kick",
            "--repair-missing-manifests",
            "--repair-apply",
            "--repair-lanes",
            "all",
            "--repair-limit",
            str(args.max_worker_launch),
            "--max-launch",
            "0",
            "--dry-run",
        ],
        timeout=90,
    )
    if args.live_workers:
        live_launch = run_named(
            "agent-pool-live-launch",
            ["./scripts/cento.sh", "agent-pool-kick", "--max-launch", str(args.max_worker_launch)],
            timeout=240,
        )
        if int(live_launch.get("exit_code") or 0) != 0:
            handle_agent_pool_live_incident(
                run_dir=run_dir,
                loop_number=loop_number,
                args=args,
                live_result=live_launch,
                run_named=run_named,
            )
    else:
        commands.append({"name": "agent-pool-live-launch", "exit_code": 0, "skipped": True, "reason": "live workers disabled"})

    if loop_number % 2 == 0 or args.make_check_every == 1:
        run_named("make-check", ["make", "check"], timeout=args.make_check_timeout)
    else:
        commands.append({"name": "make-check", "exit_code": 0, "skipped": True, "reason": "not scheduled this loop"})

    after_repair_dry_run = run_named("agent-pool-post-repair-dry-run", ["./scripts/cento.sh", "agent-pool-kick", "--max-launch", str(args.max_worker_launch), "--dry-run"], timeout=90)

    current_spend = spend_summary(run_dir)
    budget_gate = live_api_budget_gate(args, current_spend)
    explicit_api_allowed = (
        args.allow_live_api
        and bool(budget_gate.get("allowed"))
        and loop_number % 3 == 0
        and previous_green
        and float(current_spend.get("total_cost_usd") or 0.0) < args.soft_cap_usd
    )
    if explicit_api_allowed:
        run_named(
            "parallel-delivery-self-improve",
            ["./scripts/cento.sh", "parallel-delivery", "self-improve", "run", "--json"],
            timeout=args.proreq_timeout,
            extra_env={
                "CENTO_HARD_PROREQ_DISPATCH_PRO": "1",
                REQUIRE_DASHBOARD_BUDGET_ENV: "1",
                DASHBOARD_TOTAL_ENV: str(budget_gate.get("dashboard_total_spend_usd") or ""),
                OPENAI_HARD_CAP_ENV: str(args.hard_cap_usd),
            },
        )
    else:
        commands.append(
            {
                "name": "parallel-delivery-self-improve",
                "exit_code": 0,
                "skipped": True,
                "reason": "api gate closed or not scheduled",
                "allow_live_api": bool(args.allow_live_api),
                "previous_green": previous_green,
                "total_cost_usd": current_spend.get("total_cost_usd"),
                "soft_cap_usd": args.soft_cap_usd,
                "budget_gate": budget_gate,
            }
        )

    factory_record = spend_ledger.build_factory_record(
        run_id=run_dir.name,
        status="completed",
        cost_usd=0.0,
        artifact=f"loops/loop-{loop_number:04d}.md",
        note="Factory status/autopilot dry-run loop cost is deterministic zero.",
    )
    spend_ledger.append_record(run_dir / "spend-ledger.jsonl", factory_record, dedupe=False)
    after_spend = spend_summary(run_dir)
    spend_summary_record = {
        "schema_version": "cento.walk_autopilot.spend_summary.v1",
        "written_at": now_iso(),
        "run_id": run_dir.name,
        "loop": loop_number,
        "category": "loop_summary",
        "status": "completed",
        "billable": False,
        "cost_usd": 0.0,
        "summary": after_spend,
    }
    append_jsonl(run_dir / "spend-ledger.jsonl", spend_summary_record)

    after_dirty = count_dirty_files()
    changed_files = run_command(["git", "status", "--short"], timeout=20)
    green = validation_green(commands)
    blockers = live_worker_blockers(commands)
    if after_dirty != before_dirty:
        blockers.append(f"git dirty count changed from {before_dirty} to {after_dirty}; loop note records changed files")
    if hard_cap_reached(after_spend, args.hard_cap_usd):
        blockers.append(f"hard cap reached: {after_spend.get('total_cost_usd')} >= {args.hard_cap_usd}")

    metrics = {
        "schema_version": "cento.walk_autopilot.metrics.v1",
        "written_at": now_iso(),
        "run_id": run_dir.name,
        "loop": loop_number,
        "started_at": loop_started,
        "validation_green": green,
        "command_count": len(commands),
        "failed_command_count": len([item for item in commands if int(item.get("exit_code") or 0) != 0]),
        "unresolved_failed_command_count": len(live_worker_blockers(commands)),
        "spend_total_usd": after_spend.get("total_cost_usd"),
        "factory_cost_usd": after_spend.get("factory_cost_usd"),
        "api_cost_usd": after_spend.get("api_cost_usd"),
        "dirty_count_before": before_dirty,
        "dirty_count_after": after_dirty,
        "hard_cap_reached": hard_cap_reached(after_spend, args.hard_cap_usd),
        "soft_cap_warning": float(after_spend.get("total_cost_usd") or 0.0) >= args.soft_cap_usd,
        "make_check_exit_code": next((item.get("exit_code") for item in commands if item.get("name") == "make-check"), None),
        "make_check_skipped": bool(next((item.get("skipped") for item in commands if item.get("name") == "make-check"), False)),
        "review_unblock_mode": review_unblock_stage.get("mode"),
        "review_unblock_action_count": review_unblock_stage.get("summary", {}).get("action_count", 0),
        "review_unblock_applied_count": review_unblock_stage.get("applied_count", 0),
        "review_unblock_failed_count": review_unblock_stage.get("failed_count", 0),
        "review_unblock_operator_needed_count": review_unblock_stage.get("operator_needed_count", 0),
    }
    append_jsonl(run_dir / "metrics.jsonl", metrics)

    loop_path = run_dir / "loops" / f"loop-{loop_number:04d}.md"
    write_loop_markdown(
        loop_path,
        run_dir=run_dir,
        loop_number=loop_number,
        findings=loop_findings(commands, before_spend, after_spend),
        breakthroughs=loop_breakthroughs(repair, after_repair_dry_run, commands),
        copied_notes=copied_forward_notes(run_dir, loop_number),
        next_steps=[
            "Keep Factory and API spend separated in ledger summaries.",
            "Let Review/Unblock close, validate, requeue, or repair only when the decision report gives evidence.",
            "Use repaired canonical manifests only as preflight scaffolds; workers must produce real evidence.",
            "Run make check on the next scheduled even loop." if loop_number % 2 else "Review make check output before the next worker launch.",
        ],
        spend=after_spend,
        validation=commands,
        changed_files=str(changed_files.get("stdout_tail") or "").splitlines(),
        blockers=blockers,
        recommended_next_loop="Continue loop cadence if validation is green and hard cap is not reached; otherwise stop and inspect blockers.",
    )
    update_handoff(run_dir, loop_number, metrics, blockers)
    append_notes(run_dir, loop_number, blockers, after_spend)
    notify(args.notify_target, f"Walk loop {loop_number}/{args.loops}: green={green} spend=${float(after_spend.get('total_cost_usd') or 0):.2f} blockers={len(blockers)}")
    return {"green": green, "metrics": metrics, "blockers": blockers, "spend": after_spend, "loop_path": rel(loop_path)}


def loop_findings(commands: list[dict[str, Any]], before_spend: dict[str, Any], after_spend: dict[str, Any]) -> list[str]:
    findings = [
        f"Spend before loop: ${float(before_spend.get('total_cost_usd') or 0.0):.4f}; after loop: ${float(after_spend.get('total_cost_usd') or 0.0):.4f}.",
        "Factory dry-run work is recorded as a separate zero-cost factory ledger entry.",
    ]
    for item in commands:
        if int(item.get("exit_code") or 0) != 0:
            findings.append(f"{item.get('name')} failed with exit {item.get('exit_code')}.")
        if item.get("name") == "review-unblock":
            stage = as_dict(item.get("review_unblock"))
            summary = as_dict(stage.get("summary"))
            findings.append(
                "Review/Unblock stage "
                f"mode={stage.get('mode', 'unknown')} actions={summary.get('action_count', 0)} "
                f"applied={stage.get('applied_count', 0)} operator_needed={stage.get('operator_needed_count', 0)}."
            )
    return findings


def loop_breakthroughs(repair: dict[str, Any], post_repair: dict[str, Any], commands: list[dict[str, Any]] | None = None) -> list[str]:
    items = []
    try:
        payload = json.loads(str(repair.get("stdout_tail") or "{}"))
    except json.JSONDecodeError:
        payload = {}
    repairs = payload.get("manifest_repairs") if isinstance(payload, dict) else []
    if repairs:
        lanes = sorted({str(item.get("lane") or "unknown") for item in repairs if isinstance(item, dict)})
        items.append(f"Repaired {len(repairs)} missing live-lane manifest set(s): {', '.join(lanes) or 'unknown'}.")
    else:
        items.append("No missing live-lane story manifests needed repair in this loop.")
    if int(post_repair.get("exit_code") or 0) == 0:
        items.append("Post-repair pool dry-run completed.")
    command_rows = commands or []
    if any(item.get("name") == "agent-pool-live-retry-after-incident" and int(item.get("exit_code") or 0) == 0 for item in command_rows):
        items.append("Recovered a live worker dispatch incident with manifest repair and bounded retry.")
    elif any(item.get("name") == "agent-work-recovery-plan" for item in command_rows):
        items.append("Attached an agent-work recovery plan for an unresolved live dispatch incident.")
    review_stage = next((as_dict(item.get("review_unblock")) for item in command_rows if item.get("name") == "review-unblock"), {})
    if review_stage:
        applied = int(review_stage.get("applied_count") or 0)
        failed = int(review_stage.get("failed_count") or 0)
        operator_needed = int(review_stage.get("operator_needed_count") or 0)
        if applied:
            items.append(f"Review/Unblock applied {applied} evidence-gated action(s).")
        elif operator_needed:
            items.append(f"Review/Unblock identified {operator_needed} ambiguity item(s) for operator review.")
        elif failed:
            items.append("Review/Unblock wrote a failure record for the next recovery loop.")
    return items


def markdown_list(items: list[str], empty: str = "None.") -> str:
    if not items:
        return f"- {empty}"
    return "\n".join(f"- {item}" for item in items)


def write_loop_markdown(
    path: Path,
    *,
    run_dir: Path,
    loop_number: int,
    findings: list[str],
    breakthroughs: list[str],
    copied_notes: str,
    next_steps: list[str],
    spend: dict[str, Any],
    validation: list[dict[str, Any]],
    changed_files: list[str],
    blockers: list[str],
    recommended_next_loop: str,
) -> None:
    validation_lines = [
        f"{item.get('name')}: exit={item.get('exit_code', 'skipped')} skipped={bool(item.get('skipped'))}"
        for item in validation
    ]
    lines = [
        f"# Walk Autopilot Loop {loop_number:04d}",
        "",
        "## Findings",
        markdown_list(findings),
        "",
        "## Breakthroughs",
        markdown_list(breakthroughs),
        "",
        "## Copied-Forward Notes",
        copied_notes.strip() or "- None.",
        "",
        "## Next Steps",
        markdown_list(next_steps),
        "",
        "## Next Big Things",
        markdown_list(
            [
                "Reliable spend accounting remains the first priority.",
                "Hard ProReq/image fallback validation stays second.",
                "Live worker dispatch unlock via canonical manifests stays third.",
            ]
        ),
        "",
        "## Spend",
        "```json",
        json.dumps(spend, indent=2, sort_keys=True),
        "```",
        "",
        "## Validation",
        markdown_list(validation_lines),
        "",
        "## Changed Files",
        markdown_list(changed_files),
        "",
        "## Blockers",
        markdown_list(blockers),
        "",
        "## Recommended Next Loop",
        recommended_next_loop,
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    missing = [section for section in REQUIRED_LOOP_SECTIONS if f"## {section}" not in path.read_text(encoding="utf-8")]
    if missing:
        raise RuntimeError(f"loop markdown is missing required sections: {missing}")


def update_handoff(run_dir: Path, loop_number: int, metrics: dict[str, Any], blockers: list[str]) -> None:
    lines = [
        "# Walk Autopilot Handoff",
        "",
        f"- Run: `{run_dir.name}`",
        f"- Latest loop: `{loop_number}`",
        f"- Latest metrics: `{json.dumps(metrics, sort_keys=True)}`",
        "",
        "## Current Blockers",
        markdown_list(blockers),
        "",
        "## Incident Runbook",
        "`docs/agent-work-live-dispatch-incident.md`",
        "",
        "## Resume Command",
        f"`./scripts/cento.sh walk-autopilot run --run-id {run_dir.name}`",
        "",
    ]
    (run_dir / "handoff.md").write_text("\n".join(lines), encoding="utf-8")


def append_notes(run_dir: Path, loop_number: int, blockers: list[str], spend: dict[str, Any]) -> None:
    with (run_dir / "notes.md").open("a", encoding="utf-8") as handle:
        handle.write(
            f"\n## Loop {loop_number:04d} Note\n\n"
            f"- Spend total: ${float(spend.get('total_cost_usd') or 0.0):.4f}\n"
            f"- Blockers: {len(blockers)}\n"
        )


def notify(target: str, message: str) -> None:
    if not target:
        return
    subprocess.run(["./scripts/cento.sh", "notify", target, message], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=20)


def command_run(args: argparse.Namespace) -> int:
    run_id = args.run_id or timestamp_id()
    run_dir = RUN_ROOT / run_id
    budget_gate = live_api_budget_gate(args, {})
    if not bool(budget_gate.get("allowed")):
        print(json.dumps({"status": "blocked", "budget_gate": budget_gate}, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    init_run(run_dir, args)
    notify(args.notify_target, f"Walk autopilot {run_id} starting: loops={args.loops} cadence={args.cadence_seconds}s hard_cap=${args.hard_cap_usd:.0f}")
    previous_green = True
    consecutive_make_failures = 0
    for loop_number in range(1, args.loops + 1):
        started = time.monotonic()
        result = run_loop(run_dir, loop_number, args, previous_green)
        previous_green = bool(result["green"])
        make_ran = result["metrics"].get("make_check_skipped") is False
        make_fail = make_ran and int(result["metrics"].get("make_check_exit_code") or 0) != 0
        if make_fail:
            consecutive_make_failures += 1
        elif make_ran:
            consecutive_make_failures = 0
        if result["metrics"].get("hard_cap_reached"):
            notify(args.notify_target, f"Walk autopilot stopping: hard cap reached at loop {loop_number}.")
            break
        if consecutive_make_failures >= 2:
            notify(args.notify_target, f"Walk autopilot stopping: make check failed twice by loop {loop_number}.")
            break
        if loop_number < args.loops and args.cadence_seconds > 0:
            elapsed = time.monotonic() - started
            sleep_seconds = max(0.0, args.cadence_seconds - elapsed)
            if sleep_seconds:
                time.sleep(sleep_seconds)
    notify(args.notify_target, f"Walk autopilot {run_id} finished or detached loop exited. Handoff: {rel(run_dir / 'handoff.md')}")
    print(json.dumps({"run_id": run_id, "run_dir": rel(run_dir), "handoff": rel(run_dir / "handoff.md")}, indent=2))
    return 0


def command_start_tmux(args: argparse.Namespace) -> int:
    run_id = args.run_id or timestamp_id()
    budget_gate = live_api_budget_gate(args, {})
    if not bool(budget_gate.get("allowed")):
        print(json.dumps({"status": "blocked", "budget_gate": budget_gate}, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    command = [
        "./scripts/cento.sh",
        "walk-autopilot",
        "run",
        "--run-id",
        run_id,
        "--loops",
        str(args.loops),
        "--cadence-seconds",
        str(args.cadence_seconds),
        "--soft-cap-usd",
        str(args.soft_cap_usd),
        "--hard-cap-usd",
        str(args.hard_cap_usd),
        "--max-worker-launch",
        str(args.max_worker_launch),
    ]
    dashboard_total = dashboard_total_spend_usd(args)
    if dashboard_total is not None:
        command.extend(["--dashboard-total-spend-usd", str(dashboard_total)])
    if args.live_workers:
        command.append("--live-workers")
    if args.allow_live_api:
        command.append("--allow-live-api")
    if getattr(args, "review_unblock_mode", ""):
        command.extend(["--review-unblock-mode", args.review_unblock_mode])
    if getattr(args, "no_review_unblock", False):
        command.append("--no-review-unblock")
    if getattr(args, "patch_swarm", False):
        command.append("--patch-swarm")
        command.extend(["--patch-swarm-candidate-target", str(args.patch_swarm_candidate_target)])
        command.extend(["--patch-swarm-max-parallel-agents", str(args.patch_swarm_max_parallel_agents)])
        command.extend(["--patch-swarm-providers", args.patch_swarm_providers])
    if args.notify_target:
        command.extend(["--notify-target", args.notify_target])
    session = args.session or f"walk-autopilot-{run_id[-16:]}"
    result = subprocess.run(["tmux", "new-session", "-d", "-s", session, shlex.join(command)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        print(result.stderr or result.stdout, file=sys.stderr)
        return result.returncode
    print(json.dumps({"run_id": run_id, "session": session, "command": shlex.join(command), "run_dir": rel(RUN_ROOT / run_id)}, indent=2))
    return 0


def command_status(args: argparse.Namespace) -> int:
    run_dir = RUN_ROOT / args.run_id if args.run_id else sorted(RUN_ROOT.glob("walk-autopilot-*"))[-1]
    payload = {
        "run_id": run_dir.name,
        "run_dir": rel(run_dir),
        "config": read_json(run_dir / "config.json"),
        "spend": spend_summary(run_dir),
        "metrics_records": len(spend_ledger.read_jsonl(run_dir / "metrics.jsonl")),
        "loops": [path.name for path in sorted((run_dir / "loops").glob("loop-*.md"))],
        "incidents": [path.name for path in sorted(path for path in (run_dir / "incidents").glob("*") if path.is_dir())] if (run_dir / "incidents").exists() else [],
        "handoff": rel(run_dir / "handoff.md"),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def command_review_unblock_run(args: argparse.Namespace) -> int:
    run_id = args.run_id or timestamp_id("review-unblock")
    run_dir = REVIEW_UNBLOCK_RUN_ROOT / run_id
    stage = run_review_unblock_stage(run_dir, mode=args.mode)
    mirror_review_unblock_latest(run_dir)
    payload = {
        "status": stage.get("status"),
        "run_id": run_id,
        "run_dir": rel(run_dir),
        "latest_dir": rel(REVIEW_UNBLOCK_LATEST_DIR),
        "decision_report": stage.get("decision_report"),
        "summary": stage.get("summary"),
        "applied_count": stage.get("applied_count", 0),
        "failed_count": stage.get("failed_count", 0),
        "operator_needed_count": stage.get("operator_needed_count", 0),
    }
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else str(payload["decision_report"]))
    return int(stage.get("exit_code") or 0)


def review_unblock_status_payload() -> dict[str, Any]:
    run_dir = latest_review_unblock_run_dir()
    decision = read_json(run_dir / "decision.json") if run_dir else {}
    results = read_json(run_dir / "results.json") if run_dir else {}
    return {
        "schema_version": "cento.review_unblock.status.v1",
        "checked_at": now_iso(),
        "latest_run": rel(run_dir) if run_dir else "",
        "latest_dir": rel(REVIEW_UNBLOCK_LATEST_DIR) if REVIEW_UNBLOCK_LATEST_DIR.exists() else "",
        "decision_summary": as_dict(decision.get("summary")) if isinstance(decision, dict) else {},
        "result_count": len(as_list(results.get("results"))) if isinstance(results, dict) else 0,
        "decision_report": rel(run_dir / "decision_report.md") if run_dir and (run_dir / "decision_report.md").exists() else "",
    }


def command_review_unblock_status(args: argparse.Namespace) -> int:
    payload = review_unblock_status_payload()
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else json.dumps(payload["decision_summary"], sort_keys=True))
    return 0


def command_routing_run(args: argparse.Namespace) -> int:
    run_id = args.run_id or timestamp_id("routing-native")
    run_dir = ROUTING_RUN_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    dirty_before = count_dirty_files()
    raw = collect_routing_raw_counts(args.crontab_file)
    write_json(run_dir / "raw_counts.json", raw)
    dirty_after = count_dirty_files()
    decision = decide_routing_changes(raw, dirty_before=dirty_before, dirty_after=dirty_after)
    write_json(run_dir / "decision.json", decision)
    agent_request = upsert_routing_agent_work(run_dir, decision, no_agent_work=bool(args.no_agent_work))
    write_json(run_dir / "agent_work_request.json", agent_request)
    write_routing_report(run_dir / "decision_report.md", raw, decision, agent_request)
    write_next_iteration(run_dir / "next_iteration.md", decision)
    metrics = {
        "schema_version": "cento.routing_nativeness.metrics.v1",
        "written_at": now_iso(),
        "run_id": run_id,
        "action_count": decision.get("summary", {}).get("action_count", 0),
        "actionable_count": decision.get("summary", {}).get("actionable_count", 0),
        "agent_work_status": agent_request.get("status"),
        "dirty_count_before": dirty_before,
        "dirty_count_after": dirty_after,
        "cron_installed": raw.get("cron", {}).get("installed"),
        "skill_drift_count": raw.get("cento_native_skill_drift", {}).get("drift_count"),
        "codex_error_count": raw.get("codex_observability", {}).get("error_count"),
        "agent_stale_count": raw.get("agent_work", {}).get("stale_count"),
    }
    append_jsonl(run_dir / "metrics.jsonl", metrics)
    mirror_routing_latest(run_dir)
    payload = {
        "status": "completed",
        "run_id": run_id,
        "run_dir": rel(run_dir),
        "latest_dir": rel(ROUTING_LATEST_DIR),
        "decision_report": rel(run_dir / "decision_report.md"),
        "agent_work_request": agent_request,
        "summary": decision.get("summary"),
    }
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else rel(run_dir / "decision_report.md"))
    return 0


def routing_status_payload(crontab_file: str = "") -> dict[str, Any]:
    run_dir = latest_routing_run_dir()
    decision = read_json(run_dir / "decision.json") if run_dir else {}
    agent_request = read_json(run_dir / "agent_work_request.json") if run_dir else {}
    metrics_records = spend_ledger.read_jsonl(run_dir / "metrics.jsonl") if run_dir else []
    return {
        "schema_version": "cento.routing_nativeness.status.v1",
        "checked_at": now_iso(),
        "cron": routing_cron_status(crontab_file),
        "latest_run": rel(run_dir) if run_dir else "",
        "latest_dir": rel(ROUTING_LATEST_DIR) if ROUTING_LATEST_DIR.exists() else "",
        "decision_summary": decision.get("summary") if isinstance(decision.get("summary"), dict) else {},
        "agent_work_request": {
            "status": agent_request.get("status"),
            "issue_id": agent_request.get("issue_id"),
            "story_manifest": agent_request.get("story_manifest"),
        },
        "metrics_records": len(metrics_records),
    }


def command_routing_status(args: argparse.Namespace) -> int:
    payload = routing_status_payload(args.crontab_file)
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else json.dumps(payload["decision_summary"], sort_keys=True))
    return 0


def command_routing_install_cron(args: argparse.Namespace) -> int:
    block = routing_cron_block(args.every_hours)
    current = read_crontab(args.crontab_file)
    stripped = strip_routing_cron_block(current).rstrip()
    updated = (stripped + "\n" if stripped else "") + block
    if not args.dry_run:
        write_crontab(updated, args.crontab_file)
    payload = {
        "status": "planned" if args.dry_run else "installed",
        "dry_run": bool(args.dry_run),
        "every_hours": args.every_hours,
        "schedule": f"0 */{args.every_hours} * * *",
        "cron_installed_before": ROUTING_CRON_BEGIN in current,
        "crontab_file": args.crontab_file,
        "log_path": rel(ROUTING_LOG_PATH),
    }
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else payload["status"])
    return 0


def command_routing_uninstall_cron(args: argparse.Namespace) -> int:
    current = read_crontab(args.crontab_file)
    updated = strip_routing_cron_block(current)
    if not args.dry_run:
        write_crontab(updated, args.crontab_file)
    payload = {
        "status": "planned" if args.dry_run else "uninstalled",
        "dry_run": bool(args.dry_run),
        "cron_installed_before": ROUTING_CRON_BEGIN in current,
        "crontab_file": args.crontab_file,
    }
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else payload["status"])
    return 0


def mirror_patch_swarm_autopilot_latest(run_dir: Path) -> None:
    if PATCH_SWARM_AUTOPILOT_LATEST_DIR.exists() or PATCH_SWARM_AUTOPILOT_LATEST_DIR.is_symlink():
        if PATCH_SWARM_AUTOPILOT_LATEST_DIR.is_dir() and not PATCH_SWARM_AUTOPILOT_LATEST_DIR.is_symlink():
            shutil.rmtree(PATCH_SWARM_AUTOPILOT_LATEST_DIR)
        else:
            PATCH_SWARM_AUTOPILOT_LATEST_DIR.unlink()
    PATCH_SWARM_AUTOPILOT_LATEST_DIR.parent.mkdir(parents=True, exist_ok=True)
    try:
        PATCH_SWARM_AUTOPILOT_LATEST_DIR.symlink_to(run_dir.resolve(), target_is_directory=True)
    except OSError:
        shutil.copytree(run_dir, PATCH_SWARM_AUTOPILOT_LATEST_DIR)


def command_patch_swarm_run(args: argparse.Namespace) -> int:
    run_id = args.run_id or timestamp_id("patch-swarm-autopilot")
    run_dir = PATCH_SWARM_AUTOPILOT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "./scripts/cento.sh",
        "parallel-delivery",
        "patch-swarm",
        "e2e",
        "--run-id",
        run_id,
        "--candidate-target",
        str(args.candidate_target),
        "--max-parallel-agents",
        str(args.max_parallel_agents),
        "--providers",
        args.providers,
        "--fixture",
        "--json",
    ]
    result = run_command(command, timeout=args.timeout)
    record = command_record("parallel-delivery-patch-swarm", result)
    write_json(run_dir / "command_result.json", record)
    try:
        payload = json.loads(str(result.get("stdout_tail") or "{}"))
    except json.JSONDecodeError:
        payload = {}
    summary = {
        "schema_version": "cento.walk_autopilot.patch_swarm.v1",
        "run_id": run_id,
        "written_at": now_iso(),
        "status": payload.get("status") or ("completed" if int(result.get("exit_code") or 1) == 0 else "blocked"),
        "parallel_delivery_run": payload.get("run_dir") or f"workspace/runs/parallel-delivery/patch-swarm/{run_id}",
        "candidate_count": payload.get("candidate_count", 0),
        "selected_count": payload.get("selected_count", 0),
        "estimated_cost_usd": payload.get("estimated_cost_usd", 0.0),
        "safe_integrator_handoff": payload.get("safe_integrator_handoff", ""),
        "ui_state": payload.get("ui_state", ""),
        "decision_report": payload.get("decision_report", ""),
        "command_result": rel(run_dir / "command_result.json"),
    }
    write_json(run_dir / "summary.json", summary)
    (run_dir / "summary.md").write_text(
        "\n".join(
            [
                "# Patch Swarm Autopilot",
                "",
                f"- Run: `{run_id}`",
                f"- Status: `{summary['status']}`",
                f"- Candidates: `{summary['candidate_count']}`",
                f"- Selected: `{summary['selected_count']}`",
                f"- Estimated cost: `${float(summary['estimated_cost_usd'] or 0.0):.6f}`",
                f"- Parallel delivery run: `{summary['parallel_delivery_run']}`",
                f"- UI state: `{summary['ui_state'] or '-'}`",
                f"- Decision report: `{summary['decision_report'] or '-'}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    mirror_patch_swarm_autopilot_latest(run_dir)
    print(json.dumps(summary, indent=2, sort_keys=True) if args.json else rel(run_dir / "summary.md"))
    return 0 if summary["status"] == "completed" else 1


def command_patch_swarm_status(args: argparse.Namespace) -> int:
    if args.run_id:
        run_dir = PATCH_SWARM_AUTOPILOT_ROOT / args.run_id
    else:
        run_dir = PATCH_SWARM_AUTOPILOT_LATEST_DIR if PATCH_SWARM_AUTOPILOT_LATEST_DIR.exists() else None
    summary = read_json(run_dir / "summary.json") if run_dir else {}
    if not summary:
        payload = {"schema_version": "cento.walk_autopilot.patch_swarm.status.v1", "status": "unknown", "latest_run": ""}
    else:
        payload = {"schema_version": "cento.walk_autopilot.patch_swarm.status.v1", "latest_run": rel(run_dir), **summary}
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else json.dumps(payload, sort_keys=True))
    return 0


def factory_scale_install_cron_for_run(run_id: str, *, duration_hours: float | None = None, crontab_file: str = "", dry_run: bool = False) -> dict[str, Any]:
    block = factory_scale_cron_block(run_id, duration_hours)
    current = read_crontab(crontab_file)
    stripped = strip_factory_scale_cron_block(current).rstrip()
    updated = (stripped + "\n" if stripped else "") + block
    if not dry_run:
        write_crontab(updated, crontab_file)
    run_dir = factory_scale_run_dir(run_id)
    config = read_json(run_dir / "config.json")
    schedule = str(config.get("tick_schedule") or "*/12 * * * *")
    cron_payload = {
        "schema_version": "cento.walk_autopilot.factory_scale.cron.v1",
        "written_at": now_iso(),
        "run_id": run_id,
        "status": "planned" if dry_run else "installed",
        "dry_run": bool(dry_run),
        "schedule": schedule,
        "batch_size": int(config.get("batch_size") or 1),
        "lock_name": str(config.get("lock_name") or "factory-scale-final-test.lock"),
        "duration_hours": duration_hours,
        "cron_installed_before": FACTORY_SCALE_CRON_BEGIN in current,
        "crontab_file": crontab_file,
        "log_path": rel(FACTORY_SCALE_LOG_PATH),
        "block": block,
    }
    if run_dir.exists():
        write_json(run_dir / "cron.json", cron_payload)
        (run_dir / "cron.md").write_text(
            "\n".join(
                [
                    "# Factory Scale Cron",
                    "",
                    f"- Status: `{cron_payload['status']}`",
                    f"- Schedule: `{cron_payload['schedule']}`",
                    f"- Batch size: `{cron_payload['batch_size']}`",
                    f"- Log: `{cron_payload['log_path']}`",
                    f"- Crontab file: `{crontab_file or 'system crontab'}`",
                    "",
                    "```cron",
                    block.rstrip(),
                    "```",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        factory_scale_append_event(run_dir, "cron_planned" if dry_run else "cron_installed", {"crontab_file": crontab_file, "schedule": schedule, "batch_size": cron_payload["batch_size"]})
    return cron_payload


def command_factory_scale_start(args: argparse.Namespace) -> int:
    preflight = factory_scale_no_overlap_preflight(args.run_id, args.crontab_file)
    if bool(preflight.get("active")):
        payload = {
            "schema_version": "cento.walk_autopilot.factory_scale.start.v1",
            "status": "attached",
            "reason": "existing active factory-scale/autopilot lane detected; start did not create a duplicate run",
            "preflight": preflight,
            "summary": preflight.get("latest_status") or preflight.get("target_status"),
        }
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else str(payload["reason"]))
        return 0
    run_id = args.run_id or timestamp_id("factory-scale")
    run_dir = factory_scale_run_dir(run_id)
    if not (run_dir / "config.json").exists():
        factory_scale_init_run(run_dir, args)
    cron_payload: dict[str, Any] = {"status": "skipped"}
    if not bool(getattr(args, "no_install_cron", False)):
        cron_payload = factory_scale_install_cron_for_run(
            run_id,
            duration_hours=float(args.duration_hours),
            crontab_file=args.crontab_file,
            dry_run=bool(args.dry_run),
        )
    factory_scale_write_handoff(run_dir)
    payload = {
        "status": "started",
        "run_id": run_id,
        "run_dir": rel(run_dir),
        "config": rel(run_dir / "config.json"),
        "roadmap": rel(run_dir / "roadmap.md"),
        "handoff": rel(run_dir / "handoff.md"),
        "cron": cron_payload,
        "summary": factory_scale_status_payload(run_id, args.crontab_file),
    }
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else rel(run_dir / "handoff.md"))
    return 0


def command_factory_scale_start_day(args: argparse.Namespace) -> int:
    hard_limit = 10_000
    target_calls = int(args.target_proreq_calls)
    max_calls = int(args.max_proreq_calls)
    if target_calls <= 0 or max_calls <= 0:
        print(json.dumps({"status": "blocked", "reason": "target and max ProReq-light calls must be positive"}, indent=2), file=sys.stderr)
        return 2
    if max_calls > hard_limit:
        print(json.dumps({"status": "blocked", "reason": f"--max-proreq-calls cannot exceed {hard_limit}"}, indent=2), file=sys.stderr)
        return 2
    if target_calls > max_calls:
        print(json.dumps({"status": "blocked", "reason": "--target-proreq-calls cannot exceed --max-proreq-calls"}, indent=2), file=sys.stderr)
        return 2
    tick_minutes = max(1, min(59, int(args.tick_minutes)))
    batch_size = max(1, int(args.batch_size))
    proreq_executions = factory_scale_executions_for_call_target(target_calls)
    expected_calls = factory_scale_call_target_for_executions(proreq_executions)
    if expected_calls > max_calls:
        payload = {
            "status": "blocked",
            "reason": "derived ProReq-light command-call count would exceed --max-proreq-calls",
            "target_proreq_calls": target_calls,
            "derived_expected_proreq_calls": expected_calls,
            "max_proreq_calls": max_calls,
        }
        print(json.dumps(payload, indent=2), file=sys.stderr)
        return 2
    preflight = factory_scale_no_overlap_preflight(args.run_id, args.crontab_file)
    if bool(preflight.get("active")):
        payload = {
            "schema_version": "cento.walk_autopilot.factory_scale.day_start.v1",
            "status": "attached",
            "reason": "existing active factory-scale/autopilot lane detected; day start did not create a duplicate run",
            "preflight": preflight,
            "summary": preflight.get("latest_status") or preflight.get("target_status"),
        }
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else str(payload["reason"]))
        return 0

    run_id = args.run_id or timestamp_id("factory-scale-day")
    run_dir = factory_scale_run_dir(run_id)
    day_args = argparse.Namespace(**vars(args))
    day_args.run_id = run_id
    day_args.proreq_executions = proreq_executions
    day_args.min_proreq_calls = target_calls
    day_args.patch_swarm = not bool(getattr(args, "no_patch_swarm", False))
    day_args.patch_swarm_candidate_target = int(args.patch_swarm_candidate_target)
    day_args.patch_swarm_max_parallel_agents = int(args.patch_swarm_max_parallel_agents)
    day_args.execute_proreq = False
    day_args.proreq_command_timeout = int(args.proreq_command_timeout)
    day_args.tick_schedule = f"*/{tick_minutes} * * * *"
    day_args.batch_size = batch_size
    day_args.run_mode = "day-scale"
    day_args.lock_name = "factory-scale-day.lock"
    day_args.target_proreq_calls = target_calls
    day_args.max_proreq_calls = max_calls
    if not (run_dir / "config.json").exists():
        factory_scale_init_run(run_dir, day_args)
    cron_payload: dict[str, Any] = {"status": "skipped"}
    if not bool(getattr(args, "no_install_cron", False)):
        cron_payload = factory_scale_install_cron_for_run(
            run_id,
            duration_hours=float(args.duration_hours),
            crontab_file=args.crontab_file,
            dry_run=bool(args.dry_run),
        )
    factory_scale_write_handoff(run_dir)
    payload = {
        "schema_version": "cento.walk_autopilot.factory_scale.day_start.v1",
        "status": "started",
        "run_id": run_id,
        "run_dir": rel(run_dir),
        "target_proreq_calls": target_calls,
        "max_proreq_calls": max_calls,
        "proreq_executions": proreq_executions,
        "expected_proreq_calls": expected_calls,
        "batch_size": batch_size,
        "tick_schedule": day_args.tick_schedule,
        "expected_patch_swarm_runs": factory_scale_status_payload(run_id, args.crontab_file).get("expected_patch_swarm_runs"),
        "expected_candidate_patch_receipts": factory_scale_status_payload(run_id, args.crontab_file).get("expected_candidate_patch_receipts"),
        "cron": cron_payload,
        "handoff": rel(run_dir / "handoff.md"),
        "summary": factory_scale_status_payload(run_id, args.crontab_file),
    }
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else rel(run_dir / "handoff.md"))
    return 0


def command_factory_scale_preflight(args: argparse.Namespace) -> int:
    payload = factory_scale_no_overlap_preflight(args.run_id, args.crontab_file)
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else payload.get("decision", "unknown"))
    return 0


def command_factory_scale_advance(args: argparse.Namespace) -> int:
    run_dir = factory_scale_run_dir(args.run_id) if args.run_id else latest_factory_scale_run_dir()
    if not run_dir or not run_dir.exists():
        payload = {"schema_version": "cento.walk_autopilot.factory_scale.advance.v1", "status": "unknown", "reason": "no factory-scale run found"}
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    preflight = factory_scale_no_overlap_preflight(run_dir.name, args.crontab_file)
    source_status = as_dict(preflight.get("target_status"))
    if bool(preflight.get("active")):
        payload = {
            "schema_version": "cento.walk_autopilot.factory_scale.advance.v1",
            "status": "attached",
            "reason": "existing active factory-scale/autopilot lane detected; advance did not write derived artifacts",
            "preflight": preflight,
            "summary": source_status,
        }
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else str(payload["reason"]))
        return 0
    if str(source_status.get("status") or "") != "completed" and not bool(getattr(args, "allow_incomplete", False)):
        payload = {
            "schema_version": "cento.walk_autopilot.factory_scale.advance.v1",
            "status": "blocked",
            "reason": "factory-scale advance requires a completed run unless --allow-incomplete is passed",
            "preflight": preflight,
            "summary": source_status,
        }
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else str(payload["reason"]), file=sys.stderr)
        return 2
    live_guard = factory_scale_live_api_guard(args, run_dir)
    payload = factory_scale_write_advance_artifacts(
        run_dir,
        preflight=preflight,
        live_api_guard=live_guard,
        promotion_limit=int(args.promotion_limit),
    )
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else payload["morning_report"])
    return 0


def command_factory_scale_promote(args: argparse.Namespace) -> int:
    run_dir = factory_scale_run_dir(args.run_id) if args.run_id else latest_factory_scale_run_dir()
    if not run_dir or not run_dir.exists():
        payload = {"schema_version": "cento.walk_autopilot.factory_scale.factory_promotion.v1", "status": "unknown", "reason": "no factory-scale run found"}
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    preflight = factory_scale_no_overlap_preflight(run_dir.name, args.crontab_file)
    source_status = as_dict(preflight.get("target_status"))
    if bool(preflight.get("active")):
        payload = {
            "schema_version": "cento.walk_autopilot.factory_scale.factory_promotion.v1",
            "status": "attached",
            "reason": "existing active factory-scale/autopilot lane detected; promotion did not create Factory work",
            "preflight": preflight,
            "summary": source_status,
        }
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else str(payload["reason"]))
        return 0
    if str(source_status.get("status") or "") != "completed" and not bool(getattr(args, "allow_incomplete", False)):
        payload = {
            "schema_version": "cento.walk_autopilot.factory_scale.factory_promotion.v1",
            "status": "blocked",
            "reason": "factory-scale promotion requires a completed run unless --allow-incomplete is passed",
            "preflight": preflight,
            "summary": source_status,
        }
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else str(payload["reason"]), file=sys.stderr)
        return 2
    promotion_plan = resolve_cento_path(args.promotion_plan) if getattr(args, "promotion_plan", "") else None
    payload = factory_scale_promote_to_factory(
        run_dir,
        promotion_plan_path=promotion_plan,
        factory_run=args.factory_run,
        apply=bool(args.apply),
        validate_each=bool(args.validate_each),
        branch=args.branch,
        worktree=args.worktree,
        limit=max(0, int(args.limit or 0)),
        exclusive_paths=bool(args.exclusive_paths),
    )
    if payload.get("status") == "blocked":
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else str(payload.get("reason", "blocked")), file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else str(payload.get("receipt") or payload.get("factory_run_dir")))
    return 0


def factory_scale_tick_once(run_dir: Path, *, cron_lock_conflict: bool = False) -> tuple[dict[str, Any], int]:
    config = read_json(run_dir / "config.json")
    events = spend_ledger.read_jsonl(run_dir / "events.jsonl")
    if cron_lock_conflict:
        factory_scale_append_event(run_dir, "cron_lock_conflict", {"status": "skipped", "reason": "another factory-scale tick holds the flock lock"})
        if events and str(events[-1].get("event") or "") == "cron_lock_conflict":
            factory_scale_append_event(run_dir, "hard_stop", {"reason": "cron lock conflict lasted more than one tick"})
        factory_scale_append_metrics(run_dir, {"tick_result": "cron_lock_conflict"})
        factory_scale_write_handoff(run_dir)
        payload = factory_scale_status_payload(run_dir.name)
        return payload, 0

    if any(str(item.get("event") or "") == "hard_stop" for item in events):
        factory_scale_append_metrics(run_dir, {"tick_result": "already_stopped"})
        factory_scale_write_handoff(run_dir)
        payload = factory_scale_status_payload(run_dir.name)
        return payload, 0

    deadline = parse_iso_datetime(config.get("deadline_at"))
    if deadline and datetime.now(timezone.utc) >= deadline:
        factory_scale_append_event(run_dir, "deadline_reached", {"deadline_at": config.get("deadline_at"), "status": "stopped"})
        factory_scale_append_metrics(run_dir, {"tick_result": "deadline_reached"})
        factory_scale_write_handoff(run_dir)
        payload = factory_scale_status_payload(run_dir.name)
        return payload, 0

    if factory_scale_consecutive_infra_failures(events) >= 2:
        factory_scale_append_event(run_dir, "hard_stop", {"reason": "two consecutive infrastructure failures"})
        factory_scale_append_metrics(run_dir, {"tick_result": "hard_stop"})
        factory_scale_write_handoff(run_dir)
        payload = factory_scale_status_payload(run_dir.name)
        return payload, 0

    execution = factory_scale_next_execution(run_dir)
    if not execution:
        already_recorded = any(str(item.get("event") or "") == "run_complete" for item in events)
        if not already_recorded:
            factory_scale_append_event(run_dir, "run_complete", {"status": "completed"})
            factory_scale_append_metrics(run_dir, {"tick_result": "run_complete"})
        factory_scale_write_handoff(run_dir)
        payload = factory_scale_status_payload(run_dir.name)
        return payload, 0

    before_dirty = count_dirty_files()
    factory_scale_append_event(
        run_dir,
        "tick_started",
        {"execution_id": str(execution["id"]), "execution_index": int(execution.get("index") or 0), "dirty_count_before": before_dirty},
    )
    proreq_result = factory_scale_run_proreq_execution(run_dir, execution, config)
    patch_summary: dict[str, Any] = {}
    if proreq_result.get("status") == "completed" and bool(config.get("patch_swarm_enabled")):
        milestone = factory_scale_milestone_for_execution(run_dir, execution)
        if str(milestone.get("patch_swarm_trigger_after") or "") == str(execution.get("id") or "") and not factory_scale_patch_swarm_already_ran(run_dir, str(milestone.get("id") or "")):
            patch_summary = factory_scale_run_patch_swarm_milestone(run_dir, milestone)

    after_dirty = count_dirty_files()
    if after_dirty != before_dirty:
        factory_scale_append_event(
            run_dir,
            "dirty_count_changed",
            {"dirty_count_before": before_dirty, "dirty_count_after": after_dirty, "matched_ledger_event": True},
        )
    events_after = spend_ledger.read_jsonl(run_dir / "events.jsonl")
    if factory_scale_consecutive_infra_failures(events_after) >= 2:
        factory_scale_append_event(run_dir, "hard_stop", {"reason": "two consecutive infrastructure failures"})
    factory_scale_append_metrics(
        run_dir,
        {
            "tick_result": proreq_result.get("status"),
            "execution_id": str(execution["id"]),
            "dirty_count_before": before_dirty,
            "dirty_count_after": after_dirty,
            "patch_swarm_status": patch_summary.get("status", "not_scheduled"),
            "patch_swarm_candidate_count": patch_summary.get("candidate_count", 0),
        },
    )
    factory_scale_write_handoff(run_dir)
    payload = {
        "status": factory_scale_status_payload(run_dir.name).get("status"),
        "run_id": run_dir.name,
        "run_dir": rel(run_dir),
        "execution": {"id": str(execution["id"]), "status": proreq_result.get("status"), "pipeline_root": proreq_result.get("pipeline_root")},
        "patch_swarm": patch_summary,
        "summary": factory_scale_status_payload(run_dir.name),
    }
    return payload, 0 if proreq_result.get("status") == "completed" else 1


def command_factory_scale_tick(args: argparse.Namespace) -> int:
    if not args.run_id:
        latest = latest_factory_scale_run_dir()
        if not latest:
            print(json.dumps({"status": "unknown", "reason": "no factory-scale run found"}, indent=2), file=sys.stderr)
            return 2
        run_dir = latest
    else:
        run_dir = factory_scale_run_dir(args.run_id)
    if not run_dir.exists():
        print(json.dumps({"status": "unknown", "reason": f"run not found: {run_dir}"}, indent=2), file=sys.stderr)
        return 2
    requested_batch_size = max(1, int(getattr(args, "batch_size", 1)))
    if bool(getattr(args, "cron_lock_conflict", False)):
        requested_batch_size = 1
    ticks: list[dict[str, Any]] = []
    exit_code = 0
    for batch_index in range(1, requested_batch_size + 1):
        payload, tick_exit = factory_scale_tick_once(run_dir, cron_lock_conflict=bool(getattr(args, "cron_lock_conflict", False)))
        payload["batch_index"] = batch_index
        ticks.append(payload)
        if tick_exit != 0:
            exit_code = tick_exit
            break
        summary = as_dict(payload.get("summary")) if isinstance(payload.get("summary"), dict) else payload
        status = str(summary.get("status") or payload.get("status") or "")
        if status in {"completed", "deadline_reached", "stopped"} or not str(summary.get("next_execution_id") or ""):
            break
    summary = factory_scale_status_payload(run_dir.name)
    if requested_batch_size == 1:
        output = ticks[-1] if ticks else summary
    else:
        output = {
            "schema_version": "cento.walk_autopilot.factory_scale.batch_tick.v1",
            "status": summary.get("status"),
            "run_id": run_dir.name,
            "run_dir": rel(run_dir),
            "batch_size_requested": requested_batch_size,
            "batch_size_completed": len(ticks),
            "ticks": ticks,
            "summary": summary,
        }
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(output.get("status", "unknown"))
    return exit_code


def command_factory_scale_status(args: argparse.Namespace) -> int:
    payload = factory_scale_status_payload(args.run_id, args.crontab_file)
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else payload.get("status", "unknown"))
    return 0


def command_factory_scale_install_cron(args: argparse.Namespace) -> int:
    payload = factory_scale_install_cron_for_run(
        args.run_id,
        duration_hours=float(args.duration_hours),
        crontab_file=args.crontab_file,
        dry_run=bool(args.dry_run),
    )
    if factory_scale_run_dir(args.run_id).exists():
        factory_scale_write_handoff(factory_scale_run_dir(args.run_id))
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else payload["status"])
    return 0


def command_factory_scale_uninstall_cron(args: argparse.Namespace) -> int:
    current = read_crontab(args.crontab_file)
    updated = strip_factory_scale_cron_block(current)
    if not args.dry_run:
        write_crontab(updated, args.crontab_file)
    payload = {
        "schema_version": "cento.walk_autopilot.factory_scale.cron_uninstall.v1",
        "status": "planned" if args.dry_run else "uninstalled",
        "dry_run": bool(args.dry_run),
        "cron_installed_before": FACTORY_SCALE_CRON_BEGIN in current,
        "crontab_file": args.crontab_file,
    }
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else payload["status"])
    return 0


def add_common_run_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-id", default="")
    parser.add_argument("--loops", type=int, default=12)
    parser.add_argument("--cadence-seconds", type=int, default=20 * 60)
    parser.add_argument("--soft-cap-usd", type=float, default=12.0)
    parser.add_argument("--hard-cap-usd", type=float, default=20.0)
    parser.add_argument("--max-worker-launch", type=int, default=3)
    parser.add_argument("--live-workers", action="store_true")
    parser.add_argument("--allow-live-api", action="store_true")
    parser.add_argument(
        "--review-unblock-mode",
        choices=("report", "aggressive"),
        default="",
        help="Override Review/Unblock stage mode. Default is report unless --live-workers is enabled.",
    )
    parser.add_argument("--no-review-unblock", action="store_true", help="Skip the Review/Unblock Autopilot stage.")
    parser.add_argument(
        "--dashboard-total-spend-usd",
        type=float,
        default=None,
        help=f"OpenAI dashboard total spend snapshot. Required for --allow-live-api; {DASHBOARD_TOTAL_ENV} is also accepted.",
    )
    parser.add_argument("--notify-target", default="")
    parser.add_argument("--patch-swarm", action="store_true", help="Run one fixture Patch Swarm e2e inside each loop.")
    parser.add_argument("--patch-swarm-candidate-target", type=int, default=100)
    parser.add_argument("--patch-swarm-max-parallel-agents", type=int, default=5)
    parser.add_argument("--patch-swarm-providers", default="codex-exec,claude-code,api-openai")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run append-only Walk Autopilot loops.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run loops in the foreground.")
    add_common_run_args(run)
    run.add_argument("--factory-run-id", default="walk-autopilot-followup")
    run.add_argument("--command-timeout", type=int, default=180)
    run.add_argument("--make-check-timeout", type=int, default=900)
    run.add_argument("--make-check-every", type=int, default=2)
    run.add_argument("--proreq-timeout", type=int, default=900)
    run.add_argument("--dashboard-delta-usd", type=float, default=0.0)
    run.set_defaults(func=command_run)

    tmux_cmd = sub.add_parser("start-tmux", help="Start the loop in a detached tmux session.")
    add_common_run_args(tmux_cmd)
    tmux_cmd.add_argument("--session", default="")
    tmux_cmd.set_defaults(func=command_start_tmux)

    status = sub.add_parser("status", help="Show latest or named walk autopilot status.")
    status.add_argument("--run-id", default="")
    status.set_defaults(func=command_status)

    review_unblock = sub.add_parser("review-unblock", help="Scan Agent Work review, blocked, and stale states and choose safe recovery actions.")
    review_unblock_sub = review_unblock.add_subparsers(dest="review_unblock_command", required=True)

    review_unblock_run = review_unblock_sub.add_parser("run", help="Run one Review/Unblock decision pass.")
    review_unblock_run.add_argument("--run-id", default="")
    review_unblock_run.add_argument("--mode", choices=("report", "aggressive"), default="report")
    review_unblock_run.add_argument("--json", action="store_true")
    review_unblock_run.set_defaults(func=command_review_unblock_run)

    review_unblock_status = review_unblock_sub.add_parser("status", help="Show latest Review/Unblock run status.")
    review_unblock_status.add_argument("--json", action="store_true")
    review_unblock_status.set_defaults(func=command_review_unblock_status)

    patch_swarm = sub.add_parser("patch-swarm", help="Coordinate Patch Swarm dry-run e2e through Walk Autopilot artifacts.")
    patch_swarm_sub = patch_swarm.add_subparsers(dest="patch_swarm_command", required=True)

    patch_swarm_run = patch_swarm_sub.add_parser("run", help="Run one fixture Patch Swarm e2e and write autopilot summary artifacts.")
    patch_swarm_run.add_argument("--run-id", default="")
    patch_swarm_run.add_argument("--candidate-target", type=int, default=100)
    patch_swarm_run.add_argument("--max-parallel-agents", type=int, default=5)
    patch_swarm_run.add_argument("--providers", default="codex-exec,claude-code,api-openai")
    patch_swarm_run.add_argument("--timeout", type=int, default=360)
    patch_swarm_run.add_argument("--json", action="store_true")
    patch_swarm_run.set_defaults(func=command_patch_swarm_run)

    patch_swarm_status = patch_swarm_sub.add_parser("status", help="Show latest Patch Swarm autopilot summary.")
    patch_swarm_status.add_argument("--run-id", default="")
    patch_swarm_status.add_argument("--json", action="store_true")
    patch_swarm_status.set_defaults(func=command_patch_swarm_status)

    factory_scale = sub.add_parser("factory-scale", help="Run the six-hour Factory scale final test coordinator.")
    factory_scale_sub = factory_scale.add_subparsers(dest="factory_scale_command", required=True)

    factory_scale_start = factory_scale_sub.add_parser("start", help="Initialize and schedule the Factory scale final test run.")
    factory_scale_start.add_argument("--run-id", default="")
    factory_scale_start.add_argument("--duration-hours", type=float, default=6.0)
    factory_scale_start.add_argument("--proreq-executions", type=int, default=30)
    factory_scale_start.add_argument("--min-proreq-calls", type=int, default=100)
    factory_scale_start.add_argument("--patch-swarm", action="store_true")
    factory_scale_start.add_argument("--execute-proreq", action="store_true", help="Run ProReq-light commands instead of ledgering the API-safe command calls.")
    factory_scale_start.add_argument("--proreq-command-timeout", type=int, default=900)
    factory_scale_start.add_argument("--crontab-file", default=os.environ.get("CENTO_FACTORY_SCALE_CRONTAB_PATH", ""))
    factory_scale_start.add_argument("--no-install-cron", action="store_true", help="Initialize artifacts without installing the managed cron block.")
    factory_scale_start.add_argument("--dry-run", action="store_true", help="Plan cron installation without writing crontab.")
    factory_scale_start.add_argument("--json", action="store_true")
    factory_scale_start.set_defaults(func=command_factory_scale_start)

    factory_scale_start_day = factory_scale_sub.add_parser("start-day", help="Initialize and schedule the day-scale Factory autopilot run.")
    factory_scale_start_day.add_argument("--run-id", default="")
    factory_scale_start_day.add_argument("--target-proreq-calls", type=int, default=3000)
    factory_scale_start_day.add_argument("--max-proreq-calls", type=int, default=10000)
    factory_scale_start_day.add_argument("--duration-hours", type=float, default=12.0)
    factory_scale_start_day.add_argument("--tick-minutes", type=int, default=10)
    factory_scale_start_day.add_argument("--batch-size", type=int, default=5)
    factory_scale_start_day.add_argument("--patch-swarm-candidate-target", type=int, default=100)
    factory_scale_start_day.add_argument("--patch-swarm-max-parallel-agents", type=int, default=5)
    factory_scale_start_day.add_argument("--no-patch-swarm", action="store_true", help="Disable Patch Swarm fixture milestones for the day-scale run.")
    factory_scale_start_day.add_argument("--proreq-command-timeout", type=int, default=900)
    factory_scale_start_day.add_argument("--crontab-file", default=os.environ.get("CENTO_FACTORY_SCALE_CRONTAB_PATH", ""))
    factory_scale_start_day.add_argument("--no-install-cron", action="store_true", help="Initialize day-scale artifacts without installing the managed cron block.")
    factory_scale_start_day.add_argument("--dry-run", action="store_true", help="Plan cron installation without writing crontab.")
    factory_scale_start_day.add_argument("--json", action="store_true")
    factory_scale_start_day.set_defaults(func=command_factory_scale_start_day)

    factory_scale_preflight = factory_scale_sub.add_parser("preflight", help="Check for active Factory scale lanes before starting or advancing.")
    factory_scale_preflight.add_argument("--run-id", default="")
    factory_scale_preflight.add_argument("--crontab-file", default=os.environ.get("CENTO_FACTORY_SCALE_CRONTAB_PATH", ""))
    factory_scale_preflight.add_argument("--json", action="store_true")
    factory_scale_preflight.set_defaults(func=command_factory_scale_preflight)

    factory_scale_advance = factory_scale_sub.add_parser("advance", help="Index completed Factory scale receipts and write Safe Integrator promotion artifacts.")
    factory_scale_advance.add_argument("--run-id", default="")
    factory_scale_advance.add_argument("--promotion-limit", type=int, default=25)
    factory_scale_advance.add_argument("--allow-incomplete", action="store_true")
    factory_scale_advance.add_argument("--allow-live-api", action="store_true")
    factory_scale_advance.add_argument("--dashboard-total-spend-usd", type=float, default=None)
    factory_scale_advance.add_argument("--hard-cap-usd", type=float, default=25.0)
    factory_scale_advance.add_argument("--max-live-calls-per-hour", type=int, default=4)
    factory_scale_advance.add_argument("--min-live-call-spacing-seconds", type=int, default=900)
    factory_scale_advance.add_argument("--crontab-file", default=os.environ.get("CENTO_FACTORY_SCALE_CRONTAB_PATH", ""))
    factory_scale_advance.add_argument("--json", action="store_true")
    factory_scale_advance.set_defaults(func=command_factory_scale_advance)

    factory_scale_promote = factory_scale_sub.add_parser("promote", help="Promote factory-scale advance candidates into a Factory validation run.")
    factory_scale_promote.add_argument("--run-id", default="")
    factory_scale_promote.add_argument("--promotion-plan", default="")
    factory_scale_promote.add_argument("--factory-run", default="")
    factory_scale_promote.add_argument("--limit", type=int, default=25)
    factory_scale_promote.add_argument("--exclusive-paths", action="store_true", default=True, help="Skip candidates that touch paths already selected in this promotion batch.")
    factory_scale_promote.add_argument("--allow-path-overlap", dest="exclusive_paths", action="store_false", help="Allow Factory to reject overlapping owned paths instead of filtering them first.")
    factory_scale_promote.add_argument("--apply", action="store_true", help="Apply through Factory/Safe Integrator worktree after fanout validation.")
    factory_scale_promote.add_argument("--validate-each", action="store_true", help="Run candidate validation after each Safe Integrator apply.")
    factory_scale_promote.add_argument("--branch", default="")
    factory_scale_promote.add_argument("--worktree", default="")
    factory_scale_promote.add_argument("--allow-incomplete", action="store_true")
    factory_scale_promote.add_argument("--crontab-file", default=os.environ.get("CENTO_FACTORY_SCALE_CRONTAB_PATH", ""))
    factory_scale_promote.add_argument("--json", action="store_true")
    factory_scale_promote.set_defaults(func=command_factory_scale_promote)

    factory_scale_tick = factory_scale_sub.add_parser("tick", help="Run one Factory scale tick.")
    factory_scale_tick.add_argument("--run-id", default="")
    factory_scale_tick.add_argument("--batch-size", type=int, default=1)
    factory_scale_tick.add_argument("--cron-lock-conflict", action="store_true", help=argparse.SUPPRESS)
    factory_scale_tick.add_argument("--json", action="store_true")
    factory_scale_tick.set_defaults(func=command_factory_scale_tick)

    factory_scale_status = factory_scale_sub.add_parser("status", help="Show log-derived Factory scale final test status.")
    factory_scale_status.add_argument("--run-id", default="")
    factory_scale_status.add_argument("--crontab-file", default=os.environ.get("CENTO_FACTORY_SCALE_CRONTAB_PATH", ""))
    factory_scale_status.add_argument("--json", action="store_true")
    factory_scale_status.set_defaults(func=command_factory_scale_status)

    factory_scale_install = factory_scale_sub.add_parser("install-cron", help="Install the marked Factory scale cron block.")
    factory_scale_install.add_argument("--run-id", required=True)
    factory_scale_install.add_argument("--duration-hours", type=float, default=6.0)
    factory_scale_install.add_argument("--crontab-file", default=os.environ.get("CENTO_FACTORY_SCALE_CRONTAB_PATH", ""))
    factory_scale_install.add_argument("--dry-run", action="store_true")
    factory_scale_install.add_argument("--json", action="store_true")
    factory_scale_install.set_defaults(func=command_factory_scale_install_cron)

    factory_scale_uninstall = factory_scale_sub.add_parser("uninstall-cron", help="Remove the marked Factory scale cron block.")
    factory_scale_uninstall.add_argument("--crontab-file", default=os.environ.get("CENTO_FACTORY_SCALE_CRONTAB_PATH", ""))
    factory_scale_uninstall.add_argument("--dry-run", action="store_true")
    factory_scale_uninstall.add_argument("--json", action="store_true")
    factory_scale_uninstall.set_defaults(func=command_factory_scale_uninstall_cron)

    routing = sub.add_parser("routing", help="Run and manage the lightweight routing nativeness loop.")
    routing_sub = routing.add_subparsers(dest="routing_command", required=True)

    routing_run = routing_sub.add_parser("run", help="Collect counts-only routing stats, decide changes, and hand off bounded work.")
    routing_run.add_argument("--run-id", default="")
    routing_run.add_argument("--crontab-file", default=os.environ.get("CENTO_ROUTING_CRONTAB_PATH", ""))
    routing_run.add_argument("--no-agent-work", action="store_true", help="Write reports without creating or updating Agent Work.")
    routing_run.add_argument("--json", action="store_true")
    routing_run.set_defaults(func=command_routing_run)

    routing_status = routing_sub.add_parser("status", help="Show latest routing nativeness run and cron status.")
    routing_status.add_argument("--crontab-file", default=os.environ.get("CENTO_ROUTING_CRONTAB_PATH", ""))
    routing_status.add_argument("--json", action="store_true")
    routing_status.set_defaults(func=command_routing_status)

    routing_install = routing_sub.add_parser("install-cron", help="Install the marked routing nativeness cron block.")
    routing_install.add_argument("--every-hours", type=int, default=4)
    routing_install.add_argument("--crontab-file", default=os.environ.get("CENTO_ROUTING_CRONTAB_PATH", ""))
    routing_install.add_argument("--dry-run", action="store_true")
    routing_install.add_argument("--json", action="store_true")
    routing_install.set_defaults(func=command_routing_install_cron)

    routing_uninstall = routing_sub.add_parser("uninstall-cron", help="Remove the marked routing nativeness cron block.")
    routing_uninstall.add_argument("--crontab-file", default=os.environ.get("CENTO_ROUTING_CRONTAB_PATH", ""))
    routing_uninstall.add_argument("--dry-run", action="store_true")
    routing_uninstall.add_argument("--json", action="store_true")
    routing_uninstall.set_defaults(func=command_routing_uninstall_cron)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
