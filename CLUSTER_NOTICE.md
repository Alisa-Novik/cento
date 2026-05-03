# Cluster Notice: Claude Worker Pool

Updated: 2026-05-01

Claude Code workers are the active coordination option while Codex weekly limit is reserved for interactive coordination.

Use this when there is queued work that is simple, bounded, validator-like, docs/evidence-oriented, or otherwise safe to delegate while the main agent keeps working.

## Safe Planning

Plan candidate work without mutating Redmine or starting agents:

```bash
cento agent-work dispatch-pool --limit 3
cento agent-work dispatch-pool --limit 5 --json
```

Current defaults:

- runtime: `claude-code`
- model: `claude-sonnet-4-6`
- mode: plan-only
- skips epics and non-dispatchable nodes unless explicitly overridden

## Start Workers

Only start workers when the plan looks reasonable:

```bash
cento agent-work dispatch-pool --limit 2 --execute
```

For a specific package:

```bash
cento agent-work dispatch-pool --package industrial-panels-v1 --limit 2 --execute
```

## Encouraged Work Creation

Create more small, cheap-worker-friendly tasks when a project has broad work:

- validation evidence
- docs/evidence updates
- fixture generation
- screenshot/plain snapshot capture
- board reconciliation
- small isolated parser/format checks
- review-gate checks

Keep tasks scoped and independently verifiable. Prefer `story.json`, `validation.json`, and `start-here.html` evidence for each assigned task.

## Guardrails

- `dispatch-pool` is safe by default; it does not launch anything without `--execute`.
- Use `cento agent-work runs --json --active` to see active workers.
- Cross-node Linux runs are reconciled from Mac before being called stale.
- Do not overwrite dirty node work. Sync through git or use temporary worktrees for validation.
