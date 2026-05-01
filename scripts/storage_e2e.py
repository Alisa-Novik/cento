#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

import storage


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "workspace" / "runs" / "storage" / "cento-storage-v1"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def seed_fixture(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    run = root / "factory" / "career-consulting-storage-fixture"
    task = run / "tasks" / "crm-schema-extension"
    patch_dir = run / "patches" / "crm-schema-extension"
    evidence = run / "evidence"
    screenshots = run / "screenshots"
    logs = run / "logs"
    db_dir = run / "db"
    build_dir = run / "DerivedData" / "Build" / "Products"

    write_json(
        run / "factory-plan.json",
        {
            "schema_version": "factory-plan/v1",
            "run_id": "career-consulting-storage-fixture",
            "package": "cento-storage-v1",
            "tasks": [{"id": "crm-schema-extension", "title": "CRM schema extension"}],
        },
    )
    write_json(
        task / "story.json",
        {
            "schema_version": "story-manifest/v1",
            "story_id": "crm-schema-extension",
            "title": "CRM schema extension",
        },
    )
    write_json(
        task / "validation.json",
        {
            "schema_version": "validation-manifest/v1",
            "story_id": "crm-schema-extension",
            "checks": [{"name": "catalog", "command": "cento storage scan"}],
        },
    )
    write_json(evidence / "validation-summary.json", {"decision": "approve", "ai_calls_used": 0})
    patch_dir.mkdir(parents=True, exist_ok=True)
    (patch_dir / "patch.diff").write_text(
        "diff --git a/docs/storage.md b/docs/storage.md\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/docs/storage.md\n"
        "@@ -0,0 +1 @@\n"
        "+# Storage\n",
        encoding="utf-8",
    )
    (patch_dir / "changed-files.txt").write_text("docs/storage.md\n", encoding="utf-8")
    (patch_dir / "diffstat.txt").write_text(" docs/storage.md | 1 +\n", encoding="utf-8")
    screenshots.mkdir(parents=True, exist_ok=True)
    (screenshots / "overview.xwd").write_bytes(b"placeholder xwd bytes for storage policy\n")
    (screenshots / "overview.png").write_bytes(b"\x89PNG\r\n\x1a\nplaceholder normalized bytes\n")
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "codex.log").write_text("command: cento storage scan\nresult: ok\n", encoding="utf-8")
    (logs / "worker-prompt.md").write_text("# Worker Prompt\n\nScan artifacts only.\n", encoding="utf-8")
    db_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_dir / "sample.db")
    conn.execute("CREATE TABLE contacts (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO contacts (name) VALUES ('Ada Lovelace')")
    conn.commit()
    conn.close()
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "temporary.o").write_text("reproducible build output\n", encoding="utf-8")


def sqlite_integrity(db_path: Path) -> str:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("PRAGMA integrity_check;").fetchone()
        return str(row[0]) if row else "missing"
    finally:
        conn.close()


def run_e2e(out: Path, fixture: str) -> dict[str, Any]:
    input_root = out / "input-workspace" / "workspace" / "runs"
    seed_fixture(input_root)
    db_path = out / "catalog.sqlite"
    reports = out / "reports"
    scan = storage.scan_artifacts(input_root, db_path)
    plan = storage.build_retention_plan(db_path)
    retention_plan_path = out / "retention-plan.json"
    write_json(retention_plan_path, plan)
    verify = storage.verify_artifacts(db_path, all_rows=True, sample=None)
    write_json(out / "verify-report.json", verify)
    snapshot = storage.snapshot_sqlite(db_path, out / "db-snapshots" / "catalog-snapshot.db")
    restore = storage.restore_sample(db_path, out / "restore-tests" / "sample")
    (out / "storage-summary.md").write_text(storage.render_markdown_report(db_path, plan), encoding="utf-8")
    storage.screenshot_plan(db_path, reports / "screenshot-normalization-plan.json")
    storage.log_compression_plan(db_path, reports / "log-compression-plan.json")
    summary = {
        "schema_version": "cento-storage-e2e/v1",
        "fixture": fixture,
        "out": storage.rel(out),
        "catalog": storage.rel(db_path),
        "scan": scan,
        "retention_plan": storage.rel(retention_plan_path),
        "verify": verify["summary"],
        "snapshot": snapshot,
        "restore": restore["summary"],
        "sqlite_integrity": sqlite_integrity(db_path),
        "ai_calls_used": 0,
        "estimated_ai_cost_usd": 0,
    }
    write_json(out / "e2e-summary.json", summary)
    lines = [
        "# Cento Storage E2E",
        "",
        f"- fixture: `{fixture}`",
        f"- catalog: `{storage.rel(db_path)}`",
        f"- artifacts: `{scan['artifact_count']}`",
        f"- verify passed: `{verify['summary']['passed']}`",
        f"- verify failed: `{verify['summary']['failed']}`",
        f"- sqlite integrity: `{summary['sqlite_integrity']}`",
        f"- snapshot integrity: `{snapshot['integrity_check']}`",
        f"- restore passed: `{restore['summary']['passed']}`",
        "- destructive actions: `0`",
        "- AI calls used: 0",
        "",
        "## Outputs",
        "",
        f"- `{storage.rel(retention_plan_path)}`",
        f"- `{storage.rel(out / 'verify-report.json')}`",
        f"- `{storage.rel(out / 'db-snapshots' / 'catalog-snapshot.db')}`",
        f"- `{storage.rel(out / 'restore-tests' / 'sample' / 'restore-test-report.json')}`",
        f"- `{storage.rel(out / 'storage-summary.md')}`",
        f"- `{storage.rel(reports / 'screenshot-normalization-plan.json')}`",
        f"- `{storage.rel(reports / 'log-compression-plan.json')}`",
    ]
    (out / "e2e-summary.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Cento storage zero-AI E2E.")
    parser.add_argument("--fixture", default="mixed-artifacts", help="Fixture name; mixed-artifacts is built in.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output run directory.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.fixture != "mixed-artifacts":
        raise SystemExit("Only the built-in mixed-artifacts fixture is available in v1.")
    out = storage.repo_path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    summary = run_e2e(out, args.fixture)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(storage.rel(out / "e2e-summary.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
