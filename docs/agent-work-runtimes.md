# Agent Work Runtimes

Cento agent-work dispatch supports weighted local agent runtimes.

## Registered Runtimes

Runtime registry: `data/agent-runtimes.json`

- `codex`
  - Provider: OpenAI
  - Default model: `gpt-5.3-codex-spark`
  - Weight: `0`
  - Role: temporarily disabled while Codex weekly limit is reserved for interactive coordination

- `claude-code`
  - Provider: Anthropic
  - Default model: `claude-sonnet-4-6`
  - Plan: personal Pro
  - Weight: `100`
  - Role: temporary Claude-only runtime for automatic task dispatches

## Routing

Automatic routing is deterministic and weighted by issue id, role, and package.

```bash
python3 scripts/agent_work.py runtimes --sample 1000
```

Expected result while Claude-only mode is active:

- Claude Code: `100%`

## Dispatch Examples

Automatic weighted route:

```bash
python3 scripts/agent_work.py dispatch ISSUE_ID --dry-run
```

Forced Claude Code:

```bash
python3 scripts/agent_work.py dispatch ISSUE_ID --runtime claude-code --dry-run
```

Forced Codex:

```bash
python3 scripts/agent_work.py dispatch ISSUE_ID --runtime codex --dry-run
```

Spark worker pool planning:

```bash
python3 scripts/agent_work.py dispatch-pool --limit 3
```

`dispatch-pool` honors `CENTO_AGENT_RUNTIME` and currently defaults to `claude-code`. It prints planned dispatch commands without mutating issues. Add `--execute` only when the operator wants workers started.

## Overrides

- `CENTO_AGENT_RUNTIME=claude-code` forces the runtime when dispatch uses `--runtime auto`.
- `CENTO_AGENT_RUNTIME_CONFIG=/path/to/agent-runtimes.json` uses a different runtime registry.
- `CENTO_CLAUDE_BIN=/path/to/claude` overrides the Claude Code binary.
- `CENTO_CODEX_BIN=/path/to/codex` overrides the Codex binary.

## Cost Policy

Claude-only mode is temporary. Restore the Codex weights when the weekly limit is no longer constrained.
