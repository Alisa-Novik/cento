# Cento Agent Work

Readable HTML guide: [`docs/agent-work.html`](./agent-work.html).

`cento agent-work` is the Taskstream command surface inside the broader Cento Console. It creates, splits, dispatches, validates, and reviews tasks across the Mac/Linux cluster.

## Cento Web App Direction

The web app is the broader Cento Console, not a single-purpose task board. Its primary header should expose these top-level areas early:

- `Taskstream`: issues, review queue, dispatch, validation evidence, and agent-work lifecycle.
- `Cluster`: Mac/Linux/iPhone node health, bridge mesh, Agent Processes, worker pools, and runtime status.
- `Consulting`: CRM, career intake, funnel, and client deliverable workflows.
- `Docs`: operating guides, tasking contracts, validation lanes, runbooks, and generated tool references.

Taskstream remains the tasking system inside that console. Issues and review are nested under Taskstream rather than being the whole product shell.

## What It Creates

- Taskstream project: `cento-agent-work`
- Trackers: `Agent Epic`, `Agent Task`
- Statuses: `Queued`, `Running`, `Validating`, `Review`, `Blocked`, `Done`
- Custom fields: `Agent Node`, `Agent Owner`, `Agent State`, `Cento Work Package`, `TUI Summary`, `Cluster Dispatch`
- Local run bundles: `workspace/runs/agent-work/<run-id>/`

This is the operating model:

1. You create or split work into Taskstream issues.
2. Each task gets a node, agent owner, package, status, and work instructions.
3. Agents claim tasks, update status, and leave notes in Taskstream.
4. You inspect Taskstream, `cento agent-work list`, and `cento cluster activity` to see what is assigned and what is actually running.

## Deterministic-First Validation

No-model validation in Cento means deterministic-first validation is the default. Builders should leave behind durable artifacts that a validator can check mechanically, and validators should prefer files, commands, URLs, screenshots, and generated reports over model judgment when deciding pass or fail.

The story manifest's `validation` block is the source of truth for that routing decision: `mode`, `risk`, `no_model_eligible`, `escalation_triggers`, and `commands` tell the validator whether the work stays no-model or must escalate.

Use `preflight` before dispatch, then the existing `validate-run` and `validate` commands for the rollout. The no-model path is stricter because it requires a story manifest, validation manifest, 95%+ automation coverage, and no unresolved manual-review items before work leaves planning.

```bash
cento agent-work preflight workspace/runs/agent-work/ISSUE_ID/story.json \
  --validation-manifest workspace/runs/agent-work/ISSUE_ID/validation.json

cento agent-work validate-run ISSUE_ID \
  --manifest workspace/runs/agent-work/ISSUE_ID/validation.json \
  --story-manifest workspace/runs/agent-work/ISSUE_ID/story.json

cento agent-work validate ISSUE_ID \
  --result pass \
  --evidence workspace/runs/agent-work/ISSUE_ID/validation-report.md \
  --note "..."
```

Coordinator rule of thumb:

- Keep the acceptance contract explicit enough to validate from durable evidence.
- Split or block work that would require an unannounced model judge.
- Route subjective or device-bound judgment into a human handoff instead of burying it in validation.
- `agent-work dispatch` runs preflight by default and blocks AI launch when the story or validation manifest is missing, coverage is below 95%, or manual review is unresolved. Use `--skip-preflight` only for explicit legacy/manual dispatch.
- If a future CLI command is genuinely required, register it in `data/tools.json` and regenerate `docs/tool-index.md` and `docs/platform-support.md`.

## Bootstrap

Run this once from the Mac or Linux node:

```bash
cento agent-work bootstrap
```

It is safe to run again. The command creates any missing Taskstream schema and workflow metadata.

## Create One Task

```bash
cento agent-work create \
  --title "Improve mission control pane" \
  --manifest workspace/runs/agent-work/drafts/mission-control-story.json \
  --description "Add a compact running-agent summary and link it to cluster activity." \
  --node linux \
  --agent codex \
  --package mission-control
```

