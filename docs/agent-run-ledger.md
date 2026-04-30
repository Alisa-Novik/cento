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
```

`runs` also scans `ps` for interactive Codex and Claude Code sessions that do not have a ledger record. In JSON those are `untracked_interactive`; in the Industrial OS pane they are shown as `MANUAL` because they are real local agent shells, but Cento cannot attach them to an issue, prompt, or log path.

## Industrial OS Pane

The main Industrial OS workspace now uses an Agents pane in the old Activity pane slot:

```sh
./scripts/industrial_aux_tui.sh agents --once
```

The pane displays tracked Redmine work first, then manual local Codex/Claude sessions. This keeps the manager view useful even before all agents are launched through the ledger wrapper.
