# Patch Swarm Deterministic Validation and Fixture E2E

## Overview

Patch Swarm deterministic validation E2E proves the local fixture flow from request intake through release-candidate evidence. It is a dry-run evidence path: fixture workers write local artifacts, patch bundles are validated against leases, integration records what would be applied, and no repository source files are patched.

The implementation is local-only. It does not call ChatGPT Pro, OpenAI APIs, Codex, MCP, Taskstream, Redmine, or live worker pools.

## Acceptance Command

```bash
cento parallel-delivery patch-swarm e2e \
  --candidate-target 100 \
  --max-parallel-agents 5 \
  --fixture \
  --json
```

For deterministic validation evidence:

```bash
cento parallel-delivery patch-swarm e2e \
  --candidate-target 100 \
  --max-parallel-agents 5 \
  --fixture \
  --run-id fixture-100-agents \
  --run-root workspace/runs/parallel-delivery/e2e-fixture \
  --fixed-timestamp 2026-01-01T00:00:00Z \
  --json
```

## Fixture Flow

The fixture flow is:

```text
request
  -> split
  -> leases
  -> worker packets
  -> fixture patch bundles
  -> patch validation
  -> malformed artifact rejection
  -> integration plan
  -> dry-run integration receipt
  -> validation summary
  -> release candidate evidence
```

## 100 Candidate Tasks with 5 Simulated Workers

`--candidate-target 100 --max-parallel-agents 5` creates 100 deterministic candidate tasks and 20 simulated worker batches. Simulated workers are local artifact writers only; they do not launch Codex or agents.

Every task is assigned to one batch, and no batch exceeds `max_parallel_agents`.

## Validation Engine

The validation engine writes and checks:

- `split-plan.json`
- `task-graph.json`
- `path-leases.json`
- `worker-packets/codex-packet-index.json`
- `patch-bundles/*.patch-bundle.json`
- `integration/integration-plan.json`
- `integration/integration-receipt.json`
- `release-candidate/release-candidate.json`

Use the direct helper to inspect policy or validate an existing run:

```bash
python3 scripts/parallel_delivery_validation_e2e.py print-policy --json
python3 scripts/parallel_delivery_validation_e2e.py validate-run --run-dir workspace/runs/parallel-delivery/e2e-fixture/fixture-100-agents --json
```

## Positive Checks

Positive checks require:

- every task has one lease
- owned lease paths do not overlap
- every task has one worker packet
- every valid fixture patch bundle changes only owned paths
- integration queue contains accepted bundles only
- dry-run receipt includes accepted bundles only
- release-candidate evidence exists

## Negative Checks

The fixture includes negative checks that pass only when unsafe input is rejected.

## Unsafe Bundle Rejection

The fixture writes `patch-bundles/unsafe-out-of-lease.patch-bundle.json`. It intentionally changes `README.md` without owning that path. Validation rejects it with a changed-path-outside-owned-lease reason, and the integration plan excludes it.

## Malformed Artifact Rejection

The fixture writes `validation/malformed/missing-run-id.json`. The malformed artifact is rejected because it omits `run_id`; `validation/malformed-artifact-validation.json` records the negative check.

## Dry-Run Integration

Dry-run integration writes:

- `integration/integration-plan.json`
- `integration/integration-receipt.json`
- `integration/dry-run-apply-log.jsonl`

No diffs are applied. The receipt state is `dry_run_completed`.

## Release Candidate Evidence

Release-candidate evidence is fixture-only:

- `release-candidate/release-candidate.json`
- `release-candidate/release-notes.md`

It records `rc_fixture_validated` and does not claim a production release.

## Run Directory Layout

Runs are written under:

```text
workspace/runs/parallel-delivery/e2e-fixture/<run-id>/
```

Required files include:

```text
request.md
run.json
context-pack.json
split-plan.json
task-graph.json
path-leases.json
worker-packets/codex-packet-bundle.json
worker-packets/codex-packet-index.json
fixture-workers/simulated-worker-ledger.jsonl
patch-bundles/
validation/artifact-validation.json
validation/lease-validation.json
validation/packet-validation.json
validation/patch-bundle-validation.json
validation/malformed-artifact-validation.json
integration/integration-plan.json
integration/integration-receipt.json
integration/rejected-patches.json
integration/dry-run-apply-log.jsonl
release-candidate/release-candidate.json
release-candidate/release-notes.md
validation-summary.json
validation-report.md
command-output.log
start-here.md
```

## JSON Output

`--json` emits one deterministic JSON object on stdout. Logs and evidence are written to files. Important fields include `ok`, `run_id`, `run_dir`, `candidate_target`, `candidate_count`, `max_parallel_agents`, `simulated_worker_batches`, `accepted_patch_bundles`, `rejected_patch_bundles`, `overall`, `validation_summary`, and `validation_report`.

## CLI Examples

```bash
cento parallel-delivery patch-swarm e2e --candidate-target 5 --max-parallel-agents 5 --fixture --json
cento parallel-delivery patch-swarm e2e --candidate-target 100 --max-parallel-agents 5 --fixture --json
python3 scripts/parallel_delivery_validation_e2e.py validate-run --run-dir workspace/runs/parallel-delivery/e2e-fixture/fixture-100-agents --json
```

## Troubleshooting

If `overall` is `failed`, inspect:

- `validation-summary.json`
- `validation-report.md`
- `validation/patch-bundle-validation.json`
- `integration/rejected-patches.json`

Common causes are overlapping owned paths, missing worker packets, malformed patch bundle JSON, changed paths outside the lease, or missing evidence files.

## Unsafe Rules

The fixture rejects protected or unsafe behavior:

- no secret-like paths
- no `.env` or `.env.mcp`
- no paths outside owned leases
- no binary patches
- no unsafe deletes
- no unowned renames
- no direct Taskstream/Redmine/story database mutation
- no destructive git commands
- no live AI/API/agent dispatch
