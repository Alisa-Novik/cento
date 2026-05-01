# Factory Autopilot

Factory Autopilot Runtime v1 is a deterministic dry-run control loop for complex Factory runs. It does not launch live workers, apply patches to main, prune storage, upload artifacts, or send notifications.

## Commands

```bash
cento factory autopilot RUN_ID --dry-run --cycles 5
cento factory autopilot-status RUN_ID --json
cento factory autopilot-render RUN_ID
```

## Control Loop

Each cycle writes durable evidence under `workspace/runs/factory/<run-id>/autopilot/cycles/<cycle>/`:

- `scan.json`
- `decision.json`
- `action.json`
- `result.json`
- `summary.md`

The runtime also writes `autopilot/factory-state.json`, `autopilot/policy.json`, `autopilot/metrics.json`, `autopilot/stop-reason.json`, and `autopilot/autopilot-summary.md`.

## Policy

The v1 priority order is:

1. Missing factory state: materialize or stop with a clear reason.
2. Invalid or missing queue: queue.
3. Unvalidated patch backlog: validate before integration.
4. Validation backlog: validate before more dispatch.
5. Validated patch or integration backlog: integrate dry-run before more dispatch.
6. Storage pressure: hold live fanout, but continue dry-run cycles.
7. Runnable tasks and clear downstream: dispatch exactly one dry-run task.
8. Nothing runnable: render summary or stop.

The primary metric is validated integrated output per dollar. Because v1 is dry-run only, metrics report simulated validated integrated progress, blocked reasons, readiness for real execution, cycle decisions, action-effect deltas, and evidence completeness.

## Fixture

```bash
python3 scripts/factory_autopilot_runtime_e2e.py \
  --fixture complex-project \
  --tasks 50 \
  --out workspace/runs/factory/factory-autopilot-runtime-e2e
```

The fixture seeds at least 50 tasks across coordinator, builder, validator, docs-evidence, and integration-style work. It includes dependencies, owned paths, intentional patch conflicts, a validation backlog, an integration backlog, docs/registry work, storage pressure input, and cost budget input.
