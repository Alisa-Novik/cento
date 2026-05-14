#!/usr/bin/env python3
"""Codebase Intelligence: local repository scanner for capability graph, inspector, and health data."""
from __future__ import annotations

import ast
import fnmatch
import json
import os
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Capability definitions: each capability groups script patterns into a node
# ---------------------------------------------------------------------------
CAPABILITIES: list[dict[str, Any]] = [
    {
        "id": "agent-work",
        "label": "Agent Work",
        "description": "Taskstream issue tracking, builder/validator workflow, local DB backend",
        "color": "#4f8ef7",
        "patterns": ["agent_work*.py"],
        "kind": "core",
        "route": "/",
    },
    {
        "id": "factory",
        "label": "Factory Autopilot",
        "description": "Automated factory pipeline, policy matrix, and run dispatch",
        "color": "#f7a04f",
        "patterns": ["factory_autopilot*.py", "factory_dispatch*.py", "factory_console*.py"],
        "kind": "core",
        "route": "/factory",
    },
    {
        "id": "cluster",
        "label": "Cluster & Industrial",
        "description": "Cluster job dispatch, industrial actions, focus, and panel",
        "color": "#4ff7a0",
        "patterns": ["cluster_*.py", "industrial_*.py"],
        "kind": "infrastructure",
        "route": "/cluster",
    },
    {
        "id": "cento-cli",
        "label": "Cento CLI",
        "description": "Unified CLI facade, interactive shell, run-mode, build, workset, runtime",
        "color": "#a04ff7",
        "patterns": ["cento_*.py"],
        "kind": "tooling",
        "route": None,
    },
    {
        "id": "storage",
        "label": "Storage",
        "description": "Storage policies and data persistence layer",
        "color": "#f74f4f",
        "patterns": ["storage*.py"],
        "kind": "infrastructure",
        "route": None,
    },
    {
        "id": "mcp",
        "label": "MCP Server",
        "description": "Model Context Protocol server and tooling integration",
        "color": "#f7e04f",
        "patterns": ["*mcp*.py"],
        "kind": "tooling",
        "route": None,
    },
    {
        "id": "docs",
        "label": "Docs",
        "description": "Documentation rendering, browsing, and delivery hub",
        "color": "#4fd4f7",
        "patterns": ["docs_*.py", "deliverables_hub.py"],
        "kind": "ui",
        "route": "/docs",
    },
    {
        "id": "research",
        "label": "Research Center",
        "description": "Research map and context gathering",
        "color": "#f74fa0",
        "patterns": ["research_*.py", "gather_*.py"],
        "kind": "ui",
        "route": "/research-center",
    },
    {
        "id": "consulting",
        "label": "Consulting & Funnel",
        "description": "Funnel checks, CRM module, and scan one-pager",
        "color": "#a0f74f",
        "patterns": ["funnel_*.py", "crm_*.py", "scan_*.py"],
        "kind": "business",
        "route": "/consulting",
    },
    {
        "id": "validation",
        "label": "Validation",
        "description": "Story manifest validation, contract checks, and validator tiers",
        "color": "#4f4ff7",
        "patterns": [
            "*validation*.py",
            "*validate*.py",
            "*contract_check*.py",
            "story_*.py",
            "validator_*.py",
            "manifest_*.py",
            "no_model_*.py",
        ],
        "kind": "quality",
        "route": None,
    },
    {
        "id": "agent-manager",
        "label": "Agent Manager",
        "description": "Agent pool coordination, manager, and coordinator",
        "color": "#e04ff7",
        "patterns": ["agent_manager*.py", "agent_coordinator*.py", "agent_pool*.py"],
        "kind": "core",
        "route": None,
    },
    {
        "id": "platform",
        "label": "Platform & Tools",
        "description": "Platform reporting, tool index, network server, dashboard",
        "color": "#f7c04f",
        "patterns": [
            "platform_*.py",
            "tool_index.py",
            "network_*.py",
            "dashboard_*.py",
            "jobs_server.py",
            "idea_board_server.py",
            "bluetooth_*.py",
        ],
        "kind": "tooling",
        "route": "/dev-pipeline-studio",
    },
]

