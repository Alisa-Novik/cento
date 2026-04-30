# Agent Work Runtimes

Cento agent-work dispatch supports weighted local agent runtimes.

## Registered Runtimes

Runtime registry: `data/agent-runtimes.json`

- `codex`
  - Provider: OpenAI
  - Default model: `gpt-5.3-codex-spark`
  - Weight: `75`
  - Role: preferred majority runtime

- `claude-code`
  - Provider: Anthropic
  - Default model: `claude-sonnet-4-6`
  - Plan: personal Pro
  - Weight: `25`
  - Role: secondary runtime for roughly 20-30% of automatic task dispatches

## Routing

Automatic routing is deterministic and weighted by issue id, role, and package.

```bash
python3 scripts/agent_work.py runtimes --sample 1000
```

Expected result should stay near:

- Codex: about 70-80%
- Claude Code: about 20-30%

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

## Overrides

- `CENTO_AGENT_RUNTIME=claude-code` forces the runtime when dispatch uses `--runtime auto`.
- `CENTO_AGENT_RUNTIME_CONFIG=/path/to/agent-runtimes.json` uses a different runtime registry.
- `CENTO_CLAUDE_BIN=/path/to/claude` overrides the Claude Code binary.
- `CENTO_CODEX_BIN=/path/to/codex` overrides the Codex binary.

## Cost Policy

Codex remains the primary runtime. Claude Code is registered at 25% because its budget is materially lower.
