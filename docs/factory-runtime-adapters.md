# Factory Runtime Adapters

`factory-runtime-adapters-v1` defines the contract between Factory Autopilot and bounded worker runtimes. It is contract-first and does not enable broad live execution, high fanout, automatic retries, automatic Taskstream Done transitions, automatic integration apply, or merges.

## Commands

```bash
cento factory runtime list --json
cento factory runtime prepare RUN_ID --task TASK_ID --runtime noop --dry-run
cento factory runtime launch RUN_ID --task TASK_ID --runtime noop --dry-run
cento factory runtime status RUN_ID --task TASK_ID --json
cento factory runtime collect RUN_ID --task TASK_ID
cento factory runtime cancel RUN_ID --task TASK_ID --dry-run
```

## Adapters

- `noop`: records the full lifecycle without side effects.
- `local-shell-fixture`: writes a deterministic patch bundle for zero-AI validation.
- `codex-dry-run`: renders the Codex command, prompt, and environment without executing Codex.

## Artifacts

Each adapter run writes under `workspace/runs/factory/<run-id>/runtime/<task-id>/`:

- `adapter-run.json`
- `launch-plan.json`
- `worker-ledger.json`
- `heartbeat.json`
- `status.json`
- `cost.json`
- `stdout.log`
- `stderr.log`
- `patch/patch.diff`
- `patch/changed-files.txt`
- `patch/diffstat.txt`
- `patch/patch.json`
- `collect-result.json`

## Safety

Runtime v1 records `dry_run_command`, `execute_command`, `execute_supported`, `unsupported_execute_reason`, and `side_effects_if_execute` in `launch-plan.json`. This prevents dry-run behavior from implying that live execution is safe or implemented.

Adapter output is collected into Factory patch artifacts only after the adapter writes the required patch bundle. Factory validation and integration remain separate gates.