# Built-in cross-capability dependency hints (supplement import scanning)
CAPABILITY_DEPS: list[tuple[str, str]] = [
    ("factory", "agent-work"),
    ("cluster", "agent-work"),
    ("docs", "agent-work"),
    ("validation", "agent-work"),
    ("validation", "factory"),
    ("agent-manager", "agent-work"),
    ("cento-cli", "factory"),
    ("cento-cli", "storage"),
]

# Known HTTP route groups
ROUTE_GROUPS: list[dict[str, Any]] = [
    {"prefix": "/health", "methods": ["GET"], "module": "agent-work", "description": "App health check"},
    {"prefix": "/api/issues", "methods": ["GET", "POST", "PATCH"], "module": "agent-work", "description": "Issue CRUD"},
    {"prefix": "/api/runs", "methods": ["GET"], "module": "agent-work", "description": "Agent-work run list"},
    {"prefix": "/api/review", "methods": ["GET", "POST"], "module": "agent-work", "description": "Validator review queue and decisions"},
    {"prefix": "/api/factory", "methods": ["GET"], "module": "factory", "description": "Factory pipeline runs"},
    {"prefix": "/api/sync", "methods": ["GET"], "module": "agent-work", "description": "Sync from agent-work backend"},
    {"prefix": "/api/projects", "methods": ["GET"], "module": "agent-work", "description": "Project reference list"},
    {"prefix": "/api/trackers", "methods": ["GET"], "module": "agent-work", "description": "Tracker reference list"},
    {"prefix": "/api/statuses", "methods": ["GET"], "module": "agent-work", "description": "Status reference list"},
    {"prefix": "/api/artifacts", "methods": ["GET"], "module": "agent-work", "description": "Serve local artifact files"},
    {"prefix": "/api/queries", "methods": ["GET", "POST"], "module": "agent-work", "description": "Saved queries"},
    {"prefix": "/api/codebase-intelligence", "methods": ["GET"], "module": "codebase-intelligence", "description": "Codebase Intelligence inventory and graph"},
    {"prefix": "/api/codebase-intelligence/graph", "methods": ["GET"], "module": "codebase-intelligence", "description": "Capability graph nodes and edges"},
    {"prefix": "/api/codebase-intelligence/inspect", "methods": ["GET"], "module": "codebase-intelligence", "description": "File inspector details"},
]

# Known data stores
DATASTORES: list[dict[str, str]] = [
    {"id": "sqlite-agent-work", "label": "Agent Work SQLite DB", "kind": "sqlite", "path": "~/.local/state/cento/agent-work-app.sqlite3", "used_by": "agent-work"},
    {"id": "tools-registry", "label": "Tools Registry", "kind": "json-file", "path": "data/tools.json", "used_by": "platform"},
    {"id": "cento-cli-registry", "label": "CLI Commands Registry", "kind": "json-file", "path": "data/cento-cli.json", "used_by": "cento-cli"},
    {"id": "agent-runtimes", "label": "Agent Runtimes", "kind": "json-file", "path": "data/agent-runtimes.json", "used_by": "cluster"},
    {"id": "storage-policies", "label": "Storage Policies", "kind": "json-file", "path": "data/storage-policies.json", "used_by": "storage"},
    {"id": "industrial-actions", "label": "Industrial Actions", "kind": "json-file", "path": "data/industrial-actions.json", "used_by": "cluster"},
    {"id": "runtimes-yaml", "label": "Runtime Config", "kind": "yaml-file", "path": ".cento/runtimes.yaml", "used_by": "cento-cli"},
    {"id": "api-workers-yaml", "label": "API Workers", "kind": "yaml-file", "path": ".cento/api_workers.yaml", "used_by": "cento-cli"},
]


# ---------------------------------------------------------------------------
# File scanning
# ---------------------------------------------------------------------------

def _scripts_dir() -> Path:
    return ROOT_DIR / "scripts"


