#!/usr/bin/env python3
"""Focused tests for Dev Pipeline Studio real delivery routing."""
from __future__ import annotations

import json
import sys
import base64
import argparse
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import agent_work_app as app
import cento_build
import dev_pipeline_hard_proreq as hard
import proreq_light


def hard_proreq_run_payload(prompt: str = "Build the run pipeline contract.") -> dict:
    return {
        "schema_version": app.PIPELINE_RUN_SCHEMA_VERSION,
        "project_id": app.HARD_PROREQ_PROJECT_ID,
        "template_id": app.HARD_PROREQ_TEMPLATE_ID,
        "inputs": [
            {"id": "operator-thoughts", "kind": "questionnaire", "source": "user", "answer": prompt},
            {"id": "generated-cento-context", "kind": "path", "source": "auto"},
            {"id": "ui-screenshot-request", "kind": "image", "source": "auto"},
            {"id": "pro-backend-schema", "kind": "details", "source": "auto"},
            {"id": "backend-work-handoff", "kind": "evidence", "source": "auto"},
        ],
    }


def proreq_light_run_payload(prompt: str = "Build the run pipeline contract without live Pro API.") -> dict:
    payload = hard_proreq_run_payload(prompt)
    payload["project_id"] = app.PROREQ_LIGHT_PROJECT_ID
    payload["template_id"] = app.PROREQ_LIGHT_TEMPLATE_ID
    return payload


def parallel_run_payload(prompt: str = "Create a parallel pipeline UI config.") -> dict:
    return {
        "schema_version": app.PIPELINE_RUN_SCHEMA_VERSION,
        "project_id": app.PARALLEL_PIPELINE_PROJECT_ID,
        "template_id": app.PARALLEL_PIPELINE_TEMPLATE_ID,
        "inputs": [
            {"id": "parallel-objective", "kind": "questionnaire", "source": "user", "answer": prompt},
            {
                "id": "parallel-workstreams",
                "kind": "path",
                "source": "user",
                "paths": [
                    "workspace/runs/parallel-pipeline/ui-config.json",
                    "workspace/runs/parallel-pipeline/execution-ui.json",
                ],
            },
            {"id": "parallel-read-context", "kind": "path", "source": "auto"},
            {"id": "parallel-ui-config", "kind": "details", "source": "user", "answer": "max_parallel: 3\nruntime: api-openai\nintegrator: sequential"},
            {"id": "parallel-integrator-gate", "kind": "evidence", "source": "auto"},
            {"id": "parallel-validation-evidence", "kind": "evidence", "source": "auto"},
        ],
    }


def multipipeline_run_payload(prompt: str = "Run a four-pass ProReq chain from the operator objective.") -> dict:
    return {
        "schema_version": app.PIPELINE_RUN_SCHEMA_VERSION,
        "project_id": app.MULTIPIPELINE_PROJECT_ID,
        "template_id": app.MULTIPIPELINE_TEMPLATE_ID,
        "inputs": [
            {"id": "multipipeline-objective", "kind": "questionnaire", "source": "user", "answer": prompt},
            {
                "id": "multipipeline-schedule-config",
                "kind": "details",
                "source": "user",
                "answer": "passes: 4\nchild_pipeline: hard-proreq-task\nexecution_mode: request-artifacts\nui_screenshot: request-artifact\npro_call: request-artifact\nhandoff_policy: previous-guidance-required",
            },
            {"id": "multipipeline-context", "kind": "path", "source": "auto"},
            {"id": "ui-screenshot-request", "kind": "image", "source": "auto"},
            {"id": "multipipeline-pro-request", "kind": "details", "source": "auto"},
            {"id": "multipipeline-evidence", "kind": "evidence", "source": "auto"},
        ],
    }


def write_hard_proreq_manifest(root: Path) -> dict:
    manifest = {
        "id": "test-dev-pipeline",
        "projects": [app.dev_pipeline_hard_proreq_project_defaults()],
        "templates": [app.dev_pipeline_hard_proreq_blueprint_defaults()],
        "defaults": {
            "project_id": app.HARD_PROREQ_PROJECT_ID,
            "template_id": app.HARD_PROREQ_TEMPLATE_ID,
        },
        "artifacts": {"events": "events.ndjson"},
    }
    app.write_json_path(root / "pipeline_manifest.json", manifest)
    return manifest


def write_proreq_light_manifest(root: Path) -> dict:
    manifest = {
        "id": "test-proreq-light",
        "projects": [app.dev_pipeline_proreq_light_project_defaults()],
        "templates": [app.dev_pipeline_proreq_light_blueprint_defaults()],
        "defaults": {
            "project_id": app.PROREQ_LIGHT_PROJECT_ID,
            "template_id": app.PROREQ_LIGHT_TEMPLATE_ID,
        },
        "artifacts": {"events": "events.ndjson"},
    }
    app.write_json_path(root / "pipeline_manifest.json", manifest)
    return manifest


def write_parallel_manifest(root: Path) -> dict:
    manifest = {
        "id": "test-parallel-pipeline",
        "projects": [app.dev_pipeline_parallel_project_defaults()],
        "templates": [app.dev_pipeline_parallel_blueprint_defaults()],
        "defaults": {
            "project_id": app.PARALLEL_PIPELINE_PROJECT_ID,
            "template_id": app.PARALLEL_PIPELINE_TEMPLATE_ID,
        },
        "artifacts": {"events": "events.ndjson"},
    }
    app.write_json_path(root / "pipeline_manifest.json", manifest)
    return manifest


