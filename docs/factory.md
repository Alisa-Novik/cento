# Cento Factory

Cento Factory is the layer above Taskstream for turning one high-level request into durable artifacts, queue state, dispatch plans, integration gates, and release evidence before any worker can mutate the repo.

The delivered slice defaults to no-model dry-runs. It does not launch agents by default. Live Taskstream issue creation requires `--apply`, and AI dispatch remains gated behind explicit operator action.

## Workflow

```bash
cento factory intake "develop me a career consulting module" \
  --dry-run \
  --out workspace/runs/factory/factory-planning-e2e

cento factory plan workspace/runs/factory/factory-planning-e2e --no-model
cento factory materialize workspace/runs/factory/factory-planning-e2e
cento factory queue workspace/runs/factory/factory-planning-e2e
cento factory dispatch workspace/runs/factory/factory-planning-e2e --lane builder --max 4 --include-waiting
cento factory integrate workspace/runs/factory/factory-planning-e2e --dry-run
cento factory release workspace/runs/factory/factory-planning-e2e --json
cento factory render-hub workspace/runs/factory/factory-planning-e2e
cento factory create-issues workspace/runs/factory/factory-planning-e2e --dry-run
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
- `queue/state.json`
- `queue/queued.jsonl`
- `queue/waiting.jsonl`
- `queue/leased.jsonl`
- `queue/owned-paths.json`
- `create-issues-preview.json`
- `dispatch-plan.json`
- `integration-plan.json`
- `start-here.html`
- `implementation-map.html`
- `summary.md`
- `release-notes.md`
- `validation-summary.json`, when the E2E runner is used
- `delivery-status.json`
- `project-delivery.md`

## Guardrails

`factory-plan.json` is validated before materialization. The validator checks schema version, package metadata, budget fields, task ownership, expected outputs, validation commands, dependency references, dependency cycles, and owned-path overlaps.

Generated story manifests are validated with `scripts/story_manifest.py`. Generated validation manifests are validated with `scripts/validation_manifest.py` and must preserve no-model coverage.

`create-issues --dry-run` writes `create-issues-preview.json` so operators can inspect the intended Taskstream shape. `create-issues --apply` creates an Agent Epic plus child Agent Tasks from generated manifests and records `taskstream-issues.json`.

`dispatch` writes a deterministic dispatch plan and lease records. It runs Agent Manager preflight and records whether each task has a Taskstream issue before any live dispatch can happen.

`integrate --dry-run` writes an integration gate plan in dependency order. Patches are only accepted through the patch queue path and must keep validation evidence.

`release` writes `delivery-status.json` and `project-delivery.md`. A delivered run requires intake, plan, materialization, queue, dispatch plan, integration plan, evidence hub, implementation map, and validation summary.

## E2E

```bash
python3 scripts/factory_e2e.py \
  --fixture career-consulting \
  --out workspace/runs/factory/factory-planning-e2e
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
