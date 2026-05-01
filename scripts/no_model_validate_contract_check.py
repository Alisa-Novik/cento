#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import validator_tier0


ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = ROOT / "scripts" / "fixtures" / "no-model-validation"
DEFAULT_RUN_DIR = ROOT / "workspace" / "runs" / "agent-work" / "no-model-validation-contract"
FIXTURE_FILES = [
    FIXTURE_DIR / "pass.json",
    FIXTURE_DIR / "fail.json",
    FIXTURE_DIR / "escalate.json",
]
SCHEMA = "cento.no-model-validation.fixture.v1"
RESULT_SCHEMA = "cento.validation-result.v1"
PACKET_SCHEMA = "cento.validation-packet.v1"
STATUS_TO_DECISION = {
    "pass": "approve",
    "fail": "needs_fix",
    "escalate": "blocked",
}


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_keys(item: dict[str, Any], keys: list[str], label: str) -> None:
    missing = [key for key in keys if key not in item]
    assert_true(not missing, f"{label} missing keys: {missing}")


def validate_fixture_shape(fixture: dict[str, Any], path: Path) -> None:
    require_keys(fixture, ["schema", "name", "status", "manifest", "expected"], f"fixture {path}")
    assert_true(str(fixture["schema"]) == SCHEMA, f"unexpected schema in {path}: {fixture['schema']!r}")
    assert_true(str(fixture["status"]) in STATUS_TO_DECISION, f"unexpected status in {path}: {fixture['status']!r}")
    assert_true(isinstance(fixture["manifest"], dict), f"manifest must be an object in {path}")
    assert_true(isinstance(fixture["expected"], dict), f"expected must be an object in {path}")
    assert_true(isinstance(fixture.get("metadata"), dict), f"metadata must be an object in {path}")
    manifest = fixture["manifest"]
    expected = fixture["expected"]
    metadata = fixture["metadata"]
    require_keys(manifest, ["task", "claim", "risk", "decision_requested", "checks"], f"manifest {path}")
    assert_true(isinstance(manifest["checks"], list) and manifest["checks"], f"checks must be a non-empty list in {path}")
    assert_true(all(isinstance(item, dict) for item in manifest["checks"]), f"all checks must be objects in {path}")
    assert_true(isinstance(expected.get("decision"), str) and expected["decision"], f"expected decision missing in {path}")
    assert_true(
        expected["decision"] == STATUS_TO_DECISION[str(fixture["status"])],
        f"expected decision mismatch in {path}: {expected['decision']!r}",
    )
    assert_true(
        str(manifest["decision_requested"]) == expected["decision"],
        f"decision_requested mismatch in {path}: {manifest['decision_requested']!r}",
    )
    reason_contains = str(expected.get("reason_contains") or "").strip()
    assert_true(bool(reason_contains), f"expected.reason_contains missing in {path}")
    if str(fixture["status"]) == "pass":
        evidence_path_value = str(metadata.get("evidence_path") or "").strip()
        assert_true(bool(evidence_path_value), f"pass fixture should record evidence_path in {path}")
        evidence_path = Path(evidence_path_value)
        if not evidence_path.is_absolute():
            evidence_path = ROOT / evidence_path
        assert_true(evidence_path.exists(), f"pass evidence missing in {path}: {evidence_path}")
    elif str(fixture["status"]) == "fail":
        missing_path_value = str(metadata.get("missing_artifact_path") or "").strip()
        assert_true(bool(missing_path_value), f"fail fixture should record missing_artifact_path in {path}")
        missing_path = Path(missing_path_value)
        if not missing_path.is_absolute():
            missing_path = ROOT / missing_path
        assert_true(not missing_path.exists(), f"fail artifact should be absent in {path}: {missing_path}")
    else:
        assert_true(bool(metadata.get("high_risk")), f"escalate fixture should be marked high_risk in {path}")
        assert_true(bool(metadata.get("ux_ambiguity")), f"escalate fixture should be marked ux_ambiguity in {path}")


def validate_check_shape(check: dict[str, Any], fixture_path: Path) -> None:
    require_keys(check, ["name", "type", "status", "reason", "evidence", "observed"], f"check in {fixture_path}")
    assert_true(isinstance(check.get("duration_ms"), (int, float)), f"duration_ms must be numeric in {fixture_path}")
    assert_true(isinstance(check.get("observed"), dict), f"observed must be an object in {fixture_path}")
    assert_true(str(check.get("status")) in {"passed", "failed", "missing", "blocked"}, f"unexpected check status in {fixture_path}: {check.get('status')!r}")