`--manifest` is mandatory. The coordinator/AI caller must interpret the feature request and generate a valid draft `story.json` before creating the task. Use `issue.id: 0` in the draft; `agent-work create` writes the canonical copy to `workspace/runs/agent-work/<issue-id>/story.json` after Taskstream assigns the issue ID.

List active work:

```bash
cento agent-work list
```

Machine-readable task JSON from `cento agent-work list --json` and `cento agent-work show --json` includes `tui_summary`, a short one- or two-word label intended for constrained terminal dashboards. Existing issues get a generated fallback from their subject when the custom field is not populated.

Show a task:

```bash
cento agent-work show 123
```

## Split Work Across The Cluster

Use `split` when you want one package of work spread across nodes:

```bash
cento agent-work split \
  --title "Mission control MVP" \
  --goal "Track what agents are doing as first-class Taskstream work." \
  --nodes linux,macos \
  --task "Create Taskstream task model and CLI" \
  --task "Add Mac mission-control tile view" \
  --task "Document agent operating procedure"
```

That creates one `Agent Epic` plus one `Agent Task` per `--task`. Node assignments rotate through `--nodes`.

## Agent Lifecycle

Agents should keep the issue current:

```bash
cento agent-work claim 123 --node linux --agent codex
cento agent-work update 123 --status running --note "Found the dashboard entry point."
cento agent-work update 123 --status review --note "Implemented; make check passes."
cento agent-work update 123 --status blocked --note "Blocked waiting for required access."
cento agent-work update 123 --status done --note "Verified and closed."
```

Use `Review` for code that is ready for human inspection. Use `Done` only after verification.

## Agent Lanes

Cento work scales by separating ownership:

- Builder lane: implements the smallest coherent code or content change.
- Validator lane: independently validates with deterministic evidence first and moves work to Review only after evidence passes. See [`docs/agent-work-validator-lane.md`](./agent-work-validator-lane.md).
- Docs/Evidence lane: preserves manager-facing hubs, screenshots, validation logs, and review notes. See [`docs/agent-work-docs-evidence-lane.md`](./agent-work-docs-evidence-lane.md).
- Coordinator lane: splits stories, routes work, manages status hygiene, plans worker pools, and escalates blockers. See [`docs/agent-work-coordinator-lane.md`](./agent-work-coordinator-lane.md).

## Give An Agent The Prompt

Generate the exact prompt for a task:

```bash
cento agent-work prompt 123
cento agent-work prompt 123 --output workspace/runs/agent-work/issue-123-prompt.md
```

The prompt includes the issue title, node, owner, package, description, and update protocol.

## Dispatch Through Cento Cluster

Dry-run first:

```bash
cento agent-work dispatch 123 --node linux --agent codex --dry-run
```

Actual dispatch starts a detached tmux session on the target node through `cento cluster exec`:

```bash
cento agent-work dispatch 123 --node linux --agent codex
```

The dispatch writes a local bundle under `workspace/runs/agent-work/<run-id>/` and copies the prompt into the target node's repo workspace. The target tmux session runs `codex exec` with the default background model `gpt-5.3-codex-spark` unless you pass `--model`.

```bash
cento agent-work dispatch 123 --node linux --agent codex --model gpt-5.3-codex-spark
```

## Spark Worker Pool

Use `dispatch-pool` to keep cheap Spark/Codex workers busy without interrupting the main operator session. It is plan-only by default and does not start agents unless `--execute` is passed.

Plan the next three queued items:

```bash
cento agent-work dispatch-pool --limit 3
```

Plan queued work for one package:

```bash
cento agent-work dispatch-pool --package spark-docs-evidence-lane --limit 2
```

Start the planned Spark workers explicitly:

```bash
cento agent-work dispatch-pool --limit 2 --runtime codex --model gpt-5.3-codex-spark --execute
```

