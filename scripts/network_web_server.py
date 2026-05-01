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
from typing import Any, TypedDict

from industrial_activity import cluster_events


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


def strip_ansi(value: str) -> str:
    result = []
    index = 0
    while index < len(value):
        if value[index] == "\033":
            index += 1
            while index < len(value) and value[index] not in "mK":
                index += 1
        else:
            result.append(value[index])
        index += 1
    return "".join(result)


def parse_local_node(status_output: str) -> str:
    for raw in strip_ansi(status_output).splitlines():
        parts = raw.split()
        if len(parts) >= 2 and parts[0] == "local":
            return parts[1]
    return ""


def parse_status_nodes(status_output: str) -> dict[str, str]:
    states: dict[str, str] = {}
    in_nodes = False
    for raw in strip_ansi(status_output).splitlines():
        line = raw.strip()
        if line == "nodes":
            in_nodes = True
            continue
        if not in_nodes or not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            states[parts[0]] = parts[1]
    return states


def parse_status_node_details(status_output: str) -> dict[str, dict[str, str]]:
    details: dict[str, dict[str, str]] = {}
    in_nodes = False
    for raw in strip_ansi(status_output).splitlines():
        line = raw.strip()
        if line == "nodes":
            in_nodes = True
            continue
        if not in_nodes or not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        node_details: dict[str, str] = {"state": parts[1]}
        for token in parts[2:]:
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            node_details[key] = value
        details[parts[0]] = node_details
    return details


def parse_mesh_sockets(mesh_output: str) -> dict[str, dict[str, Any]]:
    sockets: dict[str, dict[str, Any]] = {}
    for raw in strip_ansi(mesh_output).splitlines():
        parts = raw.split()
        if len(parts) < 9:
            continue
        socket_path = parts[-1]
        sockets[socket_path] = {
            "present": parts[0].startswith("s"),
            "owner": parts[2] if len(parts) > 2 else "",
            "group": parts[3] if len(parts) > 3 else "",
            "raw": raw,
        }
    return sockets


def local_metrics() -> dict[str, Any]:
    try:
        from industrial_status import metrics

        return metrics()
    except Exception as exc:
        return {"error": str(exc)}


def metrics_issue(metrics: dict[str, Any]) -> str | None:
    error = str(metrics.get("error") or "").strip()
    if error:
        return error
    required = ("cpu", "ram", "disk", "temp", "net_down", "net_up")
    missing = [key for key in required if metrics.get(key) in (None, "")]
    if missing:
        return "missing " + ", ".join(missing)
    return None


