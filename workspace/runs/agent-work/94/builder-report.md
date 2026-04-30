# Issue 94 Builder Report

Status: ready for validation
Generated: 2026-04-30

## Objective

Reconcile useful Linux-side pool tooling into Mac/origin main without pulling, resetting, or overwriting the dirty Linux checkout.

## Coordination

- Ran Mac context refresh and confirmed Linux was reachable.
- Asked Claude Code on Linux for a porting note before touching Mac files.
- Saved the Claude coordination note at `workspace/runs/agent-work/94/claude-issue94-porting-note-20260430.md`.
- Followed the recommendation to port only the self-contained untracked pool scripts and leave the high-risk Linux `scripts/agent_work.py` dual-backend changes untouched.

## Changes

- Added `scripts/agent_pool_kick.py`.
  - Keeps builder, validator, small-worker, and coordinator lanes moving with per-lane targets.
  - Uses active run ledgers to avoid dispatching issues that already have live runs.
  - Supports `--dry-run`, `--max-launch`, target flags, and `--model`.
  - Defaults to `gpt-5.3-codex-spark`, overridable by `CENTO_POOL_CODEX_MODEL`, `CENTO_AGENT_MODEL`, or `--model`.
- Added `scripts/agent_work_hygiene.sh`.
  - Captures run ledger reconciliation, tmux sessions, process probes, stale counts, and minimal cleanup suggestions.
- Registered both tools in `data/tools.json`.
- Regenerated `docs/tool-index.md` and `docs/platform-support.md`.
- Updated `docs/agent-work.md` with pool hygiene usage.

## Evidence

- Pool dry-run: `workspace/runs/agent-work/94/agent-pool-kick-dry-run-latest.json`
- Scoped hygiene report: `workspace/runs/agent-work/94/hygiene-issue94/hygiene-20260430-095503/hygiene-report.md`
- Recovery snapshot: `workspace/runs/agent-work/94/recovery-plan-after-port.json`
- Claude note: `workspace/runs/agent-work/94/claude-issue94-porting-note-20260430.md`

## Validation

Passed:

```bash
python3 scripts/tool_index.py --registry data/tools.json --output docs/tool-index.md
python3 scripts/platform_report.py --markdown --output docs/platform-support.md
python3 -m py_compile scripts/agent_pool_kick.py scripts/agent_work.py
bash scripts/agent_work_hygiene.sh --help
cento agent-pool-kick --dry-run --max-launch 2
cento agent-work-hygiene --issue 94 --out-dir workspace/runs/agent-work/94/hygiene-issue94
python3 -m json.tool workspace/runs/agent-work/94/agent-pool-kick-dry-run-latest.json
```

Latest pool dry-run used `gpt-5.3-codex-spark` and planned two bounded launches: validator issue 15 and coordinator issue 52.

## Not Ported

- Linux dirty `scripts/agent_work.py` dual-backend migration.
- Linux untracked `scripts/agent_work_app.py`.
- Linux runtime workspace artifacts.

Those require a separate merge plan because Linux is behind origin/main and has substantial local dirty work.
