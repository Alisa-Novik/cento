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
