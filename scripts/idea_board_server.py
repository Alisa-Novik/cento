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
DATA_PATH = ROOT_DIR / "data" / "idea-board.json"
TEMPLATE_DIR = ROOT_DIR / "templates" / "idea-board"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 47872
PORT_SPAN = 20


class IdeaBoardError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local Cento idea board.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Bind host. Default: {DEFAULT_HOST}")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Preferred port. Default: {DEFAULT_PORT}")
    parser.add_argument("--data", default=str(DATA_PATH), help="Idea board JSON file.")
    parser.add_argument("--open", action="store_true", help="Open the idea board in the default browser.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise IdeaBoardError(f"Missing idea board data: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise IdeaBoardError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise IdeaBoardError("Idea board data must be a JSON object.")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    payload["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def safe_static_path(raw_path: str) -> Path:
    route = raw_path.split("?", 1)[0].split("#", 1)[0]
    if route in ("", "/"):
        route = "/index.html"
    relative = route.lstrip("/")
    path = (TEMPLATE_DIR / relative).resolve()
    template_root = TEMPLATE_DIR.resolve()
    if template_root not in path.parents and path != template_root:
        raise IdeaBoardError("Invalid static path.")
    return path


def find_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + PORT_SPAN):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise IdeaBoardError(f"Could not bind a free port in range {preferred}-{preferred + PORT_SPAN - 1}.")


def make_handler(data_path: Path) -> type[BaseHTTPRequestHandler]:
    class IdeaBoardHandler(BaseHTTPRequestHandler):
        server_version = "cento-idea-board/1.0"

        def log_message(self, fmt: str, *args: object) -> None:
            print(f"{self.address_string()} - {fmt % args}", file=sys.stderr)

        def send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_error_json(self, status: int, message: str) -> None:
            self.send_json(status, {"error": message})

        def do_GET(self) -> None:
            if self.path.startswith("/api/ideas"):
                try:
                    self.send_json(200, read_json(data_path))
                except IdeaBoardError as exc:
                    self.send_error_json(500, str(exc))
                return
            try:
                path = safe_static_path(self.path)
            except IdeaBoardError as exc:
                self.send_error_json(400, str(exc))
                return
            if not path.exists() or not path.is_file():
                self.send_error_json(404, "Not found.")
                return
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_PUT(self) -> None:
            if not self.path.startswith("/api/ideas"):
                self.send_error_json(404, "Not found.")
                return
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0:
                self.send_error_json(400, "Missing JSON body.")
                return
            try:
                payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            except json.JSONDecodeError as exc:
                self.send_error_json(400, f"Invalid JSON: {exc}")
                return
            if not isinstance(payload, dict) or not isinstance(payload.get("ideas"), list):
                self.send_error_json(400, "Payload must be an object with an ideas array.")
                return
            write_json(data_path, payload)
            self.send_json(200, payload)

    return IdeaBoardHandler


def main() -> int:
    args = parse_args()
    data_path = Path(args.data).expanduser().resolve()
    read_json(data_path)
    if not (TEMPLATE_DIR / "index.html").exists():
        raise IdeaBoardError(f"Missing frontend template: {TEMPLATE_DIR / 'index.html'}")

    port = find_port(args.host, args.port)
    url = f"http://{args.host}:{port}/"
    server = ThreadingHTTPServer((args.host, port), make_handler(data_path))
    print(f"Cento idea board running at {url}")
    print(f"Data file: {data_path}")
    if args.open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Cento idea board.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except IdeaBoardError as exc:
        print(f"idea-board: {exc}", file=sys.stderr)
        raise SystemExit(1)
