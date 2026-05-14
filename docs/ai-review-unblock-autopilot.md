# AI Review/Unblock Autopilot

`cento walk-autopilot review-unblock` is the evidence-gated Agent Work cleanup stage for Review, Blocked, Validating, and stale worker states.

The stage exists because the worker pool can finish implementation work while the board still contains review-ready tasks, stale validator runs, blocked internal artifact gaps, or historical demo/test inventory. Review/Unblock turns that backlog into explicit decisions every loop instead of leaving the live worker pool with nothing launchable.

## Operating Contract

- Authority: report by default; bounded apply only in aggressive mode.
- Default in `walk-autopilot run`: report mode.
- Default when `--live-workers` is enabled: aggressive mode.
- Closure rule: Review items close only through `agent-work review-drain`, which requires validation pass plus evidence.
- Safety rule: if the Git dirty count changes during snapshot collection, mutating actions are blocked.
- Escalation rule: ambiguous, credential/device/LAN, missing-manifest, active-run, or failed snapshot states become `operator_needed`.

## Commands

```bash
cento walk-autopilot review-unblock run --mode report --json
cento walk-autopilot review-unblock run --mode aggressive --json
cento walk-autopilot review-unblock status --json
cento walk-autopilot run --review-unblock-mode report
cento walk-autopilot run --live-workers --review-unblock-mode aggressive
cento walk-autopilot run --no-review-unblock
```

Use report mode when validating decision quality or inspecting the current board. Use aggressive mode only when the operator wants the stage to mutate Agent Work within its caps.

## Artifacts

Standalone runs write to:

```text
workspace/runs/walk-autopilot/review-unblock/<timestamp>/
workspace/runs/walk-autopilot/review-unblock/latest/
```

Loop-integrated runs write to:

```text
workspace/runs/walk-autopilot/<run-id>/review-unblock/loop-0001/
```

The stable artifact set is:

- `snapshot.json`
- `snapshot/recovery-plan.json`
- `snapshot/agent-work-list.json`
- `snapshot/agent-work-runs.json`
- `snapshot/commands.json`
- `decision.json`
- `decision_report.md`
- `actions.jsonl`
- `results.json`
- `actions/<index>-<type>/action.json`

Repair-task actions also materialize a draft story manifest under the action directory before calling `agent-work create`.

## Decisions

The stage can choose these action types:

- `close_done`: drain a Review package through `agent-work review-drain --apply`.
- `validate_local`: run `agent-work validate-run` for a Validating issue that has canonical story and validation manifests and no active run.
- `dispatch_validator`: launch a bounded validator when local validation capacity is exhausted and the issue has valid manifests.
- `requeue_stale_dispatch`: move a stale Blocked, Running, or Validating issue back to Queued with a precise note.
- `repair_task`: create a narrow builder task for an internal artifact gap.
- `close_demo_test`: close demo/test inventory identified by Agent Work metadata when no active run exists.
- `archive_stale_historical`: reconcile or archive a stale run ledger for a Done or closed issue.
- `operator_needed`: stop for real ambiguity instead of guessing.

## Caps

Each run is capped so a bad rule cannot churn the whole board:

- Close done: 20 packages.
- Local validations: 4 issues.
- Validator dispatches: 3 issues.
- Stale requeues: 6 issues.
- Repair tasks: 3 issues.
- Demo/test closures: 10 issues.
- Historical stale ledger archives: 6 runs.

Caps should increase only after two consecutive runs show stable action types and no unexpected failures.

## Integration Point

Walk Autopilot runs Review/Unblock after `agent-work-hygiene` and before `agent-pool-kick --dry-run`.

That order matters: hygiene refreshes the run/process picture first, Review/Unblock removes or repairs stale board states, and the worker pool dry-run sees a fresher queue immediately after.

## Review/Unblock Versus Recovery Plan

`agent-work recovery-plan` remains the lower-level board analysis tool. Review/Unblock uses it as one snapshot source, then adds:

- canonical manifest checks,
- active-run guards,
- action caps,
- apply/report mode,
- loop metrics,
- per-action transcripts,
- latest-run status.

Use `recovery-plan` for manual diagnosis. Use Review/Unblock when the walk autopilot needs to keep the board moving continuously.

## Next Iteration

The next iteration should compare consecutive `decision.json` files for action stability. Repeated `operator_needed` reasons are the best candidates for new deterministic rules, but only when the rule can be proven from structured Agent Work state, manifests, or run ledgers.

Do not add raw prompt, stdout, or log-body persistence to this stage. If a new signal is needed, store counts, hashes, paths, and command metadata instead of raw content whenever possible.
