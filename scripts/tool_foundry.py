#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "workspace" / "runs" / "foundry"
SCHEMA_SPEC = "cento.foundry.spec.v1"
SCHEMA_PLAN = "cento.foundry.plan_receipt.v1"
SCHEMA_EXECUTION = "cento.foundry.execution_receipt.v1"
SCHEMA_VALIDATION = "cento.foundry.validation.v1"
SCHEMA_COST = "cento.foundry.cost_receipt.v1"
SCHEMA_STORAGE_POLICY = "cento.foundry.storage_policy.v1"
SCHEMA_DEMO = "cento.foundry.demo_evidence.v1"
SCHEMA_REAL_FILE_MANIFEST = "cento.foundry.real_file_manifest.v1"
SCHEMA_MATERIALIZATION_PLAN = "cento.foundry.materialization_plan.v1"
SCHEMA_MATERIALIZATION_RECEIPT = "cento.foundry.materialization_receipt.v1"
DEFAULT_FIXTURE = "client-intake-hub"
DEFAULT_DOMAIN = "career-consulting"
DEFAULT_BUDGET_USD = 10.0
DEFAULT_MAX_BUDGET_USD = 20.0
DEFAULT_REAL_FILE_TARGET_ROOT = "templates/foundry/client-intake-hub"
DEFAULT_CLIENT_INTAKE_DOCS_PATH = "docs/client-intake-hub.md"


@dataclass(frozen=True)
class ExternalResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    payload: Any

    def receipt(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "payload": self.payload,
        }


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:80] or "tool"


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def repo_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path


def run_arg(path: Path) -> str:
    return rel(path) if path.resolve().is_relative_to(ROOT.resolve()) else path.as_posix()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def parse_json(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_repo_relative(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("path must not be empty")
    path = Path(text)
    if path.is_absolute():
        raise ValueError(f"path must be repo-relative: {value}")
    parts = path.parts
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"path must not contain traversal segments: {value}")
    normalized = Path(*parts).as_posix()
    if normalized in {"", "."}:
        raise ValueError(f"path must be repo-relative: {value}")
    return normalized


def path_inside(child: str, parent: str) -> bool:
    parent = parent.rstrip("/")
    return child == parent or child.startswith(parent + "/")


def normalize_real_file_target_root(value: str = DEFAULT_REAL_FILE_TARGET_ROOT) -> str:
    target_root = normalize_repo_relative(value or DEFAULT_REAL_FILE_TARGET_ROOT)
    if not target_root.startswith("templates/foundry/"):
        raise ValueError("Foundry real-file target root must be under templates/foundry/")
    return target_root


def validate_real_file_target_path(path: str, target_root: str) -> str:
    normalized = normalize_repo_relative(path)
    if path_inside(normalized, target_root) or normalized == DEFAULT_CLIENT_INTAKE_DOCS_PATH:
        return normalized
    raise ValueError(f"Foundry materialization path is outside the allowlist: {path}")


def append_event(run_dir: Path, event: str, payload: dict[str, Any] | None = None) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    row = {"ts": now_iso(), "event": event, **(payload or {})}
    with (run_dir / "events.ndjson").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def run_external(command: list[str]) -> ExternalResult:
    completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return ExternalResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        payload=parse_json(completed.stdout),
    )


def output(payload: dict[str, Any], *, json_flag: bool) -> None:
    if json_flag:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"{payload.get('status', 'unknown')} {payload.get('run_dir', '')}".strip())


def resolve_run_dir(run_id_or_path: str, *, create: bool = False) -> Path:
    if not run_id_or_path:
        raise SystemExit("run id is required")
    raw = Path(run_id_or_path)
    if raw.is_absolute() or "/" in run_id_or_path:
        run_dir = repo_path(raw)
    else:
        run_dir = RUN_ROOT / run_id_or_path
    if create:
        run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def default_run_id(idea: str, domain: str) -> str:
    return f"foundry-{slugify(domain)}-{slugify(idea)}-{now_stamp()}"


def load_spec(run_dir: Path) -> dict[str, Any]:
    spec = read_json(run_dir / "foundry-spec.json")
    if spec.get("schema_version") != SCHEMA_SPEC:
        raise SystemExit(f"missing Foundry spec: {run_dir / 'foundry-spec.json'}")
    return spec


def title_from_idea(idea: str) -> str:
    cleaned = " ".join(idea.strip().split())
    return cleaned[:1].upper() + cleaned[1:] if cleaned else "Client Intake Hub"


def write_cost_receipt(
    run_dir: Path,
    *,
    mode: str,
    runtime: str,
    budget_usd: float | None,
    max_budget_usd: float | None,
    actual_cost_usd: float = 0.0,
    ai_calls_used: int = 0,
) -> dict[str, Any]:
    hard_cap = float(max_budget_usd if max_budget_usd is not None else DEFAULT_MAX_BUDGET_USD)
    target = float(budget_usd if budget_usd is not None else DEFAULT_BUDGET_USD)
    receipt = {
        "schema_version": SCHEMA_COST,
        "run_id": run_dir.name,
        "mode": mode,
        "runtime": runtime,
        "budget_usd": target,
        "max_budget_usd": hard_cap,
        "actual_cost_usd": float(actual_cost_usd),
        "ai_calls_used": int(ai_calls_used),
        "hard_cap_exceeded": float(actual_cost_usd) > hard_cap,
        "live_requires_explicit_budget": True,
        "written_at": now_iso(),
    }
    write_json(run_dir / "cost_receipt.json", receipt)
    return receipt


def write_storage_policy(run_dir: Path, spec: dict[str, Any]) -> dict[str, Any]:
    policy = {
        "schema_version": SCHEMA_STORAGE_POLICY,
        "run_id": run_dir.name,
        "domain": spec.get("domain", DEFAULT_DOMAIN),
        "tool": spec.get("tool", {}).get("id", DEFAULT_FIXTURE),
        "default_location": "local",
        "oci_storage_tier": "Standard",
        "public_access": "blocked",
        "client_data": {
            "contains_real_client_data": False,
            "fixture_only": True,
            "requires_operator_confirmation_for_real_files": True,
            "never_upload_without_explicit_live_flag": True,
        },
        "allowed_cloud_artifacts": ["dummy receipts", "fixture screenshots", "non-sensitive generated evidence"],
        "blocked_cloud_artifacts": ["resumes", "LinkedIn exports", "client notes", "secrets", "tokens", "raw PII"],
        "written_at": now_iso(),
    }
    write_json(run_dir / "storage-policy.json", policy)
    return policy


