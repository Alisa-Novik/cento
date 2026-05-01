# Cento Factory

Cento Factory is the plan-only layer above Taskstream for turning one high-level request into durable artifacts before any worker dispatch happens.

The first slice is `factory-planning-v1`. It does not launch agents, create live Taskstream issues, apply patches, or merge code. It creates a validated plan and the manifests future dispatch must use.

## Workflow

```bash
cento factory intake "develop me a career consulting module" \
  --dry-run \
  --out workspace/runs/factory/factory-planning-e2e

cento factory plan workspace/runs/factory/factory-planning-e2e --no-model
cento factory materialize workspace/runs/factory/factory-planning-e2e
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
- `start-here.html`
- `implementation-map.html`
- `summary.md`
- `release-notes.md`
- `validation-summary.json`, when the E2E runner is used

## Guardrails

`factory-plan.json` is validated before materialization. The validator checks schema version, package metadata, budget fields, task ownership, expected outputs, validation commands, dependency references, dependency cycles, and owned-path overlaps.

Generated story manifests are validated with `scripts/story_manifest.py`. Generated validation manifests are validated with `scripts/validation_manifest.py` and must preserve no-model coverage.

Live dispatch is intentionally absent from this slice. `create-issues --dry-run` only writes `create-issues-preview.json` so operators can inspect the intended Taskstream shape before any future live creation path exists.

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
