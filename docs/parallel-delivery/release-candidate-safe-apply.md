# Parallel Delivery Safe Apply And Release Candidate

## Overview

`cento parallel-delivery release-candidate create` turns an accepted integration receipt into deterministic apply evidence. It verifies accepted patch bundle receipts, refuses rejected or non-integratable bundles, checks patch SHA-256 values, performs mechanical dry-run checks, and writes apply receipts, rollback metadata, and release-candidate artifacts.

The command is local-only. It does not dispatch workers, call AI APIs, mutate Taskstream or Redmine state, merge branches, push commits, or apply patches to the operator worktree.

## CLI

```bash
cento parallel-delivery release-candidate create \
  --integration-receipt workspace/runs/parallel-delivery/release-candidate-fixture/input/integration-receipt.accepted.json \
  --out workspace/runs/parallel-delivery/release-candidate-fixture/dry-run \
  --mode dry-run \
  --target-repo workspace/runs/parallel-delivery/release-candidate-fixture/fixture-repo \
  --base-commit "$(git rev-parse HEAD)" \
  --json
```

```bash
cento parallel-delivery release-candidate create \
  --integration-receipt workspace/runs/parallel-delivery/release-candidate-fixture/input/integration-receipt.accepted.json \
  --out workspace/runs/parallel-delivery/release-candidate-fixture/apply \
  --mode apply \
  --target-repo workspace/runs/parallel-delivery/release-candidate-fixture/fixture-repo \
  --target-worktree workspace/runs/parallel-delivery/release-candidate-fixture/integration-worktree \
  --base-commit "$(git rev-parse HEAD)" \
  --final-validation-cmd "python -m pytest -q tests" \
  --json
```

Dry-run is the default-safe mode. Apply mode requires an explicit isolated target worktree under `workspace/runs/`, `workspace/factory-integration-worktrees/`, or `/tmp`.

## Inputs

The command reads `cento.parallel_delivery.integration_receipt.v1`:

- `status` must be `accepted`.
- `accepted_bundle_receipts` lists local bundle receipt paths.
- `rejected_bundle_receipts` is retained as evidence but is never applied.
- `apply_order` controls deterministic bundle order.
- `final_validation_commands` run after successful apply before a ready release candidate can be written.

Each applied bundle receipt must be accepted, `integratable=true`, contain a patch path, and contain a matching `patch_sha256`.

## Outputs

The output directory contains:

- `apply-report.json`
- `apply-report.md`
- `apply-receipts/step-NNN-<bundle-id>.json`
- `logs/*.stdout`
- `logs/*.stderr`
- `rollback-metadata.json`

Successful apply mode also writes:

- `release-candidate.json`
- `release-notes.md`
- `integrated.diff`

Rejected receipts write `refusal.json` and exit non-zero.

## Safety Rules

The safe apply layer refuses unsafe command snippets such as `git reset`, `git checkout`, `git clean`, `git stash`, `.env.mcp`, and direct Taskstream or Redmine database commands. Rollback is metadata-only: the recorded strategy is isolated worktree abandonment or dry-run no changes.

Dry-run runs `git apply --check --whitespace=error-all` for each accepted bundle and applies zero patches. Apply mode first runs the same mechanical check, then applies bundles sequentially with `git apply` in the isolated target, validates after each bundle, and stops on the first patch or validation failure.

## Schemas

This layer writes:

- `cento.parallel_delivery.apply_step_receipt.v1`
- `cento.parallel_delivery.apply_report.v1`
- `cento.parallel_delivery.rollback_metadata.v1`
- `cento.parallel_delivery.release_candidate.v1`

It also supports the minimal local input schemas:

- `cento.parallel_delivery.integration_receipt.v1`
- `cento.parallel_delivery.bundle_receipt.v1`

## Fixture

Generate fixture inputs:

```bash
python3 scripts/parallel_delivery/release_candidate_fixture.py \
  --out workspace/runs/parallel-delivery/release-candidate-fixture \
  --base-commit "$(git rev-parse HEAD)"
```

The fixture creates a tiny isolated target repo, two accepted bundle receipts, one rejected bundle receipt, accepted and rejected integration receipts, and patch files under `workspace/runs/parallel-delivery/release-candidate-fixture/input/`.

## Validation

```bash
python3 -m pytest -q \
  tests/test_parallel_delivery_safe_apply.py \
  tests/test_parallel_delivery_release_candidate.py
```

The tests cover accepted and rejected integration receipts, rejected and non-integratable bundle receipts, patch hash mismatch refusal, dry-run no-mutation behavior, sequential apply, first-failure stopping, rollback metadata, release-candidate creation, and CLI JSON output.
