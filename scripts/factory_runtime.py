#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shlex
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import factory_dispatch_core


ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = {
    "noop": {
        "description": "Lifecycle adapter that records prepare/launch/status/collect/cancel without side effects.",
        "execute_supported": False,
    },
    "local-shell-fixture": {
        "description": "Deterministic fixture adapter that writes a bounded patch bundle without running external workers.",
        "execute_supported": False,
    },
    "codex-dry-run": {
        "description": "Renders the Codex launch command, prompt, and environment without executing Codex.",
        "execute_supported": False,
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected object JSON: {path}")
    return payload


def run_dir_for(value: str | Path) -> Path:
    return factory_dispatch_core.resolve_run_dir(value)


def runtime_dir(run_dir: Path, task_id: str) -> Path:
    return run_dir / "runtime" / task_id


def load_task(run_dir: Path, task_id: str) -> dict[str, Any]:
    queue = factory_dispatch_core.load_queue(run_dir)
    return factory_dispatch_core.find_queue_task(queue, task_id)


def adapter_run_id(run_dir: Path, task_id: str, runtime: str) -> str:
    return f"{run_dir.name}-{task_id}-{runtime}"


def ensure_adapter(runtime: str) -> None:
    if runtime not in ADAPTERS:
        raise SystemExit(f"unknown runtime adapter: {runtime}")


def first_owned_output(item: dict[str, Any]) -> str:
    owned = factory_dispatch_core.owned_paths_for(item)
    if not owned:
        return f"workspace/runs/factory/runtime/{factory_dispatch_core.task_id(item)}/output.txt"
    path = owned[0].rstrip("/")
    suffix = Path(path).suffix
    return path if suffix else f"{path}/runtime-fixture-output.txt"


def base_adapter_payload(run_dir: Path, task_id: str, runtime: str) -> dict[str, Any]:
    item = load_task(run_dir, task_id)
    return {
        "schema_version": "factory-runtime-adapter-run/v1",
        "run_id": run_dir.name,
        "task_id": task_id,
        "runtime": runtime,
        "adapter_run_id": adapter_run_id(run_dir, task_id, runtime),
        "base_sha": factory_dispatch_core.git_sha(),
        "owned_paths": factory_dispatch_core.owned_paths_for(item),
        "dry_run": True,
        "execute_supported": bool(ADAPTERS[runtime]["execute_supported"]),
        "unsupported_execute_reason": "runtime adapter v1 is contract-first; real execution is out of scope",
        "ai_calls_used": 0,
        "estimated_cost_usd": 0,
    }


def write_logs(rdir: Path, stdout: str = "", stderr: str = "") -> None:
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "stdout.log").write_text(stdout, encoding="utf-8")
    (rdir / "stderr.log").write_text(stderr, encoding="utf-8")


def write_common_files(run_dir: Path, task_id: str, runtime: str, status: str, *, phase: str) -> dict[str, Any]:
    rdir = runtime_dir(run_dir, task_id)
    rdir.mkdir(parents=True, exist_ok=True)
    payload = base_adapter_payload(run_dir, task_id, runtime)
    payload.update({"status": status, "phase": phase, "updated_at": now_iso()})
    write_json(rdir / "adapter-run.json", payload)
    write_json(
        rdir / "status.json",
        {
            "schema_version": "factory-runtime-status/v1",
            "run_id": run_dir.name,
            "task_id": task_id,
            "runtime": runtime,
            "status": status,
            "phase": phase,
            "updated_at": now_iso(),
            "ai_calls_used": 0,
            "estimated_cost_usd": 0,
        },
    )
    write_json(
        rdir / "cost.json",
        {
            "schema_version": "factory-runtime-cost/v1",
            "run_id": run_dir.name,
            "task_id": task_id,
            "runtime": runtime,
            "ai_calls_used": 0,
            "estimated_cost_usd": 0,
            "budget_check": "passed",
            "generated_at": now_iso(),
        },
    )
    write_json(
        rdir / "heartbeat.json",
        {
            "schema_version": "factory-runtime-heartbeat/v1",
            "run_id": run_dir.name,
            "task_id": task_id,
            "runtime": runtime,
            "status": status,
            "heartbeat_at": now_iso(),
            "expires_at": (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
        },
    )
    return payload


def launch_plan(run_dir: Path, task_id: str, runtime: str) -> dict[str, Any]:
    item = load_task(run_dir, task_id)
    task_dir = run_dir / "tasks" / task_id
    prompt_path = task_dir / "worker-prompt.md"
    if not prompt_path.exists():
        factory_dispatch_core.render_worker_prompt(run_dir, item, mode="runtime_dry_run")
    command: list[str]
    env: dict[str, str]
    if runtime == "codex-dry-run":
        command = ["codex", "exec", "--sandbox", "workspace-write", "--cd", rel(ROOT), "--prompt-file", rel(prompt_path)]
        env = {"CENTO_FACTORY_RUN": run_dir.name, "CENTO_FACTORY_TASK": task_id, "CENTO_RUNTIME_MODE": "dry-run"}
    elif runtime == "local-shell-fixture":
        command = ["bash", "-lc", f"printf '%s\\n' {shlex.quote('local-shell-fixture patch')}"]
        env = {"CENTO_RUNTIME_MODE": "fixture"}
    else:
        command = ["true"]
        env = {"CENTO_RUNTIME_MODE": "noop"}
    return {
        "schema_version": "factory-runtime-launch-plan/v1",
        "run_id": run_dir.name,
        "task_id": task_id,
        "runtime": runtime,
        "dry_run_command": command,
        "execute_command": [],
        "execute_supported": False,
        "unsupported_execute_reason": "factory-runtime-adapters-v1 does not execute real workers",
        "side_effects_if_execute": ["worker_process", "worktree_writes", "patch_bundle"],
        "env": env,
        "prompt": rel(prompt_path),
        "timeout_seconds": 900,
        "budget": {"ai_calls_allowed": 0, "estimated_cost_limit_usd": 0},
        "owned_path_check": "passed" if factory_dispatch_core.owned_paths_for(item) else "failed",
        "generated_at": now_iso(),
    }


def prepare(run_dir: Path, task_id: str, runtime: str, *, dry_run: bool) -> dict[str, Any]:
    ensure_adapter(runtime)
    if not dry_run:
        raise SystemExit("factory runtime prepare v1 requires --dry-run")
    rdir = runtime_dir(run_dir, task_id)
    write_common_files(run_dir, task_id, runtime, "prepared", phase="prepare")
    plan = launch_plan(run_dir, task_id, runtime)
    write_json(rdir / "launch-plan.json", plan)
    write_json(
        rdir / "worker-ledger.json",
        {
            "schema_version": "factory-runtime-worker-ledger/v1",
            "run_id": run_dir.name,
            "task_id": task_id,
            "runtime": runtime,
            "events": [{"ts": now_iso(), "event": "prepared", "dry_run": True}],
            "ai_calls_used": 0,
            "estimated_cost_usd": 0,
        },
    )
    write_logs(rdir)
    return {"schema_version": "factory-runtime-prepare-result/v1", "run_id": run_dir.name, "task_id": task_id, "runtime": runtime, "launch_plan": rel(rdir / "launch-plan.json"), "adapter_run": rel(rdir / "adapter-run.json")}


def write_fixture_patch(run_dir: Path, task_id: str, runtime: str) -> dict[str, Any]:
    item = load_task(run_dir, task_id)
    rdir = runtime_dir(run_dir, task_id)
    patch_dir = rdir / "patch"
    patch_dir.mkdir(parents=True, exist_ok=True)
    changed_file = first_owned_output(item)
    patch_text = "\n".join(
        [
            f"diff --git a/{changed_file} b/{changed_file}",
            "new file mode 100644",
            "index 0000000..e69de29",
            "--- /dev/null",
            f"+++ b/{changed_file}",
            "@@ -0,0 +1 @@",
            f"+runtime fixture output for {task_id}",
            "",
        ]
    )
    (patch_dir / "patch.diff").write_text(patch_text, encoding="utf-8")
    (patch_dir / "changed-files.txt").write_text(changed_file + "\n", encoding="utf-8")
    (patch_dir / "diffstat.txt").write_text(f"1 file changed: {changed_file}\n", encoding="utf-8")
    (patch_dir / "handoff.md").write_text(f"# Runtime Fixture Handoff\n\nTask: `{task_id}`\nRuntime: `{runtime}`\n", encoding="utf-8")
    write_json(
        patch_dir / "validation-result.json",
        {
            "schema_version": "factory-validation-result/v1",
            "status": "passed",
            "runtime": runtime,
            "ai_calls_used": 0,
            "estimated_cost_usd": 0,
            "generated_at": now_iso(),
        },
    )
    patch = {
        "schema_version": "factory-patch/v1",
        "run_id": run_dir.name,
        "task_id": task_id,
        "runtime": runtime,
        "patch_file": "patch.diff",
        "changed_files": [changed_file],
        "diffstat_file": "diffstat.txt",
        "handoff_file": "handoff.md",
        "validation_result": "validation-result.json",
        "evidence_paths": [],
        "collection_state": "collected",
        "owned_path_check": "passed" if factory_dispatch_core.path_allowed(changed_file, factory_dispatch_core.owned_paths_for(item)) else "failed",
        "protected_path_failures": [],
        "git_apply_check": "pending",
        "docs_registry_gate": "not_applicable",
        "validation_status": "passed",
        "integration_status": "candidate",
    }
    write_json(patch_dir / "patch.json", patch)
    return patch


def launch(run_dir: Path, task_id: str, runtime: str, *, dry_run: bool) -> dict[str, Any]:
    ensure_adapter(runtime)
    if not dry_run:
        raise SystemExit("factory runtime launch v1 requires --dry-run")
    rdir = runtime_dir(run_dir, task_id)
    if not (rdir / "launch-plan.json").exists():
        prepare(run_dir, task_id, runtime, dry_run=True)
    write_common_files(run_dir, task_id, runtime, "completed" if runtime != "codex-dry-run" else "planned", phase="launch")
    if runtime == "local-shell-fixture":
        write_fixture_patch(run_dir, task_id, runtime)
        write_logs(rdir, stdout="local-shell-fixture produced deterministic patch bundle\n")
    elif runtime == "codex-dry-run":
        plan = read_json(rdir / "launch-plan.json")
        write_logs(rdir, stdout="codex dry-run launch rendered only\n" + shlex.join(plan.get("dry_run_command") or []) + "\n")
    else:
        write_logs(rdir, stdout="noop adapter launch recorded\n")
    ledger = read_json(rdir / "worker-ledger.json") if (rdir / "worker-ledger.json").exists() else {"schema_version": "factory-runtime-worker-ledger/v1", "events": []}
    ledger.setdefault("events", []).append({"ts": now_iso(), "event": "launch_recorded", "runtime": runtime, "dry_run": True})
    write_json(rdir / "worker-ledger.json", ledger)
    return {"schema_version": "factory-runtime-launch-result/v1", "run_id": run_dir.name, "task_id": task_id, "runtime": runtime, "status": "completed" if runtime != "codex-dry-run" else "planned", "adapter_run": rel(rdir / "adapter-run.json")}


def mirror_patch_to_factory(run_dir: Path, task_id: str, runtime: str) -> dict[str, Any] | None:
    src = runtime_dir(run_dir, task_id) / "patch"
    if not (src / "patch.json").exists():
        return None
    dest = run_dir / "patches" / task_id
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("patch.diff", "changed-files.txt", "diffstat.txt", "handoff.md", "validation-result.json"):
        (dest / name).write_text((src / name).read_text(encoding="utf-8"), encoding="utf-8")
    patch = read_json(src / "patch.json")
    patch["patch_bundle_source"] = rel(src / "patch.json")
    write_json(dest / "patch.json", patch)
    queue = factory_dispatch_core.load_queue(run_dir)
    try:
        item = factory_dispatch_core.find_queue_task(queue, task_id)
        item["patch_bundle"] = rel(dest / "patch.json")
        item["status"] = "ready_to_integrate"
        item["last_event"] = "runtime_patch_collected"
        factory_dispatch_core.save_queue(run_dir, queue)
    except factory_dispatch_core.FactoryDispatchError:
        pass
    return patch


def collect(run_dir: Path, task_id: str) -> dict[str, Any]:
    rdir = runtime_dir(run_dir, task_id)
    adapter = read_json(rdir / "adapter-run.json") if (rdir / "adapter-run.json").exists() else {}
    runtime = str(adapter.get("runtime") or "unknown")
    patch = mirror_patch_to_factory(run_dir, task_id, runtime)
    result = {
        "schema_version": "factory-runtime-collect-result/v1",
        "run_id": run_dir.name,
        "task_id": task_id,
        "runtime": runtime,
        "patch_collected": bool(patch),
        "factory_patch": rel(run_dir / "patches" / task_id / "patch.json") if patch else "",
        "ai_calls_used": 0,
        "estimated_cost_usd": 0,
        "generated_at": now_iso(),
    }
    write_json(rdir / "collect-result.json", result)
    write_common_files(run_dir, task_id, runtime if runtime in ADAPTERS else "noop", "collected", phase="collect")
    return result


def cancel(run_dir: Path, task_id: str, *, dry_run: bool) -> dict[str, Any]:
    if not dry_run:
        raise SystemExit("factory runtime cancel v1 requires --dry-run")
    rdir = runtime_dir(run_dir, task_id)
    adapter = read_json(rdir / "adapter-run.json") if (rdir / "adapter-run.json").exists() else {"runtime": "unknown"}
    runtime = str(adapter.get("runtime") or "unknown")
    result = {
        "schema_version": "factory-runtime-cancel-result/v1",
        "run_id": run_dir.name,
        "task_id": task_id,
        "runtime": runtime,
        "dry_run": True,
        "would_cancel": True,
        "status": "cancel_simulated",
        "generated_at": now_iso(),
    }
    write_json(rdir / "cancel-result.json", result)
    if runtime in ADAPTERS:
        write_common_files(run_dir, task_id, runtime, "cancel_simulated", phase="cancel")
    return result


def status(run_dir: Path, task_id: str) -> dict[str, Any]:
    rdir = runtime_dir(run_dir, task_id)
    return {
        "schema_version": "factory-runtime-status-report/v1",
        "run_id": run_dir.name,
        "task_id": task_id,
        "adapter_run": read_json(rdir / "adapter-run.json") if (rdir / "adapter-run.json").exists() else {},
        "status": read_json(rdir / "status.json") if (rdir / "status.json").exists() else {},
        "launch_plan": rel(rdir / "launch-plan.json") if (rdir / "launch-plan.json").exists() else "",
        "collect_result": read_json(rdir / "collect-result.json") if (rdir / "collect-result.json").exists() else {},
        "artifacts": {
            "runtime_dir": rel(rdir),
            "patch": rel(rdir / "patch" / "patch.json") if (rdir / "patch" / "patch.json").exists() else "",
        },
        "ai_calls_used": 0,
        "estimated_cost_usd": 0,
    }


def list_adapters() -> dict[str, Any]:
    return {
        "schema_version": "factory-runtime-adapters/v1",
        "adapters": [{"id": name, **meta} for name, meta in sorted(ADAPTERS.items())],
        "default": "noop",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Factory runtime adapter contract commands.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("list", help="List runtime adapters.")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("prepare", help="Prepare a runtime adapter run.")
    p.add_argument("run_id")
    p.add_argument("--task", required=True)
    p.add_argument("--runtime", default="noop")
    p.add_argument("--dry-run", action="store_true", default=True)
    p = sub.add_parser("launch", help="Launch or simulate a runtime adapter run.")
    p.add_argument("run_id")
    p.add_argument("--task", required=True)
    p.add_argument("--runtime", default="noop")
    p.add_argument("--dry-run", action="store_true", default=True)
    p = sub.add_parser("status", help="Show runtime adapter status.")
    p.add_argument("run_id")
    p.add_argument("--task", required=True)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("collect", help="Collect runtime adapter output.")
    p.add_argument("run_id")
    p.add_argument("--task", required=True)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("cancel", help="Cancel or simulate cancellation of a runtime adapter run.")
    p.add_argument("run_id")
    p.add_argument("--task", required=True)
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "list":
        payload = list_adapters()
    else:
        run_dir = run_dir_for(args.run_id)
        if args.command == "prepare":
            payload = prepare(run_dir, args.task, args.runtime, dry_run=args.dry_run)
        elif args.command == "launch":
            payload = launch(run_dir, args.task, args.runtime, dry_run=args.dry_run)
        elif args.command == "status":
            payload = status(run_dir, args.task)
        elif args.command == "collect":
            payload = collect(run_dir, args.task)
        elif args.command == "cancel":
            payload = cancel(run_dir, args.task, dry_run=args.dry_run)
        else:
            raise SystemExit(f"unknown command: {args.command}")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