def _file_matches(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def _capability_for_file(name: str) -> str | None:
    for cap in CAPABILITIES:
        if _file_matches(name, cap["patterns"]):
            return cap["id"]
    return None


def _count_lines(path: Path) -> int:
    try:
        return sum(1 for _ in path.open("r", errors="replace"))
    except OSError:
        return 0


def _parse_ast(path: Path) -> ast.Module | None:
    try:
        src = path.read_text(errors="replace")
        return ast.parse(src, filename=str(path))
    except SyntaxError:
        return None


def _extract_imports(tree: ast.Module) -> list[str]:
    """Return local module names imported (stdlib/third-party filtered out)."""
    stdlib_prefixes = {
        "os", "sys", "re", "json", "ast", "abc", "io", "math", "time",
        "datetime", "collections", "itertools", "functools", "typing",
        "pathlib", "subprocess", "threading", "socket", "signal",
        "sqlite3", "hashlib", "uuid", "base64", "shutil", "shlex",
        "argparse", "textwrap", "fnmatch", "mimetypes", "tempfile",
        "http", "urllib", "webbrowser", "logging", "copy", "enum",
        "dataclasses", "contextlib", "traceback", "inspect", "platform",
        "struct", "array", "queue", "weakref", "gc", "string",
        "__future__",
    }
    local_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in stdlib_prefixes:
                    local_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top not in stdlib_prefixes:
                    local_imports.append(node.module)
    return sorted(set(local_imports))


def _extract_functions(tree: ast.Module) -> list[str]:
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]


def _extract_classes(tree: ast.Module) -> list[str]:
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


def _module_docstring(tree: ast.Module) -> str:
    val = ast.get_docstring(tree) or ""
    return val.splitlines()[0] if val else ""


def scan_scripts() -> list[dict[str, Any]]:
    """Return metadata for every .py file under scripts/."""
    scripts = _scripts_dir()
    result: list[dict[str, Any]] = []
    for path in sorted(scripts.glob("*.py")):
        name = path.name
        rel = str(path.relative_to(ROOT_DIR))
        tree = _parse_ast(path)
        imports = _extract_imports(tree) if tree else []
        functions = _extract_functions(tree) if tree else []
        classes = _extract_classes(tree) if tree else []
        docstring = _module_docstring(tree) if tree else ""
        lines = _count_lines(path)
        cap = _capability_for_file(name)
        result.append({
            "name": name,
            "path": rel,
            "capability": cap,
            "lines": lines,
            "functions": len(functions),
            "classes": len(classes),
            "imports": imports,
            "docstring": docstring,
        })
    return result


# ---------------------------------------------------------------------------
# Capability graph
# ---------------------------------------------------------------------------

def build_graph() -> dict[str, Any]:
    """Build nodes and edges from live file scan + known hints."""
    files = scan_scripts()

    # Aggregate metrics per capability
    cap_files: dict[str, list[dict[str, Any]]] = {c["id"]: [] for c in CAPABILITIES}
    unassigned: list[dict[str, Any]] = []
    for f in files:
        if f["capability"] and f["capability"] in cap_files:
            cap_files[f["capability"]].append(f)
        else:
            unassigned.append(f)

    # Build nodes
    nodes: list[dict[str, Any]] = []
    for cap in CAPABILITIES:
        cid = cap["id"]
        flist = cap_files[cid]
        total_lines = sum(f["lines"] for f in flist)
        total_fn = sum(f["functions"] for f in flist)
        nodes.append({
            "id": cid,
            "label": cap["label"],
            "description": cap["description"],
            "color": cap["color"],
            "kind": cap["kind"],
            "route": cap.get("route"),
            "file_count": len(flist),
            "total_lines": total_lines,
            "total_functions": total_fn,
            "files": [f["path"] for f in flist],
        })

    # Build edges from import scanning
    # Map script module stem -> capability id
    stem_to_cap: dict[str, str] = {}
    for f in files:
        if f["capability"]:
            stem = Path(f["name"]).stem
            stem_to_cap[stem] = f["capability"]

    edge_set: set[tuple[str, str]] = set()
    for f in files:
        if not f["capability"]:
            continue
        src_cap = f["capability"]
        for imp in f["imports"]:
            imp_stem = imp.split(".")[0]
            dst_cap = stem_to_cap.get(imp_stem)
            if dst_cap and dst_cap != src_cap:
                edge_set.add((src_cap, dst_cap))

    # Add built-in hints not already covered
    for src, dst in CAPABILITY_DEPS:
        edge_set.add((src, dst))

    edges: list[dict[str, str]] = [{"source": s, "target": t} for s, t in sorted(edge_set)]

    return {
        "nodes": nodes,
        "edges": edges,
        "unassigned_files": [f["path"] for f in unassigned],
        "total_scripts": len(files),
    }