def write_multipipeline_manifest(root: Path) -> dict:
    manifest = {
        "id": "test-multipipeline-proreq",
        "projects": [app.dev_pipeline_multipipeline_project_defaults()],
        "templates": [app.dev_pipeline_multipipeline_blueprint_defaults()],
        "defaults": {
            "project_id": app.MULTIPIPELINE_PROJECT_ID,
            "template_id": app.MULTIPIPELINE_TEMPLATE_ID,
        },
        "artifacts": {"events": "events.ndjson"},
    }
    app.write_json_path(root / "pipeline_manifest.json", manifest)
    return manifest


def test_delivery_target_paths_come_from_prompt_not_repo_context() -> None:
    project = {
        "id": "generic-easy-medium-task",
        "read_paths": ["AGENTS.md", "README.md", "scripts/**"],
    }
    template = {
        "id": "generic-task",
        "description": "Generic task",
        "required_inputs": [
            {
                "id": "repo-context-manifest",
                "title": "Repo context manifest",
                "answer_values": ["AGENTS.md", "README.md", "scripts/**/*.py"],
            }
        ],
    }
    trigger = {
        "prompt": "Please create a file named test123.txt with hello world.",
        "issue_subject": "create test123.txt",
    }

    assert app.dev_pipeline_delivery_target_paths(project, template, trigger) == ["test123.txt"]


def test_delivery_target_paths_drop_basename_when_full_path_exists() -> None:
    project = {"id": "generic-easy-medium-task", "read_paths": []}
    template = {"id": "generic-task", "description": "Generic task", "required_inputs": []}
    trigger = {
        "prompt": "Create workspace/runs/dev-pipeline-studio/docs-pages/latest/evidence/pipeline_route_probe.txt.",
        "issue_subject": "write pipeline_route_probe.txt",
    }

    assert app.dev_pipeline_delivery_target_paths(project, template, trigger) == [
        "workspace/runs/dev-pipeline-studio/docs-pages/latest/evidence/pipeline_route_probe.txt"
    ]


def test_delivery_seed_blocks_without_api_runtime_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CENTO_OPENAI_WORKER_MODEL", raising=False)
    project = {
        "id": "generic-easy-medium-task",
        "read_paths": ["AGENTS.md", "README.md"],
    }
    template = {
        "id": "generic-task",
        "description": "Generic task",
        "factory_steps": [{"id": "delivery", "title": "delivery"}],
    }
    trigger = {
        "prompt": "Create demo_delivery_smoke.txt with a short status line.",
        "issue_subject": "create demo_delivery_smoke.txt",
    }

    run = app.dev_pipeline_seed_execution_e2e(tmp_path, {}, project, template, trigger)

    assert run["status"] == "blocked"
    assert "demo_delivery_smoke.txt" in run["target_paths"]
    assert any("OPENAI_API_KEY" in item for item in run["readiness_errors"])
    assert any("model is not configured" in item for item in run["readiness_errors"])
    workset_path = tmp_path / run["workset_manifest"]
    if not workset_path.exists():
        workset_path = app.ROOT_DIR / run["workset_manifest"]
    workset = json.loads(workset_path.read_text(encoding="utf-8"))
    assert workset["tasks"][0]["write_paths"] == ["demo_delivery_smoke.txt"]
    assert workset["tasks"][0]["output_schema"] == "patch_proposal.v1"


def test_hard_proreq_seed_uses_default_pro_route(tmp_path: Path) -> None:
    project = app.dev_pipeline_hard_proreq_project_defaults()
    template = app.dev_pipeline_hard_proreq_blueprint_defaults()
    manifest = {"projects": [project], "templates": [template]}
    trigger = {
        "prompt": "Build a hard project plan from my rough notes and keep frontend screenshot work separate.",
        "issue_subject": "hard proreq route smoke",
        "triggered_by": "issue-1000160",
        "issue_id": "1000160",
    }

    run = app.dev_pipeline_seed_execution_e2e(tmp_path, manifest, project, template, trigger)

    assert run["source"] == "cento-hard-proreq-pro"
    assert run["status"] == "running"
    assert "10-story split" in run["runtime"]
    assert run["triggered_by"] == "issue-1000160"
    assert any(step["id"] == "write-ui-screenshot-request" for step in run["steps"])
    assert any("pro_backend_request.json" in artifact["path"] for artifact in run["artifacts"])
    assert any(fact["value"] == "strict Responses JSON Schema + codex --output-schema" for fact in run["facts"])
    assert any(fact["label"] == "Model ceiling" and fact["value"].endswith("gpt-4.1-mini") for fact in run["facts"])

    execution_path = tmp_path / "execution" / "execution_run.json"
    assert execution_path.exists()
    persisted = json.loads(execution_path.read_text(encoding="utf-8"))
    assert persisted["pipeline"] == "hard-proreq-task-hard-proreq-project"


def test_proreq_light_seed_uses_codex_exec_route(tmp_path: Path) -> None:
    project = app.dev_pipeline_proreq_light_project_defaults()
    template = app.dev_pipeline_proreq_light_blueprint_defaults()
    manifest = {"projects": [project], "templates": [template]}
    trigger = {
        "prompt": "Build a hard project plan from rough notes, but do not use live Pro API.",
        "issue_subject": "proreq light route smoke",
        "triggered_by": "issue-1000200",
        "issue_id": "1000200",
    }

    run = app.dev_pipeline_seed_execution_e2e(tmp_path, manifest, project, template, trigger)

    assert run["source"] == "cento-proreq-light-codex"
    assert run["status"] == "running"
    assert run["delivery_mode"] == "closed-loop"
    assert run["apply_mode"] == "closed-loop-clean-apply"
    assert "Codex Exec ProReq-light" in run["runtime"]
    assert any(step["id"] == "dispatch-codex-pro-backend-plan" for step in run["steps"])
    assert not any(step["id"] == "dispatch-pro-backend-plan" for step in run["steps"])
    assert any("proreq_light_codex_prompt.md" in artifact["path"] for artifact in run["artifacts"])
    assert any(fact["label"] == "Budget" and "Codex Exec" in fact["value"] for fact in run["facts"])


