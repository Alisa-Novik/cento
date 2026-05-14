# Parallel Integration Train

`cento parallel-delivery train` is the dry-run bridge between aggressive parallel Workset planning and safe sequential integration.

The train exists so Cento can prepare for wave-10 delivery without letting workers or integrations mutate the repository in the first implementation. It copies a Workset into a run bundle, runs the existing Workset checker, builds a dependency-aware integration queue, can either simulate worker readiness or invoke the existing parallel Workset executor, and records dry-run integration receipts.

## Commands

```bash
cento parallel-delivery train plan --workset tests/fixtures/cento_workset/workset.valid.json --max-parallel 10 --json
cento parallel-delivery train run RUN_ID --simulate --json
cento parallel-delivery train run RUN_ID --workset-execute --runtime fixture --validation smoke --allow-dirty-owned --json
cento parallel-delivery train promote RUN_ID --dry-run --json
cento parallel-delivery train e2e --workset tests/fixtures/cento_workset/workset.execute.fixture.json --max-parallel 3 --runtime fixture --allow-dirty-owned --dry-run --json
cento parallel-delivery train integrate RUN_ID --dry-run --json
cento parallel-delivery train status RUN_ID --json
cento parallel-delivery train validate RUN_ID --json
```

The `run` command requires either `--simulate` or `--workset-execute`. `--workset-execute` routes through `cento workset execute` with the copied Workset and records the Workset command, result, and receipt into the train run. The train wrapper never passes `--apply`; repository mutation stays outside this MVP. `--runtime api-openai` is available only when explicitly requested and requires both `--budget-usd` and `--max-budget-usd`.

The `promote` command is the missing e2e bridge that previously made the flow feel circular. It reads a completed train Workset receipt, creates a Factory run, converts accepted Workset patch bundles into Factory patch collection, builds the Factory apply plan, and writes a promotion decision. `--dry-run` is the default behavior. `--apply` is explicit and applies only inside a Factory integration worktree branch before rendering a release candidate.

The `e2e` command runs plan, Workset execution, train validation, and promotion in one call.

The `integrate` command is still for the simulation path and requires `--dry-run`.

## Artifacts

Train runs write under:

```text
workspace/runs/parallel-delivery/train/<run-id>/
```

The stable artifact set is:

- `train_manifest.json`
- `workset.json`
- `workset_check.json`
- `integration_queue.json`
- `train_receipt.json`
- `workset_execute_command.json`
- `workset_execute_result.json`
- `promotion_manifest.json`
- `promotion_decision.json`
- `promotion_decision.md`
- `factory_handoff.json`
- `events.ndjson`
- `decision_report.md`
- `workers/<worker-id>/worker_receipt.json`
- `integration/<task-id>/integration_receipt.json`
- `validation_summary.json`

## Behavior

- Worksets are checked through `cento workset check`; the train does not duplicate the lower-level Workset contract.
- Shards keep `task_id`, `worker_id`, `write_paths`, `depends_on`, blockers, and integration order.
- Overlapping, glob, absolute, missing, or dependency-broken write paths are blocked before worker simulation.
- Dependency order is stable and sequential for integration.
- Simulated workers move ready shards to `ready_for_integration`.
- Dry-run integration moves ready shards to `integration_planned`.
- Workset execution runs `cento workset execute WORKSET --integrate sequential --json` and stores the Workset receipt path on each queue item.
- Workset task statuses of `accepted`, `applied`, or `completed` become train queue status `workset_integrated`.
- Promotion hands accepted Workset patch bundles to Factory/Safe Integrator instead of inventing a second integration authority.
- Promotion dry-run stops at Factory patch collection plus apply-plan generation.
- Promotion apply mode uses Factory integration worktree behavior and does not merge to main.
- Train planning and Workset execution keep `apply` false; promotion apply is a separate explicit integration-worktree mode.

## Current State

Already implemented:

- Train planning and dependency-aware queue generation.
- Simulated train worker readiness.
- Real Workset execution via `train run --workset-execute`.
- Train validation for Workset execution receipts.
- Factory/Safe Integrator promotion via `train promote`.
- One-command fixture e2e via `train e2e`.

Still intentionally out of scope:

- Automatic merge to main.
- Uncapped live API fanout.
- Bypassing Factory release-candidate gates.