# ---------------------------------------------------------------------------
# File inspector
# ---------------------------------------------------------------------------

def inspect_file(rel_path: str) -> dict[str, Any]:
    """Return inspector payload for a repository file."""
    # Sanitize path — must stay inside ROOT_DIR
    candidate = (ROOT_DIR / rel_path).resolve()
    if ROOT_DIR.resolve() not in candidate.parents and candidate != ROOT_DIR.resolve():
        return {"error": "path is outside repository", "path": rel_path}
    if not candidate.exists():
        return {"error": "file not found", "path": rel_path}
    if not candidate.is_file():
        return {"error": "path is not a file", "path": rel_path}

    lines = _count_lines(candidate)
    result: dict[str, Any] = {
        "path": rel_path,
        "lines": lines,
        "size_bytes": candidate.stat().st_size,
        "extension": candidate.suffix,
    }

    if candidate.suffix == ".py":
        tree = _parse_ast(candidate)
        if tree:
            imports = _extract_imports(tree)
            functions = _extract_functions(tree)
            classes = _extract_classes(tree)
            docstring = _module_docstring(tree)
            cap = _capability_for_file(candidate.name)
            result.update({
                "docstring": docstring,
                "capability": cap,
                "imports": imports,
                "public_functions": functions,
                "classes": classes,
                "function_count": len(functions),
                "class_count": len(classes),
                "import_count": len(imports),
                "health": _health_score(lines, functions, docstring),
            })
        else:
            result["parse_error"] = True
    elif candidate.suffix == ".json":
        try:
            data = json.loads(candidate.read_text(errors="replace"))
            result["json_keys"] = list(data.keys()) if isinstance(data, dict) else None
            result["json_items"] = len(data) if isinstance(data, (dict, list)) else None
        except (json.JSONDecodeError, OSError):
            result["json_parse_error"] = True

    return result


def _health_score(lines: int, functions: list[str], docstring: str) -> dict[str, Any]:
    """Simple heuristic health score for a Python file."""
    score = 100
    issues: list[str] = []
    if lines > 2000:
        score -= 20
        issues.append("large file (>2000 lines)")
    elif lines > 1000:
        score -= 10
        issues.append("large file (>1000 lines)")
    if not docstring:
        score -= 10
        issues.append("no module docstring")
    if not functions:
        score -= 5
        issues.append("no public functions")
    return {"score": max(0, score), "issues": issues}


# ---------------------------------------------------------------------------
# Health summary
# ---------------------------------------------------------------------------

def health_summary() -> dict[str, Any]:
    """Aggregate health metrics across all scripts."""
    files = scan_scripts()
    total = len(files)
    with_docstring = sum(1 for f in files if f.get("docstring"))
    large_files = [f["path"] for f in files if f["lines"] > 1000]
    total_lines = sum(f["lines"] for f in files)
    total_functions = sum(f["functions"] for f in files)
    uncategorized = [f["path"] for f in files if not f["capability"]]

    tests_dir = ROOT_DIR / "tests"
    test_files = list(tests_dir.glob("test_*.py")) if tests_dir.exists() else []

    return {
        "script_count": total,
        "total_lines": total_lines,
        "total_functions": total_functions,
        "test_file_count": len(test_files),
        "with_docstring_pct": round(with_docstring / total * 100) if total else 0,
        "large_files": large_files,
        "uncategorized_files": uncategorized,
        "data_file_count": len([p for p in (ROOT_DIR / "data").glob("*.json") if p.is_file()]) if (ROOT_DIR / "data").exists() else 0,
        "doc_count": len(list((ROOT_DIR / "docs").glob("*.md"))) if (ROOT_DIR / "docs").exists() else 0,
    }


# ---------------------------------------------------------------------------
# Full inventory (page payload)
# ---------------------------------------------------------------------------

def inventory() -> dict[str, Any]:
    """Full Codebase Intelligence page payload."""
    graph = build_graph()
    health = health_summary()
    return {
        "graph": graph,
        "health": health,
        "routes": ROUTE_GROUPS,
        "datastores": DATASTORES,
        "capabilities": [
            {
                "id": c["id"],
                "label": c["label"],
                "description": c["description"],
                "kind": c["kind"],
                "route": c.get("route"),
                "color": c["color"],
            }
            for c in CAPABILITIES
        ],
    }
