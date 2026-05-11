# Claude Code Chores

Claude Code chores are a controlled Cento maintenance loop for using otherwise idle Claude Code subscription capacity on small repo-local work. The loop is native Cento plumbing: it discovers chores, creates Taskstream issues with story and validation manifests, and launches workers through `agent-work` and `agent-pool-kick`.

## Command Surface

- `cento claude-chores plan --scope broad-repo --json`
- `cento claude-chores run --scope broad-repo --chore-limit 2 --max-launch 2 --runtime claude-code --model claude-sonnet-4-6 --json`
- `cento claude-chores run --scope broad-repo --chore-limit 2 --max-launch 2 --dry-run --json`
- `cento claude-chores status --json`
- `cento claude-chores install-cron --interval-minutes 30 --json`
- `cento claude-chores uninstall-cron --json`

## Default Policy

- Cadence: every 30 minutes when the managed cron block is installed.
- Per tick: create at most 2 new chores and launch at most 2 new Claude Code jobs.
- Active targets: `builder=2`, `small=1`, `validator=1`, `coordinator=0`.
- Runtime/model: `claude-code` with `claude-sonnet-4-6`.
- Package filter: worker launch is constrained to the `claude-chores` package, so cron does not dispatch unrelated queued work.
- Spend policy: this loop uses agent subscription capacity and does not route chores through metered OpenAI API workers.

When Codex/Claude weekly utilization is above 30%, eligible non-API-only work should prefer agent lanes in roughly 70-80% of cases. Claude chores implement that preference for maintenance work by forcing Claude Code, keeping API spend at zero, and using small validation-focused tasks.

## Chore Sources

The broad repo scanner looks for deterministic maintenance work:

- missing registered tool entrypoints, such as a registry entry whose script path is absent;
- docs/CLI drift, such as stale references to removed commands;
- TODO/FIXME hotspots in `scripts/`, `docs/`, `tests/`, and `data/`;
- blocked Taskstream issues that need manifest repair, clearer owned paths, or a closure recommendation.

Each candidate receives a stable fingerprint. Open `claude-chores` issues with the same `[chore:<fingerprint>]` prefix block duplicate creation on later cron ticks.

## Artifacts

Each `plan` or `run` writes:

- `workspace/runs/claude-chores/<timestamp>/candidate_chores.json`
- `workspace/runs/claude-chores/<timestamp>/created_issues.json`
- `workspace/runs/claude-chores/<timestamp>/dispatch_summary.json`
- `workspace/runs/claude-chores/<timestamp>/claude-code-chores.md`
- `workspace/runs/claude-chores/<timestamp>/status.json`
- `workspace/runs/claude-chores/latest/status.json`

The run Markdown includes a process benefit scan from native Cento state instead of messaging unrelated untracked Codex processes. That keeps the loop auditable and avoids interrupting live interactive sessions.

## Cron

`cento claude-chores install-cron --interval-minutes 30 --json` installs a guarded block between:

- `# >>> cento claude-chores >>>`
- `# <<< cento claude-chores <<<`

The cron command uses `flock` and logs to `~/.local/state/cento/claude-chores.log`. Existing cron blocks are preserved. Use `--crontab-file` for tests and dry-run validation so the real crontab is not modified.
