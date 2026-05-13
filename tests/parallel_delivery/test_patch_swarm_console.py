from __future__ import annotations

import json
import subprocess
import sys
import threading
from dataclasses import replace
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import agent_work_app  # noqa: E402
import parallel_delivery_patch_swarm_console as console  # noqa: E402
import parallel_delivery_validation_e2e as e2e  # noqa: E402


FIXED_TS = "2026-05-13T00:00:00Z"


def run_fixture(tmp_path: Path, *, run_id: str = "console-fixture", target: int = 5, max_agents: int = 5) -> Path:
    result = e2e.run_fixture_e2e(
        e2e.E2ERequest(
            run_id=run_id,
            run_root=tmp_path,
            candidate_target=target,
            max_parallel_agents=max_agents,
            fixture=True,
            dry_run=True,
            fixed_timestamp=FIXED_TS,
        )
    )
    assert result.ok, result.errors
    return result.run_dir


def test_console_data_aggregation_from_fixture_artifacts(tmp_path: Path) -> None:
    run_dir = run_fixture(tmp_path, run_id="aggregate", target=5, max_agents=3)
    data = console.collect_patch_swarm_console_data(run_dir)

    assert data.schema_version == console.SCHEMA_VERSION
    assert data.run_id == "aggregate"
    assert data.candidate_count == 5
    assert data.task_graph.total_tasks == 5
    assert data.workers.max_parallel_agents == 3
    assert data.workers.max_observed_parallel_workers <= 3
    assert data.bundles.accepted == 5
    assert data.bundles.rejected == 1
    assert data.bundles.safe_apply == 5
    assert data.integration.conflict_report_path
    assert data.validation.report_path == "validation-report.md"
    assert data.release_candidate.created is True
    labels = {link.label for link in data.evidence_links}
    assert {"Validation Summary", "Validation Report", "Integration Plan", "Conflict Report", "Release Candidate"} <= labels


def test_static_html_rendering_and_link_validation(tmp_path: Path) -> None:
    run_dir = run_fixture(tmp_path, run_id="render", target=5, max_agents=5)
    data = console.collect_patch_swarm_console_data(run_dir)
    console.write_console_data(data, run_dir)
    html_path = console.render_patch_swarm_html(data, run_dir)
    link_check = console.validate_console_links(run_dir, html_path)

    html = html_path.read_text(encoding="utf-8")
    for text in [
        "Patch Swarm",
        "Current Run",
        "Next Action",
        "Task Graph",
        "Workers",
        "Bundles",
        "Integration",
        "Validation",
        "Evidence",
        "Release Candidate",
    ]:
        assert text in html
    assert link_check["passed"] is True
    assert (run_dir / "console-data.json").exists()
    assert (run_dir / "link-check.json").exists()


def test_next_action_rules_are_deterministic(tmp_path: Path) -> None:
    run_dir = run_fixture(tmp_path, run_id="next-action", target=5, max_agents=5)
    data = console.collect_patch_swarm_console_data(run_dir)
    ready = replace(
        data,
        bundles=console.BundleBucketSummary(0, 5, 0, 5, 0, 0, 0),
        integration=console.IntegrationStatus("passed", 1, 0, 5, 0, 0, 0, "integration/rejected-patches.json"),
        validation=console.ValidationStatus("passed", 8, 0, tuple(), "validation-report.md"),
        release_candidate=console.ReleaseCandidateStatus(True, "ready_for_operator_review", "release-candidate/release-candidate.json", "release-candidate/demo-evidence.md"),
    )

    assert console.compute_next_action(replace(ready, validation=console.ValidationStatus("missing", 0, 1, ("missing",), None))) == "Generate or repair fixture validation summary"
    assert console.compute_next_action(replace(ready, validation=console.ValidationStatus("failed", 7, 1, ("gate",), "validation-report.md"))) == "Inspect validation-report.md and failing stage"
    assert console.compute_next_action(replace(ready, bundles=console.BundleBucketSummary(0, 4, 1, 4, 0, 0, 1))) == "Review rejected bundles before release candidate"
    assert console.compute_next_action(replace(ready, integration=console.IntegrationStatus("passed", 1, 1, 5, 0, 1, 0, "integration/rejected-patches.json"))) == "Resolve conflicts in conflict-report.md"
    assert console.compute_next_action(replace(ready, integration=console.IntegrationStatus("failed", 1, 0, 5, 0, 0, 0, "integration/rejected-patches.json"))) == "Run rebase or dry-run repair for affected bundles"
    assert console.compute_next_action(replace(ready, release_candidate=console.ReleaseCandidateStatus(False, "missing", None, None))) == "Create release candidate evidence"
    assert console.compute_next_action(ready) == "Ready for operator demo/release review"


def test_status_cli_writes_console_exports(tmp_path: Path) -> None:
    run_dir = run_fixture(tmp_path, run_id="cli-status", target=5, max_agents=5)
    cmd = [
        sys.executable,
        str(SCRIPTS / "parallel_delivery.py"),
        "patch-swarm",
        "status",
        "--run-dir",
        str(run_dir),
        "--write-html",
        "--json",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["run_id"] == "cli-status"
    assert payload["candidate_count"] == 5
    assert payload["artifacts"]["start_here"].endswith("start-here.html")
    assert (run_dir / "start-here.html").exists()
    assert (run_dir / "console-data.json").exists()


def test_agent_work_app_console_route_smoke() -> None:
    run_root = ROOT / "workspace" / "runs" / "parallel-delivery" / "console-fixture"
    run_dir = e2e.run_fixture_e2e(
        e2e.E2ERequest(
            run_id="pytest-app-route-smoke",
            run_root=run_root,
            candidate_target=5,
            max_parallel_agents=5,
            fixture=True,
            dry_run=True,
            fixed_timestamp=FIXED_TS,
        )
    ).run_dir
    db_path = ROOT / "workspace" / "runs" / "parallel-delivery" / "console-fixture" / "pytest-app-route-smoke.sqlite3"
    server = ThreadingHTTPServer(("127.0.0.1", 0), agent_work_app.make_handler(db_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/patch-swarm/console?run_dir={quote(console.rel(run_dir))}"
        with urlopen(url, timeout=5) as response:
            body = response.read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "Patch Swarm Current Run" in body
    assert "Current Run" in body
    assert (run_dir / "start-here.html").exists()
