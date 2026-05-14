#!/usr/bin/env python3

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import mimetypes
import os
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = ROOT / "workspace" / "runs" / "object-storage"
SCHEMA_VERSION = "cento.object_storage_mvp.v1"
E2E_SCHEMA_VERSION = "cento.object_storage_mvp_e2e.v1"
IMAGE_MIGRATION_SCHEMA_VERSION = "cento.object_storage_image_migration.v1"
IMAGE_UPLOAD_SCHEMA_VERSION = "cento.object_storage_image_upload.v1"
IMAGE_VERIFY_SCHEMA_VERSION = "cento.object_storage_image_verify.v1"
DEFAULT_IMAGE_BUCKET = "cento-images-standard"
DEFAULT_IMAGE_ROOT = ROOT / "workspace" / "runs"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".xwd"}
SKIPPED_DIRS = {".git", ".venv", "__pycache__", "node_modules", "venv"}
SENSITIVE_NAME_FRAGMENTS = {"token", "secret"}
STANDARD_OBJECT_STORAGE_RATE_PER_GIB_MONTH = 0.0255


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def run_id(prefix: str = "object-storage") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}"


def repo_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def env_first(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def configured_bucket(value: str = "") -> str:
    return value.strip() or env_first("CENTO_OBJECT_STORAGE_BUCKET", "CENTO_OCI_BUCKET", "OCI_OBJECT_STORAGE_BUCKET")


def configured_namespace(value: str = "") -> str:
    return value.strip() or env_first("CENTO_OBJECT_STORAGE_NAMESPACE", "CENTO_OCI_NAMESPACE", "OCI_OBJECT_STORAGE_NAMESPACE")


def configured_compartment(value: str = "") -> str:
    return value.strip() or env_first("CENTO_OBJECT_STORAGE_COMPARTMENT_ID", "CENTO_OCI_COMPARTMENT_ID", "OCI_COMPARTMENT_ID")


def configured_region(value: str = "") -> str:
    return value.strip() or env_first("CENTO_OBJECT_STORAGE_REGION", "CENTO_OCI_REGION", "OCI_CLI_REGION", "OCI_REGION")


def configured_prefix(value: str = "") -> str:
    return (value.strip() or env_first("CENTO_OBJECT_STORAGE_PREFIX") or "cento/dummy").strip("/")


def safe_uploaded_path(root: Path, object_name: str) -> Path:
    parts = [part for part in PurePosixPath(object_name).parts if part not in {"", ".", ".."}]
    if not parts:
        parts = ["dummy.txt"]
    return root.joinpath(*parts)


def configured_image_bucket(value: str = "") -> str:
    return configured_bucket(value) or DEFAULT_IMAGE_BUCKET


def tenancy_from_config(config_file: str = "", profile: str = "") -> str:
    config_path = Path(config_file).expanduser() if config_file else Path.home() / ".oci" / "config"
    if not config_path.exists():
        return ""
    parser = configparser.RawConfigParser()
    parser.read(config_path)
    section = profile or "DEFAULT"
    if parser.has_section(section):
        return parser.get(section, "tenancy", fallback="").strip()
    return parser.defaults().get("tenancy", "").strip()


def image_content_type(path: Path) -> str:
    if path.suffix.lower() == ".xwd":
        return "application/octet-stream"
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def is_sensitive_image_path(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    name = path.name.lower()
    if name == "key4.db" or name.endswith(".pem") or name.startswith(".env"):
        return True
    if any(part.startswith(".env") for part in parts):
        return True
    return any(fragment in part for fragment in SENSITIVE_NAME_FRAGMENTS for part in parts)


def image_artifact_class(path: Path) -> str:
    suffix = path.suffix.lower()
    lower_parts = [part.lower() for part in path.parts]
    if suffix == ".xwd":
        return "screenshot_raw"
    if suffix in IMAGE_SUFFIXES and any("screenshot" in part for part in lower_parts):
        return "screenshot_normalized"
    return "image"


def image_sensitivity(path: Path, blocked: bool) -> str:
    if blocked:
        return "secret_risk"
    return "internal"


def iter_image_files(root: Path) -> list[Path]:
    if not root.exists():
        raise SystemExit(f"Image root does not exist: {root}")
    files: list[Path] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [item for item in dirs if item not in SKIPPED_DIRS]
        current_path = Path(current)
        for name in names:
            path = current_path / name
            if path.is_symlink() or not path.is_file():
                continue
            if path.suffix.lower() in IMAGE_SUFFIXES:
                files.append(path)
    return sorted(files)


def object_name_for_image(path: Path, sha256: str) -> str:
    filename = PurePosixPath(path.name).name or "image"
    return f"cento/images/v1/objects/sha256/{sha256[:2]}/{sha256}/{filename}"


def object_uri(namespace: str, bucket: str, object_name: str) -> str:
    return f"oci://{namespace or '<namespace>'}/{bucket or '<bucket>'}/{object_name}"


def parse_json_stdout(result: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(result.get("stdout") or "{}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Expected JSON output from `{result.get('command')}`: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected JSON object from `{result.get('command')}`")
    return payload


def oci_global_args(args: argparse.Namespace) -> list[str]:
    global_args: list[str] = []
    if getattr(args, "region", ""):
        global_args.extend(["--region", str(args.region)])
    if getattr(args, "config_file", ""):
        global_args.extend(["--config-file", str(args.config_file)])
    if getattr(args, "profile", ""):
        global_args.extend(["--profile", str(args.profile)])
    return global_args


def run_command(command: list[str], cwd: Path = ROOT) -> dict[str, Any]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    return {
        "command": shlex.join(command),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def render_summary(path: Path, receipt: dict[str, Any]) -> None:
    lines = [
        "# Cento Object Storage MVP",
        "",
        f"- status: `{receipt.get('status', '')}`",
        f"- mode: `{receipt.get('mode', '')}`",
        f"- bucket: `{receipt.get('bucket') or 'not configured'}`",
        f"- namespace: `{receipt.get('namespace') or 'auto'}`",
        f"- object: `{receipt.get('object_name', '')}`",
        f"- dummy file: `{receipt.get('dummy_file', '')}`",
        f"- sha256: `{receipt.get('sha256', '')}`",
        f"- receipt: `{receipt.get('receipt', '')}`",
    ]
    if receipt.get("error"):
        lines.extend(["", "## Error", "", str(receipt["error"])])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def base_receipt(args: argparse.Namespace, out: Path, dummy_file: Path, object_name: str, mode: str) -> dict[str, Any]:
    bucket = configured_bucket(getattr(args, "bucket", ""))
    namespace = configured_namespace(getattr(args, "namespace", ""))
    region = configured_region(getattr(args, "region", ""))
    receipt_path = out / "receipt.json"
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": out.name,
        "status": "initialized",
        "mode": mode,
        "written_at": now_iso(),
        "bucket": bucket,
        "namespace": namespace,
        "region": region,
        "object_name": object_name,
        "object_uri": f"oci://{namespace or '<namespace>'}/{bucket or '<bucket>'}/{object_name}",
        "dummy_file": rel(dummy_file),
        "receipt": rel(receipt_path),
        "summary": rel(out / "summary.md"),
        "sha256": sha256_file(dummy_file),
        "size_bytes": dummy_file.stat().st_size,
        "oci_cli": shutil.which(getattr(args, "oci_bin", "oci")) or getattr(args, "oci_bin", "oci"),
    }


def write_dummy_file(out: Path, content: str) -> Path:
    dummy_file = out / "dummy.txt"
    dummy_file.parent.mkdir(parents=True, exist_ok=True)
    dummy_file.write_text(content, encoding="utf-8")
    return dummy_file


def object_name_for(args: argparse.Namespace, current_run_id: str) -> str:
    if getattr(args, "object_name", ""):
        return str(args.object_name).strip().lstrip("/")
    prefix = configured_prefix(getattr(args, "prefix", ""))
    return f"{prefix}/{current_run_id}/dummy.txt" if prefix else f"{current_run_id}/dummy.txt"


def put_dummy(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    current_run_id = str(getattr(args, "run_id", "") or run_id()).strip()
    out = repo_path(getattr(args, "out", "") or DEFAULT_RUN_ROOT / current_run_id)
    out.mkdir(parents=True, exist_ok=True)
    object_name = object_name_for(args, current_run_id)
    dummy_file = write_dummy_file(out, getattr(args, "content", "") or "cento object storage dummy\n")
    mode = "dry-run" if getattr(args, "dry_run", False) else "live"
    receipt = base_receipt(args, out, dummy_file, object_name, mode)
    receipt_path = out / "receipt.json"

    if mode == "dry-run":
        uploaded = safe_uploaded_path(out / "uploaded", object_name)
        uploaded.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(dummy_file, uploaded)
        receipt.update(
            {
                "status": "uploaded-dry-run",
                "uploaded_copy": rel(uploaded),
                "verified": sha256_file(uploaded) == receipt["sha256"],
                "note": "Dry-run copied the dummy file into the run-scoped uploaded/ directory instead of calling OCI.",
            }
        )
        write_json(receipt_path, receipt)
        render_summary(out / "summary.md", receipt)
        return 0, receipt

    if not receipt["bucket"]:
        receipt.update(
            {
                "status": "blocked",
                "error": "Missing bucket. Pass --bucket or set CENTO_OBJECT_STORAGE_BUCKET.",
            }
        )
        write_json(receipt_path, receipt)
        render_summary(out / "summary.md", receipt)
        return 2, receipt

    command = [
        getattr(args, "oci_bin", "oci"),
        "os",
        "object",
        "put",
        "--bucket-name",
        receipt["bucket"],
        "--file",
        str(dummy_file),
        "--name",
        object_name,
        "--force",
        "--no-multipart",
        "--content-type",
        "text/plain",
        *oci_global_args(args),
    ]
    if receipt["namespace"]:
        command.extend(["--namespace-name", receipt["namespace"]])

    command_result = run_command(command)
    (out / "oci.stdout.log").write_text(command_result["stdout"], encoding="utf-8")
    (out / "oci.stderr.log").write_text(command_result["stderr"], encoding="utf-8")
    receipt["oci"] = {
        "command": command_result["command"],
        "returncode": command_result["returncode"],
        "stdout_log": rel(out / "oci.stdout.log"),
        "stderr_log": rel(out / "oci.stderr.log"),
    }
    if command_result["returncode"] == 0:
        receipt["status"] = "uploaded"
        receipt["verified"] = True
    else:
        receipt["status"] = "failed"
        receipt["verified"] = False
        receipt["error"] = command_result["stderr"].strip() or "OCI object put failed"

    write_json(receipt_path, receipt)
    render_summary(out / "summary.md", receipt)
    return (0 if receipt["status"] == "uploaded" else 1), receipt


def status(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    oci_bin = getattr(args, "oci_bin", "oci")
    oci_path = shutil.which(oci_bin) or ""
    config_file = Path(getattr(args, "config_file", "") or Path.home() / ".oci" / "config")
    payload: dict[str, Any] = {
        "schema_version": "cento.object_storage_status.v1",
        "ok": bool(oci_path and config_file.exists()),
        "oci_cli": oci_path,
        "config_file": str(config_file),
        "config_exists": config_file.exists(),
        "bucket_configured": bool(configured_bucket(getattr(args, "bucket", ""))),
        "namespace_configured": bool(configured_namespace(getattr(args, "namespace", ""))),
        "compartment_configured": bool(configured_compartment(getattr(args, "compartment_id", ""))),
        "region": configured_region(getattr(args, "region", "")),
    }
    if getattr(args, "probe", False) and oci_path:
        command = [oci_bin, "os", "ns", "get", *oci_global_args(args)]
        probe = run_command(command)
        payload["probe"] = {
            "command": probe["command"],
            "returncode": probe["returncode"],
            "stdout": probe["stdout"],
            "stderr": probe["stderr"],
        }
        payload["ok"] = payload["ok"] and probe["returncode"] == 0
    return (0 if payload["ok"] else 1), payload


def run_e2e(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    current_run_id = str(getattr(args, "run_id", "") or run_id("object-storage-e2e")).strip()
    out = repo_path(getattr(args, "out", "") or DEFAULT_RUN_ROOT / current_run_id)
    put_args = argparse.Namespace(**vars(args))
    put_args.run_id = current_run_id
    put_args.out = str(out)
    put_args.content = getattr(args, "content", "") or "cento object storage e2e dummy\n"
    put_args.dry_run = not bool(getattr(args, "live", False))
    code, receipt = put_dummy(put_args)
    dummy_file = repo_path(receipt["dummy_file"])
    checks = [
        {"name": "dummy file exists", "passed": dummy_file.exists(), "evidence": receipt["dummy_file"]},
        {"name": "receipt exists", "passed": repo_path(receipt["receipt"]).exists(), "evidence": receipt["receipt"]},
        {"name": "sha256 recorded", "passed": bool(receipt.get("sha256")), "evidence": receipt["receipt"]},
    ]
    if receipt["mode"] == "dry-run":
        uploaded = repo_path(str(receipt.get("uploaded_copy") or ""))
        checks.append({"name": "dry-run uploaded copy exists", "passed": uploaded.exists(), "evidence": rel(uploaded)})
        checks.append({"name": "dry-run uploaded copy matches", "passed": uploaded.exists() and sha256_file(uploaded) == receipt.get("sha256"), "evidence": rel(uploaded)})
    else:
        checks.append({"name": "live OCI upload completed", "passed": receipt.get("status") == "uploaded", "evidence": receipt["receipt"]})

    passed = all(item["passed"] for item in checks)
    summary = {
        "schema_version": E2E_SCHEMA_VERSION,
        "run_id": current_run_id,
        "status": "passed" if passed else "failed",
        "mode": receipt["mode"],
        "out": rel(out),
        "receipt": receipt,
        "checks": checks,
        "ai_calls_used": 0,
        "estimated_ai_cost_usd": 0,
        "written_at": now_iso(),
    }
    write_json(out / "e2e-summary.json", summary)
    lines = [
        "# Cento Object Storage MVP E2E",
        "",
        f"- status: `{summary['status']}`",
        f"- mode: `{summary['mode']}`",
        f"- receipt: `{receipt['receipt']}`",
        "",
        "## Checks",
        "",
        *[f"- {'PASS' if item['passed'] else 'FAIL'} `{item['name']}`: `{item['evidence']}`" for item in checks],
    ]
    (out / "e2e-summary.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return (0 if passed and code == 0 else 1), summary


def bucket_get(args: argparse.Namespace, bucket: str, namespace: str) -> dict[str, Any]:
    command = [
        getattr(args, "oci_bin", "oci"),
        "os",
        "bucket",
        "get",
        "--bucket-name",
        bucket,
        *oci_global_args(args),
    ]
    if namespace:
        command.extend(["--namespace-name", namespace])
    return run_command(command)


def bucket_is_private_standard(bucket_data: dict[str, Any]) -> bool:
    return bucket_data.get("storage-tier") == "Standard" and bucket_data.get("public-access-type") == "NoPublicAccess"


def ensure_bucket(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    bucket = str(getattr(args, "name", "") or configured_image_bucket(getattr(args, "bucket", ""))).strip()
    namespace = configured_namespace(getattr(args, "namespace", ""))
    compartment_id = configured_compartment(getattr(args, "compartment_id", "")) or tenancy_from_config(
        getattr(args, "config_file", ""),
        getattr(args, "profile", ""),
    )
    payload: dict[str, Any] = {
        "schema_version": "cento.object_storage_bucket.v1",
        "bucket": bucket,
        "namespace": namespace,
        "region": configured_region(getattr(args, "region", "")),
        "storage_tier": "Standard",
        "public_access_type": "NoPublicAccess",
        "written_at": now_iso(),
    }
    if not bucket:
        payload.update({"status": "blocked", "error": "Missing bucket name."})
        return 2, payload

    get_result = bucket_get(args, bucket, namespace)
    if get_result["returncode"] == 0:
        data = parse_json_stdout(get_result).get("data", {})
        payload["bucket_data"] = data
        payload["status"] = "exists" if bucket_is_private_standard(data) else "blocked"
        if payload["status"] == "blocked":
            payload["error"] = "Bucket exists but is not Standard tier with NoPublicAccess."
        return (0 if payload["status"] == "exists" else 1), payload

    if not compartment_id:
        payload.update(
            {
                "status": "blocked",
                "error": "Missing compartment. Pass --compartment-id or configure tenancy in ~/.oci/config.",
                "bucket_get_stderr": get_result["stderr"],
            }
        )
        return 2, payload

    command = [
        getattr(args, "oci_bin", "oci"),
        "os",
        "bucket",
        "create",
        "--compartment-id",
        compartment_id,
        "--name",
        bucket,
        "--public-access-type",
        "NoPublicAccess",
        "--storage-tier",
        "Standard",
        *oci_global_args(args),
    ]
    if namespace:
        command.extend(["--namespace-name", namespace])
    create_result = run_command(command)
    payload["oci"] = {
        "command": create_result["command"],
        "returncode": create_result["returncode"],
    }
    if create_result["returncode"] != 0:
        payload.update({"status": "failed", "error": create_result["stderr"].strip() or "OCI bucket create failed"})
        return 1, payload

    data = parse_json_stdout(create_result).get("data", {})
    payload["bucket_data"] = data
    payload["status"] = "created" if bucket_is_private_standard(data) else "blocked"
    if payload["status"] == "blocked":
        payload["error"] = "Created bucket did not report Standard tier with NoPublicAccess."
    return (0 if payload["status"] == "created" else 1), payload


def image_migration_run_dir(args: argparse.Namespace, prefix: str = "image-migration") -> Path:
    current_run_id = str(getattr(args, "run_id", "") or run_id(prefix)).strip()
    return repo_path(getattr(args, "out", "") or DEFAULT_RUN_ROOT / current_run_id)


def render_image_summary(path: Path, payload: dict[str, Any]) -> None:
    totals = payload.get("totals", {})
    lines = [
        "# Cento OCI Image Migration",
        "",
        f"- status: `{payload.get('status', '')}`",
        f"- mode: `{payload.get('mode', '')}`",
        f"- bucket: `{payload.get('bucket', '')}`",
        f"- namespace: `{payload.get('namespace', '')}`",
        f"- region: `{payload.get('region', '')}`",
        f"- files: `{totals.get('files', 0)}`",
        f"- unique upload objects: `{totals.get('unique_upload_objects', 0)}`",
        f"- blocked: `{totals.get('blocked_files', 0)}`",
        f"- duplicate rows: `{totals.get('duplicate_rows', 0)}`",
        f"- bytes: `{totals.get('bytes', 0)}`",
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def plan_images(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    out = image_migration_run_dir(args)
    root = repo_path(getattr(args, "root", "") or DEFAULT_IMAGE_ROOT)
    bucket = configured_image_bucket(getattr(args, "bucket", ""))
    namespace = configured_namespace(getattr(args, "namespace", ""))
    region = configured_region(getattr(args, "region", ""))
    rows: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()

    for path in iter_image_files(root):
        sha256 = sha256_file(path)
        blocked = is_sensitive_image_path(path)
        duplicate = sha256 in seen_hashes
        if not blocked:
            seen_hashes.add(sha256)
        object_name = "" if blocked else object_name_for_image(path, sha256)
        rows.append(
            {
                "artifact_id": "image-" + hashlib.sha256(rel(path).encode("utf-8")).hexdigest()[:20],
                "source_path": rel(path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256,
                "extension": path.suffix.lower(),
                "content_type": image_content_type(path),
                "artifact_class": image_artifact_class(path),
                "sensitivity": image_sensitivity(path, blocked),
                "blocked": blocked,
                "block_reason": "sensitive_path" if blocked else "",
                "upload_role": "blocked" if blocked else ("duplicate" if duplicate else "primary"),
                "upload_status": "blocked_sensitive_path" if blocked else ("dedupe_reference" if duplicate else "planned"),
                "object_name": object_name,
                "object_uri": "" if blocked else object_uri(namespace, bucket, object_name),
            }
        )

    unique_upload_bytes = sum(row["size_bytes"] for row in rows if row["upload_role"] == "primary")
    payload = {
        "schema_version": IMAGE_MIGRATION_SCHEMA_VERSION,
        "run_id": out.name,
        "status": "planned",
        "mode": "mirror-only",
        "root": rel(root),
        "out": rel(out),
        "bucket": bucket,
        "namespace": namespace,
        "region": region,
        "manifest": rel(out / "manifest.json"),
        "summary": rel(out / "summary.md"),
        "written_at": now_iso(),
        "totals": {
            "files": len(rows),
            "bytes": sum(row["size_bytes"] for row in rows),
            "unique_upload_objects": sum(1 for row in rows if row["upload_role"] == "primary"),
            "unique_upload_bytes": unique_upload_bytes,
            "blocked_files": sum(1 for row in rows if row["blocked"]),
            "duplicate_rows": sum(1 for row in rows if row["upload_role"] == "duplicate"),
            "estimated_standard_storage_gib": round(unique_upload_bytes / (1024**3), 6),
            "estimated_standard_storage_usd_month": round(
                unique_upload_bytes / (1024**3) * STANDARD_OBJECT_STORAGE_RATE_PER_GIB_MONTH,
                6,
            ),
        },
        "rows": rows,
    }
    write_json(out / "manifest.json", payload)
    render_image_summary(out / "summary.md", payload)
    return 0, payload


def validate_upload_bucket(args: argparse.Namespace, bucket: str, namespace: str) -> tuple[bool, str]:
    result = bucket_get(args, bucket, namespace)
    if result["returncode"] != 0:
        return False, result["stderr"].strip() or "Unable to inspect OCI bucket."
    data = parse_json_stdout(result).get("data", {})
    if not bucket_is_private_standard(data):
        return False, "Bucket must be Standard tier with NoPublicAccess."
    return True, ""


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
        raise SystemExit(f"Expected image migration manifest with rows: {path}")
    return payload


def upload_images(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    manifest_path = repo_path(getattr(args, "manifest", ""))
    manifest = load_manifest(manifest_path)
    out = repo_path(getattr(args, "out", "") or manifest_path.parent)
    bucket = configured_image_bucket(getattr(args, "bucket", "") or str(manifest.get("bucket", "")))
    namespace = configured_namespace(getattr(args, "namespace", "") or str(manifest.get("namespace", "")))
    region = configured_region(getattr(args, "region", "") or str(manifest.get("region", "")))
    live = bool(getattr(args, "live", False))
    rows = [dict(row) for row in manifest["rows"]]
    status_by_sha: dict[str, dict[str, Any]] = {}

    receipt = {
        **{key: value for key, value in manifest.items() if key != "rows"},
        "schema_version": IMAGE_UPLOAD_SCHEMA_VERSION,
        "status": "initialized",
        "mode": "live" if live else "dry-run",
        "bucket": bucket,
        "namespace": namespace,
        "region": region,
        "source_manifest": rel(manifest_path),
        "out": rel(out),
        "upload_receipt": rel(out / "upload-receipt.json"),
        "written_at": now_iso(),
        "rows": rows,
    }

    if live:
        ok, error = validate_upload_bucket(args, bucket, namespace)
        if not ok:
            receipt.update({"status": "blocked", "error": error})
            write_json(out / "upload-receipt.json", receipt)
            render_image_summary(out / "upload-summary.md", receipt)
            return 2, receipt

    for row in rows:
        if row.get("blocked"):
            continue
        sha256 = str(row["sha256"])
        if sha256 in status_by_sha:
            previous = status_by_sha[sha256]
            row["upload_status"] = "dedupe_reference"
            row["upload_verified"] = bool(previous.get("upload_verified"))
            row["uploaded_copy"] = previous.get("uploaded_copy", "")
            continue

        source = repo_path(row["source_path"])
        if live:
            command = [
                getattr(args, "oci_bin", "oci"),
                "os",
                "object",
                "put",
                "--bucket-name",
                bucket,
                "--file",
                str(source),
                "--name",
                row["object_name"],
                "--force",
                "--content-type",
                row.get("content_type") or image_content_type(source),
                *oci_global_args(argparse.Namespace(**{**vars(args), "region": region})),
            ]
            if namespace:
                command.extend(["--namespace-name", namespace])
            result = run_command(command)
            row["oci_command"] = result["command"]
            row["oci_returncode"] = result["returncode"]
            if result["returncode"] == 0:
                row["upload_status"] = "uploaded"
                row["upload_verified"] = True
            else:
                row["upload_status"] = "failed"
                row["upload_verified"] = False
                row["error"] = result["stderr"].strip() or "OCI object put failed"
        else:
            uploaded = safe_uploaded_path(out / "uploaded", row["object_name"])
            uploaded.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, uploaded)
            row["upload_status"] = "uploaded-dry-run"
            row["uploaded_copy"] = rel(uploaded)
            row["upload_verified"] = sha256_file(uploaded) == sha256

        status_by_sha[sha256] = row

    failures = [row for row in rows if row.get("upload_status") == "failed"]
    uploaded = [row for row in rows if row.get("upload_status") in {"uploaded", "uploaded-dry-run"}]
    receipt["totals"] = {
        **dict(receipt.get("totals", {})),
        "uploaded_objects": len(uploaded),
        "failed_objects": len(failures),
    }
    receipt["status"] = "failed" if failures else ("uploaded" if live else "uploaded-dry-run")
    write_json(out / "upload-receipt.json", receipt)
    render_image_summary(out / "upload-summary.md", receipt)
    return (1 if failures else 0), receipt


def verify_images(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    manifest_path = repo_path(getattr(args, "manifest", ""))
    manifest = load_manifest(manifest_path)
    out = repo_path(getattr(args, "out", "") or manifest_path.parent)
    sample = int(getattr(args, "sample", 10))
    bucket = configured_image_bucket(getattr(args, "bucket", "") or str(manifest.get("bucket", "")))
    namespace = configured_namespace(getattr(args, "namespace", "") or str(manifest.get("namespace", "")))
    region = configured_region(getattr(args, "region", "") or str(manifest.get("region", "")))
    rows: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for row in manifest["rows"]:
        status = row.get("upload_status")
        if row.get("blocked") or status not in {"uploaded", "uploaded-dry-run", "dedupe_reference"}:
            continue
        sha256 = str(row["sha256"])
        if sha256 in seen_hashes:
            continue
        seen_hashes.add(sha256)
        rows.append(dict(row))
    if sample > 0:
        rows = rows[:sample]

    checks: list[dict[str, Any]] = []
    for row in rows:
        expected_sha = str(row["sha256"])
        if row.get("upload_status") == "uploaded-dry-run" and row.get("uploaded_copy"):
            candidate = repo_path(str(row["uploaded_copy"]))
            actual_sha = sha256_file(candidate) if candidate.exists() else ""
            checks.append(
                {
                    "source_path": row["source_path"],
                    "object_name": row["object_name"],
                    "verified": actual_sha == expected_sha,
                    "mode": "dry-run-copy",
                    "sha256": expected_sha,
                }
            )
            continue

        download = out / "verify-downloads" / expected_sha[:2] / f"{expected_sha}-{Path(row['source_path']).name}"
        download.parent.mkdir(parents=True, exist_ok=True)
        command = [
            getattr(args, "oci_bin", "oci"),
            "os",
            "object",
            "get",
            "--bucket-name",
            bucket,
            "--name",
            row["object_name"],
            "--file",
            str(download),
            *oci_global_args(argparse.Namespace(**{**vars(args), "region": region})),
        ]
        if namespace:
            command.extend(["--namespace-name", namespace])
        result = run_command(command)
        actual_sha = sha256_file(download) if result["returncode"] == 0 and download.exists() else ""
        checks.append(
            {
                "source_path": row["source_path"],
                "object_name": row["object_name"],
                "downloaded_file": rel(download),
                "verified": actual_sha == expected_sha,
                "mode": "oci-get",
                "sha256": expected_sha,
                "oci_returncode": result["returncode"],
                "error": "" if result["returncode"] == 0 else result["stderr"].strip(),
            }
        )

    passed = all(check["verified"] for check in checks)
    receipt = {
        "schema_version": IMAGE_VERIFY_SCHEMA_VERSION,
        "status": "passed" if passed else "failed",
        "source_manifest": rel(manifest_path),
        "out": rel(out),
        "bucket": bucket,
        "namespace": namespace,
        "region": region,
        "sample": sample,
        "checks": checks,
        "verify_receipt": rel(out / "verify-receipt.json"),
        "written_at": now_iso(),
    }
    write_json(out / "verify-receipt.json", receipt)
    return (0 if passed else 1), receipt


def add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--bucket", default="", help="OCI Object Storage bucket name. Defaults to CENTO_OBJECT_STORAGE_BUCKET.")
    parser.add_argument("--namespace", default="", help="OCI Object Storage namespace. Defaults to CENTO_OBJECT_STORAGE_NAMESPACE or OCI auto-discovery.")
    parser.add_argument("--compartment-id", default="", help="Compartment OCID for status/list-oriented commands.")
    parser.add_argument("--region", default="", help="OCI region for Object Storage calls, for example us-ashburn-1.")
    parser.add_argument("--profile", default="", help="OCI CLI profile.")
    parser.add_argument("--config-file", default="", help="OCI CLI config path.")
    parser.add_argument("--oci-bin", default="oci", help="OCI CLI executable.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cento Oracle Object Storage MVP.")
    sub = parser.add_subparsers(dest="command", required=True)

    status_parser = sub.add_parser("status", help="Check local OCI Object Storage configuration.")
    add_common_options(status_parser)
    status_parser.add_argument("--probe", action="store_true", help="Call `oci os ns get` to verify authentication.")
    status_parser.add_argument("--json", action="store_true")

    bucket_parser = sub.add_parser("ensure-bucket", help="Create or verify a private Standard OCI image bucket.")
    add_common_options(bucket_parser)
    bucket_parser.add_argument("--name", default=DEFAULT_IMAGE_BUCKET, help="Bucket name to create or verify.")
    bucket_parser.add_argument("--json", action="store_true")

    put_parser = sub.add_parser("put-dummy", help="Write a dummy file and upload it to OCI Object Storage.")
    add_common_options(put_parser)
    put_parser.add_argument("--run-id", default="")
    put_parser.add_argument("--out", default="")
    put_parser.add_argument("--prefix", default="")
    put_parser.add_argument("--object-name", default="")
    put_parser.add_argument("--content", default="")
    put_parser.add_argument("--dry-run", action="store_true", help="Do not call OCI; copy the dummy file into uploaded/.")
    put_parser.add_argument("--json", action="store_true")

    e2e_parser = sub.add_parser("e2e", help="Run deterministic Object Storage MVP end-to-end validation.")
    add_common_options(e2e_parser)
    e2e_parser.add_argument("--run-id", default="")
    e2e_parser.add_argument("--out", default="")
    e2e_parser.add_argument("--prefix", default="")
    e2e_parser.add_argument("--object-name", default="")
    e2e_parser.add_argument("--content", default="")
    e2e_parser.add_argument("--live", action="store_true", help="Use live OCI upload instead of dry-run fixture mode.")
    e2e_parser.add_argument("--json", action="store_true")

    plan_images_parser = sub.add_parser("plan-images", help="Write a mirror-only OCI image migration manifest.")
    add_common_options(plan_images_parser)
    plan_images_parser.add_argument("--run-id", default="")
    plan_images_parser.add_argument("--root", default=str(DEFAULT_IMAGE_ROOT))
    plan_images_parser.add_argument("--out", default="")
    plan_images_parser.add_argument("--json", action="store_true")

    upload_images_parser = sub.add_parser("upload-images", help="Upload image manifest objects to OCI or a dry-run copy.")
    add_common_options(upload_images_parser)
    upload_images_parser.add_argument("--manifest", required=True)
    upload_images_parser.add_argument("--out", default="")
    upload_images_parser.add_argument("--live", action="store_true")
    upload_images_parser.add_argument("--json", action="store_true")

    verify_images_parser = sub.add_parser("verify-images", help="Download and verify uploaded image objects.")
    add_common_options(verify_images_parser)
    verify_images_parser.add_argument("--manifest", required=True)
    verify_images_parser.add_argument("--out", default="")
    verify_images_parser.add_argument("--sample", type=int, default=10)
    verify_images_parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "status":
        code, payload = status(args)
    elif args.command == "ensure-bucket":
        code, payload = ensure_bucket(args)
    elif args.command == "put-dummy":
        code, payload = put_dummy(args)
    elif args.command == "e2e":
        code, payload = run_e2e(args)
    elif args.command == "plan-images":
        code, payload = plan_images(args)
    elif args.command == "upload-images":
        code, payload = upload_images(args)
    elif args.command == "verify-images":
        code, payload = verify_images(args)
    else:
        raise SystemExit(f"unknown command: {args.command}")

    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if args.command == "status":
            print("ok" if payload.get("ok") else "not ready")
        elif args.command == "ensure-bucket":
            print(payload.get("status", ""))
        elif args.command in {"e2e", "plan-images"}:
            print(payload.get("out", ""))
        elif args.command == "upload-images":
            print(payload.get("upload_receipt", ""))
        elif args.command == "verify-images":
            print(payload.get("verify_receipt", ""))
        else:
            print(payload.get("receipt", ""))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
