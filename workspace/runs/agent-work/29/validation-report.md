# Runtime Registration Validation

Generated: 2026-04-30T02:29:00Z

Ticket: #29 Improve Dev Process: Register Claude Code weighted agent runtime

## Result

PASS

## Checks

- `data/agent-runtimes.json` parses as valid JSON.
- `scripts/agent_work.py` compiles with `python3 -m py_compile`.
- Runtime registry includes `codex` at weight 75 with model `gpt-5.3-codex-spark`.
- Runtime registry includes `claude-code` at weight 25 with model `claude-sonnet-4-6`.
- Weighted sample over 1000 deterministic issue routes selected Codex 740 times and Claude Code 260 times.
- Forced Claude Code dry-run dispatch selected `runtime=claude-code`, `node=linux`, and `model=claude-sonnet-4-6`.
- Forced Codex dry-run dispatch selected `runtime=codex`, `node=linux`, and `model=gpt-5.3-codex-spark`.
- The same validation was run through the Linux node via `cento bridge to-linux`.

## Evidence

- `logs/agent-runtimes-json.log`
- `logs/runtimes-sample.json`
- `logs/dispatch-claude-dry-run.log`
- `logs/dispatch-codex-dry-run.log`
- `logs/linux-validation.log`
