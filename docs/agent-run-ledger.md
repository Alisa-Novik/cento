# Agent Run Ledger

`cento agent-work runs` shows what Cento agents are doing now.

The ledger lives under:

```text
workspace/runs/agent-runs/<run_id>/run.json
```

Each run records issue, package, node, runtime, model, command, pid, tmux session, status, prompt path, log path, cwd, and git head.

## Commands

```sh
cento agent-work runs
cento agent-work runs --json --active
cento agent-work run-status RUN_ID --json
cento agent-work recovery-plan
cento agent-work dispatch ISSUE --runtime claude-code --dry-run
```

Reconcile stale entries and capture proof artifacts in one shot:

```sh
./scripts/agent_work_hygiene.sh --out-dir workspace/runs/agent-work/reconciliation
```

The script runs:

1. `cento agent-work runs --json --reconcile`
2. `tmux list-sessions -F '#{session_name}\t#{session_created}\t#{session_attached}'`
3. `ps` probe for interactive Codex/Claude/`agent_work.py` processes

This is the evidence bundle expected for visibility audits: reconciled runs JSON,
tmux session snapshot, and a short `hygiene-report.md` with minimal fix suggestions.
The reconciliation step now promotes stale entries back to `running` when their
pid or tmux session is still alive, so the report only flags runs that are truly dead.

Agent Manager owns the safe cleanup path for historical stale rows:

```sh
make agent-manager-janitor ARGS="--dry-run --json"
make agent-manager-janitor ARGS="--apply --json"
```

The janitor archives only stale ledgers attached to Done issues. Stale ledgers for
open issues remain visible as actionable risk, because they may need validation,
requeue, blocker triage, or a follow-up ticket.

`runs` also scans `ps` for interactive Codex and Claude Code sessions that do not have a ledger record. In JSON those are `untracked_interactive`; in the Industrial OS pane they are shown as `MANUAL` because they are real local agent shells, but Cento cannot attach them to an issue, prompt, or log path.

`recovery-plan` is the board recovery companion: it summarizes blocked/review pressure, stale runs, manual shells, blocker causes, and safe next commands. In report-only mode it also writes a before/after board snapshot plus guardrails; `--apply` is bounded to requeueing stale blocked work and creating at most three small follow-up tasks when the blocker is an internal Cento gap or an explicit split-needed case.

## Industrial OS Pane

The main Industrial OS workspace now uses an Agents pane in the old Activity pane slot:

```sh
./scripts/industrial_aux_tui.sh agents --once
```

The pane displays tracked Redmine work first, then manual local Codex/Claude sessions. This keeps the manager view useful even before all agents are launched through the ledger wrapper.
