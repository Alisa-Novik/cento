# Cento Agent Work

Readable HTML guide: [`docs/agent-work.html`](./agent-work.html).

`cento agent-work` turns the Linux Redmine stack into a small Jira-style board for Cento agents. The MVP is intentionally direct: Cento writes to the trusted local Redmine Postgres container over SSH, so it works without hunting for a Redmine API key.

## What It Creates

- Redmine project: `cento-agent-work`
- Trackers: `Agent Epic`, `Agent Task`
- Statuses: `Queued`, `Running`, `Review`, `Blocked`, `Done`
- Custom fields: `Agent Node`, `Agent Owner`, `Agent State`, `Cento Work Package`, `Cluster Dispatch`
- Local run bundles: `workspace/runs/agent-work/<run-id>/`

This is the operating model:

1. You create or split work into Redmine issues.
2. Each task gets a node, agent owner, package, status, and work instructions.
3. Agents claim tasks, update status, and leave notes in Redmine.
4. You inspect Redmine, `cento agent-work list`, and `cento cluster activity` to see what is assigned and what is actually running.

## Bootstrap

Run this once from the Mac or Linux node:

```bash
cento agent-work bootstrap
```

It is safe to run again. The command creates anything missing and leaves existing Redmine data in place.

On macOS, Redmine database access uses `alice@alisapad.local` when that LAN route is available, then falls back to `cento cluster exec linux`. Override this when needed:

```bash
CENTO_REDMINE_TRANSPORT=cluster cento agent-work list
CENTO_REDMINE_SSH=alice@alisapad.local cento agent-work list
```

## Create One Task

```bash
cento agent-work create \
  --title "Improve mission control pane" \
  --description "Add a compact running-agent summary and link it to cluster activity." \
  --node linux \
  --agent codex \
  --package mission-control
```

List active work:

```bash
cento agent-work list
```

Show a task:

```bash
cento agent-work show 123
```

## Split Work Across The Cluster

Use `split` when you want one package of work spread across nodes:

```bash
cento agent-work split \
  --title "Mission control MVP" \
  --goal "Track what agents are doing as first-class Redmine work." \
  --nodes linux,macos \
  --task "Create Redmine-backed task model and CLI" \
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
cento agent-work update 123 --status blocked --note "Blocked waiting for Redmine access."
cento agent-work update 123 --status done --note "Verified and closed."
```

Use `Review` for code that is ready for human inspection. Use `Done` only after verification.

## Agent Lanes

Cento work scales by separating ownership:

- Builder lane: implements the smallest coherent code or content change.
- Validator lane: independently validates and moves work to Review only after evidence passes. See [`docs/agent-work-validator-lane.md`](./agent-work-validator-lane.md).
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

The Redmine issue tracks assignment and lifecycle. `cluster activity` tracks the live node state: tmux sessions, Codex processes, and recent pane text.

Dispatch also writes a durable run ledger under `workspace/runs/agent-runs/<run-id>/run.json`:

```bash
cento agent-work runs
cento agent-work runs --json --active
cento agent-work run-status RUN_ID --json
```

`runs` reconciles ledger entries with `ps`/tmux health and reports interactive Codex or Claude Code sessions without a ledger as `untracked_interactive`. The Industrial OS pane labels those as `MANUAL`: real local agent shells that cannot yet be attached to an issue, prompt, or log. The pane also shows tracked Redmine work first so the manager view remains useful before every agent launch flows through the ledger wrapper.

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

## Redmine UI

The existing Linux Redmine stack is the visual board:

- Container: `cento-redmine`
- Project identifier: `cento-agent-work`
- Local Linux URL: `http://127.0.0.1:47874`

If you expose the Redmine port through your existing tunnel or browser path, use the `Cento Agent Work` project as the board.

## MVP Limits

- This MVP writes directly to the trusted local Redmine database over local SSH or the Cento cluster SSH mesh. It is meant for your self-hosted Redmine stack, not a shared production Redmine.
- Dispatch expects the target node to have `codex`, `tmux`, and a usable Cento checkout. If the target checkout has not been updated with `agent-work`, the Codex run still starts, but final status updates from inside the tmux job may be skipped.
- Parent/child hierarchy is represented by the `Cento Work Package` field in the MVP. A future version can add native Redmine parent links or a REST API backend.

## Verification

Run the E2E probe:

```bash
make agent-work-e2e
```

It bootstraps Redmine, creates a unique issue, claims it, moves it to review, generates a dry-run dispatch bundle, closes the issue, and confirms it appears in `list --all`.
