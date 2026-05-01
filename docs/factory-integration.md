# Factory Integration

Factory integration is the Safe Integrator layer for Cento Factory. It turns collected patch bundles into an isolated release candidate without merging to main automatically.

The flow is deterministic and no-model by default:

```bash
cento factory integrate factory-integration-e2e --plan
cento factory integrate factory-integration-e2e \
  --prepare-branch \
  --branch factory/factory-integration-e2e/integration
cento factory integrate factory-integration-e2e \
  --apply \
  --validate-each \
  --limit 3
cento factory validate-integrated factory-integration-e2e
cento factory release-candidate factory-integration-e2e
cento factory sync-taskstream factory-integration-e2e --dry-run
```

## Policy

Safe Integrator creates an integration worktree under `workspace/factory-integration-worktrees/<run-id>/` and records the branch in `integration/integration-branch.json`. Patches are applied there one at a time. Main is not touched, and Taskstream is not moved to Done.

`apply-plan.json` orders candidate patches by dependency and risk. The applier runs `git apply --check`, applies a patch, runs per-patch validation when `--validate-each` is passed, then records a checkpoint. Failed patches are quarantined under `integration/quarantine/<task-id>/` with the failure reason and recovery recommendation.

## Artifacts

- `integration/integration-state.json`
- `integration/integration-branch.json`
- `integration/apply-plan.json`
- `integration/apply-log.jsonl`
- `integration/applied-patches.json`
- `integration/rejected-patches.json`
- `integration/validation-after-each-patch.json`
- `integration/quarantine/<task-id>/failure.json`
- `integration/rollback-plan.json`
- `integration/registry-gate.json`
- `integration/merge-readiness.json`
- `integration/taskstream-sync-preview.json`
- `integration/release-candidate.md`
- `integration/integration-summary.html`
- `integration/residual-risks.md`

## Gates

The integration gate rejects patches that are missing, fail `git apply --check`, touch files outside their owned scope, touch protected shared files without ownership, fail validation, or change command surfaces without docs/tool registry updates.

`rollback-plan.json` contains reverse patch commands for the integration worktree. It is required for `integration-state.json` validation and release candidate readiness.

`merge-readiness.json` is machine-readable. A ready decision means the integration branch is prepared, patches were applied, validation passed, registry gates passed, and no rejected patches remain. A human/operator still performs the final merge review.

## E2E

```bash
python3 scripts/factory_integration_e2e.py \
  --fixture career-consulting \
  --out workspace/runs/factory/factory-integration-e2e
```

The fixture records:

```text
AI calls used: 0
```
