# Patch Swarm Artifact Schema

## Overview

Patch Swarm artifact schemas define the durable run contract for Parallel Software Delivery. They cover run state, task state, path leases, worker prompts, worker ledgers, patch bundles, validation, integration receipts, release candidate evidence, and the operator entrypoint artifact.

This contract is schema and evidence only. It does not claim live planning, worker dispatch, patch application, or full integration runtime support.

## Run Directory Layout

The canonical schema fixture and future run contract use this root-relative shape:

```text
workspace/runs/parallel-delivery/<run_id>/
  run.json
  request.md
  context-pack.json
  split-plan.json
  task-graph.json
  path-leases.json
  worker-prompts/
    manifest.json
    task-0001.md
  worker-ledger.jsonl
  patch-bundles/
    manifest.json
    task-0001.bundle.json
    task-0001.patch
  integration-plan.json
  integration-receipt.json
  validation.json
  validation-report.md
  release-candidate.json
  release-notes.md
  start-here.md
```

The generated fixture lives at `workspace/runs/parallel-delivery/schema-fixture/`.

## Common Metadata

Every JSON artifact includes:

```json
{
  "schema_version": 1,
  "artifact_type": "run",
  "run_id": "schema-fixture",
  "created_at": "2026-01-01T00:00:00Z",
  "provenance": {
    "producer": "cento.parallel-delivery.artifacts",
    "command": "schema-fixture",
    "source": "fixture",
    "repo": "cento",
    "notes": []
  },
  "evidence_pointers": []
}
```

Mutable JSON artifacts also include `updated_at` when their state can change. Markdown artifacts start with a parseable metadata comment:

```markdown
<!-- cento-artifact: {"schema_version":1,"artifact_type":"request","run_id":"schema-fixture","created_at":"2026-01-01T00:00:00Z"} -->
```

## Versioning and Compatibility

- `schema_version == 1`: valid.
- `schema_version < 1`: invalid until an explicit compatibility shim exists.
- `schema_version > 1`: invalid by default.
- `schema_version > 1` with `allow_future=True`: allowed for generic/common checks only.
- Unknown extra fields are allowed.
- Missing required fields are fatal.
- Invalid `artifact_type`, state, or transition is fatal.

## Run States

Allowed run states:

```text
request_received
run_created
context_packed
split_planned
task_graph_ready
paths_leased
prompts_emitted
workers_started
patches_collected
validation_started
validation_passed
validation_failed
integration_planned
integration_started
integration_completed
rc_built
rc_validated
completed
failed
aborted
```

Terminal states are `completed`, `failed`, and `aborted`. The schema helper enforces known transitions and rejects movement out of terminal states.

## Task States

Allowed task states:

```text
created
context_ready
leased
prompt_emitted
dispatched
patch_submitted
validation_running
validation_passed
validation_failed
queued_for_integration
integrated
rejected
superseded
aborted
```

Terminal task states are `integrated`, `rejected`, `superseded`, and `aborted`.

## Artifact Producer / Consumer Matrix

| Artifact | Produced by | Consumed by |
| --- | --- | --- |
| `run.json` | `patch-swarm init` / fixture builder | status, validator, release evidence |
| `request.md` | operator / init | context packer, splitter |
| `context-pack.json` | context packer | splitter, prompt emitter |
| `split-plan.json` | factory splitter | task graph builder, lease planner |
| `task-graph.json` | task graph builder | scheduler, integrator |
| `path-leases.json` | workset lease planner | prompt emitter, patch bundle validator |
| `worker-prompts/` | prompt emitter | Codex/worker threads |
| `worker-ledger.jsonl` | dispatcher/collector | status, validation, evidence |
| `patch-bundles/` | workers/collector | validation, integrator |
| `integration-plan.json` | safe integrator planner | safe integrator executor |
| `integration-receipt.json` | safe integrator | release candidate builder |
| `validation.json` | validator/build | release candidate builder, status |
| `validation-report.md` | validator/build | operator, evidence |
| `release-candidate.json` | RC builder | release notes, operator |
| `release-notes.md` | RC builder | operator |
| `start-here.md` | evidence writer | operator |

