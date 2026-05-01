#!/usr/bin/env python3
from __future__ import annotations

import network_web_server as nws


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def status(stdout: str, ok: bool = True) -> dict:
    return {"ok": ok, "stdout": stdout, "stderr": "", "returncode": 0 if ok else 1}


def mesh(stdout: str, ok: bool = True) -> dict:
    return {"ok": ok, "stdout": stdout, "stderr": "", "returncode": 0 if ok else 1}


def cluster(nodes: list[dict]) -> dict:
    return {"nodes": nodes, "relay": {"host": "example"}}


def test_empty() -> None:
    model = nws.node_health_model(cluster([]), status("local linux\n\nnodes\n"), mesh(""))
    assert_true(model["overall"] == "empty", f"empty overall: {model['overall']}")
    assert_true(model["nodes"] == [], "empty nodes")


def test_healthy_two_node_mesh() -> None:
    nodes = [
        {"id": "linux", "platform": "linux", "socket": "/tmp/linux.sock"},
        {"id": "macos", "platform": "macos", "socket": "/tmp/mac.sock"},
    ]
    model = nws.node_health_model(
        cluster(nodes),
        status("local linux\n\nnodes\nlinux connected\nmacos connected\n"),
        mesh("srw------- 1 opc opc 0 Apr 30 00:00 /tmp/mac.sock\n"),
    )
    assert_true(model["overall"] == "healthy", f"healthy overall: {model['overall']}")
    by_id = {node["id"]: node for node in model["nodes"]}
    assert_true(by_id["linux"]["is_local"], "linux local")
    assert_true(by_id["macos"]["socket_present"], "macos socket")
    assert_true(by_id["macos"]["state"] == "online", f"macos state: {by_id['macos']['state']}")
    assert_true(by_id["macos"]["remediation"]["severity"] == "ok", "healthy remote remediation severity")
    assert_true(model["actions"] == [], "healthy model should not emit remediation actions")


def test_degraded_missing_socket_and_companion() -> None:
    nodes = [
        {"id": "linux", "platform": "linux", "socket": "/tmp/linux.sock"},
        {"id": "macos", "platform": "macos", "socket": "/tmp/mac.sock"},
        {"id": "iphone", "platform": "ios-ish", "role": "companion", "socket": ""},
    ]
    model = nws.node_health_model(
        cluster(nodes),
        status("local linux\n\nnodes\nlinux connected\nmacos connected\niphone disconnected\n"),
        mesh(""),
    )
    by_id = {node["id"]: node for node in model["nodes"]}
    assert_true(model["overall"] == "degraded", f"degraded overall: {model['overall']}")
    assert_true(by_id["macos"]["state"] == "degraded", f"macos state: {by_id['macos']['state']}")
    assert_true("mesh socket missing" in by_id["macos"]["reasons"], "macos missing socket reason")
    assert_true(by_id["macos"]["remediation"]["action"] == "repair mesh socket", "macos remediation action")
    assert_true("cento bridge mesh-status" in by_id["macos"]["remediation"]["commands"], "macos remediation command")
    assert_true(by_id["iphone"]["state"] == "offline", f"iphone state: {by_id['iphone']['state']}")
    assert_true("companion disconnected" in by_id["iphone"]["reasons"], "iphone disconnected reason")
    assert_true(by_id["iphone"]["remediation"]["action"] == "refresh companion heartbeat", "iphone remediation action")
    assert_true(by_id["iphone"]["remediation"]["owner"] == "companion entry node operator", "iphone owner hint")
    action_nodes = {action["node"] for action in model["actions"]}
    assert_true(action_nodes == {"macos", "iphone"}, f"action nodes: {action_nodes}")


def test_stale_socket_and_metrics_issue() -> None:
    nodes = [
        {"id": "linux", "platform": "linux", "socket": "/tmp/linux.sock"},
        {"id": "macos", "platform": "macos", "socket": "/tmp/mac.sock"},
    ]
    original_local_metrics = nws.local_metrics
    nws.local_metrics = lambda: {"error": "collector unavailable"}  # type: ignore[assignment]
    try:
        model = nws.node_health_model(
            cluster(nodes),
            status("local linux\n\nnodes\nlinux connected\nmacos disconnected\n"),
            mesh("srw------- 1 opc opc 0 Apr 30 00:00 /tmp/mac.sock\n"),
        )
    finally:
        nws.local_metrics = original_local_metrics
    by_id = {node["id"]: node for node in model["nodes"]}
    assert_true(model["overall"] == "degraded", f"stale overall: {model['overall']}")
    assert_true(by_id["linux"]["state"] == "degraded", f"linux state: {by_id['linux']['state']}")
    assert_true("metrics unavailable: collector unavailable" in by_id["linux"]["reasons"], "linux metrics reason")
    assert_true(by_id["linux"]["remediation"]["action"] == "restore local metrics", "linux metrics remediation")
    assert_true(by_id["macos"]["state"] == "degraded", f"macos state: {by_id['macos']['state']}")
    assert_true("stale mesh socket" in by_id["macos"]["reasons"], "macos stale reason")
    assert_true(by_id["macos"]["remediation"]["action"] == "repair stale socket", "macos stale remediation")
    assert_true(by_id["macos"]["remediation"]["commands"][0] == "cento bridge status", "macos stale commands")
    action_nodes = {action["node"] for action in model["actions"]}
    assert_true(action_nodes == {"linux", "macos"}, f"stale action nodes: {action_nodes}")


def test_panel_relay_action() -> None:
    panel = nws.build_cluster_panel_model(
        {
            "health": {
                "overall": "unavailable",
                "local": "",
                "counts": {"online": 0, "offline": 0, "degraded": 0},
                "nodes": [],
                "reasons": ["cluster status command unavailable", "bridge mesh-status unavailable"],
                "actions": [],
            },
            "status": {"ok": False, "stdout": "", "stderr": "cluster status unreachable"},
            "mesh": {"ok": False, "stdout": "", "stderr": "bridge mesh-status unreachable"},
            "relay": {},
            "nodes": [],
            "metrics": {"error": "collector unavailable"},
            "updated_at": "2026-04-30T10:12:00-04:00",
        }
    )
    assert_true(panel["overall"] == "unavailable", f"panel overall: {panel['overall']}")
    action_nodes = {action["node"] for action in panel["remediation_actions"]}
    assert_true("relay" in action_nodes, f"relay action nodes: {action_nodes}")


def main() -> int:
    test_empty()
    test_healthy_two_node_mesh()
    test_degraded_missing_socket_and_companion()
    test_stale_socket_and_metrics_issue()
    test_panel_relay_action()
    print("industrial cluster contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
