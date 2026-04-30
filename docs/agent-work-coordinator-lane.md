# Agent Work Coordinator Lane

The Coordinator lane keeps Cento agent work moving without turning into another implementation lane. It owns routing, story shape, board hygiene, and escalation discipline.

This contract comes from the process-scaling report at `workspace/runs/agent-work/18/process-scaling.html`: builders should build, validators should validate, Docs/Evidence should preserve proof, and coordinators should remove coordination drag.

## Lane Contract

The Coordinator lane is responsible for:

- Splitting Redmine work before dispatch when routes, APIs, screenshots, or device requirements differ.
- Combining small items when they share validation evidence and can be reviewed together.
- Creating or updating `story.json` before a worker starts.
- Keeping statuses accurate across `Queued`, `Running`, `Validating`, `Review`, `Blocked`, and `Done`.
- Assigning Builder, Validator, Docs/Evidence, and small-worker lanes based on board pressure.
- Running pool planning in dry-run mode before launching more agents.
- Detecting stale ledgers and asking for hygiene before capacity decisions.
- Escalating missing device, credential, quota, bridge, or environment access early.
- Sending notifications only on meaningful state changes.

The Coordinator lane does **not**:

- Implement product code except tiny manifest or process fixes needed to route work.
- Approve its own implementation work.
- Move a story to `Review` without a Validator pass.
- Launch unbounded workers or retry quota failures in a loop.
- Overwrite dirty work on another node.

## Required Inputs

Every coordinator cycle should start from current state, not chat memory:

```bash
cento gather-context
cento agent-work list --json
cento agent-work runs --json --active
cento agent-work recovery-plan --json
```

When capacity looks wrong, run hygiene before dispatch:

```bash
cento agent-work-hygiene
```

Before launching workers, plan first:

```bash
cento agent-pool-kick --dry-run --max-launch 3
```

## Status Rules

Use these status meanings consistently:

| Status | Coordinator meaning |
|---|---|
| `Queued` | Work is ready to assign; it should have enough scope for an agent to start. |
| `Running` | A human or tracked run is actively working it; stale or missing runs need a note. |
| `Validating` | Builder output exists and needs independent validation. |
| `Review` | Validator passed, or a human review decision is explicitly pending. |
| `Blocked` | A concrete external blocker exists, with the next unblock action named. |
| `Done` | Verified, approved, or intentionally closed with evidence. |

Blocked notes must name the blocker and the next action. Examples:

```text
Blocked: Spark quota hit. Next action: retry after reset or dispatch with explicitly approved fallback model.
Blocked: iPhone is locked. Next action: operator unlocks device and reconnects cable.
```

## Splitting Rules

Split a Redmine item when:

- It touches unrelated files or ownership boundaries.
- It needs different validation evidence, screenshots, devices, or API endpoints.
- One part can be validated while another remains blocked.
- A worker would need more than one coherent context window to finish safely.

Keep a Redmine item together when:

- The same screenshots or validation commands prove all acceptance criteria.
- The files are tightly coupled and a split would create merge friction.
- The work is small enough for one focused handoff.

## Dispatch Rules

The default pool policy is conservative:

- Dry-run first.
- Cap launches with `--max-launch`.
- Prefer Spark/Codex for cheap workers when available.
- Do not retry the same quota failure repeatedly.
- Keep at most one coordinator worker active unless explicitly scaling a coordinator backlog.
- Do not launch workers against a dirty remote checkout unless the work is isolated from those files.

Useful commands:

```bash
cento agent-pool-kick --dry-run --max-launch 3
cento agent-pool-kick --max-launch 1 --coordinator-target 1 --builder-target 0 --validator-target 0 --small-target 0
cento agent-work dispatch-pool --limit 3 --json
```

If Spark is blocked, the coordinator should record the blocker instead of silently switching models. Model fallback must be explicit:

```bash
cento agent-pool-kick --max-launch 1 --model gpt-5.4-mini
```

## Notification Rules

Notify only on state changes that affect the operator:

- Work starts on a high-priority item.
- Human input is required.
- A device, credential, quota, bridge, or relay blocker appears.
- A story reaches `Review` or `Done`.
- Validation fails with a clear next action.

Avoid progress pings that do not change operator action.

## Coordinator Cycle

A normal coordinator cycle:

1. Refresh context and board state.
2. Run recovery-plan and hygiene if runs look stale.
3. Close or route `Review` noise before launching more work.
4. Pick the largest blocked package and create the smallest unblock task.
5. Create or update `story.json` for queued work.
6. Run pool dry-run.
7. Launch a capped batch only when capacity and blockers are understood.
8. Leave Redmine notes that name the action taken and evidence path.

## Required Outputs

For coordinator-owned stories, produce:

| File | Purpose |
|---|---|
| `workspace/runs/agent-work/<id>/story.json` | Shared scope and evidence contract. |
| `workspace/runs/agent-work/<id>/builder-report.md` | What coordination decision changed and why. |
| `workspace/runs/agent-work/<id>/start-here.html` | Manager-facing evidence hub when generated from story manifest. |

## Review Handoff

Coordinator handoff notes should include:

```text
Delivered:
- Story split/routing/status hygiene completed.

Validation:
- Commands run and result.

Evidence:
- story.json path
- builder-report path
- generated hub path

Residual risk:
- Remaining blockers, if any, or "None".
```

