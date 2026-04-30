# Agent Run Ledger Hygiene Audit

Generated: 2026-04-30T13:55:05.061321+00:00
Run artifact directory: workspace/runs/agent-work/94/hygiene-issue94/hygiene-20260430-095503

## Command sequence

1) `cento agent-work runs --json --reconcile` (optionally with `--issue`)
2) `tmux list-sessions -F '#{session_name}\t#{session_created}\t#{session_attached}'`
3) `ps -eo pid=,ppid=,command= | grep -E '(^|/)(codex|claude|agent_work.py)'`

## Scope

- issue_id filter: 94
- stale reconciliation: enabled (`--reconcile`)
- runs count: 1
- stale count: 0

## Status counts

- failed: 1

## Stale run entries

- None.

## Minimal reconciliation fix suggestion

- No stale runs detected in reconciled snapshot.

## Evidence artifacts

- runs JSON: `workspace/runs/agent-work/94/hygiene-issue94/hygiene-20260430-095503/agent-work-runs.json`
- tmux sessions: `workspace/runs/agent-work/94/hygiene-issue94/hygiene-20260430-095503/tmux-sessions.txt`
- process probe: `workspace/runs/agent-work/94/hygiene-issue94/hygiene-20260430-095503/process-probe.txt`
