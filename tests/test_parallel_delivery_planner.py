#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import parallel_delivery_planner as planner  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
FIXED_TS = "2026-01-01T00:00:00Z"


def run_fixture(tmp_path: Path, candidate_target: int, max_parallel_agents: int = 5) -> tuple[dict, Path]:
    run_dir = tmp_path / f"planner-{candidate_target}"
    payload, code = planner.run_planner_command(
        candidate_target=candidate_target,
        max_parallel_agents=max_parallel_agents,
        mode="fixture",
        run_dir=run_dir,
        run_id=f"planner-fixture-{candidate_target}",
        timestamp=FIXED_TS,
    )
    assert code == 0, payload
    return payload, run_dir


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_fixture_planner_creates_exact_candidate_counts(tmp_path: Path) -> None:
    for count, parallel in [(5, 2), (20, 5), (100, 5)]:
        payload, run_dir = run_fixture(tmp_path, count, parallel)
        split_plan = read_json(run_dir / "split-plan.json")
        graph = read_json(run_dir / "task-graph.json")

        assert payload["candidate_count"] == count
        assert split_plan["candidate_count"] == count
        assert len(split_plan["tasks"]) == count
        assert len(graph["nodes"]) == count
        assert len(graph["topological_order"]) == count


def test_candidate_target_bounds_are_rejected(tmp_path: Path) -> None:
    for target in [0, 101]:
        payload, code = planner.run_planner_command(
            candidate_target=target,
            max_parallel_agents=1,
            mode="fixture",
            run_dir=tmp_path / f"invalid-{target}",
            run_id=f"invalid-{target}",
        )
        assert code != 0
        assert "candidate_target must be between 1 and 100" in payload["errors"][0]


def test_max_parallel_agents_cannot_exceed_candidate_target(tmp_path: Path) -> None:
    payload, code = planner.run_planner_command(
        candidate_target=5,
        max_parallel_agents=6,
        mode="fixture",
        run_dir=tmp_path / "invalid-parallel",
        run_id="invalid-parallel",
    )

    assert code != 0
    assert "max_parallel_agents must be between 1 and candidate_target" in payload["errors"][0]


def test_no_model_does_not_blindly_fill_to_100_for_small_request(tmp_path: Path) -> None:
    request = tmp_path / "small-request.md"
    request.write_text("# Small request\n\nAdd a help text clarification for one existing CLI command.\n", encoding="utf-8")

    payload, code = planner.run_planner_command(
        candidate_target=100,
        max_parallel_agents=5,
        mode="no-model",
        request_file=request,
        run_dir=tmp_path / "no-model-small",
        run_id="no-model-small",
        timestamp=FIXED_TS,
    )
    split_plan = read_json(tmp_path / "no-model-small" / "split-plan.json")

    assert code == 0, payload
    assert split_plan["candidate_target"] == 100
    assert 1 <= split_plan["candidate_count"] < 100


def test_task_ids_are_deterministic_unique_and_paths_do_not_overlap(tmp_path: Path) -> None:
    _, run_dir = run_fixture(tmp_path, 100)
    split_plan = read_json(run_dir / "split-plan.json")
    tasks = split_plan["tasks"]
    ids = [task["task_id"] for task in tasks]
    owned = [(task["task_id"], path.rstrip("/")) for task in tasks for path in task["owned_paths"]]

    assert ids[0] == "task-0001"
    assert ids[-1] == "task-0100"
    assert len(ids) == len(set(ids))
    assert planner.validate_non_overlapping_owned_paths(tasks) == []
    for index, (task_a, path_a) in enumerate(owned):
        for task_b, path_b in owned[index + 1 :]:
            assert path_a != path_b
            assert not path_a.startswith(path_b + "/"), (task_a, path_a, task_b, path_b)
            assert not path_b.startswith(path_a + "/"), (task_a, path_a, task_b, path_b)


def test_task_graph_contains_every_task_and_parallel_groups_are_bounded(tmp_path: Path) -> None:
    _, run_dir = run_fixture(tmp_path, 20)
    split_plan = read_json(run_dir / "split-plan.json")
    graph = read_json(run_dir / "task-graph.json")
    task_ids = {task["task_id"] for task in split_plan["tasks"]}

    assert {node["task_id"] for node in graph["nodes"]} == task_ids
    assert set(graph["topological_order"]) == task_ids
    assert planner.validate_task_graph(graph, split_plan) == []
    for group in graph["parallel_groups"]:
        assert len(group["task_ids"]) <= graph["max_parallel_agents"]


def test_non_human_tasks_have_contracts_and_validation_commands(tmp_path: Path) -> None:
    _, run_dir = run_fixture(tmp_path, 20)
    split_plan = read_json(run_dir / "split-plan.json")

    for task in split_plan["tasks"]:
        if not task["human_handoff"]:
            assert task["acceptance_contract"], task["task_id"]
            assert task["validation_commands"], task["task_id"]


