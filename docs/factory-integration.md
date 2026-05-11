# Factory Integration

Factory integration is the Safe Integrator layer for Cento Factory. It turns collected patch bundles into an isolated release candidate. Automatic main merge is available only through the explicit `factory merge --auto-merge-main` gate.

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
cento factory validate-fanout factory-integration-e2e --max-parallel 32 --json
cento factory release-candidate factory-integration-e2e
cento factory merge factory-integration-e2e --auto-merge-main --push --json
cento factory sync-taskstream factory-integration-e2e --dry-run
```

## Policy

Safe Integrator creates an integration worktree under `workspace/factory-integration-worktrees/<run-id>/` and records the branch in `integration/integration-branch.json`. Patches are applied there one at a time. Main is not touched unless the separate auto-merge gate passes, and Taskstream is not moved to Done.

`apply-plan.json` orders candidate patches by dependency and risk. `validate-fanout` runs cacheable deterministic checks in parallel before apply. The applier runs `git apply --check`, applies a patch, runs per-patch validation when `--validate-each` is passed, then records a checkpoint. Failed patches are quarantined under `integration/quarantine/<task-id>/` with the failure reason and recovery recommendation.

## Artifacts

- `integration/integration-state.json`
- `integration/integration-branch.json`
- `integration/apply-plan.json`
- `integration/apply-log.jsonl`
- `integration/applied-patches.json`
- `integration/rejected-patches.json`
- `integration/validation-after-each-patch.json`
- `integration/validation-fanout.json`
- `integration/validation-cache/<cache-key>.json`
- `integration/quarantine/<task-id>/failure.json`
- `integration/rollback-plan.json`
- `integration/registry-gate.json`
- `integration/merge-readiness.json`
- `integration/taskstream-sync-preview.json`
- `integration/release-candidate.md`
- `integration/merge-receipt.json`
- `integration/push-receipt.json`
- `integration/integration-summary.html`
- `integration/residual-risks.md`

## Gates

The integration gate rejects patches that are missing, fail `git apply --check`, touch files outside their owned scope, touch protected shared files without ownership, fail validation, or change command surfaces without docs/tool registry updates.

`rollback-plan.json` contains reverse patch commands for the integration worktree. It is required for `integration-state.json` validation and release candidate readiness.

`merge-readiness.json` is machine-readable. `ready_for_human_merge_review` means the integration branch is prepared, patches were applied, validation passed, registry gates passed, and no rejected patches remain. `ready_for_auto_merge` is stricter and is produced only for the auto-merge path after rollback and fanout evidence are present.

`merge --auto-merge-main` blocks unless main is clean, the current branch matches the target branch, release and rollback evidence exist, validation fanout passes, integrated validation approves, and pre/post validation commands pass. `--push` writes `push-receipt.json` only after local merge and post-merge validation.

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