def normalize_node_state(raw_state: str, socket_present: bool, is_local: bool, role: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if role == "companion":
        if raw_state in {"connected", "local", "online"}:
            return "online", reasons
        reasons.append(f"companion {raw_state or 'not reported'}")
        return "offline", reasons
    if raw_state in {"connected", "local", "online"}:
        if not is_local and not socket_present:
            reasons.append("mesh socket missing")
            return "degraded", reasons
        return "online", reasons
    if raw_state in {"disconnected", "offline", "stale"} and not is_local and socket_present:
        reasons.append(f"cluster status={raw_state}")
        reasons.append("stale mesh socket")
        return "degraded", reasons
    if raw_state:
        reasons.append(f"cluster status={raw_state}")
    else:
        reasons.append("missing from cluster status")
    if not is_local and socket_present:
        reasons.append("stale mesh socket")
        return "degraded", reasons
    if not is_local and not socket_present:
        reasons.append("mesh socket missing")
    return "offline", reasons


def owner_hint(node: dict[str, Any], is_local: bool) -> str:
    role = str(node.get("role") or "")
    if is_local:
        return "local operator"
    if role == "companion":
        return f"{node.get('entry_node') or 'companion entry node'} operator"
    return f"{node.get('platform') or node.get('id') or 'node'} operator"


def remediation_for_node(
    node: dict[str, Any],
    state: str,
    reasons: list[str],
    is_local: bool,
    metrics_problem: str | None = None,
) -> dict[str, Any]:
    node_id = str(node.get("id") or "")
    role = str(node.get("role") or "")
    if state == "online":
        return {
            "severity": "ok",
            "owner": owner_hint(node, is_local),
            "action": "monitor",
            "commands": [f"cento cluster exec {node_id} -- true"] if not is_local and role != "companion" else ["cento cluster status"],
        }
    commands: list[str] = ["cento cluster status"]
    action = "inspect node"
    severity = "warning" if state == "degraded" else "critical"
    if metrics_problem:
        action = "restore local metrics"
        commands = ["python3 scripts/industrial_status.py --json", "cento cluster status"]
    elif any("stale mesh socket" in reason for reason in reasons):
        action = "repair stale socket"
        commands = ["cento bridge status", "cento bridge mesh-status", f"cento cluster heal {node_id}"]
    elif any("mesh socket missing" in reason for reason in reasons):
        action = "repair mesh socket"
        commands = [f"cento cluster heal {node_id}", "cento bridge mesh-status"]
    elif role == "companion":
        action = "refresh companion heartbeat"
        commands = [f"cento cluster heartbeat {node_id}", f"cento cluster heal {node.get('entry_node') or 'macos'}"]
    elif any("missing from cluster status" in reason for reason in reasons) or any(
        str(reason).startswith("cluster status=") for reason in reasons
    ):
        action = "restore node reachability"
        commands = [f"cento cluster heal {node_id}", f"cento cluster exec {node_id} -- hostname"]
    return {
        "severity": severity,
        "owner": owner_hint(node, is_local),
        "action": action,
        "commands": commands,
    }


def resource_health_model(metrics: dict[str, Any], nodes: list[dict[str, Any]], metrics_problem: str | None) -> dict[str, Any]:
    local_metrics = {
        key: metrics.get(key)
        for key in ("cpu", "ram", "disk", "temp", "net_down", "net_up")
        if metrics.get(key) not in (None, "")
    }
    remote_nodes = [
        {
            "id": str(node.get("id") or ""),
            "state": str(node.get("state") or "unknown"),
            "status": "telemetry missing" if str(node.get("state") or "") == "online" else "unavailable",
        }
        for node in nodes
        if not node.get("is_local")
    ]
    return {
        "local": {
            "status": "healthy" if not metrics_problem else "degraded",
            "problem": metrics_problem or "",
            "metrics": local_metrics,
        },
        "remote": {
            "status": "limited" if remote_nodes else "none",
            "nodes": remote_nodes,
            "summary": "remote metrics are not collected by cento cluster status",
        },
    }


def synthesize_resource_health(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    local_node = next((node for node in nodes if node.get("is_local")), None)
    local_metrics = dict(local_node.get("metrics") or {}) if isinstance(local_node, dict) else {}
    problem = str(local_metrics.get("error") or "").strip()
    if problem:
        local_metrics = {}
    else:
        local_metrics = {
            key: local_metrics.get(key)
            for key in ("cpu", "ram", "disk", "temp", "net_down", "net_up")
            if local_metrics.get(key) not in (None, "")
        }
    remote_nodes = [
        {
            "id": str(node.get("id") or ""),
            "state": str(node.get("state") or "unknown"),
            "status": "telemetry missing" if str(node.get("state") or "") == "online" else "unavailable",
        }
        for node in nodes
        if not node.get("is_local")
    ]
    return {
        "local": {
            "status": "healthy" if not problem else "degraded",
            "problem": problem,
            "metrics": local_metrics,
        },
        "remote": {
            "status": "limited" if remote_nodes else "none",
            "nodes": remote_nodes,
            "summary": "remote metrics are not collected by cento cluster status",
        },
    }


def node_health_model(cluster: dict[str, Any], status: dict[str, Any], mesh: dict[str, Any]) -> dict[str, Any]:
    status_output = "\n".join(item for item in [status.get("stdout", ""), status.get("stderr", "")] if item)
    mesh_output = "\n".join(item for item in [mesh.get("stdout", ""), mesh.get("stderr", "")] if item)
    local_id = parse_local_node(status_output)
    status_nodes = parse_status_nodes(status_output)
    status_details = parse_status_node_details(status_output)
    mesh_sockets = parse_mesh_sockets(mesh_output)
    metrics = local_metrics()
    metrics_problem = metrics_issue(metrics)
    nodes = []
    counts = {"online": 0, "offline": 0, "degraded": 0}
    for node in cluster.get("nodes", []):
        node_id = str(node.get("id") or "")
        role = str(node.get("role") or "")
        socket_path = str(node.get("socket") or "")
        is_local = node_id == local_id
        socket_info = mesh_sockets.get(socket_path, {}) if socket_path else {}
        raw_state = status_nodes.get(node_id, "local" if is_local else "")
        state, reasons = normalize_node_state(raw_state, bool(socket_info.get("present") or is_local or not socket_path), is_local, role)
        if is_local and metrics_problem:
            reasons.append(f"metrics unavailable: {metrics_problem}")
            if state == "online":
                state = "degraded"
        remediation = remediation_for_node(node, state, reasons, is_local, metrics_problem if is_local else None)
        counts[state] = counts.get(state, 0) + 1
        node_metrics = metrics if is_local else {}
        nodes.append(
            {
                "id": node_id,
                "platform": node.get("platform", ""),
                "role": role or "worker",
                "state": state,
                "status": raw_state or "unknown",
                "is_local": is_local,
                "host_alias": node.get("host_alias", ""),
                "socket": socket_path,
                "socket_present": bool(socket_info.get("present") or is_local or not socket_path),
                "socket_detail": socket_info,
                "bridge_service": node.get("bridge_service", ""),
                "capabilities": node.get("capabilities", []),
                "status_detail": status_details.get(node_id, {}),
                "metrics": node_metrics,
                "reasons": reasons,
                "remediation": remediation,
            }
        )
    overall = "empty"
    if nodes:
        overall = "healthy" if counts.get("offline", 0) == 0 and counts.get("degraded", 0) == 0 else "degraded"
    if not status.get("ok"):
        overall = "degraded"
    if not mesh.get("ok") and any(node.get("socket") for node in cluster.get("nodes", [])):
        overall = "degraded"
    return {
        "overall": overall,
        "local": local_id,
        "counts": counts,
        "nodes": nodes,
        "mesh_sockets": mesh_sockets,
        "metrics": metrics,
        "resource_health": resource_health_model(metrics, nodes, metrics_problem),
        "reasons": [
            reason
            for node in nodes
            for reason in node.get("reasons", [])
        ],
        "actions": [
            {
                "node": node["id"],
                **node["remediation"],
            }
            for node in nodes
            if node.get("state") != "online"
        ],
    }


class ClusterNodeEntry(TypedDict):
    id: str
    platform: str
    role: str
    state: str  # "online" | "offline" | "degraded"
    status_detail: dict[str, Any]
    reasons: list[str]
    metrics: dict[str, Any]
    socket_present: bool
    socket_path: str
    is_local: bool
    host_alias: str
    bridge_service: str
    capabilities: list[str]
    remediation_action: str
    remediation_commands: list[str]
    remediation_owner: str
    remediation_severity: str


class ClusterPanelModel(TypedDict):
    overall: str  # "healthy" | "degraded" | "empty" | "unavailable"
    local_id: str
    counts: dict[str, int]
    nodes: list[ClusterNodeEntry]
    relay_host: str
    relay_present: bool
    registry_loaded: bool
    status_ok: bool
    mesh_ok: bool
    degraded_reasons: list[str]
    remediation_actions: list[dict[str, Any]]
    resource_health: dict[str, Any]
    recent_events: list[dict[str, Any]]
    updated_at: str


def build_cluster_panel_model(snapshot: dict[str, Any]) -> ClusterPanelModel:
    health = snapshot.get("health") or {}
    status = snapshot.get("status") or {}
    mesh_result = snapshot.get("mesh") or {}
    relay = snapshot.get("relay") or {}

    status_ok = bool(status.get("ok"))
    mesh_ok = bool(mesh_result.get("ok"))
    registry_nodes = snapshot.get("nodes") or []
    registry_loaded = bool(registry_nodes)

    overall = str(health.get("overall") or "empty")
    if not status_ok and not mesh_ok and not registry_nodes:
        overall = "unavailable"

    relay_host = str(relay.get("host") or "")
    relay_present = bool(relay_host)
    relay_issue = not status_ok or not mesh_ok

    nodes: list[ClusterNodeEntry] = []
    for n in (health.get("nodes") or []):
        rem = n.get("remediation") or {}
        nodes.append(
            ClusterNodeEntry(
                id=str(n.get("id") or ""),
                platform=str(n.get("platform") or ""),
                role=str(n.get("role") or "worker"),
                state=str(n.get("state") or "offline"),
                status_detail=dict(n.get("status_detail") or {}),
                reasons=list(n.get("reasons") or []),
                metrics=dict(n.get("metrics") or {}),
                socket_present=bool(n.get("socket_present")),
                socket_path=str(n.get("socket") or ""),
                is_local=bool(n.get("is_local")),
                host_alias=str(n.get("host_alias") or ""),
                bridge_service=str(n.get("bridge_service") or ""),
                capabilities=list(n.get("capabilities") or []),
                remediation_action=str(rem.get("action") or ""),
                remediation_commands=list(rem.get("commands") or []),
                remediation_owner=str(rem.get("owner") or ""),
                remediation_severity=str(rem.get("severity") or ""),
            )
        )

    remediation_actions = list(health.get("actions") or [])
    if relay_issue:
        remediation_actions.append(
            {
                "node": "relay",
                "severity": "critical",
                "owner": "local operator",
                "action": "inspect relay bridge",
                "commands": [
                    "cento bridge status",
                    "cento bridge mesh-status",
                ],
            }
        )

    resource_health_value = health.get("resource_health") or {}
    resource_health = resource_health_value if isinstance(resource_health_value, dict) else {}
    if not resource_health:
        resource_health = synthesize_resource_health(nodes)
    recent_events_value = health.get("events") or snapshot.get("events") or cluster_events(snapshot, include_placeholder=False) or []
    recent_events = list(recent_events_value) if isinstance(recent_events_value, list) else []

    return ClusterPanelModel(
        overall=overall,
        local_id=str(health.get("local") or ""),
        counts=dict(health.get("counts") or {"online": 0, "offline": 0, "degraded": 0}),
        nodes=nodes,
        relay_host=relay_host,
        relay_present=relay_present,
        registry_loaded=registry_loaded,
        status_ok=status_ok,
        mesh_ok=mesh_ok,
        degraded_reasons=list(health.get("reasons") or []),
        remediation_actions=remediation_actions,
        resource_health=resource_health,
        recent_events=recent_events,
        updated_at=str(snapshot.get("updated_at") or ""),
    )


def cluster_snapshot() -> dict[str, Any]:
    if not CLUSTER_FILE.exists():
        run_command([str(CLUSTER_SH), "init"], timeout=8)
    cluster = read_json(CLUSTER_FILE)
    status = run_command([str(CLUSTER_SH), "status"], timeout=12)
    mesh = run_command([str(ROOT_DIR / "scripts" / "bridge.sh"), "mesh-status"], timeout=8)
    health = node_health_model(cluster, status, mesh)
    snapshot = {
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "cluster_file": str(CLUSTER_FILE),
        "relay": cluster.get("relay", {}),
        "nodes": cluster.get("nodes", []),
        "health": health,
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
    events = cluster_events(snapshot, include_placeholder=False)
    snapshot["health"]["events"] = events
    snapshot["events"] = events
    return snapshot


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