For automation and dashboards:

```bash
cento agent-work dispatch-pool --limit 5 --json
```

The JSON output includes `diagnostics`, including `zero_launch_reason`, so a zero-worker result explains whether the cause was no matching status, filters, companion-node exclusion, non-task epics, or `--limit 0`.

Check what is actually running:

```bash
cento cluster activity linux
cento cluster activity --json linux
```

The Taskstream issue tracks assignment and lifecycle. `cluster activity` tracks the live node state: tmux sessions, Codex processes, and recent pane text.

Dispatch also writes a durable run ledger under `workspace/runs/agent-runs/<run-id>/run.json`:

```bash
cento agent-work runs
cento agent-work runs --json --active
cento agent-work run-status RUN_ID --json
```

`runs` reconciles ledger entries with `ps`/tmux health and reports interactive Codex or Claude Code sessions without a ledger as `untracked_interactive`. The Industrial OS pane labels those as `MANUAL`: real local agent shells that cannot yet be attached to an issue, prompt, or log. The pane also shows tracked Taskstream work first so the manager view remains useful before every agent launch flows through the ledger wrapper.

The cluster command path still prefers the OCI Unix-socket mesh. If that socket is stale, `cento cluster exec linux` now falls back to direct LAN SSH at `alice@alisapad.local`, which keeps dispatch and activity usable while the relay repairs itself.

## Recovery Plan

When the board has no queued work, many blocked items, or confusing run state, use the recovery planner before creating more issues:

```bash
cento agent-work recovery-plan
cento agent-work recovery-plan --json
```

It summarizes queued, blocked, review, running, validating, active-run, and stale-run counts, then suggests bounded unblock actions. The command is read-only by default.

If the board is genuinely stalled, it can create one guarded self-improvement follow-up:

```bash
cento agent-work recovery-plan --create-followup
```

The create path has duplicate-task and cooldown guards. Use `--force-create` only when intentionally bypassing those guards.

## Pool Hygiene

Use the pool kicker when the board has queued builder, validator, small evidence, or coordinator work and the active run targets are below capacity:

```bash
cento agent-pool-kick --dry-run
cento agent-pool-kick --max-launch 3
cento agent-pool-kick --max-launch 3 --model gpt-5.3-codex-spark
```

It writes the latest summary to:

```text
~/.local/state/cento/agent-pool-kick-latest.json
```

The default launch model is `gpt-5.3-codex-spark`, with `CENTO_POOL_CODEX_MODEL`, `CENTO_AGENT_MODEL`, or `--model` available when the pool needs a different Codex runtime.

Use the hygiene report before launching more workers when capacity looks wrong, workers went stale, or blocked state is confusing:

```bash
cento agent-work-hygiene
cento agent-work-hygiene --issue 94
```

The report includes run ledger JSON, tmux sessions, process probes, stale counts, and minimal reconciliation suggestions under `workspace/runs/agent-work/reconciliation/`.

## Cento Console UI

The web UI is the Cento Console. Taskstream is its first fully interactive area:

- Project identifier: `cento-agent-work`
- App command: `make agent-work-app-status`
- Local Linux app URL: shown by `make agent-work-app-status`
- Main sections: `Taskstream`, `Cluster`, `Consulting`, `Docs`
- Taskstream sections: `Issues`, `Review`

## MVP Limits

- Taskstream is the main tasking backend for Cento agent work.
- Dispatch expects the target node to have `codex`, `tmux`, and a usable Cento checkout. If the target checkout has not been updated with `agent-work`, the Codex run still starts, but final status updates from inside the tmux job may be skipped.
- Parent/child hierarchy is represented by the `Cento Work Package` field.

## Verification

Run the E2E probe:

```bash
make agent-work-e2e
```

It bootstraps Taskstream, creates a unique issue, claims it, moves it to review, generates a dry-run dispatch bundle, closes the issue, and confirms it appears in `list --all`.
