#!/usr/bin/env python3
"""Deterministic backend tests for codebase_intelligence module and API response shapes."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import codebase_intelligence as ci


# ---------------------------------------------------------------------------
# scan_scripts
# ---------------------------------------------------------------------------

def test_scan_scripts_returns_list():
    files = ci.scan_scripts()
    assert isinstance(files, list)
    assert len(files) > 0


def test_scan_scripts_fields():
    files = ci.scan_scripts()
    required = {"name", "path", "capability", "lines", "functions", "classes", "imports", "docstring"}
    for f in files[:5]:
        assert required <= set(f.keys()), f"Missing fields in {f['name']}"


def test_scan_scripts_includes_codebase_intelligence():
    files = ci.scan_scripts()
    names = [f["name"] for f in files]
    assert "codebase_intelligence.py" in names


def test_scan_scripts_includes_agent_work_app():
    files = ci.scan_scripts()
    names = [f["name"] for f in files]
    assert "agent_work_app.py" in names


def test_scan_scripts_lines_positive():
    files = ci.scan_scripts()
    for f in files:
        assert f["lines"] >= 0, f"{f['name']} has negative line count"


def test_scan_scripts_capability_values():
    valid_ids = {c["id"] for c in ci.CAPABILITIES} | {None}
    files = ci.scan_scripts()
    for f in files:
        assert f["capability"] in valid_ids, f"Unknown capability {f['capability']} for {f['name']}"


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------

def test_build_graph_keys():
    graph = ci.build_graph()
    assert "nodes" in graph
    assert "edges" in graph
    assert "total_scripts" in graph
    assert "unassigned_files" in graph


def test_build_graph_nodes_shape():
    graph = ci.build_graph()
    node_fields = {"id", "label", "description", "color", "kind", "file_count", "total_lines", "files"}
    for node in graph["nodes"]:
        assert node_fields <= set(node.keys()), f"Missing fields in node {node.get('id')}"


def test_build_graph_nodes_count():
    graph = ci.build_graph()
    assert len(graph["nodes"]) == len(ci.CAPABILITIES)


def test_build_graph_edges_shape():
    graph = ci.build_graph()
    for edge in graph["edges"]:
        assert "source" in edge
        assert "target" in edge
        assert edge["source"] != edge["target"]


def test_build_graph_no_self_loops():
    graph = ci.build_graph()
    for edge in graph["edges"]:
        assert edge["source"] != edge["target"]


def test_build_graph_total_scripts_positive():
    graph = ci.build_graph()
    assert graph["total_scripts"] > 0


def test_build_graph_known_capability_ids():
    graph = ci.build_graph()
    valid_ids = {c["id"] for c in ci.CAPABILITIES}
    for node in graph["nodes"]:
        assert node["id"] in valid_ids


# ---------------------------------------------------------------------------
# inspect_file
# ---------------------------------------------------------------------------

def test_inspect_file_python():
    result = ci.inspect_file("scripts/codebase_intelligence.py")
    assert "error" not in result
    assert result["lines"] > 0
    assert result["extension"] == ".py"
    assert isinstance(result["public_functions"], list)
    assert isinstance(result["imports"], list)


def test_inspect_file_missing():
    result = ci.inspect_file("scripts/does_not_exist_xyz.py")
    assert "error" in result


def test_inspect_file_outside_repo():
    result = ci.inspect_file("../../etc/passwd")
    assert "error" in result
    assert "outside" in result["error"]


def test_inspect_file_json():
    result = ci.inspect_file("data/tools.json")
    assert "error" not in result
    assert result["extension"] == ".json"
    assert result["lines"] > 0


def test_inspect_file_health_keys():
    result = ci.inspect_file("scripts/codebase_intelligence.py")
    assert "health" in result
    health = result["health"]
    assert "score" in health
    assert "issues" in health
    assert 0 <= health["score"] <= 100


def test_inspect_file_capability_assigned():
    result = ci.inspect_file("scripts/agent_work_app.py")
    assert result.get("capability") == "agent-work"


# ---------------------------------------------------------------------------
# health_summary
# ---------------------------------------------------------------------------

def test_health_summary_keys():
    h = ci.health_summary()
    required = {"script_count", "total_lines", "total_functions", "test_file_count", "with_docstring_pct", "large_files", "uncategorized_files"}
    assert required <= set(h.keys())


def test_health_summary_script_count():
    h = ci.health_summary()
    assert h["script_count"] > 0


def test_health_summary_docstring_pct_range():
    h = ci.health_summary()
    assert 0 <= h["with_docstring_pct"] <= 100


# ---------------------------------------------------------------------------
# inventory
# ---------------------------------------------------------------------------

def test_inventory_keys():
    inv = ci.inventory()
    assert "graph" in inv
    assert "health" in inv
    assert "routes" in inv
    assert "datastores" in inv
    assert "capabilities" in inv


def test_inventory_routes_shape():
    inv = ci.inventory()
    for route in inv["routes"]:
        assert "prefix" in route
        assert "methods" in route
        assert "module" in route
        assert isinstance(route["methods"], list)


def test_inventory_datastores_shape():
    inv = ci.inventory()
    for ds in inv["datastores"]:
        assert "id" in ds
        assert "label" in ds
        assert "kind" in ds


def test_inventory_capabilities_shape():
    inv = ci.inventory()
    cap_fields = {"id", "label", "description", "kind", "color"}
    for cap in inv["capabilities"]:
        assert cap_fields <= set(cap.keys())


def test_inventory_codebase_intelligence_route_present():
    inv = ci.inventory()
    prefixes = [r["prefix"] for r in inv["routes"]]
    assert "/api/codebase-intelligence" in prefixes
    assert "/api/codebase-intelligence/graph" in prefixes
    assert "/api/codebase-intelligence/inspect" in prefixes