def test_human_device_bound_request_creates_handoff_task(tmp_path: Path) -> None:
    request = tmp_path / "device-request.md"
    request.write_text("# Device request\n\nTry on device and approve visual polish with production credentials.\n", encoding="utf-8")

    payload, code = planner.run_planner_command(
        candidate_target=20,
        max_parallel_agents=5,
        mode="no-model",
        request_file=request,
        run_dir=tmp_path / "device",
        run_id="device",
        timestamp=FIXED_TS,
    )
    split_plan = read_json(tmp_path / "device" / "split-plan.json")

    assert code == 0, payload
    assert any(task["human_handoff"] and task["worker_profile"] == "human-operator" for task in split_plan["tasks"])


def test_proreq_mode_emits_manifest_and_prompt_without_live_call(tmp_path: Path) -> None:
    request = tmp_path / "request.md"
    request.write_text("# Planner request\n\nSplit a Patch Swarm planner into safe lanes.\n", encoding="utf-8")

    payload, code = planner.run_planner_command(
        candidate_target=20,
        max_parallel_agents=5,
        mode="proreq",
        request_file=request,
        run_dir=tmp_path / "proreq",
        run_id="proreq",
        timestamp=FIXED_TS,
    )
    manifest = read_json(tmp_path / "proreq" / "proreq" / "planning-manifest.json")

    assert code == 0, payload
    assert (tmp_path / "proreq" / "proreq" / "chatgpt-pro-planner-prompt.md").exists()
    assert manifest["live_pro_called"] is False


def test_manual_import_accepts_valid_import(tmp_path: Path) -> None:
    _, source_dir = run_fixture(tmp_path, 5, 2)

    payload, code = planner.run_planner_command(
        candidate_target=100,
        max_parallel_agents=5,
        mode="manual-import",
        import_plan=source_dir / "split-plan.json",
        run_dir=tmp_path / "manual-valid",
        run_id="manual-valid",
        timestamp=FIXED_TS,
    )

    assert code == 0, payload
    assert payload["ok"] is True
    assert (tmp_path / "manual-valid" / "split-plan.json").exists()
    assert (tmp_path / "manual-valid" / "task-graph.json").exists()


def test_manual_import_rejects_overlapping_owned_paths(tmp_path: Path) -> None:
    _, source_dir = run_fixture(tmp_path, 5, 2)
    plan = read_json(source_dir / "split-plan.json")
    plan["tasks"][1]["owned_paths"] = list(plan["tasks"][0]["owned_paths"])
    invalid = tmp_path / "overlap.json"
    invalid.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    payload, code = planner.run_planner_command(
        mode="manual-import",
        import_plan=invalid,
        run_dir=tmp_path / "manual-overlap",
        run_id="manual-overlap",
    )

    assert code != 0
    assert "owned path overlap" in payload["errors"][0]


def test_manual_import_rejects_unknown_dependency(tmp_path: Path) -> None:
    _, source_dir = run_fixture(tmp_path, 5, 2)
    plan = read_json(source_dir / "split-plan.json")
    plan["tasks"][0]["dependencies"] = ["task-9999"]
    invalid = tmp_path / "unknown-dependency.json"
    invalid.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    payload, code = planner.run_planner_command(
        mode="manual-import",
        import_plan=invalid,
        run_dir=tmp_path / "manual-dependency",
        run_id="manual-dependency",
    )

    assert code != 0
    assert "unknown dependency" in payload["errors"][0]


def test_manual_import_rejects_unsafe_paths(tmp_path: Path) -> None:
    _, source_dir = run_fixture(tmp_path, 5, 2)
    plan = read_json(source_dir / "split-plan.json")
    for unsafe_path in [".env.mcp", "../outside"]:
        plan["tasks"][0]["owned_paths"] = [unsafe_path]
        invalid = tmp_path / f"unsafe-{unsafe_path.replace('/', '-')}.json"
        invalid.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        payload, code = planner.run_planner_command(
            mode="manual-import",
            import_plan=invalid,
            run_dir=tmp_path / f"manual-{unsafe_path.replace('/', '-')}",
            run_id=f"manual-{unsafe_path.replace('/', '-')}",
        )

        assert code != 0
        assert any(fragment in payload["errors"][0] for fragment in [".env.mcp", "parent traversal"])


def test_cli_json_for_split_emits_valid_json(tmp_path: Path) -> None:
    request = tmp_path / "request.md"
    request.write_text("# Planner request\n\nBuild planner CLI coverage.\n", encoding="utf-8")
    run_dir = tmp_path / "cli"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "parallel_delivery.py"),
            "patch-swarm",
            "split",
            "--request-file",
            str(request),
            "--candidate-target",
            "5",
            "--max-parallel-agents",
            "2",
            "--fixture",
            "--run-id",
            "cli",
            "--run-dir",
            str(run_dir),
            "--json",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["candidate_count"] == 5
    assert (run_dir / "split-plan.json").exists()