def test_pipeline_run_api_starts_hard_proreq_without_taskstream_issue(monkeypatch, tmp_path: Path) -> None:
    write_hard_proreq_manifest(tmp_path)
    monkeypatch.setattr(app, "DEV_PIPELINE_STUDIO_ROOT", tmp_path)
    db_path = tmp_path / "agent-work.sqlite3"
    with app.connect(db_path) as conn:
        app.init_db(conn)
        before = conn.execute("select count(*) from issues").fetchone()[0]

    response = app.dev_pipeline_start_pipeline_run(hard_proreq_run_payload(), spawn=False)

    assert response["status"] == "running"
    assert response["pipeline_route"]["url"] == "/dev-pipeline-studio#pipeline-flow"
    assert response["execution_run"]["issue_id"] == ""
    assert response["execution_run"]["inputs"][0]["id"] == "operator-thoughts"
    state = app.dev_pipeline_studio_state(app.HARD_PROREQ_PROJECT_ID, app.HARD_PROREQ_TEMPLATE_ID, response["execution_run"]["run_id"])
    execution_flow = state["pipeline"]["execution_flow"]
    selected_history = next(item for item in execution_flow["history"] if item["run_id"] == response["execution_run"]["run_id"])
    assert selected_history["artifact_count"] >= len(response["execution_run"]["artifacts"])
    assert any(item["name"] == "pro_backend_request.json" for item in execution_flow["artifacts"])
    with app.connect(db_path) as conn:
        app.init_db(conn)
        after = conn.execute("select count(*) from issues").fetchone()[0]
    assert after == before


def test_pipeline_run_api_starts_proreq_light_without_taskstream_issue(monkeypatch, tmp_path: Path) -> None:
    write_proreq_light_manifest(tmp_path)
    monkeypatch.setattr(app, "DEV_PIPELINE_STUDIO_ROOT", tmp_path)
    db_path = tmp_path / "agent-work.sqlite3"
    with app.connect(db_path) as conn:
        app.init_db(conn)
        before = conn.execute("select count(*) from issues").fetchone()[0]

    response = app.dev_pipeline_start_pipeline_run(proreq_light_run_payload(), spawn=False)

    assert response["status"] == "running"
    assert response["pipeline_route"]["template_id"] == app.PROREQ_LIGHT_TEMPLATE_ID
    assert response["execution_run"]["source"] == "cento-proreq-light-codex"
    assert response["execution_run"]["delivery_mode"] == "closed-loop"
    state = app.dev_pipeline_studio_state(app.PROREQ_LIGHT_PROJECT_ID, app.PROREQ_LIGHT_TEMPLATE_ID, response["execution_run"]["run_id"])
    execution_flow = state["pipeline"]["execution_flow"]
    assert execution_flow["stages"][3]["title"] == "4. ProReq Light Planning"
    assert any(item["name"] == "proreq_light_codex_prompt.md" for item in execution_flow["artifacts"])
    with app.connect(db_path) as conn:
        app.init_db(conn)
        after = conn.execute("select count(*) from issues").fetchone()[0]
    assert after == before


def test_pipeline_run_accepts_proreq_light_plan_only_escape_hatch(monkeypatch, tmp_path: Path) -> None:
    write_proreq_light_manifest(tmp_path)
    monkeypatch.setattr(app, "DEV_PIPELINE_STUDIO_ROOT", tmp_path)
    payload = proreq_light_run_payload()
    payload["delivery_mode"] = "plan-only"

    response = app.dev_pipeline_start_pipeline_run(payload, spawn=False)

    assert response["execution_run"]["delivery_mode"] == "plan-only"
    assert response["execution_run"]["apply_mode"] == "backend-plan-first"


def test_pipeline_run_accepts_optional_auto_screenshot_reference(monkeypatch, tmp_path: Path) -> None:
    write_hard_proreq_manifest(tmp_path)
    monkeypatch.setattr(app, "DEV_PIPELINE_STUDIO_ROOT", tmp_path)
    payload = hard_proreq_run_payload()
    payload["inputs"][2] = {
        "id": "ui-screenshot-request",
        "kind": "image",
        "source": "auto",
        "image_refs": ["workspace/runs/reference-ui.png"],
        "image_notes": "optional screenshot context",
    }

    response = app.dev_pipeline_start_pipeline_run(payload, spawn=False)

    screenshot_input = next(item for item in response["execution_run"]["inputs"] if item["id"] == "ui-screenshot-request")
    assert screenshot_input["status"] == "provided"
    assert screenshot_input["image_refs"][0] == "workspace/runs/reference-ui.png"