def run_fixture(fixture_path: Path, run_dir: Path) -> dict[str, Any]:
    fixture = read_json(fixture_path)
    validate_fixture_shape(fixture, fixture_path)

    fixture_name = str(fixture["name"]).strip()
    status = str(fixture["status"])
    expected = fixture["expected"]
    fixture_run_dir = run_dir / status
    validator_run_dir = fixture_run_dir / "validator"
    fixture_run_dir.mkdir(parents=True, exist_ok=True)
    validator_run_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = fixture_run_dir / "validation-manifest.json"
    write_json(manifest_path, fixture["manifest"])

    result = validator_tier0.run_manifest(manifest_path, validator_run_dir)
    result_path = validator_run_dir / "validation-result.json"
    packet_path = validator_run_dir / "validation-packet.json"
    stats_path = validator_run_dir / "stats.json"
    summary_path = validator_run_dir / "validation-summary.md"

    assert_true(result_path.exists(), f"missing validation result for {fixture_name}")
    assert_true(packet_path.exists(), f"missing validation packet for {fixture_name}")
    assert_true(stats_path.exists(), f"missing stats for {fixture_name}")
    assert_true(summary_path.exists(), f"missing summary for {fixture_name}")

    stored_result = read_json(result_path)
    stored_packet = read_json(packet_path)
    stored_stats = read_json(stats_path)
    assert_true(stored_result["schema"] == RESULT_SCHEMA, f"unexpected result schema for {fixture_name}")
    assert_true(stored_packet["schema"] == PACKET_SCHEMA, f"unexpected packet schema for {fixture_name}")
    assert_true(stored_result["decision"] == expected["decision"], f"decision mismatch for {fixture_name}: {stored_result['decision']!r}")
    assert_true(expected["reason_contains"].lower() in stored_result["reason"].lower(), f"reason mismatch for {fixture_name}: {stored_result['reason']!r}")
    assert_true(result["decision"] == stored_result["decision"], f"in-memory and stored decisions differ for {fixture_name}")
    assert_true(result["schema"] == stored_result["schema"], f"in-memory and stored schemas differ for {fixture_name}")
    assert_true(stored_result["validator_tier"] == "tier0", f"validator tier mismatch for {fixture_name}")
    assert_true(stored_result["ai_calls_used"] == 0, f"ai_calls_used should be zero for {fixture_name}")
    assert_true(stored_result["estimated_ai_cost"] == 0, f"estimated_ai_cost should be zero for {fixture_name}")
    assert_true(isinstance(stored_result["checks"], list) and stored_result["checks"], f"checks missing for {fixture_name}")
    for check in stored_result["checks"]:
        validate_check_shape(check, fixture_path)
    assert_true(stored_stats["checks_executed"] == len(fixture["manifest"]["checks"]), f"stats count mismatch for {fixture_name}")
    for output_path_value in stored_result["outputs"].values():
        output_path = Path(str(output_path_value))
        if not output_path.is_absolute():
            output_path = ROOT / output_path
        assert_true(output_path.exists(), f"missing output path for {fixture_name}: {output_path}")
    if status == "pass":
        assert_true(stored_result["missing_evidence"] == [], f"pass fixture should not miss evidence: {fixture_name}")
    elif status == "fail":
        assert_true(stored_result["decision"] == "needs_fix", f"fail fixture should need fixes: {fixture_name}")
    else:
        assert_true(stored_result["decision"] == "blocked", f"escalate fixture should be blocked: {fixture_name}")

    return {
        "fixture": fixture_name,
        "status": status,
        "expected_decision": expected["decision"],
        "actual_decision": stored_result["decision"],
        "reason": stored_result["reason"],
        "run_dir": str(fixture_run_dir.relative_to(ROOT)),
        "validator_run_dir": str(validator_run_dir.relative_to(ROOT)),
        "manifest": str(manifest_path.relative_to(ROOT)),
        "result": str(result_path.relative_to(ROOT)),
        "packet": str(packet_path.relative_to(ROOT)),
        "stats": str(stats_path.relative_to(ROOT)),
        "summary": str(summary_path.relative_to(ROOT)),
    }


def render_report(run_dir: Path, results: list[dict[str, Any]]) -> Path:
    lines = [
        "# No-model Validation Fixtures",
        "",
        "Command:",
        f"- `python3 scripts/no_model_validate_contract_check.py --run-dir {run_dir.relative_to(ROOT)}`",
        "",
        "## Results",
        "",
        "| Fixture | Status | Expected | Actual | Reason | Run Dir |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in results:
        lines.append(
            f"| {item['fixture']} | {item['status']} | {item['expected_decision']} | {item['actual_decision']} | "
            f"{item['reason']} | `{item['run_dir']}` |"
        )
    lines.extend(
        [
            "",
            "## Evidence",
            "",
        ]
    )
    for item in results:
        lines.extend(
            [
                f"### {item['fixture']}",
                "",
                f"- Manifest: `{item['manifest']}`",
                f"- Packet: `{item['packet']}`",
                f"- Result: `{item['result']}`",
                f"- Stats: `{item['stats']}`",
                f"- Summary: `{item['summary']}`",
                "",
            ]
        )
    report_path = run_dir / "fixtures-evidence.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    run_dir = DEFAULT_RUN_DIR
    if len(sys.argv) > 1:
        import argparse

        parser = argparse.ArgumentParser(description="Run no-model validation fixture contract checks.")
        parser.add_argument("--run-dir", default=str(DEFAULT_RUN_DIR), help="Directory for contract outputs and evidence.")
        args = parser.parse_args()
        run_dir = Path(args.run_dir).expanduser()
        if not run_dir.is_absolute():
            run_dir = ROOT / run_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    results = [run_fixture(path, run_dir) for path in FIXTURE_FILES]
    report_path = render_report(run_dir, results)
    summary_path = run_dir / "fixtures-contract.json"
    write_json(
        summary_path,
        {
            "schema": "cento.no-model-validation.contract.v1",
            "fixture_count": len(results),
            "results": results,
            "report": str(report_path.relative_to(ROOT)),
        },
    )
    print(f"report: {report_path.relative_to(ROOT)}")
    print(f"summary: {summary_path.relative_to(ROOT)}")
    print("no-model-validation-contract-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
