# Patch Swarm Worker Pool and Process Visibility

## Overview

Patch Swarm worker status is a local, dry-run-first layer for planning bounded worker dispatch and rendering operator-visible status. It consumes `split-plan.json`, `task-graph.json`, `path-leases.json`, and optional worker packet metadata, then writes worker pool, dispatch, queue, status, stale/risk, process visibility, and Console/UI artifacts.

## 100 Candidate Tasks, Bounded Workers

Patch Swarm may represent up to 100 candidate tasks, but it must not launch 100 workers blindly. `max_parallel_agents` controls batch size. The fixture proves 100 tasks with `max_parallel_agents=5`, producing 20 planned batches with no task appearing in more than one batch.

## Dry-Run Dispatch

Dry-run dispatch is the default. `cento parallel-delivery patch-swarm dispatch --dry-run --fixture --json` writes dispatch metadata and queue events without running `cento agent-pool-kick`, external Codex, tmux commands, or process/session mutation. Unsupported `--live` dispatch fails closed unless a later explicit backend owns it.

## Worker Pool Plan

`worker-pool-plan.json` records candidate count, max parallel agents, dispatch policy, task lease metadata, bounded batches, blocked/stale indicators, warnings, and evidence pointers. It is the operator review artifact for deciding whether a run can move from local planning to an explicit live dispatch path.

## Queue Ledger

`worker-queue-ledger.jsonl` is append-style JSONL. Events include `queue_created`, `task_queued`, `dispatch_planned`, `dispatch_skipped_dry_run`, `worker_active`, `worker_completed`, `worker_blocked`, `worker_stale`, `worker_failed`, and `status_snapshot`.

## Worker Status JSON

`worker-status.json` summarizes active, pending, completed, blocked, stale, and failed task counts. The fixture state is 5 active dry-run workers, 92 pending tasks, 1 completed task, 1 blocked task, 1 stale task, and 0 failed tasks.

## Console/UI Status JSON

`console-status.json` is a compact UI payload with run state, candidate count, max workers, status counts, risk level, stale indicators, risk indicators, artifact links, and the next operator action. Detailed ledgers stay in separate artifacts.

## Stale and Risk Indicators

Stale detection considers state, `updated_at`, `last_heartbeat_at`, `stale_after_seconds`, blocked reasons, risk tier, dependency gates, dirty/manual-review flags, missing leases, missing worker packets, and process visibility mismatches. The default fixture threshold is 3600 seconds.

## Process Visibility Compatibility

`process-visibility.json` bridges local Patch Swarm status to existing process surfaces without assuming process availability. Fixture process IDs are `null`, status is `dry_run_not_launched`, and platform process inspection is recorded as unavailable unless a safe backend explicitly provides it.

## agent-pool-kick Integration

`agent-pool-kick` already supports `--dry-run` and bounded `--max-launch` behavior. Patch Swarm records compatible metadata but does not call it by default. Live launch remains a separate explicit opt-in path.

## agent-processes Integration

`agent-processes` is read-only status visibility. Operators can use `cento agent-processes --once` outside the fixture to inspect current managed/manual sessions. Patch Swarm does not mutate or reset those sessions.

## Cluster and Bridge Status

`cento cluster status` and `cento bridge status` are read-only compatibility surfaces. Patch Swarm status records the commands and availability metadata but does not heal, start, stop, restart, or execute remote commands.

## Platform Guards

The worker-status helper uses standard-library platform checks and `shutil.which`. It does not assume tmux, Linux `ps`, macOS process fields, or OCI bridge availability. Missing process support is a warning, not a fixture failure.

## CLI Examples

```bash
cento parallel-delivery patch-swarm dispatch \
  --run-dir workspace/runs/parallel-delivery/worker-status-fixture \
  --run-id worker-status-fixture \
  --candidate-target 100 \
  --max-parallel-agents 5 \
  --dry-run \
  --fixture \
  --json

cento parallel-delivery patch-swarm worker-status \
  --run-dir workspace/runs/parallel-delivery/worker-status-fixture \
  --json

cento parallel-delivery status \
  --run worker-status-fixture \
  --run-root workspace/runs/parallel-delivery \
  --json
```

## Fixture Run

The deterministic fixture lives under `workspace/runs/parallel-delivery/worker-status-fixture/` and writes `request.md`, `split-plan.json`, `task-graph.json`, `path-leases.json`, `worker-pool-plan.json`, `dry-run-dispatch.json`, `worker-queue-ledger.jsonl`, `worker-status.json`, `worker-status-report.md`, `stale-workers.json`, `process-visibility.json`, `console-status.json`, and `start-here.md`.

## Validation Commands

```bash
python3 scripts/parallel_delivery_worker_status.py validate-status \
  --run-dir workspace/runs/parallel-delivery/worker-status-fixture \
  --json

pytest -q tests/test_parallel_delivery_worker_status.py
```

Validation checks parseability, batch bounds, duplicate task dispatch, status count consistency, stale/blocked fixture detection, dry-run launch refusal, process read-only flags, and Console/UI fields.

## Unsafe Operations

The worker-status layer must not launch external agents, mutate tmux/process state, kill/restart processes, write Taskstream/Redmine directly, inspect secrets, copy environment values, apply patches, or reset/clean/stash/checkout unrelated work.