def test_pipeline_run_api_writes_parallel_workset_and_execution_summary(monkeypatch, tmp_path: Path) -> None:
    write_parallel_manifest(tmp_path)
    monkeypatch.setattr(app, "DEV_PIPELINE_STUDIO_ROOT", tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("CENTO_OPENAI_WORKER_MODEL", "gpt-test-worker")

    response = app.dev_pipeline_start_pipeline_run(parallel_run_payload(), spawn=False)

    assert response["status"] == "running"
    run = response["execution_run"]
    assert run["execution_model"] == "parallel"
    assert run["workset_task_count"] == 2
    assert run["workset_max_parallel"] == 3
    workset = json.loads((app.ROOT_DIR / run["workset_manifest"]).read_text(encoding="utf-8"))
    assert workset["max_parallel"] == 3
    assert [task["write_paths"] for task in workset["tasks"]] == [
        ["workspace/runs/parallel-pipeline/ui-config.json"],
        ["workspace/runs/parallel-pipeline/execution-ui.json"],
    ]

    state = app.dev_pipeline_studio_state(app.PARALLEL_PIPELINE_PROJECT_ID, app.PARALLEL_PIPELINE_TEMPLATE_ID, run["run_id"])
    parallel = state["pipeline"]["execution_flow"]["parallel"]
    assert parallel["enabled"] is True
    assert parallel["task_count"] == 2
    assert parallel["max_parallel"] == 3
    assert parallel["integration"] == "sequential"
    assert [task["status"] for task in parallel["tasks"]] == ["queued", "queued"]


def test_pipeline_run_api_starts_multipipeline_proreq_chain(monkeypatch, tmp_path: Path) -> None:
    write_multipipeline_manifest(tmp_path)
    monkeypatch.setattr(app, "DEV_PIPELINE_STUDIO_ROOT", tmp_path)

    response = app.dev_pipeline_start_pipeline_run(multipipeline_run_payload(), spawn=False)

    run = response["execution_run"]
    assert response["status"] == "running"
    assert response["pipeline_route"]["template_id"] == app.MULTIPIPELINE_TEMPLATE_ID
    assert run["source"] == "cento-multipipeline-proreq-chain"
    assert run["apply_mode"] == "request-artifacts-only"
    assert len(run["steps"]) == 9
    assert any(step["id"] == "run-proreq-pass-4" for step in run["steps"])
    assert any("multipipeline_schedule.json" in artifact["path"] for artifact in run["artifacts"])
    assert any(fact["label"] == "Model policy" and "request artifacts" in fact["value"] for fact in run["facts"])


def test_multipipeline_proreq_chain_finishes_e2e(monkeypatch, tmp_path: Path) -> None:
    write_multipipeline_manifest(tmp_path)
    monkeypatch.setattr(app, "DEV_PIPELINE_STUDIO_ROOT", tmp_path)
    monkeypatch.setattr(app, "DEV_PIPELINE_EXECUTION_MIN_STEP_SECONDS", 0)
    monkeypatch.setenv("CENTO_DEV_PIPELINE_STUDIO_ROOT", str(tmp_path))
    response = app.dev_pipeline_start_pipeline_run(multipipeline_run_payload(), spawn=False)
    run_id = response["execution_run"]["run_id"]

    app.dev_pipeline_finish_execution_e2e(tmp_path, app.MULTIPIPELINE_PROJECT_ID, app.MULTIPIPELINE_TEMPLATE_ID, run_id)

    run_path = tmp_path / "execution" / "runs" / f"{run_id}.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    assert run["status"] == "completed"
    assert all(step["status"] in {"completed", "muted"} for step in run["steps"])
    current = tmp_path / "execution" / "multipipeline" / run_id
    schedule = json.loads((current / "multipipeline_schedule.json").read_text(encoding="utf-8"))
    evidence = json.loads((current / "multipipeline_evidence.json").read_text(encoding="utf-8"))
    pass_4_request = json.loads((current / "pass_04_proreq_request.json").read_text(encoding="utf-8"))
    assert len(schedule["passes"]) == 4
    assert evidence["status"] == "completed"
    assert evidence["pass_count"] == 4
    assert pass_4_request["child_pipeline_payload"]["template_id"] == app.HARD_PROREQ_TEMPLATE_ID
    assert (current / "ui_screenshot_request.json").exists()
    assert (current / "chatgpt_pro_request.json").exists()
    assert (current / "chain_roadmap.md").exists()


def test_pipeline_run_rejects_missing_required_user_input(monkeypatch, tmp_path: Path) -> None:
    write_hard_proreq_manifest(tmp_path)
    monkeypatch.setattr(app, "DEV_PIPELINE_STUDIO_ROOT", tmp_path)
    payload = hard_proreq_run_payload("")
    payload["inputs"][0] = {"id": "operator-thoughts", "kind": "questionnaire", "source": "user"}

    try:
        app.dev_pipeline_start_pipeline_run(payload, spawn=False)
    except app.AgentWorkAppError as exc:
        assert "required user input is missing: operator-thoughts" in str(exc)
    else:
        raise AssertionError("missing operator input was accepted")


def test_pipeline_run_rejects_extra_input_id(monkeypatch, tmp_path: Path) -> None:
    write_hard_proreq_manifest(tmp_path)
    monkeypatch.setattr(app, "DEV_PIPELINE_STUDIO_ROOT", tmp_path)
    payload = hard_proreq_run_payload()
    payload["inputs"].append({"id": "extra-input", "kind": "details", "source": "auto"})

    try:
        app.dev_pipeline_start_pipeline_run(payload, spawn=False)
    except app.AgentWorkAppError as exc:
        assert "extra: extra-input" in str(exc)
    else:
        raise AssertionError("extra input id was accepted")


def test_pipeline_run_rejects_wrong_kind_specific_payload(monkeypatch, tmp_path: Path) -> None:
    write_hard_proreq_manifest(tmp_path)
    monkeypatch.setattr(app, "DEV_PIPELINE_STUDIO_ROOT", tmp_path)
    payload = hard_proreq_run_payload()
    payload["inputs"][0] = {
        "id": "operator-thoughts",
        "kind": "questionnaire",
        "source": "user",
        "paths": ["unexpected.txt"],
    }

    try:
        app.dev_pipeline_start_pipeline_run(payload, spawn=False)
    except app.AgentWorkAppError as exc:
        assert "invalid field(s) for questionnaire/user: paths" in str(exc)
    else:
        raise AssertionError("wrong kind-specific payload was accepted")


def test_pipeline_run_compatibility_prefill_points_to_run_pipeline() -> None:
    index_html = (app.ROOT_DIR / "templates" / "agent-work-app" / "index.html").read_text(encoding="utf-8")
    app_js = (app.ROOT_DIR / "templates" / "agent-work-app" / "app.js").read_text(encoding="utf-8")

    assert "Run Pipeline" in index_html
    assert "Run pipeline" in index_html
    assert "/issues/new" in app_js
    assert "pendingRunPipelinePrompt" in app_js
    assert "New issue" not in index_html
    assert "Create issue" not in index_html


def test_hard_proreq_image_edit_response_writes_png(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(hard, "ROOT", tmp_path)
    monkeypatch.setattr(hard, "PIPELINE_ROOT", tmp_path / "pipeline")
    run_root = hard.PIPELINE_ROOT / "execution"
    app.write_json_path(run_root / "execution_run.json", {"run_id": "run-image"})
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"png-reference")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class Response:
        status_code = 200
        text = ""

        def json(self) -> dict:
            return {
                "created": 123,
                "usage": {"input_tokens": 1},
                "data": [{"b64_json": base64.b64encode(b"png-output").decode("ascii")}],
            }

    class Requests:
        calls = 0

        @staticmethod
        def post(*_args, **_kwargs):
            Requests.calls += 1
            return Response()

    monkeypatch.setitem(sys.modules, "requests", Requests)

    result = hard.dispatch_image_generation(
        {
            "model": "gpt-image-2",
            "prompt": "Generate a UI screenshot",
            "parameters": {"size": "1024x1024", "quality": "low", "output_format": "png", "input_fidelity": "high", "n": 1},
        },
        reference,
    )

    assert Requests.calls == 1
    assert result["status"] == "completed"
    assert (hard.PIPELINE_ROOT / "execution" / "hard-proreq" / "run-image" / "generated_integrator_screenshot.png").read_bytes() == b"png-output"


def test_hard_proreq_image2_preflight_falls_back_to_image1(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(hard, "ROOT", tmp_path)
    monkeypatch.setattr(hard, "PIPELINE_ROOT", tmp_path / "pipeline")
    app.write_json_path(hard.PIPELINE_ROOT / "execution" / "execution_run.json", {"run_id": "run-image-fallback"})
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"png-reference")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class PreflightResponse:
        status_code = 403
        text = "organization verification required"

        def json(self) -> dict:
            return {"error": {"message": "Organization verification required"}}

    class EditResponse:
        status_code = 200
        text = ""

        def json(self) -> dict:
            return {
                "id": "img_resp_1",
                "created": 123,
                "usage": {"input_text_tokens": 100, "input_image_tokens": 200, "output_image_tokens": 300},
                "data": [{"b64_json": base64.b64encode(b"png-output").decode("ascii")}],
            }

    class Requests:
        posted_models: list[str] = []

        @staticmethod
        def get(*_args, **_kwargs):
            return PreflightResponse()

        @staticmethod
        def post(*_args, **kwargs):
            Requests.posted_models.append(kwargs["data"]["model"])
            return EditResponse()

    monkeypatch.setitem(sys.modules, "requests", Requests)

    result = hard.dispatch_image_generation(
        {
            "model": "gpt-image-2",
            "prompt": "Generate a UI screenshot",
            "parameters": {"size": "1024x1024", "quality": "low", "output_format": "png", "input_fidelity": "high", "n": 1},
        },
        reference,
    )
    ledger = (hard.PIPELINE_ROOT / "execution" / "hard-proreq" / "run-image-fallback" / "spend-ledger.jsonl").read_text(encoding="utf-8")

    assert Requests.posted_models == ["gpt-image-1"]
    assert result["status"] == "completed"
    assert result["requested_model"] == "gpt-image-2"
    assert result["model"] == "gpt-image-1"
    assert result["preflight"]["fallback_used"] is True
    assert "img_resp_1" in ledger


def test_hard_proreq_image_lane_not_automated_skips_network(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(hard, "ROOT", tmp_path)
    monkeypatch.setattr(hard, "PIPELINE_ROOT", tmp_path / "pipeline")
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"png-reference")
    app.write_json_path(
        hard.PIPELINE_ROOT / "execution" / "execution_run.json",
        {
            "run_id": "run-manual-image",
            "prompt": "manual image lane",
            "inputs": [{"id": "ui-screenshot-request", "kind": "image", "source": "user"}],
        },
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("CENTO_HARD_PROREQ_REFERENCE_SCREENSHOT", str(reference))

    class Requests:
        @staticmethod
        def post(*_args, **_kwargs):
            raise AssertionError("network should not be called")

    monkeypatch.setitem(sys.modules, "requests", Requests)

    assert hard.command_screenshot(argparse.Namespace()) == 0
    response = hard.read_json(hard.PIPELINE_ROOT / "execution" / "hard-proreq" / "run-manual-image" / "image_generation_response.json")
    assert response["status"] == "skipped"
    assert response["skip_code"] == "image-lane-not-automated"


def test_hard_proreq_missing_image_key_skips_without_failing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(hard, "ROOT", tmp_path)
    monkeypatch.setattr(hard, "PIPELINE_ROOT", tmp_path / "pipeline")
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"png-reference")
    app.write_json_path(
        hard.PIPELINE_ROOT / "execution" / "execution_run.json",
        {
            "run_id": "run-missing-key",
            "prompt": "auto image lane",
            "inputs": [{"id": "ui-screenshot-request", "kind": "image", "source": "auto", "automation": "openai-image"}],
        },
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CENTO_HARD_PROREQ_REFERENCE_SCREENSHOT", str(reference))

    assert hard.command_screenshot(argparse.Namespace()) == 0
    response = hard.read_json(hard.PIPELINE_ROOT / "execution" / "hard-proreq" / "run-missing-key" / "image_generation_response.json")
    assert response["status"] == "skipped"
    assert response["skip_code"] == "missing-openai-api-key"


def test_hard_proreq_pro_timeout_writes_receipt_and_ledger(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(hard, "ROOT", tmp_path)
    monkeypatch.setattr(hard, "PIPELINE_ROOT", tmp_path / "pipeline")
    app.write_json_path(
        hard.PIPELINE_ROOT / "execution" / "execution_run.json",
        {"run_id": "run-pro-timeout", "prompt": "plan the backend split"},
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("CENTO_HARD_PROREQ_DISPATCH_PRO", "1")
    monkeypatch.setenv("CENTO_HARD_PROREQ_PRO_TIMEOUT", "1")

    def timeout_urlopen(*_args, **_kwargs):
        raise TimeoutError("test timeout")

    monkeypatch.setattr(hard.urllib.request, "urlopen", timeout_urlopen)

    assert hard.command_pro_request(argparse.Namespace()) == 0
    assert hard.command_pro_plan(argparse.Namespace()) == 0

    current = hard.PIPELINE_ROOT / "execution" / "hard-proreq" / "run-pro-timeout"
    timeout_receipt = hard.read_json(current / "pro_backend_timeout.json")
    response = hard.read_json(current / "pro_backend_response.json")
    ledger = (current / "spend-ledger.jsonl").read_text(encoding="utf-8")

    assert timeout_receipt["status"] == "timeout"
    assert timeout_receipt["timeout_seconds"] == 1
    assert response["status"] == "timeout"
    assert "unknown-timeout" in ledger
    assert "pro_backend_timeout.json" in ledger


def test_hard_proreq_pro_budget_gate_blocks_dispatch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(hard, "ROOT", tmp_path)
    monkeypatch.setattr(hard, "PIPELINE_ROOT", tmp_path / "pipeline")
    app.write_json_path(
        hard.PIPELINE_ROOT / "execution" / "execution_run.json",
        {"run_id": "run-pro-budget-block", "prompt": "plan the backend split"},
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("CENTO_HARD_PROREQ_DISPATCH_PRO", "1")
    monkeypatch.setenv("CENTO_REQUIRE_DASHBOARD_TOTAL_BUDGET", "1")
    monkeypatch.setenv("CENTO_OPENAI_DASHBOARD_TOTAL_SPEND_USD", "45.82")
    monkeypatch.setenv("CENTO_OPENAI_HARD_CAP_USD", "20")

    def unexpected_urlopen(*_args, **_kwargs):
        raise AssertionError("budget gate should block network dispatch")

    monkeypatch.setattr(hard.urllib.request, "urlopen", unexpected_urlopen)

    assert hard.command_pro_request(argparse.Namespace()) == 0
    assert hard.command_pro_plan(argparse.Namespace()) == 0

    current = hard.PIPELINE_ROOT / "execution" / "hard-proreq" / "run-pro-budget-block"
    budget_gate = hard.read_json(current / "pro_backend_budget_gate.json")
    response = hard.read_json(current / "pro_backend_response.json")
    ledger = (current / "spend-ledger.jsonl").read_text(encoding="utf-8")

    assert budget_gate["status"] == "blocked"
    assert response["status"] == "skipped"
    assert response["skip_code"] == "dashboard-budget-gate"
    assert "budget-gated" in ledger


def test_proreq_light_codex_plan_replaces_live_pro_request(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(hard, "ROOT", tmp_path)
    monkeypatch.setattr(hard, "PIPELINE_ROOT", tmp_path / "pipeline")
    app.write_json_path(
        hard.PIPELINE_ROOT / "execution" / "execution_run.json",
        {"run_id": "run-proreq-light", "prompt": "plan the backend split without live Pro API"},
    )
    monkeypatch.setattr(hard.shutil, "which", lambda name: "/usr/bin/codex" if name == "codex" else None)
    assert hard.command_context(argparse.Namespace()) == 0
    assert hard.command_screenshot(argparse.Namespace()) == 0
    assert hard.command_pro_request(argparse.Namespace()) == 0

    calls: list[dict] = []

    def fake_run(command, **kwargs):
        calls.append({"command": command, "input": kwargs.get("input")})

        class Result:
            returncode = 0
            stdout = json.dumps(
                {
                    "schema_version": "cento.hard_proreq_backend_plan.v1",
                    "summary": "Codex Exec simulated Pro planning.",
                    "backend_workstreams": [
                        {
                            "id": "codex-light-story",
                            "title": "Codex Light Story",
                            "intent": "ProReq-light story from Codex Exec.",
                            "owned_paths": ["docs/dev-pipeline-run-contracts.md"],
                            "read_paths": ["docs/**"],
                            "depends_on": [],
                            "validation_commands": ["python3 -m py_compile scripts/dev_pipeline_hard_proreq.py"],
                            "handoff_artifacts": ["stories/codex-light-story.json"],
                        }
                    ],
                    "integration_plan": ["Integrate deterministically."],
                    "validation_plan": ["Run focused tests."],
                    "parallelization_notes": ["Keep write paths exclusive."],
                    "codex_exec_prompts": [],
                    "risks": [],
                }
            )
            stderr = ""

        return Result()

    monkeypatch.setattr(hard.subprocess, "run", fake_run)

    assert hard.command_codex_pro_plan(argparse.Namespace()) == 0

    current = hard.PIPELINE_ROOT / "execution" / "hard-proreq" / "run-proreq-light"
    prompt = (current / "proreq_light_codex_prompt.md").read_text(encoding="utf-8")
    output_schema = hard.read_json(current / "proreq_light_output_schema.json")
    command_receipt = hard.read_json(current / "proreq_light_codex_command.json")
    response = hard.read_json(current / "proreq_light_codex_response.json")
    plan = hard.read_json(current / "pro_backend_plan.json")

    assert calls
    assert calls[0]["command"][:2] == ["/usr/bin/codex", "exec"]
    assert "You're chatGPT Pro model" in prompt
    assert "Do not write code" in prompt
    assert output_schema["type"] == "object"
    assert "schema" not in output_schema
    assert command_receipt["output_schema"].endswith("proreq_light_output_schema.json")
    assert response["backend"] == "codex-exec-proreq-light"
    assert response["status"] == "completed"
    assert plan["schema_version"] == "cento.hard_proreq_backend_plan.v1"
    assert any(stream["id"] == "codex-light-story" for stream in plan["backend_workstreams"])


def test_proreq_light_screenshot_never_dispatches_image(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(hard, "ROOT", tmp_path)
    monkeypatch.setattr(hard, "PIPELINE_ROOT", tmp_path / "pipeline")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    app.write_json_path(
        hard.PIPELINE_ROOT / "execution" / "execution_run.json",
        {"run_id": "run-proreq-light-screenshot", "prompt": "keep image lane request-only"},
    )

    def unexpected_dispatch(*_args, **_kwargs):
        raise AssertionError("ProReq-light must not dispatch image API work")

    monkeypatch.setattr(hard, "dispatch_image_generation", unexpected_dispatch)

    assert hard.command_light_screenshot(argparse.Namespace()) == 0

    current = hard.PIPELINE_ROOT / "execution" / "hard-proreq" / "run-proreq-light-screenshot"
    image_response = hard.read_json(current / "image_generation_response.json")
    screenshot_request = hard.read_json(current / "ui_screenshot_request.json")

    assert image_response["status"] == "skipped"
    assert image_response["skip_code"] == "image-lane-muted-by-proreq-light"
    assert screenshot_request["image_generation_status"]["skip_code"] == "image-lane-muted-by-proreq-light"


def test_hard_proreq_image_budget_gate_blocks_dispatch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(hard, "ROOT", tmp_path)
    monkeypatch.setattr(hard, "PIPELINE_ROOT", tmp_path / "pipeline")
    app.write_json_path(hard.PIPELINE_ROOT / "execution" / "execution_run.json", {"run_id": "run-image-budget-block"})
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"png-reference")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("CENTO_REQUIRE_DASHBOARD_TOTAL_BUDGET", "1")
    monkeypatch.setenv("CENTO_OPENAI_DASHBOARD_TOTAL_SPEND_USD", "48.21")
    monkeypatch.setenv("CENTO_OPENAI_HARD_CAP_USD", "20")

    class Requests:
        @staticmethod
        def post(*_args, **_kwargs):
            raise AssertionError("budget gate should block image dispatch")

    monkeypatch.setitem(sys.modules, "requests", Requests)

    result = hard.dispatch_image_generation(
        {
            "model": "gpt-image-1",
            "prompt": "Generate a UI screenshot",
            "parameters": {"size": "1024x1024", "quality": "low", "output_format": "png", "input_fidelity": "high", "n": 1},
        },
        reference,
    )
    current = hard.PIPELINE_ROOT / "execution" / "hard-proreq" / "run-image-budget-block"
    ledger = (current / "spend-ledger.jsonl").read_text(encoding="utf-8")

    assert result["status"] == "skipped"
    assert result["skip_code"] == "dashboard-budget-gate"
    assert (current / "image_generation_budget_gate.json").exists()
    assert "budget-gated" in ledger


def test_hard_proreq_backend_work_writes_ten_story_manifests(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(hard, "ROOT", tmp_path)
    monkeypatch.setattr(hard, "PIPELINE_ROOT", tmp_path / "pipeline")
    app.write_json_path(
        hard.PIPELINE_ROOT / "execution" / "execution_run.json",
        {"run_id": "run-ten-stories", "prompt": "UI to ten stories to parallel patches"},
    )
    assert hard.command_pro_plan(argparse.Namespace()) == 0
    assert hard.command_backend_work(argparse.Namespace()) == 0

    current = hard.PIPELINE_ROOT / "execution" / "hard-proreq" / "run-ten-stories"
    story_index = hard.read_json(current / "story_index.json")
    backend = hard.read_json(current / "backend_work_manifest.json")
    workset = hard.read_json(current / "parallel_patch_workset.json")

    assert story_index["story_count"] == 10
    assert len(story_index["stories"]) == 10
    assert backend["story_count"] == 10
    assert workset["execution_model"] == "parallel"
    assert workset["integration_model_policy"]["profile"] == "local-codex-only"
    assert workset["integration_model_policy"]["model_ceiling"] == "none"
    assert workset["policies"]["allow_creates"] is True
    assert workset["tasks"][0]["runtime"] == "local-command"
    assert workset["tasks"][0]["runtime_profile"] == "codex-fast"
    assert workset["tasks"][0]["worker_id"].startswith("codex-story-worker-")
    assert "api-openai" not in json.dumps(workset)
    assert (current / "stories" / "run-input-contract.json").exists()


def test_proreq_light_deliver_runs_local_codex_workset(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(hard, "ROOT", tmp_path)
    monkeypatch.setattr(hard, "PIPELINE_ROOT", tmp_path / "pipeline")
    app.write_json_path(hard.PIPELINE_ROOT / "execution" / "execution_run.json", {"run_id": "run-light-deliver"})
    current = hard.PIPELINE_ROOT / "execution" / "hard-proreq" / "run-light-deliver"
    current.mkdir(parents=True)
    app.write_json_path(
        current / "story_index.json",
        {"schema_version": "cento.hard_proreq.story_index.v1", "stories": []},
    )
    app.write_json_path(
        current / "parallel_patch_workset.json",
        {
            "schema_version": "cento.workset.v1",
            "id": "light-deliver",
            "mode": "standard",
            "max_parallel": 1,
            "policies": {"allow_creates": True},
            "tasks": [
                {
                    "id": "story-a",
                    "worker_id": "codex-story-worker-1",
                    "task": "Write local output",
                    "write_paths": ["new-local-output.txt"],
                    "read_paths": [],
                }
            ],
        },
    )
    calls: list[list[str]] = []

    class Result:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(command, **_kwargs):
        calls.append([str(part) for part in command])
        if "execute" in command:
            workset_dir = tmp_path / ".cento" / "worksets" / "light-deliver-run"
            workset_dir.mkdir(parents=True)
            receipt_rel = ".cento/worksets/light-deliver-run/workset_receipt.json"
            app.write_json_path(
                tmp_path / receipt_rel,
                {
                    "schema_version": "cento.workset_receipt.v1",
                    "status": "completed",
                    "runtime": "local-command",
                    "total_tasks": 1,
                    "max_parallel": 1,
                    "total_cost_usd": 0.0,
                    "changed_paths": ["new-local-output.txt"],
                    "events": ".cento/worksets/light-deliver-run/events.ndjson",
                    "tasks": {"story-a": {"status": "applied"}},
                },
            )
            return Result(
                0,
                json.dumps(
                    {
                        "status": "completed",
                        "workset_dir": ".cento/worksets/light-deliver-run",
                        "workset_receipt": receipt_rel,
                        "changed_paths": ["new-local-output.txt"],
                    }
                ),
            )
        return Result(0, json.dumps({"status": "passed", "errors": [], "warnings": []}))

    monkeypatch.setattr(proreq_light.subprocess, "run", fake_run)
    args = argparse.Namespace(
        fresh=False,
        plan_only=False,
        no_apply=False,
        runtime_profile="codex-fast",
        max_parallel=3,
        validation="smoke",
        worker_timeout=180,
        delivery_timeout=1800,
        validation_timeout=600,
        full_check=False,
        json=False,
    )

    assert proreq_light.command_deliver(args) == 0

    delivery = hard.read_json(current / "closed_loop_delivery.json")
    validation = hard.read_json(current / "closed_loop_validation.json")
    execute_call = next(call for call in calls if "execute" in call)
    assert delivery["status"] == "completed"
    assert delivery["runtime"] == "local-command"
    assert delivery["runtime_profile"] == "codex-fast"
    assert delivery["changed_paths"] == ["new-local-output.txt"]
    assert validation["status"] == "passed"
    assert "--runtime" in execute_call
    assert "local-command" in execute_call
    assert "--allow-creates" in execute_call
    assert "api-openai" not in execute_call
    assert (current / "closed_loop_evidence.md").exists()


def test_proreq_light_deliver_writes_incident_on_preflight_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(hard, "ROOT", tmp_path)
    monkeypatch.setattr(hard, "PIPELINE_ROOT", tmp_path / "pipeline")
    app.write_json_path(hard.PIPELINE_ROOT / "execution" / "execution_run.json", {"run_id": "run-light-blocked"})
    current = hard.PIPELINE_ROOT / "execution" / "hard-proreq" / "run-light-blocked"
    current.mkdir(parents=True)
    app.write_json_path(current / "parallel_patch_workset.json", {"schema_version": "cento.workset.v1", "id": "blocked", "tasks": []})

    class Result:
        returncode = 1
        stdout = json.dumps({"status": "failed", "errors": ["missing path policy"]})
        stderr = "workset preflight failed"

    monkeypatch.setattr(proreq_light.subprocess, "run", lambda *_args, **_kwargs: Result())
    args = argparse.Namespace(
        fresh=False,
        plan_only=False,
        no_apply=False,
        runtime_profile="codex-fast",
        max_parallel=3,
        validation="smoke",
        worker_timeout=180,
        delivery_timeout=1800,
        validation_timeout=600,
        full_check=False,
        json=False,
    )

    assert proreq_light.command_deliver(args) == 1

    delivery = hard.read_json(current / "closed_loop_delivery.json")
    incident = hard.read_json(current / "closed_loop_incident.json")
    validation = hard.read_json(current / "closed_loop_validation.json")
    assert delivery["status"] == "blocked"
    assert delivery["stage"] == "preflight"
    assert incident["incident_type"] == "workset_preflight_failed"
    assert validation["status"] == "skipped"
    assert (current / "closed_loop_check_stderr.txt").read_text(encoding="utf-8") == "workset preflight failed"


def test_command_runtime_profile_feeds_prompt_through_stdin_file(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    worker_dir = tmp_path / "worker"
    build_dir.mkdir()
    worker_dir.mkdir()
    manifest = {
        "id": "stdin-runtime",
        "mode": "standard",
        "task": {"title": "Prompt stdin smoke", "description": "Verify stdin_file reaches command runtime."},
        "scope": {"write_paths": ["prompt-copy.txt"], "read_paths": []},
        "workers": [{"id": "worker-1", "write_paths": ["prompt-copy.txt"], "artifact_dir": str(worker_dir)}],
        "validation": {"commands": []},
    }
    manifest_path = tmp_path / "manifest.json"
    app.write_json_path(manifest_path, manifest)
    profile = {
        "type": "command",
        "argv": [
            sys.executable,
            "-c",
            "import sys; from pathlib import Path; Path('prompt-copy.txt').write_text(sys.stdin.read(), encoding='utf-8')",
        ],
        "cwd": "{worktree}",
        "stdin_file": "{prompt}",
        "env_allowlist": ["PATH", "HOME"],
        "timeout_seconds": 30,
    }

    assert cento_build.validate_runtime_profile("stdin-smoke", profile)["status"] == "passed"
    result = cento_build.run_worker_runtime(
        manifest,
        manifest_path,
        "worker-1",
        "command",
        tmp_path,
        build_dir,
        worker_dir,
        30,
        profile_name="stdin-smoke",
        profile_config=profile,
    )

    assert result["status"] == "passed"
    assert result["stdin_file"].endswith("builder.prompt.md")
    assert "Prompt stdin smoke" in (tmp_path / "prompt-copy.txt").read_text(encoding="utf-8")
