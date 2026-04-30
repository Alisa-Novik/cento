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
cento agent-work dispatch ISSUE --runtime claude-code --dry-run
cento agent-work dispatch-pool --limit 3
```

`runs` also scans `ps` for interactive Codex and Claude Code sessions that do not have a ledger record. In JSON those are `untracked_interactive`; in the Industrial OS pane they are shown as `MANUAL` because they are real local agent shells, but Cento cannot attach them to an issue, prompt, or log path.

`dispatch-pool` is the safe way to prepare several cheap Spark/Codex workers. It is plan-only by default, so it does not create run ledger entries until the operator passes `--execute`.

For runs dispatched to another node, Mac-side `runs` and `run-status` perform a bounded remote lookup before marking the local ledger stale. Mac-side `runs` also appends Linux's own run ledger so the manager view can see Linux-local pool workers that were launched from Linux and never had a Mac-side ledger record. A Linux run that is still active remotely reports `remote_running`; a finished remote run reports the remote health such as `remote_ok`. Use `--no-remote-reconcile` when you need a strictly local, no-SSH view.

This distinction matters during pool work:

- `cento agent-work runs --json --active` is the cluster-aware manager view.
- `cento agent-work runs --json --active --no-remote-reconcile` is the local-only view.
- If the local-only view is empty but the cluster-aware view has Linux records, workers exist but were launched from another node.
- If both views are empty and the board has queued work, the pool is not dispatching.

## Industrial OS Pane

The main Industrial OS workspace now uses an Agents pane in the old Activity pane slot:

```sh
./scripts/industrial_aux_tui.sh agents --once
```

The pane displays tracked Redmine work first, then manual local Codex/Claude sessions. This keeps the manager view useful even before all agents are launched through the ledger wrapper.
