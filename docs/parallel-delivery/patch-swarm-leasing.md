# Patch Swarm Path Leasing and Workset Compatibility

## Overview

Patch Swarm path leasing turns `split-plan.json` and `task-graph.json` into a durable `path-leases.json` contract before prompts, validation, or integration run. The lease helper is `scripts/parallel_delivery_leases.py`, exposed through `cento parallel-delivery patch-swarm leases` and `validate-leases`.

This layer validates task ownership and planned patch metadata only. It does not dispatch workers, apply patches, or mutate Taskstream/Redmine/story state.

## Why Every Task Needs a Lease

Every patch task must declare explicit `owned_paths` before prompt emission. Tasks that cannot safely own paths are blocked or rejected with evidence. Shared files must be read-only unless one task owns them and later tasks depend on that output through a dependency gate.

## Read Many, Write Few

Many tasks may share `read_only_paths`. Write ownership is exclusive: active leases may not own the same path, a parent/child path pair, or a directory/file pair. Different files in the same directory are allowed when neither task owns the parent directory.

## Lease Artifact Schema

`path-leases.json` includes:

- `schema_version`, `artifact_type`, `run_id`, `created_at`, `updated_at`
- `provenance`, `lease_policy`, `leases`, `conflicts`
- `dependency_gates`, `parallel_groups`, `workset_manifest`
- `dirty_targets`, `warnings`, `evidence_pointers`

Each lease includes `lease_id`, `task_id`, `state`, `lane`, `risk_tier`, `owned_paths`, `read_only_paths`, `guarded_paths`, `protected_paths`, `dirty_owned_paths`, allowed and blocked operations, dependencies, dependency gate, parallel group, manual-review flags, timestamp, and evidence pointers.

## Stable Lease IDs

Lease IDs are deterministic:

```text
lease-<task_id>-<12_hex_sha256>
```

The hash uses the run id, task id, normalized owned paths, and normalized read-only paths. Dirty status changes warnings and risk metadata, not the lease ID.

## Protected Paths

Always rejected:

- `.env`, `.env.*`, `.env.mcp`
- `.git/**`
- `*.pem`, `*.key`
- paths containing `secret`, `token`, or `credential`
- absolute paths, `..`, home-relative paths, and repo-root cleanup paths

## Guarded Paths and Lockfiles

Guarded paths such as `data/tools.json`, `data/cento-cli.json`, `Makefile`, config files, and lockfiles are allowed only when explicitly owned by one task. They force high risk, manual review, and minimal hunks. Lockfiles also require the task contract to mention lockfile, package, or dependency validation.

## Dirty Target Handling

The lease tool parses `git status --porcelain=v1` path names without reading untracked file contents. Dirty owned paths become high-risk, require manual review, require minimal hunks, and add a warning to preserve unrelated hunks and forbid reset, checkout, clean, or stash.

## Overlap Detection

The validator rejects exact owned-path overlap and parent/child ownership overlap. Shared read-only paths are allowed. Owned path plus another task's read-only path is allowed, with dependency gates used when generated output must be consumed later.

## Dependency Gates

`depends_on` edges from `task-graph.json` become dependency gates. Guarded paths, dirty targets, and manual review also create gates so unsafe parallelism is surfaced explicitly instead of hidden in grouping.

## Parallel Groups

Parallel groups include only tasks that can run together safely. Dependent tasks are separated. Manual-review or blocked tasks are placed in non-automated groups. Shared read-only context does not block parallel grouping.

## Patch Operation Validation

`planned-operations.json` can validate future patch bundle claims without applying patches. It rejects unowned changes, unsafe deletes, unowned renames, binary patches, broad cleanup paths, lockfile changes outside explicit contract, and attempts to modify read-only-only paths.

## Workset Compatibility

Patch Swarm emits `path-leases.json` as the canonical contract. When a safe automatable subset exists, it also emits a Workset v1-compatible `workset-manifest.json` for `cento workset check WORKSET --allow-creates --json`. Guarded/manual-review tasks stay in the richer Patch Swarm lease artifact. `workset-compatibility.json` records the discovered Workset format and any command-shape gaps.

## CLI Examples

```bash
cento parallel-delivery patch-swarm leases \
  --run-dir workspace/runs/parallel-delivery/lease-fixture \
  --run-id lease-fixture \
  --fixture \
  --json
```

```bash
cento parallel-delivery patch-swarm validate-leases \
  --run-dir workspace/runs/parallel-delivery/lease-fixture \
  --json
```

```bash
python3 scripts/parallel_delivery_leases.py check-operations \
  --run-dir workspace/runs/parallel-delivery/lease-fixture \
  --operations workspace/runs/parallel-delivery/lease-fixture/planned-operations.json \
  --json
```

## Fixture Run

The deterministic fixture lives under `workspace/runs/parallel-delivery/lease-fixture/`. It includes `request.md`, `split-plan.json`, `task-graph.json`, `path-leases.json`, `lease-conflicts.json`, reports, Workset compatibility evidence, planned operations, `start-here.md`, and conflict examples.

## Validation Commands

```bash
python3 scripts/parallel_delivery_leases.py print-policy --json
python3 scripts/parallel_delivery_leases.py write-fixture --run-dir workspace/runs/parallel-delivery/lease-fixture --run-id lease-fixture --fixed-timestamp 2026-01-01T00:00:00Z --json
python3 scripts/parallel_delivery_leases.py validate --run-dir workspace/runs/parallel-delivery/lease-fixture --json
pytest -q tests/test_parallel_delivery_path_leases.py
```

## Unsafe Rejection Rules

- Do not include secrets.
- Do not copy `.env.mcp`.
- Do not store OpenAI keys or local secret values.
- Do not store absolute secret paths.
- Do not directly mutate Taskstream/Redmine/story state.
- Do not claim validation passed without validation evidence.
- Do not write generated run artifacts outside `workspace/runs/`.
- Do not apply patches in the lease validation slice.
