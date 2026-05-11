# Cluster Notice: Claude Worker Pool

Updated: 2026-05-05

Claude Code workers are the active coordination option while Codex weekly limit is reserved for interactive coordination.

Use this when there is queued work that is simple, bounded, validator-like, docs/evidence-oriented, or otherwise safe to delegate while the main agent keeps working.

## Safe Planning

Plan candidate work without mutating Redmine or starting agents:

```bash
cento agent-pool-kick --dry-run
cento agent-pool-kick --dry-run --max-launch 5
```

Current defaults:

- runtime: `claude-code`
- model: `claude-sonnet-4-6`
- mode: plan-only (`--dry-run`)
- skips epics and non-dispatchable nodes unless explicitly overridden

## Start Workers

Only start workers when the plan looks reasonable:

```bash
cento agent-pool-kick --max-launch 2
```

For a specific package:

```bash
cento agent-pool-kick --package industrial-panels-v1 --max-launch 2
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

- `agent-pool-kick` is safe by default (`--dry-run`); it does not launch anything unless `--dry-run` is omitted.
- Use `cento agent-work runs --json --active` to see active workers.
- Cross-node Linux runs are reconciled from Mac before being called stale.
- Do not overwrite dirty node work. Sync through git or use temporary worktrees for validation.
