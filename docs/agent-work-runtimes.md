# Agent Work Runtimes

Cento agent-work dispatch supports weighted local agent runtimes.

## Registered Runtimes

Runtime registry: `data/agent-runtimes.json`
Local command runtime profiles: `.cento/runtimes.yaml`

- `codex`
  - Provider: OpenAI
  - Default model: `gpt-5.3-codex-spark`
  - Weight: controlled by `cento compute-policy`
  - Role: preferred when Codex limit/subscription capacity is available

- `claude-code`
  - Provider: Anthropic
  - Default model: `claude-sonnet-4-6`
  - Plan: personal Pro
  - Weight: controlled by `cento compute-policy`
  - Role: fallback or partial-share runtime for automatic task dispatches

- `claude-code-fast`
  - Surface: local command runtime profile for Workset/Build-style isolated worktrees
  - Command: `claude -p --output-format text`
  - Prompt delivery: stdin from the generated builder prompt
  - Role: Patch Swarm candidate provider adapter compatible with `candidate_patch.v1` receipts

## Routing

Automatic routing is deterministic and weighted by issue id, role, and package.

```bash
python3 scripts/agent_work.py runtimes --sample 1000
```

Expected result for the default `codex-first` policy:

- Codex: about `85%`
- Claude Code: about `15%`

To change this mix:

```bash
cento compute-policy set --codex 70 --claude 30 --openai-api 0 --json
cento agent-work runtimes --sample 1000 --json
```

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
cento agent-pool-kick --dry-run --max-launch 3
```

`agent-pool-kick` honors `CENTO_AGENT_RUNTIME` when set. Otherwise it uses Agent Work `auto` routing and the current compute-policy weights.

## Overrides

- `CENTO_AGENT_RUNTIME=claude-code` forces the runtime when dispatch uses `--runtime auto`.
- `CENTO_AGENT_RUNTIME=codex` forces Codex.
- `CENTO_AGENT_RUNTIME_CONFIG=/path/to/agent-runtimes.json` uses a different runtime registry.
- `CENTO_CLAUDE_BIN=/path/to/claude` overrides the Claude Code binary.
- `CENTO_CODEX_BIN=/path/to/codex` overrides the Codex binary.

## Cost Policy

Use `cento compute-policy` to prefer available agent subscription/limit before metered API calls:

```bash
cento compute-policy preset codex-first --json
```

Explicit `api-openai` commands remain explicit API spend.
