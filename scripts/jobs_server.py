#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import mimetypes
import socket
import sys
import os
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
EXPLICIT_RUN_ROOT = "CENTO_CLUSTER_JOBS_ROOT" in os.environ
RUN_ROOT = Path(os.environ.get("CENTO_CLUSTER_JOBS_ROOT", ROOT_DIR / "workspace" / "runs" / "cluster-jobs"))
TEMPLATE_DIR = ROOT_DIR / "templates" / "jobs-web"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 47883
PORT_SPAN = 20


class NetworkWebError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Cento cluster jobs web dashboard.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Bind host. Default: {DEFAULT_HOST}")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Preferred port. Default: {DEFAULT_PORT}")
    parser.add_argument("--open", action="store_true", help="Open the dashboard in the default browser.")
    return parser.parse_args()


def find_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + PORT_SPAN):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise NetworkWebError(f"Could not bind a free port in range {preferred}-{preferred + PORT_SPAN - 1}.")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise NetworkWebError(f"Missing JSON file: {path}") from None
    except json.JSONDecodeError as exc:
        raise NetworkWebError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise NetworkWebError(f"JSON root must be an object: {path}")
    return payload


def recent_log_tail(path: Path, limit: int = 30) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-limit:]


def normalize_status(value: Any) -> str:
    status = str(value or "").strip().lower().replace("_", "-")
    return status or "unknown"


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def age_label(dt: datetime | None, now: datetime | None = None) -> str:
    if not dt:
        return "unknown"
    current = now or datetime.now().astimezone()
    if dt.tzinfo is None:
        dt = dt.astimezone()
    seconds = max(0, int((current - dt.astimezone(current.tzinfo)).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def first_line(value: Any) -> str:
    for line in str(value or "").splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def latest_log_for_job(job: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    candidates: list[Path] = []
    for result in job.get("results", []):
        if isinstance(result, dict) and result.get("log"):
            candidates.append(Path(str(result["log"])))
    log_dir = run_dir / "logs"
    if log_dir.exists():
        candidates.extend(path for path in log_dir.glob("*.log") if path.is_file())
    existing = [path for path in candidates if path.exists() and path.is_file()]
    if not existing:
        return {"path": "", "exists": False, "tail": []}
    latest = max(existing, key=lambda path: path.stat().st_mtime)
    return {"path": str(latest), "exists": True, "tail": recent_log_tail(latest, limit=8)}


def current_step(job: dict[str, Any]) -> str:
    tasks = [task for task in job.get("tasks", []) if isinstance(task, dict)]
    results = {item.get("task"): item for item in job.get("results", []) if isinstance(item, dict)}
    for task in tasks:
        task_id = task.get("id", "")
        if task_id and task_id not in results:
            return str(task.get("title") or task_id)
    if tasks:
        return str(tasks[-1].get("title") or tasks[-1].get("id") or "tasks complete")
    return "no tasks"


def job_summary(job: dict[str, Any], run_dir: Path, job_path: Path, now: datetime | None = None) -> dict[str, Any]:
    status = normalize_status(job.get("status"))
    summary_path = Path(job.get("artifacts", {}).get("summary") or run_dir / "summary.md")
    latest_log = latest_log_for_job(job, run_dir)
    updated_at = parse_time(job.get("finished_at")) or parse_time(job.get("updated_at")) or parse_time(job.get("created_at"))
    if not updated_at:
        updated_at = datetime.fromtimestamp(job_path.stat().st_mtime).astimezone()
    tasks = [task for task in job.get("tasks", []) if isinstance(task, dict)]
    results = [result for result in job.get("results", []) if isinstance(result, dict)]
    failed_results = [result for result in results if result.get("returncode") not in (0, None)]
    degraded_reasons: list[str] = []
    if status in {"failed", "error", "invalid", "unknown"}:
        degraded_reasons.append(f"status={status}")
    if failed_results:
        degraded_reasons.append(f"{len(failed_results)} failed task result(s)")
    if tasks and not results and status not in {"planned", "queued", "dry-run"}:
        degraded_reasons.append("tasks have no results")
    if not latest_log["exists"] and status in {"running", "failed", "succeeded"}:
        degraded_reasons.append("latest log missing")
    return {
        "id": job.get("id") or job_path.parent.name,
        "status": status,
        "feature": first_line(job.get("feature")),
        "task_count": len(tasks),
        "result_count": len(results),
        "failed_task_count": len(failed_results),
        "summary_exists": summary_path.exists(),
        "updated_at": updated_at.isoformat(timespec="seconds"),
        "updated_age": age_label(updated_at, now),
        "current_step": current_step(job),
        "latest_log": latest_log,
        "state": "degraded" if degraded_reasons else ("empty" if not tasks else "ok"),
        "degraded_reasons": degraded_reasons,
    }


def task_details(job: dict[str, Any], run_dir: Path) -> list[dict[str, Any]]:
    results = {item.get("task"): item for item in job.get("results", []) if isinstance(item, dict)}
    details = []
    for task in job.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = task.get("id", "")
        result = results.get(task_id, {})
        log_path = Path(result.get("log") or run_dir / "logs" / f"{task_id}.log")
        script_path = run_dir / "tasks" / f"{task_id}.sh"
        prompt_path = run_dir / "tasks" / f"{task_id}.json"
        details.append(
            {
                "id": task_id,
                "node": task.get("node", ""),
                "title": task.get("title", ""),
                "scope": task.get("scope", ""),
                "ownership": task.get("ownership", []),
                "returncode": result.get("returncode"),
                "elapsed_seconds": result.get("elapsed_seconds"),
                "log": str(log_path),
                "log_exists": log_path.exists(),
                "log_tail": recent_log_tail(log_path),
                "script": str(script_path),
                "script_exists": script_path.exists(),
                "manifest": str(prompt_path),
                "manifest_exists": prompt_path.exists(),
            }
        )
    return details


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_jsonl_tail(path: Path, limit: int = 4) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows[-limit:]


def latest_file_time(*paths: Path) -> datetime:
    latest: datetime | None = None
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        stamp = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
        if latest is None or stamp > latest:
            latest = stamp
    return latest or datetime.now().astimezone()


def first_existing_path(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists() and path.is_file():
            return path
    return None


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def first_int(*values: Any) -> int:
    for value in values:
        parsed = int_value(value)
        if parsed:
            return parsed
    return 0


def progress_label(label: str, done: int, total: int) -> str:
    return f"{label} {done}/{total}" if total else f"{label} {done}"


def live_task(task_id: str, title: str, status: str, *, node: str = "local", log: Path | None = None) -> dict[str, Any]:
    normalized = normalize_status(status)
    returncode: int | None
    if normalized in {"completed", "succeeded", "success", "done"}:
        returncode = 0
    elif normalized in {"failed", "error", "invalid"}:
        returncode = 1
    else:
        returncode = None
    return {
        "id": task_id,
        "node": node,
        "title": title,
        "scope": "",
        "ownership": [],
        "returncode": returncode,
        "elapsed_seconds": None,
        "log": str(log) if log else "",
        "log_exists": bool(log and log.exists()),
        "log_tail": recent_log_tail(log, limit=4) if log else [],
        "script": "",
        "script_exists": False,
        "manifest": "",
        "manifest_exists": False,
    }


def autopilot_jobs(now: datetime) -> list[dict[str, Any]]:
    root = Path(os.environ.get("CENTO_WALK_AUTOPILOT_ROOT", ROOT_DIR / "workspace" / "runs" / "walk-autopilot"))
    if not root.exists() or not root.is_dir():
        return []
    jobs: list[dict[str, Any]] = []
    for run_dir in root.iterdir():
        if not run_dir.is_dir():
            continue
        metrics_path = run_dir / "metrics.jsonl"
        events_path = run_dir / "events.jsonl"
        if not metrics_path.exists() and not events_path.exists():
            continue
        metrics = read_jsonl_tail(metrics_path, 1)
        events = read_jsonl_tail(events_path, 1)
        metric = metrics[-1] if metrics else {}
        event = events[-1] if events else {}
        config = read_json_if_exists(run_dir / "config.json")
        manifest = read_json_if_exists(run_dir / "execution-manifest.json")
        updated_at = latest_file_time(metrics_path, events_path, run_dir / "handoff.md", run_dir / "factory_promotion.json")
        for payload in (event, metric):
            parsed = parse_time(payload.get("written_at"))
            if parsed and parsed > updated_at:
                updated_at = parsed
        status = normalize_status(metric.get("status") or event.get("status"))
        event_name = str(event.get("event") or "progress")
        event_status = normalize_status(event.get("status"))
        degraded_reasons: list[str] = []
        if "failed" in event_status or event_status == "error":
            status = "failed"
            degraded_reasons.append(f"{event_name}={event_status}")
        if event_name == "hard_stop":
            status = "failed"
        completed_exec = int_value(metric.get("completed_proreq_executions") or event.get("execution_index"))
        expected_exec = first_int(manifest.get("proreq_execution_count"), config.get("proreq_execution_count"))
        completed_calls = int_value(metric.get("proreq_call_count"))
        expected_calls = first_int(manifest.get("expected_proreq_call_count"), config.get("target_proreq_calls"), config.get("min_proreq_calls"))
        completed_swarm = int_value(metric.get("patch_swarm_runs"))
        expected_swarm = first_int(manifest.get("patch_swarm_milestone_count"), config.get("expected_patch_swarm_runs"))
        completed_receipts = int_value(metric.get("candidate_patch_receipts"))
        expected_receipts = first_int(manifest.get("expected_candidate_patch_receipts"), config.get("expected_candidate_patch_receipts"))
        if event_status and event_status != "unknown":
            step = f"{event_name.replace('_', ' ')}: {event_status.replace('-', ' ')}"
        elif expected_exec:
            step = f"executions {completed_exec}/{expected_exec} · calls {completed_calls}/{expected_calls} · patch swarm {completed_swarm}/{expected_swarm}"
        else:
            step = event_name.replace("_", " ")
        latest_log = first_existing_path(events_path, metrics_path)
        summary_path = run_dir / "handoff.md"
        summary = {
            "id": run_dir.name,
            "status": status,
            "feature": f"Factory scale autopilot ({config.get('run_mode') or 'walk'})",
            "task_count": max(completed_exec, expected_exec),
            "result_count": completed_exec,
            "failed_task_count": 1 if degraded_reasons else 0,
            "summary_exists": summary_path.exists(),
            "updated_at": updated_at.isoformat(timespec="seconds"),
            "updated_age": age_label(updated_at, now),
            "current_step": step,
            "latest_log": {
                "path": str(latest_log or ""),
                "exists": bool(latest_log),
                "tail": recent_log_tail(latest_log, limit=4) if latest_log else [],
            },
            "state": "degraded" if degraded_reasons or status == "failed" else "ok",
            "degraded_reasons": degraded_reasons,
        }
        jobs.append(
            {
                "id": run_dir.name,
                "source": "walk-autopilot",
                "status": status,
                "feature": summary["feature"],
                "created_at": str(config.get("created_at") or ""),
                "finished_at": "",
                "updated_at": summary["updated_at"],
                "updated_age": summary["updated_age"],
                "repo": str(ROOT_DIR),
                "run_dir": str(run_dir),
                "job": str(run_dir / "config.json"),
                "summary": str(summary_path),
                "job_summary": summary,
                "summary_exists": summary_path.exists(),
                "agent_command": f"cento walk-autopilot factory-scale status --run-id {run_dir.name} --json",
                "tasks": [
                    live_task("proreq", progress_label("ProReq calls", completed_calls, expected_calls), status, log=latest_log),
                    live_task("executions", progress_label("ProReq executions", completed_exec, expected_exec), status, log=latest_log),
                    live_task("patch-swarm", progress_label("Patch Swarm runs", completed_swarm, expected_swarm), status, log=latest_log),
                    live_task("receipts", progress_label("Candidate receipts", completed_receipts, expected_receipts), status, log=latest_log),
                ],
            }
        )
    return jobs


def factory_feature(plan: dict[str, Any], queue: dict[str, Any]) -> str:
    request = plan.get("request") if isinstance(plan.get("request"), dict) else {}
    for value in (request.get("raw"), plan.get("feature"), plan.get("package"), queue.get("package")):
        line = first_line(value)
        if line:
            return line
    return "Factory run"


def factory_jobs(now: datetime) -> list[dict[str, Any]]:
    root = Path(os.environ.get("CENTO_FACTORY_RUNS_ROOT", ROOT_DIR / "workspace" / "runs" / "factory"))
    if not root.exists() or not root.is_dir():
        return []
    jobs: list[dict[str, Any]] = []
    for run_dir in root.iterdir():
        if not run_dir.is_dir() or not (run_dir / "factory-plan.json").exists():
            continue
        plan = read_json_if_exists(run_dir / "factory-plan.json")
        queue = read_json_if_exists(run_dir / "queue" / "state.json") or read_json_if_exists(run_dir / "queue" / "queue.json")
        validation = read_json_if_exists(run_dir / "integration" / "validation-fanout.json")
        integration = read_json_if_exists(run_dir / "integration" / "integration-state.json")
        stats = queue.get("stats") if isinstance(queue.get("stats"), dict) else {}
        updated_at = latest_file_time(
            run_dir / "factory-plan.json",
            run_dir / "summary.md",
            run_dir / "queue" / "state.json",
            run_dir / "queue" / "events.jsonl",
            run_dir / "integration" / "validation-fanout.json",
            run_dir / "integration" / "integration-state.json",
        )
        for payload in (validation, integration):
            for key in ("generated_at", "updated_at"):
                parsed = parse_time(payload.get(key))
                if parsed and parsed > updated_at:
                    updated_at = parsed
        total = int_value(stats.get("total"))
        tasks_map = queue.get("tasks") if isinstance(queue.get("tasks"), dict) else {}
        if not total:
            total = len(tasks_map) or len(plan.get("tasks") or [])
        status = "queued" if int_value(stats.get("queued")) or int_value(stats.get("waiting")) else "succeeded"
        if int_value(stats.get("running")) or int_value(stats.get("leased")) or int_value(stats.get("validating")):
            status = "running"
        if normalize_status(validation.get("status")) in {"failed", "error", "invalid"}:
            status = "failed"
        failed = int_value(stats.get("blocked")) + int_value(stats.get("deadletter")) + int_value(validation.get("failed_count"))
        if failed:
            status = "failed"
        if status == "succeeded" and total and not validation and not (int_value(stats.get("done")) + int_value(stats.get("integrated"))):
            status = "planned"
        reasons: list[str] = []
        if int_value(validation.get("failed_count")):
            reasons.append(f"{int_value(validation.get('failed_count'))} validation failure(s)")
        if int_value(stats.get("blocked")):
            reasons.append(f"{int_value(stats.get('blocked'))} blocked task(s)")
        readiness = integration.get("merge_readiness") if isinstance(integration.get("merge_readiness"), dict) else {}
        for blocker in readiness.get("blockers") or []:
            reasons.append(str(blocker))
            if len(reasons) >= 3:
                break
        if validation:
            step = f"validation fanout {normalize_status(validation.get('status'))} · {int_value(validation.get('passed_count'))} passed / {int_value(validation.get('failed_count'))} failed"
        else:
            step = f"queued {int_value(stats.get('queued'))} · running {int_value(stats.get('running')) + int_value(stats.get('validating'))} · done {int_value(stats.get('done')) + int_value(stats.get('integrated'))} / {total}"
        latest_log = first_existing_path(run_dir / "queue" / "events.jsonl", run_dir / "integration" / "validation-fanout.json")
        summary_path = run_dir / "summary.md"
        summary = {
            "id": run_dir.name,
            "status": status,
            "feature": factory_feature(plan, queue),
            "task_count": total,
            "result_count": int_value(stats.get("done")) + int_value(stats.get("integrated")) + int_value(validation.get("passed_count")),
            "failed_task_count": failed,
            "summary_exists": summary_path.exists(),
            "updated_at": updated_at.isoformat(timespec="seconds"),
            "updated_age": age_label(updated_at, now),
            "current_step": step,
            "latest_log": {
                "path": str(latest_log or ""),
                "exists": bool(latest_log),
                "tail": recent_log_tail(latest_log, limit=4) if latest_log else [],
            },
            "state": "degraded" if reasons or status == "failed" else ("empty" if total == 0 else "ok"),
            "degraded_reasons": reasons,
        }
        task_rows = []
        for task_id in sorted(tasks_map)[:8]:
            task = tasks_map[task_id] if isinstance(tasks_map[task_id], dict) else {}
            task_rows.append(live_task(str(task.get("task_id") or task_id), str(task.get("title") or ""), normalize_status(task.get("status")), node=str(task.get("node") or "local"), log=latest_log))
        jobs.append(
            {
                "id": run_dir.name,
                "source": "factory",
                "status": status,
                "feature": summary["feature"],
                "created_at": str(plan.get("created_at") or ""),
                "finished_at": "",
                "updated_at": summary["updated_at"],
                "updated_age": summary["updated_age"],
                "repo": str(ROOT_DIR),
                "run_dir": str(run_dir),
                "job": str(run_dir / "factory-plan.json"),
                "summary": str(summary_path),
                "job_summary": summary,
                "summary_exists": summary_path.exists(),
                "agent_command": f"cento factory status {run_dir} --json",
                "tasks": task_rows,
            }
        )
    return jobs


def load_jobs() -> dict[str, Any]:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    jobs = []
    counts: dict[str, int] = {}
    states: dict[str, int] = {}
    current_time = datetime.now().astimezone()
    for job_path in sorted(RUN_ROOT.glob("*/job.json"), key=lambda path: path.stat().st_mtime, reverse=True):
        try:
            job = read_json(job_path)
        except NetworkWebError as exc:
            summary = {
                "id": job_path.parent.name,
                "status": "invalid",
                "feature": str(exc),
                "task_count": 0,
                "result_count": 0,
                "failed_task_count": 0,
                "updated_at": datetime.fromtimestamp(job_path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
                "updated_age": age_label(datetime.fromtimestamp(job_path.stat().st_mtime).astimezone(), current_time),
                "current_step": "invalid job.json",
                "latest_log": {"path": "", "exists": False, "tail": []},
                "state": "degraded",
                "degraded_reasons": [str(exc)],
            }
            counts["invalid"] = counts.get("invalid", 0) + 1
            states["degraded"] = states.get("degraded", 0) + 1
            jobs.append(
                {
                    "id": job_path.parent.name,
                    "status": "invalid",
                    "error": str(exc),
                    "path": str(job_path),
                    "summary": summary,
                    "job_summary": summary,
                }
            )
            continue
        run_dir = Path(job.get("run_dir") or job_path.parent)
        summary = Path(job.get("artifacts", {}).get("summary") or run_dir / "summary.md")
        normalized = job_summary(job, run_dir, job_path, current_time)
        counts[normalized["status"]] = counts.get(normalized["status"], 0) + 1
        states[normalized["state"]] = states.get(normalized["state"], 0) + 1
        jobs.append(
            {
                "id": job.get("id", job_path.parent.name),
                "source": "cluster-jobs",
                "status": normalized["status"],
                "feature": normalized["feature"],
                "created_at": job.get("created_at", ""),
                "finished_at": job.get("finished_at", ""),
                "updated_at": normalized["updated_at"],
                "updated_age": normalized["updated_age"],
                "repo": job.get("repo", ""),
                "run_dir": str(run_dir),
                "job": str(job_path),
                "summary": str(summary),
                "job_summary": normalized,
                "summary_exists": summary.exists(),
                "agent_command": job.get("agent_command", ""),
                "tasks": task_details(job, run_dir),
            }
        )
    if not EXPLICIT_RUN_ROOT or os.environ.get("CENTO_INDUSTRIAL_JOBS_INCLUDE_LIVE") == "1":
        jobs.extend(autopilot_jobs(current_time))
        jobs.extend(factory_jobs(current_time))
    counts = {}
    states = {}
    for job in jobs:
        summary = job.get("job_summary") if isinstance(job.get("job_summary"), dict) else {}
        status = normalize_status(summary.get("status") or job.get("status"))
        state = str(summary.get("state") or "unknown")
        counts[status] = counts.get(status, 0) + 1
        states[state] = states.get(state, 0) + 1
    jobs.sort(key=lambda item: parse_time((item.get("job_summary") or {}).get("updated_at")) or datetime.fromtimestamp(0).astimezone(), reverse=True)
    return {
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "run_root": str(RUN_ROOT),
        "state": "empty" if not jobs else ("degraded" if states.get("degraded") else "ok"),
        "counts": counts,
        "states": states,
        "jobs": jobs,
    }


def safe_static_path(raw_path: str) -> Path:
    route = raw_path.split("?", 1)[0].split("#", 1)[0]
    if route in ("", "/"):
        route = "/index.html"
    relative = route.lstrip("/")
    path = (TEMPLATE_DIR / relative).resolve()
    template_root = TEMPLATE_DIR.resolve()
    if template_root not in path.parents and path != template_root:
        raise NetworkWebError("Invalid static path.")
    return path


def make_handler() -> type[BaseHTTPRequestHandler]:
    class NetworkHandler(BaseHTTPRequestHandler):
        server_version = "cento-jobs-web/1.0"

        def log_message(self, fmt: str, *args: object) -> None:
            print(f"{self.address_string()} - {fmt % args}", file=sys.stderr)

        def send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_static(self, path: Path, include_body: bool = True) -> None:
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if include_body:
                self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path.startswith("/api/jobs"):
                self.send_json(200, load_jobs())
                return
            try:
                path = safe_static_path(self.path)
            except NetworkWebError as exc:
                self.send_json(400, {"error": str(exc)})
                return
            if not path.exists() or not path.is_file():
                self.send_json(404, {"error": "Not found."})
                return
            self.send_static(path)

        def do_HEAD(self) -> None:
            try:
                path = safe_static_path(self.path)
            except NetworkWebError:
                self.send_response(400)
                self.end_headers()
                return
            if not path.exists() or not path.is_file():
                self.send_response(404)
                self.end_headers()
                return
            self.send_static(path, include_body=False)

    return NetworkHandler


def main() -> int:
    args = parse_args()
    if not (TEMPLATE_DIR / "index.html").exists():
        raise NetworkWebError(f"Missing frontend template: {TEMPLATE_DIR / 'index.html'}")
    port = find_port(args.host, args.port)
    url = f"http://{args.host}:{port}/"
    server = ThreadingHTTPServer((args.host, port), make_handler())
    print(f"Cento jobs dashboard running at {url}")
    print(f"Cluster jobs: {RUN_ROOT}")
    if args.open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Cento jobs dashboard.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NetworkWebError as exc:
        print(f"jobs-web: {exc}", file=sys.stderr)
        raise SystemExit(1)