## Artifact Schemas

`run.json` records `request_title`, `state`, `artifact_paths`, `counts`, optional operator metadata, compatibility notes, failure reason, and completion time.

`context-pack.json` records safe repo metadata only: repo name, default branch, relevant surfaces, dirty-work policy, source refs, constraints, and request reference.

`split-plan.json` records up to 100 candidate tasks. Every task has a task ID, title, summary, state, acceptance contract, validation commands, owned paths, and read-only paths.

`task-graph.json` records task nodes and edges. Dependency edges must be acyclic.

`path-leases.json` records proposed, active, released, conflict, or expired leases. Paths must be relative repo paths and active owned paths must not overlap.

`worker-prompts/manifest.json` indexes prompt files by task ID, relative path, SHA-256, and creation time. Each prompt Markdown file has a `cento-artifact` metadata comment.

`worker-ledger.jsonl` records one event per line. Invalid JSON reports the exact line number.

`patch-bundles/manifest.json` indexes patch bundles. Each bundle records task ID, bundle ID, base ref, changed paths, claimed paths, diff path, tests run, summary, evidence pointers, and manual-review status. Changed paths must be inside the task lease and claimed paths.

`integration-plan.json` records the integration strategy, queue, rejected entries, validation references, and ordering reasons.

`integration-receipt.json` records started and completed timestamps, integrated entries, rejected entries, conflicts, strategy, and final state.

`validation.json` records schema checks, command checks, task checks, overall result, and evidence pointers.

`release-candidate.json` records RC ID, included tasks, included bundles, validation reference, source integration receipt, state, and evidence pointers.

`validation-report.md`, `release-notes.md`, and `start-here.md` are human-facing Markdown artifacts with metadata comments and required sections.

## Evidence Pointers

Evidence pointers are objects that can include `artifact_type`, `path`, `sha256`, and `description`. Paths must be relative to the run directory or repo context. Absolute paths, parent traversal, `.env.mcp`, and secret-like paths are rejected.

## Failure States

Run failure states:

- `failed`: deterministic validation, schema validation, planning, integration, or release-candidate construction failed.
- `aborted`: operator or safety policy stopped the run.

Task failure states:

- `validation_failed`: deterministic validation failed.
- `rejected`: the task is not eligible for integration.
- `superseded`: a newer task or bundle replaces it with evidence.
- `aborted`: operator or safety policy stopped the task.

Integration final states:

- `integration_completed`
- `integration_failed`
- `integration_aborted`

Release candidate states:

- `rc_built`
- `rc_validated`
- `rc_failed`

## Validation Commands

Print the schema summary:

```bash
python3 scripts/parallel_delivery_artifacts.py print-schema-summary --json
```

Write the deterministic fixture:

```bash
python3 scripts/parallel_delivery_artifacts.py write-fixture \
  --run-dir workspace/runs/parallel-delivery/schema-fixture \
  --run-id schema-fixture \
  --fixed-timestamp 2026-01-01T00:00:00Z
```

Validate a run directory:

```bash
python3 scripts/parallel_delivery_artifacts.py validate-run \
  --run-dir workspace/runs/parallel-delivery/schema-fixture \
  --json
```

## Fixture Run

The fixture is deterministic when `--fixed-timestamp` is provided. It includes all required schema artifacts, two worker prompts, one patch bundle, an integration plan and receipt, validation evidence, release notes, and `start-here.md`.

The fixture does not apply patches or dispatch live workers.

## Unsafe Artifact Rules

- Do not include secrets.
- Do not copy `.env.mcp`.
- Do not store OpenAI keys or local secret values.
- Do not store absolute secret paths.
- Do not directly mutate Taskstream, Redmine, or story database state.
- Do not claim validation passed without validation evidence.
- Do not write generated run artifacts outside `workspace/runs/`.
