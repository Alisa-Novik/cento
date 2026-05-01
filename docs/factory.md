# Cento Factory

Cento Factory is the layer above Taskstream for turning one high-level request into durable artifacts, queue state, owned-path leases, worktree metadata, prompt bundles, patch collection, integration dry-runs, safe factory integration branches, release candidates, and release evidence before any worker output can reach a human merge decision.

The delivered slice defaults to no-model dry-runs. It does not launch agents by default. Live Taskstream issue creation requires `--apply`, and AI dispatch remains gated behind explicit operator action.

## Workflow

```bash
cento factory intake "develop me a career consulting module" \
  --dry-run \
  --out workspace/runs/factory/factory-planning-e2e

cento factory plan workspace/runs/factory/factory-planning-e2e --no-model
cento factory materialize workspace/runs/factory/factory-planning-e2e
cento factory queue workspace/runs/factory/factory-planning-e2e
cento factory preflight workspace/runs/factory/factory-planning-e2e --json
cento factory lease workspace/runs/factory/factory-planning-e2e --task crm-schema-extension --dry-run
cento factory dispatch workspace/runs/factory/factory-planning-e2e --lane builder --max 4 --dry-run
cento factory collect workspace/runs/factory/factory-planning-e2e
cento factory validate workspace/runs/factory/factory-planning-e2e
cento factory integrate workspace/runs/factory/factory-planning-e2e --dry-run
cento factory integrate factory-integration-e2e --plan
cento factory integrate factory-integration-e2e --prepare-branch --branch factory/factory-integration-e2e/integration
cento factory integrate factory-integration-e2e --apply --validate-each --limit 3
cento factory validate-integrated factory-integration-e2e
cento factory release-candidate factory-integration-e2e
cento factory sync-taskstream factory-integration-e2e --dry-run
cento factory release workspace/runs/factory/factory-planning-e2e --json
cento factory render-hub workspace/runs/factory/factory-planning-e2e
cento factory create-issues workspace/runs/factory/factory-planning-e2e --dry-run
cento factory autopilot factory-autopilot-runtime-e2e --dry-run --cycles 5
cento factory autopilot-status factory-autopilot-runtime-e2e --json
cento factory autopilot-render factory-autopilot-runtime-e2e
```

## Artifacts

Each run writes under `workspace/runs/factory/<run-id>/`:

- `request.md`
- `intake.json`
- `constraints.json`
- `context-pack.json`
- `factory-plan.json`
- `tasks/<task-id>/story.json`
- `tasks/<task-id>/validation.json`
- `queue/queue.json`
- `queue/events.jsonl`
- `queue/leases.json`
- `queue/backpressure.json`
- `queue/queued.jsonl`
- `queue/waiting.jsonl`
- `queue/leased.jsonl`
- `queue/owned-paths.json`
- `create-issues-preview.json`
- `tasks/<task-id>/worker-prompt.md`
- `tasks/<task-id>/prompt-record.json`
- `tasks/<task-id>/dispatch.json`
- `tasks/<task-id>/worktree.json`
- `patches/<task-id>/patch.json`
- `patches/<task-id>/patch.diff`
- `dispatch-plan.json`
- `integration/integration-plan.json`
- `integration/dry-run-summary.md`
- `integration/integration-state.json`
- `integration/integration-branch.json`
- `integration/apply-plan.json`
- `integration/apply-log.jsonl`
- `integration/applied-patches.json`
- `integration/rejected-patches.json`
- `integration/validation-after-each-patch.json`
- `integration/quarantine/<task-id>/failure.json`
- `integration/conflict-report.json`
- `integration/rollback-plan.json`
- `integration/release-gates.json`
- `integration/registry-gate.json`
- `integration/merge-readiness.json`
- `integration/taskstream-sync-preview.json`
- `integration/release-candidate.md`
- `integration/integration-summary.html`
- `integration/residual-risks.md`
- `evidence/validation-summary.json`
- `start-here.html`
- `implementation-map.html`
- `release-packet.md`
- `summary.md`
- `release-notes.md`
- `validation-summary.json`, when the E2E runner is used
- `delivery-status.json`
- `project-delivery.md`
- `autopilot/factory-state.json`
- `autopilot/policy.json`
- `autopilot/cycles/<cycle>/scan.json`
- `autopilot/cycles/<cycle>/decision.json`
- `autopilot/cycles/<cycle>/action.json`
- `autopilot/cycles/<cycle>/result.json`
- `autopilot/cycles/<cycle>/summary.md`
- `autopilot/metrics.json`
- `autopilot/stop-reason.json`
- `autopilot/autopilot-summary.md`

