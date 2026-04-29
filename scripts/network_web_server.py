#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import socket
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
CLUSTER_SH = ROOT_DIR / "scripts" / "cluster.sh"
RUN_ROOT = ROOT_DIR / "workspace" / "runs" / "cluster-jobs"
TEMPLATE_DIR = ROOT_DIR / "templates" / "network-web"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "cento"
CLUSTER_FILE = CONFIG_DIR / "cluster.json"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 47882
PORT_SPAN = 20


class NetworkWebError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Cento cluster network web dashboard.")
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


def run_command(command: list[str], timeout: int = 8) -> dict[str, Any]:
    try:
        result = subprocess.run(command, cwd=ROOT_DIR, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc)}
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def job_summary() -> dict[str, int]:
    counts = {"total": 0, "planned": 0, "dry_run": 0, "succeeded": 0, "failed": 0}
    if not RUN_ROOT.exists():
        return counts
    for job_path in RUN_ROOT.glob("*/job.json"):
        counts["total"] += 1
        status = str(read_json(job_path).get("status", "planned")).replace("-", "_")
        if status in counts:
            counts[status] += 1
    return counts


def cluster_snapshot() -> dict[str, Any]:
    if not CLUSTER_FILE.exists():
        run_command([str(CLUSTER_SH), "init"], timeout=8)
    cluster = read_json(CLUSTER_FILE)
    status = run_command([str(CLUSTER_SH), "status"], timeout=12)
    mesh = run_command([str(ROOT_DIR / "scripts" / "bridge.sh"), "mesh-status"], timeout=8)
    return {
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "cluster_file": str(CLUSTER_FILE),
        "relay": cluster.get("relay", {}),
        "nodes": cluster.get("nodes", []),
        "status": status,
        "mesh": mesh,
        "jobs": job_summary(),
        "commands": {
            "tui": "cento network --tui",
            "web": "cento network --web",
            "jobs": "cento jobs",
            "cluster_status": "cento cluster status",
            "cluster_heal": "cento cluster heal",
        },
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
        server_version = "cento-network-web/1.0"

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
            if self.path.startswith("/api/network"):
                self.send_json(200, cluster_snapshot())
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
    print(f"Cento network dashboard running at {url}")
    print(f"Cluster registry: {CLUSTER_FILE}")
    if args.open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Cento network dashboard.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NetworkWebError as exc:
        print(f"network-web: {exc}", file=sys.stderr)
        raise SystemExit(1)
