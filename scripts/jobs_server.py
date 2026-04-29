#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import mimetypes
import socket
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
RUN_ROOT = ROOT_DIR / "workspace" / "runs" / "cluster-jobs"
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
            }
        )
    return details


def load_jobs() -> dict[str, Any]:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    jobs = []
    for job_path in sorted(RUN_ROOT.glob("*/job.json"), key=lambda path: path.stat().st_mtime, reverse=True):
        try:
            job = read_json(job_path)
        except NetworkWebError as exc:
            jobs.append({"id": job_path.parent.name, "status": "invalid", "error": str(exc), "path": str(job_path)})
            continue
        run_dir = Path(job.get("run_dir") or job_path.parent)
        summary = Path(job.get("artifacts", {}).get("summary") or run_dir / "summary.md")
        jobs.append(
            {
                "id": job.get("id", job_path.parent.name),
                "status": job.get("status", "unknown"),
                "feature": job.get("feature", ""),
                "created_at": job.get("created_at", ""),
                "finished_at": job.get("finished_at", ""),
                "repo": job.get("repo", ""),
                "run_dir": str(run_dir),
                "job": str(job_path),
                "summary": str(summary),
                "summary_exists": summary.exists(),
                "agent_command": job.get("agent_command", ""),
                "tasks": task_details(job, run_dir),
            }
        )
    return {
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "run_root": str(RUN_ROOT),
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