## Guardrails

`factory-plan.json` is validated before materialization. The validator checks schema version, package metadata, budget fields, task ownership, expected outputs, validation commands, dependency references, dependency cycles, and owned-path overlaps.

Generated story manifests are validated with `scripts/story_manifest.py`. Generated validation manifests are validated with `scripts/validation_manifest.py` and must preserve no-model coverage.

`create-issues --dry-run` writes `create-issues-preview.json` so operators can inspect the intended Taskstream shape. `create-issues --apply` creates an Agent Epic plus child Agent Tasks from generated manifests and records `taskstream-issues.json`.

`lease` simulates or acquires an owned-path lease. Active leases reject overlapping owned paths, write `tasks/<task-id>/worktree.json`, and keep live state in `queue/leases.json`.

`dispatch --dry-run` writes a deterministic dispatch plan, lease simulations, worktree metadata, per-task `dispatch.json`, `worker-prompt.md`, and `prompt-record.json`. It runs Agent Manager preflight and records skipped tasks with reasons before any live dispatch can happen.

`collect` creates patch bundle records under `patches/<task-id>/`. A task may have a collected patch or an explicitly missing dry-run patch bundle; both states are visible to validation and integration.

`integrate --dry-run` writes an integration gate plan in dependency order. It checks patch presence, owned paths, protected shared files, `git apply --check` when a patch exists, docs/tool registry alignment, conflicts, validation results, and rollback metadata.

`integrate --plan`, `--prepare-branch`, and `--apply --validate-each` are the factory integration Safe Integrator commands. They create an isolated integration worktree, apply candidate patch bundles one at a time, run validation after each patch, quarantine failures, write `rollback-plan.json`, update `merge-readiness.json`, and render `release-candidate.md`. They do not merge to main.

`sync-taskstream --dry-run` writes `integration/taskstream-sync-preview.json`. It previews Review or Blocked transitions from integration results but does not mark Factory tasks Done.

`validate` writes `evidence/validation-summary.json` and root `validation-summary.json` with T0/T1/T2 ladder status, no-model usage, residual risks, and evidence links.

`release` writes `delivery-status.json`, `project-delivery.md`, and `release-packet.md`. A delivered run requires intake, plan, materialization, queue, dispatch plan, integration dry-run, evidence hub, implementation map, and validation summary.

`autopilot --dry-run --cycles N` runs a deterministic control loop over an existing Factory run. Each cycle scans durable state, chooses exactly one safe action, runs one bounded dry-run command or hold/stop action, writes cycle evidence, updates `autopilot/factory-state.json`, and refreshes metrics. Storage pressure gates future live fanout but does not block dry-run cycles.

## E2E

```bash
python3 scripts/factory_e2e.py \
  --fixture career-consulting \
  --out workspace/runs/factory/factory-planning-e2e

python3 scripts/factory_dispatch_e2e.py \
  --fixture career-consulting \
  --out workspace/runs/factory/factory-dispatch-e2e

python3 scripts/factory_integration_e2e.py \
  --fixture career-consulting \
  --out workspace/runs/factory/factory-integration-e2e

python3 scripts/factory_autopilot_runtime_e2e.py \
  --fixture complex-project \
  --tasks 50 \
  --out workspace/runs/factory/factory-autopilot-runtime-e2e
```

The E2E records mandatory timing stats per step and total stats in `validation-summary.json`. The expected AI usage for this slice is always:

```text
ai_calls_used: 0
estimated_ai_cost_usd: 0
```

## Research Map

`implementation-map.html` is a static stub for the research/spec-to-implementation control surface. The accompanying `research-map.json` can be validated with:

```bash
python3 scripts/research_map.py validate workspace/runs/factory/factory-planning-e2e/research-map.json
```

Statuses are `implemented`, `partial`, `not_implemented`, `deferred_deliberately`, `not_applicable`, and `existing_capability`.
