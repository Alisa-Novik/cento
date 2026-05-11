#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "object_storage.py"


def run_object_storage(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_put_dummy_dry_run_writes_dummy_receipt_and_uploaded_copy(tmp_path: Path) -> None:
    out = tmp_path / "dry-run"
    result = run_object_storage("put-dummy", "--dry-run", "--out", str(out), "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "uploaded-dry-run"
    assert Path(payload["dummy_file"]).read_text(encoding="utf-8") == "cento object storage dummy\n"
    assert Path(payload["uploaded_copy"]).exists()
    assert payload["verified"] is True
    assert (out / "receipt.json").exists()
    assert (out / "summary.md").exists()


def test_put_dummy_live_uses_oci_cli_with_bucket_namespace_and_object_name(tmp_path: Path) -> None:
    fake_oci = tmp_path / "oci"
    args_log = tmp_path / "oci-args.json"
    fake_oci.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"open({str(args_log)!r}, 'w').write(json.dumps(sys.argv[1:]))\n"
        "print(json.dumps({'etag': 'fake-etag'}))\n",
        encoding="utf-8",
    )
    fake_oci.chmod(0o755)
    out = tmp_path / "live"

    result = run_object_storage(
        "put-dummy",
        "--bucket",
        "cento-test-bucket",
        "--namespace",
        "centons",
        "--region",
        "us-ashburn-1",
        "--object-name",
        "e2e/dummy.txt",
        "--oci-bin",
        str(fake_oci),
        "--out",
        str(out),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "uploaded"
    argv = json.loads(args_log.read_text(encoding="utf-8"))
    assert argv[:3] == ["os", "object", "put"]
    assert argv[argv.index("--bucket-name") + 1] == "cento-test-bucket"
    assert argv[argv.index("--namespace-name") + 1] == "centons"
    assert argv[argv.index("--region") + 1] == "us-ashburn-1"
    assert argv[argv.index("--name") + 1] == "e2e/dummy.txt"


def test_e2e_dry_run_passes_and_records_no_ai_cost(tmp_path: Path) -> None:
    out = tmp_path / "e2e"
    result = run_object_storage("e2e", "--out", str(out), "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["mode"] == "dry-run"
    assert payload["ai_calls_used"] == 0
    assert all(item["passed"] for item in payload["checks"])
    assert (out / "e2e-summary.json").exists()
    assert (out / "e2e-summary.md").exists()


def test_plan_images_discovers_dedupes_and_blocks_sensitive_paths(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    (root / "issue-1" / "screenshots").mkdir(parents=True)
    (root / "issue-1" / "screenshots" / "a.png").write_bytes(b"same-image")
    (root / "issue-1" / "screenshots" / "copy.png").write_bytes(b"same-image")
    (root / "issue-1" / "screenshots" / "raw.xwd").write_bytes(b"raw-xwd")
    (root / "issue-1" / "screenshots" / "secret-token.png").write_bytes(b"blocked")
    (root / "issue-1" / "node_modules").mkdir()
    (root / "issue-1" / "node_modules" / "skip.png").write_bytes(b"skip")
    out = tmp_path / "migration"

    result = run_object_storage(
        "plan-images",
        "--root",
        str(root),
        "--out",
        str(out),
        "--bucket",
        "cento-images-standard",
        "--namespace",
        "centons",
        "--region",
        "us-ashburn-1",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["totals"]["files"] == 4
    assert payload["totals"]["unique_upload_objects"] == 2
    assert payload["totals"]["duplicate_rows"] == 1
    assert payload["totals"]["blocked_files"] == 1
    statuses = {Path(row["source_path"]).name: row["upload_status"] for row in payload["rows"]}
    assert statuses["secret-token.png"] == "blocked_sensitive_path"
    assert statuses["copy.png"] == "dedupe_reference"
    assert not any("node_modules" in row["source_path"] for row in payload["rows"])
    assert (out / "manifest.json").exists()
    assert (out / "summary.md").exists()


def test_upload_and_verify_images_dry_run(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    (root / "issue-1" / "screenshots").mkdir(parents=True)
    (root / "issue-1" / "screenshots" / "a.png").write_bytes(b"image-a")
    (root / "issue-1" / "screenshots" / "raw.xwd").write_bytes(b"raw-xwd")
    out = tmp_path / "migration"
    plan = run_object_storage("plan-images", "--root", str(root), "--out", str(out), "--json")
    assert plan.returncode == 0, plan.stderr

    upload = run_object_storage("upload-images", "--manifest", str(out / "manifest.json"), "--json")
    assert upload.returncode == 0, upload.stderr
    upload_payload = json.loads(upload.stdout)
    assert upload_payload["status"] == "uploaded-dry-run"
    assert upload_payload["totals"]["uploaded_objects"] == 2
    assert all(row.get("upload_verified", True) for row in upload_payload["rows"] if not row["blocked"])

    verify = run_object_storage("verify-images", "--manifest", str(out / "upload-receipt.json"), "--sample", "0", "--json")
    assert verify.returncode == 0, verify.stderr
    verify_payload = json.loads(verify.stdout)
    assert verify_payload["status"] == "passed"
    assert len(verify_payload["checks"]) == 2


def test_ensure_bucket_and_live_image_upload_use_private_standard_bucket(tmp_path: Path) -> None:
    fake_oci = tmp_path / "oci"
    args_log = tmp_path / "oci-args.jsonl"
    fake_oci.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        f"log = pathlib.Path({str(args_log)!r})\n"
        "args = sys.argv[1:]\n"
        "with log.open('a', encoding='utf-8') as handle:\n"
        "    handle.write(json.dumps(args) + '\\n')\n"
        "if args[:3] == ['os', 'bucket', 'get']:\n"
        "    print(json.dumps({'data': {'name': 'cento-images-standard', 'storage-tier': 'Standard', 'public-access-type': 'NoPublicAccess'}}))\n"
        "elif args[:3] == ['os', 'bucket', 'create']:\n"
        "    print(json.dumps({'data': {'name': 'cento-images-standard', 'storage-tier': 'Standard', 'public-access-type': 'NoPublicAccess'}}))\n"
        "elif args[:3] == ['os', 'object', 'put']:\n"
        "    print(json.dumps({'etag': 'fake-etag'}))\n"
        "else:\n"
        "    print(json.dumps({'data': 'ok'}))\n",
        encoding="utf-8",
    )
    fake_oci.chmod(0o755)
    root = tmp_path / "runs"
    (root / "issue-1" / "screenshots").mkdir(parents=True)
    (root / "issue-1" / "screenshots" / "a.png").write_bytes(b"image-a")
    out = tmp_path / "migration"

    ensure = run_object_storage(
        "ensure-bucket",
        "--name",
        "cento-images-standard",
        "--namespace",
        "centons",
        "--region",
        "us-ashburn-1",
        "--oci-bin",
        str(fake_oci),
        "--json",
    )
    assert ensure.returncode == 0, ensure.stderr
    assert json.loads(ensure.stdout)["status"] == "exists"
    plan = run_object_storage("plan-images", "--root", str(root), "--out", str(out), "--json")
    assert plan.returncode == 0, plan.stderr

    upload = run_object_storage(
        "upload-images",
        "--manifest",
        str(out / "manifest.json"),
        "--bucket",
        "cento-images-standard",
        "--namespace",
        "centons",
        "--region",
        "us-ashburn-1",
        "--oci-bin",
        str(fake_oci),
        "--live",
        "--json",
    )

    assert upload.returncode == 0, upload.stderr
    payload = json.loads(upload.stdout)
    assert payload["status"] == "uploaded"
    calls = [json.loads(line) for line in args_log.read_text(encoding="utf-8").splitlines()]
    put = next(call for call in calls if call[:3] == ["os", "object", "put"])
    assert put[put.index("--bucket-name") + 1] == "cento-images-standard"
    assert put[put.index("--namespace-name") + 1] == "centons"
    assert put[put.index("--region") + 1] == "us-ashburn-1"
    assert put[put.index("--content-type") + 1] == "image/png"