def seed_client_intake_hub(run_dir: Path, spec: dict[str, Any]) -> dict[str, str]:
    tool_dir = run_dir / "tool" / "client-intake-hub"
    files = {
        "schema": tool_dir / "client-profile.schema.json",
        "commands": tool_dir / "command-api.json",
        "ui": tool_dir / "client-intake-hub.html",
        "docs": tool_dir / "operator-docs.md",
        "storage": tool_dir / "storage-leak-policy.json",
        "validation": tool_dir / "validation-plan.json",
    }
    write_json(
        files["schema"],
        {
            "schema_version": "cento.client_intake_hub.profile.v1",
            "fields": {
                "client_id": "string",
                "name": "string",
                "target_role": "string",
                "source_materials": ["resume", "linkedin", "job-description", "notes"],
                "deliverables": ["intake-synthesis", "resume-review", "linkedin-review", "action-plan"],
            },
            "fixture_profile": {
                "client_id": "fixture-client-001",
                "name": "Ada Lovelace",
                "target_role": "Principal platform engineer",
                "contains_real_client_data": False,
            },
        },
    )
    write_json(
        files["commands"],
        {
            "schema_version": "cento.client_intake_hub.commands.v1",
            "commands": [
                "cento crm intake init --person \"Ada Lovelace\"",
                "cento crm intake add --person \"Ada Lovelace\" --kind resume --file ./resume.pdf",
                "cento crm intake plan --person \"Ada Lovelace\"",
                "cento foundry status " + run_dir.name,
            ],
            "source_tool": "cento crm",
        },
    )
    write_text(
        files["ui"],
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Client Intake Hub</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, system-ui, sans-serif; background: #0b0f10; color: #e7ebe8; }
    body { margin: 0; padding: 32px; }
    main { max-width: 1120px; margin: 0 auto; display: grid; gap: 20px; }
    header { display: flex; align-items: end; justify-content: space-between; gap: 20px; border-bottom: 1px solid #26312d; padding-bottom: 18px; }
    h1 { margin: 0; font-size: 32px; letter-spacing: 0; }
    section { border: 1px solid #26312d; border-radius: 6px; padding: 18px; background: #101615; }
    .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
    .item { border: 1px solid #28352f; border-radius: 6px; padding: 14px; background: #0d1211; min-height: 96px; }
    .muted { color: #99a39d; }
    .ok { color: #1fd17f; font-weight: 700; }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Client Intake Hub</h1>
        <p class="muted">Career consulting fixture generated by Cento Tool Foundry.</p>
      </div>
      <div class="ok">Fixture Ready</div>
    </header>
    <section>
      <h2>Profile</h2>
      <div class="grid">
        <div class="item"><strong>Ada Lovelace</strong><br /><span class="muted">Fixture client</span></div>
        <div class="item"><strong>Principal platform engineer</strong><br /><span class="muted">Target role</span></div>
        <div class="item"><strong>No real client data</strong><br /><span class="muted">Privacy state</span></div>
      </div>
    </section>
    <section>
      <h2>Deliverables</h2>
      <div class="grid">
        <div class="item">Intake synthesis</div>
        <div class="item">Resume impact review</div>
        <div class="item">LinkedIn positioning review</div>
      </div>
    </section>
  </main>
</body>
</html>
""",
    )
    write_text(
        files["docs"],
        f"""
# Client Intake Hub Operator Notes

This fixture proves the Foundry pipeline for `{spec.get('domain', DEFAULT_DOMAIN)}` without using real client data.

The generated hub should become the private workspace for profile intake, source materials, deliverables, storage policy, and validation evidence.
""",
    )
    write_json(
        files["storage"],
        {
            "schema_version": "cento.client_intake_hub.storage.v1",
            "local_first": True,
            "oci_allowed": False,
            "public_access_allowed": False,
            "fixture_only": True,
            "blocked_real_inputs": ["resume", "linkedin export", "client notes", "private job search notes"],
        },
    )
    write_json(
        files["validation"],
        {
            "schema_version": "cento.client_intake_hub.validation.v1",
            "checks": [
                {"name": "profile schema exists", "type": "file_exists", "path": run_arg(files["schema"])},
                {"name": "ui preview exists", "type": "file_exists", "path": run_arg(files["ui"])},
                {"name": "storage policy blocks public access", "type": "json_value", "path": run_arg(files["storage"])},
            ],
        },
    )
    return {key: run_arg(path) for key, path in files.items()}


def client_intake_docs_page(run_dir: Path, spec: dict[str, Any], target_root: str) -> str:
    return f"""# Client Intake Hub

Client Intake Hub is the first real-file Tool Foundry bundle for the career consulting workflow. It is still fixture-only: it proves Cento can materialize a repo-ready tool surface without using real resumes, LinkedIn exports, private notes, or client PII.

## Current State

- `status`: materialized MVP
- `target_root`: `{target_root}`
- `domain`: `{spec.get('domain', DEFAULT_DOMAIN)}`
- `privacy`: fixture data only, local-first, no public upload

## Materialized Files

- `{target_root}/client-intake-hub.html`
- `{target_root}/client-profile.schema.json`
- `{target_root}/command-api.json`
- `{target_root}/storage-leak-policy.json`
- `{target_root}/validation-plan.json`
- `{target_root}/README.md`

## Preview

Run the CRM server and open the Studio view:

```bash
cento crm serve
```

The CRM exposes Foundry tool metadata at `/api/foundry/tools` and serves the generated preview from `/foundry/client-intake-hub/client-intake-hub.html`.

## Safety

- The bundle uses only the built-in Ada Lovelace fixture profile.
- Existing materialized files are not overwritten by Foundry unless their content is identical.
- OCI upload is not part of this MVP; storage remains local unless a later explicit storage promotion is approved.
"""


def stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def materialized_command_api_content() -> str:
    return stable_json(
        {
            "schema_version": "cento.client_intake_hub.commands.v1",
            "commands": [
                "cento crm intake init --person \"Ada Lovelace\"",
                "cento crm intake add --person \"Ada Lovelace\" --kind resume --file ./resume.pdf",
                "cento crm intake plan --person \"Ada Lovelace\"",
                "cento foundry status RUN_ID",
                "cento foundry materialize RUN_ID --target-root templates/foundry/client-intake-hub --dry-run --json",
            ],
            "source_tool": "cento crm",
        }
    )


def materialized_validation_plan_content(target_root: str) -> str:
    return stable_json(
        {
            "schema_version": "cento.client_intake_hub.validation.v1",
            "checks": [
                {"name": "profile schema exists", "type": "file_exists", "path": f"{target_root}/client-profile.schema.json"},
                {"name": "ui preview exists", "type": "file_exists", "path": f"{target_root}/client-intake-hub.html"},
                {"name": "storage policy blocks public access", "type": "json_value", "path": f"{target_root}/storage-leak-policy.json"},
                {"name": "CRM Foundry tools API returns metadata", "type": "http_get", "path": "/api/foundry/tools"},
            ],
        }
    )


def real_file_entries(run_dir: Path, spec: dict[str, Any], target_root: str) -> list[dict[str, str]]:
    seeded = seed_client_intake_hub(run_dir, spec)
    mapping = [
        ("schema", f"{target_root}/client-profile.schema.json", "client profile schema"),
        ("commands", f"{target_root}/command-api.json", "command api map"),
        ("ui", f"{target_root}/client-intake-hub.html", "no-build preview"),
        ("storage", f"{target_root}/storage-leak-policy.json", "storage and leak policy"),
        ("validation", f"{target_root}/validation-plan.json", "validation plan"),
        ("docs", f"{target_root}/README.md", "operator notes"),
    ]
    entries: list[dict[str, str]] = []
    for source_key, target_path, description in mapping:
        source_path = repo_path(seeded[source_key])
        if source_key == "commands":
            content = materialized_command_api_content()
        elif source_key == "validation":
            content = materialized_validation_plan_content(target_root)
        else:
            content = source_path.read_text(encoding="utf-8")
        entries.append(
            {
                "id": source_key,
                "description": description,
                "source_path": rel(source_path),
                "target_path": validate_real_file_target_path(target_path, target_root),
                "content": content.rstrip() + "\n",
                "privacy_class": "fixture-public-safe",
            }
        )
    docs_content = client_intake_docs_page(run_dir, spec, target_root)
    entries.append(
        {
            "id": "human-docs",
            "description": "human-facing Client Intake Hub docs page",
            "source_path": rel(run_dir / "foundry-spec.json"),
            "target_path": validate_real_file_target_path(DEFAULT_CLIENT_INTAKE_DOCS_PATH, target_root),
            "content": docs_content.rstrip() + "\n",
            "privacy_class": "fixture-public-safe",
        }
    )
    return entries


def write_real_file_manifest(run_dir: Path, spec: dict[str, Any], target_root: str, entries: list[dict[str, str]]) -> dict[str, Any]:
    manifest = {
        "schema_version": SCHEMA_REAL_FILE_MANIFEST,
        "run_id": run_dir.name,
        "fixture": spec.get("tool", {}).get("id", DEFAULT_FIXTURE),
        "target_root": target_root,
        "docs_path": DEFAULT_CLIENT_INTAKE_DOCS_PATH,
        "privacy": {
            "contains_real_client_data": False,
            "fixture_only": True,
            "cloud_upload_allowed": False,
        },
        "files": [
            {
                "id": item["id"],
                "description": item["description"],
                "source_path": item["source_path"],
                "target_path": item["target_path"],
                "content_sha256": sha256_text(item["content"]),
                "privacy_class": item["privacy_class"],
            }
            for item in entries
        ],
        "written_at": now_iso(),
    }
    write_json(run_dir / "real_file_manifest.json", manifest)
    return manifest


def build_materialization_plan(run_dir: Path, target_root: str, entries: list[dict[str, str]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    blocked = False
    for item in entries:
        target_path = validate_real_file_target_path(item["target_path"], target_root)
        target = ROOT / target_path
        content_hash = sha256_text(item["content"])
        existing_hash = ""
        if target.exists():
            existing = target.read_text(encoding="utf-8")
            existing_hash = sha256_text(existing)
            action = "skip_identical" if existing_hash == content_hash else "block_existing_changed"
        else:
            action = "write"
        if action == "block_existing_changed":
            blocked = True
        rows.append(
            {
                "id": item["id"],
                "target_path": target_path,
                "source_path": item["source_path"],
                "action": action,
                "exists": target.exists(),
                "content_sha256": content_hash,
                "existing_sha256": existing_hash,
                "privacy_class": item["privacy_class"],
            }
        )
    plan = {
        "schema_version": SCHEMA_MATERIALIZATION_PLAN,
        "run_id": run_dir.name,
        "target_root": target_root,
        "status": "blocked" if blocked else "ready",
        "files": rows,
        "blocked_reason": "existing changed target files would be overwritten" if blocked else "",
        "written_at": now_iso(),
    }
    write_json(run_dir / "materialization_plan.json", plan)
    return plan


def materialize_real_files(run_dir: Path, spec: dict[str, Any], *, target_root: str, apply: bool) -> dict[str, Any]:
    entries = real_file_entries(run_dir, spec, target_root)
    manifest = write_real_file_manifest(run_dir, spec, target_root, entries)
    plan = build_materialization_plan(run_dir, target_root, entries)
    written: list[dict[str, Any]] = []
    status = "blocked" if plan["status"] == "blocked" else ("materialized" if apply else "planned")
    if apply and plan["status"] == "ready":
        content_by_path = {item["target_path"]: item["content"] for item in entries}
        for row in plan["files"]:
            target_path = row["target_path"]
            if row["action"] == "skip_identical":
                written.append({**row, "status": "skipped_identical"})
                continue
            target = ROOT / target_path
            write_text(target, content_by_path[target_path])
            written.append({**row, "status": "written"})
    receipt = {
        "schema_version": SCHEMA_MATERIALIZATION_RECEIPT,
        "run_id": run_dir.name,
        "status": status,
        "mode": "apply" if apply else "dry-run",
        "target_root": target_root,
        "real_file_manifest": rel(run_dir / "real_file_manifest.json"),
        "materialization_plan": rel(run_dir / "materialization_plan.json"),
        "files": written if apply and plan["status"] == "ready" else plan["files"],
        "blocked_reason": plan.get("blocked_reason", ""),
        "applied": bool(apply and plan["status"] == "ready"),
        "file_count": len(manifest["files"]),
        "written_at": now_iso(),
    }
    write_json(run_dir / "materialization_receipt.json", receipt)
    return receipt


def write_demo_evidence(run_dir: Path, spec: dict[str, Any], seeded: dict[str, str]) -> dict[str, Any]:
    demo = {
        "schema_version": SCHEMA_DEMO,
        "run_id": run_dir.name,
        "tool": spec.get("tool", {}).get("id", DEFAULT_FIXTURE),
        "mode": "fixture",
        "preview": seeded.get("ui", ""),
        "claim": "Client Intake Hub fixture artifacts exist and are ready for deterministic Foundry validation.",
        "evidence": [
            seeded.get("schema", ""),
            seeded.get("commands", ""),
            seeded.get("ui", ""),
            seeded.get("docs", ""),
            seeded.get("storage", ""),
            seeded.get("validation", ""),
        ],
        "written_at": now_iso(),
    }
    write_json(run_dir / "demo-evidence.json", demo)
    write_text(
        run_dir / "demo-evidence.md",
        "\n".join(
            [
                "# Foundry Demo Evidence",
                "",
                f"- Run: `{run_dir.name}`",
                f"- Tool: `{demo['tool']}`",
                f"- Preview: `{demo['preview']}`",
                "- Mode: `fixture`",
                "",
            ]
        ),
    )
    return demo


def client_intake_fixture_targets() -> dict[str, str]:
    return {
        "schema": "docs/career-intake.md",
        "commands": "docs/crm-module.md",
        "ui": "standards/tui.md",
        "docs": "standards/tool-registration.md",
        "storage": "standards/mcp.md",
        "validation": "docs/validator-tier0.md",
    }


def write_summary(run_dir: Path, status: str, detail: str) -> None:
    write_text(
        run_dir / "summary.md",
        "\n".join(
            [
                "# Cento Tool Foundry Run",
                "",
                f"- Run: `{run_dir.name}`",
                f"- Status: `{status}`",
                f"- Detail: {detail}",
                f"- Updated: `{now_iso()}`",
                "",
                "## Core Artifacts",
                "",
                "- `foundry-spec.json`",
                "- `factory_handoff.json`",
                "- `workset.json`",
                "- `execution_receipt.json`",
                "- `cost_receipt.json`",
                "- `storage-policy.json`",
                "- `demo-evidence.json`",
                "- `validation_summary.json`",
                "- `real_file_manifest.json` (real-file mode)",
                "- `materialization_plan.json` (real-file mode)",
                "- `materialization_receipt.json` (real-file mode)",
            ]
        ),
    )


def build_spec(args: argparse.Namespace, run_dir: Path) -> dict[str, Any]:
    idea = str(args.idea or "client intake hub")
    fixture = str(getattr(args, "fixture", DEFAULT_FIXTURE) or DEFAULT_FIXTURE)
    domain = str(args.domain or DEFAULT_DOMAIN)
    return {
        "schema_version": SCHEMA_SPEC,
        "run_id": run_dir.name,
        "created_at": now_iso(),
        "idea": idea,
        "domain": domain,
        "mode": "tool_foundry",
        "max_parallel": int(args.max_parallel or 6),
        "budget": {
            "target_usd": float(args.budget_usd if args.budget_usd is not None else DEFAULT_BUDGET_USD),
            "hard_max_usd": float(args.max_budget_usd if args.max_budget_usd is not None else DEFAULT_MAX_BUDGET_USD),
            "live_requires_explicit_budget": True,
        },
        "tool": {
            "id": fixture,
            "title": "Client Intake Hub" if fixture == DEFAULT_FIXTURE else title_from_idea(idea),
            "domain": domain,
            "audience": "career consulting operator",
            "privacy": "fixture-only until real client data is explicitly supplied",
        },
        "pipeline": {
            "factory": "cento factory",
            "workset": "cento workset",
            "train": "cento parallel-delivery train",
            "storage": "cento object-storage / cento storage",
            "demo": "cento demo-evidence compatible manifest",
        },
    }


def command_create(args: argparse.Namespace) -> int:
    run_id = args.run_id or default_run_id(args.idea, args.domain)
    run_dir = repo_path(args.out) if args.out else resolve_run_dir(run_id, create=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    spec = build_spec(args, run_dir)
    seeded = seed_client_intake_hub(run_dir, spec)
    write_json(run_dir / "foundry-spec.json", spec)
    write_storage_policy(run_dir, spec)
    write_cost_receipt(run_dir, mode="created", runtime="none", budget_usd=args.budget_usd, max_budget_usd=args.max_budget_usd)
    write_demo_evidence(run_dir, spec, seeded)
    write_summary(run_dir, "created", "Foundry spec and Client Intake Hub fixture seed artifacts are ready.")
    append_event(run_dir, "foundry_created", {"tool": spec["tool"]["id"], "domain": spec["domain"]})
    payload = {"status": "created", "run_id": run_dir.name, "run_dir": rel(run_dir), "foundry_spec": rel(run_dir / "foundry-spec.json")}
    if not getattr(args, "quiet", False):
        output(payload, json_flag=args.json)
    return 0


def ensure_created(run_dir: Path) -> dict[str, Any]:
    spec = load_spec(run_dir)
    seeded = seed_client_intake_hub(run_dir, spec)
    write_storage_policy(run_dir, spec)
    if not (run_dir / "demo-evidence.json").exists():
        write_demo_evidence(run_dir, spec, seeded)
    return spec


def factory_request(spec: dict[str, Any]) -> str:
    title = str(spec.get("tool", {}).get("title") or "Client Intake Hub")
    domain = str(spec.get("domain") or DEFAULT_DOMAIN)
    return (
        f"Foundry create {domain} {title}: build a Cento-native internal consulting tool "
        "with CRM state, intake workflow, no-build UI preview, Docs, storage/leak policy, "
        "cost receipt, validation, and demo evidence."
    )


def run_factory_plan(run_dir: Path, spec: dict[str, Any]) -> dict[str, Any]:
    factory_dir = run_dir / "factory"
    request = factory_request(spec)
    package = f"foundry-{slugify(spec.get('tool', {}).get('id', DEFAULT_FIXTURE))}-v1"
    steps = [
        (
            "intake",
            [
                sys.executable,
                "scripts/factory.py",
                "intake",
                request,
                "--dry-run",
                "--out",
                run_arg(factory_dir),
                "--package",
                package,
                "--risk",
                "medium",
                "--json",
            ],
        ),
        ("plan", [sys.executable, "scripts/factory.py", "plan", run_arg(factory_dir), "--no-model", "--json"]),
        ("materialize", [sys.executable, "scripts/factory.py", "materialize", run_arg(factory_dir), "--json"]),
        ("queue", [sys.executable, "scripts/factory.py", "queue", run_arg(factory_dir), "--json"]),
        ("validate", [sys.executable, "scripts/factory.py", "validate", run_arg(factory_dir), "--json"]),
    ]
    receipts: list[dict[str, Any]] = []
    status = "passed"
    for name, command in steps:
        result = run_external(command)
        acceptable_blocked_validation = (
            name == "validate"
            and isinstance(result.payload, dict)
            and result.payload.get("schema_version") == "factory-validation-summary/v1"
            and result.payload.get("decision") == "blocked"
        )
        receipt = {"step": name, "accepted_blocked_validation": acceptable_blocked_validation, **result.receipt()}
        receipts.append(receipt)
        write_json(run_dir / "receipts" / f"factory-{name}.json", receipt)
        if result.returncode != 0 and not acceptable_blocked_validation:
            status = "failed"
            break
    handoff = {
        "schema_version": "cento.foundry.factory_handoff.v1",
        "run_id": run_dir.name,
        "status": status,
        "factory_run_dir": rel(factory_dir),
        "factory_plan": rel(factory_dir / "factory-plan.json"),
        "receipts": [rel(run_dir / "receipts" / f"factory-{item['step']}.json") for item in receipts],
        "written_at": now_iso(),
    }
    write_json(run_dir / "factory_handoff.json", handoff)
    return handoff


def build_workset(run_dir: Path, spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    seeded = seed_client_intake_hub(run_dir, spec)
    fixture_targets = client_intake_fixture_targets()
    tasks = [
        {
            "id": "crm-state-schema",
            "worker_id": "crm_schema",
            "task": "Refine Client Intake Hub CRM state schema fixture.",
            "description": "Keep the generated profile schema aligned with career consulting intake and deliverables.",
            "write_paths": [fixture_targets["schema"]],
            "read_paths": [rel(run_dir / "foundry-spec.json"), rel(run_dir / "factory" / "factory-plan.json")],
            "routes": ["crm", "factory"],
            "depends_on": [],
        },
        {
            "id": "command-api",
            "worker_id": "command_api",
            "task": "Refine Client Intake Hub command API fixture.",
            "description": "Keep the generated command map routed through existing Cento CRM and Foundry commands.",
            "write_paths": [fixture_targets["commands"]],
            "read_paths": [rel(run_dir / "foundry-spec.json")],
            "routes": ["crm", "foundry"],
            "depends_on": ["crm-state-schema"],
        },
        {
            "id": "ui-preview",
            "worker_id": "ui_preview",
            "task": "Refine Client Intake Hub no-build UI preview.",
            "description": "Keep the generated preview usable for operator review without introducing a build stack.",
            "write_paths": [fixture_targets["ui"]],
            "read_paths": [rel(run_dir / "foundry-spec.json")],
            "routes": ["crm", "docs"],
            "depends_on": ["crm-state-schema"],
        },
        {
            "id": "docs-and-operator-notes",
            "worker_id": "docs_operator",
            "task": "Refine operator Docs for the Client Intake Hub fixture.",
            "description": "Keep the generated Docs clear about fixture data, privacy, commands, and next steps.",
            "write_paths": [fixture_targets["docs"]],
            "read_paths": [rel(run_dir / "foundry-spec.json"), seeded["commands"]],
            "routes": ["docs", "crm"],
            "depends_on": ["command-api"],
        },
        {
            "id": "storage-leak-policy",
            "worker_id": "storage_policy",
            "task": "Refine Client Intake Hub storage and leak policy fixture.",
            "description": "Keep private-by-default storage, OCI eligibility, and blocked data categories explicit.",
            "write_paths": [fixture_targets["storage"]],
            "read_paths": [rel(run_dir / "storage-policy.json")],
            "routes": ["storage", "object-storage"],
            "depends_on": ["crm-state-schema"],
        },
        {
            "id": "validation-demo-evidence",
            "worker_id": "validation_demo",
            "task": "Refine Client Intake Hub validation and demo evidence fixture.",
            "description": "Keep validation and demo evidence paths aligned with the generated tool artifacts.",
            "write_paths": [fixture_targets["validation"]],
            "read_paths": [rel(run_dir / "demo-evidence.json"), rel(run_dir / "cost_receipt.json")],
            "routes": ["demo-evidence", "validation"],
            "depends_on": ["ui-preview", "docs-and-operator-notes", "storage-leak-policy"],
        },
    ]
    workset = {
        "schema_version": "cento.workset.v1",
        "id": f"foundry_{slugify(run_dir.name)}_{slugify(spec.get('tool', {}).get('id', DEFAULT_FIXTURE))}",
        "mode": "fast",
        "max_parallel": int(spec.get("max_parallel") or 6),
        "tasks": tasks,
    }
    workset_path = run_dir / "workset.json"
    write_json(workset_path, workset)
    result = run_external([sys.executable, "scripts/cento_workset.py", "check", run_arg(workset_path), "--json"])
    check = result.payload if isinstance(result.payload, dict) else {"status": "failed", "errors": [result.stderr or result.stdout]}
    write_json(run_dir / "workset_check.json", check)
    write_json(run_dir / "receipts" / "workset-check.json", result.receipt())
    return workset, check


def command_plan(args: argparse.Namespace) -> int:
    run_dir = resolve_run_dir(args.run_id, create=False)
    spec = ensure_created(run_dir)
    handoff = run_factory_plan(run_dir, spec)
    workset, check = build_workset(run_dir, spec)
    status = "planned" if handoff.get("status") == "passed" and check.get("status") == "passed" else "blocked"
    receipt = {
        "schema_version": SCHEMA_PLAN,
        "run_id": run_dir.name,
        "status": status,
        "factory_handoff": rel(run_dir / "factory_handoff.json"),
        "workset": rel(run_dir / "workset.json"),
        "workset_check": rel(run_dir / "workset_check.json"),
        "task_count": len(workset.get("tasks", [])),
        "written_at": now_iso(),
    }
    write_json(run_dir / "plan_receipt.json", receipt)
    write_summary(run_dir, status, "Factory handoff and Workset manifest generated.")
    append_event(run_dir, "foundry_planned", {"status": status, "tasks": receipt["task_count"]})
    payload = {"status": status, "run_id": run_dir.name, "run_dir": rel(run_dir), **receipt}
    if not getattr(args, "quiet", False):
        output(payload, json_flag=args.json)
    return 0 if status == "planned" else 1


def require_live_budget(runtime: str, budget_usd: float | None, max_budget_usd: float | None) -> None:
    if runtime != "api-openai":
        return
    if budget_usd is None or max_budget_usd is None:
        raise SystemExit("live/api-openai Foundry execution requires both --budget-usd and --max-budget-usd")
    if budget_usd <= 0 or max_budget_usd <= 0:
        raise SystemExit("Foundry budgets must be positive")
    if budget_usd > max_budget_usd:
        raise SystemExit("--budget-usd must be less than or equal to --max-budget-usd")
    if max_budget_usd > DEFAULT_MAX_BUDGET_USD:
        raise SystemExit(f"Foundry v1 hard cap cannot exceed ${DEFAULT_MAX_BUDGET_USD:.0f}")


def train_run_id(run_dir: Path, explicit: str = "") -> str:
    return explicit or f"foundry-{slugify(run_dir.name)}-train"


def read_train_cost(payload: dict[str, Any]) -> float:
    train_run_dir = payload.get("run_dir")
    if isinstance(train_run_dir, str) and train_run_dir:
        receipt = read_json(repo_path(train_run_dir) / "train_receipt.json")
        value = receipt.get("workset_total_cost_usd", receipt.get("total_cost_usd", 0.0))
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def command_execute(args: argparse.Namespace) -> int:
    run_dir = resolve_run_dir(args.run_id, create=False)
    spec = ensure_created(run_dir)
    if not (run_dir / "workset.json").exists():
        plan_args = argparse.Namespace(run_id=args.run_id, json=False, quiet=True)
        if command_plan(plan_args) != 0:
            return 1
    runtime = str(args.runtime or "fixture")
    require_live_budget(runtime, args.budget_usd, args.max_budget_usd)
    train_id = train_run_id(run_dir, args.train_run_id)
    command = [
        sys.executable,
        "scripts/parallel_delivery.py",
        "train",
        "e2e",
        "--workset",
        run_arg(run_dir / "workset.json"),
        "--max-parallel",
        str(int(args.max_parallel or spec.get("max_parallel") or 6)),
        "--runtime",
        runtime,
        "--validation",
        str(args.validation or "smoke"),
        "--allow-dirty-owned",
        "--run-id",
        train_id,
        "--dry-run",
        "--json",
    ]
    if runtime == "api-openai":
        command.extend(["--budget-usd", str(args.budget_usd), "--max-budget-usd", str(args.max_budget_usd)])
    result = run_external(command)
    write_json(run_dir / "train_e2e_result.json", result.receipt())
    payload = result.payload if isinstance(result.payload, dict) else {}
    actual_cost = read_train_cost(payload)
    write_cost_receipt(
        run_dir,
        mode="live" if runtime == "api-openai" else "dry-run",
        runtime=runtime,
        budget_usd=args.budget_usd,
        max_budget_usd=args.max_budget_usd,
        actual_cost_usd=actual_cost,
        ai_calls_used=0 if runtime == "fixture" else -1,
    )
    status = "completed" if result.returncode == 0 and payload.get("status") == "completed" else "blocked"
    receipt = {
        "schema_version": SCHEMA_EXECUTION,
        "run_id": run_dir.name,
        "status": status,
        "runtime": runtime,
        "train_run_id": train_id,
        "train_run_dir": payload.get("run_dir", ""),
        "train_manifest": payload.get("train_manifest", ""),
        "workset_receipt": payload.get("workset_receipt", ""),
        "validation": payload.get("validation", "unknown"),
        "promotion": payload.get("promotion", "unknown"),
        "factory_run_dir": payload.get("factory_run_dir", ""),
        "cost_receipt": rel(run_dir / "cost_receipt.json"),
        "written_at": now_iso(),
    }
    write_json(run_dir / "execution_receipt.json", receipt)
    write_summary(run_dir, status, "Workset train executed and promoted through Factory dry-run handoff.")
    append_event(run_dir, "foundry_executed", {"status": status, "runtime": runtime, "train_run_id": train_id})
    out = {"status": status, "run_id": run_dir.name, "run_dir": rel(run_dir), **receipt}
    if not getattr(args, "quiet", False):
        output(out, json_flag=args.json)
    return 0 if status == "completed" else 1


def command_promote(args: argparse.Namespace) -> int:
    if args.apply and args.dry_run:
        print("foundry promote accepts either --dry-run or --apply, not both.", file=sys.stderr)
        return 2
    run_dir = resolve_run_dir(args.run_id, create=False)
    execution = read_json(run_dir / "execution_receipt.json")
    train_id = str(execution.get("train_run_id") or "")
    if not train_id:
        raise SystemExit("Foundry run has no execution_receipt.json with train_run_id")
    command = [sys.executable, "scripts/parallel_delivery.py", "train", "promote", train_id, "--json"]
    if args.apply:
        command.append("--apply")
    else:
        command.append("--dry-run")
    result = run_external(command)
    write_json(run_dir / "promotion_receipt.json", result.receipt())
    payload = result.payload if isinstance(result.payload, dict) else {}
    status = "completed" if result.returncode == 0 and payload.get("status") in {"planned", "completed"} else "blocked"
    append_event(run_dir, "foundry_promoted", {"status": status, "train_run_id": train_id})
    out = {"status": status, "run_id": run_dir.name, "run_dir": rel(run_dir), "promotion_receipt": rel(run_dir / "promotion_receipt.json"), **payload}
    output(out, json_flag=args.json)
    return 0 if status == "completed" else 1


def command_materialize(args: argparse.Namespace) -> int:
    if args.apply and args.dry_run:
        print("foundry materialize accepts either --dry-run or --apply, not both.", file=sys.stderr)
        return 2
    run_dir = resolve_run_dir(args.run_id, create=False)
    spec = ensure_created(run_dir)
    try:
        target_root = normalize_real_file_target_root(args.target_root)
    except ValueError as exc:
        print(f"foundry materialize: {exc}", file=sys.stderr)
        return 2
    apply_files = bool(args.apply)
    try:
        receipt = materialize_real_files(run_dir, spec, target_root=target_root, apply=apply_files)
    except (OSError, ValueError) as exc:
        print(f"foundry materialize: {exc}", file=sys.stderr)
        return 1
    append_event(
        run_dir,
        "foundry_materialized",
        {"status": receipt["status"], "mode": receipt["mode"], "target_root": target_root},
    )
    payload = {"run_id": run_dir.name, "run_dir": rel(run_dir), "materialization_receipt": rel(run_dir / "materialization_receipt.json"), **receipt}
    if not getattr(args, "quiet", False):
        output(payload, json_flag=args.json)
    return 0 if receipt["status"] in {"planned", "materialized"} else 1


def validate_run(run_dir: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    spec = read_json(run_dir / "foundry-spec.json")
    workset_check = read_json(run_dir / "workset_check.json")
    execution = read_json(run_dir / "execution_receipt.json")
    cost = read_json(run_dir / "cost_receipt.json")
    storage = read_json(run_dir / "storage-policy.json")
    demo = read_json(run_dir / "demo-evidence.json")
    real_file_manifest = read_json(run_dir / "real_file_manifest.json")
    materialization = read_json(run_dir / "materialization_receipt.json")

    add_check("foundry spec", spec.get("schema_version") == SCHEMA_SPEC, rel(run_dir / "foundry-spec.json"))
    add_check("factory handoff", (run_dir / "factory_handoff.json").exists(), rel(run_dir / "factory_handoff.json"))
    add_check("workset manifest", (run_dir / "workset.json").exists(), rel(run_dir / "workset.json"))
    add_check("workset check passed", workset_check.get("status") == "passed", str(workset_check.get("errors") or ""))
    add_check("execution completed", execution.get("status") == "completed", str(execution.get("train_run_id") or ""))
    add_check("train validation passed", execution.get("validation") == "passed", str(execution.get("validation") or "unknown"))
    add_check("factory promotion ready", str(execution.get("promotion") or "") in {"ready_for_apply", "applied"}, str(execution.get("promotion") or "unknown"))
    add_check("cost receipt", cost.get("schema_version") == SCHEMA_COST and not bool(cost.get("hard_cap_exceeded")), rel(run_dir / "cost_receipt.json"))
    add_check("storage private by default", storage.get("public_access") == "blocked", rel(run_dir / "storage-policy.json"))
    add_check("demo evidence", demo.get("schema_version") == SCHEMA_DEMO, rel(run_dir / "demo-evidence.json"))
    if real_file_manifest or materialization:
        materialized_status = materialization.get("status")
        add_check("real-file manifest", real_file_manifest.get("schema_version") == SCHEMA_REAL_FILE_MANIFEST, rel(run_dir / "real_file_manifest.json"))
        add_check(
            "materialization receipt",
            materialization.get("schema_version") == SCHEMA_MATERIALIZATION_RECEIPT and materialized_status in {"planned", "materialized"},
            str(materialized_status or "missing"),
        )
        add_check(
            "real-file privacy",
            real_file_manifest.get("privacy", {}).get("contains_real_client_data") is False
            and real_file_manifest.get("privacy", {}).get("cloud_upload_allowed") is False,
            rel(run_dir / "real_file_manifest.json"),
        )

    status = "passed" if all(item["passed"] for item in checks) else "failed"
    summary = {
        "schema_version": SCHEMA_VALIDATION,
        "run_id": run_dir.name,
        "status": status,
        "checks": checks,
        "written_at": now_iso(),
    }
    write_json(run_dir / "validation_summary.json", summary)
    write_text(
        run_dir / "validation_summary.md",
        "\n".join(
            ["# Foundry Validation", "", f"- Run: `{run_dir.name}`", f"- Status: `{status}`", "", "## Checks", ""]
            + [f"- [{'x' if item['passed'] else ' '}] {item['name']}: {item['detail']}" for item in checks]
        ),
    )
    return summary


def command_validate(args: argparse.Namespace) -> int:
    run_dir = resolve_run_dir(args.run_id, create=False)
    summary = validate_run(run_dir)
    append_event(run_dir, "foundry_validated", {"status": summary["status"]})
    payload = {"run_id": run_dir.name, "run_dir": rel(run_dir), **summary}
    output(payload, json_flag=args.json)
    return 0 if summary["status"] == "passed" else 1


def command_status(args: argparse.Namespace) -> int:
    run_dir = resolve_run_dir(args.run_id, create=False)
    spec = read_json(run_dir / "foundry-spec.json")
    plan = read_json(run_dir / "plan_receipt.json")
    execution = read_json(run_dir / "execution_receipt.json")
    validation = read_json(run_dir / "validation_summary.json")
    cost = read_json(run_dir / "cost_receipt.json")
    materialization = read_json(run_dir / "materialization_receipt.json")
    payload = {
        "status": validation.get("status") or execution.get("status") or plan.get("status") or ("created" if spec else "missing"),
        "run_id": run_dir.name,
        "run_dir": rel(run_dir),
        "tool": spec.get("tool", {}).get("id", ""),
        "domain": spec.get("domain", ""),
        "plan": plan.get("status", "unknown"),
        "execution": execution.get("status", "unknown"),
        "validation": validation.get("status", "unknown"),
        "materialization": materialization.get("status", "not_run"),
        "materialization_receipt": rel(run_dir / "materialization_receipt.json") if materialization else "",
        "actual_cost_usd": cost.get("actual_cost_usd", 0),
        "max_budget_usd": cost.get("max_budget_usd", 0),
        "summary": rel(run_dir / "summary.md") if (run_dir / "summary.md").exists() else "",
    }
    output(payload, json_flag=args.json)
    return 0


def command_e2e(args: argparse.Namespace) -> int:
    if args.live and args.dry_run:
        print("foundry e2e accepts either --dry-run or --live, not both.", file=sys.stderr)
        return 2
    if args.materialize_apply and not args.real_files:
        print("foundry e2e --materialize-apply requires --real-files.", file=sys.stderr)
        return 2
    runtime = "api-openai" if args.live else "fixture"
    require_live_budget(runtime, args.budget_usd, args.max_budget_usd)
    idea = args.idea or "client intake hub"
    create_args = argparse.Namespace(
        idea=idea,
        domain=args.domain,
        fixture=args.fixture,
        run_id=args.run_id or default_run_id(idea, args.domain),
        out=args.out,
        max_parallel=args.max_parallel,
        budget_usd=args.budget_usd,
        max_budget_usd=args.max_budget_usd,
        json=False,
        quiet=True,
    )
    if command_create(create_args) != 0:
        return 1
    run_dir = repo_path(args.out) if args.out else resolve_run_dir(create_args.run_id)
    if command_plan(argparse.Namespace(run_id=run_arg(run_dir), json=False, quiet=True)) != 0:
        return 1
    execute_code = command_execute(
        argparse.Namespace(
            run_id=run_arg(run_dir),
            runtime=runtime,
            train_run_id="",
            budget_usd=args.budget_usd,
            max_budget_usd=args.max_budget_usd,
            max_parallel=args.max_parallel,
            validation=args.validation,
            json=False,
            quiet=True,
        )
    )
    validation: dict[str, Any] = {"status": "not_run"}
    materialization: dict[str, Any] = {"status": "not_run"}
    if execute_code == 0:
        validation = validate_run(run_dir)
        append_event(run_dir, "foundry_e2e_validated", {"status": validation["status"]})
    if execute_code == 0 and validation.get("status") == "passed" and args.real_files:
        materialize_args = argparse.Namespace(
            run_id=run_arg(run_dir),
            target_root=args.target_root,
            dry_run=not bool(args.materialize_apply),
            apply=bool(args.materialize_apply),
            json=False,
            quiet=True,
        )
        materialize_code = command_materialize(materialize_args)
        materialization = read_json(run_dir / "materialization_receipt.json")
        if materialize_code == 0:
            validation = validate_run(run_dir)
            append_event(run_dir, "foundry_e2e_materialized", {"status": materialization.get("status", "unknown")})
        else:
            validation = {"status": "failed"}
    status = (
        "passed"
        if execute_code == 0
        and validation.get("status") == "passed"
        and (not args.real_files or materialization.get("status") in {"planned", "materialized"})
        else "failed"
    )
    payload = {
        "status": status,
        "mode": "live" if args.live else "dry-run",
        "real_files": bool(args.real_files),
        "run_id": run_dir.name,
        "run_dir": rel(run_dir),
        "validation": validation.get("status", "not_run"),
        "materialization": materialization.get("status", "not_run"),
        "foundry_spec": rel(run_dir / "foundry-spec.json"),
        "execution_receipt": rel(run_dir / "execution_receipt.json"),
        "validation_summary": rel(run_dir / "validation_summary.json"),
        "cost_receipt": rel(run_dir / "cost_receipt.json"),
        "materialization_receipt": rel(run_dir / "materialization_receipt.json") if (run_dir / "materialization_receipt.json").exists() else "",
    }
    output(payload, json_flag=args.json)
    return 0 if status == "passed" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create Cento-native business tools through Factory, Workset, train, storage, and evidence gates.")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create a Foundry run spec and seed fixture tool artifacts.")
    create.add_argument("idea")
    create.add_argument("--domain", default=DEFAULT_DOMAIN)
    create.add_argument("--fixture", default=DEFAULT_FIXTURE, choices=[DEFAULT_FIXTURE])
    create.add_argument("--run-id", default="")
    create.add_argument("--out", default="")
    create.add_argument("--max-parallel", type=int, default=6)
    create.add_argument("--budget-usd", type=float, default=None)
    create.add_argument("--max-budget-usd", type=float, default=None)
    create.add_argument("--json", action="store_true")
    create.set_defaults(func=command_create)

    plan = sub.add_parser("plan", help="Generate Factory handoff, Workset manifest, and validation-ready plan receipt.")
    plan.add_argument("run_id")
    plan.add_argument("--json", action="store_true")
    plan.set_defaults(func=command_plan)

    execute = sub.add_parser("execute", help="Execute the generated Workset through parallel-delivery train e2e.")
    execute.add_argument("run_id")
    execute.add_argument("--runtime", choices=["fixture", "api-openai"], default="fixture")
    execute.add_argument("--train-run-id", default="")
    execute.add_argument("--budget-usd", type=float, default=None)
    execute.add_argument("--max-budget-usd", type=float, default=None)
    execute.add_argument("--max-parallel", type=int, default=0)
    execute.add_argument("--validation", default="smoke")
    execute.add_argument("--json", action="store_true")
    execute.set_defaults(func=command_execute)

    promote = sub.add_parser("promote", help="Re-run Factory promotion for the Foundry train run.")
    promote.add_argument("run_id")
    promote.add_argument("--dry-run", action="store_true")
    promote.add_argument("--apply", action="store_true")
    promote.add_argument("--json", action="store_true")
    promote.set_defaults(func=command_promote)

    materialize = sub.add_parser("materialize", help="Plan or apply repo-ready files from a Foundry run.")
    materialize.add_argument("run_id")
    materialize.add_argument("--target-root", default=DEFAULT_REAL_FILE_TARGET_ROOT)
    materialize_mode = materialize.add_mutually_exclusive_group()
    materialize_mode.add_argument("--dry-run", action="store_true")
    materialize_mode.add_argument("--apply", action="store_true")
    materialize.add_argument("--json", action="store_true")
    materialize.set_defaults(func=command_materialize)

    status = sub.add_parser("status", help="Show Foundry run status.")
    status.add_argument("run_id")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=command_status)

    validate = sub.add_parser("validate", help="Validate required Foundry receipts and gates.")
    validate.add_argument("run_id")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_validate)

    e2e = sub.add_parser("e2e", help="Create, plan, execute, promote, and validate a fixture Foundry run.")
    e2e.add_argument("--fixture", default=DEFAULT_FIXTURE, choices=[DEFAULT_FIXTURE])
    e2e.add_argument("--idea", default="client intake hub")
    e2e.add_argument("--domain", default=DEFAULT_DOMAIN)
    e2e.add_argument("--run-id", default="")
    e2e.add_argument("--out", default="")
    e2e.add_argument("--max-parallel", type=int, default=6)
    mode = e2e.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--live", action="store_true")
    e2e.add_argument("--real-files", action="store_true", help="Plan real repo files after the fixture train validates.")
    e2e.add_argument("--target-root", default=DEFAULT_REAL_FILE_TARGET_ROOT, help="Repo-relative target root for --real-files.")
    e2e.add_argument("--materialize-apply", action="store_true", help="Apply real files during --real-files e2e instead of dry-run planning.")
    e2e.add_argument("--budget-usd", type=float, default=None)
    e2e.add_argument("--max-budget-usd", type=float, default=None)
    e2e.add_argument("--validation", default="smoke")
    e2e.add_argument("--json", action="store_true")
    e2e.set_defaults(func=command_e2e)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
