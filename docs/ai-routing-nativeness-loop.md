# AI Routing Nativeness Loop

`cento walk-autopilot routing` is the lightweight scheduled loop for improving Cento routing and Cento-native behavior without letting cron implement code.

The loop exists because routing quality depends on several local signals that drift over time: registered command surfaces, human Docs coverage, Agent Work health, local Codex observability, skill usage, and whether the installed `cento-native` skill matches the repo copy.

## Operating Contract

- Cadence: every 4 hours through a marked crontab block.
- Authority: report first, then create or update one bounded Agent Work task when a change is actionable.
- Mutations from cron: reports, metrics, latest artifact mirror, and Agent Work note/task only.
- Prohibited from cron: code implementation, live ProReq expansion, live worker dispatch, destructive cleanup, or raw log capture.
- Privacy boundary: counts-only. Prompt text, raw logs, command stdout payloads, and Agent Work issue subjects are not persisted.

## Commands

```bash
cento walk-autopilot routing run --json
cento walk-autopilot routing status --json
cento walk-autopilot routing install-cron --every-hours 4 --json
cento walk-autopilot routing uninstall-cron --json
```

Use this for local validation without creating or updating Agent Work:

```bash
cento walk-autopilot routing run --json --no-agent-work
```

## Artifacts

Routing artifacts are written under:

```text
workspace/runs/walk-autopilot/routing-native/<timestamp>/
workspace/runs/walk-autopilot/routing-native/latest/
```

The stable artifact set is:

- `raw_counts.json`
- `decision.json`
- `decision_report.md`
- `agent_work_request.json`
- `agent-work-story.json`
- `next_iteration.md`
- `metrics.jsonl`

`latest/` is a copied mirror of the newest run so operators and agents have a stable handoff path.

## Signals

The current collector records aggregate counts and status fields for:

- Git dirty count and status-code counts.
- Routing cron marker status and schedule.
- Tool registry count and Walk Autopilot routing command coverage.
- CLI docs and human Docs coverage.
- Latest Walk Autopilot status summary.
- Nightly self-improvement status, validation status, and promotion recommendation.
- Agent Work run status, health, role, runtime, stale, running, failed, and demo/test inventory counts.
- Codex local SQLite log level counts and top targets without reading log bodies.
- Skill mention counts for known Codex skills.
- Installed versus repo `cento-native` skill file hashes.

## Decision Rules

The loop creates decisions from counts, not from raw text.

High-priority decisions:

- `repair_self_improve_before_heavy_cron`: the heavier nightly self-improvement loop is unknown, degraded, failed, incomplete, or recommends repairing the pipeline first.
- `sync_cento_native_skill`: the installed `cento-native` skill and repo copy differ or a watched file is missing.
- `register_routing_commands`: the Walk Autopilot tool registry does not expose the routing command surface.
- `dirty_worktree_changed_during_loop`: the dirty count changed during collection, so Agent Work mutation is blocked.

Medium-priority decisions:

- `install_routing_cron`: the marked four-hour routing cron block is missing.
- `write_human_routing_docs`: the human-facing routing loop page is missing.
- `agent_work_hygiene_cleanup`: stale or demo/test Agent Work inventory needs bounded cleanup.
- `codex_error_observability`: local Codex ERROR counts are high enough to justify a follow-up.

Low-priority decisions can be recorded without creating Agent Work when they should trend for another iteration first.

## Agent Work Handoff

When actionable decisions exist, `routing run` writes `agent-work-story.json` and then creates or updates one Agent Work task in the `cento-routing-nativeness` package.

The task owns follow-up coordination, not direct cron execution. It should repair the named issue, validate deterministically, and leave evidence in the run bundle. If a previous routing task exists and is still open, the loop updates it with a note pointing at the newest `decision_report.md`.

Agent Work is skipped when:

- `--no-agent-work` is passed.
- No actionable decision exists.
- The Git dirty count changes during collection.
- Agent Work create/update fails; the local `agent_work_request.json` records the failed command metadata without raw command output.

## Cron Block

The installed block is marked so it can be replaced safely:

```text
# BEGIN CENTO ROUTING NATIVE LOOP
0 */4 * * * ...
# END CENTO ROUTING NATIVE LOOP
```

The cron command uses `flock` with:

```text
~/.local/state/cento/routing-native-loop.lock
```

Cron logs append to:

```text
workspace/logs/routing-native-loop.log
```

## Next Iteration

After installation, let the loop collect at least two samples before increasing automation. The next iteration should compare action id stability, severity movement, Agent Work handoff health, and whether any collector failed to change decisions.

Add a new collector only when all of these are true:

- It can be represented as aggregate counts or hashes.
- It changes a concrete routing decision.
- It does not persist prompt text, raw logs, stdout payloads, secrets, or issue bodies.
- It has a deterministic test.

Heavy ProReq automation and live worker dispatch stay outside this cron path unless an operator explicitly starts them.
